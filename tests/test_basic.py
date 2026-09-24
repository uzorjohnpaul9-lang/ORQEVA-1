"""
AI Trading System - Basic Test Suite
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import unittest
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

    def test_crypto_engine_analyze(self):
        from engines.crypto_engine import CryptoEngine
        ce = CryptoEngine()
        self.assertEqual(ce.market_type, "crypto")
        self.assertIn("BTC/USD", ce.get_symbols())

    def test_crypto_discovery_init(self):
        from engines.crypto_discovery import CryptoDiscovery, CRYPTO_UNIVERSE, CoinMomentum
        dc = CryptoDiscovery()
        self.assertTrue(len(CRYPTO_UNIVERSE) >= 40)
        self.assertIsNotNone(dc._api_key)
        # CoinMomentum object
        cm = CoinMomentum(symbol="TEST/USD", price=1.0, rsi=50, score=0.5, direction="BUY")
        self.assertEqual(cm.symbol, "TEST/USD")
        self.assertEqual(cm.direction, "BUY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
