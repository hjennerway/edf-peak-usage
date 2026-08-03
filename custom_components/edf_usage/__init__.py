"""EDF peak/off-peak usage integration."""

from __future__ import annotations

from inspect import isawaitable
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EDFUsageApi
from .const import (
    CONF_API_TOKEN,
    CONF_CUSTOMER_ID,
    CONF_GRAPHQL_ENDPOINT,
    CONF_OFF_PEAK_END,
    CONF_OFF_PEAK_START,
    CONF_TIMEZONE,
    DATA_COORDINATOR,
    DEFAULT_GRAPHQL_ENDPOINT,
    DEFAULT_OFF_PEAK_END,
    DEFAULT_OFF_PEAK_START,
    DEFAULT_TIMEZONE,
    DOMAIN,
)
from .coordinator import EDFUsageCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
CARD_URL = f"/{DOMAIN}/edf-usage-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up EDF Usage."""

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Expose the bundled Lovelace card from the installed integration."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("frontend_registered"):
        return

    card_path = str(Path(__file__).parent / "www" / "edf-usage-card.js")

    try:
        from homeassistant.components.http import (
            StaticPathConfig,
            async_register_static_paths,
        )
    except ImportError:
        result = hass.http.async_register_static_path(
            CARD_URL,
            card_path,
            cache_headers=True,
        )
        if isawaitable(result):
            await result
    else:
        await async_register_static_paths(
            hass,
            [StaticPathConfig(CARD_URL, card_path, True)],
        )

    domain_data["frontend_registered"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EDF Usage from a config entry."""

    await _async_register_frontend(hass)

    options = entry.options
    session = async_get_clientsession(hass)
    api = EDFUsageApi(
        session=session,
        customer_id=entry.data[CONF_CUSTOMER_ID],
        api_token=entry.data[CONF_API_TOKEN],
        graphql_endpoint=options.get(CONF_GRAPHQL_ENDPOINT, DEFAULT_GRAPHQL_ENDPOINT),
        off_peak_start=options.get(CONF_OFF_PEAK_START, DEFAULT_OFF_PEAK_START),
        off_peak_end=options.get(CONF_OFF_PEAK_END, DEFAULT_OFF_PEAK_END),
        timezone=options.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
    )
    coordinator = EDFUsageCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EDF Usage."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
