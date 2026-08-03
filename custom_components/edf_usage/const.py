"""Constants for the EDF Usage integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "edf_usage"

CONF_API_TOKEN = "api_token"
CONF_CUSTOMER_ID = "customer_id"
CONF_GRAPHQL_ENDPOINT = "graphql_endpoint"
CONF_OFF_PEAK_END = "off_peak_end"
CONF_OFF_PEAK_START = "off_peak_start"
CONF_TIMEZONE = "timezone"

DEFAULT_GRAPHQL_ENDPOINT = "https://api.edfgb-kraken.energy/v1/graphql/"
DEFAULT_OFF_PEAK_END = "06:00"
DEFAULT_OFF_PEAK_START = "23:00"
DEFAULT_TIMEZONE = "Europe/London"
POLL_INTERVAL = timedelta(hours=12)

DATA_COORDINATOR = "coordinator"
