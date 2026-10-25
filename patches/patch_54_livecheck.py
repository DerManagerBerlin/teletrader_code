#!/usr/bin/env python3
# Patch 54 - idempotent. Vorbereitung auf den Live-Betrieb.
#   Aendert NICHTS am Handel und schaltet NICHT auf live. Reine Diagnose.
#
#   Beim Umschalten von Demo auf Live aendern sich drei Dinge, die jede
#   Order scheitern lassen koennen, ohne dass es vorher auffaellt:
#     1. Der Symbolname. Demo und Live koennen verschiedene Suffixe haben
#        (.p / .s / ganz ohne). Steht das falsch, geht keine einzige Order
#        durch.
#     2. Lotgrenzen und Schrittweite. volume_min kann live 0.01 oder 0.10
#        sein. Bei 0.10 waere unser Layer-Modell sofort zu gross.
#     3. Der Mindestabstand des Stops (trade_stops_level) und der Spread.
#        Der Spread geht direkt vom Ergebnis ab, und unsere Marge ist duenn:
#        realisiert +1,67 Euro je Signal auf vier Layer. Zwei Pips mehr
#        Spread je Layer sind 0,80 Euro, also knapp die Haelfte davon.
#
#   Neu: beim Start wird einmal alles davon geloggt, ohne Zugangsdaten.
#       LIVECHECK Modus=DEMO Server=... Konto=***957 Waehrung=EUR Balance=...
#       LIVECHECK XAUUSD.s handelbar=1 lot 0.01-50.0 step 0.01 stops=0
#                 bid=... ask=... spread=2.4 Pips digits=2
#   Damit habe ich die Demo-Werte als Vergleichsmassstab, bevor
#   umgeschaltet wird, und sehe nach dem Umschalten sofort, was sich
#   geaendert hat.
#   Abschaltbar mit LIVECHECK=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "LIVECHECK" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_54")

A_OLD = '''    account_type = "DEMO" if DEMO_MODE else "LIVE ⚠️"
    log.info(f"MT5 [{account_type}] → Konto {info.login} | Balance: ${info.balance:.2f} {info.currency}")
    return True
'''
A_NEW = '''    account_type = "DEMO" if DEMO_MODE else "LIVE ⚠️"
    log.info(f"MT5 [{account_type}] → Konto {info.login} | Balance: ${info.balance:.2f} {info.currency}")
    # PATCH54: Pruefwerte fuer den Umstieg auf live. Kontonummer maskiert,
    # keine Zugangsdaten.
    if os.getenv("LIVECHECK", "true").lower() == "true":
        try:
            _kt = str(info.login)
            log.info("LIVECHECK Modus=" + ("DEMO" if DEMO_MODE else "LIVE") +
                     " Server=" + str(getattr(info, "server", "?")) +
                     " Konto=***" + _kt[-3:] +
                     " Waehrung=" + str(info.currency) +
                     " Balance=" + str(round(info.balance, 2)) +
                     " Hebel=" + str(getattr(info, "leverage", "?")) +
                     " TradeAllowed=" + str(getattr(info, "trade_allowed", "?")))
            for _sym in [GOLD_SYMBOL, BTC_SYMBOL + FX_SUFFIX]:
                try:
                    _si = mt5.symbol_info(_sym)
                    if _si is None:
                        if not mt5.symbol_select(_sym, True):
                            log.error("LIVECHECK " + str(_sym) +
                                      " NICHT VERFUEGBAR - Symbolname pruefen")
                            continue
                        _si = mt5.symbol_info(_sym)
                    if _si is None:
                        log.error("LIVECHECK " + str(_sym) + " NICHT VERFUEGBAR")
                        continue
                    _tk = mt5.symbol_info_tick(_sym)
                    _pip = (_si.point or 0.01) * 10
                    _spr = ((_tk.ask - _tk.bid) / _pip) if (_tk and _pip) else -1
                    log.info("LIVECHECK " + str(_sym) +
                             " handelbar=" + str(getattr(_si, "trade_mode", "?")) +
                             " lot " + str(_si.volume_min) + "-" + str(_si.volume_max) +
                             " step " + str(_si.volume_step) +
                             " stops=" + str(getattr(_si, "trade_stops_level", "?")) +
                             " digits=" + str(_si.digits) +
                             " bid=" + (str(_tk.bid) if _tk else "?") +
                             " ask=" + (str(_tk.ask) if _tk else "?") +
                             " spread=" + str(round(_spr, 1)) + " Pips")
                except Exception as _se:
                    log.error("LIVECHECK " + str(_sym) + " Fehler: " + str(_se))
            log.info("LIVECHECK Handel pausiert=" + str(is_trading_paused()))
        except Exception as _e:
            log.error("LIVECHECK Fehler: " + str(_e))
    return True
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 54 OK - Livecheck-Diagnose beim Start")
