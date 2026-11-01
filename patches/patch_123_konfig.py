#!/usr/bin/env python3
# patch_123_konfig.py
# NO_RESTART - liest nur.
#
# Vor dem Scharfschalten einmal die komplette Handelskonfiguration sichtbar
# machen. Ausgegeben werden NUR die Schluessel aus der Liste unten, nie
# etwas anderes: Zugangsdaten und Tokens stehen nicht darin und koennen
# darum auch nicht versehentlich in das oeffentliche Repo rutschen.
import io, os, re, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
ENV = os.path.join(TT, ".env")
PUB = os.path.join(HOME, "ttpub")

ERLAUBT = [
    "DEMO_MODE", "AUTO_CONFIRM_LIVE", "MAX_LOGIN_FAILS",
    "LIVE_GOLD_SYMBOL", "LIVE_FX_SUFFIX", "LIVE_MT5_SERVER",
    "DEMO_GOLD_SYMBOL", "DEMO_MT5_SERVER", "MT5_TERMINAL_PATH",
    "MAX_LAYERS", "MAX_LAYERS_SCALPING", "MAX_LAYERS_XAUUSD",
    "MAX_LAYERS_GOLD", "MAX_LAYERS_BTC", "LAYERS_FIT_RISK",
    "RUNNER_ONLY", "RUNNER_LAYER_ENABLED", "RUNNER_LAYERS_SCALPING",
    "NO_RUNNER_CHANNELS", "RUNNER_BE_PCT", "RUNNER_FREI",
    "RUNNER_LEINE_AB_PIPS",
    "PARTIAL_GEWICHTE", "PARTIAL_LADDER", "PARTIAL_AT_TP",
    "PARTIAL_FRACTION", "PARTIAL_COOLDOWN_SEC",
    "MAX_POS_PER_SYMBOL", "MAX_RISK_PCT", "MAX_RISK_PCT_SCALPING",
    "MAX_RISK_PCT_GTMO", "MAX_TOTAL_HEAT_PCT", "MAX_LOT_PER_LAYER",
    "TARGET_RISK_PCT", "TARGET_RISK_PCT_XAUUSD", "TARGET_RISK_PCT_GOLD",
    "RISK_PER_100", "LOT_PER_100", "URGENT_LOT_PER_100",
    "LOSE_STREAK_LIMIT", "LOSE_STREAK_LIMIT_GOLD", "LOSE_STREAK_PAUSE_MIN",
    "LOSE_STREAK_GILT_AUCH_GTMO",
    "TAGESSTOP_PCT", "WOCHENSTOP_PCT", "EQUITY_GUARD_PCT", "AUTO_CLOSE_PCT",
    "TRADING_HOUR_START", "TRADING_HOUR_END", "TRADING_SYMBOLS",
    "NUR_SYMBOLE", "REGEX_ONLY_CHANNELS", "LLM_AKTIV",
    "LADDER_START_STAGE", "LADDER_MAX_STAGE", "LADDER_FORCE_CLOSE",
    "LADDER_POLL_SECONDS", "TP_AUS_MELDUNG",
    "TRAILING_STOP_ENABLED", "TRAILING_STOP_PIPS",
    "TRAILING_STOP_PIPS_XAUUSD", "TRAILING_STOP_MIN_PROFIT_PIPS",
    "TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD",
    "TRAIL_GIVEBACK_PCT", "TRAIL_MAX_PIPS", "TRAIL_USE_M1_PEAK",
    "SCALP_ENTRY_MAX_PIPS_XAUUSD", "SCALP_SL_MAX", "SCALP_SL_MAX_PCT",
    "SL_FACTOR", "SL_COOLDOWN_SECONDS", "MAGIC_NUMBER",
    "MESSE_RUECKSETZER", "MESSE_AB_PIPS", "PENDING_EXPIRY_HOURS",
]
_z = []


def sag(t):
    t = str(t)
    print("PATCH123 " + t)
    _z.append(t)


werte = {}
try:
    with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
        for ln in f:
            m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$",
                         ln.rstrip("\n"))
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            if k not in ERLAUBT:
                continue
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            if k in werte:
                werte[k] = werte[k] + " |doppelt| " + v
            else:
                werte[k] = v
except Exception as e:
    sag("env nicht lesbar: " + str(e))
    sys.exit(0)

_zeile = []
for k in ERLAUBT:
    if k in werte:
        _zeile.append(k + "=" + (werte[k] if werte[k] != "" else "(leer)"))
    # fehlende Schluessel weglassen, der Code hat dann seine Vorgabe
# in Haeppchen ausgeben, status.txt bleibt so lesbar
_puffer = ""
for t in _zeile:
    if len(_puffer) + len(t) > 180:
        sag(_puffer)
        _puffer = ""
    _puffer += (" " if _puffer else "") + t
if _puffer:
    sag(_puffer)
sag("nicht gesetzt: " + " ".join(k for k in ERLAUBT if k not in werte)[:400])

try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("KONFIG123 " + x + "\n")
except Exception:
    pass
