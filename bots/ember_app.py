"""
EMBER — Expansion-Move Breakout, Edge-tested, Risk-capped
=============================================================
EMBER-24 (2026-10-09): USDJPY REMOVED as well. Default market: XAUUSD only. BTCUSD stays an opt-in candidate (--symbols XAUUSD BTCUSD).
  BTCUSD re-test (Vantage M5 2018-2026, Atlas spread $67, swap -15%/yr): 680 trades, +0.037R a trade, z 1.4; first half +0.063R,
  second half +0.011R. Atlas replay gold + BTCUSD was WORSE than gold alone (evaluation at 1.0%: pass 0.71 with 16% breached,
  against 0.78 / 0% for gold alone; funded at 0.75%: 83% alive, ~$730/yr, against 100% / ~$945/yr), so BTCUSD does not start by default.
  Gold alone, Atlas Access: evaluation 1.5% -> pass ~82%, ~4% breached, median ~69 trading days; funded 0.75% -> alive in every start
  date, ~0.8 payouts and ~$950 a year on $50k.
EMBER-23 (2026-10-09): JPN225 REMOVED. Markets: XAUUSD + USDJPY (default), BTCUSD as candidate (--symbols ... BTCUSD).
  Independent re-test (bot_audit/ember_bt.py, Vantage M5, Atlas-level spreads: gold $0.45, USDJPY 0.5 pip, USDJPY exit at 01:05):
    XAUUSD 2018-09 -> 2026-10: 579 trades, win 54%, +0.052R a trade, z 2.8; both halves positive; 2019-2020 (before the 2021+ data
           EMBER was built on) +0.10R / +0.07R.
    USDJPY 2012 -> 2026: 1,063 trades, +0.017R to +0.021R, z 1.1-1.3: weaker than the +0.048R in the notes below. It mainly adds
           trading days and speed in the evaluation, not much edge.
  Atlas Access replay (bot_audit/ember_atlas.py, gold + USDJPY, 2018-2026, positions held overnight, Protector modelled):
    evaluation at 1.5% per trade: pass ~88% of start dates, ~5% breached, median ~52 trading days (1.0%: ~82%, no breaches, ~74 days)
    funded at 0.75% per trade: alive after a year in every start date, Protector never reached, ~0.7 payouts a year
           (~$1,000/yr on $50k). The "3 days >= +0.5% closed" payout rule is the bottleneck, not the drawdown.
  Presets changed accordingly: --preset evaluation = 1.5%, --preset funded = 0.75% (cap 1.5%, shield 1.7%).
  The history below is kept as it was written.

Daily volatility-breakout bot for XAUUSD (gold) and USDJPY, TOGETHER in one bot like ORB's pairs (--symbols picks a subset), built on Toby Crabel's own published Opening Range
Breakout baseline ("A Century of Evidence", 2025): stretch = 0.8 x the 10-day average true range,
from the day's OPEN. Whichever side (up or down) price touches first that day becomes the position,
entered at that level. A hard stop at 2x the same ATR caps the risk (Crabel's own baseline runs with
no stop at all; this project added one after finding the un-stopped version's worst single trade was
-9.94% of account on gold — far too large for a prop-firm drawdown limit to survive). Exit at the
close of the day AFTER entry, or the stop, whichever comes first. ONE position at a time.

The name: an ember glows quietly through the night, unseen, until it flares — the position is placed
at the day's volatility stretch and then held OVERNIGHT, unlike this project's other two bots
(orb_app.py / bro_app.py, which trade intraday only, multiple FX pairs, never held overnight).

VALIDATED NUMBERS (corrected — read this before trusting any number from this project's own earlier
chat log about this strategy): three problems were found AND FIXED during this bot's development, all
disclosed here because each changed the numbers materially:
  1. ATR lookahead: an early backtest computed each day's ATR using a window that INCLUDED that same
     day's own high-low range — using information from later in the day to set that day's own entry
     level at the open. Fixed by shifting the ATR by one day.
  2. Overlapping trades: after fixing (1), the backtest still evaluated every day's signal in
     isolation, as if each day started with fresh capital — which let trades "overlap" (a new entry
     while yesterday's was still open), something one real account literally cannot do. Fixed by
     making the backtest track ONE open position at a time, exactly like this live bot must.
  3. Wrong day boundary: the gold history used for testing is in UTC, but a day on the broker's MT5 server
     runs from 17:00 New York to 17:00 New York (server midnight, all year round), and that is the day this
     bot trades. The first numbers cut days at UTC midnight — a different day. Everything below was re-run
     with days cut at server midnight (UTC converted to New York time + 7h, the broker's convention).

With all three fixes in place, gold, Jan 2021 - Sep 2026 (about 5.7 years), spread 0.30 deducted:
  423 trades (~75 a year) | win 52.5% | avg +0.043R | total +18.24R | spread DOUBLED +16.11R | worst trade -1.01R
  positive in 5 of 6 calendar years (2021 +4.0, 2022 -0.3, 2023 +1.8, 2024 +3.8, 2025 +5.3, 2026 +3.7)
  first half of the trades +5.5R, second half +12.8R (both positive, but weighted toward the later years).
Parameter sensitivity (15 variations: stretch 0.6-1.1, ATR lookback 6-20 days, stop 1.5-4x): every one was
positive (+9.5R to +23.6R) with 4-6 of 6 years positive, and the published 0.8/10/2x point sits mid-pack rather
than at a peak — which is what you want to see if the result is not an accident of one chosen number. (Those
15 runs used exact prices; rounding orders to the broker's 2 decimals, as the live bot must, moves a total by <0.1R.)
A session-time filter (trade only London+NY hours) was tested on the earlier UTC-day version of the data and
made results WORSE (the quiet overnight hours contributed more edge per trade, not less); it was not re-tested
on server-day data. This bot does not restrict by time of day.

CANDIDATE MARKETS BTCUSD AND JPN225 (EMBER-19). Screening EMBER's rule on all 43 Atlas instruments (this broker's M30 history, no costs) found NO market passing the strict bar (z >= 3.2), and five "weak" ones. The older years
  of those five, which the screening had never seen, were then tested with a rule fixed beforehand (average R above 0, z >= 2.33, 150 trades or more):
    BTCUSD  6.3 yrs +0.067R (z 2.6)  -> older 3.1 yrs +0.141R (z 3.0, 246 trades, long +0.17 / short +0.12)   CONFIRMED      ETHUSD  +0.073R (z 2.9) -> older +0.125R (z 2.6)   CONFIRMED (moves with BTC: not added)
    JPN225  3.8 yrs +0.067R (z 2.2)  -> older 10.5 yrs +0.053R (z 2.55, 729 trades)                          CONFIRMED      XAUUSD +0.025R (z 1.2) inconclusive      BRENT +0.003R no edge (dropped)
  The same rule, unchanged. They are CANDIDATES: they are NOT started by a plain "py ember_app.py" (that still runs gold and USDJPY); add them on purpose with   --symbols XAUUSD USDJPY BTCUSD JPN225
  and each start-up writes a CANDIDATE notice in the Activity Log. Run them on demo first. Costs measured at Atlas (7 days of ticks and the symbol specifications): BTCUSD spread $67 all day (no rollover
  widening) + overnight swap -15% a year = about 0.026R a trade; JPN225 spread 9 points + swap -3% long / -1.5% short a year = about 0.006R; closed 00:00-00:55 server time, reopens 01:00. No exit delay needed for either.
  Crypto leverage at Atlas is reported (by a third-party review, to be confirmed) as 1:2 in the evaluation and 1:1 funded; at 1% risk this bot's position is only about 12-15% of the account, so it is not a constraint.
  Also measured at Atlas: USDJPY spread is 0.3-0.5 pips in the day (not 1.7 as at the other broker) and wide through the whole of server hour 00 exactly as before (normal again from 01:05), so the 65-minute exit
  delay is right there too; gold is $0.41-0.48 (0.47 from 01:00 to 08:00). Swaps (counted): USDJPY short -19 points a night (about -0.014R a trade), gold long -66 points; both small.
  Estimate of the evaluation time with them, edges halved and synthetic streams (so NOT a promise): $50K at 1.0% per market, median 2.2-2.6 months instead of 6.3 (gold + USDJPY alone, recent-years edge).
  The decimals of every symbol are read from the broker at start-up (a wrong count makes the broker reject pending orders). Checked: the real bot against the reference backtest on the broker's own data turned into
  5-minute bars: BTCUSD 370 trades (+24.78R) and JPN225 265 trades (+16.98R), identical trade for trade.

FOREIGN EMBER ORDERS (EMBER-22): another EMBER copy can share the account (EMBER-06 uses magic 990711 and its own comments 'ember06_*'; it filters everything by its own magic, as does this bot, so the two never touch each
  other's orders). Every 10 minutes the bot looks at its active markets and, for any pending order or position whose comment starts with "ember" but whose magic number is not one of its own: a KNOWN sibling (EMBER-06)
  gets one quiet NOTE a day (the two copies add up their exposure on that market, and this copy's open-risk cap counts only its own trades); anything else gets a WARNING once an hour per set of tickets (probably left by an
  older version: if one fills, nobody closes it two days later). It never deletes or changes them. Orders not marked EMBER (the ORB bot's, your own) are never mentioned.
  The dashboard card "TODAY'S LOSS" is now "TODAY'S P&L": +0.28% in green for a profit, -0.50% for a loss (amber near the daily guard, red beyond it), with the dollars underneath.

BROKER NAMES (EMBER-21): the same market has another name at some brokers (Vantage calls the Nikkei JPN225ft, Atlas calls it JPN225). If the exact name is missing the bot looks through
  BROKER_NAME_ALTERNATIVES at start-up, remembers the one it finds and says so in the Activity Log; the market keeps its own name (JPN225) everywhere else. --suffix still applies to the rest.

WAITING ORDERS THE BOT NO LONGER FINDS (EMBER-18): the bot remembers its two waiting orders by ticket, so an order deleted by hand in MT5 used to leave the bot believing it still existed
  and the day's trade was lost without a word. Now, if a waiting order is gone from the broker and nothing was filled, it clears the pair and puts the day's orders on again
  (and if a trigger level was reached meanwhile, that touch is not traded, no trade today). The open-risk figure and the open-risk cap now read the broker's real waiting orders, not only the
  bot's memory (orders placed by an older version have no lot size in the saved state, which showed 0.00%). The dashboard says "Orders waiting" only when orders really exist.
  The supported way to refresh the orders is still Pause -> Resume (or Stop -> Start for one market) on the dashboard.

ATLAS ACCESS — what was measured, and what the funded-stage settings are for (official rules: help.atlasfunded.com, reviewed 27 Sep 2026):
  Evaluation: +3% CLOSED balance, 10% trailing EQUITY drawdown (open profit raises the floor), 5% daily, no time limit, no minimum days, EAs and
  weekend holding allowed. Funded: no target, 6% trailing equity, 3% daily, and ATLAS PROTECTOR (funded only): an OPEN loss of 2% of the starting
  balance closes everything and cuts the profit split to 50% for good; a second time breaches the account. A payout needs 3 UTC days per cycle
  with net closed profit >= 0.5% of the starting balance, and the best day <= 40% of the cycle's profit.
  Measured on EMBER's real trades (gold + USDJPY, 50K, with the 5-minute path inside every trade): the evaluation at 1.0% per market passes 9% / 45% / 71%
  of the time within 30 / 90 / 180 days with 0.1% breaches; at 1.5%: 24% / 63% / 82%, but 4.5% breaches. Gold alone at 1% reached a 6.9% drawdown over
  5.7 years, so the funded stage needs about 0.5% per market. Holding 2-3 gold positions at once only multiplies the same risk (3 positions: 20.8%
  drawdown, worst day -6%); splitting one signal into three trades with different exits made no difference to the worst day or the open loss.
  The Access FUNDED payout rule is not met by EMBER: a typical winner is +0.4R (+0.4% at 1% risk) and all three payout conditions held in 0-1% of
  14-day cycles, even with more trades (up to 5% with overlapping positions, which also raises the open risk). The Pro programs (any closed trade counts
  as a day) fit EMBER better, but their evaluations take about a year at 1%.
  New, all OFF unless switched on: OPEN-RISK CAP (combined planned risk of everything open or waiting, all markets, as % of the base balance; a market's lot is
  cut to what the others leave, or skipped), PROTECTOR SHIELD (closes everything and stops new entries for the rest of the market day when the OPEN loss reaches
  this % of the base, a little before Atlas would), and PRESETS (Settings page, or --preset evaluation|funded, then --open-risk-cap / --protector-shield / --risk
  to override). The cap and the shield protect the account; they do not make the payout rule reachable, and they cannot stop a gap through a stop.

REAL SPREADS AND THE EXIT DELAY (measured on this broker with spread_check.py, 7 days of quote ticks; the first backtests assumed gold $0.30 and USDJPY 1.0 pip):
  GOLD: typical $0.22; at the broker midnight the market is CLOSED (no ticks) and reopens at 01:00 with $0.26. So gold is cheaper than assumed and its result is unchanged
  (+0.044R a trade; 423 trades in 5.7 years).
  USDJPY: typical 1.7 pips, but at the broker midnight (where a trade closes) the median is 8.0 pips (mean 11.4, 95th 18.5). Data are BID prices: a long pays the spread when it ENTERS,
  a SHORT pays it when it CLOSES, so the shorts paid the rollover spread. With that cost the USDJPY edge fell from +0.052R to +0.026R a trade (z 3.4 -> 1.7).
  FIX (exit_delay_min in SYMBOL_PROFILES): a USDJPY trade that is due to close waits until 65 minutes after the broker midnight (01:05). Its stop keeps protecting it, a dashboard Close or the
  Protector shield still acts at once, and the day's orders are placed after it has closed; if a trigger level was crossed meanwhile, that touch is not traded and there is no trade that day.
  The broker's 5-minute table (spread_rollover.py), USDJPY, median pips: 23:50 2.6 | 00:00-00:20 7.8-8.3 | 00:25-00:35 14.4-16.0 (the worst) | 00:40-00:55 ~8 | 01:00 2.0 | 01:05 on 1.70.
  Backtest with the wait simulated (the price drift of the wait included): 65 min +0.048R a trade, z 3.1, against +0.047R for closing at midnight if the spread were 1.7 pips there
  (it is not), and +0.026R (z 1.7) for closing at midnight at the real spread. The live bot matches the backtest on all 1,059 trades of 14 years (test_equivalence.py) and on gold and
  USDJPY run together (test_equivalence_multi.py). If your broker ever changes its rollover hours, run "py spread_rollover.py" again and adjust exit_delay_min.
  The Atlas evaluation estimates are essentially unchanged with the real costs and the delay (1.0% per market: 9% / 44% / 69% pass within 30 / 90 / 180 days, against 9% / 45% / 71%).

PORTED FROM HACVD (hacvd_app.py), each one tested before it went in (test_ported.py, 31 checks, and every check was shown to fail when the code was deliberately broken):
  - ACTIVITY LOG FILE: every line is also appended to ember_log_<port>.txt next to this file, so the history survives a restart or a cleared window; trimmed to its last
    20,000 lines past ~5 MB; a write failure never stops the bot.
  - DASHBOARD PASSWORD (py ember_app.py --set-password; empty = off): covers EVERY page and button (status, Close, Pause, Settings). HACVD's version stored an UNSALTED SHA-256 and
    compared it with ==; this one uses salted PBKDF2 (200,000 rounds), a constant-time comparison and a 60-second lock-out after 5 wrong tries from one address (the browser's own
    first request, which carries no password, does not count). One file covers every copy in the folder. With --host other than this machine the bot REFUSES to start
    without a password. HTTP Basic is not encrypted: fine on this machine, use an SSH tunnel or VPN across a network.
  - BROKER CLOCK NOTICE: the detection was already here (from orb_app.py, with the +-14h guard HACVD learned from a -39h weekend reading); now it is logged at start-up and when
    the broker changes it (its own daylight-saving change), and an absurd reading is reported and ignored.
  NOT ported, on purpose: HACVD's signals and exits. Measured honestly on 5.7 years of gold (and on this broker's own 2026 data), the absorption signal has no edge before costs
  (-0.003R), no information of its own, and a cost of about 0.18R per trade at its stop size; its backtest booked trades at the Heikin-Ashi close, which is not a tradable price.

OTHER MARKETS, re-tested with these corrected rules (stretch 0.8, ATR 10, stop 2x, one position at a time, nothing tuned). The first
FX test was run before problems 1-3 above were found, so its conclusion that "only gold passed" is WITHDRAWN. 12 markets looked at, 2012-2025
unless stated; "M30" = 30-minute bars standing in for 5-minute ones, checked to give a trade count within ~5% of the 5-minute answer:
  PASSED  USDJPY (5-min): 1,072 trades | avg +0.052R (95% interval +0.022 to +0.082) | +55.6R, +48.1R with the spread doubled | 12 of 14
          years positive. All six single-setting neighbours (stretch 0.6 / 1.0, ATR 6 / 20, stop 1.5x / 3x) also positive, even with the
          spread doubled. Mar-Sep 2026, which that test never touched: +2.7R on 33 trades (too few to confirm anything).
  PASSED  gold (above), with weaker evidence: its 95% interval only just touches zero.
  Gold and USDJPY are not alike: EMBER's monthly results on the two correlate at -0.02 (2021-2025).
  FAILED  EURUSD -11.8R | USDCAD +2.8R but -8.7R with the spread doubled | USDCHF (M30) +9.1R but -3.7R doubled | GBPUSD (M30) -7.5R |
          AUDUSD (M30) -21.3R | NZDUSD (M30) -21.9R | GBPJPY (M30) +10.8R but -0.9R doubled | AUDJPY (M30) +9.4R but -6.8R doubled |
          NAS100 (M30, Jul 2022-Oct 2026, 325 trades) -2.0R: longs +5.5R, shorts -7.5R, in a very strong up-trend.
  WEAK    EURJPY (M30) +16.4R, +5.9R doubled, 11 of 14 years, but the 99% interval includes zero. Not added.
Looking at 12 markets means a few would look good by luck alone. Allowing for that in the usual way, USDJPY's evidence still stands and gold's
would not: treat gold as the weaker of the two, and a reason not to give it more of the risk budget than USDJPY.
Not modelled anywhere in this project, gold included: overnight swap/financing, which a position held 1-2 nights pays or earns.
EMBER trades XAUUSD and USDJPY together, in ONE bot (--symbols XAUUSD or --symbols USDJPY runs just one).

ONE BOT, TWO MARKETS — what is shared and what is not:
  Per market: its own state, pending orders, magic number (990710 gold / 990720 USDJPY), risk % and Stop/Start button; a failure in one
  never stops the other. Shared: the account guards (daily loss, max drawdown, profit target), the news guard and the Pause button (which
  pauses BOTH), the Activity Log (lines are tagged [XAUUSD] / [USDJPY]) and the trade history.
  One command works for any account size: where the broker's smallest lot would risk more than 1.5x the risk % (gold on a 5K account), that
  market places no orders and says why, while the other carries on.
  There is NO combined open-risk cap (ORB has one): both markets can be in a trade at once, so up to about twice the per-trade risk can be
  open together. The backtests treat the two as independent, which their results back up (monthly correlation -0.02, 2021-2025).
  Checked by running the real bot on both markets together against 4.8 years of 5-minute data: gold 356 trades +14.5R and USDJPY 354 trades
  +13.4R, each matching its own backtest trade for trade (same exit times, same R) — see test_equivalence_multi.py.

PORTED FROM orb_app.py, and what that changed: the NEWS GUARD (ON by default; ORB's calendar, +-15 minutes), TELEGRAM alerts,
on/off switches for each guard, a PAUSE button, and a log of how far each fill landed from its trigger level. Two things work
differently here than in ORB because EMBER keeps pending orders sitting at the broker: (1) every guard — news, pause, daily
loss, drawdown, profit target — now also CANCELS the day's pending orders when it trips (an earlier EMBER only stopped NEW
orders being placed, so orders already waiting could still fill after a limit was hit); (2) if a trigger level was touched while
entries were on hold, that first touch is not traded and there is no trade for the rest of that day.
What the news guard costs in the backtest, with the calendar the bot really carries (the NFP formula for 2021-2025, every listed
event for 2026-27 — 2021-2025 lack the CPI/FOMC/ECB/BOE dates, so the cost on a complete calendar is likely larger than this):
  guard OFF: 423 trades, +18.24R  |  guard ON: 415 trades, +17.29R (spread doubled +15.22R), positive in 5 of 6 years.
What the guard is FOR — a stop order filling at a bad price inside a news spike — cannot appear in a backtest that fills at the
exact level, so that benefit is unmeasured. NOT ported because they do not apply to one symbol, one position, pending-order
entry: per-session cap, max trades per day, max concurrent risk, entry-slippage skip, direction filter, partial-to-breakeven.

NOT YET VERIFIED AGAINST A REAL MT5 (only against a simulated one): a pending order actually FILLING, the stop
being placed on the resulting position, the next-day-close exit, and the broker's deal history being read back to
record P&L / R. The pending-order placement itself has been seen working on a Vantage demo. Watch the first few
trades by hand — compare the dashboard's Trades tab with MT5's own History tab.

Caveats, stated plainly: ONE market, SIX years, no fresh holdout left (all available gold history
was used getting here), no live or demo track record at all, and daily bars mean this trades roughly
75 times a year — a completely different pace and risk profile from this project's other two bots.
Treat this as a hypothesis to forward-test on a demo account, not a proven edge.

Single file, same architecture as orb_app.py / bro_app.py: strategy engine, MT5 live wrappers,
guards, and the web dashboard all together.

Usage:
    python ember_app.py                          (BOTH markets in one bot, default port 8710)
    python ember_app.py --symbols XAUUSD         (gold only)        python ember_app.py --symbols USDJPY      (USDJPY only)
    python ember_app.py --preset evaluation      (Atlas Access evaluation: 1% risk, 10% trailing drawdown, 3% target)      --preset funded  (0.5% risk, cap 1.5%, shield 1.7%, 6% drawdown)
                        (a preset is applied at EVERY start, so it replaces what you changed in the dashboard; options after it override it)
    python ember_app.py --port 8710 --mt5-path "C:\\MyAccount\\terminal64.exe" --max-dd 10 --dd-mode trailing --profit-target 3
    Never start two copies on the SAME account (they would add up their risk); one copy per account, each on its own port.
    python ember_app.py --set-password           (set or clear the dashboard password, then exit; needed for --host other than this machine)
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import calendar
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Optional, Dict

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

import pandas as pd


# --- Timezone rules WITHOUT depending on zoneinfo/tzdata. On Windows, ZoneInfo("America/New_York")
# raises ZoneInfoNotFoundError unless the `tzdata` pip package is installed — which used to make the
# news guard throw on every entry attempt (no trade could ever open). These rules are exact for
# every date the bot cares about (US: 2nd Sun Mar -> 1st Sun Nov; EU: last Sun Mar -> last Sun Oct).
_STD_OFFSET = {"America/New_York": -5, "Europe/Berlin": 1, "Europe/London": 0}


def _nth_sunday(year, month, n):
    sundays = [d for d in calendar.Calendar().itermonthdates(year, month)
               if d.month == month and d.weekday() == 6]
    return sundays[n - 1] if n > 0 else sundays[-1]


def _dst_active(tz_name, utc_dt) -> bool:
    y = utc_dt.year
    mid = lambda d: datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
    if tz_name == "America/New_York":
        start = mid(_nth_sunday(y, 3, 2)) + timedelta(hours=7)     # 02:00 EST
        end = mid(_nth_sunday(y, 11, 1)) + timedelta(hours=6)      # 02:00 EDT
    else:
        start = mid(_nth_sunday(y, 3, -1)) + timedelta(hours=1)    # 01:00 UTC
        end = mid(_nth_sunday(y, 10, -1)) + timedelta(hours=1)
    return start <= utc_dt < end


def _utc_offset_hours(tz_name, utc_dt) -> int:
    return _STD_OFFSET[tz_name] + (1 if _dst_active(tz_name, utc_dt) else 0)


def _local_to_utc(y, m, d, h, mi, tz_name):
    """Wall-clock time in tz_name -> aware UTC datetime. Uses zoneinfo when it works,
    otherwise the rules above."""
    if ZoneInfo is not None:
        try:
            return datetime(y, m, d, h, mi, tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc)
        except Exception:
            pass
    naive = datetime(y, m, d, h, mi, tzinfo=timezone.utc)
    guess = naive - timedelta(hours=_STD_OFFSET[tz_name])
    return naive - timedelta(hours=_utc_offset_hours(tz_name, guess))


try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

APP_VERSION = "2026-10-09.EMBER-25"

# ============================================================
# STRATEGY PARAMETERS (validated — see header; not fit beyond the published 0.8/10 baseline)
# ============================================================
SYMBOL = "XAUUSD"
STRETCH_MULT = 0.8
ATR_DAYS = 10
STOP_ATR_MULT = 2.0
PIP_SIZE = 0.10
SPREAD_PIPS = 3.0            # same assumption used throughout this project's validation

BOT_NAME = "EMBER"          # shown in Telegram messages (ember06_app.py says EMBER-06, so two bots in one chat can be told apart)
MAGIC_NUMBER = 990710   # different from orb/bro/confluence family so all can run on the same account safely
DASHBOARD_PORT = 8710
DASHBOARD_HOST = "127.0.0.1"
SYMBOL_SUFFIX = ""
ACCOUNT_LABEL = ""

# Markets EMBER is ALLOWED to trade — only ones that passed the same test (see the header). A market goes in here AFTER it passes, not because it
# looks promising. pip_size = the price size of one "pip" for the lot-size maths; spread_pips = the cost the backtests assumed; digits = decimals
# shown in the log/dashboard; magic = separate per market, so two copies on one account never touch each other's orders.
SYMBOL_PROFILES = {
    # exit_delay_min: a trade that is due to close waits until this many minutes after the broker's midnight. Measured on this broker (7 days of ticks): USDJPY's spread is
    # about 8 pips at the broker midnight (median; 95th percentile 18) against 1.7 pips normally, and a SHORT pays it when it closes, which halved the strategy's edge
    # (+0.052R -> +0.026R). The broker's own 5-minute table (7 days of ticks) shows the spread WIDE through the whole of hour 00 (median 7.8 pips, and 14-16 pips at 00:25-00:35),
    # 2.0 pips at 01:00 (some wide ticks left, worst 10.7) and normal (1.70) from 01:05. So the exit waits until 01:05 = 65 minutes (30 minutes would have closed in the WORST spread).
    # Backtest, price drift of the wait included: +0.048R, z 3.1. Gold needs none: its market is closed at that hour and reopens at 01:00 ($0.26 against $0.22).
    "XAUUSD": dict(pip_size=0.10, spread_pips=3.0, digits=2, magic=990710, exit_delay_min=0),
    # USDJPY (magic 990720, exit_delay_min=65) was removed in EMBER-24: re-tested at +0.02R a trade, z 1.2.
    # CANDIDATE markets (see CANDIDATE_NOTES): they are NOT started unless asked for with --symbols. pip_size = 1 price unit (one dollar of Bitcoin, one index point); digits are corrected from the
    # broker's own symbol info at start-up. No exit delay: BTCUSD's spread is the same all day (no rollover widening). (JPN225 was removed in EMBER-23.)
    "BTCUSD": dict(pip_size=1.0, spread_pips=67.0, digits=2, magic=990730, exit_delay_min=0),
}
# The two proven markets are what a plain "py ember_app.py" runs. A market added later NEVER starts by itself (an old command line must not suddenly trade something new).
DEFAULT_SYMBOLS = ["XAUUSD"]
CANDIDATE_NOTES = {
    "BTCUSD": "CANDIDATE, not yet proven live: the same rule showed +0.067R a trade on 6.3 years of this broker's data (z 2.6) and CONFIRMED on older, never-seen years (+0.141R, z 3.0, 246 trades; long AND short positive). "
              "Costs measured at Atlas: spread $67 + overnight swap -15% a year = about 0.026R a trade. Crypto leverage at Atlas is reported as 1:2 in the evaluation and 1:1 funded (confirm it with Atlas). Trade it only after it has run on demo.",
}
PRICE_DIGITS = 2
EXIT_DELAY_MIN = 0

# ONE copy of EMBER trades every market in ACTIVE_SYMBOLS (default: DEFAULT_SYMBOLS = gold and USDJPY), like ORB trades its pairs. Each market has its own
# state, pending orders, magic number, risk % and on/off switch; the account-level guards (daily loss, drawdown, profit target, news, pause) are
# shared. To run each market on its own instead, start it with --symbols XAUUSD or --symbols USDJPY; to add the candidate:  --symbols XAUUSD USDJPY BTCUSD.
ACTIVE_SYMBOLS = list(DEFAULT_SYMBOLS)
RISK_PCT_BY_SYMBOL = {name: 0.5 for name in SYMBOL_PROFILES}
SYMBOL_ENABLED = {name: True for name in SYMBOL_PROFILES}
_LOG_TAG = None          # which market the poll thread is working on right now, so the shared Activity Log can say so


def _preset(risk, dd_pct, daily_pct, target, cap, shield, per_symbol=None):
    d = {f"risk_pct__{n}": (per_symbol or {}).get(n, risk) for n in SYMBOL_PROFILES}
    d.update(max_account_drawdown_pct=dd_pct, max_account_drawdown_mode="trailing", daily_loss_guard_pct=daily_pct, profit_target_pct=target,
             open_risk_cap_pct=cap, protector_shield_pct=shield, daily_loss_guard_enabled=True, max_account_drawdown_enabled=True,
             news_protection_enabled=True)
    return d


# One click (dashboard) or --preset (command line) fills every setting below, for the Atlas ACCESS program (official rules, help.atlasfunded.com,
# reviewed 27 Sep 2026). Evaluation: +3% target, 10% trailing equity drawdown, 5% daily. Funded: no target, 6% trailing equity, 3% daily, and Atlas Protector
# (open loss >= 2% of the starting balance closes everything and cuts the profit split to 50% for good). The daily guard is set to ~60% of the daily limit.
# The risk numbers come from this project's own measurements (header): 1.0% is the safe speed for the evaluation; 0.5% keeps the funded drawdown inside 6%.
# EMBER-24: re-measured on gold 2018-2026 (bot_audit/ember_atlas.py): 1.5% -> pass ~82%, ~4% breached; 0.75% funded survived every start date.
# BTCUSD (opt-in) always runs at HALF the gold risk: at full risk it raised the evaluation breaches (bot_audit/combo_atlas.py).
# combo-*: EMBER on the SAME account as NBRO (nbro_app.py --preset atlas-eval / atlas-funded --risk 0.25). Replay of both bots together
# (reports/combo_atlas.md): evaluation NBRO 1%/index + gold 1% + BTC 0.5% -> ~46% pass within 21 trading days, ~95% within a year,
# ~5% breached, median ~22 days; funded NBRO 0.25%/index + gold 0.5% + BTC 0.25% -> alive in every start date, ~2 payouts/yr, ~$2,200/yr on $50k.
PRESETS = {"evaluation": _preset(1.5, 10, 3.0, 3, 0, 0, {"BTCUSD": 0.75}),
           "funded": _preset(0.75, 6, 1.8, 0, 1.5, 1.7, {"BTCUSD": 0.35}),
           "combo-evaluation": _preset(1.0, 10, 3.0, 3, 0, 0, {"BTCUSD": 0.5}),
           "combo-funded": _preset(0.5, 6, 1.8, 0, 1.0, 1.7, {"BTCUSD": 0.25})}


def apply_symbol(name: str) -> None:
    """Point the module's 'current market' settings at one market. Called by use_symbol() before each market is processed."""
    global SYMBOL, PIP_SIZE, SPREAD_PIPS, MAGIC_NUMBER, PRICE_DIGITS, RISK_PCT, EXIT_DELAY_MIN
    p = SYMBOL_PROFILES[name]
    SYMBOL, PIP_SIZE, SPREAD_PIPS, MAGIC_NUMBER, PRICE_DIGITS = name, p["pip_size"], p["spread_pips"], p["magic"], p["digits"]
    EXIT_DELAY_MIN = p.get("exit_delay_min", 0)
    RISK_PCT = RISK_PCT_BY_SYMBOL.get(name, 0.5)

