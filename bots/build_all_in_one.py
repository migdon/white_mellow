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
  4. Run this file and open each account's dashboard: Atlas1 http://127.0.0.1:8800, Atlas2 :8801, Atlas3 :8802 ...
     (NBRO and EMBER of that account as two tabs; every button works from there)
     Ctrl+C stops everything.

The two bots' own code is stored inside this file unchanged (sha256 below) and is written to the folder
"atlas_bot_files" next to this file when it runs; their state, trade history and logs live there too. Don't edit those copies.
All accounts take the SAME trades: they win and lose together. Check Atlas's rules on several accounts before scaling up.
"""

import argparse
import base64
import hashlib
import http.client
import os
import re
import threading
import signal
import subprocess
import sys
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ============================================================================================ EDIT THIS
ACCOUNTS = [
    {"label": "Bot1", "mt5_path": None, "stage": "evaluation", "btc": False},
    # {"label": "Bot2", "mt5_path": r"C:\MT5_Atlas2\terminal64.exe", "stage": "evaluation", "btc": False},
    # {"label": "Bot3", "mt5_path": r"C:\MT5_Atlas3\terminal64.exe", "stage": "evaluation", "btc": False},
]
SUFFIX = ""             # broker symbol suffix, normally empty at Atlas
HUB_PORT = 8800        # dashboards: account #1 http://127.0.0.1:8800, #2 :8801, #3 :8802 ... (NBRO + EMBER of that account)
NBRO_FIRST_PORT = 8777  # internal ports the bots use behind the hub (you don't need to open these)
EMBER_FIRST_PORT = 8710
# Telegram alerts (optional): from @BotFather (token) and @userinfobot (your chat id). Empty = no Telegram.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
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


def setup_telegram():
    """Write the Telegram settings where both bots read them (bots/nbro_telegram_config.json, ember_telegram_config.json).
    Nothing is written when the token is empty, so a config file made by hand is left as it is."""
    import json
    if not (TELEGRAM_BOT_TOKEN.strip() and str(TELEGRAM_CHAT_ID).strip()):
        return False
    cfg = {"enabled": True, "bot_token": TELEGRAM_BOT_TOKEN.strip(), "chat_id": str(TELEGRAM_CHAT_ID).strip()}
    os.makedirs(RUN_DIR, exist_ok=True)
    for name in ("nbro_telegram_config.json", "ember_telegram_config.json"):
        with open(os.path.join(RUN_DIR, name), "w") as f:
            json.dump(cfg, f)
    return True


def test_telegram():
    import json
    import urllib.request
    if not setup_telegram():
        raise SystemExit("Put TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the settings first.")
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN.strip()}/sendMessage",
                                 data=json.dumps({"chat_id": str(TELEGRAM_CHAT_ID).strip(),
                                                  "text": "Atlas Bot: Telegram test OK"}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
        print("Sent. Check Telegram for 'Atlas Bot: Telegram test OK'.")
    except Exception as e:
        print(f"Telegram test FAILED: {e}\n - token wrong?  - chat id wrong?  - did you press Start in your bot's chat first?")


def commands(i, acc):
    stage = acc.get("stage", "")
    if stage not in STAGES:
        raise SystemExit(f"Account {acc.get('label', i + 1)}: stage must be 'evaluation' or 'funded', not {stage!r}")
    common = (["--mt5-path", acc["mt5_path"]] if acc.get("mt5_path") else []) + (["--suffix", SUFFIX] if SUFFIX else [])
    label = acc.get("label") or f"Bot{i + 1}"
    nbro = [sys.executable, os.path.join(RUN_DIR, "nbro_app.py"), *STAGES[stage]["nbro"],
            "--port", str(NBRO_FIRST_PORT + i), "--label", f"{label}-NBRO", *common]
    ember = [sys.executable, os.path.join(RUN_DIR, "ember_app.py"), "--symbols", "XAUUSD", *(["BTCUSD"] if acc.get("btc") else []),
             *STAGES[stage]["ember"], "--port", str(EMBER_FIRST_PORT + i), "--label", f"{label}-EMBER", *common]
    if acc.get("ember", True) is False:         # e.g. a $5k account: gold's smallest lot is ~3% risk there, so NBRO only
        ember = None
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


# ---- dashboards: one port per account (HUB_PORT + account #), that account's NBRO and EMBER behind it --------
HUB_TARGETS = {}            # "0/nbro" -> (title, port)
HUB_PROCS = {}              # "0/nbro" -> Popen (to show running / stopped)
_ABS = re.compile(rb'(["\'])/(status|control|close|dashboard\.js)(["\'])')


HUB_ACCOUNTS = []           # [(label, [target keys])], index = account #


def _hub_page(acc):
    label, keys = HUB_ACCOUNTS[acc]
    tabs = '<button onclick="show(\'ov\')" id="t-ov">Overview</button>' + "".join(
        f'<button onclick="show(\'{k}\')" id="t-{k.replace("/", "-")}">{HUB_TARGETS[k][0].split()[-1]}</button>' for k in keys)
    first = "ov"
    others = ('<span class="acc">Accounts:' + "".join(
        f'<a href="http://127.0.0.1:{HUB_PORT + j}/"{" class=cur" if j == acc else ""}>{lb} :{HUB_PORT + j}</a>'
        for j, (lb, _) in enumerate(HUB_ACCOUNTS)) + "</span>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{label} - Atlas Bot</title><style>
body{{margin:0;font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6}}
header{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 12px;background:#171a21;border-bottom:1px solid #2a2f3a}}
header b{{margin-right:10px}} button{{background:#232836;color:#e6e6e6;border:1px solid #343b4d;border-radius:6px;padding:6px 12px;cursor:pointer}}
button.on{{background:#2f6fed;border-color:#2f6fed}} .dead{{color:#ff6b6b}} #st{{margin-left:auto;font-size:12px;color:#9aa3b2}}
.acc{{font-size:12px;color:#9aa3b2;margin-left:12px}}
.acc a{{display:inline-block;margin-left:6px;padding:5px 10px;border:1px solid #343b4d;border-radius:6px;background:#232836;color:#e6e6e6;text-decoration:none;font-size:13px}}
.acc a.cur{{background:#1f8a4c;border-color:#1f8a4c;color:#fff;font-weight:600}}
iframe{{border:0;width:100%;height:calc(100vh - 52px);background:#fff}}</style></head><body>
<header><b>{label}</b>{tabs}<span id="st"></span>{others}</header><iframe id="f"></iframe>
<script>
function show(k){{document.getElementById("f").src=(k==="ov"?"/overview":"/b/"+k+"/");
 document.querySelectorAll("header button").forEach(b=>b.classList.toggle("on",b.id==="t-"+k.replace("/","-")));
 try{{localStorage.setItem("tab{acc}",k)}}catch(e){{}}}}
async function alive(){{try{{const r=await (await fetch("/alive")).json();
 document.getElementById("st").innerHTML=Object.entries(r).map(([k,v])=>v?"":'<span class="dead">'+k+' stopped</span>').join(" ")||"all bots running";}}catch(e){{}}}}
let t=null;try{{t=localStorage.getItem("tab{acc}")}}catch(e){{}}
show(t&&document.getElementById("t-"+t.replace("/","-"))?t:"{first}");alive();setInterval(alive,10000);
</script></body></html>"""

