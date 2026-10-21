#!/usr/bin/env python3
# Patch 37 - .env, idempotent. Aendert KEINEN Code.
#   SCALP_ENTRY_MAX_PIPS_XAUUSD -> 18  (war 15, nur fuer Gold)
# Am 21.10. um 10:35 wurde ein BUY bei 16.0 Pips Verzug verworfen, Grenze
# war 15. Fuenf Minuten spaeter meldete der Kanal TP1. Gerechnet auf der
# gemessenen Verteilung ist ein Einstieg mit Verzug noch positiv:
#   0 Pips +0.246R | 15 Pips +0.086R | 20 Pips +0.044R | 25 Pips +0.005R
#   ab 30 Pips negativ.
# 18 faengt die knappen Faelle und bleibt deutlich vor der Nulllinie.
import os, shutil
from datetime import datetime, timezone
ENV, LOG = ".env", "bot.log"
SOLL = {"SCALP_ENTRY_MAX_PIPS_XAUUSD":"18"}
ZEIGEN = ["TARGET_RISK_PCT","MAX_LAYERS_XAUUSD","PARTIAL_LADDER","LAYERS_FIT_RISK",
          "LADDER_START_STAGE","LADDER_MAX_STAGE","TRAILING_STOP_PIPS",
          "TRAILING_STOP_PIPS_XAUUSD","TRAILING_STOP_MIN_PROFIT_PIPS","PARTIAL_AT_TP",
          "SCALP_ENTRY_MAX_PIPS","SCALP_ENTRY_MAX_PIPS_XAUUSD"]
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
    shutil.copyfile(ENV,ENV+".bak_37")
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
