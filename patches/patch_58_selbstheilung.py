#!/usr/bin/env python3
# Patch 58 - idempotent. Zwei Dinge.
#
# (A) Selbstheilung. Heute Abend ist genau das passiert, was nicht passieren
#     darf: der Live-Login scheiterte an einem IPC-Timeout, main() kehrte
#     zurueck, der Prozess endete, systemd startete neu, gleiches Spiel.
#     Damit startete der Telegram-Client nie, und /demo erreichte niemanden
#     mehr. Der Bot war nur noch ueber den Patch-Kanal zu retten.
#     Neu: scheitert der Start im Live-Modus, schreibt der Bot selbst
#     DEMO_MODE=true in die .env und beendet sich. Der naechste
#     systemd-Start kommt auf dem Demokonto hoch, der Bot ist wieder per
#     Telegram erreichbar, und /live kann erneut versucht werden.
#     Das gilt fuer BEIDE Abbruchwege: den gescheiterten Login und die
#     Sperre nach zu vielen Fehlversuchen aus Patch 56. Ohne das zweite
#     wuerde die Sperre den Bot dauerhaft unerreichbar machen, weil sie
#     frueher zurueckkehrt als die Selbstheilung greifen koennte.
#     Abschaltbar mit SELBSTHEILUNG_DEMO=false.
#
# (B) Diagnose fuer den eigentlichen Fix. Der Kontowechsel im laufenden
#     Wine-Terminal ist unzuverlaessig: das Terminal hielt noch Konto
#     700190957, nach shutdown() kam es nicht sauber zurueck. Fuer einen
#     funktionierenden Wechsel muss terminal64.exe selbst neu gestartet
#     werden. Im Bot-Code kommt es gar nicht vor, der Start passiert also
#     ausserhalb. Diese Diagnose loggt beim Start, wie das Terminal laeuft
#     und welche Dienste es gibt. Nur Lesen, keine Aenderung.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "SELBSTHEILUNG_DEMO" in src:
    print("schon angewendet"); raise SystemExit(0)
if "LOGIN_FAIL_FLAG" not in src:
    print("FEHLER: Patch 56 fehlt"); sys.exit(1)
shutil.copyfile(F, F + ".bak_58")

# ── Helfer neben die Patch-56-Helfer legen ──────────────────────────────
H_OLD = 'def connect_mt5() -> bool:\n    _ok = False\n'
H_NEW = '''def _zurueck_auf_demo(grund: str) -> None:
    """PATCH58: DEMO_MODE=true schreiben, damit der naechste Start hochkommt
    und der Bot per Telegram erreichbar bleibt."""
    if os.getenv("SELBSTHEILUNG_DEMO", "true").lower() != "true":
        return
    try:
        _ef = os.path.join(os.path.expanduser("~"), "teletrader", ".env")
        if not os.path.exists(_ef):
            _ef = ".env"
        _zl = open(_ef, encoding="utf-8").read().splitlines()
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
        log.error("SELBSTHEILUNG: " + str(grund) + " -> DEMO_MODE=true gesetzt. "
                  "Naechster Start laeuft auf dem Demokonto, danach ist /live "
                  "wieder moeglich.")
    except Exception as _he:
        log.error("SELBSTHEILUNG fehlgeschlagen: " + str(_he))

def connect_mt5() -> bool:
    _ok = False
'''
if src.count(H_OLD) != 1:
    print("FEHLER Anker H:", src.count(H_OLD)); sys.exit(1)
src = src.replace(H_OLD, H_NEW)

# ── (A1) Sperre aus Patch 56 heilt jetzt ebenfalls ──────────────────────
A_OLD = '''            log.error("LIVE-Login gesperrt nach " + str(_login_fails()) +
                      " Fehlversuchen. Datei " + LOGIN_FAIL_FLAG +
                      " loeschen, um es erneut zu versuchen.")
            return False
'''
A_NEW = '''            log.error("LIVE-Login gesperrt nach " + str(_login_fails()) +
                      " Fehlversuchen. Datei " + LOGIN_FAIL_FLAG +
                      " loeschen, um es erneut zu versuchen.")
            _zurueck_auf_demo("Login-Sperre erreicht")      # PATCH58
            return False
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── (A2) auch der unvollstaendige Datensatz heilt ───────────────────────
A2_OLD = '''            log.error("LIVE-Login nicht versucht: " + _cwhy +
                      " - mit /demo zurueckschalten")
            return False
'''
A2_NEW = '''            log.error("LIVE-Login nicht versucht: " + _cwhy)
            _zurueck_auf_demo(_cwhy)                        # PATCH58
            return False
'''
if src.count(A2_OLD) != 1:
    print("FEHLER Anker A2:", src.count(A2_OLD)); sys.exit(1)
src = src.replace(A2_OLD, A2_NEW)

# ── (A3) gescheiterter Login ────────────────────────────────────────────
A3_OLD = '''    if not _ok:
        log.error(f"MT5 Fehler: {mt5.last_error()}")
        return False
'''
A3_NEW = '''    if not _ok:
        log.error(f"MT5 Fehler: {mt5.last_error()}")
        if not DEMO_MODE:
            _zurueck_auf_demo("Live-Login gescheitert: " +
                              str(mt5.last_error()))        # PATCH58
        return False
'''
if src.count(A3_OLD) != 1:
    print("FEHLER Anker A3:", src.count(A3_OLD)); sys.exit(1)
src = src.replace(A3_OLD, A3_NEW)

# ── (B) Terminal-Diagnose beim Start ────────────────────────────────────
B_OLD = '''    if os.getenv("LIVECHECK", "true").lower() == "true":
        try:
            _kt = str(info.login)
'''
B_NEW = '''    if os.getenv("TERMINALCHECK", "true").lower() == "true":
        try:
            import subprocess as _sp
            for _lbl, _cmd in (
                    ("Prozesse", "ps -eo pid,etimes,args | grep -i terminal64 "
                                 "| grep -v grep | head -4"),
                    ("Dienste",  "systemctl list-units --type=service --no-pager "
                                 "--no-legend 2>/dev/null "
                                 "| grep -iE 'mt5|wine|xvfb|teletrader' | head -5"),
                    ("Timer",    "crontab -l 2>/dev/null | grep -vE '^#' | head -5")):
                try:
                    _out = _sp.run(["bash", "-lc", _cmd], capture_output=True,
                                   text=True, timeout=15).stdout.strip()
                except Exception as _ce:
                    _out = "Fehler: " + str(_ce)
                for _zeile in (_out.splitlines() or ["(leer)"]):
                    log.info("TERMINALCHECK " + _lbl + ": " + _zeile[:220])
        except Exception as _te:
            log.error("TERMINALCHECK Fehler: " + str(_te))
    if os.getenv("LIVECHECK", "true").lower() == "true":
        try:
            _kt = str(info.login)
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker B:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 58 OK - Selbstheilung auf allen drei Abbruchwegen, Terminal-Diagnose")
