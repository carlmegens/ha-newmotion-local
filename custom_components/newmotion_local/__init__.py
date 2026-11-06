"""NewMotion Local: read-only local status of NewMotion / Shell Recharge chargers.

Reads the status server the charger runs on port 12800 of the local network.
Nothing on the charger is changed, so the OCPP back office keeps working.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .api import NewMotionClient
from .coordinator import NewMotionConfigEntry, NewMotionCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NewMotionConfigEntry) -> bool:
    """Set up a charger from a config entry."""
    client = NewMotionClient(get_async_client(hass), entry.data[CONF_HOST])
    coordinator = NewMotionCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NewMotionConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
