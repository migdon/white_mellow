"""
SNR — "simplified" S/R rejection bot for MT5 (the strategy from the trading-class video), 30-minute bars, gold by default.

WARNING: tested 2018-2026 (reports/snr_rejection.md) this rule LOST money: gold 29 trades/yr, 34% winners, -0.24R a trade
(-6.9R a year), and it lost on NAS100 and EURUSD too. It is here because you asked to try it yourself.
Run it on a DEMO account (or with a very small --risk), not on an Atlas evaluation or funded account.

The rule (the same one the backtest bot_audit/snr_rejection.py uses):
  1. Rejection area: a swing low / high (3 bars each side) from the last 5 days, +/- --zone x ATR14.
  2. Leg: >= --leg consecutive clean momentum candles (body >= 50% of the range, each close beyond the previous close).
  3. The next 30m candle closes the other way (the reversal candle) and the leg's extreme is inside a rejection area
     that existed before the leg started.
  4. A stop order at the reversal candle's high (buy) / low (sell), valid only during the next 30m candle.
  5. Stop at the leg's extreme. Target 2R with the trend (close vs EMA200 on 30m), 1R against it.
  6. One trade at a time, max --max-trades a day, after a loss no more trades that day (server day). Closed after 24h.

    python snr_app.py                       # XAUUSD, 0.5% risk per trade
    python snr_app.py --risk 0.25 --symbols XAUUSD NAS100
    python snr_app.py --london-ny           # only during London + New York (server 10:00-23:00)
    python snr_app.py --dry-run             # check the last completed bar, place nothing
Magic number 991100 (its own; it never touches other bots' orders). Log: snr_log.txt next to this file.
"""

import argparse
import math
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

MAGIC = 991100
K = 3
NAMES = {"XAUUSD": ["XAUUSD", "GOLD", "XAUUSD.r"], "NAS100": ["NAS100", "US100", "USTEC", "NAS100.r"],
         "EURUSD": ["EURUSD", "EURUSD.r"]}
HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ the rule (pure, testable)
def indicators(O, H, L, C):
    pc = np.r_[C[0], C[:-1]]
    atr = pd.Series(np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))).rolling(14).mean().values
    ema = pd.Series(C).ewm(span=200, adjust=False).mean().values
    clean = np.abs(C - O) / np.maximum(H - L, 1e-12) >= 0.5
    bear, bull = (C < O) & clean & (C < pc), (C > O) & clean & (C > pc)
    run_bear, run_bull = np.zeros(len(C), int), np.zeros(len(C), int)
    for i in range(1, len(C)):
        run_bear[i] = run_bear[i - 1] + 1 if bear[i] else 0
        run_bull[i] = run_bull[i - 1] + 1 if bull[i] else 0
    return atr, ema, run_bear, run_bull


def setup(O, H, L, C, r, leg_min=3, zone=0.3, ind=None):
    """Bar r = the last COMPLETED 30m bar (the reversal candle). Returns (side, trigger, stop, target_R, aligned) or None."""
    atr, ema, run_bear, run_bull = ind if ind is not None else indicators(O, H, L, C)
    if r < K + 1 or not atr[r] > 0:
        return None
    for side in (1, -1):
        legn = run_bear[r - 1] if side == 1 else run_bull[r - 1]
        if legn < leg_min or not ((C[r] > O[r]) if side == 1 else (C[r] < O[r])):
            continue
        s = r - legn
        lo = max(K, r - 240)
        if side == 1:
            ext = L[s:r + 1].min()
            lv = [L[j] for j in range(lo, s - K) if L[j] == L[j - K:j + K + 1].min()]
        else:
            ext = H[s:r + 1].max()
            lv = [H[j] for j in range(lo, s - K) if H[j] == H[j - K:j + K + 1].max()]
        if not lv or min(abs(ext - x) for x in lv) > zone * atr[r]:
            continue
        aligned = bool((C[r] > ema[r]) if side == 1 else (C[r] < ema[r]))
        return side, float(H[r] if side == 1 else L[r]), float(ext), 2.0 if aligned else 1.0, aligned
    return None