RISK_PCT = 0.5
# The broker's smallest lot (0.01) can risk far MORE than RISK_PCT when the stop is wide (gold's stop is 2 x ATR,
# about $166 per oz at the time of writing: 0.01 lot risks 3.3% of a $5,000 account). Rather than silently
# over-risking, no orders are placed that day when the real risk would exceed RISK_PCT x this factor.
MAX_RISK_OVERSHOOT = 1.5

# Atlas FUNDED-stage protection (see the header). Both are OFF (0) by default, so nothing changes for the evaluation or for the tested strategy.
OPEN_RISK_CAP_PCT = 0.0        # combined PLANNED risk of everything open or waiting, all markets, as % of the drawdown base balance
PROTECTOR_SHIELD_PCT = 0.0     # close everything when the OPEN loss reaches this % of the base (Atlas Protector fires at 2%)
_DEFAULT_INITIAL_BALANCE = 5000.0
INITIAL_ACCOUNT_BALANCE = _DEFAULT_INITIAL_BALANCE
MAX_ACCOUNT_DRAWDOWN_ENABLED = True
MAX_ACCOUNT_DRAWDOWN_PCT = 5.0
MAX_ACCOUNT_DRAWDOWN_MODE = "static"     # "static" or "trailing" — check your own prop-firm dashboard; see orb_app.py's own note
MAX_ACCOUNT_DRAWDOWN_SAFETY_BUFFER_PCT = 0.5
DAILY_LOSS_GUARD_ENABLED = True
DAILY_LOSS_GUARD_PCT = 1.8
PROFIT_TARGET_PCT = None                 # e.g. 3.0 for a 3% challenge target; None = off (default)

# ---- News guard (ported from orb_app.py: same calendar, same +-15-minute window) ------------------------------------
# What it does HERE differs from ORB, because EMBER works with pending orders sitting at the broker rather than a
# decision taken when a candle closes: from NEWS_WINDOW_BEFORE_MIN before a high-impact event until NEWS_WINDOW_AFTER_MIN
# after it, the day's pending orders are CANCELLED. If price touched either trigger level while they were off, that touch
# was news-driven, so no trade is taken for the rest of that day (the same "the first touch was blocked" rule ORB applies
# to a blocked signal); otherwise the orders go back on. A position already open is never touched by it. It exists because
# a stop order fills at whatever price the broker can give during a news spike, which the backtest (fills at the exact
# level) cannot show. Limits carried over from ORB: SCHEDULED events only (CPI, FOMC, ECB, BOE for 2026-2027, plus NFP by a
# first-Friday formula that is approximate in some months); an unscheduled shock is not covered; after 2027 only the NFP
# formula is left until dates are added to NEWS_EVENTS_STATIC.
NEWS_PROTECTION_ENABLED = True    # ON by default, as in ORB; Settings > News guard turns it off. Its measured cost is in the header.
NEWS_WINDOW_BEFORE_MIN = 15
NEWS_WINDOW_AFTER_MIN = 15
NEWS_EVENTS_STATIC: Dict[int, list] = {
    2026: [
        ((2026, 1, 13), (8, 30), "America/New_York", "US CPI"),
        ((2026, 2, 13), (8, 30), "America/New_York", "US CPI"),
        ((2026, 3, 11), (8, 30), "America/New_York", "US CPI"),
        ((2026, 4, 10), (8, 30), "America/New_York", "US CPI"),
        ((2026, 5, 12), (8, 30), "America/New_York", "US CPI"),
        ((2026, 6, 10), (8, 30), "America/New_York", "US CPI"),
        ((2026, 7, 14), (8, 30), "America/New_York", "US CPI"),
        ((2026, 8, 12), (8, 30), "America/New_York", "US CPI"),
        ((2026, 9, 11), (8, 30), "America/New_York", "US CPI"),
        ((2026, 10, 14), (8, 30), "America/New_York", "US CPI"),
        ((2026, 11, 10), (8, 30), "America/New_York", "US CPI"),
        ((2026, 12, 10), (8, 30), "America/New_York", "US CPI"),
        ((2026, 1, 28), (14, 0), "America/New_York", "FOMC"),
        ((2026, 3, 18), (14, 0), "America/New_York", "FOMC"),
        ((2026, 4, 29), (14, 0), "America/New_York", "FOMC"),
        ((2026, 6, 17), (14, 0), "America/New_York", "FOMC"),
        ((2026, 7, 29), (14, 0), "America/New_York", "FOMC"),
        ((2026, 9, 16), (14, 0), "America/New_York", "FOMC"),
        ((2026, 10, 28), (14, 0), "America/New_York", "FOMC"),
        ((2026, 12, 9), (14, 0), "America/New_York", "FOMC"),
        ((2026, 2, 5), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 3, 19), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 4, 30), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 6, 11), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 7, 23), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 9, 10), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 10, 29), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 12, 17), (14, 15), "Europe/Berlin", "ECB"),
        ((2026, 2, 5), (12, 0), "Europe/London", "BOE"),
        ((2026, 3, 19), (12, 0), "Europe/London", "BOE"),
        ((2026, 4, 30), (12, 0), "Europe/London", "BOE"),
        ((2026, 6, 18), (12, 0), "Europe/London", "BOE"),
        ((2026, 7, 30), (12, 0), "Europe/London", "BOE"),
        ((2026, 9, 17), (12, 0), "Europe/London", "BOE"),
        ((2026, 11, 5), (12, 0), "Europe/London", "BOE"),
        ((2026, 12, 17), (12, 0), "Europe/London", "BOE"),
    ],
    2027: [
        ((2027, 1, 27), (14, 0), "America/New_York", "FOMC"),
        ((2027, 3, 17), (14, 0), "America/New_York", "FOMC"),
        ((2027, 4, 28), (14, 0), "America/New_York", "FOMC"),
        ((2027, 6, 9), (14, 0), "America/New_York", "FOMC"),
        ((2027, 7, 28), (14, 0), "America/New_York", "FOMC"),
        ((2027, 9, 15), (14, 0), "America/New_York", "FOMC"),
        ((2027, 10, 27), (14, 0), "America/New_York", "FOMC"),
        ((2027, 12, 8), (14, 0), "America/New_York", "FOMC"),
        ((2027, 2, 4), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 3, 18), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 4, 29), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 6, 10), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 7, 22), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 9, 9), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 10, 28), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 12, 16), (14, 15), "Europe/Berlin", "ECB"),
        ((2027, 2, 4), (12, 0), "Europe/London", "BOE"),
        ((2027, 3, 18), (12, 0), "Europe/London", "BOE"),
        ((2027, 4, 29), (12, 0), "Europe/London", "BOE"),
        ((2027, 6, 17), (12, 0), "Europe/London", "BOE"),
        ((2027, 7, 29), (12, 0), "Europe/London", "BOE"),
        ((2027, 9, 16), (12, 0), "Europe/London", "BOE"),
        ((2027, 11, 4), (12, 0), "Europe/London", "BOE"),
        ((2027, 12, 16), (12, 0), "Europe/London", "BOE"),
    ],
}

# Pause switch (dashboard button / Settings): while True, no new pending orders are placed and any waiting ones are
# cancelled; an open position is still managed normally. Saved in the control file, so it survives a restart.
ENTRIES_PAUSED = False

STANDARD_ACCOUNT_SIZES = (1000, 2000, 2500, 5000, 10000, 15000, 20000, 25000, 30000, 40000,
                          50000, 75000, 100000, 150000, 200000, 250000, 300000, 400000, 500000)


