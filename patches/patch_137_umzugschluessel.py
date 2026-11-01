#!/usr/bin/env python3
# patch_137_umzugschluessel.py
# NO_RESTART - der laufende Bot wird nicht angefasst.
#
# Vorbereitung fuer den Umzug zu Hetzner: ein eigenes Schluesselpaar nur
# fuer diesen Zweck. Der private Teil bleibt auf diesem Server und wird
# nirgends ausgegeben. Der oeffentliche Teil kommt in status.txt, den traegt
# Alex beim Anlegen des neuen Servers ein. Ein oeffentlicher Schluessel ist
# kein Geheimnis, er erlaubt niemandem Zugang ohne den privaten Teil.
import io, os, stat, subprocess

HOME = os.path.expanduser("~")
SSH = os.path.join(HOME, ".ssh")
KEY = os.path.join(SSH, "id_ed25519_umzug")
PUB = os.path.join(HOME, "ttpub")
_z = []


def sag(t):
    t = str(t)
    print("PATCH137 " + t)
    _z.append(t)


os.makedirs(SSH, exist_ok=True)
try:
    os.chmod(SSH, 0o700)
except Exception:
    pass

if os.path.exists(KEY):
    sag("Schluessel war schon da, kein neuer erzeugt")
else:
    try:
        _p = subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-q",
             "-C", "teletrader-umzug", "-f", KEY],
            capture_output=True, text=True, timeout=60)
        if _p.returncode != 0:
            sag("FEHLER ssh-keygen: " + ((_p.stderr or "")[:150]))
        else:
            sag("Schluesselpaar erzeugt")
    except Exception as e:
        sag("FEHLER: " + str(e))

try:
    os.chmod(KEY, 0o600)
except Exception:
    pass

try:
    _pub = io.open(KEY + ".pub", encoding="utf-8").read().strip()
    sag("Rechte privater Schluessel: " +
        oct(stat.S_IMODE(os.stat(KEY).st_mode)))
    sag("OEFFENTLICHER SCHLUESSEL (dieser gehoert zu Hetzner):")
    sag(_pub)
except Exception as e:
    sag("oeffentlicher Teil nicht lesbar: " + str(e))

sag("Platzbedarf fuer den Umzug: " + subprocess.run(
    "du -sh ~/teletrader 2>/dev/null | cut -f1", shell=True,
    capture_output=True, text=True).stdout.strip())
sag("Terminalverzeichnis: " + subprocess.run(
    "du -sh ~/.wine 2>/dev/null | cut -f1", shell=True,
    capture_output=True, text=True).stdout.strip())

try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("UMZUG137 " + x + "\n")
except Exception:
    pass