# ------------------------------------------------------------------ MT5 plumbing
def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(HERE, "snr_log.txt"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def resolve(sym, suffix):
    for n in [sym + suffix] + NAMES.get(sym, []):
        if mt5.symbol_select(n, True):
            return n
    return None


def lots_for(name, side, entry, stop, money):
    info = mt5.symbol_info(name)
    per_lot = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY if side == 1 else mt5.ORDER_TYPE_SELL, name, 1.0, entry, stop)
    if not info or per_lot is None or per_lot >= 0:
        return 0.0
    step = info.volume_step or 0.01
    lots = math.floor(money / -per_lot / step + 1e-9) * step
    lots = min(lots, info.volume_max)
    return round(lots, 8) if lots >= info.volume_min else 0.0


def today_record(server_day_start):
    """(trades opened today, last closed trade today was a loss) for this bot, by server day."""
    deals = mt5.history_deals_get(server_day_start - timedelta(days=1), datetime.now() + timedelta(days=2)) or []
    opened, last_close, last_pnl = set(), None, 0.0
    pnl = {}
    for d in deals:
        if d.magic != MAGIC or datetime.fromtimestamp(d.time, timezone.utc).replace(tzinfo=None) < server_day_start:
            continue
        if d.entry == mt5.DEAL_ENTRY_IN:
            opened.add(d.position_id)
        elif d.entry == mt5.DEAL_ENTRY_OUT:
            pnl[d.position_id] = pnl.get(d.position_id, 0.0) + d.profit + d.commission + d.swap
            if last_close is None or d.time >= last_close:
                last_close, last_pnl = d.time, pnl[d.position_id]
    return len(opened), last_close is not None and last_pnl < 0


def filling(info):
    fm = getattr(info, "filling_mode", 0)
    return mt5.ORDER_FILLING_IOC if fm & 2 else (mt5.ORDER_FILLING_FOK if fm & 1 else mt5.ORDER_FILLING_RETURN)


def place(name, side, trig, stop, tp, vol):
    info = mt5.symbol_info(name)
    req = {"action": mt5.TRADE_ACTION_PENDING, "symbol": name, "volume": vol, "magic": MAGIC,
           "type": mt5.ORDER_TYPE_BUY_STOP if side == 1 else mt5.ORDER_TYPE_SELL_STOP,
           "price": round(trig, info.digits), "sl": round(stop, info.digits), "tp": round(tp, info.digits),
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling(info), "comment": "snr"}
    r = mt5.order_send(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE, getattr(r, "retcode", None)


def close_position(p):
    tick, info = mt5.symbol_info_tick(p.symbol), mt5.symbol_info(p.symbol)
    sell = p.type == mt5.POSITION_TYPE_BUY
    r = mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "position": p.ticket,
                        "type": mt5.ORDER_TYPE_SELL if sell else mt5.ORDER_TYPE_BUY, "price": tick.bid if sell else tick.ask,
                        "magic": MAGIC, "deviation": 50, "type_filling": filling(info), "comment": "snr 24h"})
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


