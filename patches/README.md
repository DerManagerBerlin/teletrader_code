# patches/

Automatische Patch-Zustellung an den TeleTrader-VPS.

`ttpull.sh` (auf dem VPS, per cron alle 5 Minuten) liest `manifest.txt`,
laedt jedes dort genannte `.py` aus diesem Verzeichnis und wendet es an:

1. `.autobak` von `teletrader_v2.py` anlegen
2. Patch ausfuehren
3. `py_compile` pruefen — bei Fehler zurueckrollen
4. Bot mit unveraenderter Kommandozeile und Umgebung neu starten
5. Ergebnis als `AUTOPATCH:`-Zeile ins `bot.log` schreiben

Jeder Name wird genau einmal angewendet (`~/teletrader/applied_patches.txt`).
Patch-Skripte muessen idempotent sein.

Abschalten: `touch ~/teletrader/NO_AUTOPATCH`
