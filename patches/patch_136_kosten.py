#!/usr/bin/env python3
# patch_136_kosten.py
# NO_RESTART - liest nur.
#
# Was kostet diese VM tatsaechlich? Maschinentyp, Zone und Plattengroesse
# stehen im Metadatendienst von Google, der ohne Zugangsdaten erreichbar ist.
# Projekt-ID und Instanzname werden bewusst NICHT ausgegeben, status.txt
# liegt in einem oeffentlichen Repo.
import io, os, subprocess

PUB = os.path.join(os.path.expanduser("~"), "ttpub")
_z = []


def sag(t):
    t = str(t)
    print("PATCH136 " + t)
    _z.append(t)


def lauf(cmd, timeout=25):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:
        return "Fehler: " + str(e)


MD = ("curl -s --max-time 8 -H 'Metadata-Flavor: Google' "
      "http://metadata.google.internal/computeMetadata/v1/")
sag("Maschinentyp: " + (lauf(MD + "instance/machine-type").split("/")[-1] or "?"))
sag("Zone: " + (lauf(MD + "instance/zone").split("/")[-1] or "?"))
sag("CPU-Plattform: " + (lauf(MD + "instance/cpu-platform") or "?"))
_pre = lauf(MD + "instance/scheduling/preemptible")
sag("Preemptible/Spot: " + (_pre or "?"))
_ip = lauf(MD + "instance/network-interfaces/0/access-configs/0/external-ip")
sag("Externe IP vorhanden: " + ("ja" if _ip and "." in _ip else "nein"))

sag("CPUs: " + lauf("nproc"))
sag("RAM: " + lauf("free -m | awk 'NR==2{print $2\" MB gesamt, \"$3\" MB benutzt, \"$7\" MB verfuegbar\"}'"))
sag("Platte: " + lauf("df -h --output=size,used,avail / | tail -1 | tr -s ' '"))
sag("Last (1/5/15): " + lauf("cut -d' ' -f1-3 /proc/loadavg"))
sag("Laufzeit: " + lauf("uptime -p"))
sag("Groesste Verbraucher RAM: " + lauf(
    "ps -eo rss,comm --sort=-rss | head -6 | awk '{printf \"%s=%dMB \", $2, $1/1024}'"))
sag("Swap: " + lauf("free -m | awk 'NR==3{print $2\" MB, benutzt \"$3\" MB\"}'"))

try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("KOSTEN136 " + x + "\n")
except Exception:
    pass
