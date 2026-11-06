"""Base entity for the NewMotion Local integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NewMotionCoordinator

MODELS = {"HOMEADVANCED": "Home Advanced"}


class NewMotionEntity(CoordinatorEntity[NewMotionCoordinator]):
    """Entity tied to one charger."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NewMotionCoordinator, key: str) -> None:
        """Set up device info shared by all entities of the charger."""
        super().__init__(coordinator)
        raw = coordinator.data.state.raw
        cpid = coordinator.data.state.charge_point_id
        model = str(raw.get("model") or "")
        self._attr_unique_id = f"{cpid}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cpid)},
            manufacturer=MANUFACTURER,
            model=MODELS.get(model, model.title() or None),
            model_id=model or None,
            name=f"{MANUFACTURER} {cpid}",
            serial_number=str(raw.get("serial") or cpid),
            sw_version=raw.get("version"),
        )
