#!/usr/bin/env python3
# Patch 46 - idempotent.
#   Die SL-Leiter arbeitet rein kursgetrieben: sie vergleicht das Extrem
#   unserer eigenen M1-Bars mit den TP-Niveaus. Die Meldung des Kanals
#   spielt keine Rolle - und kann auch keine spielen, denn BREAKEVEN_WORDS
#   enthaelt ausschliesslich englische Wendungen ("sl to be", "move sl to
#   breakeven", ...). Der Kanal schreibt aber deutsch:
#       "✅ TP1 HIT! +50 PIPS  ➡️ SL auf Entry (BE)"
#   Das trifft keinen einzigen Eintrag. Der nachrichtengetriebene
#   Breakeven-Pfad feuert fuer diesen Kanal also nie.
#
#   Folge: druckt der Kurs beim Signalgeber TP1, bei unserem Broker aber
#   nicht (Spread, andere Feed-Spitze), bleibt die Leiter auf Stufe 0. Dann
#   geht KEIN Layer auf Entry, und ein Ruecklauf nimmt den vollen SL auf
#   allen Layern statt einer Nullrunde.
#   Belegt am 22.10.:
#     15:15 UTC  TP1 4051.00, unser tiefster Bid 4050.88 -> 12 Cent gefehlt
#     20:10 UTC  TP1 4021.38, unser tiefster Bid 4021.34 ->  4 Cent gefehlt
#
#   Neu: meldet der Kanal "TP<n> HIT", gilt die Stufe als erreicht, auch
#   wenn unsere Bars sie nicht gedruckt haben. Die Leiter behaelt dabei
#   alle Sicherungen: sie verschlechtert keinen SL, haelt den
#   Mindestabstand ein und laesst den Layer mit eigenem TP in Ruhe
#   (Patch 43). Die gemeldete Stufe wird auf LADDER_MAX_STAGE begrenzt und
#   bei jedem neuen Signal zurueckgesetzt, kann also nicht auf die Layer
#   des naechsten Trades durchschlagen.
#   Abschaltbar mit TP_AUS_MELDUNG=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "TP_AUS_MELDUNG" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_46")

# ── 1. Speicher + Erkennung auf Modulebene ───────────────────────────────
A_OLD = '_NACHHOL_DATEI = "nachholen.json"\n'
A_NEW = '''_NACHHOL_DATEI = "nachholen.json"
# PATCH46: zuletzt vom Kanal gemeldete TP-Stufe. Wird bei jedem neuen
# Signal zurueckgesetzt, gilt also immer nur fuer den laufenden Trade.
_tp_meldung = {"stufe": 0, "ts": 0.0}
_TP_MELD_RX = re.compile(r"TP\\s*(\\d)\\s*(?:HIT|Hit)", re.IGNORECASE)

def _tp_meldung_pruefen(text):
    """Erkennt die TP-Treffermeldung des Kanals und merkt die Stufe."""
    try:
        if not text:
            return
        if "SCALP IDEE" in text or "NEUE TRADE IDEE" in text:
            _tp_meldung["stufe"] = 0
            _tp_meldung["ts"] = datetime.now().timestamp()
            return
        _m = _TP_MELD_RX.search(text)
        if _m:
            _s = int(_m.group(1))
            if _s > int(_tp_meldung.get("stufe") or 0):
                _tp_meldung["stufe"] = _s
                _tp_meldung["ts"] = datetime.now().timestamp()
                log.info("Kanal meldet TP" + str(_s) +
                         " - Leiter darf die Stufe ohne eigenen Kursdruck setzen")
    except Exception:
        pass
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── 2. Erkennung in den Parser haengen (laeuft fuer jede Kanalnachricht) ─
B_OLD = '''    def _f(s):
        return float(s.replace(",", "."))
'''
B_NEW = '''    _tp_meldung_pruefen(text)          # PATCH46

    def _f(s):
        return float(s.replace(",", "."))
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

# ── 3. Gemeldete Stufe in der Leiter beruecksichtigen ────────────────────
C_OLD = '''                    _lmax = int(os.getenv("LADDER_MAX_STAGE", "0"))
                    if _lmax > 0 and _reached > _lmax:
                        continue
'''
C_NEW = '''                    _lmax = int(os.getenv("LADDER_MAX_STAGE", "0"))
                    # PATCH46: Was der Kanal gemeldet hat, zaehlt auch dann,
                    # wenn unsere eigenen Bars die Stufe nicht gedruckt haben.
                    if os.getenv("TP_AUS_MELDUNG", "true").lower() == "true":
                        _ms = int(_tp_meldung.get("stufe") or 0)
                        _mts = float(_tp_meldung.get("ts") or 0)
                        if _ms > 0 and _mts > 0 and \\
                                (datetime.now().timestamp() - _mts) < 14400:
                            if _lmax > 0:
                                _ms = min(_ms, _lmax)
                            if _ms > _reached:
                                if tk not in _meld_genutzt:
                                    _meld_genutzt.add(tk)
                                    if len(_meld_genutzt) > 500:
                                        _meld_genutzt.clear()
                                    log.info("SL-Leiter #" + str(tk) + ": Stufe " +
                                             str(_ms) + " aus der Kanalmeldung (" +
                                             "eigener Kurs hat sie nicht gedruckt)")
                                _reached = _ms
                    if _lmax > 0 and _reached > _lmax:
                        continue
'''
if src.count(C_OLD) != 1:
    print("FEHLER Anker 3:", src.count(C_OLD)); sys.exit(1)
src = src.replace(C_OLD, C_NEW)

# ── 4. Ticketspeicher fuer die Logzeile ──────────────────────────────────
D_OLD = '_leiter_gemeldet = set()    # PATCH45: Tickets, fuer die die Leiter schon gemeldet hat\n'
D_NEW = ('_leiter_gemeldet = set()    # PATCH45: Tickets, fuer die die Leiter schon gemeldet hat\n'
         '_meld_genutzt = set()       # PATCH46: Tickets, die schon eine Kanalstufe genutzt haben\n')
if src.count(D_OLD) != 1:
    print("FEHLER Anker 4:", src.count(D_OLD)); sys.exit(1)
src = src.replace(D_OLD, D_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 46 OK - Leiter akzeptiert die TP-Meldung des Kanals")
