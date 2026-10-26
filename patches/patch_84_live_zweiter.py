#!/usr/bin/env python3
# Patch 84 - zweiter Anlauf des Live-Umstiegs, laengeres Fenster.
#
#   Warum anders als bisher:
#     Der Weg ueber mt5.initialize(login=...) meldet das LAUFENDE Terminal
#     um. Das endet zweimal in (-10005, 'IPC timeout'), auch mit 180 s.
#     Stattdessen wird hier Konto und Server in common.ini eingetragen und
#     das Terminal neu gestartet. Dann meldet MT5 sich beim Start selbst
#     an, so wie es das mit dem Demokonto taeglich tut. Das Passwort holt
#     MT5 aus seinem eigenen Speicher (accounts.dat); es steht nirgends in
#     diesem Skript und wird nicht ausgegeben.
#
#   Sicherheitsnetz: Klappt der Livestart nicht, wird alles zurueckgedreht
#   (common.ini aus der Sicherung, DEMO_MODE=true) und der Bot laeuft
#   weiter auf Demo. Besser ein Bot auf Demo als keiner.
#
#   [Experts] Enabled=1 wird in beiden Faellen gesetzt, damit AutoTrading
#   laeuft. MT5 schaltet es bei jedem Kontowechsel selbst ab.
import os, re, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
BOTLOG = os.path.join(TT, "bot.log")
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
INI = os.path.join(MT5DIR, "Config", "common.ini")
MARKE = os.path.join(TT, ".patch84_laeuft")
UNIT = "teletrader.service"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH live84: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=60):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)

# --- Doppellauf verhindern ----------------------------------------------
if os.path.exists(MARKE):
    try:
        alt = time.time() - os.path.getmtime(MARKE)
    except Exception:
        alt = 0
    if alt < 900:
        melde("laeuft bereits seit " + str(int(alt)) + "s, kein zweiter Lauf")
        raise SystemExit(0)
try:
    with open(MARKE, "w") as f:
        f.write(datetime.now().isoformat())
except Exception:
    pass

# --- Zugangsdaten: nur Kontonummer und Server, kein Passwort -------------
live_login = live_server = ""
try:
    with open(ENV, encoding="utf-8") as f:
        for z in f:
            s = z.strip()
            if s.startswith("LIVE_MT5_LOGIN="):
                live_login = s.split("=", 1)[1].strip()
            elif s.startswith("LIVE_MT5_SERVER="):
                live_server = s.split("=", 1)[1].strip()
except Exception as e:
    melde("ABBRUCH: .env nicht lesbar: " + str(e)); raise SystemExit(0)

if not live_login.isdigit():
    melde("ABBRUCH: LIVE_MT5_LOGIN ist keine Kontonummer"); raise SystemExit(0)
melde("Ziel: Konto endet auf " + live_login[-3:] + ", Server laut .env: " +
      (live_server or "(leer)"))

# --- Servernamen gegen die Serverliste des Terminals pruefen -------------
srv = sh("find '" + MT5DIR + "' -maxdepth 3 -iname '*.srv' -printf '%f\\n' "
         "2>/dev/null | sed 's/\\.srv$//' | head -40")
melde("Terminal kennt: " + (srv or "(keine srv-Dateien gefunden)"))
kandidaten = [s.strip() for s in srv.split(" | ") if s.strip()]
treffer = [k for k in kandidaten if "ultima" in k.lower()]
if treffer and live_server not in kandidaten:
    melde("Servername aus .env steht nicht in der Liste, nehme: " + treffer[0])
    live_server = treffer[0]
if not live_server:
    melde("ABBRUCH: kein Livesserver bestimmbar"); raise SystemExit(0)

# --- common.ini schreiben ------------------------------------------------
def kodierung(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if b[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4:
        return "utf-16-le"
    return "utf-8"

def setze_ini(login, server):
    """Login/Server unter [Common] und Enabled=1 unter [Experts]."""
    with open(INI, "rb") as f:
        roh = f.read()
    kod = kodierung(roh)
    text = roh.decode(kod, errors="strict")
    crlf = "\r\n" in text
    zeilen = text.split("\r\n") if crlf else text.split("\n")
    abschnitt = ""
    sah = {"Login": False, "Server": False, "Enabled": False}
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("[") and s.endswith("]"):
            abschnitt = s.lower(); continue
        if abschnitt == "[common]" and re.match(r"^\s*Login\s*=", z, re.I):
            zeilen[i] = "Login=" + login; sah["Login"] = True
        elif abschnitt == "[common]" and re.match(r"^\s*Server\s*=", z, re.I):
            zeilen[i] = "Server=" + server; sah["Server"] = True
        elif abschnitt == "[experts]" and re.match(r"^\s*Enabled\s*=", z, re.I):
            zeilen[i] = "Enabled=1"; sah["Enabled"] = True
    for name, wert, kopf in (("Login", login, "[common]"),
                             ("Server", server, "[common]"),
                             ("Enabled", "1", "[experts]")):
        if sah[name]:
            continue
        for i, z in enumerate(zeilen):
            if z.strip().lower() == kopf:
                zeilen.insert(i + 1, name + "=" + wert); break
    neu = ("\r\n" if crlf else "\n").join(zeilen)
    st = os.stat(INI)
    tmp = INI + ".neu84"
    with open(tmp, "wb") as f:
        f.write(neu.encode(kod)); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, INI)

def setze_env(demo):
    with open(ENV, encoding="utf-8") as f:
        zeilen = f.readlines()
    neu, da = [], False
    for z in zeilen:
        if z.strip().startswith("DEMO_MODE="):
            neu.append("DEMO_MODE=" + ("true" if demo else "false") + "\n"); da = True
        else:
            neu.append(z)
    if not da:
        neu.append("DEMO_MODE=" + ("true" if demo else "false") + "\n")
    tmp = ENV + ".tmp84"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(neu); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV)

