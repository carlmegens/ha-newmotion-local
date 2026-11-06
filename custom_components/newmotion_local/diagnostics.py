"""Diagnostics for the NewMotion Local integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import NewMotionConfigEntry

# Charging card ids and SIM identifiers are personal; leave them out.
TO_REDACT = {"imsi", "iccid", "token", "tokenCode", "publicId", "meterSerial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NewMotionConfigEntry
) -> dict[str, Any]:
    """Return the last status and session payloads, redacted."""
    data = entry.runtime_data.data
    return {
        "entry": dict(entry.data),
        "status": async_redact_data(data.state.raw, TO_REDACT),
        "transactions": async_redact_data(data.transactions[-5:], TO_REDACT),
        "meter_total_kwh": data.meter_total_kwh,
    }
