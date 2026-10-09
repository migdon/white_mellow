"""
NBRO — Noise-Band Risk-Optimizer  (NAS100 + SPX500)
=====================================================
The Noise Area strategy, in the BRO family: same prop-firm guards and risk handling as BRO/ORB.
Strategy: a day-trading momentum bot for the US cash session, built on the "Noise Area" idea of Zarattini, Aziz and Barbon
("Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", 2024). When price leaves the area of normal
intraday movement the day tends to trend, so the bot rides it and gets out when the trend loses its footing. My own reconstruction of the
paper's rules (the exact formulas were not readable when this was built), tested on NAS100 and SPX500 CFD data:

  every 30 minutes from 10:00 to 15:30 New York time:
    sigma(t)  = average, over the previous 14 sessions, of |price at t / price at the 09:30 open - 1|
    UPPER     = max(today's open, yesterday's close) x (1 + sigma(t))        LOWER = min(open, yesterday's close) x (1 - sigma(t))
    VWAP      = volume-weighted average price since the 09:30 open
    flat      : price above UPPER -> go LONG;  price below LOWER -> go SHORT
    in a trade: LONG exits when price falls below min(UPPER, VWAP); SHORT exits when price rises above max(LOWER, VWAP)   (the "loose" exit, called X2 in the tests)
    everything is closed at 15:55 New York (the open of the last 5-minute bar).  After an exit the bot may enter again at a later check.
  PLUS (new, for live use): a hard emergency stop at the BROKER, 1.0% of the entry price away, so a crash of the bot, the PC or the internet can never leave a trade without a stop.

EVIDENCE (read this before trusting it; full numbers in README_NOISE.md):
  NAS100 2019-2026 (first sample): 1,346 trades, +0.051% per trade after costs, z 2.55, Sharpe 0.97 -- missed the pre-set bar (z 2.6) by a hair, so officially "no edge".
  NAS100 2012-2018 (fresh sample): 1,276 trades, +0.034%, z 2.25, Sharpe 0.85, positive both ways -- confirmed for NAS100.
  SPX500 2019-2026: +0.036%, z 2.49, Sharpe 0.94.   US30 (not used): -0.007%, no edge.   => the pre-registered confirmation FAILED as a whole (US30), so this bot is a CANDIDATE:
  run it on demo / the evaluation with small size and judge it forward in time, not by the backtest.

This is a SINGLE FILE like orb_app.py (engine, guards, Telegram, dashboard). It was built from orb_app.py v28: the prop-firm guards, the account-size
detection, the dashboard, the restart safety (state file, take-over of open positions) and the order handling are the same code; only the strategy is new.

Usage:
    python nbro_app.py --port 8777 --label Atlas1 --plan 5-10 --dd-mode trailing --profit-target 3 --suffix ""
    python nbro_app.py --console        # no dashboard
"""

import calendar
import math
import json
import os
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field, asdict, fields as dc_fields
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Optional, List, Dict

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


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

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


# --- Telegram notifications. Config lives in a separate small JSON file
# (TELEGRAM_CONFIG_FILE, not this source file) so the bot token isn't
# sitting in version-controlled code — same pattern as HACVD's own
# hacvd_telegram_config.json. Set it up once with set_telegram_alerts.py.
TELEGRAM_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "nbro_telegram_config.json")


@lru_cache(maxsize=1)
def _load_telegram_config_cached(_cache_bust: float) -> dict:
    """_cache_bust exists so callers can force a fresh read (pass
    time.time()) without a real cache-invalidation mechanism — config
    changes rarely enough that re-reading every call would be fine too,
    but this avoids doing that on every poll when alerts fire often."""
    # nbro_telegram_config.json first; if there is none, the one the ORB bot already uses (same bot token / chat), so no extra setup
    for path in (TELEGRAM_CONFIG_FILE, os.path.join(os.path.dirname(TELEGRAM_CONFIG_FILE), "orb_telegram_config.json")):
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return {"enabled": False}


def send_telegram_alert(message: str) -> None:
    """Best-effort — a Telegram outage, bad token, or no internet must
    NEVER block or crash real trading logic, so every failure mode here
    is caught and just logged, never raised. Uses urllib (stdlib) rather
    than the `requests` package to stay a zero-extra-dependency feature."""
    cfg = _load_telegram_config_cached(round(time.time() / 10) * 10)
    if not cfg.get("enabled"):
        return
    if ACCOUNT_LABEL:
        message = f"[{ACCOUNT_LABEL}] {message}"
    token = cfg.get("bot_token", "")
    chat_id = cfg.get("chat_id", "")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        _log(f"Telegram alert failed to send (bot keeps trading normally regardless): {e}")


# ============================================================
# CONFIG
# ============================================================

# CONFIRMED default trading list — passed rigorous 3-way out-of-sample
# validation (consistently positive AND improving across all three
# 2-month periods) under the CURRENT config (75-min range + ATR-stop).
# GBPUSD is real but weaker (2/3 periods positive, one genuine negative
# third) — kept available but NOT in the default list; see
# GBPUSD_EXPERIMENTAL below. AUDUSD/XAUUSD/NAS100_r tested and rejected —
# see README for the full real-data comparison across all 7 instruments.
SYMBOLS = ["NAS100", "SPX500"]
TIMEFRAME_STR = "M5"

# The same index has different names at different brokers (Atlas: NAS100 / SPX500; Vantage: NAS100.r / SP500.r). If the exact name (+ --suffix) does not exist,
# the alternatives are tried at start-up, the one found is remembered and written to the Activity Log. The market keeps its own name everywhere else.
BROKER_NAME_ALTERNATIVES = {
    "NAS100": ["NAS100.r", "USTEC", "US100", "USTECH"],
    "SPX500": ["SP500.r", "SP500", "US500", "SPX"],
}
SYMBOL_USD_STRENGTH_DIRECTION = {}     # not used by this strategy (both directions are traded); kept so shared code that reads it keeps working

ORB_SESSION_HOUR = 16       # server-clock hour at which 09:00 New York falls (the US cash open, 09:30, is this hour + SESSION_OPEN_MINUTE).
                             # Measured automatically from the broker's clock (SERVER_TIME_AUTO); 16 is the fallback = New York + 7h.
SERVER_TIME_AUTO = True
SESSION_ANCHOR_NY_HOUR = 9
_CLOCK = {"offset_hours": None, "checked_at": 0.0, "pending": None, "warned_closed": False}
CLOCK_RECHECK_SECONDS = 1800

# ---- the strategy (identical to the tested rule; see the header) ----
SESSION_OPEN_MINUTE = 30                                   # 09:30 New York = ORB_SESSION_HOUR:30 server time
NOISE_LOOKBACK_DAYS = 14                                   # sessions averaged for sigma
CHECK_MINUTES_AFTER_OPEN = tuple(range(30, 361, 30))       # 10:00, 10:30 ... 15:30 New York
SESSION_END_MINUTES_AFTER_OPEN = 385                       # 15:55 New York: the bar whose open closes everything
EXIT_READING = "X2"                                        # the loose exit that was tested (min(UPPER, VWAP) for longs)
EMERGENCY_STOP_PCT = 1.0                                   # broker-side stop, % of the entry price (chosen by a rule fixed before the run: see README)
LOCK_AFTER_EMERGENCY_STOP = False                          # True would stop re-entering on a symbol the same day after an emergency stop (safer, but cuts the tested edge by ~14%)
NOISE_BARS = 6500                                          # M5 bars requested from MT5 (about 3 weeks, enough for 14 complete sessions even with holidays)
NOISE_STRICT_SESSIONS = False                              # False: a session counts as complete if it has the opening bar, every check bar and ran to the close (one missing quiet bar is tolerated).
                                                           # True: exactly the backtest's rule, all 78 five-minute bars. The two rules differ on a handful of days in 14 years; kept False because a live feed can lose a bar.
MAX_CHECK_LATE_MINUTES = 5                                 # a check is acted on (entry) only while the bar of that check is still the forming one

SYMBOL_SPECS = {
    "NAS100": {"pip_size": 1.0, "min_stop_abs": 3.0},       # index: 1 point = 1 "pip" here
    "SPX500": {"pip_size": 1.0, "min_stop_abs": 1.0},
}
RISK_PCT = 0.5   # fallback only, for a symbol that has no entry in RISK_PCT_BY_SYMBOL

# --- Per-pair defaults, sized for the STRICTEST plan (Atlas Instant: 3% daily / 5% max drawdown); use --plan to scale them up (5-10 doubles them).
# A pair's risk is the % of equity LOST if the 1.0% emergency stop is hit, so the position is worth  risk% / 1.0%  times the account:
# 0.50 -> a position worth 0.5x the account per index; --plan 5-10 -> 1.0% -> 1.0x per index (NAS100 and SPX500 together about 2x).
RISK_PCT_BY_SYMBOL = {"NAS100": 0.50, "SPX500": 0.50}
_BASE_RISK_BY_SYMBOL = dict(RISK_PCT_BY_SYMBOL)
_BASE_MAX_OPEN_RISK = 1.0                 # both indices open together at the base risk (0.5 + 0.5)
DEFAULT_DISABLED_SYMBOLS = set()          # both pairs ON
SYMBOL_NOTES = {
    "NAS100": "Both directions. The main market: confirmed on a fresh sample (2012-2018) as well as 2019-2026.",
    "SPX500": "Both directions. Same idea, tested 2019-2026 only (z 2.5): moves with NAS100, so the two together are really one bet.",
}
SYMBOL_STATS = {
    "NAS100": "Backtest 2012-2026, with the 1.0% emergency stop: 2,639 trades | about 0.7 a day | +0.048% per trade after costs | Sharpe 1.04 | worst day -4.1% at 1x",
    "SPX500": "Backtest 2019-2026, with the 1.0% emergency stop: 1,364 trades | about 0.7 a day | +0.033% per trade after costs | Sharpe 0.85 | worst day -2.0% at 1x",
}
_DEFAULT_RISK_SNAPSHOT = {}   # the risk % each pair started with (after --plan / CLI, before dashboard edits)
# prop-plan presets: (max drawdown %, daily loss limit %). Risk and caps scale with max drawdown / 5.   Atlas Access evaluation = "5-10".
PLAN_PRESETS = {"instant": (5.0, 3.0), "4-8": (8.0, 4.0), "5-10": (10.0, 5.0)}
DEFAULT_LOT_SIZE = {"NAS100": 0.10, "SPX500": 0.10}
DISABLED_SYMBOLS = set(DEFAULT_DISABLED_SYMBOLS) & set(SYMBOLS)   # dashboard-controlled: symbols temporarily paused (no new entries; an open trade is still managed)

# --- Prop-firm risk guards, ported from HACVD's real, live-verified
# FundedNext-challenge config (not a generic guess — these are the actual
# values/mechanics HACVD ran on a real $50K Stellar-2-Step account).
# ACCOUNT-LEVEL (shared across both symbols here, unlike HACVD which only
# ever traded one symbol) — a prop firm's daily-loss and drawdown rules
# apply to the whole account, not per-instrument.

# Daily Loss Guard: blocks NEW entries once today's REALIZED loss (closed
# trades only, no floating P&L — matches HACVD's exact reasoning: this bot
# is flat when this check runs anyway) reaches this % of TODAY's starting
# equity. Does NOT force-close an already-open trade; HACVD's own
# reasoning for that applies equally here: at 0.75% risk per trade, even a
# full stop-out after the guard fires only adds 0.75%, safely under a
# typical 5% daily wall — letting the open trade reach its own real exit
# (partial+BE, measured-move/decay target) is better than crystallizing a
# loss on a position that might still win.
DAILY_LOSS_GUARD_ENABLED = True
DAILY_LOSS_GUARD_PCT = 1.8      # 60% of a 3% daily limit

# Static Max Drawdown Guard: real gap this closes that the daily guard
# alone can't — several days each individually under the daily limit can
# still cumulatively breach a prop firm's overall floor. STATIC means
# computed once from INITIAL_ACCOUNT_BALANCE, never recalculated off
# current/peak equity (a real static-drawdown account's max-loss line
# sits flat, confirmed against HACVD's actual account dashboard — it does
# NOT rise with equity like a trailing-drawdown rule would).
# SET INITIAL_ACCOUNT_BALANCE AND MAX_ACCOUNT_DRAWDOWN_PCT TO MATCH YOUR
# OWN PROP FIRM'S REAL RULE (check your account dashboard) BEFORE
# TRUSTING THIS GUARD — these are placeholders, not your actual numbers.
MAX_ACCOUNT_DRAWDOWN_ENABLED = True
INITIAL_ACCOUNT_BALANCE = 5000.0
_DEFAULT_INITIAL_BALANCE = 5000.0    # the untouched default; while it is still this, the real balance is adopted at first start
MAX_ACCOUNT_DRAWDOWN_PCT = 5.0
# "static" (default, unchanged behaviour): floor is fixed at INITIAL_ACCOUNT_BALANCE forever.
# "trailing": floor rises with the account's own EOD high-water mark (balance at each new day's
# start, the same value already computed once a day in _sync_daily_from_mt5, AND live equity peaks seen while running — deliberately the tighter reading) — matches a real
# prop-firm "Trailing" drawdown label (confirmed against the user's own Atlas Funded dashboard:
# "Max Drawdown 10% Trailing"), which this guard did NOT support before and would have been
# silently too lenient for once the account grew. CHECK YOUR OWN DASHBOARD before picking a mode
# — "Static"-labelled accounts (most 1-Step/2-Step challenges) still want "static".
MAX_ACCOUNT_DRAWDOWN_MODE = "static"
# Optional: stop opening NEW trades once the account's closed profit reaches this % of the starting
# balance (e.g. 3.0 for a challenge with a 3% profit target). None = off (default), nothing changes.
# Open trades are still managed to their normal end; this only blocks fresh entries so a trade
# opened after the target can't hand the profit back. Set with --profit-target.
PROFIT_TARGET_PCT = None
# Atlas PROTECTOR (Access FUNDED stage only): an OPEN loss of 2% of the starting balance closes everything and cuts the
# profit split to 50% for good; a second time breaches the account. The shield acts a little before that line: when the
# account's open (floating) loss reaches PROTECTOR_SHIELD_PCT of INITIAL_ACCOUNT_BALANCE, this bot closes ITS positions at
# market and opens nothing new for the rest of the UTC day. 0 = off. Set by --preset atlas-funded or --protector-shield.
PROTECTOR_SHIELD_PCT = 0.0
_shield_state = {"day": None}
# Presets measured on NBRO's own trades (Vantage M5, Sep 2018 - Oct 2026, replayed by noise_fx/atlas_sim.py):
#   atlas-eval    1.0% per index: passes +3% in ~91% of start dates, median ~26 trading days, ~4% breached
#   atlas-funded  0.35% per index: ~85-100% of accounts alive after a year, Protector never reached,
#                 ~1-1.5 payouts a year (the "3 days >= +0.5%" payout rule is the bottleneck)
ATLAS_PRESETS = {
    "atlas-eval": {"risk": 1.0, "max_dd": 10.0, "daily_guard": 3.0, "dd_mode": "trailing",
                   "profit_target": 3.0, "shield": 0.0, "max_open_risk": 2.0},
    "atlas-funded": {"risk": 0.35, "max_dd": 6.0, "daily_guard": 1.8, "dd_mode": "trailing",
                     "profit_target": None, "shield": 1.7, "max_open_risk": 0.7},
}
MAX_ACCOUNT_DRAWDOWN_SAFETY_BUFFER_PCT = 0.5   # stop entries this much %
                                    # of original balance BEFORE the real
                                    # hard floor, not exactly at it —
                                    # leaves room for one open position's
                                    # in-flight risk plus exit slippage.

# Per-session trade cap: ORB is already naturally one-trade-per-session by
# design (DONE_FOR_SESSION), so this defaults to 1 and is mostly here for
# parity with HACVD's config shape / future-proofing if that ever changes.
PER_SESSION_CAP_ENABLED = True
PER_SESSION_TRADE_CAP = 6          # entries per symbol per session (12 checks: a flip at every check is the most it could do)

# Max trades per day — ACCOUNT-level (all symbols together), ported from HACVD's
# MAX_TRADES_PER_DAY. The per-session cap above is per symbol; on real data the three symbols
# together entered up to 5 trades in one calendar day (86% of entries come 17:00-19:00 server
# right after the range closes, but ~14% happen overnight, and a late entry from yesterday's
# session can land on the same day as today's). Measured on 6 months of real data: a cap of 4
# keeps 99% of the R, a cap of 3 keeps 90%, a cap of 2 keeps only 69%. Counted per UTC day;
# rebuilt from MT5's deal history after a restart.
MAX_TRADES_PER_DAY_ENABLED = True
MAX_TRADES_PER_DAY = 8
MAX_TRADES_PER_DAY_CEILING = 12     # the dashboard can never raise the cap past this

# Max concurrent open risk — ported from HACVD's MAX_CONCURRENT_RISK_PCT. Total risk of every
# trade currently open, across ALL symbols, as a % of equity (a trade whose stop is already at
# breakeven counts as 0). This is the guard that actually matters with 3 symbols: they all enter
# within the same ~2 hours, so the Daily Loss Guard (which only sees REALIZED losses) has no
# chance to act before all three are already open. Measured: all 3 stopped out the same day
# happened 6 times in 105 days (-3.19R worst day). Set it to about  risk% x number of symbols.
MAX_CONCURRENT_RISK_ENABLED = True
MAX_CONCURRENT_RISK_PCT = 1.0

# News Protection Guard — ported from HACVD's real static calendar (not a
# live API — no dependency, no key, no new failure point). Blocks NEW
# entries within a window around known high-impact scheduled events.
# Genuine limitation carried over as-is: catches known SCHEDULED events,
# not unscheduled shocks — needs next year's CPI/FOMC/ECB/BOE dates added
# once published (see HACVD's own README for sources/update process).
NEWS_PROTECTION_ENABLED = False     # OFF by default: the tested strategy trades through news (the band is built from normal days). Switch on from the dashboard for a no-news rule.
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

# Max Entry Slippage Guard — ported from HACVD. Real gap this closes: the
# entry decision uses the just-closed bar's price, but the actual market
# order fills at whatever the LIVE ask/bid is when it's sent — a real gap
# exists between "decision made" and "order sent" (poll timing, MT5
# round-trip). If price already moved away past this threshold, skip the
# entry entirely rather than silently taking on more real risk than the
# stop distance was calculated for.
MAX_ENTRY_SLIPPAGE_ENABLED = True
MAX_ENTRY_SLIPPAGE_R = 0.03       # R = the 1% emergency-stop distance, so 0.03R = 0.03% of price (NAS100 ~7 points): the whole edge per trade is only ~0.05%, so a worse fill is skipped

# Max Spread Guard (new, from real Atlas tick data). ORB enters with a MARKET order right at the US open (09:00 New York) - exactly when the spread spikes for a few seconds around news.
# Measured on Atlas (7 days of ticks): USDJPY is 0.3-0.5 pips normally but reached 6-18 pips in the server hours 15-17. A market order sent in such a second pays the whole spread, and
# the slippage guard above does not see it (it looks at the PRICE, not at the gap between ask and bid). This guard compares the live spread with the stop distance, so it means the same
# thing on FX, gold and indices: above MAX_SPREAD_R the entry WAITS - the signal is kept and retried at every poll - for SPREAD_WAIT_SECONDS (a spike lasts seconds); if the spread is
# still too wide after that, the session is given up like any other skipped signal. ORB's own stops are wide (median 28-42 pips on EURUSD / USDJPY / USDCAD in the 2012-2015 holdout),
# so 0.15R is about 4-6 pips: it never fires on a normal spread (0.3-1.1 pips, under 0.2% of trades) and does fire on the spikes (6-18 pips = 0.14-0.64R of the median stop).
MAX_SPREAD_GUARD_ENABLED = True
MAX_SPREAD_R = 0.02               # 0.02R = 0.02% of price (NAS100 ~5 points, SPX500 ~1.4); a normal index spread is far below that
SPREAD_WAIT_SECONDS = 90
_spread_wait_since: dict = {}      # symbol -> (identity of the signal, time the wait began)

# Risk-based position sizing — opt-in (matches the established convention
# across every other bot here: "risk percent should not default, can be
# enabled but not default"). USE_RISK_BASED_SIZING=False keeps
# DEFAULT_LOT_SIZE (fixed lots); True computes lots from RISK_PCT x
# account equity via calculate_lot_size(), which existed as a function
# here but was never actually wired into the entry path until now.
USE_RISK_BASED_SIZING = True

MAGIC_NUMBER = 990801

# --- Multi-account / multi-terminal support (set via CLI flags, see __main__) ---
MT5_TERMINAL_PATH = None   # path to a specific terminal64.exe; None = default terminal
ACCOUNT_LABEL = ""         # short name shown in Telegram alerts, e.g. "Atlas-1"
APP_VERSION = "2026-10-07.noise.1"   # shown in the Activity Log at start-up and under the dashboard title
DAILY_LOSS_FLATTEN_ENABLED = True   # NEW vs ORB: when the Daily Loss Guard (or the drawdown safety line) is reached, open trades are CLOSED too, not just new entries blocked.
                                    # The indices can lose 1% in minutes, so blocking entries alone is not enough on a 5% daily limit.
SYMBOL_SUFFIX = ""         # broker-side suffix, e.g. ".r", ".pro" or "m" when the broker calls it EURUSD.r


def _bn(symbol: str) -> str:
    """The name this broker uses for one of our (plain) symbols (found at start-up, see _resolve_broker_name)."""
    return _BROKER_NAME.get(symbol) or (symbol + SYMBOL_SUFFIX)


_BROKER_NAME: dict = {}


def _resolve_broker_name(sym):
    """Find this broker's name for one of our markets: the plain name (+ --suffix) first, then the usual alternatives."""
    candidates = [sym + SYMBOL_SUFFIX] + [a for a in BROKER_NAME_ALTERNATIVES.get(sym, []) if a != sym + SYMBOL_SUFFIX]
    for name in candidates:
        try:
            if mt5.symbol_info(name) is not None:
                if name != sym + SYMBOL_SUFFIX:
                    _log(f"[{sym}] This broker calls it '{name}': using that name.")
                _BROKER_NAME[sym] = name
                return name
        except Exception:
            pass
    return sym + SYMBOL_SUFFIX


_warned_at = {}


