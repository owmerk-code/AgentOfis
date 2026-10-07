# -*- coding: utf-8 -*-
"""KABIN INDIRMELERI ISIN KLASORUNE (06.10.2026 canli gosteri bulgusu). Jeton yakmaz.

Gosteride ajanin Flow'dan indirdigi video patronun KENDI `Indirilenler`
klasorune dustu. Artik is suresince kabinin indirme klasoru isin
`.ofis/indirilenler/` klasoru; tur nasil biterse bitsin eski haline doner.

GERCEK basliksiz Chrome (gecici profil, ayri kapi) ve gercek bir indirme
(Content-Disposition: attachment) ile olculur.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import http.server
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import kabin  # noqa: E402
from ofis.surec import PENCERE_YOK  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-indirme-"))
KAPI = 9396
print("1. gercek Chrome ile indirme yeri")
sina("kabin yoksa ayarlanmaz (is durmaz)", kabin.indirme_yeri("http://127.0.0.1:1", str(d)) is None)
sina("adres bozuksa ayarlanmaz", kabin.indirme_yeri("", str(d)) is None)


class _Isleyici(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        veri = b"OFIS-INDIRME-SINAMASI"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="ofis-sinama-{self.path[-1]}.bin"')
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *a):
        pass


sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Isleyici)
threading.Thread(target=sunucu.serve_forever, daemon=True).start()
adres = f"http://127.0.0.1:{sunucu.server_address[1]}/indir"
profil = d / "profil"
# SINAMANIN KENDISI de patronun Indirilenler'ine dosya dusurmesin (07.10 olculdu):
# sinama Chrome'unun VARSAYILAN indirme klasoru gecici klasor.
varsayilan = d / "varsayilan"
varsayilan.mkdir()
(profil / "Default").mkdir(parents=True)
(profil / "Default" / "Preferences").write_text(json.dumps(
    {"download": {"default_directory": str(varsayilan), "prompt_for_download": False}}), encoding="utf-8")
krom = subprocess.Popen([kabin.calistirilabilir_bul(), "--headless=new", f"--remote-debugging-port={KAPI}",
                         f"--user-data-dir={profil}", "--no-first-run", "--no-default-browser-check",
                         "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=PENCERE_YOK)
try:
    for _ in range(60):
        if kabin.acik_mi(KAPI):
            break
        time.sleep(0.25)
    sina("sinama Chrome'u ayakta", kabin.acik_mi(KAPI))
    hedef = d / "is" / ".ofis" / "indirilenler"
    hedef.mkdir(parents=True)
    t = kabin.indirme_yeri(f"http://127.0.0.1:{KAPI}", str(hedef))
    sina("indirme yeri ISIN klasorune ayarlandi", t is not None)

    def indir(n, klasor):
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{KAPI}/json/new?{adres}{n}",
                                                      method="PUT"), timeout=5).read()
        f = klasor / f"ofis-sinama-{n}.bin"
        for _ in range(40):
            if f.is_file() and f.read_bytes() == b"OFIS-INDIRME-SINAMASI":
                return True
            time.sleep(0.25)
        return False

    sina("indirilen dosya ISIN klasorune dustu", indir(1, hedef), str(list(hedef.iterdir())))
    time.sleep(2)
    sina("  baglanti ACIK kaldikca ikinci indirme de iste (ayar dusmedi)", indir(2, hedef),
         str(list(hedef.iterdir())))
    if t is not None:
        t.bitir()
    sina("tur bitince eski haline dondu (varsayilan klasore indi)", indir(3, varsayilan),
         str(list(varsayilan.iterdir())))
finally:
    try:
        kabin.cdp_kapat(KAPI)
    except Exception:
        pass
    krom.kill()
    sunucu.shutdown()
    _sizan = [p for p in (Path.home() / "Downloads").glob("ofis-sinama-*.bin")]
    for _p in _sizan:
        _p.unlink()
    sina("patronun Indirilenler klasorune HICBIR sinama dosyasi dusmedi", not _sizan, str(_sizan))

print("\n2. koltuk: tur nasil biterse bitsin geri alinir")
from ofis.koltuk import Koltuk  # noqa: E402
cagri = []


class _SahteTutucu:
    def bitir(self):
        cagri.append("bitti")


def _dusen(self, no, ajan_ad, *, _indirme=None, **ayar):
    _indirme["indirme"] = _SahteTutucu()
    yield {"tur": "basladi"}
    raise RuntimeError("tur dustu")


Koltuk._akit, _eski_akit = _dusen, Koltuk._akit
try:
    k = Koltuk.__new__(Koltuk)
    try:
        list(k.akit(1, "deniz"))
    except RuntimeError:
        pass
    sina("tur DUSTUGUNDE indirme baglantisi kapandi", cagri == ["bitti"], str(cagri))
    cagri.clear()
    g = k.akit(1, "deniz")
    next(g)
    g.close()
    sina("akis yarida BIRAKILINCA da kapandi", cagri == ["bitti"], str(cagri))
finally:
    Koltuk._akit = _eski_akit
src = (Path(__file__).resolve().parent.parent / "ofis" / "koltuk.py").read_text(encoding="utf-8")
sina("ajana indirme klasoru SOYLENIYOR", "`.ofis/indirilenler/`" in src)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
