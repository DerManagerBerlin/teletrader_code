#!/usr/bin/env python3
# patch_120_ultima.py
# NO_RESTART - der laufende Bot wird nicht angefasst.
#
# Befund 119: installiert ist nur das Terminal von PU Prime, und es kennt
# keinen Ultima-Server. Das erklaert die vier gescheiterten Kontowechsel.
# Dieser Patch holt den Installer von Ultima Markets (Adresse aus 119
# bestaetigt, HTTP 200) und installiert ihn im selben Wine-Prefix daneben.
#
# Der Patch selbst kehrt sofort zurueck. Die Installation laeuft abgekoppelt
# weiter, sonst wuerde der naechste cron-Lauf von ttpull darueber stolpern.
# Das frisch gestartete Terminal wird am Ende wieder beendet, damit es dem
# laufenden Bot nicht die IPC-Verbindung wegnimmt. Kein Loginversuch hier.
import io, os, stat, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
SKRIPT = os.path.join(TT, "ultima_install.sh")
URL = ("https://download.mql5.com/cdn/web/ultima.markets.ltd/mt5/"
       "ultimamarkets5setup.exe")


def sag(t):
    print("PATCH120 " + str(t))


INHALT = r'''#!/bin/bash
# Von patch_120_ultima.py geschrieben. Installiert das Terminal von Ultima
# Markets im vorhandenen Wine-Prefix, beendet es danach wieder.
exec >> "$HOME/teletrader/ultima_install.log" 2>&1
set -u
PUB="$HOME/ttpub"
melde() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') INSTALL120 $*" >> "$PUB/status.txt"; echo "$*"; }

echo "===== $(date -u) Start ====="
mkdir -p "$HOME/mt5inst" "$PUB"
cd "$HOME/mt5inst" || { melde "Verzeichnis nicht anlegbar"; exit 1; }

VORHER=$(ls -d "$HOME/.wine/drive_c/Program Files/"*/ 2>/dev/null | wc -l)

if ! curl -fsSL --max-time 300 -o ultimamarkets5setup.exe "URL_PLATZHALTER"; then
    melde "Download fehlgeschlagen"
    exit 1
fi
SZ=$(stat -c %s ultimamarkets5setup.exe 2>/dev/null || echo 0)
melde "Installer geladen, $SZ Bytes"
if [ "$SZ" -lt 100000 ]; then
    melde "Datei zu klein, vermutlich kein Installer"
    exit 1
fi

export WINEDEBUG=-all
export DISPLAY=:99
timeout 900 wine ultimamarkets5setup.exe /auto
RC=$?
melde "Installer beendet, rc=$RC"

sleep 20
FUND=$(find "$HOME/.wine/drive_c/Program Files" -maxdepth 2 -name terminal64.exe 2>/dev/null)
NACHHER=$(ls -d "$HOME/.wine/drive_c/Program Files/"*/ 2>/dev/null | wc -l)
melde "Programmverzeichnisse $VORHER -> $NACHHER"
echo "$FUND" | while IFS= read -r t; do
    [ -z "$t" ] && continue
    melde "Terminal: $(basename "$(dirname "$t")")"
done

# Frisch gestartetes Ultima-Terminal wieder beenden: zwei Terminals teilen
# sich sonst die Python-IPC und der Bot verliert seine Verbindung.
for p in $(pgrep -f "terminal64.exe" 2>/dev/null); do
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$c" in
        *[Uu]ltima*) kill "$p" 2>/dev/null; melde "Ultima-Terminal PID $p beendet" ;;
    esac
done

# Serverliste des neuen Terminals sichtbar machen
for d in "$HOME/.wine/drive_c/Program Files/"*[Uu]ltima*/; do
    [ -d "$d" ] || continue
    N=$(find "$d" -maxdepth 2 -iname "*.srv" 2>/dev/null | wc -l)
    melde "srv-Dateien in $(basename "$d"): $N"
    find "$d" -maxdepth 2 -iname "*.srv" 2>/dev/null | head -5 | while IFS= read -r s; do
        melde "  $(basename "$s")"
    done
done
melde "Installation abgeschlossen"
echo "===== $(date -u) Ende ====="
'''.replace("URL_PLATZHALTER", URL)

os.makedirs(TT, exist_ok=True)
tmp = SKRIPT + ".neu"
with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
    f.write(INHALT)
os.chmod(tmp, 0o755)
os.replace(tmp, SKRIPT)
sag("Installationsskript geschrieben: " + SKRIPT)

try:
    subprocess.Popen(["setsid", "bash", SKRIPT],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, cwd=TT)
    sag("Installation abgekoppelt gestartet, Dauer etwa 3 bis 10 Minuten")
    sag("Fortschritt: ultima_install.log, Ergebnis in status.txt als INSTALL120")
except Exception as e:
    sag("FEHLER beim Start: " + str(e))
    sys.exit(1)
