"""
RSI2 — Connors RSI(2) pullback bot for MT5 (SPX500 + NAS100, long only, daily bars).

Rule (the one tested in bot_audit/classics.py, 2012-2026: SPX500 t 2.67, 73% winners; NAS100 t 1.63; pooled t 2.37 PASS):
  once per day, on COMPLETED daily bars (the broker's server day):
    flat  and close > SMA(200) and RSI(2) < 10   -> BUY at market at the start of the new day
    long  and close > SMA(5)                     -> SELL (close) at market at the start of the new day
  plus a broker-side emergency stop (not in the classic rule / the backtest): --stop-pct below entry.

Sizing: each position is --notional x equity (0.5 = a position worth half the account). The backtest's worst drawdown was
-17.6% at 1x (SPX500), so 0.5x per index is about -9%: keep it at 0.25-0.5 on a prop account (10% trailing drawdown).
Guards: no new entry once today's account loss reaches --daily-guard %, or the account is within 1% of --max-dd (trailing).

    python rsi2_app.py                                  # defaults: SPX500 + NAS100, 0.5x each, stop 4%
    python rsi2_app.py --notional 0.25 --label Atlas1   # smaller
    python rsi2_app.py --dry-run                        # print today's signals, place nothing
Options: --mt5-path, --symbols, --suffix. Magic number 990900 (its own; never touches other bots' orders).
Not yet run live: watch the first trades and compare with MT5's History.
"""

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

MAGIC = 990900
NAMES = {"SPX500": ["SPX500", "US500", "SP500", "SP500.r", "SPX500.r"], "NAS100": ["NAS100", "US100", "USTEC", "NAS100.r"]}
HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ the rule (pure functions, testable)
def rsi2(closes):
    c = np.asarray(closes, dtype=float)
    up = np.zeros(len(c)); dn = np.zeros(len(c))
    d = np.diff(c)
    a = 1 / 2.0
    for i in range(1, len(c)):          # Wilder-style EWM, alpha = 1/2 (same as pandas ewm(alpha=1/2, adjust=False))
        u, v = max(d[i - 1], 0.0), max(-d[i - 1], 0.0)
        up[i] = a * u + (1 - a) * up[i - 1] if i > 1 else u * a
        dn[i] = a * v + (1 - a) * dn[i - 1] if i > 1 else v * a
    rs = up[-1] / dn[-1] if dn[-1] > 0 else np.inf
    return 100 - 100 / (1 + rs)


def signal(closes, in_position):
    """closes = COMPLETED daily closes, oldest first. Returns 'BUY', 'SELL' or None."""
    if len(closes) < 205:
        return None
    c = np.asarray(closes, dtype=float)
    if in_position:
        return "SELL" if c[-1] > c[-5:].mean() else None
    if c[-1] > c[-200:].mean() and rsi2(c) < 10:
        return "BUY"
    return None


