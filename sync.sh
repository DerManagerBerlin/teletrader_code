#!/bin/bash
cd ~/ttpub || exit
cp ~/teletrader/teletrader_v2.py ~/teletrader/intelligent_interpreter_v2.py . 2>/dev/null
tail -8000 ~/teletrader/bot.log | sed -E 's#bot[0-9]{6,}:[A-Za-z0-9_-]{30,}#bot***#g' > recent.log
git add -A -f recent.log
git add -A
git -c user.email=bot@local -c user.name=alex commit -q -m "auto $(date +%H:%M)" 2>/dev/null
git push -q 2>/dev/null
