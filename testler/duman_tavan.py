# -*- coding: utf-8 -*-
"""TAVAN: kacan turu OFIS durduruyor mu -- motor ne olursa olsun.

Kullanici cok motorlu bir sistem istiyor (DeepSeek, Qwen, Kimi, Grok
eklenecek). Tur basina tavani her motordan tek tek beklemek, motor
sayisiyla carpilan bir borctur: bir adaptorde olur, otekinde unutulur.

OLCULMUS SORUN: tavan uygulayamayan motor, tavan istenen her iste
ATLANIYORDU -- yani "tavan koy" demek pratikte "codex'i kapat"
demekti. Kontrol CLI'dan ofise tasindi.

UC SORU, ve ucu de SIMETRIK sinaniyor (her "durdu"nun bir "gecti"
karsiligi var; her seyi durduran bir fren de fren degildir):

1. Kacak freni gercekten FRENLIYOR mu -- ve normal isi kesmiyor mu?
2. Birikmis jeton tavani yeni turu DURDURUYOR mu -- ve isi
   OLDURMUYOR mu?
3. Dolar tavani uygulayamayan basamakta bu SOYLENIYOR mu?

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis import tavan as T
from ofis.motor import MotorHatasi
from ofis.motor.tip import MotorOlayi
from ofis.motor.sahte import SahteMotor

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


# ------------------------------------------------- 1. KACAK FRENI
print("\n1. KACAK FRENI -- sayiyor, karar VERMIYOR")

f = T.KacakFreni(azami_arac=3, azami_cikti_harf=50)
sina("baslangicta asilmamis", f.asildi_mi() == "")
for _ in range(3):
    f.olay("arac", "x")
sina("tavana kadar SERBEST", f.asildi_mi() == "")
f.olay("arac", "x")
sina("tavani asinca FRENLIYOR", bool(f.asildi_mi()))
# Teshis koyup NE oldugunu soylemeyen gosterge, insani bir kez daha
# dusundurur.
sina("sebep SAYIYI soyluyor", "4 arac" in f.asildi_mi(), f.asildi_mi())

f2 = T.KacakFreni(azami_arac=1000, azami_cikti_harf=20)
f2.olay("metin", "a" * 21)
sina("cikti hacmi de FRENLIYOR", bool(f2.asildi_mi()))
sina("sebep hacmi soyluyor", "harf" in f2.asildi_mi())

# Nabiz gibi olaylar SAYILMAZ -- yoksa uzun ama saglikli bir tur,
# yalnizca uzun oldugu icin frenlenirdi.
f3 = T.KacakFreni(azami_arac=2, azami_cikti_harf=1000)
for _ in range(50):
    f3.olay("nabiz", "")
sina("nabiz frene SAYILMIYOR", f3.asildi_mi() == "")

# Varsayilanlar OLCULMUS is profillerinin ustunde olmali: en agir
# olculen tarayici isi 31 arac cagrisi yapmisti.
sina("varsayilan arac tavani olculen isin USTUNDE",
     T.VARSAYILAN_AZAMI_ARAC > 31)
sina("varsayilan jeton tavani en agir isin USTUNDE",
     T.VARSAYILAN_AZAMI_JETON > 4_860_234)


# ------------------------------------------ 2. BIRIKMIS JETON TAVANI
print("\n2. BIRIKMIS JETON TAVANI -- turlar arasi, KESIN olcum")

kok = Path(tempfile.mkdtemp(prefix="ofis-tavan-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Tavan", amac="tavan sinamasi",
                     basari_olcutu="fren tutuyor", kok_klasor=str(kok))
ofis.kadro.ise_al("cinar", "backend", motor="sahte", klasor=str(kok))
g = ofis.tahta.gorev_ac("Agir is", neden="n", ana_hedef="h",
                        kabul_olcutu="k", yazma_alani=["a"])

sina("harcama yokken tavan bos", T.gorev_jetonu(db, ofis.proje_id,
                                                g["id"]) == 0)
sina("bos tavan sebep URETMIYOR",
     T.jeton_tavani_denetle(db, ofis.proje_id, g["id"]) == "")

# Sayim `tur_ozeti` olayindan -- yani KAYDIN TUTULDUGU YERDEN.
for jeton in (1000, 2500):
    db.olay_yaz(ofis.proje_id, "tur_ozeti",
                json.dumps({"jeton": jeton, "maliyet_usd": 0.1}),
                ajan_ad="cinar", gorev_id=g["id"])
sina("jetonlar TOPLANIYOR",
     T.gorev_jetonu(db, ofis.proje_id, g["id"]) == 3500)
sina("tavanin altinda sessiz",
     T.jeton_tavani_denetle(db, ofis.proje_id, g["id"],
                            azami_jeton=10_000) == "")
_s = T.jeton_tavani_denetle(db, ofis.proje_id, g["id"], azami_jeton=3000)
sina("tavan dolunca SEBEP donuyor", bool(_s))
sina("sebep SAYIYI soyluyor", "3,500" in _s, _s)
# Is OLMEZ -- zincirdeki ayni ayrim: kaynak tukenmesi bir hata degildir.
sina("sebep isin OLMEDIGINI soyluyor", "OLMEDI" in _s)

# BASKA gorevin jetonu bu goreve SAYILMAZ -- yoksa yogun bir ofis
# butun isleri birbirinin tavanindan duserdi.
g2 = ofis.tahta.gorev_ac("Baska is", neden="n", ana_hedef="h",
                         kabul_olcutu="k")
sina("baska gorevin harcamasi SAYILMIYOR",
     T.gorev_jetonu(db, ofis.proje_id, g2["id"]) == 0)


# ------------------------------------------- 3. KOLTUK FRENI UYGULUYOR
print("\n3. KOLTUK -- fren gercekten kesiyor mu")


class KacanMotor(SahteMotor):
    """Durmadan arac cagiran bir tur -- gercek bir kacagin sekli."""

    def tur_kos(self, metin, **ayar):
        ayar.pop("izin_araci", None)
        for i in range(500):
            yield MotorOlayi("arac", f"arac_{i}", {})
        yield MotorOlayi("metin", "bitti", {})
        yield MotorOlayi("bitti", "", {"basarili": True, "jeton": 10})


ofis.kadro.ise_al("kacan", "backend", motor="sahte", klasor=str(kok))
g3 = ofis.tahta.gorev_ac("Kacan is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["b"])
olaylar = list(Koltuk(ofis, motor_fabrikasi=lambda a, **k: KacanMotor())
               .akit(g3["no"], "kacan", zaman_asimi=30))
uyarilar = [o for o in olaylar if o["tur"] == "uyari"]
arac_sayisi = len([o for o in olaylar if o["tur"] == "arac"])
sina("fren TUTTU (500 cagri tamamlanmadi)",
     arac_sayisi <= T.VARSAYILAN_AZAMI_ARAC + 2, str(arac_sayisi))
sina("fren SEBEBINI soyledi",
     any("Kacak freni" in (o["govde"] or "") for o in uyarilar),
     str([o["govde"][:60] for o in uyarilar]))

# TERS YON: normal bir tur FRENLENMEMELI. Yoksa "her seyi durduran"
# bir kod da yukaridaki sinamayi gecerdi.
g4 = ofis.tahta.gorev_ac("Normal is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["c"])
_f = lambda a, **k: SahteMotor(  # noqa: E731
    cevap="Bitti." + chr(10) + "KANIT dosya: x -> y")
olay2 = list(Koltuk(ofis, motor_fabrikasi=_f).akit(g4["no"], "cinar",
                                                   zaman_asimi=30))
sina("normal tur FRENLENMIYOR",
     not any("Kacak freni" in (o["govde"] or "") for o in olay2))
sina("normal tur basarili bitti",
     any(o["tur"] == "tur_bitti" and o["ek"].get("basarili") for o in olay2))


# --------------------------------------- 4. JETON TAVANI TURU BASLATMIYOR
print("\n4. JETON TAVANI -- yeni tur BASLAMIYOR")

g5 = ofis.tahta.gorev_ac("Tavani dolmus is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["d"])
db.olay_yaz(ofis.proje_id, "tur_ozeti",
            json.dumps({"jeton": T.VARSAYILAN_AZAMI_JETON + 1}),
            ajan_ad="cinar", gorev_id=g5["id"])
kosuldu = {"n": 0}


class SayanMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        kosuldu["n"] += 1
        ayar.pop("izin_araci", None)
        yield from super().tur_kos(metin, **ayar)


olay3 = list(Koltuk(ofis, motor_fabrikasi=lambda a, **k: SayanMotor())
             .akit(g5["no"], "cinar", zaman_asimi=30))
sina("MOTOR HIC KOSMADI", kosuldu["n"] == 0, str(kosuldu))
sina("sebep gorunur oldu",
     any("Jeton tavani" in (o["govde"] or "") for o in olay3),
     str([o["tur"] for o in olay3]))
# Is OLMEDI: kilit birakildi, yeniden dagitilabilir.
sina("is OLMEDI, hazira dondu",
     ofis.tahta.gorev(g5["no"])["durum"] == "hazir",
     ofis.tahta.gorev(g5["no"])["durum"])


# ------------------------------------- 5. DOLAR TAVANI YOKSA SOYLENIYOR
print("\n5. DOLAR TAVANI uygulanamiyorsa SESSIZ olmuyor")

_gorulen = {}


class AyarGoren(SahteMotor):
    butce_destegi = False

    def tur_kos(self, metin, **ayar):
        _gorulen.update(ayar)
        ayar.pop("izin_araci", None)
        yield from super().tur_kos(metin, **ayar)


g6 = ofis.tahta.gorev_ac("Tavanli is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["e"])
olay4 = list(Koltuk(ofis, motor_fabrikasi=lambda a, **k: AyarGoren(
    cevap="Bitti." + chr(10) + "KANIT dosya: x -> y"))
    .akit(g6["no"], "cinar", butce_usd=1.0, zaman_asimi=30))
# Uygulayamayan motora dolar tavani VERILMEZ -- codex onu alinca turu
# hic baslatmadan reddediyor (olculdu).
sina("uygulayamayan motora dolar tavani VERILMEDI",
     _gorulen.get("butce_usd") is None, str(_gorulen.get("butce_usd")))
sina("yerine gecen kontrol SOYLENDI",
     any("ofis freni" in (o["govde"] or "") for o in olay4),
     str([o["govde"][:70] for o in olay4 if o["tur"] == "uyari"]))
sina("tur yine de KOSTU (atlanmadi)",
     any(o["tur"] == "tur_bitti" for o in olay4))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
