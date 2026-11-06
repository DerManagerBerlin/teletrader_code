#!/usr/bin/env python3
# patch_145_kanalname.py
#
# Der Goldkanal hat sich am 5.11. umbenannt, von "XAUUSD SCALPING" zu
# "SMC | GOLD TRADES". Die Auswahl des Parsers haengt am Kanalnamen:
# REGEX_ONLY_CHANNELS stand auf "scalping", der neue Name enthaelt das nicht
# mehr. Damit landeten alle Nachrichten beim LLM-Pfad, und weil der LLM aus
# ist, wurden sie als Rauschen verworfen. 408 Nachrichten seit Donnerstag.
#
# Zwei Korrekturen:
#   1. Ist der LLM aus, gilt grundsaetzlich der Regex-Parser. Ohne LLM gibt
#      es keinen Grund, irgendetwas an den LLM-Pfad zu geben, dort faellt es
#      nur lautlos hinten runter. Damit haengt nichts mehr am Kanalnamen.
#   2. "smc" zusaetzlich in REGEX_ONLY_CHANNELS, damit es auch mit
#      eingeschaltetem LLM stimmt.
import io, os, re, stat, sys, py_compile

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
BOT = os.path.join(TT, "teletrader_v2.py")
ENV = os.path.join(TT, ".env")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
    ENV = ".env"


def sag(t):
    print("PATCH145 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "PATCH145" in src:
    sag("Code schon angepasst")
else:
    A = ('    cn = (channel or "").lower()\n'
         '    names = os.getenv("REGEX_ONLY_CHANNELS", "scalping").lower().split(",")\n'
         '    return any(n.strip() and n.strip() in cn for n in names)\n')
    N = ('    # PATCH145: Ohne LLM gibt es keinen zweiten Pfad. Wuerde hier\n'
         '    # False zurueckkommen, landet die Nachricht beim LLM-Parser und\n'
         '    # wird dort als Rauschen verworfen. Genau das ist passiert, als\n'
         '    # der Kanal sich umbenannt hat und "scalping" nicht mehr passte.\n'
         '    if os.getenv("LLM_AKTIV", "false").lower() != "true":\n'
         '        return True\n'
         '    cn = (channel or "").lower()\n'
         '    names = os.getenv("REGEX_ONLY_CHANNELS", "scalping").lower().split(",")\n'
         '    return any(n.strip() and n.strip() in cn for n in names)\n')
    if src.count(A) != 1:
        sag("FEHLER: Anker " + str(src.count(A)) + "x")
        sys.exit(1)
    src = src.replace(A, N, 1)
    tmp = BOT + ".p145"
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
    sag("Regex-Parser gilt jetzt immer, wenn der LLM aus ist")

# ---------------------------------------------------------------- .env
try:
    alt = io.open(ENV, encoding="utf-8", errors="surrogateescape").read()
except Exception as e:
    sag("env nicht lesbar: " + str(e))
    sys.exit(0)
zeilen = alt.split("\n")


def key(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (key(z) for z in zeilen) if k)
hit = False
for i, z in enumerate(zeilen):
    if key(z) == "REGEX_ONLY_CHANNELS":
        zeilen[i] = "REGEX_ONLY_CHANNELS=scalping,smc,gold trades"
        hit = True
if not hit:
    if zeilen and zeilen[-1].strip() != "":
        zeilen.append("")
    zeilen.append("REGEX_ONLY_CHANNELS=scalping,smc,gold trades")
neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nicht geschrieben")
    sys.exit(0)
fd = os.open(ENV + ".bak145", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
fd = os.open(ENV + ".p145", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    os.chmod(ENV + ".p145", stat.S_IMODE(os.stat(ENV).st_mode))
except Exception:
    pass
os.replace(ENV + ".p145", ENV)
sag("REGEX_ONLY_CHANNELS=scalping,smc,gold trades gesetzt")
sag("fertig")
