#!/usr/bin/env python3
# Patch 77 - Linux-Seite: Terminal-Neustart auf Zuruf.
#
#   Ausgangslage:
#     - Der einzige Weg, AutoTrading zu setzen, ist [Experts] Enabled=1 in
#       common.ini plus Neustart des Terminals. Tastendruecke erreichen
#       Wine nicht.
#     - MT5 schaltet AutoTrading bei jedem Kontowechsel selbst ab. Nach
#       jedem /live muss es also neu gesetzt werden.
#     - Der Bot laeuft unter Wine-Python und kann keine Linux-Befehle
#       absetzen (WinError 2). Er kann aber eine Datei schreiben.
#
#   Dieser Patch legt zwei Dinge an:
#     1) algo_set.py - Linux-Helfer, setzt [Experts] Enabled=1 atomar,
#        Kodierung und Zeilenenden bleiben erhalten (Logik aus Patch 70).
#     2) algo_enabler.sh - der laufende Watcher bekommt einen zweiten
#        Zweig: sieht er TERMINAL_RESTART_REQUEST, setzt er die
#        Konfiguration und startet teletrader.service neu.
#
#   Schleifenschutz: Die Flagge wird VOR dem Neustart geloescht, und
#   zwischen zwei Neustarts liegen mindestens 120 Sekunden.
#   Der bestehende Ctrl+E-Zweig bleibt unveraendert, er schadet nicht.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
SKRIPT = os.path.join(TT, "algo_enabler.sh")
HELFER = os.path.join(TT, "algo_set.py")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH neustart: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=30):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Fehler: " + str(e)