if not os.path.exists(INI):
    melde("ABBRUCH: common.ini fehlt"); raise SystemExit(0)

sh("cp -p '" + INI + "' '" + INI + ".bak_84'")
sh("cp -p '" + ENV + "' '" + ENV + ".bak_84'")
melde("Sicherungen angelegt")

try:
    setze_ini(live_login, live_server)
    setze_env(False)
    # IPC-Timeouts sind keine abgelehnten Logins - Zaehler zuruecksetzen
    for f_ in ("LOGIN_FAILS", os.path.join(TT, "LOGIN_FAILS")):
        try:
            if os.path.exists(f_):
                os.remove(f_)
        except Exception:
            pass
    melde("Konfiguration auf LIVE gesetzt (Server " + live_server + ")")
except Exception as e:
    melde("FEHLER beim Schreiben: " + str(e))
    sh("cp -p '" + INI + ".bak_84' '" + INI + "'")
    sh("cp -p '" + ENV + ".bak_84' '" + ENV + "'")
    raise SystemExit(0)

# Stand vor dem Neustart merken, damit eine alte LIVECHECK-Zeile nicht
# faelschlich als Erfolg durchgeht.
def lcheck_zahl():
    n = sh("grep -c 'LIVECHECK Modus' '" + BOTLOG + "' 2>/dev/null").strip()
    return int(n) if n.isdigit() else 0

vor_n = lcheck_zahl()
melde("LIVECHECK-Zeilen vor dem Neustart: " + str(vor_n))

melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))

# --- Ergebnis abwarten ---------------------------------------------------
erfolg = False
zeile = ""
for _ in range(54):            # bis 270 s, laenger als der 180s-Login
    time.sleep(5)
    if lcheck_zahl() <= vor_n:
        continue               # noch keine NEUE Zeile, also noch nicht oben
    zeile = sh("grep 'LIVECHECK Modus' '" + BOTLOG + "' 2>/dev/null | tail -1")
    if "Modus=LIVE" in zeile and live_login[-3:] in zeile:
        erfolg = True
    break                      # neue Zeile da: Ergebnis steht fest

melde("LIVECHECK: " + (zeile or "(noch keine Zeile)"))

# Was sagt das Terminal selbst? Das entscheidet, ob es bei Ultima
# ueberhaupt angekommen ist.
melde("Config-Inhalt: " + sh("ls -1 '" + MT5DIR + "/Config' 2>/dev/null | head -12"))
melde("Terminal-Log: " + sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); [ -n \"$L\" ] && tail -25 \"$L\" | grep -iE 'login|authoriz|connect|server|ultima|invalid|failed' | tail -8 || echo '(kein Log)'"))

if erfolg:
    melde("LIVE steht. AutoTrading: " +
          ("an" if "TradeAllowed=True" in zeile else "PRUEFEN"))
else:
    melde("Livestart nicht bestaetigt - drehe zurueck auf Demo")
    sh("cp -p '" + INI + ".bak_84' '" + INI + "'")
    try:
        setze_env(True)
    except Exception as e:
        melde("ENV-Ruecksetzen fehlgeschlagen: " + str(e))
    # AutoTrading auch auf Demo wieder einschalten
    try:
        with open(INI, "rb") as f:
            roh = f.read()
        kod = kodierung(roh)
        t = roh.decode(kod, errors="replace")
        crlf = "\r\n" in t
        zs = t.split("\r\n") if crlf else t.split("\n")
        ab = ""
        for i, z in enumerate(zs):
            s = z.strip()
            if s.startswith("[") and s.endswith("]"):
                ab = s.lower(); continue
            if ab == "[experts]" and re.match(r"^\s*Enabled\s*=", z, re.I):
                zs[i] = "Enabled=1"
        with open(INI + ".neu84b", "wb") as f:
            f.write((("\r\n" if crlf else "\n").join(zs)).encode(kod))
        os.replace(INI + ".neu84b", INI)
    except Exception as e:
        melde("Enabled auf Demo nicht gesetzt: " + str(e))
    melde("Neustart zurueck: " + sh("sudo -n systemctl restart " + UNIT +
                                    " 2>&1 && echo OK"))
    time.sleep(20)
    melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1"))

try:
    os.remove(MARKE)
except Exception:
    pass
print("Patch 84 fertig")
