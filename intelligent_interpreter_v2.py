"""
TeleTrader Intelligent Interpreter V2.0
Zweistufige Architektur:
  Stage 1: Claude Haiku  → RELEVANT / NOISE (schnell, günstig)
  Stage 2: Claude Sonnet → vollständige Signal-Analyse (nur für RELEVANT)

Kosten: ~$0.45/Tag statt $4.26/Tag bei reinem Sonnet
"""

import httpx
import asyncio
import json
import logging
import os

log = logging.getLogger(__name__)

MODEL_FILTER  = "claude-haiku-4-5-20251001"


def _load_signal_examples() -> str:
    """Lädt Signal-Beispiele aus signal_examples.json falls vorhanden."""
    search_paths = [
        os.path.join(os.path.dirname(__file__), "signal_examples.json"),
        os.path.expanduser("~/teletrader/signal_examples.json"),
        "signal_examples.json",
    ]
    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                lines = ["\n## SIGNAL EXAMPLES LIBRARY\n"]
                for category, examples in data.items():
                    lines.append(f"### {category.upper()} SIGNALS")
                    for ex in examples[:5]:  # max 5 pro Kategorie
                        lines.append(f'Input: "{ex["text"]}"')
                        lines.append(f'→ action={ex["expected"].get("action","?")}' +
                                     (f' direction={ex["expected"].get("direction","")}' if ex["expected"].get("direction") else "") +
                                     (f' entry={ex["expected"].get("entry","")}' if ex["expected"].get("entry") else ""))
                        lines.append("")
                log.info("Signal-Library geladen: " + path)
                return "\n".join(lines)
            except Exception as e:
                log.warning("Signal-Library Fehler: " + str(e))
    return ""  # Keine Datei gefunden, OK


MODEL_ANALYSE = "claude-sonnet-4-6"

# ── Stage 1: Haiku Pre-Filter ─────────────────────────────────────────────────
PREFILTER_PROMPT = """\
You are a fast pre-filter for a trading bot.

Decide if this Telegram message from a trading signal channel is RELEVANT or NOISE.

RELEVANT — must pass to Sonnet for analysis:
- ANY message containing: buy, sell, long, short, close, cancel, breakeven
- "buy gold", "sell now", "buy gold now", "gold buy", "sell gold" → ALWAYS RELEVANT
- Contains prices or levels (4500, 1.2345, SL, TP, entry)
- Management commands: hold, take profits, backup plan, move SL, targets
- "go in", "enter", "now" (as standalone or with direction)
- Zone/level mentions with numbers
- TP hit announcements: "tp1 hit", "tp2 hit", "target hit", "first target reached" → ALWAYS RELEVANT
- Partial close: "close some", "take half", "close first", "secure profits", "lock profits" → ALWAYS RELEVANT

NOISE — only clearly non-trading content:
- Pure motivation/celebration WITHOUT any direction word: "BOOM", "amazing", "who is ready"
- Ads, spam, referral links, PBTC/purple bitcoin, VIP promotions
- Pure market commentary WITHOUT buy/sell: "gold is bullish", "structure looks good"
- Greetings/farewells WITHOUT direction: "good morning", "good night"
- Pure emojis only
- "I think", "maybe" WITHOUT buy/sell direction words

CRITICAL: If in doubt → RELEVANT. A false RELEVANT costs $0.005.
ALWAYS RELEVANT regardless of length:
- "sl to be", "sl to breakeven", "move to be", "set be" → RELEVANT (breakeven)
- "close", "close all", "cancel", "cancel all" → RELEVANT
- "tp1 XXXX", "sl XXXX" (with number) → RELEVANT
- Any message under 5 words containing a number → RELEVANT
A missed RELEVANT (false NOISE) costs real money.
"Buy gold now" = RELEVANT (has "buy" + "gold" + "now")
"Sell now" = RELEVANT (has "sell" + "now")
"Gold buy" = RELEVANT

Respond with ONLY one word: RELEVANT or NOISE"""