# ------------------------------------------------------------------ main loop
def main():
    ap = argparse.ArgumentParser(description="S/R rejection bot (video strategy), 30m. Lost money in testing: use a demo.")
    ap.add_argument("--symbols", nargs="+", default=["XAUUSD"], choices=sorted(NAMES))
    ap.add_argument("--risk", type=float, default=0.5, help="%% of balance risked per trade")
    ap.add_argument("--leg", type=int, default=3, help="minimum momentum candles in the leg")
    ap.add_argument("--zone", type=float, default=0.3, help="rejection-area half width in ATR14(30m)")
    ap.add_argument("--max-trades", type=int, default=3, help="max trades per server day")
    ap.add_argument("--daily-guard", type=float, default=2.0, help="no new orders once today's loss reaches this %%")
    ap.add_argument("--london-ny", action="store_true",
                    help="only place orders 10:00-23:00 server time (London+NY): least bad filter in the test, still negative")
    ap.add_argument("--mt5-path", default=None)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if mt5 is None:
        raise SystemExit("pip install MetaTrader5")
    if not (mt5.initialize(path=a.mt5_path) if a.mt5_path else mt5.initialize()):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    names = {}
    for s in a.symbols:
        n = resolve(s, a.suffix)
        if n:
            names[s] = n
            log(f"{s}: trading broker symbol {n}")
        else:
            log(f"{s}: not found at this broker - skipped")
    log(f"SNR started: risk {a.risk}% per trade, leg >= {a.leg}, zone {a.zone} ATR, max {a.max_trades}/day, "
        f"stop after a loss, daily guard {a.daily_guard}%, dry-run {a.dry_run}")
    checked = {}
    day_key, day_start_eq = None, None
    while True:
        try:
            acc = mt5.account_info()
            for s, n in names.items():
                rates = mt5.copy_rates_from_pos(n, mt5.TIMEFRAME_M30, 0, 1500)
                tick = mt5.symbol_info_tick(n)
                if rates is None or len(rates) < 600 or not tick:
                    continue
                forming = int(rates[-1]["time"])                    # server-time epoch of the forming bar
                server_now = datetime.fromtimestamp(tick.time, timezone.utc).replace(tzinfo=None)
                sday = server_now.replace(hour=0, minute=0, second=0, microsecond=0)
                if day_key != sday:
                    day_key, day_start_eq = sday, acc.equity
                orders = [o for o in (mt5.orders_get(symbol=n) or []) if o.magic == MAGIC]
                positions = [p for p in (mt5.positions_get(symbol=n) or []) if p.magic == MAGIC]
                # a pending order lives only during the bar after its reversal candle
                for o in orders:
                    if forming > int(o.time_setup) // 1800 * 1800:       # the bar it was placed in has ended
                        if not a.dry_run:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                        log(f"{s}: order {o.ticket} not triggered within its 30m bar -> cancelled")
                for p in positions:
                    if tick.time - p.time >= 24 * 3600:
                        log(f"{s}: position {p.ticket} open 24h -> close {'ok' if a.dry_run or close_position(p) else 'FAILED'}")
                if checked.get(s) == forming:
                    continue
                checked[s] = forming
                if time.time() - tick.time > 600 and not a.dry_run:
                    continue                                       # market closed / stale
                b = pd.DataFrame(rates[:-1])                       # completed bars only
                O, H, L, C = (b[c].values.astype(float) for c in ("open", "high", "low", "close"))
                st = setup(O, H, L, C, len(C) - 1, a.leg, a.zone)
                if not st:
                    if a.dry_run:
                        log(f"{s}: no setup on the last completed 30m bar")
                    continue
                side, trig, stop, tgt, aligned = st
                n_today, lost_today = today_record(sday)
                day_loss = (day_start_eq - acc.equity) / acc.balance * 100
                why = ("outside London/NY hours" if a.london_ny and not 10 <= server_now.hour < 23 else
                       "a trade/order is already open" if orders or positions else
                       "already lost today" if lost_today else
                       f"{n_today} trades today" if n_today >= a.max_trades else
                       f"daily loss {day_loss:.2f}%" if day_loss >= a.daily_guard else None)
                spread = tick.ask - tick.bid
                entry = trig + (spread if side == 1 else 0.0)
                risk = (entry - stop) if side == 1 else (stop - entry)
                if risk <= spread:
                    why = why or "stop too close"
                tp = entry + side * tgt * risk
                desc = (f"{'BUY' if side == 1 else 'SELL'} STOP {trig:.5g} stop {stop:.5g} target {tp:.5g} "
                        f"({tgt:g}R, {'with' if aligned else 'against'} trend)")
                if why:
                    log(f"{s}: setup {desc} skipped: {why}")
                    continue
                vol = lots_for(n, side, entry, stop, acc.balance * a.risk / 100)
                if vol <= 0:
                    log(f"{s}: setup {desc} skipped: minimum lot is more than {a.risk}% risk")
                    continue
                if (side == 1 and tick.ask >= trig) or (side == -1 and tick.bid <= trig):
                    log(f"{s}: setup {desc} skipped: price already past the trigger")
                    continue
                ok, rc = (True, None) if a.dry_run else place(n, side, trig, stop, tp, vol)
                log(f"{s}: {desc} {vol} lots {'(dry-run)' if a.dry_run else ('placed' if ok else f'FAILED rc {rc}')}")
            if a.dry_run:
                log("dry-run: one pass done")
                break
        except Exception as e:                                     # the loop must not die
            log(f"loop error: {type(e).__name__}: {e}")
        time.sleep(5)
    mt5.shutdown()


if __name__ == "__main__":
    main()
