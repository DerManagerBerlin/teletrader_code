#!/usr/bin/env python3
# NO_RESTART
# Patch 101 - ttpull.sh verbessern (Pfad korrigiert: ~/ttpub/). Drei Punkte, die heute Schaden angerichtet haben.
#
#   1) Marker "# NO_RESTART": Ein Patch, der das in den ersten 40 Zeilen
#      traegt, loest keinen Dienstneustart aus. Bisher startete JEDER
#      Patch den Bot neu, auch rein lesende. Das hat heute AutoTrading
#      abgeschaltet, zweimal den VNC-Server gekillt und Handelsluecken
#      erzeugt.
#   2) Meldungen zusaetzlich nach ttpub/status.txt. Das bot.log war
#      stundenlang unbrauchbar und hat mich falsche Zustaende lesen
#      lassen. Eine zweite, kleine Datei behebt das dauerhaft.
#   3) Groessenbremse: Wird bot.log groesser als 80 MB, werden die
#      letzten 20000 Zeilen an Ort und Stelle behalten. Nicht per mv,
#      denn genau so ist die Datei heute kaputtgegangen.
#
#   ttpull.sh ist die Lebensader. Deshalb: Sicherung, gezielte
#   Ersetzungen statt Neuschreiben, Syntaxpruefung, und bei jedem Zweifel
#   wird zurueckgerollt.
import os, re, shutil, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

ZIEL = None
for k in (os.path.join(HOME, "ttpub", "ttpull.sh"),
          os.path.join(HOME, "ttpull.sh"),
          os.path.join(TT, "ttpull.sh")):
    if os.path.exists(k):
        ZIEL = k
        break

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH101 " + t
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
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Fehler: " + str(e)[:80]

if not ZIEL:
    melde("ABBRUCH: ttpull.sh nicht gefunden"); raise SystemExit(0)
melde("Datei: " + ZIEL)

with open(ZIEL, "r", encoding="utf-8") as f:
    src = f.read()

if "NO_RESTART" in src:
    melde("schon gepatcht, nichts zu tun"); raise SystemExit(0)

aenderungen = []

# --- 1) say/err auch nach status.txt --------------------------------------
A1 = ('say() { echo "$(ts) [INFO] AUTOPATCH: $*"  >> "$LOG"; }\n'
      'err() { echo "$(ts) [ERROR] AUTOPATCH: $*" >> "$LOG"; }\n')
N1 = ('STATUS="$HOME/ttpub/status.txt"\n'
      '# Doppelt melden: bot.log wie bisher, zusaetzlich status.txt. Das\n'
      '# bot.log kann beschaedigt sein, status.txt ist klein und ehrlich.\n'
      'say() { echo "$(ts) [INFO] AUTOPATCH: $*"  >> "$LOG";\n'
      '        mkdir -p "$(dirname "$STATUS")" 2>/dev/null;\n'
      '        echo "$(date -u \'+%Y-%m-%d %H:%M:%S\') TTPULL $*" >> "$STATUS"; }\n'
      'err() { echo "$(ts) [ERROR] AUTOPATCH: $*" >> "$LOG";\n'
      '        mkdir -p "$(dirname "$STATUS")" 2>/dev/null;\n'
      '        echo "$(date -u \'+%Y-%m-%d %H:%M:%S\') TTPULL FEHLER: $*" >> "$STATUS"; }\n')
if A1 in src:
    src = src.replace(A1, N1, 1); aenderungen.append("status.txt-Meldungen")

# --- 2) Groessenbremse fuers Log ------------------------------------------
A2 = '[ -e "$TT/NO_AUTOPATCH" ] && exit 0\n'
N2 = ('# Groessenbremse: in place kuerzen, NICHT per mv. Ein mv waehrend\n'
      '# offener Dateihandles hat bot.log heute zerloechert.\n'
      'if [ -f "$LOG" ]; then\n'
      '    _sz=$(stat -c %s "$LOG" 2>/dev/null || echo 0)\n'
      '    if [ "$_sz" -gt 83886080 ]; then\n'
      '        tail -n 20000 "$LOG" > "$LOG.kurz" 2>/dev/null && \\\n'
      '          cat "$LOG.kurz" > "$LOG" && rm -f "$LOG.kurz"\n'
      '    fi\n'
      'fi\n'
      '[ -e "$TT/NO_AUTOPATCH" ] && exit 0\n')
if A2 in src:
    src = src.replace(A2, N2, 1); aenderungen.append("Groessenbremse")

# --- 3) NO_RESTART-Marker --------------------------------------------------
A3 = ('        say "$NAME angewendet - $OUT"\n'
      '        echo "$NAME" >> "$STATE"; APPLIED=1\n')
N3 = ('        say "$NAME angewendet - $OUT"\n'
      '        echo "$NAME" >> "$STATE"\n'
      '        # Patches mit "# NO_RESTART" in den ersten 40 Zeilen fassen\n'
      '        # den laufenden Bot nicht an. Lesende Patches brauchen keinen\n'
      '        # Neustart, und jeder Neustart kostet Handelszeit und schaltet\n'
      '        # AutoTrading ab.\n'
      '        if head -40 "$TMP" 2>/dev/null | grep -q "NO_RESTART"; then\n'
      '            say "$NAME ohne Neustart (NO_RESTART)"\n'
      '        else\n'
      '            APPLIED=1\n'
      '        fi\n')
if A3 in src:
    src = src.replace(A3, N3, 1); aenderungen.append("NO_RESTART")

if not aenderungen:
    melde("kein Anker gefunden, Datei unveraendert"); raise SystemExit(0)

shutil.copyfile(ZIEL, ZIEL + ".bak_101")
TMP = ZIEL + ".neu101"
with open(TMP, "w", encoding="utf-8") as f:
    f.write(src); f.flush(); os.fsync(f.fileno())
os.chmod(TMP, 0o755)

pruef = sh("bash -n '" + TMP + "' && echo SYNTAXOK")
if "SYNTAXOK" not in pruef:
    melde("SYNTAXFEHLER, nichts geaendert: " + pruef)
    try: os.remove(TMP)
    except Exception: pass
    raise SystemExit(0)

os.replace(TMP, ZIEL)
melde("geaendert: " + ", ".join(aenderungen))
melde("Gegenprobe: " + sh("bash -n '" + ZIEL + "' && echo ok"))
melde("Sicherung liegt unter " + os.path.basename(ZIEL) + ".bak_101")
# Zum Schluss: hat der Login von Hand funktioniert? Und VNC neu starten.
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
melde("Terminal-Log Anmeldungen: " + sh(
    "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
    "[ -n \"$L\" ] && grep -iE 'authorized|ultima|login' \"$L\" | tail -4 "
    "| sed -E 's/[0-9]{6,}/***/g' || echo '(kein Log)'", t=60))
HELFER = os.path.join(HOME, "vnc_login.sh")
if os.path.exists(HELFER):
    sh("setsid nohup '" + HELFER + "' >/dev/null 2>&1 < /dev/null & disown; echo ab", t=8)
    melde("VNC-Helfer gestartet, Fenster in rund 3 Minuten")
print("Patch 101 fertig")
