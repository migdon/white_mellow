"""
Carry + time-series momentum on 9 USD pairs, daily marking, monthly rebalance.

Pre-registered family (5 rules, fixed BEFORE looking at results):
  CARRY_XS3   long 3 highest-rate, short 3 lowest-rate currencies   [primary]
  TSMOM_12M   sign of trailing 12m excess return, per pair           [primary]
  TSMOM_3M    same, 3 months
  TSMOM_1M    same, 1 month
  COMBO       50/50 risk blend of CARRY_XS3 and TSMOM_12M            [primary]

No parameter is tuned. Lookbacks are the textbook ones (Moskowitz-Ooi-Pedersen
2012; Lustig-Roussanov-Verdelhan 2011 / Menkhoff et al. 2012).

Timing: signal at month-end close t, position held from t+1 close-to-close
(delay=1). Stress test uses delay=2 (one extra day late).
"""

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

ANN = 252
ASSET_VOL = 0.10           # per-position risk budget before portfolio scaling
PORT_VOL = 0.10            # portfolio vol target for reported numbers
VOL_COM = 60               # EWMA centre of mass (days) for ex-ante vol


@dataclass
class Costs:
    spread_mult: float = 1.0       # x typical spread
    swap_markup: float = 0.010     # broker markup, annual fraction of |notional| per side
    delay: int = 1                 # days between signal close and position start


