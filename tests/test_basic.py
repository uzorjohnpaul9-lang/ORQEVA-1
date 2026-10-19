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


class TestMarketSentiment(unittest.TestCase):
    """Phase H: keyless sentiment feeds + confidence modifier (never raises)."""

    def setUp(self):
        from engines import market_sentiment as ms
        self.ms = ms
        self._down = dict(ms._down_until)
        ms._down_until.clear()
        ms._cache.clear()

    def tearDown(self):
        self.ms._down_until.clear()
        self.ms._down_until.update(self._down)
        self.ms._cache.clear()

    def _resp(self, payload):
        r = mock.Mock()
        r.raise_for_status.return_value = None
        r.json.return_value = payload
        return r

    def test_orderbook_imbalance_computes_and_clamps(self):
        payload = {"bids": [["100", "5"], ["99", "5"]], "asks": [["101", "1"], ["102", "1"]]}
        with mock.patch.object(self.ms.requests, "get", return_value=self._resp(payload)):
            out = self.ms.orderbook_imbalance("BTC/USD")
        self.assertIsNotNone(out)
        self.assertEqual(out["source"], "binance_us")
        self.assertGreater(out["imbalance"], 0)   # bid-heavy
        self.assertTrue(-1.0 <= out["imbalance"] <= 1.0)

    def test_orderbook_failure_returns_none_not_raise(self):
        with mock.patch.object(self.ms.requests, "get", side_effect=RuntimeError("down")):
            self.assertIsNone(self.ms.orderbook_imbalance("BTC/USD"))
        self.assertTrue(self.ms._down_until)  # cooldown marked

    def test_fear_greed_parses_value(self):
        payload = {"data": [{"value": "78", "value_classification": "Greed"},
                            {"value": "65", "value_classification": "Greed"}]}
        with mock.patch.object(self.ms.requests, "get", return_value=self._resp(payload)):
            out = self.ms.fear_greed()
        self.assertEqual(out["value"], 78)
        self.assertEqual(out["prev_value"], 65)

    def test_btc_dominance_parses(self):
        payload = {"data": {"market_cap_percentage": {"btc": 52.5},
                            "total_market_cap": {"usd": 2.1e12}}}
        with mock.patch.object(self.ms.requests, "get", return_value=self._resp(payload)):
            out = self.ms.btc_dominance()
        self.assertEqual(out["btc_dominance"], 52.5)

    def test_sentiment_no_feeds_is_noop(self):
        with mock.patch.object(self.ms, "orderbook_imbalance", return_value=None), \
             mock.patch.object(self.ms, "funding_oi", return_value=None), \
             mock.patch.object(self.ms, "fear_greed", return_value=None), \
             mock.patch.object(self.ms, "btc_dominance", return_value=None):
            out = self.ms.sentiment_for("BTC/USD", "BUY")
        self.assertFalse(out["available"])
        self.assertEqual(out["modifier"], 0.0)
        self.assertIsNone(out["tag"])

    def test_sentiment_modifier_never_exceeds_cap(self):
        ob = {"imbalance": 1.0, "bid_volume": 10, "ask_volume": 0, "source": "coinbase"}
        fo = {"funding_rate": -0.001, "open_interest": 1.0, "source": "bybit"}
        fg = {"value": 20, "classification": "Fear", "prev_value": 30, "source": "alternative.me"}
        bd = {"btc_dominance": 58.0, "source": "coingecko"}
        with mock.patch.object(self.ms, "orderbook_imbalance", return_value=ob), \
             mock.patch.object(self.ms, "funding_oi", return_value=fo), \
             mock.patch.object(self.ms, "fear_greed", return_value=fg), \
             mock.patch.object(self.ms, "btc_dominance", return_value=bd):
            out = self.ms.sentiment_for("ETH/USD", "BUY")
        self.assertTrue(out["available"])
        self.assertTrue(-self.ms.MAX_ADJUST <= out["modifier"] <= self.ms.MAX_ADJUST)

    def test_crowded_longs_tag_on_extreme_funding(self):
        fo = {"funding_rate": 0.001, "open_interest": 100.0, "source": "bybit"}
        with mock.patch.object(self.ms, "orderbook_imbalance", return_value=None), \
             mock.patch.object(self.ms, "funding_oi", return_value=fo), \
             mock.patch.object(self.ms, "fear_greed", return_value=None), \
             mock.patch.object(self.ms, "btc_dominance", return_value=None):
            out = self.ms.sentiment_for("BTC/USD", "BUY")
        self.assertIn("crowded_longs", out["tag"])
        self.assertLess(out["modifier"], 0)

    def test_probe_never_raises_when_all_down(self):
        with mock.patch.object(self.ms.requests, "get", side_effect=RuntimeError("down")):
            rows = self.ms.probe("BTC/USD")
        self.assertEqual([r["feed"] for r in rows],
                         ["orderflow", "derivatives", "fear_greed", "btc_dominance"])
        self.assertTrue(all(r["ok"] is False for r in rows))

    def test_base_engine_hooks_sentiment_for_crypto(self):
        from engines import base_engine as be
        from unittest import mock as m

        class _Crypto(be.BaseEngine):
            market_type = "crypto"
            risk_params = be.EngineRiskParams(max_position_size=0.1, max_daily_trades=5, max_positions=3, stop_loss_pct=0.02, take_profit_pct=0.04, trailing_stop_pct=0.01, max_spread_pct=0.01, fee_per_trade=0.0, fee_percentage=0.001)
            indicator_config = be.IndicatorConfig()
            fetch_prices = lambda self, s, n: [100.0] * 40
            get_symbols = lambda self: ["BTC/USD"]
            is_market_hours = lambda self: True
            calculate_fees = lambda self, s, q, p: 0.0
            calculate_slippage = lambda self, s, q, p: 0.0
            calculate_position_size = lambda self, s, p, a: 1.0

        eng = _Crypto()
        fake = {"available": True, "modifier": -0.05, "tag": "crowded_longs", "feeds": {}}
        with m.patch.object(be, "score_signal",
                            return_value={"direction": "BUY", "confidence": 0.72,
                                          "reasons": ["rsi"]}), \
             m.patch("engines.market_sentiment.sentiment_for", return_value=fake):
            sig = eng.analyze("BTC/USD")
        self.assertIsNotNone(sig)
        self.assertIn("[sentiment: crowded_longs]", sig.reason)
        self.assertAlmostEqual(sig.confidence, 0.67, places=2)
        self.assertEqual(sig.metadata["sentiment"]["tag"], "crowded_longs")

    def test_base_engine_sentiment_noop_for_stock(self):
        from engines import base_engine as be
        from unittest import mock as m

        class _Stock(be.BaseEngine):
            market_type = "stock"
            risk_params = be.EngineRiskParams(max_position_size=0.1, max_daily_trades=5, max_positions=3, stop_loss_pct=0.02, take_profit_pct=0.04, trailing_stop_pct=0.01, max_spread_pct=0.01, fee_per_trade=0.0, fee_percentage=0.001)
            indicator_config = be.IndicatorConfig()
            fetch_prices = lambda self, s, n: [100.0] * 40
            get_symbols = lambda self: ["AAPL"]
            is_market_hours = lambda self: True
            calculate_fees = lambda self, s, q, p: 0.0
            calculate_slippage = lambda self, s, q, p: 0.0
            calculate_position_size = lambda self, s, p, a: 1.0

        eng = _Stock()
        with m.patch.object(be, "score_signal",
                            return_value={"direction": "BUY", "confidence": 0.72,
                                          "reasons": ["rsi"]}), \
             m.patch("engines.market_sentiment.sentiment_for",
                     side_effect=AssertionError("should not be called")):
            sig = eng.analyze("AAPL")
        self.assertIsNotNone(sig)
        self.assertNotIn("[sentiment", sig.reason)
        self.assertFalse(sig.metadata["sentiment"]["available"])


