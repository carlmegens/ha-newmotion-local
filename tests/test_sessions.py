"""Session log: events for finished sessions and the last-session sensor."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.newmotion_local.const import DOMAIN, EVENT_SESSION_FINISHED

CPID = "07999999"


async def _setup(hass: HomeAssistant, host: str) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CPID, data={CONF_HOST: host})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _last_session(hass: HomeAssistant):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{CPID}-last_session"
    )
    return hass.states.get(entity_id)


async def test_existing_sessions_are_not_announced(
    hass: HomeAssistant, charger
) -> None:
    events: list[Event] = []
    hass.bus.async_listen(EVENT_SESSION_FINISHED, events.append)
    await _setup(hass, charger.host)
    assert events == []
    state = _last_session(hass)
    assert state.state == "12.82"
    assert state.attributes["session_id"] == "1503410528"


async def test_new_session_is_announced_once(hass: HomeAssistant, charger) -> None:
    events: list[Event] = []
    hass.bus.async_listen(EVENT_SESSION_FINISHED, events.append)
    entry = await _setup(hass, charger.host)

    charger.device.consumed = 30000
    charger.device.finish_session()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    data = events[0].data
    assert data["session_id"] == "1503500000"
    assert data["energy_kwh"] == 30.0
    assert data["start"] == "2026-11-06T18:45:03+00:00"
    assert data["config_entry_id"] == entry.entry_id
    assert data["device_id"] is not None
    assert _last_session(hass).state == "30.0"

    # Nothing new on the next refresh.
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_session_finished_while_down_is_announced(
    hass: HomeAssistant, charger
) -> None:
    entry = await _setup(hass, charger.host)
    assert await hass.config_entries.async_unload(entry.entry_id)

    # The car is unplugged while the integration is not running.
    charger.device.finish_session()

    events: list[Event] = []
    hass.bus.async_listen(EVENT_SESSION_FINISHED, events.append)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [e.data["session_id"] for e in events] == ["1503500000"]
