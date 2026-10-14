"""Public trading methodology library.

These are widely-taught, general market concepts (price action, market
structure, supply & demand, liquidity/smart-money, trend, mean reversion,
risk). They are general knowledge, not any individual's proprietary system,
so nothing here reproduces copyrighted course material.

The same library feeds two consumers:
  * the AI Instructor curriculum (`learn_service`)
  * the signal engines (`engines.strategy_library`)
"""
from __future__ import annotations

from typing import Any

METHODOLOGIES: list[dict[str, Any]] = [
    {
        "key": "trend_following",
        "name": "Trend Following — Higher-Timeframe Alignment",
        "category": "Trend",
        "timeframe": "swing / intraday",
        "summary": (
            "Trade in the direction of the dominant trend. Align a fast and slow "
            "average, only take longs when price is above both and making higher "
            "highs, only shorts below both and making lower lows. Trends persist "
            "more often than they reverse."
        ),
        "concepts": [
            "Higher highs & higher lows = uptrend; lower highs & lower lows = downtrend",
            "Moving-average stack (fast above slow = bullish)",
            "Trade with the trend, not against it",
        ],
        "entry_rules": [
            "Fast MA above slow MA (long) or below (short)",
            "Price on the correct side of both averages",
            "Momentum (e.g. MACD) agreeing with the direction",
        ],
        "exit_rules": [
            "Exit on a close back through the slow average",
            "Trail the stop behind the most recent swing",
        ],
        "risk_rules": [
            "Stop beyond the last swing low/high, not a fixed dollar amount",
            "Risk 0.5–1% of the account per trend trade",
        ],
        "attribution": "Core concept in every trend-following/CTA curriculum; public knowledge.",
    },
    {
        "key": "breakout_retest",
        "name": "Breakout & Retest",
        "category": "Breakout",
        "timeframe": "intraday / swing",
        "summary": (
            "Price breaks a well-defined range or level, then pulls back to retest "
            "it before continuing. Entering on the retest gives a tighter stop and "
            "filters out weak false breaks."
        ),
        "concepts": [
            "A level becomes support once broken to the upside (and resistance when broken down)",
            "Volume/momentum should expand on the break",
            "The retest is the second chance to enter with less risk",
        ],
        "entry_rules": [
            "Price closes beyond a multi-bar range high/low",
            "Pullback toward the broken level holds as new support/resistance",
        ],
        "exit_rules": [
            "Target the measured move (range height projected from the break)",
            "Invalidate if price closes back inside the range",
        ],
        "risk_rules": [
            "Stop just inside the range on the wrong side of the level",
            "Avoid chasing an extended break — wait for the retest",
        ],
        "attribution": "Classic technical-analysis concept (Edwards & Magee lineage); public knowledge.",
    },
    {
        "key": "market_structure",
        "name": "Market Structure — BOS & Change of Character",
        "category": "Price Action",
        "timeframe": "intraday / swing",
        "summary": (
            "Read the skeleton of the chart: sequences of swings. A Break of "
            "Structure (BOS) continues the trend; a Change of Character (CHoCH) "
            "is the first sign the trend may be turning."
        ),
        "concepts": [
            "Swing highs/lows define structure",
            "BOS = price breaking the last swing point in the trend direction",
            "CHoCH = the first opposite break after a run",
        ],
        "entry_rules": [
            "Trade continuation after a BOS in the trend direction",
            "Look for reversal setups only after a confirmed CHoCH",
        ],
        "exit_rules": [
            "Exit if structure breaks against the position",
            "Scale out at prior swing points",
        ],
        "risk_rules": [
            "Stop beyond the swing that invalidates the structure",
            "Never fade a trend without a CHoCH first",
        ],
        "attribution": "Popularised by many price-action/smart-money educators; the concept is public.",
    },
    {
        "key": "supply_demand",
        "name": "Supply & Demand Zones (Order Blocks)",
        "category": "Price Action",
        "timeframe": "intraday / swing",
        "summary": (
            "Institutions leave footprints: the base of candles before a strong "
            "impulse marks supply (sellers) or demand (buyers). Price often returns "
            "to these zones and reacts."
        ),
        "concepts": [
            "Strong impulse = imbalance; the origin base is the zone",
            "Demand zone = last down-candle before a big up-move (buy area)",
            "Supply zone = last up-candle before a big down-move (sell area)",
        ],
        "entry_rules": [
            "Wait for price to return into a fresh zone",
            "Enter on a reaction/confirmation candle, not blindly",
        ],
        "exit_rules": [
            "Target the next opposing zone",
            "Zone is consumed once price closes through it",
        ],
        "risk_rules": [
            "Stop just beyond the zone",
            "Skip zones that have already been tested several times",
        ],
        "attribution": "Supply/demand and order-block teaching; the underlying concept is public.",
    },
    {
        "key": "liquidity_sweep",
        "name": "Liquidity Sweeps (Stop Hunts)",
        "category": "Smart Money / Liquidity",
        "timeframe": "intraday",
        "summary": (
            "Price often spikes through an obvious high/low to trigger stops, then "
            "reverses. The sweep — a failed break — frequently marks the real turn "
            "as the market grabs the liquidity resting there."
        ),
        "concepts": [
            "Stops cluster just beyond equal highs/lows",
            "A wick through the level that closes back inside = sweep",
            "After the sweep, trade the reversal back into the range",
        ],
        "entry_rules": [
            "Price wicks beyond a swing high/low then closes back inside",
            "Confirmation: structure shift or candlestick rejection",
        ],
        "exit_rules": [
            "Target the opposite side of the range / next liquidity pool",
        ],
        "risk_rules": [
            "Stop beyond the sweep wick",
            "Don't enter before the candle closes back inside",
        ],
        "attribution": "Widely taught as 'smart money' / liquidity concepts; public knowledge.",
    },
    {
        "key": "fair_value_gap",
        "name": "Fair Value Gaps & Imbalances",
        "category": "Smart Money / Liquidity",
        "timeframe": "intraday",
        "summary": (
            "A three-candle move that leaves an untouched band between the candle "
            "before and the candle after the impulse. Price often returns to "
            "'rebalance' this gap before continuing."
        ),
        "concepts": [
            "FVG = gap between candle 1 high and candle 3 low (bullish) or 1 low and 3 high (bearish)",
            "Imbalance = one-sided aggressive move",
            "The gap can act as support/resistance on the retrace",
        ],
        "entry_rules": [
            "Identify a clean three-candle gap",
            "Enter on the retrace into the gap with trend",
        ],
        "exit_rules": ["Target the next swing / opposite liquidity"],
        "risk_rules": ["Stop beyond the origin of the impulse"],
        "attribution": "Commonly taught imbalance concept; public knowledge.",
    },
    {
        "key": "mean_reversion_range",
        "name": "Mean Reversion in a Range",
        "category": "Reversal",
        "timeframe": "intraday / swing",
        "summary": (
            "In a sideways market, price oscillates between support and resistance. "
            "Fade the edges back toward the middle — but only while the range holds."
        ),
        "concepts": [
            "Range = repeated tests of a high and low without a breakout",
            "RSI overbought/oversold near the edges",
            "Ranges break eventually — respect the boundary",
        ],
        "entry_rules": [
            "Price at range extreme with a reversal signal / stretched RSI",
            "Confirm with a rejection candle",
        ],
        "exit_rules": ["Target the mid or opposite edge of the range"],
        "risk_rules": ["Stop just outside the range boundary", "Cut fast if the range breaks"],
        "attribution": "Standard mean-reversion / range trading; public knowledge.",
    },
    {
        "key": "momentum_surge",
        "name": "Momentum Surge",
        "category": "Trend",
        "timeframe": "intraday",
        "summary": (
            "Trade the strongest movers: a sharp acceleration in rate-of-change with "
            "expanding range. Momentum begets momentum over short horizons."
        ),
        "concepts": [
            "Rate-of-change measured over 5/20 bars",
            "Expanding candle bodies = conviction",
            "Combine with trend so you're not buying a spike into resistance",
        ],
        "entry_rules": ["Multi-horizon momentum agrees", "Price above/below trend filter"],
        "exit_rules": ["Exit when momentum decelerates", "Take partials into strength"],
        "risk_rules": ["Tight stop under the breakout candle", "Avoid over-extended entries"],
        "attribution": "Momentum investing/trading; public knowledge.",
    },
    {
        "key": "support_resistance",
        "name": "Support & Resistance Reactions",
        "category": "Price Action",
        "timeframe": "any",
        "summary": (
            "Horizontal levels where price repeatedly reversed. The more touches and "
            "the more recent, the more meaningful. Trade the reaction, not the level alone."
        ),
        "concepts": [
            "Levels are zones, not exact prices",
            "Reaction (rejection wick, engulfing) confirms the level",
            "Levels flip role once broken",
        ],
        "entry_rules": ["Price at a level with a rejection/confirmation", "Trend supports the direction"],
        "exit_rules": ["Target the next level"],
        "risk_rules": ["Stop beyond the level zone"],
        "attribution": "Foundational technical analysis; public knowledge.",
    },
]

METHODOLOGY_BY_KEY = {m["key"]: m for m in METHODOLOGIES}


def render_library() -> str:
    """Compact text form of the library for LLM prompts."""
    lines: list[str] = []
    for m in METHODOLOGIES:
        lines.append(f"### {m['name']} [{m['category']}]")
        lines.append(m["summary"])
        lines.append("Concepts: " + "; ".join(m["concepts"]))
        lines.append("Entry: " + "; ".join(m["entry_rules"]))
        lines.append("Exit: " + "; ".join(m["exit_rules"]))
        lines.append("Risk: " + "; ".join(m["risk_rules"]))
        lines.append("")
    return "\n".join(lines)
