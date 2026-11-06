"""Read-only client for the local status server of NewMotion chargers.

NewMotion (Shell Recharge) Home Advanced chargers run a small HTTP server on
port 12800 on the local network, without authentication:

* ``GET /user/status``        live charger and connector status
* ``GET /user/transactions``  the last charging sessions with meter readings

This client only ever sends GET requests to those two paths. It never changes
anything on the charger, so the OCPP back office (and with it things like
reimbursement of charging costs) keeps working exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

import httpx

from .const import (
    DEFAULT_PORT,
    REQUEST_TIMEOUT,
    STATUS_AVAILABLE,
    STATUS_CHARGING,
    STATUS_CONNECTED,
    STATUS_ERROR,
)


class NewMotionError(Exception):
    """Base error for this client."""


class CannotConnect(NewMotionError):
    """The charger could not be reached."""


class NotNewMotion(NewMotionError):
    """Something answered, but it is not a NewMotion status server."""


# "Charging rate: 3.52kw 3 phase [5.11A 0.95pf ] "
_RATE_RE = re.compile(
    r"(?P<power>[\d.]+)\s*kw\s*(?P<phases>\d+)\s*phase\s*"
    r"\[\s*(?P<current>[\d.]+)\s*A(?:\s+(?P<pf>[\d.]+)\s*pf)?",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ChargingRate:
    """Values parsed from the free-text ``chargingRate`` field."""

    power_kw: float | None = None
    phases: int | None = None
    current: float | None = None
    power_factor: float | None = None


def parse_charging_rate(text: str | None) -> ChargingRate:
    """Parse ``Charging rate: 3.52kw 3 phase [5.11A 0.95pf ]``."""
    if not text or not (match := _RATE_RE.search(text)):
        return ChargingRate()
    pf = match.group("pf")
    return ChargingRate(
        power_kw=float(match.group("power")),
        phases=int(match.group("phases")),
        current=float(match.group("current")),
        power_factor=float(pf) if pf else None,
    )


def _ms_to_datetime(value: Any) -> datetime | None:
    if not isinstance(value, int | float) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _phase_current(block: Any) -> float | None:
    if isinstance(block, dict) and isinstance(block.get("current"), int | float):
        return float(block["current"])
    return None


@dataclass(slots=True)
class ChargerState:
    """A parsed snapshot of ``/user/status`` (first connector)."""

    raw: dict[str, Any]
    connector: dict[str, Any]
    rate: ChargingRate
    transaction: dict[str, Any] | None
    errors: list[Any] = field(default_factory=list)
    warnings: list[Any] = field(default_factory=list)

    @property
    def charge_point_id(self) -> str:
        """Return the charge point id, used as unique id."""
        return str(self.raw.get("cpid") or self.raw.get("serial"))

    @property
    def car_status(self) -> str | None:
        """Return the car status as reported by the charger (e.g. Charging)."""
        if self.transaction is None:
            return None
        return self.transaction.get("statusCar")

    @property
    def transaction_status(self) -> str | None:
        """Return the transaction status as reported (e.g. CHARGING)."""
        if self.transaction is None:
            return None
        return self.transaction.get("status")

    @property
    def car_connected(self) -> bool:
        """Return True while a session is open, i.e. a car is plugged in."""
        return self.transaction is not None

    @property
    def charging(self) -> bool:
        """Return True while energy flows to the car."""
        if self.transaction is None:
            return False
        if str(self.transaction.get("statusCar", "")).lower() == "charging":
            return True
        if str(self.transaction.get("status", "")).upper() == "CHARGING":
            return bool(self.rate.power_kw)
        return False

    @property
    def status(self) -> str:
        """Return one of the STATUS_* constants."""
        if self.errors:
            return STATUS_ERROR
        if self.charging:
            return STATUS_CHARGING
        if self.car_connected:
            return STATUS_CONNECTED
        return STATUS_AVAILABLE

    @property
    def session_energy_kwh(self) -> float | None:
        """Return the energy charged in the open session."""
        if self.transaction is None:
            return None
        consumed = self.transaction.get("consumed")
        if not isinstance(consumed, int | float):
            return None
        return round(consumed / 1000, 3)

    @property
    def session_start(self) -> datetime | None:
        """Return when the open session started."""
        if self.transaction is None:
            return None
        return _ms_to_datetime(self.transaction.get("start"))

    @property
    def transaction_id(self) -> Any:
        """Return the charger's id for the open session."""
        if self.transaction is None:
            return None
        return self.transaction.get("privateId")

    @property
    def current_limit(self) -> float | None:
        """Return the current limit per phase the charger offers right now."""
        return _phase_current(self.connector.get("limit"))

    @property
    def max_current(self) -> float | None:
        """Return the configured maximum current per phase."""
        return _phase_current(self.connector.get("max"))

    @property
    def backend_connected(self) -> bool:
        """Return True when the OCPP back office accepted the charger."""
        return str(self.raw.get("ocppStatus", "")).lower() == "accepted"


