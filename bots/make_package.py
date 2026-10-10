"""
Builds a clean, organized folder AtlasBot/ (and AtlasBot.zip) from the same code as atlas_bot.py:

  AtlasBot/
    BASAHIN.txt            how to run it (Tagalog)
    config.py              THE ONLY FILE YOU EDIT: your accounts, stage, ports
    start_atlas_bot.bat    double-click to run (restarts the bot if it ever stops)
    atlas_bot.py           launcher + one dashboard per account (no hidden code inside)
    bots/nbro_app.py       NBRO  (NAS100 + SPX500)
    bots/ember_app.py      EMBER (gold)

    python bots/make_package.py        # run again after changing nbro_app.py, ember_app.py or the launcher
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_all_in_one import TEMPLATE  # noqa: E402

OUT = os.path.join(HERE, "dist", "AtlasBot")

CONFIG = '''r"""
ATLAS BOT SETTINGS — the only file you need to edit.

Each line in ACCOUNTS is one Atlas account (one MT5 terminal each).
  label     a name for the account (shown on its dashboard)
  mt5_path  None = this PC's normal MT5 (only for ONE account);
            with several accounts, give each its own MT5:  r"C:\\MT5_Atlas2\\terminal64.exe"
  stage     "evaluation" while passing the +3% challenge, "funded" after you pass
  btc       False (recommended): BTCUSD is not traded

Dashboards: the 1st account http://127.0.0.1:8800, the 2nd :8801, the 3rd :8802 ...
"""

ACCOUNTS = [
    {"label": "Atlas1", "mt5_path": None, "stage": "evaluation", "btc": False},
    # {"label": "Atlas2", "mt5_path": r"C:\\MT5_Atlas2\\terminal64.exe", "stage": "evaluation", "btc": False},
    # {"label": "Atlas3", "mt5_path": r"C:\\MT5_Atlas3\\terminal64.exe", "stage": "evaluation", "btc": False},
    # {"label": "Atlas4", "mt5_path": r"C:\\MT5_Atlas4\\terminal64.exe", "stage": "evaluation", "btc": False},
    # {"label": "Atlas5", "mt5_path": r"C:\\MT5_Atlas5\\terminal64.exe", "stage": "evaluation", "btc": False},
]

# ---- normally leave these as they are ----
SUFFIX = ""              # broker symbol suffix (empty at Atlas)
HUB_PORT = 8800          # dashboard of the 1st account; the next accounts use 8801, 8802, ...
NBRO_FIRST_PORT = 8777   # internal ports of the bots behind the dashboards
EMBER_FIRST_PORT = 8710

# ---- Telegram alerts (optional) ----
# 1. In Telegram, talk to @BotFather -> /newbot -> copy the TOKEN it gives you.
# 2. Open YOUR new bot's chat and press Start.
# 3. Talk to @userinfobot -> copy your Id (a number).
# 4. Put both here, then test:  python atlas_bot.py --test-telegram
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
'''

README = """ATLAS BOT — NBRO (NAS100 + SPX500) + EMBER (gold)
===================================================

MGA FILE
  config.py              ITO LANG ANG BABAGUHIN MO: mga account, stage (evaluation / funded)
  start_atlas_bot.bat    i-double click para patakbuhin (kusang bubukas ulit kapag tumigil)
  atlas_bot.py           ang nagpapatakbo ng mga bot + dashboard (huwag galawin)
  bots\\nbro_app.py       NBRO  - NAS100 + SPX500, gabi sa Pilipinas (huwag galawin)
  bots\\ember_app.py      EMBER - gold (huwag galawin)

UNANG BESES (isang beses lang)
  1. I-install ang Python 3.10/3.11 (i-check ang "Add Python to PATH").
  2. Sa Command Prompt:   pip install MetaTrader5 pandas numpy
  3. Buksan ang Atlas MT5, mag-log in, i-on ang Algo Trading.
     Tools > Options > Charts > Max bars in chart = 100000 (huwag Unlimited: mabigat sa VPS), tapos i-restart ang MT5.

PATAKBUHIN
  1. Buksan ang config.py at ilagay ang (mga) account mo.
  2. Subukan kung kumokonekta ang bawat MT5:   python check_mt5.py
     Subukan ang settings (walang trade):      python atlas_bot.py --dry-run
  3. I-double click ang start_atlas_bot.bat
  4. Dashboard sa browser:  Atlas1 http://127.0.0.1:8800   Atlas2 :8801   Atlas3 :8802 ...
     Unang tab = Overview: ang 3 market (NAS100, SPX500, gold), balance, bukas na trade, at Stop/Start bawat market.

