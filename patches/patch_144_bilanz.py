#!/usr/bin/env python3
# patch_144_bilanz.py
# NO_RESTART - liest nur.
#
# Der Kontostandverlauf mischt Demo und Live und ist dadurch unlesbar. Hier
# wird die echte Abschlussliste direkt beim Broker geholt und nach Urheber
# getrennt: Magic 88888 ist der Bot, Magic 0 ist von Hand gestellt.
# Ergebnis als CSV in ttpub, dazu eine Zusammenfassung in status.txt.
# Keine Kontonummer, keine Zugangsdaten in der Ausgabe.
import io, os, re, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
_z = []


def sag(t):
    t = str(t)
    print("PATCH144 " + t)
    _z.append(t)


def env_wert(key, vor=""):
    try:
        with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
            for ln in f:
                m = re.match(r"^\s*(?:export\s+)?" + re.escape(key) +
                             r"\s*=\s*(.*?)\s*$", ln.rstrip("\n"))
                if m:
                    v = m.group(1)
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    return v
    except Exception:
        pass
    return vor


W = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                           "Python*", "python.exe"))
if not W:
    sag("ABBRUCH: Wine-Python fehlt")
    sys.exit(0)

ZIEL = "Z:\\home\\alexander_lacher\\ttpub\\deals_live.csv"
PROBE = os.path.join(TT, ".probe144.py")
CODE = '''import os, csv
from datetime import datetime, timedelta
import MetaTrader5 as mt5
p = os.environ.get("TTPATH") or ""
a = {"path": p} if p else {}
if os.environ.get("TTPORT") == "true":
    a["portable"] = True
print("INIT", mt5.initialize(**a), mt5.last_error())
ai = mt5.account_info()
if ai:
    print("MODUS Konto ***" + str(ai.login)[-3:], "Server", ai.server,
          "Balance", round(ai.balance, 2), "Equity", round(ai.equity, 2))
von = datetime(2026, 11, 1)
bis = datetime.now() + timedelta(days=1)
dl = mt5.history_deals_get(von, bis) or []
print("DEALS", len(dl))
zeilen = []
sum_bot = sum_hand = 0.0
n_bot = n_hand = 0
for d in dl:
    if d.entry != 1:          # nur Schliessungen zaehlen als Ergebnis
        continue
    erg = float(d.profit) + float(d.swap) + float(d.commission)
    wer = "BOT" if int(d.magic) == 88888 else "HAND"
    if wer == "BOT":
        sum_bot += erg; n_bot += 1
    else:
        sum_hand += erg; n_hand += 1
    zeilen.append([datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S"),
                   wer, d.symbol, d.volume, round(float(d.price), 2),
                   round(erg, 2), int(d.magic), str(d.comment)[:30]])
with open(os.environ["TTZIEL"], "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["zeit", "wer", "symbol", "volumen", "preis", "ergebnis",
                "magic", "kommentar"])
    w.writerows(zeilen)
print("BILANZ Bot:", n_bot, "Abschluesse", round(sum_bot, 2), "EUR")
print("BILANZ Hand:", n_hand, "Abschluesse", round(sum_hand, 2), "EUR")
for sym in sorted(set(z[2] for z in zeilen)):
    s = sum(z[5] for z in zeilen if z[2] == sym)
    nb = sum(1 for z in zeilen if z[2] == sym and z[1] == "BOT")
    nh = sum(1 for z in zeilen if z[2] == sym and z[1] == "HAND")
    print("SYMBOL", sym, round(s, 2), "EUR |", nb, "Bot,", nh, "Hand")
print("OFFEN", len(mt5.positions_get() or []))
for q in (mt5.positions_get() or []):
    print("POS", q.symbol, "vol", q.volume, "magic", q.magic,
          "profit", round(q.profit, 2), "sl", q.sl, "tp", q.tp)
# Margin fuer BTC, Frage zum neuen Kanal
mt5.symbol_select("BTCUSD", True)
tb = mt5.symbol_info_tick("BTCUSD")
sb = mt5.symbol_info("BTCUSD")
if tb and sb:
    print("BTC bid", tb.bid, "Spread",
          round((tb.ask - tb.bid), 2), "USD | min", sb.volume_min,
          "| Margin 0.01 Lot",
          mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, "BTCUSD", 0.01, tb.ask))
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)
_u = dict(os.environ)
_u.update({"TTPATH": env_wert("MT5_TERMINAL_PATH", ""),
           "TTPORT": env_wert("MT5_TERMINAL_PORTABLE", "false").lower(),
           "TTZIEL": ZIEL, "DISPLAY": ":99", "WINEDEBUG": "-all"})
try:
    _p = subprocess.run(["wine", W[0], "Z:" + PROBE.replace("/", "\\")],
                        env=_u, capture_output=True, text=True, timeout=300)
    _aus = ((_p.stdout or "") + "\n" + (_p.stderr or "")).strip()
except Exception as e:
    _aus = "Fehler: " + str(e)
finally:
    try:
        os.remove(PROBE)
    except Exception:
        pass
for _l in _aus.splitlines():
    _l = _l.strip()
    if _l.startswith(("INIT", "MODUS", "DEALS", "BILANZ", "SYMBOL", "OFFEN",
                      "POS", "BTC")):
        sag(_l[:210])

# Warum war der Bot am 3.11. kurz auf Demo
sag("DEMO_MODE in .env jetzt: " + env_wert("DEMO_MODE", "(fehlt)"))
_bl = os.path.join(TT, "bot.log")
try:
    _tr = subprocess.run(
        "grep -a -n 'Selbstheilung\\|zurueck auf Demo\\|/demo\\|/live\\|Live-Login\\|"
        "LIVE-Login\\|Login-Sperre' " + _bl + " | tail -8",
        shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    for _l in (_tr.splitlines() or ["keine Treffer"]):
        sag("LOG " + _l[:190])
except Exception as e:
    sag("Logsuche: " + str(e))

try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("BILANZ144 " + x + "\n")
except Exception:
    pass
