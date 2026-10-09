"""
Export D1 history + swap/spread specs from your MT5 terminal.

Run on the Windows machine where MT5 is installed and logged in:

    pip install MetaTrader5 pandas
    python -m carry_tsmom.export_mt5 --out mt5_export [--suffix .r]

Writes:
    mt5_export/<SYMBOL>_D1.csv     time,open,high,low,close,tick_volume,spread
    mt5_export/symbol_specs.json   swap_long/short, swap_mode, point, digits,
                                   contract size, current spread, triple-swap day
Then (anywhere):
    python run_research.py --mt5 mt5_export [--suffix .r]
"""

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd

from carry_tsmom.data import PAIRS

SPEC_FIELDS = ["swap_long", "swap_short", "swap_mode", "swap_rollover3days",
               "point", "digits", "trade_contract_size", "spread", "spread_float",
               "currency_base", "currency_profit", "volume_min", "volume_step",
               "trade_tick_value", "trade_tick_size"]


def main():
    import MetaTrader5 as mt5

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="mt5_export")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--bars", type=int, default=10000, help="max D1 bars per symbol")
    ap.add_argument("--terminal", default=None, help="path to terminal64.exe")
    a = ap.parse_args()

    ok = mt5.initialize(path=a.terminal) if a.terminal else mt5.initialize()
    if not ok:
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    os.makedirs(a.out, exist_ok=True)
    specs = {"exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    acc = mt5.account_info()
    if acc:
        specs["account"] = {"server": acc.server, "currency": acc.currency, "leverage": acc.leverage}
    try:
        for sym, _ in PAIRS.values():
            name = sym + a.suffix
            if not mt5.symbol_select(name, True):
                print(f"!! {name}: not available at this broker - skipped")
                continue
            rates = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_D1, 0, a.bars)
            if rates is None or len(rates) == 0:
                print(f"!! {name}: no D1 history ({mt5.last_error()})")
                continue
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
            df.to_csv(os.path.join(a.out, f"{name}_D1.csv"), index=False)
            info = mt5.symbol_info(name)
            specs[name] = {f: getattr(info, f, None) for f in SPEC_FIELDS}
            print(f"{name}: {len(df)} bars {df.time.iloc[0].date()} -> {df.time.iloc[-1].date()}  "
                  f"swap L/S {info.swap_long}/{info.swap_short} (mode {info.swap_mode})")
    finally:
        mt5.shutdown()
    with open(os.path.join(a.out, "symbol_specs.json"), "w") as f:
        json.dump(specs, f, indent=1, default=str)
    print(f"Saved to {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
