"""Tests for EDF billing data aggregation."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def _load_api_module():
    """Load api.py without requiring a full Home Assistant environment."""

    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.ClientResponseError = type("ClientResponseError", (Exception,), {})
        aiohttp.ClientSession = object
        sys.modules["aiohttp"] = aiohttp

    path = Path(__file__).parents[1] / "custom_components" / "edf_usage" / "api.py"
    spec = importlib.util.spec_from_file_location("edf_usage_api_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


api_module = _load_api_module()


class BillSummaryTests(unittest.TestCase):
    """Verify partial EDF responses are combined into one bill summary."""

    def test_usage_response_does_not_skip_transaction_cost_fallback(self) -> None:
        """Usage-only GBR data should be combined with transaction costs."""

        api = api_module.EDFUsageApi.__new__(api_module.EDFUsageApi)
        api._customer_id = "A-123"
        api._timezone = "Europe/London"
        calls: list[str] = []

        async def graphql(query, variables):
            calls.append(query)
            if query == api_module.GBR_COST_OF_USAGE_QUERY:
                return {
                    "gbrCostOfUsage": {
                        "periods": [
                            {
                                "totalConsumption": "42.5",
                                "totalCost": None,
                                "currency": "GBP",
                            }
                        ]
                    }
                }
            if query == api_module.COST_OF_USAGE_QUERY:
                return {
                    "costOfUsage": {
                        "details": {
                            "edges": [],
                            "usageKwh": None,
                            "cost": None,
                        }
                    }
                }
            if query == api_module.ACCOUNT_TRANSACTIONS_QUERY:
                return {
                    "account": {
                        "transactions": {
                            "edges": [
                                {
                                    "node": {
                                        "amount": 1234,
                                        "isReversed": False,
                                    }
                                }
                            ]
                        }
                    }
                }
            self.fail("The meter-consumption fallback should not be needed")

        api._graphql = graphql
        now = datetime.now()

        result = asyncio.run(api._async_get_bill_summary(now, now))

        self.assertEqual(
            result,
            {
                "cost_pence": Decimal("1234"),
                "usage_kwh": Decimal("42.5"),
                "currency": "GBP",
                "source": "gbrCostOfUsage + account.transactions",
            },
        )
        self.assertIn(api_module.ACCOUNT_TRANSACTIONS_QUERY, calls)


class AuthenticationTests(unittest.TestCase):
    """Verify EDF token-exchange failures are reported as authentication errors."""

    def test_invalid_data_during_token_exchange_is_auth_failure(self) -> None:
        """EDF's generic invalid-data response should request reauthentication."""

        api = api_module.EDFUsageApi.__new__(api_module.EDFUsageApi)
        api._authorization_header = None

        async def graphql(query, variables, *, allow_token_refresh=True):
            raise api_module.EDFUsageError("Invalid data.")

        api._graphql = graphql

        with self.assertRaisesRegex(
            api_module.EDFUsageAuthError,
            "EDF rejected the configured account-user API key",
        ):
            asyncio.run(api._obtain_kraken_token("invalid-key"))


if __name__ == "__main__":
    unittest.main()
