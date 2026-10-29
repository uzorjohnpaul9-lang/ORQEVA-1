-- Public track-record integrity.
-- Records *how* each signal was resolved so a future methodology change cannot
-- silently rewrite the meaning of historical rows. Additive and idempotent.

alter table public.signals add column if not exists resolution_basis text;
alter table public.signals add column if not exists resolution_version text;
-- strategy is present on newer deployments; keep this safe for older ones.
alter table public.signals add column if not exists strategy text;

comment on column public.signals.resolution_basis is
  'Bar interval used to resolve the signal, e.g. 1h or 1day (legacy = pre-provenance).';
comment on column public.signals.resolution_version is
  'Resolver rule version; bump when the resolution methodology changes.';

create index if not exists signals_status_resolved_idx
  on public.signals (status, resolved_at desc);

create index if not exists signals_status_source_idx
  on public.signals (status, data_source);

-- The public ledger only reads platform-wide (user_id is null) closed rows.
create index if not exists signals_public_track_record_idx
  on public.signals (status, data_source, resolved_at desc)
  where user_id is null;
