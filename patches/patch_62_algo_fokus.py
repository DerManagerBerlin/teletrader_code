#!/usr/bin/env python3
# Patch 62 - repariert algo_enabler.sh.
#
#   Befund aus Patch 61:
#     Fenster99: 10485761  700190957 - PUPrime-Demo: Demo Account - Hedge
#     Aktiv99:   windowmanager claims not to support _NET_ACTIVE_WINDOW
#     Journal:   seit 22:27 im Minutentakt "Ctrl+E an WID 10485761 gesendet"
#   Das Fenster wird also gefunden, die Taste aber nie zugestellt: auf :99
#   laeuft kein Window-Manager, deshalb schlagen windowfocus --sync und
#   windowactivate fehl und die Taste geht an den Fokus, den es nicht gibt.
#
#   Neu: algo_enabler.sh schickt die Taste DIREKT an die Fenster-ID
#   (xdotool key --window), was ohne Window-Manager funktioniert. Weil das
#   unter Wine nicht garantiert ankommt, wechselt das Skript bei jeder
#   Anforderung die Methode durch:
#       0  key --window WID          (ohne Fokus, Standard ohne WM)
#       1  windowfocus, dann key     (XSetInputFocus, braucht keinen WM)
#       2  windowactivate, dann key  (alt, braucht einen WM)
#   Pro Anforderung genau EIN Tastendruck. Wichtig, weil Ctrl+E umschaltet:
#   zweimal hintereinander waere wieder aus. Der Bot fragt nur an, solange
#   trade_allowed false ist, und hoert nach dem ersten Erfolg auf.
#
#   algoenabler.service kann ich nicht per sudo neu starten, dafuer fehlt
#   das Recht. Die Unit hat aber Restart=always, deshalb reicht es, den
#   laufenden Prozess zu beenden.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
SKRIPT = os.path.join(os.path.expanduser("~"), "teletrader", "algo_enabler.sh")
if not os.path.exists(SKRIPT):
    SKRIPT = "algo_enabler.sh"
FLAG = "ENABLE_ALGO_REQUEST"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH algo2: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=20):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

NEU = r'''#!/usr/bin/env bash
# TeleTrader AutoTrading Enabler. Von Patch 62 neu geschrieben.
# Auf :99 laeuft kein Window-Manager, deshalb wird die Taste direkt an die
# Fenster-ID geschickt. Methoden wechseln sich ab, genau ein Tastendruck
# je Anforderung (Ctrl+E schaltet um).
set -u
export DISPLAY="${MT5_DISPLAY:-:99}"
MATCH="${MT5_WINDOW_MATCH:-PUPrime}"
TT="$HOME/teletrader"
FLAG="$TT/ENABLE_ALGO_REQUEST"
CNT="$TT/.algo_methode"
logger -t algo_enabler "Watcher gestartet (DISPLAY=$DISPLAY MATCH=$MATCH, Patch 62)"
while true; do
  if [ -e "$FLAG" ]; then
    for D in $(xdotool search --name "^Login$" 2>/dev/null); do
      xdotool windowclose "$D" 2>/dev/null
    done
    WID=$(xdotool search --name "$MATCH" 2>/dev/null | head -1)
    if [ -n "${WID:-}" ]; then
      M=$(cat "$CNT" 2>/dev/null || echo 0)
      case "$M" in
        0)
          xdotool key --window "$WID" --clearmodifiers ctrl+e 2>/dev/null
          MN="direkt an WID"
          ;;
        1)
          xdotool windowfocus "$WID" 2>/dev/null
          sleep 0.3
          xdotool key --clearmodifiers ctrl+e 2>/dev/null
          MN="nach windowfocus"
          ;;
        *)
          xdotool windowactivate "$WID" 2>/dev/null
          sleep 0.3
          xdotool key --clearmodifiers ctrl+e 2>/dev/null
          MN="nach windowactivate"
          ;;
      esac
      echo $(( (M + 1) % 3 )) > "$CNT"
      logger -t algo_enabler "Ctrl+E an WID $WID gesendet (Methode $M, $MN)"
    else
      logger -t algo_enabler "Kein Fenster zu MATCH=$MATCH gefunden"
    fi
    rm -f "$FLAG"
  fi
  sleep 1
done
'''

try:
    if os.path.exists(SKRIPT):
        import shutil as _sh
        _sh.copyfile(SKRIPT, SKRIPT + ".bak_62")
    with open(SKRIPT, "w", encoding="utf-8") as f:
        f.write(NEU)
    os.chmod(SKRIPT, 0o755)
    melde("algo_enabler.sh neu geschrieben: " + SKRIPT)
except Exception as e:
    melde("FEHLER beim Schreiben von algo_enabler.sh: " + str(e)); raise SystemExit(1)

# Zaehler auf Methode 0 setzen
try:
    with open(os.path.join(os.path.dirname(SKRIPT) or ".", ".algo_methode"),
              "w", encoding="utf-8") as f:
        f.write("0\n")
except Exception:
    pass

# Watcher beenden, Restart=always startet ihn mit dem neuen Skript neu.
# NICHT pkill -f: das Muster steht in der eigenen Kommandozeile, die Shell
# wuerde sich selbst erschiessen. Die PID kommt von systemd.
_pid = sh("systemctl show -p MainPID --value algoenabler.service 2>/dev/null").strip()
if _pid.isdigit() and int(_pid) > 1:
    melde("beende alten Watcher PID " + _pid + ": " +
          sh("kill " + _pid + " && echo beendet || echo Fehler"))
else:
    melde("keine MainPID von systemd (" + repr(_pid) + "), Watcher nicht beendet")
time.sleep(8)
melde("Dienst: " + sh("systemctl is-active algoenabler.service 2>&1 | head -1"))
melde("Journal: " + sh("journalctl -u algoenabler.service -n 3 --no-pager 2>/dev/null "
                       "| tail -3").replace("\n", " | ")[:300])

# Anforderung stellen
try:
    with open(FLAG, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat() + "\n")
    melde("Anforderung gestellt")
except Exception as e:
    melde("Flag-Fehler: " + str(e))

time.sleep(6)
melde("Flag " + ("noch da (Watcher reagiert nicht)" if os.path.exists(FLAG)
                 else "abgeraeumt"))
melde("Journal: " + sh("journalctl -u algoenabler.service -n 2 --no-pager 2>/dev/null "
                       "| tail -2").replace("\n", " | ")[:300])
print("Patch 62 fertig")
