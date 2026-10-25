#!/usr/bin/env python3
# Patch 55 - legt ein Abfrage-Skript fuer die Live-Zugangsdaten an.
#   Aendert NICHTS am Handel und schaltet NICHT auf live.
#
#   Die Zugangsdaten koennen nicht ueber den Patch-Kanal laufen, weil jeder
#   Patch im oeffentlichen Repo landet. Statt nano gibt es jetzt ein
#   Skript, das die drei Werte abfragt und selbst eintraegt:
#       bash ~/teletrader/live_setup.sh
#   Eigenschaften:
#     - Das Passwort wird mit "read -s" eingelesen, erscheint also nicht
#       auf dem Bildschirm und nicht in der Shell-Historie.
#     - Die Werte gehen per Umgebungsvariable an den Schreibvorgang, nicht
#       als Argument. Damit stehen sie auch nicht in "ps aux".
#     - .env wird ueber eine temporaere Datei mit umask 077 ersetzt,
#       vorher eine Sicherung .env.bak_live.
#     - Vorhandene LIVE_-Zeilen werden ersetzt, nicht verdoppelt.
#     - Am Ende eine Zusammenfassung OHNE Passwort, nur Laenge.
#     - DEMO_MODE bleibt unangetastet.
import os, stat

SKRIPT = "live_setup.sh"
INHALT = r'''#!/usr/bin/env bash
# Von Patch 55 angelegt. Fragt die Live-Zugangsdaten ab und traegt sie in
# .env ein. Schaltet NICHT auf live um, das passiert separat.
set -u
cd "$(dirname "$0")" || exit 1
if [ ! -f .env ]; then echo "FEHLER: .env nicht gefunden"; exit 1; fi

echo "Live-Zugangsdaten eintragen. Abbruch mit Strg-C."
echo

read -r -p "LIVE_MT5_LOGIN  (Kontonummer): " TT_LOGIN
case "$TT_LOGIN" in
  ''|*[!0-9]*) echo "FEHLER: Login muss eine Zahl sein"; exit 1 ;;
esac

read -r -s -p "LIVE_MT5_PASSWORD           : " TT_PW
echo
if [ -z "$TT_PW" ]; then echo "FEHLER: Passwort ist leer"; exit 1; fi
read -r -s -p "Passwort zur Kontrolle      : " TT_PW2
echo
if [ "$TT_PW" != "$TT_PW2" ]; then echo "FEHLER: Passwoerter stimmen nicht ueberein"; exit 1; fi

read -r -p "LIVE_MT5_SERVER (z.B. Broker-Server): " TT_SRV
if [ -z "$TT_SRV" ]; then echo "FEHLER: Server ist leer"; exit 1; fi

read -r -p "LIVE_GOLD_SYMBOL [XAUUSD.s]: " TT_SYM
TT_SYM="${TT_SYM:-XAUUSD.s}"
TT_SUF=".${TT_SYM##*.}"
if [ "$TT_SYM" = "${TT_SYM%.*}" ]; then TT_SUF=""; fi

umask 077
TT_LOGIN="$TT_LOGIN" TT_PW="$TT_PW" TT_SRV="$TT_SRV" \
TT_SYM="$TT_SYM" TT_SUF="$TT_SUF" python3 - <<'PYEOF'
import os, shutil
soll = {
    "LIVE_MT5_LOGIN":    os.environ["TT_LOGIN"],
    "LIVE_MT5_PASSWORD": os.environ["TT_PW"],
    "LIVE_MT5_SERVER":   os.environ["TT_SRV"],
    "LIVE_GOLD_SYMBOL":  os.environ["TT_SYM"],
    "LIVE_FX_SUFFIX":    os.environ["TT_SUF"],
}
zeilen = open(".env", encoding="utf-8").read().splitlines()
neu, gesehen = [], set()
for z in zeilen:
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k = s.split("=", 1)[0].strip()
        if k in soll:
            neu.append(k + "=" + soll[k]); gesehen.add(k); continue
    neu.append(z)
for k, v in soll.items():
    if k not in gesehen:
        neu.append(k + "=" + v)
shutil.copyfile(".env", ".env.bak_live")
with open(".env.tmp_live", "w", encoding="utf-8") as f:
    f.write("\n".join(neu) + "\n")
os.chmod(".env.tmp_live", 0o600)
os.replace(".env.tmp_live", ".env")
print()
print("Eingetragen:")
print("  LIVE_MT5_LOGIN    = " + soll["LIVE_MT5_LOGIN"])
print("  LIVE_MT5_PASSWORD = (" + str(len(soll["LIVE_MT5_PASSWORD"])) + " Zeichen, nicht angezeigt)")
print("  LIVE_MT5_SERVER   = " + soll["LIVE_MT5_SERVER"])
print("  LIVE_GOLD_SYMBOL  = " + soll["LIVE_GOLD_SYMBOL"])
print("  LIVE_FX_SUFFIX    = " + soll["LIVE_FX_SUFFIX"])
print()
print("Sicherung: .env.bak_live")
print("DEMO_MODE wurde NICHT veraendert, der Bot laeuft weiter auf Demo.")
PYEOF
_rc=$?
unset TT_PW TT_PW2
if [ "$_rc" -ne 0 ]; then echo "FEHLER beim Schreiben der .env"; exit 1; fi
chmod 600 .env 2>/dev/null
echo
echo "Fertig. Das Umschalten auf live uebernimmt der naechste Patch."
'''

with open(SKRIPT, "w", encoding="utf-8") as f:
    f.write(INHALT)
os.chmod(SKRIPT, 0o700)
print("Patch 55 OK - " + os.path.abspath(SKRIPT) + " angelegt (" +
      stat.filemode(os.stat(SKRIPT).st_mode) + ")")
print("Aufruf:  bash ~/teletrader/live_setup.sh")