def _warn_once(key: str, msg: str, every: float = 600.0):
    """Log a problem, but not on every 15-second poll."""
    now = time.time()
    if now - _warned_at.get(key, 0.0) >= every:
        _warned_at[key] = now
        _log(msg)


def _mt5_init() -> bool:
    """mt5.initialize() targeting a specific terminal when MT5_TERMINAL_PATH
    is set — required when running several accounts, each in its own MT5
    terminal instance on one PC (a bare initialize() always grabs the
    default terminal, so every bot instance would end up on the SAME account)."""
    if MT5_TERMINAL_PATH:
        return mt5.initialize(path=MT5_TERMINAL_PATH)
    return mt5.initialize()


def session_hour_for_offset(offset_hours, now_utc=None) -> int:
    """Server-clock hour at which 09:00 New York falls, given the broker's UTC offset."""
    now_utc = now_utc or datetime.now(timezone.utc)
    ny_local = now_utc + timedelta(hours=_utc_offset_hours("America/New_York", now_utc))
    anchor_utc = _local_to_utc(ny_local.year, ny_local.month, ny_local.day,
                               SESSION_ANCHOR_NY_HOUR, 0, "America/New_York")
    return (anchor_utc + timedelta(hours=offset_hours)).hour


def detect_server_offset_hours(now_utc=None):
    """Broker server clock minus true UTC, in whole hours, or None if it can't be measured
    reliably right now. Same method as HACVD: compare true UTC against the newest bar's raw
    timestamp (bars are stamped with server time). Guards against the ways that goes wrong:
      - market closed  -> the newest bar is stale (HACVD once adopted -39h on a weekend);
      - +-14h sanity   -> no real server clock is further from UTC than that;
      - whole-hour fit -> a live bar is at most a few minutes behind 'now', so the difference
                          must sit close to a whole number of hours;
      - freshest of several liquid symbols, since one thin symbol's last bar can be stale."""
    now_utc = now_utc or datetime.now(timezone.utc)
    wd = now_utc.weekday()
    if wd == 5 or (wd == 4 and now_utc.hour >= 21) or (wd == 6 and now_utc.hour < 22):
        return None
    latest = None
    for sym in dict.fromkeys(["XAUUSD", "EURUSD"] + list(SYMBOLS)):
        try:
            rates = mt5.copy_rates_from_pos(_bn(sym), mt5.TIMEFRAME_M5, 0, 1)
        except Exception:
            continue
        if rates is None or len(rates) == 0:
            continue
        t = int(rates[0]["time"])
        latest = t if latest is None else max(latest, t)
    if latest is None:
        return None
    diff = (latest - now_utc.timestamp()) / 3600.0
    off = round(diff)
    if abs(off) > 14 or abs(diff - off) > 0.35:
        return None
    return int(off)


def refresh_session_clock(force=False):
    """Measure the server clock, and keep ORB_SESSION_HOUR pointed at 09:00 New York. Never raises.
    A CHANGE of offset is only adopted after two consecutive identical measurements, so one odd
    reading can't move the session."""
    global ORB_SESSION_HOUR
    if not SERVER_TIME_AUTO or not MT5_AVAILABLE:
        return
    try:
        now = time.time()
        if not force and now - _CLOCK["checked_at"] < CLOCK_RECHECK_SECONDS:
            return
        _CLOCK["checked_at"] = now
        measured = detect_server_offset_hours()
        if measured is None:
            if not _CLOCK["warned_closed"]:
                _log(f"Server-time check skipped: market closed or no fresh bar. Using "
                     f"{'UTC%+d' % _CLOCK['offset_hours'] if _CLOCK['offset_hours'] is not None else 'the default'} "
                     f"/ session hour {ORB_SESSION_HOUR}; it re-checks automatically.")
                _CLOCK["warned_closed"] = True
            return
        _CLOCK["warned_closed"] = False
        prev = _CLOCK["offset_hours"]
        if prev is not None and measured != prev:
            if _CLOCK["pending"] != measured:
                _CLOCK["pending"] = measured
                return
            _log(f"Broker server clock changed: UTC{prev:+d} -> UTC{measured:+d} (confirmed twice; "
                 f"usually the broker's own DST switch).")
            send_telegram_alert(f"🕒 Broker server clock changed UTC{prev:+d} -> UTC{measured:+d}; "
                                f"session hour re-aligned automatically.")
        _CLOCK["pending"] = None
        _CLOCK["offset_hours"] = measured
        new_hour = session_hour_for_offset(measured)
        if new_hour != ORB_SESSION_HOUR or prev is None:
            old = ORB_SESSION_HOUR
            ORB_SESSION_HOUR = new_hour
            utc_h = (new_hour - measured) % 24
            _log(f"Server clock measured UTC{measured:+d}. the US session (09:00 New York) is at {new_hour:02d}:00 server time "
                 f"= {utc_h:02d}:00 UTC = {SESSION_ANCHOR_NY_HOUR:02d}:00 New York (auto"
                 f"{'' if old == new_hour else f'; was {old:02d}:00'}).")
    except Exception as e:
        _log(f"Server-time check failed ({e}) — keeping session hour {ORB_SESSION_HOUR}.")


def _server_ts_to_utc_iso(ts) -> str:
    """MT5 stamps positions/deals with SERVER time; convert to true UTC for display (HACVD hit
    the same mislabelling bug in its reconcile path)."""
    return datetime.fromtimestamp(ts - (_CLOCK["offset_hours"] or 0) * 3600, timezone.utc).isoformat()


def get_clock_status() -> dict:
    off = _CLOCK["offset_hours"]
    d = {"offset_hours": off, "auto": bool(SERVER_TIME_AUTO and off is not None),
         "session_hour_server": ORB_SESSION_HOUR, "anchor_ny_hour": SESSION_ANCHOR_NY_HOUR}
    if off is not None:
        now = datetime.now(timezone.utc)
        utc_h = (ORB_SESSION_HOUR - off) % 24
        d["session_hour_utc"] = utc_h
        d["session_hour_ny"] = (utc_h + _utc_offset_hours("America/New_York", now)) % 24
    return d
STATUS_FILE = "nbro_status.json"
CONTROL_FILE = "nbro_control.json"
MAX_LOG_LINES = 200
MAX_RECENT_TRADES = 200


# ============================================================
# STATE MACHINE
# ============================================================

class Phase(str, Enum):
    WAITING_FOR_RANGE = "WAITING_FOR_RANGE"
    RANGE_SET = "RANGE_SET"
    IN_TRADE = "IN_TRADE"
    DONE_FOR_SESSION = "DONE_FOR_SESSION"


@dataclass
class ActiveTrade:
    direction: str
    entry_price: float
    sl_price: float
    initial_risk: float
    volume: float
    target_price: float
    partial_done: bool = False
    ticket: Optional[int] = None
    be_moved: bool = False           # SL confirmed moved to breakeven at the broker
    entry_volume: Optional[float] = None   # ORIGINAL lots (volume = what's left now)
    initial_sl: Optional[float] = None
    opened_at: Optional[str] = None


@dataclass
class SymbolState:
    phase: Phase = Phase.WAITING_FOR_RANGE
    current_session_date = None
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    trade: Optional[ActiveTrade] = None
    last_criteria: List[dict] = field(default_factory=list)
    ambiguous_until: float = 0.0     # a timed-out order may still fill: no retry before this moment
    last_signal_price: Optional[float] = None
    last_signal_direction: Optional[str] = None
    live_snapshot: dict = field(default_factory=dict)   # last price/R/profit for the dashboard
    finalize_attempts: int = 0
    last_check_k: int = -1             # the last 30-minute check whose ENTRY side was handled this session
    exit_k: int = -1                   # the last check whose EXIT rule was evaluated for the open trade
    frame: Optional[dict] = None       # today's open, yesterday's close and sigma(t): fixed for the whole session
    ctx: Optional[dict] = None         # the numbers of the latest check (P, VWAP, UPPER, LOWER)
    signal_ts: Optional[str] = None    # the check time the pending signal belongs to
    entry_attempts: int = 0
    session_hour_used: Optional[int] = None   # the ORB_SESSION_HOUR in effect when THIS session's range was
                                                # anchored — frozen so a later auto-detected clock change can't
                                                # retroactively shift where this session's window starts
    close_requested: bool = False      # set by the dashboard's "Close Now" button (HTTP thread); acted on by
                                        # the poll loop (its own thread) on the next pass — never sent straight
                                        # from the HTTP handler, since MT5 calls are not meant to run from two
                                        # threads at once


# ============================================================
# PURE ANALYSIS FUNCTIONS
# ============================================================

def get_session_date(ts: pd.Timestamp, session_hour: int = None) -> pd.Timestamp:
    """Which 'trading session day' a timestamp belongs to: the session
    that started at the most recent `session_hour`:00 at-or-before `ts`.

    NOTE: session_hour defaults to None, resolved inside the function body
    — a module constant bound directly into a default parameter value
    freezes it at import time, so a later `orb_bot.ORB_SESSION_HOUR = X`
    would silently have no effect otherwise. Same footgun already found
    and fixed in cvdpoc_bot.py; caught it again here via a robustness
    check that gave suspiciously identical results across "different"
    configs — the tell that this bug was recurring."""
    if session_hour is None:
        session_hour = ORB_SESSION_HOUR
    d = ts.normalize()
    if ts.hour < session_hour:
        d = d - pd.Timedelta(days=1)
    return d


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
    now = datetime.now(timezone.utc)
    candidates = []
    for year in (now.year, now.year + 1):
        candidates += [(t, n) for t, n in _news_events_for_year(year) if t >= now]
    if not candidates:
        return None
    event_time, name = min(candidates)
    return {"time": event_time.isoformat(), "name": name}


# Which symbols have USD as the BASE currency (USDCAD, USDJPY) rather than
# the quote currency (EURUSD, GBPUSD, AUDUSD) — needed because the $-value
# of one pip, per standard 100,000-unit lot, is a flat $10 ONLY when USD is
# the quote currency. When USD is the base currency, one pip is worth
# (100,000 x pip_size) / current_price in USD terms — it moves with the
# exchange rate, not a fixed $10. XAUUSD's own lot convention (100 oz)
# happens to also work out to ~$10/pip and is treated the same as the
# flat-$10 group here.
USD_BASE_CURRENCY_SYMBOLS = {"USDCAD", "USDJPY"}


def calculate_lot_size(equity: float, risk_pct: float, entry_price: float,
                        sl_price: float, symbol: str, pip_value_per_lot: float = None) -> float:
    """NOTE: pip_value_per_lot defaults to None and is resolved per-symbol
    inside the function body when not given explicitly — see
    find_accumulation_box's docstring pattern (elsewhere in this project)
    for why a mutable/context-dependent value should never be a bare
    literal default. Real bug found and fixed here: a flat $10/pip/lot
    default was being used for EVERY symbol, but that figure is only
    correct when USD is the QUOTE currency (EURUSD, GBPUSD, AUDUSD) — for
    a USD-as-BASE pair (USDCAD, USDJPY) the true $-value of one pip moves
    with the exchange rate and was measured at ~$7.27 for USDCAD and
    ~$6.29 for USDJPY (at illustrative ~1.375 and ~159 rates) — 27-37%
    below the flat $10 this function was silently assuming for them,
    which meant the ACTUAL dollar risk taken on those two symbols was
    correspondingly smaller than RISK_PCT intended (safe-direction, but
    still wrong, and precision matters more on a small account trying to
    stay inside tight daily/drawdown guards)."""
    spec = SYMBOL_SPECS[symbol]
    if pip_value_per_lot is None:
        pip_value_per_lot = _pip_value_per_lot(symbol, entry_price)
    risk_amount = equity * (risk_pct / 100.0)
    stop_dist = max(abs(entry_price - sl_price), spec["min_stop_abs"])
    pips = stop_dist / spec["pip_size"]
    if pips <= 0:
        return 0.0
    lot = risk_amount / (pips * pip_value_per_lot)
    # floor, never round up: rounding to nearest could risk slightly MORE than RISK_PCT,
    # which matters when a prop firm's daily-loss / drawdown limits are tight
    return max(math.floor(lot * 100 + 1e-9) / 100, 0.01)



def session_window(session_date):
    """(open timestamp, last-bar timestamp) of the US cash session that belongs to this session date, in broker server time."""
    o = pd.Timestamp(session_date).normalize() + pd.Timedelta(hours=ORB_SESSION_HOUR, minutes=SESSION_OPEN_MINUTE)
    return o, o + pd.Timedelta(minutes=SESSION_END_MINUTES_AFTER_OPEN)


def _session_bars_needed() -> int:
    return SESSION_END_MINUTES_AFTER_OPEN // 5 + 1


def noise_frame(df: pd.DataFrame, session_date) -> Optional[dict]:
    """Everything that is fixed for the whole session: today's open, yesterday's close and sigma(t) for every check time.
    sigma(t) = mean over the previous NOISE_LOOKBACK_DAYS COMPLETE sessions of |price at t / that session's open - 1| (price at t = the open of the M5 bar at t).
    Yesterday's close = the close of the last bar of the most recent earlier session, complete or not. Returns None until today's opening bar exists, or when there is not enough history."""
    o_ts, e_ts = session_window(session_date)
    t = df["time"]
    today = df[(t >= o_ts) & (t <= e_ts)]
    if today.empty or today["time"].iloc[0] != o_ts:
        return None
    offsets = [pd.Timedelta(minutes=m) for m in CHECK_MINUTES_AFTER_OPEN]
    sigmas, prev = [], None
    d = pd.Timestamp(session_date).normalize() - pd.Timedelta(days=1)
    for _ in range(40):
        a, b = session_window(d)
        g = df[(t >= a) & (t <= b)]
        if len(g):
            if prev is None:
                prev = float(g["close"].iloc[-1])
            if len(sigmas) < NOISE_LOOKBACK_DAYS and g["time"].iloc[0] == a and g["time"].iloc[-1] >= b - pd.Timedelta(minutes=5):
                px = g.drop_duplicates("time").set_index("time")["open"]
                full_bars = (not NOISE_STRICT_SESSIONS) or (len(g) == _session_bars_needed() and (g["time"].diff().dropna() == pd.Timedelta(minutes=5)).all())
                if full_bars and all((a + off) in px.index for off in offsets):     # a complete session: opening bar, every check bar, and it ran to the close
                    op = float(g["open"].iloc[0])
                    sigmas.append([abs(float(px[a + off]) / op - 1.0) for off in offsets])
        d -= pd.Timedelta(days=1)
        if len(sigmas) >= NOISE_LOOKBACK_DAYS and prev is not None:
            break
    if prev is None or len(sigmas) < NOISE_LOOKBACK_DAYS:
        return {"ready": False, "sessions": len(sigmas)}
    return {"ready": True, "open": float(today["open"].iloc[0]), "prev": prev, "sessions": len(sigmas),
            "sigma": [float(x) for x in np.mean(np.array(sigmas), axis=0)]}


def noise_context(df: pd.DataFrame, frame: dict, session_date, k: int) -> Optional[dict]:
    """The numbers of check number k: P (open of the M5 bar at the check time), VWAP of the bars before it, UPPER and LOWER. None if that bar is missing."""
    o_ts, e_ts = session_window(session_date)
    ct = o_ts + pd.Timedelta(minutes=CHECK_MINUTES_AFTER_OPEN[k])
    t = df["time"]
    bar = df[t == ct]
    if bar.empty:
        return None
    before = df[(t >= o_ts) & (t < ct)]
    vol = before["volume"].to_numpy(dtype=float)
    cv = float(vol.sum())
    vwap = float((((before["high"] + before["low"] + before["close"]) / 3.0).to_numpy(dtype=float) * vol).sum() / cv) if cv > 0 else frame["open"]
    hi, lo = max(frame["open"], frame["prev"]), min(frame["open"], frame["prev"])
    sig = frame["sigma"][k]
    return {"ts": ct, "k": k, "P": float(bar["open"].iloc[0]), "vwap": vwap, "UB": hi * (1.0 + sig), "LB": lo * (1.0 - sig)}


def noise_entry_direction(P, UB, LB) -> Optional[str]:
    if P > UB:
        return "LONG"
    if P < LB:
        return "SHORT"
    return None


def noise_exit_due(direction, P, vwap, UB, LB, reading=None) -> bool:
    reading = reading or EXIT_READING
    if direction == "LONG":
        line = max(UB, vwap) if reading == "X1" else min(UB, vwap)
        return P < line
    line = min(LB, vwap) if reading == "X1" else max(LB, vwap)
    return P > line


def noise_exit_line(direction, vwap, UB, LB, reading=None) -> float:
    reading = reading or EXIT_READING
    if direction == "LONG":
        return max(UB, vwap) if reading == "X1" else min(UB, vwap)
    return min(LB, vwap) if reading == "X1" else max(LB, vwap)


def emergency_stop_price(direction, price) -> float:
    d = EMERGENCY_STOP_PCT / 100.0
    return price * (1.0 - d) if direction == "LONG" else price * (1.0 + d)


def due_check(latest_bar_time, session_date, last_k) -> Optional[int]:
    """The newest check whose time has been reached and that has not been handled yet (None if none)."""
    o_ts, _ = session_window(session_date)
    k_new = None
    for k, m in enumerate(CHECK_MINUTES_AFTER_OPEN):
        if o_ts + pd.Timedelta(minutes=m) <= latest_bar_time:
            k_new = k
    if k_new is None or k_new <= last_k:
        return None
    return k_new


def session_is_over(latest_bar_time, session_date) -> bool:
    return latest_bar_time >= session_window(session_date)[1]



def analyze_symbol(symbol: str, df: pd.DataFrame, state: SymbolState) -> List[str]:
    """Entry side of the state machine for ONE symbol (only called while flat). Works on the bars MT5 returned, the LAST of which is still forming.
    Mutates `state` in place and places no orders: a signal is left in state.last_signal_* for _try_enter."""
    logs: List[str] = []
    latest = df["time"].iloc[-1]
    sd = get_session_date(latest)

    if state.current_session_date is None or sd != state.current_session_date:
        state.current_session_date = sd           # a new session: everything per-session starts again
        state.phase = Phase.WAITING_FOR_RANGE
        state.entry_attempts = 0
        state.range_high = None
        state.range_low = None
        state.frame = None
        state.ctx = None
        state.last_check_k = -1
        state.exit_k = -1
        state.last_signal_price = None
        state.last_signal_direction = None
        state.session_hour_used = ORB_SESSION_HOUR

    if session_is_over(latest, sd):
        state.phase = Phase.DONE_FOR_SESSION
        state.last_signal_price = None
        return logs
    if state.phase == Phase.DONE_FOR_SESSION:
        return logs

    if state.frame is None or not state.frame.get("ready"):
        fr = noise_frame(df, sd)
        state.frame = fr
        if fr is None:
            state.last_criteria = [{"name": "session_open", "pass": False}]
            return logs
        if not fr["ready"]:
            state.last_criteria = [{"name": "session_open", "pass": True}, {"name": "history", "pass": False}]
            _warn_once(f"hist:{symbol}", f"[{symbol}] Noise band not ready: only {fr['sessions']} of the last {NOISE_LOOKBACK_DAYS} full sessions "
                                         f"were found in the {len(df)} bars MT5 returned. The broker's index CFD needs bars from "
                                         f"{ORB_SESSION_HOUR}:{SESSION_OPEN_MINUTE:02d} to about {ORB_SESSION_HOUR + SESSION_END_MINUTES_AFTER_OPEN // 60 + (SESSION_OPEN_MINUTE + SESSION_END_MINUTES_AFTER_OPEN % 60) // 60}:"
                                         f"{(SESSION_OPEN_MINUTE + SESSION_END_MINUTES_AFTER_OPEN) % 60:02d} server time each day. It keeps trying.", every=3600.0)
            return logs
        state.phase = Phase.RANGE_SET
        logs.append(f"[{symbol}] Noise band ready for {sd.date()}: open {fr['open']:.2f}, yesterday's close {fr['prev']:.2f}, "
                    f"sigma {fr['sigma'][0] * 100:.2f}% at 10:00 -> {fr['sigma'][-1] * 100:.2f}% at 15:30 New York.")

    k = due_check(latest, sd, state.last_check_k)
    if k is None:
        return logs
    state.last_check_k = k
    ctx = noise_context(df, state.frame, sd, k)
    if ctx is None:
        logs.append(f"[{symbol}] Check {k + 1}/{len(CHECK_MINUTES_AFTER_OPEN)}: the bar of the check time is missing in the data — skipped.")
        return logs
    state.ctx = ctx
    state.range_high, state.range_low = ctx["UB"], ctx["LB"]
    direction = noise_entry_direction(ctx["P"], ctx["UB"], ctx["LB"])
    on_time = (latest - ctx["ts"]) < pd.Timedelta(minutes=MAX_CHECK_LATE_MINUTES)
    state.last_criteria = [{"name": "band_ready", "pass": True},
                           {"name": "outside_band", "pass": direction is not None},
                           {"name": "check_on_time", "pass": bool(on_time)}]
    if direction is None:
        return logs
    if not on_time:
        logs.append(f"[{symbol}] Check {k + 1}: price is outside the band ({direction}) but the check time passed more than "
                    f"{MAX_CHECK_LATE_MINUTES} minutes ago (bot started late or lost its connection) — not entering on stale data.")
        return logs
    state.last_signal_price = ctx["P"]
    state.last_signal_direction = direction
    state.signal_ts = str(ctx["ts"])
    logs.append(f"[{symbol}] Check {k + 1}/{len(CHECK_MINUTES_AFTER_OPEN)}: price {ctx['P']:.2f} is {'above' if direction == 'LONG' else 'below'} the band "
                f"({ctx['LB']:.2f} - {ctx['UB']:.2f}, VWAP {ctx['vwap']:.2f}) -> {direction} signal.")
    return logs
def register_trade(state: SymbolState, direction: str, entry_price: float,
                    sl_price: float, volume: float, target_price: float):
    state.trade = ActiveTrade(direction=direction, entry_price=entry_price,
                               sl_price=sl_price, initial_risk=abs(entry_price - sl_price),
                               volume=volume, target_price=target_price)
    state.phase = Phase.IN_TRADE
    state.last_signal_price = None
    state.last_signal_direction = None


# ============================================================
# MT5 WRAPPERS (live-only)
# ============================================================

_MT5_TIMEFRAMES = {}
if MT5_AVAILABLE:
    _MT5_TIMEFRAMES = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}


