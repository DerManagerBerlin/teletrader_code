#!/usr/bin/env python3
# Patch 104 - Watchdog kann das Terminal einmalig mit Konfiguration starten.
#
#   Eingaben erreichen Wine nicht, der Login von Hand faellt aus. MT5 kann
#   sich aber beim Start selbst anmelden, wenn ihm eine Konfigurationsdatei
#   mitgegeben wird. Dafuer braucht die Startzeile im Watchdog einen
#   optionalen Zusatz.
#
#   Einmalig heisst: Liegt die Datei .mt5_start_cfg vor, wird ihr Inhalt
#   als Argument uebergeben und die Datei sofort geloescht. Jeder weitere
#   Start laeuft wieder ohne. Es bleibt also nichts zurueck, was spaeter
#   ueberraschen koennte.
#
#   Die laufende watchdog.sh wird NICHT in place geaendert. Bash liest
#   Skripte haeppchenweise nach; eine Aenderung an der offenen Datei kann
#   mitten im Lauf Unsinn ausfuehren. Deshalb neue Datei, dann ersetzen,
#   dann Neustart.
import os, shutil, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
WD = os.path.join(TT, "watchdog.sh")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH104 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=40):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:200]
    except Exception as e:
        return "Fehler: " + str(e)[:60]

if not os.path.exists(WD):
    melde("ABBRUCH: watchdog.sh fehlt"); raise SystemExit(0)

with open(WD, encoding="utf-8") as f:
    src = f.read()

if "mt5_start_cfg" in src:
    melde("schon vorhanden"); raise SystemExit(0)

ALT = '        WINEDEBUG=-all DISPLAY=:99 wine "$MT5" &\n'
if ALT not in src:
    melde("ABBRUCH: Startzeile nicht wie erwartet"); raise SystemExit(0)

NEU = ('        # Einmalstart mit Konfiguration (Patch 104). Liegt die Datei\n'
       '        # vor, meldet MT5 sich beim Start selbst am dort genannten\n'
       '        # Konto an. Danach wird sie geloescht, der naechste Start\n'
       '        # laeuft wieder ohne.\n'
       '        _MT5CFG="$HOME/teletrader/.mt5_start_cfg"\n'
       '        if [ -s "$_MT5CFG" ]; then\n'
       '            _CFGARG=$(head -1 "$_MT5CFG")\n'
       '            rm -f "$_MT5CFG"\n'
       '            wlog "MT5 Start mit Konfiguration"\n'
       '            WINEDEBUG=-all DISPLAY=:99 wine "$MT5" "$_CFGARG" &\n'
       '        else\n'
       '            WINEDEBUG=-all DISPLAY=:99 wine "$MT5" &\n'
       '        fi\n')

shutil.copyfile(WD, WD + ".bak_104")
TMP = WD + ".neu104"
with open(TMP, "w", encoding="utf-8") as f:
    f.write(src.replace(ALT, NEU, 1)); f.flush(); os.fsync(f.fileno())
os.chmod(TMP, 0o755)

if "SYNTAXOK" not in sh("bash -n '" + TMP + "' && echo SYNTAXOK"):
    melde("SYNTAXFEHLER, nichts geaendert")
    try: os.remove(TMP)
    except Exception: pass
    raise SystemExit(0)

os.replace(TMP, WD)          # neue Inode, die laufende Instanz bleibt heil
melde("watchdog.sh erweitert, Sicherung .bak_104")
melde("Gegenprobe: " + sh("bash -n '" + WD + "' && echo ok"))
melde("Neustart, damit der neue Watchdog laeuft: " +
      sh("sudo -n systemctl restart teletrader.service 2>&1 && echo OK", t=60))
print("Patch 104 fertig")
