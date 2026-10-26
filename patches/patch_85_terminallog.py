#!/usr/bin/env python3
# Patch 85 - reine Lesung, aendert nichts, startet nichts neu.
#
#   Zwei Umstiegsversuche auf das Livekonto sind ohne jede Rueckmeldung
#   verlaufen. Die entscheidende Frage ist, ob das Terminal ueberhaupt
#   versucht, sich bei UltimaMarkets anzumelden, oder ob es den Server gar
#   nicht erreicht. Das steht im Log des Terminals selbst.
#
#   Zugangsdaten werden nicht ausgegeben: Zeilen mit Passwortbezug fliegen
#   raus, Kontonummern werden auf die letzten drei Stellen gekuerzt.
import os, re, subprocess
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH tlog: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=60):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

GEHEIM = re.compile(r"(?i)(pass|pwd|kennwor|secret)")

def sauber(z):
    if GEHEIM.search(z):
        return ""
    # Kontonummern kuerzen
    return re.sub(r"\b(\d{5,})\b", lambda m: "***" + m.group(1)[-3:], z)

melde("Logdatei: " + sh("ls -lt '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -2 | tr '\\n' ' '")[:200])

roh = sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
         "[ -n \"$L\" ] && tail -45 \"$L\" || echo KEINLOG")
zeilen = [sauber(z.strip()) for z in roh.splitlines()]
zeilen = [z for z in zeilen if z]
if not zeilen:
    melde("Terminal-Log leer oder nicht lesbar")
for z in zeilen[-24:]:
    melde("TLOG " + z[:200])

melde("Ultima im ganzen Log? " + (sh(
    "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
    "[ -n \"$L\" ] && grep -ic ultima \"$L\" || echo 0") or "0") + " Treffer")

melde("zweites MT5 auf dem Rechner? " + (sh(
    "find $HOME -maxdepth 6 -iname 'terminal64.exe' -printf '%p\\n' 2>/dev/null "
    "| head -5 | tr '\\n' ' '") or "(nur eins)"))

melde("Serverlisten: " + (sh(
    "find '" + MT5DIR + "' -maxdepth 3 \\( -iname '*.srv' -o -iname 'servers*' \\) "
    "-printf '%P ' 2>/dev/null | head -c 250") or "(keine)"))

print("Patch 85 fertig")