# ------------------------------------------------------------------ MT5 plumbing
def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(HERE, "rsi2_log.txt"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def resolve(sym, suffix):
    for n in [sym + suffix] + NAMES.get(sym, []):
        if mt5.symbol_select(n, True):
            return n
    return None


def my_position(name):
    return next((p for p in (mt5.positions_get(symbol=name) or []) if p.magic == MAGIC), None)


def lots_for(name, equity, notional):
    info, tick = mt5.symbol_info(name), mt5.symbol_info_tick(name)
    if not info or not tick:
        return 0.0
    value_per_lot = tick.ask * info.trade_contract_size
    step = info.volume_step or 0.01
    lots = math.floor(equity * notional / value_per_lot / step + 1e-9) * step
    return round(lots, 8) if lots >= info.volume_min else 0.0


def send(name, side, volume, position=None, sl=0.0):
    tick = mt5.symbol_info_tick(name)
    info = mt5.symbol_info(name)
    fm = getattr(info, "filling_mode", 0)
    filling = mt5.ORDER_FILLING_IOC if fm & 2 else (mt5.ORDER_FILLING_FOK if fm & 1 else mt5.ORDER_FILLING_RETURN)
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": name, "volume": volume, "magic": MAGIC, "deviation": 50,
           "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
           "price": tick.ask if side == "BUY" else tick.bid, "type_filling": filling, "comment": "rsi2"}
    if position:
        req["position"] = position
    if sl:
        req["sl"] = round(sl, info.digits)
    r = mt5.order_send(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE, getattr(r, "retcode", None)


# ------------------------------------------------------------------ main loop
def main():
    ap = argparse.ArgumentParser(description="Connors RSI(2) bot, SPX500 + NAS100, long only")
    ap.add_argument("--symbols", nargs="+", default=["SPX500", "NAS100"], choices=sorted(NAMES))
    ap.add_argument("--notional", type=float, default=0.5, help="position size per index as a fraction of equity")
    ap.add_argument("--stop-pct", type=float, default=4.0, help="emergency stop, %% below entry")
    ap.add_argument("--daily-guard", type=float, default=3.0, help="no new entries once today's loss reaches this %%")
    ap.add_argument("--max-dd", type=float, default=10.0, help="trailing max drawdown %% of the start balance (entries stop 1%% before)")
    ap.add_argument("--mt5-path", default=None)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if mt5 is None:
        raise SystemExit("pip install MetaTrader5")
    if not (mt5.initialize(path=a.mt5_path) if a.mt5_path else mt5.initialize()):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    state_path = os.path.join(HERE, f"rsi2_state_{a.label or 'default'}.json")
    try:
        state = json.load(open(state_path))
    except (OSError, ValueError):
        state = {}
    acc = mt5.account_info()
    state.setdefault("start_balance", acc.balance)
    state.setdefault("hwm", acc.equity)
    names = {}
    for s in a.symbols:
        n = resolve(s, a.suffix)
        if not n:
            log(f"{s}: not found at this broker - skipped")
        else:
            names[s] = n
            log(f"{s}: trading broker symbol {n}")
    log(f"RSI2 started{' [' + a.label + ']' if a.label else ''}: notional {a.notional}x per index, stop {a.stop_pct}%, "
        f"daily guard {a.daily_guard}%, max dd {a.max_dd}% trailing, dry-run {a.dry_run}")
    while True:
        try:
            acc = mt5.account_info()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if state.get("day") != today:
                state.update(day=today, day_start=acc.equity)
            state["hwm"] = max(state["hwm"], acc.equity)
            day_loss = (state["day_start"] - acc.equity) / state["start_balance"] * 100
            dd_room = acc.equity - (state["hwm"] - state["start_balance"] * a.max_dd / 100)
            entries_blocked = day_loss >= a.daily_guard or dd_room <= state["start_balance"] * 0.01
            for s, n in names.items():
                rates = mt5.copy_rates_from_pos(n, mt5.TIMEFRAME_D1, 0, 260)
                tick = mt5.symbol_info_tick(n)
                if rates is None or len(rates) < 206 or not tick:
                    continue
                bar_day = str(datetime.fromtimestamp(int(rates[-1]["time"]), timezone.utc).date())   # the forming (new) day
                if state.get(f"done_{s}") == bar_day:
                    continue
                if abs(tick.time - int(rates[-1]["time"])) > 4 * 86400 or time.time() - tick.time > 600:
                    continue                    # market closed / stale quotes: try again later today
                closes = [float(r["close"]) for r in rates[:-1]]      # COMPLETED days only
                pos = my_position(n)
                sig = signal(closes, pos is not None)
                if sig == "SELL" and pos:
                    ok, rc = (True, None) if a.dry_run else send(n, "SELL", pos.volume, position=pos.ticket)
                    log(f"{s}: close > SMA5 -> EXIT {pos.volume} lots {'(dry-run)' if a.dry_run else ('ok' if ok else f'FAILED rc {rc}')}")
                    if not ok:
                        continue
                elif sig == "BUY" and not pos:
                    if entries_blocked:
                        log(f"{s}: BUY signal skipped (daily loss {day_loss:.2f}% / drawdown guard)")
                    else:
                        vol = lots_for(n, acc.equity, a.notional)
                        if vol <= 0:
                            log(f"{s}: BUY signal but the minimum lot is larger than {a.notional}x equity - skipped")
                        else:
                            sl = tick.ask * (1 - a.stop_pct / 100)
                            ok, rc = (True, None) if a.dry_run else send(n, "BUY", vol, sl=sl)
                            log(f"{s}: close > SMA200, RSI(2) < 10 -> BUY {vol} lots, stop {sl:.2f} "
                                f"{'(dry-run)' if a.dry_run else ('ok' if ok else f'FAILED rc {rc}')}")
                            if not ok:
                                continue
                state[f"done_{s}"] = bar_day
            json.dump(state, open(state_path, "w"))
            if a.dry_run:
                log("dry-run: one pass done")
                break
        except Exception as e:                      # the loop must not die
            log(f"loop error: {type(e).__name__}: {e}")
        time.sleep(30)
    mt5.shutdown()


if __name__ == "__main__":
    main()
