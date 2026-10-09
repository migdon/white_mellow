"""
Builds bots/atlas_bot.py: ONE file that carries nbro_app.py and ember_app.py (byte-for-byte, compressed inside it)
plus the launcher for one or several Atlas accounts.

    python bots/build_all_in_one.py        # run again after changing nbro_app.py or ember_app.py
"""

import base64
import hashlib
import os
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = r'''"""
ATLAS BOT — NBRO + EMBER in ONE file.

    python atlas_bot.py            (or the Run button in VS Code)
    python atlas_bot.py --dry-run  (only show what would start)

WHAT IT RUNS, on each Atlas Access account listed below:
  NBRO  — NAS100 + SPX500, US session (night in the Philippines), intraday, closes before the session ends
  EMBER — gold (and BTCUSD if btc=True), daily breakout held overnight
Settings, tested together on 2018-2026 data (reports/combo_atlas.md):
  stage "evaluation": NBRO 1% per index + gold 1% (BTC 0.5%)   -> ~46% pass within 1 month, ~75% within 2, ~3-4% breached
  stage "funded":     NBRO 0.25% per index + gold 0.5% (BTC 0.25%), Protector shield 1.7% -> ~2 payouts/yr (~$2,000 on $50k)

SETUP
  1. Open Atlas MT5 and log in (one MT5 terminal PER account if you run more than one account).
  2. Edit ACCOUNTS below. One account on this PC's normal MT5: leave mt5_path = None.
     Several accounts: give each its own terminal64.exe path.
  3. Change "evaluation" to "funded" for an account once it passes.
  4. Run this file. Dashboards: account #1 NBRO http://127.0.0.1:8777  EMBER http://127.0.0.1:8710 (#2: 8778 / 8711, ...)
     Ctrl+C stops everything.

The two bots' own code is stored inside this file unchanged (sha256 below) and is written to the folder
"atlas_bot_files" next to this file when it runs; their state, trade history and logs live there too. Don't edit those copies.
All accounts take the SAME trades: they win and lose together. Check Atlas's rules on several accounts before scaling up.
"""

import argparse
import base64
import hashlib
import os
import signal
import subprocess
import sys
import time
import zlib

# ============================================================================================ EDIT THIS
ACCOUNTS = [
    {"label": "Atlas1", "mt5_path": None, "stage": "evaluation", "btc": False},
    # {"label": "Atlas2", "mt5_path": r"C:\MT5_Atlas2\terminal64.exe", "stage": "evaluation", "btc": False},
    # {"label": "Atlas3", "mt5_path": r"C:\MT5_Atlas3\terminal64.exe", "stage": "evaluation", "btc": False},
]
SUFFIX = ""             # broker symbol suffix, normally empty at Atlas
NBRO_FIRST_PORT = 8777
EMBER_FIRST_PORT = 8710
# ======================================================================================================

STAGES = {
    "evaluation": {"nbro": ["--preset", "atlas-eval"], "ember": ["--preset", "combo-evaluation"]},
    "funded": {"nbro": ["--preset", "atlas-funded", "--risk", "0.25"], "ember": ["--preset", "combo-funded"]},
}
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "atlas_bot_files")

# ---- the two bots, unchanged (zlib + base64) -------------------------------------------------------------
BOTS = {
    "nbro_app.py": ("@@NBRO_SHA@@", "@@NBRO_B64@@"),
    "ember_app.py": ("@@EMBER_SHA@@", "@@EMBER_B64@@"),
}


def unpack_bots():
    """Write the embedded bots to atlas_bot_files/ (only when missing or different), verifying their checksums."""
    os.makedirs(RUN_DIR, exist_ok=True)
    for name, (sha, b64) in BOTS.items():
        src = zlib.decompress(base64.b64decode(b64))
        if hashlib.sha256(src).hexdigest() != sha:
            raise SystemExit(f"{name}: embedded copy is corrupted (checksum mismatch). Download atlas_bot.py again.")
        path = os.path.join(RUN_DIR, name)
        if not os.path.exists(path) or open(path, "rb").read() != src:
            with open(path, "wb") as f:
                f.write(src)


def commands(i, acc):
    stage = acc.get("stage", "")
    if stage not in STAGES:
        raise SystemExit(f"Account {acc.get('label', i + 1)}: stage must be 'evaluation' or 'funded', not {stage!r}")
    common = (["--mt5-path", acc["mt5_path"]] if acc.get("mt5_path") else []) + (["--suffix", SUFFIX] if SUFFIX else [])
    label = acc.get("label") or f"Atlas{i + 1}"
    nbro = [sys.executable, os.path.join(RUN_DIR, "nbro_app.py"), *STAGES[stage]["nbro"],
            "--port", str(NBRO_FIRST_PORT + i), "--label", f"{label}-NBRO", *common]
    ember = [sys.executable, os.path.join(RUN_DIR, "ember_app.py"), "--symbols", "XAUUSD", *(["BTCUSD"] if acc.get("btc") else []),
             *STAGES[stage]["ember"], "--port", str(EMBER_FIRST_PORT + i), "--label", f"{label}-EMBER", *common]
    return label, stage, nbro, ember


def check_setup():
    problems = []
    if len(ACCOUNTS) > 1:
        paths = [a.get("mt5_path") for a in ACCOUNTS]
        if any(p is None for p in paths):
            problems.append("with more than one account, every account needs its own mt5_path (one MT5 terminal per account)")
        for p in set(x for x in paths if x):
            if paths.count(p) > 1:
                problems.append(f"the same MT5 terminal is used by more than one account: {p}")
    for a in ACCOUNTS:
        if a.get("mt5_path") and os.name == "nt" and not os.path.exists(a["mt5_path"]):
            problems.append(f"MT5 terminal not found: {a['mt5_path']}")
    return problems


def stop(p):
    if p.poll() is None:
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        except Exception:
            p.terminate()


def main():
    ap = argparse.ArgumentParser(description="NBRO + EMBER on one or several Atlas accounts, from one file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not ACCOUNTS:
        raise SystemExit("ACCOUNTS is empty: add your account(s) at the top of atlas_bot.py")
    plan = [commands(i, acc) for i, acc in enumerate(ACCOUNTS)]
    print(f"{'#':<3}{'account':<12}{'stage':<12}{'NBRO dashboard':<26}{'EMBER dashboard':<26}MT5")
    for i, (label, stage, _, _) in enumerate(plan):
        print(f"{i + 1:<3}{label:<12}{stage:<12}{'http://127.0.0.1:' + str(NBRO_FIRST_PORT + i):<26}"
              f"{'http://127.0.0.1:' + str(EMBER_FIRST_PORT + i):<26}{ACCOUNTS[i].get('mt5_path') or '(this PC default MT5)'}")
    problems = check_setup()
    if problems:
        raise SystemExit("Fix these first:\n  - " + "\n  - ".join(problems))
    unpack_bots()
    if a.dry_run:
        for label, _, nbro, ember in plan:
            print(f"\n[{label}] " + " ".join(nbro) + f"\n[{label}] " + " ".join(ember))
        return
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    running = {}
    for label, _, nbro, ember in plan:
        running[label] = (subprocess.Popen(nbro, cwd=RUN_DIR, creationflags=flags),
                          subprocess.Popen(ember, cwd=RUN_DIR, creationflags=flags))
        time.sleep(3)
    print(f"\nRunning {len(running)} account(s). Ctrl+C stops everything.\n")
    try:
        while running:
            for label, (pn, pe) in list(running.items()):
                dead = [n for n, p in (("NBRO", pn), ("EMBER", pe)) if p.poll() is not None]
                if dead:
                    print(f"[{label}] {' and '.join(dead)} stopped: stopping the other bot of {label} too.")
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
'''


def pack(name):
    raw = open(os.path.join(HERE, name), "rb").read()
    return hashlib.sha256(raw).hexdigest(), base64.b64encode(zlib.compress(raw, 9)).decode()


if __name__ == "__main__":
    nsha, nb64 = pack("nbro_app.py")
    esha, eb64 = pack("ember_app.py")
    out = (TEMPLATE.replace("@@NBRO_SHA@@", nsha).replace("@@NBRO_B64@@", nb64)
           .replace("@@EMBER_SHA@@", esha).replace("@@EMBER_B64@@", eb64))
    dst = os.path.join(HERE, "atlas_bot.py")
    with open(dst, "w") as f:
        f.write(out)
    print(f"wrote {dst} ({len(out) / 1024:.0f} KB)  nbro {nsha[:12]}  ember {esha[:12]}")