# ------------------------------------------------------------------ Helfer
ALGO_SET = r'''#!/usr/bin/env python3
"""Setzt [Experts] Enabled=1 in der MT5-common.ini. Linux-Seite.
Kodierung, Zeilenenden und Rechte bleiben wie vorgefunden. Der Inhalt
wird nie ausgegeben, die Datei enthaelt Kontodaten."""
import os, re, sys

INI = os.path.join(os.path.expanduser("~"), ".wine", "drive_c",
                   "Program Files", "PU Prime MT5 Terminal",
                   "Config", "common.ini")

def kodierung(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if b[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4:
        return "utf-16-le"
    return "utf-8"

def main():
    if not os.path.exists(INI):
        print("common.ini fehlt:", INI); return 1
    with open(INI, "rb") as f:
        roh = f.read()
    kod = kodierung(roh)
    text = roh.decode(kod, errors="strict")
    crlf = "\r\n" in text
    zeilen = text.split("\r\n") if crlf else text.split("\n")
    drin = False
    gesetzt = False
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("[") and s.endswith("]"):
            drin = (s.lower() == "[experts]")
            continue
        if drin and re.match(r"^\s*Enabled\s*=", z, re.I):
            if s.split("=", 1)[1].strip() == "1":
                print("stand bereits auf 1"); return 0
            zeilen[i] = "Enabled=1"; gesetzt = True
            break
    if not gesetzt:
        for i, z in enumerate(zeilen):
            if z.strip().lower() == "[experts]":
                zeilen.insert(i + 1, "Enabled=1"); gesetzt = True
                break
    if not gesetzt:
        print("kein [Experts] gefunden"); return 1
    neu = ("\r\n" if crlf else "\n").join(zeilen)
    st = os.stat(INI)
    tmp = INI + ".neu"
    with open(tmp, "wb") as f:
        f.write(neu.encode(kod)); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, INI)
    print("Enabled auf 1 gesetzt (" + kod + ")")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

try:
    with open(HELFER, "w", encoding="utf-8") as f:
        f.write(ALGO_SET)
    os.chmod(HELFER, 0o755)
    melde("algo_set.py geschrieben")
except Exception as e:
    melde("FEHLER algo_set.py: " + str(e)); raise SystemExit(1)

melde("Probelauf: " + sh("python3 '" + HELFER + "' 2>&1 | head -1"))

# ------------------------------------------------------------- Watcher neu
WATCHER = r'''#!/usr/bin/env bash
# TeleTrader AutoTrading Enabler.
#   Zweig 1 (alt, Patch 64): Ctrl+E an das MT5-Fenster. Erreicht Wine in
#     dieser Umgebung nicht, bleibt aber drin, weil es nicht schadet.
#   Zweig 2 (Patch 77): TERMINAL_RESTART_REQUEST -> [Experts] Enabled=1
#     setzen und teletrader.service neu starten. Das ist der Weg, der
#     nachweislich wirkt. Noetig nach jedem Kontowechsel, weil MT5
#     AutoTrading dabei selbst abschaltet.
set -u
export DISPLAY="${MT5_DISPLAY:-:99}"
[ -f "$HOME/.Xauthority" ] && export XAUTHORITY="$HOME/.Xauthority"
MATCH="${MT5_WINDOW_MATCH:-PUPrime}"
TT="$HOME/teletrader"
FLAG="$TT/ENABLE_ALGO_REQUEST"
REQ="$TT/TERMINAL_RESTART_REQUEST"
STAMP="$TT/.letzter_neustart"
WLOG="$TT/algo_set.log"
logger -t algo_enabler "Watcher gestartet (DISPLAY=$DISPLAY MATCH=$MATCH, Patch 77)"
while true; do
  # --- Zweig 2: Neustart auf Zuruf ---------------------------------------
  if [ -f "$REQ" ]; then
    rm -f "$REQ"                       # zuerst weg, sonst Endlosschleife
    JETZT=$(date +%s)
    LETZT=$(cat "$STAMP" 2>/dev/null || echo 0)
    case "$LETZT" in ''|*[!0-9]*) LETZT=0 ;; esac
    if [ $((JETZT - LETZT)) -lt 120 ]; then
      logger -t algo_enabler "Neustart abgelehnt, letzter ist $((JETZT - LETZT))s her"
    else
      echo "$JETZT" > "$STAMP"
      {
        echo "=== $(date -u '+%Y-%m-%d %H:%M:%S') Neustart angefordert ==="
        python3 "$TT/algo_set.py" 2>&1
      } >> "$WLOG"
      logger -t algo_enabler "Konfiguration gesetzt, starte teletrader.service neu"
      if sudo -n systemctl restart teletrader.service >> "$WLOG" 2>&1; then
        logger -t algo_enabler "Neustart ok"
      else
        logger -t algo_enabler "Neustart FEHLGESCHLAGEN (sudo?)"
        echo "systemctl restart fehlgeschlagen" >> "$WLOG"
      fi
    fi
  fi
  # --- Zweig 1: alter Tastenweg ------------------------------------------
  if [ -f "$FLAG" ]; then
    for D in $(xdotool search --name "^Login$" 2>/dev/null); do
      xdotool windowclose "$D" 2>/dev/null
    done
    WID=$(xdotool search --name "$MATCH" 2>/dev/null | head -1)
    if [ -n "${WID:-}" ]; then
      if xdotool windowactivate --sync "$WID" 2>/dev/null \
         && xdotool windowfocus --sync "$WID" 2>/dev/null; then
        xdotool key --clearmodifiers ctrl+e
      else
        xdotool key --window "$WID" --clearmodifiers ctrl+e 2>/dev/null
      fi
    fi
    rm -f "$FLAG"
  fi
  sleep 1
done
'''

try:
    if os.path.exists(SKRIPT):
        import shutil as _sh
        _sh.copyfile(SKRIPT, SKRIPT + ".bak_77")
    with open(SKRIPT, "w", encoding="utf-8") as f:
        f.write(WATCHER)
    os.chmod(SKRIPT, 0o755)
    melde("algo_enabler.sh erweitert")
except Exception as e:
    melde("FEHLER Watcher: " + str(e)); raise SystemExit(1)

melde("Syntaxpruefung: " + (sh("bash -n '" + SKRIPT + "' && echo ok") or "?"))

# Watcher neu starten, damit die neue Fassung laeuft. Restart=always holt ihn.
_pid = sh("systemctl show -p MainPID --value algoenabler.service 2>/dev/null").strip()
if _pid.isdigit() and int(_pid) > 1:
    melde("Watcher PID " + _pid + ": " + sh("kill " + _pid + " && echo beendet"))
time.sleep(8)
melde("Dienst: " + sh("systemctl is-active algoenabler.service 2>&1 | head -1"))
melde("Journal: " + sh("journalctl -t algo_enabler -n 2 --no-pager 2>/dev/null | tail -2"))
print("Patch 77 fertig")
