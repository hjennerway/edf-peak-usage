"""Sensors for EDF Usage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
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

    value_fn: Callable[[UsageSummary], Decimal | datetime | str | None]


def _round(value: Decimal) -> float:
    """Round Home Assistant states consistently."""

    return float(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


SENSORS: tuple[EDFUsageSensorDescription, ...] = (
    EDFUsageSensorDescription(
        key="weekly_peak_usage",
        name="Weekly peak usage",
        translation_key="weekly_peak_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.peak_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_off_peak_usage",
        name="Weekly off-peak usage",
        translation_key="weekly_off_peak_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.off_peak_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_total_usage",
        name="Weekly total usage",
        translation_key="weekly_total_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total_kwh,
    ),
    EDFUsageSensorDescription(
        key="weekly_peak_percentage",
        name="Weekly peak percentage",
        translation_key="weekly_peak_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.peak_percent,
    ),
    EDFUsageSensorDescription(
        key="weekly_off_peak_percentage",
        name="Weekly off-peak percentage",
        translation_key="weekly_off_peak_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.off_peak_percent,
    ),
    EDFUsageSensorDescription(
        key="bill_30_day_cost",
        name="30-day bill",
        translation_key="bill_30_day_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.bill_30_day_cost,
    ),
    EDFUsageSensorDescription(
        key="bill_30_day_usage",
        name="30-day usage",
        translation_key="bill_30_day_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.bill_30_day_usage_kwh,
    ),
    EDFUsageSensorDescription(
        key="last_updated",
        name="Last updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_updated,
    ),
    EDFUsageSensorDescription(
        key="last_refresh_attempt",
        name="Last refresh attempt",
        translation_key="last_refresh_attempt",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_refresh_attempt,
    ),
    EDFUsageSensorDescription(
        key="update_status",
        name="Update status",
        translation_key="update_status",
        value_fn=lambda data: "ok" if data.last_refresh_success else "failed",
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


class EDFUsageSensor(CoordinatorEntity[EDFUsageCoordinator], RestoreSensor):
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
        self._restored_native_value: float | datetime | str | None = None
        self._restored_extra_state_attributes: dict[str, Any] | None = None
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="EDF Energy",
            name=f"EDF Usage {entry.data['customer_id']}",
        )

    @property
    def available(self) -> bool:
        """Return whether the entity can show a current or restored value."""

        return (
            self.coordinator.data is not None
            or self._restored_native_value is not None
        )

    async def async_added_to_hass(self) -> None:
        """Restore the most recent value when Home Assistant restarts."""

        await super().async_added_to_hass()

        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is not None:
            self._restored_native_value = self._coerce_restored_native_value(
                last_sensor_data.native_value
            )

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._restored_extra_state_attributes = {
                key: value
                for key, value in last_state.attributes.items()
                if key
                in {
                    "period_start",
                    "period_end",
                    "interval_count",
                    "source",
                    "bill_30_day_currency",
                    "bill_30_day_source",
                    "last_updated",
                    "last_refresh_attempt",
                    "last_refresh_error",
                    "last_refresh_success",
                }
            }

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the current sensor value."""

        data = self.coordinator.data
        if data is None:
            return self._restored_native_value

        value = self.entity_description.value_fn(data)
        if value is None:
            return None
        if isinstance(value, Decimal):
            return _round(value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return common metadata for diagnostics and cards."""

        data = self.coordinator.data
        if data is None:
            return self._restored_extra_state_attributes

        return {
            "period_start": data.start.isoformat(),
            "period_end": data.end.isoformat(),
            "interval_count": len(data.intervals),
            "source": data.source,
            "bill_30_day_currency": data.bill_30_day_currency,
            "bill_30_day_source": data.bill_30_day_source,
            "last_updated": data.last_updated.isoformat(),
            "last_refresh_attempt": (
                data.last_refresh_attempt.isoformat()
                if data.last_refresh_attempt is not None
                else None
            ),
            "last_refresh_error": data.last_refresh_error,
            "last_refresh_success": data.last_refresh_success,
        }

    def _coerce_restored_native_value(self, value: Any) -> float | datetime | str | None:
        """Return a restored value in the native type expected by the sensor."""

        if value is None:
            return None

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None

        if self.entity_description.key == "update_status":
            return str(value)

        try:
            return float(value)
        except (TypeError, ValueError):
            return None
