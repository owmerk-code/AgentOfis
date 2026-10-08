# -*- coding: utf-8 -*-
"""KABIN PANELLE BIRLIKTE KAPANIR (08.10.2026, canli bulgu).

Gosteri paneli durdurulunca kabin Chrome'u saatlerce yasadi ve profili kilitli
tuttu; patronun panelinin tarayicisi "profil baska bir Chrome'da acik" diye
acilamadi. Kabin artik panel surecinin IS NESNESINDE (`SurecKafesi`): panel
sureci oldurulse bile Chrome biter.

Gercek Chrome, GECICI profil (`_temizlik` evi geciciye cevirir), bos kapi.
"""
import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from ofis import kabin  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


try:
    kabin.calistirilabilir_bul()
except Exception as exc:                          # noqa: BLE001
    print(f"  [ATLANDI] Chrome yok: {exc}")
    print("\n== sonuc: 0 gecti, 0 kaldi ==")
    sys.exit(0)

with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    kapi = _s.getsockname()[1]

COCUK = (
    "import sys, time\n"
    f"sys.path.insert(0, {str(KOK / 'testler')!r}); sys.path.insert(0, {str(KOK)!r})\n"
    "import _temizlik\n"
    "from ofis import kabin\n"
    f"k = kabin.Kabin(kapi={kapi})\n"
    "k.ac()\n"
    "print('ACIK', k.kafes.kuruldu, flush=True)\n"
    "time.sleep(120)\n")
c = subprocess.Popen([sys.executable, "-c", COCUK], stdout=subprocess.PIPE, text=True,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
satir = ""
bitis = time.time() + 60
while time.time() < bitis:
    satir = c.stdout.readline().strip()
    if satir.startswith("ACIK"):
        break
sina("panel (alt surec) kabini acti, kafes kuruldu", satir == "ACIK True" and kabin.acik_mi(kapi), satir)
c.kill()                                          # panel ZORLA durduruldu (TerminateProcess)
c.wait(timeout=10)
kapandi = False
for _ in range(40):
    if not kabin.acik_mi(kapi):
        kapandi = True
        break
    time.sleep(0.25)
sina("panel oldurulunce kabin Chrome'u da KAPANDI (profil kilidi kalmaz)", kapandi)
if not kapandi:
    kabin.cdp_kapat(kapi)

# E1: ilk acilis olumunun SEBEBI (08.10 olculdu, 20/20 temiz acilis): ayni
# profil baska kabinde acikken ikinci Chrome cikis 21 ile kapanir. Hata duz
# soylenir ve kayit cikis kodunu tutar.
def _bos():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_a = kabin.Kabin(kapi=_bos())
_a.ac()
_b = kabin.Kabin(kapi=_bos())
_hata = None
try:
    _b.ac()
except kabin.KabinHatasi as exc:
    _hata = exc
_kayit = Path(kabin.gunluk_yolu()).read_text(encoding="utf-8", errors="replace")
sina("ayni profil ikinci kez: duz sebep (profil baska Chrome'da acik), cikis 21",
     _hata is not None and getattr(_hata, "cikis", None) == kabin.Kabin.PROFIL_KILITLI
     and "profili baska" in str(_hata), str(_hata)[:160])
sina("kabin kaydi olumun cikis kodunu tutar",
     "kabin kapandi cikis=21 (profil baska Chrome da acik)" in _kayit)
_a.kapat()
_b.kapat()
_c = kabin.Kabin(kapi=_bos())
_c.ac()
sina("ilki kapaninca ayni profil yeniden acilir", kabin.acik_mi(_c.kapi))
_c.kapat()
print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