class TestSentinelMiddleware(unittest.TestCase):
    """Phase G: honeypot / injection / auto-block request pipeline."""

    def _client(self, **kw):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.middleware import sentinel
        from backend.middleware.sentinel import SentinelMiddleware

        sentinel._blocked.clear()
        sentinel._failures.clear()
        sentinel._blocklist_loaded_at = 0.0

        app = FastAPI()

        @app.get("/api/health")
        def health():
            return {"ok": True}

        app.add_middleware(SentinelMiddleware)
        for k, v in kw.items():
            setattr(sentinel, k, v)
        return TestClient(app, raise_server_exceptions=False)

    def setUp(self):
        from backend.middleware import sentinel
        self.sentinel = sentinel
        self._blocked_orig = dict(sentinel._blocked)
        self._fail_orig = {k: list(v) for k, v in sentinel._failures.items()}
        self._persist_calls = []
        # never hit the network in tests
        async def _noop_event(ip, kind, severity, details):
            self._persist_calls.append(("event", ip, kind, severity))
        async def _noop_block(ip, reason, ttl):
            self._persist_calls.append(("block", ip, reason, ttl))
        async def _noop_load(force=False):
            return None
        self._patches = [
            mock.patch.object(sentinel, "_persist_event", new=_noop_event),
            mock.patch.object(sentinel, "_persist_block", new=_noop_block),
            mock.patch.object(sentinel, "_load_blocks", new=_noop_load),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        from backend.middleware import sentinel
        for p in self._patches:
            p.stop()
        sentinel._blocked.clear()
        sentinel._blocked.update(self._blocked_orig)
        sentinel._failures.clear()
        sentinel._failures.update(self._fail_orig)

    def test_clean_request_passes(self):
        c = self._client()
        r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

    def test_honeypot_returns_404_and_blocks(self):
        c = self._client()
        r = c.get("/wp-admin/setup-config.php")
        self.assertEqual(r.status_code, 404)
        # same IP now blocked
        r2 = c.get("/api/health")
        self.assertEqual(r2.status_code, 403)
        self.assertTrue(any(p[0] == "block" for p in self._persist_calls))

    def test_env_probe_returns_404_and_blocks(self):
        c = self._client()
        r = c.get("/.env")
        # .env is a honeypot path -> always 404, and the IP gets blocked
        self.assertEqual(r.status_code, 404)
        r2 = c.get("/api/health")
        self.assertEqual(r2.status_code, 403)

    def test_sqli_in_query_is_blocked(self):
        c = self._client()
        r = c.get("/api/health?q=1' OR '1'='1")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(any(p[0] == "block" for p in self._persist_calls))

    def test_xss_in_query_is_blocked(self):
        c = self._client()
        r = c.get("/api/health?q=<script>alert(1)</script>")
        self.assertEqual(r.status_code, 403)

    def test_traversal_is_blocked(self):
        c = self._client()
        r = c.get("/api/health?q=../../etc/passwd")
        self.assertEqual(r.status_code, 403)

    def test_preblocked_ip_forbidden(self):
        from backend.middleware import sentinel
        sentinel.block_ip("1.2.3.4", 60)
        c = self._client()
        # TestClient sends from "testclient" host, so seed that instead
        sentinel.block_ip("testclient", 60)
        r = c.get("/api/health")
        self.assertEqual(r.status_code, 403)

    def test_auth_spike_blocks_after_threshold(self):
        from backend.middleware import sentinel
        n = 0
        for _ in range(sentinel.BLOCK_AFTER + 5):
            n = sentinel._note_failure("9.9.9.9")
        self.assertGreaterEqual(n, sentinel.BLOCK_AFTER)
        self.assertGreater(sentinel.BLOCK_AFTER, sentinel.AUTH_FAIL_LIMIT)

    def test_success_clears_failure_streak(self):
        from backend.middleware import sentinel
        c = self._client()
        for _ in range(3):
            sentinel._note_failure("testclient")
        self.assertTrue(sentinel._failures.get("testclient"))
        c.get("/api/health")  # 200 clears
        self.assertFalse(sentinel._failures.get("testclient"))

    def test_client_ip_prefers_cf_header(self):
        from starlette.requests import Request
        scope = {
            "type": "http", "method": "GET", "path": "/", "query_string": b"",
            "headers": [(b"cf-connecting-ip", b"5.6.7.8")],
            "client": ("9.9.9.9", 1), "scheme": "http", "server": ("t", 1),
        }
        self.assertEqual(self.sentinel.client_ip(Request(scope)), "5.6.7.8")

    def test_sentinel_never_raises_on_dispatch_error(self):
        c = self._client()
        # unknown route -> 404 from FastAPI, not a sentinel failure
        r = c.get("/definitely/not/a/route")
        self.assertEqual(r.status_code, 404)


class TestSentinelService(unittest.TestCase):
    """Phase G: event recording + blocklist helpers (failure-tolerant)."""

    def test_kinds_and_severities_are_constrained(self):
        from backend.services import sentinel_service as ss
        self.assertIn("login_fail", ss.KINDS)
        self.assertIn("suspicious", ss.KINDS)
        self.assertIn("critical", ss.SEVERITIES)
        self.assertEqual(set(ss.HIGH), {"high", "critical"})

    def test_record_never_raises_when_db_fails(self):
        import asyncio
        from backend.services import sentinel_service as ss

        class BrokenDB:
            async def insert(self, *a, **k):
                raise RuntimeError("db down")

        out = asyncio.run(ss.record_anomaly(BrokenDB(), kind="anomaly",
                                             severity="high", ip="1.1.1.1"))
        self.assertIsNone(out)

    def test_login_fail_severity_escalates_with_count(self):
        import asyncio
        from backend.services import sentinel_service as ss

        class DB:
            def __init__(self):
                self.sev = None
            async def insert(self, table, row):
                self.sev = row["severity"]
                return row
            async def fetch_all(self, *a, **k):
                return []

        ss._windows.clear()
        db = DB()
        for _ in range(10):
            asyncio.run(ss.record_login_fail(db, ip="2.2.2.2", email="a@b.c"))
        self.assertEqual(db.sev, "high")

    def test_list_blocks_and_unblock_tolerant(self):
        import asyncio
        from backend.services import sentinel_service as ss

        class BrokenDB:
            async def fetch_all(self, *a, **k):
                raise RuntimeError("down")
            async def update(self, *a, **k):
                raise RuntimeError("down")

        rows = asyncio.run(ss.list_blocks(BrokenDB()))
        self.assertEqual(rows, [])
        out = asyncio.run(ss.unblock(BrokenDB(), "1.2.3.4", {"id": "adm"}))
        self.assertIsNone(out)


class _FakeBillingDB:
    """Generic in-memory table store for billing_service tests (Phase I)."""

    def __init__(self):
        self.tables = {
            "invoices": [], "subscriptions": [], "users": [],
            "payment_events": [], "promo_codes": [], "user_preferences": [],
        }

    @staticmethod
    def _match(row, where):
        if not where:
            return True
        for k, v in where.items():
            if isinstance(v, (list, tuple, set)):
                if row.get(k) not in v:
                    return False
            elif row.get(k) != v:
                return False
        return True

    async def fetch_one(self, table, where=None, columns="*"):
        rows = [dict(r) for r in self.tables.get(table, []) if self._match(r, where)]
        return rows[0] if rows else None

    async def fetch_all(self, table, where=None, order=None, limit=None, columns="*"):
        rows = [dict(r) for r in self.tables.get(table, []) if self._match(r, where)]
        if order and "." in str(order):
            col, _, direction = str(order).partition(".")
            rows.sort(key=lambda r: r.get(col) or "", reverse=direction.lower() == "desc")
        if limit:
            rows = rows[:limit]
        return rows

    async def insert(self, table, data):
        self.tables.setdefault(table, []).append(dict(data))
        return dict(data)

    async def update(self, table, data, where=None):
        out = []
        for row in self.tables.get(table, []):
            if self._match(row, where):
                row.update(data)
                out.append(dict(row))
        return out

    async def count(self, table, where=None):
        return sum(1 for r in self.tables.get(table, []) if self._match(r, where))


class TestBillingScale(unittest.TestCase):
    """Phase I: unique amounts, gateway checkout, webhooks, grace, dashboard, dunning."""

    PROVIDER_ENV = {
        "NOWPAYMENTS_API_KEY": "np_test_key",
        "NOWPAYMENTS_IPN_SECRET": "np_test_secret",
    }

    def _db(self):
        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "alice@test.dev", "tier": "free"})
        return db

    def _invoice(self, db, tier="premium", method="manual"):
        import asyncio
        from backend.services import billing_service as billing
        inv = asyncio.run(billing.create_invoice(
            db, {"id": "u1", "email": "alice@test.dev"}, tier, method))
        self.assertNotIn("error", inv, inv)
        return inv

    # ---- unique amount / memo ----

    def test_unique_amount_and_memo_on_handpay(self):
        inv1 = self._invoice(self._db())
        db2 = self._db()
        inv2 = self._invoice(db2)
        self.assertTrue(inv1["memo"].startswith("ORQ-"))
        self.assertIsNotNone(inv1["unique_amount"])
        self.assertGreater(float(inv1["unique_amount"]), float(inv1["amount_usd"]))
        # collision check: two pending invoices never share an amount
        db = self._db()
        a = self._invoice(db)
        b = self._invoice(db)
        self.assertNotEqual(a["unique_amount"], b["unique_amount"])

    def test_unknown_and_unconfigured_methods(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        bad = asyncio.run(billing.create_invoice(
            db, {"id": "u1", "email": "a@b.c"}, "premium", "paypal"))
        self.assertEqual(bad, {"error": "invalid_method"})

        with mock.patch.dict("os.environ", {"STRIPE_SECRET_KEY": ""}, clear=False):
            out = asyncio.run(billing.create_invoice(
                db, {"id": "u1", "email": "a@b.c"}, "premium", "stripe"))
        self.assertEqual(out, {"error": "checkout_unavailable"})
        self.assertEqual(db.tables["invoices"][0]["status"], "cancelled")

    # ---- webhooks ----

    def test_webhook_unknown_provider(self):
        import asyncio
        from backend.services import billing_service as billing
        out = asyncio.run(billing.handle_gateway_webhook(self._db(), "paypal", {}, b"{}", {}))
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], 404)

    def test_webhook_bad_signature_rejected(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        inv = self._invoice(db)
        payload = {"payment_id": 1, "order_id": inv["id"], "payment_status": "finished"}
        with mock.patch.dict("os.environ", self.PROVIDER_ENV):
            out = asyncio.run(billing.handle_gateway_webhook(
                db, "nowpayments", {"x-nowpayments-sig": "deadbeef"},
                b"{}", payload))
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], 400)

    def _signed_nowpayments(self, payload):
        import hashlib
        import hmac
        import json
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        sig = hmac.new(self.PROVIDER_ENV["NOWPAYMENTS_IPN_SECRET"].encode(),
                       body, hashlib.sha512).hexdigest()
        return {"x-nowpayments-sig": sig}, body

    def test_webhook_happy_path_auto_approves(self):
        import asyncio
        from backend.db.models import SUBSCRIPTIONS, USERS, PAYMENT_EVENTS
        from backend.services import billing_service as billing
        db = self._db()
        inv = self._invoice(db, tier="vip")
        payload = {
            "payment_id": 99001,
            "order_id": inv["id"],
            "payment_status": "finished",
            "price_amount": float(inv["unique_amount"]),
            "price_currency": "usd",
        }
        headers, body = self._signed_nowpayments(payload)
        with mock.patch.dict("os.environ", self.PROVIDER_ENV):
            out = asyncio.run(billing.handle_gateway_webhook(
                db, "nowpayments", headers, body, payload))
        self.assertTrue(out["ok"], out)
        self.assertTrue(out.get("approved"))

        stored = db.tables["invoices"][0]
        self.assertEqual(stored["status"], "approved")
        self.assertEqual(stored["provider"], "nowpayments")
        self.assertIsNotNone(stored["paid_at"])
        self.assertEqual(db.tables[USERS][0]["tier"], "vip")
        self.assertEqual(db.tables[SUBSCRIPTIONS][0]["tier"], "vip")
        self.assertEqual(db.tables[SUBSCRIPTIONS][0]["status"], "active")
        self.assertEqual(len(db.tables[PAYMENT_EVENTS]), 1)

        # replayed delivery is a no-op (idempotent)
        with mock.patch.dict("os.environ", self.PROVIDER_ENV):
            again = asyncio.run(billing.handle_gateway_webhook(
                db, "nowpayments", headers, body, payload))
        self.assertTrue(again.get("duplicate"))
        self.assertEqual(db.tables[SUBSCRIPTIONS][0]["status"], "active")

    def test_webhook_not_paid_is_recorded_and_ignored(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        inv = self._invoice(db)
        payload = {"payment_id": 99002, "order_id": inv["id"], "payment_status": "waiting"}
        headers, body = self._signed_nowpayments(payload)
        with mock.patch.dict("os.environ", self.PROVIDER_ENV):
            out = asyncio.run(billing.handle_gateway_webhook(
                db, "nowpayments", headers, body, payload))
        self.assertTrue(out["ok"])
        self.assertNotIn("approved", out)
        self.assertEqual(db.tables["invoices"][0]["status"], "pending")
        self.assertEqual(db.tables["payment_events"][0]["status"], "ignored")

    def test_webhook_orphan_event_has_no_invoice(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        payload = {"payment_id": 99003, "order_id": "nope", "payment_status": "finished"}
        headers, body = self._signed_nowpayments(payload)
        with mock.patch.dict("os.environ", self.PROVIDER_ENV):
            out = asyncio.run(billing.handle_gateway_webhook(
                db, "nowpayments", headers, body, payload))
        self.assertTrue(out["ok"])
        self.assertEqual(out.get("detail"), "no matching invoice")

    # ---- grace / cancel-at-period-end ----

    def _sub(self, db, *, expires_in_days, auto_renew=True, cancel=False, grace=None):
        from backend.db.models import SUBSCRIPTIONS
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        db.tables[SUBSCRIPTIONS].append({
            "id": "s1", "user_id": "u1", "tier": "premium", "status": "active",
            "auto_renew": auto_renew, "cancel_at_period_end": cancel,
            "grace_until": grace, "provider": "manual",
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(days=expires_in_days)).isoformat(),
            "last_invoice_id": None, "reminder_sent_count": 0,
        })
        db.tables["users"][0]["tier"] = "premium"

    def test_grace_window_keeps_tier(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        self._sub(db, expires_in_days=-1, auto_renew=True)
        sub = asyncio.run(billing.get_subscription(db, "u1"))
        self.assertEqual(sub["status"], "grace")
        self.assertEqual(db.tables["users"][0]["tier"], "premium")
        self.assertIsNotNone(db.tables["subscriptions"][0]["grace_until"])

    def test_grace_expired_downgrades(self):
        import asyncio
        from backend.services import billing_service as billing
        from datetime import timedelta, timezone
        db = self._db()
        self._sub(db, expires_in_days=-5, auto_renew=True,
                  grace=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        sub = asyncio.run(billing.get_subscription(db, "u1"))
        self.assertEqual(sub["status"], "expired")
        self.assertEqual(db.tables["users"][0]["tier"], "free")

    def test_cancelled_sub_expires_immediately_after_period(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        self._sub(db, expires_in_days=-1, auto_renew=False, cancel=True)
        sub = asyncio.run(billing.get_subscription(db, "u1"))
        self.assertEqual(sub["status"], "expired")
        self.assertEqual(db.tables["users"][0]["tier"], "free")

    def test_set_auto_renew_sets_cancel_at_period_end(self):
        import asyncio
        from backend.services import billing_service as billing
        db = self._db()
        self._sub(db, expires_in_days=10, auto_renew=True)
        self.assertTrue(asyncio.run(billing.set_auto_renew(db, "u1", False)))
        self.assertTrue(db.tables["subscriptions"][0]["cancel_at_period_end"])
        self.assertFalse(db.tables["subscriptions"][0]["auto_renew"])
        self.assertTrue(asyncio.run(billing.set_auto_renew(db, "u1", True)))
        self.assertFalse(db.tables["subscriptions"][0]["cancel_at_period_end"])

    # ---- revenue dashboard ----

    def test_revenue_dashboard_keys_and_mrr(self):
        import asyncio
        from backend.db.models import SUBSCRIPTIONS
        from backend.services import billing_service as billing
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        db = self._db()
        self._sub(db, expires_in_days=7)
        db.tables["subscriptions"].append({
            "id": "s2", "user_id": "u2", "tier": "vip", "status": "active",
            "auto_renew": True, "cancel_at_period_end": False, "grace_until": None,
            "started_at": now.isoformat(), "expires_at": (now + timedelta(days=20)).isoformat(),
        })
        db.tables["invoices"].append({
            "id": "i1", "user_id": "u1", "tier": "premium", "status": "approved",
            "amount_usd": 49.0, "provider": "manual", "user_id": "u1",
            "created_at": now.isoformat(),
        })
        db.tables["invoices"].append({
            "id": "i2", "user_id": "u2", "tier": "vip", "status": "approved",
            "amount_usd": 199.0, "provider": "stripe", "user_id": "u2",
            "created_at": now.isoformat(),
        })
        db.tables["invoices"].append({
            "id": "i3", "user_id": "u3", "tier": "premium", "status": "pending",
            "amount_usd": 49.0, "provider": "manual", "created_at": now.isoformat(),
        })
        out = asyncio.run(billing.revenue_dashboard(db))
        self.assertEqual(out["mrr_usd"], 49.0 + 199.0)
        self.assertEqual(out["arr_usd"], (49.0 + 199.0) * 12)
        self.assertEqual(out["pending_invoices"], 1)
        self.assertEqual(out["active_subscriptions"], 2)
        self.assertEqual(out["expiring_7d"], 1)
        self.assertEqual(out["paying_users"], 2)
        self.assertEqual(out["revenue_by_provider"]["stripe"]["revenue_usd"], 199.0)
        self.assertEqual(len(out["revenue_by_month"]), 6)
        self.assertIn("gateway_providers", out)

    # ---- dunning / scheduler sweep ----

    def test_billing_jobs_reminder_and_stale_sweep(self):
        import asyncio
        from backend.services import billing_service as billing
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        db = self._db()

        # stale pending invoice -> expired
        db.tables["invoices"].append({
            "id": "old", "user_id": "u1", "tier": "premium", "status": "pending",
            "amount_usd": 49.0, "provider": "manual",
            "created_at": (now - timedelta(days=3)).isoformat(),
            "expires_at": (now - timedelta(days=1)).isoformat(),
        })
        # expires in ~7 days -> lands in the 7-day reminder bucket
        # (ceil-based buckets are boundary-safe either way); window is
        # >3 days so no renewal invoice yet
        self._sub(db, expires_in_days=7, auto_renew=True)

        warned = []

        async def _fake_warn(db_, user_id, tier, days_left, reason):
            warned.append((user_id, days_left))

        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out = asyncio.run(billing.billing_jobs(db))

        self.assertEqual(db.tables["invoices"][0]["status"], "expired")
        self.assertEqual(out["reminders_sent"], 1, (out, warned))
        self.assertEqual(warned, [("u1", 7)])
        self.assertEqual(db.tables["subscriptions"][0]["reminder_sent_count"], 1)
        self.assertEqual(out["renewal_invoices"], 0)

        # second sweep: the same reminder is not repeated
        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out2 = asyncio.run(billing.billing_jobs(db))
        self.assertEqual(out2["reminders_sent"], 0)

    def test_billing_jobs_renewal_invoice_for_autorenew(self):
        import asyncio
        from backend.services import billing_service as billing
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        db = self._db()
        # expiring within 3 days, auto-renew on -> one pending renewal invoice
        self._sub(db, expires_in_days=3, auto_renew=True)

        async def _fake_warn(db_, user_id, tier, days_left, reason):
            pass

        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out = asyncio.run(billing.billing_jobs(db))
        self.assertEqual(out["renewal_invoices"], 1)
        renewals = [i for i in db.tables["invoices"] if i["id"] != "old"]
        self.assertEqual(len(renewals), 1)
        self.assertEqual(renewals[0]["status"], "pending")

        # a second sweep must not open another one
        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out2 = asyncio.run(billing.billing_jobs(db))
        self.assertEqual(out2["renewal_invoices"], 0)

        # cancelling at period end suppresses renewals entirely
        db2 = self._db()
        self._sub(db2, expires_in_days=3, auto_renew=False, cancel=True)
        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out3 = asyncio.run(billing.billing_jobs(db2))
        self.assertEqual(out3["renewal_invoices"], 0)
        self.assertEqual(db2.tables["invoices"], [])

    def test_billing_jobs_grace_set_and_lapsed(self):
        import asyncio
        from backend.services import billing_service as billing
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        db = self._db()

        async def _fake_warn(*a, **k):
            pass

        # already-expired auto-renew sub: grace opened, not downgraded
        self._sub(db, expires_in_days=-1, auto_renew=True)
        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out = asyncio.run(billing.billing_jobs(db))
        self.assertEqual(out["grace_expired"], 0)
        self.assertIsNotNone(db.tables["subscriptions"][0]["grace_until"])
        self.assertEqual(db.tables["users"][0]["tier"], "premium")

        # lapsed grace -> expired + downgrade
        db.tables["subscriptions"][0]["grace_until"] = (
            now - timedelta(days=1)).isoformat()
        with mock.patch.object(billing, "_warn_subscriber", _fake_warn):
            out = asyncio.run(billing.billing_jobs(db))
        self.assertEqual(out["grace_expired"], 1)
        self.assertEqual(db.tables["subscriptions"][0]["status"], "expired")
        self.assertEqual(db.tables["users"][0]["tier"], "free")


class TestGatewaySignatures(unittest.TestCase):
    """Phase I: per-provider webhook signature verification."""

    def test_configured_gateways_reflect_env(self):
        from backend.payments.registry import configured_gateways
        empty = {"STRIPE_SECRET_KEY": "", "PAYSTACK_SECRET_KEY": "",
                 "FLUTTERWAVE_SECRET_KEY": "", "NOWPAYMENTS_API_KEY": ""}
        with mock.patch.dict("os.environ", empty, clear=False):
            self.assertEqual(configured_gateways(), [])
        with mock.patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_live_x"}, clear=False):
            names = [g["provider"] for g in configured_gateways()]
            self.assertIn("paystack", names)

    def test_stripe_signature_roundtrip(self):
        import hashlib
        import hmac
        import json
        import time
        from backend.payments.registry import get_provider
        body = json.dumps({
            "id": "evt_1", "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_1", "metadata": {"invoice_id": "inv1"},
                                "payment_status": "paid", "amount_total": 4900,
                                "currency": "usd"}},
        }).encode()
        ts = str(int(time.time()))
        sig = hmac.new(b"whsec_test", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        with mock.patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test",
                                            "STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            p = get_provider("stripe")
            out = p.verify_webhook({"stripe-signature": f"t={ts},v1={sig}"}, body, json.loads(body))
            self.assertTrue(out["ok"], out)
            ev = out["event"]
            self.assertTrue(ev.paid)
            self.assertEqual(ev.invoice_id, "inv1")
            self.assertEqual(ev.amount_usd, 49.0)
            bad = p.verify_webhook({"stripe-signature": f"t={ts},v1={'0' * 64}"},
                                   body, json.loads(body))
            self.assertFalse(bad["ok"])
            missing = p.verify_webhook({}, body, json.loads(body))
            self.assertFalse(missing["ok"])

    def test_paystack_and_flutterwave_signatures(self):
        import hashlib
        import hmac
        import json
        from backend.payments.registry import get_provider

        body = json.dumps({
            "event": "charge.success",
            "data": {"id": 5, "status": "success", "reference": "inv1",
                     "amount": 4900, "currency": "USD"},
        }).encode()
        sig = hmac.new(b"sk_live_x", body, hashlib.sha512).hexdigest()
        with mock.patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_live_x"}):
            out = get_provider("paystack").verify_webhook(
                {"x-paystack-signature": sig}, body, json.loads(body))
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["event"].paid)
        self.assertEqual(out["event"].amount_usd, 49.0)

        with mock.patch.dict("os.environ", {"FLUTTERWAVE_SECRET_KEY": "flw_x",
                                            "FLUTTERWAVE_WEBHOOK_HASH": "hash_x"}):
            good = get_provider("flutterwave").verify_webhook(
                {"verif-hash": "hash_x"}, b"{}",
                {"event": "charge.completed",
                 "data": {"id": 7, "tx_ref": "inv1", "status": "successful",
                          "amount": 199.0, "currency": "USD"}})
        self.assertTrue(good["ok"], good)
        self.assertTrue(good["event"].paid)

        with mock.patch.dict("os.environ", {"FLUTTERWAVE_SECRET_KEY": "flw_x",
                                            "FLUTTERWAVE_WEBHOOK_HASH": "hash_x"}):
            bad = get_provider("flutterwave").verify_webhook(
                {"verif-hash": "nope"}, b"{}", {"event": "charge.completed", "data": {}})
        self.assertFalse(bad["ok"])


class TestGatewayRedirectSplit(unittest.TestCase):
    """Gateway checkouts split webhook (backend) vs redirect (frontend) origins."""

    ENV = {
        "NOWPAYMENTS_API_KEY": "np_key",
        "NOWPAYMENTS_IPN_SECRET": "np_secret",
        "STRIPE_SECRET_KEY": "sk_test",
        "PAYSTACK_CURRENCY": "USD",
    }

    def test_frontend_base_fallback(self):
        from backend.config import frontend_base, settings
        orig_f, orig_a = settings.FRONTEND_BASE_URL, settings.APP_BASE_URL
        try:
            settings.APP_BASE_URL = "https://api.orqeva.test"
            settings.FRONTEND_BASE_URL = ""
            self.assertEqual(frontend_base(), "https://api.orqeva.test")
            settings.FRONTEND_BASE_URL = "https://app.orqeva.test/"
            self.assertEqual(frontend_base(), "https://app.orqeva.test")
        finally:
            settings.FRONTEND_BASE_URL, settings.APP_BASE_URL = orig_f, orig_a

    def test_nowpayments_ipn_is_backend_redirect_is_frontend(self):
        from backend.payments.nowpayments import NowPaymentsProvider
        import json as _json
        captured = {}

        def fake_post(url, *, headers, json_body, timeout=20.0):
            captured["body"] = json_body
            return {"id": "123", "invoice_url": "https://nowpayments.io/pay/123"}

        with mock.patch.dict("os.environ", self.ENV):
            with mock.patch.object(NowPaymentsProvider, "_post_json", staticmethod(fake_post)):
                out = NowPaymentsProvider()._create_checkout(
                    {"id": "inv1", "amount_usd": 49.0, "tier": "premium"},
                    "https://api.orqeva.test", "https://app.orqeva.test")
        self.assertTrue(out["ok"], out)
        b = captured["body"]
        self.assertEqual(b["ipn_callback_url"], "https://api.orqeva.test/api/billing/webhooks/nowpayments")
        self.assertEqual(b["success_url"], "https://app.orqeva.test/billing?status=paid")
        self.assertEqual(b["cancel_url"], "https://app.orqeva.test/billing")

    def test_stripe_paystack_flutterwave_redirect_to_frontend(self):
        from backend.payments.paystack import PaystackProvider
        from backend.payments.flutterwave import FlutterwaveProvider
        inv = {"id": "inv1", "amount_usd": 49.0, "tier": "premium"}

        with mock.patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test"}):
            from backend.payments.stripe import StripeProvider
            captured = {}
            def fake_post_form(url, form):
                captured["form"] = dict(form)
                return {"url": "https://stripe.com/checkout/xyz", "id": "cs_1"}
            with mock.patch.object(StripeProvider, "_post_form", staticmethod(fake_post_form)):
                StripeProvider()._create_checkout(inv, "https://api.orqeva.test", "https://app.orqeva.test")
            self.assertEqual(captured["form"]["success_url"], "https://app.orqeva.test/billing?status=paid")
            self.assertEqual(captured["form"]["cancel_url"], "https://app.orqeva.test/billing")

        with mock.patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_live_x"}):
            captured = {}
            def fake_post(url, *, headers, json_body, timeout=20.0):
                captured["body"] = json_body
                return {"data": {"authorization_url": "https://paystack.com/pay/xyz"}}
            with mock.patch.object(PaystackProvider, "_post_json", staticmethod(fake_post)):
                PaystackProvider()._create_checkout(inv, "https://api.orqeva.test", "https://app.orqeva.test")
            self.assertEqual(captured["body"]["callback_url"], "https://app.orqeva.test/billing?status=paid")

        with mock.patch.dict("os.environ", {"FLUTTERWAVE_SECRET_KEY": "flw_x"}):
            captured = {}
            def fake_post(url, *, headers, json_body, timeout=20.0):
                captured["body"] = json_body
                return {"data": {"link": "https://flutterwave.com/pay/xyz"}}
            with mock.patch.object(FlutterwaveProvider, "_post_json", staticmethod(fake_post)):
                FlutterwaveProvider()._create_checkout(inv, "https://api.orqeva.test", "https://app.orqeva.test")
            self.assertEqual(captured["body"]["redirect_url"], "https://app.orqeva.test/billing?status=paid")


class _FakeSignalsDB:
    """Captures the where clause so the Phase J gating can be asserted."""

    def __init__(self, rows=None):
        self.rows = [dict(r) for r in (rows or [])]
        self.last_where = None
        self.last_limit = None
        self.calls = 0

    async def fetch_all(self, table, where=None, order=None, limit=None, columns="*"):
        self.calls += 1
        self.last_where = where
        self.last_limit = limit
        return [dict(r) for r in self.rows]


def _ago_iso(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class TestSignalLatency(unittest.TestCase):
    """Phase J: the advertised ladder - free 5 min / premium 1 min / vip real-time."""

    def test_release_delay_ladder(self):
        from backend.services.signal_service import release_delay
        self.assertEqual(release_delay("free"), 300)
        self.assertEqual(release_delay("premium"), 60)
        self.assertEqual(release_delay("vip"), 0)
        self.assertEqual(release_delay("FREE"), 300)
        self.assertEqual(release_delay(None), 300)
        self.assertEqual(release_delay("banana"), 300)

    def test_is_released_windows(self):
        from backend.services.signal_service import is_released
        fresh = {"created_at": _ago_iso(0)}
        four_min = {"created_at": _ago_iso(240)}
        six_min = {"created_at": _ago_iso(360)}
        self.assertFalse(is_released(fresh, "free"))
        self.assertFalse(is_released(fresh, "premium"))
        self.assertTrue(is_released(fresh, "vip"))
        self.assertFalse(is_released(four_min, "free"))
        self.assertTrue(is_released(four_min, "premium"))
        self.assertTrue(is_released(four_min, "vip"))
        self.assertTrue(is_released(six_min, "free"))
        self.assertTrue(is_released({}, "free"))

    def test_list_signals_hides_signals_inside_the_window(self):
        import asyncio
        from backend.services.signal_service import list_signals

        db = _FakeSignalsDB()
        asyncio.run(list_signals(db, tier="free", limit=10))
        where = db.last_where
        self.assertIn("created_at", where)
        self.assertEqual(where["created_at"]["op"], "lte")
        self.assertEqual(where["tier_required"], ["free"])

        db2 = _FakeSignalsDB()
        asyncio.run(list_signals(db2, tier="vip", limit=10))
        self.assertEqual(db2.last_where["tier_required"], ["free", "premium", "vip"])
        self.assertIn("created_at", db2.last_where)

    def test_unknown_tier_still_denied(self):
        import asyncio
        from backend.services.signal_service import list_signals

        db = _FakeSignalsDB()
        self.assertEqual(asyncio.run(list_signals(db, tier="hacked")), [])
        self.assertEqual(db.calls, 0)


class TestConfidenceSplit(unittest.TestCase):
    """Phase J: free keeps the everyday subset, paying users get the best calls."""

    def test_strong_free_signal_promoted_to_premium(self):
        from backend.services.signal_service import split_free_signals
        signals = [
            {"tier": "free", "confidence": 0.92},
            {"tier": "free", "confidence": 0.75},
            {"tier": "free", "confidence": 0.74},
            {"tier": "free", "confidence": 0.2},
            {"tier": "premium", "confidence": 0.99},
            {"tier": "vip", "confidence": 0.99},
            {"tier": "free"},
        ]
        promoted = split_free_signals(signals)
        self.assertEqual(promoted, 2)
        self.assertEqual(signals[0]["tier"], "premium")
        self.assertEqual(signals[1]["tier"], "premium")
        self.assertEqual(signals[2]["tier"], "free")
        self.assertEqual(signals[3]["tier"], "free")
        self.assertEqual(signals[4]["tier"], "premium")
        self.assertEqual(signals[5]["tier"], "vip")
        self.assertEqual(signals[6]["tier"], "free")

    def test_custom_ceiling(self):
        from backend.services.signal_service import split_free_signals
        signals = [{"tier": "free", "confidence": 0.6}]
        self.assertEqual(split_free_signals(signals, ceiling=0.5), 1)
        self.assertEqual(signals[0]["tier"], "premium")


class TestLockedTeasers(unittest.TestCase):
    """Phase J: locked upgrades show symbol/market but no tradeable levels."""

    def test_teaser_strips_levels(self):
        from backend.services.signal_service import _teaser
        sig = {
            "id": "s1", "symbol": "EURUSD", "market": "forex", "direction": "buy",
            "confidence": 0.9, "entry_price": 1.1, "stop_loss": 1.05,
            "take_profit": 1.2, "indicators": {"rsi": 71}, "tier_required": "premium",
        }
        out = _teaser(sig)
        self.assertTrue(out["locked"])
        self.assertIsNone(out["entry_price"])
        self.assertIsNone(out["stop_loss"])
        self.assertIsNone(out["take_profit"])
        self.assertIsNone(out["indicators"])
        self.assertEqual(out["symbol"], "EURUSD")
        self.assertEqual(out["market"], "forex")
        self.assertEqual(out["confidence"], 0.9)
        self.assertEqual(sig["entry_price"], 1.1)

    def test_tiers_requested(self):
        import asyncio
        from backend.services.signal_service import locked_teasers

        free_db = _FakeSignalsDB()
        asyncio.run(locked_teasers(free_db, tier="free"))
        self.assertEqual(free_db.last_where["tier_required"], ["premium", "vip"])

        pre_db = _FakeSignalsDB()
        asyncio.run(locked_teasers(pre_db, tier="premium"))
        self.assertEqual(pre_db.last_where["tier_required"], ["vip"])

        vip_db = _FakeSignalsDB()
        self.assertEqual(asyncio.run(locked_teasers(vip_db, tier="vip")), [])
        self.assertEqual(vip_db.calls, 0)

        odd_db = _FakeSignalsDB()
        self.assertEqual(asyncio.run(locked_teasers(odd_db, tier="nope")), [])
        self.assertEqual(odd_db.calls, 0)

    def test_teasers_respect_the_latency_window(self):
        import asyncio
        from backend.services.signal_service import locked_teasers
        db = _FakeSignalsDB()
        asyncio.run(locked_teasers(db, tier="free"))
        self.assertIn("created_at", db.last_where)
        self.assertEqual(db.last_where["created_at"]["op"], "lte")

    def test_serialize_marks_locked(self):
        from backend.api.signals import _serialize
        sig = {
            "id": "s1", "symbol": "BTCUSD", "market": "crypto", "direction": "buy",
            "confidence": 0.9, "entry_price": None, "stop_loss": None,
            "take_profit": None, "strategy": "Crypto Momentum", "status": "active",
            "tier_required": "vip", "indicators": None, "locked": True,
            "created_at": _ago_iso(60),
        }
        self.assertTrue(_serialize(sig)["locked"])

        unlocked = dict(sig, locked=False, tier_required="free")
        self.assertFalse(_serialize(unlocked)["locked"])


class TestAutoTradeTierGates(unittest.TestCase):
    """Phase J: live routing + promoted signals stay behind a paid plan."""

    def test_live_route_requires_paid_plan(self):
        from backend.services.auto_trade_service import _LIVE_MIN_TIER_RANK, _TIER_RANK
        self.assertGreaterEqual(_LIVE_MIN_TIER_RANK, 1)
        self.assertLess(_TIER_RANK["free"], _LIVE_MIN_TIER_RANK)
        self.assertGreaterEqual(_TIER_RANK["premium"], _LIVE_MIN_TIER_RANK)
        self.assertGreaterEqual(_TIER_RANK["vip"], _LIVE_MIN_TIER_RANK)

    def test_market_tier_ladder_unchanged(self):
        from backend.services.auto_trade_service import _tier_allows
        self.assertTrue(_tier_allows("free", "forex"))
        self.assertFalse(_tier_allows("free", "stock"))
        self.assertFalse(_tier_allows("premium", "crypto"))
        self.assertTrue(_tier_allows("vip", "crypto"))
        self.assertFalse(_tier_allows("free", "unknown-market"))


class TestTelegramLatencyQueue(unittest.TestCase):
    """Phase J: channel/user alerts hold signals until the target's window elapses."""

    def _queue(self, tg, signal):
        import asyncio
        asyncio.run(tg.queue_channel_signals({"free": [signal]}))

    def test_fresh_signal_only_reaches_the_vip_channel(self):
        import asyncio
        from unittest import mock
        from backend.services import telegram_service as tg

        posted = []

        async def fake_post(chan_tier, text):
            posted.append(chan_tier)
            return True, "ok"

        fresh = {"id": "s1", "symbol": "EURUSD", "market": "forex",
                 "direction": "buy", "confidence": 0.8, "entry_price": 1.1,
                 "stop_loss": 1.0, "take_profit": 1.2, "tier_required": "free",
                 "created_at": _ago_iso(0)}
        tg._PENDING_CHANNELS.clear()
        with mock.patch.object(tg, "_channel_id", lambda t: "chan123"), \
                mock.patch.object(tg, "_post_to_channel", fake_post):
            self._queue(tg, fresh)
            asyncio.run(tg.flush_channel_signals())
        self.assertEqual(posted, ["vip"])
        self.assertIn("free", tg._PENDING_CHANNELS)
        self.assertIn("premium", tg._PENDING_CHANNELS)

        # Once aged past every window it leaves the queue and fans out.
        posted.clear()
        aged = dict(fresh, created_at=_ago_iso(600))
        tg._PENDING_CHANNELS.clear()
        with mock.patch.object(tg, "_channel_id", lambda t: "chan123"), \
                mock.patch.object(tg, "_post_to_channel", fake_post):
            self._queue(tg, aged)
            asyncio.run(tg.flush_channel_signals())
        self.assertEqual(posted, ["free", "premium", "vip"])
        self.assertFalse(tg._PENDING_CHANNELS)

    def test_unconfigured_channel_drains_silently(self):
        import asyncio
        from unittest import mock
        from backend.services import telegram_service as tg

        aged = {"id": "s2", "symbol": "EURUSD", "market": "forex", "tier_required": "free",
                "created_at": _ago_iso(600)}
        tg._PENDING_CHANNELS.clear()
        with mock.patch.object(tg, "_channel_id", lambda t: None):
            self._queue(tg, aged)
            asyncio.run(tg.flush_channel_signals())
        self.assertFalse(tg._PENDING_CHANNELS)

    def test_per_user_alerts_deferred_until_released(self):
        from backend.services import telegram_service as tg

        fresh = {"id": "s3", "created_at": _ago_iso(0)}
        tg._PENDING_ALERTS.clear()
        self.assertEqual(tg._take_released_alerts("u1", "free"), [])
        self.assertEqual(tg._take_released_alerts("u1", "vip"), [])

        tg._PENDING_ALERTS["u1"] = [fresh]
        self.assertEqual(tg._take_released_alerts("u1", "vip"), [fresh])
        self.assertFalse(tg._PENDING_ALERTS)

        tg._PENDING_ALERTS["u1"] = [fresh]
        self.assertEqual(tg._take_released_alerts("u1", "free"), [])
        self.assertEqual(tg._PENDING_ALERTS["u1"], [fresh])
        tg._PENDING_ALERTS.clear()


class TestAnnualPlans(unittest.TestCase):
    """Phase K: yearly terms priced from the shared payment config."""

    def test_plans_advertise_annual_pricing(self):
        from backend.services import billing_service as billing
        by_tier = {p["tier"]: p for p in billing.plans()}
        prem = by_tier["premium"]
        self.assertEqual(prem["price_usd"], 49)
        self.assertEqual(prem["annual_price_usd"], 490)
        self.assertEqual(prem["annual_days"], 365)
        self.assertEqual(prem["annual_savings_usd"], 98.0)
        self.assertEqual(by_tier["vip"]["annual_price_usd"], 1990)
        self.assertEqual(by_tier["vip"]["annual_savings_usd"], 398.0)
        self.assertNotIn("free", by_tier)

    def test_annual_invoice_prices_and_term(self):
        import asyncio
        from backend.services import billing_service as billing
        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "a@b.c", "tier": "free"})
        user = {"id": "u1", "email": "a@b.c"}

        annual = asyncio.run(billing.create_invoice(db, user, "premium", "manual", annual=True))
        self.assertNotIn("error", annual, annual)
        self.assertEqual(float(annual["amount_usd"]), 490.0)
        self.assertEqual(annual["duration_days"], 365)

        monthly = asyncio.run(billing.create_invoice(db, user, "premium", "manual"))
        self.assertEqual(float(monthly["amount_usd"]), 49.0)
        self.assertIsNone(monthly["duration_days"])

    def test_annual_activation_extends_a_full_year(self):
        import asyncio
        from datetime import datetime, timezone
        from backend.services import billing_service as billing
        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "a@b.c", "tier": "free"})
        inv = asyncio.run(billing.create_invoice(
            db, {"id": "u1", "email": "a@b.c"}, "vip", "manual", annual=True))
        asyncio.run(billing._activate_subscription(db, inv))
        sub = db.tables["subscriptions"][0]
        self.assertEqual(sub["tier"], "vip")
        expires = datetime.fromisoformat(sub["expires_at"].replace("Z", "+00:00"))
        self.assertGreaterEqual((expires - datetime.now(timezone.utc)).days, 364)
        self.assertEqual(db.tables["users"][0]["tier"], "vip")


