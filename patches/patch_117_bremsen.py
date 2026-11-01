#!/usr/bin/env python3
# patch_117_bremsen.py
#
# 1. Verlustserien-Bremse reparieren.
#    Ursache, warum sie bei vier Verlusten in Folge nie ausgeloest hat:
#    streak_tracker liest mt5.history_deals_get(). Dieser Broker liefert
#    darueber 0 Deals (DEALDIAG: total=0, last_error=(1,'Success')), der
#    Streak wurde also nie fortgeschrieben. Abschluesse werden jetzt daran
#    erkannt, dass ein verfolgtes Ticket aus positions_get verschwindet,
#    das Ergebnis kommt aus der Balanceaenderung.
# 2. Tages- und Wochenstop. Referenzbalance liegt in bremse.json, damit ein
#    Neustart die Messlatte nicht verschiebt. Beide Vorgaben 0 = aus.
import io, os, sys, py_compile

BOT = os.path.join(os.path.expanduser("~"), "teletrader", "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"


def sag(t):
    print("PATCH117 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "_periodenbremse" in src:
    sag("schon vorhanden - nichts zu tun")
    sys.exit(0)

# ------------------------------------------------- 1. Helfer am Modulanfang
ANKER0 = 'PAUSE_FLAG = "TRADING_PAUSED"'
HELFER = '''_pos_bekannt = {}      # PATCH117: Ticket -> letzter bekannter Floating-Gewinn
_bal_bekannt = [None]  # PATCH117: letzte bekannte Balance
BREMSE_FILE = "bremse.json"   # relativ zum CWD, wie runners.json


def _bremse_lesen():
    import json
    try:
        with open(BREMSE_FILE, "r", encoding="utf-8") as _f:
            _d = json.load(_f)
        return _d if isinstance(_d, dict) else {}
    except Exception:
        return {}


def _bremse_schreiben(_d):
    import json
    try:
        with open(BREMSE_FILE, "w", encoding="utf-8") as _f:
            json.dump(_d, _f)
    except Exception as _e:
        log.error("bremse.json schreiben: " + str(_e))


def _periodenbremse(_info):
    """PATCH117: Tages- und Wochenstop.

    Vergleicht die Equity mit der Startbalance des Tages bzw. der Woche.
    Reisst eine Grenze, wird der Handel pausiert; am naechsten Tag bzw. in
    der neuen Woche gibt die Bremse von selbst wieder frei - aber nur die
    Pause, die sie selbst gesetzt hat. Eine Pause per /pause bleibt stehen.
    Rueckgabe: Meldungstext oder None.
    """
    try:
        _tag_pct = float(os.getenv("TAGESSTOP_PCT", "0") or 0)
        _wo_pct = float(os.getenv("WOCHENSTOP_PCT", "0") or 0)
    except Exception:
        return None
    if _tag_pct <= 0 and _wo_pct <= 0:
        return None
    _jetzt = datetime.now()
    _tag = _jetzt.strftime("%Y-%m-%d")
    _woche = _jetzt.strftime("%G-KW%V")
    _d = _bremse_lesen()
    _bal = float(_info.balance)
    _eq = float(_info.equity)
    _neu = False
    _frei = []
    if _d.get("tag") != _tag:
        _d["tag"] = _tag
        _d["tag_start"] = _bal
        if _d.pop("tag_pause", False):
            _frei.append("Tagesstop")
        _neu = True
    if _d.get("woche") != _woche:
        _d["woche"] = _woche
        _d["woche_start"] = _bal
        if _d.pop("woche_pause", False):
            _frei.append("Wochenstop")
        _neu = True
    _meld = None
    if _frei and not _d.get("tag_pause") and not _d.get("woche_pause"):
        set_trading_paused(False)
        _meld = "\\u25b6 Neue Periode: " + "/".join(_frei) + " aufgehoben, Handel frei"
    if _meld is None and _tag_pct > 0 and not _d.get("tag_pause"):
        _grenze = float(_d.get("tag_start") or _bal) * (1.0 - _tag_pct)
        if _eq < _grenze:
            _d["tag_pause"] = True
            _neu = True
            set_trading_paused(True)
            _meld = ("\\u23f8 TAGESSTOP: Equity " + str(round(_eq, 2)) + " unter " +
                     str(round(_grenze, 2)) + " (" + str(int(_tag_pct * 100)) +
                     "% von " + str(round(float(_d.get("tag_start") or _bal), 2)) +
                     "). Handel bis morgen pausiert.")
    if _meld is None and _wo_pct > 0 and not _d.get("woche_pause"):
        _grenze = float(_d.get("woche_start") or _bal) * (1.0 - _wo_pct)
        if _eq < _grenze:
            _d["woche_pause"] = True
            _neu = True
            set_trading_paused(True)
            _meld = ("\\u23f8 WOCHENSTOP: Equity " + str(round(_eq, 2)) + " unter " +
                     str(round(_grenze, 2)) + " (" + str(int(_wo_pct * 100)) +
                     "% von " + str(round(float(_d.get("woche_start") or _bal), 2)) +
                     "). Handel bis naechste Woche pausiert.")
    if _neu:
        _bremse_schreiben(_d)
    return _meld


'''
if src.count(ANKER0) != 1:
    sag("FEHLER: Anker PAUSE_FLAG nicht eindeutig")
    sys.exit(1)
src = src.replace(ANKER0, HELFER + ANKER0, 1)
sag("Helfer _periodenbremse eingesetzt")

# ------------------------------------------------------- 2. Streak-Erkennung
A_STREAK = (
    "                cutoff = datetime.now() - timedelta(hours=24)\n"
    "                deals = mt5.history_deals_get(cutoff, datetime.now()) or []\n"
    "                for deal in deals:\n"
    "                    if deal.magic != MAGIC_NUMBER:\n"
    "                        continue\n"
    "                    if deal.entry != 1:  # entry=1 = OUT (Schließung)\n"
    "                        continue\n"
    "                    # Welchem Kanal gehört dieses Ticket?\n"
    "                    ch = None\n"
    "                    for channel, tickets in _channel_open_tickets.items():\n"
    "                        if deal.position_id in tickets:\n"
    "                            ch = channel\n"
    "                            tickets.discard(deal.position_id)\n"
    "                            break\n"
    "                    if not ch:\n"
    "                        continue\n"
    "                    # Ergebnis NICHT je Layer werten - ein Signal besteht aus\n"
    "                    # mehreren Layern und ergibt erst als Summe ein Resultat.\n"
    "                    _channel_batch_pnl[ch] = _channel_batch_pnl.get(ch, 0.0) + deal.profit\n"
)
N_STREAK = '''                # PATCH117: history_deals_get liefert bei diesem Broker 0
                # Deals, deshalb wurde der Streak nie fortgeschrieben und die
                # Bremse nie ausgeloest. Ein Abschluss ist jetzt daran zu
                # erkennen, dass ein verfolgtes Ticket aus positions_get
                # verschwindet; das Ergebnis kommt aus der Balanceaenderung.
                _ai = mt5.account_info()
                _bal = float(_ai.balance) if _ai else None
                _offen = {}
                for _p in (mt5.positions_get() or []):
                    if _p.magic == MAGIC_NUMBER:
                        _offen[int(_p.ticket)] = float(_p.profit)
                _weg = []
                for _ch2, _tks in list(_channel_open_tickets.items()):
                    for _tk in list(_tks):
                        if int(_tk) in _offen:
                            continue
                        _tks.discard(_tk)
                        if int(_tk) in _pos_bekannt or _bal is not None:
                            _weg.append((_ch2, int(_tk)))
                if _weg:
                    _delta = None
                    if _bal is not None and _bal_bekannt[0] is not None:
                        _delta = _bal - _bal_bekannt[0]
                    _summe = sum(abs(_pos_bekannt.get(_t, 0.0)) for _c, _t in _weg)
                    for _c, _t in _weg:
                        if _delta is not None and len(_weg) == 1:
                            _erg = _delta
                        elif _delta is not None and _summe > 0:
                            _erg = _delta * (abs(_pos_bekannt.get(_t, 0.0)) / _summe)
                        else:
                            _erg = _pos_bekannt.get(_t, 0.0)
                        # Ergebnis NICHT je Layer werten - ein Signal besteht
                        # aus mehreren Layern und ergibt erst als Summe eins.
                        _channel_batch_pnl[_c] = _channel_batch_pnl.get(_c, 0.0) + _erg
                        log.info("ABSCHLUSS #" + str(_t) + " " + str(_c)[:14] +
                                 " Ergebnis " + str(round(_erg, 2)))
                _pos_bekannt.clear()
                _pos_bekannt.update(_offen)
                if _bal is not None:
                    _bal_bekannt[0] = _bal
'''
if src.count(A_STREAK) != 1:
    sag("FEHLER: Anker streak_tracker nicht eindeutig (" +
        str(src.count(A_STREAK)) + ")")
    sys.exit(1)
src = src.replace(A_STREAK, N_STREAK, 1)
sag("Streak erkennt Abschluesse jetzt ueber positions_get und Balance")

# ------------------------------------------------- 3. Bremse im Guardian
A_EQ = "                equity    = info.equity"
N_EQ = ('                # PATCH117: Tages- und Wochenstop\n'
        '                try:\n'
        '                    _bm = _periodenbremse(info)\n'
        '                    if _bm:\n'
        '                        log.warning(_bm)\n'
        '                        await send_notification(_bm)\n'
        '                except Exception as _be:\n'
        '                    log.error("Periodenbremse: " + str(_be))\n'
        + A_EQ)
if src.count(A_EQ) != 1:
    sag("FEHLER: Anker equity nicht eindeutig")
    sys.exit(1)
src = src.replace(A_EQ, N_EQ, 1)
sag("Tages- und Wochenstop im Equity Guardian verankert")

# ----------------------------------------------------------------- schreiben
tmp = BOT + ".p117"
with io.open(tmp, "w", encoding="utf-8") as f:
    f.write(src)
try:
    py_compile.compile(tmp, cfile=tmp + "c", doraise=True)
except Exception as e:
    sag("FEHLER beim Compilieren: " + str(e))
    try:
        os.remove(tmp)
    except Exception:
        pass
    sys.exit(1)
try:
    os.remove(tmp + "c")
except Exception:
    pass
os.replace(tmp, BOT)
sag("fertig: Streak-Bremse reparierbar, TAGESSTOP_PCT/WOCHENSTOP_PCT verfuegbar")
