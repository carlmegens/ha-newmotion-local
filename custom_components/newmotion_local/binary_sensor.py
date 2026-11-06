"""Binary sensors for NewMotion chargers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NewMotionConfigEntry, NewMotionCoordinator, NewMotionData
from .entity import NewMotionEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NewMotionBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a charger binary sensor."""

    value_fn: Callable[[NewMotionData], bool]
    attrs_fn: Callable[[NewMotionData], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[NewMotionBinarySensorDescription, ...] = (
    NewMotionBinarySensorDescription(
        key="car_connected",
        translation_key="car_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d: d.state.car_connected,
    ),
    NewMotionBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.state.charging,
    ),
    NewMotionBinarySensorDescription(
        key="backend_connected",
        translation_key="backend_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.state.backend_connected,
        attrs_fn=lambda d: {
            "ocpp_status": d.state.raw.get("ocppStatus"),
            "ocpp_endpoint": d.state.raw.get("ocppEndpoint"),
        },
    ),
    NewMotionBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.state.errors or d.state.warnings),
        attrs_fn=lambda d: {"errors": d.state.errors, "warnings": d.state.warnings},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NewMotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the charger binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        NewMotionBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class NewMotionBinarySensor(NewMotionEntity, BinarySensorEntity):
    """A binary sensor fed from the charger status."""

    entity_description: NewMotionBinarySensorDescription

    def __init__(
        self,
        coordinator: NewMotionCoordinator,
        description: NewMotionBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes, if the description defines them."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
