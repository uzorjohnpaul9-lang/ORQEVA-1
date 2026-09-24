"""
Market Data Manager - Alpaca API Integration
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False
    logger.warning("alpaca-py not installed. Using simulated data.")


class MarketDataManager:
    """Manage market data feeds via Alpaca API."""

    def __init__(self):
        self.cache = {}
        self.data_feeds = {}
        self.connected = False
        self.trading_client = None
        self.data_client = None

        api_key = os.getenv("ALPACA_API_KEY", "")
        secret_key = os.getenv("ALPACA_SECRET_KEY", "")

        if api_key and secret_key and HAS_ALPACA:
            self.connect_alpaca(api_key, secret_key)

    def connect_alpaca(self, api_key: str, secret_key: str) -> bool:
        try:
            self.trading_client = TradingClient(api_key, secret_key, paper=True)
            self.data_client = StockHistoricalDataClient(api_key, secret_key)

            account = self.trading_client.get_account()
            self.connected = True
            logger.info(f"Connected to Alpaca | Account: {account.status} | Equity: ${float(account.equity):,.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.connected = False
            return False

    def get_stock_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        cache_key = f"{symbol}_{timeframe}_{start_date}_{end_date}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not self.connected or not self.data_client:
            return self._simulated_data(symbol, timeframe, start_date, end_date)

        try:
            tf_map = {
                "1m": TimeFrame(1, TimeFrameUnit.Minute),
                "5m": TimeFrame(5, TimeFrameUnit.Minute),
                "15m": TimeFrame(15, TimeFrameUnit.Minute),
                "1h": TimeFrame(1, TimeFrameUnit.Hour),
                "1d": TimeFrame(1, TimeFrameUnit.Day),
            }
            tf = tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Hour))

            if start_date is None:
                start_date = datetime.now() - timedelta(days=30)
            if end_date is None:
                end_date = datetime.now()

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start_date,
                end=end_date
            )

            bars = self.data_client.get_stock_bars(request)
            df = bars.df.reset_index()

            df = df.rename(columns={
                "timestamp": "timestamp",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "vwap": "vwap"
            })

            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)

            self.cache[cache_key] = df
            logger.info(f"Fetched {len(df)} bars for {symbol} ({timeframe})")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self._simulated_data(symbol, timeframe, start_date, end_date)

    def _simulated_data(self, symbol, timeframe, start_date, end_date) -> pd.DataFrame:
        dates = pd.date_range(
            start=start_date or datetime.now() - timedelta(days=30),
            end=end_date or datetime.now(),
            freq='1h'
        )
        base_price = 150 + hash(symbol) % 100
        prices = base_price + np.cumsum(np.random.randn(len(dates)) * 0.5)

        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices + np.random.uniform(-1, 1, len(dates)),
            'high': prices + np.random.uniform(0, 3, len(dates)),
            'low': prices - np.random.uniform(0, 3, len(dates)),
            'close': prices,
            'volume': np.random.randint(1000, 100000, len(dates))
        })
        return df

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        if not self.connected or not self.data_client:
            return self._simulated_quote(symbol)

        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = self.data_client.get_stock_latest_quote(request)
            q = quote[symbol]

            return {
                "symbol": symbol,
                "bid": float(q.bid_price),
                "ask": float(q.ask_price),
                "last": float((float(q.bid_price) + float(q.ask_price)) / 2),
                "bid_size": q.bid_size,
                "ask_size": q.ask_size,
                "timestamp": datetime.now()
            }
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return self._simulated_quote(symbol)

    def _simulated_quote(self, symbol: str) -> Dict[str, Any]:
        base = 150 + hash(symbol) % 100
        return {
            "symbol": symbol,
            "bid": base,
            "ask": base + 0.05,
            "last": base + 0.02,
            "bid_size": 100,
            "ask_size": 200,
            "timestamp": datetime.now()
        }

    def get_account_info(self) -> Dict[str, Any]:
        if not self.connected or not self.trading_client:
            return {"status": "not_connected", "equity": 100000}

        try:
            account = self.trading_client.get_account()
            return {
                "status": account.status,
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value)
            }
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return {"status": "error", "equity": 0}

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.connected or not self.trading_client:
            return []

        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "qty": float(p.qty),
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pl": float(p.unrealized_pl),
                    "market_value": float(p.market_value)
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_market_calendar(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        target_date = date or datetime.now()
        return {
            "date": target_date.date(),
            "is_open": target_date.weekday() < 5,
            "open_time": "09:30",
            "close_time": "16:00",
            "extended_hours": {
                "pre_market_start": "04:00",
                "after_hours_end": "20:00"
            }
        }

    def is_market_open(self) -> bool:
        calendar = self.get_market_calendar()
        now = datetime.now()
        return calendar["is_open"] and 9 <= now.hour < 16

    def clear_cache(self):
        self.cache.clear()
        logger.info("Data cache cleared")
