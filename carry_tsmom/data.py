"""
Data loading. Everything is expressed per *currency vs USD*:

    spot[c]  = USD per 1 unit of currency c   (so +return = c up vs USD)
    w[c] > 0 = long c / short USD             (EURUSD buy, USDJPY sell, ...)

Two sources:
  * Fed H.10 noon rates (data/h10_units_per_usd.csv) - mid prices, 1999 -> now.
  * MT5 D1 export from your broker (see export_mt5.py) - broker closes.
"""

import json
import os
from typing import Optional

import pandas as pd

# currency -> (MT5 symbol, USD is base?)   USD-base pairs are inverted.
PAIRS = {
    "EUR": ("EURUSD", False), "GBP": ("GBPUSD", False), "AUD": ("AUDUSD", False),
    "NZD": ("NZDUSD", False), "JPY": ("USDJPY", True), "CHF": ("USDCHF", True),
    "CAD": ("USDCAD", True), "NOK": ("USDNOK", True), "SEK": ("USDSEK", True),
}
CURRENCIES = list(PAIRS)

# Typical retail ECN spread (in pips) used when no broker spec file is given.
DEFAULT_SPREAD_PIPS = {
    "EUR": 0.8, "GBP": 1.2, "AUD": 1.0, "NZD": 1.8, "JPY": 1.0,
    "CHF": 1.5, "CAD": 1.5, "NOK": 30.0, "SEK": 35.0,
}
PIP = {c: (0.01 if c == "JPY" else 0.0001) for c in CURRENCIES}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H10_FILE = os.path.join(_ROOT, "data", "h10_units_per_usd.csv")


def load_h10(path: str = H10_FILE) -> pd.DataFrame:
    """H.10 file is units-of-currency per USD -> invert to USD per unit."""
    raw = pd.read_csv(path, index_col=0, parse_dates=True)
    raw = raw[CURRENCIES].dropna(how="all").ffill().dropna()
    return 1.0 / raw


def load_mt5(folder: str, suffix: str = "") -> pd.DataFrame:
    """Read <folder>/<SYMBOL>_D1.csv written by export_mt5.py."""
    cols = {}
    for c, (sym, usd_base) in PAIRS.items():
        f = os.path.join(folder, f"{sym}{suffix}_D1.csv")
        if not os.path.exists(f):
            raise FileNotFoundError(f)
        d = pd.read_csv(f, parse_dates=["time"]).set_index("time")
        d = d[d.index.dayofweek < 5]           # drop Sunday stubs some brokers emit
        cols[c] = 1.0 / d["close"] if usd_base else d["close"]
    df = pd.DataFrame(cols).sort_index()
    df.index = df.index.normalize()
    return df.ffill().dropna()


def pair_price(spot: pd.DataFrame) -> pd.DataFrame:
    """Back to the quoted pair price (needed to turn pips into %)."""
    return pd.DataFrame({c: (1.0 / spot[c] if PAIRS[c][1] else spot[c]) for c in spot})


def half_spread_frac(spot: pd.DataFrame, spread_pips: Optional[dict] = None) -> pd.DataFrame:
    """Cost of trading 1 unit notional = half the spread, as fraction of price."""
    sp = spread_pips or DEFAULT_SPREAD_PIPS
    px = pair_price(spot)
    return pd.DataFrame({c: sp[c] * PIP[c] / 2.0 / px[c] for c in spot})


def load_broker_specs(folder: str) -> Optional[dict]:
    f = os.path.join(folder, "symbol_specs.json")
    if not os.path.exists(f):
        return None
    with open(f) as fh:
        return json.load(fh)
