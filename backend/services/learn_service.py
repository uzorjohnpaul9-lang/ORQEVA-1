"""ORQEVA Academy — curriculum + AI Instructor.

Content is built on `backend.services.methodology` (public market concepts).
The curriculum, glossary and quizzes are static; the Instructor layer calls the
configured LLM (`llm_service`) with the methodology library and the learner's
real ORQEVA data, and falls back to a scripted instructor when no LLM is set.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.services import llm_service
from backend.services.methodology import METHODOLOGIES, METHODOLOGY_BY_KEY, render_library

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Educational only — not financial advice. Trading involves substantial risk "
    "of loss. Practise on paper first."
)

GLOSSARY: list[dict[str, str]] = [
    {"term": "Ask", "category": "Basics", "definition": "The price at which you can buy; the lowest price a seller will accept right now."},
    {"term": "Bid", "category": "Basics", "definition": "The price at which you can sell; the highest price a buyer will pay right now."},
    {"term": "Spread", "category": "Basics", "definition": "The gap between the bid and the ask. It is a hidden cost on every trade."},
    {"term": "Long", "category": "Basics", "definition": "A position that profits when price rises (you buy, expecting to sell higher)."},
    {"term": "Short", "category": "Basics", "definition": "A position that profits when price falls (you sell, expecting to buy back lower)."},
    {"term": "Position size", "category": "Risk", "definition": "How much of a market you hold. Sizing controls how much a bad trade hurts you."},
    {"term": "Leverage", "category": "Basics", "definition": "Borrowed exposure that multiplies both gains and losses. High leverage is the fastest way to lose an account."},
    {"term": "Margin", "category": "Basics", "definition": "The collateral required to hold a leveraged position."},
    {"term": "Pip", "category": "Forex", "definition": "The smallest standard move in a currency pair (0.0001 for most pairs, 0.01 for JPY pairs)."},
    {"term": "Lot", "category": "Forex", "definition": "A standardised trade size. 1 standard lot = 100,000 units of the base currency."},
    {"term": "Entry", "category": "Execution", "definition": "The price at which you open a position."},
    {"term": "Stop-loss", "category": "Risk", "definition": "A pre-set price that closes the trade to cap the loss. Decide it before you enter."},
    {"term": "Take-profit", "category": "Risk", "definition": "A pre-set price that closes the trade to lock in gains."},
    {"term": "Risk/Reward (R)", "category": "Risk", "definition": "The ratio of potential profit to potential loss. 1:2 means you risk 1 to make 2."},
    {"term": "Drawdown", "category": "Risk", "definition": "The peak-to-trough fall in your account value. Keep it small to stay in the game."},
    {"term": "Volatility", "category": "Market", "definition": "How much price moves around. Higher volatility means bigger swings and wider stops."},
    {"term": "Liquidity", "category": "Market", "definition": "How easily you can trade without moving price. Thin markets slip more."},
    {"term": "Slippage", "category": "Execution", "definition": "The difference between the price you expected and the price you got."},
    {"term": "Market order", "category": "Execution", "definition": "An order that fills immediately at the best available price."},
    {"term": "Limit order", "category": "Execution", "definition": "An order that only fills at your price or better; it may not fill at all."},
    {"term": "Support", "category": "Technical", "definition": "A level where falling price has tended to stop and bounce."},
    {"term": "Resistance", "category": "Technical", "definition": "A level where rising price has tended to stall and reverse."},
    {"term": "Trend", "category": "Technical", "definition": "A sustained directional move: higher highs/lows (up) or lower highs/lows (down)."},
    {"term": "Range", "category": "Technical", "definition": "A sideways market bouncing between support and resistance without a breakout."},
    {"term": "Candlestick", "category": "Technical", "definition": "One bar showing open, high, low and close for a period. Its body shows the net move; its wicks show rejection."},
    {"term": "Break of Structure (BOS)", "category": "Price Action", "definition": "Price breaking the last swing point in the trend direction — a sign of continuation."},
    {"term": "Change of Character (CHoCH)", "category": "Price Action", "definition": "The first opposite break in structure after a run — an early reversal warning."},
    {"term": "Supply zone", "category": "Price Action", "definition": "An area where strong selling began; price often falls again when it returns."},
    {"term": "Demand zone", "category": "Price Action", "definition": "An area where strong buying began; price often rises again when it returns."},
    {"term": "Liquidity sweep", "category": "Smart Money", "definition": "A quick spike through an obvious high/low that triggers stops and then reverses."},
    {"term": "Fair Value Gap (FVG)", "category": "Smart Money", "definition": "An imbalance left by a fast move; price often returns to fill the gap."},
    {"term": "Moving average", "category": "Indicator", "definition": "The average close over N bars, smoothed. Used to define trend direction."},
    {"term": "RSI", "category": "Indicator", "definition": "Relative Strength Index (0-100). Above ~70 is stretched up; below ~30 stretched down."},
    {"term": "MACD", "category": "Indicator", "definition": "Momentum indicator from two averages; the cross above/below zero signals shifting momentum."},
    {"term": "ATR", "category": "Indicator", "definition": "Average True Range — a measure of volatility used to size stops."},
    {"term": "Confidence score", "category": "ORQEVA", "definition": "ORQEVA's blended 0-100% score for a signal, combining regime, momentum and volatility."},
    {"term": "Regime", "category": "ORQEVA", "definition": "ORQEVA's read of the market state: bull, bear, sideways or volatile."},
    {"term": "Tier", "category": "ORQEVA", "definition": "Your ORQEVA plan (free / premium / vip) which sets which markets you receive."},
    {"term": "Kill switch", "category": "ORQEVA", "definition": "The one-click control that blocks all new orders everywhere until re-enabled."},
    {"term": "Paper trading", "category": "ORQEVA", "definition": "Simulated trading at real prices — no money moves. The safest way to practise."},
]


LESSONS: list[dict[str, Any]] = [
    {
        "slug": "market-structure-bos-choch",
        "title": "Market Structure: Reading the Skeleton of a Chart",
        "level": "beginner",
        "minutes": 9,
        "category": "Price Action",
        "methodology": "market_structure",
        "summary": "Learn the one skill professionals read first: the sequence of swing highs and lows that tells you whether the market is trending or turning.",
        "objectives": [
            "Identify swing highs and swing lows",
            "Tell continuation (BOS) from reversal (CHoCH)",
            "Decide which side of the market to hunt",
        ],
        "sections": [
            {
                "heading": "Swing highs and lows are the alphabet",
                "body": [
                    "Before indicators, before patterns, traders read structure. A swing high is a peak with lower highs on both sides; a swing low is a trough with higher lows on both sides. String them together and the chart tells a story.",
                    "An uptrend is simply higher highs and higher lows. A downtrend is lower highs and lower lows. If neither is true, you are in a range.",
                ],
            },
            {
                "heading": "BOS — continuation",
                "body": [
                    "A Break of Structure (BOS) happens when price pushes beyond the last swing point in the direction of the trend. In an uptrend, a BOS above the prior swing high says buyers are still in control.",
                ],
                "bullets": [
                    "BOS confirms the trend is intact",
                    "Trade continuation with the trend, not against it",
                ],
            },
            {
                "heading": "CHoCH — the first crack",
                "body": [
                    "A Change of Character (CHoCH) is the first opposite break after a run. If an uptrend stops making higher highs and instead breaks the last higher low, that is a CHoCH — an early warning that the trend may be turning.",
                ],
            },
            {
                "heading": "Putting it to work",
                "body": [
                    "Most of the time you want to be a continuation trader: wait for a BOS, then buy the pullback. Only look for reversals after a CHoCH, and always with a stop beyond the swing that would prove you wrong.",
                ],
            },
        ],
        "takeaways": [
            "Structure is swings, not indicators",
            "BOS = trend continuation; CHoCH = possible reversal",
            "Trade with structure and put your stop beyond the swing that invalidates it",
        ],
        "quiz": [
            {
                "question": "In an uptrend, what does a Break of Structure above the prior swing high tell you?",
                "options": ["The trend is likely to continue", "The trend is over", "You should short immediately", "Nothing — BOS is meaningless"],
                "answer": 0,
                "explanation": "A BOS in the trend direction confirms buyers are still in control, so continuation is favoured.",
            },
            {
                "question": "A Change of Character is best described as…",
                "options": ["The first opposite structural break after a run", "A moving-average cross", "A news event", "A type of limit order"],
                "answer": 0,
                "explanation": "CHoCH is the first break against the trend and an early reversal warning — not a confirmation of trend.",
            },
        ],
    },
    {
        "slug": "supply-demand-zones",
        "title": "Supply & Demand: Where Big Orders Leave Footprints",
        "level": "beginner",
        "minutes": 8,
        "category": "Price Action",
        "methodology": "supply_demand",
        "summary": "Institutions can't hide. The base before a violent move marks a zone where price often reacts again — learn to find it and trade the reaction.",
        "objectives": [
            "Mark a demand zone and a supply zone",
            "Wait for price to return and confirm",
            "Avoid exhausted zones",
        ],
        "sections": [
            {
                "heading": "Every strong move has an origin",
                "body": [
                    "Before price rockets up, there is usually a quiet few candles — the base — where large buyers accumulated. That base is a demand zone. The mirror image before a sharp drop is a supply zone.",
                    "Price often returns to these zones to fill unfilled orders, which is why they act as support and resistance.",
                ],
            },
            {
                "heading": "Trading the reaction, not the line",
                "body": [
                    "Never buy the instant price touches a zone. Wait for a reaction — a rejection wick, an engulfing candle, a mini structure shift — to show buyers are stepping back in.",
                ],
                "bullets": [
                    "Fresh, untested zones are the best",
                    "A zone that's been hit several times is weak — skip it",
                    "Place your stop just beyond the far edge of the zone",
                ],
            },
        ],
        "takeaways": [
            "Zones are the origin of strong moves",
            "Enter on a reaction, not on the touch",
            "Fresh zones work best; used-up zones fail",
        ],
        "quiz": [
            {
                "question": "What defines a demand zone?",
                "options": ["The last down candles before a strong up move", "The highest price of the day", "An RSI reading above 70", "A moving-average line"],
                "answer": 0,
                "explanation": "The base (last down candles) before a strong impulse marks where buyers took control — a demand zone.",
            },
            {
                "question": "Why wait for a reaction inside a zone?",
                "options": ["To confirm buyers/sellers are actually there, tightening risk", "Because it looks nicer", "To pay more spread", "It is never necessary"],
                "answer": 0,
                "explanation": "A reaction confirms the zone is live and lets you place a tighter stop — far better odds than blindly buying a touch.",
            },
        ],
    },
    {
        "slug": "liquidity-sweeps",
        "title": "Liquidity Sweeps: Why Price Spikes Then Reverses",
        "level": "intermediate",
        "minutes": 9,
        "category": "Smart Money",
        "methodology": "liquidity_sweep",
        "summary": "Stop-losses cluster just beyond obvious highs and lows. Understand the sweep and you stop being the liquidity — and start trading the reversal.",
        "objectives": [
            "Spot where stops are resting",
            "Recognise a failed break as a sweep",
            "Trade the reversal with a defined stop",
        ],
        "sections": [
            {
                "heading": "Where the stops live",
                "body": [
                    "Traders put stops just above swing highs and just below swing lows. Equal highs and lows are especially magnetic: thousands of stops sit a few ticks beyond them.",
                    "Large players push price into that cluster to trigger those orders, filling their own larger position on the other side.",
                ],
            },
            {
                "heading": "The sweep signature",
                "body": [
                    "A sweep looks like a fast wick through the level that closes back inside the range. The break failed — the level held — which is itself information.",
                ],
                "bullets": [
                    "Wick through the level, close back inside",
                    "Often followed by a structure shift in the opposite direction",
                    "The high/low of the wick is the invalidation point",
                ],
            },
            {
                "heading": "Trading it",
                "body": [
                    "After a sweep you trade back into the range toward the opposite side. Your stop sits beyond the sweep wick, which is usually a tight, logical risk.",
                ],
            },
        ],
        "takeaways": [
            "Obvious highs/lows attract stop hunts",
            "A failed break (wick out, close in) is a sweep",
            "Stop beyond the wick; target the other side of the range",
        ],
        "quiz": [
            {
                "question": "A liquidity sweep is best identified by…",
                "options": ["A wick through a high/low that closes back inside the range", "A huge green candle", "A moving-average cross", "Low volume all day"],
                "answer": 0,
                "explanation": "The failed break — spike out, close back in — is the sweep signature.",
            },
            {
                "question": "Where does the stop go on a sweep reversal trade?",
                "options": ["Beyond the sweep wick", "At your entry price", "Nowhere", "At yesterday's close"],
                "answer": 0,
                "explanation": "If price trades back beyond the wick, the sweep idea is invalid, so that is the logical stop location.",
            },
        ],
    },
    {
        "slug": "fair-value-gaps",
        "title": "Fair Value Gaps & Imbalances",
        "level": "intermediate",
        "minutes": 7,
        "category": "Smart Money",
        "methodology": "fair_value_gap",
        "summary": "Fast, one-sided moves leave a gap in the chart. Price often returns to 'rebalance' it — and that retrace is your opportunity.",
        "objectives": [
            "Identify a three-candle fair value gap",
            "Use it as a lower-risk entry",
            "Avoid chasing the impulsive candle",
        ],
        "sections": [
            {
                "heading": "What leaves a gap",
                "body": [
                    "When buyers or sellers move price so fast that one candle barely overlaps its neighbours, a Fair Value Gap (FVG) is left behind. In a bullish gap, the high of candle 1 and the low of candle 3 never meet.",
                    "Markets tend to seek efficiency: price often retraces into the gap to 'rebalance' before continuing.",
                ],
            },
            {
                "heading": "Entering on the retrace",
                "body": [
                    "Instead of chasing the big candle, wait for price to pull back into the gap. Entry there gives a tighter stop (below the gap origin) and a better reward-to-risk.",
                ],
            },
        ],
        "takeaways": [
            "FVG = imbalance from a fast three-candle move",
            "Price often retraces to fill it",
            "Use the gap as an entry zone, not a chase",
        ],
        "quiz": [
            {
                "question": "A bullish fair value gap exists when…",
                "options": ["The high of candle 1 and low of candle 3 do not overlap", "Two candles are the same colour", "RSI is over 70", "The spread widens"],
                "answer": 0,
                "explanation": "That non-overlap is the imbalance — the gap price may return to fill.",
            },
            {
                "question": "Why prefer entering on the retrace into an FVG?",
                "options": ["Better reward-to-risk with a tighter stop", "It guarantees profit", "It pays no spread", "It avoids volatility entirely"],
                "answer": 0,
                "explanation": "Entering at the gap gives a logical, tight invalidation versus chasing the extended impulse candle.",
            },
        ],
    },
    {
        "slug": "trend-following",
        "title": "Trend Following: The Only Edge You Need to Start",
        "level": "beginner",
        "minutes": 8,
        "category": "Trend",
        "methodology": "trend_following",
        "summary": "Trading with the trend is the simplest durable edge. Learn alignment, entries on pullbacks, and stops that follow the market's own structure.",
        "objectives": [
            "Define the trend with averages",
            "Enter on pullbacks, not breakouts chasing",
            "Trail stops to let winners run",
        ],
        "sections": [
            {
                "heading": "Trend is your default bias",
                "body": [
                    "If price is above a rising fast average and a rising slow average, and making higher highs, the path of least resistance is up. Fight that only with strong evidence.",
                    "ORQEVA's engines lean on exactly this: regime detection plus multi-horizon momentum.",
                ],
            },
            {
                "heading": "Entries and exits",
                "body": [
                    "Don't buy the top of an extension. Wait for a pullback to the fast average or a prior structure level, then enter with the trend.",
                ],
                "bullets": [
                    "Long when fast > slow and price > both",
                    "Short when fast < slow and price < both",
                    "Exit on a close back through the slow average",
                ],
            },
        ],
        "takeaways": [
            "Default to the trend's direction",
            "Buy pullbacks, not extended breakouts",
            "Let winners run with a trailing stop",
        ],
        "quiz": [
            {
                "question": "A classic trend-following long filter is…",
                "options": ["Fast average above slow average and price above both", "RSI below 30", "Price at resistance", "A bearish engulfing candle"],
                "answer": 0,
                "explanation": "Fast above slow with price above both is the standard bullish alignment.",
            },
            {
                "question": "Where is the best trend entry?",
                "options": ["On a pullback toward support/averages", "At the very top of an extended candle", "Only at all-time highs", "Never — you shouldn't trade trends"],
                "answer": 0,
                "explanation": "Pullbacks give a tighter stop and better reward-to-risk than chasing the extension.",
            },
        ],
    },
    {
        "slug": "breakout-retest",
        "title": "Breakouts & Retests: Enter Late, Risk Less",
        "level": "beginner",
        "minutes": 7,
        "category": "Breakout",
        "methodology": "breakout_retest",
        "summary": "Most breakouts fail. The ones that don't usually come back to say hello — and that retest is where patient traders get in.",
        "objectives": [
            "Define a clean range/level",
            "Filter false breaks",
            "Enter on the retest with a tight stop",
        ],
        "sections": [
            {
                "heading": "Why breaks fail",
                "body": [
                    "A level everyone can see is a level everyone trades. A first push through it often just grabs liquidity (see Liquidity Sweeps) before snapping back. The higher-quality trade is the retest: price breaks out, pulls back to the broken level, and holds.",
                ],
            },
            {
                "heading": "The retest playbook",
                "body": [
                    "Wait for a decisive close beyond the range, then let price come back. If the old resistance now holds as support (flip), enter with a stop just inside the range.",
                ],
                "bullets": [
                    "Measured-move target = range height projected from the break",
                    "Invalidate on a close back inside the range",
                ],
            },
        ],
        "takeaways": [
            "First breaks are often traps",
            "The retest offers a tighter stop",
            "Broken resistance becomes support (and vice-versa)",
        ],
        "quiz": [
            {
                "question": "Why is the retest often a better entry than the break itself?",
                "options": ["It filters false breaks and gives a tighter stop", "It has no risk", "It always moves further", "It avoids fees"],
                "answer": 0,
                "explanation": "The retest confirms the level flipped and lets you risk a small, logical amount.",
            },
            {
                "question": "After an upside breakout, old resistance usually becomes…",
                "options": ["Support", "Nothing", "A moving average", "A dividend"],
                "answer": 0,
                "explanation": "Levels flip role: broken resistance commonly acts as new support.",
            },
        ],
    },
    {
        "slug": "mean-reversion-ranges",
        "title": "Ranges & Mean Reversion: Trading the Box",
        "level": "intermediate",
        "minutes": 7,
        "category": "Reversal",
        "methodology": "mean_reversion_range",
        "summary": "Not everything trends. In a range, fading the edges back to the middle is a repeatable edge — until the box breaks.",
        "objectives": [
            "Confirm a range",
            "Fade the edges with confirmation",
            "Respect the boundary and cut fast",
        ],
        "sections": [
            {
                "heading": "Recognising a range",
                "body": [
                    "When price repeatedly fails at a high and holds at a low without trending, you are in a range. RSI will swing between overbought at the top and oversold at the bottom.",
                ],
            },
            {
                "heading": "Fade, don't force",
                "body": [
                    "Sell the top edge and buy the bottom edge only with a rejection candle, targeting the middle or the opposite edge. The one rule that matters: if price closes out of the box, you are wrong — cut it.",
                ],
            },
        ],
        "takeaways": [
            "Ranges reward fading the edges",
            "Always use rejection confirmation",
            "A range break invalidates the trade fast",
        ],
        "quiz": [
            {
                "question": "The key risk in range trading is…",
                "options": ["The range breaking into a trend", "Paying commission", "Too much liquidity", "Nothing"],
                "answer": 0,
                "explanation": "Ranges eventually break; the failure mode is holding a fade as price trends away.",
            },
            {
                "question": "In a range you generally…",
                "options": ["Fade the edges toward the middle", "Buy every high", "Hold forever", "Ignore the boundaries"],
                "answer": 0,
                "explanation": "Mean reversion targets the middle from the edges — with confirmation.",
            },
        ],
    },
    {
        "slug": "support-resistance",
        "title": "Support & Resistance Without the Mysticism",
        "level": "beginner",
        "minutes": 6,
        "category": "Price Action",
        "methodology": "support_resistance",
        "summary": "Levels are zones, not lasers. Learn to mark the ones that matter and trade the reaction instead of the line.",
        "objectives": ["Mark meaningful levels", "Rank levels by touches and recency", "Trade reactions only"],
        "sections": [
            {
                "heading": "Zones, not razor lines",
                "body": [
                    "A level is a price band, not a single number. The more times price respected it and the more recently, the more weight it carries.",
                ],
            },
            {
                "heading": "Reaction is the signal",
                "body": [
                    "A level alone is not a trade. Wait for a rejection wick or engulfing candle at the level, and align the trade with the trend whenever possible.",
                ],
            },
        ],
        "takeaways": ["Levels are zones", "More touches + more recent = stronger", "Trade the reaction"],
        "quiz": [
            {
                "question": "Which makes a level more significant?",
                "options": ["More touches and recent tests", "Round numbers only", "A red colour", "High spread"],
                "answer": 0,
                "explanation": "Repeated, recent reactions give a level weight.",
            },
            {
                "question": "A level by itself is…",
                "options": ["Not enough — wait for a reaction", "An automatic buy", "A guarantee", "Always resistance"],
                "answer": 0,
                "explanation": "You trade confirmation at the level, not the level itself.",
            },
        ],
    },
    {
        "slug": "risk-and-position-sizing",
        "title": "Risk First: The Maths That Keeps You Alive",
        "level": "beginner",
        "minutes": 9,
        "category": "Risk",
        "methodology": None,
        "summary": "You cannot control the market — only your risk. This is the single lesson that separates survivors from statistics.",
        "objectives": [
            "Size positions so a loss is 1% of the account",
            "Read reward-to-risk like a pro",
            "Use ORQEVA's Risk page and kill switch",
        ],
        "sections": [
            {
                "heading": "The 1% rule",
                "body": [
                    "Decide before every trade: if the stop is hit, I lose at most 1% of my account. That immediately tells you your position size: size = (account x 1%) / distance-to-stop.",
                    "Lose 10 times in a row and you are still down only ~10% — alive, calm, and able to trade tomorrow. Risk 10% per trade and the same streak wipes you out.",
                ],
            },
            {
                "heading": "Reward-to-risk (R)",
                "body": [
                    "Aim to make at least 2x what you risk. At 2R you only need to win ~34% of trades to break even; that is why pros obsess over R, not win-rate.",
                ],
                "bullets": [
                    "Set the stop and target BEFORE you enter",
                    "Never move a stop further away to avoid a loss",
                ],
            },
            {
                "heading": "ORQEVA's guardrails",
                "body": [
                    "Every signal ships with an entry, stop-loss and take-profit. On the Risk page you set a daily loss limit, max positions and a kill switch that blocks all new orders instantly.",
                ],
            },
        ],
        "takeaways": [
            "Risk a fixed small % per trade",
            "Size from the stop distance, not a feeling",
            "Think in R multiples; protect capital first",
        ],
        "quiz": [
            {
                "question": "If your account is $10,000 and you risk 1% with a 2% stop distance, your position size is about…",
                "options": ["$5,000", "$100", "$500", "$10,000"],
                "answer": 0,
                "explanation": "Risk $100 (1%). Stop distance 2% -> size = 100 / 0.02 = $5,000 notional.",
            },
            {
                "question": "At a 1:2 reward-to-risk, roughly what win-rate breaks even?",
                "options": ["About 34%", "About 66%", "About 90%", "It doesn't matter"],
                "answer": 0,
                "explanation": "With 2R wins vs 1R losses, ~33-34% winning trades break even before costs.",
            },
        ],
    },
    {
        "slug": "reading-orqeva-signals",
        "title": "How to Read an ORQEVA Signal",
        "level": "beginner",
        "minutes": 8,
        "category": "ORQEVA",
        "methodology": None,
        "summary": "Turn a signal card into a decision. What direction, confidence, entry, stop, target and strategy actually mean — and when to skip a signal.",
        "objectives": [
            "Decode every field on a signal",
            "Judge quality via confidence and R",
            "Decide when NOT to take a signal",
        ],
        "sections": [
            {
                "heading": "Anatomy of a signal",
                "body": [
                    "Each ORQEVA signal shows the symbol and market, a direction (buy/sell), a confidence score, an entry price, a stop-loss, a take-profit and the strategy that produced it, plus the indicator breakdown.",
                ],
                "bullets": [
                    "Direction — which way the engine expects price to go",
                    "Confidence — a blended 0-100% score, not a promise",
                    "Entry / Stop / Target — the plan; compute your R from these",
                    "Strategy — the logic behind the call, so you can learn it",
                ],
            },
            {
                "heading": "When to skip a signal",
                "body": [
                    "Low confidence, a stop that is far away, an R below 1:1.5, or an entry you would have to chase — all reasons to pass. The best traders skip far more signals than they take.",
                ],
            },
        ],
        "takeaways": [
            "Read direction, confidence, entry, stop, target and strategy",
            "Confidence is a probability estimate, not a guarantee",
            "Skipping bad signals is a skill",
        ],
        "quiz": [
            {
                "question": "ORQEVA's confidence score is…",
                "options": ["A blended probability estimate, not a promise", "A guarantee of profit", "Your position size", "The spread"],
                "answer": 0,
                "explanation": "It blends regime, momentum and volatility into an estimate — you still manage risk.",
            },
            {
                "question": "A signal with reward-to-risk below ~1:1.5 is usually…",
                "options": ["Best skipped", "An instant buy", "Risk-free", "A typo"],
                "answer": 0,
                "explanation": "Poor R makes profits mathematically hard; passing is often the right call.",
            },
        ],
    },
    {
        "slug": "trading-psychology",
        "title": "Psychology & Discipline: The Final Boss",
        "level": "beginner",
        "minutes": 8,
        "category": "Psychology",
        "methodology": None,
        "summary": "Your edge is worthless if you can't execute it. Beat FOMO, revenge trading and over-sizing with rules you set when calm.",
        "objectives": [
            "Name your emotional failure modes",
            "Build a pre-trade checklist",
            "Journal to improve deliberately",
        ],
        "sections": [
            {
                "heading": "The three killers",
                "body": [
                    "FOMO — chasing entries out of fear of missing out. Revenge trading — doubling size after a loss to 'get it back'. Over-sizing — risking too much because you're sure. All three blow up accounts that had a real edge.",
                ],
            },
            {
                "heading": "Systems beat willpower",
                "body": [
                    "Write a short pre-trade checklist (trend? level? R >= 1:2? size <= 1%?). If you can't tick every box, you don't take the trade. Then journal every trade: setup, emotion, outcome. Patterns in your journal are your best teacher.",
                ],
            },
        ],
        "takeaways": [
            "FOMO, revenge and over-sizing are the killers",
            "Use a checklist so decisions aren't emotional",
            "Journal — your patterns are the lesson",
        ],
        "quiz": [
            {
                "question": "Revenge trading usually means…",
                "options": ["Increasing size right after a loss to win it back", "Taking a break", "Journaling", "Reducing risk"],
                "answer": 0,
                "explanation": "It is an emotional response that ignores your rules and typically compounds losses.",
            },
            {
                "question": "The most reliable way to reduce emotional decisions is…",
                "options": ["A written pre-trade checklist and journal", "More leverage", "Watching more charts", "Removing stop-losses"],
                "answer": 0,
                "explanation": "Pre-committed rules and review replace in-the-moment emotion with process.",
            },
        ],
    },
]

LESSON_BY_SLUG = {l["slug"]: l for l in LESSONS}


def lesson_index() -> list[dict[str, Any]]:
    """Lightweight list for the Academy index page."""
    return [
        {
            "slug": l["slug"],
            "title": l["title"],
            "level": l["level"],
            "minutes": l["minutes"],
            "category": l["category"],
            "methodology": l["methodology"],
            "summary": l["summary"],
        }
        for l in LESSONS
    ]


def get_lesson(slug: str) -> dict[str, Any] | None:
    return LESSON_BY_SLUG.get(slug)


def all_quiz() -> list[dict[str, Any]]:
    """Flatten every lesson quiz for the final exam."""
    out: list[dict[str, Any]] = []
    for l in LESSONS:
        for q in l.get("quiz", []):
            out.append({**q, "lesson": l["title"], "slug": l["slug"]})
    return out


def status() -> dict[str, Any]:
    s = llm_service.status()
    return {
        **s,
        "lessons": len(LESSONS),
        "glossary_terms": len(GLOSSARY),
        "methodologies": len(METHODOLOGIES),
    }


# --------------------------------------------------------------------------- #
# AI Instructor
# --------------------------------------------------------------------------- #

def _persona() -> str:
    return (
        "You are the ORQEVA AI Instructor — a patient, sophisticated trading mentor "
        "for complete beginners. You explain WITH the ORQEVA platform: signals, "
        "confidence scores, the risk page, paper trading. Style: warm, concrete, "
        "Socratic — teach the why, not just the what. Use short paragraphs and "
        "occasional bullet points. Always connect theory to a real decision the "
        "learner can make today. Never promise profits; always reinforce risk "
        "management and that this is education, not financial advice. When a "
        "concept maps to one of the methodologies below, name it so the learner "
        "can study it on the Academy pages. Keep answers under ~250 words unless "
        "asked to go deep.\n\n"
        "METHODOLOGY LIBRARY (public concepts):\n" + render_library() + "\n"
        f"ACADEMY LESSONS: {', '.join(l['title'] for l in LESSONS)}\n"
        "DISCLAIMER to echo when giving any trade-related guidance: " + DISCLAIMER
    )


def _scripted_answer(question: str) -> str:
    """Deterministic fallback when no LLM key is configured."""
    q = (question or "").lower()
    terms: list[tuple[str, dict[str, Any]]] = [
        ("structure", METHODOLOGY_BY_KEY["market_structure"]),
        ("bos", METHODOLOGY_BY_KEY["market_structure"]),
        ("choch", METHODOLOGY_BY_KEY["market_structure"]),
        ("supply", METHODOLOGY_BY_KEY["supply_demand"]),
        ("demand", METHODOLOGY_BY_KEY["supply_demand"]),
        ("order block", METHODOLOGY_BY_KEY["supply_demand"]),
        ("liquidity", METHODOLOGY_BY_KEY["liquidity_sweep"]),
        ("sweep", METHODOLOGY_BY_KEY["liquidity_sweep"]),
        ("stop hunt", METHODOLOGY_BY_KEY["liquidity_sweep"]),
        ("fair value", METHODOLOGY_BY_KEY["fair_value_gap"]),
        ("fvg", METHODOLOGY_BY_KEY["fair_value_gap"]),
        ("imbalance", METHODOLOGY_BY_KEY["fair_value_gap"]),
        ("trend", METHODOLOGY_BY_KEY["trend_following"]),
        ("breakout", METHODOLOGY_BY_KEY["breakout_retest"]),
        ("retest", METHODOLOGY_BY_KEY["breakout_retest"]),
        ("range", METHODOLOGY_BY_KEY["mean_reversion_range"]),
        ("mean reversion", METHODOLOGY_BY_KEY["mean_reversion_range"]),
        ("support", METHODOLOGY_BY_KEY["support_resistance"]),
        ("resistance", METHODOLOGY_BY_KEY["support_resistance"]),
    ]
    for needle, m in terms:
        if needle in q:
            return (
                f"**{m['name']}** — {m['summary']}\n\n"
                f"Key ideas: {'; '.join(m['concepts'])}.\n\n"
                f"Entry: {'; '.join(m['entry_rules'])}. "
                f"Risk: {'; '.join(m['risk_rules'])}.\n\n"
                f"Study it in the Academy lesson that covers this methodology, then "
                f"look at how ORQEVA's engines express the same idea in their signals.\n\n"
                f"_{DISCLAIMER}_"
            )
    if any(w in q for w in ("risk", "size", "position", "stop", "1%", "lose")):
        lesson = LESSON_BY_SLUG["risk-and-position-sizing"]
        return (
            "**Risk first.** " + lesson["summary"] + "\n\n"
            + " ".join(lesson["sections"][0]["body"]) + "\n\n"
            f"_{DISCLAIMER}_"
        )
    if any(w in q for w in ("signal", "confidence", "entry", "target", "tp", "take profit")):
        lesson = LESSON_BY_SLUG["reading-orqeva-signals"]
        return "**Reading a signal.** " + lesson["summary"] + "\n\n" + " ".join(lesson["sections"][0]["body"])
    return (
        "Great question. The live AI Instructor is offline right now (no model key "
        "configured), but I can still guide you through the Academy. Popular topics: "
        "market structure (BOS/CHoCH), supply & demand, liquidity sweeps, fair value "
        "gaps, trend following, breakouts, ranges, support/resistance and risk sizing.\n\n"
        "Ask about any of those, or open a lesson and use 'Explain this signal' on a "
        "live ORQEVA signal.\n\n"
        f"_{DISCLAIMER}_"
    )


SYSTEM_FOOTER = "\n\nRemember: education, not financial advice."


async def tutor(messages: list[dict], user: dict | None = None) -> dict[str, Any]:
    """Conversational instructor. Falls back to scripted content without a key."""
    safe = [
        {"role": ("assistant" if m.get("role") == "assistant" else "user"), "content": str(m.get("content", ""))[:4000]}
        for m in messages[-12:]
        if m.get("content")
    ]
    if not safe:
        return {"reply": "Ask me anything about trading — I'll teach it against real ORQEVA data.", "live": llm_service.configured()}

    system = _persona()
    if user:
        system += f"\nLearner tier: {user.get('tier', 'free')}."
        if user.get("username"):
            system += f" Learner name: {user['username']}."

    reply = await llm_service.chat(safe, system=system, temperature=0.6, max_tokens=700)
    live = reply is not None
    if reply is None:
        reply = _scripted_answer(safe[-1]["content"])
    return {"reply": reply, "live": live}


async def explain_signal(signal: dict, user: dict | None = None) -> dict[str, Any]:
    """Explain one ORQEVA signal in beginner terms, using its real numbers."""
    try:
        entry = float(signal.get("entry_price") or 0)
        stop = float(signal.get("stop_loss") or 0)
        target = float(signal.get("take_profit") or 0)
    except (TypeError, ValueError):
        entry = stop = target = 0.0

    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = (reward / risk) if risk else 0.0

    facts = (
        f"Symbol {signal.get('symbol')} ({signal.get('market')}), direction "
        f"{signal.get('direction')}, confidence {signal.get('confidence')}, "
        f"strategy '{signal.get('strategy')}', entry {entry}, stop {stop}, "
        f"target {target}, reward-to-risk ~1:{rr:.2f}."
    )

    system = _persona()
    user_msg = (
        "Explain this live ORQEVA signal to a beginner. Cover: what the engine is "
        "seeing, which public methodology it resembles, what the stop and target "
        "mean, the reward-to-risk, the main risk to the idea, and one thing to "
        "watch. Signal facts: " + facts
    )
    reply = await llm_service.chat(
        [{"role": "user", "content": user_msg}], system=system, temperature=0.5, max_tokens=650
    )
    live = reply is not None
    if reply is None:
        direction = (signal.get("direction") or "").upper()
        verdict = "favourable" if rr >= 2 else ("thin" if rr else "unclear")
        reply = (
            f"**{signal.get('symbol')} — {direction}** ({signal.get('market')}, "
            f"strategy: {signal.get('strategy')}).\n\n"
            f"The engine sees a {direction.lower()} setup and scores its confidence at "
            f"{signal.get('confidence')}. The plan: entry {entry}, stop {stop}, target "
            f"{target}.\n\n"
            f"- **Risk**: distance from entry to stop is your risk; here it maps to a "
            f"~1:{rr:.2f} reward-to-risk, which is {verdict}.\n"
            f"- **What to watch**: a close beyond the stop invalidates the idea — that is "
            f"when good traders walk away.\n\n"
            f"Practice executing this plan on paper trading before risking real capital.\n\n"
            f"_{DISCLAIMER}_"
        )
    return {"reply": reply, "live": live}