def get_rates(symbol: str, timeframe_str: str = TIMEFRAME_STR, n: int = None) -> Optional[pd.DataFrame]:
    if not MT5_AVAILABLE:
        return None
    rates = mt5.copy_rates_from_pos(_bn(symbol), _MT5_TIMEFRAMES[timeframe_str], 0, n or NOISE_BARS)
    if rates is None or len(rates) == 0:
        _warn_once(f"norates:{symbol}",
                   f"[{symbol}] No price data from MT5 for '{_bn(symbol)}'. Usual causes: the name is different on this "
                   f"broker (use --suffix), the pair isn't in Market Watch, or the market is closed.")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["volume"] = df["tick_volume"].astype(float) if "tick_volume" in df.columns else 1.0
    return df


def send_market_order(symbol: str, direction: str, volume: float, sl: float, comment: str = "noise"):
    if not MT5_AVAILABLE:
        return None
    order_type = mt5.ORDER_TYPE_BUY if direction == "LONG" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(_bn(symbol))
    if tick is None:
        return None
    price = tick.ask if direction == "LONG" else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": _bn(symbol), "volume": volume,
        "type": order_type, "price": price, "sl": sl, "magic": MAGIC_NUMBER,
        "comment": comment, "type_filling": _filling(symbol), "deviation": 20,
    }
    return mt5.order_send(request)


def close_partial(symbol: str, ticket: int, volume: float, direction: str, comment: str = "noise_close"):
    if not MT5_AVAILABLE:
        return None
    order_type = mt5.ORDER_TYPE_SELL if direction == "LONG" else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(_bn(symbol))
    if tick is None:
        return None
    price = tick.bid if direction == "LONG" else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": _bn(symbol), "volume": volume,
        "type": order_type, "position": ticket, "price": price,
        "magic": MAGIC_NUMBER, "comment": comment, "type_filling": _filling(symbol), "deviation": 20,
    }
    return mt5.order_send(request)


def modify_sl(symbol: str, ticket: int, new_sl: float):
    if not MT5_AVAILABLE:
        return None
    request = {"action": mt5.TRADE_ACTION_SLTP, "symbol": _bn(symbol), "position": ticket, "sl": new_sl}
    return mt5.order_send(request)


# ============================================================
# LIVE ORCHESTRATION (dashboard reads what this writes)
# ============================================================

_states: Dict[str, SymbolState] = {s: SymbolState() for s in SYMBOLS}

# Account-level guard state (shared across all symbols — see the guard
# config comments above for why this is account-level, not per-symbol).
_account_guard_state = {
    "current_day": None,          # UTC date string, e.g. "2026-09-27"
    "day_start_equity": 0.0,
    "closed_trades_today": [],    # list of realized $ P&L, reset each new day
    "session_trade_counts": {},   # {(symbol, session_date_str): count}
    "entries_today": 0,           # trades OPENED today (UTC day), all symbols
    "ops_today": 0.0,             # deposits/withdrawals today (paper-money top-ups): not trading results
    "dd_high_water_mark": 0.0,    # trailing-mode only: highest EOD balance seen so far (0.0 = not yet set; resolved to INITIAL_ACCOUNT_BALANCE on first read)
}


def _roll_account_day_if_needed(equity: float):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _account_guard_state["current_day"] != today:
        _account_guard_state["current_day"] = today
        _account_guard_state["day_start_equity"] = equity
        _account_guard_state["closed_trades_today"] = []
        _account_guard_state["entries_today"] = 0
        _account_guard_state["ops_today"] = 0.0


def record_closed_trade_pnl(pnl_dollars: float):
    """Call this whenever a trade actually closes (partial or final) so the
    Daily Loss Guard has real realized P&L to check against."""
    _account_guard_state["closed_trades_today"].append(pnl_dollars)


def compute_daily_loss_dollars() -> Optional[float]:
    """Today's loss the way a prop firm counts it: from the balance at the start of the day to the EQUITY now, so a
    trade that is open and losing counts before it is closed. Deposits or top-ups made today are not trading
    results and are taken out. Falls back to realized-only when no live equity reading exists yet."""
    g = _account_guard_state
    start = g["day_start_equity"]
    if start <= 0:
        return None
    if _last_equity is not None:
        return start - (_last_equity - g.get("ops_today", 0.0))
    return -sum(g["closed_trades_today"])


def compute_daily_loss_pct() -> Optional[float]:
    """Today's loss as a % of the account's starting SIZE (INITIAL_ACCOUNT_BALANCE). A firm's daily limit is a fixed
    amount worked out from that size (FundedNext $50K 2-Step: 5% = $2,500), not a % of whatever the balance was this
    morning, so the guard is measured against the same base."""
    d = compute_daily_loss_dollars()
    if d is None or INITIAL_ACCOUNT_BALANCE <= 0:
        return None
    return round(d / INITIAL_ACCOUNT_BALANCE * 100.0, 3)


def compute_overall_drawdown_status(equity: float) -> dict:
    """Real distance from the account's max-drawdown floor. In "static" mode (see
    MAX_ACCOUNT_DRAWDOWN_MODE's comment above) the base never moves off INITIAL_ACCOUNT_BALANCE;
    in "trailing" mode the base is the higher of that and the account's own EOD high-water mark,
    tracked once a day in _sync_daily_from_mt5 — rises with the account the same way a real
    trailing-drawdown prop-firm rule does."""
    base = INITIAL_ACCOUNT_BALANCE
    if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing":
        base = max(base, _account_guard_state.get("dd_high_water_mark", INITIAL_ACCOUNT_BALANCE))
    floor = base * (1 - MAX_ACCOUNT_DRAWDOWN_PCT / 100.0)
    stop_new_entries_below = floor + INITIAL_ACCOUNT_BALANCE * (MAX_ACCOUNT_DRAWDOWN_SAFETY_BUFFER_PCT / 100.0)
    return {
        "floor": round(floor, 2),
        "trailing_base": round(base, 2) if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing" else None,
        "stop_new_entries_below": round(stop_new_entries_below, 2),
        "remaining_to_floor_dollars": round(equity - floor, 2),
        "remaining_to_floor_pct": round((equity - floor) / INITIAL_ACCOUNT_BALANCE * 100.0, 3),
        "blocked": equity <= stop_new_entries_below,
    }


def _session_trade_count(symbol: str, session_date) -> int:
    key = (symbol, str(session_date))
    return _account_guard_state["session_trade_counts"].get(key, 0)


def _increment_session_trade_count(symbol: str, session_date):
    key = (symbol, str(session_date))
    _account_guard_state["session_trade_counts"][key] = _account_guard_state["session_trade_counts"].get(key, 0) + 1
_activity_log: deque = deque(maxlen=MAX_LOG_LINES)
_recent_trades: deque = deque(maxlen=MAX_RECENT_TRADES)


def _snapshot_deque(d) -> list:
    """list(deque) can raise 'deque mutated during iteration' when the bot thread appends while the
    dashboard thread reads. Retry instead of letting the dashboard go blank."""
    for _ in range(8):
        try:
            return list(d)
        except RuntimeError:
            continue
    return []


def _log(line: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    _activity_log.append(f"{ts} UTC  {line}")


# ---------------- broker helpers ----------------

def _filling(symbol):
    info = mt5.symbol_info(_bn(symbol))
    fm = getattr(info, "filling_mode", 0) if info else 0
    if fm & 2:
        return mt5.ORDER_FILLING_IOC
    if fm & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _round_price(symbol, price):
    info = mt5.symbol_info(_bn(symbol))
    return round(price, getattr(info, "digits", 5) if info else 5)


def _vol_limits(symbol):
    info = mt5.symbol_info(_bn(symbol))
    if not info:
        return 0.01, 100.0, 0.01
    return info.volume_min, info.volume_max, (info.volume_step or 0.01)


def _floor_to_step(symbol, vol):
    _, _, step = _vol_limits(symbol)
    return round(math.floor(vol / step + 1e-9) * step, 8)


def _normalize_volume(symbol, vol):
    vmin, vmax, _ = _vol_limits(symbol)
    return max(vmin, min(_floor_to_step(symbol, vol), vmax))


def _risk_pct_for(symbol) -> float:
    return float(RISK_PCT_BY_SYMBOL.get(symbol, RISK_PCT))


def apply_plan_preset(name):
    """Scale the per-pair risk, the open-risk cap, the daily-loss guard and the drawdown floor
    to a prop plan. Guard = 60% of the daily limit; risk scales with max drawdown / 5."""
    global MAX_ACCOUNT_DRAWDOWN_PCT, DAILY_LOSS_GUARD_PCT, MAX_CONCURRENT_RISK_PCT
    max_dd, daily = PLAN_PRESETS[name]
    scale = max_dd / 5.0
    for k, v in _BASE_RISK_BY_SYMBOL.items():
        RISK_PCT_BY_SYMBOL[k] = round(v * scale, 2)
    MAX_CONCURRENT_RISK_PCT = round(_BASE_MAX_OPEN_RISK * scale, 2)
    DAILY_LOSS_GUARD_PCT = round(0.6 * daily, 2)
    MAX_ACCOUNT_DRAWDOWN_PCT = max_dd


_SETTING_RULES = {          # key: (kind, min, max, label)
    "per_session_trade_cap": ("int", 1, 10, "Per-session trade cap"),
    "max_trades_per_day": ("int", 1, None, "Max trades per day"),
    "daily_loss_guard_pct": ("float", 0.1, 20, "Daily Loss Guard %"),
    "initial_account_balance": ("float", 100, 100000000, "Account balance for the drawdown floor"),
    "max_account_drawdown_pct": ("float", 0.5, 50, "Max drawdown %"),
    "max_concurrent_risk_pct": ("float", 0.05, 10, "Max concurrent open risk %"),
    "max_entry_slippage_r": ("float", 0.05, 2, "Max entry slippage (R)"),
    "max_spread_r": ("float", 0.02, 1, "Max spread (R of the stop distance)"),
}
_BOOL_KEYS = {"daily_loss_guard_enabled", "max_account_drawdown_enabled",
              "per_session_cap_enabled", "max_trades_per_day_enabled", "max_concurrent_risk_enabled",
              "news_protection_enabled", "max_entry_slippage_enabled", "max_spread_guard_enabled", "use_risk_based_sizing"}


def _validate_control(control: dict):
    """Split a dashboard request into values that are safe to apply and human-readable rejections.
    An empty or non-numeric field used to reach the server as null and crash the request, so nothing
    was applied and nothing was shown."""
    clean, rejected = {}, []
    for k, v in control.items():
        if k in _SETTING_RULES:
            kind, lo, hi, label = _SETTING_RULES[k]
            if hi is None:
                hi = MAX_TRADES_PER_DAY_CEILING
            try:
                x = float(v)
                if not math.isfinite(x):
                    raise ValueError
            except (TypeError, ValueError):
                rejected.append(f"{label}: enter a number (the field was empty or not a number)")
                continue
            if not lo <= x <= hi:
                rejected.append(f"{label}: {x:g} is outside the allowed range {lo:g} to {hi:g}")
                continue
            if kind == "int5" and x % 5:
                rejected.append(f"{label}: must be a multiple of 5 (the bot works on 5-minute bars)")
                continue
            clean[k] = x if kind == "float" else int(x)
        elif k in _BOOL_KEYS:
            clean[k] = bool(v)
        elif k == "disabled_symbols":
            if isinstance(v, list) and all(x in SYMBOLS for x in v):
                clean[k] = v
            else:
                rejected.append("Symbols: unknown pair in the list")
        elif k == "risk_pct_by_symbol" and isinstance(v, dict):
            good = {}
            for sym, val in v.items():
                try:
                    x = float(val)
                    if sym not in SYMBOLS or not math.isfinite(x) or not 0.05 <= x <= 5:
                        raise ValueError
                    good[sym] = x
                except (TypeError, ValueError):
                    rejected.append(f"{sym} risk %: enter a number between 0.05 and 5")
            if good:
                clean[k] = good
        elif k in ("risk_pct",):
            try:
                clean[k] = float(v)
            except (TypeError, ValueError):
                rejected.append("Risk %: not a number")
    return clean, rejected


def _onoff(enabled, value=""):
    return (f"ON {value}" if value != "" else "ON") if enabled else "OFF"


def _settings_snapshot() -> dict:
    d = {
        "Daily Loss Guard": _onoff(DAILY_LOSS_GUARD_ENABLED, f"{DAILY_LOSS_GUARD_PCT:g}%"),
        "Drawdown base balance": f"${INITIAL_ACCOUNT_BALANCE:,.0f}",
        "Max Drawdown guard": _onoff(MAX_ACCOUNT_DRAWDOWN_ENABLED, f"{MAX_ACCOUNT_DRAWDOWN_PCT:g}%"),
        "Per-session cap": _onoff(PER_SESSION_CAP_ENABLED, PER_SESSION_TRADE_CAP),
        "Max trades per day": _onoff(MAX_TRADES_PER_DAY_ENABLED, min(MAX_TRADES_PER_DAY, MAX_TRADES_PER_DAY_CEILING)),
        "Max concurrent open risk": _onoff(MAX_CONCURRENT_RISK_ENABLED, f"{MAX_CONCURRENT_RISK_PCT:g}%"),
        "News guard": _onoff(NEWS_PROTECTION_ENABLED),
        "Slippage guard": _onoff(MAX_ENTRY_SLIPPAGE_ENABLED, f"{MAX_ENTRY_SLIPPAGE_R:g}R"),
        "Spread guard": _onoff(MAX_SPREAD_GUARD_ENABLED, f"{MAX_SPREAD_R:g}R, waits {SPREAD_WAIT_SECONDS}s"),
        "Risk-based sizing": _onoff(USE_RISK_BASED_SIZING),
    }
    for sym in SYMBOLS:
        d[f"{sym} trading"] = "OFF" if sym in DISABLED_SYMBOLS else "ON"
        d[f"{sym} risk %"] = f"{_risk_pct_for(sym):g}"
    return d


def _log_setting_changes(before: dict, after: dict, source: str) -> list:
    changes = [f"{k}: {before.get(k)} -> {v}" for k, v in after.items() if before.get(k) != v]
    for c in changes:
        _log(f"Setting changed ({source}): {c}")
    return changes


def _save_control(control: dict):
    """Merge a dashboard change into the saved control file (never overwrite it): a one-field
    change such as the Start/Stop button must not wipe every other saved setting."""
    merged = {}
    try:
        with open(CONTROL_FILE) as f:
            merged = json.load(f)
    except Exception:
        pass
    for k, v in control.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)          # e.g. risk_pct_by_symbol: saving one pair must keep the others
        else:
            merged[k] = v
    with open(CONTROL_FILE, "w") as f:
        json.dump(merged, f)


def _clear_control_keys(keys):
    """A setting given explicitly on the command line beats the value saved from the dashboard."""
    try:
        with open(CONTROL_FILE) as f:
            saved = json.load(f)
    except Exception:
        return
    changed = False
    for k in keys:
        if k in saved:
            del saved[k]
            changed = True
    if changed:
        with open(CONTROL_FILE, "w") as f:
            json.dump(saved, f)


def _profile_summary() -> str:
    on = [f"{s} {_risk_pct_for(s):.2f}%" for s in SYMBOLS if s not in DISABLED_SYMBOLS]
    off = [s for s in SYMBOLS if s in DISABLED_SYMBOLS]
    return (f"Profile: ON {', '.join(on) or 'none'} | OFF {', '.join(off) or 'none'} | "
            f"daily-loss guard {DAILY_LOSS_GUARD_PCT}% | max drawdown {MAX_ACCOUNT_DRAWDOWN_PCT}% "
            f"of the account size | open-risk cap {MAX_CONCURRENT_RISK_PCT}% | "
            f"max {MAX_TRADES_PER_DAY} trades/day")


def verify_symbols():
    """After connecting: every configured pair must exist on THIS broker and be visible in Market
    Watch. Without this a wrong name or a hidden pair makes MT5 return no data and the bot just
    sits there doing nothing, with no error anywhere."""
    if not MT5_AVAILABLE:
        return
    try:
        all_names = None
        for sym in SYMBOLS:
            name = _resolve_broker_name(sym)
            info = mt5.symbol_info(name)
            if info is None:
                if all_names is None:
                    got = mt5.symbols_get()
                    all_names = [g.name for g in got] if got else []
                near = [n for n in all_names if sym.upper() in n.upper()][:6]
                _log(f"[{sym}] '{name}' does not exist on this broker. Similar names: {near or 'none found'}. "
                     f"If the broker adds a suffix (e.g. {sym}.r or {sym}m) start the bot with --suffix .r (or m). "
                     f"Until then this pair CANNOT trade.")
                continue
            if not getattr(info, "visible", True):
                ok = mt5.symbol_select(name, True)
                _log(f"[{sym}] '{name}' was not in Market Watch: {'added it' if ok else 'FAILED to add it'}.")
            if getattr(info, "trade_mode", None) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", -1):
                _log(f"[{sym}] trading is DISABLED for '{name}' on this account.")
    except Exception as e:
        _log(f"Symbol check failed (bot keeps running): {e}")


def _pip_value_per_lot(symbol, price) -> float:
    """Value of one pip per 1.0 lot, in the ACCOUNT's currency. MT5 publishes it (tick value and tick size), so
    this is right for any account currency, any broker contract size and any pair. Only if MT5 does not give
    it is the USD rule of thumb used (flat $10 when USD is the quote currency; moves with the rate when USD
    is the base currency)."""
    if MT5_AVAILABLE:
        try:
            info = mt5.symbol_info(_bn(symbol))
            tick_value = getattr(info, "trade_tick_value_loss", 0) or getattr(info, "trade_tick_value", 0)
            tick_size = getattr(info, "trade_tick_size", 0)
            if tick_value and tick_size and tick_value > 0 and tick_size > 0:
                return float(tick_value) * SYMBOL_SPECS[symbol]["pip_size"] / float(tick_size)
        except Exception:
            pass
    if symbol in USD_BASE_CURRENCY_SYMBOLS:
        return (100000 * SYMBOL_SPECS[symbol]["pip_size"]) / price
    return 10.0


def _risk_pct_of(symbol, volume, entry, sl, equity) -> float:
    if equity <= 0:
        return 0.0
    pips = abs(entry - sl) / SYMBOL_SPECS[symbol]["pip_size"]
    return pips * _pip_value_per_lot(symbol, entry) * volume / equity * 100.0


def get_total_open_risk_pct(equity) -> float:
    """Risk currently live across every symbol, % of equity. A trade already at breakeven risks
    nothing more, so it counts as 0 (same as HACVD, whose |entry - stop| is 0 at breakeven)."""
    total = 0.0
    for sym, st in _states.items():
        t = st.trade
        if t is None or (t.partial_done and t.be_moved):
            continue
        sl = t.initial_sl or t.sl_price
        total += _risk_pct_of(sym, t.volume, t.entry_price, sl, equity)
    return total


# 10012 timeout, 10031 no connection, 10011 generic error, or no reply at all: the server may have executed the order anyway.
_AMBIGUOUS_RETCODES = (10012, 10031, 10011)
AMBIGUOUS_ORDER_HOLD_SECONDS = 300   # a demo server was seen taking 2m45s to answer; a retry inside that window doubled the trade


def _order_may_have_filled(res) -> bool:
    return res is None or getattr(res, "retcode", None) in _AMBIGUOUS_RETCODES