# ── Stage 2: Sonnet Deep Analysis ────────────────────────────────────────────
ANALYSIS_PROMPT = """\
You are the signal interpreter for an automated Gold/Forex trading bot on MetaTrader 5.

Analyze the incoming Telegram message with full context and decide what action to take.

## OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "action": "TRADE|URGENT|WAIT|NOISE|CLOSE|CANCEL|BREAKEVEN|PARTIAL_CLOSE|HOLD_LOWEST|MOVE_SL|MOVE_TP",
  "direction": "BUY|SELL|null",
  "symbol": "XAUUSD|BTCUSD|EURUSD|GBPUSD|...|null",
  "entry": number|null,
  "entry_low": number|null,
  "sl": number|null,
  "tp1": number|null,
  "tp2": number|null,
  "tp3": number|null,
  "tp4": number|null,
  "tp5": number|null,
  "tp6": number|null,
  "tp7": number|null,
  "is_limit": true|false,
  "is_backup": true|false,
  "new_sl": number|null,
  "new_tp": number|null,
  "confidence": 0-100,
  "reasoning": "brief explanation",
  "small_lot": false
}

## ACTION DEFINITIONS

TRADE — complete signal with direction + entry + SL + ≥1 TP
  - is_limit=true when entry price specified (most signals)
  - is_backup=true if history contains "backup plan", "recovery", "plan b"

URGENT — direction known, NO entry price yet, SL/TP follow in next message
  - "buy gold", "sell now" → URGENT
  - "buy gold 4700" → TRADE (has price)
  HARD RULE: If the message contains ANY of: SL level, TP level, or entry price
  → it is NEVER URGENT. It must be TRADE or NOISE.
  A message with SL + TP + entry is ALWAYS TRADE, confidence 95+.

WAIT — signal building but incomplete, wait for next message
  - "SL 4721" alone after "Gold buy now" → WAIT (missing entry/TP)
  - Use when you see partial signal that clearly needs more info

NOISE — no actionable instruction
  - Commentary, motivation, celebration, analysis without action

CLOSE — close ALL open positions of this channel (FULL exit only):
  "take profits now", "close all", "off the charts now", "off the charts",
  "closed all", "out of all", "closed everything", "fully out", "all closed now"
CANCEL — cancel pending orders: "cancel", "cancel for now"
BREAKEVEN — move SL to entry: "SL to BE", "set breakeven now"
  - NOT if preceded by "if you wish" / "if you want" → NOISE
PARTIAL_CLOSE — close a PORTION, not all:
  Instructions: "close some", "take some profit", "take partial", "take half",
  "lock some", "secure partial", "book some profits", "close 1/3"
  ALSO when the operator REPORTS closing ONE/SOME of their OWN entries while
  STAYING IN (mirror it even if it reads like celebration):
  "just closed one more entry", "closed one entry", "closed one of my positions",
  "took one off", "closed some entries", "out of one entry"
  → Distinguish: "i'll close"/"at TP1 i'll close" = FUTURE → NOISE (no action yet);
    "closed all"/"off the charts"/"out of all" = FULL exit → CLOSE;
    "TP2 done/hit" with no close = HOLD_LOWEST.

HOLD_LOWEST — close all but the best position:
  "hold only lowest entry", "keep best position", "close all except best"
  "TP1 hit" / "TP2 hit" / "target hit" + no new direction → HOLD_LOWEST
  CRITICAL: TP hit announcements are ALWAYS HOLD_LOWEST, never NOISE.
  Even casual phrasing ("you can close some") = PARTIAL_CLOSE, not NOISE.
MOVE_SL — update stop loss on open positions
MOVE_TP — update take profit

## CRITICAL RULES

1. Gold prices: 4-digit (3300-5000). Forex: 4-5 decimal (1.0850).
   Abbreviated: "82.63" in Gold context = "4682.63"

2. Entry already passed: "buy limit 4680" but price is 4685 → TRADE is_limit=false (market)

3. Zone entries: "Buy zone 4720-4725" → entry=4725 for BUY (highest), entry_low=4720
   "Sell zone 4172-4177" → entry=4177 for SELL (highest), entry_low=4172
   Always set entry_low to the lower number of the zone range.

4. "if you wish/want" makes any instruction optional → NOISE

5. Hypothetical ("I think", "maybe", "could") → always NOISE even with prices

6. "Prepare for", "get ready", "watch for" → always NOISE even with prices

7. "Again" / "Now" after direction in history + entry+SL in history → TRADE (not URGENT)

8. "TP: open" = no fixed TP, set null

9. Confidence: 95+ only for crystal clear signals. Below 70 → prefer WAIT or NOISE.

10. Backup: history has "backup plan" → next trade signal gets is_backup=true

11. RISK WARNINGS → extract as modifier:
    "high volatile use small lot", "risky trade", "use small lot", "reduce size"
    → Set "small_lot": true in output. This halves the lot size.
    "high volatile" alone without trade direction → NOISE.

12. TIME-BOUND ANNOUNCEMENTS → always NOISE:
    "in 5 min we buy", "at 19:20 we buy", "in 10 minutes we sell"
    The bot cannot wait for a specific time. Treat as NOISE.
    Wait for the actual signal when the time comes.
    "all together", "everyone buy" = community call, not a bot command.

12. "sell at - X" / "buy at - X" → TRADE with entry=X:
    The dash " - " before a price is a visual separator, NOT minus.
    "So let's sell at - 4587, SL 4602" → TRADE SELL entry=4587 sl=4602 is_limit=true
    NEVER treat this as URGENT. Always extract the number after " - " as entry.

13. "We SELL/BUY again at X" → always TRADE with is_backup=true:
    Additional layer on existing signal. Always execute even if position open.
    "We SELL again at 78400" → TRADE SELL entry=78400 is_limit=true is_backup=true

14. "Active" as reply to previous signal → TRADE with high confidence:
    Extract entry/direction from history and execute with confidence=95.
    Without clear signal in history → NOISE.

15. "TARGET" / "TARGETS" = TP:
    "Target 4638", "Targets 4638", "TP target 4638" → set as tp1.
    "Few layers open, keep SL 4689. Targets 4638" → MOVE_SL new_sl=4689 AND new_tp=4638.
    Always extract target prices as TP levels even without explicit "TP" keyword.
    "in 5 min we buy", "at 19:20 we buy", "in 10 minutes we sell"
    The bot cannot wait for a specific time. Treat as NOISE.
    Wait for the actual signal when the time comes.
    "all together", "everyone buy" = community call, not a bot command.

## FEW-SHOT EXAMPLES — Paul/Goldhunter informal style

Input: "gold sell"
→ {"action":"URGENT","direction":"SELL","symbol":"XAUUSD","confidence":80}

Input: "Sell gold at 4185\nSL 4205\nTP 4175\nTP 4165\nTP 4155\nTP open"
→ {"action":"TRADE","direction":"SELL","entry":4185,"sl":4205,"tp1":4175,"tp2":4165,"tp3":4155,"is_limit":true,"confidence":97}

Input: "We sell again at 4185 SL 4200"
→ {"action":"TRADE","direction":"SELL","entry":4185,"sl":4200,"is_backup":true,"confidence":92}

Input: "SELL 4185-4190 SL 4205 TP 4170"
→ {"action":"TRADE","direction":"SELL","entry":4190,"entry_low":4185,"sl":4205,"tp1":4170,"is_limit":true,"confidence":95}

Input: "TP1 done! Hold the rest boys 🏆"
→ {"action":"HOLD_LOWEST","confidence":88}

Input: "Target reached, lock some profits"
→ {"action":"PARTIAL_CLOSE","confidence":85}
Input: "Just closed one more entry"
→ {"action":"PARTIAL_CLOSE","confidence":88}
Input: "I'm off the charts now, closed everything"
→ {"action":"CLOSE","confidence":92}
Input: "At TP1 i'll close my first entries and set breakeven"
→ {"action":"NOISE","confidence":85}

Input: "Move sl to 4170"
→ {"action":"MOVE_SL","new_sl":4170,"confidence":95}

Input: "High volatile use small lot\nSell 4185 SL 4205 TP 4170"
→ {"action":"TRADE","direction":"SELL","entry":4185,"sl":4205,"tp1":4170,"small_lot":true,"confidence":95}

Input: "4185 sell sl 4200"
→ {"action":"TRADE","direction":"SELL","entry":4185,"sl":4200,"is_limit":true,"confidence":90}

Input: "Sell at - 4185 SL 4200 TP 4170"
→ {"action":"TRADE","direction":"SELL","entry":4185,"sl":4200,"tp1":4170,"is_limit":true,"confidence":97}

Input: "Are you ready?? 🚀🚀🚀 JOIN THE ARMY"
→ {"action":"NOISE","confidence":99}

Input: "Wait for the limit"
→ {"action":"NOISE","confidence":95}
"""


