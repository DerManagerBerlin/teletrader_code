#!/usr/bin/env python3
# Patch 38 - .env, idempotent. Aendert KEINEN Code.
#   TRAILING_STOP_PIPS_XAUUSD             -> 30  (war 50)
#   TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD  -> 30  (war 50, global bleibt 50)
# Grundlage: 17 gemessene Hochpunkte aus der Nacht, Median 57 Pips, 41%
# bleiben unter 50. Dazu der Tagestrade vom 21.10. 14:35: Hoch +100 Pips,
# Ausstieg +50, und der groesste Ruecksetzer auf dem ganzen Weg betrug
# 6,3 Pips. Ein 30er-Trail haette dort +70 statt +50 gebracht.
# Nur Gold; BTC behaelt seine 500/1200.

import os, shutil
from datetime import datetime, timezone
ENV, LOG = ".env", "bot.log"
SOLL = {"TRAILING_STOP_PIPS_XAUUSD":"30",
        "TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD":"30"}
ZEIGEN = ["TARGET_RISK_PCT","MAX_LAYERS_XAUUSD","PARTIAL_LADDER","LAYERS_FIT_RISK",
          "LADDER_START_STAGE","LADDER_MAX_STAGE","TRAILING_STOP_PIPS",
          "TRAILING_STOP_PIPS_XAUUSD","TRAILING_STOP_MIN_PROFIT_PIPS","PARTIAL_AT_TP",
          "SCALP_ENTRY_MAX_PIPS_XAUUSD","TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD"]
def log(t):
    try:
        with open(LOG,"a",encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000")+
                    " [INFO] AUTOPATCH env: "+t+"\n")
    except Exception: pass
if not os.path.exists(ENV): print("FEHLER: .env fehlt"); raise SystemExit(1)
neu=[]; alt={}; gesetzt=[]
for z in open(ENV,encoding="utf-8").read().splitlines():
    s=z.strip(); fertig=False
    if s and not s.startswith("#") and "=" in s:
        k,v=s.split("=",1); k,v=k.strip(),v.strip(); alt[k]=v
        if k in SOLL:
            if v!=SOLL[k]: neu.append(k+"="+SOLL[k]); gesetzt.append(k+": "+v+" -> "+SOLL[k])
            else: neu.append(z)
            fertig=True
    if not fertig: neu.append(z)
for k,v in SOLL.items():
    if k not in alt: neu.append(k+"="+v); gesetzt.append(k+": (fehlte) -> "+v)
if gesetzt:
    shutil.copyfile(ENV,ENV+".bak_38")
    open(ENV,"w",encoding="utf-8").write("\n".join(neu)+"\n")
    print("geaendert: "+" | ".join(gesetzt))
else: print("nichts zu tun")
akt={}
for z in open(ENV,encoding="utf-8").read().splitlines():
    s=z.strip()
    if s and not s.startswith("#") and "=" in s:
        k,v=s.split("=",1); akt[k.strip()]=v.strip()
log("geaendert: "+(" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: "+" ".join(k+"="+akt[k] for k in ZEIGEN if k in akt))
