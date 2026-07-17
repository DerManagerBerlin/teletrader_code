"""
╔══════════════════════════════════════════════════════════╗
║           TeleTrader AI  –  Finale Version               ║
║   Telegram → Claude KI → MetaTrader 5                   ║
╠══════════════════════════════════════════════════════════╣
║  Features:                                               ║
║  ✅ 5 Kanäle überwachen (2 Signalgeber)                  ║
║  ✅ Duplikate per Text-Hash erkennen (60 Sek. Fenster)   ║
║  ✅ Cancellations erkennen & Order stornieren            ║
║  ✅ KI-Parser (erkennt jedes Signal-Format)              ║
║  ✅ Zinseszins Lotsize (1% pro $100 Kontostand)          ║
║  ✅ Layer-Aufteilung auf TPs (Rest immer zu TP1)         ║
║  ✅ Phasensystem (Phase 1/2/3 per Telegram-Befehl)       ║
║  ✅ Telegram-Bestätigung per Handy-Buttons               ║
║  ✅ Tägliche Zusammenfassung per Telegram                ║
║  ✅ Demo-Account Modus                                   ║
╚══════════════════════════════════════════════════════════╝

Setup:
  pip install telethon MetaTrader5 python-dotenv colorama anthropic
"""

import os
import re
import json
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
from telethon.tl.custom import Button
import MetaTrader5 as mt5
import httpx
from intelligent_interpreter_v2 import IntelligentInterpreterV2 as IntelligentInterpreter

def is_market_open(symbol: str) -> bool:
    """Prueft ob der Markt fuer das Symbol geoeffnet ist."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return False
    # trade_mode 0 = SYMBOL_TRADE_MODE_DISABLED (kein Handel)
    if info.trade_mode == 0:
        return False
    # Pruefen ob ein aktueller Bid/Ask vorhanden ist
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.bid == 0.0 or tick.ask == 0.0:
        return False
    return True

def resolve_symbol(symbol: str) -> str:
    """Loest ein Symbol auf eine in MT5 verfuegbare Variante auf."""
    info = mt5.symbol_info(symbol)
    if info is not None:
        return symbol
    base = symbol.split('.')[0]
    all_symbols = [s.name for s in mt5.symbols_get() or []]
    candidates = [s for s in all_symbols if s.startswith(base)]
    if not candidates:
        logging.error(f"Symbol {symbol} nicht gefunden in MT5. Keine Alternativen verfuegbar.")
        return symbol
    logging.error(f"Symbol {symbol} nicht gefunden in MT5. Verfuegbare Alternativen: {candidates}")
    preferred = [s for s in candidates if s.endswith('.s')]
    resolved = preferred[0] if preferred else candidates[0]
    logging.info(f"Symbol {symbol} automatisch ersetzt durch {resolved}")
    return resolved


def round_price(symbol: str, price: float) -> float:
    """Rundet einen Preis auf die erlaubte Tick-Groesse des Symbols."""
    if price is None or price == 0.0:
        return price
    symbol = resolve_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        return price
    digits = info.digits
    tick_size = info.trade_tick_size
    if tick_size and tick_size > 0.0:
        rounded = round(round(price / tick_size) * tick_size, digits)
    else:
        rounded = round(price, digits)
    return rounded
    if tick_size and tick_size > 0.0:
        price = round(round(price / tick_size) * tick_size, digits)
    else:
        price = round(price, digits)
    return price

# ─── Setup ───────────────────────────────────────────────────────────────────
load_dotenv()
colorama_init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("teletrader.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
# --- BEGIN token redaction (auto-added) ---
import os as _os_mask
import re as _re_mask

class _TokenRedactFilter(logging.Filter):
    _PAT = _re_mask.compile(r'bot(\d{6,12}):([A-Za-z0-9_-]{30,})')
    def __init__(self, secrets=None):
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]
    def _redact(self, text):
        for s in self._secrets:
            if s and s in text:
                text = text.replace(s, '***REDACTED***')
        text = self._PAT.sub(lambda m: 'bot' + m.group(1)[:5] + '...:REDACTED', text)
        return text
    def filter(self, record):
        try:
            msg = record.getMessage()
            red = self._redact(msg)
            if red != msg:
                record.msg = red
                record.args = ()
        except Exception:
            pass
        return True

_tok_filter = _TokenRedactFilter([_os_mask.environ.get(k, '') for k in
    ('TELEGRAM_BOT_TOKEN', 'BOT_TOKEN', 'TG_BOT_TOKEN', 'TELEGRAM_TOKEN', 'TELE_TOKEN')])
for _h in logging.getLogger().handlers:
    _h.addFilter(_tok_filter)
# logger-level token redaction (survives handler rebuilds)
for _lname in ('httpx', 'httpcore', 'telegram'):
    logging.getLogger(_lname).addFilter(_tok_filter)
logging.getLogger().addFilter(_tok_filter)
# --- END token redaction ---

log = logging.getLogger("TeleTrader")

# ─── Konfiguration (.env) ─────────────────────────────────────────────────────
# Telegram API
TG_API_ID        = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH      = os.getenv("TG_API_HASH", "")
TG_PHONE         = os.getenv("TG_PHONE", "")

# 5 Signal-Kanäle (Gruppenname oder @username)
TG_CHANNELS      = [
    os.getenv("TG_CHANNEL_1", ""),   # Signalgeber A – Kanal 1
    os.getenv("TG_CHANNEL_2", ""),   # Signalgeber A – Kanal 2
    os.getenv("TG_CHANNEL_3", ""),   # Signalgeber A – Kanal 3
    os.getenv("TG_CHANNEL_4", ""),   # Signalgeber B – Kanal 1
    os.getenv("TG_CHANNEL_5", ""),   # Signalgeber B – Kanal 2
]

# Dein persönlicher Telegram-Bot (für Bestätigungen & Befehle)
# Erstellen via @BotFather auf Telegram
TG_BOT_TOKEN     = os.getenv("TG_BOT_TOKEN", "")
TG_MY_CHAT_ID    = int(os.getenv("TG_MY_CHAT_ID", "0"))  # Deine Telegram User-ID

# MetaTrader 5 – dualer Account-Setup
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
if DEMO_MODE:
    MT5_LOGIN    = int(os.getenv("DEMO_MT5_LOGIN",  os.getenv("MT5_LOGIN", "0")))
    MT5_PASSWORD = os.getenv("DEMO_MT5_PASSWORD",   os.getenv("MT5_PASSWORD", ""))
    MT5_SERVER   = os.getenv("DEMO_MT5_SERVER",     os.getenv("MT5_SERVER", ""))
    GOLD_SYMBOL  = os.getenv("DEMO_GOLD_SYMBOL",    "XAUUSD.p")
    FX_SUFFIX    = os.getenv("DEMO_FX_SUFFIX",       ".p")
else:
    MT5_LOGIN    = int(os.getenv("LIVE_MT5_LOGIN",  "0"))
    MT5_PASSWORD = os.getenv("LIVE_MT5_PASSWORD",   "")
    MT5_SERVER   = os.getenv("LIVE_MT5_SERVER",     "")
    GOLD_SYMBOL  = os.getenv("LIVE_GOLD_SYMBOL",    "XAUUSD.s")
    FX_SUFFIX    = os.getenv("LIVE_FX_SUFFIX",       ".s")
BTC_SYMBOL = "BTCUSD"
TRAILING_STOP_ENABLED    = os.getenv("TRAILING_STOP_ENABLED", "false").lower() == "true"
TRAILING_STOP_PIPS       = float(os.getenv("TRAILING_STOP_PIPS", "20"))
# Text-Trigger fuer Teilgewinnmitnahme (Klartext des Kanals, unabhaengig von der KI-Action)
PARTIAL_TEXT_WORDS = [w.strip().lower() for w in os.getenv(
    "PARTIAL_TEXT_WORDS",
    "take some profit,take some more profit,take more profit,take profits,"
    "take half,half profits,take partial,more partials,can take partials,"
    "taking profits,take more partials").split(",") if w.strip()]
TRAILING_STOP_MIN_PROFIT = float(os.getenv("TRAILING_STOP_MIN_PROFIT_PIPS", "15"))

# KI-Interpreter (wird lazy initialisiert beim ersten Signal)
_interpreter = None  # type: IntelligentInterpreter

def get_interpreter():
    """Lazy-Init des KI-Interpreters."""
    global _interpreter
    if _interpreter is None:
        _interpreter = IntelligentInterpreter(
            api_key=ANTHROPIC_KEY,
            gold_symbol=GOLD_SYMBOL,
        )
    return _interpreter

# Claude API
ANTHROPIC_KEY    = (os.getenv("ANTHROPIC_API_KEY_V2") or
                    os.getenv("ANTHROPIC_API_KEY", ""))

# Trading Parameter
# Lot-Sizing: Kelly-Empfehlung
# Backtest-Werte: avg_win=$17.04, avg_loss=$13.85, win_rate=0.80
# Kelly = 0.80 - 0.20/1.23 = 63.7%
# 1/8-Kelly = 7.96% Risiko → ~14.5x aktuelles Lot → 0.15 Lot/$100
# Erhöhe schrittweise wenn Bot stabil läuft:
#   Konservativ (aktuell): KELLY_FRACTION=0.125 → 0.15 Lot/$100
#   Moderat:               KELLY_FRACTION=0.25  → 0.29 Lot/$100
#   Aggressiv:             KELLY_FRACTION=0.5   → 0.58 Lot/$100
# Lot-Sizing Stufenplan (Kelly-basiert, aus 7-Tage Backtest)
# Erhöhe stufenweise wenn Bot live stabil läuft:
#
# Phase 1 – Start Live (jetzt):   RISK_PER_100=0.03  → 3× konservativ  → ~+$243/Woche auf $1000
# Phase 2 – nach 1 Monat:         RISK_PER_100=0.07  → 7× konservativ  → ~+$567/Woche auf $1000
# Phase 3 – nach 3 Monaten:       RISK_PER_100=0.14  → 14× (1/8-Kelly) → ~+$1174/Woche auf $1000
# Phase 4 – nach 6 Monaten:       RISK_PER_100=0.29  → 29× (1/4-Kelly) → ~+$2348/Woche auf $1000
#
# Direkt anpassen: RISK_PER_100=0.03 in der .env Datei
RISK_PER_100     = float(os.getenv("RISK_PER_100", "0.03"))
MAX_POS_PER_SYM  = int(os.getenv("MAX_POS_PER_SYMBOL", "15"))  # Max Layer pro Symbol
MAX_LOT_PER_LAYER = float(os.getenv("MAX_LOT_PER_LAYER", "5.0"))  # Max Lot pro Layer (Broker-Limit)
PENDING_EXPIRY_H  = int(os.getenv("PENDING_EXPIRY_HOURS", "12"))   # Pending Orders nach X Stunden löschen
MAGIC_NUMBER       = int(os.getenv("MAGIC_NUMBER", "88888"))
MAX_POS_PER_SYMBOL = int(os.getenv("MAX_POS_PER_SYMBOL", "6"))
_channel_streak: dict = {}   # +1 pro Win, -1 pro SL, reset bei 0
_channel_open_tickets: dict = {}  # channel -> set of ticket numbers
_daily_audit: dict = {}            # channel -> {msgs, trades, noise, decisions}
DUPLICATE_WINDOW       = 900    # 15 Min Text-Hash-Duplikat
ENTRY_DUPLICATE_WINDOW = 21600  # 6 Std Entry-Preis-Duplikat
SL_COOLDOWN_SECONDS    = 7200   # 2 Std Cooldown nach SL-Hit
BACKUP_LOT_MULTIPLIER  = float(os.getenv("BACKUP_LOT_MULTIPLIER", "2.0"))
TRADING_HOUR_START     = int(os.getenv("TRADING_HOUR_START", "6"))   # 06:00
LIMIT_BUFFER_PIPS      = float(os.getenv("LIMIT_BUFFER_PIPS", "0.5"))  # Buffer fuer Limit-Orders
TRADING_HOUR_END       = int(os.getenv("TRADING_HOUR_END",   "20"))  # 20:00

# ─── Globaler State ───────────────────────────────────────────────────────────
class BotState:
    def __init__(self):
        self.phase             = 3
        self.seen_hashes       = {}
        self.pending_signals   = {}
        self.open_orders       = {}
        self.pending_context   = {}
        self.tp_layers         = {}
        self.channel_history   = {}
        self.MAX_HISTORY       = 5
        self.CONTEXT_WINDOW    = int(os.getenv("URGENT_ATTACH_WINDOW", "120"))
        self.daily_stats       = {"trades": 0, "cancelled": 0, "skipped": 0, "profit": 0.0}
        self.last_partial      = {}   # channel -> timestamp letzter Teilschluss
        self.last_summary_date = ""
        self.symbol_owner      = {}
        self.sl_cooldowns      = {}
        self.seen_entries      = {}
        self.pending_be        = {}  # symbol → True
state = BotState()

# ─── Kanal-Prioritäten ───────────────────────────────────────────────────────
# 1 = höchste Priorität (TFXC)
# 2 = mittlere Priorität (GTMo)
# 3 = niedrigste Priorität (GHP / Goldhunter)
# Wenn ein Kanal mit höherer Priorität signalisiert und ein niedrigerer aktiv
# ist, werden die niedrigeren Positionen automatisch geschlossen.

def get_channel_priority(channel_name: str) -> int:
    """Gibt Priorität 1-3 zurück. 1 = höchste."""
    name = channel_name.lower()
    if "tfxc" in name:
        return 1
    if "gtmo" in name or "goldtradermo" in name:
        return 2
    if "ghp" in name or "goldhunter" in name or "jackpot" in name or "paul" in name:
        return 3
    return 2  # unbekannte Kanäle = mittlere Priorität


async def check_channel_permission(channel_name: str, symbol: str) -> bool:
    """
    Prueft ob ein Kanal auf diesem Symbol traden darf.
    Prioritaet 1 (TFXC) > 2 (GTMo) > 3 (GHP).
    Hoehere Prioritaet schliesst niedrigere Positionen und uebernimmt.
    Niedrigere Prioritaet wird blockiert solange hoehere aktiv ist.
    """
    new_prio = get_channel_priority(channel_name)
    positions = mt5.positions_get(symbol=symbol)
    our_pos   = [p for p in (positions or []) if p.magic == MAGIC_NUMBER]

    if not our_pos:
        state.symbol_owner[symbol] = channel_name
        return True

    existing_channel = state.symbol_owner.get(symbol, "")
    existing_prio    = get_channel_priority(existing_channel) if existing_channel else 99

    if new_prio < existing_prio:
        log.info("Prioritaet-Override: " + channel_name + "(P" + str(new_prio) +
                 ") uebernimmt von " + (existing_channel or "?") + "(P" + str(existing_prio) +
                 ") auf " + symbol)
        closed = close_positions_by_channel(existing_channel or "override", symbol)
        state.symbol_owner[symbol] = channel_name
        notif = (channel_name + " (P" + str(new_prio) + ") uebernimmt " + symbol +
                 " | " + str(closed) + " Positionen geschlossen")
        await send_notification(notif)
        return True

    elif new_prio == existing_prio:
        return True

    else:
        log.info("Blockiert: " + channel_name + "(P" + str(new_prio) +
                 ") – " + (existing_channel or "?") + "(P" + str(existing_prio) +
                 ") ist aktiv auf " + symbol)
        notif = ("Blockiert: " + channel_name + " | " +
                 (existing_channel or "?") + " hat Prioritaet auf " + symbol)
        await send_notification(notif)
        return False


# ─── Signal Datenklasse ───────────────────────────────────────────────────────
@dataclass
class TradeSignal:
    symbol: str
    direction: str
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    tp4: Optional[float] = None
    tp5: Optional[float] = None
    tp6: Optional[float] = None
    is_limit: bool = False   # True = Pending Limit Order
    is_backup: bool = False  # True = GHP Backup/Recovery (2x Lot)
    entry_low: float = 0.0   # Untere Zone-Grenze (z.B. 4172 bei Zone 4172-4177)
    small_lot: bool  = False  # True wenn Kanal "high volatile / use small lot" warnt
    raw_text: str = ""
    text_hash: str = ""
    source_channel: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    def tps(self) -> list:
        """Gibt alle gesetzten TPs als Liste zurück"""
        return [tp for tp in [self.tp1, self.tp2, self.tp3, self.tp4, self.tp5, self.tp6] if tp is not None]

    def is_valid(self) -> bool:
        # SL alleine reicht – TP kann als Folgenachricht kommen
        return (
            self.symbol is not None and
            self.direction in ("BUY", "SELL") and
            self.sl is not None
        )

    def risk_pips(self) -> float:
        if self.entry and self.sl:
            return abs(self.entry - self.sl)
        return 0.0

    def reward_pips(self) -> float:
        if self.entry and self.tp1:
            return abs(self.tp1 - self.entry)
        return 0.0

    def rr_ratio(self) -> str:
        r = self.risk_pips()
        if r == 0:
            return "N/A"
        return f"1 : {(self.reward_pips() / r):.2f}"


# ─── Lotsize & Layer Berechnung ───────────────────────────────────────────────


def calculate_layers(balance: float, channel: str = "", is_backup: bool = False) -> tuple[int, float]:
    """
    Lot-Sizing: fest 0.01 Lot pro $100, maximal 3 Layer.
    Ziel: 3 Layer zu je ~$1 Risiko auf $100 Konto.

    Beispiele:
      $100  → 3 Layer × 0.01 lot
      $500  → 3 Layer × 0.05 lot
      $1000 → 3 Layer × 0.10 lot
    """
    LOT_PER_100 = float(os.getenv("LOT_PER_100", "0.01"))
    MAX_LAYERS  = int(os.getenv("MAX_LAYERS", "6"))

    # Festes Lot pro Layer basierend auf Balance
    lot_per_layer = round(max(0.01, min(LOT_PER_100 * (balance / 100),
                                        MAX_LOT_PER_LAYER)), 2)
    # Anzahl Layer wird von aussen übergeben (default MAX_LAYERS)
    num_layers = MAX_LAYERS

    # GHP Backup → doppelter Einsatz
    ch_lower = channel.lower()
    is_ghp = any(x in ch_lower for x in ("ghp", "goldhunter", "jackpot", "paul"))
    if is_ghp and is_backup:
        lot_per_layer = round(min(lot_per_layer * BACKUP_LOT_MULTIPLIER, MAX_LOT_PER_LAYER), 2)
        log.info("GHP Backup-Lot: " + str(lot_per_layer) + " (2x Standard)")
    elif is_backup and not is_ghp:
        log.info("Backup-Flag ignoriert: nur GHP erhaelt doppeltes Lot")

    log.info("Lot-Sizing: Balance=" + str(round(balance, 0)) + "$" +
             "  Lot=" + str(lot_per_layer) + "  Kanal=" + str(channel[:12]))
    return num_layers, lot_per_layer

def distribute_layers(num_layers: int, tps: list, channel: str = "") -> dict:
    """
    Verteilt Layer auf TPs.
    Letzter Layer läuft IMMER offen (TP=0) – wird durch Breakeven/Trailing gesichert.
    So profitieren wir maximal wenn der Trend weiterläuft.

    Beispiele (3 Layer, 2 TPs):
      → TP1:1, TP2:1, OPEN:1

    Beispiele (3 Layer, 1 TP):
      → TP1:1, OPEN:2   (oder TP1:2, OPEN:1)

    Beispiele (3 Layer, 0 TPs):
      → OPEN:3
    """
    num_tps = len(tps)

    # Runner-Layer (TP=0) nur wenn RUNNER_LAYER_ENABLED=true; sonst alle Layer mit hartem TP
    open_layers    = 1 if os.getenv("RUNNER_LAYER_ENABLED", "false").lower() == "true" else 0
    if "tfxc" in (channel or "").lower():
        open_layers = 0  # TFXC: kein Runner - alle Layer feste TPs
    # (b) Runner nur als ZUSAETZLICHER Layer: bei vorhandenen TPs behaelt mind. 1
    # Layer einen TP (kein TP-loser Runner bei auf 1 gekapptem Kleinkonto-Trade).
    if num_tps > 0:
        open_layers = min(open_layers, max(0, num_layers - 1))
    layers_for_tps = num_layers - open_layers

    if num_tps == 0 or layers_for_tps <= 0:
        return {0: num_layers}

    # Wenn mehr TPs als verfügbare Layer: nur die ersten verwenden
    if num_tps >= layers_for_tps:
        dist = {tp: 1 for tp in tps[:layers_for_tps]}
        if open_layers:
            dist[0] = open_layers   # 0 = kein TP (offen)
        return dist

    # Jedes TP bekommt mindestens 1 Layer, Rest absteigend verteilt
    # Erst jedem TP einen Layer geben
    distribution = {tp: 1 for tp in tps}
    remaining = layers_for_tps - num_tps  # nur TP-Layer verteilen (Runner separat)

    # Rest absteigend auf die ersten TPs verteilen (nähere Ziele bevorzugt)
    i = 0
    while remaining > 0:
        distribution[tps[i % num_tps]] += 1
        remaining -= 1
        i += 1

    if open_layers:
        distribution[0] = open_layers   # zusaetzlicher Runner-Layer (TP=0)

    return distribution


# ─── Regex Signal Parser (kein API-Key nötig) ────────────────────────────────
# Sobald Anthropic-Guthaben vorhanden → auf KI-Parser umstellen

def _fx(pair):
    """Gibt das Broker-Symbol fuer ein Forex-Paar zurueck."""
    return pair.upper() + FX_SUFFIX


def resolve_symbol(raw: str) -> str:
    """Wandelt KI-Symbol (z.B. EURAUD) in MT5-Symbol (EURAUD.s) um.
    Fallback: 6-Buchstaben Forex-Paar bekommt automatisch FX_SUFFIX.
    """
    if not raw:
        return ""
    key = raw.lower().replace("/", "").replace(" ", "")
    if key in SYMBOL_MAP and SYMBOL_MAP[key]:
        return SYMBOL_MAP[key]
    # Automatischer Fallback fuer unbekannte Paare
    clean = raw.upper().replace("/", "").replace(" ", "")
    if 6 <= len(clean) <= 8 and clean.replace(".", "").isalpha():
        result = clean if "." in clean else clean + FX_SUFFIX
        log.info("Symbol auto-resolved: " + raw + " → " + result)
        return result
    return raw.upper()

# Alle bekannten Forex-Paare (Majors + Crosses)
_FOREX_PAIRS = [
    # Majors
    "eurusd", "gbpusd", "usdjpy", "usdchf", "audusd", "nzdusd", "usdcad",
    # EUR Crosses
    "eurgbp", "eurjpy", "eurcad", "euraud", "eurchf", "eurnzd",
    # GBP Crosses
    "gbpjpy", "gbpcad", "gbpaud", "gbpchf", "gbpnzd",
    # AUD Crosses
    "audjpy", "audcad", "audchf", "audnzd",
    # NZD Crosses
    "nzdjpy", "nzdcad", "nzdchf",
    # CAD/CHF Crosses
    "cadjpy", "cadchf", "chfjpy",
]

SYMBOL_MAP = {
    # Gold
    "gold": GOLD_SYMBOL, "xau": GOLD_SYMBOL, "xauusd": GOLD_SYMBOL,
    # Silver
    "silver": _fx("xagusd"), "xag": _fx("xagusd"), "xagusd": _fx("xagusd"),
    # Crypto
    "btc": BTC_SYMBOL, "bitcoin": BTC_SYMBOL, "btcusd": BTC_SYMBOL,
    # Alle Forex-Paare automatisch
    **{pair: _fx(pair) for pair in _FOREX_PAIRS},
    **{pair[:3] + "/" + pair[3:]: _fx(pair) for pair in _FOREX_PAIRS},
    # Slang-Bezeichnungen
    "cable": _fx("gbpusd"), "fiber": _fx("eurusd"), "aussie": _fx("audusd"),
    "kiwi":  _fx("nzdusd"), "loonie": _fx("usdcad"), "swissy": _fx("usdchf"),
    "guppy": _fx("gbpjpy"), "ninja": _fx("usdjpy"),
    # Indices
    "nasdaq": None, "nas100": None, "nas": None,
    "us30": None, "dow": None, "dj30": None,
    # Rohstoffe
    "oil": None, "wti": None, "usoil": None,
}

CANCEL_WORDS   = ["cancel", "cancelled", "void", "ignore", "invalidate", "abort"]

# "close" alleine reicht NICHT – braucht Kontext oder steht alleine als einziges Wort
# Verhindert False Positives wie "close to resistance", "close watch", "we are close"
CLOSE_WORDS_STRONG = [
    "close now", "close all", "close position", "close trade",
    "close sell", "close buy", "exit now", "exit immediately",
    "get out now", "close everything", "close it",
]
# "close" alleine nur als einziges Wort in der Nachricht (max 3 Wörter gesamt)
CLOSE_WORD_SOLO = "close"


def is_close_signal(text: str) -> bool:
    """
    Erkennt echte Close-Befehle und vermeidet False Positives.
    'close to resistance', 'close watch', 'we are close' → False
    'close', 'close now', 'close all', 'close sell' → True
    """
    tl = text.lower().strip()
    words = tl.split()

    # Starke Phrasen – immer True
    if any(phrase in tl for phrase in CLOSE_WORDS_STRONG):
        return True

    # "close" als einziges oder fast einziges Wort (max 2 Wörter)
    if CLOSE_WORD_SOLO in words and len(words) <= 2:
        return True

    # "close" gefolgt von Symbol oder Richtung
    if re.search(r"\bclose\b.{0,20}\b(gold|xauusd|btc|bitcoin|buy|sell|long|short)\b", tl):
        return True

    # Ausschlussliste – harmlose Verwendungen
    FALSE_POSITIVES = [
        "close to", "getting close", "very close", "so close",
        "close watch", "closely", "close eye", "closed market",
        "close range", "market close", "closing time", "close resistance",
        "close support", "close level",
    ]
    if any(fp in tl for fp in FALSE_POSITIVES):
        return False

    return False

BREAKEVEN_WORDS = ["move sl to be", "sl to be", "set breakeven", "breakeven now",
                   "move to breakeven", "break even now", "sl to breakeven",
                   "move sl to breakeven", "set sl to be", "be now"]

# "Move SL to 4718.2" / "update sl to 79500" / "change sl to 79500"
SL_MOVE_PATTERN = re.compile(
    r"(?:move sl|set sl|update sl|change sl|sl) to ([\d]+\.?[\d]*)",
    re.IGNORECASE
)

# "move tp to 82000" / "change tp1 to 82000" / "tp1 to 82000"
# Group 1 = tp number (optional), Group 2 = price
TP_MOVE_PATTERN = re.compile(
    r"(?:move\s+tp(\d?)|set\s+tp(\d?)|update\s+tp(\d?)|change\s+tp(\d?)|tp(\d?))\s+to\s+([\d]+\.?[\d]*)",
    re.IGNORECASE
)

# Urgent-Signal Patterns: "buy gold now", "sell btc now", "long gold" etc.
# Kein SL/TP – Bot wartet 30 Sek. auf Folgenachricht
URGENT_PATTERNS = [
    r"(buy|long)\s+(gold|xauusd|xau)(\s|$|!|\.)",
    r"(sell|short)\s+(gold|xauusd|xau)(\s|$|!|\.)",
    r"(buy|long)\s+(btc|bitcoin|btcusd)(\s|$|!|\.)",
    r"(sell|short)\s+(btc|bitcoin|btcusd)(\s|$|!|\.)",
    r"(gold|xauusd)\s+(buy|long|sell|short)(\s|$|!|\.)",
    r"(btc|bitcoin)\s+(buy|long|sell|short)(\s|$|!|\.)",
]

URGENT_SYMBOL_MAP = {
    "gold": GOLD_SYMBOL, "xauusd": GOLD_SYMBOL, "xau": GOLD_SYMBOL,
    "btc": BTC_SYMBOL, "bitcoin": BTC_SYMBOL, "btcusd": BTC_SYMBOL,
}

# "buy now" / "sell now" ohne Symbol → immer Gold
URGENT_NOW_PATTERNS = [
    r"^(buy|long)\s*now[!.]?$",
    r"^(sell|short)\s*now[!.]?$",
    r"^(buy|long)[!.]?$",
    r"^(sell|short)[!.]?$",
]


def detect_urgent_signal(text: str) -> dict | None:
    """
    Erkennt kurze Urgent-Signale wie 'buy gold now' oder 'sell BTC immediately'.
    "buy now" / "sell now" ohne Symbol → immer Gold (XAUUSD.p).
    Gibt {symbol, direction} zurück oder None.
    """
    text_lower = text.lower().strip()

    # Muss kurz sein (max 8 Wörter) – lange Nachrichten sind keine Urgent-Signale
    if len(text_lower.split()) > 8:
        return None

    # "buy now" / "sell now" ohne Symbol → Gold
    for pattern in URGENT_NOW_PATTERNS:
        m = re.match(pattern, text_lower)
        if m:
            direction = "BUY" if m.group(1) in ("buy", "long") else "SELL"
            return {"symbol": GOLD_SYMBOL, "direction": direction}

    # Kontextprüfung: "buy" / "sell" nur als echte Order-Wörter erkennen
    # False Positives: "good to buy", "I would sell", "buy the dip eventually"
    FALSE_BUY_SELL = [
        "would buy", "would sell", "could buy", "could sell",
        "might buy", "might sell", "should buy", "should sell",
        "good to buy", "good to sell", "good buy", "level to buy",
        "level to sell", "looking to buy", "looking to sell",
        "want to buy", "want to sell", "thinking of buying",
        "thinking of selling", "buy the dip", "sell the rally",
        "buy zone", "sell zone", "buy area", "sell area",
        "buy signal", "sell signal", "buy side", "sell side",
        "buy pressure", "sell pressure", "buy limit", "sell limit",
        "buyers", "sellers", "buying pressure", "selling pressure",
        "buy opportunity", "potential buy", "potential sell",
    ]
    if any(fp in text_lower for fp in FALSE_BUY_SELL):
        return None

    for pattern in URGENT_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            groups = [g for g in m.groups() if g]
            direction = None
            symbol = None
            for g in groups:
                if g in ("buy", "long"):
                    direction = "BUY"
                elif g in ("sell", "short"):
                    direction = "SELL"
                elif g in URGENT_SYMBOL_MAP:
                    symbol = URGENT_SYMBOL_MAP[g]
            if symbol and direction:
                return {"symbol": symbol, "direction": direction}
    return None


def is_plausible_price(val: float, symbol: str) -> bool:
    """Prüft ob ein Zahlenwert ein plausibler Preis für das Symbol ist."""
    if symbol == GOLD_SYMBOL:
        return 3000 <= val <= 6000   # Gold: 3000-6000
    elif symbol == BTC_SYMBOL:
        return 20000 <= val <= 200000  # BTC: 20k-200k
    return val > 100  # Fallback


def extract_levels(text: str, ctx_symbol: str = None) -> dict:
    """
    Extrahiert SL/TP/Entry aus einer Folgenachricht – auch ohne Labels.

    Relevanzprüfung: Zahlen im plausiblen Preisbereich des Symbols
    werden als potenzielle SL/TP erkannt, auch wenn kein Label dabei steht.

    Beispiele:
      "SL 4710"           → sl=4710
      "SL: 4710"          → sl=4710
      "TP 4740"           → tp1=4740
      "4740"              → tp1=4740 (Relevanzprüfung)
      "TP 4700 4720 4740" → tp1=4700 tp2=4720 tp3=4740
      "TP 4688-86-777"    → tp1=4688 tp2=4686 tp3=4777
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    sl = entry = None
    tp_values = []
    unlabeled_values = []  # Zahlen ohne Label

    for i, line in enumerate(lines):
        ll = line.lower()
        nums = re.findall(r"\d+\.?\d*", line)
        if not nums:
            continue

        has_sl_label  = bool(re.search(r"\bss?l\b|stop.?loss", ll))
        has_tp_label  = bool(re.search(r"\btp\d?\b|take.?profit|target", ll))
        has_ent_label = bool(re.search(r"\bentry\b|\bat\b", ll))

        if has_sl_label:
            vals = [float(n) for n in nums if float(n) > 100]
            if vals:
                sl = vals[0]
            elif i + 1 < len(lines):
                next_nums = re.findall(r"\d+\.?\d*", lines[i+1])
                if next_nums:
                    sl = float(next_nums[0])

        elif has_tp_label:
            raw = re.sub(r"tp\d?\s*:?\s*|take.?profit\s*:?\s*|target\s*:?\s*", "", ll)
            parts = re.split(r"[\s/\-]+", raw.strip())
            base = None
            for p in parts:
                n = re.findall(r"\d+\.?\d*", p.strip())
                if n:
                    val_str = n[0]
                    if base and len(val_str) < len(str(int(base))):
                        prefix = str(int(base))[:-len(val_str)]
                        val = float(prefix + val_str)
                    else:
                        val = float(val_str)
                    if val > 100:
                        base = val
                        tp_values.append(val)

        elif has_ent_label:
            slash = re.search(r"(\d{4,5})/(\d{1,5})", line)
            if slash:
                a = float(slash.group(1))
                b_raw = slash.group(2)
                if len(b_raw) < len(str(int(a))):
                    prefix = str(int(a))[:-len(b_raw)]
                    b = float(prefix + b_raw)
                else:
                    b = float(b_raw)
                entry = round((a + b) / 2, 2)
            else:
                vals = [float(n) for n in nums if float(n) > 100]
                if vals:
                    entry = vals[0]

        else:
            # Kein Label – Relevanzprüfung: ist die Zahl ein plausibler Preis?
            for n in nums:
                val = float(n)
                if ctx_symbol:
                    if is_plausible_price(val, ctx_symbol):
                        unlabeled_values.append(val)
                elif val > 100:
                    unlabeled_values.append(val)

    # Unbeschriftete plausible Zahlen: erste = TP wenn noch kein TP, zweite = weitere TPs
    if unlabeled_values and not tp_values and not sl:
        tp_values = unlabeled_values[:3]

    return {
        "sl":    sl,
        "entry": entry,
        "tp1":   tp_values[0] if len(tp_values) > 0 else None,
        "tp2":   tp_values[1] if len(tp_values) > 1 else None,
        "tp3":   tp_values[2] if len(tp_values) > 2 else None,
    }


