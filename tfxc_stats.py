#!/usr/bin/env python3
"""Trefferquoten pro Layer. wine python tfxc_stats.py [CODE] [TAGE]"""
import sys
from collections import defaultdict
from datetime import datetime, timedelta
import MetaTrader5 as mt5

MAGIC = 88888
SERVER_OFFSET_H = 4

def outcome(comment, pnl):
    c = (comment or "").lower()
    if "[tp" in c:
        return "tp"
    if "[sl" in c:
        if pnl > 0.5:
            return "sl_plus"
        if pnl >= -0.5:
            return "sl_be"
        return "sl_minus"
    if "close" in c or "hold" in c:
        return "manual"
    return "other"

def layer_of(comment):
    c = (comment or "").upper()
    for n in ("L1","L2","L3","L4","L5","L6"):
        if c.endswith("-"+n) or ("-"+n+"-") in c:
            return n
    return "?"

def main():
    code = (sys.argv[1] if len(sys.argv) > 1 else "TFXC").upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    if not mt5.initialize():
        print("MT5 init fehlgeschlagen:", mt5.last_error()); return
    end = datetime.now() + timedelta(hours=SERVER_OFFSET_H)
    deals = mt5.history_deals_get(end - timedelta(days=days), end) or []
    opens, closes = {}, {}
    for d in deals:
        if d.magic != MAGIC: continue
        if d.entry == 0: opens[d.position_id] = d
        elif d.entry in (1,2): closes[d.position_id] = d
    charges = defaultdict(list)
    for pid, od in opens.items():
        if code not in (od.comment or "").upper(): continue
        cd = closes.get(pid)
        if cd: charges[(od.symbol, od.time)].append((od, cd))
    if not charges:
        print(f"Keine abgeschlossenen {code}-Chargen in {days} Tagen."); mt5.shutdown(); return
    print("="*66)
    print(f"  {code} LAYER-ANALYSE   |   {days} Tage   |   {len(charges)} Chargen")
    print("="*66)
    CATS = ("tp","sl_plus","sl_be","sl_minus","manual","other")
    layer_stat = defaultdict(lambda: {c:0 for c in CATS} | {"pnl":0.0})
    charge_pnl = []
    l1_then = {"ok":0,"loss":0}
    n_l1_tp = n_l1_sl = 0
    for (sym,t), legs in sorted(charges.items(), key=lambda kv: kv[0][1]):
        total = 0.0; by = {}
        for od, cd in legs:
            lay = layer_of(od.comment)
            pnl = cd.profit + cd.swap + cd.commission
            res = outcome(cd.comment, pnl)
            layer_stat[lay][res] += 1
            layer_stat[lay]["pnl"] += pnl
            by[lay] = res; total += pnl
        charge_pnl.append(total)
        if by.get("L1") == "tp":
            n_l1_tp += 1
            l2 = by.get("L2")
            if l2 in ("tp","sl_plus","sl_be"): l1_then["ok"] += 1
            elif l2 == "sl_minus": l1_then["loss"] += 1
        elif by.get("L1") == "sl_minus":
            n_l1_sl += 1
    print("\n  Pro Layer   (SL+ = nachgezogener SL im Gewinn)")
    print(f"    {'Layer':6} {'TP':>4} {'SL+':>4} {'BE':>4} {'SL-':>4} {'sonst':>6} {'ok-Quote':>9} {'P&L':>11}")
    for lay in sorted(layer_stat):
        st = layer_stat[lay]
        dec = st["tp"]+st["sl_plus"]+st["sl_be"]+st["sl_minus"]
        good = st["tp"]+st["sl_plus"]+st["sl_be"]
        q = (good/dec*100) if dec else 0
        other = st["manual"]+st["other"]
        print(f"    {lay:6} {st['tp']:>4} {st['sl_plus']:>4} {st['sl_be']:>4} "
              f"{st['sl_minus']:>4} {other:>6} {q:>8.1f}% {st['pnl']:>+11.2f}")
    dec1 = n_l1_tp + n_l1_sl
    print("\n  Kernfrage - faellt TP1 vor dem SL?")
    if dec1:
        print(f"    L1 mit TP: {n_l1_tp} | L1 mit SL: {n_l1_sl}  ->  p(TP1) = {n_l1_tp/dec1*100:.1f}%")
    else:
        print("    zu wenig Daten")
    if n_l1_tp:
        a,b = l1_then["ok"], l1_then["loss"]
        if a+b:
            print(f"    Wenn TP1 fiel: L2 ohne Verlust {a}x / mit Verlust {b}x -> {a/(a+b)*100:.1f}% gerettet")
    n = len(charge_pnl); tot = sum(charge_pnl)
    win = [p for p in charge_pnl if p > 0]; los = [p for p in charge_pnl if p < 0]
    print("\n  Pro Signal (ganze Charge):")
    print(f"    Netto:          ${tot:+.2f}")
    print(f"    Erwartungswert: ${tot/n:+.2f} pro Signal")
    print(f"    Gewinn: {len(win)} | Verlust: {len(los)}")
    if win: print(f"    Avg Gewinn:   ${sum(win)/len(win):+.2f}")
    if los: print(f"    Avg Verlust:  ${sum(los)/len(los):+.2f}")
    if los and sum(los): print(f"    Profit-Faktor: {abs(sum(win)/sum(los)):.2f}")
    print("="*66)
    mt5.shutdown()

if __name__ == "__main__":
    main()
