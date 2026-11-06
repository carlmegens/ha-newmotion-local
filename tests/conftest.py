"""Fixtures: a real local HTTP mock of a NewMotion status server."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
import sys

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from mock_newmotion import MockNewMotion  # noqa: E402


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


@pytest.fixture(autouse=True)
def allow_local_sockets(socket_enabled):
    """The mock charger is a real HTTP server on 127.0.0.1."""
    return


class RunningMock:
    """A started mock charger plus its host:port."""

    def __init__(self, device: MockNewMotion, server: TestServer) -> None:
        self.device = device
        self.server = server

    @property
    def host(self) -> str:
        return f"127.0.0.1:{self.server.port}"


@pytest.fixture
async def charger() -> AsyncIterator[RunningMock]:
    """A charger with a car plugged in and charging."""
    device = MockNewMotion("charging")
    server = TestServer(device.app(), host="127.0.0.1")
    await server.start_server()
    yield RunningMock(device, server)
    await server.close()


@pytest.fixture
async def other_http() -> AsyncIterator[str]:
    """Some other HTTP server: everything is 404."""

    async def not_found(request: web.Request) -> web.Response:
        return web.Response(status=404)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", not_found)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    yield f"127.0.0.1:{server.port}"
    await server.close()