# ============================================================
# PURE STRATEGY FUNCTIONS
# ============================================================
def resample_daily(m5: pd.DataFrame) -> pd.DataFrame:
    """M5 OHLC (any index name) -> daily OHLC, calendar-day boundaries in whatever timezone the
    M5 index already is (server/broker time — same convention this strategy was validated on)."""
    d = m5[["open", "high", "low", "close"]]
    return d.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def atr_prior_days(daily: pd.DataFrame, n: int = ATR_DAYS) -> pd.Series:
    """ATR(n), shifted by one day: today's value uses ONLY the n complete days before today — never
    today's own (not-yet-known) high/low. This is the fix for the lookahead bug described in the
    module header; do not remove the .shift(1)."""
    pc = daily["close"].shift(1)
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - pc).abs(), (daily["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().shift(1)


def todays_levels(daily: pd.DataFrame, today_open: float, atr_series: pd.Series, today_idx) -> Optional[dict]:
    """Given the daily series (for ATR lookup) and today's actual open price, the long/short trigger
    levels and the stop distance for today — or None if there isn't enough history yet."""
    if today_idx not in atr_series.index:
        return None
    a = atr_series.loc[today_idx]
    if pd.isna(a) or a <= 0:
        return None
    stretch = STRETCH_MULT * a
    risk = STOP_ATR_MULT * a
    return dict(atr=float(a), stretch=float(stretch), risk=float(risk),
               long_level=round(today_open + stretch, 5), short_level=round(today_open - stretch, 5))


def _now_utc() -> datetime:
    """The bot's clock for news windows and holds. One function so a test can replace it with a simulated time."""
    return datetime.now(timezone.utc)


@lru_cache(maxsize=8)
def _news_events_for_year(year: int) -> tuple:
    """All high-impact event UTC timestamps for one calendar year — static
    list + formula-computed NFP (first Friday of month, 8:30 ET — self-
    computing, needs no annual maintenance)."""
    events = []
    for (y, m, d), (h, mi), tz_name, name in NEWS_EVENTS_STATIC.get(year, []):
        events.append((_local_to_utc(y, m, d, h, mi, tz_name), name))
    cal = calendar.Calendar()
    for month in range(1, 13):
        fridays = [d for d in cal.itermonthdates(year, month)
                   if d.month == month and d.weekday() == 4]
        ff = fridays[0]
        events.append((_local_to_utc(ff.year, ff.month, ff.day, 8, 30, "America/New_York"), "NFP"))
    return tuple(sorted(events))


def is_news_blackout(check_time_utc: datetime, window_before_min: int = None,
                      window_after_min: int = None):
    """True + event name if check_time_utc falls within the news window
    around any known high-impact event. Checks the adjacent year too at
    Dec/Jan boundaries so early-January checks still see late-December
    events and vice versa.

    NOTE: window params default to None, resolved inside the function
    body — see find_accumulation_box's docstring pattern elsewhere in
    this project for why a module constant bound directly into a default
    parameter silently ignores later runtime changes to that constant."""
    if window_before_min is None:
        window_before_min = NEWS_WINDOW_BEFORE_MIN
    if window_after_min is None:
        window_after_min = NEWS_WINDOW_AFTER_MIN
    years = {check_time_utc.year}
    if check_time_utc.month == 1:
        years.add(check_time_utc.year - 1)
    if check_time_utc.month == 12:
        years.add(check_time_utc.year + 1)
    before = timedelta(minutes=window_before_min)
    after = timedelta(minutes=window_after_min)
    for year in years:
        for event_time, name in _news_events_for_year(year):
            if event_time - before <= check_time_utc <= event_time + after:
                return True, name
    return False, None


def get_next_news_event():
    """Next known high-impact event from now, for dashboard display. None
    if ZoneInfo isn't available or nothing found in the next ~2 years."""
    now = _now_utc()
    candidates = []
    for year in (now.year, now.year + 1):
        candidates += [(t, n) for t, n in _news_events_for_year(year) if t >= now]
    if not candidates:
        return None
    event_time, name = min(candidates)
    return {"time": event_time.isoformat(), "name": name}


def news_calendar_note() -> str:
    """Empty when the current year has its CPI/FOMC/ECB/BOE dates; otherwise says only the NFP formula is protecting."""
    y = _now_utc().year
    if NEWS_EVENTS_STATIC.get(y):
        return ""
    return f"No CPI/FOMC/ECB/BOE dates for {y} in NEWS_EVENTS_STATIC: only the NFP formula is protected."


# ---- Telegram alerts (ported from orb_app.py) -----------------------------------------------------------------------
# Config is a small JSON file next to this script: {"enabled": true, "bot_token": "...", "chat_id": "..."}. The first of
# these that exists is used, so an existing orb_telegram_config.json in the same folder works without any new setup.
TELEGRAM_CONFIG_FILES = ("ember_telegram_config.json", "orb_telegram_config.json")
_TELEGRAM_ASYNC = True          # sent from a background thread so a slow/blocked Telegram can never delay a poll
_tg_cache = {"at": 0.0, "cfg": {"enabled": False}}
_alerted: Dict[str, str] = {}


def _load_telegram_config() -> dict:
    now = time.time()
    if now - _tg_cache["at"] < 10:
        return _tg_cache["cfg"]
    cfg = {"enabled": False}
    for name in TELEGRAM_CONFIG_FILES:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)) as f:
                cfg = json.load(f)
            break
        except (OSError, ValueError):
            continue
    _tg_cache["at"], _tg_cache["cfg"] = now, cfg
    return cfg


def _telegram_send_now(message: str) -> None:
    try:
        cfg = _load_telegram_config()
        if not cfg.get("enabled"):
            return
        token, chat_id = cfg.get("bot_token", ""), cfg.get("chat_id", "")
        if not token or not chat_id:
            return
        text = f"[{ACCOUNT_LABEL}] {message}" if ACCOUNT_LABEL else message
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:          # best effort: a Telegram problem must NEVER affect trading
        _log(f"Telegram alert failed to send (the bot keeps trading normally regardless): {e}")


def send_telegram_alert(message: str) -> None:
    if _TELEGRAM_ASYNC:
        threading.Thread(target=_telegram_send_now, args=(message,), daemon=True).start()
    else:
        _telegram_send_now(message)


def _alert_once(key: str, day: str, message: str) -> None:
    """One Telegram message per key per day (guards re-evaluate every poll and would otherwise repeat every 15 seconds)."""
    key = f"{SYMBOL}:{key}"
    if _alerted.get(key) != day:
        _alerted[key] = day
        send_telegram_alert(message)


# ============================================================
# MT5 WRAPPERS
# ============================================================
_warned_at: Dict[str, float] = {}


def _warn_once(key: str, msg: str, every: float = 600.0):
    key = f"{SYMBOL}:{key}"          # each market throttles its own warnings
    now = time.time()
    if now - _warned_at.get(key, 0.0) >= every:
        _warned_at[key] = now
        _log(msg)


# The same market can carry another name at another broker (Vantage calls the Nikkei JPN225ft; Atlas calls it JPN225). When the exact name is not there, verify_symbol() looks through
# these and remembers the one it finds. The global --suffix still applies to every market that has no such alias.
BROKER_NAME_ALTERNATIVES = {"BTCUSD": ["BTCUSD.r", "BTCUSDm"], "XAUUSD": ["XAUUSD.r", "XAUUSDm"]}
_BROKER_NAME: Dict[str, str] = {}


def _bn(symbol: str) -> str:
    return _BROKER_NAME.get(symbol) or (symbol + SYMBOL_SUFFIX)


def _filling(symbol):
    info = mt5.symbol_info(_bn(symbol))
    mode = getattr(info, "filling_mode", 1)
    if mode & 1:
        return mt5.ORDER_FILLING_FOK
    if mode & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _round_price(symbol, price):
    info = mt5.symbol_info(_bn(symbol))
    digits = getattr(info, "digits", 2)
    return round(price, digits)


def _vol_limits(symbol):
    info = mt5.symbol_info(_bn(symbol))
    return (getattr(info, "volume_min", 0.01), getattr(info, "volume_max", 100.0), getattr(info, "volume_step", 0.01))


def _normalize_volume(symbol, vol):
    vmin, vmax, vstep = _vol_limits(symbol)
    vol = max(vmin, min(vol, vmax))
    steps = math.floor(vol / vstep + 1e-9)
    return round(steps * vstep, 8)


def _pip_value_per_lot(symbol, price) -> float:
    if MT5_AVAILABLE:
        try:
            info = mt5.symbol_info(_bn(symbol))
            tick_value = getattr(info, "trade_tick_value_loss", 0) or getattr(info, "trade_tick_value", 0)
            tick_size = getattr(info, "trade_tick_size", 0)
            if tick_value and tick_size and tick_value > 0 and tick_size > 0:
                return float(tick_value) * PIP_SIZE / float(tick_size)
        except Exception:
            pass
    return 10.0


def calculate_lot_size(equity: float, risk_pct: float, entry_price: float, sl_price: float) -> float:
    risk_dollars = equity * (risk_pct / 100.0)
    risk_pips = abs(entry_price - sl_price) / PIP_SIZE
    if risk_pips <= 0:
        return 0.0
    pip_value = _pip_value_per_lot(SYMBOL, entry_price)
    lots = risk_dollars / (risk_pips * pip_value)
    return _normalize_volume(SYMBOL, lots)


def _risk_pct_of(volume, entry, sl, equity) -> float:
    if equity <= 0:
        return 0.0
    pips = abs(entry - sl) / PIP_SIZE
    return pips * _pip_value_per_lot(SYMBOL, entry) * volume / equity * 100.0


def risk_within_tolerance(equity: float, volume: float, entry: float, sl: float):
    """(ok, actual_risk_pct, equity_needed). Is the REAL risk of this lot size within RISK_PCT x MAX_RISK_OVERSHOOT?"""
    actual = _risk_pct_of(volume, entry, sl, equity)
    limit = RISK_PCT * MAX_RISK_OVERSHOOT
    dollars = actual * equity / 100.0
    needed = dollars / (limit / 100.0) if limit > 0 else float("inf")
    return actual <= limit + 1e-9, actual, needed


def _order_ok(res) -> bool:
    return res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE


def get_rates(symbol, n=(ATR_DAYS + 20) * 288):
    """Enough M5 bars for ATR_DAYS+buffer of daily history plus intraday touch detection."""
    if not MT5_AVAILABLE:
        return None
    rates = mt5.copy_rates_from_pos(_bn(symbol), mt5.TIMEFRAME_M5, 0, n)
    if rates is None or len(rates) == 0:
        _warn_once(f"norates:{symbol}", f"[{symbol}] No price data from MT5 for '{_bn(symbol)}'.")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time")[["open", "high", "low", "close"]]


def place_pending(symbol, direction, volume, price, sl, comment):
    if not MT5_AVAILABLE:
        return None
    order_type = mt5.ORDER_TYPE_BUY_STOP if direction == "LONG" else mt5.ORDER_TYPE_SELL_STOP
    request = {
        "action": mt5.TRADE_ACTION_PENDING, "symbol": _bn(symbol), "volume": volume, "type": order_type,
        "price": _round_price(symbol, price), "sl": _round_price(symbol, sl), "magic": MAGIC_NUMBER,
        "comment": comment, "type_filling": _filling(symbol), "type_time": mt5.ORDER_TIME_DAY,
    }
    return mt5.order_send(request)


def cancel_pending(ticket):
    if not MT5_AVAILABLE:
        return None
    return mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})


def close_at_market(symbol, ticket, volume, direction, comment="ember_close"):
    if not MT5_AVAILABLE:
        return None
    order_type = mt5.ORDER_TYPE_SELL if direction == "LONG" else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(_bn(symbol))
    if tick is None:
        return None
    price = tick.bid if direction == "LONG" else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": _bn(symbol), "volume": volume, "type": order_type,
        "position": ticket, "price": price, "magic": MAGIC_NUMBER, "comment": comment,
        "type_filling": _filling(symbol), "deviation": 20,
    }
    return mt5.order_send(request)


def verify_symbol():
    if not MT5_AVAILABLE:
        return
    try:
        name = _bn(SYMBOL)
        info = mt5.symbol_info(name)
        if info is None:
            for alt in BROKER_NAME_ALTERNATIVES.get(SYMBOL, []):
                ai = mt5.symbol_info(alt)
                if ai is not None:
                    _BROKER_NAME[SYMBOL] = alt
                    _log(f"This broker calls {SYMBOL} '{alt}' (not '{name}'): using that.")
                    name, info = alt, ai
                    break
        if info is None:
            got = mt5.symbols_get()
            names = [g.name for g in got] if got else []
            near = [n for n in names if SYMBOL in n.upper()][:6] or [n for n in names if SYMBOL[:3] in n.upper()][:6]
            _log(f"'{name}' does not exist on this broker. Similar names: {near or 'none found'}. "
                f"If the broker adds a suffix, start with --suffix .r (or m). This bot CANNOT trade.")
            return
        if not getattr(info, "visible", True):
            ok = mt5.symbol_select(name, True)
            _log(f"'{name}' was not in Market Watch: {'added it' if ok else 'FAILED to add it'}.")
        # A pending order whose price has more decimals than the broker's symbol is rejected. The broker is the authority on that, not this file.
        bd = getattr(info, "digits", None)
        if isinstance(bd, int) and not isinstance(bd, bool) and 0 <= bd <= 8 and bd != PRICE_DIGITS:
            _log(f"This broker quotes {SYMBOL} with {bd} decimals (the built-in profile says {PRICE_DIGITS}): using {bd}.")
            SYMBOL_PROFILES[SYMBOL]["digits"] = bd
            apply_symbol(SYMBOL)
    except Exception as e:
        _log(f"Symbol check failed (bot keeps running): {e}")


# ============================================================
# STATE
# ============================================================
@dataclass
class ActiveTrade:
    direction: str
    entry_price: float
    sl_price: float
    volume: float
    ticket: int = 0
    entry_day: Optional[str] = None      # ISO date string of the day this was entered
    opened_at: Optional[str] = None
    slip_r: Optional[float] = None       # fill price vs the trigger level, in R (positive = worse than the level)


@dataclass
class BotState:
    phase: str = "WAITING_FOR_DAY"       # WAITING_FOR_DAY -> LEVELS_SET -> IN_TRADE
    current_day: Optional[str] = None
    long_order_ticket: int = 0
    short_order_ticket: int = 0
    today_long_level: Optional[float] = None
    today_short_level: Optional[float] = None
    today_risk: Optional[float] = None
    trade: Optional[ActiveTrade] = None
    close_requested: bool = False
    finalize_tries: int = 0                  # polls spent waiting for the broker's deal history to show the exit
    exit_reason_hint: Optional[str] = None   # why WE closed it (survives the wait above)
    hold_since: Optional[str] = None         # UTC time entries were put on hold (news / pause / a guard); None = not on hold
    hold_reason: Optional[str] = None
    day_skipped: bool = False                # a trigger was touched while on hold: that first touch is not traded, no trade today
    pending_volume: float = 0.0              # lots on the waiting order pair (so the open-risk cap can count them)
    close_reason: Optional[str] = None       # why a close was requested ("protector shield"); None = the dashboard's Close button
    shield_day: Optional[str] = None         # the market day on which the Protector shield tripped: no new entries until the day changes


# One BotState per market. `_state` is the one for the market being processed right now (swapped by use_symbol() on the poll thread); code
# that runs on the web-server thread must NOT use it — it reads _states[name] for the market it is asked about.
_states: Dict[str, BotState] = {name: BotState() for name in SYMBOL_PROFILES}
_state = _states[SYMBOL]
_last_login = None
_restored_login = None
_last_equity = None
_last_balance = None
_last_daily_sync = 0.0
_BALANCE_SET_BY_CLI = False

_account_guard_state = {
    "current_day": None, "day_start_equity": 0.0, "entries_today": 0,
    "dd_high_water_mark": 0.0,
}
_activity_log: deque = deque(maxlen=500)
_recent_trades: deque = deque(maxlen=5000)   # was 200: the history file and the dashboard's Total R silently forgot the oldest trades after ~2 years


# The Activity Log on the dashboard is only the last few hundred lines kept in memory: a restart or a reboot wipes it, and a trade that
# looked wrong can no longer be traced. Every line is therefore ALSO appended to ember_log_<port>.txt next to this file (ported from HACVD,
# which learned this the hard way). The file is trimmed to its last lines once it passes ~5 MB; a write failure never stops the bot.
LOG_TO_FILE = True
LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
LOG_FILE_KEEP_LINES = 20000
LOG_ROTATE_CHECK_EVERY = 200
_log_file_lock = threading.Lock()
_log_file_writes = 0


def _log_file_path() -> str:
    return os.path.join(_script_dir(), f"ember_log_{DASHBOARD_PORT}.txt")


def _write_log_file(entry: str) -> None:
    global _log_file_writes
    if not LOG_TO_FILE:
        return
    try:
        with _log_file_lock:
            path = _log_file_path()
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            _log_file_writes += 1
            if _log_file_writes % LOG_ROTATE_CHECK_EVERY == 0 and os.path.getsize(path) > LOG_FILE_MAX_BYTES:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(lines[-LOG_FILE_KEEP_LINES:])
    except OSError:
        pass


def _log(line: str, sym: Optional[str] = None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    tag = sym or _LOG_TAG
    prefix = f"[{tag}] " if (tag and len(ACTIVE_SYMBOLS) > 1) else ""
    entry = f"{ts} UTC {prefix}{line}"
    _activity_log.append(entry)
    _write_log_file(entry)


def use_symbol(name: str) -> None:
    """Make `name` the market the module-level helpers act on (settings AND state), until the next call."""
    global _state, _LOG_TAG
    apply_symbol(name)
    _state = _states[name]
    _LOG_TAG = name


def _no_symbol() -> None:
    global _LOG_TAG
    _LOG_TAG = None


def poll_all() -> None:
    """One pass over every market, in order. A failure in one market never stops the next one."""
    global _LOG_TAG, _last_foreign_check
    try:
        try:
            check_protector_shield()
        except Exception as e:
            _log(f"Protector shield check failed (bot keeps running): {type(e).__name__}: {e}")
        for name in ACTIVE_SYMBOLS:
            use_symbol(name)
            try:
                process_poll()
            except Exception as e:
                _log(f"Poll error (bot keeps running): {type(e).__name__}: {e}")
        _update_risk_snapshot()
        if time.time() - _last_foreign_check >= FOREIGN_CHECK_EVERY:
            _last_foreign_check = time.time()
            try:
                check_foreign_ember_orders()
            except Exception as e:
                _log(f"Check for foreign EMBER orders failed (bot keeps running): {type(e).__name__}: {e}")
    finally:
        _LOG_TAG = None


def _snapshot_deque(d) -> list:
    for _ in range(8):
        try:
            return list(d)
        except RuntimeError:
            continue
    return []


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


# ---- Dashboard password. HACVD had this (HTTP Basic, set by a separate script) but stored an UNSALTED SHA-256 and compared it with ==. This version: salted
# PBKDF2-HMAC-SHA256, constant-time comparison, a lock-out after repeated wrong tries, and it protects EVERY page and button (status, Close, Pause, Settings).
# One file (ember_dashboard_auth.json) next to this script covers every EMBER copy in the folder. Set or clear it with:  py ember_app.py --set-password
# HTTP Basic sends the password with each request without encryption: fine on localhost; across a network use an SSH tunnel or a VPN, not the open internet.
AUTH_FILE_NAME = "ember_dashboard_auth.json"
AUTH_ITERATIONS = 200_000
AUTH_MAX_FAILS = 5            # wrong tries from one address ...
AUTH_FAIL_WINDOW = 600        # ... within this many seconds ...
AUTH_LOCK_SECONDS = 60        # ... lock that address out for this long (even with the right password)
AUTH_OK_CACHE_SECONDS = 300   # a header already verified is trusted this long, so the dashboard's 5-second polling does not redo the slow hash each time
_auth_fails: Dict[str, list] = {}
_auth_ok_cache: Dict[str, float] = {}
_auth_lock = threading.Lock()


def _auth_path() -> str:
    return os.path.join(_script_dir(), AUTH_FILE_NAME)


def _load_auth() -> dict:
    try:
        with open(_auth_path()) as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def auth_enabled() -> bool:
    cfg = _load_auth()
    return bool(cfg.get("enabled") and cfg.get("hash") and cfg.get("salt") and cfg.get("username"))


def _pbkdf2_hex(password: str, salt_hex: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations).hex()


def set_dashboard_password(username: str, password: str) -> None:
    """Write the auth file. An empty password turns the protection OFF."""
    if not password:
        data = {"enabled": False}
    else:
        salt = os.urandom(16).hex()
        data = {"enabled": True, "username": username, "salt": salt, "iterations": AUTH_ITERATIONS, "hash": _pbkdf2_hex(password, salt, AUTH_ITERATIONS)}
    tmp = _auth_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, _auth_path())
    _auth_ok_cache.clear()


