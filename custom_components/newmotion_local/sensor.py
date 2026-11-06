"""Sensors for NewMotion chargers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUS_OPTIONS
from .coordinator import NewMotionConfigEntry, NewMotionCoordinator, NewMotionData
from .entity import NewMotionEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NewMotionSensorDescription(SensorEntityDescription):
    """Describe a charger sensor."""

    value_fn: Callable[[NewMotionData], float | int | str | datetime | None]
    attrs_fn: Callable[[NewMotionData], dict[str, Any]] | None = None


def _charging_value(fn: Callable[[NewMotionData], float | int | None]):
    """Report 0 instead of a stale number when no energy flows."""

    def value(data: NewMotionData) -> float | int | None:
        if not data.state.charging:
            return 0
        return fn(data)

    return value


SENSORS: tuple[NewMotionSensorDescription, ...] = (
    NewMotionSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value_fn=lambda d: d.state.status,
        attrs_fn=lambda d: {
            "car_status": d.state.car_status,
            "transaction_status": d.state.transaction_status,
            "errors": d.state.errors,
            "warnings": d.state.warnings,
        },
    ),
    NewMotionSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=_charging_value(lambda d: d.state.rate.power_kw),
    ),
    NewMotionSensorDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=_charging_value(lambda d: d.state.rate.current),
    ),
    NewMotionSensorDescription(
        key="active_phases",
        translation_key="active_phases",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_charging_value(lambda d: d.state.rate.phases),
    ),
    NewMotionSensorDescription(
        key="power_factor",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.state.rate.power_factor if d.state.charging else None,
    ),
    NewMotionSensorDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda d: d.state.session_energy_kwh,
    ),
    NewMotionSensorDescription(
        key="session_start",
        translation_key="session_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.state.session_start,
    ),
    NewMotionSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d: d.meter_total_kwh,
    ),
    NewMotionSensorDescription(
        key="last_session",
        translation_key="last_session",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda d: d.last_session.energy_kwh if d.last_session else None,
        attrs_fn=lambda d: d.last_session.as_event_data() if d.last_session else {},
    ),
    NewMotionSensorDescription(
        key="current_limit",
        translation_key="current_limit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda d: d.state.current_limit,
    ),
    NewMotionSensorDescription(
        key="max_current",
        translation_key="max_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.state.max_current,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NewMotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the charger sensors."""
    coordinator = entry.runtime_data
    async_add_entities(NewMotionSensor(coordinator, desc) for desc in SENSORS)


class NewMotionSensor(NewMotionEntity, SensorEntity):
    """A sensor fed from the charger status."""

    entity_description: NewMotionSensorDescription

    def __init__(
        self,
        coordinator: NewMotionCoordinator,
        description: NewMotionSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes, if the description defines them."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
