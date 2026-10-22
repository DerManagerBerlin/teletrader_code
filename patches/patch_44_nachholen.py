#!/usr/bin/env python3
# Patch 44 - idempotent.
#   Wird ein Signal verworfen, weil der Markt beim Eintreffen schon zu weit
#   vom Entry weg war, ist es bisher endgueltig weg. Kommt der Kurs danach
#   in die Entry-Zone zurueck, schaut der Bot zu.
#   Beispiel 22.10. 22:05 UTC: BUY Entry 4026.09, Markt stand 25.9 Pips
#   dagegen bei 4028.68 (Fenster 18). Verworfen. Kurz danach war der Kurs
#   wieder am Entry, TP1 (4031.09) war nie erreicht - der Trade war also
#   noch vollstaendig da.
#   Weitere Faelle: 21.10. 10:35 / 13:05 / 14:00 / 18:50, 22.10. 06:05.
#
#   Neu: solche Signale landen in nachholen.json. Ein Watcher prueft alle
#   10 Sekunden und steigt ein, sobald der Kurs wieder im normalen
#   Entry-Fenster liegt. Verworfen wird der Kandidat, wenn
#     - TP1 durchlaufen ist (die Bewegung ist gelaufen, wir springen nicht
#       hinterher),
#     - der SL beruehrt wurde (das Setup ist tot),
#     - oder die Frist ablaeuft (NACHHOL_FRIST_MIN, Standard 60 Minuten).
#   Solange eine Position auf dem Symbol offen ist, wartet der Watcher.
#   Der Einstieg laeuft ueber process_signal, also mit der normalen
#   Layer-, Risiko- und SL-Logik inklusive Patch 39 (SL-Distanz vom echten
#   Einstiegskurs).
#   Abschaltbar mit NACHHOLEN=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "NACHHOL_FRIST_MIN" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_44")

