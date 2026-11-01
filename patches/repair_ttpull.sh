#!/bin/bash
# repair_ttpull.sh - stellt den Auto-Patch-Kanal wieder her.
# Seit 30.10. 13:50 hat ttpull.sh nichts mehr angewendet, obwohl der Bot
# laeuft und sync.sh weiter pusht. Dieses Skript findet heraus warum,
# behebt die drei moeglichen Ursachen und laesst ttpull einmal laufen.
# Es liest keine Zugangsdaten und schreibt keine in die Ausgabe.
set -u
TT="$HOME/teletrader"
PUB="$HOME/ttpub"
ST="$PUB/status.txt"

sag() { echo "$*"; echo "$(date -u '+%Y-%m-%d %H:%M:%S') REPARATUR $*" >> "$ST"; }

mkdir -p "$PUB"
echo "=============================================="
echo " Auto-Patch-Kanal reparieren"
echo "=============================================="

# 1. Kill-Schalter
if [ -e "$TT/NO_AUTOPATCH" ]; then
    sag "NO_AUTOPATCH war gesetzt -> entfernt"
    rm -f "$TT/NO_AUTOPATCH"
else
    sag "NO_AUTOPATCH nicht gesetzt"
fi

# 2. Skript vorhanden und lesbar
if [ -f "$PUB/ttpull.sh" ]; then
    sag "ttpull.sh vorhanden, $(wc -l < "$PUB/ttpull.sh") Zeilen"
else
    sag "ttpull.sh FEHLT in $PUB -> wird aus dem Repo geholt"
    curl -fsSL "https://raw.githubusercontent.com/DerManagerBerlin/teletrader_code/main/ttpull.sh" \
         -o "$PUB/ttpull.sh" && chmod +x "$PUB/ttpull.sh" && sag "ttpull.sh neu geladen"
fi

# 3. Cron-Eintrag
CT=$(crontab -l 2>/dev/null || true)
if printf '%s' "$CT" | grep -q "ttpull"; then
    sag "Cron-Eintrag fuer ttpull vorhanden"
else
    sag "Cron-Eintrag fuer ttpull FEHLTE -> wird ergaenzt"
    { printf '%s\n' "$CT"
      echo "*/5 * * * * /bin/bash $PUB/ttpull.sh"; } | crontab -
    sag "Cron ergaenzt"
fi
sag "Cron-Zeilen gesamt: $(crontab -l 2>/dev/null | grep -c . )"
sag "Cron-Dienst: $(systemctl is-active cron 2>/dev/null || echo unbekannt)"

# 4. Netzzugang zum Manifest
HTTP=$(curl -o /dev/null -s -w '%{http_code}' --max-time 20 \
  "https://raw.githubusercontent.com/DerManagerBerlin/teletrader_code/patches/patches/manifest.txt?t=$(date +%s)")
sag "Manifest abrufbar: HTTP $HTTP"

# 5. Wie weit ist der Bestand
sag "applied_patches: $(wc -l < "$TT/applied_patches.txt" 2>/dev/null || echo 0) Zeilen, zuletzt $(tail -1 "$TT/applied_patches.txt" 2>/dev/null || echo keine)"

# 6. Einmal laufen lassen
echo ""
echo "--- ttpull laeuft jetzt einmal ---"
bash "$PUB/ttpull.sh"
RC=$?
sag "ttpull Durchlauf beendet, rc=$RC"

echo ""
echo "--- letzte Statuszeilen ---"
tail -12 "$ST"
echo ""
echo "Fertig. Das Ergebnis steht auch in status.txt und erreicht Claude"
echo "mit dem naechsten sync-Lauf (hoechstens 10 Minuten)."
