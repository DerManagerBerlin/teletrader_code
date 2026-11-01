#!/usr/bin/env python3
# patch_133_algo_reihenfolge.py
#
# AutoTrading im Ultima-Terminal erzwingen. Patch 129 hat an der common.ini
# nichts geaendert, der Terminalschalter stand beim Login aber auf False.
# Hier wird nachgesehen, wie die Datei wirklich aussieht, und der Abschnitt
# [Experts] notfalls angelegt. Danach werden die Terminals beendet, der
# Neustart durch ttpull laesst den Bot das Terminal neu hochfahren.
import io, os, re, glob, stat, sys

HOME = os.path.expanduser("~")
PUB = os.path.join(HOME, "ttpub")
_z = []


def sag(t):
    t = str(t)
    print("PATCH133 " + t)
    _z.append(t)


def schreiben():
    try:
        os.makedirs(PUB, exist_ok=True)
        with io.open(os.path.join(PUB, "status.txt"), "a",
                     encoding="utf-8") as f:
            for x in _z:
                f.write("ALGO133 " + x + "\n")
    except Exception:
        pass


def lies(p):
    with open(p, "rb") as f:
        roh = f.read()
    if roh[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return roh.decode("utf-16"), "utf-16"
    if roh.count(b"\x00") > len(roh) // 4:
        return roh.decode("utf-16-le", "replace"), "utf-16-le"
    return roh.decode("utf-8", "replace"), "utf-8"


_t = [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "Program Files", "*", "terminal64.exe"))
    if "ultima" in p.lower()]
if not _t:
    sag("ABBRUCH: kein Ultima-Terminal")
    schreiben()
    sys.exit(1)
DIR = os.path.dirname(_t[0])

# MT5 schreibt seine Einstellungen beim Beenden zurueck. Darum zuerst
# beenden, dann die Datei setzen, sonst ueberschreibt das Terminal sie.
#
# Patch 131 hat ueber /proc/<pid>/comm gesucht und nichts gefunden, obwohl
# ein Terminal laeuft. Unter Wine traegt der Prozess offenbar einen anderen
# Namen. Deshalb hier erst zeigen, wie die Prozesse wirklich aussehen, und
# dann ueber die Argumente suchen: irgendein Argument endet auf
# terminal64.exe. Die eigene Prozesskette bleibt ausgenommen.
_eigen = {os.getpid(), os.getppid(), 1}
_gefunden = []
for _pid in os.listdir("/proc"):
    if not _pid.isdigit() or int(_pid) in _eigen:
        continue
    try:
        with open("/proc/" + _pid + "/cmdline", "rb") as _f:
            _args = [a.decode("utf-8", "replace")
                     for a in _f.read().split(b"\x00") if a]
        with open("/proc/" + _pid + "/comm") as _f:
            _comm = _f.read().strip()
    except Exception:
        continue
    if not any(a.lower().endswith("terminal64.exe") for a in _args):
        continue
    _gefunden.append((int(_pid), _comm, " ".join(_args)[:90]))

for _pid, _comm, _cl in _gefunden:
    sag("Terminalprozess " + str(_pid) + " comm=" + _comm + " | " + _cl)
if not _gefunden:
    sag("kein laufender Terminalprozess gefunden")

_k = 0
for _pid, _comm, _cl in _gefunden:
    try:
        os.kill(_pid, 15)
        _k += 1
    except Exception as _e:
        sag("kill " + str(_pid) + " fehlgeschlagen: " + str(_e))
sag("Terminalprozesse beendet: " + str(_k))
import time as _t
_t.sleep(15)
_rest = 0
for _pid, _comm, _cl in _gefunden:
    if os.path.exists("/proc/" + str(_pid)):
        try:
            os.kill(_pid, 9)
            sag("Nachschlag SIGKILL auf " + str(_pid))
        except Exception:
            pass
        _rest += 1
if _rest:
    _t.sleep(5)
sag("nach dem Beenden noch da: " + str(_rest))

kand = []
for m in ("config", "Config", "CONFIG"):
    kand += glob.glob(os.path.join(DIR, m, "common.ini"))
kand += glob.glob(os.path.join(HOME, ".wine", "drive_c", "users", "*", "*",
                               "MetaQuotes", "Terminal", "*", "config",
                               "common.ini"))
kand += glob.glob(os.path.join(HOME, ".wine", "drive_c", "users", "*", "*",
                               "*", "MetaQuotes", "Terminal", "*", "config",
                               "common.ini"))
kand = sorted(set(kand))
sag("common.ini gefunden: " + str(len(kand)))

geaendert = 0
for p in kand:
    kurz = p.replace(HOME, "~")
    try:
        txt, kod = lies(p)
    except Exception as e:
        sag(kurz + ": nicht lesbar, " + str(e))
        continue
    hat_sec = bool(re.search(r"(?im)^\s*\[Experts\]\s*$", txt))
    treffer = re.findall(r"(?im)^\s*Enabled\s*=\s*(\S*)\s*$", txt)
    sag(kurz + " | " + kod + " | " + str(len(txt)) + " Zeichen | [Experts] " +
        ("ja" if hat_sec else "nein") + " | Enabled-Zeilen " + str(treffer))
    # Nur die Terminal-eigene Datei anfassen
    if not p.startswith(DIR):
        continue
    neu = txt
    if hat_sec:
        neu2, n = re.subn(r"(?im)^(\s*Enabled\s*=\s*)\S*(\s*)$",
                          r"\g<1>1\g<2>", neu)
        if n:
            neu = neu2
        else:
            neu = re.sub(r"(?im)^(\s*\[Experts\]\s*)$", r"\g<1>\nEnabled=1",
                         neu, count=1)
    else:
        trenn = "\r\n" if "\r\n" in neu else "\n"
        if neu and not neu.endswith(("\n", "\r")):
            neu += trenn
        neu += "[Experts]" + trenn + "Enabled=1" + trenn
    if neu == txt:
        sag("  unveraendert noetig")
        continue
    try:
        mode = stat.S_IMODE(os.stat(p).st_mode)
        tmp = p + ".p133"
        with open(tmp, "wb") as f:
            f.write(neu.encode(kod))
        os.chmod(tmp, mode)
        os.replace(tmp, p)
        geaendert += 1
        sag("  AutoTrading auf 1 gesetzt")
    except Exception as e:
        sag("  Schreibfehler: " + str(e))

if geaendert == 0 and kand:
    sag("nichts zu aendern - Schalter stand schon richtig oder Datei fehlt")

sag("fertig")
schreiben()