TELEGRAM (para may alert sa phone)
  1. Sa Telegram, i-message ang @BotFather -> /newbot -> kopyahin ang TOKEN.
  2. Buksan ang chat ng bago mong bot at pindutin ang Start.
  3. I-message ang @userinfobot -> kopyahin ang Id mo (numero).
  4. Ilagay sa config.py:  TELEGRAM_BOT_TOKEN = "..."   TELEGRAM_CHAT_ID = "..."
  5. Subukan:  python atlas_bot.py --test-telegram
  6. I-restart ang bot. Bawat alert ay may [Atlas1-NBRO], [Atlas2-EMBER] ... para alam mo kung aling account.

KAPAG PUMASA KA
  Sa config.py, palitan ang "evaluation" ng "funded" para sa account na iyon, tapos i-restart.

PAALALA
  - Isang start_atlas_bot.bat lang para sa lahat ng account (huwag gumawa ng maraming kopya ng folder).
  - Sa VPS: huwag mag-Sign out; isara lang ang Remote Desktop window.
  - Para ihinto: isara ang window ng start_atlas_bot.bat.
"""

BAT = ('@echo off\r\nREM Runs atlas_bot.py and starts it again if it ever stops. Close this window to stop for good.\r\n'
       'cd /d "%~dp0"\r\nset PY=python\r\nwhere python >nul 2>nul || set PY=py\r\n'
       '%PY% --version >nul 2>nul || (echo Python is not installed: get the 64-bit Python from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)\r\n'
       ':loop\r\necho %date% %time% starting atlas_bot.py\r\n%PY% atlas_bot.py\r\n'
       'echo %date% %time% atlas_bot.py stopped - restarting in 60 seconds (close this window to stop for good)\r\n'
       'timeout /t 60 /nobreak\r\ngoto loop\r\n')


def launcher():
    s = TEMPLATE
    s = s.replace(s[:s.index('"""', 3) + 3], '''"""
ATLAS BOT launcher: runs NBRO (NAS100 + SPX500) and EMBER (gold) on every account in config.py,
with one dashboard per account (1st account http://127.0.0.1:8800, 2nd :8801, ...).

    python atlas_bot.py            (or double-click start_atlas_bot.bat)
    python atlas_bot.py --dry-run  (only show what would start)

Settings are in config.py. The two bots are the files in the bots folder. Ctrl+C stops everything.
All accounts take the SAME trades: they win and lose together.
"""''', 1)
    s = re.sub(r"# =+ EDIT THIS\n.*?\n# =+\n",
               "from config import (ACCOUNTS, EMBER_FIRST_PORT, HUB_PORT, NBRO_FIRST_PORT, SUFFIX,  # noqa: F401\n"
               "                    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)\n", s, count=1, flags=re.S)
    s = re.sub(r"# ---- the two bots, unchanged.*?\ndef unpack_bots\(\):.*?\n\n\n", "", s, count=1, flags=re.S)
    s = s.replace('RUN_DIR = os.path.join(HERE, "atlas_bot_files")', 'RUN_DIR = os.path.join(HERE, "bots")')
    s = s.replace("    unpack_bots()\n    print(", '''    for f in ("nbro_app.py", "ember_app.py"):
        if not os.path.exists(os.path.join(RUN_DIR, f)):
            raise SystemExit(f"bots\\\\{f} is missing: keep the whole AtlasBot folder together.")
    print(''')
    s = s.replace('raise SystemExit("ACCOUNTS is empty: add your account(s) at the top of atlas_bot.py")',
                  'raise SystemExit("ACCOUNTS is empty: add your account(s) in config.py")')
    for mod in ("import base64\n", "import hashlib\n", "import zlib\n"):
        s = s.replace(mod, "", 1)
    assert "BOTS" not in s and "unpack_bots" not in s and "@@" not in s, "template changed: update make_package.py"
    return s


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.path.join(OUT, "bots"))
    files = {"atlas_bot.py": launcher(), "config.py": CONFIG, "BASAHIN.txt": README.replace("\n", "\r\n")}
    for name, text in files.items():
        with open(os.path.join(OUT, name), "w", newline="") as f:
            f.write(text)
    with open(os.path.join(OUT, "start_atlas_bot.bat"), "w", newline="") as f:
        f.write(BAT)
    for b in ("nbro_app.py", "ember_app.py"):
        shutil.copy(os.path.join(HERE, b), os.path.join(OUT, "bots", b))
    shutil.copy(os.path.join(HERE, "check_mt5.py"), os.path.join(OUT, "check_mt5.py"))
    zp = shutil.make_archive(OUT, "zip", os.path.dirname(OUT), "AtlasBot")
    print(f"wrote {OUT}/ and {zp}")
