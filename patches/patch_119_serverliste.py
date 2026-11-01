#!/usr/bin/env python3
# patch_119_serverliste.py
# NO_RESTART - nur lesen und probieren, der Bot wird nicht angefasst.
#
# Frage: Warum sind vier Wege zum Kontowechsel gescheitert? Verdacht: das
# installierte Terminal ist das von PU Prime und kennt die Server von Ultima
# Markets ueberhaupt nicht. MT5 haelt seine Serverliste als .srv-Dateien im
# config-Verzeichnis. Stehen da nur PUPrime-Dateien, ist der Fall klar und
# wir brauchen das Terminal von Ultima Markets.
# Zweitens: welche Installer-Adresse von Ultima Markets ist erreichbar.
import io, os, glob, subprocess, sys

HOME = os.path.expanduser("~")
STATUS = os.path.join(HOME, "ttpub", "status.txt")
_z = []


def sag(t):
    t = str(t)
    print("PATCH119 " + t)
    _z.append(t)


def lauf(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:
        return "Fehler: " + str(e)


# ------------------------------------------------- 1. Terminals und srv-Dateien
_terms = []
for _g in ("Program Files", "Program Files (x86)"):
    _terms += glob.glob(os.path.join(HOME, ".wine", "drive_c", _g,
                                     "*", "terminal64.exe"))
sag("Terminals gefunden: " + str(len(_terms)))
for _t in _terms:
    _dir = os.path.dirname(_t)
    sag("Terminal: " + os.path.basename(_dir))
    _srv = []
    for _c in ("config", "Config", "CONFIG"):
        _srv += glob.glob(os.path.join(_dir, _c, "*.srv"))
    # auch das Roaming-Verzeichnis, dort liegen die Listen nach erstem Start
    _roam = glob.glob(os.path.join(HOME, ".wine", "drive_c", "users", "*",
                                   "Application Data", "MetaQuotes",
                                   "Terminal", "*", "config", "*.srv"))
    _roam += glob.glob(os.path.join(HOME, ".wine", "drive_c", "users", "*",
                                    "AppData", "Roaming", "MetaQuotes",
                                    "Terminal", "*", "config", "*.srv"))
    _namen = sorted(set(os.path.basename(x) for x in _srv))
    sag("  srv im Programmverzeichnis: " +
        (", ".join(_namen)[:300] if _namen else "keine"))
    _rn = sorted(set(os.path.basename(x) for x in _roam))
    sag("  srv im Roaming: " + (", ".join(_rn)[:300] if _rn else "keine"))
    _hat_ultima = any("ultima" in x.lower() for x in _namen + _rn)
    sag("  Ultima-Server bekannt: " + ("JA" if _hat_ultima else "NEIN"))

# auch die gespeicherten Konten zaehlen, ohne Inhalt
for _d in set(os.path.dirname(os.path.dirname(x)) for x in glob.glob(
        os.path.join(HOME, ".wine", "drive_c", "users", "*", "*", "MetaQuotes",
                     "Terminal", "*", "config", "accounts.dat"))):
    pass
_acc = glob.glob(os.path.join(HOME, ".wine", "drive_c", "**", "accounts.dat"),
                 recursive=True)
sag("accounts.dat: " + str(len(_acc)) + " Datei(en)")

# --------------------------------------------- 2. Installer-Adresse probieren
BASIS = "https://download.mql5.com/cdn/web/"
SLUGS = ["ultima.markets.ltd", "ultima.markets.pty.ltd", "ultima.markets",
         "ultimamarkets.ltd", "ultimamarkets", "ultima.markets.limited",
         "ultima.market.ltd", "ultima.markets.group"]
DATEI = ["ultimamarkets5setup.exe", "ultima5setup.exe", "mt5setup.exe"]
_treffer = []
for _s in SLUGS:
    for _d in DATEI:
        _u = BASIS + _s + "/mt5/" + _d
        _out = lauf("curl -o /dev/null -s -I -w '%{http_code}' --max-time 12 '" +
                    _u + "'", timeout=20)
        if _out.strip() == "200":
            _treffer.append(_u)
            sag("TREFFER " + _u)
            break
if not _treffer:
    sag("kein Ultima-Installer gefunden unter den geratenen Adressen")
sag("Referenz MetaQuotes mt5setup.exe: " + lauf(
    "curl -o /dev/null -s -I -w '%{http_code}' --max-time 12 "
    "'" + BASIS + "metaquotes.software.corp/mt5/mt5setup.exe'", timeout=20))

# ------------------------------------------------------- 3. Umgebung fuer Wine
sag("wine: " + (lauf("which wine && wine --version 2>/dev/null | tail -1") or "fehlt"))
sag("Xvfb/DISPLAY: " + (lauf("pgrep -c -f 'Xvfb :99'") or "0") + " Prozess(e)")
sag("Platz frei: " + lauf("df -h --output=avail / | tail -1"))

try:
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with io.open(STATUS, "a", encoding="utf-8") as f:
        for x in _z:
            f.write("BEFUND119 " + x + "\n")
except Exception:
    pass
sag("Befund 119 fertig")