def _order_ok(res) -> bool:
    return res is not None and getattr(res, "retcode", None) in (
        mt5.TRADE_RETCODE_DONE, getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", -1))


def _fetch_positions(symbol):
    """OUR positions (by magic) for a symbol, or None if the read failed —
    'could not read' must never be mistaken for 'position is gone'."""
    pos = mt5.positions_get(symbol=_bn(symbol))
    if pos is None:
        err = mt5.last_error()
        return [] if (err and err[0] == 1) else None
    return [p for p in pos if p.magic == MAGIC_NUMBER]


# ---------------- persistence (survives restarts) ----------------

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _state_path():
    return os.path.join(_script_dir(), f"nbro_state_{DASHBOARD_PORT}.json")


def _history_path():
    return os.path.join(_script_dir(), f"nbro_trades_{DASHBOARD_PORT}.json")


def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    os.replace(tmp, path)


def save_state():
    """Snapshot everything needed to carry on after a restart: open trades
    (incl. the target/partial plan that MT5 itself doesn't store), which
    session each symbol already traded (so a restart can't cause a second
    entry in the same session), and today's realized P&L for the guards."""
    try:
        g = _account_guard_state
        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "account_login": _last_login,
            "account_guard": {
                "current_day": g["current_day"],
                "day_start_equity": g["day_start_equity"],
                "closed_trades_today": list(g["closed_trades_today"]),
                "entries_today": g.get("entries_today", 0),
                "session_trade_counts": [[k[0], k[1], v] for k, v in g["session_trade_counts"].items()],
                "dd_high_water_mark": g.get("dd_high_water_mark", 0.0),   # trailing mode: must survive a restart —
                                    # Atlas's own trailing floor does not reset just because the bot restarted
            },
            "symbols": {},
        }
        for sym, st in _states.items():
            data["symbols"][sym] = {
                "phase": st.phase.value,
                "current_session_date": (str(st.current_session_date)
                                          if st.current_session_date is not None else None),
                "range_high": st.range_high,
                "range_low": st.range_low,
                "entry_attempts": st.entry_attempts,
                "last_check_k": st.last_check_k,
                "exit_k": st.exit_k,
                "session_hour_used": st.session_hour_used,
                "trade": asdict(st.trade) if st.trade is not None else None,
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
        _log(f"Could not read {os.path.basename(path)} ({e}) — starting with a clean state.")
        return False

    _restored_login = data.get("account_login")
    g = _account_guard_state
    ag = data.get("account_guard", {})
    if ag.get("current_day") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
        g["current_day"] = ag["current_day"]
        g["day_start_equity"] = ag.get("day_start_equity", 0.0)
        g["closed_trades_today"] = list(ag.get("closed_trades_today", []))
        g["entries_today"] = ag.get("entries_today", 0)
    # NOT gated on same-day: a trailing-mode high-water mark must survive every restart, any day,
    # same as the real prop-firm floor it mirrors does not reset just because the bot restarted.
    g["dd_high_water_mark"] = max(g.get("dd_high_water_mark", 0.0), ag.get("dd_high_water_mark", 0.0))
    for sym, date, n in ag.get("session_trade_counts", []):
        g["session_trade_counts"][(sym, date)] = n

    valid = {f.name for f in dc_fields(ActiveTrade)}
    for sym, sd in data.get("symbols", {}).items():
        if sym not in _states:
            continue
        st = _states[sym]
        try:
            st.phase = Phase(sd.get("phase", "WAITING_FOR_RANGE"))
        except ValueError:
            st.phase = Phase.WAITING_FOR_RANGE
        if sd.get("current_session_date"):
            st.current_session_date = pd.Timestamp(sd["current_session_date"])
        st.range_high = sd.get("range_high")
        st.range_low = sd.get("range_low")
        st.entry_attempts = sd.get("entry_attempts", 0)
        st.last_check_k = sd.get("last_check_k", -1)
        st.exit_k = sd.get("exit_k", -1)
        st.session_hour_used = sd.get("session_hour_used")
        if sd.get("trade"):
            st.trade = ActiveTrade(**{k: v for k, v in sd["trade"].items() if k in valid})
            st.phase = Phase.IN_TRADE
        elif st.phase == Phase.IN_TRADE:
            st.phase = Phase.WAITING_FOR_RANGE
    _log(f"Restored saved state from {os.path.basename(path)} "
         f"(saved {data.get('saved_at', '?')}).")
    return True


def _load_trade_history():
    path = _history_path()
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            rows = json.load(f)
    except Exception:
        return
    _recent_trades.clear()
    for r in rows[-MAX_RECENT_TRADES:]:
        _recent_trades.append(r)
    _log(f"Restored {len(_recent_trades)} closed trade(s) from {os.path.basename(path)}.")


def _record_closed_trade(rec: dict):
    _recent_trades.append(rec)
    try:
        _atomic_write_json(_history_path(), _snapshot_deque(_recent_trades))
    except Exception as e:
        _log(f"Could not write trade history (bot keeps running): {e}")


_startup_done = False


def _startup_restore():
    global _startup_done
    if _startup_done:
        return
    _startup_done = True
    _log(f"NBRO app version {APP_VERSION}")
    _load_trade_history()
    restore_state()
    _DEFAULT_RISK_SNAPSHOT.update(RISK_PCT_BY_SYMBOL)
    _before = _settings_snapshot()
    load_control()
    _log_setting_changes(_before, _settings_snapshot(), "saved from the dashboard earlier, applied at start-up")
    _log(_profile_summary())


# ---------------- closed-trade bookkeeping (real broker deals) ----------------

def _finalize_closed_trade(symbol, state) -> bool:
    """A trade we were managing is no longer an open position: stop-loss or
    breakeven-stop hit at the broker, a manual close, or it closed while
    the bot was offline. Reads the real deals to record the true exit, R,
    and dollar P&L (this is also what feeds the Daily Loss Guard — the old
    estimate-at-close approach never saw broker-side stop-outs at all)."""
    trade = state.trade
    deals = mt5.history_deals_get(position=trade.ticket) if trade.ticket else None
    # history_deals_get(position=...) alone is the correctly-scoped call; the explicit
    # position_id filter is a second, independent guard against ever attributing
    # another position's deal to this trade (a real bug HACVD hit on live trades).
    deals = [d for d in (deals or []) if getattr(d, "position_id", trade.ticket) == trade.ticket]
    out = [d for d in deals if d.entry in (mt5.DEAL_ENTRY_OUT, getattr(mt5, "DEAL_ENTRY_OUT_BY", -1))]
    entry_vol = trade.entry_volume or trade.volume

    if not out:
        state.finalize_attempts += 1
        if state.finalize_attempts < 8:
            return False            # deals may not be visible yet — retry next poll
        rec = {"symbol": symbol, "direction": trade.direction, "entry": trade.entry_price,
               "exit": None, "sl": trade.initial_sl, "target": trade.target_price,
               "volume": entry_vol, "r": None, "pnl": None,
               "reason": "closed (deal details unavailable)",
               "opened_at": trade.opened_at,
               "closed_at": datetime.now(timezone.utc).isoformat()}
    else:
        r_total = 0.0
        for d in out:
            move = ((d.price - trade.entry_price) if trade.direction == "LONG"
                    else (trade.entry_price - d.price))
            if trade.initial_risk > 0:
                r_total += (d.volume / entry_vol) * move / trade.initial_risk
        pnl = sum(d.profit + d.commission + d.swap for d in deals)
        last = max(out, key=lambda d: d.time)
        rc = getattr(last, "reason", None)
        if rc == mt5.DEAL_REASON_SL:
            reason = f"emergency stop ({EMERGENCY_STOP_PCT:g}%)"
        elif rc == mt5.DEAL_REASON_TP:
            reason = "target"
        elif rc == getattr(mt5, "DEAL_REASON_SO", -99):
            reason = "stop_out"
        elif str(getattr(last, "comment", "")).startswith("noise_manual"):
            reason = "manual (dashboard)"
        elif str(getattr(last, "comment", "")).startswith("noise_exit"):
            reason = "exit rule"
        elif str(getattr(last, "comment", "")).startswith("noise_eod"):
            reason = "end of session"
        elif str(getattr(last, "comment", "")).startswith("noise_guard"):
            reason = "guard flatten"
        else:
            reason = "manual/external"
        rec = {"symbol": symbol, "direction": trade.direction, "entry": trade.entry_price,
               "exit": last.price, "sl": trade.initial_sl, "target": trade.target_price,
               "volume": entry_vol, "r": round(r_total, 3), "pnl": round(pnl, 2),
               "reason": reason, "opened_at": trade.opened_at,
               "closed_at": _server_ts_to_utc_iso(last.time)}
        # already inside today's MT5-derived P&L if it closed before the last sync
        if last.time > _account_guard_state.get("synced_until", 0):
            record_closed_trade_pnl(pnl)

    _record_closed_trade(rec)
    emoji = "✅" if (rec["pnl"] or 0) > 0 else ("⚪" if (rec["pnl"] or 0) == 0 else "🔴")
    r_txt = f"{rec['r']:+.2f}R" if rec["r"] is not None else "n/a"
    pnl_txt = f"${rec['pnl']:+.2f}" if rec["pnl"] is not None else "n/a"
    send_telegram_alert(f"{emoji} CLOSED {symbol} {trade.direction}\n"
                        f"Reason: {rec['reason']} | R: {r_txt} | P&L: {pnl_txt}")
    _log(f"[{symbol}] Trade closed — {rec['reason']} | R {r_txt} | P&L {pnl_txt}")
    state.trade = None
    state.phase = (Phase.DONE_FOR_SESSION if (LOCK_AFTER_EMERGENCY_STOP and str(rec.get("reason", "")).startswith("emergency"))
                   else (Phase.RANGE_SET if state.frame and state.frame.get("ready") else Phase.WAITING_FOR_RANGE))
    state.finalize_attempts = 0
    state.live_snapshot = {}
    save_state()
    return True


_broker_offset_cache = None


def _broker_offset_seconds() -> int:
    if _CLOCK["offset_hours"] is not None:
        return int(_CLOCK["offset_hours"]) * 3600
    return _broker_offset_seconds_from_tick()


def _broker_offset_seconds_from_tick() -> int:
    """Broker server clock minus UTC, in whole hours (as seconds). A stale weekend tick
    can make this look absurd (HACVD measured -39h once), so anything beyond +-14h is
    rejected in favour of the last good value."""
    global _broker_offset_cache
    try:
        tick = mt5.symbol_info_tick(_bn(SYMBOLS[0]))
        if tick is not None:
            h = round((tick.time - time.time()) / 3600.0)
            if abs(h) <= 14:
                _broker_offset_cache = int(h) * 3600
    except Exception:
        pass
    return _broker_offset_cache or 0


def _recent_deals():
    """All account deals in the last few days, or None if the read failed. A wide range
    is used on purpose: date-range queries are quirky about timezones, so the exact
    window is filtered afterwards on the deal's own timestamp."""
    now = datetime.now(timezone.utc)
    deals = mt5.history_deals_get(now - timedelta(days=4), now + timedelta(days=1))
    return None if deals is None else list(deals)


def reconcile_open_positions(symbol, state, bars=None):
    """Called EVERY poll while the bot believes it is flat. If MT5 holds a position under our magic number, take it
    over and keep managing it, so a restart, a crash, a PC reboot or a deleted state file can never orphan a live
    trade and never lead to a second entry stacked on top of it. Everything is rebuilt from MT5 itself: entry,
    lots and time from the position; the stop distance from its stop-loss (or the emergency-stop percentage when the
    stop is missing, which the manager then re-applies)."""
    if not MT5_AVAILABLE or state.trade is not None:
        return
    positions = _fetch_positions(symbol)
    if not positions:
        return
    p = positions[0]
    if len(positions) > 1:
        _log(f"[{symbol}] WARNING: {len(positions)} open positions under this bot's magic number; "
             f"managing the oldest (#{p.ticket}) only — check the others by hand.")
    direction = "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT"
    deals = [d for d in (mt5.history_deals_get(position=p.ticket) or [])
             if getattr(d, "position_id", p.ticket) == p.ticket]
    ins = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    entry_vol = sum(d.volume for d in ins) or p.volume
    entry = p.price_open
    if p.sl and abs(p.sl - entry) > 0:
        risk = abs(entry - p.sl)
        how = "stop distance taken from the position's stop-loss"
    else:
        risk = entry * EMERGENCY_STOP_PCT / 100.0
        how = f"no stop-loss on the position: the {EMERGENCY_STOP_PCT:g}% emergency stop will be re-applied"
    initial_sl = (entry - risk) if direction == "LONG" else (entry + risk)
    register_trade(state, direction, entry, initial_sl, p.volume, 0.0)
    t = state.trade
    t.ticket = p.ticket
    t.entry_volume = entry_vol
    t.initial_sl = initial_sl
    t.opened_at = _server_ts_to_utc_iso(p.time)
    state.current_session_date = get_session_date(pd.Timestamp(p.time, unit="s"))
    _log(f"[{symbol}] TOOK OVER open {direction} #{p.ticket} from MT5 — {p.volume} lots @ {entry:.2f} ({how}). Managing it again.")
    send_telegram_alert(f"🔁 {symbol}: bot reconnected to open {direction} #{p.ticket} "
                        f"({p.volume} lots @ {entry:.2f}) and is managing it again.")
    save_state()
def _sync_daily_from_mt5(quiet=False):
    """Read today's realized P&L and the day-start balance from MT5's deal history. Done at start-up AND
    every ~30 seconds afterwards: it used to run only at start-up, so losses from anything else on the
    account (another bot, a manual trade) stayed invisible until the next restart, when the number would
    suddenly jump. The whole account is read, the way a prop firm counts the daily loss."""
    acct = mt5.account_info()
    deals = _recent_deals()
    if acct is None or deals is None:
        return
    now = datetime.now(timezone.utc)
    off = _broker_offset_seconds()
    midnight_epoch = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) + off
    buy, sell = getattr(mt5, "DEAL_TYPE_BUY", 0), getattr(mt5, "DEAL_TYPE_SELL", 1)
    bal_type = getattr(mt5, "DEAL_TYPE_BALANCE", 2)
    # A deposit (paper-money top-up on a demo) made today RESTARTS the day's count from that moment: the account is
    # treated as freshly funded, so what was lost before the top-up no longer blocks trading. A real prop account
    # never has a deposit in the middle of a day, so nothing changes there. Withdrawals do not restart anything.
    deposits_today = [d for d in deals if d.time >= midnight_epoch and getattr(d, "type", None) == bal_type and d.profit > 0]
    restart_at = max((d.time for d in deposits_today), default=None)
    since = restart_at if restart_at is not None else midnight_epoch - 1
    today = [d for d in deals if d.time > since and getattr(d, "type", buy) in (buy, sell)]
    pnl_all = sum(d.profit + d.commission + d.swap for d in today)
    ops_today = sum(d.profit for d in deals if d.time > since and getattr(d, "type", None) == bal_type)
    counted = pnl_all
    g = _account_guard_state
    previous = sum(g["closed_trades_today"]) if g.get("current_day") == now.strftime("%Y-%m-%d") else None
    g["entries_today"] = sum(1 for d in deals if d.time > since and d.entry == mt5.DEAL_ENTRY_IN
                             and getattr(d, "magic", MAGIC_NUMBER) == MAGIC_NUMBER)   # also restarts after a deposit
    if restart_at is not None:
        try:
            g["entries_today"] += sum(1 for p in (mt5.positions_get() or [])
                                      if getattr(p, "magic", MAGIC_NUMBER) == MAGIC_NUMBER and midnight_epoch <= p.time <= restart_at)
        except Exception:
            pass
    g["current_day"] = now.strftime("%Y-%m-%d")
    g["day_start_equity"] = getattr(acct, "balance", acct.equity) - pnl_all - ops_today   # a paper-money top-up today is not part of the day-start balance
    # trailing-mode high-water mark: the highest EOD/day-start balance seen so far. Harmless to
    # recompute every call (this function may run several times per day) since max() is idempotent.
    g["dd_high_water_mark"] = max(g.get("dd_high_water_mark", INITIAL_ACCOUNT_BALANCE), g["day_start_equity"])
    g["closed_trades_today"] = [counted]
    g["ops_today"] = ops_today
    g["synced_until"] = int(now.timestamp()) + off
    restarted = restart_at is not None and g.get("restart_at") != restart_at
    g["restart_at"] = restart_at
    if restarted:
        amount = sum(d.profit for d in deposits_today if d.time == restart_at)
        when = datetime.fromtimestamp(restart_at - off, timezone.utc).strftime("%H:%M")
        _log(f"Deposit of ${amount:,.2f} at {when} UTC: today's count restarts from there, as a freshly funded account.")
    if restarted or not quiet or previous is None or abs(previous - counted) > 0.005:
        _log(f"Daily P&L from MT5: {counted:+.2f} today (day-start balance {g['day_start_equity']:.2f}).")


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


STANDARD_ACCOUNT_SIZES = (1000, 2000, 2500, 5000, 10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000,
                          100000, 150000, 200000, 250000, 300000, 400000, 500000)


def _balance_deposits():
    """Every positive balance operation (deposit) in the account history, oldest first, or None if it can't be read."""
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
    """The starting size a static drawdown is measured from. A prop account has ONE deposit: that is the size.
    A demo that was topped up with paper money has several, and the first one says nothing (it was $1,000 on a
    demo that is really a $50,000 account), so then the answer is the standard account size nearest to the
    balance (5K, 10K, 25K, 50K, 100K...). Only if the balance is not near any standard size is the balance itself used."""
    deposits = _balance_deposits() or []
    if len(deposits) == 1:
        return deposits[0], "the account's only deposit, read from the MT5 history"
    size = min(STANDARD_ACCOUNT_SIZES, key=lambda x: abs(balance - x) / x)
    if abs(balance - size) / size <= 0.15:
        note = f"{len(deposits)} deposits in the history" if deposits else "no deposit record in the history"
        return float(size), f"the standard account size nearest to its balance of ${balance:,.0f} ({note})"
    return balance, "its balance right now (it is not near a standard account size)"


