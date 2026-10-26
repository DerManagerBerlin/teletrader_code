#!/usr/bin/env python3
# Patch 92 - Screenshot plus Serverliste des Terminals. Rein lesend.
#
#   Ziel: Die Frage beantworten, ob dieses PU-Prime-Terminal den Server
#   UltimaMarkets-Live 1 ueberhaupt kennt. Drei Quellen:
#     1) Bild vom MT5-Fenster
#     2) vollstaendiges Config-Verzeichnis
#     3) Servernamen aus accounts.dat
#
#   accounts.dat enthaelt auch verschluesselte Passwoerter. Deshalb wird
#   die Datei NICHT ausgegeben. Es werden ausschliesslich Zeichenketten
#   herausgefiltert, die wie ein Servername aussehen, also Buchstaben,
#   dann -Live oder -Demo, optional eine Ziffer. Alles andere faellt weg.
import os, re, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH92 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=60):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

# 1) Bild
ziel = os.path.join(PUB, "mt5_konten.png")
sh("rm -f '" + ziel + "'; DISPLAY=:99 scrot -o '" + ziel + "' 2>&1 | head -1")
melde("Bild: " + (str(os.path.getsize(ziel)) + " Bytes"
                  if os.path.exists(ziel) else "fehlgeschlagen"))

# 2) Config vollstaendig
melde("Config: " + sh("ls -1 '" + MT5DIR + "/Config' 2>/dev/null | tr '\\n' ' '")[:400])

# 3) Servernamen aus accounts.dat, streng gefiltert
AD = os.path.join(MT5DIR, "Config", "accounts.dat")
RX = re.compile(r"\b[A-Za-z][A-Za-z0-9]{2,20}-(?:Live|Demo|Real)[ ]?\d{0,2}\b")
namen = []
try:
    with open(AD, "rb") as f:
        roh = f.read()
    for kod in ("utf-16-le", "latin-1"):
        try:
            txt = roh.decode(kod, errors="ignore")
        except Exception:
            continue
        for m in RX.findall(txt):
            if m not in namen:
                namen.append(m)
    melde("Server in accounts.dat: " + (", ".join(namen[:15]) or "(keine gefunden)"))
    melde("accounts.dat Groesse: " + str(len(roh)) + " Bytes")
except Exception as e:
    melde("accounts.dat nicht lesbar: " + str(e))

# 4) Terminal-Log, ungefiltert aber ohne Passwortzeilen
roh = sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
         "[ -n \"$L\" ] && tail -20 \"$L\" || echo KEINLOG")
for z in roh.splitlines()[-14:]:
    if re.search(r"(?i)pass|pwd|secret", z):
        continue
    melde("TLOG " + re.sub(r"\b(\d{6,})\b",
                           lambda m: "***" + m.group(1)[-3:], z.strip())[:180])
print("Patch 92 fertig")
