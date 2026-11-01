#!/usr/bin/env python3
# patch_127_erststart.py
# NO_RESTART - der laufende Bot wird nicht angefasst.
#
# Der Installer meldete rc=1, das Verzeichnis ist aber angelegt. Dieser Patch
# sieht nach, ob die Installation vollstaendig ist, und startet das Terminal
# einmal im portablen Modus. Erst beim ersten Start legt MT5 sein
# Datenverzeichnis an und holt die Serverliste des Brokers. Danach wird es
# wieder beendet. Kein Login, keine Zugangsdaten.
import io, os, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
SKRIPT = os.path.join(TT, "ultima_erststart.sh")


def sag(t):
    print("PATCH127 " + str(t))


INHALT = r'''#!/bin/bash
exec >> "$HOME/teletrader/ultima_install.log" 2>&1
set -u
PUB="$HOME/ttpub"
melde() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') ERST127 $*" >> "$PUB/status.txt"; echo "$*"; }
mkdir -p "$PUB"

D=$(ls -d "$HOME/.wine/drive_c/Program Files/"*[Uu]ltima*/ 2>/dev/null | head -1)
if [ -z "${D:-}" ]; then melde "kein Ultima-Verzeichnis"; exit 1; fi
melde "Verzeichnis: $(basename "$D")"
melde "Dateien gesamt: $(find "$D" -type f 2>/dev/null | wc -l), Groesse $(du -sh "$D" 2>/dev/null | cut -f1)"
melde "terminal64.exe: $(stat -c %s "$D/terminal64.exe" 2>/dev/null || echo fehlt) Bytes"
for f in terminal64.exe metaeditor64.exe MQL5 Bases config; do
    [ -e "$D/$f" ] && melde "  vorhanden: $f" || melde "  FEHLT: $f"
done

# Nachinstallieren, falls das Terminal unvollstaendig ist
SZ=$(stat -c %s "$D/terminal64.exe" 2>/dev/null || echo 0)
if [ "$SZ" -lt 1000000 ]; then
    melde "terminal64.exe zu klein, Installer wird wiederholt"
    cd "$HOME/mt5inst" 2>/dev/null && WINEDEBUG=-all DISPLAY=:99 timeout 900 wine ultimamarkets5setup.exe /auto
    melde "Wiederholung rc=$?"
    sleep 15
fi

export WINEDEBUG=-all DISPLAY=:99
cd "$D" || exit 1
melde "Erststart im portablen Modus"
nohup wine "$D/terminal64.exe" /portable >/dev/null 2>&1 &
sleep 150

melde "config vorhanden: $([ -d "$D/config" ] && echo ja || echo nein)"
melde "common.ini: $([ -f "$D/config/common.ini" ] && echo ja || echo nein)"
melde "srv-Dateien: $(find "$D" -maxdepth 3 -iname '*.srv' 2>/dev/null | wc -l)"
find "$D" -maxdepth 3 -iname '*.srv' 2>/dev/null | head -6 | while IFS= read -r s; do
    melde "  $(basename "$s")"
done
melde "servers.dat: $(find "$D" -maxdepth 3 -iname 'servers.dat' 2>/dev/null | wc -l)"
melde "Bases-Verzeichnisse: $(ls -1 "$D/Bases" 2>/dev/null | head -4 | tr '\n' ' ')"
L=$(find "$D/logs" -name '*.log' 2>/dev/null | sort | tail -1)
if [ -n "${L:-}" ]; then
    melde "Terminal-Log letzte Zeilen:"
    tail -6 "$L" 2>/dev/null | sed 's/[[:space:]]\+/ /g' | cut -c1-150 | while IFS= read -r z; do melde "   $z"; done
else
    melde "kein Terminal-Log gefunden"
fi

for p in $(pgrep -f "terminal64.exe" 2>/dev/null); do
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$c" in *[Uu]ltima*) kill "$p" 2>/dev/null; melde "Ultima-Terminal PID $p beendet" ;; esac
done
melde "Erststart fertig"
'''

os.makedirs(TT, exist_ok=True)
tmp = SKRIPT + ".neu"
with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
    f.write(INHALT)
os.chmod(tmp, 0o755)
os.replace(tmp, SKRIPT)
sag("Skript geschrieben")
try:
    subprocess.Popen(["setsid", "bash", SKRIPT],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, cwd=TT)
    sag("Erststart abgekoppelt gestartet, Ergebnis in etwa 4 Minuten als ERST127")
except Exception as e:
    sag("FEHLER: " + str(e))
    sys.exit(1)