def check_auth(auth_header: Optional[str], client_ip: str):
    """Returns (allowed, http_status, seconds_to_wait). Not enabled -> always allowed."""
    cfg = _load_auth()
    if not (cfg.get("enabled") and cfg.get("hash") and cfg.get("salt") and cfg.get("username")):
        return True, 200, 0
    now = time.time()
    with _auth_lock:
        rec = _auth_fails.get(client_ip)
        if rec and now < rec[2]:
            return False, 429, int(rec[2] - now) + 1
        cache_key = hashlib.sha256(((auth_header or "") + "|" + cfg["hash"]).encode()).hexdigest()
        if auth_header and _auth_ok_cache.get(cache_key, 0) > now:
            return True, 200, 0
    if not auth_header:
        return False, 401, 0          # the browser's first request, before it asks for the password: not a wrong try
    user_ok = pw_ok = False
    if auth_header.startswith("Basic "):
        try:
            user, _, pw = base64.b64decode(auth_header[6:]).decode("utf-8").partition(":")
            # both comparisons always run, so the timing does not reveal whether the user name was right
            user_ok = hmac.compare_digest(user.encode(), str(cfg["username"]).encode())
            pw_ok = hmac.compare_digest(_pbkdf2_hex(pw, cfg["salt"], int(cfg.get("iterations", AUTH_ITERATIONS))).encode(), str(cfg["hash"]).encode())
        except Exception:
            user_ok = pw_ok = False
    with _auth_lock:
        if user_ok and pw_ok:
            _auth_fails.pop(client_ip, None)
            _auth_ok_cache[cache_key] = now + AUTH_OK_CACHE_SECONDS
            if len(_auth_ok_cache) > 200:
                _auth_ok_cache.clear()
            return True, 200, 0
        rec = _auth_fails.get(client_ip)
        if not rec or now - rec[1] > AUTH_FAIL_WINDOW:
            rec = [0, now, 0.0]
        rec[0] += 1
        if rec[0] >= AUTH_MAX_FAILS:
            rec[2] = now + AUTH_LOCK_SECONDS
            rec[0] = 0
            rec[1] = now
        _auth_fails[client_ip] = rec
    return False, 401, 0


def _is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def _cli_set_password() -> None:
    print("EMBER dashboard password. It protects every page and button of every EMBER copy that runs from this folder.")
    print("(Leave the password empty to turn the protection OFF.)")
    user = input("User name [admin]: ").strip() or "admin"
    pw = getpass.getpass("Password (at least 8 characters): ")
    if pw:
        if len(pw) < 8:
            print("Too short: use at least 8 characters. Nothing was changed.")
            return
        if getpass.getpass("Same password again: ") != pw:
            print("The two passwords differ. Nothing was changed.")
            return
    set_dashboard_password(user, pw)
    print(f"Saved to {_auth_path()}." if pw else "Password protection is now OFF.")
    print("No restart needed: a running copy reads this file on every request.")


def _state_path():
    return os.path.join(_script_dir(), f"ember_state_{DASHBOARD_PORT}.json")


def _history_path():
    return os.path.join(_script_dir(), f"ember_trades_{DASHBOARD_PORT}.json")


def _control_path():
    return os.path.join(_script_dir(), f"ember_control_{DASHBOARD_PORT}.json")


def _atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, default=str)
    os.replace(tmp, path)


def _state_to_dict(st: "BotState") -> dict:
    return {"phase": st.phase, "current_day": st.current_day,
            "long_order_ticket": st.long_order_ticket, "short_order_ticket": st.short_order_ticket,
            "today_long_level": st.today_long_level, "today_short_level": st.today_short_level,
            "today_risk": st.today_risk, "hold_since": st.hold_since, "hold_reason": st.hold_reason,
            "day_skipped": st.day_skipped, "pending_volume": st.pending_volume, "shield_day": st.shield_day,
            "trade": asdict(st.trade) if st.trade else None}


def _state_from_dict(st: "BotState", b: dict) -> None:
    """Fill an EXISTING BotState in place (other code holds a reference to it)."""
    st.phase = b.get("phase", "WAITING_FOR_DAY")
    st.current_day = b.get("current_day")
    st.long_order_ticket = b.get("long_order_ticket", 0)
    st.short_order_ticket = b.get("short_order_ticket", 0)
    st.today_long_level = b.get("today_long_level")
    st.today_short_level = b.get("today_short_level")
    st.today_risk = b.get("today_risk")
    st.hold_since = b.get("hold_since")
    st.hold_reason = b.get("hold_reason")
    st.day_skipped = bool(b.get("day_skipped", False))
    st.pending_volume = float(b.get("pending_volume", 0.0) or 0.0)
    st.shield_day = b.get("shield_day")
    st.trade = (ActiveTrade(**{k: v for k, v in b["trade"].items() if k in ActiveTrade.__dataclass_fields__})
                if b.get("trade") else None)


def save_state():
    try:
        g = _account_guard_state
        # `_state` is authoritative for the market being processed (it is the same object as _states[SYMBOL] in normal running)
        snap = {n: (_state if n == SYMBOL else _states[n]) for n in ACTIVE_SYMBOLS}
        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(), "account_login": _last_login, "format": 2,
            "account_guard": {"current_day": g["current_day"], "day_start_equity": g["day_start_equity"],
                              "entries_today": g.get("entries_today", 0),
                              "dd_high_water_mark": g.get("dd_high_water_mark", 0.0)},
            "symbols": {n: _state_to_dict(st) for n, st in snap.items()},
        }
        _atomic_write_json(_state_path(), data)
    except Exception as e:
        _log(f"save_state failed (bot keeps running): {e}")