# ------------------------------------------------------------------ returns
def excess_returns(spot: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    """Daily return of long ccy / short USD incl. interest differential (interbank)."""
    days = spot.index.to_series().diff().dt.days.fillna(1).values[:, None]
    diff = rates[spot.columns].sub(rates["USD"], axis=0).shift(1)
    r = spot.pct_change() + diff.values * days / 365.0
    return r.iloc[1:]


def month_ends(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = idx.to_series()
    return pd.DatetimeIndex(s.groupby(idx.to_period("M")).max().values)


def ewm_vol(ret: pd.DataFrame) -> pd.DataFrame:
    return ret.ewm(com=VOL_COM, min_periods=60).std() * np.sqrt(ANN)


# ------------------------------------------------------------------ signals
def sig_carry_xs(diff: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    rk = diff.rank(axis=1, method="first")
    n = diff.notna().sum(axis=1)
    s = (rk > n.values[:, None] - k).astype(float) - (rk <= k).astype(float)
    return s.where(diff.notna(), 0.0)


def sig_tsmom(ret: pd.DataFrame, days: int) -> pd.DataFrame:
    cum = np.log1p(ret).rolling(days, min_periods=int(days * 0.9)).sum()
    return np.sign(cum).fillna(0.0)


def raw_weights(ret: pd.DataFrame, rates: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Month-end target weights per rule (risk-parity per position, before port scaling)."""
    me = month_ends(ret.index)
    vol = ewm_vol(ret)
    inv = (ASSET_VOL / vol).clip(upper=5.0)          # cap leverage on dead-calm pairs
    diff = rates[ret.columns].sub(rates["USD"], axis=0)
    sig = {
        "CARRY_XS3": sig_carry_xs(diff),
        "TSMOM_12M": sig_tsmom(ret, 252),
        "TSMOM_3M": sig_tsmom(ret, 63),
        "TSMOM_1M": sig_tsmom(ret, 21),
    }
    out = {}
    for k, s in sig.items():
        w = (s * inv).loc[me]
        nact = (s.loc[me] != 0).sum(axis=1).replace(0, np.nan)
        out[k] = w.div(np.sqrt(nact), axis=0).fillna(0.0)   # ~ASSET_VOL if uncorrelated
    # equal *risk*, not equal notional: the TSMOM book carries a USD factor and is
    # ~2x as volatile as the dollar-neutral carry book, so normalise each first
    c = out["CARRY_XS3"].div(book_vol(out["CARRY_XS3"], ret), axis=0)
    t = out["TSMOM_12M"].div(book_vol(out["TSMOM_12M"], ret), axis=0)
    out["COMBO"] = (0.5 * c + 0.5 * t).fillna(0.0) * ASSET_VOL
    return out


def book_vol(w_me: pd.DataFrame, ret: pd.DataFrame) -> pd.Series:
    """Ex-ante vol of holding the month-end book over the trailing year (uses data <= t)."""
    me = w_me.index
    cov_vol = []
    for t in me:
        hist = ret.loc[:t].iloc[-252:]
        if len(hist) < 120:
            cov_vol.append(np.nan)
            continue
        cov_vol.append(float((hist * w_me.loc[t]).sum(axis=1).std() * np.sqrt(ANN)))
    return pd.Series(cov_vol, index=me).replace(0.0, np.nan)


# ------------------------------------------------------------------ engine
def run(w_me: pd.DataFrame, ret: pd.DataFrame, half_spread: pd.DataFrame,
        costs: Costs, port_scale: bool = True, shift: int = 0) -> pd.Series:
    """
    Daily net return series. Month-end weights are held until the next month-end.
    `shift` circularly rotates the weight path vs returns (used for the null test).
    """
    w = w_me.reindex(ret.index).ffill().fillna(0.0)
    if shift:
        w = pd.DataFrame(np.roll(w.values, shift, axis=0), index=w.index, columns=w.columns)
    w = w.shift(costs.delay).fillna(0.0)

    if port_scale:
        # ex-ante portfolio scaling: realised vol of the *unscaled* book, known at t-1
        gross0 = (w * ret).sum(axis=1)
        pv = gross0.ewm(com=VOL_COM, min_periods=120).std().shift(1) * np.sqrt(ANN)
        k = (PORT_VOL / pv).clip(upper=4.0)
        # only update the scaler on rebalance days so turnover stays monthly
        reb = (w.diff().abs().sum(axis=1) > 0)
        k = k.where(reb).ffill().fillna(0.0)
        w = w.mul(k, axis=0)

    gross = (w * ret).sum(axis=1)
    trade = w.diff().abs().fillna(w.abs())
    tc = (trade * half_spread.reindex(ret.index).ffill() * costs.spread_mult).sum(axis=1)
    days = ret.index.to_series().diff().dt.days.fillna(1)
    swap = w.abs().sum(axis=1) * costs.swap_markup * days / 365.0
    return gross - tc - swap


# ------------------------------------------------------------------ stats
def nw_tstat(x: pd.Series, lags: int = 3) -> float:
    x = x.dropna().values
    n = len(x)
    if n < 12:
        return float("nan")
    e = x - x.mean()
    s = e @ e / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / n
    return float(x.mean() / np.sqrt(s / n))


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    r = r[r.index >= r.ne(0).idxmax()] if r.ne(0).any() else r
    if len(r) < 60:
        return {}
    m = (1 + r).resample("ME").prod() - 1
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    yrs = len(r) / ANN
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(ANN)
    return {
        "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
        "cagr": cagr, "vol": vol, "sharpe": r.mean() / r.std() * np.sqrt(ANN),
        "t_nw": nw_tstat(m), "maxdd": dd.min(),
        "worst_day": r.min(), "p_day_lt_1_8": float((r < -0.018).mean()),
        "hit_month": float((m > 0).mean()),
    }


def by_period(r: pd.Series, periods: Dict[str, tuple]) -> Dict[str, dict]:
    return {k: stats(r.loc[a:b]) for k, (a, b) in periods.items()}


# ------------------------------------------------------------------ null test
def null_max_sharpe(weights: Dict[str, pd.DataFrame], ret, hs, costs, n=400, seed=7):
    """
    Circular-shift null: rotate every rule's position path by the SAME random
    offset (>= 1y) against returns. Keeps each rule's turnover, persistence and
    the cross-rule correlation; destroys any timing link to future returns.
    Returns (per-rule null Sharpes, null distribution of the family max).
    """
    rng = np.random.default_rng(seed)
    T = len(ret)
    per = {k: [] for k in weights}
    mx = []
    for _ in range(n):
        sh = int(rng.integers(ANN, T - ANN))
        srs = [stats(run(w, ret, hs, costs, shift=sh)).get("sharpe", np.nan) for w in weights.values()]
        for k, s in zip(weights, srs):
            per[k].append(s)
        mx.append(np.nanmax(srs))
    return {k: np.array(v) for k, v in per.items()}, np.array(mx)


# ------------------------------------------------------------------ prop challenge MC
def prop_mc(r: pd.Series, target_vol: float, profit_target=0.08, max_loss=0.05,
            daily_limit=0.03, horizon=504, n=4000, block=20, seed=11) -> dict:
    """
    Stationary block bootstrap of daily returns re-scaled to `target_vol`.
    Static max-loss from initial balance, daily loss vs start-of-day equity,
    both checked on daily closes (intraday breaches are NOT modelled -> optimistic).
    """
    x = r.dropna().values
    x = x / x.std() * target_vol / np.sqrt(ANN)
    T = len(x)
    rng = np.random.default_rng(seed)
    pass_day, fail = [], 0
    p_by = {30: 0, 60: 0, 120: 0, 252: 0, horizon: 0}
    for _ in range(n):
        eq, i, t = 1.0, int(rng.integers(T)), 0
        res = None
        while t < horizon:
            if rng.random() < 1.0 / block:
                i = int(rng.integers(T))
            d = x[i % T]
            i += 1
            t += 1
            if d <= -daily_limit:
                res = ("fail", t)
                break
            eq *= 1 + d
            if eq <= 1 - max_loss:
                res = ("fail", t)
                break
            if eq >= 1 + profit_target:
                res = ("pass", t)
                break
        if res and res[0] == "pass":
            pass_day.append(res[1])
            for h in p_by:
                if res[1] <= h:
                    p_by[h] += 1
        elif res:
            fail += 1
    return {
        "vol": target_vol,
        **{f"p_pass_{h}d": p_by[h] / n for h in p_by},
        "p_fail": fail / n,
        "p_undecided": 1 - (len(pass_day) + fail) / n,
        "median_days_to_pass": float(np.median(pass_day)) if pass_day else float("nan"),
    }


def zero_edge_pass_prob(profit_target=0.08, max_loss=0.05) -> float:
    """Gambler's-ruin baseline: a driftless random walk hits +T before -L with p = L/(L+T)."""
    return max_loss / (max_loss + profit_target)
