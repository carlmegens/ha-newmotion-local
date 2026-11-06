"""A local HTTP mock of a NewMotion Home Advanced status server.

Payloads follow what a real Home Advanced (firmware 1.13.1.3) returns on
port 12800, with made-up identifiers. Run it standalone to try the
integration without a charger:

    python tools/mock_newmotion.py --port 12800 --state charging
"""

from __future__ import annotations

import argparse
import copy
from typing import Any

from aiohttp import web

CPID = "07999999"
METER_BEFORE = 34696170  # Wh, meter reading at the start of the open session

STATES = ("available", "charging", "suspended", "error")


def _connector(state: str, consumed: int) -> dict[str, Any]:
    connector: dict[str, Any] = {
        "id": 1,
        "type": "Type2 Cable",
        "status": "ON",
        "max": {"phases": "PHASE3", "current": 16.0, "currentArray": [16.0] * 3},
        "plugMax": {"phases": "PHASE3", "current": 53.0, "currentArray": [53.0] * 3},
        "limit": {
            "phases": "PHASE3",
            "current": 16.0,
            "currents": [16.0] * 3,
            "currentArray": [16.0] * 3,
        },
        "chargingRate": "Charging rate: 0kw 3 phase [0A pf ] ",
        "chargingNeed": "Need: 0kw 3 phase [0A ] ",
        "errors": [],
        "warnings": [],
    }
    if state == "available":
        return connector
    charging = state == "charging"
    connector["transaction"] = {
        "privateId": 11905,
        "publicId": "1500000000",
        "status": "CHARGING",
        "consumed": consumed,
        "token": "04AABBCCDDEEFF",
        "start": 1793990704347,
        "statusCar": "Charging" if charging else "Connected",
        "fullPotential": True,
    }
    if charging:
        connector["chargingRate"] = "Charging rate: 3.52kw 3 phase [5.11A 0.95pf ] "
        connector["chargingNeed"] = "Need: 36.57kw 3 phase [53A ] "
    if state == "error":
        connector["errors"] = ["RCD tripped"]
    return connector


def status_payload(state: str, consumed: int = 2270) -> dict[str, Any]:
    """Return a /user/status body for one of STATES."""
    return {
        "cpid": CPID,
        "serial": CPID,
        "model": "HOMEADVANCED",
        "imsi": "204040000000000",
        "iccid": "89310000000000000000",
        "meterSerial": "17000000",
        "meterType": "3f_Inepro",
        "ocppType": "JOCPP16",
        "ocppEndpoint": "wss://ws.evc-net.com/",
        "ocppProtocolType": "ocpp/json",
        "ocppStatus": "Accepted",
        "modemStatus": "Modem not active",
        "connectors": [_connector(state, consumed)],
        "maxLimit": {"phases": "PHASE3", "current": 32.0, "currentArray": [32.0] * 3},
        "status": "ON",
        "version": "1.13.1.3",
        "errors": [],
        "warnings": [],
    }


def transactions_payload(
    open_session: bool, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Return a /user/transactions body."""
    finished = [
        {
            "chargepointIdentity": CPID,
            "privateID": 11903,
            "id": 1503371130,
            "token": {"tokenCode": "04AABBCCDDEEFF"},
            "startDate": 1793793974000,
            "stopDate": 1793807841000,
            "status": "FINISHED",
            "meterStart": 34669870,
            "meterStop": 34683350,
            "currentEnergyAmount": 13480,
            "connector": 1,
        },
        {
            "chargepointIdentity": CPID,
            "privateID": 11904,
            "id": 1503410528,
            "token": {"tokenCode": "04AABBCCDDEEFF"},
            "startDate": 1793809277000,
            "stopDate": 1793896716000,
            "status": "FINISHED",
            "meterStart": 34683350,
            "meterStop": METER_BEFORE,
            "currentEnergyAmount": 12820,
            "connector": 1,
        },
    ]
    finished.extend(extra or [])
    if open_session:
        finished.append(
            {
                "chargepointIdentity": CPID,
                "privateID": 11905,
                "startDate": 1793990703000,
                "meterStart": METER_BEFORE,
                "currentEnergyAmount": 0,
                "connector": 1,
            }
        )
    return {"value": finished}


class MockNewMotion:
    """Serve /user/status and /user/transactions for a settable state."""

    def __init__(self, state: str = "charging") -> None:
        """Start in the given state."""
        self.state = state
        self.consumed = 2270
        self.extra_sessions: list[dict[str, Any]] = []
        self.requests: list[tuple[str, str]] = []

    def finish_session(self) -> None:
        """End the open session: the car is unplugged."""
        self.extra_sessions.append(
            {
                "chargepointIdentity": CPID,
                "privateID": 11905,
                "id": 1503500000,
                "token": {"tokenCode": "04AABBCCDDEEFF"},
                "startDate": 1793990703000,
                "stopDate": 1794020000000,
                "status": "FINISHED",
                "meterStart": METER_BEFORE,
                "meterStop": METER_BEFORE + self.consumed,
                "currentEnergyAmount": self.consumed,
                "connector": 1,
            }
        )
        self.state = "available"

    def app(self) -> web.Application:
        """Return the aiohttp application."""
        app = web.Application()
        app.router.add_route("*", "/user/status", self._status)
        app.router.add_route("*", "/user/transactions", self._transactions)
        return app

    async def _status(self, request: web.Request) -> web.Response:
        self.requests.append((request.method, request.path))
        if request.method != "GET":
            return web.Response(status=405)
        return web.json_response(
            copy.deepcopy(status_payload(self.state, self.consumed))
        )

    async def _transactions(self, request: web.Request) -> web.Response:
        self.requests.append((request.method, request.path))
        if request.method != "GET":
            return web.Response(status=405)
        return web.json_response(
            transactions_payload(self.state != "available", self.extra_sessions)
        )


def main() -> None:
    """Run the mock standalone."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=12800)
    parser.add_argument("--state", choices=STATES, default="charging")
    args = parser.parse_args()
    web.run_app(MockNewMotion(args.state).app(), port=args.port)


if __name__ == "__main__":
    main()
