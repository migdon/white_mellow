"""
Sanity checks for the engine (run: python -m tests.test_sanity).

1. Pure random walks, no edge          -> no rule looks good.
2. Planted carry premium               -> CARRY_XS3 finds it.
3. Planted 12m trend                   -> TSMOM_12M finds it.
4. No look-ahead: scrambling the future does not change past P&L.
"""

import numpy as np
import pandas as pd

from carry_tsmom import backtest as bt
from carry_tsmom.data import CURRENCIES, half_spread_frac
from carry_tsmom.policy_rates import policy_rates

IDX = pd.bdate_range("1999-01-04", "2024-12-31")


def _spot(drift: pd.DataFrame, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal((len(IDX), len(CURRENCIES))) * 0.10 / np.sqrt(252)
    lr = drift.values / 252 + eps
    return pd.DataFrame(np.exp(np.cumsum(lr, axis=0)), index=IDX, columns=CURRENCIES)


def _family(spot, rates):
    ret = bt.excess_returns(spot, rates)
    W = bt.raw_weights(ret, rates)
    hs = half_spread_frac(spot) * 0
    c = bt.Costs(spread_mult=0, swap_markup=0)
    return {k: bt.stats(bt.run(w, ret, hs, c))["sharpe"] for k, w in W.items()}, (W, ret, hs, c)


def test_no_edge():
    rates = pd.DataFrame(0.0, index=IDX, columns=CURRENCIES + ["USD"])
    srs = []
    for s in range(6):
        sr, _ = _family(_spot(pd.DataFrame(0.0, index=IDX, columns=CURRENCIES), seed=s), rates)
        srs += list(sr.values())
    srs = np.array(srs)
    # 25y of noise: SE of Sharpe ~ 0.2. Mean should be ~0, extremes bounded.
    assert abs(srs.mean()) < 0.12, srs.mean()
    assert np.abs(srs).max() < 0.75, srs
    print(f"no edge: mean SR {srs.mean():+.3f}, max |SR| {np.abs(srs).max():.2f}  OK")


def test_planted_carry():
    rates = policy_rates(IDX)
    diff = rates[CURRENCIES].sub(rates["USD"], axis=0)
    # forward-premium puzzle: high-rate ccys do NOT depreciate -> full carry earned;
    # add a little extra appreciation to make the premium unmistakable
    sr, _ = _family(_spot(0.5 * diff, seed=1), rates)
    assert sr["CARRY_XS3"] > 0.6, sr
    print(f"planted carry: CARRY_XS3 SR {sr['CARRY_XS3']:+.2f}  OK")


def test_planted_trend():
    rates = pd.DataFrame(0.0, index=IDX, columns=CURRENCIES + ["USD"])
    rng = np.random.default_rng(3)
    # slow regime drift: +/-10%/yr, switching on average every ~3 years
    reg = np.sign(rng.standard_normal(len(CURRENCIES)))
    d = np.zeros((len(IDX), len(CURRENCIES)))
    for t in range(len(IDX)):
        flip = rng.random(len(CURRENCIES)) < 1 / 750
        reg = np.where(flip, -reg, reg)
        d[t] = 0.10 * reg
    sr, _ = _family(_spot(pd.DataFrame(d, index=IDX, columns=CURRENCIES), seed=4), rates)
    assert sr["TSMOM_12M"] > 0.5, sr
    print(f"planted trend: TSMOM_12M SR {sr['TSMOM_12M']:+.2f}  OK")


def test_no_lookahead():
    rates = policy_rates(IDX)
    spot = _spot(pd.DataFrame(0.0, index=IDX, columns=CURRENCIES), seed=5)
    cut = IDX[4000]
    spot2 = spot.copy()
    rng = np.random.default_rng(9)
    spot2.loc[spot2.index > cut] *= np.exp(rng.standard_normal(spot2.loc[spot2.index > cut].shape) * 0.05)
    out = []
    for s in (spot, spot2):
        ret = bt.excess_returns(s, rates)
        W = bt.raw_weights(ret, rates)
        out.append(bt.run(W["COMBO"], ret, half_spread_frac(s), bt.Costs()))
    a, b = out[0].loc[:cut], out[1].loc[:cut]
    assert np.allclose(a.values, b.values), (a - b).abs().max()
    print("no look-ahead: P&L up to cut identical after scrambling the future  OK")


if __name__ == "__main__":
    test_no_edge()
    test_planted_carry()
    test_planted_trend()
    test_no_lookahead()