def _read_control_file() -> dict:
    try:
        with open(CONTROL_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _check_account_identity(login):
    """State and history files are named by PORT. Pointing an instance at a different account (a 5K demo after a
    50K one, say) would otherwise load the other account's open trades and history. The files remember which
    account wrote them; on a mismatch they are archived and this instance starts clean."""
    global _last_login, _restored_login
    if login is None:
        return
    if _restored_login is not None and _restored_login != login:
        _log(f"WARNING: the saved state on this port belongs to account {_restored_login}, but MT5 is now connected "
             f"to account {login}. Archiving it and starting clean for this account.")
        for f in (_state_path(), _history_path()):
            try:
                if os.path.exists(f):
                    os.replace(f, f + f".account{_restored_login}.bak")
            except OSError:
                pass
        for sym in list(_states):
            _states[sym] = SymbolState()
        _recent_trades.clear()
        _account_guard_state.update({"current_day": None, "day_start_equity": 0.0, "closed_trades_today": [],
                                     "session_trade_counts": {}, "entries_today": 0,
                                     "dd_high_water_mark": 0.0})   # another account's peak must not become this one's floor
        _restored_login = None
    _last_login = login


def _resolve_account_base():
    """One bot for any account size: everything is a % of the account except the drawdown floor's base, the
    account's STARTING size. It is worked out once per account (see _detect_account_base) and remembered with the
    account number, so a different account (5K, 10K, 25K, 50K...) gets its own automatically. A base typed in
    Settings, or --balance, is never overwritten for the same account."""
    global INITIAL_ACCOUNT_BALANCE
    try:
        acct = mt5.account_info()
        if acct is None:
            return
        bal = getattr(acct, "balance", acct.equity)
        login = getattr(acct, "login", None)
        currency = getattr(acct, "currency", None)
        if currency and currency != "USD":
            _log(f"Account currency is {currency}: lot sizes use MT5's own tick values, so they are correct in {currency}; "
                 f"every money figure in this dashboard is in {currency}.")
        ctl = _read_control_file()
        verified = ("initial_account_balance" in ctl and ctl.get("account_login") == login
                    and ctl.get("base_mode") in ("auto", "manual"))
        if _BALANCE_SET_BY_CLI or verified:
            if login is not None and ctl.get("account_login") != login and _BALANCE_SET_BY_CLI:
                _save_control({"account_login": login})
            return
        base, source = _detect_account_base(bal)
        INITIAL_ACCOUNT_BALANCE = round(base, 2)
        _save_control({"initial_account_balance": INITIAL_ACCOUNT_BALANCE, "account_login": login, "base_mode": "auto"})
        floor = INITIAL_ACCOUNT_BALANCE * (1 - MAX_ACCOUNT_DRAWDOWN_PCT / 100.0)
        _log(f"Account {login}: drawdown base ${INITIAL_ACCOUNT_BALANCE:,.0f} = {source}. With max drawdown "
             f"{MAX_ACCOUNT_DRAWDOWN_PCT:g}% the floor is ${floor:,.0f} (the drawdown % is your firm's rule and is not "
             f"in MT5: change it in Settings or start with --max-dd).")
    except Exception as e:
        _log(f"Account base check failed (bot keeps running): {e}")


def reconcile_positions():
    """After every (re)connect: rebuild daily P&L from MT5, then take over any position
    the broker still holds for us. Trades this bot had already saved are picked up by the
    per-poll manager; anything else is adopted straight from MT5."""
    if not MT5_AVAILABLE:
        return
    try:
        _check_account_identity(getattr(mt5.account_info(), "login", None))
    except Exception as e:
        _log(f"Account check failed (bot keeps running): {e}")
    try:
        _sync_daily_from_mt5()
    except Exception as e:
        _log(f"Daily P&L sync from MT5 failed (bot keeps running): {e}")
    _resolve_account_base()
    for symbol in SYMBOLS:
        st = _states[symbol]
        if st.trade is None:
            reconcile_open_positions(symbol, st)
        else:
            _log(f"[{symbol}] Resuming saved {st.trade.direction} #{st.trade.ticket}; "
                 f"it will be checked against MT5 on the next poll.")
    save_state()


# ---------------- live orchestration ----------------

_last_equity = None
_last_balance = None
_last_daily_sync = 0.0
_last_login = None            # the MT5 account this instance is connected to
_restored_login = None        # the account that wrote the saved state file
_BALANCE_SET_BY_CLI = False   # --balance given on the command line always wins


def _profit_target_reached():
    """(reached, gained_pct). Uses the account BALANCE (closed profit) against the starting balance, since
    prop-firm targets are normally counted on closed results, not on floating profit."""
    if PROFIT_TARGET_PCT is None or INITIAL_ACCOUNT_BALANCE <= 0 or _last_balance is None:
        return False, None
    gained = (_last_balance - INITIAL_ACCOUNT_BALANCE) / INITIAL_ACCOUNT_BALANCE * 100.0
    return gained >= PROFIT_TARGET_PCT, gained


def _skip_signal(state, symbol, direction, why, logs):
    logs.append(f"[{symbol}] Signal skipped — {why}")
    send_telegram_alert(f"❌ SIGNAL SKIPPED — {symbol} {direction}\n{why}")
    state.last_signal_price = None            # the next check can try again; nothing is chased in between
    save_state()
_range_tried = {}


_dup_tries = {}


DUPLICATE_RETRY_BACKOFF_SECONDS = 600   # after 3 quick tries, keep retrying every 10 min instead of giving up forever


def _close_duplicate_positions(symbol, extras, logs):
    """The plan is ONE trade per symbol per session. A second position of ours on the same symbol (typically a
    timed-out order that filled late) is not tracked, so it had no partial, no breakeven, no target and was left out
    of the open-risk total. Close it at market and say so.

    Tries every poll for the first 3 attempts (matches the original behaviour), then backs off to one attempt
    every DUPLICATE_RETRY_BACKOFF_SECONDS instead of surrendering permanently — a duplicate found during a
    connection outage (MT5 auth errors, timeouts) used to need a manual bot restart to get another attempt;
    now it keeps trying on its own until it succeeds or the person closes it by hand."""
    now = time.time()
    for p in extras:
        info = _dup_tries.get(p.ticket, {"count": 0, "last_attempt": 0.0})
        if info["count"] >= 3 and now - info["last_attempt"] < DUPLICATE_RETRY_BACKOFF_SECONDS:
            continue   # cooling down between backed-off attempts; still reported periodically below on the next try
        info["count"] += 1
        info["last_attempt"] = now
        _dup_tries[p.ticket] = info
        direction = "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT"
        res = close_partial(symbol, p.ticket, p.volume, direction)
        if _order_ok(res):
            msg = (f"[{symbol}] DUPLICATE position #{p.ticket} ({direction} {p.volume} lots @ {p.price_open}) closed at market. "
                   f"The plan is one trade per symbol per session; this second position (most likely a timed-out order that "
                   f"filled late) doubled the risk and was not being managed.")
            logs.append(msg)
            send_telegram_alert("⚠️ " + msg)
            _dup_tries.pop(p.ticket, None)
        elif info["count"] <= 3:
            logs.append(f"[{symbol}] DUPLICATE position #{p.ticket} found but closing it failed "
                        f"(retcode {getattr(res, 'retcode', None)}): retrying next poll ({info['count']}/3).")
        else:
            _warn_once(f"dup{p.ticket}",
                      f"[{symbol}] DUPLICATE position #{p.ticket} still could not be closed after {info['count']} tries "
                      f"(retcode {getattr(res, 'retcode', None)}). Will keep retrying automatically every "
                      f"{DUPLICATE_RETRY_BACKOFF_SECONDS // 60} min — no restart needed. If this keeps failing, "
                      f"close it by hand in MT5.", every=DUPLICATE_RETRY_BACKOFF_SECONDS)


def _close_reason_for(state, latest):
    """Why this trade has to be closed NOW, independent of the 30-minute rule: (comment tag, text) or None."""
    sd = state.current_session_date
    if latest is not None and sd is not None:
        if get_session_date(latest) != sd:
            return ("noise_eod", "carried over from an earlier session")
        if session_is_over(latest, sd):
            return ("noise_eod", "end of session")
    if DAILY_LOSS_FLATTEN_ENABLED and DAILY_LOSS_GUARD_ENABLED:
        d = compute_daily_loss_pct()
        if d is not None and d >= DAILY_LOSS_GUARD_PCT:
            return ("noise_guard", f"Daily Loss Guard {d:.2f}% >= {DAILY_LOSS_GUARD_PCT}%: positions flattened")
    if DAILY_LOSS_FLATTEN_ENABLED and MAX_ACCOUNT_DRAWDOWN_ENABLED and _last_equity is not None:
        dd = compute_overall_drawdown_status(_last_equity)
        if dd["blocked"]:
            return ("noise_guard", f"Max Drawdown Guard: equity {_last_equity:.2f} at/below the safety line {dd['stop_new_entries_below']:.2f}: positions flattened")
    return None


def _manage_open_trade(symbol, state, logs):
    trade = state.trade
    positions = _fetch_positions(symbol)
    if positions is None:
        return                      # can't see the broker this poll — don't guess
    pos = next((p for p in positions if p.ticket == trade.ticket), None)
    if pos is None:
        _finalize_closed_trade(symbol, state)
        return

    extras = [p for p in positions if p.ticket != trade.ticket]
    if extras:
        _close_duplicate_positions(symbol, extras, logs)

    if state.close_requested:
        res = close_partial(symbol, trade.ticket, pos.volume, trade.direction, comment="noise_manual")
        if _order_ok(res):
            logs.append(f"[{symbol}] Closed at market — " + ("Protector shield." if _shield_tripped_today() else "requested from the dashboard."))
            state.close_requested = False
            _finalize_closed_trade(symbol, state)
        else:
            logs.append(f"[{symbol}] Dashboard close request failed (retcode {getattr(res, 'retcode', None)}): "
                        f"will try again next poll.")
        return

    trade.volume = pos.volume
    tick = mt5.symbol_info_tick(_bn(symbol))
    if tick is None:
        return
    price = tick.bid if trade.direction == "LONG" else tick.ask
    risk = trade.initial_risk
    fr = None
    if risk > 0:
        fr = ((price - trade.entry_price) if trade.direction == "LONG"
              else (trade.entry_price - price)) / risk
    state.live_snapshot = {"price": price, "r": round(fr, 3) if fr is not None else None,
                           "profit": pos.profit, "sl": pos.sl}

    # Heal: the emergency stop must always exist at the broker.
    if not pos.sl:
        ok = _order_ok(modify_sl(symbol, trade.ticket,
                                 _round_price(symbol, trade.initial_sl or trade.sl_price)))
        logs.append(f"[{symbol}] Position had no stop-loss — {'re-applied' if ok else 'FAILED to re-apply'} it.")

    bars = get_rates(symbol)
    latest = bars["time"].iloc[-1] if bars is not None and len(bars) else None
    reason = _close_reason_for(state, latest)

    # The exit rule, at every 30-minute check
    if reason is None and latest is not None and state.current_session_date is not None:
        sd = state.current_session_date
        if state.frame is None or not state.frame.get("ready"):
            state.frame = noise_frame(bars, sd)
        k = due_check(latest, sd, state.exit_k)
        if k is not None and state.frame and state.frame.get("ready"):
            state.exit_k = k
            state.last_check_k = max(state.last_check_k, k)       # this check was spent on managing the trade: no new entry at it unless we exit now
            ctx = noise_context(bars, state.frame, sd, k)
            if ctx is None:
                logs.append(f"[{symbol}] Exit check {k + 1}: the bar of the check time is missing in the data — kept the trade.")
            else:
                state.ctx = ctx
                state.range_high, state.range_low = ctx["UB"], ctx["LB"]
                trade.target_price = noise_exit_line(trade.direction, ctx["vwap"], ctx["UB"], ctx["LB"])
                if noise_exit_due(trade.direction, ctx["P"], ctx["vwap"], ctx["UB"], ctx["LB"]):
                    reason = ("noise_exit", f"exit rule at check {k + 1}: price {ctx['P']:.2f} is {'below' if trade.direction == 'LONG' else 'above'} "
                                            f"the exit line {trade.target_price:.2f}")
                else:
                    logs.append(f"[{symbol}] Exit check {k + 1}: price {ctx['P']:.2f}, exit line {trade.target_price:.2f} — keeping the {trade.direction}.")
            save_state()

    if reason is None:
        return
    tag, text = reason
    if _order_ok(close_partial(symbol, trade.ticket, pos.volume, trade.direction, comment=tag)):
        logs.append(f"[{symbol}] Closing the {trade.direction}: {text}.")
        if tag == "noise_exit":
            # the entry stage of the SAME check may now take the opposite side (the tested rule allows the flip)
            state.last_check_k = min(state.last_check_k, state.exit_k - 1)
        _finalize_closed_trade(symbol, state)
    else:
        logs.append(f"[{symbol}] Close ({text}) FAILED — will retry next poll.")
def _try_enter(symbol, state, bars, equity, logs):
    direction = state.last_signal_direction
    entry_price = state.last_signal_price

    if time.time() < state.ambiguous_until:
        return
    existing = _fetch_positions(symbol)
    if existing is None:
        return                                  # can't see the broker this poll: don't guess
    if existing:
        state.last_signal_price = None          # we already hold a position here (the take-over adopts it): never stack a second one
        return

    reached, gained = _profit_target_reached()
    if reached:
        return _skip_signal(state, symbol, direction,
                            f"Profit target reached: +{gained:.2f}% >= {PROFIT_TARGET_PCT:g}% — no new trades.", logs)
    if DAILY_LOSS_GUARD_ENABLED:
        d = compute_daily_loss_pct()
        if d is not None and d >= DAILY_LOSS_GUARD_PCT:
            return _skip_signal(state, symbol, direction,
                                f"Daily Loss Guard: {d:.2f}% >= {DAILY_LOSS_GUARD_PCT}% limit.", logs)
    if MAX_ACCOUNT_DRAWDOWN_ENABLED:
        dd = compute_overall_drawdown_status(equity)
        if dd["blocked"]:
            return _skip_signal(state, symbol, direction,
                                f"Max Drawdown Guard: equity {equity:.2f} at/below safety line "
                                f"{dd['stop_new_entries_below']:.2f}.", logs)
    if PER_SESSION_CAP_ENABLED:
        count = _session_trade_count(symbol, state.current_session_date)
        if count >= PER_SESSION_TRADE_CAP:
            return _skip_signal(state, symbol, direction,
                                f"Per-session trade cap reached ({count}/{PER_SESSION_TRADE_CAP}).", logs)
    if MAX_TRADES_PER_DAY_ENABLED:
        cap = min(MAX_TRADES_PER_DAY, MAX_TRADES_PER_DAY_CEILING)
        n = _account_guard_state.get("entries_today", 0)
        if n >= cap:
            return _skip_signal(state, symbol, direction,
                                f"Max trades per day reached ({n}/{cap}).", logs)
    if NEWS_PROTECTION_ENABLED:
        blocked, event_name = is_news_blackout(datetime.now(timezone.utc))
        if blocked:
            return _skip_signal(state, symbol, direction, f"News blackout ({event_name}).", logs)

    sl = _round_price(symbol, emergency_stop_price(direction, entry_price))

    if MAX_ENTRY_SLIPPAGE_ENABLED:
        tick = mt5.symbol_info_tick(_bn(symbol))
        if tick is not None:
            live_price = tick.ask if direction == "LONG" else tick.bid
            risk_dist = abs(entry_price - sl)
            unfav = ((live_price - entry_price) if direction == "LONG" else (entry_price - live_price))
            slip_r = (unfav / risk_dist) if risk_dist > 0 else 0.0
            if slip_r > MAX_ENTRY_SLIPPAGE_R:
                return _skip_signal(state, symbol, direction,
                                    f"Max Slippage Guard: price moved {slip_r:.3f}R ({unfav:.2f} points) unfavorably "
                                    f"(decision {entry_price:.2f} -> live {live_price:.2f}).", logs)

    if MAX_SPREAD_GUARD_ENABLED:
        tick = mt5.symbol_info_tick(_bn(symbol))
        if tick is not None:
            risk_dist = abs(entry_price - sl)
            spread = float(tick.ask) - float(tick.bid)
            spread_r = (spread / risk_dist) if risk_dist > 0 else 0.0
            if spread_r > MAX_SPREAD_R:
                ident = (state.current_session_date, round(float(entry_price), 6), direction)
                rec = _spread_wait_since.get(symbol)
                first = rec is None or rec[0] != ident
                if first:
                    rec = (ident, time.time())
                    _spread_wait_since[symbol] = rec
                waited = time.time() - rec[1]
                pips = spread / SYMBOL_SPECS[symbol]["pip_size"]
                if waited < SPREAD_WAIT_SECONDS:
                    if first:
                        logs.append(f"[{symbol}] Spread guard: the spread is {pips:.1f} points = {spread_r:.3f}R of the stop distance (limit {MAX_SPREAD_R:g}R). "
                                    f"Waiting up to {SPREAD_WAIT_SECONDS}s for it to come down; the signal is kept.")
                    return
                _spread_wait_since.pop(symbol, None)
                return _skip_signal(state, symbol, direction,
                                    f"Max Spread Guard: still {pips:.1f} points = {spread_r:.3f}R after {waited:.0f}s (limit {MAX_SPREAD_R:g}R).", logs)
            if symbol in _spread_wait_since:
                logs.append(f"[{symbol}] Spread guard: the spread is back to {spread / SYMBOL_SPECS[symbol]['pip_size']:.1f} points ({spread_r:.3f}R): entering.")
                _spread_wait_since.pop(symbol, None)

    if USE_RISK_BASED_SIZING:
        vol = calculate_lot_size(equity, _risk_pct_for(symbol), entry_price, sl, symbol)
    else:
        vol = DEFAULT_LOT_SIZE.get(symbol, 0.10)
    vol = _normalize_volume(symbol, vol)

    if MAX_CONCURRENT_RISK_ENABLED:
        new_risk = _risk_pct_of(symbol, vol, entry_price, sl, equity)
        open_risk = get_total_open_risk_pct(equity)
        if open_risk + new_risk > MAX_CONCURRENT_RISK_PCT + 1e-9:
            return _skip_signal(state, symbol, direction,
                                f"Max concurrent risk: {open_risk:.2f}% already open + {new_risk:.2f}% new "
                                f"> {MAX_CONCURRENT_RISK_PCT}% cap.", logs)

    res = send_market_order(symbol, direction, vol, sl, comment="noise")
    filled_anyway = False
    if not _order_ok(res) and _order_may_have_filled(res):
        time.sleep(1.0)
        if _fetch_positions(symbol):          # we were flat on this symbol, so any position of ours IS this order
            filled_anyway = True
            logs.append(f"[{symbol}] The order reply was retcode {getattr(res, 'retcode', None)}, but MT5 already holds our "
                        f"position: treating it as filled, no retry.")
    if not _order_ok(res) and not filled_anyway:
        state.entry_attempts += 1
        state.last_signal_price = None
        why = f"retcode {getattr(res, 'retcode', None)} {getattr(res, 'comment', mt5.last_error())}"
        unsure = _order_may_have_filled(res)
        if unsure:
            state.ambiguous_until = time.time() + AMBIGUOUS_ORDER_HOLD_SECONDS
        checked = (f" MT5 shows no position yet, but a lagging server can still fill it: holding "
                   f"{AMBIGUOUS_ORDER_HOLD_SECONDS // 60} minutes before any retry (a late fill is taken over, never doubled).") if unsure else ""
        logs.append(f"[{symbol}] ORDER REJECTED ({why}) — attempt {state.entry_attempts}/3, NOT counted as a trade.{checked}")
        if state.entry_attempts >= 3:
            state.phase = Phase.DONE_FOR_SESSION
            send_telegram_alert(f"⚠️ {symbol} {direction}: order rejected 3x ({why}). Giving up for this session.")
        save_state()
        return

    positions = _fetch_positions(symbol) or []
    pos = max(positions, key=lambda p: p.time) if positions else None
    fill = pos.price_open if pos else entry_price
    register_trade(state, direction, fill, sl, pos.volume if pos else vol, 0.0)
    t = state.trade
    t.ticket = pos.ticket if pos else getattr(res, "order", None)
    t.entry_volume = vol
    t.initial_sl = sl
    t.opened_at = datetime.now(timezone.utc).isoformat()
    state.exit_k = max(state.exit_k, state.last_check_k)       # the check that opened the trade is not also an exit check
    ctx = state.ctx or {}
    if ctx:
        t.target_price = noise_exit_line(direction, ctx["vwap"], ctx["UB"], ctx["LB"])
    _increment_session_trade_count(symbol, state.current_session_date)
    _account_guard_state["entries_today"] = _account_guard_state.get("entries_today", 0) + 1
    logs.append(f"[{symbol}] Entered {direction} {vol} lots @ {fill:.2f} emergency-stop={sl:.2f}")
    send_telegram_alert(
        f"🚀 ENTRY {direction} — {symbol}\n"
        f"Fill: {fill:.2f} | Lots: {vol}\n"
        f"Emergency stop: {sl:.2f} ({EMERGENCY_STOP_PCT:g}%)\n"
        + (f"Band {ctx['LB']:.2f} - {ctx['UB']:.2f} | VWAP {ctx['vwap']:.2f}\n" if ctx else "")
        + "Noise Area momentum: exits by the rule at the next 30-min check, or at the session close")
    save_state()


def _shield_tripped_today() -> bool:
    return _shield_state["day"] == datetime.now(timezone.utc).date().isoformat()


def check_protector_shield(account, logs) -> None:
    """Close this bot's positions when the ACCOUNT's open loss reaches the shield line (see PROTECTOR_SHIELD_PCT).
    Atlas measures the whole account, so floating losses of other bots / manual trades count too; this bot can only
    close its own positions and says so when the rest of the loss is not its own."""
    if PROTECTOR_SHIELD_PCT <= 0 or account is None or INITIAL_ACCOUNT_BALANCE <= 0:
        return
    floating = float(account.equity) - float(getattr(account, "balance", account.equity))
    open_loss_pct = -floating / INITIAL_ACCOUNT_BALANCE * 100.0
    if open_loss_pct < PROTECTOR_SHIELD_PCT:
        return
    first = not _shield_tripped_today()
    _shield_state["day"] = datetime.now(timezone.utc).date().isoformat()
    mine = [s for s, st in _states.items() if st.trade is not None]
    for s in mine:
        _states[s].close_requested = True
    if first:
        others = "" if mine else " None of the open positions are this bot's: close them yourself."
        msg = (f"PROTECTOR SHIELD: account open loss {open_loss_pct:.2f}% of the starting balance reached "
               f"{PROTECTOR_SHIELD_PCT:g}% (Atlas Protector fires at 2%). Closing {', '.join(mine) or 'nothing'}; "
               f"no new entries until the next UTC day.{others}")
        logs.append(msg)
        send_telegram_alert("🛡 " + msg)


def _process_symbol_inner(symbol, logs):
    global _last_equity, _last_balance
    state = _states[symbol]
    account = mt5.account_info() if MT5_AVAILABLE else None
    if account:
        _last_equity = account.equity
        _last_balance = getattr(account, "balance", account.equity)
        if MAX_ACCOUNT_DRAWDOWN_MODE == "trailing":
            # Conservative: ALSO follow live equity peaks, not only each day's starting balance. Whether a
            # firm trails on end-of-day balance or on intraday equity highs isn't always clear from its
            # dashboard; if this guess is too tight the cost is stopping NEW entries a little early, if it
            # were too loose the cost could be a breached account — so lean tight.
            _account_guard_state["dd_high_water_mark"] = max(
                _account_guard_state.get("dd_high_water_mark", 0.0), account.equity)
    equity = account.equity if account else (_last_equity or INITIAL_ACCOUNT_BALANCE)
    _roll_account_day_if_needed(equity)
    check_protector_shield(account, logs)

    # Flat in memory but MT5 holds a position of ours? Take it over (before anything else).
    if state.trade is None:
        reconcile_open_positions(symbol, state)

    # An open trade is ALWAYS managed, even if the symbol was stopped from the dashboard.
    if state.phase == Phase.IN_TRADE and state.trade is not None:
        _manage_open_trade(symbol, state, logs)
        if state.trade is not None:
            return
    if state.ambiguous_until and time.time() < state.ambiguous_until:
        return          # waiting to see whether a timed-out order fills (the takeover above adopts it if it does)
    if symbol in DISABLED_SYMBOLS:
        return
    if _shield_tripped_today():
        return          # Protector shield tripped today: no new entries until the next UTC day

    bars = get_rates(symbol)
    if bars is None or len(bars) < 2:
        return
    if state.last_signal_price is not None and state.signal_ts:
        if bars["time"].iloc[-1] - pd.Timestamp(state.signal_ts) >= pd.Timedelta(minutes=MAX_CHECK_LATE_MINUTES):
            logs.append(f"[{symbol}] The {state.last_signal_direction} signal is older than {MAX_CHECK_LATE_MINUTES} minutes — dropped.")
            state.last_signal_price = None
    logs.extend(analyze_symbol(symbol, bars, state))
    if state.phase == Phase.RANGE_SET and state.last_signal_price is not None:
        _try_enter(symbol, state, bars, equity, logs)
def process_symbol(symbol: str) -> List[str]:
    """One live poll for one symbol (shared by the console loop and the
    dashboard loop, so there is a single code path)."""
    logs: List[str] = []
    try:
        _process_symbol_inner(symbol, logs)
    finally:
        for l in logs:
            _log(l)
    return logs



def get_status_dict() -> dict:
    equity = _last_equity if _last_equity is not None else INITIAL_ACCOUNT_BALANCE
    daily_loss_pct = compute_daily_loss_pct()
    drawdown = compute_overall_drawdown_status(equity)
    open_trades = []
    for _sym, _st in _states.items():
        if _st.trade is not None:
            t = _st.trade
            snap = _st.live_snapshot or {}
            open_trades.append({
                "symbol": _sym, "direction": t.direction, "entry": t.entry_price,
                "sl": snap.get("sl") or t.initial_sl or t.sl_price, "target": (t.target_price or None),
                "volume": t.volume, "partial_done": t.partial_done, "opened_at": t.opened_at,
                "price": snap.get("price"), "r": snap.get("r"), "profit": snap.get("profit")})
    closed = _snapshot_deque(_recent_trades)
    rs = [c["r"] for c in closed if c.get("r") is not None]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trade_stats = {
        "trades": len(closed),
        "wins": sum(1 for r in rs if r > 0),
        "win_rate": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else 0,
        "total_r": round(sum(rs), 2),
        "total_pnl": round(sum(c.get("pnl") or 0 for c in closed), 2),
        "today_r": round(sum(c["r"] for c in closed
                             if c.get("r") is not None and str(c.get("closed_at", ""))[:10] == today), 2),
    }
    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": {},
        "activity_log": _snapshot_deque(_activity_log)[-MAX_LOG_LINES:],
        "recent_trades": _snapshot_deque(_recent_trades)[-MAX_RECENT_TRADES:],
        "open_trades": open_trades,
        "trade_stats": trade_stats,
        "clock": get_clock_status(),
        "version": APP_VERSION,
        "config": {
            "noise_lookback_days": NOISE_LOOKBACK_DAYS,
            "emergency_stop_pct": EMERGENCY_STOP_PCT,
            "orb_session_hour": ORB_SESSION_HOUR,
            "risk_pct": RISK_PCT,
            "risk_pct_by_symbol": {k: RISK_PCT_BY_SYMBOL.get(k, RISK_PCT) for k in SYMBOLS},
            "symbol_notes": SYMBOL_NOTES,
            "symbol_stats": SYMBOL_STATS,
            "default_risk_by_symbol": {k: (_DEFAULT_RISK_SNAPSHOT or RISK_PCT_BY_SYMBOL).get(k, RISK_PCT) for k in SYMBOLS},
            "disabled_symbols": list(DISABLED_SYMBOLS),
            "daily_loss_guard_enabled": DAILY_LOSS_GUARD_ENABLED,
            "daily_loss_guard_pct": DAILY_LOSS_GUARD_PCT,
            "max_account_drawdown_enabled": MAX_ACCOUNT_DRAWDOWN_ENABLED,
            "initial_account_balance": INITIAL_ACCOUNT_BALANCE,
            "max_account_drawdown_pct": MAX_ACCOUNT_DRAWDOWN_PCT,
            "per_session_cap_enabled": PER_SESSION_CAP_ENABLED,
            "per_session_trade_cap": PER_SESSION_TRADE_CAP,
            "max_trades_per_day_enabled": MAX_TRADES_PER_DAY_ENABLED,
            "max_trades_per_day": min(MAX_TRADES_PER_DAY, MAX_TRADES_PER_DAY_CEILING),
            "max_trades_per_day_ceiling": MAX_TRADES_PER_DAY_CEILING,
            "max_concurrent_risk_enabled": MAX_CONCURRENT_RISK_ENABLED,
            "max_concurrent_risk_pct": MAX_CONCURRENT_RISK_PCT,
            "news_protection_enabled": NEWS_PROTECTION_ENABLED,
            "news_window_before_min": NEWS_WINDOW_BEFORE_MIN,
            "news_window_after_min": NEWS_WINDOW_AFTER_MIN,
            "max_entry_slippage_enabled": MAX_ENTRY_SLIPPAGE_ENABLED,
            "max_entry_slippage_r": MAX_ENTRY_SLIPPAGE_R,
            "max_spread_guard_enabled": MAX_SPREAD_GUARD_ENABLED,
            "max_spread_r": MAX_SPREAD_R,
            "use_risk_based_sizing": USE_RISK_BASED_SIZING,
            "telegram_enabled": _load_telegram_config_cached(round(time.time() / 10) * 10).get("enabled", False),
        },
        "guards": {
            "equity": equity,
            "daily_loss_pct": daily_loss_pct,
            "daily_loss_dollars": (round(compute_daily_loss_dollars(), 2) if compute_daily_loss_dollars() is not None else None),
            "daily_limit_dollars": round(DAILY_LOSS_GUARD_PCT / 100.0 * INITIAL_ACCOUNT_BALANCE, 2),
            "account_size": INITIAL_ACCOUNT_BALANCE,
            "daily_loss_blocked": (daily_loss_pct is not None and DAILY_LOSS_GUARD_ENABLED
                                    and daily_loss_pct >= DAILY_LOSS_GUARD_PCT),
            "drawdown": drawdown,
            "next_news_event": get_next_news_event(),
            "entries_today": _account_guard_state.get("entries_today", 0),
            "account_balance": _last_balance,
            "day_start_equity": _account_guard_state.get("day_start_equity", 0.0),
            "open_risk_pct": round(get_total_open_risk_pct(equity), 3),
        },
    }
    for symbol, state in _states.items():
        out["symbols"][symbol] = {
            "phase": state.phase.value,
            "direction_mode": state.trade.direction if state.trade is not None else "FLAT",
            "vwap": (state.ctx or {}).get("vwap"),
            "price_at_check": (state.ctx or {}).get("P"),
            "check_time": str((state.ctx or {}).get("ts", "")) or None,
            "range_high": state.range_high,
            "range_low": state.range_low,
            "last_criteria": state.last_criteria,
            "disabled": symbol in DISABLED_SYMBOLS,
            "trade": None if state.trade is None else {
                "direction": state.trade.direction,
                "entry_price": state.trade.entry_price,
                "sl_price": state.trade.sl_price,
                "target_price": (state.trade.target_price or None),
                "volume": state.trade.volume,
                "partial_done": state.trade.partial_done,
            },
        }
    return out


