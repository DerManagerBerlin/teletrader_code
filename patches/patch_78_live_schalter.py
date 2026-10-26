#!/usr/bin/env python3
# Patch 78 - Bot-Seite des Live-Umschalters.
#
#   Was heute schiefging:
#     14:16:00  Terminal haelt Konto 700190957 statt 34706330
#     14:17:01  Parameter-Login fehlgeschlagen: (-10005, 'IPC timeout')
#   Genau 61 Sekunden, also der Standard-Timeout von initialize(). Ein
#   Kontowechsel unter Wine dauert laenger. Zusaetzlich schaltet MT5 bei
#   jedem Kontowechsel AutoTrading selbst ab, danach lief nichts mehr.
#
#   Drei Aenderungen:
#   1) connect_mt5: Parameter-Login mit 180 s statt 60 s. Und nach einem
#      Timeout wird nachgesehen, ob der Wechsel doch geklappt hat - ein
#      IPC-Timeout ist kein Beweis fuer einen gescheiterten Login. Erst
#      wenn das Konto wirklich falsch ist, gilt es als Fehlschlag.
#      Das ist KEIN Wiederholungslauf: es wird nur nachgesehen, nicht
#      erneut angemeldet. Die Sperre nach MAX_LOGIN_FAILS bleibt.
#   2) /live und /demo: statt nur den Bot zu beenden wird jetzt die Flagge
#      TERMINAL_RESTART_REQUEST gesetzt. Der Linux-Watcher aus Patch 77
#      setzt dann [Experts] Enabled=1 und startet den ganzen Dienst neu,
#      also auch das Terminal. Damit ist AutoTrading nach dem Wechsel an.
#   3) /algotrading: nutzt denselben Weg statt des Tastendrucks, der Wine
#      nicht erreicht.
import os, shutil
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH liveschalt: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if "TERMINAL_RESTART_REQUEST" in src:
    melde("schon gepatcht"); raise SystemExit(0)

getan = []

# ---- 1. laengerer Timeout + Nachkontrolle --------------------------------
A1 = ("        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, "
      "server=MT5_SERVER)\n"
      "        if not _ok:\n"
      "            log.error('MT5 Parameter-Login fehlgeschlagen: %s', mt5.last_error())\n")
N1 = ("        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD,\n"
      "                             server=MT5_SERVER, timeout=180000)\n"
      "        if not _ok:\n"
      "            # PATCH78: Ein IPC-Timeout heisst nicht, dass der Login\n"
      "            # scheiterte. Nachsehen, ob das Konto trotzdem steht.\n"
      "            # Kein zweiter Anmeldeversuch, nur ein Blick.\n"
      "            _fehler = mt5.last_error()\n"
      "            try:\n"
      "                import time as _t78\n"
      "                _t78.sleep(10)\n"
      "                if mt5.initialize():\n"
      "                    _nach = mt5.account_info()\n"
      "                    if _nach and int(_nach.login) == int(MT5_LOGIN):\n"
      "                        _ok = True\n"
      "                        log.info('MT5: Login lag nur am IPC-Timeout, "
      "Konto %s steht', _nach.login)\n"
      "                    else:\n"
      "                        log.warning('MT5: nach Timeout weiterhin Konto %s',\n"
      "                                    getattr(_nach, 'login', None))\n"
      "            except Exception as _e78:\n"
      "                log.warning('MT5 Nachkontrolle: %s', _e78)\n"
      "        if not _ok:\n"
      "            log.error('MT5 Parameter-Login fehlgeschlagen: %s', _fehler)\n")

if A1 in src:
    src = src.replace(A1, N1, 1); getan.append("Timeout 180s + Nachkontrolle")
else:
    melde("WARNUNG: Anker 1 nicht gefunden")

# ---- 2. /live und /demo: Terminal mit neu starten ------------------------
A2 = ("            # Watchdog übernimmt Neustart – kein execv unter Wine\n"
      "            import os as _os, signal as _sig\n"
      "            _os.kill(_os.getpid(), _sig.SIGTERM)\n")
N2 = ("            # PATCH78: Nicht nur den Bot beenden. Das Terminal muss\n"
      "            # mit neu starten, sonst bleibt es auf dem alten Konto und\n"
      "            # AutoTrading bleibt aus (MT5 schaltet es beim Kontowechsel\n"
      "            # selbst ab). Der Linux-Watcher erledigt beides.\n"
      "            try:\n"
      "                with open('/home/alexander_lacher/teletrader/"
      "TERMINAL_RESTART_REQUEST', 'w', encoding='utf-8') as _rf:\n"
      "                    _rf.write(datetime.now().isoformat() + '\\n')\n"
      "                log.info('Terminal-Neustart angefordert (Kontowechsel)')\n"
      "            except Exception as _re:\n"
      "                log.error('Neustart-Flagge nicht schreibbar: %s', _re)\n"
      "                import os as _os, signal as _sig\n"
      "                _os.kill(_os.getpid(), _sig.SIGTERM)\n")

if A2 in src:
    src = src.replace(A2, N2, 1); getan.append("/live startet Terminal mit")
else:
    melde("WARNUNG: Anker 2 nicht gefunden")

# ---- 3. /algotrading auf den wirksamen Weg ------------------------------
A3 = ("                ok = False\n"
      "                for _versuch in range(3):\n"
      "                    if await _enable_algo_trading_via_gui():\n"
      "                        ok = True\n"
      "                        break\n"
      "                    await asyncio.sleep(2)\n"
      "                if ok:\n"
      "                    await send_notification(\"Algo Trading aktiviert\")\n"
      "                else:\n"
      "                    await send_notification(\n"
      "                        \"Algo Trading konnte nicht aktiviert werden.\\n\"\n"
      "                        \"Bitte in MT5 manuell aktivieren (gruener Button oben).\"\n"
      "                    )\n")
N3 = ("                # PATCH78: Tastendruecke erreichen Wine nicht. Der\n"
      "                # wirksame Weg ist [Experts] Enabled=1 plus Neustart\n"
      "                # des Terminals, erledigt vom Linux-Watcher.\n"
      "                try:\n"
      "                    with open('/home/alexander_lacher/teletrader/"
      "TERMINAL_RESTART_REQUEST', 'w', encoding='utf-8') as _rf:\n"
      "                        _rf.write(datetime.now().isoformat() + '\\n')\n"
      "                    await send_notification(\n"
      "                        \"Algo Trading wird gesetzt.\\n\"\n"
      "                        \"Terminal startet neu, das dauert etwa eine Minute.\")\n"
      "                except Exception as _ae:\n"
      "                    await send_notification(\"Anforderung fehlgeschlagen: \"\n"
      "                                            + str(_ae))\n")

if A3 in src:
    src = src.replace(A3, N3, 1); getan.append("/algotrading umgestellt")
else:
    melde("WARNUNG: Anker 3 nicht gefunden")

if not getan:
    melde("nichts geaendert, kein Anker gefunden"); raise SystemExit(1)

shutil.copyfile(BOT, BOT + ".bak_78")
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("fertig: " + ", ".join(getan))
except Exception as e:
    shutil.copyfile(BOT + ".bak_78", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 78 fertig")