class TestAffiliateTracking(unittest.TestCase):
    """Phase K: broker/prop-firm links with click + last-touch conversion credit."""

    def test_safe_url_filters_dangerous_schemes(self):
        from backend.services.affiliate_service import _safe_url
        self.assertEqual(_safe_url("javascript:alert(1)"), "")
        self.assertEqual(_safe_url("data:text/html,x"), "")
        self.assertEqual(_safe_url(""), "")
        self.assertEqual(_safe_url(None), "")
        self.assertTrue(_safe_url("https://broker.example/ref?x=1").startswith("https://"))

    def test_create_partner_validates(self):
        import asyncio
        from backend.services import affiliate_service as aff
        db = _FakeBillingDB()
        self.assertEqual(
            asyncio.run(aff.create_partner(db, name="X", url="ftp://nope")), {"error": "invalid_partner"})
        self.assertEqual(
            asyncio.run(aff.create_partner(db, name="   ", url="https://ok.dev")), {"error": "invalid_partner"})
        partner = asyncio.run(aff.create_partner(
            db, name="BrokerCo", url="https://broker.example/ref", category="prop_firm"))
        self.assertEqual(partner["category"], "prop_firm")
        self.assertEqual(partner["click_count"], 0)
        self.assertEqual(partner["conversion_rate"], 0.0)
        # public listing hides the internal counters
        public = asyncio.run(aff.list_partners(db))
        self.assertEqual(len(public), 1)
        self.assertNotIn("click_count", public[0])

    def test_click_and_last_touch_conversion(self):
        import asyncio
        import time
        from backend.services import affiliate_service as aff
        db = _FakeBillingDB()
        p1 = asyncio.run(aff.create_partner(db, name="A", url="https://a.example"))
        p2 = asyncio.run(aff.create_partner(db, name="B", url="https://b.example"))

        asyncio.run(aff.record_click(db, p1["id"], "u1"))
        self.assertIsNone(asyncio.run(aff.record_click(db, "missing", "u1")))
        asyncio.run(aff.set_partner_active(db, p2["id"], False))
        self.assertIsNone(asyncio.run(aff.record_click(db, p2["id"], "u1")))

        asyncio.run(aff.set_partner_active(db, p2["id"], True))
        time.sleep(0.01)  # keep created_at ordering unambiguous
        asyncio.run(aff.record_click(db, p2["id"], "u1"))

        conv = asyncio.run(aff.record_conversion(
            db, user_id="u1", invoice={"id": "inv1", "amount_usd": 490.0}))
        self.assertEqual(conv["partner_id"], p2["id"])
        self.assertEqual(conv["amount_usd"], 490.0)

        row_b = [r for r in db.tables["affiliate_partners"] if r["id"] == p2["id"]][0]
        self.assertEqual(row_b["conversion_count"], 1)
        self.assertEqual(float(row_b["revenue_usd"]), 490.0)
        self.assertEqual(row_b["click_count"], 1)

        self.assertIsNone(asyncio.run(aff.record_conversion(
            db, user_id="nobody", invoice={"id": "x", "amount_usd": 10.0})))
        summary = asyncio.run(aff.summary(db))
        self.assertEqual(summary["conversions"], 1)
        self.assertEqual(summary["revenue_usd"], 490.0)


