"""Sensors for EDF Usage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import UsageSummary
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EDFUsageCoordinator


@dataclass(frozen=True, kw_only=True)
class EDFUsageSensorDescription(SensorEntityDescription):
    """Description for an EDF usage sensor."""

    value_fn: Callable[[UsageSummary], Decimal]


def _round(value: Decimal) -> float:
    """Round Home Assistant states consistently."""

    return float(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


SENSORS: tuple[EDFUsageSensorDescription, ...] = (
    EDFUsageSensorDescription(
        key="weekly_peak_usage",
        translation_key="weekly_peak_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.peak_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_off_peak_usage",
        translation_key="weekly_off_peak_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.off_peak_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_total_usage",
        translation_key="weekly_total_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_peak_percentage",
        translation_key="weekly_peak_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.peak_percent,
    ),
    EDFUsageSensorDescription(
        key="weekly_off_peak_percentage",
        translation_key="weekly_off_peak_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.off_peak_percent,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EDF Usage sensors."""

    coordinator: EDFUsageCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        EDFUsageSensor(coordinator, entry, description) for description in SENSORS
    )


class EDFUsageSensor(CoordinatorEntity[EDFUsageCoordinator], SensorEntity):
    """EDF usage sensor entity."""

    entity_description: EDFUsageSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EDFUsageCoordinator,
        entry: ConfigEntry,
        description: EDFUsageSensorDescription,
    ) -> None:
        """Create the sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="EDF Energy",
            name=f"EDF Usage {entry.data['customer_id']}",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value."""

        if self.coordinator.data is None:
            return None
        return _round(self.entity_description.value_fn(self.coordinator.data))

    @property
    def extra_state_attributes(self) -> dict[str, str | int] | None:
        """Return common metadata for diagnostics and cards."""

        data = self.coordinator.data
        if data is None:
            return None

        return {
            "period_start": data.start.isoformat(),
            "period_end": data.end.isoformat(),
            "interval_count": len(data.intervals),
            "source": data.source,
        }
