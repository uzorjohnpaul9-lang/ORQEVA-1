export type InstrumentMarket = "stock" | "forex" | "crypto" | "commodity";

export interface Instrument {
  symbol: string;
  market: InstrumentMarket;
  name?: string;
}

/** First-run watchlist: a small, mixed set so the page is never overwhelming. */
export const DEFAULT_WATCHLIST = [
  "EUR/USD",
  "GBP/USD",
  "XAU/USD",
  "BTC/USD",
  "AAPL",
];

const NAMES: Record<string, string> = {
  "EUR/USD": "Euro / US Dollar",
  "GBP/USD": "British Pound / US Dollar",
  "USD/JPY": "US Dollar / Japanese Yen",
  "USD/CHF": "US Dollar / Swiss Franc",
  "AUD/USD": "Australian Dollar / US Dollar",
  "USD/CAD": "US Dollar / Canadian Dollar",
  "NZD/USD": "New Zealand Dollar / US Dollar",
  "XAU/USD": "Gold",
  "XAG/USD": "Silver",
  "WTI/USD": "Crude Oil (WTI)",
  "BRENT/USD": "Crude Oil (Brent)",
  "NATGAS/USD": "Natural Gas",
  "BTC/USD": "Bitcoin",
  "ETH/USD": "Ethereum",
  "SOL/USD": "Solana",
  "BNB/USD": "BNB",
  "XRP/USD": "XRP",
  "ADA/USD": "Cardano",
  "DOGE/USD": "Dogecoin",
  "AVAX/USD": "Avalanche",
  "TRX/USD": "TRON",
  "SHIB/USD": "Shiba Inu",
  "PEPE/USD": "Pepe",
  "BONK/USD": "Bonk",
  "FLOKI/USD": "Floki",
  "WIF/USD": "dogwifhat",
  "TRUMP/USD": "Official Trump",
  "FARTCOIN/USD": "Fartcoin",
  "PENGU/USD": "Pudgy Penguins",
  "LINK/USD": "Chainlink",
  "NEAR/USD": "NEAR Protocol",
  "SUI/USD": "Sui",
  "SEI/USD": "Sei",
  "TIA/USD": "Celestia",
  "INJ/USD": "Injective",
  "ARB/USD": "Arbitrum",
  "OP/USD": "Optimism",
  "APT/USD": "Aptos",
  "LTC/USD": "Litecoin",
  "DOT/USD": "Polkadot",
  "ATOM/USD": "Cosmos",
  "UNI/USD": "Uniswap",
  "AAVE/USD": "Aave",
};

const STOCKS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
  "TSLA", "META", "JPM", "V", "UNH",
  "XOM", "JNJ", "WMT", "PG", "MA",
  "HD", "CVX", "MRK", "ABBV", "LLY",
];

const FOREX = [
  "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
  "AUD/USD", "USD/CAD", "NZD/USD",
];

const CRYPTO = [
  "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD",
  "XRP/USD", "ADA/USD", "DOGE/USD", "AVAX/USD", "TRX/USD",
  "SHIB/USD", "PEPE/USD", "BONK/USD", "FLOKI/USD",
  "WIF/USD", "TRUMP/USD", "FARTCOIN/USD", "PENGU/USD",
  "LINK/USD", "NEAR/USD", "SUI/USD", "SEI/USD", "TIA/USD",
  "INJ/USD", "ARB/USD", "OP/USD", "APT/USD",
  "LTC/USD", "DOT/USD", "ATOM/USD", "UNI/USD", "AAVE/USD",
];

const COMMODITIES = ["XAU/USD", "XAG/USD", "WTI/USD", "BRENT/USD", "NATGAS/USD"];

function build(): Instrument[] {
  const seen = new Set<string>();
  const out: Instrument[] = [];
  const add = (symbol: string, market: InstrumentMarket) => {
    if (seen.has(symbol)) return;
    seen.add(symbol);
    out.push({ symbol, market, name: NAMES[symbol] });
  };
  STOCKS.forEach((s) => add(s, "stock"));
  FOREX.forEach((s) => add(s, "forex"));
  CRYPTO.forEach((s) => add(s, "crypto"));
  COMMODITIES.forEach((s) => add(s, "commodity"));
  return out;
}

/** Every instrument the engines can scan, regardless of whether it has a signal. */
export const INSTRUMENTS: Instrument[] = build();
