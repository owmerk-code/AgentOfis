# -*- coding: utf-8 -*-
"""YUK OLCUMU (E73) -- N ajan AYNI ANDA kosarken ofis tikaniyor mu?

Bilinen tavan kayitliydi ama hic olculmemisti: `Veritabani` butun
baglantilari TEK `RLock` ile siraya dizer (19.09: "ajan sayisi buyudukce
tavan olacak"). Burada jeton yakmadan olculur: sahte motor bir tur
boyunca gercek bir motor gibi BEKLER (kelime basina gecikme) ve olay
akitir; koltuk her olayi deftere yazar, nabiz atar, kanit ekler.

Olculen:
  * duvar saati / tek turun suresi  (1.0 = mukemmel paralel)
  * kac is incelemeye ulasti (hepsi olmali), kac tur dustu
  * defter kilidinde bekleme: kilidi almak icin gecen toplam ve en uzun sure

Kullanim:  python testler/olcum_yuk.py [--ajan 5 10 25] [--gecikme 0.15]
Gercek ofise, kasaya, hesaplara DOKUNMAZ (gecici kok, sahte motor).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Orkestra, Veritabani      # noqa: E402
from ofis.motor.sahte import SahteMotor          # noqa: E402

#: KANIT satiri SATIR BASINDA olmali (metin koprusu boyle okur).
CEVAP = "Is bitti adim adim yapildi " * 3 + "\nKANIT terminal: kos -> gecti"


class KilitOlcer:
    """Veritabaninin tek kilidini SARAR: kilidi almak icin beklenen sure
    olculur. Davranis degismez (ayni kilit, ayni sira)."""

    def __init__(self, kilit):
        self._k = kilit
        self.bekleme = 0.0
        self.en_uzun = 0.0
        self.alim = 0
        self._say = threading.Lock()

    def acquire(self, *a, **k):
        t = time.perf_counter()
        r = self._k.acquire(*a, **k)
        d = time.perf_counter() - t
        with self._say:
            self.bekleme += d
            self.en_uzun = max(self.en_uzun, d)
            self.alim += 1
        return r

    def release(self):
        return self._k.release()

    __enter__ = acquire

    def __exit__(self, *a):
        self.release()


def _kilidi_bul(db):
    for ad, deger in vars(db).items():
        if "lock" in type(deger).__name__.lower():
            return ad
    return None


def olc(n: int, gecikme: float) -> dict:
    kok = Path(tempfile.mkdtemp(prefix="ofis-yuk-"))
    db = Veritabani(kok / "o.sqlite3")
    o = Ofis.proje_ac(db, "Yuk", amac="a", basari_olcutu="b", kok_klasor=str(kok))
    k = o.kanat_ac("A", "A")
    o.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=k, motor="sahte",
                   klasor=str(kok))
    for i in range(n):
        o.kadro.ise_al(f"a{i}", "backend", kanat_id=k, motor="sahte", klasor=str(kok))
        o.tahta.gorev_ac(f"Is {i}", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=[f"alan{i}/"], kanat_id=k)
    kilit_ad = _kilidi_bul(db)
    olcer = None
    if kilit_ad:
        olcer = KilitOlcer(getattr(db, kilit_ad))
        setattr(db, kilit_ad, olcer)

    def fabrika(ad, **ayar):
        return SahteMotor(gecikme=gecikme, cevap=CEVAP)

    tek = len(CEVAP.split(" ")) * gecikme
    ork = Orkestra(o, motor_fabrikasi=fabrika)
    bas = time.monotonic()
    oz = ork.tik(paralel=n)
    sure = time.monotonic() - bas
    with db.baglanti() as c:
        durum = {r["durum"]: r["n"] for r in c.execute(
            "SELECT durum, COUNT(*) n FROM gorev WHERE proje_id=? GROUP BY durum",
            (o.proje_id,))}
        hata = c.execute("SELECT COUNT(*) FROM olay WHERE proje_id=? AND tur='hata'",
                         (o.proje_id,)).fetchone()[0]
        olay = c.execute("SELECT COUNT(*) FROM olay WHERE proje_id=?",
                         (o.proje_id,)).fetchone()[0]
    return {"ajan": n, "baslatilan": len(oz.get("baslatilan", [])),
            "paralel": oz.get("paralel"), "sure_sn": round(sure, 2),
            "tek_tur_sn": round(tek, 2), "oran": round(sure / tek, 2) if tek else None,
            "incelemede": durum.get("inceleme", 0), "durumlar": durum, "hata_olayi": hata,
            "olay": olay,
            "kilit_bekleme_sn": round(olcer.bekleme, 3) if olcer else None,
            "kilit_en_uzun_ms": round(olcer.en_uzun * 1000, 1) if olcer else None,
            "kilit_alim": olcer.alim if olcer else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ajan", type=int, nargs="+", default=[5, 10, 25])
    ap.add_argument("--gecikme", type=float, default=0.15)
    a = ap.parse_args()
    print(f"{'ajan':>5} {'bas.':>5} {'sure':>7} {'tek':>6} {'oran':>5} "
          f"{'inceleme':>8} {'hata':>5} {'olay':>6} {'kilit bekl.':>11} {'en uzun':>9}")
    for n in a.ajan:
        r = olc(n, a.gecikme)
        print(f"{r['ajan']:>5} {r['baslatilan']:>5} {r['sure_sn']:>6}s {r['tek_tur_sn']:>5}s "
              f"{r['oran']:>5} {r['incelemede']:>8} {r['hata_olayi']:>5} {r['olay']:>6} "
              f"{str(r['kilit_bekleme_sn']) + 's':>11} {str(r['kilit_en_uzun_ms']) + 'ms':>9}")
        if r["incelemede"] != n:
            print("   DIKKAT: her is incelemeye ulasmadi:", r["durumlar"])


if __name__ == "__main__":
    main()
