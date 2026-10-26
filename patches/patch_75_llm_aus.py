#!/usr/bin/env python3
# Patch 75 - schaltet die Anthropic-API ab.
#
#   Alex will sie nicht mehr nutzen. Der Regex-Parser hat heute alle
#   Trades allein richtig gelesen, auch waehrend die API seit 06:55 mit
#   400 antwortete ("credit balance is too low").
#
#   Verhalten danach ist genau das von heute, nur ohne Netzaufrufe:
#   interpret() liefert sofort NOISE, der Scalp-Parser entscheidet. Keine
#   HTTP-Anfragen, keine Kosten, keine Fehlerflut im Log, keine
#   Telegram-Warnung mehr.
#
#   Umkehrbar: LLM_AKTIV=true in der .env setzen und neu starten.
#   Der API-Schluessel bleibt unangetastet, ich fasse keine Zugangsdaten an.
import os, shutil
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
INT = os.path.join(TT, "intelligent_interpreter_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
if not os.path.exists(INT):
    INT = "intelligent_interpreter_v2.py"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH llmaus: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

getan = []

# ---- 1. Interpreter: sofort aussteigen ----------------------------------
if os.path.exists(INT):
    with open(INT, "r", encoding="utf-8") as f:
        src = f.read()
    MARKE = "LLM_AKTIV"
    ANKER = '        self._stats["total"] += 1\n'
    if MARKE in src:
        melde("Interpreter schon gepatcht")
    elif ANKER not in src:
        melde("FEHLER: Anker im Interpreter nicht gefunden")
    else:
        NEU = ('        if os.getenv("LLM_AKTIV", "false").lower() != "true":\n'
               '            fallback["reasoning"] = "LLM aus - nur Regex-Parser"\n'
               '            return fallback\n\n')
        shutil.copyfile(INT, INT + ".bak_75")
        src = src.replace(ANKER, NEU + ANKER, 1)
        with open(INT, "w", encoding="utf-8") as f:
            f.write(src)
        import py_compile
        try:
            py_compile.compile(INT, doraise=True)
            getan.append("Interpreter aus")
        except Exception as e:
            shutil.copyfile(INT + ".bak_75", INT)
            melde("FEHLER Interpreter, zurueckgerollt: " + str(e))
            raise SystemExit(1)
else:
    melde("intelligent_interpreter_v2.py nicht gefunden")

# ---- 2. Telegram-Warnung stummschalten ----------------------------------
with open(BOT, "r", encoding="utf-8") as f:
    bsrc = f.read()
A2 = '                if os.path.exists("API_ALERT.flag"):\n'
N2 = ('                if (os.getenv("LLM_AKTIV", "false").lower() == "true"\n'
      '                        and os.path.exists("API_ALERT.flag")):\n')
if 'LLM_AKTIV", "false").lower() == "true"' in bsrc:
    melde("Warnung schon stummgeschaltet")
elif A2 not in bsrc:
    melde("Anker fuer API_ALERT nicht gefunden")
else:
    shutil.copyfile(BOT, BOT + ".bak_75")
    bsrc = bsrc.replace(A2, N2, 1)
    with open(BOT, "w", encoding="utf-8") as f:
        f.write(bsrc)
    import py_compile
    try:
        py_compile.compile(BOT, doraise=True)
        getan.append("Telegram-Warnung aus")
    except Exception as e:
        shutil.copyfile(BOT + ".bak_75", BOT)
        melde("FEHLER Bot, zurueckgerollt: " + str(e))
        raise SystemExit(1)

# ---- 3. stehengebliebene Flagge entfernen -------------------------------
for f_ in ("API_ALERT.flag", os.path.join(TT, "API_ALERT.flag")):
    try:
        if os.path.exists(f_):
            os.remove(f_); getan.append("Flagge entfernt")
    except Exception:
        pass

melde("fertig: " + (", ".join(getan) or "nichts geaendert") +
      " | LLM_AKTIV steht auf " + os.getenv("LLM_AKTIV", "false"))
print("Patch 75 fertig")
