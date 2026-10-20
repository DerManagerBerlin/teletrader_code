#!/bin/bash
# ttpull.sh - holt neue Patch-Skripte aus dem GitHub-Repo und wendet sie an.
# Laeuft per cron alle 5 Minuten, direkt vor sync.sh.
# Abschalten jederzeit:  touch ~/teletrader/NO_AUTOPATCH
set -u

RAW="https://raw.githubusercontent.com/DerManagerBerlin/teletrader_code/patches"
TT="$HOME/teletrader"
BOT="$TT/teletrader_v2.py"
STATE="$TT/applied_patches.txt"
LOG="$TT/bot.log"
RESTART_CMD=""          # leer = Startweg automatisch aus /proc uebernehmen

ts()  { date -u '+%Y-%m-%d %H:%M:%S,000'; }
say() { echo "$(ts) [INFO] AUTOPATCH: $*"  >> "$LOG"; }
err() { echo "$(ts) [ERROR] AUTOPATCH: $*" >> "$LOG"; }

[ -e "$TT/NO_AUTOPATCH" ] && exit 0
[ -f "$BOT" ] || exit 0
touch "$STATE"

MAN=$(curl -fsS --max-time 20 "$RAW/patches/manifest.txt?t=$(date +%s)") || exit 0
[ -z "$MAN" ] && exit 0

APPLIED=0
while IFS= read -r LINE; do
    NAME=$(printf '%s' "$LINE" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    [ -z "$NAME" ] && continue
    case "$NAME" in \#*) continue ;; esac
    # nur schlichte Dateinamen, keine Pfade
    case "$NAME" in *.py) ;; *) continue ;; esac
    case "$NAME" in */*|.*) err "Name abgelehnt: $NAME"; continue ;; esac
    grep -qxF "$NAME" "$STATE" && continue

    TMP="$TT/.autopatch_$NAME"
    if ! curl -fsS --max-time 30 "$RAW/patches/$NAME?t=$(date +%s)" -o "$TMP"; then
        err "Download fehlgeschlagen: $NAME"
        rm -f "$TMP"; continue
    fi
    cp -f "$BOT" "$BOT.autobak"
    OUT=$(cd "$TT" && python3 "$TMP" 2>&1); RC=$?
    OUT=$(printf '%s' "$OUT" | tr '\n' ' ' | cut -c1-220)
    if [ $RC -eq 0 ] && python3 -c "import py_compile; py_compile.compile('$BOT', doraise=True)" 2>/dev/null; then
        say "$NAME angewendet - $OUT"
        echo "$NAME" >> "$STATE"; APPLIED=1
    else
        cp -f "$BOT.autobak" "$BOT"
        err "$NAME FEHLGESCHLAGEN (rc=$RC), zurueckgerollt - $OUT"
        echo "$NAME" >> "$STATE"       # nicht alle 5 Minuten erneut versuchen
    fi
    rm -f "$TMP"
done <<< "$MAN"

[ "$APPLIED" -eq 0 ] && exit 0

# ---------------------------------------------------------------- Neustart
# Den Bot streng identifizieren: die Kommandozeile muss einen Python-
# Interpreter UND das Skript enthalten. Ein blosses "pgrep -f teletrader_v2.py"
# trifft auch das cp aus sync.sh - und wuerde den falschen Prozess killen.
find_bot_pid() {
    local p c
    for p in $(pgrep -f "teletrader_v2\.py" 2>/dev/null); do
        [ "$p" = "$$" ] && continue
        [ "$p" = "${PPID:-0}" ] && continue
        c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
        case "$c" in *python*teletrader_v2.py*) printf '%s' "$p"; return 0 ;; esac
    done
    return 1
}
PID=$(find_bot_pid) || PID=""
UNIT=""
[ -n "$PID" ] && UNIT=$(grep -oE '[A-Za-z0-9@._-]+\.service' "/proc/$PID/cgroup" 2>/dev/null | head -1)

if [ -n "$RESTART_CMD" ]; then
    say "Neustart ueber RESTART_CMD"
    bash -c "$RESTART_CMD" >>"$LOG" 2>&1
elif [ -n "$UNIT" ]; then
    say "Neustart ueber systemd: $UNIT"
    # --no-ask-password: unter cron gibt es kein TTY, ein polkit-Passwortdialog
    # wuerde den Lauf blockieren. sudo -n zuerst, weil eine System-Unit Root
    # braucht und der unprivilegierte Versuch sonst nur den Dialog ausloest.
    if sudo -n systemctl restart "$UNIT" >>"$LOG" 2>&1; then
        :
    elif systemctl --no-ask-password --user restart "$UNIT" >>"$LOG" 2>&1; then
        :
    elif systemctl --no-ask-password restart "$UNIT" >>"$LOG" 2>&1; then
        :
    else
        err "Neustart von $UNIT nicht moeglich - Code ist gepatcht, laeuft aber"
        err "noch nicht. Einmalig erlauben: echo '$(whoami) ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart $UNIT' | sudo tee /etc/sudoers.d/teletrader-restart"
    fi
    sleep 5
    if systemctl is-active --quiet "$UNIT"; then say "$UNIT laeuft"
    else err "$UNIT ist NICHT aktiv - von Hand pruefen"; fi
elif [ -n "$PID" ]; then
    CMD=$(tr '\0' ' ' < "/proc/$PID/cmdline")
    CWD=$(readlink "/proc/$PID/cwd")
    say "Neustart ueber Kommandozeile in $CWD"
    # Umgebung des laufenden Prozesses uebernehmen - unter cron fehlen
    # sonst DISPLAY=:99, WINEPREFIX und PATH, und Wine/MT5 startet nicht.
    while IFS= read -r -d '' KV; do
        case "$KV" in [A-Za-z_]*=*) export "${KV?}" ;; esac
    done < "/proc/$PID/environ"
    kill "$PID" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
    kill -9 "$PID" 2>/dev/null
    cd "$CWD" && nohup $CMD >> "$TT/autopatch_start.log" 2>&1 &
    sleep 3
    if find_bot_pid >/dev/null; then say "Bot laeuft wieder"
    else err "Bot startet nicht - von Hand pruefen"; fi
else
    err "Patch angewendet, aber kein laufender Bot gefunden - Neustart noetig"
fi
