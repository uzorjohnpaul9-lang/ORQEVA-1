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
from backend.exchanges.kraken_adapter import KrakenAdapter
from backend.exchanges.oanda_adapter import OandaAdapter
from backend.exchanges.coinbase_adapter import CoinbaseAdapter

_REGISTRY: dict[str, BaseAdapter] = {}


def register(adapter: BaseAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


for _cls in (AlpacaAdapter, KrakenAdapter, OandaAdapter, CoinbaseAdapter):
    register(_cls())


def get_adapter(name: str) -> BaseAdapter | None:
    return _REGISTRY.get(name)


def supported() -> list[BaseAdapter]:
    return list(_REGISTRY.values())