def restore_state() -> bool:
    global _restored_login
    path = _state_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        _log(f"Could not read saved state ({e}) — starting clean.")
        return False
    _restored_login = data.get("account_login")
    g = _account_guard_state
    ag = data.get("account_guard", {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if ag.get("current_day") == today:
        g["current_day"] = ag["current_day"]
        g["day_start_equity"] = ag.get("day_start_equity", 0.0)
        g["entries_today"] = ag.get("entries_today", 0)
    g["dd_high_water_mark"] = max(g.get("dd_high_water_mark", 0.0), ag.get("dd_high_water_mark", 0.0))
    saved = data.get("symbols")
    if saved is None and data.get("bot"):
        saved = {"XAUUSD": data["bot"]}      # written by the one-market EMBER, which only ever traded gold
    restored = []
    for name in ACTIVE_SYMBOLS:
        if saved and name in saved:
            _state_from_dict(_states[name], saved[name])
            restored.append(name)
    _log(f"Restored saved state for {', '.join(restored) or 'no market'} (saved {data.get('saved_at')}).")
    return True


def _load_trade_history():
    path = _history_path()
    if os.path.exists(path):
        try:
            hist = json.load(open(path))
            _recent_trades.clear()
            _recent_trades.extend(hist)
            _log(f"Restored {len(hist)} closed trade(s) from history.")
        except Exception as e:
            _log(f"Could not read trade history ({e}).")


def _record_closed_trade(rec: dict):
    _recent_trades.append(rec)
    try:
        _atomic_write_json(_history_path(), _snapshot_deque(_recent_trades))
    except Exception as e:
        _log(f"Could not save trade history: {e}")


def _check_account_identity(login):
    global _last_login, _restored_login
    if login is None:
        return
    if _restored_login is not None and _restored_login != login:
        _log(f"WARNING: saved state on this port belongs to account {_restored_login}, MT5 is now {login}. "
             f"Archiving it and starting clean.")
        for f in (_state_path(), _history_path()):
            if os.path.exists(f):
                os.replace(f, f + f".account{_restored_login}.bak")
        global _state
        for n in list(_states):
            _states[n] = BotState()
        _state = _states[SYMBOL]
        _recent_trades.clear()
        _account_guard_state.update(current_day=None, day_start_equity=0.0, entries_today=0, dd_high_water_mark=0.0)
        _restored_login = None
    _last_login = login


def _balance_deposits():
    try:
        now = datetime.now(timezone.utc)
        deals = mt5.history_deals_get(datetime(2015, 1, 1), now + timedelta(days=1))
        if deals is None:
            return None
        bal_type = getattr(mt5, "DEAL_TYPE_BALANCE", 2)
        return [float(d.profit) for d in sorted(deals, key=lambda d: d.time)
               if getattr(d, "type", None) == bal_type and d.profit > 0]
    except Exception:
        return None


def _detect_account_base(balance):
    deposits = _balance_deposits() or []
    if len(deposits) == 1:
        return deposits[0], "the account's only deposit, read from the MT5 history"
    size = min(STANDARD_ACCOUNT_SIZES, key=lambda x: abs(balance - x) / x)
    if abs(balance - size) / size <= 0.15:
        note = f"{len(deposits)} deposits in the history" if deposits else "no deposit record in the history"
        return float(size), f"the standard account size nearest to its balance of ${balance:,.0f} ({note})"
    return balance, "its balance right now (it is not near a standard account size)"


def _read_control_file():
    try:
        with open(_control_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_control(control: dict):
    merged = {}
    try:
        with open(_control_path()) as f:
            merged = json.load(f)
    except Exception:
        pass
    merged.update(control)
    with open(_control_path(), "w") as f:
        json.dump(merged, f)


def _resolve_account_base():
    global INITIAL_ACCOUNT_BALANCE
    try:
        acct = mt5.account_info()
        if acct is None:
            return
        bal = getattr(acct, "balance", acct.equity)
        login = getattr(acct, "login", None)
        ctl = _read_control_file()
        verified = "initial_account_balance" in ctl and ctl.get("account_login") == login
        if _BALANCE_SET_BY_CLI or verified:
            if login is not None and ctl.get("account_login") != login and _BALANCE_SET_BY_CLI:
                _save_control({"account_login": login})
            return
        base, source = _detect_account_base(bal)
        INITIAL_ACCOUNT_BALANCE = round(base, 2)
        _save_control({"initial_account_balance": INITIAL_ACCOUNT_BALANCE, "account_login": login})
        floor = INITIAL_ACCOUNT_BALANCE * (1 - MAX_ACCOUNT_DRAWDOWN_PCT / 100.0)
        _log(f"Account {login}: drawdown base ${INITIAL_ACCOUNT_BALANCE:,.0f} = {source}. With max drawdown "
             f"{MAX_ACCOUNT_DRAWDOWN_PCT:g}% the floor is ${floor:,.0f} (your firm's rule, not in MT5: "
             f"set it in Settings or --max-dd).")
    except Exception as e:
        _log(f"Account base check failed (bot keeps running): {e}")


def compute_overall_drawdown_status(equity: float) -> dict:
    base = INITIAL_ACCOUNT_BALANCE
    if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing":
        base = max(base, _account_guard_state.get("dd_high_water_mark", INITIAL_ACCOUNT_BALANCE))
    floor = base * (1 - MAX_ACCOUNT_DRAWDOWN_PCT / 100.0)
    stop_new_entries_below = floor + INITIAL_ACCOUNT_BALANCE * (MAX_ACCOUNT_DRAWDOWN_SAFETY_BUFFER_PCT / 100.0)
    return {
        "floor": round(floor, 2), "trailing_base": round(base, 2) if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing" else None,
        "stop_new_entries_below": round(stop_new_entries_below, 2),
        "remaining_to_floor_dollars": round(equity - floor, 2),
        "remaining_to_floor_pct": round((equity - floor) / INITIAL_ACCOUNT_BALANCE * 100.0, 3),
        "blocked": equity <= stop_new_entries_below,
    }


def compute_daily_loss_pct():
    g = _account_guard_state
    start = g["day_start_equity"]
    if start <= 0 or _last_equity is None:
        return None
    return round((start - _last_equity) / INITIAL_ACCOUNT_BALANCE * 100.0, 3)


def _profit_target_reached():
    if PROFIT_TARGET_PCT is None or INITIAL_ACCOUNT_BALANCE <= 0 or _last_balance is None:
        return False, None
    gained = (_last_balance - INITIAL_ACCOUNT_BALANCE) / INITIAL_ACCOUNT_BALANCE * 100.0
    return gained >= PROFIT_TARGET_PCT, gained


_broker_offset_cache = 0
_broker_offset_known = False


def _broker_offset_seconds() -> int:
    """Broker server clock minus UTC, in whole hours (as seconds), measured from the symbol's last tick. MT5 stamps
    deals/positions with SERVER time, so a UTC day boundary must be shifted by this before it is compared with a
    deal's timestamp. A stale weekend tick can look absurd (HACVD once measured -39h), so anything beyond +-14h is
    rejected in favour of the last good value. Ported from orb_app.py (the first EMBER port left this out, which
    shifted the daily-loss window by the broker's offset)."""
    global _broker_offset_cache, _broker_offset_known
    try:
        tick = mt5.symbol_info_tick(_bn(SYMBOL))
        if tick is not None:
            h = round((tick.time - time.time()) / 3600.0)
            if abs(h) <= 14:
                new = int(h) * 3600
                if not _broker_offset_known:
                    _log(f"Broker server clock measured as UTC{h:+d} (from the live tick; it times the news windows and the daily-loss day).")
                elif new != _broker_offset_cache:
                    _log(f"Broker server clock changed: UTC{_broker_offset_cache // 3600:+d} -> UTC{h:+d} (usually the broker's own daylight-saving change). "
                         f"News windows and the daily-loss day follow it automatically.")
                _broker_offset_cache = new
                _broker_offset_known = True
            else:
                _warn_once("tzstale", f"Ignored a broker clock reading of {h:+d}h: far outside any real timezone, so the tick is stale (market closed?). "
                                      f"Keeping UTC{_broker_offset_cache // 3600:+d}.", every=6 * 3600)
    except Exception:
        pass
    return _broker_offset_cache or 0


def _recent_deals():
    now = datetime.now(timezone.utc)
    deals = mt5.history_deals_get(now - timedelta(days=4), now + timedelta(days=1))
    return None if deals is None else list(deals)


def _sync_daily_from_mt5(quiet=False):
    acct = mt5.account_info()
    if acct is None:
        return
    now = datetime.now(timezone.utc)
    midnight_epoch = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) + _broker_offset_seconds()
    deals = _recent_deals() or []
    buy, sell = getattr(mt5, "DEAL_TYPE_BUY", 0), getattr(mt5, "DEAL_TYPE_SELL", 1)
    bal_type = getattr(mt5, "DEAL_TYPE_BALANCE", 2)
    today_trades = [d for d in deals if d.time > midnight_epoch and getattr(d, "type", buy) in (buy, sell)]
    pnl_all = sum(d.profit + d.commission + d.swap for d in today_trades)
    ops_today = sum(d.profit for d in deals if d.time > midnight_epoch and getattr(d, "type", None) == bal_type)
    g = _account_guard_state
    g["current_day"] = now.strftime("%Y-%m-%d")
    g["day_start_equity"] = getattr(acct, "balance", acct.equity) - pnl_all - ops_today
    g["dd_high_water_mark"] = max(g.get("dd_high_water_mark", 0.0), g["day_start_equity"])
    if not quiet:
        _log(f"Daily P&L from MT5: {pnl_all:+.2f} today (day-start balance {g['day_start_equity']:.2f}).")


def refresh_daily_pnl(force=False):
    global _last_daily_sync
    if not MT5_AVAILABLE:
        return
    now = time.time()
    if not force and now - _last_daily_sync < 30:
        return
    _last_daily_sync = now
    try:
        _sync_daily_from_mt5(quiet=True)
    except Exception as e:
        _warn_once("dailysync", f"Daily P&L refresh failed (bot keeps running): {e}", every=300)


# ============================================================
# LIVE STATE MACHINE
# ============================================================
_risk_snapshot = {"open_risk_pct": 0.0, "by_symbol": {}, "open_loss_pct": None}


def _risk_dollars(symbol, volume, entry, sl) -> float:
    """Loss in account currency if price travels from `entry` to `sl` with `volume` lots — for ANY market (not only the current one)."""
    dist = abs(entry - sl)
    if MT5_AVAILABLE:
        try:
            info = mt5.symbol_info(_bn(symbol))
            tv = getattr(info, "trade_tick_value_loss", 0) or getattr(info, "trade_tick_value", 0)
            ts = getattr(info, "trade_tick_size", 0)
            if tv and ts and tv > 0 and ts > 0:
                return dist / float(ts) * float(tv) * volume
        except Exception:
            pass
    return dist / SYMBOL_PROFILES[symbol]["pip_size"] * 10.0 * volume


def _market_open_risk_dollars(name) -> float:
    """What this market can lose right now if its stop is hit: the open position, or else the waiting order pair (only one side can fill)."""
    st = _states[name]; magic = SYMBOL_PROFILES[name]["magic"]; total = 0.0; pos = []
    if MT5_AVAILABLE:
        try:
            pos = [p for p in (mt5.positions_get(symbol=_bn(name)) or []) if getattr(p, "magic", None) == magic]
        except Exception:
            pos = []
    if pos:
        for p in pos:
            sl = getattr(p, "sl", 0) or (st.trade.sl_price if st.trade else 0)
            if sl:
                total += _risk_dollars(name, p.volume, p.price_open, sl)
    elif st.trade:
        total = _risk_dollars(name, st.trade.volume, st.trade.entry_price, st.trade.sl_price)
    else:
        # The waiting orders: ask the BROKER what it really holds (the source of truth), not only the bot's own memory. After an upgrade or a restart in the middle of a
        # day, orders placed by an older version have no lot size in the saved state, which made this read 0.00% (and let the open-risk cap under-count them).
        worst = 0.0; seen = False
        if MT5_AVAILABLE:
            try:
                for o in (mt5.orders_get(symbol=_bn(name)) or []):
                    if getattr(o, "magic", None) != magic:
                        continue
                    seen = True
                    vol = getattr(o, "volume_current", None) or getattr(o, "volume", 0) or 0
                    px = getattr(o, "price_open", None) or getattr(o, "price", 0) or 0
                    sl = getattr(o, "sl", 0) or 0
                    dist = abs(px - sl) if (px and sl) else (st.today_risk or 0)
                    worst = max(worst, _risk_dollars(name, vol, 0.0, dist))      # only one side of the pair can fill: the larger of the two counts
            except Exception:
                seen = False
        if seen:
            total = worst
        elif (st.long_order_ticket or st.short_order_ticket) and st.pending_volume > 0 and st.today_risk:
            total = _risk_dollars(name, st.pending_volume, 0.0, st.today_risk)
    return total


def _broker_pending_tickets():
    """Tickets of this market's waiting orders as the broker holds them right now, or None when that cannot be read."""
    if not MT5_AVAILABLE:
        return None
    try:
        return {o.ticket for o in (mt5.orders_get(symbol=_bn(SYMBOL)) or []) if getattr(o, "magic", None) == MAGIC_NUMBER}
    except Exception:
        return None


def _has_our_position() -> bool:
    """True if the broker holds a position of this market with our magic number (and True when that cannot be read: be careful rather than sorry)."""
    if not MT5_AVAILABLE:
        return False
    try:
        return any(getattr(p, "magic", None) == MAGIC_NUMBER for p in (mt5.positions_get(symbol=_bn(SYMBOL)) or []))
    except Exception:
        return True


FOREIGN_CHECK_EVERY = 600.0
KNOWN_COMPANIONS = {990711: "EMBER-06"}      # another EMBER copy that is known to run alongside this one (its magic number is documented in its own file)
_last_foreign_check = 0.0
_foreign_warned: Dict[str, float] = {}


def check_foreign_ember_orders() -> None:
    """Warn (never touch) about pending orders or positions on this bot's markets that are MARKED as EMBER (comment starts with "ember") but carry a magic number that is not one of this
    bot's: typically left behind by an older version (e.g. 'ember06_long'). The bot does not manage them: if one fills, nobody closes it two days later, and it can double a trade.
    Anything not marked EMBER (the ORB bot's trades, your own manual ones) is left alone and not mentioned."""
    if not MT5_AVAILABLE:
        return
    own = {p["magic"] for p in SYMBOL_PROFILES.values()}
    for name in ACTIVE_SYMBOLS:
        try:
            sym = _bn(name)
            items = list(mt5.orders_get(symbol=sym) or []) + list(mt5.positions_get(symbol=sym) or [])
        except Exception:
            continue
        foreign = [x for x in items if getattr(x, "magic", None) not in own and str(getattr(x, "comment", "") or "").lower().startswith("ember")]
        companion = [x for x in foreign if getattr(x, "magic", None) in KNOWN_COMPANIONS]
        stray = [x for x in foreign if getattr(x, "magic", None) not in KNOWN_COMPANIONS]
        if companion:                      # a known sibling that runs on purpose: one quiet note a day, not a warning
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            ckey = f"{name}:companion:{day}"
            if ckey not in _foreign_warned:
                _foreign_warned[ckey] = time.time()
                who = ", ".join(sorted({KNOWN_COMPANIONS[getattr(x, 'magic')] + f" (magic {getattr(x, 'magic')})" for x in companion}))
                what = ", ".join(f"#{getattr(x, 'ticket', '?')} '{getattr(x, 'comment', '')}'" for x in companion[:6])
                _log(f"NOTE: {who} is also trading {name} on this account ({what}). It manages its own orders and positions and this copy never touches them. The two copies ADD UP their exposure "
                     f"on {name} (each risks its own %), and this copy's open-risk cap counts only its own trades.", sym=name)
        if not stray:
            continue
        key = f"{name}:{sorted(int(getattr(x, 'ticket', 0)) for x in stray)}"
        if time.time() - _foreign_warned.get(key, 0.0) < 3600.0:
            continue
        _foreign_warned[key] = time.time()
        what = ", ".join(f"#{getattr(x, 'ticket', '?')} '{getattr(x, 'comment', '')}'" for x in stray[:6])
        _log(f"WARNING: {name} has {len(stray)} pending order(s)/position(s) marked EMBER that this bot does NOT manage ({what}): left by an older version, or by another copy that is running. "
             f"If nothing manages them, nobody closes a filled one the next day and it can double a trade. If you do not want them, delete them in MT5 (Trade tab, right-click, Delete). "
             f"This bot has not touched them.", sym=name)


def _risk_base(equity=None) -> float:
    return INITIAL_ACCOUNT_BALANCE if INITIAL_ACCOUNT_BALANCE > 0 else float(equity or _last_equity or 0.0)


def _update_risk_snapshot() -> None:
    """Runs on the poll thread; the dashboard only reads the result."""
    try:
        base = _risk_base()
        by = {n: (_market_open_risk_dollars(n) / base * 100.0 if base > 0 else 0.0) for n in ACTIVE_SYMBOLS}
        loss = None
        if MT5_AVAILABLE and base > 0:
            acct = mt5.account_info(); positions = mt5.positions_get() or []
            if acct is not None:
                net_loss = max(0.0, float(acct.balance) - float(acct.equity))
                losers = sum(-float(p.profit) for p in positions if float(p.profit) < 0)
                loss = max(net_loss, losers) / base * 100.0
        _risk_snapshot.update(open_risk_pct=round(sum(by.values()), 3), by_symbol={k: round(v, 3) for k, v in by.items()}, open_loss_pct=(round(loss, 3) if loss is not None else None))
    except Exception:
        pass


def check_protector_shield() -> None:
    """Atlas FUNDED accounts: when OPEN losses reach 2% of the starting balance, Atlas closes everything and cuts the profit split to 50% for good (a second time: breach).
    This acts a little BEFORE that line (PROTECTOR_SHIELD_PCT, e.g. 1.7%): close our positions at market and stop new entries for the rest of the market day.
    Open loss = the larger of the account's net floating loss and the total of its losing positions — the same measure Atlas uses."""
    if PROTECTOR_SHIELD_PCT <= 0 or not MT5_AVAILABLE:
        return
    base = _risk_base()
    if base <= 0:
        return
    acct = mt5.account_info(); positions = mt5.positions_get() or []
    if acct is None or not positions:
        return
    net_loss = max(0.0, float(acct.balance) - float(acct.equity))
    losers = sum(-float(p.profit) for p in positions if float(p.profit) < 0)
    pct = max(net_loss, losers) / base * 100.0
    if pct < PROTECTOR_SHIELD_PCT:
        return
    closing = []
    for n in ACTIVE_SYMBOLS:
        st = _states[n]
        st.shield_day = st.current_day
        if st.trade is not None and not st.close_requested:
            st.close_requested = True; st.close_reason = "protector shield"; closing.append(n)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _alerted.get("shield") != day:
        _alerted["shield"] = day
        _log(f"PROTECTOR SHIELD: open loss {pct:.2f}% of the starting balance reached the {PROTECTOR_SHIELD_PCT:g}% line (Atlas Protector fires at 2%). "
             f"Closing {', '.join(closing) or 'nothing of ours'} at market; no new entries for the rest of the market day.")
        send_telegram_alert(f"🛡 {BOT_NAME}: open loss {pct:.2f}% reached the shield line ({PROTECTOR_SHIELD_PCT:g}%). Closing positions, no new entries today.")


def _entry_block_reason(equity: float):
    """(key, text) while NEW entries must not happen, else None. Every one of these must also cancel the pending orders
    already sitting at the broker — a guard that only stops NEW orders being placed would let the old ones still fill."""
    if ENTRIES_PAUSED:
        return "paused", "entries paused from the dashboard"
    if not SYMBOL_ENABLED.get(SYMBOL, True):
        return "stopped", f"{SYMBOL} stopped from the dashboard"
    if _state.shield_day and _state.shield_day == _state.current_day:
        return "shield", "Protector shield tripped today: open loss reached the safety line"
    reached, gained = _profit_target_reached()
    if reached:
        return "target", f"profit target reached (+{gained:.2f}%)"
    if MAX_ACCOUNT_DRAWDOWN_ENABLED and compute_overall_drawdown_status(equity)["blocked"]:
        return "dd", "Max Drawdown Guard: equity at/below the safety line"
    if DAILY_LOSS_GUARD_ENABLED:
        d = compute_daily_loss_pct()
        if d is not None and d >= DAILY_LOSS_GUARD_PCT:
            return "dloss", f"Daily Loss Guard: {d:.2f}% >= {DAILY_LOSS_GUARD_PCT:g}%"
    if NEWS_PROTECTION_ENABLED:
        blocked, name = is_news_blackout(_now_utc())
        if blocked:
            return "news", f"news blackout ({name})"
    return None


def _level_touched_since(m5, since_iso) -> bool:
    """Did price reach either of today's trigger levels on a COMPLETED 5-minute bar since the hold began? The bar still
    forming is not counted: the hold ended during it, and orders are back on for the rest of it."""
    try:
        since = datetime.fromisoformat(since_iso).replace(tzinfo=None)
    except Exception:
        return False
    off = pd.Timedelta(seconds=_broker_offset_seconds())
    start = (pd.Timestamp(since) + off).floor("5min")
    now_bar = (pd.Timestamp(_now_utc().replace(tzinfo=None)) + off).floor("5min")
    day_start = now_bar.normalize()
    seg = m5[(m5.index >= max(start, day_start)) & (m5.index < now_bar)]
    if seg.empty or _state.today_long_level is None:
        return False
    return bool(seg["high"].max() >= _state.today_long_level or seg["low"].min() <= _state.today_short_level)


def _cancel_pending_orders():
    handled = set()
    for attr in ("long_order_ticket", "short_order_ticket"):
        ticket = getattr(_state, attr)
        if ticket:
            handled.add(ticket)
            res = cancel_pending(ticket)
            if not _order_ok(res):
                _log(f"Could not cancel pending order #{ticket} (retcode {getattr(res, 'retcode', None)}); "
                    f"it may have already filled or expired.")
            setattr(_state, attr, 0)
    _state.pending_volume = 0.0
    # Also sweep any pending order of ours that this process has no record of (saved state lost, or the bot was
    # started from a different folder/port than before) — otherwise a restart would stack a SECOND pair of
    # pending orders on top of the first one still sitting at the broker.
    try:
        for o in (mt5.orders_get(symbol=_bn(SYMBOL)) or []) if MT5_AVAILABLE else []:
            if getattr(o, "magic", None) == MAGIC_NUMBER and o.ticket not in handled:
                res = cancel_pending(o.ticket)
                _log(f"Cancelled a leftover pending order #{o.ticket} of this bot "
                    f"({'ok' if _order_ok(res) else 'retcode ' + str(getattr(res, 'retcode', None))}).")
    except Exception as e:
        _warn_once("sweep", f"Could not check for leftover pending orders (bot keeps running): {e}", every=600)


FINALIZE_MAX_TRIES = 4


def _finalize_closed_trade(reason_hint=None) -> bool:
    """Record a trade that is no longer open at the broker. Returns False (trade kept in memory) while the broker's
    deal history has not caught up with the close yet — it is retried on the next polls, up to FINALIZE_MAX_TRIES,
    before being recorded without a P&L. Recording it immediately would lose the P&L and R for good."""
    trade = _state.trade
    if reason_hint:
        _state.exit_reason_hint = reason_hint
    reason_hint = reason_hint or _state.exit_reason_hint
    deals = _recent_deals() or []
    exit_deal = next((d for d in sorted(deals, key=lambda d: -d.time)
                      if d.position_id == trade.ticket and d.entry == mt5.DEAL_ENTRY_OUT), None)
    if exit_deal is None and _state.finalize_tries < FINALIZE_MAX_TRIES:
        _state.finalize_tries += 1
        return False
    pnl = (exit_deal.profit + exit_deal.commission + exit_deal.swap) if exit_deal else None
    risk_price = abs(trade.entry_price - trade.sl_price)
    r = None
    if exit_deal and risk_price > 0:
        move = (exit_deal.price - trade.entry_price) if trade.direction == "LONG" else (trade.entry_price - exit_deal.price)
        r = move / risk_price
    reason = reason_hint or "unknown"
    if exit_deal and reason_hint is None:
        reason = "stop" if getattr(exit_deal, "reason", None) == getattr(mt5, "DEAL_REASON_SL", 4) else "manual/external"
    rec = dict(symbol=SYMBOL, direction=trade.direction, entry=trade.entry_price,
              exit=(exit_deal.price if exit_deal else None), sl=trade.sl_price, volume=trade.volume,
              r=r, pnl=pnl, reason=reason, entry_day=trade.entry_day, opened_at=trade.opened_at,
              closed_at=datetime.now(timezone.utc).isoformat())
    _record_closed_trade(rec)
    emoji = "✅" if (pnl or 0) > 0 else ("⚪" if (pnl or 0) == 0 else "🔴")
    _log(f"{emoji} Trade closed — {reason} | R {f'{r:+.2f}' if r is not None else 'n/a'} | "
         f"P&L {f'${pnl:+.2f}' if pnl is not None else 'n/a'}")
    send_telegram_alert(f"{emoji} {BOT_NAME} CLOSED {SYMBOL} {trade.direction}\nreason: {reason}\n"
                        f"R {f'{r:+.2f}' if r is not None else 'n/a'} | P&L {f'${pnl:+.2f}' if pnl is not None else 'n/a'}")
    _state.trade = None
    _state.phase = "WAITING_FOR_DAY"
    _state.finalize_tries = 0
    _state.exit_reason_hint = None
    save_state()
    return True


def _close_duplicate_positions(mine):
    """Both pending orders can fill before the 15-second poll cancels the second one (a fast news spike crossing both
    levels). Only ONE position may exist: keep the one already tracked (else the earliest) and close the rest at
    market — left alone, the extra would have no next-day-close exit and only its stop to end it. Returns the ticket kept."""
    tracked = _state.trade.ticket if _state.trade is not None else None
    keep = tracked if tracked in [p.ticket for p in mine] else min(mine, key=lambda p: (p.time, p.ticket)).ticket
    for p in mine:
        if p.ticket == keep:
            continue
        direction = "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT"
        res = close_at_market(SYMBOL, p.ticket, p.volume, direction, comment="ember_dup")
        note = (f"DUPLICATE POSITION #{p.ticket} ({direction}, both pending orders filled): "
                f"{'closed at market' if _order_ok(res) else 'close FAILED retcode ' + str(getattr(res, 'retcode', None)) + ' — retrying next poll'}; "
                f"keeping #{keep}.")
        _log(note)
        send_telegram_alert(f"⚠️ {BOT_NAME} " + note)
    return keep


def _reconcile() -> bool:
    """Flat in memory but MT5 holds a position of ours? Take it over. Holding one in memory that MT5 no longer has?
    It was closed (stop, or by us) — record it. Returns True while that record is still waiting for the broker's
    deal history, so the caller skips the rest of the poll instead of acting on a half-closed trade."""
    positions = mt5.positions_get(symbol=_bn(SYMBOL)) or []
    mine = [p for p in positions if p.magic == MAGIC_NUMBER]
    if not mine:
        if _state.trade is not None:
            return not _finalize_closed_trade()
        return False
    if len(mine) > 1:
        keep = _close_duplicate_positions(mine)
        mine = [p for p in mine if p.ticket == keep]
    pos = mine[0]
    if _state.trade is not None and _state.trade.ticket == pos.ticket:
        return False
    direction = "LONG" if pos.type == mt5.POSITION_TYPE_BUY else "SHORT"
    _state.trade = ActiveTrade(direction=direction, entry_price=pos.price_open, sl_price=pos.sl or 0.0,
                               volume=pos.volume, ticket=pos.ticket,
                               entry_day=datetime.fromtimestamp(pos.time, timezone.utc).strftime("%Y-%m-%d"),
                               opened_at=datetime.fromtimestamp(pos.time, timezone.utc).isoformat())
    _state.phase = "IN_TRADE"
    _cancel_pending_orders()
    level = _state.today_long_level if direction == "LONG" else _state.today_short_level
    slip_txt = ""
    risk_px = abs(pos.price_open - (pos.sl or 0.0))
    if level is not None and _state.current_day == _state.trade.entry_day and risk_px > 0:
        slip = (pos.price_open - level) if direction == "LONG" else (level - pos.price_open)
        _state.trade.slip_r = round(slip / risk_px, 3)
        slip_txt = f" | trigger was {level:.{PRICE_DIGITS}f}, slippage {slip:+.{PRICE_DIGITS}f} ({_state.trade.slip_r:+.2f}R, positive = worse)"
    _log(f"TOOK OVER open {direction} #{pos.ticket} from MT5 — {pos.volume} lots @ {pos.price_open}{slip_txt}.")
    send_telegram_alert(f"🔔 {BOT_NAME} {SYMBOL} {direction} FILLED @ {pos.price_open}\n{pos.volume} lots, stop {pos.sl}{slip_txt}")
    save_state()
    return False


def process_poll():
    global _last_equity, _last_balance
    account = mt5.account_info() if MT5_AVAILABLE else None
    if account:
        _last_equity = account.equity
        _last_balance = getattr(account, "balance", account.equity)
        if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing":
            _account_guard_state["dd_high_water_mark"] = max(_account_guard_state.get("dd_high_water_mark", 0.0), account.equity)
    equity = account.equity if account else (_last_equity or INITIAL_ACCOUNT_BALANCE)

    if _reconcile():
        return          # a closed trade is still waiting for the broker's deal history: finish that first

    m5 = get_rates(SYMBOL)
    if m5 is None or len(m5) < (ATR_DAYS + 5) * 288:
        return
    daily = resample_daily(m5)
    if len(daily) < ATR_DAYS + 2:
        return
    today_idx = daily.index[-1]
    today_str = today_idx.strftime("%Y-%m-%d")
    atr_series = atr_prior_days(daily, ATR_DAYS)

    new_day = _state.current_day != today_str
    day_positions = {ts.strftime("%Y-%m-%d"): i for i, ts in enumerate(daily.index)}
    today_pos = day_positions.get(today_str)

    # A trade that is DUE to close may be made to WAIT (EXIT_DELAY_MIN, see SYMBOL_PROFILES) so it does not close in the rollover spread. Its broker stop keeps protecting it,
    # a dashboard Close / Protector shield request still acts at once, and no new orders are made until it has closed.
    exit_wait = False
    if new_day and _state.trade is not None and EXIT_DELAY_MIN > 0:
        ep = day_positions.get(_state.trade.entry_day) if _state.trade.entry_day else None
        if ep is not None and today_pos is not None and today_pos > ep + 1:
            lb = m5.index[-1]
            if lb.strftime("%Y-%m-%d") == today_str and lb.hour * 60 + lb.minute < EXIT_DELAY_MIN:
                exit_wait = True
                _warn_once(f"exitwait:{today_str}", f"The trade is due to close, but waits until {EXIT_DELAY_MIN} min after the broker midnight so it does not pay the "
                                                    f"rollover spread (its stop still protects it).", every=6 * 3600)
    exited_late = False

    if new_day and not exit_wait:
        # Exit at the close of the day AFTER entry -- only once we are TWO trading-day positions past
        # the entry day (entry day's own position + one full day elapsed), using the ACTUAL trading-day
        # sequence (skips weekends/holidays exactly as daily.index already does) rather than a plain
        # calendar-date string comparison. The string-comparison version exited a full day too soon --
        # caught by comparing this live code's own output against the validated backtest, fixed here.
        entry_pos = day_positions.get(_state.trade.entry_day) if (_state.trade and _state.trade.entry_day) else None
        if (_state.trade is not None and entry_pos is not None and today_pos is not None
                and today_pos > entry_pos + 1):
            res = close_at_market(SYMBOL, _state.trade.ticket, _state.trade.volume, _state.trade.direction,
                                  comment="ember_nextclose")
            if _order_ok(res):
                if not _finalize_closed_trade(reason_hint="next_day_close"):
                    return      # deal history not visible yet: _reconcile() records it on the next poll
                exited_late = EXIT_DELAY_MIN > 0
            else:
                _log(f"Next-day-close exit FAILED (retcode {getattr(res, 'retcode', None)}): will retry next poll.")
                return

        if _state.trade is None:
            _cancel_pending_orders()
            levels = todays_levels(daily, float(daily["open"].iloc[-1]), atr_series, today_idx)
            _state.current_day = today_str
            _state.hold_since = _state.hold_reason = None
            _state.day_skipped = False
            if levels is None:
                _state.phase = "WAITING_FOR_DAY"
                _state.today_long_level = _state.today_short_level = _state.today_risk = None
            else:
                _state.today_long_level = levels["long_level"]
                _state.today_short_level = levels["short_level"]
                _state.today_risk = levels["risk"]
                _state.phase = "LEVELS_SET"
                _log(f"New day. Open {daily['open'].iloc[-1]:.{PRICE_DIGITS}f} | ATR({ATR_DAYS}) {levels['atr']:.{PRICE_DIGITS}f} | "
                    f"LONG above {levels['long_level']:.{PRICE_DIGITS}f} | SHORT below {levels['short_level']:.{PRICE_DIGITS}f}")
                if exited_late:
                    # the levels were set late (the trade waited for its exit delay): a level crossed in the meantime is not traded, like any touch while entries were on hold
                    prior = m5[(m5.index.strftime("%Y-%m-%d") == today_str) & (m5.index < m5.index[-1])]
                    if len(prior) and (prior["high"].max() >= round(levels["long_level"], PRICE_DIGITS) or prior["low"].min() <= round(levels["short_level"], PRICE_DIGITS)):
                        _state.day_skipped = True
                        _log("A trigger level was crossed while the trade waited for its exit delay: that touch is not traded, no trade today.")
            save_state()

    if _state.trade is not None and _state.close_requested:
        res = close_at_market(SYMBOL, _state.trade.ticket, _state.trade.volume, _state.trade.direction,
                              comment="ember_manual")
        if _order_ok(res):
            _state.close_requested = False
            _finalize_closed_trade(reason_hint=_state.close_reason or "manual (dashboard)")
            _state.close_reason = None
        else:
            _log(f"Dashboard close request failed (retcode {getattr(res, 'retcode', None)}): will retry next poll.")
        return

    if _state.phase == "LEVELS_SET" and _state.trade is None:
        if _state.day_skipped:
            return
        block = _entry_block_reason(equity)
        if block is not None:
            key, why = block
            if _state.hold_since is None:
                _cancel_pending_orders()
                _state.hold_since, _state.hold_reason = _now_utc().isoformat(), why
                _log(f"ENTRIES ON HOLD — {why}. Pending orders cancelled; open positions are still managed.")
                _alert_once(f"hold:{key}", today_str, f"⏸ {BOT_NAME} {SYMBOL}: {why}. Pending orders cancelled, no new entries until it clears.")
                save_state()
            return
        if _state.hold_since is not None:
            touched = _level_touched_since(m5, _state.hold_since)
            why, _state.hold_since, _state.hold_reason = _state.hold_reason, None, None
            if touched:
                _state.day_skipped = True
                _log(f"Hold ended ({why}), but a trigger level was TOUCHED while it lasted: that first touch is not traded, "
                     f"so no trade for the rest of today.")
                send_telegram_alert(f"⏭ {BOT_NAME} {SYMBOL}: a trigger was touched during the hold ({why}) — no trade today.")
                save_state()
                return
            _log(f"Hold ended ({why}); no trigger level was touched meanwhile, orders go back on.")
            send_telegram_alert(f"▶ {BOT_NAME} {SYMBOL}: hold ended ({why}), orders going back on.")
            save_state()
        if _state.long_order_ticket or _state.short_order_ticket:
            # The bot remembers its two waiting orders by ticket. If they are no longer at the broker (deleted by hand in MT5, or cancelled by the broker) and nothing
            # was filled, the memory is wrong: without this the bot would believe the orders still exist and the day's trade would be silently lost.
            alive = _broker_pending_tickets()
            mine = {t for t in (_state.long_order_ticket, _state.short_order_ticket) if t}
            if alive is not None and (mine - alive) and not _has_our_position():
                _log(f"The waiting order(s) {sorted(mine - alive)} are no longer at the broker (deleted by hand, or cancelled by it) and nothing was filled: "
                     f"clearing the pair and putting the day's orders on again.")
                _cancel_pending_orders()                      # also removes whatever is left of the pair
                if float(daily["high"].iloc[-1]) >= round(_state.today_long_level, PRICE_DIGITS) or float(daily["low"].iloc[-1]) <= round(_state.today_short_level, PRICE_DIGITS):
                    _state.day_skipped = True                 # a level was reached while the orders were gone: that touch is not traded, like any touch while entries were on hold
                    _log("A trigger level was reached while the orders were gone: that touch is not traded, no trade today.")
                    save_state()
                    return
        if _state.long_order_ticket == 0 and _state.short_order_ticket == 0:
            risk_pct = RISK_PCT
            vol = calculate_lot_size(equity, risk_pct, _state.today_long_level,
                                     _state.today_long_level - _state.today_risk)
            if vol <= 0:
                return
            long_sl = _state.today_long_level - _state.today_risk
            short_sl = _state.today_short_level + _state.today_risk
            if OPEN_RISK_CAP_PCT > 0:
                # Combined risk cap: what the OTHER markets have open or waiting counts against the budget; this market gets what is left.
                base = _risk_base(equity)
                others = sum(_market_open_risk_dollars(n) for n in ACTIVE_SYMBOLS if n != SYMBOL) / base * 100.0
                one_lot = _risk_dollars(SYMBOL, 1.0, _state.today_long_level, long_sl) / base * 100.0
                room = OPEN_RISK_CAP_PCT - others
                if one_lot > 0 and vol * one_lot > room + 1e-9:
                    vmin, vmax, vstep = _vol_limits(SYMBOL)
                    fit = math.floor((room / one_lot) / vstep + 1e-9) * vstep if room > 0 else 0.0
                    if fit < vmin - 1e-9:
                        _warn_once(f"cap:{today_str}",
                                   f"NO ORDERS TODAY: the open-risk cap is {OPEN_RISK_CAP_PCT:g}% and the other markets already use {others:.2f}% of it; "
                                   f"even the smallest lot ({vmin}) would risk {vmin * one_lot:.2f}%.", every=6 * 3600)
                        _alert_once("cap", today_str, f"🚫 {BOT_NAME} {SYMBOL}: no orders today — the open-risk cap ({OPEN_RISK_CAP_PCT:g}%) leaves no room.")
                        return
                    _warn_once(f"capfit:{today_str}",
                               f"Open-risk cap {OPEN_RISK_CAP_PCT:g}%: other markets use {others:.2f}%, so this market's lot is cut from {vol} to {round(fit, 8)}.",
                               every=6 * 3600)
                    vol = round(fit, 8)
            ok_risk, actual_pct, needed = risk_within_tolerance(equity, vol, _state.today_long_level, long_sl)
            if not ok_risk:
                _warn_once(f"minlot:{today_str}",
                           f"NO ORDERS TODAY: the smallest lot this broker allows ({vol}) would risk {actual_pct:.2f}% of "
                           f"equity at today's {STOP_ATR_MULT:g}xATR stop ({_state.today_risk:.{PRICE_DIGITS}f} price units), against a "
                           f"{RISK_PCT:g}% target (limit {RISK_PCT * MAX_RISK_OVERSHOOT:g}%). This strategy needs an account of "
                           f"about ${needed:,.0f}+ at this Risk %, or a higher Risk % in Settings.", every=6 * 3600)
                _alert_once("minlot", today_str, f"🚫 {BOT_NAME} {SYMBOL}: no orders today — the smallest lot risks {actual_pct:.2f}% "
                            f"(limit {RISK_PCT * MAX_RISK_OVERSHOOT:g}%). Account too small for this strategy at this Risk %.")
                return
            r1 = place_pending(SYMBOL, "LONG", vol, _state.today_long_level, long_sl, "ember_long")
            r2 = place_pending(SYMBOL, "SHORT", vol, _state.today_short_level, short_sl, "ember_short")
            if r1 is not None and getattr(r1, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                _state.long_order_ticket = r1.order
            if r2 is not None and getattr(r2, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                _state.short_order_ticket = r2.order
            if _state.long_order_ticket and _state.short_order_ticket:
                _state.pending_volume = vol
                _log(f"Pending orders placed: LONG #{_state.long_order_ticket} @ {_state.today_long_level:.{PRICE_DIGITS}f}, "
                    f"SHORT #{_state.short_order_ticket} @ {_state.today_short_level:.{PRICE_DIGITS}f}, {vol} lots each.")
                _alert_once("levels", today_str, f"🕯 {BOT_NAME} {SYMBOL} {today_str}\nLONG above {_state.today_long_level:.{PRICE_DIGITS}f} | "
                            f"SHORT below {_state.today_short_level:.{PRICE_DIGITS}f}\n{vol} lots each, stop {_state.today_risk:.{PRICE_DIGITS}f} away "
                            f"(~{actual_pct:.2f}% risk)")
                save_state()
            else:
                _warn_once(f"place:{today_str}",
                           f"Could not place both pending orders (long ok={bool(_state.long_order_ticket)}, "
                           f"short ok={bool(_state.short_order_ticket)}; retcodes {getattr(r1, 'retcode', None)}/"
                           f"{getattr(r2, 'retcode', None)}) — keeps retrying every poll, logged here every 10 min. "
                           f"Common cause: price is already beyond one of the levels (e.g. the bot was off when it crossed).",
                           every=600)
                _cancel_pending_orders()
        else:
            # isa sa dalawang pending order ba ang nag-fill na? (iiwan ng MT5 ang isa sa positions, tatanggalin
            # ang parehong pending kapag na-fill ang isa dahil one-cancels-other ay hindi native sa MT5 -- gawin
            # natin ito mismo: kung may bagong position, kanselahin ang natitirang pending)
            positions = mt5.positions_get(symbol=_bn(SYMBOL)) or []
            mine = [p for p in positions if p.magic == MAGIC_NUMBER]
            if mine:
                _cancel_pending_orders()
                # ang _reconcile() sa susunod na poll ang kukuha nito papuntang _state.trade


# ============================================================
# STATUS / DASHBOARD
# ============================================================
def _symbol_status(name: str) -> dict:
    """Everything the dashboard shows for ONE market. Reads _states[name] directly — this runs on the web-server thread, which must not use the
    poll thread's 'current market' globals."""
    st = _states[name]
    closed = [c for c in _snapshot_deque(_recent_trades) if (c.get("symbol") or "XAUUSD") == name]
    rs = [c["r"] for c in closed if c.get("r") is not None]
    open_trade = None
    if st.trade:
        t = st.trade
        price = None
        if MT5_AVAILABLE:
            try:
                tick = mt5.symbol_info_tick(_bn(name))
                price = tick.bid if tick else None
            except Exception:
                price = None
        r = None
        if price is not None:
            risk = abs(t.entry_price - t.sl_price)
            if risk > 0:
                move = (price - t.entry_price) if t.direction == "LONG" else (t.entry_price - price)
                r = round(move / risk, 2)
        open_trade = dict(symbol=name, direction=t.direction, entry=t.entry_price, sl=t.sl_price,
                          volume=t.volume, price=price, r=r, entry_day=t.entry_day)
    return {"symbol": name, "digits": SYMBOL_PROFILES[name]["digits"], "phase": st.phase,
            "today_long_level": st.today_long_level, "today_short_level": st.today_short_level,
            "open_trade": open_trade, "hold": {"since": st.hold_since, "reason": st.hold_reason},
            "day_skipped": st.day_skipped, "orders_placed": bool(st.long_order_ticket and st.short_order_ticket), "enabled": SYMBOL_ENABLED.get(name, True), "exit_delay_min": SYMBOL_PROFILES[name].get("exit_delay_min", 0),
            "risk_pct": RISK_PCT_BY_SYMBOL.get(name),
            "trade_stats": {"trades": len(closed), "wins": sum(1 for r in rs if r > 0),
                            "win_rate": round(100 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else 0,
                            "total_r": round(sum(rs), 2), "total_pnl": round(sum(c.get("pnl") or 0 for c in closed), 2)}}


def get_status_dict():
    equity = _last_equity if _last_equity is not None else INITIAL_ACCOUNT_BALANCE
    dd = compute_overall_drawdown_status(equity)
    daily_loss_pct = compute_daily_loss_pct()
    closed = _snapshot_deque(_recent_trades)
    rs = [c["r"] for c in closed if c.get("r") is not None]
    symbols = {n: _symbol_status(n) for n in ACTIVE_SYMBOLS}
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(), "version": APP_VERSION,
        "active_symbols": list(ACTIVE_SYMBOLS), "symbols": symbols,
        "open_trades": [v["open_trade"] for v in symbols.values() if v["open_trade"]],
        "activity_log": _snapshot_deque(_activity_log)[-300:], "recent_trades": closed[-100:],
        "trade_stats": {"trades": len(closed), "wins": sum(1 for r in rs if r > 0),
                        "win_rate": round(100 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else 0,
                        "total_r": round(sum(rs), 2), "total_pnl": round(sum(c.get("pnl") or 0 for c in closed), 2)},
        "guards": {"equity": equity, "balance": _last_balance, "drawdown": dd, "daily_loss_pct": daily_loss_pct,
                  "daily_limit_pct": DAILY_LOSS_GUARD_PCT,
                  "daily_limit_dollars": round(DAILY_LOSS_GUARD_PCT / 100.0 * INITIAL_ACCOUNT_BALANCE, 2)},
        "config": {"initial_account_balance": INITIAL_ACCOUNT_BALANCE, "max_account_drawdown_pct": MAX_ACCOUNT_DRAWDOWN_PCT,
                  "max_account_drawdown_mode": MAX_ACCOUNT_DRAWDOWN_MODE, "daily_loss_guard_pct": DAILY_LOSS_GUARD_PCT,
                  "risk_pct_by_symbol": {n: v for n, v in RISK_PCT_BY_SYMBOL.items() if n in ACTIVE_SYMBOLS}, "profit_target_pct": PROFIT_TARGET_PCT,
                  "open_risk_cap_pct": OPEN_RISK_CAP_PCT, "protector_shield_pct": PROTECTOR_SHIELD_PCT,
                  "daily_loss_guard_enabled": DAILY_LOSS_GUARD_ENABLED, "max_account_drawdown_enabled": MAX_ACCOUNT_DRAWDOWN_ENABLED,
                  "news_protection_enabled": NEWS_PROTECTION_ENABLED, "news_window_before_min": NEWS_WINDOW_BEFORE_MIN,
                  "news_window_after_min": NEWS_WINDOW_AFTER_MIN},
        "entries_paused": ENTRIES_PAUSED, "presets": PRESETS, "risk": dict(_risk_snapshot),
        "news": {"enabled": NEWS_PROTECTION_ENABLED, "next_event": get_next_news_event(), "calendar_note": news_calendar_note()},
        "telegram_on": bool(_load_telegram_config().get("enabled")),
    }


_DASHBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>EMBER — daily breakout</title>
<style>
  :root { --bg:#0a0e17; --panel:#111826; --line:#232d40; --txt:#e5ecf6; --muted:#8aa0c0; --accent:#38bdf8;
          --good:#34d399; --bad:#f87171; --warn:#fbbf24; }
  * { box-sizing:border-box; }
  body { background:var(--bg); color:var(--txt); font-family:-apple-system,Segoe UI,Roboto,sans-serif; margin:0;
        padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px); }
  header { padding:16px 20px; border-bottom:1px solid var(--line); }
  header .title { font-size:18px; font-weight:600; }
  header .subtitle { color:var(--muted); font-size:12px; margin-top:2px; }
  nav { display:flex; gap:4px; padding:0 20px; border-bottom:1px solid var(--line); }
  .tab-btn { padding:10px 14px; cursor:pointer; color:var(--muted); font-size:13px; border:none; background:none; border-bottom:2px solid transparent; }
  .tab-btn.active { color:var(--accent); border-color:var(--accent); }
  main { padding:20px; max-width:1100px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:16px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; }
  .card .label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }
  .card .value { font-size:20px; font-weight:600; margin-top:4px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:16px; }
  .panel-title { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-bottom:10px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:500; font-size:11px; text-transform:uppercase; }
  tr.clickable { cursor:pointer; } tr.clickable:hover td { background:#0d1626; } tr.sel td { background:#0f2233; }
  .log { font-family:monospace; font-size:11px; max-height:380px; overflow-y:auto; color:#9fb3cc; white-space:pre-wrap; }
  .tabpage { display:none; } .tabpage.active { display:block; }
  .close-btn { background:#5c1a1a; border:1px solid #7a2424; color:#fca5a5; padding:8px 14px; border-radius:8px; cursor:pointer; font-size:13px; }
  .go-btn { background:#0f2a22; border:1px solid rgba(52,211,153,.5); color:#6ee7b7; padding:8px 14px; border-radius:8px; cursor:pointer; font-size:13px; }
  .symbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:16px; }
  .pill { background:#0d1320; border:1px solid var(--line); color:var(--txt); padding:8px 16px; border-radius:999px; cursor:pointer; font-size:13px; }
  .pill.sel { border-color:var(--accent); color:var(--accent); background:#0f2233; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; background:var(--good); }
  .dot.off { background:var(--bad); } .dot.trade { background:var(--warn); }
  #notice { position:fixed; top:12px; right:12px; max-width:480px; padding:10px 14px; border-radius:8px; font-size:12px; z-index:50; display:none; }
  #notice.ok { background:#0f2a22; border:1px solid rgba(52,211,153,.5); color:#6ee7b7; }
  #notice.error { background:#2a1414; border:1px solid rgba(248,113,113,.5); color:#fca5a5; }
  .settings-row { display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid #131a26; gap:16px; flex-wrap:wrap; }
  .settings-row:last-child { border-bottom:none; }
  .settings-row .desc { font-size:11px; color:var(--muted); margin-top:3px; max-width:480px; }
  input[type="checkbox"] { width:18px; height:18px; accent-color:var(--accent); }
  .banner { padding:10px 14px; border-radius:8px; font-size:12.5px; margin-bottom:14px; border:1px solid; }
  .banner.warn { background:#2a2110; border-color:rgba(251,191,36,.5); color:#fcd34d; }
  .banner.info { background:#102235; border-color:rgba(56,189,248,.4); color:#7dd3fc; }
  input[type="number"], select {
    background:#0d1320; border:1px solid var(--line); color:var(--txt);
    padding:6px 10px; border-radius:6px; width:90px; font-size:12px;
  }
  select#tradeFilter { width:160px; }
  .apply-btn { background:var(--accent); color:#04121f; border:none; padding:8px 18px;
    border-radius:8px; font-size:12.5px; font-weight:600; cursor:pointer; margin-top:6px; }
</style></head>
<body>
<div id="notice"></div>
<header>
  <div class="title">EMBER <span style="opacity:.5; font-size:12px; font-weight:400;">— Expansion-Move Breakout, Edge-tested, Risk-capped</span></div>
  <div class="subtitle"><b id="marketsLine"></b> · Stretch = 0.8 x ATR(10), 2x ATR stop, next-day-close exit <span id="appVersion" style="opacity:.6;"></span></div>
</header>
<nav>
  <button class="tab-btn active" data-tab="dashboard" onclick="switchTab('dashboard')">Dashboard</button>
  <button class="tab-btn" data-tab="trades" onclick="switchTab('trades')">Trades</button>
  <button class="tab-btn" data-tab="settings" onclick="switchTab('settings')">Settings</button>
</nav>
<main>
  <div id="tab-dashboard" class="tabpage active">
    <div class="cards" id="statCards"></div>
    <div class="panel"><div class="panel-title">MARKETS (click one to look at it)</div>
      <table><thead><tr><th>Market</th><th>Status</th><th>Today's levels</th><th>Open trade</th><th>Risk %</th></tr></thead><tbody id="overviewBody"></tbody></table></div>
    <div class="symbar" id="symBar"></div>
    <div class="panel"><div class="panel-title" id="todayTitle">TODAY</div><div id="todayBody"></div></div>
    <div class="panel"><div class="panel-title" id="entriesTitle">NEW ENTRIES</div><div id="entriesBody"></div></div>
    <div class="panel"><div class="panel-title" id="openTitle">OPEN TRADE</div><div id="openTradeBody"></div></div>
    <div class="panel"><div class="panel-title">ACTIVITY LOG (all markets)</div><div class="log" id="activityLog"></div></div>
  </div>
  <div id="tab-trades" class="tabpage">
    <div style="margin-bottom:12px;">Show: <select id="tradeFilter" onchange="renderTrades()"></select></div>
    <div class="cards" id="tradeStatCards"></div>
    <div class="panel"><div class="panel-title">TRADE HISTORY</div><table id="tradeHistTable"><thead><tr>
      <th>Market</th><th>Dir</th><th>Entry</th><th>Exit</th><th>SL</th><th>Vol</th><th>R</th><th>P&L</th><th>Reason</th><th>Closed</th>
    </tr></thead><tbody id="tradeHistBody"></tbody></table></div>
  </div>
  <div id="tab-settings" class="tabpage">
    <div class="panel">
      <div class="panel-title">MARKETS — what this copy trades</div>
      <div style="font-size:12.5px; color:#9fb3cc; line-height:1.6;">
        This copy trades <b id="marketsLine2"></b> together, like ORB does with its pairs; each market has its own orders, state, risk % and Stop/Start button,
        while the account guards below are shared. The default market is gold (re-tested 2018-2026 at Atlas costs: 579 trades, +0.052R a trade, z 2.8, 8 of 9 years positive).
        USDJPY (+0.02R, z 1.2 on re-test) and JPN225 were removed. All 43 Atlas instruments were screened with this
        same rule and none passed the strict bar. BTCUSD is an opt-in CANDIDATE: weaker at Atlas costs (+0.037R, z 1.4)
        and it made the Atlas results worse when added to gold; it runs only when the bot is started with it (--symbols XAUUSD BTCUSD).
        On a small account the broker's smallest lot can risk more than the risk % below on a wide-stop market (gold on a 5K account): that market
        simply places no orders that day and says why in the Activity Log, while the others carry on.
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">RISK PER MARKET</div>
      <div id="riskRows"></div>
    </div>
    <div class="panel">
      <div class="panel-title">PRESETS FOR ATLAS ACCESS (one click fills the settings and saves them)</div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button class="apply-btn" style="margin:0;" onclick="applyPreset('evaluation')">Evaluation (3% target)</button>
        <button class="apply-btn" style="margin:0; background:#fbbf24;" onclick="applyPreset('funded')">Funded (after you pass)</button>
      </div>
      <div class="desc" id="presetDesc" style="margin-top:10px; max-width:none;"></div>
    </div>
    <div class="panel">
      <div class="panel-title">COMBINED RISK — for Atlas funded accounts (Atlas Protector)</div>
      <div class="settings-row">
        <div><div>Open-risk cap %</div>
          <div class="desc">The most that everything open or waiting, in ALL markets together, may lose if every stop is hit, as a % of the starting balance. A market's lot is cut to fit what the others leave, or skipped. Blank / 0 = off. Atlas Protector closes everything at an OPEN loss of 2%, so use about 1.5 on a funded account.</div></div>
        <input type="number" id="openRiskCap" step="0.1" min="0" max="5" placeholder="off">
      </div>
      <div class="settings-row">
        <div><div>Protector shield %</div>
          <div class="desc">If the OPEN loss reaches this % of the starting balance, all positions are closed at market and no new entries are made for the rest of that market day: a little before Atlas Protector would (at 2% it closes everything, cuts your profit split to 50% for good, and a second time breaches the account). Blank / 0 = off. About 1.7 on a funded account.</div></div>
        <input type="number" id="shieldPct" step="0.1" min="0" max="5" placeholder="off">
      </div>
      <button class="apply-btn" onclick="saveSettings()">Save settings</button>
    </div>
    <div class="panel">
      <div class="panel-title">ACCOUNT GUARDS (shared by all markets)</div>
      <div class="settings-row">
        <div><div>Drawdown base balance</div>
          <div class="desc">Found automatically per account (5K, 10K, 25K, 50K...). Type a number only if your firm's starting balance is different.</div></div>
        <input type="number" id="initialBalance" step="500" min="500">
      </div>
      <div class="settings-row">
        <div><div>Max Account Drawdown %</div>
          <div class="desc">Your firm's rule (not in MT5) — e.g. 10 for a 10% limit.</div></div>
        <input type="number" id="maxDrawdownPct" step="0.5" min="1" max="50">
      </div>
      <div class="settings-row">
        <div><div>Drawdown mode</div>
          <div class="desc">Static: floor fixed at the starting balance. Trailing: floor rises with the account's own equity peak — check your dashboard's own wording before picking.</div></div>
        <select id="ddMode"><option value="static">Static</option><option value="trailing">Trailing</option></select>
      </div>
      <div class="settings-row">
        <div><div>Daily Loss Guard %</div>
          <div class="desc">Blocks new entries once today's loss reaches this % of the starting balance. Set to about 60% of your firm's daily limit.</div></div>
        <input type="number" id="dailyLossPct" step="0.1" min="0.5" max="20">
      </div>
      <div class="settings-row">
        <div><div>Profit target %</div>
          <div class="desc">Blocks new entries once closed profit reaches this % — leave blank for no target. Open trades still managed normally.</div></div>
        <input type="number" id="profitTarget" step="0.1" min="0.1" max="100" placeholder="off">
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">ENTRY GUARDS (each one cancels the waiting pending orders of every market when it trips)</div>
      <div class="settings-row">
        <div><div>Daily Loss Guard</div>
          <div class="desc">On/off. The % is above. When it trips, the day's pending orders are cancelled, not just left unplaced.</div></div>
        <input type="checkbox" id="dailyLossOn">
      </div>
      <div class="settings-row">
        <div><div>Max Drawdown Guard</div>
          <div class="desc">On/off. Stops entries (and cancels pending orders) when equity gets within 0.5% of the floor.</div></div>
        <input type="checkbox" id="maxDdOn">
      </div>
      <div class="settings-row">
        <div><div>News guard</div>
          <div class="desc">Cancels the pending orders from just before until just after a high-impact event (CPI, FOMC, ECB, BOE, NFP). If a trigger level was touched meanwhile, that touch is not traded and there is no trade that day. NOT part of the tested strategy: see the file header for what it did to the backtest.</div></div>
        <input type="checkbox" id="newsOn">
      </div>
      <div class="settings-row">
        <div><div>News window: minutes before / after</div>
          <div class="desc">ORB uses 15 and 15.</div></div>
        <div><input type="number" id="newsBefore" step="5" min="0" max="120"> <input type="number" id="newsAfter" step="5" min="0" max="120"></div>
      </div>
      <button class="apply-btn" onclick="saveSettings()">Save settings</button>
    </div>
  </div>
</main>
<script>__JS__</script>
</body></html>"""


_DASHBOARD_JS = """
let latestStatus = null, currentSymbol = null, riskRowsFor = "";
function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tabpage").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
}
function fmtMoney(v) { return v == null ? "-" : "$" + Number(v).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); }
function dig(sym) { const s = latestStatus && latestStatus.symbols[sym]; return s ? s.digits : 2; }
function px(v, sym) { return v == null ? "" : Number(v).toFixed(dig(sym)); }
function showNotice(text, kind) {
  const el = document.getElementById("notice");
  el.className = kind; el.textContent = text; el.style.display = "block";
  clearTimeout(window._nt); window._nt = setTimeout(() => el.style.display = "none", kind === "error" ? 12000 : 7000);
}
function post(url, obj) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) }).then(r => r.json());
}
function selectSymbol(s) { currentSymbol = s; if (latestStatus) render(latestStatus); }
function closeNow(sym) {
  if (!confirm("Close the open " + sym + " trade at market right now?\\n\\nThis cannot be undone.")) return;
  post("/close", { symbol: sym }).then(res => {
    if (!res.ok) { showNotice("Could not close: " + (res.error || "unknown error"), "error"); return; }
    showNotice("Close requested — within about 15 seconds.", "ok"); poll(true);
  }).catch(e => showNotice("Could not reach the bot: " + e, "error"));
}
function setPaused(v) {
  post("/control", { entries_paused: v }).then(res => {
    if (res.rejected && res.rejected.length) { showNotice("Not changed: " + res.rejected.join("; "), "error"); return; }
    showNotice(v ? "Entries paused for ALL markets: waiting pending orders are cancelled within about 15 seconds." : "Entries resumed.", "ok"); poll(true);
  }).catch(e => showNotice("Could not reach the bot: " + e, "error"));
}
function setSymbolEnabled(sym, on) {
  const o = {}; o["enabled__" + sym] = on;
  post("/control", o).then(res => {
    if (res.rejected && res.rejected.length) { showNotice("Not changed: " + res.rejected.join("; "), "error"); return; }
    showNotice(on ? sym + " started." : sym + " stopped: its waiting orders are cancelled within about 15 seconds; an open trade is still managed.", "ok"); poll(true);
  }).catch(e => showNotice("Could not reach the bot: " + e, "error"));
}
function statusText(S, paused) {
  if (S.open_trade) return "In trade (" + S.open_trade.direction + ")";
  if (!S.enabled) return "Stopped";
  if (paused) return "Paused";
  if (S.hold && S.hold.since) return "On hold";
  if (S.day_skipped) return "No trade today";
  if (S.orders_placed) return "Orders waiting";
  return S.today_long_level != null ? "Levels set, NO orders (see log)" : "Waiting";
}
function renderOverview(status) {
  document.getElementById("overviewBody").innerHTML = status.active_symbols.map(n => {
    const S = status.symbols[n], ot = S.open_trade;
    const dot = !S.enabled ? "off" : (ot ? "trade" : "");
    const lv = S.today_long_level != null ? "↑ " + px(S.today_long_level, n) + " &nbsp; ↓ " + px(S.today_short_level, n) : "-";
    const tr = ot ? ot.direction + " " + (ot.r != null ? (ot.r >= 0 ? "+" : "") + ot.r.toFixed(2) + "R" : "") : "-";
    return "<tr class='clickable " + (n === currentSymbol ? "sel" : "") + "' onclick=\\"selectSymbol('" + n + "')\\"><td><span class='dot " + dot + "'></span><b>" + n + "</b></td><td>" +
      statusText(S, status.entries_paused) + "</td><td>" + lv + "</td><td>" + tr + "</td><td>" + (S.risk_pct != null ? S.risk_pct : "") + "</td></tr>";
  }).join("");
}
function renderSymbolBar(status) {
  const pills = status.active_symbols.map(n => "<button class='pill " + (n === currentSymbol ? "sel" : "") + "' onclick=\\"selectSymbol('" + n + "')\\">" + n + "</button>").join("");
  const S = status.symbols[currentSymbol];
  const btn = S.enabled
    ? "<button class='close-btn' onclick=\\"setSymbolEnabled('" + currentSymbol + "', false)\\">■ Stop " + currentSymbol + "</button>"
    : "<button class='go-btn' onclick=\\"setSymbolEnabled('" + currentSymbol + "', true)\\">▶ Start " + currentSymbol + "</button>";
  document.getElementById("symBar").innerHTML = pills + btn;
}
function renderEntries(status) {
  const S = status.symbols[currentSymbol], h = S.hold || {};
  let line, cls = "info";
  if (!S.enabled) { line = "■ <b>" + currentSymbol + " is STOPPED</b> from the dashboard. No new orders for it; an open trade is still managed. The other markets carry on."; cls = "warn"; }
  else if (status.entries_paused) { line = "⏸ <b>PAUSED</b> from the dashboard (all markets). No new orders; open trades are still managed."; cls = "warn"; }
  else if (h.since) { line = "⏸ <b>ON HOLD</b>: " + h.reason + " (since " + h.since.slice(11, 16) + " UTC). Pending orders cancelled; they return when it clears."; cls = "warn"; }
  else if (S.day_skipped) { line = "⏭ <b>No trade today</b>: a trigger level was touched while entries were on hold, and that first touch is not traded."; cls = "warn"; }
  else { line = "Active. Orders go in when the day's levels are set."; }
  const n = status.news || {};
  let news = n.enabled ? "News guard <b>ON</b>" : "News guard <b>OFF</b>";
  if (n.next_event) news += " · next event: " + n.next_event.name + " " + n.next_event.time.slice(0, 16).replace("T", " ") + " UTC";
  const note = n.calendar_note ? "<div style='color:#fcd34d; margin-top:6px;'>⚠ " + n.calendar_note + "</div>" : "";
  const tg = status.telegram_on ? "Telegram alerts <b>on</b>" : "Telegram alerts <b>not set up</b> (put ember_telegram_config.json or orb_telegram_config.json next to this file)";
  const btn = status.entries_paused
    ? "<button class='apply-btn' onclick='setPaused(false)'>▶ Resume all entries</button>"
    : "<button class='close-btn' onclick='setPaused(true)'>⏸ Pause ALL new entries</button>";
  document.getElementById("entriesBody").innerHTML =
    "<div class='banner " + cls + "'>" + line + "</div>" +
    "<div style='display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;'><div style='font-size:12px; color:#9fb3cc;'>" + news + "<br>" + tg + "</div>" + btn + "</div>" + note;
}
function buildRiskRows(status) {
  const key = status.active_symbols.join(",");
  if (key === riskRowsFor) return;
  riskRowsFor = key;
  document.getElementById("riskRows").innerHTML = status.active_symbols.map(n => `
    <div class="settings-row">
      <div><div>${n}: risk % per trade</div>
        <div class="desc">% of account equity risked per ${n} trade (stop distance = 2x ATR(10)). If the broker's smallest lot would risk more than 1.5x this (small accounts), ${n} places no orders that day instead of over-risking.</div></div>
      <input type="number" id="risk_${n}" step="0.05" min="0.05" max="5">
    </div>`).join("") + "<button class='apply-btn' onclick='saveSettings()'>Save settings</button>";
}
function populateSettings(cfg, status) {
  buildRiskRows(status);
  if (document.activeElement && document.activeElement.closest("#tab-settings")) return;  // huwag guluhin habang nagta-type
  status.active_symbols.forEach(n => { document.getElementById("risk_" + n).value = cfg.risk_pct_by_symbol[n]; });
  document.getElementById("dailyLossOn").checked = !!cfg.daily_loss_guard_enabled;
  document.getElementById("maxDdOn").checked = !!cfg.max_account_drawdown_enabled;
  document.getElementById("newsOn").checked = !!cfg.news_protection_enabled;
  document.getElementById("newsBefore").value = cfg.news_window_before_min;
  document.getElementById("newsAfter").value = cfg.news_window_after_min;
  document.getElementById("initialBalance").value = cfg.initial_account_balance;
  document.getElementById("maxDrawdownPct").value = cfg.max_account_drawdown_pct;
  document.getElementById("ddMode").value = cfg.max_account_drawdown_mode;
  document.getElementById("dailyLossPct").value = cfg.daily_loss_guard_pct;
  document.getElementById("profitTarget").value = cfg.profit_target_pct != null ? cfg.profit_target_pct : "";
  document.getElementById("openRiskCap").value = cfg.open_risk_cap_pct ? cfg.open_risk_cap_pct : "";
  document.getElementById("shieldPct").value = cfg.protector_shield_pct ? cfg.protector_shield_pct : "";
  const P = status.presets;
  const d = p => "risk " + Object.keys(p).filter(k => k.startsWith("risk_pct__")).map(k => p[k])[0] + "% per market, drawdown " + p.max_account_drawdown_pct + "% " + p.max_account_drawdown_mode + ", daily guard " + p.daily_loss_guard_pct + "%, " + (p.profit_target_pct ? "target " + p.profit_target_pct + "%" : "no target") + (p.open_risk_cap_pct ? ", open-risk cap " + p.open_risk_cap_pct + "%" : ", no cap") + (p.protector_shield_pct ? ", shield " + p.protector_shield_pct + "%" : "");
  document.getElementById("presetDesc").innerHTML = "<b>Evaluation:</b> " + d(P.evaluation) + ".<br><b>Funded:</b> " + d(P.funded) + ".<br>Funded accounts have tighter limits (6% drawdown, 3% daily, Atlas Protector at 2%): switch to Funded after you pass.";
}
function applyPreset(name) {
  const p = latestStatus.presets[name];
  const lines = Object.keys(p).map(k => k + " = " + p[k]).join("\\n");
  if (!confirm("Apply the " + name.toUpperCase() + " preset? It replaces your current values for these settings:\\n\\n" + lines)) return;
  post("/control", p).then(res => {
    if (res.rejected && res.rejected.length) { showNotice("Not applied: " + res.rejected.join("; "), "error"); return; }
    showNotice(name + " preset applied.", "ok");
    if (document.activeElement) document.activeElement.blur();
    poll();
  }).catch(e => showNotice("Could not reach the bot: " + e, "error"));
}
function saveSettings() {
  const body = {
    initial_account_balance: parseFloat(document.getElementById("initialBalance").value),
    max_account_drawdown_pct: parseFloat(document.getElementById("maxDrawdownPct").value),
    max_account_drawdown_mode: document.getElementById("ddMode").value,
    daily_loss_guard_pct: parseFloat(document.getElementById("dailyLossPct").value),
    daily_loss_guard_enabled: document.getElementById("dailyLossOn").checked,
    max_account_drawdown_enabled: document.getElementById("maxDdOn").checked,
    news_protection_enabled: document.getElementById("newsOn").checked,
    news_window_before_min: parseFloat(document.getElementById("newsBefore").value),
    news_window_after_min: parseFloat(document.getElementById("newsAfter").value),
  };
  latestStatus.active_symbols.forEach(n => { body["risk_pct__" + n] = parseFloat(document.getElementById("risk_" + n).value); });
  const pt = document.getElementById("profitTarget").value;
  body.profit_target_pct = pt === "" ? 0 : parseFloat(pt);          // blank = no target
  body.open_risk_cap_pct = parseFloat(document.getElementById("openRiskCap").value) || 0;
  body.protector_shield_pct = parseFloat(document.getElementById("shieldPct").value) || 0;
  post("/control", body).then(res => {
    if (res.rejected && res.rejected.length) { showNotice("Not saved: " + res.rejected.join("; "), "error"); return; }
    showNotice("Settings saved.", "ok"); poll(true);
  }).catch(e => showNotice("Could not reach the bot: " + e, "error"));
}
function renderTrades() {
  const status = latestStatus; if (!status) return;
  const sel = document.getElementById("tradeFilter"), want = sel.value || "ALL";
  const rows = status.recent_trades.filter(t => want === "ALL" || (t.symbol || "XAUUSD") === want);
  const rs = rows.filter(t => t.r != null).map(t => t.r);
  const wins = rs.filter(r => r > 0).length, totR = rs.reduce((a, b) => a + b, 0), totP = rows.reduce((a, t) => a + (t.pnl || 0), 0);
  document.getElementById("tradeStatCards").innerHTML = `
    <div class="card"><div class="label">Total trades</div><div class="value">${rows.length}</div></div>
    <div class="card"><div class="label">Win rate</div><div class="value">${rs.length ? (100 * wins / rs.length).toFixed(1) : 0}%</div></div>
    <div class="card"><div class="label">Total R</div><div class="value">${totR >= 0 ? "+" : ""}${totR.toFixed(2)}R</div></div>
    <div class="card"><div class="label">Total P&L</div><div class="value">${fmtMoney(totP)}</div></div>`;
  document.getElementById("tradeHistBody").innerHTML = rows.slice().reverse().map(t => { const s = t.symbol || "XAUUSD"; return `
    <tr><td>${s}</td><td>${t.direction}</td><td>${px(t.entry, s)}</td><td>${px(t.exit, s)}</td>
    <td>${px(t.sl, s)}</td><td>${t.volume ?? ""}</td>
    <td>${t.r != null ? (t.r >= 0 ? "+" : "") + t.r.toFixed(2) : ""}</td><td>${fmtMoney(t.pnl)}</td><td>${t.reason ?? ""}</td>
    <td>${(t.closed_at || "").slice(0, 16).replace("T", " ")}</td></tr>`; }).join("");
}
function render(status) {
  latestStatus = status;
  if (!currentSymbol || !status.symbols[currentSymbol]) currentSymbol = status.active_symbols[0];
  const names = status.active_symbols.join(" + ");
  document.getElementById("marketsLine").textContent = names;
  document.getElementById("marketsLine2").textContent = names;
  document.title = "EMBER — " + names;
  document.getElementById("appVersion").textContent = "v" + status.version;
  populateSettings(status.config, status);
  const sel = document.getElementById("tradeFilter");
  if (sel.options.length !== status.active_symbols.length + 1) {
    sel.innerHTML = "<option value='ALL'>All markets</option>" + status.active_symbols.map(n => "<option value='" + n + "'>" + n + "</option>").join("");
  }
  const g = status.guards, dd = g.drawdown, S = status.symbols[currentSymbol], open = status.open_trades.length;
  // g.daily_loss_pct is a LOSS (positive = loss, negative = profit); shown here as a P&L so that a profit reads as +, not as a negative "loss".
  const dl = g.daily_loss_pct, dlim = g.daily_limit_pct, acctSize = status.config.initial_account_balance;
  const pnlColor = dl == null ? "" : (dlim && dl >= dlim ? "#f87171" : (dlim && dl >= dlim * 0.7 ? "#fbbf24" : (dl < 0 ? "#34d399" : "")));
  const pnlTxt = dl == null ? "-" : ((dl < 0 ? "+" : (dl > 0 ? "-" : "")) + Math.abs(dl).toFixed(2) + "%");
  const pnlSub = dl == null ? "" : ((dl < 0 ? "profit +" : (dl > 0 ? "loss -" : "break-even ")) + (dl === 0 ? "" : fmtMoney(Math.abs(dl) / 100 * acctSize)) + (dlim ? " · daily guard " + dlim + "%" : ""));
  document.getElementById("statCards").innerHTML = `
    <div class="card"><div class="label">EQUITY</div><div class="value">${fmtMoney(g.equity)}</div></div>
    <div class="card"><div class="label">REMAINING TO FLOOR</div><div class="value">${fmtMoney(dd.remaining_to_floor_dollars)}</div></div>
    <div class="card"><div class="label">TODAY'S P&L</div><div class="value" style="color:${pnlColor}">${pnlTxt}</div><div style="font-size:11px; color:#8aa0c0; margin-top:3px;">${pnlSub}</div></div>
    <div class="card"><div class="label">OPEN TRADES</div><div class="value">${open} <span style="font-size:13px; color:#8aa0c0;">of ${status.active_symbols.length} markets</span></div></div>
    <div class="card"><div class="label">OPEN RISK (if all stops hit)</div><div class="value">${(status.risk.open_risk_pct || 0).toFixed(2)}%</div><div style="font-size:11px; color:#8aa0c0; margin-top:3px;">${status.config.open_risk_cap_pct ? "cap " + status.config.open_risk_cap_pct + "%" : "no cap"}${status.risk.open_loss_pct != null ? " · open loss now " + status.risk.open_loss_pct.toFixed(2) + "%" + (status.config.protector_shield_pct ? " (shield " + status.config.protector_shield_pct + "%)" : "") : ""}</div></div>`;
  renderOverview(status);
  renderSymbolBar(status);
  document.getElementById("todayTitle").textContent = "TODAY — " + currentSymbol;
  document.getElementById("entriesTitle").textContent = "NEW ENTRIES — " + currentSymbol;
  document.getElementById("openTitle").textContent = "OPEN TRADE — " + currentSymbol;
  renderEntries(status);
  document.getElementById("todayBody").innerHTML = S.today_long_level != null ? `
    <div>LONG above <b>${px(S.today_long_level, currentSymbol)}</b> &nbsp;|&nbsp; SHORT below <b>${px(S.today_short_level, currentSymbol)}</b></div>` :
    `<div class="desc" style="color:#8aa0c0;">Waiting for enough daily history, or not enough ATR data yet.</div>`;
  const ot = S.open_trade;
  document.getElementById("openTradeBody").innerHTML = ot ? `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div><b>${ot.direction}</b> entry ${px(ot.entry, currentSymbol)} sl ${px(ot.sl, currentSymbol)} vol ${ot.volume} (opened ${ot.entry_day})
        &nbsp; ${ot.r != null ? (ot.r >= 0 ? "+" : "") + ot.r.toFixed(2) + "R" : ""}</div>
      <button class="close-btn" onclick="closeNow('${currentSymbol}')">✕ Close ${currentSymbol} now</button>
    </div>${S.exit_delay_min ? `<div class="desc" style="margin-top:8px;">When due, this trade closes ${S.exit_delay_min} minutes after the broker midnight (not at it), to avoid the rollover spread.</div>` : ""}` : `<div style="color:#8aa0c0;">No open ${currentSymbol} trade — scanning.</div>`;
  document.getElementById("activityLog").textContent = status.activity_log.slice().reverse().join("\\n");
  renderTrades();
}
async function poll() {
  try { const r = await fetch("/status"); render(await r.json()); } catch (e) { console.error(e); }
}
(function loop() { poll().finally(() => setTimeout(loop, 5000)); })();
"""


# ============================================================
# HTTP SERVER
# ============================================================
_SETTING_RULES = {
    "initial_account_balance": ("float", 100, 100000000, "Drawdown base balance"),
    "max_account_drawdown_pct": ("float", 0.5, 50, "Max drawdown %"),
    "daily_loss_guard_pct": ("float", 0.1, 20, "Daily Loss Guard %"),
    "risk_pct": ("float", 0.05, 5, "Risk % per trade"),
    "profit_target_pct": ("float", 0, 100, "Profit target % (0 = none)"),
    "open_risk_cap_pct": ("float", 0, 5, "Open-risk cap % (0 = off)"),
    "protector_shield_pct": ("float", 0, 5, "Protector shield % (0 = off)"),
    "news_window_before_min": ("float", 0, 120, "News window before (min)"),
    "news_window_after_min": ("float", 0, 120, "News window after (min)"),
    "daily_loss_guard_enabled": ("bool", None, None, "Daily Loss Guard"),
    "max_account_drawdown_enabled": ("bool", None, None, "Max Drawdown Guard"),
    "news_protection_enabled": ("bool", None, None, "News guard"),
    "entries_paused": ("bool", None, None, "Pause new entries"),
}
for _n in SYMBOL_PROFILES:
    _SETTING_RULES[f"risk_pct__{_n}"] = ("float", 0.05, 5, f"{_n} risk %")
    _SETTING_RULES[f"enabled__{_n}"] = ("bool", None, None, f"{_n} trading")


def _validate_control(control):
    clean, rejected = {}, []
    for k, v in control.items():
        if k in _SETTING_RULES:
            kind, lo, hi, label = _SETTING_RULES[k]
            if kind == "bool":
                if isinstance(v, bool) or v in (0, 1):
                    clean[k] = bool(v)
                else:
                    rejected.append(f"{label}: must be on or off")
                continue
            try:
                x = float(v)
                if not math.isfinite(x):
                    raise ValueError
            except (TypeError, ValueError):
                rejected.append(f"{label}: enter a number")
                continue
            if not lo <= x <= hi:
                rejected.append(f"{label}: {x:g} outside {lo:g}-{hi:g}")
                continue
            clean[k] = x
        elif k == "max_account_drawdown_mode" and v in ("static", "trailing"):
            clean[k] = v
    return clean, rejected


def load_control():
    global INITIAL_ACCOUNT_BALANCE, MAX_ACCOUNT_DRAWDOWN_PCT, DAILY_LOSS_GUARD_PCT
    global PROFIT_TARGET_PCT, MAX_ACCOUNT_DRAWDOWN_MODE, ENTRIES_PAUSED, NEWS_PROTECTION_ENABLED
    global NEWS_WINDOW_BEFORE_MIN, NEWS_WINDOW_AFTER_MIN, DAILY_LOSS_GUARD_ENABLED, MAX_ACCOUNT_DRAWDOWN_ENABLED
    global OPEN_RISK_CAP_PCT, PROTECTOR_SHIELD_PCT
    control = _read_control_file()
    if "initial_account_balance" in control:
        INITIAL_ACCOUNT_BALANCE = float(control["initial_account_balance"])
    if "max_account_drawdown_pct" in control:
        MAX_ACCOUNT_DRAWDOWN_PCT = float(control["max_account_drawdown_pct"])
    if "max_account_drawdown_mode" in control:
        MAX_ACCOUNT_DRAWDOWN_MODE = control["max_account_drawdown_mode"]
    if "daily_loss_guard_pct" in control:
        DAILY_LOSS_GUARD_PCT = float(control["daily_loss_guard_pct"])
    if "risk_pct" in control:                      # the single risk % of the one-market EMBER: the default for every market...
        for _n in RISK_PCT_BY_SYMBOL:
            RISK_PCT_BY_SYMBOL[_n] = float(control["risk_pct"])
    for _n in SYMBOL_PROFILES:                     # ...unless a market has its own
        if f"risk_pct__{_n}" in control:
            RISK_PCT_BY_SYMBOL[_n] = float(control[f"risk_pct__{_n}"])
        if f"enabled__{_n}" in control:
            SYMBOL_ENABLED[_n] = bool(control[f"enabled__{_n}"])
    # (RISK_PCT itself is set by apply_symbol() when each market's turn comes: setting it here, on the web thread, could clash with a poll)
    if "profit_target_pct" in control:
        PROFIT_TARGET_PCT = float(control["profit_target_pct"]) or None        # 0 = no target
    if "open_risk_cap_pct" in control:
        OPEN_RISK_CAP_PCT = float(control["open_risk_cap_pct"])
    if "protector_shield_pct" in control:
        PROTECTOR_SHIELD_PCT = float(control["protector_shield_pct"])
    if "news_window_before_min" in control:
        NEWS_WINDOW_BEFORE_MIN = int(control["news_window_before_min"])
    if "news_window_after_min" in control:
        NEWS_WINDOW_AFTER_MIN = int(control["news_window_after_min"])
    if "daily_loss_guard_enabled" in control:
        DAILY_LOSS_GUARD_ENABLED = bool(control["daily_loss_guard_enabled"])
    if "max_account_drawdown_enabled" in control:
        MAX_ACCOUNT_DRAWDOWN_ENABLED = bool(control["max_account_drawdown_enabled"])
    if "news_protection_enabled" in control:
        NEWS_PROTECTION_ENABLED = bool(control["news_protection_enabled"])
    if "entries_paused" in control:
        ENTRIES_PAUSED = bool(control["entries_paused"])


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        # The browser closed or reloaded the page (or a tab went to sleep) while this answer was being written. Nothing is wrong
        # and there is nobody left to answer, so ignore it — it used to print a long traceback each time.
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _authorized(self) -> bool:
        ok, code, wait = check_auth(self.headers.get("Authorization"), self.client_address[0])
        if ok:
            return True
        body = (b"Too many wrong tries. Wait and try again." if code == 429 else b"Password required.")
        self.send_response(code)
        if code == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="EMBER Dashboard", charset="UTF-8"')
        if code == 429:
            self.send_header("Retry-After", str(wait))
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return False

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._authorized():
            return
        if self.path == "/" or self.path.startswith("/?"):
            body = _DASHBOARD_HTML.replace("__JS__", _DASHBOARD_JS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/status":
            try:
                self._send_json(get_status_dict())
            except Exception as e:
                self._send_json({"error": f"{type(e).__name__}: {e}"}, code=500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self._authorized():
            return
        if self.path == "/control":
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self._send_json({"ok": False, "error": "Content-Type must be application/json"}, code=415)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                control = json.loads(raw)
            except Exception:
                control = {}
            clean, rejected = _validate_control(control if isinstance(control, dict) else {})
            if clean:
                _save_control(clean)
                load_control()
            self._send_json({"ok": not rejected, "rejected": rejected})
        elif self.path == "/close":
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self._send_json({"ok": False, "error": "Content-Type must be application/json"}, code=415)
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length)) if length else {}
            except Exception:
                body = {}
            name = body.get("symbol") if isinstance(body, dict) else None
            if name is None and len(ACTIVE_SYMBOLS) == 1:
                name = ACTIVE_SYMBOLS[0]
            if name not in ACTIVE_SYMBOLS:
                self._send_json({"ok": False, "error": "say which market to close (symbol)"}, code=400)
            elif _states[name].trade is None:
                self._send_json({"ok": False, "error": f"no open {name} trade right now"}, code=409)
            else:
                _states[name].close_requested = True
                _log("Close requested from the dashboard — will close at market on the next poll (within ~15s).", sym=name)
                self._send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()


# ============================================================
# BOT LOOP
# ============================================================
_stop_event = threading.Event()
_startup_done = False
_MT5_PATH = None


def _announce_candidates():
    for n in ACTIVE_SYMBOLS:
        if n in CANDIDATE_NOTES:
            _log(f"{n}: {CANDIDATE_NOTES[n]}", sym=n)


def _startup_restore():
    global _startup_done
    if _startup_done:
        return
    _startup_done = True
    _log(f"EMBER app version {APP_VERSION}")
    _announce_candidates()
    _load_trade_history()
    restore_state()
    load_control()


def bot_loop():
    _startup_restore()
    while not _stop_event.is_set():
        if not MT5_AVAILABLE:
            _stop_event.wait(5)
            continue
        try:
            ok = mt5.initialize(path=_MT5_PATH) if _MT5_PATH else mt5.initialize()
            if not ok:
                _warn_once("mt5init", f"MT5 connect failed: {mt5.last_error()}", every=30)
                _stop_event.wait(5)
                continue
            info = mt5.terminal_info()
            if info is None or not getattr(info, "trade_allowed", True):
                _warn_once("mt5trade", "MT5 connected but Algo Trading / Trade is not allowed.", every=60)
            acct = mt5.account_info()
            if acct and _last_login != getattr(acct, "login", None):
                _log(f"MT5 connected. Terminal: {getattr(info, 'name', '?')} | Account: {acct.login} | "
                    f"Trade allowed: {getattr(info, 'trade_allowed', True)}")
                _check_account_identity(acct.login)
                for _n in ACTIVE_SYMBOLS:
                    use_symbol(_n)
                    verify_symbol()
                _no_symbol()
                use_symbol(ACTIVE_SYMBOLS[0]); _broker_offset_seconds(); _no_symbol()
                _resolve_account_base()
                refresh_daily_pnl(force=True)
        except Exception as e:
            _warn_once("mt5loop", f"MT5 connection error: {e}", every=30)
            _stop_event.wait(5)
            continue
        try:
            refresh_daily_pnl()
            poll_all()
        except Exception as e:
            _log(f"Poll error (bot keeps running): {type(e).__name__}: {e}")
        _stop_event.wait(15)


def _shutdown_bot(server, bot_thread):
    _stop_event.set()
    try:
        server.server_close()
    except Exception:
        pass
    bot_thread.join(timeout=20)
    save_state()
    if MT5_AVAILABLE:
        try:
            mt5.shutdown()
        except Exception:
            pass
    open_now = [f"{n} {_states[n].trade.direction} #{_states[n].trade.ticket}" for n in ACTIVE_SYMBOLS if _states[n].trade]
    status = "no open trade" if not open_now else f"{', '.join(open_now)} stay(s) open with its SL"
    print(f"Stopped. {status}. The next start takes it over again.")


def run_dashboard():
    # Claim the port FIRST, same fix orb_app.py got — a second copy on a port already in use must not
    # touch MT5 or trade before failing to bind.
    if not _is_loopback(DASHBOARD_HOST) and not auth_enabled():
        print(f"\nCANNOT START: --host {DASHBOARD_HOST} would let anyone who can reach this machine press Close, Pause or change the Settings.\n"
              f"Set a dashboard password first:   py ember_app.py --set-password\nThen start again. Nothing was started and no trade was touched.")
        sys.exit(0)
    try:
        server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler)
    except OSError as e:
        print(f"\nCANNOT START: port {DASHBOARD_PORT} is already in use ({e}).\n"
              f"Another copy of the bot is probably running on it. Give this one its own port, e.g. "
              f"--port {DASHBOARD_PORT + 1}.\nNothing was started and no trade was touched.")
        sys.exit(0)
    _startup_restore()
    _log(f"Dashboard on {DASHBOARD_HOST}:{DASHBOARD_PORT} | password protection {'ON' if auth_enabled() else 'off (this machine only)'} | log file {os.path.basename(_log_file_path())}")
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    print(f"EMBER dashboard running at http://localhost:{DASHBOARD_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping (Ctrl+C)...")
    finally:
        _shutdown_bot(server, bot_thread)


def _supervise():
    args = sys.argv[1:]
    while True:
        proc = subprocess.Popen([sys.executable, __file__, "--child"] + args)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            if os.name != "nt":
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass
            try:
                proc.wait(timeout=30)
            except Exception:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
            return
        if code == 0:
            return
        print(f"Bot exited with code {code}, restarting in 5s...")
        time.sleep(5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", choices=sorted(SYMBOL_PROFILES), default=None,
                    help="markets to trade (default: all of them, in this one copy). Only markets that passed the test are listed.")
    ap.add_argument("--symbol", choices=sorted(SYMBOL_PROFILES), default=None,
                    help="same as --symbols with a single market (kept so the earlier one-market command lines still work)")
    ap.add_argument("--port", type=int, default=8710)
    ap.add_argument("--label", default="")
    ap.add_argument("--mt5-path", default=None)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--host", default=None)
    ap.add_argument("--balance", type=float, default=None)
    ap.add_argument("--risk", type=float, default=None)
    ap.add_argument("--symbol-risk", nargs="*", default=None, metavar="SYMBOL=PCT",
                    help="risk %% for one market, e.g. --symbol-risk BTCUSD=0.5 (applied after --preset and --risk)")
    ap.add_argument("--max-dd", type=float, default=None)
    ap.add_argument("--dd-mode", choices=["static", "trailing"], default=None)
    ap.add_argument("--daily-loss", type=float, default=None)
    ap.add_argument("--profit-target", type=float, default=None)
    ap.add_argument("--preset", choices=sorted(PRESETS), default=None,
                    help="fill every Atlas Access setting for the evaluation or the funded stage (risk, drawdown, daily guard, target, open-risk cap, "
                         "Protector shield). Applied at every start, before any other option, which then overrides it.")
    ap.add_argument("--open-risk-cap", type=float, default=None, help="combined planned risk of all open/waiting trades, %% of the base balance (0 = off)")
    ap.add_argument("--protector-shield", type=float, default=None, help="close everything when the open loss reaches this %% of the base balance (0 = off)")
    ap.add_argument("--set-password", action="store_true", help="set (or clear) the dashboard password, then exit")
    ap.add_argument("--no-supervise", action="store_true")
    ap.add_argument("--child", action="store_true")
    args = ap.parse_args()
    if args.set_password:
        _cli_set_password()
        sys.exit(0)

    ACTIVE_SYMBOLS = list(dict.fromkeys(args.symbols or ([args.symbol] if args.symbol else list(DEFAULT_SYMBOLS))))
    use_symbol(ACTIVE_SYMBOLS[0])
    _no_symbol()
    DASHBOARD_PORT = args.port
    ACCOUNT_LABEL = args.label
    SYMBOL_SUFFIX = args.suffix
    _MT5_PATH = args.mt5_path
    if args.host:
        DASHBOARD_HOST = args.host
    _cli_keys = []
    if args.preset:
        _save_control(PRESETS[args.preset])
    if args.balance is not None:
        INITIAL_ACCOUNT_BALANCE = args.balance
        _BALANCE_SET_BY_CLI = True
        _cli_keys.append("initial_account_balance")
    if args.risk is not None:
        for _n in RISK_PCT_BY_SYMBOL:
            RISK_PCT_BY_SYMBOL[_n] = args.risk
        RISK_PCT = args.risk
        _cli_keys += ["risk_pct"] + [f"risk_pct__{_n}" for _n in SYMBOL_PROFILES]
    if args.symbol_risk:
        for _item in args.symbol_risk:
            _n, _, _v = _item.partition("=")
            if _n not in SYMBOL_PROFILES or not _v:
                ap.error(f"--symbol-risk {_item}: use SYMBOL=PCT with SYMBOL one of {', '.join(sorted(SYMBOL_PROFILES))}")
            RISK_PCT_BY_SYMBOL[_n] = float(_v)
            _cli_keys.append(f"risk_pct__{_n}")
    if args.max_dd is not None:
        MAX_ACCOUNT_DRAWDOWN_PCT = args.max_dd
        _cli_keys.append("max_account_drawdown_pct")
    if args.dd_mode is not None:
        MAX_ACCOUNT_DRAWDOWN_MODE = args.dd_mode
    if args.daily_loss is not None:
        DAILY_LOSS_GUARD_PCT = args.daily_loss
        _cli_keys.append("daily_loss_guard_pct")
    if args.profit_target is not None:
        PROFIT_TARGET_PCT = args.profit_target or None
        _cli_keys.append("profit_target_pct")
    if args.open_risk_cap is not None:
        OPEN_RISK_CAP_PCT = args.open_risk_cap
        _cli_keys.append("open_risk_cap_pct")
    if args.protector_shield is not None:
        PROTECTOR_SHIELD_PCT = args.protector_shield
        _cli_keys.append("protector_shield_pct")
    if _cli_keys:
        try:
            saved = _read_control_file()
            changed = False
            for k in _cli_keys:
                if k in saved:
                    del saved[k]
                    changed = True
            if changed:
                with open(_control_path(), "w") as f:
                    json.dump(saved, f)
        except Exception:
            pass

    if args.child or args.no_supervise:
        run_dashboard()
    else:
        _supervise()
