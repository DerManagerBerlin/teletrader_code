#!/usr/bin/env python3
# patch_116_befund.py
# NO_RESTART - nur lesen und berichten, der Bot wird nicht angefasst.
# Befund fuer die Live-Umstellung: welche Schluessel liegen in .env (NUR die
# Namen, niemals Werte), ist das MetaApi-SDK da, welche Terminals sind
# installiert, wieviel Platz ist frei, erreicht der Server die Installer.
import io, os, re, shutil, subprocess, sys, glob

TT = os.path.join(os.path.expanduser("~"), "teletrader")
STATUS = os.path.join(os.path.expanduser("~"), "ttpub", "status.txt")

_zeilen = []


def sag(t):
    t = str(t)
    print("PATCH116 " + t)
    _zeilen.append(t)


def lauf(cmd, timeout=40):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:
        return "Fehler: " + str(e)


# ------------------------------------------------------------ 1. .env Namen
for _p in (os.path.join(TT, ".env"), os.path.join(os.path.expanduser("~"), ".env")):
    if not os.path.exists(_p):
        continue
    _namen = []
    try:
        for ln in io.open(_p, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k = ln.split("=", 1)[0].strip()
            v = ln.split("=", 1)[1].strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
                _namen.append(k + ("+" if v else "-"))
    except Exception as e:
        _namen = ["Lesefehler " + str(e)]
    sag("env " + os.path.basename(os.path.dirname(_p)) + "/.env: " +
        " ".join(sorted(_namen)))

# --------------------------------------------------------------- 2. MetaApi
sag("metaapi linux: " + lauf("python3 -c \"import metaapi_cloud_sdk as m;"
                             "print(getattr(m,'__version__','da'))\" 2>&1 | tail -1"))
sag("pip-Netz: " + lauf("python3 -m pip download --no-deps -d /tmp/p116 "
                        "metaapi-cloud-sdk 2>&1 | tail -2")[:160])
shutil.rmtree("/tmp/p116", ignore_errors=True)

# ------------------------------------------------------------- 3. Terminals
_t = []
for _g in ("~/.wine/drive_c/Program Files/*/terminal64.exe",
           "~/.wine/drive_c/Program Files (x86)/*/terminal64.exe"):
    _t += glob.glob(os.path.expanduser(_g))
sag("Terminals: " + (" | ".join(os.path.basename(os.path.dirname(x)) for x in _t)
                     or "keins"))
sag("Prozesse: " + (lauf("pgrep -c -f terminal64.exe") or "0") + " terminal64")
sag("Platz: " + lauf("df -h / | tail -1 | awk '{print $2\" gesamt \"$4\" frei \"$5\" belegt\"}'"))
sag("RAM: " + lauf("free -m | awk 'NR==2{print $2\" MB gesamt \"$7\" MB verfuegbar\"}'"))

# --------------------------------------------------- 4. Erreichbarkeit Netz
for _name, _url in (("metaapi", "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"),
                    ("ultima", "https://download.mql5.com/cdn/web/ultima.markets.pty/mt5/ultimamarkets5setup.exe"),
                    ("mql5", "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe")):
    sag("netz " + _name + ": " + lauf(
        "curl -o /dev/null -s -I -w '%{http_code} %{size_download}' --max-time 20 '" +
        _url + "'"))

# ----------------------------------------------------- 5. aktuelle Einstellung
_cfg = []
for k in ("RUNNER_FREI", "RUNNER_LEINE_AB_PIPS", "TRAIL_GIVEBACK_PCT",
          "PARTIAL_GEWICHTE", "RISIKO_PROZENT", "MAX_LAYER", "DEMO_MODE",
          "BTC_AKTIV", "VERLUST_SERIE_MAX", "LLM_AKTIV"):
    _cfg.append(k + "=" + str(os.getenv(k, "(nicht gesetzt)")))
sag("env-aktiv: " + " ".join(_cfg))

try:
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with io.open(STATUS, "a", encoding="utf-8") as f:
        for z in _zeilen:
            f.write("BEFUND116 " + z + "\n")
except Exception:
    pass
sag("Befund fertig")