class TestApiKeys(unittest.TestCase):
    """Phase K: metered API keys - hashing, quotas, revocation."""

    def test_hash_and_quota_ladder(self):
        from backend.services import api_key_service as keys
        self.assertEqual(keys.KEY_PREFIX, "orq_")
        self.assertEqual(keys.hash_key("abc"), keys.hash_key("abc"))
        self.assertNotEqual(keys.hash_key("abc"), keys.hash_key("abd"))
        self.assertEqual(keys.daily_quota("free"), 200)
        self.assertGreater(keys.daily_quota("vip"), keys.daily_quota("free"))
        self.assertEqual(keys.daily_quota("unknown"), keys.FREE_DAILY_QUOTA)

    def test_used_today_resets_on_new_day(self):
        from backend.services import api_key_service as keys
        self.assertEqual(keys._used_today({"usage_day": keys._today(), "requests_today": 5}), 5)
        self.assertEqual(keys._used_today({"usage_day": "2000-01-01", "requests_today": 5}), 0)

    def test_create_key_stores_hash_not_raw(self):
        import asyncio
        from backend.services import api_key_service as keys
        db = _FakeBillingDB()
        created = asyncio.run(keys.create_key(db, "u1", "my bot"))
        self.assertTrue(created["key"].startswith(keys.KEY_PREFIX))
        row = db.tables["api_keys"][0]
        self.assertEqual(row["key_hash"], keys.hash_key(created["key"]))
        self.assertNotEqual(row["key_hash"], created["key"])
        self.assertNotIn("key_hash", created)
        self.assertEqual(created["prefix"], row["key_prefix"])

    def test_authenticate_and_meter(self):
        import asyncio
        from backend.services import api_key_service as keys
        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "a@b.c", "tier": "premium", "is_active": True})
        created = asyncio.run(keys.create_key(db, "u1"))

        self.assertIsNone(asyncio.run(keys.authenticate(db, None)))
        self.assertIsNone(asyncio.run(keys.authenticate(db, "bad-prefix")))
        self.assertIsNone(asyncio.run(keys.authenticate(db, keys.KEY_PREFIX + "unknown")))

        auth = asyncio.run(keys.authenticate(db, created["key"]))
        self.assertEqual(auth["user"]["id"], "u1")
        self.assertEqual(auth["quota"], keys.daily_quota("premium"))

        asyncio.run(keys.record_usage(db, auth["key"]))
        row = db.tables["api_keys"][0]
        self.assertEqual(row["requests_today"], 1)
        self.assertEqual(row["requests_total"], 1)

        self.assertTrue(asyncio.run(keys.revoke_key(db, "u1", row["id"])))
        self.assertIsNone(asyncio.run(keys.authenticate(db, created["key"])))

    def test_quota_exceeded(self):
        import asyncio
        from backend.services import api_key_service as keys
        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "a@b.c", "tier": "free", "is_active": True})
        created = asyncio.run(keys.create_key(db, "u1"))
        row = db.tables["api_keys"][0]
        row["usage_day"] = keys._today()
        row["requests_today"] = keys.daily_quota("free")

        out = asyncio.run(keys.authenticate(db, created["key"]))
        self.assertEqual(out["error"], "quota_exceeded")
        self.assertEqual(out["quota"], 200)

    def test_v1_endpoint_requires_key_and_meters(self):
        import asyncio
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.db.database import get_db
        from backend.services import api_key_service as keys

        db = _FakeBillingDB()
        db.tables["users"].append({"id": "u1", "email": "a@b.c", "tier": "free", "is_active": True})
        db.tables["signals"] = []
        created = asyncio.run(keys.create_key(db, "u1"))

        app.dependency_overrides[get_db] = lambda: db
        try:
            client = TestClient(app)
            self.assertEqual(client.get("/v1/signals").status_code, 401)
            self.assertEqual(
                client.get("/v1/signals", headers={"X-API-Key": "orq_nope"}).status_code, 401)
            ok = client.get("/v1/signals", headers={"X-API-Key": created["key"]})
            self.assertEqual(ok.status_code, 200)
            body = ok.json()
            self.assertEqual(body["tier"], "free")
            self.assertEqual(body["usage"]["used_today"], 1)
            self.assertEqual(db.tables["api_keys"][0]["requests_today"], 1)
        finally:
            app.dependency_overrides.clear()


