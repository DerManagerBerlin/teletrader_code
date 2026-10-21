#!/bin/bash
# TeleTrader -> GitHub Mirror. Alle 5 Minuten per cron.  # PATCH36
cd ~/ttpub || exit
cp ~/teletrader/teletrader_v2.py ~/teletrader/intelligent_interpreter_v2.py . 2>/dev/null
tail -300000 ~/teletrader/bot.log 2>/dev/null \
  | grep -v "getUpdates" \
  | tail -8000 \
  | sed -E 's#bot[0-9]{6,}:[A-Za-z0-9_-]{30,}#bot***#g' > recent.log
cp ~/teletrader/mfe.csv . 2>/dev/null
tail -600 ~/teletrader/channel_msgs.log > channel_msgs.log 2>/dev/null
git add -A -f recent.log mfe.csv channel_msgs.log 2>/dev/null
git add -A
git -c user.email=bot@local -c user.name=alex commit -q -m "auto $(date +%H:%M)" 2>/dev/null
if ! git push -q 2>>~/ttpub/push_err.log; then
  echo "$(date -u +%F_%T) push fehlgeschlagen" >> ~/ttpub/push_err.log
fi
