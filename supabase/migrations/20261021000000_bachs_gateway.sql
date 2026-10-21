-- Bachs becomes the only hosted-checkout gateway.
--
-- 1. Widen invoices.method.
--    The Phase I schema (20260925000000) declared
--      method text not null default 'crypto' check (method in ('crypto','manual'))
--    but the billing service writes 'gateway' for every hosted-checkout
--    invoice (nowpayments/stripe/paystack/flutterwave, now bachs). The
--    20261018000002_billing_scale migration added the provider /
--    checkout_url columns but never widened that constraint, so every
--    gateway invoice failed on insert with PostgREST 23514
--    ("invoices_method_check") and the API returned HTTP 500.
--    Only the hand-pay crypto/manual rails ever worked.
--
-- 2. Record the corridor the customer chose.
--    The billing page lets the customer pick a Bachs payment corridor
--    (card / bank transfer / mobile money / crypto) before checkout. The
--    choice is stored per invoice so the billing page and reconciliation
--    can show how an order was paid.

alter table public.invoices drop constraint if exists invoices_method_check;

alter table public.invoices add constraint invoices_method_check
  check (method in ('crypto','manual','gateway'));

alter table public.invoices add column if not exists payment_method text;

create index if not exists invoices_payment_method_idx
  on public.invoices (payment_method);
