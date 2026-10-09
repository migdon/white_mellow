"""
Checks, one by one, that Python can connect to every MT5 in config.py. Nothing is traded.

    python check_mt5.py

Put it in the AtlasBot folder (next to config.py) and send the output if something fails.
"""
import os
import platform
import struct
import sys
import time

print(f"Python {platform.python_version()} ({struct.calcsize('P') * 8}-bit) at {sys.executable}")
if struct.calcsize("P") * 8 != 64:
    print("PROBLEM: this Python is 32-bit. MetaTrader5 needs 64-bit Python: install the 64-bit version from python.org.")
try:
    import MetaTrader5 as mt5
    print(f"MetaTrader5 package {getattr(mt5, '__version__', '?')}: OK")
except ImportError:
    raise SystemExit("PROBLEM: MetaTrader5 is not installed for THIS Python. Run:  \"%s\" -m pip install MetaTrader5 pandas numpy"
                     % sys.executable)
try:
    import numpy, pandas  # noqa: F401,E401
    print("numpy / pandas: OK")
except ImportError as e:
    print(f"PROBLEM: {e}. Run:  \"{sys.executable}\" -m pip install pandas numpy")

try:
    from config import ACCOUNTS
except Exception as e:
    raise SystemExit(f"PROBLEM reading config.py: {type(e).__name__}: {e}")

ok = 0
for acc in ACCOUNTS:
    label, path = acc.get("label"), acc.get("mt5_path")
    print(f"\n=== {label}: {path or '(default MT5)'}")
    if path and not os.path.exists(path):
        print("  PROBLEM: file not found. Open that folder in Explorer and copy the exact path of terminal64.exe.")
        continue
    t0 = time.time()
    good = mt5.initialize(path=path, timeout=60000) if path else mt5.initialize(timeout=60000)
    if not good:
        print(f"  PROBLEM: cannot connect ({mt5.last_error()}) after {time.time() - t0:.0f}s.")
        print("  - Is this MT5 open and logged in (account number shown at the bottom right)?")
        print("  - Open MT5 and run this the same way: both normal, or both 'Run as administrator'.")
        print("  - Tools > Options > Expert Advisors: allow algorithmic trading.")
        continue
    a, t = mt5.account_info(), mt5.terminal_info()
    if a is None:
        print(f"  PROBLEM: connected but NOT logged in to an account ({mt5.last_error()}). Log in inside MT5 (save password).")
    else:
        print(f"  connected: account {a.login} @ {a.server}, balance {a.balance:,.2f} {a.currency}")
        print(f"  Algo Trading button: {'ON' if t.trade_allowed else 'OFF  <- PROBLEM: press the Algo Trading button in MT5'}")
        names = []
        for s in ("NAS100", "SPX500", "XAUUSD"):
            names.append(f"{s} {'OK' if mt5.symbol_select(s, True) else 'NOT FOUND'}")
        print("  symbols: " + ", ".join(names))
        ok += 1
    mt5.shutdown()
print(f"\n{ok} of {len(ACCOUNTS)} account(s) ready.")
