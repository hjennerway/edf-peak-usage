"""Data coordinator for EDF Usage."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EDFUsageApi, EDFUsageAuthError, EDFUsageError, UsageSummary
from .const import POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EDFUsageCoordinator(DataUpdateCoordinator[UsageSummary]):
    """Fetch EDF data twice per day and share it with entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: EDFUsageApi,
    ) -> None:
        """Create the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=f"EDF Usage {entry.data['customer_id']}",
            update_interval=POLL_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> UsageSummary:
        """Fetch data from EDF."""

        try:
            return await self.api.async_get_weekly_usage()
        except EDFUsageAuthError as err:
            raise UpdateFailed(str(err)) from err
        except EDFUsageError as err:
            if self.data is not None:
                _LOGGER.warning(
                    "Unable to refresh EDF usage; keeping previous data: %s",
                    err,
                )
                return self.data.with_refresh_failure(str(err), dt_util.now())
            raise UpdateFailed(str(err)) from err
