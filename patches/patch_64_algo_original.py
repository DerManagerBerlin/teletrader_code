#!/usr/bin/env python3
# Patch 64 - stellt die funktionierende Fassung von algo_enabler.sh wieder her.
#
#   Im August lief die Kette nachweislich. Die damals erfolgreiche
#   Reihenfolge war:
#       export XAUTHORITY="$HOME/.Xauthority"
#       xdotool windowactivate --sync "$WID"
#       xdotool windowfocus    --sync "$WID"
#       xdotool key --clearmodifiers ctrl+e
#   Beide Aufrufe mit --sync, und XAUTHORITY gesetzt.
#
#   In Patch 62 habe ich das Skript neu geschrieben und dabei beides
#   weggelassen: --sync fehlte, XAUTHORITY fehlte. Danach kam die Taste
#   nicht mehr an. Das war keine neue Ursache, sondern meine Regression.
#   Patch 63 (Window-Manager) war auf derselben falschen Spur und bleibt
#   wirkungslos, schadet aber nicht.
#
#   Diese Fassung ist die alte Logik plus eine einzige Ergaenzung: wenn
#   --sync nicht durchkommt, folgt ein Versuch ohne Fokus direkt an die
#   Fenster-ID. Weiterhin genau EIN Tastendruck je Anforderung, weil
#   Ctrl+E umschaltet.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
SKRIPT = os.path.join(TT, "algo_enabler.sh")
FLAG = os.path.join(TT, "ENABLE_ALGO_REQUEST")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH algo3: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=25):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

NEU = r'''#!/usr/bin/env bash
# TeleTrader AutoTrading Enabler. Fassung von August wiederhergestellt
# (Patch 64). Entscheidend: XAUTHORITY und --sync bei windowactivate und
# windowfocus. Genau ein Tastendruck je Anforderung, Ctrl+E schaltet um.
set -u
export DISPLAY="${MT5_DISPLAY:-:99}"
[ -f "$HOME/.Xauthority" ] && export XAUTHORITY="$HOME/.Xauthority"
MATCH="${MT5_WINDOW_MATCH:-PUPrime}"
FLAG="$HOME/teletrader/ENABLE_ALGO_REQUEST"
logger -t algo_enabler "Watcher gestartet (DISPLAY=$DISPLAY MATCH=$MATCH, Patch 64)"
while true; do
  if [ -f "$FLAG" ]; then
    for D in $(xdotool search --name "^Login$" 2>/dev/null); do
      xdotool windowclose "$D" 2>/dev/null
    done
    WID=$(xdotool search --name "$MATCH" 2>/dev/null | head -1)
    if [ -n "${WID:-}" ]; then
      if xdotool windowactivate --sync "$WID" 2>/dev/null \
         && xdotool windowfocus --sync "$WID" 2>/dev/null; then
        xdotool key --clearmodifiers ctrl+e
        logger -t algo_enabler "Ctrl+E an WID $WID gesendet (activate+focus --sync)"
      else
        xdotool key --window "$WID" --clearmodifiers ctrl+e 2>/dev/null
        logger -t algo_enabler "Ctrl+E an WID $WID gesendet (Rueckfall: direkt an WID)"
      fi
    else
      logger -t algo_enabler "kein MT5-Fenster (Match=$MATCH)"
    fi
    rm -f "$FLAG"
  fi
  sleep 1
done
'''

try:
    if os.path.exists(SKRIPT):
        import shutil as _sh
        _sh.copyfile(SKRIPT, SKRIPT + ".bak_64")
    with open(SKRIPT, "w", encoding="utf-8") as f:
        f.write(NEU)
    os.chmod(SKRIPT, 0o755)
    melde("algo_enabler.sh wiederhergestellt")
except Exception as e:
    melde("FEHLER: " + str(e)); raise SystemExit(1)

melde("XAUTHORITY vorhanden: " + sh("ls -la $HOME/.Xauthority 2>&1 | head -1"))

_pid = sh("systemctl show -p MainPID --value algoenabler.service 2>/dev/null").strip()
if _pid.isdigit() and int(_pid) > 1:
    melde("Watcher PID " + _pid + " beendet: " +
          sh("kill " + _pid + " && echo ok || echo Fehler"))
time.sleep(8)
melde("Dienst: " + sh("systemctl is-active algoenabler.service 2>&1 | head -1"))

try:
    with open(FLAG, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat() + "\n")
    melde("Anforderung gestellt")
except Exception as e:
    melde("Flag-Fehler: " + str(e))

time.sleep(8)
melde("Flag " + ("noch da" if os.path.exists(FLAG) else "abgeraeumt"))
melde("Journal: " + sh("journalctl -t algo_enabler -n 3 --no-pager 2>/dev/null "
                       "| tail -3").replace("\n", " | ")[:300])
print("Patch 64 fertig")
