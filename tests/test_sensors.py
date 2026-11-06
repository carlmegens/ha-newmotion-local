"""Entity tests: set up the integration against the mock charger."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.newmotion_local.const import DOMAIN

CPID = "07999999"


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{CPID}-{key}"
    )
    assert entity_id is not None, key
    return entity_id


def _state(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(_entity_id(hass, platform, key)).state


async def _setup(hass: HomeAssistant, host: str) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CPID, data={CONF_HOST: host})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _tick(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_charging(hass: HomeAssistant, charger) -> None:
    entry = await _setup(hass, charger.host)
    assert entry.state is ConfigEntryState.LOADED

    assert _state(hass, "sensor", "status") == "charging"
    assert _state(hass, "sensor", "charging_power") == "3.52"
    assert _state(hass, "sensor", "charging_current") == "5.11"
    assert _state(hass, "sensor", "active_phases") == "3"
    assert _state(hass, "sensor", "session_energy") == "2.27"
    assert _state(hass, "sensor", "energy_total") == "34698.44"
    assert _state(hass, "sensor", "current_limit") == "16.0"
    assert _state(hass, "sensor", "session_start") == "2026-11-06T18:45:04+00:00"
    assert _state(hass, "binary_sensor", "car_connected") == STATE_ON
    assert _state(hass, "binary_sensor", "charging") == STATE_ON
    assert _state(hass, "binary_sensor", "backend_connected") == STATE_ON
    assert _state(hass, "binary_sensor", "problem") == STATE_OFF

    status = hass.states.get(_entity_id(hass, "sensor", "status"))
    assert status.attributes["car_status"] == "Charging"

    # The integration must never change anything on the charger.
    assert {method for method, _ in charger.device.requests} == {"GET"}


async def test_session_progress_and_unplug(hass: HomeAssistant, charger) -> None:
    entry = await _setup(hass, charger.host)

    charger.device.consumed = 5000
    await _tick(hass, entry)
    assert _state(hass, "sensor", "session_energy") == "5.0"
    assert _state(hass, "sensor", "energy_total") == "34701.17"

    charger.device.state = "suspended"
    await _tick(hass, entry)
    assert _state(hass, "sensor", "status") == "connected"
    assert _state(hass, "sensor", "charging_power") == "0"
    assert _state(hass, "binary_sensor", "charging") == STATE_OFF
    assert _state(hass, "binary_sensor", "car_connected") == STATE_ON

    charger.device.state = "available"
    await _tick(hass, entry)
    assert _state(hass, "sensor", "status") == "available"
    assert _state(hass, "binary_sensor", "car_connected") == STATE_OFF
    assert _state(hass, "sensor", "session_energy") == "unknown"
    # The mock's finished-session list ends at the start reading, which is
    # lower than what we already saw: the total must not go backwards.
    assert _state(hass, "sensor", "energy_total") == "34701.17"


async def test_error(hass: HomeAssistant, charger) -> None:
    charger.device.state = "error"
    await _setup(hass, charger.host)
    assert _state(hass, "sensor", "status") == "error"
    assert _state(hass, "binary_sensor", "problem") == STATE_ON


async def test_unreachable_becomes_unavailable(hass: HomeAssistant, charger) -> None:
    entry = await _setup(hass, charger.host)
    await charger.server.close()
    await _tick(hass, entry)
    assert _state(hass, "sensor", "status") == STATE_UNAVAILABLE


async def test_setup_retries_when_unreachable(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CPID, data={CONF_HOST: "127.0.0.1:1"}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_redacts(hass: HomeAssistant, charger) -> None:
    from custom_components.newmotion_local.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = await _setup(hass, charger.host)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    status = diag["status"]
    assert status["imsi"] == "**REDACTED**"
    assert status["iccid"] == "**REDACTED**"
    assert status["connectors"][0]["transaction"]["token"] == "**REDACTED**"
    assert diag["meter_total_kwh"] == 34698.44
