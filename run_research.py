"""
Carry + TSMOM research run.

    python run_research.py                      # Fed H.10 mid data, 1999 -> now
    python run_research.py --mt5 mt5_export     # your broker's D1 closes + swaps

Writes reports/carry_tsmom_results.json and prints a summary.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from carry_tsmom import backtest as bt
from carry_tsmom.data import (CURRENCIES, PAIRS, half_spread_frac, load_broker_specs,
                              load_h10, load_mt5)
from carry_tsmom.policy_rates import policy_rates

PERIODS = {
    # 3-way split (same discipline as the intraday study)
    "train_1999_2008": ("1999-01-01", "2008-12-31"),
    "valid_2009_2016": ("2009-01-01", "2016-12-31"),
    "test_2017_now": ("2017-01-01", "2100-01-01"),
    # literature split: everything after the papers were published is true OOS
    "post_pub_2013_now": ("2013-01-01", "2100-01-01"),
    "full": ("1999-01-01", "2100-01-01"),
}
PRIMARY = ["CARRY_XS3", "TSMOM_12M", "COMBO"]


def broker_swap_summary(specs: dict, spot_last: pd.Series, rates_last: pd.Series) -> dict:
    """
    Turn MT5 swap_long/swap_short into annual % of notional and back out the
    broker markup. Interbank: long ~ +d, short ~ -d (d = base minus quote rate),
    so markup per side ~ -(long + short) / 2 regardless of what the true d is.
    """
    out = {}
    for c, (sym, usd_base) in PAIRS.items():
        s = next((v for k, v in specs.items() if k.startswith(sym)), None)
        if not s:
            continue
        px = 1.0 / spot_last[c] if usd_base else spot_last[c]
        mode = s.get("swap_mode")
        if mode == 1:          # points per lot per day
            f = s["point"] / px * 365.0
            lg, sh = s["swap_long"] * f, s["swap_short"] * f
        elif mode in (5, 6):   # annual interest %
            lg, sh = s["swap_long"] / 100.0, s["swap_short"] / 100.0
        else:
            out[c] = {"symbol": sym, "note": f"swap_mode {mode} not converted"}
            continue
        d = rates_last[c] - rates_last["USD"]
        model_long = -d if usd_base else d   # long the *pair*
        out[c] = {
            "symbol": sym, "long_ann": lg, "short_ann": sh,
            "broker_implied_diff": (lg - sh) / 2.0,
            "model_diff_long_pair": model_long,
            "markup_per_side": -(lg + sh) / 2.0,
        }
    return out


def _gross(w_me, ret) -> float:
    """Average sum|notional| / equity after portfolio vol scaling (drives swap cost)."""
    w = w_me.reindex(ret.index).ffill().fillna(0.0).shift(1).fillna(0.0)
    g0 = (w * ret).sum(axis=1)
    pv = g0.ewm(com=bt.VOL_COM, min_periods=120).std().shift(1) * np.sqrt(bt.ANN)
    k = (bt.PORT_VOL / pv).clip(upper=4.0)
    return float((w.abs().sum(axis=1) * k).loc["2000":].mean())


def _rate_variants(rates: pd.DataFrame) -> dict:
    """Stale (1 month late) and noisy (+/-0.5% per currency-year) versions of the table."""
    rng = np.random.default_rng(5)
    out = {"as_listed": rates, "1_month_stale": rates.shift(21).bfill()}
    for i in range(3):
        yrs = rates.index.year
        noise = pd.DataFrame({c: pd.Series(rng.normal(0, 0.005, yrs.nunique()),
                                           index=sorted(set(yrs))).reindex(yrs).values
                              for c in rates.columns}, index=rates.index)
        out[f"noise_0.5pct_seed{i}"] = rates + noise
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mt5", help="folder written by export_mt5.py")
    ap.add_argument("--suffix", default="", help="broker symbol suffix, e.g. .r")
    ap.add_argument("--null", type=int, default=400, help="null shifts")
    ap.add_argument("--markup", type=float, default=None,
                    help="swap markup per side, annual fraction (default: measured from "
                         "broker specs if --mt5, else 0.01)")
    ap.add_argument("--out", default="reports/carry_tsmom_results.json")
    a = ap.parse_args()

    spot = load_mt5(a.mt5, a.suffix) if a.mt5 else load_h10()
    rates = policy_rates(spot.index)
    ret = bt.excess_returns(spot, rates)
    hs = half_spread_frac(spot)
    W = bt.raw_weights(ret, rates)

    swaps = None
    if a.mt5:
        specs = load_broker_specs(a.mt5)
        if specs:
            swaps = broker_swap_summary(specs, spot.iloc[-1], rates.iloc[-1])
    mk = a.markup
    if mk is None:
        meas = [v["markup_per_side"] for v in (swaps or {}).values() if "markup_per_side" in v]
        mk = float(np.median(meas)) if meas else 0.01
    base = bt.Costs(swap_markup=mk)
    scen = {
        f"base (1x spread, {mk:.2%}/yr swap markup)": base,
        "2x spread": bt.Costs(spread_mult=2.0, swap_markup=mk),
        "1 day late": bt.Costs(delay=2, swap_markup=mk),
        "2x spread + late + 2x markup": bt.Costs(spread_mult=2.0, delay=2, swap_markup=2 * mk),
        "no costs (interbank)": bt.Costs(spread_mult=0.0, swap_markup=0.0),
    }

    res = {"data": "MT5 " + a.mt5 if a.mt5 else "Fed H.10 noon mid",
           "sample": [str(spot.index[0].date()), str(spot.index[-1].date())],
           "rules": {}, "stress": {}, "null": {}, "prop": {}}

    series = {}
    for k, w in W.items():
        r = bt.run(w, ret, hs, base)
        series[k] = r
        res["rules"][k] = bt.by_period(r, PERIODS)
    for name, c in scen.items():
        res["stress"][name] = {k: bt.stats(bt.run(W[k], ret, hs, c)) for k in PRIMARY}

    # --- how much broker swap markup can the edge survive?
    res["markup_sensitivity"] = {
        f"{m * 100:.2f}%": {k: bt.stats(bt.run(W[k], ret, hs, bt.Costs(swap_markup=m)))["sharpe"]
                            for k in PRIMARY}
        for m in (0.0, 0.0025, 0.005, 0.0075, 0.01, 0.015)}
    res["combo_avg_gross_leverage_at_10pct_vol"] = _gross(W["COMBO"], ret)

    # --- the rate table is hand-made: does carry survive if it is stale or noisy?
    rob = {}
    for name, rr in _rate_variants(rates).items():
        Wv = bt.raw_weights(ret, rr)
        rob[name] = bt.stats(bt.run(Wv["CARRY_XS3"], ret, hs, base))["sharpe"]
    res["carry_rate_table_robustness"] = rob

    # --- null / multiple testing on the whole family
    per, mx = bt.null_max_sharpe(W, ret, hs, base, n=a.null)
    for k in W:
        obs = res["rules"][k]["full"]["sharpe"]
        res["null"][k] = {
            "obs_sharpe": obs,
            "p_single": float((per[k] >= obs).mean()),
            "p_family_max": float((mx >= obs).mean()),
            "null_sharpe_mean": float(np.nanmean(per[k])),
            "null_sharpe_95": float(np.nanpercentile(per[k], 95)),
        }
    res["null"]["family_max_95"] = float(np.nanpercentile(mx, 95))

    # --- correlations (monthly) between primary rules
    m = pd.DataFrame({k: (1 + series[k]).resample("ME").prod() - 1 for k in PRIMARY})
    res["corr_monthly"] = m.loc["2000":].corr().round(2).to_dict()

    # --- per-year COMBO
    yr = (1 + series["COMBO"]).resample("YE").prod() - 1
    res["combo_by_year"] = {str(i.year): float(v) for i, v in yr.items()}

    # --- prop challenge on post-publication COMBO returns
    post = series["COMBO"].loc["2013":]
    res["prop"]["assumptions"] = {"profit_target": 0.08, "max_loss_static": 0.05,
                                  "daily_limit": 0.03, "horizon_days": 504,
                                  "zero_edge_baseline": bt.zero_edge_pass_prob()}
    res["prop"]["runs"] = [bt.prop_mc(post, v) for v in (0.04, 0.06, 0.08, 0.10, 0.15, 0.20)]

    # --- current book (what it would hold today)
    last = {k: W[k].iloc[-1].round(3).to_dict() for k in PRIMARY}
    res["current_signal_month_end"] = {"date": str(W["COMBO"].index[-1].date()), **last}
    diff_now = (rates[CURRENCIES].iloc[-1] - rates["USD"].iloc[-1]).round(4)
    res["rate_diff_vs_usd_now"] = diff_now.to_dict()

    res["swap_markup_used"] = mk
    if swaps:
        res["broker_swaps"] = swaps

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1, default=float)
    series_out = os.path.splitext(a.out)[0] + "_daily.csv"
    pd.DataFrame(series).to_csv(series_out, float_format="%.6g")
    _print(res)


def _pct(x):
    return "   n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:6.1f}%"


def _print(res):
    print(f"\nData: {res['data']}  {res['sample'][0]} -> {res['sample'][1]}\n")
    print(f"{'rule':<11}" + "".join(f"{p:>22}" for p in PERIODS))
    for k, per in res["rules"].items():
        cells = [f"SR {v.get('sharpe', np.nan):+.2f} t {v.get('t_nw', np.nan):+.1f}" for v in per.values()]
        print(f"{k:<11}" + "".join(f"{c:>22}" for c in cells))
    print("\nNull (circular shift, family of 5):")
    for k, v in res["null"].items():
        if isinstance(v, dict):
            print(f"  {k:<11} SR {v['obs_sharpe']:+.2f}  p_single {v['p_single']:.3f}  "
                  f"p_family {v['p_family_max']:.3f}  (null mean {v['null_sharpe_mean']:+.2f})")
    print(f"  family-max null 95th pct SR = {res['null']['family_max_95']:+.2f}")
    print("\nStress (full sample):")
    for s, d in res["stress"].items():
        print(f"  {s:<36}" + "  ".join(f"{k} SR {v['sharpe']:+.2f}" for k, v in d.items()))
    print("\nSwap-markup sensitivity (full-sample Sharpe):")
    for m, d in res["markup_sensitivity"].items():
        print(f"  markup {m:>6}/yr per side: " + "  ".join(f"{k} {v:+.2f}" for k, v in d.items()))
    print(f"  COMBO avg gross leverage at 10% vol: {res['combo_avg_gross_leverage_at_10pct_vol']:.2f}x")
    print("\nCarry vs rate-table errors (full-sample Sharpe):",
          ", ".join(f"{k} {v:+.2f}" for k, v in res["carry_rate_table_robustness"].items()))
    print("\nProp challenge MC (COMBO 2013+, +8% target / -5% static / 3% daily):")
    print(f"  zero-edge baseline pass prob = {res['prop']['assumptions']['zero_edge_baseline']:.2f}")
    for r in res["prop"]["runs"]:
        print(f"  vol {r['vol']:.0%}: pass<=60d {r['p_pass_60d']:.2f}  pass<=252d {r['p_pass_252d']:.2f}"
              f"  pass<=2y {r['p_pass_504d']:.2f}  fail {r['p_fail']:.2f}  "
              f"undecided {r['p_undecided']:.2f}  median days {r['median_days_to_pass']:.0f}")


if __name__ == "__main__":
    main()
