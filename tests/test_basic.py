"""
AI Trading System - Basic Test Suite
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import unittest
from unittest import mock
from datetime import datetime

# Import modules to test
from config.risk_profiles import get_risk_profile, CONSERVATIVE, MODERATE, AGGRESSIVE
from data.market_data import MarketDataManager
from data.technical_indicators import TechnicalIndicators
from data.data_validator import DataValidator
from risk.risk_engine import RiskEngine, TradeDecision
from risk.kill_switch import KillSwitch
from risk.position_manager import PositionManager
from risk.time_controls import TimeControls
from strategy.entry_generator import EntryGenerator
from strategy.exit_generator import ExitGenerator
from ai_models.regime_detector import MarketRegimeDetector
from ai_models.confidence_scorer import ConfidenceScorer
from ai_models.momentum_decoder import MomentumDecoder
from execution.paper_trader import PaperTrader

class TestRiskProfiles(unittest.TestCase):
    """Test risk profile configurations."""
    
    def test_conservative_profile(self):
        profile = get_risk_profile("conservative")
        self.assertEqual(profile.name, "conservative")
        self.assertEqual(profile.risk_per_trade, 0.01)
        self.assertEqual(profile.max_positions, 5)
    
    def test_moderate_profile(self):
        profile = get_risk_profile("moderate")
        self.assertEqual(profile.name, "moderate")
        self.assertEqual(profile.risk_per_trade, 0.02)
        self.assertEqual(profile.max_positions, 8)
    
    def test_aggressive_profile(self):
        profile = get_risk_profile("aggressive")
        self.assertEqual(profile.name, "aggressive")
        self.assertEqual(profile.risk_per_trade, 0.03)
        self.assertEqual(profile.max_positions, 12)
    
    def test_invalid_profile(self):
        with self.assertRaises(ValueError):
            get_risk_profile("invalid")

class TestMarketData(unittest.TestCase):
    """Test market data functionality."""
    
    def setUp(self):
        self.market_data = MarketDataManager()
    
    def test_get_stock_data(self):
        df = self.market_data.get_stock_data("AAPL")
        self.assertFalse(df.empty)
        self.assertIn("close", df.columns)
        self.assertIn("volume", df.columns)
    
    def test_get_realtime_quote(self):
        quote = self.market_data.get_realtime_quote("AAPL")
        self.assertIn("bid", quote)
        self.assertIn("ask", quote)
        self.assertIn("last", quote)
    
    def test_market_calendar(self):
        calendar = self.market_data.get_market_calendar()
        self.assertIn("is_open", calendar)
        self.assertIn("open_time", calendar)
        self.assertIn("close_time", calendar)

class TestTechnicalIndicators(unittest.TestCase):
    """Test technical indicator calculations."""
    
    def setUp(self):
        self.indicators = TechnicalIndicators()
    
    def test_calculate_rsi(self):
        import pandas as pd
        import numpy as np
        
        prices = pd.Series(np.random.uniform(100, 200, 100))
        rsi = self.indicators.calculate_rsi(prices)
        
        self.assertEqual(len(rsi), len(prices))
        self.assertTrue(all(0 <= x <= 100 for x in rsi.dropna()))
    
    def test_calculate_macd(self):
        import pandas as pd
        import numpy as np
        
        prices = pd.Series(np.random.uniform(100, 200, 100))
        macd = self.indicators.calculate_macd(prices)
        
        self.assertIn("macd", macd)
        self.assertIn("signal", macd)
        self.assertIn("histogram", macd)

class TestRiskEngine(unittest.TestCase):
    """Test risk engine functionality."""
    
    def setUp(self):
        self.risk_engine = RiskEngine("conservative")
    
    def test_kill_switch(self):
        self.assertFalse(self.risk_engine.kill_switch.is_active)
        
        self.risk_engine.activate_kill_switch("Test")
        self.assertTrue(self.risk_engine.kill_switch.is_active)
        
        self.risk_engine.deactivate_kill_switch()
        self.assertFalse(self.risk_engine.kill_switch.is_active)
    
    def test_trade_allowed_check(self):
        decision = self.risk_engine.check_trade_allowed(
            symbol="AAPL",
            side="buy",
            quantity=10,
            current_price=150.0,
            account_value=100000
        )

        self.assertIsInstance(decision, TradeDecision)
        self.assertIsInstance(decision.allowed, bool)
        self.assertIsInstance(decision.checks, list)
        self.assertTrue(len(decision.checks) > 0)

class TestKillSwitch(unittest.TestCase):
    """Test kill switch functionality."""
    
    def setUp(self):
        import os
        ks_file = os.path.join(os.path.dirname(__file__), "..", "data", "kill_switch.json")
        if os.path.exists(ks_file):
            os.remove(ks_file)
        self.kill_switch = KillSwitch()
    
    def test_activation(self):
        result = self.kill_switch.activate("Test reason")
        self.assertTrue(result)
        self.assertTrue(self.kill_switch.is_active)
    
    def test_deactivation(self):
        self.kill_switch.activate("Test")
        result = self.kill_switch.deactivate()
        self.assertTrue(result)
        self.assertFalse(self.kill_switch.is_active)
    
    def test_auto_activate(self):
        result = self.kill_switch.check_auto_activate(0.06)  # 6% drawdown
        self.assertTrue(result)
        self.assertTrue(self.kill_switch.is_active)

class TestPositionManager(unittest.TestCase):
    """Test position manager functionality."""
    
    def setUp(self):
        self.position_manager = PositionManager(max_positions=5)
    
    def test_open_position(self):
        position = self.position_manager.open_position(
            "AAPL", "buy", 10, 150.0
        )
        
        self.assertEqual(position["symbol"], "AAPL")
        self.assertEqual(position["side"], "buy")
        self.assertEqual(position["quantity"], 10)
    
    def test_position_count_limit(self):
        for i in range(5):
            self.position_manager.open_position(f"SYM{i}", "buy", 1, 100.0)
        
        can_open = self.position_manager.can_open_position("NEW", 0.1)
        self.assertFalse(can_open)

class TestTimeControls(unittest.TestCase):
    """Test time controls functionality."""
    
    def setUp(self):
        self.time_controls = TimeControls()
    
    def test_trading_hours_check(self):
        result = self.time_controls.check_trading_hours()
        self.assertIn("allowed", result)
        self.assertIn("reason", result)
    
    def test_eod_rules_check(self):
        result = self.time_controls.check_eod_rules()
        self.assertIn("allowed", result)

class TestAIModels(unittest.TestCase):
    """Test AI model functionality."""
    
    def setUp(self):
        self.regime_detector = MarketRegimeDetector()
        self.confidence_scorer = ConfidenceScorer()
        self.momentum_decoder = MomentumDecoder()
    
    def test_regime_detection(self):
        market_data = {
            "prices": [100, 101, 102, 103, 104],
            "volatility": 0.02,
            "trend_strength": 0.6
        }
        
        result = self.regime_detector.detect_regime(market_data)
        self.assertIn("regime", result)
        self.assertIn("description", result)
    
    def test_momentum_calculation(self):
        import numpy as np
        prices = np.random.uniform(100, 200, 100)
        
        result = self.momentum_decoder.calculate_momentum(prices)
        self.assertIn("short_term", result)
        self.assertIn("medium_term", result)
        self.assertIn("long_term", result)

class TestPaperTrader(unittest.TestCase):
    """Test paper trading functionality."""
    
    def setUp(self):
        self.paper_trader = PaperTrader(initial_capital=100000)
    
    def test_start_stop(self):
        self.paper_trader.start()
        self.assertTrue(self.paper_trader.is_active)
        
        self.paper_trader.stop()
        self.assertFalse(self.paper_trader.is_active)
    
    def test_place_order(self):
        self.paper_trader.start()
        
        order = self.paper_trader.place_order(
            "AAPL", 10, "buy"
        )
        
        self.assertEqual(order["status"], "filled")
        self.assertEqual(order["symbol"], "AAPL")

class TestTradingSystem(unittest.TestCase):
    """Test complete trading system integration."""
    
    def setUp(self):
        from trading_system import TradingSystem
        self.system = TradingSystem("conservative")
    
    def test_system_start_stop(self):
        self.system.start()
        self.assertTrue(self.system.is_running)
        
        self.system.stop()
        self.assertFalse(self.system.is_running)
    
    def test_analyze_symbol(self):
        analysis = self.system.analyze_symbol("AAPL")
        self.assertIn("current_price", analysis)
        self.assertIn("regime", analysis)


class TestEngineArchitecture(unittest.TestCase):
    """Test the 3-engine architecture."""

    def test_signal_to_dict(self):
        from engines.base_engine import Signal
        s = Signal(
            symbol="AAPL", direction="BUY", price=150.0,
            confidence=0.75, reason="RSI oversold",
            target_price=155.0, stop_loss=145.0,
            signal_type="stock", fees=1.5, slippage=0.3,
        )
        d = s.to_dict()
        self.assertEqual(d["symbol"], "AAPL")
        self.assertEqual(d["direction"], "BUY")
        self.assertAlmostEqual(d["price"], 150.0)
        self.assertAlmostEqual(d["confidence"], 0.75)
        self.assertIn("reason", d)
        self.assertIn("target_price", d)
        self.assertIn("stop_loss", d)
        self.assertIn("type", d)
        self.assertIn("timestamp", d)

    def test_indicator_config_defaults(self):
        from engines.engine_config import IndicatorConfig
        c = IndicatorConfig()
        self.assertEqual(c.rsi_period, 14)
        self.assertEqual(c.rsi_oversold, 35.0)
        self.assertEqual(c.rsi_overbought, 65.0)
        self.assertEqual(c.min_signal_score, 0.40)

    def test_stock_engine_config(self):
        from engines.engine_config import StockEngineConfig
        c = StockEngineConfig()
        self.assertEqual(c.market_open_hour, 9)
        self.assertEqual(c.market_close_hour, 16)
        self.assertIn("AAPL", c.symbols)

    def test_forex_engine_config(self):
        from engines.engine_config import ForexEngineConfig
        c = ForexEngineConfig()
        self.assertEqual(c.market_open_hour, 0)
        self.assertEqual(c.market_close_hour, 24)
        self.assertIn("EUR/USD", c.pairs)

    def test_crypto_engine_config(self):
        from engines.engine_config import CryptoEngineConfig
        c = CryptoEngineConfig()
        self.assertEqual(c.market_open_hour, 0)
        self.assertEqual(c.market_close_hour, 24)
        self.assertIn("BTC/USD", c.pairs)

    def test_indicators_rsi(self):
        from engines.indicators import calculate_rsi
        prices = [100 + i * 0.5 for i in range(30)]
        rsi = calculate_rsi(prices)
        self.assertGreater(rsi, 0)
        self.assertLessEqual(rsi, 100)

    def test_indicators_macd(self):
        from engines.indicators import calculate_macd
        prices = [100 + i * 0.5 for i in range(30)]
        macd = calculate_macd(prices)
        self.assertIn("macd", macd)
        self.assertIn("signal", macd)
        self.assertIn("histogram", macd)

    def test_indicators_bollinger(self):
        from engines.indicators import calculate_bollinger
        prices = [100 + i * 0.5 for i in range(30)]
        bb = calculate_bollinger(prices)
        self.assertIn("upper", bb)
        self.assertIn("middle", bb)
        self.assertIn("lower", bb)
        self.assertGreater(bb["upper"], bb["lower"])

    def test_score_signal_direction(self):
        from engines.indicators import score_signal, calculate_bollinger
        from engines.engine_config import IndicatorConfig
        import numpy as np
        config = IndicatorConfig(rsi_oversold=35, rsi_overbought=65)
        prices = list(np.linspace(100, 120, 30))
        rsi = 75.0
        macd = {"macd": 2.0, "signal": 1.0, "histogram": 1.0}
        bb = calculate_bollinger(prices)
        result = score_signal(rsi, macd, bb, prices, prices[-1], config)
        self.assertEqual(result["direction"], "SELL")

    def test_central_risk_engine(self):
        from risk.central_risk import CentralRiskEngine
        cr = CentralRiskEngine()
        # Check kill switch starts inactive
        summary = cr.get_portfolio_summary()
        self.assertIn("positions", summary)
        # Open a position
        cr.open_position("stock", "AAPL", "BUY", 10, 150.0)
        summary = cr.get_portfolio_summary()
        self.assertIn("positions", summary)
        # Kill switch
        cr.activate_kill_switch("Test reason")
        summary2 = cr.get_portfolio_summary()
        cr.deactivate_kill_switch()

    def test_stock_engine_analyze(self):
        from engines.stock_engine import StockEngine
        se = StockEngine()
        self.assertEqual(se.market_type, "stock")
        self.assertIsInstance(se.get_symbols(), list)
        self.assertGreater(len(se.get_symbols()), 0)

    def test_forex_engine_analyze(self):
        from engines.forex_engine import ForexEngine
        fe = ForexEngine()
        self.assertEqual(fe.market_type, "forex")
        self.assertIn("EUR/USD", fe.get_symbols())

    def test_crypto_alt_engine_config(self):
        from engines.engine_config import CryptoAltEngineConfig, MEME_COINS, HOT_COINS
        c = CryptoAltEngineConfig()
        self.assertTrue(len(c.symbols) >= 10)
        self.assertIn('DOGE/USD', c.symbols)
        self.assertIn('TRUMP/USD', MEME_COINS)
        self.assertIn('SOL/USD', HOT_COINS)

    def test_commodity_engine_config(self):
        from engines.engine_config import CommodityEngineConfig
        g = CommodityEngineConfig()
        self.assertEqual(g.market_open_hour, 0)
        self.assertIn('XAU/USD', g.symbols)
        self.assertIn('XAG/USD', g.symbols)
        from engines.crypto_discovery import CryptoDiscovery, CRYPTO_UNIVERSE, CoinMomentum
        dc = CryptoDiscovery()
        self.assertTrue(len(CRYPTO_UNIVERSE) >= 40)
        self.assertIsNotNone(dc._api_key)
        # CoinMomentum object
        cm = CoinMomentum(symbol="TEST/USD", price=1.0, rsi=50, score=0.5, direction="BUY")
        self.assertEqual(cm.symbol, "TEST/USD")
        self.assertEqual(cm.direction, "BUY")


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestCalendarService(unittest.TestCase):
    """Keyless economic-calendar service (mocked feed - no network)."""

    def setUp(self):
        from backend.services import calendar_service as cs
        from backend.middleware.cache import cache
        cache.clear()
        self.cs = cs

    def test_markets_for_heuristic(self):
        self.assertEqual(
            self.cs._markets_for("US CPI Report October 2026", "economic-indicators"),
            ["commodity", "crypto", "forex", "stock"],
        )
        self.assertEqual(self.cs._markets_for("Gold Futures", ""), ["commodity"])
        self.assertEqual(
            self.cs._markets_for("FOMC Rate Decision", "central-banks-monetary-policy"),
            ["commodity", "crypto", "forex", "stock"],
        )

    def test_normalize_event(self):
        ev = self.cs._normalize({
            "name": "US CPI",
            "title": "US CPI Report October 2026",
            "impact": "high",
            "category": "economic-indicators",
            "date": "2026-10-14",
            "time_utc": "2026-10-14T12:30:00+00:00",
            "url": "https://www.financecalendar.com/event/x/",
        })
        self.assertEqual(ev["impact"], "high")
        self.assertIn("stock", ev["affected_markets"])
        self.assertEqual(ev["time_utc"], "2026-10-14T12:30:00+00:00")

    def test_upcoming_parses_mocked_feed(self):
        payload = {
            "count": 1,
            "events": [{
                "name": "US CPI",
                "title": "US CPI Report October 2026",
                "impact": "high",
                "category": "economic-indicators",
                "date": "2026-10-14",
                "time_utc": "2026-10-14T12:30:00+00:00",
                "url": "https://www.financecalendar.com/event/x/",
            }],
        }
        with mock.patch.object(self.cs.requests, "get", return_value=_FakeResp(payload)):
            events = self.cs.upcoming(days=7, impact="high")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "US CPI")

    def test_upcoming_fails_open_on_error(self):
        with mock.patch.object(self.cs.requests, "get", side_effect=RuntimeError("boom")):
            self.assertEqual(self.cs.upcoming(days=7), [])


class TestExchangeData(unittest.TestCase):
    """Keyless Binance/Bybit kline parsing (mocked - no network)."""

    def test_to_pair(self):
        from engines.exchange_data import to_pair
        self.assertEqual(to_pair("BTC/USD"), "BTCUSDT")
        self.assertEqual(to_pair("ETH/USD"), "ETHUSDT")
        self.assertEqual(to_pair("BTCUSDT"), "BTCUSDT")

    def test_binance_parse_mocked(self):
        from engines import exchange_data as ed
        payload = [[1791849600000, "81852.1", "84172.6", "81031.2", "83172", "1", 0, "0", 0, "0", "0", "0"]]
        with mock.patch.object(ed.requests, "get", return_value=_FakeResp(payload)):
            bars = ed._binance_klines("BTCUSDT", "1day", 1)
        self.assertEqual(bars[0]["close"], 83172.0)
        self.assertEqual(bars[0]["open"], 81852.1)

    def test_bybit_parse_mocked_newest_first(self):
        from engines import exchange_data as ed
        payload = {"retCode": 0, "result": {"list": [
            ["1791936000000", "83172", "84137.6", "83027.4", "83657.8", "1", "1"],
            ["1791849600000", "81852.1", "84172.6", "81031.2", "83172", "1", "1"],
        ]}}
        with mock.patch.object(ed.requests, "get", return_value=_FakeResp(payload)):
            bars = ed._bybit_klines("BTCUSDT", "1day", 2)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["close"], 83172.0)
        self.assertLess(bars[0]["time"], bars[1]["time"])

    def test_fetch_klines_falls_back_to_bybit(self):
        from engines import exchange_data as ed
        ed._down_until.clear()
        bybit = {"retCode": 0, "result": {"list": [["1791849600000", "1", "2", "0.5", "1.5", "1", "1"]]}}

        def fake_get(url, params=None, timeout=None):
            if "binance" in url:
                raise RuntimeError("blocked")
            return _FakeResp(bybit)

        with mock.patch.object(ed.requests, "get", side_effect=fake_get):
            bars, provider = ed.fetch_klines("BTC/USD", "1day", 5)
        self.assertEqual(provider, "bybit")
        self.assertEqual(len(bars), 1)

    def test_fetch_klines_empty_when_all_fail(self):
        from engines import exchange_data as ed
        ed._down_until.clear()
        with mock.patch.object(ed.requests, "get", side_effect=RuntimeError("down")):
            bars, provider = ed.fetch_klines("BTC/USD", "1day", 5)
        self.assertEqual(bars, [])
        self.assertIsNone(provider)

    def test_probe_reports_each_provider(self):
        from engines import exchange_data as ed
        with mock.patch.object(ed.requests, "get", side_effect=RuntimeError("down")):
            rows = ed.probe("BTC/USD", "1day", 3)
        self.assertEqual([r["provider"] for r in rows], list(ed.DEFAULT_ORDER))
        self.assertTrue(all(r["ok"] is False for r in rows))


class _FakeWeb:
    def __init__(self, payload=None, text=""):
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class TestTradFiData(unittest.TestCase):
    """Keyless Yahoo/Stooq/Frankfurter parsing for stocks/forex/commodities."""

    def setUp(self):
        from engines import tradfi_data as td
        td._down_until.clear()

    def test_symbol_mapping(self):
        from engines import tradfi_data as td
        self.assertEqual(td._yahoo_symbol("EUR/USD", "forex"), "EURUSD=X")
        self.assertEqual(td._yahoo_symbol("XAU/USD", "commodity"), "GC=F")
        self.assertEqual(td._yahoo_symbol("AAPL", "stock"), "AAPL")
        self.assertEqual(td._stooq_symbol("EUR/USD", "forex"), "eurusd")
        self.assertEqual(td._stooq_symbol("AAPL", "stock"), "aapl.us")

    def test_yahoo_parse_mocked(self):
        from engines import tradfi_data as td
        payload = {"chart": {"result": [{
            "timestamp": [1791849600, 1791936000],
            "indicators": {"quote": [{
                "open": [81852.1, 83172.0],
                "high": [84172.6, 84137.6],
                "low": [81031.2, 83027.4],
                "close": [83172.0, 83657.8],
            }]},
        }], "error": None}}
        with mock.patch.object(td.requests, "get", return_value=_FakeWeb(payload=payload)):
            bars, source = td.fetch_bars("AAPL", "1day", 5, "stock")
        self.assertEqual(source, "yahoo")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[-1]["close"], 83657.8)

    def test_stooq_parse_mocked(self):
        from engines import tradfi_data as td
        csv_text = (
            "Date,Open,High,Low,Close,Volume\n"
            "2025-10-01,100,110,90,105,1000\n"
            "2025-10-02,105,115,95,110,1200\n"
        )
        with mock.patch.object(td.requests, "get", return_value=_FakeWeb(text=csv_text)):
            bars = td._stooq_bars("AAPL", "1day", 5, "stock")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[-1]["close"], 110.0)

    def test_fetch_bars_falls_back_to_stooq(self):
        from engines import tradfi_data as td
        csv_text = "Date,Open,High,Low,Close,Volume\n2025-10-02,105,115,95,110,1200\n"

        def fake_get(url, params=None, timeout=None, headers=None):
            if "finance.yahoo" in url:
                raise RuntimeError("blocked")
            return _FakeWeb(text=csv_text)

        with mock.patch.object(td.requests, "get", side_effect=fake_get):
            bars, source = td.fetch_bars("EUR/USD", "1day", 5, "forex")
        self.assertEqual(source, "stooq")
        self.assertEqual(len(bars), 1)

    def test_fetch_bars_empty_when_all_fail(self):
        from engines import tradfi_data as td
        with mock.patch.object(td.requests, "get", side_effect=RuntimeError("down")):
            bars, source = td.fetch_bars("AAPL", "1day", 5, "stock")
        self.assertEqual(bars, [])
        self.assertIsNone(source)

    def test_frankfurter_close_fallback(self):
        from engines import tradfi_data as td
        payload = {"rates": {"2025-10-01": {"USD": 1.09}, "2025-10-02": {"USD": 1.10}}}

        def fake_get(url, params=None, timeout=None, headers=None):
            if "finance.yahoo" in url or "stooq" in url:
                raise RuntimeError("blocked")
            return _FakeWeb(payload=payload)

        with mock.patch.object(td.requests, "get", side_effect=fake_get):
            closes, source = td.fetch_closes("EUR/USD", 5, "forex")
        self.assertEqual(source, "frankfurter")
        self.assertEqual(closes, [1.09, 1.10])

    def test_fetch_quote_mocked(self):
        from engines import tradfi_data as td
        payload = {"chart": {"result": [{"meta": {
            "regularMarketPrice": 2400.0,
            "chartPreviousClose": 2380.0,
        }}]}}
        with mock.patch.object(td.requests, "get", return_value=_FakeWeb(payload=payload)):
            q = td.fetch_quote("XAU/USD", "commodity")
        self.assertEqual(q["price"], 2400.0)
        self.assertAlmostEqual(q["change_percent"], 0.8403, places=3)


class TestCryptoEngineData(unittest.TestCase):
    """Crypto engine + discovery prefer keyless exchange data."""

    def test_engine_uses_exchange_data(self):
        from engines import exchange_data as ed
        from engines.crypto_engine import CryptoEngine
        prices = [100.0 + i for i in range(30)]
        with mock.patch.object(ed, "fetch_prices", return_value=prices):
            self.assertEqual(CryptoEngine().fetch_prices("BTC/USD", 30), prices)

    def test_engine_simulated_fallback(self):
        from engines import exchange_data as ed
        from engines.crypto_engine import CryptoEngine
        eng = CryptoEngine()
        eng._api_key = ""
        with mock.patch.object(ed, "fetch_prices", return_value=[]):
            out = eng.fetch_prices("BTC/USD", 30)
        self.assertEqual(len(out), 30)

    def test_discovery_uses_exchange_data(self):
        from engines import exchange_data as ed
        from engines.crypto_discovery import CryptoDiscovery
        prices = [1.0 + i * 0.1 for i in range(30)]
        with mock.patch.object(ed, "fetch_prices", return_value=prices):
            with mock.patch.object(CryptoDiscovery, "_save_cache", lambda self: None):
                out = CryptoDiscovery()._fetch_batch(["BTC/USD", "ETH/USD"], 30)
        self.assertEqual(set(out), {"BTC/USD", "ETH/USD"})
        self.assertAlmostEqual(out["BTC/USD"][-1], prices[-1])


class _FakePrefsDB:
    """Minimal in-memory stand-in for SupabaseDB used by preferences/webhook."""

    def __init__(self, prefs=None):
        self._prefs = dict(prefs or {"id": "p1", "user_id": "u1"})
        self.updates = []

    async def fetch_one(self, table, where=None, columns="*"):
        return dict(self._prefs)

    async def insert(self, table, data):
        self._prefs.update(data)
        return dict(self._prefs)

    async def update(self, table, data, where=None):
        self.updates.append(data)
        self._prefs.update(data)
        return [dict(self._prefs)]


class TestSignalFilters(unittest.TestCase):
    """Phase C: watchlist / direction / min-confidence filters."""

    def test_empty_filters_pass_everything(self):
        from backend.services.preferences_service import matches_filters
        prefs = {"watchlist": [], "directions": [], "min_confidence": 0}
        self.assertTrue(matches_filters(prefs, {"symbol": "BTC", "direction": "buy", "confidence": 0.1}))

    def test_watchlist_and_direction_and_confidence(self):
        from backend.services.preferences_service import matches_filters
        prefs = {"watchlist": ["BTC"], "directions": ["buy"], "min_confidence": 0.6}
        ok = {"symbol": "BTC", "direction": "BUY", "confidence": 0.7}
        self.assertTrue(matches_filters(prefs, ok))
        self.assertFalse(matches_filters(prefs, {"symbol": "ETH", "direction": "buy", "confidence": 0.9}))
        self.assertFalse(matches_filters(prefs, {"symbol": "BTC", "direction": "sell", "confidence": 0.9}))
        self.assertFalse(matches_filters(prefs, {"symbol": "BTC", "direction": "buy", "confidence": 0.5}))

    def test_missing_confidence_not_disqualifying(self):
        from backend.services.preferences_service import matches_filters
        prefs = {"watchlist": [], "directions": [], "min_confidence": 0.9}
        self.assertTrue(matches_filters(prefs, {"symbol": "X", "direction": "buy"}))

    def test_normalizers(self):
        from backend.services.preferences_service import (
            _norm_watchlist, _norm_directions, _norm_min_confidence,
        )
        self.assertEqual(_norm_watchlist(" btc , eth , btc ,"), ["BTC", "ETH"])
        self.assertEqual(_norm_directions(["Buy", "HOLD", "sell", "buy"]), ["buy", "sell"])
        self.assertEqual(_norm_min_confidence(1.7), 1.0)
        self.assertEqual(_norm_min_confidence(-2), 0.0)
        self.assertEqual(_norm_min_confidence("abc"), 0.0)


class TestTelegramCommands(unittest.TestCase):
    """Phase C: two-way bot command parsing + dispatch."""

    def test_parse_command(self):
        from backend.api.telegram import parse_command
        self.assertEqual(parse_command("/watch BTC,ETH"), ("watch", "BTC,ETH"))
        self.assertEqual(parse_command("/help@TradeAIbot extra"), ("help", "extra"))
        self.assertEqual(parse_command("/"), ("", ""))
        self.assertEqual(parse_command("just chatting"), (None, "just chatting"))
        self.assertEqual(parse_command(None), (None, ""))
        self.assertEqual(parse_command("   /Status   "), ("status", ""))

    def test_dispatch_unlinked_chat_gets_link_hint(self):
        from backend.api.telegram import dispatch_command
        import asyncio
        db = _FakePrefsDB()
        out = asyncio.run(dispatch_command(db, None, "status", "", "123456"))
        self.assertIn("123456", out)
        self.assertIn("link", out.lower())

    def test_dispatch_mutates_filters(self):
        from backend.api.telegram import dispatch_command
        from backend.services import preferences_service as prefs_service
        import asyncio

        db = _FakePrefsDB({"id": "p1", "user_id": "u1"})
        user = {"id": "u1", "tier": "free", "username": "alice"}

        asyncio.run(dispatch_command(db, user, "watch", "btc , eth", "c"))
        self.assertEqual(db._prefs["watchlist"], ["BTC", "ETH"])

        asyncio.run(dispatch_command(db, user, "directions", "buy", "c"))
        self.assertEqual(db._prefs["directions"], ["buy"])

        asyncio.run(dispatch_command(db, user, "minconf", "0.65", "c"))
        self.assertEqual(db._prefs["min_confidence"], 0.65)

        asyncio.run(dispatch_command(db, user, "digest", "off", "c"))
        self.assertIs(db._prefs["telegram_weekly_digest"], False)

        asyncio.run(dispatch_command(db, user, "mute", "", "c"))
        self.assertIs(db._prefs["telegram_signals"], False)
        asyncio.run(dispatch_command(db, user, "unmute", "", "c"))
        self.assertIs(db._prefs["telegram_signals"], True)

        # clearing works
        asyncio.run(dispatch_command(db, user, "watch", "", "c"))
        self.assertEqual(db._prefs["watchlist"], [])

        # status reflects state and tier
        out = asyncio.run(dispatch_command(db, user, "status", "", "c"))
        self.assertIn("free", out)
        self.assertIn("Watchlist", out)

        # unknown command
        out = asyncio.run(dispatch_command(db, user, "wat", "", "c"))
        self.assertIn("Unknown", out)

        # minconf bad input
        out = asyncio.run(dispatch_command(db, user, "minconf", "abc", "c"))
        self.assertIn("Usage", out)

        # sanitizer actually filtered directions through EDITABLE
        self.assertTrue(db.updates)

    def test_dispatch_watch_uses_sanitizer(self):
        from backend.api.telegram import dispatch_command
        import asyncio
        db = _FakePrefsDB({"id": "p1", "user_id": "u1"})
        user = {"id": "u1", "tier": "premium", "username": "bob"}
        asyncio.run(dispatch_command(db, user, "watch", "aapl,  aapl, msft , ,42", "c"))
        self.assertEqual(db._prefs["watchlist"], ["AAPL", "MSFT", "42"])


class TestWeeklyDigest(unittest.TestCase):
    """Phase C: digest scheduling + rendering."""
    def test_should_send_digest_schedule(self):
        from backend.services.scheduler import should_send_digest
        sunday_evening = datetime(2026, 10, 18, 19, 0)
        self.assertTrue(should_send_digest(sunday_evening, None, 18))
        self.assertFalse(should_send_digest(datetime(2026, 10, 18, 17, 0), None, 18))
        self.assertFalse(should_send_digest(datetime(2026, 10, 17, 19, 0), None, 18))
        self.assertFalse(should_send_digest(sunday_evening, "2026-10-18", 18))
        self.assertTrue(should_send_digest(sunday_evening, "2026-10-11", 18))

    def test_format_weekly_digest(self):
        from backend.services.telegram_service import format_weekly_digest
        stats = {
            "generated": 42,
            "overall": {"resolved": 20, "wins": 13, "losses": 7, "win_rate": 0.65, "avg_r": 1.4},
            "by_market": {"crypto": {"resolved": 10, "win_rate": 0.8}, "forex": {"resolved": 5, "win_rate": 0.4}},
        }
        out = format_weekly_digest(stats)
        self.assertIn("Weekly digest", out)
        self.assertIn("65.0%", out)
        self.assertIn("Crypto", out)

    def test_format_weekly_digest_empty(self):
        from backend.services.telegram_service import format_weekly_digest
        out = format_weekly_digest({})
        self.assertIn("No resolved signals yet", out)


class _FakeTradeDB:
    """In-memory stand-in for SupabaseDB scoped to demo-account logic."""

    def __init__(self, prefs=None, rows=None):
        self._prefs = dict(prefs or {})
        self.rows = [dict(r) for r in (rows or [])]

    @staticmethod
    def _match(row, where):
        for k, v in (where or {}).items():
            if isinstance(v, dict) and "op" in v:
                op, val, rv = v["op"], v.get("value"), row.get(k)
                if rv is None:
                    return False
                if op == "gte" and not rv >= val:
                    return False
                if op == "lte" and not rv <= val:
                    return False
                if op == "gt" and not rv > val:
                    return False
                if op == "lt" and not rv < val:
                    return False
            elif row.get(k) != v:
                return False
        return True

    async def fetch_one(self, table, where=None, columns="*"):
        return dict(self._prefs) if self._prefs else None

    async def fetch_all(self, table, where=None, columns="*"):
        return [dict(r) for r in self.rows if self._match(r, where)]

    async def count(self, table, where=None):
        return sum(1 for r in self.rows if self._match(r, where))

    async def delete(self, table, where=None):
        removed = [r for r in self.rows if self._match(r, where)]
        self.rows = [r for r in self.rows if not self._match(r, where)]
        return removed


class TestDemoAccounts(unittest.TestCase):
    """Phase D: virtual/demo ledger isolation + balance."""

    def test_starting_balance_from_prefs(self):
        import asyncio
        from backend.services.trade_service import get_starting_balance, DEFAULT_STARTING_BALANCE
        db = _FakeTradeDB({"user_id": "u1", "demo_starting_balance": 250000})
        self.assertEqual(asyncio.run(get_starting_balance(db, "u1", is_demo=True)), 250000.0)
        self.assertEqual(asyncio.run(get_starting_balance(db, "u1", is_demo=False)), DEFAULT_STARTING_BALANCE)

    def test_reset_demo_clears_only_demo_trades(self):
        import asyncio
        from backend.services.trade_service import reset_demo
        db = _FakeTradeDB(
            {"user_id": "u1", "demo_starting_balance": 50000},
            [
                {"id": "a", "user_id": "u1", "is_demo": True, "status": "closed", "pnl": 100},
                {"id": "b", "user_id": "u1", "is_demo": False, "status": "closed", "pnl": 999},
            ],
        )
        res = asyncio.run(reset_demo(db, "u1"))
        self.assertEqual(res["deleted"], 1)
        self.assertEqual(res["starting_balance"], 50000.0)
        self.assertEqual([t["id"] for t in db.rows], ["b"])

    def test_demo_account_snapshot(self):
        import asyncio
        from backend.services.trade_service import get_demo_account
        db = _FakeTradeDB(
            {"user_id": "u1", "demo_starting_balance": 10000},
            [
                {"id": "a", "user_id": "u1", "is_demo": True, "status": "closed", "pnl": 150},
                {"id": "b", "user_id": "u1", "is_demo": True, "status": "closed", "pnl": -50},
                {"id": "c", "user_id": "u1", "is_demo": True, "status": "open"},
                {"id": "d", "user_id": "u1", "is_demo": False, "status": "closed", "pnl": 500},
            ],
        )
        snap = asyncio.run(get_demo_account(db, "u1"))
        self.assertEqual(snap["starting_balance"], 10000.0)
        self.assertEqual(snap["realized_pnl"], 100.0)
        self.assertEqual(snap["portfolio_value"], 10100.0)
        self.assertEqual(snap["open_positions"], 1)
        self.assertEqual(snap["closed_trades"], 2)

    def test_risk_status_uses_demo_balance(self):
        import asyncio
        from backend.services.risk_service import get_risk_status
        db = _FakeTradeDB(
            {"user_id": "u1", "demo_starting_balance": 10000},
            [
                {"id": "a", "user_id": "u1", "is_demo": True, "status": "closed", "pnl": 250},
                {"id": "z", "user_id": "u1", "is_demo": False, "status": "closed", "pnl": 99999},
            ],
        )
        status = asyncio.run(get_risk_status(db, "u1", is_demo=True))
        self.assertEqual(status["account_value"], 10250.0)


class _FakeResetDB:
    def __init__(self, user):
        self.user = user
        self.inserts = []

    async def fetch_one(self, table, where, columns=None):
        from backend.db.models import USERS

        return self.user if table == USERS else None

    async def insert(self, table, row):
        self.inserts.append((table, row))
        return row


class TestPasswordResetEmail(unittest.TestCase):
    """Phase E: reset-link construction, SMTP toggle and fallback delivery."""

    def test_reset_email_embeds_link(self):
        from backend.services.email_service import reset_email
        subject, html = reset_email("u@test.dev", "https://app.orqeva.test/reset?token=abc123")
        self.assertIn("password reset", subject.lower())
        self.assertIn("https://app.orqeva.test/reset?token=abc123", html)

    def test_absolute_link_joins_base(self):
        from backend.api.auth import _absolute_link
        from backend.config import settings as st
        orig = st.APP_BASE_URL
        try:
            st.APP_BASE_URL = "https://app.orqeva.test/"
            self.assertEqual(_absolute_link("/reset?token=x"), "https://app.orqeva.test/reset?token=x")
            st.APP_BASE_URL = "https://app.orqeva.test"
            self.assertEqual(_absolute_link("/reset?token=x"), "https://app.orqeva.test/reset?token=x")
            st.APP_BASE_URL = ""
            self.assertEqual(_absolute_link("/reset?token=x"), "/reset?token=x")
        finally:
            st.APP_BASE_URL = orig

    def test_send_email_disabled_is_false(self):
        import asyncio
        from backend.config import settings as st
        from backend.services import email_service
        orig = st.SMTP_HOST
        try:
            st.SMTP_HOST = ""
            self.assertFalse(email_service.is_configured())
            self.assertFalse(asyncio.run(email_service.send_email("u@test.dev", "s", "<p>x</p>")))
        finally:
            st.SMTP_HOST = orig

    def test_forgot_fallback_delivers_link(self):
        import asyncio
        from backend.api.auth import ForgotRequest, forgot_password
        from backend.config import settings as st
        from backend.db.models import NOTIFICATIONS, PASSWORD_RESET_TOKENS
        db = _FakeResetDB({"id": "u1", "email": "u@test.dev", "is_active": True,
                           "telegram_chat_id": None, "tier": "free"})
        orig_host, orig_base = st.SMTP_HOST, st.APP_BASE_URL
        try:
            st.SMTP_HOST = ""
            st.APP_BASE_URL = "https://app.orqeva.test"
            res = asyncio.run(forgot_password(ForgotRequest(email="u@test.dev"), db=db))
        finally:
            st.SMTP_HOST, st.APP_BASE_URL = orig_host, orig_base
        self.assertEqual(res["status"], "ok")
        self.assertTrue(any(t == PASSWORD_RESET_TOKENS for t, _ in db.inserts))
        notes = [r for t, r in db.inserts if t == NOTIFICATIONS]
        self.assertEqual(len(notes), 1)
        self.assertIn("https://app.orqeva.test/reset?token=", notes[0]["message"])

    def test_forgot_email_path_skips_fallback(self):
        import asyncio
        from unittest import mock
        from backend.api.auth import ForgotRequest, forgot_password
        from backend.config import settings as st
        from backend.db.models import NOTIFICATIONS
        from backend.services import email_service
        db = _FakeResetDB({"id": "u1", "email": "u@test.dev", "is_active": True,
                           "telegram_chat_id": None, "tier": "free"})
        orig = st.APP_BASE_URL
        try:
            st.APP_BASE_URL = "https://app.orqeva.test"
            with mock.patch.object(email_service, "is_configured", return_value=True), \
                 mock.patch.object(email_service, "send_email", new=mock.AsyncMock(return_value=True)):
                asyncio.run(forgot_password(ForgotRequest(email="u@test.dev"), db=db))
        finally:
            st.APP_BASE_URL = orig
        self.assertFalse(any(t == NOTIFICATIONS for t, _ in db.inserts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
