#!/usr/bin/env python3
# Patch 34 - .env, idempotent. Aendert KEINEN Code.
#   PARTIAL_LADDER            -> false  (zurueck auf 1 Partial TP1 + Rest Runner)
#   PARTIAL_AT_TP             -> 1
#   TRAILING_STOP_PIPS_XAUUSD -> 50
# Grund: bei 3,7% Risiko und 5 Layern bringt TP1-TP4 mit Trail 100 nur
# 0,385% Zuwachs je Trade, 1x TP1 + 4 Runner mit Trail 50 dagegen 0,841%.
# TARGET_RISK_PCT bleibt bei 0.038, also weiter 5 Layer.
import os, shutil
from datetime import datetime, timezone
ENV, LOG = ".env", "bot.log"
SOLL = {"PARTIAL_LADDER":"false", "PARTIAL_AT_TP":"1", "TRAILING_STOP_PIPS_XAUUSD":"50"}
ZEIGEN = ["TARGET_RISK_PCT","MAX_LAYERS_XAUUSD","PARTIAL_LADDER","LAYERS_FIT_RISK",
          "LADDER_START_STAGE","LADDER_MAX_STAGE","TRAILING_STOP_PIPS",
          "TRAILING_STOP_PIPS_XAUUSD","TRAILING_STOP_MIN_PROFIT_PIPS","PARTIAL_AT_TP"]
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
    shutil.copyfile(ENV,ENV+".bak_34")
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