async def parse_message_ai(text: str) -> dict:
    """
    Verbesserter Parser – versteht alle echten Signal-Formate.
    Erkennt: multi-TP in einer Zeile, Schrägstrich-Ranges, Verneinungen,
    hold-lowest, big buy at, TP mit Bindestrichen etc.
    """
    text_lower = text.lower()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # ── Verneinung prüfen (früh, vor allem anderen) ───────────────────────
    NEGATIONS = ["don't sell", "dont sell", "don't buy", "dont buy",
                 "do not sell", "do not buy", "not selling", "not buying",
                 "no sell", "no buy", "we don't", "we dont"]
    if any(n in text_lower for n in NEGATIONS):
        return {"is_signal": False, "is_cancel": False,
                "reason": "Verneinung erkannt – kein Signal"}

    # ── Hold Lowest Layer ─────────────────────────────────────────────────
    HOLD_LOWEST_WORDS = ["hold lowest layer", "hold only lowest", "keep lowest layer",
                         "hold lowest at", "close some profit", "close some profits",
                         "take half", "take partial", "secure profit", "secure some",
                         "lock profit", "lock in profit", "close first entries",
                         "tp1 hit", "tp2 hit", "first target hit", "target 1 hit"]
    if any(w in text_lower for w in HOLD_LOWEST_WORDS):
        return {"is_signal": False, "is_cancel": False,
                "is_hold_lowest": True,
                "reason": "Hold-lowest erkannt"}

    # ── Breakeven ─────────────────────────────────────────────────────────
    if any(w in text_lower for w in BREAKEVEN_WORDS):
        return {"is_signal": False, "is_cancel": False,
                "is_breakeven": True,
                "reason": "Breakeven erkannt"}

    # ── Cancel ────────────────────────────────────────────────────────────
    if any(word in text_lower for word in CANCEL_WORDS):
        return {"is_signal": False, "is_cancel": True,
                "cancel_reason": "Cancel-Wort erkannt"}

    # ── Close ─────────────────────────────────────────────────────────────
    if is_close_signal(text):
        # Richtungsumkehr: "we sell higher" = schließe aktuelle BUY Position
        direction_flip = None
        if "we sell" in text_lower or "sell higher" in text_lower:
            direction_flip = "BUY"   # schließe BUYs
        elif "we buy" in text_lower or "buy lower" in text_lower:
            direction_flip = "SELL"  # schließe SELLs
        return {"is_signal": False, "is_cancel": False, "is_close": True,
                "cancel_direction": direction_flip,
                "reason": "Close-Now erkannt"}

    # ── Symbol erkennen ───────────────────────────────────────────────────
    ALLOWED_SYMBOLS = {GOLD_SYMBOL, BTC_SYMBOL}
    symbol = None
    for key, val in SYMBOL_MAP.items():
        if key in text_lower and val in ALLOWED_SYMBOLS:
            symbol = val
            break

    if not symbol:
        return {"is_signal": False, "is_cancel": False}

    # ── Richtung erkennen ─────────────────────────────────────────────────
    direction = None
    if any(w in text_lower for w in ["buy", "long", "big buy", "🟢", "⬆"]):
        direction = "BUY"
    elif any(w in text_lower for w in ["sell", "short", "🔴", "⬇"]):
        direction = "SELL"

    if not direction:
        return {"is_signal": False, "is_cancel": False}

    # ── Preise extrahieren ────────────────────────────────────────────────
    entry = sl = None
    tp_values = []

    for line in lines:
        ll = line.lower()

        # SL erkennen
        if re.search(r"\bss?l\b|stop.?loss|stoploss", ll):
            nums = re.findall(r"[\d]+\.?[\d]*", line)
            if nums:
                sl = float(nums[0])
            continue

        # Entry erkennen (inkl. Schrägstrich-Range: 4686/87 → 4686.5)
        if re.search(r"\bentry\b|\benter\b|\bat\b", ll):
            slash_match = re.search(r"(\d{4,5})/(\d{1,5})", line)
            if slash_match:
                a = float(slash_match.group(1))
                b_raw = slash_match.group(2)
                # "4686/87" → b = 4687 (prefix completion)
                if len(b_raw) < len(str(int(a))):
                    prefix = str(int(a))[:-len(b_raw)]
                    b = float(prefix + b_raw)
                else:
                    b = float(b_raw)
                entry = round((a + b) / 2, 2)
            else:
                nums = re.findall(r"[\d]+\.?[\d]*", line)
                if nums:
                    entry = float(nums[0])
            continue

        # TP erkennen – mehrere Formate:
        if re.search(r"\btp\b|take.?profit|target", ll):
            # Format 1: "TP 4688-86-777" → Bindestriche als Trennzeichen
            # Format 2: "TP 4700 4720 4740" → Leerzeichen
            # Format 3: "TP 4688/86/777" → Schrägstriche
            raw_tp = re.sub(r"(tp\d?\s*:?\s*|take.?profit\s*:?\s*|target\s*:?\s*)", "", ll)

            # Slash-getrennte TPs
            slash_parts = re.split(r"[/]", raw_tp.strip())
            if len(slash_parts) > 1:
                base = None
                for part in slash_parts:
                    part = part.strip()
                    nums = re.findall(r"[\d]+\.?[\d]*", part)
                    if nums:
                        val_str = nums[0]
                        if base and len(val_str) < len(str(int(base))):
                            prefix = str(int(base))[:-len(val_str)]
                            val = float(prefix + val_str)
                        else:
                            val = float(val_str)
                        base = val
                        tp_values.append(val)
            else:
                # Bindestrich-getrennte TPs mit Präfix-Completion: "4688-86-777"
                dash_parts = re.split(r"[-]", raw_tp.strip())
                if len(dash_parts) > 1:
                    base = None
                    for part in dash_parts:
                        part = part.strip()
                        nums = re.findall(r"[\d]+\.?[\d]*", part)
                        if nums:
                            val_str = nums[0]
                            if base and len(val_str) < len(str(int(base))):
                                prefix = str(int(base))[:-len(val_str)]
                                val = float(prefix + val_str)
                            else:
                                val = float(val_str)
                            base = val
                            tp_values.append(val)
                else:
                    # Leerzeichen-getrennte TPs
                    nums = re.findall(r"[\d]+\.?[\d]*", line)
                    for n in nums:
                        if float(n) > 100:  # Filtere kleine Zahlen (TP-Nummern wie 1,2,3)
                            tp_values.append(float(n))
            continue

        # Standalone SL-Zeile: nur eine Zahl, kein Keyword, aber nach "SL" Label
        # z.B. "SL 4747.5" bereits abgedeckt, aber auch "4747.5" allein wenn vorher SL-Zeile kam
        # → handled oben

    # ── Auch SL als einzelne Zeile erkennen (nur Zahl nach "SL" Headline) ─
    for i, line in enumerate(lines):
        ll = line.lower().strip()
        if ll in ("sl", "stop loss", "stop"):
            # Nächste Zeile ist der Wert
            if i + 1 < len(lines):
                nums = re.findall(r"[\d]+\.?[\d]*", lines[i+1])
                if nums and not sl:
                    sl = float(nums[0])

    # ── "TP: open" erkennen → letzte Layer ohne TP lassen ───────────────────
    has_open_tp = bool(re.search(r"tp\s*:?\s*open", text_lower))

    # ── "Move SL to 4718.2" → konkreter SL-Wert (kein Breakeven) ────────────
    sl_move_match = SL_MOVE_PATTERN.search(text)
    if sl_move_match and not sl:
        sl = float(sl_move_match.group(1))

    tp1 = tp_values[0] if len(tp_values) > 0 else None
    tp2 = tp_values[1] if len(tp_values) > 1 else None
    tp3 = tp_values[2] if len(tp_values) > 2 else None

    # Wenn TP: open → tp3 (oder tp2 wenn nur 2 TPs) auf None setzen
    # Die letzte Layer läuft ohne TP
    if has_open_tp and tp3:
        tp3 = None   # letzte Layer offen lassen
    elif has_open_tp and tp2:
        tp2 = None

    # "Move SL to X" ohne Signal-Kontext → als SL-Update zurückgeben
    if sl_move_match and not direction:
        return {
            "is_signal": False,
            "is_cancel": False,
            "is_sl_move": True,
            "new_sl": float(sl_move_match.group(1)),
            "reason": f"SL verschieben auf {sl_move_match.group(1)}",
        }

    is_signal = bool(sl and tp1)

    return {
        "is_signal": is_signal,
        "is_cancel": False,
        "has_open_tp": has_open_tp,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
    }