# ── 1. Helfer auf Modulebene, direkt vor parse_scalp_signal ──────────────
A_OLD = 'def parse_scalp_signal(text: str) -> dict:\n'
A_NEW = '''_NACHHOL_DATEI = "nachholen.json"

def _nachhol_lesen():
    """Vorgemerkte Signale lesen (PATCH44). Fehler = leere Liste."""
    try:
        with open(_NACHHOL_DATEI, encoding="utf-8") as _f:
            _d = json.load(_f)
        return _d if isinstance(_d, list) else []
    except Exception:
        return []

def _nachhol_schreiben(liste):
    try:
        with open(_NACHHOL_DATEI + ".tmp", "w", encoding="utf-8") as _f:
            json.dump(liste, _f)
        os.replace(_NACHHOL_DATEI + ".tmp", _NACHHOL_DATEI)
    except Exception:
        pass

def _nachhol_merken(symbol, direction, entry, sl, tps, text, warum):
    """Signal fuer einen spaeteren Einstieg vormerken, wenn der Markt beim
    Eintreffen zu weit weg war. Der Watcher entscheidet dann."""
    if os.getenv("NACHHOLEN", "true").lower() != "true":
        return
    try:
        if not (symbol and direction and entry and sl and tps.get(1)):
            return
        liste = [k for k in _nachhol_lesen()
                 if not (k.get("symbol") == symbol
                         and k.get("direction") == direction
                         and abs(float(k.get("entry") or 0) - float(entry)) < 1e-9)]
        liste = liste[-20:]
        liste.append({"symbol": symbol, "direction": direction,
                      "entry": float(entry), "sl": float(sl),
                      "tp1": tps.get(1), "tp2": tps.get(2), "tp3": tps.get(3),
                      "tp4": tps.get(4), "tp5": tps.get(5),
                      "ts": datetime.now().timestamp(),
                      "raw_text": (text or "")[:400],
                      "hash": "nachhol_" + str(symbol) + str(direction) + str(entry),
                      "warum": warum})
        _nachhol_schreiben(liste)
        log.info("Nachholen vorgemerkt: " + str(symbol) + " " + str(direction) +
                 " Entry " + str(entry) + " (" + str(warum) + ")")
    except Exception:
        pass

def parse_scalp_signal(text: str) -> dict:
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── 2. Pip-Grenze: vormerken statt nur verwerfen ─────────────────────────
B_OLD = '''                        if _gap_pips > _max_pips:
                            return _noise("Markt " + str(round(_gap_pips, 1)) +
'''
B_NEW = '''                        if _gap_pips > _max_pips:
                            _nachhol_merken(symbol, direction, entry, sl, tps, text,
                                            "Markt " + str(round(_gap_pips, 1)) +
                                            " Pips weg, Fenster " + str(_max_pips))
                            return _noise("Markt " + str(round(_gap_pips, 1)) +
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

# ── 3. SL-Anteil-Grenze: ebenfalls vormerken ─────────────────────────────
C_OLD = '''                        if _frac > _max_frac:
                            return _noise("Markt " + str(round(_frac * 100, 1)) +
'''
C_NEW = '''                        if _frac > _max_frac:
                            _nachhol_merken(symbol, direction, entry, sl, tps, text,
                                            "Markt " + str(round(_frac * 100, 1)) +
                                            "% der SL-Distanz weg")
                            return _noise("Markt " + str(round(_frac * 100, 1)) +
'''
if src.count(C_OLD) != 1:
    print("FEHLER Anker 3:", src.count(C_OLD)); sys.exit(1)
src = src.replace(C_OLD, C_NEW)

# ── 4. Watcher-Loop, definiert direkt vor dem gather ─────────────────────
D_OLD = '''    await asyncio.gather(
        user_client.run_until_disconnected(),
'''
D_NEW = '''    async def nachhol_watcher():
        """PATCH44: holt verworfene Signale nach, deren Kurs vor TP1 wieder
        in die Entry-Zone zurueckkommt."""
        if os.getenv("NACHHOLEN", "true").lower() != "true":
            return
        _poll  = max(3.0, float(os.getenv("NACHHOL_POLL_SECONDS", "10")))
        _frist = float(os.getenv("NACHHOL_FRIST_MIN", "60"))
        while True:
            try:
                liste = _nachhol_lesen()
                if liste:
                    rest = []
                    for k in liste:
                        try:
                            _alter = (datetime.now().timestamp() -
                                      float(k.get("ts") or 0)) / 60.0
                        except Exception:
                            _alter = 99999.0
                        _bs  = resolve_symbol(k.get("symbol") or "")
                        _dir = str(k.get("direction") or "").upper()
                        if _alter > _frist or not _bs or _dir not in ("BUY", "SELL"):
                            log.info("Nachholen verfallen: " + str(_bs) + " " + _dir +
                                     " Entry " + str(k.get("entry")) + " nach " +
                                     str(round(_alter, 1)) + " Min")
                            continue
                        _tk = mt5.symbol_info_tick(_bs)
                        _si = mt5.symbol_info(_bs)
                        if not _tk or not (_tk.bid or _tk.ask):
                            rest.append(k); continue
                        _buy = (_dir == "BUY")
                        _ref = _tk.ask if _buy else _tk.bid
                        try:
                            _entry = float(k["entry"]); _sl = float(k["sl"])
                            _tp1   = float(k["tp1"])
                        except Exception:
                            continue
                        # Bewegung gelaufen oder Setup tot -> nicht hinterherspringen
                        if (_ref >= _tp1) if _buy else (_ref <= _tp1):
                            log.info("Nachholen verworfen: " + str(_bs) + " " + _dir +
                                     " TP1 " + str(_tp1) + " schon durchlaufen")
                            continue
                        if (_ref <= _sl) if _buy else (_ref >= _sl):
                            log.info("Nachholen verworfen: " + str(_bs) + " " + _dir +
                                     " SL " + str(_sl) + " beruehrt")
                            continue
                        _off = mt5.positions_get(symbol=_bs)
                        if _off and len(_off) > 0:
                            rest.append(k); continue
                        _pip = ((getattr(_si, "point", 0) or 0.01) * 10.0) if _si else 0.1
                        _gap = (abs(_entry - _ref) / _pip) if _pip else 99999.0
                        _adv = (_ref > _entry) if _buy else (_ref < _entry)
                        _fenster = _scalp_env("SCALP_ENTRY_MAX_PIPS",
                                              k.get("symbol") or "", "15")
                        if _adv and _fenster > 0 and _gap > _fenster:
                            rest.append(k); continue   # noch zu weit weg, weiter warten
                        log.info("Signal nachgeholt: " + str(_bs) + " " + _dir +
                                 " Entry " + str(_entry) + ", Kurs " +
                                 str(round(_ref, 5)) + " (" + str(round(_gap, 1)) +
                                 " Pips, " + str(round(_alter, 1)) + " Min nach dem Signal)")
                        try:
                            _sig = TradeSignal(
                                symbol=_bs, direction=_dir,
                                entry=_entry, sl=_sl,
                                tp1=k.get("tp1"), tp2=k.get("tp2"), tp3=k.get("tp3"),
                                tp4=k.get("tp4"), tp5=k.get("tp5"),
                                raw_text=k.get("raw_text") or "",
                                text_hash=str(k.get("hash") or ""),
                                source_channel=str(k.get("channel") or "nachgeholt"))
                            await process_signal(_sig)
                            await send_notification(
                                "\\u23ed Nachgeholt: " + str(_bs) + " " + _dir +
                                " Entry " + str(_entry) + " (" + str(round(_alter, 1)) +
                                " Min nach dem Signal)")
                        except Exception as _pe:
                            log.error("Nachholen fehlgeschlagen #" + str(_bs) +
                                      ": " + str(_pe))
                    if len(rest) != len(liste):
                        _nachhol_schreiben(rest)
            except Exception as _e:
                log.error("nachhol_watcher: " + str(_e))
            await asyncio.sleep(_poll)

    await asyncio.gather(
        user_client.run_until_disconnected(),
'''
if src.count(D_OLD) != 1:
    print("FEHLER Anker 4:", src.count(D_OLD)); sys.exit(1)
src = src.replace(D_OLD, D_NEW)

# ── 5. Loop registrieren ─────────────────────────────────────────────────
E_OLD = '        runner_breakeven_checker(),\n'
E_NEW = '        runner_breakeven_checker(),\n        nachhol_watcher(),\n'
if src.count(E_OLD) != 1:
    print("FEHLER Anker 5:", src.count(E_OLD)); sys.exit(1)
src = src.replace(E_OLD, E_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 44 OK - verworfene Signale werden nachgeholt")
