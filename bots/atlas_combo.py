"""
ONE command, ONE Atlas Access account, BOTH strategies:
  NBRO  (NAS100 + SPX500, US session, intraday)      nbro_app.py
  EMBER (gold, optionally BTCUSD, held overnight)    ember_app.py

    python atlas_combo.py --stage evaluation            # while passing the +3% evaluation
    python atlas_combo.py --stage funded                # after passing
    options:  --btc  (add BTCUSD to EMBER at half risk)   --label Atlas50k   --mt5-path "C:\\...\\terminal64.exe"
              --dry-run  (print the two commands and exit)

Settings, from the replay of both bots together on 2018-2026 data (reports/combo_atlas.md):
  evaluation: NBRO 1% per index + EMBER gold 1% (BTC 0.5%)  -> ~46% pass within a month, ~75% within two, ~3-4% breached
  funded:     NBRO 0.25% per index + EMBER gold 0.5% (BTC 0.25%), Protector shield 1.7% in both bots
              -> alive after a year in every start date, ~2 payouts a year (~$2,000 on $50k)

Both bots read the WHOLE account's equity for the daily-loss guard, the drawdown guard and the Protector shield, so either one
stops new entries (and, funded, closes its own positions at the shield line) whatever the other is doing. They use different magic
numbers and never touch each other's orders. Each keeps its own dashboard (NBRO http://127.0.0.1:8777, EMBER http://127.0.0.1:8710)
and its own auto-restart. Ctrl+C here stops both.
Put this file in the same folder as nbro_app.py and ember_app.py.
"""

import argparse
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = {
    "evaluation": {"nbro": ["--preset", "atlas-eval"], "ember": ["--preset", "combo-evaluation"]},
    "funded": {"nbro": ["--preset", "atlas-funded", "--risk", "0.25"], "ember": ["--preset", "combo-funded"]},
}


def build(args):
    common = []
    if args.mt5_path:
        common += ["--mt5-path", args.mt5_path]
    if args.suffix:
        common += ["--suffix", args.suffix]
    nbro = [sys.executable, os.path.join(HERE, "nbro_app.py"), *STAGES[args.stage]["nbro"],
            "--port", str(args.nbro_port), "--label", f"{args.label}-NBRO" if args.label else "NBRO", *common]
    symbols = ["XAUUSD", "BTCUSD"] if args.btc else ["XAUUSD"]
    ember = [sys.executable, os.path.join(HERE, "ember_app.py"), "--symbols", *symbols, *STAGES[args.stage]["ember"],
             "--port", str(args.ember_port), "--label", f"{args.label}-EMBER" if args.label else "EMBER", *common]
    return nbro, ember


def main():
    ap = argparse.ArgumentParser(description="Run NBRO + EMBER together on one Atlas Access account")
    ap.add_argument("--stage", choices=sorted(STAGES), default=None,
                    help="evaluation or funded; asked for when missing (e.g. started with VS Code's Run button)")
    ap.add_argument("--btc", action="store_true", help="add BTCUSD to EMBER (half of gold's risk)")
    ap.add_argument("--label", default="")
    ap.add_argument("--mt5-path", default=None)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--nbro-port", type=int, default=8777)
    ap.add_argument("--ember-port", type=int, default=8710)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.stage is None:
        # deliberately NOT defaulting: evaluation risk on a funded account could breach it
        print("Which stage is this Atlas account in?\n  1 = evaluation (passing the +3% target)\n  2 = funded")
        while a.stage is None:
            ans = input("Type 1 or 2 and press Enter: ").strip().lower()
            a.stage = {"1": "evaluation", "2": "funded", "evaluation": "evaluation", "funded": "funded"}.get(ans)
        if not a.label:
            a.label = input("Account label for alerts (Enter to skip): ").strip()

    cmds = build(a)
    for name, c in zip(("NBRO", "EMBER"), cmds):
        print(f"{name}: " + " ".join(f'"{x}"' if " " in x else x for x in c))
    if a.dry_run:
        return
    for f in ("nbro_app.py", "ember_app.py"):
        if not os.path.exists(os.path.join(HERE, f)):
            raise SystemExit(f"{f} not found next to atlas_combo.py")

    # Windows: each bot (and the auto-restart child it starts) gets its own process group, so CTRL_BREAK below reaches all of them
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    procs = [subprocess.Popen(c, cwd=HERE, creationflags=flags) for c in cmds]
    print(f"\nRunning ({a.stage}). Dashboards: NBRO http://127.0.0.1:{a.nbro_port}   EMBER http://127.0.0.1:{a.ember_port}")
    print("Ctrl+C stops both.\n")
    try:
        while True:
            for name, p in zip(("NBRO", "EMBER"), procs):
                if p.poll() is not None:
                    print(f"{name} exited with code {p.returncode}. Stopping the other one too, so the account is never "
                          f"run by one strategy while you think both are on.")
                    raise KeyboardInterrupt
            time.sleep(5)
    except KeyboardInterrupt:
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
                except Exception:
                    p.terminate()
        for p in procs:
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
        print("Both stopped.")


if __name__ == "__main__":
    main()