def parse_status(raw: dict[str, Any]) -> ChargerState:
    """Turn a ``/user/status`` payload into a ChargerState."""
    connectors = raw.get("connectors") or []
    connector = connectors[0] if connectors and isinstance(connectors[0], dict) else {}
    transaction = connector.get("transaction")
    if not isinstance(transaction, dict) or not transaction:
        transaction = None
    errors = [*(raw.get("errors") or []), *(connector.get("errors") or [])]
    warnings = [*(raw.get("warnings") or []), *(connector.get("warnings") or [])]
    return ChargerState(
        raw=raw,
        connector=connector,
        rate=parse_charging_rate(connector.get("chargingRate")),
        transaction=transaction,
        errors=errors,
        warnings=warnings,
    )


def meter_total_kwh(
    state: ChargerState, transactions: list[dict[str, Any]]
) -> float | None:
    """Return the lifetime meter reading of the charger in kWh.

    While a session runs this is its start reading plus what it consumed so
    far. Otherwise it is the stop reading of the most recent finished session.
    """
    if state.transaction is not None:
        current_id = state.transaction_id
        consumed = state.transaction.get("consumed")
        for tx in transactions:
            if (
                tx.get("privateID") == current_id
                and isinstance(tx.get("meterStart"), int | float)
                and isinstance(consumed, int | float)
            ):
                return round((tx["meterStart"] + consumed) / 1000, 3)
        return None

    readings = [
        (tx.get("stopDate") or 0, tx["meterStop"])
        for tx in transactions
        if isinstance(tx.get("meterStop"), int | float)
    ]
    if not readings:
        return None
    return round(max(readings)[1] / 1000, 3)


class NewMotionClient:
    """Read the status of one charger."""

    def __init__(self, client: httpx.AsyncClient, host: str) -> None:
        """Initialise the client. ``host`` may include ``:port``."""
        self._client = client
        self._host = host if ":" in host else f"{host}:{DEFAULT_PORT}"

    @property
    def host(self) -> str:
        """Return host:port of the charger."""
        return self._host

    async def _get(self, path: str) -> Any:
        url = f"http://{self._host}{path}"
        try:
            resp = await self._client.get(url, timeout=REQUEST_TIMEOUT)
        except httpx.HTTPError as err:
            raise CannotConnect(f"Error talking to {self._host}: {err}") from err
        if resp.status_code != 200:
            raise NotNewMotion(f"{url} answered HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as err:
            raise NotNewMotion(f"{url} did not return JSON") from err

    async def get_status(self) -> ChargerState:
        """Return the parsed live status."""
        raw = await self._get("/user/status")
        if not isinstance(raw, dict) or not (raw.get("cpid") or raw.get("serial")):
            raise NotNewMotion(f"{self._host} is not a NewMotion status server")
        return parse_status(raw)

    async def get_transactions(self) -> list[dict[str, Any]]:
        """Return the recent sessions (oldest first, as the charger sends them)."""
        raw = await self._get("/user/transactions")
        if isinstance(raw, dict):
            raw = raw.get("value")
        if not isinstance(raw, list):
            raise NotNewMotion(f"{self._host} returned unexpected transactions")
        return [tx for tx in raw if isinstance(tx, dict)]
