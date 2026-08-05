"""Buttons for EDF Usage."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EDFUsageCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EDF Usage buttons."""

    coordinator: EDFUsageCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([EDFUsageRefreshButton(coordinator, entry)])


class EDFUsageRefreshButton(ButtonEntity):
    """Button that refreshes EDF usage data on demand."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: EDFUsageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Create the refresh button."""

        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="EDF Energy",
            name=f"EDF Usage {entry.data['customer_id']}",
        )

    async def async_press(self) -> None:
        """Refresh EDF usage data."""

        await self._coordinator.async_request_refresh()
