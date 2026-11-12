#!/usr/bin/env python3
# patch_147_demosetup.py
# NO_RESTART - der laufende Bot wird nicht angefasst.
#
# Vorbereitung fuer das neue Demokonto bei Ultima Markets.
#   1. demo_setup.sh auf den Server schreiben. Das fragt die Zugangsdaten ab
#      und traegt sie selbst in die .env ein. Weder dieser Patch noch das
#      Skript enthalten Zugangsdaten, und das Skript gibt keine aus.
#   2. Das Demo-Terminal auf das Ultima-Terminal umstellen. Bisher zeigte
#      MT5_TERMINAL_PATH_DEMO auf PU Prime, dort gibt es keinen Ultima-Server.
#   3. Symbolnamen fuer das Demokonto auf die Ultima-Schreibweise setzen.
# DEMO_MODE bleibt vorerst auf false, umgeschaltet wird erst, wenn die
# Zugangsdaten drin sind.
import io, os, re, glob, stat, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
ENV = os.path.join(TT, ".env")
SKRIPT = os.path.join(TT, "demo_setup.sh")
PUB = os.path.join(HOME, "ttpub")
_z = []


def sag(t):
    t = str(t)
    print("PATCH147 " + t)
    _z.append(t)


def win_pfad(p):
    m = p.replace("\\", "/")
    k = m.find("/drive_c/")
    return "C:\\" + m[k + len("/drive_c/"):].replace("/", "\\") if k >= 0 else p


SH = r'''#!/bin/bash
# Traegt die Zugangsdaten des Demokontos in die .env ein.
# Zeigt nichts an, protokolliert nichts, schreibt mit 0600.
set -u
ENV="$HOME/teletrader/.env"
[ -f "$ENV" ] || { echo "FEHLER: .env nicht gefunden unter $ENV"; exit 1; }

echo "============================================="
echo " Demokonto eintragen (Ultima Markets)"
echo "============================================="
echo "Die Eingaben landen direkt in der .env."
echo "Das Passwort wird beim Tippen nicht angezeigt."
echo

read -r -p "Kontonummer: " LOGIN
case "$LOGIN" in
    ''|*[!0-9]*) echo "FEHLER: Kontonummer muss eine Zahl sein."; exit 1 ;;
esac
read -r -s -p "Passwort   : " PASS; echo
[ -n "$PASS" ] || { echo "FEHLER: Passwort ist leer."; exit 1; }
read -r -p "Server [UltimaMarkets-Demo]: " SERVER
SERVER="${SERVER:-UltimaMarkets-Demo}"

TMP=$(mktemp) || exit 1
chmod 600 "$TMP"
cp -p "$ENV" "$ENV.bak_demo"
chmod 600 "$ENV.bak_demo" 2>/dev/null

# Alle drei Schluessel entfernen, danach frisch anhaengen.
grep -v -E '^[[:space:]]*(export[[:space:]]+)?DEMO_MT5_(LOGIN|PASSWORD|SERVER)[[:space:]]*=' \
    "$ENV" > "$TMP"
{
    echo ""
    echo "# Demokonto, gesetzt am $(date -u '+%Y-%m-%d %H:%M UTC')"
    echo "DEMO_MT5_LOGIN=$LOGIN"
    echo "DEMO_MT5_PASSWORD=$PASS"
    echo "DEMO_MT5_SERVER=$SERVER"
} >> "$TMP"

ALT=$(grep -c '=' "$ENV"); NEU=$(grep -c '=' "$TMP")
if [ "$NEU" -lt "$ALT" ]; then
    echo "FEHLER: Es waeren Zeilen verloren gegangen ($ALT -> $NEU). Nichts geaendert."
    rm -f "$TMP"; exit 1
fi
mv "$TMP" "$ENV"
chmod 600 "$ENV"
unset PASS

echo
echo "Eingetragen: Konto ***${LOGIN: -3}, Server $SERVER."
echo "Das Passwort steht in der .env und wurde nirgends angezeigt."
echo "Sicherung der alten Datei: $ENV.bak_demo"
echo
echo "$(date -u '+%Y-%m-%d %H:%M:%S') DEMOSETUP Konto ***${LOGIN: -3} Server $SERVER eingetragen" \
    >> "$HOME/ttpub/status.txt"
echo "Fertig. Sag Claude im Chat Bescheid, er schaltet dann um."
'''

os.makedirs(TT, exist_ok=True)
tmp = SKRIPT + ".neu"
with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
    f.write(SH)
os.chmod(tmp, 0o755)
os.replace(tmp, SKRIPT)
sag("demo_setup.sh geschrieben nach " + SKRIPT)

# --- Demo-Terminal auf Ultima, Symbole auf die Ultima-Schreibweise ---
_k = [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "Program Files", "*", "terminal64.exe"))
    if "ultima" in p.lower()]
if not _k:
    sag("WARNUNG: kein Ultima-Terminal gefunden, Pfad nicht gesetzt")
    SOLL = [("DEMO_GOLD_SYMBOL", "XAUUSD"), ("DEMO_FX_SUFFIX", "")]
else:
    SOLL = [("MT5_TERMINAL_PATH_DEMO", win_pfad(_k[0])),
            ("DEMO_GOLD_SYMBOL", "XAUUSD"), ("DEMO_FX_SUFFIX", "")]
    sag("Demo-Terminal: " + os.path.basename(os.path.dirname(_k[0])))

alt = io.open(ENV, encoding="utf-8", errors="surrogateescape").read()
zeilen = alt.split("\n")


def key(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (key(z) for z in zeilen) if k)
fehlt = []
for k, v in SOLL:
    hit = False
    for i, z in enumerate(zeilen):
        if key(z) == k:
            zeilen[i] = k + "=" + v
            hit = True
    if not hit:
        fehlt.append((k, v))
if fehlt:
    if zeilen and zeilen[-1].strip() != "":
        zeilen.append("")
    zeilen.append("# PATCH147 Demokonto Ultima")
    for k, v in fehlt:
        zeilen.append(k + "=" + v)
neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nicht geschrieben")
else:
    fd = os.open(ENV + ".bak147", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(alt)
    fd = os.open(ENV + ".p147", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(neu)
    try:
        os.chmod(ENV + ".p147", stat.S_IMODE(os.stat(ENV).st_mode))
    except Exception:
        pass
    os.replace(ENV + ".p147", ENV)
    sag("env gesetzt: " + ", ".join(k for k, _ in SOLL))
sag("DEMO_MODE bleibt vorerst unveraendert")
sag("fertig")
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("DEMO147 " + x + "\n")
except Exception:
    pass
