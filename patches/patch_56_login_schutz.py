#!/usr/bin/env python3
# Patch 56 - idempotent. Schuetzt den Kontowechsel, aendert nichts am Handel.
#
#   Das Umschalten laeuft wie gewohnt ueber /live und /demo in Telegram.
#   Daran wird nichts geaendert. Der Befehl prueft aber nicht, ob die
#   Live-Zugangsdaten ueberhaupt vollstaendig sind, und das ist gefaehrlich:
#       /live -> DEMO_MODE=false -> SIGTERM -> systemd startet neu
#       -> connect_mt5() scheitert -> main() kehrt zurueck -> Prozess endet
#       -> systemd startet neu -> naechster Loginversuch ...
#   Das ist eine Schleife aus Loginversuchen, und wiederholte Fehlversuche
#   sperren beim Broker das Konto. Mit leerem LIVE_MT5_LOGIN oder falschem
#   Passwort laeuft das endlos.
#
#   Drei Sicherungen:
#   (A) /live prueft vorher, ob Login, Passwort, Server und Symbol gesetzt
#       sind. Fehlt etwas, wird NICHT umgeschaltet und der Grund kommt per
#       Telegram zurueck. /demo bleibt jederzeit moeglich.
#   (B) connect_mt5() versucht im Live-Modus gar keinen Login, wenn die
#       Daten unvollstaendig sind. Der Broker sieht dann keinen einzigen
#       Fehlversuch.
#   (C) Zaehler fuer fehlgeschlagene Logins in der Datei LOGIN_FAILS. Ab
#       MAX_LOGIN_FAILS (Standard 3) wird kein weiterer Versuch mehr
#       unternommen, bis die Datei weg ist. Bei Erfolg wird sie geloescht.
#       Damit kann auch ein falsches Passwort das Konto nicht sperren.
#       Zuruecksetzen: Datei ~/teletrader/LOGIN_FAILS loeschen.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "LOGIN_FAILS" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_56")

# ── Helfer direkt vor connect_mt5 ───────────────────────────────────────
A_OLD = 'def connect_mt5() -> bool:\n    _ok = False\n'
A_NEW = '''LOGIN_FAIL_FLAG = "LOGIN_FAILS"   # PATCH56, relativ zum CWD wie PAUSE_FLAG

def _live_creds_ok():
    """(ok, grund) - sind die Live-Zugangsdaten vollstaendig? PATCH56"""
    _lg = str(os.getenv("LIVE_MT5_LOGIN", "")).strip()
    if not _lg.isdigit() or int(_lg) <= 0:
        return False, "LIVE_MT5_LOGIN fehlt oder ist keine Kontonummer"
    if not str(os.getenv("LIVE_MT5_PASSWORD", "")).strip():
        return False, "LIVE_MT5_PASSWORD ist leer"
    if not str(os.getenv("LIVE_MT5_SERVER", "")).strip():
        return False, "LIVE_MT5_SERVER ist leer"
    if not str(os.getenv("LIVE_GOLD_SYMBOL", "")).strip():
        return False, "LIVE_GOLD_SYMBOL ist leer"
    return True, ""

def _login_fails() -> int:
    try:
        with open(LOGIN_FAIL_FLAG, encoding="utf-8") as _f:
            return int((_f.read().strip().split() or ["0"])[0])
    except Exception:
        return 0

def _login_fail_note(reset: bool = False):
    try:
        if reset:
            if os.path.exists(LOGIN_FAIL_FLAG):
                os.remove(LOGIN_FAIL_FLAG)
            return
        _n = _login_fails() + 1
        with open(LOGIN_FAIL_FLAG, "w", encoding="utf-8") as _f:
            _f.write(str(_n) + " " + datetime.now().isoformat() + "\\n")
    except Exception:
        pass

def connect_mt5() -> bool:
    _ok = False
    # PATCH56: im Live-Modus niemals mit unvollstaendigen Daten einloggen.
    if not DEMO_MODE:
        _cok, _cwhy = _live_creds_ok()
        if not _cok:
            log.error("LIVE-Login nicht versucht: " + _cwhy +
                      " - mit /demo zurueckschalten")
            return False
        _mx = int(float(os.getenv("MAX_LOGIN_FAILS", "3")))
        if _mx > 0 and _login_fails() >= _mx:
            log.error("LIVE-Login gesperrt nach " + str(_login_fails()) +
                      " Fehlversuchen. Datei " + LOGIN_FAIL_FLAG +
                      " loeschen, um es erneut zu versuchen.")
            return False
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── Zaehler bei Fehlversuch / Erfolg ────────────────────────────────────
B_OLD = '''        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if not _ok:
            log.error('MT5 Parameter-Login fehlgeschlagen: %s', mt5.last_error())
'''
B_NEW = '''        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if not _ok:
            log.error('MT5 Parameter-Login fehlgeschlagen: %s', mt5.last_error())
            if not DEMO_MODE:
                _login_fail_note()            # PATCH56
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker B:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

C_OLD = '''    account_type = "DEMO" if DEMO_MODE else "LIVE ⚠️"
    log.info(f"MT5 [{account_type}] → Konto {info.login} | Balance: ${info.balance:.2f} {info.currency}")
'''
C_NEW = '''    account_type = "DEMO" if DEMO_MODE else "LIVE ⚠️"
    _login_fail_note(reset=True)              # PATCH56: Erfolg -> Zaehler weg
    log.info(f"MT5 [{account_type}] → Konto {info.login} | Balance: ${info.balance:.2f} {info.currency}")
'''
if src.count(C_OLD) != 1:
    print("FEHLER Anker C:", src.count(C_OLD)); sys.exit(1)
src = src.replace(C_OLD, C_NEW)

# ── /live vorher pruefen ────────────────────────────────────────────────
D_OLD = '''    elif cmd in ("/live", "/demo"):
        switch_to = "live" if cmd == "/live" else "demo"
'''
D_NEW = '''    elif cmd in ("/live", "/demo"):
        switch_to = "live" if cmd == "/live" else "demo"
        if switch_to == "live":               # PATCH56
            _cok, _cwhy = _live_creds_ok()
            if not _cok:
                await send_notification(
                    "\\u274c Wechsel auf LIVE abgelehnt\\n" + _cwhy +
                    "\\nZugangsdaten mit live_setup.sh eintragen.")
                return True
            if _login_fails() > 0:
                _login_fail_note(reset=True)
'''
if src.count(D_OLD) != 1:
    print("FEHLER Anker D:", src.count(D_OLD)); sys.exit(1)
src = src.replace(D_OLD, D_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 56 OK - /live geprueft, Login-Schleife verhindert")
