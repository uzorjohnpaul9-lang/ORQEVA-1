-- One-time backfill: seed per-pair Telegram alerts for users who have none.
--
-- Commit 9bcf87a made signal alerts opt-in per pair: matches_filters() treats
-- an empty watchlist as "subscribed to no pairs", so users who never picked a
-- pair stopped receiving Telegram signal DMs. This seeds their watchlist with
-- the symbols for their chosen default_market (the union for "all"), which
-- restores the previous behaviour without changing the opt-in model. Users can
-- remove pairs afterwards. Idempotent: only rows with an empty watchlist are
-- touched, so re-running is harmless.

update public.user_preferences
set watchlist = case coalesce(default_market, 'all')
    when 'stock' then array[
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
        'TSLA', 'META', 'JPM', 'V', 'UNH',
        'XOM', 'JNJ', 'WMT', 'PG', 'MA',
        'HD', 'CVX', 'MRK', 'ABBV', 'LLY'
    ]
    when 'forex' then array[
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF',
        'AUD/USD', 'USD/CAD', 'NZD/USD'
    ]
    when 'crypto' then array[
        'BTC/USD', 'ETH/USD', 'SOL/USD', 'BNB/USD',
        'XRP/USD', 'ADA/USD', 'DOGE/USD', 'AVAX/USD', 'TRX/USD',
        'SHIB/USD', 'PEPE/USD', 'BONK/USD', 'FLOKI/USD',
        'WIF/USD', 'TRUMP/USD', 'FARTCOIN/USD', 'PENGU/USD',
        'LINK/USD', 'NEAR/USD', 'SUI/USD', 'SEI/USD',
        'TIA/USD', 'INJ/USD', 'ARB/USD', 'OP/USD', 'APT/USD',
        'LTC/USD', 'DOT/USD', 'ATOM/USD', 'UNI/USD', 'AAVE/USD'
    ]
    when 'commodity' then array[
        'XAU/USD', 'XAG/USD', 'WTI/USD', 'BRENT/USD', 'NATGAS/USD'
    ]
    else array[
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
        'TSLA', 'META', 'JPM', 'V', 'UNH',
        'XOM', 'JNJ', 'WMT', 'PG', 'MA',
        'HD', 'CVX', 'MRK', 'ABBV', 'LLY',
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF',
        'AUD/USD', 'USD/CAD', 'NZD/USD',
        'BTC/USD', 'ETH/USD', 'SOL/USD', 'BNB/USD',
        'XRP/USD', 'ADA/USD', 'DOGE/USD', 'AVAX/USD', 'TRX/USD',
        'SHIB/USD', 'PEPE/USD', 'BONK/USD', 'FLOKI/USD',
        'WIF/USD', 'TRUMP/USD', 'FARTCOIN/USD', 'PENGU/USD',
        'LINK/USD', 'NEAR/USD', 'SUI/USD', 'SEI/USD',
        'TIA/USD', 'INJ/USD', 'ARB/USD', 'OP/USD', 'APT/USD',
        'LTC/USD', 'DOT/USD', 'ATOM/USD', 'UNI/USD', 'AAVE/USD',
        'XAU/USD', 'XAG/USD', 'WTI/USD', 'BRENT/USD', 'NATGAS/USD'
    ]
end
where watchlist is null or cardinality(watchlist) = 0;
