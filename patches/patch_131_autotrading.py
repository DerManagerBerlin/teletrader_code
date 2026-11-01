#!/usr/bin/env python3
# patch_131_autotrading.py
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
    print("PATCH131 " + t)
    _z.append(t)


def schreiben():
    try:
        os.makedirs(PUB, exist_ok=True)
        with io.open(os.path.join(PUB, "status.txt"), "a",
                     encoding="utf-8") as f:
            for x in _z:
                f.write("ALGO131 " + x + "\n")
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
        tmp = p + ".p131"
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

# Terminals beenden, damit das Ultima-Terminal mit der neuen Einstellung
# hochkommt. Pruefung ueber den Prozessnamen, nicht ueber die Kommandozeile.
_eigen = {os.getpid(), os.getppid()}
_k = 0
for pid in os.listdir("/proc"):
    if not pid.isdigit() or int(pid) in _eigen:
        continue
    try:
        with open("/proc/" + pid + "/comm") as f:
            if f.read().strip() != "terminal64.exe":
                continue
    except Exception:
        continue
    try:
        os.kill(int(pid), 15)
        _k += 1
    except Exception:
        pass
sag("Terminalprozesse beendet: " + str(_k))
sag("fertig")
schreiben()
