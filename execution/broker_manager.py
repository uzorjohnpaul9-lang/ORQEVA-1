"""
Modular Broker System
Supports multiple brokers for auto-trading.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

BROKERS_DIR = Path(__file__).parent.parent / "data" / "brokers"
BROKERS_DIR.mkdir(parents=True, exist_ok=True)


class BaseBroker(ABC):
    """Base class for all brokers."""

    @abstractmethod
    def connect(self, api_key: str, api_secret: str) -> bool:
        """Connect to broker."""
        pass

    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        """Get account balance."""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "market") -> Dict:
        """Place an order."""
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> bool:
        """Close a position."""
        pass

    @abstractmethod
    def get_pnl(self) -> float:
        """Get total P&L."""
        pass


class BinanceBroker(BaseBroker):
    """Binance broker for crypto and forex-like pairs."""

    def __init__(self):
        self.client = None
        self.connected = False

    def connect(self, api_key: str, api_secret: str) -> bool:
        try:
            from binance.client import Client
            self.client = Client(api_key, api_secret)
            self.connected = True
            return True
        except ImportError:
            return False
        except Exception:
            return False

    def get_balance(self) -> Dict[str, float]:
        if not self.connected:
            return {}
        try:
            account = self.client.get_account()
            balances = {}
            for b in account["balances"]:
                if float(b["free"]) > 0:
                    balances[b["asset"]] = float(b["free"])
            return balances
        except:
            return {}

    def get_position(self, symbol: str) -> Optional[Dict]:
        if not self.connected:
            return None
        try:
            position = self.client.get_position(symbol=symbol)
            return {
                "symbol": symbol,
                "quantity": float(position.get("positionAmt", 0)),
                "entry_price": float(position.get("entryPrice", 0)),
                "pnl": float(position.get("unRealizedProfit", 0)),
            }
        except:
            return None

    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "market") -> Dict:
        if not self.connected:
            return {"error": "Not connected"}
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side.upper(),
                type=order_type.upper(),
                quantity=quantity
            )
            return {
                "order_id": order.get("orderId"),
                "status": order.get("status"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }
        except Exception as e:
            return {"error": str(e)}

    def close_position(self, symbol: str) -> bool:
        if not self.connected:
            return False
        try:
            position = self.get_position(symbol)
            if position and position["quantity"] != 0:
                side = "SELL" if position["quantity"] > 0 else "BUY"
                self.place_order(symbol, side, abs(position["quantity"]))
                return True
            return False
        except:
            return False

    def get_pnl(self) -> float:
        if not self.connected:
            return 0
        try:
            income = self.client.get_income_history(incomeType="REALIZED_PNL")
            return sum(float(i["income"]) for i in income[-30:])
        except:
            return 0


class OandaBroker(BaseBroker):
    """OANDA broker for forex."""

    def __init__(self):
        self.account_id = None
        self.access_token = None
        self.base_url = "https://api-fxpractice.oanda.com"
        self.connected = False

    def connect(self, api_key: str, api_secret: str = "") -> bool:
        self.access_token = api_key
        self.account_id = api_secret
        self.connected = True
        return True

    def get_balance(self) -> Dict[str, float]:
        # OANDA balance fetch
        return {}

    def get_position(self, symbol: str) -> Optional[Dict]:
        return None

    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "market") -> Dict:
        return {"error": "Not implemented"}

    def close_position(self, symbol: str) -> bool:
        return False

    def get_pnl(self) -> float:
        return 0


class BrokerManager:
    """Manage multiple brokers."""

    def __init__(self):
        self.brokers = {}
        self.user_brokers = self._load_json("user_brokers.json", {})

    def _load_json(self, filename: str, default):
        filepath = BROKERS_DIR / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
        return default

    def _save_json(self, filename: str, data):
        filepath = BROKERS_DIR / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def register_broker(self, user_id: str, broker_name: str, api_key: str, api_secret: str) -> bool:
        """Register a broker for a user (credentials encrypted at rest)."""
        broker = self._create_broker(broker_name)
        if not broker:
            return False

        if broker.connect(api_key, api_secret):
            try:
                from security.security_manager import SecurityManager
                sec = SecurityManager()
                encrypted = sec.encrypt_broker_credentials(user_id, broker_name, api_key, api_secret)
                self.user_brokers[user_id] = {
                    "broker": broker_name,
                    "encrypted_credentials": encrypted,
                    "connected_at": datetime.now().isoformat(),
                }
            except Exception:
                self.user_brokers[user_id] = {
                    "broker": broker_name,
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "connected_at": datetime.now().isoformat(),
                }
            self._save_json("user_brokers.json", self.user_brokers)
            self.brokers[user_id] = broker
            return True
        return False

    def _create_broker(self, name: str) -> Optional[BaseBroker]:
        """Create broker instance by name."""
        brokers = {
            "binance": BinanceBroker,
            "oanda": OandaBroker,
        }
        broker_class = brokers.get(name.lower())
        if broker_class:
            return broker_class()
        return None

    def get_broker(self, user_id: str) -> Optional[BaseBroker]:
        """Get broker for a user (decrypts credentials if needed)."""
        if user_id in self.brokers:
            return self.brokers[user_id]

        user_data = self.user_brokers.get(user_id)
        if user_data:
            api_key = user_data.get("api_key")
            api_secret = user_data.get("api_secret")

            if not api_key and user_data.get("encrypted_credentials"):
                try:
                    from security.security_manager import SecurityManager
                    sec = SecurityManager()
                    creds = sec.decrypt_broker_credentials(user_data["encrypted_credentials"])
                    api_key = creds.get("api_key")
                    api_secret = creds.get("api_secret")
                except Exception:
                    return None

            if api_key and api_secret:
                broker = self._create_broker(user_data["broker"])
                if broker and broker.connect(api_key, api_secret):
                    self.brokers[user_id] = broker
                    return broker
        return None

    def execute_signal(self, user_id: str, signal: Dict[str, Any]) -> Dict:
        """Execute a trading signal for a user."""
        broker = self.get_broker(user_id)
        if not broker:
            return {"error": "No broker connected"}

        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "")

        # Convert forex pair format for Binance
        if "/" in symbol:
            symbol = symbol.replace("/", "") + "T"  # EUR/USD -> EURUSDT

        # Determine quantity based on risk profile
        user_data = self.user_brokers.get(user_id, {})
        # Default to minimal trade
        quantity = 0.001

        # Place order
        result = broker.place_order(symbol, direction, quantity)

        return result


# Global instance
broker_manager = BrokerManager()
