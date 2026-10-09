"""
ONE file, ONE command, ONE window: NBRO + EMBER on SEVERAL Atlas Access accounts.

    python atlas_multi.py              (or the Run button in VS Code)
    python atlas_multi.py --dry-run    (only print what would start)

1. Install one MT5 terminal PER account in its own folder (e.g. C:\\MT5_Atlas1 ... C:\\MT5_Atlas5), log each one in
   to its own Atlas account, and set Tools > Options > Charts > Max bars in chart = Unlimited.
2. Fill in ACCOUNTS below: one line per account. stage = "evaluation" or "funded" (change it when that account passes).
3. Keep this file next to nbro_app.py and ember_app.py, then run it.

Per account it starts nbro_app.py and ember_app.py with the settings tested together in reports/combo_atlas.md:
  evaluation: NBRO 1% per index + EMBER gold 1% (BTC 0.5% if btc=True)
  funded:     NBRO 0.25% per index + EMBER gold 0.5% (BTC 0.25%), Protector shield 1.7% in both bots
Ports are given automatically: account #1 -> NBRO 8777 / EMBER 8710, account #2 -> 8778 / 8711, and so on.
Each bot keeps its own state files by port, so the accounts never mix.

If ONE bot of an account stops for good, the other bot of THAT account is stopped too (the account is never half-run);
the other accounts keep running. Ctrl+C stops everything.

All accounts take the SAME trades: they win and lose together. Check Atlas's rules on the number of accounts and on
the same strategy across accounts before you scale up, and start with 1-2 accounts.
"""

import argparse
import os
import signal
import subprocess
import sys
import time

# ----------------------------------------------------------------------------------------------- EDIT THIS
ACCOUNTS = [
    {"label": "Atlas1", "mt5_path": r"C:\MT5_Atlas1\terminal64.exe", "stage": "evaluation", "btc": False},
    {"label": "Atlas2", "mt5_path": r"C:\MT5_Atlas2\terminal64.exe", "stage": "evaluation", "btc": False},
    {"label": "Atlas3", "mt5_path": r"C:\MT5_Atlas3\terminal64.exe", "stage": "evaluation", "btc": False},
    {"label": "Atlas4", "mt5_path": r"C:\MT5_Atlas4\terminal64.exe", "stage": "evaluation", "btc": False},
    {"label": "Atlas5", "mt5_path": r"C:\MT5_Atlas5\terminal64.exe", "stage": "evaluation", "btc": False},
]
SUFFIX = ""             # broker symbol suffix if Atlas uses one (normally empty)
NBRO_FIRST_PORT = 8777
EMBER_FIRST_PORT = 8710
# --------------------------------------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = {
    "evaluation": {"nbro": ["--preset", "atlas-eval"], "ember": ["--preset", "combo-evaluation"]},
    "funded": {"nbro": ["--preset", "atlas-funded", "--risk", "0.25"], "ember": ["--preset", "combo-funded"]},
}


def commands(i, acc):
    stage = acc.get("stage", "")
    if stage not in STAGES:
        raise SystemExit(f"Account {acc.get('label', i + 1)}: stage must be 'evaluation' or 'funded', not {stage!r}")
    common = ["--mt5-path", acc["mt5_path"]] + (["--suffix", SUFFIX] if SUFFIX else [])
    label = acc.get("label") or f"Atlas{i + 1}"
    nbro = [sys.executable, os.path.join(HERE, "nbro_app.py"), *STAGES[stage]["nbro"],
            "--port", str(NBRO_FIRST_PORT + i), "--label", f"{label}-NBRO", *common]
    ember = [sys.executable, os.path.join(HERE, "ember_app.py"), "--symbols", "XAUUSD", *(["BTCUSD"] if acc.get("btc") else []),
             *STAGES[stage]["ember"], "--port", str(EMBER_FIRST_PORT + i), "--label", f"{label}-EMBER", *common]
    return label, stage, nbro, ember


def check_setup(plan):
    problems = []
    for f in ("nbro_app.py", "ember_app.py"):
        if not os.path.exists(os.path.join(HERE, f)):
            problems.append(f"{f} is not next to atlas_multi.py")
    paths = [acc["mt5_path"] for acc in ACCOUNTS]
    for p in set(paths):
        if paths.count(p) > 1:
            problems.append(f"the same MT5 terminal is used by more than one account: {p} (one terminal per account)")
        if os.name == "nt" and not os.path.exists(p):
            problems.append(f"MT5 terminal not found: {p}")
    return problems


def stop(p):
    if p.poll() is None:
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        except Exception:
            p.terminate()


def main():
    ap = argparse.ArgumentParser(description="Run NBRO + EMBER on several Atlas accounts from one file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not ACCOUNTS:
        raise SystemExit("ACCOUNTS is empty: add your accounts at the top of atlas_multi.py")

    plan = [commands(i, acc) for i, acc in enumerate(ACCOUNTS)]
    print(f"{'#':<3}{'account':<12}{'stage':<12}{'NBRO dashboard':<26}{'EMBER dashboard':<26}MT5")
    for i, (label, stage, nbro, ember) in enumerate(plan):
        print(f"{i + 1:<3}{label:<12}{stage:<12}{'http://127.0.0.1:' + str(NBRO_FIRST_PORT + i):<26}"
              f"{'http://127.0.0.1:' + str(EMBER_FIRST_PORT + i):<26}{ACCOUNTS[i]['mt5_path']}")
    if a.dry_run:
        for label, _, nbro, ember in plan:
            print(f"\n[{label}] " + " ".join(nbro) + f"\n[{label}] " + " ".join(ember))
        return
    problems = check_setup(plan)
    if problems:
        raise SystemExit("Fix these first:\n  - " + "\n  - ".join(problems))

    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    running = {}                                   # label -> (nbro_proc, ember_proc)
    for label, _, nbro, ember in plan:
        running[label] = (subprocess.Popen(nbro, cwd=HERE, creationflags=flags),
                          subprocess.Popen(ember, cwd=HERE, creationflags=flags))
        time.sleep(3)                              # stagger the MT5 connections
    print(f"\nRunning {len(running)} account(s). Ctrl+C stops everything.\n")
    try:
        while running:
            for label, (pn, pe) in list(running.items()):
                dead = [n for n, p in (("NBRO", pn), ("EMBER", pe)) if p.poll() is not None]
                if dead:
                    print(f"[{label}] {' and '.join(dead)} stopped: stopping the other bot of {label} too. "
                          f"The other accounts keep running.")
                    stop(pn); stop(pe)
                    del running[label]
            time.sleep(5)
        print("All accounts stopped.")
    except KeyboardInterrupt:
        print("\nStopping all accounts...")
        for pn, pe in running.values():
            stop(pn); stop(pe)
        for pn, pe in running.values():
            for p in (pn, pe):
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("All stopped.")


if __name__ == "__main__":
    main()
