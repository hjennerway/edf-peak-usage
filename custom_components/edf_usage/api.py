"""Client and parsing helpers for EDF Kraken usage data."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientResponseError, ClientSession


class EDFUsageError(Exception):
    """Base error for EDF Usage failures."""


class EDFUsageAuthError(EDFUsageError):
    """EDF rejected the configured token."""


@dataclass(frozen=True)
class UsageInterval:
    """A single energy usage interval."""

    start: datetime | None
    end: datetime | None
    kwh: Decimal
    label: str | None = None
    cost_pence: Decimal | None = None


@dataclass(frozen=True)
class UsageSummary:
    """Peak and off-peak usage totals for a period."""

    peak_kwh: Decimal
    off_peak_kwh: Decimal
    start: datetime
    end: datetime
    last_updated: datetime
    intervals: tuple[UsageInterval, ...]
    source: str
    bill_30_day_cost_pence: Decimal | None = None
    bill_30_day_usage_kwh: Decimal | None = None
    bill_30_day_currency: str | None = None
    bill_30_day_source: str | None = None
    last_refresh_success: bool = True
    last_refresh_attempt: datetime | None = None
    last_refresh_error: str | None = None

    @property
    def total_kwh(self) -> Decimal:
        """Return total usage."""

        return self.peak_kwh + self.off_peak_kwh

    @property
    def peak_percent(self) -> Decimal:
        """Return peak percentage."""

        if not self.total_kwh:
            return Decimal("0")
        return (self.peak_kwh / self.total_kwh) * Decimal("100")

    @property
    def off_peak_percent(self) -> Decimal:
        """Return off-peak percentage."""

        if not self.total_kwh:
            return Decimal("0")
        return (self.off_peak_kwh / self.total_kwh) * Decimal("100")

    @property
    def bill_30_day_cost(self) -> Decimal | None:
        """Return the last 30 days bill in pounds."""

        if self.bill_30_day_cost_pence is None:
            return None
        return self.bill_30_day_cost_pence / Decimal("100")

    def with_refresh_failure(self, error: str, attempted_at: datetime) -> UsageSummary:
        """Return a copy marked with the most recent refresh failure."""

        return replace(
            self,
            last_refresh_success=False,
            last_refresh_attempt=attempted_at,
            last_refresh_error=error,
        )


class EDFUsageApi:
    """Small async EDF Kraken GraphQL API client."""

    def __init__(
        self,
        *,
        session: ClientSession,
        customer_id: str,
        api_token: str,
        graphql_endpoint: str,
        off_peak_start: str,
        off_peak_end: str,
        timezone: str,
    ) -> None:
        """Create the EDF Usage API client."""

        self._session = session
        self._customer_id = customer_id
        self._api_key = _normalise_api_token(api_token)
        self._authorization_header: str | None = None
        self._graphql_endpoint = graphql_endpoint
        self._off_peak_start = _parse_hhmm(off_peak_start)
        self._off_peak_end = _parse_hhmm(off_peak_end)
        self._timezone = timezone
        self._tzinfo = ZoneInfo(timezone)

    async def async_get_weekly_usage(self) -> UsageSummary:
        """Fetch and classify the last seven days of electricity usage."""

        await self._ensure_authorization_header()

        end = datetime.now(self._tzinfo)
        start = end - timedelta(days=7)
        bill_start = end - timedelta(days=30)

        variables = {
            "accountNumber": self._customer_id,
            "periods": [
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
            ],
            "startAt": start.isoformat(),
            "timezone": self._timezone,
            "grouping": "HALF_HOUR",
            "fuelType": "ELECTRICITY",
            "after": None,
        }

        errors: list[str] = []
        for source, query, parser in (
            ("gbrCostOfUsage", GBR_COST_OF_USAGE_QUERY, self._parse_gbr_cost_of_usage),
            ("costOfUsage", COST_OF_USAGE_QUERY, self._parse_cost_of_usage),
            ("meterConsumption", METER_CONSUMPTION_QUERY, self._parse_meter_consumption),
        ):
            try:
                if source == "gbrCostOfUsage":
                    payload = await self._graphql(query, variables)
                    intervals = parser(payload)
                else:
                    intervals = await self._fetch_paginated_intervals(
                        query,
                        variables,
                        parser,
                        _connection_next_cursor,
                    )
            except EDFUsageAuthError:
                raise
            except EDFUsageError as err:
                errors.append(f"{source}: {err}")
                continue

            if intervals:
                bill = await self._async_get_bill_summary(bill_start, end)
                return self._summarise(start, end, intervals, source, bill)

            errors.append(f"{source}: no usage intervals returned")

        raise EDFUsageError("; ".join(errors) or "EDF did not return usage data")

    async def _async_get_bill_summary(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Fetch cost and consumption for the last 30 days."""

        variables = {
            "accountNumber": self._customer_id,
            "periods": [
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
            ],
            "startAt": start.isoformat(),
            "timezone": self._timezone,
            "grouping": "DAY",
            "fuelType": "ELECTRICITY",
            "after": None,
        }

        errors: list[str] = []
        try:
            payload = await self._graphql(GBR_COST_OF_USAGE_QUERY, variables)
            bill = _parse_gbr_bill(payload)
            if bill["cost_pence"] is not None:
                return bill
        except EDFUsageError as err:
            errors.append(f"gbrCostOfUsage: {err}")

        try:
            intervals = await self._fetch_paginated_intervals(
                COST_OF_USAGE_QUERY,
                variables,
                self._parse_cost_of_usage,
                _connection_next_cursor,
            )
            bill = _parse_cost_of_usage_bill(intervals)
            if bill["cost_pence"] is not None:
                return bill
        except EDFUsageError as err:
            errors.append(f"costOfUsage: {err}")

        return {
            "cost_pence": None,
            "usage_kwh": None,
            "currency": None,
            "source": "; ".join(errors) if errors else None,
        }

    async def _fetch_paginated_intervals(
        self,
        query: str,
        variables: dict[str, Any],
        parser: Any,
        next_cursor: Any,
    ) -> list[UsageInterval]:
        """Fetch all pages for a consumption/cost connection."""

        intervals: list[UsageInterval] = []
        after: str | None = None
        for _ in range(10):
            payload = await self._graphql(query, {**variables, "after": after})
            intervals.extend(parser(payload))
            after = next_cursor(payload)
            if after is None:
                return intervals

        raise EDFUsageError("EDF returned more usage pages than expected")

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
        *,
        allow_token_refresh: bool = True,
    ) -> dict[str, Any]:
        """Post a GraphQL request to EDF."""

        headers = {
            "Content-Type": "application/json",
        }
        if self._authorization_header is not None:
            headers["Authorization"] = self._authorization_header

        try:
            response = await self._session.post(
                self._graphql_endpoint,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            payload: dict[str, Any] = await response.json()
        except ClientResponseError as err:
            if err.status in (401, 403):
                if (
                    allow_token_refresh
                    and await self._async_refresh_authorization_header()
                ):
                    return await self._graphql(
                        query,
                        variables,
                        allow_token_refresh=False,
                    )
                raise EDFUsageAuthError("EDF rejected the configured API token") from err
            raise EDFUsageError(f"EDF HTTP error {err.status}") from err
        except ValueError as err:
            raise EDFUsageAuthError(f"Invalid EDF API token format: {err}") from err
        except Exception as err:  # noqa: BLE001 - surfaced as Home Assistant update failure
            raise EDFUsageError(f"Unable to contact EDF: {err}") from err

        graphql_errors = payload.get("errors") or []
        if graphql_errors:
            messages = "; ".join(
                str(error.get("message", "Unknown GraphQL error"))
                for error in graphql_errors
                if isinstance(error, dict)
            )
            messages_lower = messages.lower()
            if "unauthorized" in messages_lower or "authorization" in messages_lower:
                if (
                    allow_token_refresh
                    and await self._async_refresh_authorization_header()
                ):
                    return await self._graphql(
                        query,
                        variables,
                        allow_token_refresh=False,
                    )
                raise EDFUsageAuthError(messages)
            raise EDFUsageError(messages)

        return payload.get("data") or {}

    async def _ensure_authorization_header(self) -> None:
        """Ensure the client has a Kraken token ready for authenticated queries."""

        if self._authorization_header is not None:
            return

        if _looks_like_kraken_token(self._api_key):
            self._authorization_header = self._api_key
            return

        token = await self._obtain_kraken_token(self._api_key)
        self._authorization_header = token

    async def _obtain_kraken_token(self, api_key: str) -> str:
        """Exchange an account-user API key for a Kraken token."""

        if not api_key:
            raise EDFUsageAuthError("EDF API key is empty")

        previous_header = self._authorization_header
        self._authorization_header = None
        try:
            payload = await self._graphql(
                OBTAIN_KRAKEN_TOKEN_MUTATION,
                {"input": {"APIKey": api_key}},
                allow_token_refresh=False,
            )
        finally:
            self._authorization_header = previous_header

        token = (
            (payload.get("obtainKrakenToken") or {}).get("token")
            if isinstance(payload, dict)
            else None
        )
        if not token:
            raise EDFUsageAuthError("EDF did not return a Kraken token for the API key")
        return _normalise_api_token(token)

    async def _async_refresh_authorization_header(self) -> bool:
        """Refresh a cached Kraken token when EDF rejects it."""

        if (
            self._authorization_header is None
            or _looks_like_kraken_token(self._api_key)
        ):
            return False

        self._authorization_header = None
        self._authorization_header = await self._obtain_kraken_token(self._api_key)
        return True

    def _parse_gbr_cost_of_usage(self, data: dict[str, Any]) -> list[UsageInterval]:
        """Parse the currently documented GB cost-of-usage shape."""

        periods = ((data.get("gbrCostOfUsage") or {}).get("periods")) or []
        intervals: list[UsageInterval] = []
        for period in periods:
            for item in period.get("intervals") or []:
                time_range = item.get("period") or {}
                intervals.append(
                    UsageInterval(
                        start=_parse_datetime(time_range.get("start")),
                        end=_parse_datetime(time_range.get("end")),
                        kwh=_to_decimal(item.get("consumption")),
                        label=item.get("bandSubcategory"),
                        cost_pence=_optional_decimal(item.get("cost")),
                    )
                )
        return intervals

    def _parse_cost_of_usage(self, data: dict[str, Any]) -> list[UsageInterval]:
        """Parse the legacy/deprecated cost-of-usage connection shape."""

        details = (data.get("costOfUsage") or {}).get("details") or {}
        intervals: list[UsageInterval] = []
        for edge in details.get("edges") or []:
            node = edge.get("node") or {}
            intervals.append(
                UsageInterval(
                    start=_parse_datetime(node.get("startAt") or node.get("start")),
                    end=_parse_datetime(node.get("endAt") or node.get("end")),
                    kwh=_first_decimal(
                        node,
                        "usageKwh",
                        "consumption",
                        "value",
                        "consumptionKwh",
                    ),
                    label=node.get("bandSubcategory") or node.get("label"),
                    cost_pence=_optional_decimal(node.get("cost")),
                )
            )
        return intervals

    def _parse_meter_consumption(self, data: dict[str, Any]) -> list[UsageInterval]:
        """Parse meter-level consumption connections under account properties."""

        account = data.get("account") or {}
        intervals: list[UsageInterval] = []
        for prop in account.get("properties") or []:
            for meter_point in prop.get("electricityMeterPoints") or []:
                for meter in meter_point.get("meters") or []:
                    consumption = meter.get("consumption") or {}
                    for edge in consumption.get("edges") or []:
                        node = edge.get("node") or {}
                        intervals.append(
                            UsageInterval(
                                start=_parse_datetime(node.get("startAt")),
                                end=_parse_datetime(node.get("endAt")),
                                kwh=_to_decimal(node.get("value")),
                            )
                        )
        return intervals

    def _summarise(
        self,
        start: datetime,
        end: datetime,
        intervals: list[UsageInterval],
        source: str,
        bill: dict[str, Any],
    ) -> UsageSummary:
        """Classify intervals as peak or off-peak and total them."""

        peak = Decimal("0")
        off_peak = Decimal("0")
        for interval in intervals:
            if _label_is_off_peak(interval.label) or (
                interval.label is None and self._is_off_peak(interval.start)
            ):
                off_peak += interval.kwh
            else:
                peak += interval.kwh

        return UsageSummary(
            peak_kwh=peak,
            off_peak_kwh=off_peak,
            start=start,
            end=end,
            last_updated=end,
            intervals=tuple(intervals),
            source=source,
            bill_30_day_cost_pence=bill["cost_pence"],
            bill_30_day_usage_kwh=bill["usage_kwh"],
            bill_30_day_currency=bill["currency"],
            bill_30_day_source=bill["source"],
            last_refresh_attempt=end,
        )

    def _is_off_peak(self, value: datetime | None) -> bool:
        """Return whether a timestamp falls within the configured off-peak window."""

        if value is None:
            return False

        local_time = value.astimezone(self._tzinfo).time()
        if self._off_peak_start < self._off_peak_end:
            return self._off_peak_start <= local_time < self._off_peak_end
        return local_time >= self._off_peak_start or local_time < self._off_peak_end


GBR_COST_OF_USAGE_QUERY = """
query EDFGbrCostOfUsage($accountNumber: String!, $periods: [DateTimeRangeInput]!) {
  gbrCostOfUsage(accountNumber: $accountNumber, periods: $periods) {
    periods {
      period {
        start
        end
      }
      totalConsumption
      totalCost
      consumptionUnit
      currency
      intervals {
        bandSubcategory
        consumption
        cost
        period {
          start
          end
        }
        rateApplied
      }
    }
  }
}
"""

COST_OF_USAGE_QUERY = """
query EDFCostOfUsage(
  $accountNumber: String,
  $after: String,
  $fuelType: FuelType,
  $grouping: ConsumptionGroupings!,
  $startAt: DateTime,
  $timezone: String
) {
  costOfUsage(
    accountNumber: $accountNumber,
    fuelType: $fuelType,
    grouping: $grouping,
    startAt: $startAt,
    timezone: $timezone
  ) {
    costEnabled
    direction
    details(first: 100, after: $after) {
      usageKwh
      cost
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
          startAt
          endAt
          usageKwh
          consumption
          value
          consumptionKwh
          cost
          bandSubcategory
          label
        }
      }
    }
  }
}
"""

METER_CONSUMPTION_QUERY = """
query EDFMeterConsumption(
  $accountNumber: String!,
  $after: String,
  $grouping: ConsumptionGroupings!,
  $startAt: DateTime!,
  $timezone: String!
) {
  account(accountNumber: $accountNumber) {
    properties {
      electricityMeterPoints {
        meters {
          consumption(first: 100, after: $after, grouping: $grouping, startAt: $startAt, timezone: $timezone) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                startAt
                endAt
                value
              }
            }
          }
        }
      }
    }
  }
}
"""

OBTAIN_KRAKEN_TOKEN_MUTATION = """
mutation EDFObtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
  }
}
"""


def _parse_hhmm(value: str) -> time:
    """Parse a Home Assistant option in HH:MM form."""

    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as err:
        raise EDFUsageError(f"Invalid time '{value}', expected HH:MM") from err
    return parsed.time()


def _normalise_api_token(value: str) -> str:
    """Normalise tokens pasted from EDF docs, browsers, or terminals."""

    token = str(value or "").strip().strip("\"'")
    if token.lower().startswith("authorization:"):
        token = token.split(":", 1)[1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return "".join(token.split())


def _looks_like_kraken_token(value: str) -> bool:
    """Return whether a value looks like an already-issued Kraken JWT."""

    return value.startswith("eyJ") and value.count(".") == 2


def _parse_gbr_bill(data: dict[str, Any]) -> dict[str, Any]:
    """Parse a 30-day bill summary from the GB cost-of-usage response."""

    periods = ((data.get("gbrCostOfUsage") or {}).get("periods")) or []
    cost = Decimal("0")
    usage = Decimal("0")
    currency: str | None = None
    found_cost = False

    for period in periods:
        period_cost = _optional_decimal(period.get("totalCost"))
        if period_cost is not None:
            cost += period_cost
            found_cost = True

        usage += _to_decimal(period.get("totalConsumption"))
        currency = currency or period.get("currency")

    return {
        "cost_pence": cost if found_cost else None,
        "usage_kwh": usage if periods else None,
        "currency": currency,
        "source": "gbrCostOfUsage",
    }


def _parse_cost_of_usage_bill(intervals: list[UsageInterval]) -> dict[str, Any]:
    """Parse a 30-day bill summary from the legacy cost-of-usage response."""

    interval_costs = [
        interval.cost_pence for interval in intervals if interval.cost_pence is not None
    ]
    cost = sum(interval_costs, Decimal("0")) if interval_costs else None
    usage = sum((interval.kwh for interval in intervals), Decimal("0")) if intervals else None

    return {
        "cost_pence": cost,
        "usage_kwh": usage,
        "currency": "GBP" if cost is not None else None,
        "source": "costOfUsage",
    }


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO 8601 datetime."""

    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _to_decimal(value: Any) -> Decimal:
    """Convert a GraphQL decimal-ish value to Decimal."""

    decimal = _optional_decimal(value)
    return decimal if decimal is not None else Decimal("0")


def _optional_decimal(value: Any) -> Decimal | None:
    """Convert a GraphQL decimal-ish value to Decimal, preserving None."""

    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _first_decimal(data: dict[str, Any], *keys: str) -> Decimal:
    """Return the first present decimal from a dictionary."""

    for key in keys:
        decimal = _optional_decimal(data.get(key))
        if decimal is not None:
            return decimal
    return Decimal("0")


def _label_is_off_peak(label: str | None) -> bool:
    """Return whether a supplier label describes off-peak usage."""

    if label is None:
        return False
    normalised = label.replace("_", "").replace("-", "").replace(" ", "").lower()
    return "offpeak" in normalised or "night" in normalised


def _connection_next_cursor(data: dict[str, Any]) -> str | None:
    """Find the next cursor in a known EDF connection response."""

    details = (data.get("costOfUsage") or {}).get("details")
    if isinstance(details, dict):
        page_info = details.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            return page_info.get("endCursor")

    account = data.get("account") or {}
    for prop in account.get("properties") or []:
        for meter_point in prop.get("electricityMeterPoints") or []:
            for meter in meter_point.get("meters") or []:
                consumption = meter.get("consumption") or {}
                page_info = consumption.get("pageInfo") or {}
                if page_info.get("hasNextPage"):
                    return page_info.get("endCursor")

    return None