class IntelligentInterpreterV2:
    def __init__(self, api_key: str, gold_symbol: str = "XAUUSD.s", btc_symbol: str = "BTCUSD", **kwargs):
        self.api_key     = api_key
        self.gold_symbol = gold_symbol
        self.client      = httpx.AsyncClient(timeout=30)
        self._stats      = {"total": 0, "relevant": 0, "noise_filtered": 0}

    async def _call(self, model: str, system: str, user: str, max_tokens: int) -> str:
        """Raw API call, returns text content."""
        resp = await self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      model,
                "max_tokens": max_tokens,
                "system":     system,
                "messages":   [{"role": "user", "content": user}],
            },
        )
        if resp.status_code in (400, 401, 403):
            _body = (resp.text or "")[:200]
            _low = _body.lower()
            if (resp.status_code == 401 or "authentication" in _low
                    or "invalid x-api-key" in _low or "credit balance" in _low
                    or "billing" in _low):
                try:
                    import time as _t
                    with open("API_ALERT.flag", "w", encoding="utf-8") as _f:
                        _f.write(str(int(_t.time())) + "|HTTP " + str(resp.status_code) + "|" + _body[:120])
                except Exception:
                    pass
        resp.raise_for_status()
        try:
            import os as _os
            if _os.path.exists("API_ALERT.flag"):
                _os.remove("API_ALERT.flag")
        except Exception:
            pass
        return resp.json()["content"][0]["text"].strip()

    async def _prefilter(self, text: str, channel: str) -> bool:
        """Stage 1: Haiku pre-filter. Returns True if RELEVANT."""
        try:
            user_msg = f"Channel: {channel}\nMessage: \"{text}\""
            result = await self._call(MODEL_FILTER, PREFILTER_PROMPT, user_msg, 5)
            is_relevant = result.upper().startswith("RELEVANT")
            return is_relevant
        except Exception as e:
            log.warning("Prefilter error: " + str(e) + " - treating as RELEVANT")
            return True  # safe fallback: let Sonnet decide

    async def interpret(
        self,
        text:            str,
        channel:         str,
        mt5,
        channel_history: list,
        current_price:   float = 0.0,
    ) -> dict:
        """
        Zweistufige Analyse:
        1. Haiku pre-filter (RELEVANT/NOISE)
        2. Sonnet deep analysis (nur wenn RELEVANT)
        """
        fallback = {
            "action": "NOISE", "direction": None, "symbol": None,
            "entry": None, "sl": None,
            "tp1": None, "tp2": None, "tp3": None, "tp4": None, "tp5": None,
            "is_limit": False, "is_backup": False,
            "new_sl": None, "new_tp": None,
            "confidence": 99, "reasoning": "Pre-filter: NOISE"
        }

        self._stats["total"] += 1

        # ── Stage 1: Haiku pre-filter ─────────────────────────────────────────
        is_relevant = await self._prefilter(text, channel)

        if not is_relevant:
            self._stats["noise_filtered"] += 1
            log.info("Pre-filter NOISE [" + channel + "]: " + text[:50])
            return fallback

        # ── Stage 2: Sonnet deep analysis ─────────────────────────────────────
        self._stats["relevant"] += 1

        try:
            # Build context
            history_text = ""
            if channel_history:
                recent = channel_history[-10:]
                history_text = "\n".join(
                    f"  [{i+1}] {msg}" for i, msg in enumerate(recent)
                )

            pos_text = "No open positions"
            if mt5:
                try:
                    positions = mt5.positions_get() or []
                    if positions:
                        pos_lines = []
                        for p in positions[:5]:
                            d = "BUY" if p.type == 0 else "SELL"
                            sgn = "+" if p.profit >= 0 else ""
                            pos_lines.append(
                                f"{p.symbol} {d} @ {p.price_open} "
                                f"SL={p.sl} TP={p.tp} "
                                f"P&L={sgn}{p.profit:.2f}$"
                            )
                        pos_text = "\n".join(pos_lines)
                except Exception:
                    pass

            price_text = f"Current market price: {current_price}" if current_price else ""

            user_msg = (
                f"Channel: {channel}\n"
                f"{price_text}\n\n"
                f"Recent history (last 10 messages):\n"
                f"{history_text if history_text else '  (no history)'}\n\n"
                f"NEW MESSAGE:\n\"\"\"{text}\"\"\"\n\n"
                f"Open positions:\n{pos_text}\n\n"
                f"Respond with JSON only."
            )

            raw = await self._call(MODEL_ANALYSE, ANALYSIS_PROMPT + _load_signal_examples(), user_msg, 400)

            # Strip markdown
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)

            # Ensure all keys
            for k in ["action", "direction", "symbol", "entry", "sl",
                       "tp1", "tp2", "tp3", "tp4", "tp5",
                       "is_limit", "is_backup", "new_sl", "new_tp",
                       "confidence", "reasoning"]:
                result.setdefault(k, fallback[k])

            # Stats log every 50 messages
            if self._stats["total"] % 50 == 0:
                pct = self._stats["relevant"] / max(1, self._stats["total"]) * 100
                log.info(
                    "V2 Stats: " + str(self._stats["total"]) + " msgs, " +
                    str(self._stats["relevant"]) + " an Sonnet (" +
                    str(round(pct, 1)) + "%), " +
                    str(self._stats["noise_filtered"]) + " by Haiku gefiltert"
                )

            log.info(
                "KI-V2 [" + channel + "]: " + result["action"] +
                " | conf=" + str(result["confidence"]) + "% | " +
                str(result.get("reasoning", ""))[:80]
            )
            return result

        except json.JSONDecodeError as e:
            log.warning("V2 JSON error: " + str(e))
            return fallback
        except Exception as e:
            log.error("V2 interpreter error: " + str(e))
            return fallback

    async def close(self):
        await self.client.aclose()
