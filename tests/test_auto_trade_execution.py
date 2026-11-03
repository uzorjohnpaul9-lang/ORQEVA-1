import asyncio
import unittest
from unittest.mock import patch

from backend.services import risk_service
from backend.services import order_executor
from backend.services.auto_trade_service import (
    _log_once,
    _size_trade,
    reset_log_throttle,
)
from backend.services.order_executor import _already_closed


def _status(account_value=100000.0, total_exposure=0.0, max_pos=10.0,
            max_exposure=risk_service.MAX_TOTAL_EXPOSURE_PCT):
    return {
        "account_value": account_value,
        "total_exposure": total_exposure,
        "open_positions": 0,
        "max_positions": 10,
        "daily_loss_used_pct": 0.0,
        "daily_loss_limit": 5000.0,
        "trades_today": 0,
        "max_daily_trades": 20,
        "kill_switch_active": False,
        "limits": {
            "max_position_size_pct": max_pos,
            "max_total_exposure_pct": max_exposure,
            "max_daily_trades": 20,
        },
    }


class TestRiskTolerances(unittest.TestCase):
    def _check(self, qty, price, status):
        return asyncio.run(risk_service.pre_trade_check(None, "u1", "forex", qty, price, status=status))

    def test_exact_position_cap_is_allowed(self):
        allowed, reason = self._check(100.0, 100.0, _status())
        self.assertTrue(allowed, reason)

    def test_position_cap_over_by_a_hair_is_rejected(self):
        allowed, reason = self._check(100.01, 100.0, _status())
        self.assertFalse(allowed)
        self.assertIn("Position size", reason)

    def test_exact_exposure_cap_is_allowed(self):
        status = _status(total_exposure=70000.0)
        allowed, reason = self._check(100.0, 100.0, status)
        self.assertTrue(allowed, reason)

    def test_remaining_exposure_uses_shared_limit(self):
        status = _status(total_exposure=79000.0)
        self.assertAlmostEqual(risk_service.remaining_exposure(status), 1000.0)

    def test_exposure_budget_exhausted(self):
        status = _status(total_exposure=80000.0)
        self.assertEqual(risk_service.remaining_exposure(status), 0.0)


class TestSizing(unittest.TestCase):
    def test_risk_sizing_capped_by_position_limit(self):
        signal = {"entry_price": 100.0, "stop_loss": 99.0}
        qty = _size_trade(signal, 100000.0, 1.0, 10.0, 100.0)
        self.assertAlmostEqual(qty, 100.0, places=4)

    def test_sizing_respects_remaining_exposure(self):
        signal = {"entry_price": 100.0, "stop_loss": 99.0}
        qty = _size_trade(signal, 100000.0, 1.0, 10.0, 100.0,
                          remaining_exposure=5000.0)
        self.assertAlmostEqual(qty, 50.0, places=4)

    def test_sizing_returns_none_without_exposure_budget(self):
        signal = {"entry_price": 100.0, "stop_loss": 99.0}
        self.assertIsNone(_size_trade(signal, 100000.0, 1.0, 10.0, 100.0,
                                      remaining_exposure=0.0))

    def test_sizing_without_stop_uses_notional_cap(self):
        qty = _size_trade({"entry_price": 50.0}, 100000.0, 1.0, 10.0, 50.0)
        self.assertAlmostEqual(qty, 200.0, places=4)


class TestLogThrottle(unittest.TestCase):
    def setUp(self):
        reset_log_throttle()

    def test_duplicate_rejection_reason_is_suppressed(self):
        self.assertTrue(_log_once("u1", "rejected", "exposure limit"))
        self.assertFalse(_log_once("u1", "rejected", "exposure limit"))
        self.assertTrue(_log_once("u2", "rejected", "exposure limit"))

    def test_placed_is_never_throttled(self):
        self.assertTrue(_log_once("u1", "placed", "ok"))
        self.assertTrue(_log_once("u1", "placed", "ok"))


class TestAlreadyClosed(unittest.TestCase):
    def test_bridge_no_position_is_already_closed(self):
        self.assertTrue(_already_closed("no open ORQEVA position on EURUSDm to close"))
        self.assertTrue(_already_closed("no closable volume was found on the broker position"))

    def test_other_broker_error_is_not_ignored(self):
        self.assertFalse(_already_closed("MT5 rejected close [10009]: bad price"))


class _StubAdapter:
    def __init__(self, equity):
        self.equity = equity
        self.calls = 0

    def account(self, api_key, api_secret, is_paper):
        self.calls += 1
        return {"equity": self.equity}


class TestBrokerAccountValue(unittest.TestCase):
    def setUp(self):
        order_executor._account_cache.clear()

    def _value(self, adapter, conn):
        with patch.object(order_executor, "get_adapter", return_value=adapter), \
                patch.object(order_executor, "creds", return_value=("key", "secret")):
            return asyncio.run(order_executor.broker_account_value(conn))

    def test_value_is_cached_per_connection(self):
        adapter = _StubAdapter(1234.0)
        conn = {"id": "c1", "exchange": "exness", "is_paper": False}
        self.assertEqual(self._value(adapter, conn), 1234.0)
        self.assertEqual(self._value(adapter, conn), 1234.0)
        self.assertEqual(adapter.calls, 1)

    def test_connections_do_not_share_a_cache_entry(self):
        first = _StubAdapter(1234.0)
        second = _StubAdapter(999.0)
        self.assertEqual(self._value(first, {"id": "c1", "exchange": "exness"}), 1234.0)
        self.assertEqual(self._value(second, {"id": "c2", "exchange": "exness"}), 999.0)
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 1)

    def test_unreadable_snapshot_is_none(self):
        self.assertIsNone(self._value(None, {"id": "c1", "exchange": "exness"}))
        self.assertIsNone(asyncio.run(order_executor.broker_account_value(None)))


if __name__ == "__main__":
    unittest.main()
