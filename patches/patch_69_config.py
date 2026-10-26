#!/usr/bin/env python3
# Patch 69 - liest die MT5-Konfiguration, aendert nichts.
#
#   Befund aus Patch 68:
#     MT5 laeuft portabel aus
#       ~/.wine/drive_c/Program Files/PU Prime MT5 Terminal/
#     mit eigenem Config-Verzeichnis (grosses C, deshalb hat meine Suche
#     nach '*config*' die common.ini nicht gefunden).
#     Gestartet wird alles von teletrader/watchdog.sh (Xvfb + MT5 + Bot).
#     XTEST ist vorhanden, Xvfb laeuft normal - die Eingaben werden also
#     erzeugt, nur Wine reagiert nicht darauf.
#
#   Ziel: AutoTrading ueber die Konfiguration setzen statt ueber die
#   Oberflaeche. Dafuer brauche ich die echten Schluesselnamen im
#   [Experts]-Abschnitt und die Startzeile des Terminals.
#
#   Zugangsdaten werden nicht ausgegeben. Aus den ini-Dateien kommt nur
#   eine Positivliste harmloser Schluessel; aus watchdog.sh nur Zeilen mit
#   terminal64/Xvfb/DISPLAY, und auch die noch redigiert.
import os, re, subprocess
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
MT5 = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                   "PU Prime MT5 Terminal")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH cfg: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:420]
    except Exception as e:
        return "Fehler: " + str(e)

GEHEIM = re.compile(r"(?i)(pass|pwd|kennwor|login|/l:|account)")

def sauber(z):
    """Alles mit Anmeldebezug faellt komplett raus."""
    return "" if GEHEIM.search(z) else z

def lies(pfad):
    """Kodierung an den Bytes erkennen, nicht raten. Eine reine ASCII-Datei
    laesst sich auch als utf-16 'erfolgreich' dekodieren - dabei kommt
    Unsinn ohne Zeilenumbrueche heraus. Deshalb erst die Bytes ansehen."""
    try:
        with open(pfad, "rb") as f:
            b = f.read()
    except Exception:
        return ""
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        kod = "utf-16"
    elif b[:3] == b"\xef\xbb\xbf":
        kod = "utf-8-sig"
    elif b.count(b"\x00") > len(b) // 4:
        kod = "utf-16-le"
    else:
        kod = "utf-8"
    try:
        return b.decode(kod, errors="replace")
    except Exception:
        return b.decode("latin-1", errors="replace")

melde("Verzeichnis: " + sh("ls -1 '" + MT5 + "' 2>&1 | head -12"))
melde("Config: " + sh("ls -la '" + MT5 + "/Config' 2>&1 | tail -n +2 | head -12"))

ERLAUBT = re.compile(r"^\s*(\[[A-Za-z ]+\]\s*$|"
                     r"(Enabled|AllowLiveTrading|AllowDllImport|AllowImport|"
                     r"AllowExternalExperts|AllowWebRequest|Profile|NewsEnable|"
                     r"ProxyEnable|CertInstall|Server|KeepPrivate)\s*=.*)$", re.I)

for name in ("common.ini", "terminal.ini", "experts.ini"):
    pfad = os.path.join(MT5, "Config", name)
    if not os.path.exists(pfad):
        melde(name + ": nicht vorhanden"); continue
    roh = lies(pfad)
    treffer = []
    for z in roh.splitlines():
        z = z.strip()
        if not ERLAUBT.match(z):
            continue
        z = sauber(z)
        if z:
            treffer.append(z)
    melde(name + " (" + str(len(roh.splitlines())) + " Zeilen): " +
          (" | ".join(treffer)[:380] or "(keiner der gesuchten Schluessel)"))

# Gibt es weitere ini-Dateien im Profil?
melde("weitere ini: " + sh("find '" + MT5 + "' -maxdepth 3 -iname '*.ini' "
                           "-printf '%P ' 2>/dev/null | head -c 300"))

# --- Startzeile des Terminals aus watchdog.sh ----------------------------
WD = os.path.join(HOME, "teletrader", "watchdog.sh")
if os.path.exists(WD):
    zeilen = []
    for z in lies(WD).splitlines():
        if re.search(r"(?i)terminal64|Xvfb|DISPLAY=|wine ", z):
            z = sauber(z.strip())
            if z:
                zeilen.append(z)
    melde("watchdog.sh Start: " + (" | ".join(zeilen)[:400] or "(nichts Passendes)"))
else:
    melde("watchdog.sh nicht gefunden")

print("Patch 69 fertig")
