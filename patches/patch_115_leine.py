#!/usr/bin/env python3
# patch_115_leine.py
# Der Runner (Layer ohne eigenen TP) wird bis RUNNER_LEINE_AB_PIPS nur auf
# BE gesichert. Trail und SL-Leiter ziehen ihn vorher nicht nach.
#
# Grund: am 30.10. lief das Goldsignal bis +610 Pips weiter, unser Runner war
# bei +93 Pips schon draussen. Der Trail arbeitet mit 40 % Giveback vom Hoch,
# bei einem Hoch von 155 Pips sind das 62 Pips Leine - der Ruecksetzer war
# 76 Pips tief. Die Leiter haette ebenfalls ausgeloest (SL auf TP2 = 3981.51,
# Kurs kam bis 3981.95 zurueck). Nur ein BE-Stop haette die Bewegung gehalten.
# Genau so macht es der Signalgeber: nach TP1 SL auf BE, dann laufen lassen.
import io, os, sys, py_compile

BOT = os.path.join(os.path.expanduser("~"), "teletrader", "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"

def sag(t):
    print("PATCH115 " + t)

src = io.open(BOT, encoding="utf-8").read()
if "RUNNER_LEINE_AB_PIPS" in src:
    sag("schon vorhanden - nichts zu tun")
    sys.exit(0)

aend = 0

# ---------------------------------------------------------------- 1. Helfer
ANKER1 = "def _trail_breite(_basis_pips, _hoch_pips, _pip):"
HELFER = '''_leine_gemeldet = set()   # PATCH115: Tickets, fuer die die Leine schon gemeldet hat


def _runner_frei(_pos, _hoch_pips):
    """PATCH115: True, solange der Runner nur auf BE gesichert werden soll.

    Der Runner ist der Layer ohne eigenen TP. Trail (40 % Giveback) und
    SL-Leiter (ein TP hinterher) nehmen ihn regelmaessig bei 60-130 Pips aus
    Bewegungen heraus, die der Kanal bis 400-900 Pips laufen laesst. Unter
    RUNNER_LEINE_AB_PIPS bleibt sein Stop deshalb auf Entry stehen, darueber
    arbeiten Trail und Leiter wieder normal.
    RUNNER_FREI=false schaltet zurueck auf das alte Verhalten."""
    try:
        if os.getenv("RUNNER_FREI", "true").lower() != "true":
            return False
        if getattr(_pos, "tp", 0) and float(_pos.tp) > 0:
            return False          # Layer mit eigenem Ziel: unveraendert
        _ab = float(os.getenv("RUNNER_LEINE_AB_PIPS", "250"))
    except Exception:
        return False
    try:
        return float(_hoch_pips or 0.0) < _ab
    except Exception:
        return False


'''
if src.count(ANKER1) != 1:
    sag("FEHLER: Anker _trail_breite nicht eindeutig")
    sys.exit(1)
src = src.replace(ANKER1, HELFER + ANKER1, 1)
aend += 1
sag("Helfer _runner_frei eingesetzt")

# ------------------------------------------------------------- 2. Trail BUY
A_BUY = "                            new_sl = max(new_sl, round(pos.price_open, sym_info.digits))"
N_BUY = (A_BUY + "\n"
         "                            # PATCH115: Runner unterhalb der Schwelle nur BE\n"
         "                            if _runner_frei(pos,\n"
         "                                            (_ref - pos.price_open) / pip):\n"
         "                                new_sl = round(pos.price_open,\n"
         "                                               sym_info.digits)")
if src.count(A_BUY) != 1:
    sag("FEHLER: Anker Trail BUY nicht eindeutig")
    sys.exit(1)
src = src.replace(A_BUY, N_BUY, 1)
aend += 1

# ------------------------------------------------------------ 3. Trail SELL
A_SELL = "                            new_sl = min(new_sl, round(pos.price_open, sym_info.digits))"
N_SELL = (A_SELL + "\n"
          "                            # PATCH115: Runner unterhalb der Schwelle nur BE\n"
          "                            if _runner_frei(pos,\n"
          "                                            (pos.price_open - _ref) / pip):\n"
          "                                new_sl = round(pos.price_open,\n"
          "                                               sym_info.digits)")
if src.count(A_SELL) != 1:
    sag("FEHLER: Anker Trail SELL nicht eindeutig")
    sys.exit(1)
src = src.replace(A_SELL, N_SELL, 1)
aend += 1
sag("Trail zieht den Runner unter der Schwelle nicht mehr nach")

# ---------------------------------------------------------------- 4. Leiter
A_LEI = ("                    if _reached <= _stage_old or _reached < _lstart:\n"
         "                        continue\n")
N_LEI = (A_LEI +
         "                    # PATCH115: Der Runner bleibt bis zur Schwelle auf BE.\n"
         "                    # Eine Leiterstufe auf dem gerade durchlaufenen TP\n"
         "                    # holt ihn sonst beim naechsten Ruecksetzer heraus.\n"
         "                    if _reached > _lstart:\n"
         "                        try:\n"
         "                            _i2 = mt5.symbol_info(pos.symbol)\n"
         "                            _px = ((_i2.point if _i2 else 0.01) * 10) or 0.1\n"
         "                            _e2 = float(rec.get(\"entry\") or pos.price_open)\n"
         "                            _h2 = abs(float(_ext) - _e2) / _px\n"
         "                        except Exception:\n"
         "                            _h2 = None\n"
         "                        if _h2 is not None and _runner_frei(pos, _h2):\n"
         "                            if tk not in _leine_gemeldet:\n"
         "                                _leine_gemeldet.add(tk)\n"
         "                                if len(_leine_gemeldet) > 500:\n"
         "                                    _leine_gemeldet.clear()\n"
         "                                log.info(\"LEINE #\" + str(tk) + \" Runner \"\n"
         "                                         \"bleibt auf BE, Hoch \" +\n"
         "                                         str(round(_h2, 1)) + \"p < \" +\n"
         "                                         os.getenv(\n"
         "                                             \"RUNNER_LEINE_AB_PIPS\",\n"
         "                                             \"250\") + \"p\")\n"
         "                            continue\n")
if src.count(A_LEI) != 1:
    sag("FEHLER: Anker SL-Leiter nicht eindeutig")
    sys.exit(1)
src = src.replace(A_LEI, N_LEI, 1)
aend += 1
sag("SL-Leiter laesst den Runner unter der Schwelle auf BE stehen")

# ----------------------------------------------------------------- schreiben
tmp = BOT + ".p115"
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
sag("fertig, " + str(aend) + " Stellen geaendert, "
    "Schwelle RUNNER_LEINE_AB_PIPS=" +
    os.getenv("RUNNER_LEINE_AB_PIPS", "250") + " Pips")
