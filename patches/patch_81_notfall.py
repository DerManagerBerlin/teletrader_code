#!/usr/bin/env python3
# Patch 81 - Notfalldiagnose nach /live.
#
#   Lage: Alex hat 15:31 /live gedrueckt, der Bot hat den Wechsel
#   quittiert, danach kam keine Startmeldung mehr und der Spiegel steht
#   seit 15:30. Das deutet darauf hin, dass teletrader.service nicht
#   wieder hochgekommen ist.
#
#   Dieser Patch aendert zunaechst NICHTS am Modus. Er sammelt den
#   Zustand und startet den Dienst nur dann neu, wenn er nachweislich
#   nicht laeuft. Erst wenn auch das scheitert, faellt er auf DEMO
#   zurueck, damit der Bot ueberhaupt wieder handelt.
#
#   Zugangsdaten werden nicht ausgegeben.
import os, re, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
BOTLOG = os.path.join(TT, "bot.log")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH notfall: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:400]
    except Exception as e:
        return "Fehler: " + str(e)

GEHEIM = re.compile(r"(?i)(pass|pwd|kennwor|token|api[_-]?key|secret)")

melde("Dienst: " + sh("systemctl is-active teletrader.service 2>&1 | head -1") +
      " / " + sh("systemctl is-failed teletrader.service 2>&1 | head -1"))
melde("Seit: " + sh("systemctl show -p ActiveEnterTimestamp -p NRestarts --value "
                    "teletrader.service 2>/dev/null"))
melde("Journal: " + sh("journalctl -u teletrader.service -n 6 --no-pager 2>/dev/null "
                       "| tail -6"))
melde("Watcher-Journal: " + sh("journalctl -t algo_enabler -n 4 --no-pager 2>/dev/null "
                               "| tail -4"))
melde("algo_set.log: " + sh("tail -4 '" + os.path.join(TT, 'algo_set.log') +
                            "' 2>/dev/null || echo '(leer)'"))

# DEMO_MODE aus der .env, ohne andere Zeilen anzufassen
modus = "?"
try:
    with open(ENV, encoding="utf-8") as f:
        for z in f:
            if z.strip().startswith("DEMO_MODE="):
                modus = z.strip()
except Exception as e:
    modus = "nicht lesbar: " + str(e)
melde(".env: " + modus)

# Letzte Bot-Zeilen, gefiltert
roh = sh("tail -25 '" + BOTLOG + "' 2>/dev/null")
sauber = " | ".join(z for z in roh.split(" | ") if not GEHEIM.search(z))
melde("bot.log Ende: " + sauber[:400])

aktiv = sh("systemctl is-active teletrader.service 2>&1 | head -1").strip()
if aktiv == "active":
    melde("Dienst laeuft, kein Eingriff")
else:
    melde("Dienst laeuft NICHT - Neustartversuch")
    melde("Neustart: " + sh("sudo -n systemctl restart teletrader.service 2>&1 "
                            "&& echo OK"))
    time.sleep(25)
    aktiv2 = sh("systemctl is-active teletrader.service 2>&1 | head -1").strip()
    melde("danach: " + aktiv2)
    if aktiv2 != "active":
        melde("Immer noch unten - setze DEMO_MODE=true, damit der Bot "
              "ueberhaupt wieder handelt")
        try:
            with open(ENV, encoding="utf-8") as f:
                zeilen = f.readlines()
            neu, gefunden = [], False
            for z in zeilen:
                if z.strip().startswith("DEMO_MODE="):
                    neu.append("DEMO_MODE=true\n"); gefunden = True
                else:
                    neu.append(z)
            if not gefunden:
                neu.append("DEMO_MODE=true\n")
            tmp = ENV + ".tmp81"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(neu); f.flush(); os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, ENV)
            melde("DEMO_MODE=true gesetzt")
        except Exception as e:
            melde("ENV-Schreiben fehlgeschlagen: " + str(e))
        melde("Neustart 2: " + sh("sudo -n systemctl restart teletrader.service "
                                  "2>&1 && echo OK"))
        time.sleep(25)
        melde("Endstand: " + sh("systemctl is-active teletrader.service 2>&1 | head -1"))

print("Patch 81 fertig")