OVERVIEW_HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;padding:16px;font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.card{background:#171a21;border:1px solid #2a2f3a;border-radius:8px;padding:10px 14px;min-width:140px}
.card .k{font-size:11px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.04em}.card .v{font-size:20px;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:#171a21;border:1px solid #2a2f3a;border-radius:8px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #2a2f3a;font-size:14px;vertical-align:top}
th{font-size:11px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.04em;background:#141720}
.on{color:#4ade80}.off{color:#f87171}.muted{color:#9aa3b2;font-size:12px}.pos{color:#4ade80}.neg{color:#f87171}
button{border:1px solid #343b4d;border-radius:6px;padding:6px 12px;cursor:pointer;color:#fff;font-weight:600}
button.stop{background:#7f1d1d}button.start{background:#166534}button:disabled{opacity:.5}
#note{margin-top:10px;font-size:13px;color:#9aa3b2}
</style></head><body>
<div class="cards" id="cards"></div>
<table><thead><tr><th>Market</th><th>Bot</th><th>Status</th><th>Today</th><th>Open trade</th><th></th></tr></thead><tbody id="rows"></tbody></table>
<div id="note">Stop = no new trades on that market (its waiting orders are cancelled); an open trade is still managed and closed by its rules.</div>
<script>
const ACC = "__ACC__", HAS_EMBER = __HASEMBER__;
const f2 = (x, d=2) => (x === null || x === undefined || isNaN(x)) ? "-" : Number(x).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
async function get(bot){ try { const r = await fetch("/b/"+ACC+"/"+bot+"/status"); return r.ok ? await r.json() : null; } catch(e){ return null; } }
async function post(bot, body){ return fetch("/b/"+ACC+"/"+bot+"/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); }
let N=null, E=null;
async function stopStart(bot, sym, run){
  if (!confirm((run ? "Start " : "Stop ") + sym + "?")) return;
  if (bot === "nbro") {
    let dis = (N && N.config && N.config.disabled_symbols || []).slice();
    dis = run ? dis.filter(x => x !== sym) : Array.from(new Set(dis.concat([sym])));
    await post("nbro", {disabled_symbols: dis});
  } else { const o = {}; o["enabled__"+sym] = run; await post("ember", o); }
  setTimeout(load, 800);
}
function tradeCell(t){
  if (!t) return '<span class="muted">none</span>';
  const r = (t.r === null || t.r === undefined) ? "" : ' <span class="'+(t.r>=0?"pos":"neg")+'">'+(t.r>=0?"+":"")+f2(t.r)+'R</span>';
  const pl = (t.profit === null || t.profit === undefined) ? "" : ' <span class="'+(t.profit>=0?"pos":"neg")+'">$'+f2(t.profit)+'</span>';
  return '<b>'+t.direction+'</b> '+f2(t.volume)+' lots @ '+f2(t.entry)+'<br><span class="muted">SL '+f2(t.sl)+'</span>'+r+pl;
}
function row(sym, bot, running, status, today, trade, up){
  const btn = up ? '<button class="'+(running?"stop":"start")+'" onclick="stopStart(\\''+bot+'\\',\\''+sym+'\\','+(!running)+')">'+(running?"Stop":"Start")+'</button>' : '';
  return '<tr><td><b>'+sym+'</b></td><td>'+bot.toUpperCase()+'</td><td>'+(up?(running?'<span class="on">RUNNING</span>':'<span class="off">STOPPED</span>'):'<span class="off">BOT NOT ANSWERING</span>')+
         '<br><span class="muted">'+(status||"")+'</span></td><td>'+(today||"-")+'</td><td>'+tradeCell(trade)+'</td><td>'+btn+'</td></tr>';
}
async function load(){
  [N, E] = await Promise.all([get("nbro"), HAS_EMBER ? get("ember") : Promise.resolve(null)]);
  const g = (E && E.guards) || {}, ng = (N && N.guards) || {};
  const bal = g.balance ?? ng.account_balance, eq = g.equity ?? ng.equity;
  const dd = (N && N.guards && N.guards.drawdown) || (E && E.guards && E.guards.drawdown) || {};
  const dl = ng.daily_loss_pct ?? g.daily_loss_pct;
  const ts = [N, E].filter(Boolean).map(x => x.trade_stats || {});
  const trades = ts.reduce((a,b)=>a+(b.trades||0),0), wins = ts.reduce((a,b)=>a+(b.wins||0),0), pnl = ts.reduce((a,b)=>a+(b.total_pnl||0),0);
  document.getElementById("cards").innerHTML = [
    ["Balance","$"+f2(bal)],["Equity","$"+f2(eq)],
    ["Today's loss", dl===null||dl===undefined ? "-" : f2(dl)+"%"],
    ["Room to max drawdown", dd.remaining_to_floor_dollars===undefined ? "-" : "$"+f2(dd.remaining_to_floor_dollars)],
    ["Closed trades (bots)", trades+(trades?" ("+Math.round(100*wins/trades)+"% won)":"")],
    ["Closed P&L (bots)", '<span class="'+(pnl>=0?"pos":"neg")+'">$'+f2(pnl)+'</span>']
  ].map(c => '<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>').join("");
  let html = "";
  const nsyms = N ? Object.keys(N.symbols||{}) : ["NAS100","SPX500"];
  for (const s of nsyms) {
    const st = N ? N.symbols[s] : null, run = N ? !(N.config.disabled_symbols||[]).includes(s) : false;
    const ot = N ? (N.open_trades||[]).find(t => t.symbol === s) : null;
    const today = st && st.range_high ? "band "+f2(st.range_low)+" - "+f2(st.range_high)+(st.vwap?"<br><span class=muted>VWAP "+f2(st.vwap)+"</span>":"") : "";
    html += row(s, "nbro", run, st ? st.phase : "", today, ot, !!N);
  }
  const esyms = !HAS_EMBER ? [] : E ? (E.active_symbols||Object.keys(E.symbols||{})) : ["XAUUSD"];
  for (const s of esyms) {
    const st = E ? E.symbols[s] : null, run = st ? st.enabled !== false : false;
    const today = st && st.today_long_level ? "buy above "+f2(st.today_long_level)+"<br>sell below "+f2(st.today_short_level) : "";
    const ot = st && st.open_trade ? Object.assign({}, st.open_trade) : null;
    html += row(s, "ember", run, st ? st.phase + (E.entries_paused ? " (entries paused)" : "") : "", today, ot, !!E);
  }
  document.getElementById("rows").innerHTML = html;
}
load(); setInterval(load, 5000);
</script></body></html>"""


class HubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/plain; charset=utf-8", extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for h, v in extra:
            self.send_header(h, v)
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method):
        m = re.match(r"^/b/(\d+/(?:nbro|ember))(/.*)?$", self.path)
        if not m or m.group(1) not in HUB_ACCOUNTS[self.server.acc][1]:
            return self._send(404, b"not found")
        if m.group(2) is None:
            return self._send(302, b"", extra=[("Location", self.path + "/")])
        port = HUB_TARGETS[m.group(1)][1]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) if method == "POST" else None
        headers = {h: self.headers[h] for h in ("Content-Type", "Authorization") if self.headers.get(h)}
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
            c.request(method, m.group(2), body=body, headers=headers)
            r = c.getresponse()
            data = r.read()
        except OSError:
            return self._send(502, f"{HUB_TARGETS[m.group(1)][0]} is not answering yet (starting, or stopped). "
                                   f"This page retries when you reload it.".encode())
        ctype = r.getheader("Content-Type", "application/octet-stream")
        if "html" in ctype or "javascript" in ctype:
            data = _ABS.sub(rb"\1\2\3", data)          # "/status" -> "status": stays under /b/<account>/<bot>/
        extra = [(h, r.getheader(h)) for h in ("WWW-Authenticate", "Retry-After") if r.getheader(h)]
        self._send(r.status, data, ctype, extra)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, _hub_page(self.server.acc).encode(), "text/html; charset=utf-8")
        if self.path == "/overview":
            has_ember = any(k.endswith("/ember") for k in HUB_ACCOUNTS[self.server.acc][1])
            return self._send(200, OVERVIEW_HTML.replace("__ACC__", str(self.server.acc)).replace("__HASEMBER__", "true" if has_ember else "false")
                              .encode(), "text/html; charset=utf-8")
        if self.path == "/alive":
            import json
            return self._send(200, json.dumps({HUB_TARGETS[k][0]: HUB_PROCS[k].poll() is None for k in HUB_ACCOUNTS[self.server.acc][1] if k in HUB_PROCS}).encode(),
                              "application/json")
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")


def start_hub():
    print()
    for acc, (label, _) in enumerate(HUB_ACCOUNTS):
        port = HUB_PORT + acc
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), HubHandler)
        except OSError as e:
            print(f"Dashboard port {port} ({label}) is busy ({e}): change HUB_PORT at the top of this file. The bots still run.")
            continue
        srv.acc = acc
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f">>> {label} DASHBOARD: http://127.0.0.1:{port}  (NBRO + EMBER)")
    print()


# ---- weekly Telegram summary (every Saturday, after the US week has closed) -------------------------------------
SUMMARY_STATE = os.path.join(RUN_DIR, "weekly_summary_state.json")


def _bot_status(port):
    import json
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/status")
        r = c.getresponse()
        return json.loads(r.read()) if r.status == 200 else None
    except Exception:
        return None


def _telegram_cfg():
    import json
    if TELEGRAM_BOT_TOKEN.strip() and str(TELEGRAM_CHAT_ID).strip():
        return TELEGRAM_BOT_TOKEN.strip(), str(TELEGRAM_CHAT_ID).strip()
    for name in ("nbro_telegram_config.json", "ember_telegram_config.json"):
        try:
            with open(os.path.join(RUN_DIR, name)) as f:
                c = json.load(f)
            if c.get("enabled") and c.get("bot_token") and c.get("chat_id"):
                return c["bot_token"], str(c["chat_id"])
        except Exception:
            continue
    return None, None


def _send_telegram(text):
    import json
    import urllib.request
    token, chat = _telegram_cfg()
    if not token:
        print("Weekly summary: Telegram is not set up (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        return False
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=json.dumps({"chat_id": chat, "text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception as e:
        print(f"Weekly summary: Telegram send failed: {e}")
        return False


def weekly_summary_text(days=7):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    lines = [f"WEEKLY SUMMARY {since:%b %d} - {now:%b %d, %Y}"]
    tot_pnl, tot_n, tot_w = 0.0, 0, 0
    for i, (label, keys) in enumerate(HUB_ACCOUNTS):
        stage = ACCOUNTS[i].get("stage", "?") if i < len(ACCOUNTS) else "?"
        stats = {k.split("/")[1]: _bot_status(HUB_TARGETS[k][1]) for k in keys}
        n, e = stats.get("nbro"), stats.get("ember")
        g = (e or {}).get("guards") or {}
        ng = (n or {}).get("guards") or {}
        bal = g.get("balance") if g.get("balance") is not None else ng.get("account_balance")
        eq = g.get("equity") if g.get("equity") is not None else ng.get("equity")
        per = {}
        for st in (n, e):
            for t in (st or {}).get("recent_trades", []) or []:
                try:
                    ts = datetime.fromisoformat(str(t.get("closed_at")).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if ts < since or t.get("pnl") is None:
                    continue
                d = per.setdefault(t.get("symbol", "?"), [0, 0, 0.0])
                d[0] += 1; d[1] += (t["pnl"] > 0); d[2] += float(t["pnl"])
        an = sum(v[0] for v in per.values()); aw = sum(v[1] for v in per.values()); ap = sum(v[2] for v in per.values())
        tot_pnl += ap; tot_n += an; tot_w += aw
        openn = len((n or {}).get("open_trades") or []) + len((e or {}).get("open_trades") or [])
        down = [b.upper() for b, st in (("nbro", n), ("ember", e)) if st is None]
        lines.append("")
        lines.append(f"[{label}] {stage}" + (f"  !! {' and '.join(down)} NOT ANSWERING" if down else ""))
        if bal is not None:
            lines.append(f"  balance ${bal:,.2f}" + (f"  equity ${eq:,.2f}" if eq is not None else ""))
        lines.append(f"  week: {an} trades, {aw} won, P&L ${ap:+,.2f}" + (f"  | open now: {openn}" if openn else ""))
        for sym, (c, w, pnl) in sorted(per.items()):
            lines.append(f"    {sym}: {c} trades, {w} won, ${pnl:+,.2f}")
    if len(HUB_ACCOUNTS) > 1:
        lines.append("")
        lines.append(f"ALL ACCOUNTS: {tot_n} trades, {tot_w} won, P&L ${tot_pnl:+,.2f}")
    return "\n".join(lines)


def _weekly_summary_loop():
    import json
    from datetime import datetime, timezone
    while True:
        try:
            now = datetime.now(timezone.utc)
            week = f"{now.isocalendar()[0]}-{now.isocalendar()[1]}"
            try:
                with open(SUMMARY_STATE) as f:
                    last = json.load(f).get("week")
            except Exception:
                last = None
            # Saturday 02:00 UTC or later (= Saturday 10:00 in the Philippines), once per week
            if now.weekday() == 5 and now.hour >= 2 and last != week:
                if _send_telegram(weekly_summary_text()):
                    with open(SUMMARY_STATE, "w") as f:
                        json.dump({"week": week, "sent_at": now.isoformat()}, f)
        except Exception as e:
            print(f"Weekly summary error (bots keep running): {e}")
        time.sleep(600)


def stop(p):
    if p.poll() is None:
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        except Exception:
            p.terminate()


def main():
    ap = argparse.ArgumentParser(description="NBRO + EMBER on one or several Atlas accounts, from one file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-telegram", action="store_true", help="send one test message and exit")
    ap.add_argument("--weekly-summary-now", action="store_true",
                    help="send the weekly summary now (the bots must be running) and exit")
    a = ap.parse_args()
    if a.test_telegram:
        return test_telegram()
    if a.weekly_summary_now:
        for i, acc in enumerate(ACCOUNTS):
            lb = acc.get("label") or f"Bot{i + 1}"
            HUB_TARGETS[f"{i}/nbro"] = (f"{lb} NBRO", NBRO_FIRST_PORT + i)
            HUB_TARGETS[f"{i}/ember"] = (f"{lb} EMBER", EMBER_FIRST_PORT + i)
            HUB_ACCOUNTS.append((lb, [f"{i}/nbro"] + ([f"{i}/ember"] if acc.get("ember", True) is not False else [])))
        text = weekly_summary_text()
        print(text)
        print("\nSent to Telegram." if _send_telegram(text) else "")
        return
    if not ACCOUNTS:
        raise SystemExit("ACCOUNTS is empty: add your account(s) at the top of atlas_bot.py")
    plan = [commands(i, acc) for i, acc in enumerate(ACCOUNTS)]
    print(f"{'#':<3}{'account':<12}{'stage':<12}{'bots':<13}{'dashboard':<26}MT5")
    for i, (label, stage, _, ember) in enumerate(plan):
        print(f"{i + 1:<3}{label:<12}{stage:<12}{'NBRO+EMBER' if ember else 'NBRO only':<13}{'http://127.0.0.1:' + str(HUB_PORT + i):<26}"
              f"{ACCOUNTS[i].get('mt5_path') or '(this PC default MT5)'}")
        HUB_ACCOUNTS.append((label, [f"{i}/nbro"] + ([f"{i}/ember"] if ember else [])))
        HUB_TARGETS[f"{i}/nbro"] = (f"{label} NBRO", NBRO_FIRST_PORT + i)
        HUB_TARGETS[f"{i}/ember"] = (f"{label} EMBER", EMBER_FIRST_PORT + i)
    problems = check_setup()
    if problems:
        raise SystemExit("Fix these first:\n  - " + "\n  - ".join(problems))
    unpack_bots()
    print("Telegram alerts: " + ("ON (settings written for both bots)" if setup_telegram() else
                                 "not set in the settings (an existing bots telegram file, if any, is still used)"))
    if a.dry_run:
        for label, _, nbro, ember in plan:
            print(f"\n[{label}] " + " ".join(nbro) + (f"\n[{label}] " + " ".join(ember) if ember else f"\n[{label}] (no EMBER)"))
        return
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    running = {}
    for i, (label, _, nbro, ember) in enumerate(plan):
        procs = {"NBRO": subprocess.Popen(nbro, cwd=RUN_DIR, creationflags=flags)}
        if ember:
            procs["EMBER"] = subprocess.Popen(ember, cwd=RUN_DIR, creationflags=flags)
        running[label] = procs
        HUB_PROCS[f"{i}/nbro"] = procs["NBRO"]
        if ember:
            HUB_PROCS[f"{i}/ember"] = procs["EMBER"]
        time.sleep(3)
    start_hub()
    threading.Thread(target=_weekly_summary_loop, daemon=True).start()
    print("Weekly Telegram summary: every Saturday from 02:00 UTC (10:00 in the Philippines).")
    print(f"\nRunning {len(running)} account(s). Ctrl+C stops everything.\n")
    try:
        while running:
            for label, procs in list(running.items()):
                dead = [n for n, p in procs.items() if p.poll() is not None]
                if dead:
                    print(f"[{label}] {' and '.join(dead)} stopped: stopping the other bot of {label} too.")
                    for p in procs.values():
                        stop(p)
                    del running[label]
            time.sleep(5)
        print("All accounts stopped.")
    except KeyboardInterrupt:
        print("\nStopping all accounts...")
        for procs in running.values():
            for p in procs.values():
                stop(p)
        for procs in running.values():
            for p in procs.values():
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
