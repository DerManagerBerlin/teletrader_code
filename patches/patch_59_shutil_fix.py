#!/usr/bin/env python3
# Patch 59 - NOTFALL. Behebt meinen Fehler aus Patch 58 und holt den Bot
# erneut auf Demo.
#
#   Im Log:
#       22:08:54 [ERROR] SELBSTHEILUNG fehlgeschlagen: name 'shutil' is not defined
#   shutil ist in teletrader_v2.py NICHT auf Modulebene importiert. Der
#   /live-Handler macht es lokal mit "import shutil as _sh", mein
#   _zurueck_auf_demo() hat den globalen Namen benutzt. Damit lief die
#   Selbstheilung in eine NameError und hat nichts geschrieben - genau in
#   dem Moment, in dem sie den Bot haette retten sollen.
#
#   (A) shutil lokal importieren. Zusaetzlich faellt die Funktion jetzt auf
#       ein Schreiben ohne Sicherungskopie zurueck, falls selbst das
#       scheitert. Lieber eine Datei ohne Backup als ein Bot, der nicht
#       mehr hochkommt.
#   (B) DEMO_MODE wieder auf true, LOGIN_FAILS loeschen.
#
#   Offen und fuer morgen notiert: zwischen 22:06 und 22:07:53 ist der Bot
#   von selbst wieder in den Live-Modus gegangen, obwohl Patch 57 kurz
#   vorher DEMO_MODE=true gesetzt hatte. Verdacht: ein noch in der
#   Telegram-Warteschlange liegendes /live wurde beim Start abgearbeitet,
#   bevor "Command-Queue geleert" lief. Das sehe ich mir morgen an.
import os, shutil, py_compile, sys
from datetime import datetime, timezone

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()

# ── (A) shutil-Fehler beheben ───────────────────────────────────────────
if "import shutil as _sh_heal" in src:
    print("Code schon korrigiert")
elif "_zurueck_auf_demo" not in src:
    print("Patch 58 nicht vorhanden - nur .env wird korrigiert")
else:
    shutil.copyfile(F, F + ".bak_59")
    A_OLD = '''        _zl = open(_ef, encoding="utf-8").read().splitlines()
        _neu, _hit = [], False
        for _z in _zl:
            if _z.strip().startswith("DEMO_MODE="):
                _neu.append("DEMO_MODE=true"); _hit = True
            else:
                _neu.append(_z)
        if not _hit:
            _neu.append("DEMO_MODE=true")
        shutil.copyfile(_ef, _ef + ".bak_selbstheilung")
        with open(_ef, "w", encoding="utf-8") as _f:
            _f.write("\\n".join(_neu) + "\\n")
'''
    A_NEW = '''        import shutil as _sh_heal      # PATCH59: nicht auf Modulebene vorhanden
        _zl = open(_ef, encoding="utf-8").read().splitlines()
        _neu, _hit = [], False
        for _z in _zl:
            if _z.strip().startswith("DEMO_MODE="):
                _neu.append("DEMO_MODE=true"); _hit = True
            else:
                _neu.append(_z)
        if not _hit:
            _neu.append("DEMO_MODE=true")
        try:
            _sh_heal.copyfile(_ef, _ef + ".bak_selbstheilung")
        except Exception:
            pass                       # Backup ist nett, aber nicht wichtig
        with open(_ef, "w", encoding="utf-8") as _f:
            _f.write("\\n".join(_neu) + "\\n")
'''
    if src.count(A_OLD) != 1:
        print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)
    src = src.replace(A_OLD, A_NEW)
    open(F, "w", encoding="utf-8").write(src)
    py_compile.compile(F, doraise=True)
    print("Patch 59 Code OK - shutil lokal importiert")

# ── (B) zurueck auf Demo ────────────────────────────────────────────────
ENV, LOG = ".env", "bot.log"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH env: " + t + "\n")
    except Exception:
        pass

if os.path.exists(ENV):
    zeilen = open(ENV, encoding="utf-8").read().splitlines()
    neu, gesetzt = [], []
    for z in zeilen:
        s = z.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1); k, v = k.strip(), v.strip()
            if k == "DEMO_MODE":
                if v.lower() != "true":
                    neu.append("DEMO_MODE=true"); gesetzt.append("DEMO_MODE: " + v + " -> true")
                else:
                    neu.append(z)
                continue
        neu.append(z)
    if not any(l.strip().startswith("DEMO_MODE=") for l in neu):
        neu.append("DEMO_MODE=true"); gesetzt.append("DEMO_MODE: (fehlte) -> true")
    if gesetzt:
        try:
            shutil.copyfile(ENV, ENV + ".bak_59")
        except Exception:
            pass
        with open(ENV + ".tmp_59", "w", encoding="utf-8") as f:
            f.write("\n".join(neu) + "\n")
        os.chmod(ENV + ".tmp_59", 0o600)
        os.replace(ENV + ".tmp_59", ENV)
        print("env geaendert: " + " | ".join(gesetzt))
    else:
        print("env: DEMO_MODE stand schon auf true")
    for _f in ("LOGIN_FAILS",):
        if os.path.exists(_f):
            try:
                os.remove(_f); print("geloescht: " + _f)
            except Exception:
                pass
    log("Patch 59: shutil-Fix + zurueck auf Demo")
else:
    print("FEHLER: .env fehlt")
