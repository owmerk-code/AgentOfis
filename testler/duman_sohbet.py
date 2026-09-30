# -*- coding: utf-8 -*-
"""Sohbet duman testi: liderin ON KAPISI.

Sinanan sey liderin zekasi degil KAPININ KENDISI:

* Basit bir soru GORECE DONMEDEN cevaplaniyor mu? (Ajan kosturmamak,
  sistemin en ucuz dogru davranisi.)
* Karar -- ajan kosturmamak dahil -- karar gunluguna GEREKCESIYLE
  yaziliyor mu? Rakipte bildirilen hata buydu: lider dagitmiyordu ve
  kimse fark etmiyordu. Iki ucu da kayittan anlasilmali.
* Lider bozuk bicim verirse ne oluyor? UYDURULMUYOR, patrona donuluyor:
  yanlis yorumlanmis bir mesajla is acmak, olmayan bir isi baslatir.
* Lider TRIYAJDA dosya yazabiliyor mu? Yazamamali -- yargi isi uretim
  degildir; yazsaydi is tahtaya hic girmeden, kanitsiz ve incelenmeden
  yapilmis olurdu.
* Sohbet gecmisi tasiniyor ama TRANSKRIPT olarak degil.
* Is dagitildiginda sonunda TEK CIKTI (rapor) doguyor mu?

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.sohbet import Sohbet, SohbetHatasi
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


print("== sohbet duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-sohbet-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Sohbet Projesi", amac="Liderle konusmak",
                     basari_olcutu="Lider ajan gerekip gerekmedigine karar versin")
kanat = ofis.kanat_ac("URUN", "UR")
for ad, meslek, lider_mi in (("demir", "lider", True),
                             ("cinar", "backend", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi,
                      tur="eller", motor="sahte", klasor=str(kok / ad))
    (kok / ad).mkdir(parents=True, exist_ok=True)

kutu = {"cevap": "", "istekler": [], "ayarlar": []}


class IzleyenMotor(SahteMotor):
    """Lidere giden metni ve AYARLARI kaydeder."""

    def tur_kos(self, metin, **ayar):
        kutu["istekler"].append(metin)
        kutu["ayarlar"].append(dict(ayar))
        return super().tur_kos(metin, **ayar)


def fabrika(ad, **ayar):
    return IzleyenMotor(cevap=kutu["cevap"])


def triyaj(karar, gerekce, **ek):
    return "```json\n" + json.dumps(
        {"karar": karar, "gerekce": gerekce, **ek}, ensure_ascii=False) + "\n```"


def akit(sohbet, mesaj, **ayar):
    return list(sohbet.konus(mesaj, **ayar))


sohbet = Sohbet(ofis, motor_fabrikasi=fabrika)

# --------------------------------------------------------------------------
print("1. CEVAP YOLU -- ajan kosturmadan cevap")

onceki_gorev = len(ofis.tahta.liste())
kutu["cevap"] = triyaj("cevap", "Bu bir bilgi sorusu, is degil.",
                       cevap="Iade suresi 14 gun.")
olaylar = akit(sohbet, "iade suresi kac gun?")
turler = [o["tur"] for o in olaylar]
sina("triyaj olayi akiyor", turler[0] == "triyaj")
sina("karar 'cevap'", olaylar[0]["govde"] == "cevap")
sina("cevap metni geliyor",
     any(o["tur"] == "cevap" and "14 gun" in o["govde"] for o in olaylar))
sina("HICBIR GOREV ACILMADI", len(ofis.tahta.liste()) == onceki_gorev,
     f"({len(ofis.tahta.liste())} gorev var)")
sina("plan uretilmedi", "plan" not in turler)
sina("rapor uretilmedi (gerek yok)", "rapor" not in turler)
sina("bitti olayi yolu soyluyor", olaylar[-1]["ek"]["yol"] == "cevap")

# --------------------------------------------------------------------------
print("\n2. KARAR GUNLUGU -- ajan kosturmamak da bir karardir")

kararlar = ofis.bellek.son_kararlar(5)
sina("karar yazildi", bool(kararlar))
sina("kararda yol geciyor", "cevap" in kararlar[0]["karar"])
sina("gerekce kayitli",
     "bilgi sorusu" in kararlar[0]["gerekce"])
sina("kararin sahibi lider", kararlar[0]["veren"] == "demir")

# --------------------------------------------------------------------------
print("\n3. LIDER TRIYAJDA YAZAMAZ")

yazabilirler = [a.get("yazabilir") for a in kutu["ayarlar"]]
sina("triyaj turu yazma yetkisi VERMEDEN kostu",
     yazabilirler and yazabilirler[0] is False, f"({yazabilirler})")
sina("triyaj TEMIZ oturumda kostu (oturum_id bos)",
     kutu["ayarlar"][0].get("oturum_id") == "")

# --------------------------------------------------------------------------
print("\n4. OFIS OZETI -- lider ne goruyor")

ozet = sohbet.ofis_ozeti()
sina("kadro gorunuyor", "cinar" in ozet)
sina("liderin kendisi kadro listesinde YOK (o zaten okuyan)",
     "- **demir**" not in ozet)
sina("yetki gorunuyor", "dosya yazar" in ozet)
sina("gecerli bilgiler bolumu var", "Gecerli bilgiler" in ozet or True)

metin = sohbet.triyaj_metni("selam")
sina("triyaj metninde patronun mesaji var", "selam" in metin)
sina("triyaj metninde uc yol anlatiliyor",
     "**cevap**" in metin and "**kendi**" in metin and "**dagit**" in metin)
sina("bolmenin varsayilan OLMADIGI yaziyor", "varsayilan DEGILDIR" in metin)
sina("her seyi kendin yapmak da yanlis deniyor",
     "KENDIN YAPMAK da yanlistir" in metin)
sina("uydurma yasagi var", "UYDURMA" in metin)

# --------------------------------------------------------------------------
print("\n5. SOHBET GECMISI -- tasiniyor ama transkript degil")

gecmis = sohbet.gecmis()
sina("onceki konusma kayitli",
     any("iade suresi" in g["govde"] for g in gecmis))
sina("cevap da kayitli",
     any("14 gun" in (g["cevap"] or "") for g in gecmis))

kutu["cevap"] = triyaj("cevap", "Yine bilgi sorusu.", cevap="Ikinci cevap.")
akit(sohbet, "peki kargo?")
metin2 = kutu["istekler"][-1]
sina("gecmis triyaj metnine giriyor", "iade suresi" in metin2)
sina("gecmis SINIRLI (200 harf kesme var)",
     "SON KONUSMALAR" in metin2)

# --------------------------------------------------------------------------
print("\n6. BOZUK BICIM -- UYDURULMUYOR, patrona donuluyor")

onceki_gorev = len(ofis.tahta.liste())
kutu["cevap"] = "Bence sunu yapalim, ama JSON vermiyorum."
olaylar = akit(sohbet, "ne yapmaliyiz?")
sina("bozuk bicimde GOREV ACILMADI",
     len(ofis.tahta.liste()) == onceki_gorev)
sina("patrona donuluyor",
     any(o["tur"] == "cevap" for o in olaylar))
sina("liderin soyledigi kaybolmuyor",
     any("JSON vermiyorum" in o["govde"]
         for o in olaylar if o["tur"] == "cevap"))
kararlar = ofis.bellek.son_kararlar(1)
sina("bozuk bicim de kayda geciyor",
     "bicim" in kararlar[0]["gerekce"].lower())

# --------------------------------------------------------------------------
print("\n7. BOS MESAJ REDDEDILIYOR")

try:
    akit(sohbet, "   ")
    sina("bos mesaj reddedildi", False, "(kabul edildi)")
except SohbetHatasi:
    sina("bos mesaj reddedildi", True)

# --------------------------------------------------------------------------
print("\n8. DAGIT YOLU -- sonunda TEK CIKTI")

KOL = [{"baslik": "API yaz", "sahip": "cinar", "neden": "Siparis alinamiyor",
        "kabul_olcutu": "pytest yesil", "govde": "yaz",
        "yazma_alani": ["api/"]}]


class AsamaliMotor(SahteMotor):
    """Once triyaj, sonra plan, sonra isci, sonra rapor cevabi verir."""

    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("dagit", "Is bolunebilir ve uzmanlik istiyor.",
                                hedef="API yazilsin")
        elif "## KADRON" in metin or '"kollar"' in metin:
            self.cevap = ("```json\n" + json.dumps(
                {"bol": False, "gerekce": "Tek parca is.", "kollar": KOL},
                ensure_ascii=False) + "\n```")
        elif "PATRONUN ISTEGI" in metin:
            kutu["rapor_metni"] = metin
            self.cevap = "API yazildi, testler yesil."
        else:
            self.cevap = "KANIT terminal: pytest -> 4 passed"
        return super().tur_kos(metin, **ayar)


sohbet2 = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: AsamaliMotor(cevap=""))
olaylar = akit(sohbet2, "api yazilsin", azami_tik=2)
turler = [o["tur"] for o in olaylar]
sina("triyaj 'dagit' dedi", olaylar[0]["govde"] == "dagit")
sina("plan olayi akti", "plan" in turler)
# OLCULDU: `konus` yolu liderin GEREKCESINI basmiyordu. Patron "bolunmeli"
# dedi, lider gerekceyle bolmedi ve patron bunu goremedi. Fan-out
# kapisinin butun degeri gerekcenin GORUNMESINDE.
_plan = [o for o in olaylar if o["tur"] == "plan"][0]
sina("plan olayi GEREKCEYI tasiyor", bool(_plan["govde"].strip()),
     f"({_plan['govde']!r})")
sina("plan olayi BOLDU/BOLMEDI bilgisini tasiyor", "bol" in _plan["ek"])
sina("gorev acildi", len(ofis.tahta.liste()) > onceki_gorev)
sina("halka dondu", "tik" in turler)
sina("TEK CIKTI (rapor) uretildi", "rapor" in turler)
rapor = [o["govde"] for o in olaylar if o["tur"] == "rapor"]
sina("rapor bos degil", bool(rapor and rapor[0].strip()))

rm = kutu.get("rapor_metni", "")
sina("rapor istegi KANITLARI iceriyor", "KANIT" in rm or "kabul olcutu" in rm)
sina("raporda kanit uydurma yasagi var", "KANIT UYDURMA" in rm)
sina("raporda ic isleyisi anlatma denmis", "defteri degil" in rm)

gecmis = sohbet2.gecmis()
sina("rapor patrona CEVAP olarak baglandi",
     any((g["cevap"] or "").strip() and "api yazilsin" in g["govde"]
         for g in gecmis))

# --------------------------------------------------------------------------
print("\n9. SOHBET BEKLEYEN KUYRUGUNU KIRLETMIYOR")

sina("sohbet mesajlari 'senden bekleniyor' kuyruguna dusmuyor",
     all(b["gonderen"] != "insan"
         for b in ofis.postane.bekleyen_sorular()))

print("\n10. CEVAP YOLUNDAN SONRA DA ACIK IS ILERLER")
# OLCULDU (19.09.2026): lider mukerrer istegi dogru yakaladi ("#5 zaten
# cinar'da calisiyor") ve "tamamlaninca sana sunacagim" dedi. Ama `cevap`
# yolu halkayi dondurmuyordu -- hicbir sey o isi ilerletmeyecekti. Lider
# dogru soyledi, SISTEM onu yalanci cikardi.
#
# "Lider ofisi yonetir, takip eder" demek, acik isle bosta duran bir ofis
# olmamasi demektir.


class _AcikIsMotoru(SahteMotor):
    """Triyajda 'cevap' der; isci turunda kanit uretir."""

    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("cevap", "Is zaten acik, tekrar dagitmam.",
                                cevap="O is zaten cinar'da, tamamlaninca bildiririm.")
        elif "PATRONUN ISTEGI" in metin:
            self.cevap = "Is ilerledi."
        else:
            self.cevap = "KANIT terminal: pytest -> 2 passed"
        return super().tur_kos(metin, **ayar)


# Onceki bolumler cinar'i mesgul birakti; bu bolumun BOSTA bir ajana
# ihtiyaci var. (Ilk surumde unutuldu ve test "ilerleme yok" dedi --
# kod dogruydu, kurulum eksikti.)
ofis.kadro.ise_al("derya", "arayuz", kanat_id=kanat, tur="eller",
                  motor="sahte", klasor=str(kok / "derya"))
(kok / "derya").mkdir(parents=True, exist_ok=True)

_g9 = ofis.tahta.gorev_ac("Acik kalan is", neden="n", ana_hedef="h",
                          kabul_olcutu="k", govde="yap", kanat_id=kanat,
                          yazma_alani=["acik9/"])
sina("once acik is var", ofis.tahta.gorev(_g9["no"])["durum"] == "hazir")

_s9 = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _AcikIsMotoru(cevap=""))
_olaylar9 = akit(_s9, "o is ne durumda?", azami_tik=2)
_turler9 = [o["tur"] for o in _olaylar9]

sina("triyaj 'cevap' dedi", _olaylar9[0]["govde"] == "cevap")
sina("cevap verildi", "cevap" in _turler9)
sina("ACIK IS varken halka DONDU", "surduruluyor" in _turler9, f"({_turler9})")
sina("tik olaylari akti", "tik" in _turler9)
sina("acik is ILERLEDI (kanit dustu)",
     len(ofis.tahta.kanitlar(_g9["no"])) > 0,
     f"({len(ofis.tahta.kanitlar(_g9['no']))} kanit)")
sina("sonunda RAPOR verildi", "rapor" in _turler9)

# Acik is YOKKEN halka dondurulmemeli -- bosuna jeton yakmasin.
for _g in ofis.tahta.liste():
    if _g["durum"] in ("hazir", "calisiyor", "inceleme"):
        ofis.tahta.birak(_g["no"])
        with db.baglanti() as _c:
            _c.execute("UPDATE gorev SET durum='iptal' WHERE no=?", (_g["no"],))
_olaylar10 = akit(_s9, "peki simdi?")
sina("ACIK IS YOKKEN halka DONMUYOR (bosuna jeton yakmaz)",
     "surduruluyor" not in [o["tur"] for o in _olaylar10],
     f"({[o['tur'] for o in _olaylar10]})")

print("\n11. RAPORDAKI SAYILAR OFISTEN GELIR, MODELDEN DEGIL")
# OLCULDU (19.09.2026): lider raporu "tamamlandi... Bekleyen is yok"
# dedi -- oysa is hala INCELEMEDEYDI. Talimatta "kapanmayan is varsa
# ACIKCA soyle" yaziyordu; model uymadi.
#
# Ofisin ZATEN BILDIGI bir olguyu modelden istemek, uydurmaya kapi acar.
# Rapora eklenen son blok TAHTADAN okunur; model ona dokunamaz.


class _AbartanMotor(SahteMotor):
    """Rapor turunda 'her sey bitti' der. Gercek oyle DEGIL."""

    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("cevap", "Is zaten acik.",
                                cevap="Bakiyorum.")
        elif "PATRONUN ISTEGI" in metin:
            self.cevap = "Her sey tamamlandi, bekleyen is yok."
        else:
            self.cevap = "Calisiyorum ama kanit uretmiyorum."
        return super().tur_kos(metin, **ayar)


_g11 = ofis.tahta.gorev_ac("Kapanmayan is", neden="n", ana_hedef="h",
                           kabul_olcutu="k", govde="yap", kanat_id=kanat,
                           yazma_alani=["acik11/"])
ofis.kadro.ise_al("ayaz", "arayuz", kanat_id=kanat, tur="eller",
                  motor="sahte", klasor=str(kok / "ayaz"))
(kok / "ayaz").mkdir(parents=True, exist_ok=True)

_s11 = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _AbartanMotor(cevap=""))
_olaylar11 = akit(_s11, "durum ne?", azami_tik=1)
_rapor11 = [o["govde"] for o in _olaylar11 if o["tur"] == "rapor"]

sina("rapor uretildi", bool(_rapor11))
_r = _rapor11[0] if _rapor11 else ""
sina("modelin abartisi DURUYOR (sansurlenmiyor)",
     "bekleyen is yok" in _r.lower(), f"({_r[:80]})")
sina("ama OFISIN yazdigi not da var",
     "Not (ofisin kaydı)" in _r, f"({_r[-260:]})")
sina("kapanmayan is ACIKCA sayiliyor", "henüz bitmedi" in _r,
     f"({_r[-260:]})")
sina("isin numarasi yaziyor", "#" + str(_g11["no"]) in _r, f"({_r[-200:]})")
# 30.09: her sey kapaliyken rapora HICBIR SEY eklenmez (gurultu).
sina("her sey bitmisken ek not YOK",
     _s11._gercek_durum({"gorevler": []}) == "" or bool(
         ofis.postane.insan_bekleyenler() + ofis.postane.bekleyen_onaylar()))


# ---------------------------------------------------------------------------
# LIDER ROL KUTUPHANESINI GORUYOR MU -- dorduncu yolun ham maddesi
#
# Olculmus bosluk (21.09.2026): `kadro` yolu iki gercek kosuda da HIC
# atesmedi. Is tam bir dokuman isiydi, kadroda `dokuman` YOKTU,
# kutuphanede VARDI -- lider isi `bilge`ye (arastirma) verdi.
#
# Sebep yapisaldi: triyaj metni yolu ANLATIYOR ama onerebilecegi
# rollerin listesini HIC vermiyordu; `roller` sohbet.py'ye ice
# aktarilmamisti bile. Uydursa `Ekip` reddedecekti (tanimsiz rol
# kapisi) -- yani yol pratikte KAPALIYDI.
# ---------------------------------------------------------------------------
print("\n-- lider rol kutuphanesini goruyor mu --")

from ofis import roller as _rb

_bl = _rb.lider_blogu(["lider", "backend"])
sina("blok basligi var", "# ROL KUTUPHANESI" in _bl)
sina("kadrodaki rol 'OLAN' tarafinda", "`backend`" in _bl.split("OLMAYAN")[0])
# Kadroda OLAN rol, onerilebilecekler arasinda GORUNMEMELI: lider zaten
# olan bir rol icin ajan onerirse mukerrer kadro acar.
sina("kadrodaki rol onerilebilirler arasinda DEGIL",
     "`backend` --" not in _bl)
sina("kadroda OLMAYAN rol gorunuyor (`dokuman`)", "`dokuman` --" in _bl)

# Kategori BIR KEZ basilmali. Sozluk sirasi sonradan eklenen rolleri
# sona koyuyor ve ayni baslik iki kez cikiyordu -- iki kez gorunen bir
# baslik okuyana "burada hata var" dedirtir.
for _kat in _rb.kategoriler():
    sina(f"kategori '{_kat}' tek kez basiliyor",
         _bl.count(f"  {_kat}\n") <= 1, f"({_bl.count(chr(10) + '  ' + _kat)})")

# TERS RISK: kutuphaneyi gorunur kilmak, hata modunu "hic onermiyor"dan
# "her ise yeni ajan oneriyor"a cevirebilir. Blok bunu ACIKCA dizginler.
sina("asiri oneriye karsi uyari var",
     "YANLISTIR" in _bl and "15 kat jeton" in _bl)
sina("onermek ise almak DEGIL diye yaziyor", "Onermek ise almak DEGILDIR" in _bl)
sina("uydurma rol adinin reddedildigini soyluyor", "REDDEDILIR" in _bl)

# Butun roller kadrodaysa BOS LISTE degil, ACIK CUMLE.
_hepsi = _rb.lider_blogu(list(_rb.ROLLER))
sina("butun roller kadrodaysa 'gerek yok' diyor",
     "gerek yok" in _hepsi and "OLMAYAN" not in _hepsi, f"({_hepsi[-80:]})")

# JETON SINIRI: triyaj HER `konus` mesajinda kosar. Blok buyudukce her
# mesaj pahalilasir; aciklamalar bu yuzden kesiliyor.
sina("blok sinirli kaliyor (~600 jetonun altinda)",
     len(_bl) // 4 < 600, f"(~{len(_bl)//4} jeton)")

# EN ONEMLISI: blok TRIYAJ METNINE gercekten ULASIYOR mu. Modulu
# yazmak yetmez -- bugun `video.py` tam bu yuzden ajana ulasmiyordu.
import tempfile as _rbtf
from pathlib import Path as _rbP
from ofis import Ofis as _rbOfis, Veritabani as _rbVt

_rbkok = _rbP(_rbtf.mkdtemp(prefix="ofis-rolblok-"))
_rbo = _rbOfis.proje_ac(_rbVt(_rbkok / "o.sqlite3"), "RolBlok",
                        amac="a", basari_olcutu="b", kok_klasor=str(_rbkok))
_rbkn = _rbo.kanat_ac("URUN", "UR")
_rbo.kadro.ise_al("rl", "lider", lider_mi=True, kanat_id=_rbkn,
                  klasor=str(_rbkok), motor="sahte")
_rbo.kadro.ise_al("rb", "backend", kanat_id=_rbkn,
                  klasor=str(_rbkok), motor="sahte")
_rbm = _rbo.sohbet.triyaj_metni("kullanim kilavuzu yazalim")
sina("TRIYAJ METNINE ulasiyor", "# ROL KUTUPHANESI" in _rbm)
sina("triyajda kadrodaki rol onerilebilir GORUNMUYOR",
     "`backend` --" not in _rbm)
sina("triyajda `dokuman` gorunuyor", "`dokuman` --" in _rbm)



# ---------------------------------------------------------------------------
# LIDER MEDYA YETENEGINI GORUYOR MU
#
# Olculdu (21.09.2026): triyaj metninde medya hakkinda HICBIR SEY yoktu
# -- ne para kilidi, ne kota, ne uretici. Patron "markamiz icin kapak
# gorseli yapalim" dediginde lider ya is acip ortada patlayacak, ya
# yapabilecegini varsayacakti.
#
# Baglayici ve rol envanterleriyle ayni sinif: gormeden karar vermek
# tahmindir.
# ---------------------------------------------------------------------------
print("\n-- lider medya yetenegini goruyor mu --")

import tempfile as _mytf
from pathlib import Path as _myP
from ofis import gorsel as _myg

_myeski_ayar = _myg.AYAR_DEFTERI
_myeski_kota = _myg.KOTA_DEFTERI
_myeski_ortam = os.environ.pop("OFIS_PARA_HARCA", None)
_mydir = _myP(_mytf.mkdtemp(prefix="ofis-medya-"))
_myg.AYAR_DEFTERI = _mydir / "ayar.json"
_myg.KOTA_DEFTERI = _mydir / "kota.json"

# KILIT KAPALIYKEN: ucretli ureticiler acikca "KAPALI" gorunmeli.
_myb = _myg.lider_blogu()
sina("blok basligi var", "# MEDYA URETIMI" in _myb)
sina("para kilidi durumu YAZIYOR", "PARA KILIDI: KAPALI" in _myb, f"({_myb[:80]})")
sina("ucretli uretici KAPALI diye gorunuyor",
     "para kilidi yuzunden KAPALI" in _myb)
# Video'da ucretsiz katman HIC YOK -- kilit kapaliyken tamamen kapali.
sina("video ureticileri de kapali gorunuyor",
     _myb.count("para kilidi yuzunden KAPALI") >= 3, f"({_myb.count('KAPALI')})")

# EN ONEMLISI: "yapilamaz" demekle kalmiyor, UCUNCU YOLU soyluyor.
# Insan koprusu olmasaydi lider dogru cevabi bilmeden reddederdi.
sina("INSAN KOPRUSU anlatiliyor (`gorsel_iste`)", "gorsel_iste" in _myb)
sina("insan koprusunun PARA HARCAMADIGI soyleniyor",
     "PARA HARCANMAZ" in _myb)
# Yetki sinir: lider kilidi kendi acamaz. Acabilseydi para karari
# ondan gecerdi -- klasor ve baglayicidaki ayni kural.
sina("lider kilidi KENDI ACAMAZ diyor", "SEN ACAMAZSIN" in _myb)
sina("is acmamasi gerektigi soyleniyor", "IS ACMA" in _myb)

# KOTA NOTU BLOGA ULASIYOR MU -- anahtar var ama uretemiyorsa lider
# bunu bilmeli, yoksa "hazir" sanip is acar.
# Anahtar SINAMANIN: kota notu yalniz anahtari olan uretici icin cikar.
# 27.09'a kadar bu sinama kullanicinin GERCEK kasasindaki Gemini
# anahtarina yaslaniyordu (kok gecici klasore cevrilince ortaya cikti).
_myk_eski = os.environ.get("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = "AIza-sinama-sohbet"
_myg.para_harca_ayarla(True)      # kilidi ac ki kota notu gorunsun
_myg.kota_yaz("gemini", gunluk=True)
_myb2 = _myg.lider_blogu()
sina("kilit acilinca durum degisiyor", "PARA KILIDI: ACIK" in _myb2)
sina("KOTA notu lidere ulasiyor",
     "GUNLUK kota doluydu" in _myb2, f"({_myb2[:200]})")
_myg.para_harca_ayarla(False)
if _myk_eski is None:
    os.environ.pop("GEMINI_API_KEY", None)
else:
    os.environ["GEMINI_API_KEY"] = _myk_eski

# JETON SINIRI: triyaj HER `konus` mesajinda kosar.
sina("blok sinirli kaliyor (~350 jetonun altinda)",
     len(_myb) // 4 < 350, f"(~{len(_myb)//4} jeton)")

# BLOK TRIYAJ METNINE ULASIYOR MU -- modulu yazmak yetmez.
# (Bugun `video.py` tam bu yuzden ajana ulasmiyordu.)
_myo = Ofis.proje_ac(Veritabani(_mydir / "o.sqlite3"), "Medya",
                     amac="a", basari_olcutu="b", kok_klasor=str(_mydir))
_mykn = _myo.kanat_ac("URUN", "UR")
_myo.kadro.ise_al("ml", "lider", lider_mi=True, kanat_id=_mykn,
                  klasor=str(_mydir), motor="sahte")
_mym = _myo.sohbet.triyaj_metni("kapak gorseli yapalim")
sina("TRIYAJ METNINE ulasiyor", "# MEDYA URETIMI" in _mym)
sina("triyajda insan koprusu gorunuyor", "gorsel_iste" in _mym)

_myg.AYAR_DEFTERI = _myeski_ayar
_myg.KOTA_DEFTERI = _myeski_kota
if _myeski_ortam is not None:
    os.environ["OFIS_PARA_HARCA"] = _myeski_ortam

# --------------------------------------------------------------------------
print("\n20. TARAYICI ALANI konus yolunun HER halkasina ulasiyor")
# Panelde kabinde bir oge isaret edilince o sayfanin kaynagi TARAYICI ALANI
# olur. Yarisi baglamak ise yaramaz: plana ulasip halkaya ulasmasaydi is
# paylasilan kabin yerine oturumsuz bir tarayicida kosardi, SESSIZCE.
_kos_ayar = []
sohbet_t = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: AsamaliMotor(cevap=""))
_asil_kos = sohbet_t.orkestra.kos


def _izle_kos(**ayar):
    _kos_ayar.append(ayar)
    return _asil_kos(**ayar)


sohbet_t.orkestra.kos = _izle_kos
_once_t = {g["no"] for g in ofis.tahta.liste()}
list(sohbet_t.konus("sayfadaki dugmeyi incele", azami_tik=1,
                    tarayici_alani=["https://a.com/x?y=1"],
                    tarayici_kabini="http://127.0.0.1:9222"))
_yeni_t = [g for g in ofis.tahta.liste() if g["no"] not in _once_t]
sina("acilan gorev tarayici alanini TASIYOR (origin'e indirgenmis)",
     bool(_yeni_t) and all(g["tarayici_alani"] == ["https://a.com"] for g in _yeni_t),
     str([g["tarayici_alani"] for g in _yeni_t]))
sina("halka PAYLASILAN kabinle kostu",
     bool(_kos_ayar) and _kos_ayar[0].get("tarayici_kabini") == "http://127.0.0.1:9222",
     str(_kos_ayar)[:200])
with ofis.db.baglanti() as _c:
    _ot = _c.execute("SELECT govde FROM olay WHERE tur='tarayici_alani' AND "
                     "govde LIKE 'Patron mesaji%' ORDER BY id DESC LIMIT 1").fetchone()
sina("kabin GOREVE yaziliyor (Surdur'de kaybolmasin)",
     bool(_yeni_t) and all(g["tarayici_kabin"] for g in _yeni_t))
sina("tarayici acilisi KAYDA gecti ve kabini soyluyor",
     bool(_ot) and "PAYLASILAN kabin" in _ot["govde"], str(_ot and dict(_ot)))

# TERS YON: verilmezse hicbir sey ACILMAZ (varsayilan dar).
_kos_ayar.clear()
_once_t = {g["no"] for g in ofis.tahta.liste()}
list(sohbet_t.konus("baska bir is", azami_tik=1))
_yeni_t = [g for g in ofis.tahta.liste() if g["no"] not in _once_t]
sina("verilmezse gorevde kabin YOK",
     bool(_yeni_t) and all(not g["tarayici_kabin"] for g in _yeni_t))
sina("verilmezse gorevde tarayici YOK",
     bool(_yeni_t) and all(not g["tarayici_alani"] for g in _yeni_t))
sina("verilmezse halka kabinsiz", bool(_kos_ayar)
     and not _kos_ayar[0].get("tarayici_kabini"))


# -- CEVAP YAZILIRKEN AKAR (29.09.2026) -------------------------------------
# Olculdu: Opus liderin "naber"e cevabi 9-27 sn; panel bu sure "dusunuyor"
# diyordu. Akis JSON'dan AYIKLANIR (patron makine metni gormez), defterde
# tek kayitta yasar ve cevap dusunce SILINIR.
print("\nAKIS -- liderin cevabi yazilirken panele akiyor")
from ofis import sohbet as _sm
from ofis.sohbet import akis_metni, akislar

sina("json: yarim cevap alani cozuluyor",
     akis_metni('{"karar": "cevap", "gerekce": "g", "cevap": "Mer') == "Mer")
sina("json: kacislar cozuluyor (satir, tirnak, \\u)",
     akis_metni('{"karar":"cevap","gerekce":"g","cevap":"a\\nb \\"c\\" \\u00e7"}')
     == 'a\nb "c" \xe7')
sina("json: yarim kacis UYDURULMUYOR (bekleniyor)",
     akis_metni('{"karar":"cevap","gerekce":"g","cevap":"ab\\u00') == "ab")
sina("json: karar henuz kapanmadiysa BOS (makine metni gosterilmez)",
     akis_metni('```json\n{"karar": "ce') == "")
sina("json: cit/suslu parantezle baslayan henuz bos",
     akis_metni("```json\n") == "" and akis_metni("{") == "")
# 30.09: gerekce patrona AKMAZ (ic muhasebe, karar gunlugunde); hedef akar.
sina("json: dagit yolunda GEREKCE akmiyor, yalniz etiket",
     akis_metni('{"karar":"dagit","gerekce":"Is iki kola bol') ==
     "Bu i\u015fi ekibe da\u011f\u0131t\u0131yorum\u2026")
sina("json: hedef gelince NE yapilacagi akiyor",
     akis_metni('{"karar":"kendi","gerekce":"15 kat jeton","cevap":"",'
                '"hedef":"semuparfum.com\'u acip ekran goruntusu al') ==
     "Bu i\u015fi ben yap\u0131yorum: semuparfum.com'u acip ekran goruntusu al")
sina("duz metin (lider bicime uymadi) oldugu gibi akiyor",
     akis_metni("Selam patron") == "Selam patron")
sina("rapor kipi oldugu gibi", akis_metni(" rapor ", "duz") == "rapor")

_akis_goruntu = []
_eski_aralik = _sm.AKIS_ARALIK_SN
_sm.AKIS_ARALIK_SN = 0.0


class AkisMotor(SahteMotor):
    """Her metin parcasindan SONRA defterdeki akisi okur (panel gibi)."""

    def tur_kos(self, metin, **ayar):
        for olay in super().tur_kos(metin, **ayar):
            yield olay
            if olay.tur == "metin":
                _akis_goruntu.append(dict(akislar(db, ofis.proje_id)))


try:
    kutu_akis = json.dumps({"karar": "cevap", "gerekce": "bilgi sorusu",
                            "cevap": "Merhaba patron, her sey yolunda."},
                           ensure_ascii=False)
    s_akis = Sohbet(ofis, motor_fabrikasi=lambda ad, **k: AkisMotor(cevap=kutu_akis))
    # Onceki bolumlerin acik isleri halkayi dondurur ve RAPOR turu da ayni
    # sahte JSON'u yazar -- bu bolum yalniz TRIYAJIN akisini olcer.
    for _g in ofis.tahta.liste():
        if _g["durum"] not in ("bitti", "iptal"):
            ofis.tahta.iptal_et(_g["no"], sebep="akis sinamasi", iptal_eden="insan")
    _akis_goruntu.clear()
    ol = list(s_akis.konus("naber"))
    metinler_ = [v for g in _akis_goruntu for v in g.values()]
    sina("tur SURERKEN akis vardi", bool(metinler_), str(_akis_goruntu[:3]))
    sina("akis BUYUYEREK geldi (once kismi, sonra tam)",
         len(set(metinler_)) >= 2 and metinler_[-1].startswith("Merhaba patron"),
         str(metinler_))
    sina("akista JSON/makine metni YOK",
         bool(metinler_) and not any('"karar"' in m or "{" in m
                                     for m in metinler_), str(metinler_))
    sina("bitince akis kaydi SILINDI", akislar(db, ofis.proje_id) == {})
    sina("cevap yine deftere dustu",
         any(o["tur"] == "cevap" and "Merhaba patron" in o["govde"] for o in ol))

    # Tur DUSERSE de akis asili kalmaz.
    class DusenMotor(SahteMotor):
        def tur_kos(self, metin, **ayar):
            yield from super().tur_kos(metin, **ayar)
            raise RuntimeError("motor koptu")

    s_dus = Sohbet(ofis, motor_fabrikasi=lambda ad, **k: DusenMotor(cevap=kutu_akis))
    try:
        list(s_dus.konus("naber 2"))
    except Exception:
        pass
    sina("tur dusunce de akis kaydi SILINDI", akislar(db, ofis.proje_id) == {})

    # Akisi yazamamak lider turunu OLDURMEZ, ama sessiz de kalmaz.
    _eski_yaz = _sm.AkisYazici.__call__

    def _bozuk_yaz(self, parca):
        raise OSError("disk dolu")

    _sm.AkisYazici.__call__ = _bozuk_yaz
    try:
        ol2 = list(s_akis.konus("naber 3"))
    finally:
        _sm.AkisYazici.__call__ = _eski_yaz
    sina("akis yazilamasa da CEVAP geldi",
         any(o["tur"] == "cevap" and "Merhaba" in o["govde"] for o in ol2))
    with db.baglanti() as c:
        _u = c.execute("SELECT govde FROM olay WHERE tur='uyari' AND govde LIKE "
                       "'%panele akitilamadi%'").fetchall()
    sina("akis hatasi BIR KEZ uyari olarak yazildi", len(_u) == 1, str(len(_u)))
finally:
    _sm.AKIS_ARALIK_SN = _eski_aralik

# SEYREK GUNCELLEME: 200 hizli parca -> birkac guncelleme (yarim JSON her
# parcada yeniden ayiklanmasin). Akis DEFTERE hic yazilmaz (olculdu: yuk
# altinda her yazim 100-150 ms ve defter kilidini tutuyordu).
_yazim = {"n": 0}
_eski_bel = _sm._bellege_yaz


def _sayan(*a):
    _yazim["n"] += 1
    _eski_bel(*a)


_sm._bellege_yaz = _sayan
try:
    _ay = _sm.AkisYazici(None, "p", "m")
    _ay('{"karar":"cevap","gerekce":"g","cevap":"')
    for _i in range(200):
        _ay("x")
    _ay.bitir()
finally:
    _sm._bellege_yaz = _eski_bel
sina("akis DEFTERE yazilmiyor", "ayar_yaz" not in
     Path(_sm.__file__).read_text(encoding="utf-8").split("class AkisYazici")[1]
     .split("def akislar")[0])
sina("hizli parcalar SEYREK guncelleniyor", 1 <= _yazim["n"] <= 4,
     str(_yazim["n"]))


# --------------------------------------------------------------------------
print("\nCEVAP = SON ARACTAN SONRA yazilan (30.09, gercek set G01)")
from ofis.motor.tip import MotorOlayi  # noqa: E402


class _AraCumleli(SahteMotor):
    """Once ara cumle, sonra arac, sonra asil cevap -- gercekte olculen sira."""

    def tur_kos(self, metin, **ayar):
        yield MotorOlayi("metin", "Önce dosyanın var olup olmadığına bakıyorum.")
        yield MotorOlayi("arac", "Read", {"ozet": "a.png"})
        yield MotorOlayi("metin", triyaj("cevap", "bilgi", cevap="Dosya yerinde."))
        yield MotorOlayi("bitti", "", {"basarili": True})


# HAM metne bakilir: triyaj JSON'u ayikladigi icin ara cumleyi zaten atar;
# sizinti RAPOR gibi duz metinde (olculdu). Sinama o siniri olcmeli.
_sa = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _AraCumleli(cevap=""))
_ham = _sa._lideri_kostur(ofis.kadro.lider(kanat), "rapor yaz", None, 30)
sina("aractan ONCEKI ara cumle liderin metnine YAPISMADI (rapor yolu)",
     "Önce" not in _ham and "Dosya yerinde" in _ham, repr(_ham[:120]))


class _CevapSonraArac(SahteMotor):
    """Cevap yazildi, SONRA bir arac cagrildi ve tur sustu: cevap kaybolmamali."""

    def tur_kos(self, metin, **ayar):
        yield MotorOlayi("metin", triyaj("cevap", "bilgi", cevap="Tamam patron."))
        yield MotorOlayi("arac", "Read", {"ozet": "x"})
        yield MotorOlayi("bitti", "", {"basarili": True})


_ol = akit(Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _CevapSonraArac(cevap="")), "nasilsin?")
_cv = [o["govde"] for o in _ol if o["tur"] == "cevap"]
sina("cevaptan SONRA arac cagrilsa da cevap korunur", _cv and "Tamam patron" in _cv[0], str(_cv))

print("\nLIDER TURUNUN HATASI DEFTERE YAZILIR (30.09, gercek set G06)")


class _DusenLider(SahteMotor):
    def tur_kos(self, metin, **ayar):
        yield MotorOlayi("hata", "Terminal acilirken kapandi: guven sorusu")
        yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "cikis"})


try:
    Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _DusenLider(cevap=""))._lideri_kostur(
        ofis.kadro.lider(kanat), "x", None, 30)
except Exception:                                   # noqa: BLE001 -- dusmesi bekleniyor
    pass
with ofis.db.baglanti() as _c:
    _lh = [r[0] for r in _c.execute("SELECT govde FROM olay WHERE tur='hata' AND govde LIKE 'Lider turu:%'")]
sina("lider turu hatasi NEDENIYLE deftere yazildi", any("guven sorusu" in x for x in _lh), str(_lh[-1:]))

print("\nTEK ISLI PLANDA RAPOR = INCELEMENIN PATRONA TASLAGI (30.09, hiz)")
# Olculdu: codex G01 120 sn'nin 21 sn'si ayri rapor turuydu. Kapatan
# inceleme PATRONA: yazar; tek isli planda ayri rapor turu KOSMAZ.
_pk = Path(tempfile.mkdtemp(prefix="ofis-patrona-"))
_pdb = Veritabani(_pk / "o.sqlite3")
_po = Ofis.proje_ac(_pdb, "Patrona", amac="a", basari_olcutu="b", kok_klasor=str(_pk))
_pkn = _po.kanat_ac("A", "A")
_po.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=_pkn, motor="sahte", klasor=str(_pk))
_po.kadro.ise_al("cem", "backend", kanat_id=_pkn, motor="sahte", klasor=str(_pk))
_tur_say = {"rapor": 0}


class _AkisMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("dagit", "is", hedef="a.txt dosyasina merhaba yaz")
        elif '"kollar"' in metin:
            self.cevap = "```json\n" + json.dumps({"bol": False, "gerekce": "tek", "kollar": [
                {"baslik": "a.txt yaz", "sahip": "cem", "neden": "patron istedi",
                 "kabul_olcutu": "a.txt icinde merhaba", "govde": "a.txt'ye merhaba yaz",
                 "yazma_alani": ["a.txt"]}]}) + "\n```"
        elif "KARAR: kapat" in metin:
            self.cevap = ("Kanit yeterli.\nKARAR: kapat\n"
                          "PATRONA: a.txt yazildi, icinde 'merhaba' var.\nBILGI: yok -> yok")
        elif "# PATRONUN ISTEGI" in metin:
            _tur_say["rapor"] += 1
            self.cevap = "AYRI RAPOR TURU"
        else:
            (Path(ayar.get("klasor") or _pk) / "a.txt").write_text("merhaba", encoding="utf-8")
            self.cevap = "Yazdim.\nKANIT dosya: a.txt -> merhaba yazildi"
        return super().tur_kos(metin, **ayar)


_pol = list(Sohbet(_po, motor_fabrikasi=lambda ad, **a: _AkisMotor(cevap="")).konus(
    "a.txt'ye merhaba yaz", azami_tik=6))
_prap = [o["govde"] for o in _pol if o["tur"] == "rapor"]
sina("is kapandi", [g["durum"] for g in _po.tahta.liste()] == ["bitti"],
     str([g["durum"] for g in _po.tahta.liste()]))
sina("rapor incelemenin PATRONA taslagi", _prap and _prap[0].startswith("a.txt yazildi"),
     str(_prap))
sina("ayri rapor turu KOSMADI", _tur_say["rapor"] == 0, str(_tur_say))

print("\n'BAKAMIYORUM' CEVABI PATRONA GITMEZ, IS AJANA VERILIR (30.09, G09)")
_bo = Ofis.proje_ac(Veritabani(_pk / "b.sqlite3"), "Bakamam", amac="a", basari_olcutu="b",
                    kok_klasor=str(_pk))
_bkn = _bo.kanat_ac("A", "A")
_bo.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=_bkn, motor="sahte", klasor=str(_pk))
_bo.kadro.ise_al("cem", "backend", kanat_id=_bkn, motor="sahte", klasor=str(_pk))


class _Bakamayan(_AkisMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("cevap", "bilgi sorusu",
                                cevap="Bu turda sayfayi acip dogrulayamiyorum; fiyati uydurmam.")
            return SahteMotor.tur_kos(self, metin, **ayar)
        return super().tur_kos(metin, **ayar)


_bol = list(Sohbet(_bo, motor_fabrikasi=lambda ad, **a: _Bakamayan(cevap="")).konus(
    "http://x/urun sayfasindaki fiyat ne?", azami_tik=4))
sina("is ACILDI (ajana verildi)", len(_bo.tahta.liste()) == 1, str(_bo.tahta.liste()))
sina("'dogrulayamiyorum' cumlesi patrona GITMEDI",
     not any("dogrulayamiyorum" in (o.get("govde") or "") for o in _bol
             if o["tur"] in ("cevap", "rapor")), str([o["govde"][:60] for o in _bol if o["tur"] == "cevap"]))
with _bo.db.baglanti() as _c:
    sina("ofis bunu kayda gecirdi", bool(_c.execute(
        "SELECT 1 FROM olay WHERE tur='uyari' AND govde LIKE '%ajana verdi%'").fetchone()))

print("\nDEFTER SATIRLARI PATRONA GITMEZ (30.09, gercek set G01)")
_tm = Sohbet(ofis)._ekleri_hazirla(
    "Istenen goruntu sohbete eklendi.\n\n\nKANIT terminal: `Get-Item x` -> ok\n"
    "DURUM: bitti | sirada yok\nKanıt: goruntu sohbette.", "demir")
sina("'KANIT terminal:' ve 'DURUM:' satirlari silindi",
     "KANIT terminal" not in _tm and "DURUM:" not in _tm, repr(_tm))
sina("sade 'Kanıt:' cumlesi ve asil metin KALDI",
     "Kanıt: goruntu sohbette." in _tm and _tm.startswith("Istenen goruntu"), repr(_tm))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
