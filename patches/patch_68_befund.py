#!/usr/bin/env python3
# Patch 68 - reine Diagnose, aendert nichts.
#
#   Stand: Der Screenshot aus Patch 66/67 zeigt ein lebendes MT5 (Market
#   Watch tickt, Kurse laufen), aber weder Ctrl+E noch ein Mausklick auf
#   den Knopf "Algo Trading" bewirken etwas. Auch kein Hover-Rahmen am
#   Knopf. Eingaben erreichen Wine also ueberhaupt nicht, egal ob ueber
#   XTEST (Zeiger/Taste) oder XSendEvent (key --window).
#
#   Damit ist der GUI-Weg tot. Der verlaessliche Weg ist die
#   Terminal-Konfiguration: MT5 liest beim Start [Experts] AllowLiveTrading
#   bzw. die gespeicherten Optionen. Bevor ich daran etwas aendere, lese
#   ich, wie das Terminal gestartet wird und was in der Konfiguration
#   steht.
#
#   WICHTIG: common.ini kann Zugangsdaten enthalten. Dieser Patch gibt
#   NIEMALS Zeilen aus, die nach Login oder Passwort aussehen. Gefiltert
#   wird mit einer Positivliste, nicht mit einer Sperrliste.
import os, re, subprocess
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH befund: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=30):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:400]
    except Exception as e:
        return "Fehler: " + str(e)

melde("XTEST: " + sh("DISPLAY=:99 xdpyinfo 2>/dev/null | grep -i 'XTEST\\|XInputExtension' "
                     "| head -3 || echo '(xdpyinfo fehlt)'"))
melde("Xvfb: " + sh("ps -eo args | grep -m1 '[X]vfb'"))
melde("X-Hilfsprogramme: " + sh(
    "for p in xterm xmessage xclock xeyes xdpyinfo xwininfo xinput wmctrl; do "
    "command -v $p >/dev/null && printf '%s ' $p; done; echo"))

melde("MT5-Prozess: " + sh("ps -eo args | grep -m1 '[t]erminal64'"))
melde("Wine-Prefix: " + sh("ps -eo args | grep -m1 '[w]ineserver'"))
melde("MT5-Start-Einheit: " + sh(
    "systemctl list-units --type=service --all --no-pager 2>/dev/null "
    "| grep -i 'mt5\\|wine\\|terminal\\|xvfb' | head -5"))
melde("MT5-Startskripte: " + sh(
    "ls -1 $HOME/*.sh $HOME/teletrader/*.sh 2>/dev/null | head -12"))

# --- Terminal-Datenverzeichnis suchen -------------------------------------
melde("drive_c: " + sh("ls -d $HOME/.wine*/drive_c 2>/dev/null | head -3"))
inis = sh("find $HOME/.wine* -maxdepth 8 -name common.ini -path '*config*' "
          "2>/dev/null | head -5", timeout=90)
melde("common.ini: " + (inis or "(keine gefunden)"))
melde("terminal.ini/Origin: " + sh(
    "find $HOME/.wine* -maxdepth 8 \\( -name 'terminal.ini' -o -name 'origin.txt' \\) "
    "2>/dev/null | head -5", timeout=90))

# --- Nur unverfaengliche Schluessel ausgeben ------------------------------
ERLAUBT = re.compile(r"^\s*(\[[A-Za-z]+\]|"
                     r"(Enabled|AllowLiveTrading|AllowDllImport|AllowImport|"
                     r"Profile|NewsEnable|CertInstall|ProxyEnable)\s*=.*)$", re.I)
for pfad in [p.strip() for p in inis.split("|") if p.strip().endswith("common.ini")][:2]:
    try:
        with open(pfad, "r", encoding="utf-16-le", errors="replace") as f:
            roh = f.read()
        if "\x00" in roh or not roh.strip():
            with open(pfad, "r", encoding="utf-8", errors="replace") as f:
                roh = f.read()
    except Exception as e:
        melde("ini nicht lesbar (" + pfad + "): " + str(e)); continue
    zeilen = [z.strip() for z in roh.splitlines() if ERLAUBT.match(z.strip())]
    melde("aus " + os.path.basename(os.path.dirname(pfad)) + "/common.ini: " +
          (" | ".join(zeilen)[:350] or "(keine der gesuchten Schluessel)"))

print("Patch 68 fertig")
