#!/usr/bin/env python3
# Patch 36 - idempotent. Aendert NICHTS am Bot, nur den Mirror-Cron.
#   1) recent.log: Telegram-Polling rausfiltern. 96% des Logs waren
#      getUpdates-Zeilen, dadurch deckten 8000 Zeilen nur ~14 Stunden ab.
#   2) mfe.csv und channel_msgs.log mitspiegeln.
#   3) Push-Fehler nicht mehr stillschweigend verschlucken.
import os, shutil, subprocess

SH = os.path.expanduser("~/ttpub/sync.sh")
MARKER = "# PATCH36"
NEU = '''#!/bin/bash
# TeleTrader -> GitHub Mirror. Alle 5 Minuten per cron.  ''' + MARKER + '''
cd ~/ttpub || exit
cp ~/teletrader/teletrader_v2.py ~/teletrader/intelligent_interpreter_v2.py . 2>/dev/null
tail -300000 ~/teletrader/bot.log 2>/dev/null \\
  | grep -v "getUpdates" \\
  | tail -8000 \\
  | sed -E 's#bot[0-9]{6,}:[A-Za-z0-9_-]{30,}#bot***#g' > recent.log
cp ~/teletrader/mfe.csv . 2>/dev/null
tail -600 ~/teletrader/channel_msgs.log > channel_msgs.log 2>/dev/null
git add -A -f recent.log mfe.csv channel_msgs.log 2>/dev/null
git add -A
git -c user.email=bot@local -c user.name=alex commit -q -m "auto $(date +%H:%M)" 2>/dev/null
if ! git push -q 2>>~/ttpub/push_err.log; then
  echo "$(date -u +%F_%T) push fehlgeschlagen" >> ~/ttpub/push_err.log
fi
'''

if not os.path.exists(SH):
    print("FEHLER: " + SH + " nicht gefunden"); raise SystemExit(1)
if MARKER in open(SH, encoding="utf-8", errors="ignore").read():
    print("schon angewendet"); raise SystemExit(0)

shutil.copyfile(SH, SH + ".bak_36")
open(SH, "w", encoding="utf-8").write(NEU)
os.chmod(SH, 0o755)
r = subprocess.run(["bash", "-n", SH], capture_output=True, text=True)
if r.returncode != 0:
    shutil.copyfile(SH + ".bak_36", SH)
    print("FEHLER Syntax, zurueckgerollt: " + r.stderr.strip()); raise SystemExit(1)
print("Patch 36 OK - sync.sh filtert Polling und spiegelt mfe.csv")
