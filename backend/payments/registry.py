"""Gateway lookup + selection."""
from backend.payments.base import PaymentProvider
from backend.payments.flutterwave import FlutterwaveProvider
from backend.payments.nowpayments import NowPaymentsProvider
from backend.payments.paystack import PaystackProvider
from backend.payments.stripe import StripeProvider

_PROVIDERS: dict[str, PaymentProvider] = {
    p.name: p for p in (
        NowPaymentsProvider(),
        StripeProvider(),
        PaystackProvider(),
        FlutterwaveProvider(),
    )
}

# Methods accepted on POST /api/billing/invoices besides the legacy pair.
GATEWAY_METHODS = tuple(_PROVIDERS.keys())

# Always-available non-gateway methods (hand-pay rails kept as fallback).
LEGACY_METHODS = ("crypto", "manual")


def get_provider(name: str) -> PaymentProvider | None:
    return _PROVIDERS.get(name)


def is_gateway(method: str) -> bool:
    return method in _PROVIDERS


def configured_gateways() -> list[dict]:
    return [
        {"provider": p.name, "display_name": p.display_name}
        for p in _PROVIDERS.values()
        if p.is_configured()
    ]