class TestDeploymentHardening(unittest.TestCase):
    """Phase L: request ids, JSON 500s, enriched health, SMTP env aliases."""

    def _client(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        return app, TestClient(app, raise_server_exceptions=False)

    def test_request_id_header_generated_and_echoed(self):
        from backend.middleware import sentinel
        sentinel._blocked.clear()
        _, client = self._client()
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers.get("x-request-id"))
        r2 = client.get("/api/health", headers={"X-Request-ID": "abc123"})
        self.assertEqual(r2.headers.get("x-request-id"), "abc123")

    def test_health_reports_scanner_and_gateways(self):
        from backend.middleware import sentinel
        sentinel._blocked.clear()
        _, client = self._client()
        body = client.get("/api/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)
        self.assertGreaterEqual(body["uptime_s"], 0)
        self.assertIn("scanner", body)
        self.assertIsInstance(body["gateways"], list)

    def test_unhandled_error_is_json_with_request_id(self):
        from backend.middleware import sentinel
        sentinel._blocked.clear()
        app, client = self._client()

        async def boom():
            raise RuntimeError("kaboom")

        app.add_api_route("/api/_test_boom", boom, methods=["GET"])
        try:
            r = client.get("/api/_test_boom", headers={"X-Request-ID": "rid-500"})
            self.assertEqual(r.status_code, 500)
            body = r.json()
            self.assertEqual(body["error"], "internal")
            self.assertEqual(body["request_id"], "rid-500")
            self.assertEqual(r.headers.get("x-request-id"), "rid-500")
        finally:
            app.router.routes[:] = [
                rt for rt in app.router.routes
                if getattr(rt, "path", None) != "/api/_test_boom"
            ]

    def test_smtp_legacy_env_names_are_aliased(self):
        from backend.config import Settings
        env = {
            "SMTP_HOST": "", "SMTP_USER": "", "SMTP_PASSWORD": "", "SMTP_FROM": "",
            "SMTP_SERVER": "smtp.legacy.test",
            "SENDER_EMAIL": "bot@legacy.test",
            "SENDER_PASSWORD": "hunter2",
            "SENDER_FROM": "ORQEVA <bot@legacy.test>",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            s = Settings(_env_file=None)
        self.assertEqual(s.SMTP_HOST, "smtp.legacy.test")
        self.assertEqual(s.SMTP_USER, "bot@legacy.test")
        self.assertEqual(s.SMTP_PASSWORD, "hunter2")
        self.assertEqual(s.SMTP_FROM, "ORQEVA <bot@legacy.test>")

    def test_canonical_smtp_names_win_over_aliases(self):
        from backend.config import Settings
        env = {
            "SMTP_HOST": "smtp.canonical.test", "SMTP_USER": "new@canonical.test",
            "SMTP_PASSWORD": "pw-new", "SMTP_SERVER": "smtp.legacy.test",
            "SENDER_EMAIL": "old@legacy.test", "SENDER_PASSWORD": "pw-old",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            s = Settings(_env_file=None)
        self.assertEqual(s.SMTP_HOST, "smtp.canonical.test")
        self.assertEqual(s.SMTP_USER, "new@canonical.test")
        self.assertEqual(s.SMTP_PASSWORD, "pw-new")


if __name__ == "__main__":
    unittest.main(verbosity=2)
