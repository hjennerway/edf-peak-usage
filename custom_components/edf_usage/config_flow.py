"""Config flow for EDF Usage."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import EDFUsageError
from .const import (
    CONF_API_TOKEN,
    CONF_CUSTOMER_ID,
    CONF_GRAPHQL_ENDPOINT,
    CONF_OFF_PEAK_END,
    CONF_OFF_PEAK_START,
    CONF_TIMEZONE,
    DEFAULT_GRAPHQL_ENDPOINT,
    DEFAULT_OFF_PEAK_END,
    DEFAULT_OFF_PEAK_START,
    DEFAULT_TIMEZONE,
    DOMAIN,
)


class EDFUsageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EDF Usage config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            customer_id = user_input[CONF_CUSTOMER_ID].strip()
            await self.async_set_unique_id(customer_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"EDF Usage {customer_id}",
                data={
                    CONF_CUSTOMER_ID: customer_id,
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip(),
                },
                options={
                    CONF_GRAPHQL_ENDPOINT: DEFAULT_GRAPHQL_ENDPOINT,
                    CONF_OFF_PEAK_START: DEFAULT_OFF_PEAK_START,
                    CONF_OFF_PEAK_END: DEFAULT_OFF_PEAK_END,
                    CONF_TIMEZONE: DEFAULT_TIMEZONE,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CUSTOMER_ID): str,
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EDFUsageOptionsFlow:
        """Return the options flow."""

        return EDFUsageOptionsFlow(config_entry)


class EDFUsageOptionsFlow(config_entries.OptionsFlow):
    """Handle EDF Usage options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Create the options flow."""

        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Manage EDF Usage options."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _validate_hhmm(user_input[CONF_OFF_PEAK_START])
                _validate_hhmm(user_input[CONF_OFF_PEAK_END])
                ZoneInfo(user_input[CONF_TIMEZONE])
            except EDFUsageError:
                errors["base"] = "invalid_time"
            except ZoneInfoNotFoundError:
                errors["base"] = "invalid_timezone"
            else:
                return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GRAPHQL_ENDPOINT,
                        default=options.get(
                            CONF_GRAPHQL_ENDPOINT,
                            DEFAULT_GRAPHQL_ENDPOINT,
                        ),
                    ): str,
                    vol.Required(
                        CONF_TIMEZONE,
                        default=options.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
                    ): str,
                    vol.Required(
                        CONF_OFF_PEAK_START,
                        default=options.get(CONF_OFF_PEAK_START, DEFAULT_OFF_PEAK_START),
                    ): str,
                    vol.Required(
                        CONF_OFF_PEAK_END,
                        default=options.get(CONF_OFF_PEAK_END, DEFAULT_OFF_PEAK_END),
                    ): str,
                }
            ),
            errors=errors,
        )


def _validate_hhmm(value: str) -> None:
    """Validate an HH:MM string using the API parser."""

    from .api import _parse_hhmm

    _parse_hhmm(value)