def write_status(path: str = None):
    if path is None:
        path = STATUS_FILE   # resolved at call time so --port can change it
    try:
        with open(path, "w") as f:
            json.dump(get_status_dict(), f, indent=2, default=str)
    except Exception:
        pass


def load_control(path: str = None):
    if path is None:
        path = CONTROL_FILE  # resolved at call time so --port can change it
    global RISK_PCT
    global DAILY_LOSS_GUARD_ENABLED, DAILY_LOSS_GUARD_PCT
    global MAX_ACCOUNT_DRAWDOWN_ENABLED, INITIAL_ACCOUNT_BALANCE, MAX_ACCOUNT_DRAWDOWN_PCT
    global PER_SESSION_CAP_ENABLED, PER_SESSION_TRADE_CAP
    global NEWS_PROTECTION_ENABLED, MAX_ENTRY_SLIPPAGE_ENABLED, MAX_ENTRY_SLIPPAGE_R
    global MAX_SPREAD_GUARD_ENABLED, MAX_SPREAD_R
    global USE_RISK_BASED_SIZING
    global MAX_TRADES_PER_DAY_ENABLED, MAX_TRADES_PER_DAY
    global MAX_CONCURRENT_RISK_ENABLED, MAX_CONCURRENT_RISK_PCT
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            control = json.load(f)
    except Exception:
        return
    if "risk_pct" in control:
        RISK_PCT = float(control["risk_pct"])
    for _k, _v in (control.get("risk_pct_by_symbol") or {}).items():
        try:
            RISK_PCT_BY_SYMBOL[_k] = max(0.05, min(float(_v), 5.0))
        except (TypeError, ValueError):
            pass
    if "daily_loss_guard_enabled" in control:
        DAILY_LOSS_GUARD_ENABLED = bool(control["daily_loss_guard_enabled"])
    if "daily_loss_guard_pct" in control:
        DAILY_LOSS_GUARD_PCT = float(control["daily_loss_guard_pct"])
    if "max_account_drawdown_enabled" in control:
        MAX_ACCOUNT_DRAWDOWN_ENABLED = bool(control["max_account_drawdown_enabled"])
    if "initial_account_balance" in control:
        INITIAL_ACCOUNT_BALANCE = float(control["initial_account_balance"])
    if "max_account_drawdown_pct" in control:
        MAX_ACCOUNT_DRAWDOWN_PCT = float(control["max_account_drawdown_pct"])
    if "per_session_cap_enabled" in control:
        PER_SESSION_CAP_ENABLED = bool(control["per_session_cap_enabled"])
    if "per_session_trade_cap" in control:
        PER_SESSION_TRADE_CAP = int(control["per_session_trade_cap"])
    if "news_protection_enabled" in control:
        NEWS_PROTECTION_ENABLED = bool(control["news_protection_enabled"])
    if "max_entry_slippage_enabled" in control:
        MAX_ENTRY_SLIPPAGE_ENABLED = bool(control["max_entry_slippage_enabled"])
    if "max_entry_slippage_r" in control:
        MAX_ENTRY_SLIPPAGE_R = float(control["max_entry_slippage_r"])
    if "max_spread_guard_enabled" in control:
        MAX_SPREAD_GUARD_ENABLED = bool(control["max_spread_guard_enabled"])
    if "max_spread_r" in control:
        MAX_SPREAD_R = float(control["max_spread_r"])
    if "use_risk_based_sizing" in control:
        USE_RISK_BASED_SIZING = bool(control["use_risk_based_sizing"])
    if "max_trades_per_day_enabled" in control:
        MAX_TRADES_PER_DAY_ENABLED = bool(control["max_trades_per_day_enabled"])
    if "max_trades_per_day" in control:
        MAX_TRADES_PER_DAY = max(1, min(int(control["max_trades_per_day"]), MAX_TRADES_PER_DAY_CEILING))
    if "max_concurrent_risk_enabled" in control:
        MAX_CONCURRENT_RISK_ENABLED = bool(control["max_concurrent_risk_enabled"])
    if "max_concurrent_risk_pct" in control:
        MAX_CONCURRENT_RISK_PCT = float(control["max_concurrent_risk_pct"])
    if "disabled_symbols" in control:      # only when the key is present: a partial save must not re-enable everything
        DISABLED_SYMBOLS.clear()
        DISABLED_SYMBOLS.update(control["disabled_symbols"])


def run(poll_seconds: int = 15):
    """Console entry point. Same connection-retry fix as
    orb_dashboard_server.py's bot_loop() — a single failed mt5.initialize()
    used to end the whole function permanently instead of retrying."""
    _startup_restore()
    if not MT5_AVAILABLE:
        print("MetaTrader5 package not available. Install it with "
              "'pip install MetaTrader5' and re-run.")
        return

    connected = False
    print(f"Starting NBRO bot on {SYMBOLS}. Ctrl+C to stop.")
    try:
        while True:
            if not connected:
                if _mt5_init():
                    connected = True
                    term_info = mt5.terminal_info()
                    print(f"MT5 connected. Trade allowed: "
                          f"{getattr(term_info, 'trade_allowed', '?')}")
                    _log(f"NBRO bot started on {SYMBOLS}. Noise band over the last {NOISE_LOOKBACK_DAYS} sessions, "
                         f"session open {ORB_SESSION_HOUR}:{SESSION_OPEN_MINUTE:02d} (server time).")
                    verify_symbols()
                    refresh_session_clock(force=True)
                    reconcile_positions()
                    if term_info is not None and not getattr(term_info, "trade_allowed", True):
                        print("WARNING: 'Algo Trading' / 'AutoTrading' looks OFF in the "
                              "MT5 terminal toolbar — orders will be rejected until enabled.")
                else:
                    print(f"MT5 connection failed: {mt5.last_error()}. Retrying in 30s. "
                          f"Common causes: terminal not running, not logged into a real "
                          f"account, or 'Allow DLL imports' unchecked in "
                          f"Tools > Options > Expert Advisors.")
                    time.sleep(30)
                    continue

            if mt5.terminal_info() is None:
                connected = False
                print("MT5 connection appears to have dropped — will retry.")
                continue

            load_control()
            refresh_session_clock()
            refresh_daily_pnl()
            for symbol in SYMBOLS:
                try:
                    for line in process_symbol(symbol):
                        print(line)
                except Exception as e:
                    print(f"[{symbol}] ERROR during poll: {type(e).__name__}: {e}")
            save_state()
            write_status()
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\nStopping (Ctrl+C)...")
    finally:
        save_state()
        mt5.shutdown()
        open_now = [f"{sym} {st.trade.direction} #{st.trade.ticket}" for sym, st in _states.items() if st.trade is not None]
        print("Stopped. " + (f"{len(open_now)} open trade(s) stay open in MT5 with their stop-loss ({', '.join(open_now)}); "
                             f"the next start takes them over again." if open_now else "No open trades."))


# ============================================================
# WEB DASHBOARD — embedded HTML/JS (single-file, same pattern as HACVD's
# hacvd_app.py: no separate .html/.js files on disk, served directly from
# these string constants)
# ============================================================

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NBRO — Noise-Band Risk-Optimizer</title>
<style>
  :root {
    --bg: #0a0e16;
    --panel: #10151f;
    --panel-border: #1c2534;
    --text: #cdd6e3;
    --text-dim: #6b7789;
    --accent: #38bdf8;
    --green: #34d399;
    --red: #f87171;
    --amber: #fbbf24;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Inter, Roboto, sans-serif;
    font-size: 13px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 20px;
    border-bottom: 1px solid var(--panel-border);
  }
  header .title { font-size: 15px; font-weight: 600; color: #fff; }
  header .subtitle { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
  header .right { display: flex; align-items: center; gap: 14px; font-size: 11px; color: var(--text-dim); }
  .live-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(52,211,153,0.12); color: var(--green);
    padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 500;
  }
  .live-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }

  nav {
    display: flex; gap: 4px; padding: 0 20px;
    border-bottom: 1px solid var(--panel-border);
  }
  nav button {
    background: none; border: none; color: var(--text-dim);
    padding: 10px 14px; font-size: 12.5px; cursor: pointer;
    border-bottom: 2px solid transparent;
  }
  nav button.active { color: var(--accent); border-bottom-color: var(--accent); }
  nav button:hover:not(.active) { color: var(--text); }

  main { padding: 20px; max-width: 1200px; margin: 0 auto; }
  .tabpage { display: none; }
  .tabpage.active { display: block; }

  .symbol-picker { margin-bottom: 18px; position: relative; display: inline-block; }
  .symbol-pill {
    background: var(--panel); border: 1px solid var(--accent);
    color: var(--accent); padding: 6px 14px; border-radius: 999px;
    font-size: 13px; font-weight: 600; cursor: pointer;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .symbol-pill:after { content: "▾"; font-size: 10px; }
  .symbol-dropdown {
    display: none; position: absolute; top: 36px; left: 0; z-index: 10;
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 8px; min-width: 200px; overflow: hidden;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .symbol-dropdown.open { display: block; }
  .symbol-dropdown .opt {
    padding: 9px 14px; cursor: pointer; display: flex; justify-content: space-between; align-items: center;
  }
  .symbol-dropdown .opt:hover { background: #16202f; }
  .symbol-dropdown .opt .badge {
    font-size: 10px; padding: 1px 7px; border-radius: 999px; font-weight: 600;
  }
  .badge.confirmed { background: rgba(52,211,153,0.15); color: var(--green); }
  .badge.experimental { background: rgba(251,191,36,0.15); color: var(--amber); }

  .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
  .card {
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 14px 16px;
  }
  .card .label { font-size: 10.5px; color: var(--text-dim); letter-spacing: 0.3px; margin-bottom: 8px; }
  .card .value { font-size: 20px; font-weight: 600; color: #fff; }
  .card .sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
  .value.green { color: var(--green); }
  .value.red { color: var(--red); }
  .value.amber { color: var(--amber); }

  .panel {
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px; margin-bottom: 14px;
  }
  .panel-title { font-size: 11px; color: var(--text-dim); letter-spacing: 0.3px; margin-bottom: 12px; }

  .phase-row { display: flex; gap: 10px; }
  .phase-step {
    flex: 1; text-align: center; padding: 10px 8px; border-radius: 8px;
    border: 1px solid var(--panel-border); font-size: 11.5px; color: var(--text-dim);
  }
  .phase-step.current { border-color: var(--accent); color: var(--accent); background: rgba(56,189,248,0.06); }

  .checklist { display: flex; flex-direction: column; gap: 8px; }
  .check-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
  .check-row .name { color: var(--text); }
  .pill { font-size: 10.5px; padding: 2px 9px; border-radius: 999px; font-weight: 600; }
  .pill.yes { background: rgba(52,211,153,0.15); color: var(--green); }
  .pill.no { background: rgba(248,113,113,0.15); color: var(--red); }

  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; color: var(--text-dim); font-weight: 500; font-size: 10.5px; padding: 6px 8px; border-bottom: 1px solid var(--panel-border); }
  td { padding: 8px; border-bottom: 1px solid #131a26; }
  .dir-long { color: var(--green); font-weight: 600; }
  .dir-short { color: var(--red); font-weight: 600; }
  .r-pos { color: var(--green); }
  .r-neg { color: var(--red); }

  .log { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; max-height: 260px; overflow-y: auto; }
  .log-line { padding: 3px 0; color: var(--text-dim); border-bottom: 1px solid #10161f; }
  .empty-state { color: var(--text-dim); padding: 20px; text-align: center; font-size: 12px; }

  .settings-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #131a26; }
  .settings-row:last-child { border-bottom: none; }
  .settings-row .desc { font-size: 11px; color: var(--text-dim); margin-top: 3px; max-width: 480px; }
  input[type="number"] {
    background: #0d1320; border: 1px solid var(--panel-border); color: var(--text);
    padding: 6px 10px; border-radius: 6px; width: 90px; font-size: 12px;
  }
  select {
    background: #0d1320; border: 1px solid var(--panel-border); color: var(--text);
    padding: 6px 10px; border-radius: 6px; font-size: 12px;
  }
  .toggle {
    width: 38px; height: 20px; border-radius: 999px; background: #232d3f;
    position: relative; cursor: pointer; border: none;
  }
  .toggle.on { background: var(--accent); }
  .toggle .knob {
    width: 16px; height: 16px; border-radius: 50%; background: #fff;
    position: absolute; top: 2px; left: 2px; transition: left 0.15s;
  }
  .toggle.on .knob { left: 20px; }
  .guard-row { display: flex; gap: 24px; flex-wrap: wrap; }
  .guard-stat { flex: 1; min-width: 200px; }
  .guard-stat .big { font-size: 22px; font-weight: 700; color: #fff; }
  .guard-stat .big.amber { color: var(--amber); }
  .guard-stat .big.red { color: var(--red); }
  .guard-stat .big.green { color: var(--green); }
  .guard-stat .small { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
  .guard-blocked-banner {
    background: rgba(248,113,113,0.12); color: var(--red); border: 1px solid rgba(248,113,113,0.3);
    padding: 8px 12px; border-radius: 8px; font-size: 12px; margin-top: 12px;
  }
  .start-stop-btn {
    padding: 6px 16px; border-radius: 999px; font-size: 12px; font-weight: 600;
    border: none; cursor: pointer;
  }
  .start-stop-btn.running { background: rgba(52,211,153,0.15); color: var(--green); border: 1px solid rgba(52,211,153,0.4); }
  .start-stop-btn.stopped { background: rgba(248,113,113,0.15); color: var(--red); border: 1px solid rgba(248,113,113,0.4); }
  .apply-btn {
    background: var(--accent); color: #04121f; border: none; padding: 8px 18px;
    border-radius: 8px; font-size: 12.5px; font-weight: 600; cursor: pointer; margin-top: 14px;
  }
  #notice { position: fixed; top: 12px; right: 12px; max-width: 540px; padding: 10px 14px; border-radius: 8px;
            font-size: 12px; z-index: 50; display: none; line-height: 1.55; }
  #notice.ok { background: #0f2a22; border: 1px solid rgba(52,211,153,0.5); color: #6ee7b7; }
  #notice.error { background: #2a1414; border: 1px solid rgba(248,113,113,0.5); color: #fca5a5; }
  #uiErrors { display: none; background: #2a1414; color: #fca5a5; border-bottom: 1px solid rgba(248,113,113,0.5);
              padding: 6px 20px; font-size: 12px; }
</style>
</head>
<body>
<div id="uiErrors"></div>
<div id="notice"></div>

<header>
  <div>
    <div class="title">NBRO</div>
    <div class="subtitle">Noise Area intraday momentum — NAS100 + SPX500, US session, live monitor <span id="appVersion" style="opacity:.6;"></span></div>
  </div>
  <div class="right">
    <span id="lastPoll">Last poll: —</span>
    <span class="live-pill"><span class="dot"></span><span id="liveLabel">live</span></span>
  </div>
</header>

<nav>
  <button class="tab-btn active" data-tab="dashboard">Dashboard</button>
  <button class="tab-btn" data-tab="trades">Trades</button>
  <button class="tab-btn" data-tab="settings">Settings</button>
</nav>

<main>

  <div class="symbol-picker" style="display:flex; align-items:center; gap:12px;">
    <button class="symbol-pill" id="symbolPill" onclick="toggleSymbolDropdown()">NAS100</button>
    <div class="symbol-dropdown" id="symbolDropdown"></div>
    <button class="start-stop-btn running" id="startStopBtn" onclick="toggleSymbolRunning()">■ Stop NAS100</button>
    <button class="start-stop-btn" id="closeNowBtn" style="display:none; background:#5c1a1a; border-color:#7a2424;" onclick="closeSymbolNow()">✕ Close trade now</button>
  </div>

  <div id="tab-dashboard" class="tabpage active">
    <div class="cards" id="statCards">
      <div class="card"><div class="label">PHASE</div><div class="value" style="font-size:15px;">—</div></div>
      <div class="card"><div class="label">POSITION</div><div class="value" style="font-size:15px;">—</div></div>
      <div class="card"><div class="label">NOISE BAND</div><div class="value" style="font-size:14px;">—</div></div>
      <div class="card"><div class="label">OPEN TRADE</div><div class="value" style="font-size:15px;">—</div></div>
    </div>

    <div class="panel">
      <div class="panel-title" id="ddPanelTitle">MAX ACCOUNT DRAWDOWN GUARD</div>
      <div id="drawdownGuard" class="empty-state" style="text-align:left; padding:0;">Waiting for bot connection...</div>
    </div>

    <div class="panel">
      <div class="panel-title">SESSION / NOISE BAND</div>
      <div class="phase-row" id="phaseRow">
        <div class="phase-step">Building noise band</div>
        <div class="phase-step">Watching (band active)</div>
        <div class="phase-step">In trade</div>
        <div class="phase-step">Done for session</div>
      </div>
      <div class="empty-state" id="rangeInfo" style="text-align:left; padding: 12px 0 0;">No noise band yet for the current session.</div>
    </div>

    <div class="panel">
      <div class="panel-title">LIVE ENTRY CHECK</div>
      <div class="checklist" id="checklist"><div class="empty-state">No checks run yet this session.</div></div>
    </div>

    <div class="panel">
      <div class="panel-title">ACTIVITY LOG — real bot events only</div>
      <div class="log" id="activityLog"><div class="empty-state">Not connected to the bot yet — start nbro_app.py on the machine with your MT5 terminal.</div></div>
    </div>
  </div>

  <div id="tab-trades" class="tabpage">
    <div class="cards" id="tradeStats"></div>

    <div class="panel">
      <div class="panel-title">OPEN TRADES — managed automatically, also after a restart</div>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>Price now</th><th>SL</th><th>Exit line</th><th>Lots</th><th>Floating R</th><th>P&amp;L</th><th>Status</th></tr>
        </thead>
        <tbody id="openTradesBody"></tbody>
      </table>
      <div class="empty-state" id="openTradesEmpty">No open trades.</div>
    </div>

    <div class="panel">
      <div class="panel-title">TRADE HISTORY — saved to disk, survives restarts</div>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>Stop</th><th>Exit line</th><th>Lots</th><th>R</th><th>P&amp;L</th><th>Reason</th><th>Closed (UTC)</th></tr>
        </thead>
        <tbody id="tradesBody"></tbody>
      </table>
      <div class="empty-state" id="tradesEmpty" style="display:none;">No closed trades yet.</div>
    </div>
  </div>

  <div id="tab-settings" class="tabpage">
    <div class="panel" id="pairPanel">
      <div class="panel-title" id="pairPanelTitle">PAIR SETTINGS</div>
      <div class="desc" id="pairNote" style="padding:2px 0 10px;"></div>
      <div class="settings-row">
        <div>
          <div>Trading this pair</div>
          <div class="desc">Same as the Start/Stop button at the top. An open trade is still managed when it is OFF.</div>
        </div>
        <button class="toggle" id="pairToggle" data-on="0" onclick="toggleSymbolRunning()"><span class="knob"></span></button>
      </div>
      <div class="settings-row">
        <div>
          <div>Direction</div>
          <div class="desc" id="pairDirDesc"></div>
        </div>
        <span class="pill" id="pairDirPill"></span>
      </div>
      <div class="settings-row">
        <div>
          <div>Risk % per trade</div>
          <div class="desc" id="pairRiskDesc"></div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="pairRisk" step="0.05" min="0.05" max="5" style="width:80px;">
          <button class="apply-btn" style="padding:6px 14px;" onclick="savePairRisk()">Save</button>
          <button class="apply-btn" id="pairResetBtn" style="padding:6px 14px; background:transparent; border:1px solid #2a3550; color:#8aa0c0;" onclick="resetPairRisk()">Reset to default</button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Backtest for this pair</div>
          <div class="desc" id="pairStats"></div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">STRATEGY: fixed (the tested rule, nothing to tune)</div>
      <div class="desc" style="padding:4px 0;">Every 30 minutes from 10:00 to 15:30 New York: price above the upper band = long, below the lower band = short; the band is the usual size of the day's move
        (average of the last 14 sessions) around today's open / yesterday's close. A trade exits when price falls back inside the band past VWAP, or at 15:55 New York. Hard emergency stop 1% at the broker.
        These numbers are what the backtest used, so they are not editable here.</div>
    </div>

    <div class="panel">
      <div class="panel-title">RISK</div>
      <div class="desc" style="padding:4px 0;">Risk % per trade is set <b>per pair</b> in the pair panel at the top (it follows the pair you select). Each pair has its own default, sized from the real backtest so the pairs running together stay inside a prop firm's limits.</div>
    </div>

    <div class="panel">
      <div class="panel-title">ACCOUNT GUARDS: apply to all pairs together (ported from HACVD)</div>
      <div class="settings-row">
        <div>
          <div>Daily Loss Guard</div>
          <div class="desc">Blocks NEW entries once today's loss (open trades included) reaches this % of the account's starting size, the way a prop firm counts its daily limit (FundedNext $50K: 5% = $2,500). Set it to about 60% of your firm's limit. A paper-money deposit made today restarts the count (and today's trade count) from that moment. Never force-closes an open trade.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="dailyLossPct" step="0.1" min="0.5" max="20" style="width:70px;" value="1.8">
          <button class="toggle on" id="dailyLossToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div id="ddRowLabel">Max Account Drawdown</div>
          <div class="desc">Balance = the account's starting size (5K, 10K, 25K, 50K...), found automatically for each account. Type a number only if your firm's starting balance is different. Drawdown % is your firm's rule (usually 5% or 10%) and is not in MT5.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="initialBalance" step="500" min="500" style="width:90px;" title="Initial account balance" value="5000">
          <input type="number" id="maxDrawdownPct" step="0.5" min="1" max="50" style="width:70px;" title="Max drawdown %" value="5">
          <button class="toggle on" id="drawdownToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Per-session trade cap</div>
          <div class="desc">Max entries per symbol per session. The strategy can re-enter after an exit at a later check; 6 is the most 12 checks would ever need.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="sessionCap" step="1" min="1" max="10" style="width:70px;" value="1">
          <button class="toggle on" id="sessionCapToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Max trades per day (all symbols)</div>
          <div class="desc">No new entry once this many trades were opened today (UTC day). On 6 months of real data: 4 keeps 99% of the profit, 3 keeps 90%. Ceiling 6.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="maxTradesDay" step="1" min="1" max="6" style="width:70px;" value="4">
          <button class="toggle on" id="maxTradesDayToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Max concurrent open risk %</div>
          <div class="desc">Total risk of ALL open trades together (a trade at breakeven counts 0). Set to about the sum of the Risk % of the pairs you run together, e.g. EURUSD 0.5% + USDCAD 0.35% = 0.85%.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="maxOpenRisk" step="0.05" min="0.1" max="10" style="width:70px;" value="0.9">
          <button class="toggle on" id="maxOpenRiskToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>News Protection Guard</div>
          <div class="desc">Blocks new entries within a window around known high-impact events (CPI, FOMC, ECB, BOE, NFP) — a maintained static calendar, not a live feed.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <button class="toggle on" id="newsGuardToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Max Entry Slippage Guard</div>
          <div class="desc">Skips the entry if the live price has already moved this many R away from the decision price by the time the order would be sent — avoids silently taking on more risk than intended.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="slippageR" step="0.05" min="0.05" max="2" style="width:70px;" value="0.3">
          <button class="toggle on" id="slippageToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Max Spread Guard</div>
          <div class="desc">While the live spread is wider than this many R of the stop distance, the entry WAITS (the signal is kept, retried every poll, up to 90 seconds), then the session is given up. Spreads spike for seconds around the US open and news (USDJPY at Atlas: 0.3 pips normally, 6-18 in a spike), and a market order pays all of it.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <input type="number" id="spreadR" step="0.01" min="0.02" max="1" style="width:70px;" value="0.15">
          <button class="toggle on" id="spreadToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
      <div class="settings-row">
        <div>
          <div>Telegram Alerts</div>
          <div class="desc">Entry/exit/skipped-signal notifications. Configured separately via <code>set_telegram_alerts.py</code> (keeps the bot token out of the dashboard/web UI) — this is a status readout only.</div>
        </div>
        <span class="pill no" id="telegramStatusPill">not configured</span>
      </div>
      <div class="settings-row">
        <div>
          <div>Risk-based position sizing</div>
          <div class="desc">On (default): lot size computed from each pair's Risk % (pair panel at the top) x account equity, scaled to each trade's stop distance.</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <button class="toggle on" id="riskSizingToggle" data-on="1" onclick="toggleSwitch(this)"><span class="knob"></span></button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">ALL PAIRS: click one to edit it above</div>
      <div id="symbolToggles"><div class="empty-state">Loading pairs...</div></div>
    </div>

    <button class="apply-btn" onclick="applySettings()">Apply settings</button>
  </div>

</main>

<script src="dashboard.js"></script>
</body>
</html>
"""

_DASHBOARD_JS = """let currentSymbol = null;
let latestStatus = null;

const CONFIRMED = {
  "NAS100": "candidate", "SPX500": "candidate",
};

function toggleSymbolDropdown() {
  document.getElementById("symbolDropdown").classList.toggle("open");
}

document.addEventListener("click", (e) => {
  const picker = document.querySelector(".symbol-picker");
  if (picker && !picker.contains(e.target)) {
    document.getElementById("symbolDropdown").classList.remove("open");
  }
});

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tabpage").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

function selectSymbol(sym) {
  currentSymbol = sym;
  document.getElementById("symbolPill").textContent = sym;
  document.getElementById("symbolDropdown").classList.remove("open");
  if (latestStatus) render(latestStatus);
}

function renderStartStopBtn(status) {
  const btn = document.getElementById("startStopBtn");
  const isDisabled = status.config.disabled_symbols.includes(currentSymbol);
  if (isDisabled) {
    btn.textContent = "▶ Start " + currentSymbol;
    btn.className = "start-stop-btn stopped";
  } else {
    btn.textContent = "■ Stop " + currentSymbol;
    btn.className = "start-stop-btn running";
  }
  const closeBtn = document.getElementById("closeNowBtn");
  const hasOpenTrade = (status.open_trades || []).some(t => t.symbol === currentSymbol);
  closeBtn.style.display = hasOpenTrade ? "inline-block" : "none";
  closeBtn.textContent = "✕ Close " + currentSymbol + " now";
}

function closeSymbolNow() {
  if (!confirm("Close the open " + currentSymbol + " trade at market right now?\\n\\nThis cannot be undone. The broker will record it the same as any other bot-closed trade.")) {
    return;
  }
  const btn = document.getElementById("closeNowBtn");
  btn.disabled = true;
  fetch("/close", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: currentSymbol }) })
    .then(r => r.json())
    .then(res => {
      btn.disabled = false;
      if (!res.ok) { alert("Could not close " + currentSymbol + ": " + (res.error || "unknown error")); return; }
      alert(currentSymbol + " close requested — it will close at market within about 15 seconds.");
      refresh();
    })
    .catch(e => { btn.disabled = false; alert("Could not reach the bot: " + e); });
}

function toggleSymbolRunning() {
  if (!latestStatus) return;
  const current = latestStatus.config.disabled_symbols.slice();
  const idx = current.indexOf(currentSymbol);
  if (idx === -1) {
    current.push(currentSymbol);   // was running -> stop it
  } else {
    current.splice(idx, 1);        // was stopped -> start it
  }
  postControl({ disabled_symbols: current }).then(() => refresh());
}

function renderSymbolDropdown(status) {
  const dd = document.getElementById("symbolDropdown");
  const symbols = Object.keys(status.symbols);
  if (!currentSymbol) currentSymbol = symbols[0];
  dd.innerHTML = symbols.map(s => {
    const tag = "experimental";
    const label = "candidate";
    return `<div class="opt" onclick="selectSymbol('${s}')">
              <span>${s}</span>
              <span class="badge ${tag}">${label}</span>
            </div>`;
  }).join("");
  document.getElementById("symbolPill").textContent = currentSymbol;
}

const PHASES = ["WAITING_FOR_RANGE", "RANGE_SET", "IN_TRADE", "DONE_FOR_SESSION"];
const PHASE_LABELS = {
  "WAITING_FOR_RANGE": "Building noise band",
  "RANGE_SET": "Watching (band active)",
  "IN_TRADE": "In trade",
  "DONE_FOR_SESSION": "Done for session",
};

const uiErrors = {};

function showUiErrors() {
  const el = document.getElementById("uiErrors");
  const names = Object.keys(uiErrors);
  el.style.display = names.length ? "block" : "none";
  el.textContent = names.map(n => "Display error in " + n + ": " + uiErrors[n]).join("   |   ");
}

// One broken panel must never blank the rest of the dashboard (it used to: the first error aborted
// everything after it and was reported as 'offline').
function safe(name, fn) {
  try { fn(); delete uiErrors[name]; }
  catch (e) { uiErrors[name] = e.message || String(e); console.error("Dashboard section '" + name + "' failed:", e); }
  showUiErrors();
}

let noticeTimer = null;
function showNotice(text, kind) {
  const el = document.getElementById("notice");
  el.className = kind === "error" ? "error" : "ok";
  el.textContent = text;
  el.style.display = "block";
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { el.style.display = "none"; }, kind === "error" ? 15000 : 9000);
}

