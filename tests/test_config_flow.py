"""Config flow tests, run against the mock charger over real HTTP."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.newmotion_local.const import DOMAIN

CPID = "07999999"


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, charger) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f" {charger.host} "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"NewMotion {CPID}"
    assert result["data"] == {CONF_HOST: charger.host}
    assert result["result"].unique_id == CPID
    assert all(method == "GET" for method, _ in charger.device.requests)


async def test_user_flow_errors(hass: HomeAssistant, other_http) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1:1"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: other_http}
    )
    assert result["errors"] == {"base": "not_newmotion"}


async def test_already_configured_updates_host(hass: HomeAssistant, charger) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CPID, data={CONF_HOST: "10.0.0.1"})
    entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: charger.host}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == charger.host


async def test_reconfigure(hass: HomeAssistant, charger, other_http) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CPID, data={CONF_HOST: "10.0.0.1"})
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: other_http}
    )
    assert result["errors"] == {"base": "not_newmotion"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: charger.host}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == charger.host
    # The successful reconfigure reloads the entry; stop its polling timer.
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reconfigure_other_charger(hass: HomeAssistant, charger) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="12345678", data={CONF_HOST: "10.0.0.1"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: charger.host}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
