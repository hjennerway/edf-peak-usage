"""Data coordinator for EDF Usage."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
        self.last_refresh_attempt: datetime | None = None
        self.last_refresh_error: str | None = None
        self.last_refresh_success: bool | None = None

    async def _async_update_data(self) -> UsageSummary:
        """Fetch data from EDF."""

        attempted_at = dt_util.now()
        self.last_refresh_attempt = attempted_at
        try:
            data = await self.api.async_get_weekly_usage()
        except EDFUsageAuthError as err:
            self.last_refresh_success = False
            self.last_refresh_error = str(err)
            raise ConfigEntryAuthFailed(str(err)) from err
        except EDFUsageError as err:
            self.last_refresh_success = False
            self.last_refresh_error = str(err)
            _LOGGER.warning("Unable to refresh EDF usage: %s", err)
            if self.data is not None:
                return self.data.with_refresh_failure(str(err), attempted_at)
            raise UpdateFailed(str(err)) from err

        self.last_refresh_success = True
        self.last_refresh_error = None
        return data