function fmtNum(v, digits=5) {
  if (v === null || v === undefined) return "—";
  return Number(v).toFixed(digits);
}

function fmtR(v) {
  if (v === null || v === undefined) return "—";
  const s = (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "R";
  return s;
}

function render(status) {
  latestStatus = status;
  const pollTime = new Date(status.updated_at);
  document.getElementById("lastPoll").textContent = "Last poll: " + pollTime.toLocaleTimeString();

  const sym = currentSymbol;
  const s = status.symbols[sym];
  safe("pair selector", () => renderSymbolDropdown(status));
  safe("guards panel", () => renderGuards(status));
  safe("start/stop button", () => renderStartStopBtn(status));
  safe("version", () => { if (status.version) document.getElementById("appVersion").textContent = " | v" + status.version; });
  safe("pair settings", () => renderPairPanel());
  safe("pairs overview", () => renderSymbolToggles(status));

  // Stat cards
  if (s) safe("stat cards", () => {
  const trade = s.trade;
  const cardsHtml = `
    <div class="card">
      <div class="label">PHASE</div>
      <div class="value" style="font-size:15px;">${PHASE_LABELS[s.phase] || s.phase}</div>
    </div>
    <div class="card">
      <div class="label">DIRECTION MODE</div>
      <div class="value ${s.direction_mode === 'SHORT' ? 'red' : (s.direction_mode === 'LONG' ? 'green' : '')}" style="font-size:15px;">${s.direction_mode}</div>
      <div class="sub">${s.price_at_check ? 'price ' + fmtNum(s.price_at_check) + ' at the ' + (s.check_time || '').slice(11, 16) + ' server-time check' : 'long, short or flat: the band decides'}</div>
    </div>
    <div class="card">
      <div class="label">NOISE BAND</div>
      <div class="value" style="font-size:14px;">${s.range_low !== null ? fmtNum(s.range_low) + ' – ' + fmtNum(s.range_high) : '—'}</div>
      <div class="sub">${s.vwap ? 'VWAP ' + fmtNum(s.vwap) + ' · ' : ''}average of the last ${status.config.noise_lookback_days} sessions</div>
    </div>
    <div class="card">
      <div class="label">OPEN TRADE</div>
      <div class="value ${trade ? (trade.direction === 'LONG' ? 'green' : 'red') : ''}" style="font-size:15px;">
        ${trade ? trade.direction + ' @ ' + fmtNum(trade.entry_price) : 'None'}
      </div>
      <div class="sub">${trade ? 'Exits by the rule at the next 30-min check, or 15:55 New York' : (s.disabled ? 'Symbol disabled' : 'Scanning')}</div>
    </div>
  `;
  document.getElementById("statCards").innerHTML = cardsHtml;

  });

  // Phase row
  if (s) safe("phase row", () => {
  document.getElementById("phaseRow").innerHTML = PHASES.map(p =>
    `<div class="phase-step ${p === s.phase ? 'current' : ''}">${PHASE_LABELS[p]}</div>`
  ).join("");

  document.getElementById("rangeInfo").innerHTML = s.range_high !== null
    ? `Upper band <b style="color:#fff">${fmtNum(s.range_high)}</b> &nbsp;·&nbsp; Lower band <b style="color:#fff">${fmtNum(s.range_low)}</b> &nbsp;·&nbsp; Width ${fmtNum(s.range_high - s.range_low)} &nbsp;(as of the last check)`
    : `No noise band yet for the current session (needs the open of today's session and 14 earlier full sessions).`;

  });

  // Checklist
  if (s) safe("entry checklist", () => {
  const criteria = s.last_criteria || [];
  const names = {
    "session_open": "Today's session has started",
    "history": "14 earlier full sessions found",
    "band_ready": "Noise band ready",
    "outside_band": "Price outside the band at the check",
    "check_on_time": "Check seen on time (not stale)",
  };
  document.getElementById("checklist").innerHTML = criteria.length
    ? criteria.map(c => `
        <div class="check-row">
          <span class="name">${names[c.name] || c.name}</span>
          <span class="pill ${c.pass ? 'yes' : 'no'}">${c.pass ? 'yes' : 'no'}</span>
        </div>`).join("")
    : `<div class="empty-state">No checks run yet this session.</div>`;

  });

  // Activity log (global, not per-symbol)
  safe("activity log", () => {
  const log = status.activity_log || [];
  document.getElementById("activityLog").innerHTML = log.length
    ? log.slice().reverse().map(l => `<div class="log-line">${escapeHtml(l)}</div>`).join("")
    : `<div class="empty-state">No activity yet.</div>`;

  });

  // Trade stats, open trades, history (global, all symbols)
  safe("trades tab", () => {
  const dg = (sym) => (sym && sym.endsWith("JPY")) ? 3 : 5;
  const ts = status.trade_stats || {};
  const totR = ts.total_r || 0, todR = ts.today_r || 0, totP = ts.total_pnl || 0;
  document.getElementById("tradeStats").innerHTML = `
    <div class="card"><div class="label">CLOSED TRADES</div><div class="value">${ts.trades || 0}</div><div class="sub">Win rate ${ts.win_rate || 0}%</div></div>
    <div class="card"><div class="label">TOTAL R</div><div class="value ${totR >= 0 ? 'green' : 'red'}">${fmtR(totR)}</div></div>
    <div class="card"><div class="label">TODAY R</div><div class="value ${todR >= 0 ? 'green' : 'red'}">${fmtR(todR)}</div></div>
    <div class="card"><div class="label">TOTAL P&amp;L</div><div class="value ${totP >= 0 ? 'green' : 'red'}">${fmtMoney(totP)}</div></div>`;

  const openT = status.open_trades || [];
  document.getElementById("openTradesEmpty").style.display = openT.length ? "none" : "block";
  document.getElementById("openTradesBody").innerHTML = openT.map(t => `
    <tr>
      <td>${t.symbol}</td>
      <td class="${t.direction === 'LONG' ? 'dir-long' : 'dir-short'}">${t.direction}</td>
      <td>${fmtNum(t.entry, dg(t.symbol))}</td>
      <td>${t.price == null ? '—' : fmtNum(t.price, dg(t.symbol))}</td>
      <td>${t.sl == null ? '—' : fmtNum(t.sl, dg(t.symbol))}</td>
      <td>${t.target == null ? '—' : fmtNum(t.target, dg(t.symbol))}</td>
      <td>${t.volume}</td>
      <td class="${(t.r || 0) >= 0 ? 'r-pos' : 'r-neg'}">${t.r == null ? '—' : fmtR(t.r)}</td>
      <td class="${(t.profit || 0) >= 0 ? 'r-pos' : 'r-neg'}">${t.profit == null ? '—' : fmtMoney(t.profit)}</td>
      <td>Running</td>
    </tr>`).join("");

  const trades = status.recent_trades || [];
  document.getElementById("tradesEmpty").style.display = trades.length ? "none" : "block";
  document.getElementById("tradesBody").innerHTML = trades.slice().reverse().map(t => `
    <tr>
      <td>${t.symbol}</td>
      <td class="${t.direction === 'LONG' ? 'dir-long' : 'dir-short'}">${t.direction}</td>
      <td>${fmtNum(t.entry, dg(t.symbol))}</td>
      <td>${t.exit == null ? '—' : fmtNum(t.exit, dg(t.symbol))}</td>
      <td>${t.sl == null ? '—' : fmtNum(t.sl, dg(t.symbol))}</td>
      <td>${t.target == null ? '—' : fmtNum(t.target, dg(t.symbol))}</td>
      <td>${t.volume == null ? '—' : t.volume}</td>
      <td class="${(t.r || 0) >= 0 ? 'r-pos' : 'r-neg'}">${t.r == null ? '—' : fmtR(t.r)}</td>
      <td class="${(t.pnl || 0) >= 0 ? 'r-pos' : 'r-neg'}">${t.pnl == null ? '—' : fmtMoney(t.pnl)}</td>
      <td>${t.reason}</td>
      <td>${new Date(t.closed_at || t.time).toLocaleString()}</td>
    </tr>`).join("");

  });

  // Settings tab population (only on first load or right after Apply, don't clobber in-progress edits)
  safe("settings", () => {
  if (!window._settingsPopulated) {
    document.getElementById("dailyLossPct").value = status.config.daily_loss_guard_pct;
    setToggle(document.getElementById("dailyLossToggle"), status.config.daily_loss_guard_enabled);
    document.getElementById("initialBalance").value = status.config.initial_account_balance;
    document.getElementById("maxDrawdownPct").value = status.config.max_account_drawdown_pct;
    setToggle(document.getElementById("drawdownToggle"), status.config.max_account_drawdown_enabled);
    document.getElementById("sessionCap").value = status.config.per_session_trade_cap;
    setToggle(document.getElementById("sessionCapToggle"), status.config.per_session_cap_enabled);
    document.getElementById("maxTradesDay").value = status.config.max_trades_per_day;
    setToggle(document.getElementById("maxTradesDayToggle"), status.config.max_trades_per_day_enabled);
    document.getElementById("maxOpenRisk").value = status.config.max_concurrent_risk_pct;
    setToggle(document.getElementById("maxOpenRiskToggle"), status.config.max_concurrent_risk_enabled);
    setToggle(document.getElementById("newsGuardToggle"), status.config.news_protection_enabled);
    document.getElementById("slippageR").value = status.config.max_entry_slippage_r;
    setToggle(document.getElementById("slippageToggle"), status.config.max_entry_slippage_enabled);
    document.getElementById("spreadR").value = status.config.max_spread_r;
    setToggle(document.getElementById("spreadToggle"), status.config.max_spread_guard_enabled);
    setToggle(document.getElementById("riskSizingToggle"), status.config.use_risk_based_sizing);
    const tgPill = document.getElementById("telegramStatusPill");
    tgPill.textContent = status.config.telegram_enabled ? "configured" : "not configured";
    tgPill.className = "pill " + (status.config.telegram_enabled ? "yes" : "no");
    renderSymbolToggles(status);
    window._settingsPopulated = true;
  }
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function setToggle(el, on) {
  el.classList.toggle("on", !!on);
  el.dataset.on = on ? "1" : "0";
}

function toggleSwitch(el) {
  setToggle(el, el.dataset.on !== "1");
}


function fmtMoney(v) {
  if (v === null || v === undefined) return "—";
  const sign = v < 0 ? "-" : "";
  return sign + "$" + Math.abs(v).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function renderGuards(status) {
  const g = status.guards;
  const dd = g.drawdown;
  const clk = status.clock || {};
  const pad2 = (n) => String(n).padStart(2, '0');
  const dailyPct = g.daily_loss_pct;
  const dailyLimit = status.config.daily_loss_guard_pct;

  // The floor is STATIC or TRAILING depending on how this copy was started (--dd-mode); say which, from the data itself
  // (trailing_base is only filled in trailing mode) — these labels used to say "static" no matter what.
  const ddMode = dd.trailing_base != null ? "TRAILING" : "STATIC";
  const ddTitle = document.getElementById("ddPanelTitle");
  if (ddTitle) ddTitle.textContent = "MAX ACCOUNT DRAWDOWN GUARD (" + ddMode + " FLOOR)";
  const ddRow = document.getElementById("ddRowLabel");
  if (ddRow) ddRow.textContent = "Max Account Drawdown (" + ddMode.toLowerCase() + " floor)";

  let html = `<div class="guard-row">
    <div class="guard-stat">
      <div class="small">REMAINING BEFORE ${ddMode} FLOOR</div>
      <div class="big ${dd.remaining_to_floor_dollars < status.config.initial_account_balance * 0.02 ? 'red' : (dd.blocked ? 'red' : '')}">${fmtMoney(dd.remaining_to_floor_dollars)}</div>
      <div class="small">Floor: ${fmtMoney(dd.floor)} · Stops new entries below ${fmtMoney(dd.stop_new_entries_below)}</div>
    </div>
    <div class="guard-stat">
      <div class="small">TODAY'S P&L (open trades included)</div>
      <div class="big ${dailyPct !== null && dailyPct >= dailyLimit ? 'red' : (dailyPct !== null && dailyPct >= dailyLimit * 0.7 ? 'amber' : (dailyPct !== null && dailyPct < 0 ? 'green' : ''))}">${dailyPct !== null ? ((dailyPct < 0 ? '+' : (dailyPct > 0 ? '-' : '')) + Math.abs(dailyPct).toFixed(2) + '%') : '—'}</div>
      <div class="small">${g.daily_loss_dollars != null ? (g.daily_loss_dollars < 0 ? ('Profit +' + fmtMoney(Math.abs(g.daily_loss_dollars)) + ' today. ') : (g.daily_loss_dollars > 0 ? ('Loss -' + fmtMoney(g.daily_loss_dollars) + ' today. ') : 'Break-even so far. ')) : ''}Daily loss guard ${dailyLimit}% = ${fmtMoney(g.daily_limit_dollars)} (of the ${fmtMoney(g.account_size)} account)${(g.daily_loss_dollars != null && g.daily_limit_dollars != null) ? '. Room left before the guard: ' + fmtMoney(g.daily_limit_dollars - g.daily_loss_dollars) : ''}</div>
    </div>
    <div class="guard-stat">
      <div class="small">TRADES TODAY</div>
      <div class="big ${g.entries_today >= status.config.max_trades_per_day ? 'red' : ''}">${g.entries_today} / ${status.config.max_trades_per_day}</div>
      <div class="small">Max trades per day, all symbols</div>
    </div>
    <div class="guard-stat">
      <div class="small">OPEN RISK NOW</div>
      <div class="big ${g.open_risk_pct >= status.config.max_concurrent_risk_pct ? 'red' : (g.open_risk_pct >= status.config.max_concurrent_risk_pct * 0.7 ? 'amber' : '')}">${Number(g.open_risk_pct).toFixed(2)}%</div>
      <div class="small">Cap ${status.config.max_concurrent_risk_pct}% across all open trades</div>
    </div>
    <div class="guard-stat">
      <div class="small">NEXT NEWS EVENT</div>
      <div class="big" style="font-size:16px;">${g.next_news_event ? g.next_news_event.name : '—'}</div>
      <div class="small">${g.next_news_event ? new Date(g.next_news_event.time).toLocaleString() : 'No upcoming events found'}</div>
    </div>
    <div class="guard-stat">
      <div class="small">BROKER SERVER TIME</div>
      <div class="big ${clk.offset_hours == null ? 'amber' : ''}" style="font-size:16px;">${clk.offset_hours == null ? 'not measured yet' : 'UTC' + (clk.offset_hours >= 0 ? '+' : '') + clk.offset_hours}</div>
      <div class="small">${clk.offset_hours == null ? ('using default session hour ' + clk.session_hour_server + ':00 server time') : ('US cash session opens ' + pad2(clk.session_hour_server) + ':30 server = ' + pad2(clk.session_hour_utc) + ':00 UTC = ' + pad2(clk.session_hour_ny) + ':00 New York ' + (clk.auto ? '(auto)' : '(fixed)'))}</div>
    </div>
  </div>`;

  if (dd.blocked || g.daily_loss_blocked) {
    const reasons = [];
    if (dd.blocked) reasons.push("equity at/below the drawdown safety line");
    if (g.daily_loss_blocked) reasons.push("daily loss limit reached");
    html += `<div class="guard-blocked-banner">New entries blocked: ${reasons.join(", ")}.</div>`;
  }

  document.getElementById("drawdownGuard").innerHTML = html;
}

function renderSymbolToggles(status) {
  // Read-only overview of every pair. Editing happens in the pair panel at the top,
  // which follows the pair selected in the dropdown.
  const container = document.getElementById("symbolToggles");
  const symbols = Object.keys(status.symbols);
  const rb = status.config.risk_pct_by_symbol || {};
  container.innerHTML = symbols.map(s => {
    const off = status.config.disabled_symbols.includes(s);
    const sel = s === currentSymbol;
    return `<div class="settings-row" style="cursor:pointer; ${sel ? 'background:rgba(56,189,248,0.06);' : ''}" onclick="selectSymbol('${s}')">
      <div><div>${s}${sel ? ' (selected)' : ''}</div></div>
      <div style="display:flex; align-items:center; gap:14px;">
        <span class="desc" style="margin:0;">risk ${Number(rb[s]).toFixed(2)}%</span>
        <span class="pill ${off ? 'no' : 'yes'}">${off ? 'OFF' : 'ON'}</span>
      </div>
    </div>`;
  }).join("");
}

function renderPairPanel() {
  if (!latestStatus) return;
  const s = currentSymbol, c = latestStatus.config;
  document.getElementById("pairPanelTitle").textContent = s + " SETTINGS";
  document.getElementById("pairNote").textContent = (c.symbol_notes || {})[s] || "";
  setToggle(document.getElementById("pairToggle"), !c.disabled_symbols.includes(s));
  const dir = ((latestStatus.symbols[s] || {}).direction_mode) || "";
  const dp = document.getElementById("pairDirPill");
  dp.textContent = dir || "BOTH";
  dp.className = "pill " + (dir === "SHORT" ? "no" : "yes");
  document.getElementById("pairDirDesc").textContent = "Both directions: long above the band, short below it. The band decides, nothing to set.";
  const rb = c.risk_pct_by_symbol || {}, df = c.default_risk_by_symbol || {};
  const risk = rb[s], def = df[s];
  const inp = document.getElementById("pairRisk");
  if (document.activeElement !== inp) inp.value = risk;
  const eq = (latestStatus.guards || {}).equity;
  document.getElementById("pairRiskDesc").textContent =
    "Default " + Number(def).toFixed(2) + "%" + (eq ? " | about " + fmtMoney(eq * risk / 100) + " at risk per trade on " + fmtMoney(eq) : "") +
    (Math.abs(risk - def) > 1e-9 ? " | changed from default" : " | at default");
  document.getElementById("pairResetBtn").style.display = Math.abs(risk - def) > 1e-9 ? "" : "none";
  document.getElementById("pairStats").textContent = (c.symbol_stats || {})[s] || "";
}

function postControl(payload, okMsg) {
  return fetch("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(async r => {
    try { return await r.json(); }
    catch (e) { return { ok: false, rejected: ["the bot answered with an error (HTTP " + r.status + ")"], changes: [] }; }
  }).then(res => {
    const rej = res.rejected || [], ch = res.changes || [];
    if (rej.length) showNotice("Not applied: " + rej.join("  |  ") + (ch.length ? "   Applied: " + ch.join("  |  ") : ""), "error");
    else if (ch.length) showNotice("Saved and applied: " + ch.join("  |  "), "ok");
    else showNotice(okMsg || "Nothing changed: those were already the current values.", "ok");
    return res;
  }).catch(e => {
    showNotice("Could not reach the bot, nothing was saved: " + e, "error");
    return { ok: false, rejected: ["unreachable"], changes: [] };
  });
}

function savePairRisk() {
  const v = parseFloat(document.getElementById("pairRisk").value);
  const s = currentSymbol;
  postControl({ risk_pct_by_symbol: { [s]: Number.isFinite(v) ? v : null } }).then(() => refresh());
}

function resetPairRisk() {
  const def = (latestStatus.config.default_risk_by_symbol || {})[currentSymbol];
  if (def === undefined) return;
  document.getElementById("pairRisk").value = def;
  savePairRisk();
}

function applySettings() {
  const num = (id, isInt) => {
    const raw = document.getElementById(id).value;
    const v = isInt ? parseInt(raw, 10) : parseFloat(raw);
    return Number.isFinite(v) ? v : null;
  };
  const on = id => document.getElementById(id).dataset.on === "1";
  const payload = {
    daily_loss_guard_pct: num("dailyLossPct", false),
    daily_loss_guard_enabled: on("dailyLossToggle"),
    initial_account_balance: num("initialBalance", false),
    max_account_drawdown_pct: num("maxDrawdownPct", false),
    max_account_drawdown_enabled: on("drawdownToggle"),
    per_session_trade_cap: num("sessionCap", true),
    per_session_cap_enabled: on("sessionCapToggle"),
    max_trades_per_day: num("maxTradesDay", true),
    max_trades_per_day_enabled: on("maxTradesDayToggle"),
    max_concurrent_risk_pct: num("maxOpenRisk", false),
    max_concurrent_risk_enabled: on("maxOpenRiskToggle"),
    news_protection_enabled: on("newsGuardToggle"),
    max_entry_slippage_r: num("slippageR", false),
    max_entry_slippage_enabled: on("slippageToggle"),
    max_spread_r: num("spreadR", false),
    max_spread_guard_enabled: on("spreadToggle"),
    use_risk_based_sizing: on("riskSizingToggle"),
  };
  postControl(payload).then(() => {
    window._settingsPopulated = false;    // show what the bot actually holds now (rejected values snap back)
    return refresh();
  });
}

async function refresh() {
  let status;
  try {
    const res = await fetch("/status");
    status = await res.json();
    if (!res.ok || status.error) throw new Error(status.error || ("HTTP " + res.status));
  } catch (e) {
    document.getElementById("liveLabel").textContent = "offline";
    uiErrors["connection"] = "cannot read the bot's status (" + (e.message || e) + ")";
    showUiErrors();
    return false;
  }
  delete uiErrors["connection"];
  document.getElementById("liveLabel").textContent = "live";
  try { render(status); }
  catch (e) { uiErrors["dashboard"] = e.message || String(e); console.error(e); }
  showUiErrors();
  return true;
}

async function poll() {
  await refresh();
  setTimeout(poll, 5000);
}

poll();
"""


import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DASHBOARD_PORT = 8777   # default; ORB bots use 8700-8704, so NOISE starts at 8777 (one port per account: 8777, 8778, ...)
# The dashboard can stop the bot and change every risk setting, and it has no login, so it listens on THIS
# computer only. Use --host 0.0.0.0 only on a network you fully trust (and ideally behind a VPN).
DASHBOARD_HOST = "127.0.0.1"


_stop_event = threading.Event()


def bot_loop():
    """Runs forever, retrying the MT5 connection indefinitely rather than
    giving up after one failed attempt — see the docstring on this
    function's own body below for the full reasoning (this was a real bug
    found and fixed: a single transient mt5.initialize() failure used to
    end the whole loop permanently)."""
    if not MT5_AVAILABLE:
        _log("MetaTrader5 package not available — install it with "
             "'pip install MetaTrader5' and restart this script. "
             "Dashboard will show an empty/idle state until then.")
        return

    connected = False
    while not _stop_event.is_set():
        if not connected:
            if _mt5_init():
                connected = True
                term_info = mt5.terminal_info()
                account_info = mt5.account_info()
                _log(f"MT5 connected. Terminal: {getattr(term_info, 'name', '?')} | "
                     f"Account: {getattr(account_info, 'login', '?')} | "
                     f"Trade allowed: {getattr(term_info, 'trade_allowed', '?')}")
                _log(f"NBRO bot started on {SYMBOLS}. Noise band over the last {NOISE_LOOKBACK_DAYS} sessions.")
                verify_symbols()
                refresh_session_clock(force=True)
                reconcile_positions()
                if term_info is not None and not getattr(term_info, "trade_allowed", True):
                    _log("WARNING: 'Algo Trading' / 'AutoTrading' looks OFF in the MT5 "
                         "terminal toolbar. Orders will be rejected until it's enabled "
                         "(the button/toggle must be green, not red).")
            else:
                _log(f"MT5 connection failed: {mt5.last_error()}. Retrying in 30s. "
                     f"Common causes: MT5 terminal not running, not logged into a real "
                     f"account, or 'Allow DLL imports' unchecked in "
                     f"Tools > Options > Expert Advisors.")
                _stop_event.wait(30)
                continue

        if mt5.terminal_info() is None:
            connected = False
            _log("MT5 connection appears to have dropped — will retry.")
            continue

        try:
            load_control()
            refresh_session_clock()
            refresh_daily_pnl()
            for symbol in SYMBOLS:
                try:
                    process_symbol(symbol)
                except Exception as e:      # one bad poll must never kill the bot thread
                    _log(f"[{symbol}] ERROR during poll: {type(e).__name__}: {e}")
            save_state()
        except Exception as e:
            _log(f"ERROR in main loop: {type(e).__name__}: {e}")
        _stop_event.wait(15)


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet — the Activity Log panel is the real log

    def handle(self):
        # The browser closed or reloaded the page (or a tab went to sleep) while this answer was being written. Nothing is wrong
        # and there is nobody left to answer, so ignore it — it used to print a long traceback each time.
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, content_type):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_text(_DASHBOARD_HTML, "text/html; charset=utf-8")
        elif self.path == "/dashboard.js":
            self._send_text(_DASHBOARD_JS, "application/javascript; charset=utf-8")
        elif self.path == "/status":
            try:
                self._send_json(get_status_dict())
            except Exception as e:
                _warn_once("status_error", f"Dashboard could not build its status: {type(e).__name__}: {e}", every=60)
                self._send_json({"error": f"{type(e).__name__}: {e}"}, code=500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/control":
            # Only a real fetch() from the dashboard sends application/json. A plain HTML form on some other
            # web page can only send form/text types, which would otherwise let a website you happen to
            # visit change your bot's settings (cross-site request forgery).
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self._send_json({"ok": False, "error": "Content-Type must be application/json"}, code=415)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                control = json.loads(raw)
            except Exception:
                self._send_json({"ok": False, "error": "invalid JSON"}, code=400)
                return
            clean, rejected = _validate_control(control if isinstance(control, dict) else {})
            if "initial_account_balance" in clean:
                if abs(clean["initial_account_balance"] - INITIAL_ACCOUNT_BALANCE) <= 0.005 * INITIAL_ACCOUNT_BALANCE:
                    del clean["initial_account_balance"]       # Apply re-sends every field: an unchanged one is not an override
                else:
                    clean["base_mode"] = "manual"
            before = _settings_snapshot()
            if clean:
                _save_control(clean)
                load_control()
            changes = _log_setting_changes(before, _settings_snapshot(), "dashboard")
            for r in rejected:
                _log(f"Setting NOT applied (dashboard): {r}")
            self._send_json({"ok": not rejected, "changes": changes, "rejected": rejected})
        elif self.path == "/close":
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self._send_json({"ok": False, "error": "Content-Type must be application/json"}, code=415)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw)
            except Exception:
                self._send_json({"ok": False, "error": "invalid JSON"}, code=400)
                return
            symbol = body.get("symbol") if isinstance(body, dict) else None
            state = _states.get(symbol) if symbol else None
            if state is None:
                self._send_json({"ok": False, "error": f"unknown symbol '{symbol}'"}, code=400)
            elif state.trade is None:
                self._send_json({"ok": False, "error": f"{symbol} has no open trade right now"}, code=409)
            else:
                state.close_requested = True
                _log(f"[{symbol}] Close requested from the dashboard — will close at market on the next poll (within ~15s).")
                self._send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()


def _shutdown_bot(server, bot_thread):
    """Ctrl+C / normal stop: let a poll in progress finish, write the state file, close the MT5
    connection. Open trades are NOT touched: each one already has its stop-loss at the broker, and the
    next start takes it over again."""
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
    open_now = [f"{sym} {st.trade.direction} #{st.trade.ticket}" for sym, st in _states.items() if st.trade is not None]
    print("Stopped. " + (f"{len(open_now)} open trade(s) stay open in MT5 with their stop-loss ({', '.join(open_now)}); "
                         f"the next start takes them over again." if open_now else "No open trades."))


def run_dashboard():
    # Claim the dashboard port FIRST. Before, the trading thread was started before the port was taken, so a
    # second copy launched on a port already in use would connect to MT5 and begin polling (even trading)
    # for a few seconds, fail to bind, exit, and be restarted by the supervisor — over and over.
    try:
        server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler)
    except OSError as e:
        print(f"\nCANNOT START: port {DASHBOARD_PORT} is already in use ({e}).\n"
              f"Another copy of the bot is probably running on it. Give this one its own port, e.g. "
              f"--port {DASHBOARD_PORT + 1}  (one port per bot / per account).\n"
              f"Nothing was started and no trade was touched.")
        sys.exit(0)        # 0 so the supervisor stops instead of restarting this in a loop
    _startup_restore()
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    print(f"NBRO dashboard running at http://localhost:{DASHBOARD_PORT}"
          + ("" if DASHBOARD_HOST in ("127.0.0.1", "localhost") else f"  (listening on {DASHBOARD_HOST}: NO password, anyone who can reach it can change settings)"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping (Ctrl+C)...")
    finally:
        _shutdown_bot(server, bot_thread)


import sys
import signal
import subprocess


def _supervise(argv, restart_delay=10.0, _cmd=None):
    """Built-in auto-restart: runs the bot as a child process and starts it again whenever
    it dies (crash, MT5 DLL fault, accidental close). Each fresh start reconnects to MT5
    (launching the terminal from --mt5-path if needed), rebuilds state from MT5 and takes
    over any open trade. A clean exit (code 0) or Ctrl+C ends supervision."""
    cmd = _cmd or ([sys.executable, os.path.abspath(__file__)] + list(argv) + ["--child"])
    while True:
        proc = subprocess.Popen(cmd)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            # In a console, Ctrl+C reaches the child as well, so give it time to shut down by itself
            # (write its state, close MT5). terminate() on Windows is a hard kill, so it is only a last resort.
            if os.name != "nt":
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass
            try:
                proc.wait(timeout=30)
            except Exception:
                print("The bot did not stop in time and is being ended.")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
            return
        if code == 0:
            return
        print(f"Bot exited with code {code} — restarting in {restart_delay:.0f}s "
              f"(it reconnects to MT5 and resumes any open trade).")
        try:
            time.sleep(restart_delay)
        except KeyboardInterrupt:
            print("Stopped.")
            return


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="NBRO bot (Noise Area intraday momentum, NAS100 + SPX500) + dashboard (one instance per MT5 account)")
    ap.add_argument("--console", action="store_true", help="console only, no web dashboard")
    ap.add_argument("--port", type=int, default=DASHBOARD_PORT, help="dashboard port (unique per instance)")
    ap.add_argument("--mt5-path", default=None, help="full path to this account's terminal64.exe")
    ap.add_argument("--label", default="", help="account label shown in Telegram alerts, e.g. Atlas-1")
    ap.add_argument("--balance", type=float, default=None, help="initial account balance for the drawdown floor")
    ap.add_argument("--max-dd", type=float, default=None, help="max drawdown %% for this account's plan")
    ap.add_argument("--profit-target", type=float, default=None,
                    help="stop opening NEW trades once closed profit reaches this %% of the starting balance "
                        "(e.g. 3 for a 3%% challenge target). Off by default.")
    ap.add_argument("--dd-mode", choices=["static", "trailing"], default=None,
                    help="static (default): floor fixed at the starting balance. trailing: floor rises with the "
                        "account's own EOD high-water mark — use this if your prop firm dashboard itself labels "
                        "your max drawdown \"Trailing\" (check it — most 1-Step/2-Step challenges are \"Static\").")
    ap.add_argument("--daily-loss", type=float, default=None, help="daily loss limit %% for this account's plan")
    ap.add_argument("--host", default=None, help="dashboard bind address (default 127.0.0.1 = this computer only)")
    ap.add_argument("--suffix", default="", help="broker symbol suffix, e.g. .r, .pro or m (EURUSD -> EURUSD.r)")
    ap.add_argument("--plan", choices=sorted(PLAN_PRESETS), default=None,
                    help="prop plan preset (max drawdown-daily limit): instant=5-3, 4-8, 5-10; scales risk, caps and guards")
    ap.add_argument("--preset", choices=sorted(ATLAS_PRESETS), default=None,
                    help="Atlas 1-Step Access: atlas-eval (1.0%% per index, 10%% trailing, +3%% target) or "
                         "atlas-funded (0.35%% per index, 6%% trailing, Protector shield 1.7%%); other flags override it")
    ap.add_argument("--protector-shield", type=float, default=None,
                    help="close this bot's positions at this %% account open loss (Atlas Protector = 2%%); 0 = off")
    ap.add_argument("--risk", type=float, default=None, help="risk %% per trade, applied to every pair")
    ap.add_argument("--max-trades-day", type=int, default=None, help="max trades per day, all symbols")
    ap.add_argument("--max-open-risk", type=float, default=None, help="max total open risk %% across all symbols")
    ap.add_argument("--fixed-session-hour", type=int, default=None,
                    help="turn OFF server-time auto-detection and force this server-clock hour as the session open")
    ap.add_argument("--no-supervise", action="store_true", help="run once, without the auto-restart wrapper")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not args.child and not args.no_supervise:
        _supervise(sys.argv[1:])
        sys.exit(0)

    DASHBOARD_PORT = args.port
    MT5_TERMINAL_PATH = args.mt5_path
    ACCOUNT_LABEL = args.label
    SYMBOL_SUFFIX = args.suffix
    if args.host:
        DASHBOARD_HOST = args.host
    # each instance gets its own control file so dashboards don't overwrite each other
    CONTROL_FILE = os.path.join(_script_dir(), f"nbro_control_{args.port}.json")
    STATUS_FILE = os.path.join(_script_dir(), f"nbro_status_{args.port}.json")
    _cli_keys = []
    if args.preset:
        _p = ATLAS_PRESETS[args.preset]
        RISK_PCT = _p["risk"]
        for _k in RISK_PCT_BY_SYMBOL:
            RISK_PCT_BY_SYMBOL[_k] = _p["risk"]
        MAX_ACCOUNT_DRAWDOWN_PCT, DAILY_LOSS_GUARD_PCT = _p["max_dd"], _p["daily_guard"]
        MAX_ACCOUNT_DRAWDOWN_MODE, PROFIT_TARGET_PCT = _p["dd_mode"], _p["profit_target"]
        PROTECTOR_SHIELD_PCT, MAX_CONCURRENT_RISK_PCT = _p["shield"], _p["max_open_risk"]
        _cli_keys += ["risk_pct_by_symbol", "risk_pct", "daily_loss_guard_pct",
                      "max_account_drawdown_pct", "max_concurrent_risk_pct"]
    if args.protector_shield is not None:
        PROTECTOR_SHIELD_PCT = max(0.0, args.protector_shield)
    if args.plan:
        apply_plan_preset(args.plan)
        _cli_keys += ["risk_pct_by_symbol", "risk_pct", "daily_loss_guard_pct",
                      "max_account_drawdown_pct", "max_concurrent_risk_pct"]
    if args.risk is not None:
        _cli_keys += ["risk_pct_by_symbol", "risk_pct"]
    if args.balance is not None:
        _cli_keys += ["initial_account_balance"]
    if args.max_dd is not None:
        _cli_keys += ["max_account_drawdown_pct"]
    if args.daily_loss is not None:
        _cli_keys += ["daily_loss_guard_pct"]
    if args.max_trades_day is not None:
        _cli_keys += ["max_trades_per_day"]
    if args.max_open_risk is not None:
        _cli_keys += ["max_concurrent_risk_pct"]
    if _cli_keys:
        _clear_control_keys(_cli_keys)
    if args.balance is not None:
        INITIAL_ACCOUNT_BALANCE = args.balance
        _BALANCE_SET_BY_CLI = True
    if args.risk is not None:
        RISK_PCT = args.risk
        for _k in RISK_PCT_BY_SYMBOL:
            RISK_PCT_BY_SYMBOL[_k] = args.risk
    if args.max_trades_day is not None:
        MAX_TRADES_PER_DAY = max(1, min(args.max_trades_day, MAX_TRADES_PER_DAY_CEILING))
    if args.max_open_risk is not None:
        MAX_CONCURRENT_RISK_PCT = args.max_open_risk
    if args.fixed_session_hour is not None:
        SERVER_TIME_AUTO = False
        ORB_SESSION_HOUR = args.fixed_session_hour
    if args.max_dd is not None:
        MAX_ACCOUNT_DRAWDOWN_PCT = args.max_dd
    if args.dd_mode is not None:
        MAX_ACCOUNT_DRAWDOWN_MODE = args.dd_mode
    if args.profit_target is not None:
        PROFIT_TARGET_PCT = args.profit_target
    if args.daily_loss is not None:
        DAILY_LOSS_GUARD_PCT = args.daily_loss

    if args.console:
        run()
    else:
        run_dashboard()
