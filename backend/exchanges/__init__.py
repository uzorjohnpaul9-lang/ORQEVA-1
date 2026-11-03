"""Exchange adapter registry (Phase 14).

Each adapter is a module-level instance of BaseAdapter exposing:
  name            - canonical id stored in exchange_connections.exchange
  display_name    - UI label
  markets         - list of markets served
  needs_secret    - whether api_secret is required
  validate()      - credential check against the live endpoint
  account()       - balance/account snapshot
"""
from backend.exchanges.base import BaseAdapter
from backend.exchanges.alpaca_adapter import AlpacaAdapter
from backend.exchanges.binance_us_adapter import BinanceUSAdapter
from backend.exchanges.kraken_adapter import KrakenAdapter
from backend.exchanges.oanda_adapter import OandaAdapter
from backend.exchanges.coinbase_adapter import CoinbaseAdapter
from backend.exchanges.exness_adapter import ExnessAdapter
from backend.exchanges.bybit_adapter import BybitAdapter

_REGISTRY: dict[str, BaseAdapter] = {}


def register(adapter: BaseAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


for _cls in (AlpacaAdapter, BinanceUSAdapter, KrakenAdapter, OandaAdapter,
             CoinbaseAdapter, ExnessAdapter, BybitAdapter):
    register(_cls())


def get_adapter(name: str) -> BaseAdapter | None:
    return _REGISTRY.get(name)


def supported() -> list[BaseAdapter]:
    return list(_REGISTRY.values())
