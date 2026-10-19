"""Payment gateway adapters (Phase I).

Thin, env-configured adapters that share one contract so the billing service
treats every gateway the same: create a hosted checkout, verify a webhook,
optionally refund. See `registry.py` for lookup/selection.
"""
from backend.payments.base import GatewayEvent, PaymentProvider
from backend.payments.registry import (
    GATEWAY_METHODS,
    configured_gateways,
    get_provider,
    is_gateway,
)

__all__ = [
    "PaymentProvider",
    "GatewayEvent",
    "GATEWAY_METHODS",
    "configured_gateways",
    "get_provider",
    "is_gateway",
]
