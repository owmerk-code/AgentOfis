# -*- coding: utf-8 -*-
"""IS BASINA DURAKLAT duman testi (02.10.2026).

Rakipte sohbetin altinda is basina "Durdur · Duraklat · Iptal et" var. Bizde
ust cubuktaki Durdur BUTUN ofisi (butun takimlari) durdurur. Sinanan:
  1. kapilar: yalniz bekleyen/siradaki/calisan is duraklar; iki kez zararsiz
  2. kosan tur KESILIR (kanalli motor), oteki isler etkilenmez
  3. halka duraklatilan isi SECMEZ, oteki takimin isi surer; hepsi
     duraklatildiysa bunu SOYLER (ilerleme yok demez)
  4. Surdur ayni isi yeniden acar ve halka onu kosar
  5. panel: kartta bayrak, seritte Duraklat/Surdur/Iptal
Jeton yakmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import Ofis, Veritabani, Koltuk  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.tahta import TahtaHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def reddedilir(baslik, cagri, parca=""):
    try:
        cagri()
        sina(baslik, False, "-- kabul edildi!")
    except TahtaHatasi as exc:
        sina(baslik, parca.lower() in str(exc).lower(), str(exc)[:120])


print("== is basina duraklat ==\n")
kok = Path(tempfile.mkdtemp(prefix="ofis-duraklat-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Duraklat", amac="a", basari_olcutu="b", kok_klasor=str(kok))
A = ofis.kanat_ac("ANA", "AN")
B = ofis.kanat_ac("YAN", "YN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=A, klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", kanat_id=A, klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("bilge", "backend", kanat_id=A, klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("ayse", "lider", lider_mi=True, kanat_id=B, klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("ruzgar", "backend", kanat_id=B, klasor=str(kok), motor="sahte")


def is_ac(baslik, alan, kanat, sahip):
    return ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k",
                               yazma_alani=alan, kanat_id=kanat, sahip=sahip)


print("1. kapilar")
g1 = is_ac("api", ["api/"], A, "cinar")
r = ofis.tahta.duraklat(g1["no"])
sina("bekleyen/siradaki is duraklar, an yazilir", bool(r.get("duraklatildi")))
sina("iki kez duraklatmak zararsiz (ayni an)", ofis.tahta.duraklat(g1["no"])["duraklatildi"]
     == r["duraklatildi"])
with db.baglanti() as c:
    sina("olay yazildi", c.execute("SELECT COUNT(*) FROM olay WHERE govde LIKE '%DURAKLATTI%'"
                                   ).fetchone()[0] == 1)
ofis.tahta.devam_ettir(g1["no"])
sina("devam_ettir bayragi kaldirir", not ofis.tahta.gorev(g1["no"])["duraklatildi"])
reddedilir("duraklatilmamis is 'surdurulemez'", lambda: ofis.tahta.devam_ettir(g1["no"]), "duraklatilmamis")
g_inc = is_ac("incelenen", ["inc/"], A, "bilge")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'inceleme' WHERE id = ?", (g_inc["id"],))
reddedilir("incelemedeki is duraklamaz", lambda: ofis.tahta.duraklat(g_inc["no"]), "inceleme")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (g_inc["id"],))

print("\n2. kosan tur kesilir")
BAG = {}


class Duraklatan(SahteMotor):
    """Ilk nabizdan sonra patron isi DURAKLATIR (baska surecten gibi)."""

    def __init__(self, **kw):
        super().__init__(senaryo="sessiz", nabiz_sayisi=6, **kw)
        self.yazdi = False

    def tur_kos(self, metin, **ayar):
        for o in super().tur_kos(metin, **ayar):
            yield o
            if o.tur == "nabiz" and not self.yazdi and BAG.get("no"):
                self.yazdi = True
                ofis.tahta.duraklat(BAG["no"])


koltuk = Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: Duraklatan())
koltuk.NOT_ARALIGI_S = 0
ofis.tahta.sahiplen(g1["no"], "cinar", ofis.tahta.gorev(g1["no"])["revizyon"])
BAG["no"] = g1["no"]
olaylar = list(koltuk.akit(g1["no"], "cinar"))
son = [o for o in olaylar if o["tur"] == "tur_bitti"][-1]
sina("tur KESILDI (basarisiz bitti)", son["ek"].get("basarili") is False, str(son["ek"])[:200])
sina("kesilme SOYLENDI", any(o["tur"] == "uyari" and "KESILIYOR" in (o.get("govde") or "")
                            for o in olaylar))
from ofis.koltuk import durdurma_istendi  # noqa: E402
sina("ofisin GENEL durdurmasi istenmedi (oteki takimlar etkilenmez)",
     not durdurma_istendi(db, ofis.proje_id))
BAG["no"] = None

print("\n3. halka duraklatilani secmez")
g2 = is_ac("web", ["web/"], B, "ruzgar")
calistirilan = []


class Kayitci(SahteMotor):
    def tur_kos(self, metin, **ayar):
        calistirilan.append(metin)
        return super().tur_kos(metin, **ayar)


from ofis.orkestra import Orkestra  # noqa: E402
ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **kw: Kayitci(
    senaryo="basarili", cevap="Bitti.\nKANIT dosya: x.md -> yazildi"))
def turlar(g):
    with db.baglanti() as c:
        return c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'basladi' AND gorev_id = ?",
                         (g["id"],)).fetchone()[0]


t1, t2 = turlar(g1), turlar(g2)
ork.tik(kanat_id=None)
sina("duraklatilan is KOSMADI", turlar(g1) == t1, f"{t1} -> {turlar(g1)}")
sina("oteki takimin isi KOSTU", turlar(g2) > t2, f"{t2} -> {turlar(g2)}")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (g2["id"],))
son_adim = list(ork.kos(azami_tik=3))[-1]
sina("yalniz duraklatilan kaldi: halka bunu SOYLER", "DURAKLATILDI" in son_adim.get("sebep", ""),
     str(son_adim))

from ofis.sohbet import durum_yazisi  # noqa: E402
sina("lider/rapor duraklatmayi GORUR (ariza sanmaz -- olculdu 02.10)",
     "PATRON DURAKLATTI" in durum_yazisi(ofis.tahta.gorev(g1["no"])))

print("\n4. Surdur")
ofis.tahta.devam_ettir(g1["no"])
calistirilan.clear()
t1 = turlar(g1)
ork.tik(kanat_id=None)
sina("surdurulen is yeniden KOSTU", turlar(g1) > t1, f"{t1} -> {turlar(g1)}")

print("\n5. panel")
JS = (KOK / "web" / "panel.js").read_text(encoding="utf-8")
PY = (KOK / "ofis" / "panel.py").read_text(encoding="utf-8")
sina("kart duraklatildi bayragini tasiyor", '"duraklatildi": bool(g.get("duraklatildi"))' in PY)
sina("is basina API'ler", '"/api/gorev/{no}/duraklat"' in PY and '"/api/gorev/{no}/surdur"' in PY)
sina("seritte Duraklat/Surdur ve Iptal et", "function surenIsler()" in JS
     and '"Duraklat"' in JS and '"İptal et"' in JS and "kap.append(_suren)" in JS)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