# ─── Duplikat-Erkennung ───────────────────────────────────────────────────────
def get_text_hash(text: str) -> str:
    """Erstellt Hash des normalisierten Textes"""
    normalized = " ".join(text.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()


BACKUP_KEYWORDS = [
    "backup", "backup plan", "recovery plan", "recovery trade",
    "plan b", "plan c", "recovery entry", "double up", "recovery mode",
    "recovery buy", "recovery sell",
]

def is_trading_hours() -> bool:
    """True wenn aktuell innerhalb der Handelszeiten."""
    h = datetime.now().hour
    return TRADING_HOUR_START <= h < TRADING_HOUR_END


def trading_sleep(on_secs: float, off_secs: float = None) -> float:
    """Gibt kuerzere Schlafzeit waehrend Handelszeiten zurueck,
    laengere ausserhalb (energieoptimal)."""
    if off_secs is None:
        off_secs = on_secs * 4
    return on_secs if is_trading_hours() else off_secs


def is_backup_signal(text: str) -> bool:
    """Erkennt GHP Backup/Recovery Signale anhand von Keywords."""
    tl = text.lower()
    return any(kw in tl for kw in BACKUP_KEYWORDS)


def is_duplicate(text_hash: str) -> bool:
    """Prüft ob dieser Hash in den letzten 60 Sekunden schon gesehen wurde"""
    now = datetime.now()
    # Alte Hashes aufräumen
    expired = [h for h, t in state.seen_hashes.items()
               if (now - t).seconds > DUPLICATE_WINDOW]
    for h in expired:
        del state.seen_hashes[h]

    if text_hash in state.seen_hashes:
        return True

    state.seen_hashes[text_hash] = now
    return False


def is_entry_duplicate(direction: str, symbol: str, entry: float, channel: str = None) -> bool:
    """Entry-Preis Duplikat: blockiert IDENTISCHEN Entry DESSELBEN Kanals
    innerhalb des Fensters (enge Toleranz). Kanal-scoped, damit TFXC/Goldhunter/
    GTMo sich NICHT gegenseitig ausknocken."""
    now = datetime.now()
    _tol_rel = float(os.getenv("ENTRY_DUP_TOL_REL", "0.0001"))   # ~4 Pips @ Gold statt 218
    tol = max(entry * _tol_rel, 0.3)
    expired = [k for k, t in state.seen_entries.items()
               if (now - t).total_seconds() > ENTRY_DUPLICATE_WINDOW]
    for k in expired:
        del state.seen_entries[k]
    for key, t in list(state.seen_entries.items()):
        if len(key) != 4:            # alte 3-Tupel defensiv ueberspringen
            continue
        ch_ref, d, sym, e_ref = key
        if ch_ref == channel and d == direction and sym == symbol and abs(e_ref - entry) <= tol:
            age = int((now - t).total_seconds() / 60)
            log.info("Entry-Dup [" + str(channel) + "]: " + direction + " " + symbol +
                     " @ " + str(entry) + " = " + str(e_ref) + " vor " + str(age) + " Min")
            return True
    state.seen_entries[(channel, direction, symbol, round(entry, 1))] = now
    return False


def is_sl_cooldown(channel: str, symbol: str,
                   new_direction: str = "", new_entry: float = 0.0) -> bool:
    """
    Option A: Cooldown nur wenn GLEICHE Richtung UND GLEICHE Preiszone.

    Beispiel:
      SL-Hit: SELL @ 4713  →  neue SELLs bei 4713 ± 1% geblockt (bis zu 2h)
      Neuer SELL @ 4749 (+0.76% entfernt? nein, 4749/4713-1 = 0.77%) → NEIN warte:
      4749 vs 4713: (4749-4713)/4713 = 0.76% < 1% → eigentlich noch geblockt
      Aber 36 Punkte ist deutlich neues Setup → verwende 2% Toleranz fuer Gold

    Blockiert wenn:
      1. Zeitfenster noch aktiv (< 2h)
      2. Gleiche Richtung wie der SL-Trade
      3. Neuer Entry innerhalb ZONE_PCT des alten Entry
    """
    key = (channel, symbol)
    data = state.sl_cooldowns.get(key)
    if not data:
        return False

    hit_time, sl_direction, sl_entry = data
    elapsed = (datetime.now() - hit_time).total_seconds()

    if elapsed >= SL_COOLDOWN_SECONDS:
        del state.sl_cooldowns[key]
        return False

    # Andere Richtung → immer erlaubt
    if new_direction and new_direction != sl_direction:
        log.info("SL-Cooldown: andere Richtung → erlaubt (" +
                 new_direction + " nach " + sl_direction + " SL)")
        return False

    # Gleiche Richtung: Entry-Zone pruefen (2% Toleranz)
    ZONE_PCT = 0.005
    if new_entry > 0 and sl_entry > 0:
        distance_pct = abs(new_entry - sl_entry) / sl_entry
        if distance_pct > ZONE_PCT:
            log.info("SL-Cooldown: neues Setup (" + str(round(distance_pct*100,1)) +
                     "% vom SL-Entry entfernt) → erlaubt: " +
                     new_direction + " @ " + str(new_entry))
            return False

    remaining = int((SL_COOLDOWN_SECONDS - elapsed) / 60)
    log.info("SL-Cooldown: " + channel + "/" + symbol +
             " gleiche Zone → noch " + str(remaining) + " Min gesperrt")
    return True


def register_sl_hit(channel: str, symbol: str,
                    direction: str = "", entry: float = 0.0):
    """Registriert SL-Hit mit Richtung und Entry fuer zonengenauen Cooldown."""
    state.sl_cooldowns[(channel, symbol)] = (datetime.now(), direction, entry)
    log.info("SL-Cooldown: " + channel + "/" + symbol +
             " " + direction + " @ " + str(entry) +
             " gesperrt " + str(SL_COOLDOWN_SECONDS // 60) + " Min (gleiche Zone)")


# ─── Telegram Bot (für Bestätigungen) ────────────────────────────────────────
bot_client = None  # Wird in main() initialisiert


async def send_confirmation_request(sig: TradeSignal, layers: int, distribution: dict) -> int:
    """Schickt Bestätigungs-Nachricht mit Buttons ans Handy"""
    balance = mt5.account_info().balance if mt5.account_info() else 0

    tps_text = ""
    for tp, count in distribution.items():
        tps_text += f"  TP {tp}: {count} Layer\n"

    msg = (
        f"⚡ *NEUES SIGNAL*\n"
        f"{'─' * 30}\n"
        f"*{sig.direction} {sig.symbol}*\n"
        f"Entry: `{sig.entry or 'Market'}`\n"
        f"SL: `{sig.sl}`\n"
        f"{'─' * 30}\n"
        f"*Layer-Aufteilung ({layers} Layer):*\n"
        f"{tps_text}"
        f"{'─' * 30}\n"
        f"Lot/Layer: `0.01` | Gesamt: `{layers * 0.01:.2f}`\n"
        f"Kontostand: `${balance:.2f}`\n"
        f"Kanal: `{sig.source_channel}`\n"
        f"R/R: `{round((sig.entry - sig.tp1) / (sig.entry - sig.sl), 2) if sig.sl and sig.tp1 and sig.entry and sig.sl != sig.entry else 'N/A'}` "
    )

    # Signal im State speichern für spätere Bestätigung
    signal_id = len(state.pending_signals) + 1
    state.pending_signals[signal_id] = sig

    buttons = [
        [Button.inline("✅ AUSFÜHREN", f"confirm_{signal_id}".encode()),
         Button.inline("❌ ABLEHNEN", f"reject_{signal_id}".encode())]
    ]

    await bot_client.send_message(
        TG_MY_CHAT_ID,
        msg,
        parse_mode="md",
        buttons=buttons
    )
    return signal_id


async def send_notification(text: str):
    """Schickt einfache Benachrichtigung ans Handy"""
    try:
        await bot_client.send_message(TG_MY_CHAT_ID, text, parse_mode="md")
    except Exception as e:
        log.error(f"Telegram Benachrichtigung fehlgeschlagen: {e}")


# ─── MT5 ─────────────────────────────────────────────────────────────────────
def connect_mt5() -> bool:
    if not mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        log.error(f"MT5 Fehler: {mt5.last_error()}")
        return False
    info = mt5.account_info()
    if info is None:
        log.error("Kontodaten nicht abrufbar.")
        return False
    account_type = "DEMO" if DEMO_MODE else "LIVE ⚠️"
    log.info(f"MT5 [{account_type}] → Konto {info.login} | Balance: ${info.balance:.2f} {info.currency}")
    return True


def _total_open_risk() -> float:
    """Aggregiertes offenes Risiko ueber alle Magic-Positionen (sl_dist*pip_value*lot)."""
    total = 0.0
    positions = mt5.positions_get()
    if not positions:
        return 0.0
    for p in positions:
        if p.magic != MAGIC_NUMBER:
            continue
        si = mt5.symbol_info(p.symbol)
        if not si or si.trade_tick_size <= 0:
            continue
        pip_val = si.trade_tick_value / si.trade_tick_size
        if p.sl and p.sl > 0:
            sl_dist = abs(p.price_open - p.sl)
        else:
            sl_dist = si.point * 1000
        total += sl_dist * pip_val * p.volume
    return total


def _enforce_risk_cap(lot_per_layer, num_layers, sig, tick, symbol_info, balance):
    """
    Letzte, NICHT umgehbare Risiko-Grenze direkt vor der Order-Schleife.
    Erzwingt: SL-Distanz x pip_value x lot x num_layers <= MAX_RISK_PCT x balance.
    SL-Distanz wird HIER aus Live-Tick + sig.sl neu berechnet (auch Zonen-Entry),
    damit kein Upstream-Pfad (GTMO-Zone, Backup, Urgent) den Cap umgehen kann.
    Rueckgabe (lot_per_layer, num_layers) - ggf. reduziert.
    """
    try:
        if not sig.sl or float(sig.sl) <= 0 or not symbol_info or not tick:
            return lot_per_layer, num_layers
        is_buy = (sig.direction == "BUY")
        ref = tick.ask if is_buy else tick.bid
        # Pending-Limit: SL-Distanz vom ENTRY (echter Fill-Preis), nicht vom Markt,
        # sonst ueberschaetzt der Cap das Risiko (Markt->SL) und stutzt Layer zu stark.
        if getattr(sig, "is_limit", False) and sig.entry:
            try:
                if float(sig.entry) > 0:
                    ref = float(sig.entry)
            except (TypeError, ValueError):
                pass
        sl_dist = abs(float(ref) - float(sig.sl))
        if sl_dist <= 0:
            return lot_per_layer, num_layers
        tick_val  = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        if not tick_size or tick_size <= 0:
            return lot_per_layer, num_layers
        pip_value  = tick_val / tick_size
        max_loss   = balance * float(os.getenv("MAX_RISK_PCT", "0.10"))
        total_risk = sl_dist * pip_value * lot_per_layer * num_layers
        if total_risk <= max_loss:
            return lot_per_layer, num_layers
        scale   = max_loss / total_risk
        new_lot = max(0.01, int(lot_per_layer * scale * 100) / 100.0)  # abrunden -> immer unter Cap
        new_layers = num_layers
        risk_per_layer = sl_dist * pip_value * new_lot
        if risk_per_layer > 0:
            allowed = int(max_loss // risk_per_layer)
            if allowed < new_layers:
                new_layers = max(0, allowed)
        log.warning("RISK-CAP (final): SL=" + str(round(sl_dist, 2)) + "pts Risiko=$" +
                    str(round(total_risk, 0)) + " > Max=$" + str(round(max_loss, 0)) +
                    " -> Lot " + str(lot_per_layer) + "->" + str(new_lot) +
                    ", Layer " + str(num_layers) + "->" + str(new_layers))
        return new_lot, new_layers
    except Exception as _e:
        log.error("_enforce_risk_cap: " + str(_e))
        return lot_per_layer, num_layers


def execute_layers(sig: TradeSignal) -> list[int]:
    """
    Führt alle Layer als separate MT5-Orders aus.
    Gibt Liste der Ticket-Nummern zurück.
    """
    info = mt5.account_info()
    if not info:
        log.error("MT5 Kontodaten nicht abrufbar")
        return []

    balance = info.balance

    # -- Symbol-Gate: nur freigegebene Maerkte (Gold/BTC) traden --
    _allowed_bases = {s.strip().upper() for s in
                      os.getenv("TRADING_SYMBOLS",
                                GOLD_SYMBOL.split(".")[0] + "," + BTC_SYMBOL.split(".")[0]).split(",")
                      if s.strip()}
    _sym_base = (sig.symbol or "").upper().split(".")[0]
    if _sym_base not in _allowed_bases:
        log.warning("Symbol-Gate: " + str(sig.symbol) + " nicht freigegeben (erlaubt: " +
                    ",".join(sorted(_allowed_bases)) + ") -> uebersprungen")
        return []

    # ── SL-Validierung: muss auf richtiger Seite liegen ──────────────────────
    if sig.entry and sig.sl:
        if sig.direction == "BUY" and sig.sl >= sig.entry:
            log.warning(
                "SKIP: BUY aber SL=" + str(sig.sl) +
                " >= Entry=" + str(sig.entry) + " → ungültiges Signal"
            )
            return []
        if sig.direction == "SELL" and sig.sl <= sig.entry:
            log.warning(
                "SKIP: SELL aber SL=" + str(sig.sl) +
                " <= Entry=" + str(sig.entry) + " → ungültiges Signal"
            )
            return []

    # SL-Distanz berechnen für risikobasiertes Lot-Sizing
    sl_distance = 0.0
    if sig.entry and sig.sl:
        sl_distance = abs(sig.entry - sig.sl)
    elif sig.sl:
        # Kein expliziter Entry → aktuellen Preis als Referenz nehmen
        tick = mt5.symbol_info_tick(sig.symbol)
        if tick:
            ref_price = tick.ask if sig.direction == "BUY" else tick.bid
            sl_distance = abs(ref_price - sig.sl)

    # Kein SL im Signal -> synthetischen 100-Pip-SL setzen (kein Trade ohne SL)
    if not sig.sl:
        _tk_syn = mt5.symbol_info_tick(sig.symbol)
        _si_syn = mt5.symbol_info(sig.symbol)
        if _tk_syn and _si_syn:
            _ref_syn = _tk_syn.ask if sig.direction == "BUY" else _tk_syn.bid
            _sl_pips = (_si_syn.point or 0.01) * 1000  # 100 Pips
            _dig_syn = _si_syn.digits or 2
            if sig.direction == "BUY":
                sig.sl = round(_ref_syn - _sl_pips, _dig_syn)
            else:
                sig.sl = round(_ref_syn + _sl_pips, _dig_syn)
            sl_distance = abs(_ref_syn - sig.sl)
            log.info("Kein SL im Signal -> synthetischer 100-Pip-SL: " +
                     str(sig.sl))
    # Anzahl Layer = Anzahl TPs im Signal + 1 offener Layer
    _sig_tps = [t for t in [sig.tp1, sig.tp2, sig.tp3, sig.tp4, sig.tp5,
                              getattr(sig,"tp6",None), getattr(sig,"tp7",None)] if t]
    _max_lay  = int(os.getenv("MAX_LAYERS", "6"))
    _num_lay  = max(1, min(len(_sig_tps) + 1, _max_lay))
    num_layers, lot_per_layer = calculate_layers(balance, sig.source_channel, sig.is_backup)
    num_layers = _num_lay

    # "High volatile / use small lot" → Lot halbieren
    if getattr(sig, "small_lot", False):
        lot_per_layer = round(max(0.01, lot_per_layer * 0.5), 2)
        log.info("Small-Lot Warnung → Lot halbiert: " + str(lot_per_layer))

    # ── Confidence-Scaling: hohes Vertrauen = mehr Lot ───────────────────────
    confidence = getattr(sig, "confidence", 90) or 90
    if confidence >= 90:
        conf_scale = 1.0    # voll
    elif confidence >= 80:
        conf_scale = 0.75   # 75%
    else:
        conf_scale = 0.5    # 50% bei niedriger Confidence
    lot_per_layer = round(max(0.01, lot_per_layer * conf_scale), 2)
    if conf_scale < 1.0:
        log.info("Conf-Scale: " + str(confidence) + "% → Lot×" +
                 str(conf_scale) + "=" + str(lot_per_layer))

    # ── Max 10% Risiko pro Trade ──────────────────────────────────────────────
    MAX_RISK_PCT = float(os.getenv("MAX_RISK_PCT", "0.10"))  # 10% default
    if sl_distance > 0 and sig.symbol:
        sym_info_risk = mt5.symbol_info(sig.symbol)
        if sym_info_risk:
            # Pip-Wert: trade_tick_value × (1/tick_size) × lot
            tick_val  = sym_info_risk.trade_tick_value   # $ pro Tick pro 1 Lot
            tick_size = sym_info_risk.trade_tick_size
            if tick_size > 0:
                pip_value_per_lot = tick_val / tick_size  # $ pro Punkt pro 1 Lot
                max_loss_allowed  = balance * MAX_RISK_PCT
                total_risk_now    = sl_distance * pip_value_per_lot * lot_per_layer * num_layers
                if total_risk_now > max_loss_allowed:
                    scale = max_loss_allowed / total_risk_now
                    lot_per_layer = round(max(0.01, lot_per_layer * scale), 2)
                    log.info(
                        "Risk-Cap: SL=" + str(round(sl_distance,2)) +
                        "pts → Lot auf " + str(lot_per_layer) +
                        " reduziert (" + str(round(MAX_RISK_PCT*100)) + "% Max)"
                    )
                    # Kleinkonto-Schutz: Lot am Mindestlot-Boden (0.01) und immer
                    # noch ueber dem Cap -> Anzahl Layer reduzieren
                    risk_per_layer = sl_distance * pip_value_per_lot * lot_per_layer
                    if risk_per_layer > 0:
                        max_layers_allowed = int(max_loss_allowed // risk_per_layer)
                        if max_layers_allowed < num_layers:
                            num_layers = max(1, max_layers_allowed)
                            log.info("Kleinkonto-Cap: Layer reduziert auf " +
                                     str(num_layers) +
                                     " (Mindestlot-Boden, " +
                                     str(round(MAX_RISK_PCT*100)) + "% Max)")
                    # Kleinkonto-Schutz: Lot am Mindestlot-Boden (0.01) und immer
                    # noch ueber dem Cap -> Anzahl Layer reduzieren
                    risk_per_layer = sl_distance * pip_value_per_lot * lot_per_layer
                    if risk_per_layer > 0:
                        max_layers_allowed = int(max_loss_allowed // risk_per_layer)
                        if max_layers_allowed < num_layers:
                            num_layers = max(1, max_layers_allowed)
                            log.info("Kleinkonto-Cap: Layer reduziert auf " +
                                     str(num_layers) +
                                     " (Mindestlot-Boden, " +
                                     str(round(MAX_RISK_PCT*100)) + "% Max)")

    # Total-Heat-Deckel: aggregiertes Risiko ueber ALLE offenen Positionen
    MAX_TOTAL_HEAT_PCT = float(os.getenv("MAX_TOTAL_HEAT_PCT", "0.30"))
    if sig.symbol:
        _si_h  = mt5.symbol_info(sig.symbol)
        _acc_h = mt5.account_info()
        if _si_h and _acc_h and _si_h.trade_tick_size > 0:
            _pip_h    = _si_h.trade_tick_value / _si_h.trade_tick_size
            _heat_cap = _acc_h.equity * MAX_TOTAL_HEAT_PCT
            _open_r   = _total_open_risk()
            _headroom = _heat_cap - _open_r
            _eff_sl_h = sl_distance if sl_distance > 0 else (_si_h.point or 0.01) * 1000
            _new_r    = _eff_sl_h * _pip_h * lot_per_layer * num_layers
            if _new_r > _headroom:
                if _headroom <= 0:
                    log.warning("Total-Heat voll: offen=" + str(round(_open_r,2)) +
                                "$ >= Cap " + str(round(_heat_cap,2)) +
                                "$ -> Signal uebersprungen")
                    return []
                lot_per_layer = round(max(0.01, lot_per_layer * (_headroom / _new_r)), 2)
                log.info("Total-Heat-Cap: offen=" + str(round(_open_r,2)) +
                         "$ Headroom=" + str(round(_headroom,2)) +
                         "$ -> Lot auf " + str(lot_per_layer) + " reduziert")
                _risk_min = _eff_sl_h * _pip_h * lot_per_layer
                if _risk_min > 0:
                    _max_lay_h = int(_headroom // _risk_min)
                    if _max_lay_h < num_layers:
                        num_layers = max(0, _max_lay_h)
                        if num_layers <= 0:
                            log.warning("Total-Heat: selbst Mindestlot passt nicht -> uebersprungen")
                            return []
                        log.info("Total-Heat-Cap: Layer reduziert auf " + str(num_layers))

    tps = sig.tps()
    distribution = distribute_layers(num_layers, tps, sig.source_channel)

    tickets = []
    symbol_info = mt5.symbol_info(sig.symbol)
    if not symbol_info:
        # Versuche Symbol ohne Suffix
        base = sig.symbol.replace(FX_SUFFIX, "").replace(".p", "").replace(".s", "")
        # Suche in verfuegbaren Symbolen
        all_symbols = mt5.symbols_get() or []
        candidates = [s.name for s in all_symbols
                      if base.upper() in s.name.upper()][:5]
        log.error("Symbol " + sig.symbol + " nicht gefunden in MT5. "
                  "Verfuegbare Alternativen: " + str(candidates))
        # Kein await hier - execute_layers ist sync
        log.error("Alternativen: " + str(candidates))
        return []

    if not symbol_info.visible:
        mt5.symbol_select(sig.symbol, True)

    tick = mt5.symbol_info_tick(sig.symbol)
    if not tick:
        log.error(f"Kein Tick für {sig.symbol}")
        return []

    tp_map = {tp: [] for tp in distribution}  # tp_price → [tickets]
    lot_per_layer, num_layers = _enforce_risk_cap(
        lot_per_layer, num_layers, sig, tick, symbol_info, balance)
    if num_layers <= 0:
        log.warning("Risk-Cap (final): kein Layer passt ins Risiko -> uebersprungen")
        return []
    distribution = distribute_layers(num_layers, tps, sig.source_channel)
    tp_map = {tp: [] for tp in distribution}
    layer_num = 0
    for tp_price, count in distribution.items():
        for _ in range(count):
            layer_num += 1

            _lt = mt5.symbol_info_tick(sig.symbol) or tick
            if sig.direction == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = _lt.ask
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = _lt.bid
            # Nah-Markt-Entry (innerhalb Band) -> Market statt Limit (alle Layer oeffnen)
            _mkt_band = price * float(os.getenv("MARKET_ENTRY_BAND_PCT", "0.0007"))

            # Limit Order: explizit wenn is_limit=True ODER Entry weicht vom Markt ab
            # Schwelle: 0.1% des Preises (symbol-unabhängig: funktioniert für Gold UND BTC)
            limit_threshold = price * 0.001  # 0.1%
            is_explicit_limit = sig.is_limit and sig.entry
            is_price_limit = sig.entry and abs(sig.entry - price) > limit_threshold

            is_pending = False  # default: Market Order
            if is_explicit_limit or is_price_limit:
                if sig.direction == "BUY":
                    # BUY LIMIT: entry unter aktuellem Preis (warte auf Rücksetzer)
                    # BUY STOP: entry über aktuellem Preis (Breakout)
                    if sig.entry < price - _mkt_band:
                        order_type = mt5.ORDER_TYPE_BUY_LIMIT   # Kurs kommt von oben runter
                    else:
                        # Entry ueber aktuellem Kurs: pruefen ob schon durchgelaufen
                        # Signal sagt "BUY LIMIT" aber Entry ist hoher als Markt
                        # → als Market ausfuehren (Entry bereits vorbei)
                        is_pending = False
                        order_type = mt5.ORDER_TYPE_BUY
                        price = tick.ask
                        log.info("BUY: Entry " + str(sig.entry) + " > Ask " +
                                 str(tick.ask) + " → Market (Entry bereits durchlaufen)")
                else:  # SELL
                    if sig.entry > price + _mkt_band:
                        # Entry über Markt → SELL LIMIT (warte bis Kurs steigt)
                        order_type = mt5.ORDER_TYPE_SELL_LIMIT
                    else:
                        # Entry unter Markt → sofort Market SELL
                        # (Entry bereits durchgelaufen, günstigerer Preis verpasst)
                        is_pending = False
                        order_type = mt5.ORDER_TYPE_SELL
                        price = tick.bid
                        log.info("SELL Market: Entry " + str(sig.entry) +
                                 " < Bid " + str(round(tick.bid,5)) +
                                 " → sofort ausführen")
                is_pending = order_type in (
                    mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
                    mt5.ORDER_TYPE_BUY_STOP,  mt5.ORDER_TYPE_SELL_STOP,
                )
                if is_pending:
                    # Zone-Entry: Layers gleichmässig über Zone verteilen
                    # z.B. entry=4177, entry_low=4172 → Layer 1@4177, Layer 2@4175, etc.
                    entry_low = getattr(sig, "entry_low", None)
                    if entry_low and entry_low < sig.entry and num_layers > 1:
                        zone_range = sig.entry - entry_low
                        step = zone_range / (num_layers - 1) if num_layers > 1 else 0
                        zone_price = sig.entry - (step * (layer_num - 1))
                        price = round(zone_price, 2)
                    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
                        price = sig.entry + LIMIT_BUFFER_PIPS
                    elif order_type == mt5.ORDER_TYPE_SELL_LIMIT:
                        price = sig.entry - LIMIT_BUFFER_PIPS
                    else:
                        price = sig.entry
                log.info("Pending Order: " + str(order_type) +
                         " @ " + str(price) + " (Markt: " +
                         str(tick.ask if sig.direction == "BUY" else tick.bid) + ")")

            # is_pending gesetzt basierend auf Order-Typ
            is_pending = order_type in (
                mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
                mt5.ORDER_TYPE_BUY_STOP,  mt5.ORDER_TYPE_SELL_STOP,
            )

            # Frischen Tick für jeden Layer holen (verhindert retcode=10015)
            fresh_tick = mt5.symbol_info_tick(sig.symbol)
            if fresh_tick and not is_pending:
                if sig.direction == "BUY":
                    price = round_price(sig.symbol, fresh_tick.ask)
                else:
                    price = round_price(sig.symbol, fresh_tick.bid)
            elif is_pending:
                price = round_price(sig.symbol, price)

            # Preis muss float sein – MT5 akzeptiert keine Integer
            price_f = float(price)
            sl_f    = float(sig.sl) if sig.sl else 0.0
            tp_f    = float(tp_price) if tp_price else 0.0

            # ── SL/TP Normalisierung + Mindestabstand ────────────────────────
            sym_info_ex = mt5.symbol_info(sig.symbol)
            if sym_info_ex and price_f > 0:
                pt      = sym_info_ex.point
                digits  = sym_info_ex.digits
                stops   = getattr(sym_info_ex, "trade_stops_level", 0) or 0
                min_d   = max(stops * pt, pt * 10)  # mind. 10 Punkte

                # Preise auf Tick-Size normalisieren
                if pt > 0:
                    price_f = round(round(price_f / pt) * pt, digits)
                    if sl_f:
                        sl_f = round(round(sl_f / pt) * pt, digits)
                    if tp_f:
                        tp_f = round(round(tp_f / pt) * pt, digits)

                # SL Mindestabstand sicherstellen
                if sl_f and price_f:
                    if sig.direction == "BUY" and sl_f >= price_f - min_d:
                        sl_f = round(price_f - min_d, digits)
                    elif sig.direction == "SELL" and sl_f <= price_f + min_d:
                        sl_f = round(price_f + min_d, digits)

                # TP Mindestabstand sicherstellen
                if tp_f and price_f:
                    if sig.direction == "BUY" and tp_f <= price_f + min_d:
                        tp_f = round(price_f + min_d * 2, digits)
                    elif sig.direction == "SELL" and tp_f >= price_f - min_d:
                        tp_f = round(price_f - min_d * 2, digits)

            # Plausibilitätsprüfung: Limit-Preis muss auf richtiger Seite sein
            if is_pending:
                tick_check = mt5.symbol_info_tick(sig.symbol)
                if tick_check:
                    if order_type == mt5.ORDER_TYPE_BUY_LIMIT and price_f >= tick_check.ask:
                        log.info("BUY_LIMIT Preis >= Ask → Market Order")
                        order_type  = mt5.ORDER_TYPE_BUY
                        price_f     = tick_check.ask
                        is_pending  = False
                    elif order_type == mt5.ORDER_TYPE_SELL_LIMIT and price_f <= tick_check.bid:
                        # Nur zu Market wenn Preis weniger als 5 Punkte unter Limit
                        # (Preis weit unter Zone → als Pending warten lassen)
                        sym_pt = mt5.symbol_info(sig.symbol)
                        pt_size = sym_pt.point if sym_pt else 0.01
                        if abs(price_f - tick_check.bid) <= pt_size * 50:
                            log.info("SELL_LIMIT Preis <= Bid → Market Order")
                            order_type = mt5.ORDER_TYPE_SELL
                            price_f    = tick_check.bid
                            is_pending = False
                        else:
                            log.info("SELL_LIMIT weit über Markt → bleibt Pending (wartet auf Rückkehr)")
                    elif order_type == mt5.ORDER_TYPE_BUY_STOP and price_f <= tick_check.ask:
                        log.info("BUY_STOP Preis <= Ask → Market Order")
                        order_type  = mt5.ORDER_TYPE_BUY
                        price_f     = tick_check.ask
                        is_pending  = False
                    elif order_type == mt5.ORDER_TYPE_SELL_STOP and price_f >= tick_check.bid:
                        log.info("SELL_STOP Preis >= Bid → Market Order")
                        order_type  = mt5.ORDER_TYPE_SELL
                        price_f     = tick_check.bid
                        is_pending  = False

            request = {
                "action":       mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL,
                "symbol":       sig.symbol,
                "volume":       lot_per_layer,
                "type":         order_type,
                "price":        price_f,
                "sl":           sl_f,
                "tp":           tp_f,
                "deviation":    30,
                "magic":        MAGIC_NUMBER,
                "comment":      f"TT-{_channel_code(sig.source_channel)}-L{layer_num}",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN if is_pending else mt5.ORDER_FILLING_IOC,
            }

            # Kurze Pause zwischen Layern damit MT5 neuen Tick akzeptiert
            import time as _time_layer
            _time_layer.sleep(0.15)
            # Kurze Pause zwischen Layern damit MT5 neuen Tick akzeptiert
            import time as _time_layer
            _time_layer.sleep(0.15)
            try:
                result = mt5.order_send(request)
            except Exception as ex_send:
                log.error("Layer " + str(layer_num) + " Exception: " + str(ex_send))
                continue

            if result is None:
                log.error("Layer " + str(layer_num) + " fehlgeschlagen (None): " + str(mt5.last_error()))
            elif result.retcode == mt5.TRADE_RETCODE_DONE:
                tickets.append(result.order)
                tp_map[tp_price].append(result.order)
                if not tp_price:
                    mark_runner(result.order, channel=sig.source_channel, symbol=sig.symbol,
                                tp1=(sig.tps()[0] if sig.tps() else None),
                                is_buy=(sig.direction == "BUY"), entry=price_f)
                log.info("Layer " + str(layer_num) + "/" + str(num_layers) +
                         " Ticket #" + str(result.order) + " TP=" + str(tp_price))
            else:
                log.error("Layer " + str(layer_num) + " retcode=" + str(result.retcode) +
                          " " + str(result.comment) + " – Bot laeuft weiter")

    # Im State speichern: symbol → sorted tp levels → tickets
    if sig.symbol and tickets:
        tps_sorted = sorted(distribution.keys(),
                            reverse=(sig.direction == "SELL"))
        state.tp_layers[sig.symbol] = {
            f"tp{i+1}": tp_map[tp]
            for i, tp in enumerate(tps_sorted)
        }
        log.info(f"TP-Layer Map: {state.tp_layers[sig.symbol]}")
    return tickets


def get_todays_pnl() -> float:
    """Berechnet den heutigen P&L aus dem Log."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        total = 0.0
        with open("teletrader.log", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if today in line and "PnL:" in line:
                    m = re.search(r"PnL:\s*([+-]?\d+\.?\d*)", line)
                    if m:
                        total += float(m.group(1))
        return round(total, 2)
    except Exception:
        return 0.0


def cancel_orders(tickets: list[int]) -> int:
    """Storniert offene Orders. Gibt Anzahl erfolgreich stornierter Orders zurück."""
    cancelled = 0
    for ticket in tickets:
        # Prüfen ob Order noch offen
        orders = mt5.orders_get(ticket=ticket)
        if orders:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled += 1
                log.info(f"🚫 Order #{ticket} storniert")
            else:
                # Vielleicht schon eine offene Position → schließen
                positions = mt5.positions_get(ticket=ticket)
                if positions:
                    pos = positions[0]
                    close_type = (mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY
                                  else mt5.ORDER_TYPE_BUY)
                    tick = mt5.symbol_info_tick(pos.symbol)
                    close_price = tick.bid if pos.type == 0 else tick.ask
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": close_type,
                        "position": pos.ticket,
                        "price": close_price,
                        "deviation": 30,
                        "magic": MAGIC_NUMBER,
                        "comment": "TeleTrader-Cancel",
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    r = mt5.order_send(close_request)
                    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                        cancelled += 1
                        log.info(f"🚫 Position #{ticket} geschlossen (Cancel)")
    return cancelled


# ─── Tägliche Zusammenfassung ─────────────────────────────────────────────────
# ─── Urgent Execution ────────────────────────────────────────────────────────
async def execute_urgent(symbol: str, direction: str, raw_text: str, channel_name: str):
    """
    Führt sofort eine Market Order aus (ohne SL/TP).
    Merkt sich den Trade im pending_context.
    Wenn SL/TP innerhalb von 30s nachkommen → werden automatisch gesetzt.
    """
    info = mt5.account_info()
    if not info:
        log.error("MT5 nicht verbunden")
        return

    # Pending Order fuer gleiche Richtung + Symbol vorhanden? → abbrechen und sofort als Market
    if is_trading_paused():
        log.info("Trading PAUSIERT - Urgent uebersprungen (" + str(channel_name) + ")")
        return
    existing_orders = [o for o in (mt5.orders_get(symbol=symbol) or [])
                       if o.magic == MAGIC_NUMBER]
    for o in existing_orders:
        is_same_dir = ((direction == "BUY"  and o.type in (mt5.ORDER_TYPE_BUY_LIMIT,  mt5.ORDER_TYPE_BUY_STOP)) or
                       (direction == "SELL" and o.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)))
        if is_same_dir:
            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            log.info("Pending Order #" + str(o.ticket) + " geloescht vor URGENT " + direction)

    # Margin-Check (dynamisch)
    tick_pre2 = mt5.symbol_info_tick(symbol)
    if tick_pre2:
        order_type_pre2 = (mt5.ORDER_TYPE_BUY if direction == "BUY"
                           else mt5.ORDER_TYPE_SELL)
        price_pre2 = tick_pre2.ask if direction == "BUY" else tick_pre2.bid
        req_margin2 = mt5.order_calc_margin(
            order_type_pre2, symbol, 0.01, price_pre2) or 0
        if req_margin2 > 0 and info.margin_free < req_margin2 * 1.5:
            log.warning("Urgent blockiert: Margin zu knapp (" +
                        str(round(info.margin_free, 2)) + "$ frei, braucht " +
                        str(round(req_margin2, 2)) + "$)")
            return

    # Prioritätsprüfung
    if not await check_channel_permission(channel_name, symbol):
        return

    balance = info.balance
    # Urgent: kein SL bekannt → Fallback-Sizing, Watchdog setzt SL nach 5 Min
    num_layers, lot_per_layer = calculate_layers(balance, channel_name)
    tick = mt5.symbol_info_tick(symbol)
    sym_info = mt5.symbol_info(symbol)

    if not tick or not sym_info:
        await send_notification(f"❌ Symbol {symbol} nicht verfügbar")
        return

    if not sym_info.visible:
        mt5.symbol_select(symbol, True)

    price = tick.ask if direction == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

    # -- Synthetischer SL + Risk-Cap fuer Urgent (Signal ohne SL) --
    _pt            = sym_info.point or 0.01
    _digits        = sym_info.digits or 2
    urgent_sl_dist = _pt * 1000   # 100 Pips (Gold: 1.0 Preis = 100 Pips)
    _tick_val      = sym_info.trade_tick_value or 1.0
    _tick_size     = sym_info.trade_tick_size or 0.01
    _pip_val_lot   = (_tick_val / _tick_size) if _tick_size > 0 else 100.0
    _max_risk_pct  = float(os.getenv("MAX_RISK_PCT", "0.10"))
    _max_loss      = balance * _max_risk_pct
    _risk_now      = urgent_sl_dist * _pip_val_lot * lot_per_layer * num_layers
    if _risk_now > _max_loss and _risk_now > 0:
        lot_per_layer = round(max(0.01, lot_per_layer * (_max_loss / _risk_now)), 2)
        log.info("Urgent Risk-Cap: Lot -> " + str(lot_per_layer) +
                 " (" + str(round(_max_risk_pct*100)) + "% Max)")
    # -- Total-Heat-Deckel fuer Urgent (aggregiertes Risiko ueber ALLE Positionen) --
    _heat_pct_u = float(os.getenv("MAX_TOTAL_HEAT_PCT", "0.30"))
    _heat_cap_u = info.equity * _heat_pct_u
    _open_r_u   = _total_open_risk()
    _headroom_u = _heat_cap_u - _open_r_u
    _new_r_u    = urgent_sl_dist * _pip_val_lot * lot_per_layer * num_layers
    if _new_r_u > _headroom_u:
        if _headroom_u <= 0:
            log.warning("Total-Heat voll (Urgent): offen=" + str(round(_open_r_u, 2)) +
                        "$ >= Cap " + str(round(_heat_cap_u, 2)) + "$ -> uebersprungen")
            return
        lot_per_layer = round(max(0.01, lot_per_layer * (_headroom_u / _new_r_u)), 2)
        log.info("Total-Heat-Cap (Urgent): offen=" + str(round(_open_r_u, 2)) +
                 "$ Headroom=" + str(round(_headroom_u, 2)) +
                 "$ -> Lot auf " + str(lot_per_layer) + " reduziert")
        _risk_min_u = urgent_sl_dist * _pip_val_lot * lot_per_layer
        if _risk_min_u > 0:
            _max_lay_u = int(_headroom_u // _risk_min_u)
            if _max_lay_u < num_layers:
                num_layers = max(0, _max_lay_u)
                if num_layers <= 0:
                    log.warning("Total-Heat (Urgent): selbst Mindestlot passt nicht -> uebersprungen")
                    return
                log.info("Total-Heat-Cap (Urgent): Layer reduziert auf " + str(num_layers))
    if direction == "BUY":
        urgent_sl = round(price - urgent_sl_dist, _digits)
    else:
        urgent_sl = round(price + urgent_sl_dist, _digits)

    tickets = []
    for i in range(num_layers):
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot_per_layer,
            "type":         order_type,
            "price":        price,
            "sl":           urgent_sl,
            "tp":           0.0,
            "deviation":    30,
            "magic":        MAGIC_NUMBER,
            "comment":      f"TT-{_channel_code(channel_name)}-U{i+1}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            tickets.append(result.order)
            log.info(f"✅ Urgent Layer {i+1}/{num_layers} | Ticket #{result.order}")
        else:
            log.error(f"❌ Urgent Layer {i+1} fehlgeschlagen: {result}")

    if tickets:
        text_hash = get_text_hash(raw_text)
        state.open_orders[text_hash] = tickets

        # Pending Context für SL/TP Folgenachricht
        state.pending_context[symbol] = {
            "direction":  direction,
            "channel":    channel_name,
            "raw_text":   raw_text,
            "tickets":    tickets,
            "expires_at": datetime.now() + timedelta(seconds=state.CONTEXT_WINDOW),
        }

        state.daily_stats["trades"] += 1
        await send_notification(
            f"⚡ *Urgent Trade ausgeführt*\n"
            f"{direction} {symbol} | {num_layers} Layer\n"
            f"@ {price:.2f} | Lot: {num_layers * lot_per_layer:.2f}\n"
            f"⏳ Warte {state.CONTEXT_WINDOW}s auf SL/TP..."
        )
    else:
        await send_notification(f"❌ Urgent Trade fehlgeschlagen: {symbol}")


def parse_levels_from_text(text):
    """Stufe B: SL + TPs (+ open-Runner-Flag) robust aus Rohtext eines ENTRY-Signals.
    MOVE_SL-Texte ('adjust SL +20 to 4319') ergeben sl=None -> kein Entry-Attach."""
    import re as _re_sb
    out = {"sl": None, "tps": [], "has_open": False}
    if not text:
        return out
    m = _re_sb.search(r'\bSL\b\s*[:=]?\s*([0-9]{3,}(?:\.[0-9]+)?)', text, _re_sb.IGNORECASE)
    if m:
        out["sl"] = float(m.group(1))
    for tpm in _re_sb.finditer(r'\bTP(?:\d{1,2})?\b[\s:=]*([0-9]{3,}(?:\.[0-9]+)?|open|runner)',
                               text, _re_sb.IGNORECASE):
        val = tpm.group(1).lower()
        if val in ("open", "runner"):
            out["has_open"] = True
        else:
            out["tps"].append(float(val))
    return out


def attach_levels_to_urgent(symbol, direction, sl, tps, has_open, tickets):
    """Stufe B: SL auf alle Urgent-Positionen; TP1..TP(n-1) auf Worker; letzte = Runner (tp=0)."""
    pos = [p for p in (mt5.positions_get(symbol=symbol) or [])
           if p.magic == MAGIC_NUMBER and p.ticket in tickets]
    if not pos:
        pos = [p for p in (mt5.positions_get(symbol=symbol) or [])
               if p.magic == MAGIC_NUMBER and
               ((p.type == mt5.POSITION_TYPE_BUY and direction == "BUY") or
                (p.type == mt5.POSITION_TYPE_SELL and direction == "SELL"))]
    if not pos:
        return (0, None)
    pos.sort(key=lambda p: p.ticket)
    _si = mt5.symbol_info(symbol)
    _dig = _si.digits if _si else 2
    runner = pos[-1] if has_open else None
    workers = pos[:-1] if has_open else pos

    def _vsl(p, s):
        if not s:
            return p.sl
        if p.type == mt5.POSITION_TYPE_BUY and s >= p.price_open:
            return p.sl
        if p.type == mt5.POSITION_TYPE_SELL and s <= p.price_open:
            return p.sl
        return s

    def _vtp(p, t):
        if not t:
            return 0.0
        if p.type == mt5.POSITION_TYPE_BUY and t <= p.price_open:
            return 0.0
        if p.type == mt5.POSITION_TYPE_SELL and t >= p.price_open:
            return 0.0
        return t

    updated = 0
    for i, p in enumerate(workers):
        tp = tps[i] if i < len(tps) else 0.0
        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
                            "position": p.ticket, "sl": round(_vsl(p, sl), _dig),
                            "tp": round(_vtp(p, tp), _dig)})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            updated += 1
            log.info("Stufe B Worker #" + str(p.ticket) + " SL=" +
                     str(round(_vsl(p, sl), _dig)) + " TP=" + str(round(_vtp(p, tp), _dig)))
        else:
            log.error("Stufe B Worker #" + str(p.ticket) + " SLTP fehlgeschlagen: " + str(r))
    runner_tk = None
    if runner is not None:
        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
                            "position": runner.ticket, "sl": round(_vsl(runner, sl), _dig),
                            "tp": 0.0})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            runner_tk = runner.ticket
            mark_runner(runner.ticket, channel="", symbol=symbol)
            log.info("Stufe B Runner #" + str(runner.ticket) + " SL=" +
                     str(round(_vsl(runner, sl), _dig)) + " TP=0 (haelt bis Close)")
        else:
            log.error("Stufe B Runner SLTP fehlgeschlagen: " + str(r))
    return (updated, runner_tk)


async def apply_sl_tp_to_tickets(tickets: list[int], symbol: str, sl: float, tp: float):
    """
    Setzt SL/TP nachträglich auf bereits offene Positionen.
    Prüft Plausibilität: TP muss bei BUY über Entry, bei SELL darunter liegen.
    """
    updated = 0

    all_positions = mt5.positions_get(symbol=symbol)
    if not all_positions:
        log.warning(f"apply_sl_tp: keine offenen Positionen für {symbol}")
        return 0

    our_positions = [p for p in all_positions if p.ticket in tickets or p.magic == MAGIC_NUMBER]
    log.info(f"apply_sl_tp: {len(our_positions)} Positionen gefunden für {symbol}")

    for pos in our_positions:
        use_sl = sl if sl else pos.sl
        use_tp = tp if tp else pos.tp

        # Plausibilitätsprüfung
        if use_tp and use_tp > 0:
            if pos.type == mt5.POSITION_TYPE_BUY and use_tp <= pos.price_open:
                log.warning(f"⚠️ TP {use_tp} ungültig für BUY @ {pos.price_open} – übersprungen")
                use_tp = pos.tp  # alten TP behalten
            elif pos.type == mt5.POSITION_TYPE_SELL and use_tp >= pos.price_open:
                log.warning(f"⚠️ TP {use_tp} ungültig für SELL @ {pos.price_open} – übersprungen")
                use_tp = pos.tp

        if use_sl and use_sl > 0:
            if pos.type == mt5.POSITION_TYPE_BUY and use_sl >= pos.price_open:
                log.warning(f"⚠️ SL {use_sl} ungültig für BUY @ {pos.price_open} – übersprungen")
                use_sl = pos.sl
            elif pos.type == mt5.POSITION_TYPE_SELL and use_sl <= pos.price_open:
                log.warning(f"⚠️ SL {use_sl} ungültig für SELL @ {pos.price_open} – übersprungen")
                use_sl = pos.sl

        # Position noch offen? (manuell filtern - ticket= Parameter unzuverlässig)
        all_pos = mt5.positions_get() or []
        if not any(p.ticket == pos.ticket for p in all_pos):
            log.warning("MOVE_SL: #" + str(pos.ticket) + " nicht mehr offen")
            continue
        sym_info = mt5.symbol_info(pos.symbol)
        digits = sym_info.digits if sym_info else 5
        use_sl = round(use_sl, digits)

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": pos.ticket,
            "sl":       use_sl,
            "tp":       use_tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            updated += 1
            log.info(f"✅ SL/TP gesetzt: #{pos.ticket} SL={use_sl} TP={use_tp}")
        else:
            log.error(f"❌ SL/TP fehlgeschlagen #{pos.ticket}: {result}")
    return updated


# ─── Move SL to Price ────────────────────────────────────────────────────────
_naked_since = {}

def ensure_protective_sl():
    """Sicherheitsnetz: jede eigene Position ohne SL bekommt nach Karenzzeit
    zwangsweise einen Schutz-Stop (synthetisch 100 Pips, an den Markt geklemmt).
    Setzt NUR bei sl==0 -> geschuetzte/fremde Positionen bleiben unberuehrt."""
    try:
        grace = float(os.getenv("FALLBACK_SL_GRACE_SEC", "90"))
        now = datetime.now()
        positions = [p for p in (mt5.positions_get() or []) if p.magic == MAGIC_NUMBER]
        live = {p.ticket for p in positions}
        for _t in [t for t in list(_naked_since) if t not in live]:
            _naked_since.pop(_t, None)
        for pos in positions:
            if pos.sl and pos.sl > 0:
                _naked_since.pop(pos.ticket, None)
                continue
            first = _naked_since.get(pos.ticket)
            if first is None:
                _naked_since[pos.ticket] = now
                continue
            if (now - first).total_seconds() < grace:
                continue
            si = mt5.symbol_info(pos.symbol)
            tick = mt5.symbol_info_tick(pos.symbol)
            if not si or not tick:
                continue
            pt = si.point or 0.01
            digits = si.digits or 2
            dist = pt * 1000  # 100 Pips
            stops = getattr(si, "trade_stops_level", 0) or 0
            min_d = max(stops * pt, pt * 10)
            if pos.type == mt5.POSITION_TYPE_BUY:
                sl = round(min(pos.price_open - dist, tick.bid - min_d), digits)
            else:
                sl = round(max(pos.price_open + dist, tick.ask + min_d), digits)
            req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": pos.symbol,
                   "position": pos.ticket, "sl": sl, "tp": pos.tp}
            r = mt5.order_send(req)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                _naked_since.pop(pos.ticket, None)
                log.info("Fallback-SL gesetzt #" + str(pos.ticket) + " " +
                         pos.symbol + " -> " + str(sl))
            else:
                log.error("Fallback-SL FEHLER #" + str(pos.ticket) + ": " +
                          str(getattr(r, "retcode", "None")))
    except Exception as _e:
        log.error("Fallback-SL Ausnahme: " + str(_e))


def move_sl_to_price(new_sl: float, channel_name: str, symbol: str = None) -> int:
    """Setzt SL aller offenen Positionen auf einen konkreten Preis.
    Robust: Symbol selektieren, SL an Mindest-Stop-Distanz clampen,
    bei order_send=None den last_error loggen (sonst nur retcode=None)."""
    updated = 0
    positions = mt5.positions_get()
    if not positions:
        return 0
    for pos in positions:
        if pos.magic != MAGIC_NUMBER:
            continue
        if symbol and pos.symbol != symbol:
            continue
        si   = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if not si or not tick:
            log.error("SL-Move #" + str(pos.ticket) + ": kein symbol_info/tick (" + str(pos.symbol) + ")")
            continue
        if not si.visible:
            mt5.symbol_select(pos.symbol, True)
        pt     = si.point or 0.01
        digits = si.digits or 2
        stops  = getattr(si, "trade_stops_level", 0) or 0
        min_d  = max(stops * pt, pt * 10)
        sl_req = float(new_sl)
        if pos.type == mt5.POSITION_TYPE_BUY:
            sl_valid = min(sl_req, tick.bid - min_d)
        else:
            sl_valid = max(sl_req, tick.ask + min_d)
        sl_valid = round(sl_valid, digits)
        if abs(sl_valid - sl_req) > pt / 2:
            log.info("SL-Move #" + str(pos.ticket) + ": SL " + str(sl_req) +
                     " -> " + str(sl_valid) + " (Mindest-Stop-Distanz)")
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": pos.ticket,
            "sl":       sl_valid,
            "tp":       pos.tp,
        }
        result = mt5.order_send(request)
        if result is None:
            log.error("SL-Move fehlgeschlagen #" + str(pos.ticket) +
                      ": order_send=None last_error=" + str(mt5.last_error()))
            continue
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            updated += 1
            log.info("SL gesetzt: #" + str(pos.ticket) + " -> " + str(sl_valid))
        else:
            log.error("SL-Move fehlgeschlagen #" + str(pos.ticket) + ": retcode=" +
                      str(result.retcode) + " " + str(getattr(result, "comment", "")))
    return updated


# ─── Move TP to Price ────────────────────────────────────────────────────────
def move_tp_to_price(new_tp: float, symbol: str = None) -> int:
    """Setzt TP aller offenen Positionen auf einen konkreten Preis."""
    updated = 0
    positions = mt5.positions_get()
    if not positions:
        log.warning("move_tp_to_price: keine Positionen offen")
        return 0
    log.info("move_tp_to_price: " + str(len(positions)) + " Positionen, TP=" + str(new_tp))
    for pos in positions:
        if symbol and pos.symbol.upper().replace(".P","").replace(".S","") != symbol.upper().replace(".P","").replace(".S",""):
            continue
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": pos.ticket,
            "sl":       pos.sl,
            "tp":       new_tp,
        }
        # Digit-Rounding
        sym_info = mt5.symbol_info(pos.symbol)
        digits = sym_info.digits if sym_info else 5
        tp_rounded = float(round(float(new_tp), digits))
        request["tp"] = tp_rounded

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            updated += 1
            log.info("TP gesetzt: #" + str(pos.ticket) + " → " + str(tp_rounded))
        else:
            err = mt5.last_error()
            retcode = getattr(result, "retcode", "None") if result else "None"
            log.error("TP-Move fehlgeschlagen #" + str(pos.ticket) +
                      " retcode=" + str(retcode) +
                      " last_error=" + str(err) +
                      " TP=" + str(tp_rounded) +
                      " SL=" + str(pos.sl) +
                      " price=" + str(pos.price_open))
    return updated


# ─── Move TP Level (TP1/TP2/TP3) ─────────────────────────────────────────────
def move_tp_level(new_tp: float, tp_num: int = None, symbol: str = None) -> int:
    """
    Setzt TP für eine spezifische Layer-Gruppe (TP1, TP2 oder TP3).
    tp_num=None → alle Positionen (wie move_tp_to_price).
    tp_num=1    → nur TP1-Layers, tp_num=2 → nur TP2-Layers usw.
    """
    updated = 0

    # Wenn tp_num angegeben: nur die entsprechenden Tickets updaten
    if tp_num and symbol and symbol in state.tp_layers:
        key = f"tp{tp_num}"
        tickets = state.tp_layers[symbol].get(key, [])
        if not tickets:
            log.warning("Keine Tickets für " + str(symbol) + " " + str(key) +
                        " → setze TP auf alle offenen Positionen")
            return move_tp_to_price(new_tp, symbol)
        for ticket in tickets:
            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                continue
            for pos in positions:
                if pos.ticket != ticket:
                    continue
                request = {
                    "action":   mt5.TRADE_ACTION_SLTP,
                    "symbol":   pos.symbol,
                    "position": pos.ticket,
                    "sl":       pos.sl,
                    "tp":       new_tp,
                }
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    updated += 1
                    log.info(f"✅ TP{tp_num} gesetzt: #{pos.ticket} → {new_tp}")
                else:
                    log.error(f"❌ TP{tp_num} fehlgeschlagen #{pos.ticket}: {result}")
        # tp_layers State aktualisieren
        if updated and symbol in state.tp_layers:
            state.tp_layers[symbol][key] = tickets  # tickets bleiben, TP-Preis ist in MT5
        return updated

    # Kein tp_num → alle Positionen (Fallback)
    return move_tp_to_price(new_tp, symbol)


# ─── Partial Close ───────────────────────────────────────────────────────────
def _channel_code(channel: str) -> str:
    """Kurzer, leerzeichenfreier Kanal-Code fuers MT5-Comment (PUPrime kappt auf
    16 Zeichen). Muss zu den Keyword-Matches passen (gtmo/paul/tfxc)."""
    c = (channel or "").upper()
    if "GTMO" in c:
        return "GTMO"
    if "GOLDHUNTER" in c or "PAUL" in c:
        return "PAUL"
    if "TFXC" in c:
        return "TFXC"
    if "GHP" in c or "JACKPOT" in c:
        if "INDICES" in c or "CRYPTO" in c:
            return "GHPI"
        return "GHPF"
    import re as _re
    return (_re.sub(r"[^A-Z0-9]", "", c)[:4] or "XX")


def partial_close(channel_name: str = None, fraction: float = 0.33) -> int:
    """
    Schliesst ~1/3 der offenen Positionen (schlechteste zuerst).
    Triggered durch "close some profit", "take half", "take partial" etc.
    Gibt Anzahl geschlossener Positionen zurück.
    """
    try:
        all_pos = mt5.positions_get()
        if not all_pos:
            return 0

        # Kanalspezifisch filtern (via MT5-Comment)
        if channel_name:
            # Comment traegt nur channel[:8] -> ebenso kuerzen, sonst kein Match
            ch_lower = _channel_code(channel_name).lower()
            positions = [p for p in all_pos
                         if p.magic == MAGIC_NUMBER and ch_lower in (p.comment or "").lower()]
        else:
            positions = [p for p in all_pos if p.magic == MAGIC_NUMBER]

        if not positions:
            return 0

        # Schlechteste zuerst sortieren (kleinster P&L)
        positions_sorted = sorted(positions, key=lambda p: p.profit)

        # Bei genau EINER offenen Layer -> halbes Volumen schliessen statt der
        # ganzen Layer (GTMo-Teilausstieg: er schliesst eine von vielen, bei uns
        # = halber Runner). Rest bleibt offen.
        if len(positions_sorted) == 1:
            pos = positions_sorted[0]
            half = round(pos.volume / 2.0, 2)
            if half < 0.01:
                log.info("Partial-Close: einzelne Layer bei Min-Lot (" +
                         str(pos.volume) + ") - kein Teil-Close, bleibt offen")
                return 0
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                return 0
            close_price = tick.bid if pos.type == 0 else tick.ask
            req = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       pos.symbol,
                "volume":       half,
                "type":         mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                "position":     pos.ticket,
                "price":        close_price,
                "deviation":    30,
                "magic":        MAGIC_NUMBER,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info("PARTIAL_CLOSE (halbe Layer) #" + str(pos.ticket) + " " +
                         pos.symbol + " " + str(half) + "/" + str(pos.volume) +
                         " Lot zu | Rest offen")
                return 1
            rc = result.retcode if result else "None"
            log.warning("PARTIAL_CLOSE (halbe Layer) fehlgeschlagen: retcode=" + str(rc))
            return 0

        # Anzahl zu schliessende Positionen (mindestens 1, maximal fraction)
        # Stufe A: getrackte Runner (tp=0) NIE voll schliessen.
        _runners = runner_tickets()
        _closeable = [p for p in positions_sorted if p.ticket not in _runners]
        if not _closeable:
            # Nur Runner offen -> schlechtesten Runner halbieren statt schliessen
            _rp = positions_sorted[0]
            _half = round(_rp.volume / 2.0, 2)
            if _half < 0.01:
                log.info("Partial-Close: nur Runner bei Min-Lot - bleibt offen")
                return 0
            _tk = mt5.symbol_info_tick(_rp.symbol)
            if not _tk:
                return 0
            _cp = _tk.bid if _rp.type == 0 else _tk.ask
            _r = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": _rp.symbol,
                "volume": _half,
                "type": mt5.ORDER_TYPE_SELL if _rp.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": _rp.ticket, "price": _cp, "deviation": 30,
                "magic": MAGIC_NUMBER, "type_filling": mt5.ORDER_FILLING_IOC,
            })
            if _r and _r.retcode == mt5.TRADE_RETCODE_DONE:
                log.info("PARTIAL_CLOSE (Runner halbiert) #" + str(_rp.ticket) +
                         " " + str(_half) + "/" + str(_rp.volume) + " Lot zu | Runner laeuft")
                return 1
            log.warning("PARTIAL_CLOSE (Runner halbiert) fehlgeschlagen: retcode=" +
                        str(_r.retcode if _r else "None"))
            return 0
        # Anzahl zu schliessende Worker (mindestens 1, maximal fraction)
        n_close = max(1, round(len(_closeable) * fraction))
        to_close = _closeable[:n_close]

        closed = 0
        for pos in to_close:
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                continue
            close_price = tick.bid if pos.type == 0 else tick.ask
            req = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       pos.symbol,
                "volume":       pos.volume,
                "type":         mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                "position":     pos.ticket,
                "price":        close_price,
                "deviation":    30,
                "magic":        MAGIC_NUMBER,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                pnl = round(pos.profit, 2)
                log.info("PARTIAL_CLOSE #" + str(pos.ticket) + " " + pos.symbol +
                         " P&L=" + str(pnl))
                closed += 1
            else:
                rc = result.retcode if result else "None"
                log.warning("PARTIAL_CLOSE fehlgeschlagen: retcode=" + str(rc))

        return closed
    except Exception as e:
        log.error("partial_close: " + str(e))
        return 0


# ─── Hold Lowest Layer ───────────────────────────────────────────────────────
def tfxc_lock_after_tp1(channel_name: str, symbol: str = None) -> tuple:
    """TFXC: nach TP1-Hit SL nachziehen. (locked, be_set, closed)"""
    frac = float(os.getenv("TFXC_LOCK_FRAC", "0.5"))
    min_buf_pts = int(os.getenv("TFXC_MIN_BUFFER_POINTS", "20"))
    locked = be_set = closed = 0
    positions = mt5.positions_get() or []
    rel = [p for p in positions
           if p.magic == MAGIC_NUMBER and "tfxc" in (p.comment or "").lower()]
    if symbol:
        rel = [p for p in rel if p.symbol == symbol]
    if not rel:
        log.info("TFXC TP1-Lock: keine offene TFXC-Position")
        return (0, 0, 0)
    for pos in rel:
        si = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if not si or not tick:
            continue
        point = si.point
        spread = max(0.0, tick.ask - tick.bid)
        stops_lvl = getattr(si, "trade_stops_level", 0) or 0
        safe = max(stops_lvl * point, 2.0 * spread, min_buf_pts * point)
        is_buy = (pos.type == mt5.POSITION_TYPE_BUY)
        entry = pos.price_open
        price = tick.bid if is_buy else tick.ask
        in_profit = (price > entry) if is_buy else (price < entry)
        if not in_profit:
            log.info("TFXC TP1-Lock #" + str(pos.ticket) + ": nicht im Plus, uebersprungen")
            continue
        if is_buy:
            target = round(entry + frac * (price - entry), si.digits)
            entry_sl = round(entry, si.digits)
            if price - target >= safe:
                new_sl, stage = target, "LOCK"
            elif price - entry_sl >= safe:
                new_sl, stage = entry_sl, "BE"
            else:
                new_sl, stage = None, "CLOSE"
        else:
            target = round(entry - frac * (entry - price), si.digits)
            entry_sl = round(entry, si.digits)
            if target - price >= safe:
                new_sl, stage = target, "LOCK"
            elif entry_sl - price >= safe:
                new_sl, stage = entry_sl, "BE"
            else:
                new_sl, stage = None, "CLOSE"
        if new_sl is not None and pos.sl:
            worse = (new_sl <= pos.sl) if is_buy else (new_sl >= pos.sl)
            if worse:
                log.info("TFXC TP1-Lock #" + str(pos.ticket) + ": SL bereits besser")
                continue
        if stage == "CLOSE":
            ctype = (mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY)
            cprice = tick.bid if is_buy else tick.ask
            r = mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "position": pos.ticket,
                "symbol": pos.symbol, "volume": pos.volume, "type": ctype,
                "price": cprice, "deviation": 20, "magic": MAGIC_NUMBER,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "comment": "TFXC-TP1-close"})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
                log.info("TFXC TP1-Lock: #" + str(pos.ticket) + " geschlossen (SL zu nah)")
            else:
                log.error("TFXC TP1-Lock: Close fehlgeschlagen #" + str(pos.ticket) + " " + str(r))
            continue
        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": pos.ticket,
            "symbol": pos.symbol, "sl": new_sl, "tp": pos.tp})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            if stage == "LOCK":
                locked += 1
            else:
                be_set += 1
            log.info("TFXC TP1-Lock: #" + str(pos.ticket) + " " + stage +
                     " SL -> " + str(new_sl) + " (safe=" + str(round(safe, 5)) + ")")
        else:
            log.error("TFXC TP1-Lock: SL-Setzen fehlgeschlagen #" + str(pos.ticket) + " " + str(r))
    return (locked, be_set, closed)


def _hold_lowest_skipped(channel_name: str) -> bool:
    """True, wenn fuer diesen Kanal KEIN Hold-Lowest ausgefuehrt werden soll.
    Diese Kanaele haben verlaessliche feste TPs - ein Eingriff zum Marktpreis
    auf eine 'TP hit'-Jubelmeldung hin schliesst gesunde Layer zu frueh.
    Konfigurierbar: HOLD_LOWEST_SKIP_CHANNELS (kommagetrennt, leer = keiner)."""
    raw = os.getenv("HOLD_LOWEST_SKIP_CHANNELS", "tfxc,gtmo")
    keys = [k.strip().lower() for k in raw.split(",") if k.strip()]
    ch = (channel_name or "").lower()
    return any(k in ch for k in keys)


def hold_lowest_layer(symbol: str = None) -> int:
    """
    Schliesst alle Positionen AUSSER der profitabelsten (= niedrigste P&L bei SELL,
    höchste bei BUY, oder einfach: behalte die mit dem besten P&L).
    Gibt Anzahl geschlossener Positionen zurück.
    """
    positions = mt5.positions_get()
    if not positions:
        return 0

    relevant = [p for p in positions if p.magic == MAGIC_NUMBER]
    if symbol:
        relevant = [p for p in relevant if p.symbol == symbol]

    if len(relevant) <= 1:
        log.info("Hold-lowest: nur 1 Position offen, nichts zu tun")
        return 0

    # Beste Position = höchster unrealisierter Gewinn
    best = max(relevant, key=lambda p: p.profit)
    log.info(f"Hold-lowest: behalte #{best.ticket} (P&L: {best.profit:.2f}), schliesse {len(relevant)-1} andere")

    closed = 0
    _runners = runner_tickets()
    for pos in relevant:
        if pos.ticket == best.ticket:
            continue
        if pos.ticket in _runners:
            log.info("Hold-lowest: Runner #" + str(pos.ticket) + " geschuetzt")
            continue
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue
        close_type = (mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY
                      else mt5.ORDER_TYPE_BUY)
        close_price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     pos.ticket,
            "price":        close_price,
            "deviation":    30,
            "magic":        MAGIC_NUMBER,
            "comment":      "TeleTrader-HoldLowest",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            log.info(f"✅ Layer geschlossen: #{pos.ticket} P&L: {pos.profit:.2f}")
        else:
            log.error(f"❌ Close fehlgeschlagen #{pos.ticket}: {result}")
    return closed


# ─── Close Positions ─────────────────────────────────────────────────────────
# --- NOT-AUS / Pause ---------------------------------------------------------
# --- Runner-Tracking (Stufe A) -----------------------------------------------
RUNNERS_FILE = "runners.json"  # relativ zum CWD (~/teletrader): Wine-sicher, wie bot.log

def _load_runners():
    try:
        import json as _json
        if os.path.exists(RUNNERS_FILE):
            with open(RUNNERS_FILE, "r") as _f:
                d = _json.load(_f)
                return d if isinstance(d, dict) else {}
    except Exception as _e:
        log.error("runners.json laden: " + str(_e))
    return {}

def _save_runners(d):
    try:
        import json as _json
        with open(RUNNERS_FILE, "w") as _f:
            _json.dump(d, _f)
    except Exception as _e:
        log.error("runners.json speichern: " + str(_e))

def mark_runner(ticket, channel="", symbol="", tp1=None, is_buy=None, entry=None):
    d = _load_runners()
    rec = {"channel": str(channel), "symbol": str(symbol),
           "ts": datetime.now().isoformat(), "be_done": False}
    if tp1 is not None:
        try: rec["tp1"] = float(tp1)
        except Exception: pass
    if is_buy is not None:
        rec["is_buy"] = bool(is_buy)
    if entry is not None:
        try: rec["entry"] = float(entry)
        except Exception: pass
    d[str(ticket)] = rec
    _save_runners(d)
    log.info("Runner markiert #" + str(ticket) + " -> runners.json")

def _mark_runner_be(ticket):
    """Stufe C: be_done-Flag fuer einen Runner setzen (reload-modify-save)."""
    d = _load_runners()
    if str(ticket) in d and isinstance(d[str(ticket)], dict):
        d[str(ticket)]["be_done"] = True
        _save_runners(d)

def unmark_runner(ticket):
    d = _load_runners()
    if str(ticket) in d:
        d.pop(str(ticket), None)
        _save_runners(d)
        log.info("Runner entfernt #" + str(ticket))

def runner_tickets():
    out = set()
    for t in _load_runners().keys():
        try:
            out.add(int(t))
        except Exception:
            pass
    return out

def prune_runners():
    """Entfernt Runner-Eintraege, deren Position nicht mehr offen ist."""
    try:
        d = _load_runners()
        if not d:
            return
        open_tk = set(str(p.ticket) for p in (mt5.positions_get() or [])
                      if p.magic == MAGIC_NUMBER)
        removed = [t for t in list(d.keys()) if t not in open_tk]
        for t in removed:
            d.pop(t, None)
        if removed:
            _save_runners(d)
            log.info("prune_runners: " + str(len(removed)) + " verwaiste entfernt")
    except Exception as _e:
        log.error("prune_runners: " + str(_e))


PAUSE_FLAG = "TRADING_PAUSED"  # relativ zum CWD (~/teletrader): Wine-sicher, wie runners.json

def is_trading_paused() -> bool:
    return os.path.exists(PAUSE_FLAG)

def set_trading_paused(on: bool):
    try:
        if on:
            with open(PAUSE_FLAG, "w") as _f:
                _f.write(datetime.now().isoformat())
        elif os.path.exists(PAUSE_FLAG):
            os.remove(PAUSE_FLAG)
    except Exception as _e:
        log.error("Pause-Flag Fehler: " + str(_e))

async def _enable_algo_trading_via_gui() -> bool:
    """
    Fordert den nativen Linux-Watcher (algoenabler.service) per Flag-Datei an,
    Ctrl+E auf dem MT5-Fenster zu druecken. Der Bot laeuft unter Wine und kann
    den Linux-xdotool nicht direkt starten (WinError 2) -> Anforderung ueber
    das gemeinsame Dateisystem (Flag-Datei) ist Wine-sicher.
    Ctrl+E togglt -> nur anfordern, wenn trade_allowed AUS ist.
    Rueckgabe True, wenn danach trade_allowed True ist.
    """
    try:
        tinfo = mt5.terminal_info()
        if tinfo and tinfo.trade_allowed:
            return True
        # Flag relativ zum CWD (~/teletrader), wie runners.json -> Wine-sicher
        with open("ENABLE_ALGO_REQUEST", "w") as _f:
            _f.write(datetime.now().isoformat())
        # Watcher pollt im Sekundentakt; bis zu 6s auf das Umschalten warten
        for _ in range(6):
            await asyncio.sleep(1)
            t2 = mt5.terminal_info()
            if t2 and t2.trade_allowed:
                return True
        return False
    except Exception as _e:
        log.error("AlgoTrading-Flag Fehler: " + str(_e))
        return False


def panic_close_all() -> tuple:
    """NOT-AUS: schliesst ALLE eigenen (Magic) Positionen + cancelt alle eigenen
    Pending-Orders. Fremde/manuelle Trades bleiben unangetastet."""
    closed = 0
    cancelled = 0
    for pos in [p for p in (mt5.positions_get() or []) if p.magic == MAGIC_NUMBER]:
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue
        close_type = (mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY
                      else mt5.ORDER_TYPE_BUY)
        close_price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     pos.ticket,
            "price":        close_price,
            "deviation":    30,
            "magic":        MAGIC_NUMBER,
            "comment":      "TeleTrader-Panic",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            log.info("PANIK Close #" + str(pos.ticket) + " " + pos.symbol +
                     " | P&L: " + str(round(pos.profit, 2)))
        else:
            log.error("PANIK Close FEHLER #" + str(pos.ticket) + ": " + str(result))
    for o in (mt5.orders_get() or []):
        if o.magic != MAGIC_NUMBER:
            continue
        result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            cancelled += 1
            log.info("PANIK Cancel Pending #" + str(o.ticket))
        else:
            log.error("PANIK Cancel FEHLER #" + str(o.ticket) + ": " + str(result))
    return closed, cancelled


def _positions_safe(retries: int = 3, pause: float = 0.15):
    """positions_get() mit Retry - Wine liefert sporadisch leer trotz offener
    Positionen. Gibt Liste zurueck (nie None)."""
    import time as _t
    p = None
    for attempt in range(retries):
        p = mt5.positions_get()
        if p:
            if attempt > 0:
                log.info("positions_get: gefuellt bei Versuch " + str(attempt + 1))
            return p
        if attempt < retries - 1:
            _t.sleep(pause)
    return p if p is not None else []


def close_positions_by_channel(channel_name: str, symbol: str = None) -> int:
    """
    Schliesst alle offenen Positionen eines Kanals (und optional eines Symbols).
    Gibt Anzahl erfolgreich geschlossener Positionen zurueck.
    """
    closed = 0
    positions = _positions_safe()
    if not positions:
        log.info("Close [" + str(channel_name) +
                 "]: positions_get leer nach Retry - nichts zu schliessen")
        return 0

    # Nur eigene Bot-Positionen (Magic) - nie fremde/manuelle Trades anfassen
    own = [p for p in positions if p.magic == MAGIC_NUMBER]
    # Symbol-Filter nur bei konkretem Symbol (nicht bei "alle"/None)
    if symbol and str(symbol).lower() not in ("alle", "all", "none", ""):
        own = [p for p in own if p.symbol == symbol]

    # Kanal-Scoping: Zugehoerigkeit ueber Comment (persistent) ODER getrackte
    # Tickets. So schliesst z.B. TFXCs Close NUR TFXC-Positionen, nie GTMo.
    _ch_key = _channel_code(channel_name).lower()
    _ch_tickets = _channel_open_tickets.get(channel_name, set())
    targets = [p for p in own
               if (_ch_key and _ch_key in (p.comment or "").lower())
               or (p.ticket in _ch_tickets)]

    if not targets:
        log.info("Close [" + str(channel_name) +
                 "]: keine offene Position dieses Kanals - nichts geschlossen")
        return 0
    log.info("Close [" + str(channel_name) + "]: " + str(len(targets)) +
             " Position(en) dieses Kanals (kanal-gescoped)")

    for pos in targets:
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue

        close_type = (mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY
                      else mt5.ORDER_TYPE_BUY)
        close_price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     pos.ticket,
            "price":        close_price,
            "deviation":    30,
            "magic":        MAGIC_NUMBER,
            "comment":      "TeleTrader-Close",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            log.info(f"✅ Position geschlossen: #{pos.ticket} {pos.symbol} | P&L: {pos.profit:.2f}")
        else:
            log.error(f"❌ Close fehlgeschlagen #{pos.ticket}: {result}")
    return closed


# ─── Breakeven ────────────────────────────────────────────────────────────────
def set_breakeven(channel_name: str, symbol: str = None, channel_scoped: bool = False) -> tuple[int, int]:
    """
    Setzt SL auf Entry + 1 Pip (Breakeven).
    Plausibilitätsprüfung: wenn Position im Minus ist (Entry nicht erreichbar),
    wird SL stattdessen 10 Pips unter/über dem aktuellen Kurs gesetzt.
    Gibt (adjusted, fallback_count) zurück.
    """
    adjusted = 0
    fallback = 0
    positions = mt5.positions_get()
    if not positions:
        return 0, 0

    for pos in positions:
        if pos.magic != MAGIC_NUMBER:
            continue
        if symbol and pos.symbol != symbol:
            continue
        if channel_scoped and channel_name and _channel_code(channel_name).lower() not in (pos.comment or "").lower():
            continue

        sym_info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if not sym_info or not tick:
            continue

        one_pip = sym_info.point * 10      # 1 Pip
        ten_pips = sym_info.point * 100    # 10 Pips (Fallback-Abstand)

        # Mindestabstand den MT5 vorschreibt
        # trade_stops_level ist der korrekte Attributname in der Python API
        stops_lvl = getattr(sym_info, 'trade_stops_level', 0) or 0
        min_distance = stops_lvl * sym_info.point
        # Sicherheitspuffer: mindestens 15 Pips Abstand vom aktuellen Kurs
        safe_distance = max(min_distance, ten_pips * 1.5)

        if pos.type == mt5.POSITION_TYPE_BUY:
            ideal_sl = round(pos.price_open + one_pip, sym_info.digits)
            current_price = tick.bid

            # Im Minus wenn aktueller Kurs unter Entry
            if current_price < pos.price_open:
                # Fallback: safe_distance unter aktuellem Bid
                new_sl = round(current_price - safe_distance, sym_info.digits)
                is_fallback = True
                log.info(f"⚠️ Position #{pos.ticket} im Minus "
                         f"(Entry {pos.price_open} > Bid {current_price}) "
                         f"→ Fallback SL: {new_sl} (Abstand: {safe_distance:.5f})")
            else:
                # Im Plus: ideal SL, aber mindestens safe_distance unter Bid
                new_sl = min(ideal_sl, round(current_price - safe_distance, sym_info.digits))
                is_fallback = False

            # Nicht verschlechtern
            if pos.sl and new_sl <= pos.sl:
                log.info(f"⏭ BE übersprungen #{pos.ticket}: SL {pos.sl} bereits besser")
                continue

        else:  # SELL
            ideal_sl = round(pos.price_open - one_pip, sym_info.digits)
            current_price = tick.ask

            if current_price > pos.price_open:
                # Fallback: safe_distance über aktuellem Ask
                new_sl = round(current_price + safe_distance, sym_info.digits)
                is_fallback = True
                log.info(f"⚠️ Position #{pos.ticket} im Minus "
                         f"(Entry {pos.price_open} < Ask {current_price}) "
                         f"→ Fallback SL: {new_sl} (Abstand: {safe_distance:.5f})")
            else:
                new_sl = max(ideal_sl, round(current_price + safe_distance, sym_info.digits))
                is_fallback = False

            if pos.sl and new_sl >= pos.sl:
                log.info(f"⏭ BE übersprungen #{pos.ticket}: SL {pos.sl} bereits besser")
                continue

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": pos.ticket,
            "sl":       new_sl,
            "tp":       pos.tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            if is_fallback:
                fallback += 1
                log.info(f"✅ Fallback-SL gesetzt: #{pos.ticket} → {new_sl} (10 Pips unter Kurs)")
            else:
                adjusted += 1
                log.info(f"✅ Breakeven gesetzt: #{pos.ticket} → {new_sl}")
        else:
            log.error(f"❌ BE fehlgeschlagen #{pos.ticket}: {result}")

    return adjusted, fallback


async def send_daily_summary():
    """Schickt tägliche Zusammenfassung ans Handy"""
    info = mt5.account_info()
    balance = info.balance if info else 0

    msg = (
        f"📊 *TAGESABSCHLUSS – {datetime.now().strftime('%d.%m.%Y')}*\n"
        f"{'─' * 30}\n"
        f"Trades ausgeführt: *{state.daily_stats['trades']}*\n"
        f"Signale abgelehnt: *{state.daily_stats['skipped']}*\n"
        f"Cancellations: *{state.daily_stats['cancelled']}*\n"
        f"{'─' * 30}\n"
        f"Aktueller Kontostand: *${balance:.2f}*\n"
        f"Phase: *{state.phase}* {'🔍' if state.phase == 1 else '👀' if state.phase == 2 else '🤖'}"
    )
    await send_notification(msg)

    # Stats zurücksetzen
    state.daily_stats = {"trades": 0, "cancelled": 0, "skipped": 0, "profit": 0.0}
    state.last_summary_date = datetime.now().strftime("%Y-%m-%d")


# ─── Phasensystem ─────────────────────────────────────────────────────────────
async def handle_phase_command(text: str) -> bool:
    """Verarbeitet /phase1, /phase2, /phase3, /status Befehle"""
    cmd = text.strip().lower()

    if cmd == "/phase1":
        state.phase = 1
        await send_notification(
            "🔍 *Phase 1 aktiv*\nIch frage dich bei jedem Signal."
        )
        return True
    elif cmd == "/phase2":
        state.phase = 2
        await send_notification(
            "👀 *Phase 2 aktiv*\nIch trade automatisch und erinnere dich regelmäßig."
        )
        return True
    elif cmd == "/phase3":
        state.phase = 3
        await send_notification(
            "🤖 *Phase 3 aktiv*\nVollautomatisch. Du kriegst nur die tägliche Zusammenfassung."
        )
        return True
    elif cmd.startswith("/log"):
        # /log oder /log 20 (Anzahl Zeilen)
        parts = cmd.strip().split()
        n = 30
        if len(parts) > 1 and parts[1].isdigit():
            n = min(int(parts[1]), 100)
        try:
            import os as _os_log
            log_file = _os_log.environ.get("TELETRADER_LOG", "")
            if not log_file or not _os_log.path.exists(log_file):
                log_file = "C:\\TeleTrader\\teletrader.log"
            with open(log_file, encoding="utf-8", errors="replace") as lf:
                lines = lf.readlines()
            tail = lines[-n:]
            # Nur relevante Zeilen (kein reiner Connection-Spam)
            filtered = [l.rstrip() for l in tail
                        if not any(x in l for x in [
                            "Connecting to 149", "Connection to 149",
                            "Disconnecting from 149", "Disconnection from 149",
                            "Attempt", "Failed reconnect"
                        ])]
            text = "\n".join(filtered[-n:])
            # Telegram Nachricht max 4096 Zeichen
            if len(text) > 3800:
                text = "...\n" + text[-3800:]
            await send_notification("📋 *Log (letzte " + str(n) + " Zeilen)*\n```\n" + text + "\n```")
        except Exception as e:
            await send_notification("Log-Fehler: " + str(e))
        return True

    elif cmd == "/help":
        lines = [
            "TeleTrader Befehle:",
            "/status - Balance und Positionen",
            "/balance - Schnelle Balance",
            "/log 30 - Letzte 30 Log-Zeilen",
            "/phase1 /phase2 /phase3 - Modus wechseln",
            "/closeall - Alle Positionen schliessen",
            "/live - Auf Live-Konto wechseln",
            "/demo - Auf Demo-Konto wechseln",
            "/stop - Bot stoppen",
            "/restart - Bot neu starten",
            "/help - Diese Hilfe",
        ]
        await send_notification("\n".join(lines))
        return True

    elif cmd == "/poscom":
        _ps = mt5.positions_get() or []
        if not _ps:
            await send_notification("Keine offenen Positionen")
        else:
            _l = []
            for _p in _ps:
                _l.append("#" + str(_p.ticket) + " magic=" + str(_p.magic) +
                          " tp=" + str(_p.tp) + " comment=[" + str(_p.comment) + "]")
            await send_notification("POS-COMMENTS:\n" + "\n".join(_l))
        return True

    elif cmd == "/balance":
        info = mt5.account_info()
        if info:
            pos = [p for p in (mt5.positions_get() or []) if p.magic == MAGIC_NUMBER]
            pnl = sum(p.profit for p in pos)
            sign = "+" if pnl >= 0 else ""
            await send_notification(
                "Balance: $" + str(round(info.balance, 2)) +
                " | Equity: $" + str(round(info.equity, 2)) +
                "\nPos: " + str(len(pos)) +
                " | PnL: " + sign + str(round(pnl, 2)) + "$"
            )
        else:
            await send_notification("MT5 nicht verbunden")
        return True

    elif cmd == "/closeall":
        pos_all = mt5.positions_get() or []
        closed = 0
        for p in pos_all:
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                continue
            price = tick.bid if p.type == 0 else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket,
                "symbol": p.symbol, "volume": p.volume,
                "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                "price": price, "deviation": 50, "magic": MAGIC_NUMBER,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            r = mt5.order_send(req)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        await send_notification("Geschlossen: " + str(closed) + "/" + str(len(pos_all)))
        return True

    elif cmd == "/debug":
        try:
            import os as _os_dbg
            log_path = _os_dbg.environ.get("TELETRADER_LOG", "/home/alexander_lacher/teletrader/bot.log")
            with open(log_path, encoding="utf-8", errors="replace") as lf:
                lines = lf.readlines()
            errs = [l.strip() for l in lines[-200:]
                    if any(x in l for x in ["ERROR", "Traceback", "Error:", "Exception"])]
            msg = ("Letzte Fehler:\n" + "\n".join(errs[-10:])) if errs else "Keine Fehler"
            await send_notification(msg[-3800:])
        except Exception as e:
            await send_notification("Debug-Fehler: " + str(e))
        return True

    elif cmd == "/heal":
        await send_notification("Self-Healer laeuft...")
        try:
            import subprocess, os as _os_heal
            healer = "/home/alexander_lacher/teletrader/self_healer.py"
            import shutil as _sh
            if _sh.which("bash"):
                result = subprocess.run(
                    ["bash", "-c", "python3 '" + healer + "'"],
                    capture_output=True, text=True, timeout=60
                )
                out = (result.stdout + result.stderr)[-1500:]
                await send_notification("Heal-Ergebnis:\n" + out)
            else:
                await send_notification("Heal läuft im Hintergrund (Watchdog)")
        except Exception as e:
            await send_notification("Heal-Fehler: " + str(e))
        return True

    elif cmd in ("/live", "/demo"):
        switch_to = "live" if cmd == "/live" else "demo"
        # Immer Linux-Pfad verwenden (funktioniert unter Wine)
        env_file = "/home/alexander_lacher/teletrader/.env"
        try:
            # Backup der .env
            import shutil as _sh
            _sh.copy2(env_file, env_file + ".bak")
            with open(env_file, encoding="utf-8") as ef:
                env_lines = ef.readlines()
            new_lines = []
            changed = False
            for line in env_lines:
                if line.strip().startswith("DEMO_MODE="):
                    new_lines.append("DEMO_MODE=" + ("false" if switch_to == "live" else "true") + "\n")
                    changed = True
                else:
                    new_lines.append(line)
            if not changed:
                new_lines.append("DEMO_MODE=" + ("false" if switch_to == "live" else "true") + "\n")
            with open(env_file, "w", encoding="utf-8") as ef:
                ef.writelines(new_lines)
            # Verify
            with open(env_file, encoding="utf-8") as ef:
                verify = ef.read()
            expected = "DEMO_MODE=" + ("false" if switch_to == "live" else "true")
            if expected not in verify:
                raise Exception(".env Schreiben fehlgeschlagen – Backup wiederhergestellt")
            icon = "🔴" if switch_to == "live" else "🟡"
            mode = "LIVE ⚠️" if switch_to == "live" else "DEMO"
            await send_notification(
                icon + " Wechsle zu " + mode + "\n"
                "Bot wird neu gestartet..."
            )
            # Watchdog übernimmt Neustart – kein execv unter Wine
            import os as _os, signal as _sig
            _os.kill(_os.getpid(), _sig.SIGTERM)
        except Exception as e:
            await send_notification("Fehler beim Wechsel: " + str(e))
        return True

    elif cmd == "/algotrading":
        try:
            tinfo = mt5.terminal_info()
            if tinfo and tinfo.trade_allowed:
                await send_notification("Algo Trading ist bereits aktiv")
            else:
                ok = False
                for _versuch in range(3):
                    if await _enable_algo_trading_via_gui():
                        ok = True
                        break
                    await asyncio.sleep(2)
                if ok:
                    await send_notification("Algo Trading aktiviert")
                else:
                    await send_notification(
                        "Algo Trading konnte nicht aktiviert werden.\n"
                        "Bitte in MT5 manuell aktivieren (gruener Button oben)."
                    )
        except Exception as e:
            await send_notification("Fehler: " + str(e))
        return True

    elif cmd.startswith("/test"):
        parts = text.strip().split(None, 1)
        signal_text = parts[1] if len(parts) > 1 else ""
        if not signal_text:
            await send_notification(
                "Usage: /test [Signaltext]\n\n"
                "Beispiel:\n"
                "/test Gold buy now 4332.5 SL: 4325 TP1: 4336"
            )
            return True
        await send_notification("Teste Signal: " + signal_text[:80] + "...")
        try:
            tick = mt5.symbol_info_tick(GOLD_SYMBOL)
            cur  = tick.bid if tick else 0.0
            result = await get_interpreter().interpret(
                text=signal_text,
                channel="TEST",
                mt5=mt5,
                channel_history=[],
                current_price=cur,
            )
            action    = result.get("action", "NOISE")
            direction = result.get("direction", "-")
            symbol    = result.get("symbol", "-")
            entry     = result.get("entry", "-")
            sl        = result.get("sl", "-")
            tp1       = result.get("tp1", "-")
            conf      = result.get("confidence", 0)
            reason    = result.get("reasoning", "")[:100]
            msg = (
                "Test-Ergebnis:\n"
                "Aktion: " + action + "\n"
                "Richtung: " + str(direction) + "\n"
                "Symbol: " + str(symbol) + "\n"
                "Entry: " + str(entry) + "\n"
                "SL: " + str(sl) + "\n"
                "TP1: " + str(tp1) + "\n"
                "Confidence: " + str(conf) + "%\n"
                "Grund: " + reason
            )
            if action in ("TRADE", "URGENT") and conf >= 70:
                info = mt5.account_info()
                bal  = info.balance if info else 1000
                lot  = round(0.01 * bal / 100, 2)
                msg += "\n\nWuerde traden: " + str(direction) + " " + str(symbol)
                msg += " | Lot: " + str(lot) + " x 3 Layer"
            else:
                msg += "\n\nKein Trade"
            await send_notification(msg)
        except Exception as e:
            await send_notification("Test-Fehler: " + str(e))
        return True

    elif cmd == "/audit":
        parts = text.strip().split(None, 1)
        hours = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 24
        if not _daily_audit:
            await send_notification("Noch keine Audit-Daten (Bot gerade gestartet)")
            return True
        lines = ["Audit letzte " + str(hours) + "h:\n"]
        for ch, d in _daily_audit.items():
            ch_short = ch[:20]
            lines.append(ch_short + ":")
            lines.append("  Nachrichten: " + str(d["msgs"]))
            lines.append("  Trades: " + str(d["trades"]) + " | Noise: " + str(d["noise"]))
            # Zeige suspicious NOISE (conf 60-80% mit trade-keywords)
            suspicious = [
                dec for dec in d["decisions"]
                if dec["action"] in ("NOISE",) and
                dec["conf"] >= 60 and
                any(w in dec["text"].lower() for w in
                    ["buy","sell","sl","tp","entry","gold","xau"])
            ]
            if suspicious:
                lines.append("  Verdaechtige NOISE (" + str(len(suspicious)) + "):")
                for s in suspicious[-5:]:
                    lines.append("    " + s["ts"] + " conf=" + str(s["conf"]) +
                                 "% " + s["text"][:40])
        await send_notification("\n".join(lines))
        return True

    elif cmd == "/testparachute":
        await send_notification("Test: Fallschirm wird ausgeloest...")
        try:
            positions = [p for p in (mt5.positions_get() or [])
                         if p.magic == MAGIC_NUMBER]
            if not positions:
                await send_notification(
                    "Kein Test moeglich: keine offenen Positionen.\n"
                    "Oeffne zuerst eine Position."
                )
                return True
            closed = 0
            for p in positions:
                tick = mt5.symbol_info_tick(p.symbol)
                if not tick:
                    continue
                price = tick.bid if p.type == 0 else tick.ask
                req = {
                    "action":    mt5.TRADE_ACTION_DEAL,
                    "position":  p.ticket,
                    "symbol":    p.symbol,
                    "volume":    p.volume,
                    "type":      mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                    "price":     price,
                    "deviation": 50,
                    "magic":     MAGIC_NUMBER,
                }
                r = mt5.order_send(req)
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    closed += 1
            info = mt5.account_info()
            bal  = info.balance if info else 0
            await send_notification(
                "Fallschirm-Test abgeschlossen:\n"
                "Geschlossen: " + str(closed) + "/" + str(len(positions)) + " Positionen\n"
                "Balance: $" + str(round(bal, 2)) + "\n"
                "Fallschirm funktioniert!"
            )
        except Exception as e:
            await send_notification("Test-Fehler: " + str(e))
        return True

    elif cmd == "/update":
        await send_notification("Update angefordert - Watchdog führt git pull durch...")
        try:
            import os as _os_up
            # Watchdog-Befehl schreiben - Watchdog erledigt git pull auf Linux-Ebene
            with open("/tmp/teletrader_do_update", "w") as _f:
                _f.write("update")
            await send_notification("Update-Befehl gesetzt. Bot startet in ~30 Sekunden neu.")
            import signal as _sig_up
            _os_up.kill(_os_up.getpid(), _sig_up.SIGTERM)
        except Exception as e:
            await send_notification("Update-Fehler: " + str(e))
        return True


    elif cmd.startswith("/simulate"):
        try:
            parts = text[len("/simulate"):].strip()
            if "|" not in parts:
                await send_notification(
                    "Usage: /simulate KANAL|Signaltext\n\n"
                    "Kanaele: GTMO, PAUL, TFXC\n\n"
                    "Beispiele:\n"
                    "/simulate PAUL|Sell gold at 4185 SL 4205 TP 4175 TP 4165 TP open\n"
                    "/simulate GTMO|Sell gold 4180-4185 SL 4200 TP 4170 TP 4160\n"
                    "/simulate PAUL|Close"
                )
                return True
            channel_alias, signal_text = parts.split("|", 1)
            channel_alias = channel_alias.strip().upper()
            signal_text   = signal_text.strip()
            channel_map = {
                "GTMO": "GTMO VIP",
                "PAUL": "GOLDHUNTER | PAUL",
                "TFXC": "TFXC SIGNALS",
            }
            channel_name = channel_map.get(channel_alias, channel_alias)
            await send_notification("Simuliere: " + channel_name + "\n" + signal_text)
            tick = mt5.symbol_info_tick(GOLD_SYMBOL)
            cur  = tick.bid if tick else 0.0
            result = await get_interpreter().interpret(
                text=signal_text, channel=channel_name, mt5=mt5,
                channel_history=[], current_price=cur,
            )
            action = result.get("action", "NOISE")
            conf   = result.get("confidence", 0)
            tps    = [result.get("tp"+str(i)) for i in range(1,8) if result.get("tp"+str(i))]
            await send_notification(
                "Interpreter: " + action + " conf=" + str(conf) + "%\n"
                "Entry=" + str(result.get("entry","?")) +
                " SL=" + str(result.get("sl","?")) +
                " TPs=" + str(tps)
            )
            sym = resolve_symbol(result.get("symbol","")) or GOLD_SYMBOL
            if action in ("TRADE", "URGENT"):
                sig = TradeSignal(
                    direction=result.get("direction",""),
                    symbol=sym,
                    entry=result.get("entry") or 0.0,
                    entry_low=result.get("entry_low") or 0.0,
                    sl=result.get("sl") or 0.0,
                    tp1=result.get("tp1"), tp2=result.get("tp2"),
                    tp3=result.get("tp3"), tp4=result.get("tp4"),
                    tp5=result.get("tp5"),
                    is_limit=result.get("is_limit", False),
                    is_backup=result.get("is_backup", False),
                    small_lot=result.get("small_lot", False),
                    raw_text=signal_text,
                    text_hash=get_text_hash(signal_text),
                    source_channel=channel_name,
                )
                sig.confidence = conf
                await process_signal(sig)
            elif action == "CLOSE":
                closed = close_positions_by_channel(channel_name, sym)
                await send_notification("Close: " + str(closed) + " Position(en)")
            elif action == "PARTIAL_CLOSE":
                closed = partial_close(channel_name=channel_name)
                await send_notification("Partial-Close: " + str(closed) + " Position(en)")
            elif action == "BREAKEVEN":
                adj, fb = set_breakeven(channel_name, sym)
                await send_notification("Breakeven: " + str(adj) + " gesetzt (" + str(fb) + " Fallback)")
            elif action == "HOLD_LOWEST":
                if _hold_lowest_skipped(channel_name):
                    log.info("HOLD_LOWEST ignoriert (" + str(channel_name)[:20] + ")")
                    await send_notification("TP-Hit erkannt - feste TPs bleiben aktiv (kein Hold-Lowest)")
                else:
                    hold_lowest_layer(sym)
                    await send_notification("Hold-Lowest ausgefuehrt")
            else:
                await send_notification(str(action) + " - im Test keine Ausfuehrung")
        except Exception as e:
            await send_notification("Simulate-Fehler: " + str(e))
        return True

    elif cmd == "/testsignal":
        await send_notification("Test-Signal wird verarbeitet...")
        try:
            test_text = (
                "Gold sell now 4172 - 4177\n"
                "SL: 4180\n"
                "TP: 4170\nTP: 4168\nTP: 4166\nTP: 4164\nTP: open"
            )
            tick = mt5.symbol_info_tick(GOLD_SYMBOL)
            cur = tick.bid if tick else 0.0
            result = await get_interpreter().interpret(
                text=test_text,
                channel="GTMO VIP TEST",
                mt5=mt5,
                channel_history=[],
                current_price=cur,
            )
            action = result.get("action", "?")
            conf   = result.get("confidence", 0)
            entry  = result.get("entry", "?")
            sl     = result.get("sl", "?")
            tps    = [result.get("tp" + str(i)) for i in range(1,8)
                      if result.get("tp" + str(i))]
            await send_notification(
                "Test-Ergebnis:\n"
                "Action: " + str(action) + " conf=" + str(conf) + "%\n"
                "Entry: " + str(entry) + " SL: " + str(sl) + "\n"
                "TPs: " + str(tps) + "\n"
                "(Kein echter Trade gesetzt)"
            )
        except Exception as e:
            await send_notification("Test-Fehler: " + str(e))
        return True

    elif cmd == "/stop":








        await send_notification("\U0001F6D1 NOT-AUS: schliesse alle Positionen + pausiere...")
        closed, cancelled = panic_close_all()
        set_trading_paused(True)
        await send_notification("\U0001F6D1 NOT-AUS aktiv: " + str(closed) +
                                " Position(en) zu, " + str(cancelled) +
                                " Pending gecancelt. Trading PAUSIERT.\n"
                                "\u25B6\uFE0F /resume zum Fortsetzen.")
        return True

    elif cmd == "/pause":
        set_trading_paused(True)
        await send_notification("\u23F8\uFE0F Trading PAUSIERT (neue Trades aus, "
                                "offene werden weiter gemanagt). /resume zum Fortsetzen.")
        return True

    elif cmd == "/resume":
        set_trading_paused(False)
        await send_notification("\u25B6\uFE0F Trading wieder AKTIV.")
        return True

    elif cmd == "/start":
        _p = is_trading_paused()
        await send_notification("\U0001F916 Bot laeuft. Status: " +
                                ("PAUSIERT (/resume zum Fortsetzen)" if _p else "aktiv"))
        return True

    elif cmd == "/restart":
        await send_notification("Bot wird neu gestartet...")
        import os as _os, signal as _sig
        _os.kill(_os.getpid(), _sig.SIGTERM)
        return True

    elif cmd == "/status":
        info = mt5.account_info()
        positions = mt5.positions_get() or []
        our_pos = [p for p in positions if p.magic == MAGIC_NUMBER]
        pending = mt5.orders_get() or []
        our_pend = [o for o in pending if o.magic == MAGIC_NUMBER]

        bal = info.balance if info else 0
        equity = info.equity if info else 0
        pnl_open = sum(p.profit for p in our_pos)
        dd = (1 - equity/bal)*100 if bal > 0 else 0

        # P&L heute (aus daily_stats)
        today_pnl = get_todays_pnl()
        today_trades = state.daily_stats.get("trades", 0)

        # Offene Positionen nach Symbol
        by_symbol = {}
        for p in our_pos:
            if p.symbol not in by_symbol:
                by_symbol[p.symbol] = {"count": 0, "pnl": 0}
            by_symbol[p.symbol]["count"] += 1
            by_symbol[p.symbol]["pnl"] += p.profit

        pos_lines = ""
        for sym, d in by_symbol.items():
            sign = "📈" if d["pnl"] >= 0 else "📉"
            sign_str = "+" if d["pnl"] >= 0 else ""
            pos_lines += f"\n  {sign} {sym}: {d['count']} Layer | P&L: {sign_str}{d['pnl']:.2f}$"

        # Letzte Kanäle
        ch_lines = ""
        for ch, msgs in list(state.channel_history.items())[-3:]:
            if msgs:
                ch_lines += f"\n  {ch}: {msgs[-1][:40]}..."

        now_t = datetime.now().strftime("%H:%M")
        ps = "+" if pnl_open >= 0 else ""
        ts = "+" if today_pnl >= 0 else ""
        status_msg = (
            f"TeleTrader {now_t} | Bal: ${bal:.2f} | EQ: ${equity:.2f} ({-dd:.1f}%DD)\n"
            f"Offen: {ps}{pnl_open:.2f}$ | Heute: {today_trades}T {ts}{today_pnl:.2f}$\n"
            f"Pos: {len(our_pos)} offen | {len(our_pend)} pending{pos_lines}\n"
            f"Phase {state.phase} | 0.01 Lot/$100 | Max 10% Risiko"
        )
        await send_notification(status_msg)
        return True

    elif cmd == "/cancel_test":
        # Storniert alle Test-Orders
        cancelled = 0
        for hash_key, tickets in list(state.open_orders.items()):
            if "test_" in hash_key:
                cancelled += cancel_orders(tickets)
                del state.open_orders[hash_key]
        await send_notification(f"🧪 Test-Orders storniert: {cancelled} Orders")
        return True

    elif cmd == "/reset":
        # Setzt den Bot-State zurück (pending context, open orders)
        ctx_count = len(state.pending_context)
        state.pending_context.clear()
        state.pending_signals.clear()
        await send_notification(
            f"🔄 *State zurückgesetzt*\n"
            f"{ctx_count} Pending-Context(e) gelöscht\n"
            f"Bot ist wieder bereit."
        )
        return True

    return False


# ─── Signal verarbeiten ───────────────────────────────────────────────────────
async def process_signal(sig: TradeSignal):
    """Verarbeitet ein erkanntes Signal je nach Phase"""
    if is_trading_paused():
        log.info("Trading PAUSIERT - Signal uebersprungen (" + str(sig.source_channel) + ")")
        return
    info = mt5.account_info()
    if not info:
        log.error("MT5 nicht verbunden")
        return

    # Margin-Check: tatsaechliche Margin-Anforderung pruefen
    tick_pre = mt5.symbol_info_tick(sig.symbol)
    if tick_pre:
        order_type_pre = (mt5.ORDER_TYPE_BUY if sig.direction == "BUY"
                          else mt5.ORDER_TYPE_SELL)
        price_pre = tick_pre.ask if sig.direction == "BUY" else tick_pre.bid
        required_margin = mt5.order_calc_margin(
            order_type_pre, sig.symbol, 0.01, price_pre) or 0
        if required_margin > 0 and info.margin_free < required_margin * 1.5:
            msg = ("Margin zu knapp: " + str(round(info.margin_free, 2)) +
                   "$ frei, benoetigt ~" + str(round(required_margin, 2)) +
                   "$ pro Layer")
            log.warning(msg)
            await send_notification("⚠️ " + msg)
            return

    # Prioritaetspruefung
    # ── Lose-Streak-Schutz: nach 3 SLs pausieren (nicht für GTMo VIP) ──────
    _is_goldhunter = any(k in sig.source_channel.lower()
                         for k in ("goldhunter", "paul", "gold hunt"))
    _is_gtmo = any(k in sig.source_channel.lower()
                   for k in ("gtmo", "goldtrader", "vip"))
    if not _is_gtmo and _channel_streak.get(sig.source_channel, 0) <= -3:
        log.warning("SKIP: " + sig.source_channel + " hat 3 SLs in Folge → pausiert")
        await send_notification("⏸ " + sig.source_channel +
                                " pausiert (3 SLs in Folge)")
        return

    # ── Goldhunter: max 3 offene Positionen (kein Overtrading) ───────────────
    if _is_goldhunter:
        gh_pos = mt5.positions_get(symbol=sig.symbol) or []
        gh_open = [p for p in gh_pos
                   if p.magic == MAGIC_NUMBER and
                   any(k in (p.comment or "").lower()
                       for k in ("goldhunter", "paul", "gold hunt"))]
        if len(gh_open) >= 3:
            log.info("SKIP Goldhunter: bereits " + str(len(gh_open)) +
                     " offene Positionen → kein Overtrading")
            return

    # ── Doppelposition-Schutz ─────────────────────────────────────────────────
    open_positions = mt5.positions_get(symbol=sig.symbol) or []
    same_dir = [p for p in open_positions
                if p.magic == MAGIC_NUMBER and
                ((p.type == 0 and sig.direction == "BUY") or
                 (p.type == 1 and sig.direction == "SELL"))]
    if len(same_dir) >= MAX_POS_PER_SYMBOL:
        log.info("SKIP: " + sig.symbol + " " + sig.direction +
                 " bereits " + str(len(same_dir)) + " offene Positionen")
        return

    if not await check_channel_permission(sig.source_channel, sig.symbol):
        state.daily_stats["skipped"] += 1
        return

    # SL-Cooldown: Backup-Signale ueberspringen die Sperre
    if not sig.is_backup and is_sl_cooldown(
            sig.source_channel, sig.symbol,
            sig.direction, sig.entry or 0.0):
        state.daily_stats["skipped"] += 1
        await send_notification("SL-Cooldown: " + sig.source_channel +
                                " gleiche Zone gesperrt auf " + sig.symbol)
        return

    # Entry-Duplikat (4h) – Backup-Signale ebenfalls ausnehmen
    if not sig.is_backup and sig.entry and is_entry_duplicate(
            sig.direction, sig.symbol, sig.entry, sig.source_channel):
        state.daily_stats["skipped"] += 1
        await send_notification("Entry-Duplikat: " + sig.direction +
                                " " + sig.symbol + " @ " + str(sig.entry))
        return

    balance = info.balance
    num_layers, lot_per_layer = calculate_layers(
        balance, sig.source_channel, sig.is_backup)
    tps = sig.tps()
    distribution = distribute_layers(num_layers, tps, sig.source_channel)

    # Terminal-Ausgabe
    color = Fore.GREEN if sig.direction == "BUY" else Fore.RED
    print(f"\n{Fore.YELLOW}⚡ SIGNAL [{sig.timestamp}] aus: {sig.source_channel}")
    print(f"{color}  {sig.direction} {sig.symbol} | {num_layers} Layer à 0.01 Lot")
    print(f"{Style.RESET_ALL}  SL: {sig.sl} | TPs: {tps}")
    print(f"  Verteilung: {distribution}")

    if state.phase == 1:
        # Manuelle Bestätigung per Telegram-Button
        await send_confirmation_request(sig, num_layers, distribution)
        log.info(f"Signal zur Bestätigung gesendet: {sig.symbol} {sig.direction}")

    elif state.phase == 2:
        tickets = execute_layers(sig)
        if tickets:
            state.open_orders[sig.text_hash] = tickets
            state.daily_stats["trades"] += 1
            _channel_open_tickets.setdefault(sig.source_channel, set()).update(tickets)
            await send_notification(
                f"🚀 *Auto-Trade ausgeführt*\n"
                f"{sig.direction} {sig.symbol} | {len(tickets)} Layer\n"
                f"SL: `{sig.sl}` | Tickets: {tickets}"
            )

    elif state.phase == 3:
        tickets = execute_layers(sig)
        if tickets:
            state.open_orders[sig.text_hash] = tickets
            state.daily_stats["trades"] += 1
            _channel_open_tickets.setdefault(sig.source_channel, set()).update(tickets)
            log.info(f"Phase 3: Auto-Trade {sig.symbol} | {len(tickets)} Tickets")


# ─── Haupt-Bot ────────────────────────────────────────────────────────────────
async def main():
    global bot_client

    print(f"\n{Fore.YELLOW}{'═'*58}")
    print(f"  TeleTrader AI  –  Finale Version")
    print(f"  Modus: {'🟡 DEMO' if DEMO_MODE else '🔴 LIVE'} | Phase: {state.phase}")
    print(f"{'═'*58}{Style.RESET_ALL}\n")

    # Validierung
    if not TG_BOT_TOKEN or not TG_MY_CHAT_ID:
        print(Fore.RED + "TG_BOT_TOKEN oder TG_MY_CHAT_ID fehlt!" + Style.RESET_ALL)
        return

    # Live-Modus Sicherheitscheck
    if not DEMO_MODE:
        border = "=" * 54
        print("")
        print(Fore.RED + border)
        print("  LIVE-MODUS AKTIV - ECHTES GELD!")
        print(border + Style.RESET_ALL)
        print("")
        checks = [
            (bool(os.getenv("ANTHROPIC_API_KEY")),  "ANTHROPIC_API_KEY gesetzt"),
            (RISK_PER_100 <= 0.07,                  "RISK_PER_100=" + str(RISK_PER_100) + " (empfohlen <= 0.07)"),
            (True, "Lot-Sizing: 0.02/100$ Standard, GHP-Backup 2x"),
            (MAX_POS_PER_SYM <= 10,                 "MAX_POS_PER_SYMBOL=" + str(MAX_POS_PER_SYM) + " (empfohlen <= 10)"),
            (TRAILING_STOP_ENABLED,                 "TRAILING_STOP_ENABLED=true"),
            (MAGIC_NUMBER != 0,                     "MAGIC_NUMBER=" + str(MAGIC_NUMBER)),
        ]
        all_ok = True
        for ok, label in checks:
            tag = (Fore.GREEN + "OK") if ok else (Fore.RED + "!!")
            print("  [" + tag + Style.RESET_ALL + "] " + label)
            if not ok:
                all_ok = False
        print("")
        if not all_ok:
            print(Fore.YELLOW + "Bitte Konfiguration pruefen!" + Style.RESET_ALL)
            print("")
        if os.getenv("AUTO_CONFIRM_LIVE", "false").lower() == "true":
            confirm = "LIVE"
            print(Fore.YELLOW + "AUTO_CONFIRM_LIVE=true – Autostart" + Style.RESET_ALL)
        else:
            confirm = input(Fore.RED + "LIVE-MODUS bestaetigen? Tippe LIVE: " + Style.RESET_ALL).strip()
        if confirm != "LIVE":
            print("Abgebrochen.")
            return
        print(Fore.GREEN + "Live-Modus bestaetigt." + Style.RESET_ALL)
        print("")

    # MT5 verbinden
    if not connect_mt5():
        print(f"{Fore.RED}❌ MT5 Verbindung fehlgeschlagen.{Style.RESET_ALL}")
        return

    # Telegram User-Client (zum Lesen der Signal-Kanäle)
    user_client = TelegramClient("teletrader_user", TG_API_ID, TG_API_HASH)
    await user_client.start(phone=TG_PHONE)
    log.info("Telegram User-Client verbunden.")

    # Telegram Bot-Client (für Bestätigungen & Befehle)
    bot_client = TelegramClient("teletrader_bot", TG_API_ID, TG_API_HASH)
    await bot_client.start(bot_token=TG_BOT_TOKEN)
    log.info("Telegram Bot-Client verbunden.")

    # Signal-Kanäle auflösen
    # Private Kanäle brauchen Dialog-Lookup – get_entity allein reicht nicht
    channel_entities = []

    log.info("Lade Dialoge für private Kanal-Auflösung...")
    dialog_map = {}
    async for dialog in user_client.iter_dialogs():
        eid = str(dialog.id)
        dialog_map[eid] = dialog.entity
        # Telethon speichert Kanal-IDs intern mit -100-Prefix
        # -1001640332422 → auch "1640332422" mappen
        stripped = eid.lstrip("-")
        if stripped.startswith("100") and len(stripped) > 10:
            stripped = stripped[3:]
        dialog_map[stripped] = dialog.entity

    for ch in TG_CHANNELS:
        if not ch:
            continue
        try:
            entity = await user_client.get_entity(ch)
            channel_entities.append(entity)
            log.info(f"✅ Kanal verbunden: {getattr(entity, 'title', ch)}")
        except Exception:
            # Fallback: Dialog-Map (funktioniert für private Kanäle per ID)
            ch_str = str(ch).lstrip("-")
            if ch_str.startswith("100") and len(ch_str) > 10:
                ch_str = ch_str[3:]
            entity = dialog_map.get(str(ch)) or dialog_map.get(ch_str)
            if entity:
                channel_entities.append(entity)
                log.info(f"✅ Privater Kanal verbunden: {getattr(entity, 'title', ch)}")
            else:
                log.error(f"❌ Kanal nicht gefunden: {ch} – stelle sicher dass du Mitglied bist")

    if not channel_entities:
        print(f"{Fore.RED}❌ Keine Kanäle gefunden.{Style.RESET_ALL}")
        return

    # Eigene User-ID prüfen
    me = await user_client.get_me()
    log.info(f"Eingeloggt als: {me.first_name} (ID: {me.id})")

    await send_notification(
        f"🟢 *TeleTrader gestartet*\n"
        f"Modus: {'DEMO ✅' if DEMO_MODE else 'LIVE ⚠️'}\n"
        f"Phase: *{state.phase}* ({'Manuell' if state.phase==1 else 'Auto+Reminder' if state.phase==2 else 'Vollautomatisch'})\n"
        f"Kanäle: *{len(channel_entities)}*\n\n"
        f"Befehle:\n"
        f"/phase1 /phase2 /phase3 – Modus\n"
        f"/status – Balance & Positionen\n"
        f"/balance – Schnelle Balance\n"
        f"/log [N] – Log-Zeilen\n"
        f"/debug – Letzter Fehler\n"
        f"/heal – Auto-Fix\n"
        f"/closeall – Alle Positionen schliessen\n"
        f"/live /demo – Konto wechseln\n"
        f"/algotrading – Algo Trading aktivieren\n"
        f"/restart /stop – Bot steuern\n"
        f"/help – Alle Befehle"
    )

    print(f"{Fore.GREEN}✅ Bereit – überwache {len(channel_entities)} Kanäle{Style.RESET_ALL}\n")

    # ── Eingehende Nachrichten aus Signal-Kanälen ─────────────────────────────
    @user_client.on(events.Raw)
    async def on_user_disconnect(update):
        """Erkennt Verbindungsabbrüche des User-Clients."""
        from telethon.tl.functions.updates import GetStateRequest
        pass  # Telethon feuert Raw-Events auch bei Reconnect

    # ── Verpasste Signale prüfen ──────────────────────────────────────────────
    async def check_missed_signals(lookback_minutes: int = 60):
        """
        Prüft die letzten X Minuten auf verpasste Signale (TRADE + CLOSE + BE).
        Führt verpasste TRADE-Signale direkt aus.
        """
        log.info(f"🔍 Prüfe verpasste Signale ({lookback_minutes} Min)...")
        from datetime import timezone as tz_utc
        cutoff = datetime.now(tz_utc.utc) - timedelta(minutes=lookback_minutes)
        found_any = False

        for entity in channel_entities:
            channel_name = getattr(entity, 'title', str(entity.id))
            history = list((channel_histories if "channel_histories" in dir() else {}).get(channel_name, []))
            try:
                msgs_to_process = []
                async def _fetch():
                    async for msg in user_client.iter_messages(entity, limit=20):
                        if msg.date < cutoff:
                            break
                        if msg.text and len(msg.text.strip()) >= 3:
                            msgs_to_process.append(msg)
                await asyncio.wait_for(_fetch(), timeout=8.0)

                # Chronologisch verarbeiten (älteste zuerst)
                for msg in reversed(msgs_to_process):
                    text = msg.text.strip()
                    tl   = text.lower()
                    ts   = msg.date.strftime("%H:%M")

                    # CLOSE / BREAKEVEN / CANCEL direkt melden
                    if is_close_signal(text):
                        log.info(f"⏮ Verpasst [{channel_name}] {ts}: CLOSE → {text[:60]}")
                        found_any = True
                        continue

                    if any(w in tl for w in BREAKEVEN_WORDS):
                        log.info(f"⏮ Verpasst [{channel_name}] {ts}: BREAKEVEN → {text[:60]}")
                        found_any = True
                        continue

                    # TRADE: durch Interpreter jagen und ausführen
                    try:
                        tick = mt5.symbol_info_tick(GOLD_SYMBOL)
                        cur  = tick.bid if tick else 0.0
                        result = await asyncio.wait_for(
                            get_interpreter().interpret(
                                text=text,
                                channel=channel_name,
                                mt5=mt5,
                                channel_history=history,
                                current_price=cur,
                            ),
                            timeout=10.0
                        )
                        history.append(text)

                        action = result.get("action", "NOISE")
                        conf   = result.get("confidence", 0)

                        if action in ("TRADE", "URGENT") and conf >= 70:
                            # Alters-Riegel: verpasste TRADES nur bei frischer Nachricht
                            # ausfuehren (echte Netzwerk-Luecke), NICHT stundenalte Re-Fires.
                            _max_exec_min = float(os.getenv("MAX_MISSED_EXEC_MIN", "10"))
                            from datetime import timezone as _tzu
                            _age_min = (datetime.now(_tzu.utc) - msg.date).total_seconds() / 60.0
                            if _age_min > _max_exec_min:
                                log.info("Verpasstes TRADE uebersprungen: Nachricht " + ts +
                                         " ist " + str(round(_age_min, 1)) + " Min alt (> " +
                                         str(_max_exec_min) + " Min) - kein Re-Fire")
                                continue
                            log.info("Verpasstes Signal ausfuehren [" + channel_name + "] " + ts + ": " + action + " conf=" + str(conf) + "%")
                            found_any = True
                            sym = resolve_symbol(result.get("symbol") or "")
                            direction = str(result.get("direction") or "").upper()
                            if sym and direction in ("BUY", "SELL") and result.get("sl"):
                                # Bereits offene Positionen? → nicht nochmal ausführen
                                _existing = mt5.positions_get(symbol=sym)
                                if _existing and len(_existing) > 0:
                                    log.info("Verpasstes Signal uebersprungen: bereits " + str(len(_existing)) + " Position(en) offen")
                                    continue
                                # Aktuellen Preis holen
                                _tick = mt5.symbol_info_tick(sym or GOLD_SYMBOL)
                                cur_price = _tick.bid if _tick else 0.0
                                # Entry noch gueltig?
                                _entry = result.get("entry") or cur_price
                                _sl    = result.get("sl")
                                _sl_dist = abs(_entry - _sl) if _sl else 999
                                _price_dist = abs(cur_price - _entry)
                                _is_limit = bool(result.get("is_limit"))
                                # Limit Order: Entry unter Markt (BUY) oder über Markt (SELL) → immer gültig als Pending
                                # Mindestabstand 5 Punkte für echtes Limit (verhindert Market-Signale als Limit zu behandeln)
                                _min_limit_dist = 5.0
                                _is_buy_limit  = direction == "BUY"  and _entry < cur_price - _min_limit_dist
                                _is_sell_limit = direction == "SELL" and _entry > cur_price + _min_limit_dist
                                if _is_buy_limit or _is_sell_limit:
                                    _entry_valid = True  # Pending Limit → immer setzen
                                    log.info("Verpasstes Limit-Signal: " + direction + " @ " + str(_entry) +
                                             " (Markt=" + str(round(cur_price,2)) + ") → als Pending setzen")
                                else:
                                    _entry_valid = _price_dist <= _sl_dist * 0.5
                                if not _entry_valid:
                                    log.info("Verpasstes Signal uebersprungen: Entry " + str(_entry) +
                                             " zu weit vom aktuellen Preis " + str(round(cur_price,2)) +
                                             " (Abstand=" + str(round(_price_dist,2)) + " > " +
                                             str(round(_sl_dist*0.5,2)) + ")")
                                    history.append(text)
                                    continue
                                # TP1 bereits durchlaufen? Dann nicht mehr einsteigen
                                _tp1 = result.get("tp1")
                                if _tp1:
                                    _tp1_hit = (
                                        (direction == "BUY"  and cur_price >= float(_tp1)) or
                                        (direction == "SELL" and cur_price <= float(_tp1))
                                    )
                                    if _tp1_hit:
                                        log.info("Verpasstes Signal uebersprungen: TP1=" + str(_tp1) +
                                                 " bereits durchlaufen (Preis=" + str(round(cur_price,2)) + ")")
                                        history.append(text)
                                        continue
                                sig = TradeSignal(
                                    symbol=sym,
                                    direction=direction,
                                    entry=result.get("entry"),
                                    sl=result.get("sl"),
                                    tp1=result.get("tp1"),
                                    tp2=result.get("tp2"),
                                    tp3=result.get("tp3"),
                                    tp4=result.get("tp4"),
                                    tp5=result.get("tp5"),
                                    is_limit=bool(result.get("is_limit")),
                                    is_backup=bool(result.get("is_backup")),
                                    entry_low=float(result.get("entry_low") or result.get("entry") or 0),
                                    raw_text=text,
                                    text_hash=get_text_hash(text),
                                    source_channel=channel_name,
                                )
                                if sig.is_valid():
                                    tickets = execute_layers(sig)
                                    if tickets:
                                        log.info("Nachtraglich ausgefuhrt: " + str(len(tickets)) + " Layer")
                                        await send_notification(
                                            "Verpasstes Signal nachgeholt\n" +
                                            "[" + channel_name + "] " + ts + "\n" +
                                            direction + " " + sym + " | " + str(len(tickets)) + " Layer"
                                        )
                    except Exception as e:
                        log.warning(f"Interpreter [{channel_name}]: {e}")

            except asyncio.TimeoutError:
                log.warning(f"Timeout: {channel_name} übersprungen")
            except Exception as e:
                log.warning(f"Kanal {channel_name} Fehler: {e}")

        if not found_any:
            log.info("✅ Keine verpassten Signale")

    # Beim Start prüfen – 15 Sek warten damit Kanäle vollständig geladen sind
    await asyncio.sleep(15)
    try:
        await asyncio.wait_for(check_missed_signals(lookback_minutes=60), timeout=30)
    except asyncio.TimeoutError:
        log.warning("⏱ Verpasste-Signale-Check Timeout – wird übersprungen")

    # Verbindungsüberwachung via Heartbeat-Ping
    async def connection_watchdog():
        """Prueft ob Telegram-Verbindung steht. Faengt Fehler ab ohne zu crashen."""
        await asyncio.sleep(60)
        consecutive_failures = 0
        while True:
            try:
                await user_client.get_me()
                if consecutive_failures >= 2:
                    log.info("Verbindung wiederhergestellt nach " +
                             str(consecutive_failures) + " Fehlern")
                consecutive_failures = 0
                await asyncio.sleep(120 if is_trading_hours() else 300)
                # Wakeup-Ping alle 10 Min um verpasste Nachrichten zu vermeiden
                idle_pings = getattr(connection_watchdog, "_pings", 0) + 1
                connection_watchdog._pings = idle_pings
                if idle_pings >= 5 and is_trading_hours():
                    connection_watchdog._pings = 0
                    try:
                        await user_client.get_dialogs(limit=1)
                        log.info("Telethon Wakeup-Ping")
                    except Exception:
                        pass
            except (ConnectionError, OSError) as e:
                consecutive_failures += 1
                log.warning("Verbindungsproblem (" + str(consecutive_failures) +
                            "x): " + str(e)[:80])
                # Nicht crashen – einfach warten und nochmal versuchen
                await asyncio.sleep(min(30 * consecutive_failures, 300))
            except Exception as e:
                consecutive_failures += 1
                log.warning("connection_watchdog Fehler: " + str(e)[:80])
                await asyncio.sleep(60)

    # ── Equity Guardian (Fallschirm bei 50% Verlust) ──────────────────────────
    async def equity_guardian():
        """Notfall-Fallschirm: schliesst alle Positionen wenn Equity unter 50%."""
        await asyncio.sleep(30)
        start_balance = None
        while True:
            try:
                info = mt5.account_info()
                if not info:
                    await asyncio.sleep(60)
                    continue
                if start_balance is None:
                    start_balance = info.balance
                    log.info("Equity Guardian: Start=" + str(round(start_balance, 2)) + "$")

                equity    = info.equity
                threshold = start_balance * 0.70
                if equity < threshold:
                    log.error("FALLSCHIRM: Equity " + str(round(equity, 2)) +
                              "$ < 50% (" + str(round(threshold, 2)) + "$)")
                    positions = mt5.positions_get() or []
                    for pos in positions:
                        if pos.magic != MAGIC_NUMBER:
                            continue
                        tick = mt5.symbol_info_tick(pos.symbol)
                        if not tick:
                            continue
                        ctype = (mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY
                                 else mt5.ORDER_TYPE_BUY)
                        price = tick.bid if ctype == mt5.ORDER_TYPE_SELL else tick.ask
                        mt5.order_send({
                            "action":    mt5.TRADE_ACTION_DEAL,
                            "position":  pos.ticket,
                            "symbol":    pos.symbol,
                            "volume":    pos.volume,
                            "type":      ctype,
                            "price":     price,
                            "deviation": 50,
                            "magic":     MAGIC_NUMBER,
                            "comment":   "EquityGuardian",
                        })
                    orders = mt5.orders_get() or []
                    for o in orders:
                        if o.magic == MAGIC_NUMBER:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE,
                                            "order": o.ticket})
                    state.phase = 1
                    msg = ("FALLSCHIRM AUSGELOEST\n"
                           "Equity unter 50%!\n"
                           "Alle Positionen geschlossen.\n"
                           "Bot auf Phase 1 (manuell).\n"
                           "Equity: " + str(round(equity, 2)) + "$")
                    await send_notification(msg)
                    log.error(msg)
                    await asyncio.sleep(3600)
                    start_balance = None
            except Exception as e:
                log.error("equity_guardian: " + str(e))
            await asyncio.sleep(30)

    # ── Profit Guardian: Auto-Close bei X Pips Gewinn ───────────────────────────────
    async def profit_guardian():
        """
        Schließt Positionen automatisch wenn Gewinn > AUTO_CLOSE_PIPS Pips,
        falls kein expliziter TP gesetzt wurde.
        Verhindert dass Positionen ins Leere laufen.
        """
        AUTO_CLOSE_PCT = float(os.getenv("AUTO_CLOSE_PCT", "0.005"))  # relativ zum Entry
        CHECK_INTERVAL    = 60  # Sekunden

        await asyncio.sleep(120)  # Erst nach 2 Min starten
        while True:
            try:
                if is_trading_hours():
                    positions = mt5.positions_get() or []
                    for pos in positions:
                        if pos.magic != MAGIC_NUMBER:
                            continue
                        if pos.tp != 0.0:
                            continue  # Hat einen TP gesetzt → ignorieren

                        tick = mt5.symbol_info_tick(pos.symbol)
                        if not tick:
                            continue

                        # Punkte Abstand vom Entry
                        if pos.type == 0:  # BUY
                            points = tick.bid - pos.price_open
                        else:  # SELL
                            points = pos.price_open - tick.ask

                        if points >= pos.price_open * AUTO_CLOSE_PCT:
                            log.info("Profit Guardian: #" + str(pos.ticket) +
                                     " " + pos.symbol +
                                     " +" + str(round(points, 2)) + " Punkte → Auto-Close")
                            close_type = (mt5.ORDER_TYPE_SELL if pos.type == 0
                                          else mt5.ORDER_TYPE_BUY)
                            price = (tick.bid if pos.type == 0 else tick.ask)
                            req = {
                                "action":   mt5.TRADE_ACTION_DEAL,
                                "symbol":   pos.symbol,
                                "volume":   pos.volume,
                                "type":     close_type,
                                "position": pos.ticket,
                                "price":    price,
                                "deviation": 30,
                                "magic":    MAGIC_NUMBER,
                                "type_filling": mt5.ORDER_FILLING_IOC,
                            }
                            result = mt5.order_send(req)
                            if not (result and result.retcode == mt5.TRADE_RETCODE_DONE):
                                log.error("Profit Guardian: Close FEHLGESCHLAGEN #" +
                                          str(pos.ticket) + " retcode=" +
                                          str(getattr(result, "retcode", None)) + " " +
                                          str(getattr(result, "comment", "")))
                                for _fm in (mt5.ORDER_FILLING_IOC,
                                            mt5.ORDER_FILLING_RETURN,
                                            mt5.ORDER_FILLING_FOK):
                                    req["type_filling"] = _fm
                                    result = mt5.order_send(req)
                                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log.info("Profit Guardian: Close OK mit filling=" + str(_fm))
                                        break
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                pnl = pos.profit
                                await send_notification(
                                    "Profit Guardian: #" + str(pos.ticket) +
                                    " geschlossen\n+" +
                                    str(round(points, 2)) + " Punkte | P&L: +" +
                                    str(round(pnl, 2)) + "$"
                                )

            except Exception as e:
                log.warning("profit_guardian Fehler: " + str(e))
            await asyncio.sleep(CHECK_INTERVAL)

    # ── Trading Hours Watchdog ────────────────────────────────────────────────────
    async def trading_hours_watchdog():
        """
        Benachrichtigt bei Handelsstart/-ende.
        Bot laeuft 24/7 durch (energieoptimal: alle Watchdogs schlafen laenger
        ausserhalb der Handelszeiten). Signale werden durch is_trading_hours()
        blockiert, Bot beendet sich aber NICHT mehr um 22:00.
        """
        notified_start = False
        notified_end   = False
        while True:
            now = datetime.now()
            h, m = now.hour, now.minute
            in_hours = is_trading_hours()

            if h == TRADING_HOUR_START and m == 0 and not notified_start:
                await send_notification(
                    "Handelstag " + str(TRADING_HOUR_START) +
                    ":00 - Bot aktiv, ueberwacht " +
                    str(len(channel_entities)) + " Kanaele")
                notified_start = True
                notified_end   = False

            if h == TRADING_HOUR_END and m == 0 and not notified_end:
                await send_notification(
                    "Handelsende " + str(TRADING_HOUR_END) +
                    ":00 - Signale pausiert bis " +
                    str(TRADING_HOUR_START) + ":00")
                notified_end   = True
                notified_start = False

            # Ausserhalb Handelszeiten laenger schlafen (spart CPU/Energie)
            await asyncio.sleep(30 if in_hours else 120)

    # ── Symbol-Owner + SL-Cooldown Watchdog ──────────────────────────────────
    async def symbol_owner_watchdog():
        """Ueberwacht Positionen: gibt Prioritaet frei + registriert SL-Hits."""
        prev_tickets = {}
        while True:
            await asyncio.sleep(30)
            try:
                positions = mt5.positions_get() or []
                our_pos   = {p.ticket: p for p in positions
                             if p.magic == MAGIC_NUMBER}
                for ticket, (sym, ch) in list(prev_tickets.items()):
                    if ticket not in our_pos:
                        try:
                            deals = mt5.history_deals_get(ticket=ticket) or []
                            if deals and getattr(deals[-1], "reason", -1) == 3:
                                # Get direction+entry from the ticket
                                pos_dir = "SELL" if deals[-1].type == 1 else "BUY"
                                pos_entry = getattr(deals[-1], "price", 0.0)
                                register_sl_hit(ch, sym, pos_dir, pos_entry)
                        except Exception:
                            pass
                        del prev_tickets[ticket]
                for ticket, pos in our_pos.items():
                    if ticket not in prev_tickets:
                        ch = state.symbol_owner.get(pos.symbol, "?")
                        prev_tickets[ticket] = (pos.symbol, ch)
                        if state.pending_be.pop(pos.symbol, False):
                            log.info("pending_be anwenden: #" + str(ticket))
                            set_breakeven("auto_be", pos.symbol)
                for sym in list(state.symbol_owner.keys()):
                    if not any(p.symbol == sym for p in positions
                               if p.magic == MAGIC_NUMBER):
                        ch = state.symbol_owner.pop(sym, "?")
                        log.info("Prioritaet freigegeben: " + sym + " (" + ch + ")")
            except Exception as e:
                log.error("symbol_owner_watchdog: " + str(e))

    # ── Trailing Stop ────────────────────────────────────────────────────────
    async def trailing_stop_checker():
        """Zieht SL automatisch nach wenn Position im Plus ist."""
        if not TRAILING_STOP_ENABLED:
            log.info("Trailing Stop deaktiviert (TRAILING_STOP_ENABLED=false)")
            return
        log.info("Trailing Stop aktiv | " + str(TRAILING_STOP_PIPS) + " Pips | Min-Profit: " + str(TRAILING_STOP_MIN_PROFIT) + " Pips")
        await asyncio.sleep(60)
        while True:
            try:
                ensure_protective_sl()   # Sicherheitsnetz: SL-lose Positionen schuetzen
                prune_runners()          # Stufe A: verwaiste Runner-Eintraege aufraeumen
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        if pos.magic != MAGIC_NUMBER:
                            continue
                        if pos.ticket in runner_tickets():
                            continue   # Stufe A: getrackten Runner NICHT trailen (laeuft bis Close)
                        # Nur echte Runner (ohne harten TP) trailen - Layer mit
                        # hartem TP laeuft regelbasiert in sein Ziel.
                        if pos.tp and pos.tp > 0:
                            continue
                        sym_info = mt5.symbol_info(pos.symbol)
                        tick     = mt5.symbol_info_tick(pos.symbol)
                        if not sym_info or not tick:
                            continue
                        pip        = sym_info.point * 10
                        trail_dist = TRAILING_STOP_PIPS * pip
                        min_profit = TRAILING_STOP_MIN_PROFIT * pip
                        if pos.type == mt5.POSITION_TYPE_BUY:
                            current     = tick.bid
                            profit_pips = current - pos.price_open
                            if profit_pips < min_profit:
                                continue
                            new_sl = round(current - trail_dist, sym_info.digits)
                            # NIE schlechter als Entry: sonst schreibt der Trail
                            # einen Verlust fest, obwohl die Position im Plus ist.
                            new_sl = max(new_sl, round(pos.price_open, sym_info.digits))
                            if pos.sl and new_sl <= pos.sl:
                                continue
                        else:
                            current     = tick.ask
                            profit_pips = pos.price_open - current
                            if profit_pips < min_profit:
                                continue
                            new_sl = round(current + trail_dist, sym_info.digits)
                            new_sl = min(new_sl, round(pos.price_open, sym_info.digits))
                            if pos.sl and new_sl >= pos.sl:
                                continue
                        req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": pos.symbol,
                               "position": pos.ticket, "sl": new_sl, "tp": pos.tp}
                        r = mt5.order_send(req)
                        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                            d = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            log.info("Trail-SL #" + str(pos.ticket) + " " + pos.symbol +
                                     " " + d + " -> SL:" + str(new_sl) +
                                     " (+" + str(round(profit_pips/pip, 1)) + "p)")
            except Exception as e:
                log.error("Trailing-Stop Fehler: " + str(e))
            await asyncio.sleep(30)

    # ── Tägliche Zusammenfassung (um 22:00 Uhr) ──────────────────────────────
    async def daily_summary_loop():
        while True:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == 22 and state.last_summary_date != today:
                await send_daily_summary()
            await asyncio.sleep(60)

    async def update_status_file():
        """Schreibt Status in status.json fuer Web-Statusseite."""
        while True:
            try:
                import json as _json, os as _os_sf
                info = mt5.account_info()
                pos  = [p for p in (mt5.positions_get() or []) if p.magic == MAGIC_NUMBER]
                pnl  = sum(p.profit for p in pos)
                sf   = _os_sf.path.expanduser("~/teletrader/status.json")
                with open(sf, "w") as _f:
                    _json.dump({
                        "ts":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "balance":   round(info.balance, 2) if info else 0,
                        "equity":    round(info.equity,  2) if info else 0,
                        "positions": len(pos),
                        "pnl":       round(pnl, 2),
                        "mode":      "DEMO" if DEMO_MODE else "LIVE",
                    }, _f)
            except Exception:
                pass
            await asyncio.sleep(30)

    async def heartbeat():
        """Schickt alle 30 Minuten ein Lebenszeichen per Telegram."""
        await asyncio.sleep(60)  # Erst nach 1 Min starten
        while True:
            try:
                info = mt5.account_info()
                balance = info.balance if info else 0
                positions = mt5.positions_get()
                our_pos = [p for p in (positions or []) if p.magic == MAGIC_NUMBER]
                pending = mt5.orders_get()
                our_pending = [o for o in (pending or []) if o.magic == MAGIC_NUMBER]
                pause_txt = " | \u23f8 PAUSIERT" if is_trading_paused() else ""
                mode_txt  = "LIVE" if not DEMO_MODE else "DEMO"
                await send_notification(
                    f"\U0001f493 *Bot aktiv* {datetime.now().strftime('%H:%M')} Uhr"
                    f" | {mode_txt}{pause_txt}"
                    f" | Balance: ${balance:.2f} | Pos: {len(our_pos)} | Pending: {len(our_pending)}"
                )
            except Exception as e:
                log.error(f"Heartbeat Fehler: {e}")
            await asyncio.sleep(300 if is_trading_hours() else 1800)  # 5 Min aktiv, 30 Min inaktiv

    async def urgent_sl_watchdog():
        """
        Lücke 1: URGENT ohne SL.
        Nach 5 Minuten prüfen ob SL gesetzt wurde.
        Im Plus → schließen (Gewinn mitnehmen).
        Im Minus → SL mit Puffer setzen (15 Pips unter/über aktuellem Kurs).
        """
        await asyncio.sleep(20)
        while True:
            try:
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        if pos.magic != MAGIC_NUMBER:
                            continue
                        # Position ohne SL die älter als 5 Minuten ist
                        from datetime import timezone as _tz
                        age_seconds = (datetime.now(_tz.utc) -
                                      datetime.fromtimestamp(pos.time, tz=_tz.utc)).total_seconds()
                        if pos.sl == 0 and age_seconds > 60:
                            sym_info = mt5.symbol_info(pos.symbol)
                            tick     = mt5.symbol_info_tick(pos.symbol)
                            if not sym_info or not tick:
                                continue

                            pt    = sym_info.point
                            digs  = sym_info.digits
                            entry = pos.price_open
                            is_buy = pos.type == mt5.POSITION_TYPE_BUY

                            # Standardwerte wenn SL/TP nie geliefert wurden:
                            # TPs = 20 / 40 / 60 / 80 / 100 Pips
                            pip100 = pt * 1000   # 100 Pips (Gold: 1pt=0.01, 100pips=1.0)
                            pip20  = pt * 200
                            pip40  = pt * 400
                            pip60  = pt * 600
                            pip80  = pt * 800

                            # Risikobasierte SL-Distanz: hoechstens MAX_RISK_PCT Verlust,
                            # aber nie weiter als 100 Pips
                            _ai_wd  = mt5.account_info()
                            _bal_wd = _ai_wd.balance if _ai_wd else 1000.0
                            _tsz_wd = sym_info.trade_tick_size or 0.01
                            _tvl_wd = sym_info.trade_tick_value or 1.0
                            _pvl_wd = (_tvl_wd / _tsz_wd) if _tsz_wd > 0 else 100.0
                            _mrp_wd = float(os.getenv("MAX_RISK_PCT", "0.10"))
                            if pos.volume > 0 and _pvl_wd > 0:
                                _risk_dist = (_bal_wd * _mrp_wd) / (pos.volume * _pvl_wd)
                            else:
                                _risk_dist = pip100
                            _sl_dist  = min(pip100, _risk_dist)
                            _stops_wd = getattr(sym_info, "trade_stops_level", 0) or 0
                            _min_d_wd = max(_stops_wd * pt, pt * 10)
                            _cur_wd   = tick.bid if is_buy else tick.ask

                            if is_buy:
                                auto_sl  = round(min(entry - _sl_dist, _cur_wd - _min_d_wd), digs)
                                auto_tps = [round(entry + p, digs)
                                            for p in (pip20, pip40, pip60, pip80, pip100)]
                            else:
                                auto_sl  = round(max(entry + _sl_dist, _cur_wd + _min_d_wd), digs)
                                auto_tps = [round(entry - p, digs)
                                            for p in (pip20, pip40, pip60, pip80, pip100)]

                            # TP fuer diese Position (anhand Lot-Position bestimmen)
                            # Alle Positionen der gleichen Gruppe finden
                            same_group = [p for p in (mt5.positions_get() or [])
                                          if p.magic == MAGIC_NUMBER
                                          and p.symbol == pos.symbol
                                          and p.type == pos.type
                                          and p.sl == 0]
                            # Layer-Index bestimmen: aufsteigend nach Ticket
                            sorted_group = sorted(same_group, key=lambda p: p.ticket)
                            layer_idx    = next((i for i, p in enumerate(sorted_group)
                                                 if p.ticket == pos.ticket), 0)
                            tp_val = auto_tps[min(layer_idx, len(auto_tps)-1)]

                            req = {
                                "action":   mt5.TRADE_ACTION_SLTP,
                                "symbol":   pos.symbol,
                                "position": pos.ticket,
                                "sl":       auto_sl,
                                "tp":       tp_val,
                            }
                            result = mt5.order_send(req)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                log.warning("Auto SL/TP gesetzt #" + str(pos.ticket) +
                                            " SL=" + str(auto_sl) + " TP=" + str(tp_val))
                                await send_notification(
                                    "Kein SL nach 5 Min - Standard SL/TP gesetzt\n"
                                    "#" + str(pos.ticket) + " " + pos.symbol + "\n"
                                    "SL: " + str(auto_sl) + " (-100 Pips)\n"
                                    "TP: " + str(tp_val) + " (Layer " + str(layer_idx+1) + ")"
                                )
            except Exception as e:
                log.error(f"Urgent-SL-Watchdog Fehler: {e}")
            await asyncio.sleep(60)

    async def pending_cleanup():
        """
        Lücke 3: Alte Pending Orders akkumulieren sich.
        Löscht Pending Orders die älter als PENDING_EXPIRY_HOURS sind.
        """
        await asyncio.sleep(300)  # erst nach 5 Min starten
        while True:
            try:
                orders = mt5.orders_get()
                if orders:
                    for order in orders:
                        if order.magic != MAGIC_NUMBER:
                            continue
                        # Alter in SERVERZEIT rechnen: order.time_setup und tick.time
                        # kommen beide vom Broker -> kein Zeitzonen-Versatz moeglich.
                        _tk = mt5.symbol_info_tick(order.symbol)
                        if not _tk:
                            continue
                        age_hours = (_tk.time - order.time_setup) / 3600.0
                        if age_hours > PENDING_EXPIRY_H:
                            req = {
                                "action": mt5.TRADE_ACTION_REMOVE,
                                "order": order.ticket,
                            }
                            result = mt5.order_send(req)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                log.info(f"🗑 Alte Pending Order gelöscht: #{order.ticket} "
                                        f"({age_hours:.1f}h alt)")
                                await send_notification(
                                    f"Alte Pending Order geloescht\n"
                                    f"#{order.ticket} {order.symbol} "
                                    f"({age_hours:.0f}h alt)"
                                )
                            else:
                                log.error("Pending-Loeschung FEHLGESCHLAGEN #" +
                                          str(order.ticket) + " retcode=" +
                                          str(getattr(result, "retcode", None)))
            except Exception as e:
                log.error(f"Pending-Cleanup Fehler: {e}")
            await asyncio.sleep(1800)  # alle 30 Min prüfen

    async def streak_tracker():
        """
        Verfolgt geschlossene Positionen und aktualisiert den Kanal-Streak.
        Win (TP): +1 | SL-Hit: -1 | Nach 3× -1: Kanal pausiert.
        """
        await asyncio.sleep(90)
        while True:
            try:
                from datetime import timedelta
                cutoff = datetime.now() - timedelta(hours=24)
                deals = mt5.history_deals_get(cutoff, datetime.now()) or []
                for deal in deals:
                    if deal.magic != MAGIC_NUMBER:
                        continue
                    if deal.entry != 1:  # entry=1 = OUT (Schließung)
                        continue
                    # Welchem Kanal gehört dieses Ticket?
                    ch = None
                    for channel, tickets in _channel_open_tickets.items():
                        if deal.position_id in tickets:
                            ch = channel
                            tickets.discard(deal.position_id)
                            break
                    if not ch:
                        continue
                    # Win oder Loss?
                    if deal.profit > 0:
                        prev = _channel_streak.get(ch, 0)
                        _channel_streak[ch] = max(0, prev) + 1
                        log.info("Streak " + ch[:12] + ": +" +
                                 str(_channel_streak[ch]))
                    elif deal.profit < 0:
                        prev = _channel_streak.get(ch, 0)
                        _channel_streak[ch] = min(0, prev) - 1
                        streak = _channel_streak[ch]
                        log.info("Streak " + ch[:12] + ": " + str(streak))
                        if streak == -3:
                            log.warning("STREAK -3: " + ch + " → nächste Signale pausiert")
                            await send_notification(
                                "⚠️ " + ch + " – 3 SLs in Folge. Kanal pausiert bis zur nächsten Win.")
            except Exception as e:
                log.error("streak_tracker: " + str(e))
            await asyncio.sleep(60)

    async def command_poller():
        """
        Pollt Telegram HTTP API alle 3 Sekunden auf Bot-Befehle.
        Async mit httpx statt requests (blockiert Event-Loop nicht).
        """
        url = "https://api.telegram.org/bot" + TG_BOT_TOKEN + "/getUpdates"
        offset = 0
        # Alte Commands beim Start ignorieren
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, params={"offset": -1})
                updates = r.json().get("result", [])
                if updates:
                    offset = updates[-1]["update_id"] + 1
                    log.info("Command-Queue geleert (ab Update " + str(offset) + ")")
        except Exception:
            pass
        while True:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        url,
                        params={"offset": offset, "timeout": 3,
                                "allowed_updates": ["message"]},
                    )
                data = resp.json()
                if data.get("ok"):
                    for upd in data.get("result", []):
                        offset = upd["update_id"] + 1
                        msg     = upd.get("message", {})
                        from_id = msg.get("from", {}).get("id", 0)
                        text    = msg.get("text", "")
                        if from_id == TG_MY_CHAT_ID and text.startswith("/"):
                            log.info("Befehl empfangen: " + text)
                            await handle_phase_command(text.strip())
            except Exception as e:
                log.warning("command_poller: " + str(e))
                await asyncio.sleep(10)
                continue
            await asyncio.sleep(3)

    async def daily_audit_summary():
        """Sendet taeglich um Mitternacht eine Zusammenfassung."""
        while True:
            now = datetime.now()
            # Naechste Mitternacht berechnen
            # Mitternacht Berliner Zeit = 22:00 UTC (Sommer) / 23:00 UTC (Winter)
            from datetime import timedelta as _td
            next_midnight = now.replace(hour=22,minute=0,second=0,microsecond=0)
            if now.hour >= 22:
                next_midnight += _td(days=1)
            wait_secs = (next_midnight - now).total_seconds()
            await asyncio.sleep(wait_secs)
            if not _daily_audit:
                continue
            lines = ["Tages-Audit " + now.strftime("%d.%m") + ":"]
            for ch, d in _daily_audit.items():
                lines.append(ch[:20] + ": " + str(d["msgs"]) +
                             " Msgs | " + str(d["trades"]) + " Trades | " +
                             str(d["noise"]) + " Noise")
            await send_notification("\n".join(lines))
            # Reset
            _daily_audit.clear()

    async def periodic_missed_signals():

        """Prueft alle 30 Minuten auf verpasste Signale (Netzwerk-Luecken)."""
        await asyncio.sleep(300)  # 5 Min nach Start warten
        while True:
            try:
                await asyncio.wait_for(
                    check_missed_signals(lookback_minutes=35),
                    timeout=60
                )
            except Exception as e:
                log.error("periodic_missed_signals: " + str(e))
            await asyncio.sleep(600 if is_trading_hours() else 1800)  # 10 Min aktiv, 30 Min inaktiv

    async def algo_trading_checker():
        """
        Prueft alle 60 Sekunden ob Algo Trading aktiviert ist.
        Wenn nicht: MT5 neu verbinden und Telegram-Alarm.
        """
        await asyncio.sleep(30)
        last_alert = None
        while True:
            try:
                tinfo = mt5.terminal_info()
                if tinfo and not tinfo.trade_allowed:
                    log.warning("Algo Trading deaktiviert! Versuche GUI-Reaktivierung (Ctrl+E)...")
                    ok = False
                    for _versuch in range(3):
                        if await _enable_algo_trading_via_gui():
                            ok = True
                            break
                        await asyncio.sleep(2)
                    if ok:
                        log.info("Algo Trading per GUI automatisch reaktiviert")
                        await send_notification("\u2705 Algo Trading automatisch reaktiviert")
                        last_alert = None
                    else:
                        now = datetime.now()
                        if last_alert is None or (now - last_alert).seconds > 300:
                            last_alert = now
                            await send_notification(
                                "Algo Trading deaktiviert!\n"
                                "Auto-Reaktivierung (Ctrl+E) fehlgeschlagen.\n"
                                "Sende /algotrading oder pruefe MT5/X-Server."
                            )
            except Exception as e:
                log.error("algo_trading_checker: " + str(e))
            await asyncio.sleep(60)

    async def runner_breakeven_checker():
        """
        Stufe C: Sobald TP1 erreicht ist, SL des Runners auf Entry (Break-Even).
        Verhindert, dass ein (lone) Runner einen Gewinner zurueck ins Minus reitet.
        Greift nur auf getrackte Runner mit gespeichertem tp1 (runners.json).
        Trailing laesst Runner danach in Ruhe -> haelt auf BE, reitet weiter.
        """
        await asyncio.sleep(30)
        while True:
            try:
                recs = _load_runners()
                if recs:
                    open_pos = {p.ticket: p for p in (mt5.positions_get() or [])
                                if p.magic == MAGIC_NUMBER}
                    for tk_str, rec in list(recs.items()):
                        if not isinstance(rec, dict) or rec.get("be_done"):
                            continue
                        tp1 = rec.get("tp1")
                        if tp1 is None:
                            continue
                        try:
                            tk = int(tk_str)
                        except Exception:
                            continue
                        pos = open_pos.get(tk)
                        if pos is None:
                            continue
                        is_buy = rec.get("is_buy")
                        if is_buy is None:
                            is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
                        tick = mt5.symbol_info_tick(pos.symbol)
                        if not tick:
                            continue
                        price = tick.bid if is_buy else tick.ask
                        reached = (price >= tp1) if is_buy else (price <= tp1)
                        if not reached:
                            continue
                        entry = float(rec.get("entry") or pos.price_open)
                        info = mt5.symbol_info(pos.symbol)
                        dig = info.digits if info else 2
                        be = round(entry, dig)
                        if pos.sl and abs(pos.sl - be) < 5 * (10 ** (-dig)):
                            _mark_runner_be(tk)
                            continue
                        pt = info.point if info else 0.01
                        stops = getattr(info, "trade_stops_level", 0) or 0
                        min_d = max(stops * pt, pt * 10)
                        too_close = (be > price - min_d) if is_buy else (be < price + min_d)
                        if too_close:
                            continue  # BE-SL noch zu nah am Kurs -> still warten (kein 10016-Spam)
                        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                                            "symbol": pos.symbol, "position": tk,
                                            "sl": be, "tp": 0.0})
                        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                            _mark_runner_be(tk)
                            log.info("Stufe C: Runner #" + str(tk) + " auf BE (Entry " +
                                     str(be) + ", TP1 " + str(tp1) + " erreicht)")
                            await send_notification("\U0001f512 Runner #" + str(tk) +
                                                    " auf Break-Even gesichert (TP1 erreicht)")
                        else:
                            log.error("Stufe C: BE fehlgeschlagen #" + str(tk) + ": " + str(r))
            except Exception as _e:
                log.error("runner_breakeven_checker: " + str(_e))
            await asyncio.sleep(15)

    async def api_alert_watcher():
        """Warnt per Telegram, wenn der Interpreter API_ALERT.flag setzt
        (401 toter Key / 400 Guthaben leer). 30-Min-Cooldown gegen Spam."""
        import os, time
        _last = 0.0
        while True:
            try:
                if os.path.exists("API_ALERT.flag"):
                    _now = time.time()
                    if _now - _last > 1800:
                        try:
                            _info = open("API_ALERT.flag", encoding="utf-8").read()
                        except Exception:
                            _info = "?"
                        await send_notification(
                            "\u26a0\ufe0f API-PROBLEM: Bot klassifiziert NICHT!\n"
                            "Grund: " + _info[:160] + "\n"
                            "\u2192 Key/Guthaben in der Konsole pruefen, dann /restart."
                        )
                        _last = _now
            except Exception as _e:
                log.warning("api_alert_watcher: " + str(_e))
            await asyncio.sleep(60)

    async def auto_breakeven_checker():
        """
        Auto-Breakeven fuer ALLE Positionen des TeleTanders.
        Logik: wenn Preis mindestens 10 Punkte im Plus,
               setze SL der restlichen Layer auf Entry (Breakeven).
        """
        await asyncio.sleep(60)
        while True:
            try:
                positions = mt5.positions_get()
                if not positions:
                    await asyncio.sleep(60)
                    continue

                # Gruppiere TFXC-Positionen nach Symbol+Richtung
                from collections import defaultdict
                tfxc_groups = defaultdict(list)
                for pos in positions:
                    if pos.magic == MAGIC_NUMBER:
                        tfxc_groups[(pos.symbol, pos.type)].append(pos)

                for (symbol, ptype), pos_list in tfxc_groups.items():
                    # Prüfe ob TP1 schon hit wurde:
                    # Heuristik: weniger Positionen als beim Signal-Öffnen
                    # → einfachste Methode: aktueller Preis bereits profitabel
                    # UND mindestens eine Position fehlt (durch TP geschlossen)
                    # Wir setzen BE wenn Preis > Entry (BUY) oder < Entry (SELL)
                    # für alle Positionen die noch keinen BE-SL haben
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        continue
                    price = tick.bid if ptype == mt5.ORDER_TYPE_BUY else tick.ask

                    for pos in pos_list:
                        entry      = pos.price_open
                        current_sl = pos.sl
                        comment    = (pos.comment or "").lower()

                        is_goldhunter = any(k in comment for k in
                                           ("goldhunter", "paul", "gold hunt"))
                        is_tfxc = "tfxc" in comment
                        is_gtmo = "gtmo" in comment

                        # Open Layer (TP=0): Zwangs-BE als Sicherheitsnetz fuer TFXC
                        # UND GTMo (~bei TP2 / 1.5x SL-Distanz) - damit ein Runner
                        # nicht am Original-SL ausgestoppt wird, waehrend der Kanal
                        # laengst auf BE ist. Goldhunter haelt weiter bis Paul-Close.
                        if (pos.tp == 0.0 or pos.tp is None) and not (is_tfxc or is_gtmo):
                            _rbe = float(os.getenv("RUNNER_BE_PCT", "0.001"))
                            _si = mt5.symbol_info(pos.symbol)
                            if _rbe > 0 and _si:
                                _prof = ((price - entry) if ptype == mt5.ORDER_TYPE_BUY
                                         else (entry - price))
                                _spread = max(0.0, tick.ask - tick.bid)
                                _need = max(entry * _rbe, 2.0 * _spread)
                                if _prof >= _need:
                                    _newsl = round(entry, _si.digits)
                                    _better = (not current_sl) or (
                                        _newsl > current_sl if ptype == mt5.ORDER_TYPE_BUY
                                        else _newsl < current_sl)
                                    if _better:
                                        _r = mt5.order_send({
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": pos.ticket,
                                            "symbol": pos.symbol,
                                            "sl": _newsl, "tp": pos.tp})
                                        if _r and _r.retcode == mt5.TRADE_RETCODE_DONE:
                                            log.info("Runner-BE: #" + str(pos.ticket) +
                                                     " SL -> " + str(_newsl))
                                        else:
                                            log.error("Runner-BE fehlgeschlagen #" +
                                                      str(pos.ticket) + " retcode=" +
                                                      str(getattr(_r, "retcode", None)))
                            continue

                        # Bereits auf BE gesetzt?
                        if abs(current_sl - entry) < 0.1:
                            continue

                        # BE-Schwelle: TFXC frueh (~TP2-Bereich), sonst 1.5x SL-Distanz
                        sl_dist    = abs(entry - current_sl) if current_sl > 0 else 10
                        if is_tfxc:
                            _be_factor = float(os.getenv("TFXC_BE_FACTOR", "0.3"))
                        elif is_gtmo:
                            _be_factor = float(os.getenv("GTMO_BE_FACTOR", "0.5"))
                        else:
                            _be_factor = float(os.getenv("DEFAULT_BE_FACTOR", "1.5"))
                        min_profit = sl_dist * _be_factor

                        is_profit = (
                            (ptype == mt5.ORDER_TYPE_BUY  and price > entry) or
                            (ptype == mt5.ORDER_TYPE_SELL and price < entry)
                        )
                        enough_profit = (
                            (ptype == mt5.ORDER_TYPE_BUY  and price - entry >= min_profit) or
                            (ptype == mt5.ORDER_TYPE_SELL and entry - price >= min_profit)
                        )
                        if is_profit and enough_profit:
                            req = {
                                "action":   mt5.TRADE_ACTION_SLTP,
                                "position": pos.ticket,
                                "sl":       entry,
                                "tp":       pos.tp,
                            }
                            res = mt5.order_send(req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                src = "TFXC-TP2" if is_tfxc else ("GTMo-TP2" if is_gtmo else ("Goldhunter" if is_goldhunter else "Auto"))
                                log.info("Auto-BE (" + src + "): #" +
                                         str(pos.ticket) + " " + symbol +
                                         " SL→BE nach " + str(round(min_profit,1)) +
                                         " Pts Profit")

            except Exception as e:
                log.error("auto_breakeven_checker: " + str(e))
            await asyncio.sleep(60)

    @user_client.on(events.NewMessage(chats=channel_entities))
    async def on_signal_message(event):
        global _daily_audit, _channel_streak, _channel_open_tickets, _active_levels
        try:
            if not is_trading_hours():
                return
            text = event.message.text
            if not text or len(text) < 5:
                return

            channel_name = getattr(event.chat, 'title', 'Unbekannt')

            # Duplikat-Check
            text_hash = get_text_hash(text)
            if is_duplicate(text_hash):
                log.info(f"🔁 Duplikat ignoriert aus: {channel_name}")
                return

            log.info(f"📨 Neue Nachricht aus {channel_name}: {text[:60]!r}")

            # Kanal-History aktualisieren (für KI-Kontext)
            if channel_name not in state.channel_history:
                state.channel_history[channel_name] = []
            state.channel_history[channel_name].append(text[:200])
            if len(state.channel_history[channel_name]) > state.MAX_HISTORY:
                state.channel_history[channel_name].pop(0)

            # ── Schnell-Filter: eindeutige 1-Wort Befehle (kein API-Call nötig) ──────
            text_lower_check = text.lower().strip()
            words = text_lower_check.split()

            if len(words) <= 2:
                if any(w in text_lower_check for w in CANCEL_WORDS):
                    result = {"action": "CANCEL", "reasoning": "Cancel (schnell)"}
                elif is_close_signal(text):
                    result = {"action": "CLOSE", "reasoning": "Close (schnell)"}
                elif any(w in text_lower_check for w in BREAKEVEN_WORDS):
                    result = {"action": "BREAKEVEN", "reasoning": "Breakeven (schnell)"}
                else:
                    # Auch kurze Nachrichten durch KI
                    result = await get_interpreter().interpret(
                        text, channel_name, mt5,
                        state.channel_history.get(channel_name, [])
                    )
            else:
                # Alle längeren Nachrichten: KI mit vollem Kontext
                result = await get_interpreter().interpret(
                    text, channel_name, mt5,
                    state.channel_history.get(channel_name, [])
                )

            action = result.get("action", "NOISE")
            symbol = resolve_symbol(result.get("symbol","") or "")

            # ── Audit Tracking ────────────────────────────────────────────────
            if channel_name not in _daily_audit:
                _daily_audit[channel_name] = {"msgs": 0, "trades": 0, "noise": 0, "decisions": []}
            _daily_audit[channel_name]["msgs"] += 1
            _daily_audit[channel_name]["decisions"].append({
                "ts":     datetime.now().strftime("%H:%M"),
                "action": action,
                "conf":   result.get("confidence", 0),
                "text":   text[:60],
                "reason": str(result.get("reasoning",""))[:80],
            })
            if action in ("TRADE", "URGENT"):
                _daily_audit[channel_name]["trades"] += 1
            else:
                _daily_audit[channel_name]["noise"] += 1
            if len(_daily_audit[channel_name]["decisions"]) > 200:
                _daily_audit[channel_name]["decisions"] = _daily_audit[channel_name]["decisions"][-200:]

            # HARD RULE: SL oder TP vorhanden → niemals URGENT
            if action == "URGENT" and (result.get("sl") or result.get("tp1")):
                log.info("URGENT→TRADE override (SL/TP vorhanden)")
                action = "TRADE"
                result["action"] = "TRADE"
                result["is_limit"] = True

            # Confidence-Schwelle für URGENT: mind. 75%
            if action == "URGENT" and result.get("confidence", 100) < 75:
                log.info("URGENT blockiert: conf=" + str(result.get("confidence")) + "% < 75%")
                action = "NOISE"

            # ── Action Router ─────────────────────────────────────────────────────

            # --- Stufe B: URGENT->Levels-Attach (vor allen Action-Zweigen) ---
            _att_sym = resolve_symbol(result.get("symbol", "") or symbol or "")
            _att_ctx = state.pending_context.get(_att_sym)
            if _att_ctx and datetime.now() < _att_ctx["expires_at"]:
                _lv = parse_levels_from_text(text)
                _att_dir = _att_ctx.get("direction")
                _msg_dir = str(result.get("direction", "")).upper()
                if _lv["sl"] and (not _msg_dir or _msg_dir == _att_dir):
                    _u, _runner = attach_levels_to_urgent(
                        _att_sym, _att_dir, _lv["sl"], _lv["tps"],
                        _lv["has_open"], _att_ctx["tickets"])
                    state.pending_context.pop(_att_sym, None)
                    log.info("Stufe B Attach: SL " + str(_lv["sl"]) + " + " +
                             str(len(_lv["tps"])) + " TP auf Urgent " + _att_sym +
                             " | Worker=" + str(_u) + " Runner=#" + str(_runner))
                    await send_notification("Levels attached: SL " + str(_lv["sl"]) +
                                            " | " + str(_u) + " Worker, Runner #" + str(_runner))
                    return
            # -- TFXC "SECURE PROFITS" -> sofort kanal-scharfer BE (Text ist Trigger) --
            if "tfxc" in (channel_name or "").lower() and "tp1 hit" in text.lower():
                log.info("TFXC TP1-Hit erkannt -> SL nachziehen")
                _lk, _be, _cl = tfxc_lock_after_tp1(channel_name, symbol)
                if _lk or _be or _cl:
                    await send_notification(
                        "TFXC TP1 -> SL nachgezogen | Lock: " + str(_lk) +
                        " | BE: " + str(_be) + " | geschlossen: " + str(_cl))
                else:
                    await send_notification("TFXC TP1-Hit - keine Anpassung noetig")
                return
            if "tfxc" in (channel_name or "").lower() and "secure profit" in text.lower():
                log.info("TFXC SECURE PROFITS -> Breakeven | " + str(channel_name))
                _adj, _fb = set_breakeven(channel_name, symbol, channel_scoped=True)
                if _adj + _fb:
                    await send_notification("🔒 TFXC SECURE PROFITS -> BE | " +
                                            str(_adj + _fb) + " Position(en) gesichert")
                else:
                    await send_notification("TFXC SECURE PROFITS erkannt - keine offene TFXC-Position")
                return
            # -- Text-Trigger "Take Profits": VOR der Action-Verzweigung, ohne return,
            #    damit kombinierte Anweisungen (BE + Partial) beides ausloesen.
            if any(w in text.lower() for w in PARTIAL_TEXT_WORDS):
                import time as _t
                _cd = float(os.getenv("PARTIAL_COOLDOWN_SEC", "180"))
                if (_t.time() - state.last_partial.get(channel_name, 0.0)) < _cd:
                    log.info("Take-Profits erkannt - Cooldown aktiv, uebersprungen")
                else:
                    _frac = float(os.getenv("PARTIAL_FRACTION", "0.5"))
                    log.info("Take-Profits erkannt (Text) -> partial_close frac=" +
                             str(_frac) + " | " + str(channel_name)[:20])
                    _pc = partial_close(channel_name=channel_name, fraction=_frac)
                    if _pc:
                        state.last_partial[channel_name] = _t.time()
                        await send_notification("Take Profits -> " + str(_pc) +
                                                " Position(en) geschlossen")
                    else:
                        log.info("Take-Profits: keine offene Position dieses Kanals")

            if action == "NOISE":
                log.info(f"🔇 NOISE: {result.get('reasoning', '')}")
                return

            if action == "BREAKEVEN":
                be_symbol = symbol
                log.info("BE | Symbol: " + str(be_symbol or "alle"))
                adjusted, fallback = set_breakeven(channel_name, be_symbol)
                total = adjusted + fallback
                if total:
                    await send_notification("BE gesetzt | " + str(total) + " Position(en)")
                else:
                    # Keine offenen Pos – Pending Orders vorhanden?
                    sym_check = be_symbol or GOLD_SYMBOL
                    pend = [o for o in (mt5.orders_get(symbol=sym_check) or [])
                            if o.magic == MAGIC_NUMBER]
                    if pend:
                        state.pending_be[sym_check] = True
                        log.info("BE vorgemerkt: " + sym_check)
                        await send_notification(
                            "BE vorgemerkt: " + sym_check +
                            " - wird gesetzt sobald Pending aktiviert wird")
                return

            if action == "HOLD_LOWEST":
                if _hold_lowest_skipped(channel_name):
                    log.info("HOLD_LOWEST ignoriert (" + str(channel_name)[:20] +
                             ") - feste TPs arbeiten selbst")
                    await send_notification("TP-Hit erkannt - feste TPs bleiben aktiv (kein Hold-Lowest)")
                    return
                log.info(f"🔒 Hold-Lowest | Symbol: {symbol or 'alle'}")
                closed = hold_lowest_layer(symbol)
                await send_notification(
                    f"🔒 *Hold Lowest Layer*\nBeste Position behalten\n{closed} Layer geschlossen"
                )
                return

            # -- Confidence-Floor: destruktiver Teilausstieg nur bei sicherer Lesart --
            if action == "PARTIAL_CLOSE" and float(result.get("confidence", 0) or 0) < float(os.getenv("PARTIAL_CLOSE_MIN_CONF", "75")):
                _pc_c = result.get("confidence", 0)
                _pc_f = os.getenv("PARTIAL_CLOSE_MIN_CONF", "75")
                log.info("PARTIAL_CLOSE blockiert: conf=" + str(_pc_c) + "% < Floor " + _pc_f + "%")
                await send_notification("Partial-Close ignoriert: conf " + str(_pc_c) + "% unter Floor " + str(int(float(_pc_f))) + "%")
                return

            if action == "PARTIAL_CLOSE":
                log.info(f"📉 Partial-Close | Kanal: {channel_name}")
                closed = partial_close(channel_name=channel_name)
                await send_notification(
                    f"📉 *Partial Close*\nSchlechteste Layer geschlossen\n{closed} Layer geschlossen"
                )
                return

            if action == "CLOSE":
                cl_symbol = symbol
                log.info(f"🔴 Close | Symbol: {cl_symbol or 'alle'}")
                closed = close_positions_by_channel(channel_name, cl_symbol)
                cancelled = 0
                for hash_key, tickets in list(state.open_orders.items()):
                    cancelled += cancel_orders(tickets)
                    del state.open_orders[hash_key]
                await send_notification(
                    f"🔴 *Close ausgeführt*\nSymbol: `{cl_symbol or 'alle'}`\n"
                    f"{closed} Position(en) | {cancelled} Pending storniert"
                )
                return

            if action == "ACTIVATED":
                # Signalgeber meldet: sein Limit wurde getriggert
                # Prüfen ob unsere Pending Order auch getriggert wurde
                sym = symbol or GOLD_SYMBOL
                our_positions = [p for p in (mt5.positions_get(symbol=sym) or [])
                               if p.magic == MAGIC_NUMBER]
                our_pending   = [o for o in (mt5.orders_get(symbol=sym) or [])
                               if o.magic == MAGIC_NUMBER]

                if our_positions:
                    # Wir sind bereits drin – alles gut
                    log.info(f"✅ ACTIVATED: {sym} – wir sind bereits in der Position")
                elif our_pending:
                    # Wir haben noch eine Pending Order – Limit wurde bei uns nicht getriggert
                    # → Pending canceln + Market Order öffnen
                    log.info(f"⚡ ACTIVATED: {sym} – Pending nicht getriggert, öffne Market Order")
                    cancelled = cancel_orders([o.order for o in our_pending])

                    # Letzte bekannte Signal-Daten aus pending_context holen
                    ctx = state.pending_context.get(sym, {})
                    direction = ctx.get("direction", "BUY")
                    sl = ctx.get("sl_set", 0.0)

                    # Market Order zum aktuellen Preis
                    tick = mt5.symbol_info_tick(sym)
                    price = tick.ask if direction == "BUY" else tick.bid

                    sig = TradeSignal(
                        symbol=sym,
                        direction=direction,
                        entry=None,
                        sl=sl,
                        tp1=ctx.get("tp1"),
                        tp2=ctx.get("tp2"),
                        tp3=ctx.get("tp3"),
                        raw_text="ACTIVATED – manual market entry",
                        text_hash=get_text_hash("ACTIVATED"),
                        source_channel=channel_name,
                        is_limit=False,
                    )
                    if sig.is_valid():
                        await process_signal(sig)
                        await send_notification(
                            f"ACTIVATED: {sym} {direction} @ {price:.2f}\n"
                            f"Pending nicht getriggert - haendisch geoeffnet"
                        )
                else:
                    log.info(f"ℹ️ ACTIVATED: {sym} – keine Pending Orders, nichts zu tun")
                return

            if action == "CANCEL":
                log.info("🚫 Cancel")
                cancelled = 0
                for hash_key, tickets in list(state.open_orders.items()):
                    cancelled += cancel_orders(tickets)
                    del state.open_orders[hash_key]
                state.daily_stats["cancelled"] += 1
                if cancelled:
                    await send_notification(f"🚫 *Cancel* – {cancelled} Order(s) storniert")
                return

            if action == "MOVE_SL":
                new_sl = result.get("new_sl")
                if new_sl:
                    log.info(f"📍 Move SL → {new_sl} | Symbol: {symbol or 'alle'}")
                    updated = move_sl_to_price(new_sl, channel_name, symbol)
                    if updated:
                        await send_notification(f"📍 *SL verschoben*\nSL: `{new_sl}`\n{updated} Position(en)")
                return

            if action == "MOVE_TP":
                # new_tp kann auch als tp1 kommen
                new_tp = (result.get("new_tp") or result.get("tp1"))
                tp_level = result.get("tp_level")
                log.info("MOVE_TP: new_tp=" + str(new_tp) + " tp1=" + str(result.get("tp1")) + " symbol=" + str(symbol))
                if new_tp:
                    log.info(f"📍 Move TP{tp_level or ''} → {new_tp} | Symbol: {symbol or 'alle'}")
                    updated = move_tp_level(new_tp, tp_level, symbol)
                    label = f"TP{tp_level}" if tp_level else "TP"
                    if updated:
                        await send_notification(
                            f"📍 *{label} verschoben*\nNeuer {label}: `{new_tp}`\n{updated} Position(en)"
                        )
                return

            if action == "URGENT":
                confidence = result.get("confidence", 0)
                if confidence < 75:
                    log.info("URGENT mit conf=" + str(confidence) +
                             "% < 75% → ignoriert (zu unsicher fuer Market-Order)")
                else:
                    direction = result.get("direction")
                    urg_sym = resolve_symbol(result.get("symbol","") or symbol or "")
                    if urg_sym and direction:
                        await execute_urgent(urg_sym, direction, text, channel_name)
                return

            # TRADE or remaining → fall through to signal processing below
            if action == "TRADE" or result.get("sl") or result.get("tp1"):
                sig = TradeSignal(
                    symbol=resolve_symbol(result.get("symbol","") or ""),
                    direction=str(result.get("direction", "")).upper(),
                    entry=result.get("entry"),
                    sl=result.get("sl"),
                    tp1=result.get("tp1"),
                    tp2=result.get("tp2"),
                    tp3=result.get("tp3"),
                    tp4=result.get("tp4"),
                    tp5=result.get("tp5"),
                    tp6=result.get("tp6"),
                    is_limit=result.get("is_limit", False),
                    is_backup=is_backup_signal(text),
                    raw_text=text,
                    text_hash=text_hash,
                    source_channel=channel_name,
                )
                if sig.is_backup:
                    log.info("Backup-Signal: " + channel_name +
                             " – " + str(BACKUP_LOT_MULTIPLIER) + "x Lot, kein Cooldown")

                if not sig.is_valid():
                    log.warning(f"Signal unvollständig: {result}")
                    return

                await process_signal(sig)

        # ── Bot-Befehle & Bestätigungen (von dir) ────────────────────────────────
        except Exception as e:
            log.error("on_signal_message Fehler: " + str(e), exc_info=True)

    # ── Bot-Befehle (von dir per Telegram) ───────────────────────────────────────
    _last_cmd_time: dict = {}

    @bot_client.on(events.NewMessage(from_users=TG_MY_CHAT_ID))
    async def on_bot_message(event):
        # Deduplication: gleicher Befehl nicht innerhalb 3 Sekunden zweimal
        import time as _time
        _txt = (event.message.text or "").strip()
        _now = _time.time()
        if _txt in _last_cmd_time and _now - _last_cmd_time[_txt] < 3.0:
            return
        _last_cmd_time[_txt] = _now

        text = event.message.text or ""
        if not text:
            return
        # Phasen-Befehle & Status
        if await handle_phase_command(text):
            return
        # KI-Test vom Bot-Chat
        if len(text.strip()) > 3 and not text.startswith("/"):
            result = await get_interpreter().interpret(
                text, "manual_test", mt5,
                state.channel_history.get("manual_test", [])
            )
            ki_action = result.get("action", "NOISE")
            if ki_action not in ("NOISE",):
                log.info("Bot-Chat: " + ki_action + " | " + str(result.get("reasoning",""))[:60])
                sym = resolve_symbol(result.get("symbol","") or "")
                direction = str(result.get("direction","")).upper()
                if ki_action == "TRADE":
                    sig = TradeSignal(
                        symbol=sym,
                        direction=direction,
                        entry=result.get("entry"),
                        sl=result.get("sl"),
                        tp1=result.get("tp1"),
                        tp2=result.get("tp2"),
                        tp3=result.get("tp3"),
                        tp4=result.get("tp4"),
                        tp5=result.get("tp5"),
                        is_limit=result.get("is_limit", False),
                        is_backup=result.get("is_backup", False),
                        raw_text=text,
                        text_hash=get_text_hash(text),
                        source_channel="manual_test",
                    )
                    if sig.is_valid():
                        await process_signal(sig)
                elif ki_action == "URGENT":
                    if sym and direction:
                        await execute_urgent(sym, direction, text, "manual_test")
                elif ki_action == "CLOSE":
                    closed = close_positions_by_channel("manual_test", sym)
                    await send_notification("Close: " + str(closed) + " Position(en)")
                elif ki_action == "PARTIAL_CLOSE":
                    closed = partial_close(channel_name="manual_test")
                    await send_notification("Partial-Close: " + str(closed) + " Position(en)")
                elif ki_action == "BREAKEVEN":
                    set_breakeven("manual_test", sym)
                elif ki_action == "HOLD_LOWEST":
                    hold_lowest_layer(sym)
                elif ki_action == "MOVE_TP":
                    new_tp = result.get("new_tp") or result.get("tp1")
                    if new_tp:
                        updated = move_tp_to_price(new_tp, sym)
                        if updated:
                            await send_notification(
                                "TP gesetzt: " + str(new_tp) +
                                " | " + str(updated) + " Position(en)")
                        else:
                            await send_notification("TP setzen fehlgeschlagen: " + str(new_tp))
                elif ki_action == "MOVE_SL":
                    new_sl = result.get("new_sl")
                    if new_sl:
                        move_sl_to_price(new_sl, "manual_test", sym)
                elif ki_action == "CANCEL":
                    for tickets in list(state.open_orders.values()):
                        cancel_orders(tickets)
                    state.open_orders.clear()



    # ── Starten ───────────────────────────────────────────────────────────────
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected(),
        trading_hours_watchdog(),
        profit_guardian(),
        daily_summary_loop(),
        equity_guardian(),
        heartbeat(),
        api_alert_watcher(),
        auto_breakeven_checker(),
        runner_breakeven_checker(),
        algo_trading_checker(),
        update_status_file(),
        periodic_missed_signals(),
        daily_audit_summary(),
        command_poller(),
        streak_tracker(),
        connection_watchdog(),
        urgent_sl_watchdog(),
        pending_cleanup(),
        trailing_stop_checker(),
        symbol_owner_watchdog(),
    )


if __name__ == "__main__":
    # Socket-Lock: verhindert mehrere Instanzen (funktioniert unter Wine)
    import socket as _sock
    _lock = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    try:
        _lock.bind(("127.0.0.1", 47291))
        _lock.listen(1)
    except OSError:
        print("TeleTrader läuft bereits – beende diese Instanz")
        import sys; sys.exit(0)
    asyncio.run(main())
