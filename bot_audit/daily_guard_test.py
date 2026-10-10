"""Account-level daily-loss guard for NBRO + EMBER gold together: after the day's CLOSED loss (both bots, UTC day)
reaches the guard, no new entries that day. Trades are skipped from the real trade lists, then the Atlas replay is re-run.
(Approximation: the live bots also count open losses; this uses closed ones.)"""
import sys
import numpy as np
import pandas as pd
from bot_audit.combo_atlas import nbro_book, ember_marks, combine
from bot_audit import ember_atlas as E

S = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
nb = pd.read_csv(f"{S}/realdata/nbro_trades.csv", parse_dates=["entry_ts", "exit_ts"])
em = pd.read_csv(f"{S}/ember_XAUUSD_swap.csv", parse_dates=["entry_time", "exit_time"])
nb["e"] = nb.entry_ts.dt.tz_convert("UTC").dt.tz_localize(None); nb["x"] = nb.exit_ts.dt.tz_convert("UTC").dt.tz_localize(None)
em["e"] = em.entry_time - pd.Timedelta(hours=3); em["x"] = em.exit_time - pd.Timedelta(hours=3)   # server ~ UTC+3


def filtered(guard, risk):
    ev = pd.concat([pd.DataFrame({"src": "n", "i": nb.index, "e": nb.e, "x": nb.x, "pct": nb.ret * 100 * risk}),
                    pd.DataFrame({"src": "e", "i": em.index, "e": em.e, "x": em.x, "pct": em.R * risk})]).sort_values("e")
    keep_n, keep_e, closed = [], [], []
    for r in ev.itertuples():
        day = r.e.normalize()
        loss = -sum(p for (xt, p) in closed if xt.normalize() == day and xt <= r.e)
        if guard is None or loss < guard:
            (keep_n if r.src == "n" else keep_e).append(r.i)
            closed.append((r.x, r.pct))
    nb.loc[keep_n].drop(columns=["e", "x"]).to_csv(f"{S}/nb_g.csv", index=False)
    em.loc[keep_e].drop(columns=["e", "x"]).to_csv(f"{S}/em_g.csv", index=False)
    return len(nb) - len(keep_n) + len(em) - len(keep_e)


for guard, risk in ((None, 1.0), (3.0, 1.0), (2.0, 1.0), (1.5, 1.0), (3.0, 0.75)):
    skipped = filtered(guard, risk)
    book = combine(nbro_book(f"{S}/nb_g.csv"), risk, [(ember_marks(f"{S}/gold/unz/XAUUSD_M5.csv", f"{S}/em_g.csv", 0.45), risk)])
    starts = range(0, len(book) - 300, 5)
    res = [E.simulate(book, s, 1.0, 1.0) for s in starts]
    d = np.array([x["ev_days"] if x["passed"] else 9999 for x in res]); br = np.mean([x.get("breach", False) for x in res])
    worst = (book.low).min()
    print(f"guard {str(guard)+'%' if guard else 'none':<5} risk {risk}%: skipped {skipped:3d} trades | 1mo {np.mean(d<=21):.0%} 2mo {np.mean(d<=42):.0%} "
          f"3mo {np.mean(d<=63):.0%} 1yr {np.mean(d<=252):.0%} breach {br:.0%} | worst day (intraday low) {worst:.2f}%", flush=True)
