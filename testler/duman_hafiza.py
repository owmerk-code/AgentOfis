# -*- coding: utf-8 -*-
"""Hafiza duman testi: bilgi kapisi, `[[bag]]`, kurallar, kunye.

Bu dosyanin sebebi bir OLCUM (24.09.2026): gercek ofiste OLGU SAYISI
SIFIRDI. `olgu_yaz`i uretimde cagiran tek bir yol yoktu; hafiza isabeti
%100 olculmustu ama sentetik veriyle. Yani olcum dogruydu ve yine de
gercek kullanimda hicbir sey ifade etmiyordu.

Sinanan dort sey:

1. BILGI KAPISI -- insanin yazdigini ajan sessizce devremez, ayni icerik
   yeni surum acmaz, konu adi normallesir.
2. BAG -- secim `[[konu]]` bagini BIR ADIM izler; gorevle ortak kelimesi
   olmayan gerekli olgu artik elenmiyor (19.09'da olculen durust kayip).
3. KURAL -- yalniz insandan, gerekceli, kaldirilabilir, HER brifinge
   kosulsuz; tekrarlayan ders ADAY olarak gosterilir.
4. KUNYE LIDERE ULASIYOR -- lider triyajda, planlamada ve incelemede
   "kapsam disi"yi hic gormuyordu.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import bellek as B
from ofis.bellek import BellekHatasi

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


def reddedildi(islev, *a, **k) -> bool:
    try:
        islev(*a, **k)
    except BellekHatasi:
        return True
    return False


print("== hafiza duman testi ==")

kok = Path(tempfile.mkdtemp(prefix="ofis-hafiza-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Hafiza", amac="Hafizayi sinamak",
                     basari_olcutu="Sayilar tutar",
                     kapsam_disi="Odeme entegrasyonu YAPILMAZ",
                     kisitlar="Yeni bagimlilik eklenmez",
                     kok_klasor=str(kok))
kanat = ofis.kanat_ac("ANA", "AN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kanat, motor="sahte",
                  klasor=str(kok))
bel = ofis.bellek

# --------------------------------------------------------------------------
print("\n1. BILGI KAPISI")
r = bel.bilgi_ekle("Iade suresi", "14 gun", yazan="insan")
sina("insan bilgi yaziyor", r["durum"] == "yeni" and r["kaynak"] == "insan")
# Korumali cagri: kapi bozulursa istisna gelir ve CAKAN bir test geri kalan
# sinamalari hic kosturmaz -- kaldigini soylemesi gerekir.
try:
    r = bel.bilgi_ekle("iade süresi", "14 gun", yazan="cinar")
except BellekHatasi as exc:
    r = {"durum": f"RET: {exc}"}
sina("ayni icerik yeni surum ACMIYOR (konu adi normallesti)",
     r["durum"] == "ayni" and len(bel.konu_gecmisi("Iade suresi")) == 1, str(r))
sina("insanin yazdigini ajan DEVIREMIYOR",
     reddedildi(bel.bilgi_ekle, "IADE SURESI", "30 gun", yazan="cinar"))
sina("  bilgi degismedi",
     bel.gecerli_olgular(["Iade suresi"])[0]["icerik"] == "14 gun")
r = bel.bilgi_ekle("Kargo firmasi", "Aras", yazan="cinar", gorev_no=7)
sina("ajan yeni bilgi yaziyor, kaynagi gorevle",
     r["kaynak"] == "ajan:cinar #7")
r = bel.bilgi_ekle("kargo firmasi", "Yurtici", yazan="cinar")
sina("ajan AJANIN yazdigini devirebiliyor (ayni konu, tek gecerli)",
     r["durum"] == "guncellendi"
     and [o["icerik"] for o in bel.gecerli_olgular(["Kargo firmasi"])]
     == ["Yurtici"])
r = bel.bilgi_ekle("Kargo firmasi", "MNG", yazan="insan")
sina("insan ajanin yazdigini devirebiliyor", r["durum"] == "guncellendi")
sina("gecmis SILINMEDI (3 surum)", len(bel.konu_gecmisi("Kargo firmasi")) == 3)
sina("bos konu reddediliyor", reddedildi(bel.bilgi_ekle, " ", "x", yazan="insan"))
sina("uzun konu reddediliyor",
     reddedildi(bel.bilgi_ekle, "k" * 90, "x", yazan="insan"))
sina("uzun bilgi reddediliyor",
     reddedildi(bel.bilgi_ekle, "k", "x" * 700, yazan="insan"))
sina("yazansiz bilgi reddediliyor",
     reddedildi(bel.bilgi_ekle, "k", "x", yazan=""))

# --------------------------------------------------------------------------
print("\n2. BAG -- secim bagi BIR ADIM izliyor")
sina("baglar ayristiriliyor, tekrarsiz",
     B.baglar("a [[X y]] b [[x Y]] c [[Z]]") == ["X y", "Z"])

# Secim esigini asmak icin gurultu. Gorev metni "siparis ekrani".
for i in range(B.OLGU_SECIM_ESIGI + 5):
    bel.olgu_yaz(f"arsiv {i}", f"kayit-{i:04d}", kaynak="arsiv")
metin = "Siparis ekraninda kargo bedeli dogru gosterilsin"
bel.bilgi_ekle("kargo bedeli", "500 TL uzeri ucretsiz", yazan="insan")
bel.bilgi_ekle("lojistik anlasmasi", "Yillik sozlesme: teslimat iki is gunu",
               yazan="insan")
s = bel.ilgili_olgular(metin)
sina("BAGSIZ: gorevle ortak kelimesi olmayan olgu ELENIYOR (olculen kayip)",
     s["secim_yapildi"]
     and not any(o["konu"] == "lojistik anlasmasi" for o in s["secilen"]))
bel.bilgi_ekle("kargo bedeli",
               "500 TL uzeri ucretsiz; sure icin [[lojistik anlasmasi]]",
               yazan="insan")
s = bel.ilgili_olgular(metin)
_l = [o for o in s["secilen"] if o["konu"] == "lojistik anlasmasi"]
sina("BAGLI: ayni olgu artik brifinge geliyor", bool(_l), str(s)[:200])
sina("  bagla geldigi ISARETLI", bool(_l) and _l[0].get("bag") == "kargo bedeli")
sina("  bag_ile sayisi dogru", s.get("bag_ile") == 1)
# Tek adim: lojistik -> [[depo adresi]] zinciri izlenmez.
bel.bilgi_ekle("lojistik anlasmasi",
               "Yillik sozlesme: teslimat iki is gunu. Bkz [[depo adresi]]",
               yazan="insan")
bel.bilgi_ekle("depo adresi", "Gebze OSB", yazan="insan")
s = bel.ilgili_olgular(metin)
sina("zincir IZLENMIYOR (tek adim)",
     not any(o["konu"] == "depo adresi" for o in s["secilen"]))
# Bag siniri.
_hedefler = [f"hedef {i}" for i in range(B.AZAMI_BAG_OLGU + 4)]
for h in _hedefler:
    bel.olgu_yaz(h, f"deger-{h}", kaynak="arsiv")
bel.bilgi_ekle("kargo takibi", "Takip: " + " ".join(f"[[{h}]]" for h in _hedefler),
               yazan="insan")
s = bel.ilgili_olgular(metin + " kargo takibi")
sina("bag genislemesi SINIRLI",
     s.get("bag_ile", 0) <= B.AZAMI_BAG_OLGU, str(s.get("bag_ile")))
# Brifing bagla geleni SOYLUYOR.
g = ofis.tahta.gorev_ac("Siparis ekrani", neden="n", ana_hedef="h",
                        kabul_olcutu="k", govde=metin, kanat_id=kanat)
k2 = ofis.brifing.k2_kunye(g["no"])
sina("brifing bagla geleni isaretliyor", "bagla geldi: [[kargo bedeli]]" in k2)

# --------------------------------------------------------------------------
print("\n3. KURAL -- yalniz insandan, her brifinge kosulsuz")
sina("kural yokken K2'de kural blogu YOK", "OFIS KURALLARI" not in k2)
sina("ajan/lider kural KOYAMIYOR",
     reddedildi(bel.kural_ekle, "X", "g", veren="demir"))
sina("gerekcesiz kural reddediliyor", reddedildi(bel.kural_ekle, "X", ""))
k = bel.kural_ekle("Musteriye asla kisisel veri gosterilmez.",
                   "KVKK -- bir kez yasandi.")
sina("insan kural koyuyor", bool(k["id"]))
sina("ayni kural ikinci kez eklenemiyor",
     reddedildi(bel.kural_ekle, "musteriye asla kisisel veri gosterilmez.",
                "g"))
sina("kural karar gunlugune GEREKCESIYLE dustu",
     any(x["karar"].startswith("Kural eklendi") and x["tur"] == "kapsam"
         and "KVKK" in x["gerekce"] for x in bel.son_kararlar(5)))
k2 = ofis.brifing.k2_kunye(g["no"])
sina("kural K2'de KOSULSUZ (gorevle ortak kelimesi olmasa da)",
     "OFIS KURALLARI" in k2 and "kisisel veri" in k2)
ko = bel.olgudan_kural("DEPO ADRESI", "Her sevkiyat buradan cikar.")
sina("bilgi kurala yukseltiliyor",
     ko["kaynak_tur"] == "olgu" and "Gebze OSB" in ko["metin"])
sina("olmayan bilgi yukseltilemiyor",
     reddedildi(bel.olgudan_kural, "yok boyle bir sey", "g"))
# Ders adayi: tekrar sayaci OLCER.
ofis.kadro.ders_yaz("cinar", "Testi bosaltma, duzelt.")
sina("tek seferlik ders ADAY DEGIL",
     not any(a["ders"] == "Testi bosaltma, duzelt." for a in bel.kural_adaylari()))
ofis.kadro.ders_yaz("cinar", "Testi bosaltma, duzelt.")
_ad = [a for a in bel.kural_adaylari() if a["ders"] == "Testi bosaltma, duzelt."]
sina("TEKRARLAYAN ders aday", bool(_ad) and _ad[0]["tekrar"] == 2)
kd = bel.dersten_kural(_ad[0]["id"], "Iki kez yasandi.")
sina("ders kurala yukseltiliyor", kd["kaynak_tur"] == "ders")
sina("yukseltilen ders artik aday DEGIL",
     not any(a["ders"] == "Testi bosaltma, duzelt." for a in bel.kural_adaylari()))
sina("kaldirma sebebi zorunlu", reddedildi(bel.kural_kaldir, k["id"], ""))
bel.kural_kaldir(k["id"], "KVKK artik ayri kontrol listesinde.")
sina("kaldirilan kural brifingden CIKTI",
     "kisisel veri" not in ofis.brifing.k2_kunye(g["no"]))
sina("  ama gecmiste DURUYOR",
     any(x["id"] == k["id"] and x["kaldirildi"] for x in bel.kurallar(hepsi=True)))
sina("kaldirilan kural ikinci kez kaldirilamaz",
     reddedildi(bel.kural_kaldir, k["id"], "tekrar"))
m = bel.kural_maliyeti()
sina("kural maliyeti olculuyor", m["adet"] == 2 and m["harf"] > 0 and not m["uyari"])

# --------------------------------------------------------------------------
print("\n4. KUNYE LIDERE ULASIYOR")
plan = ofis.orkestra.plan_metni("Siparis ekrani yapilsin", kanat)
sina("PLANLAMA kapsam disini goruyor", "Odeme entegrasyonu YAPILMAZ" in plan)
sina("  ve kurallari", "OFIS KURALLARI" in plan and "Gebze OSB" in plan)
tri = ofis.sohbet.triyaj_metni("odeme ekrani da ekleyelim mi?")
sina("TRIYAJ kapsam disini goruyor", "Odeme entegrasyonu YAPILMAZ" in tri)
inc = ofis.lider.inceleme_metni(g["no"])
sina("INCELEME kapsam disini ve kurali goruyor",
     "Odeme entegrasyonu YAPILMAZ" in inc and "OFIS KURALLARI" in inc)
sina("  ve kapsam disi isi KAPATMAMASI soyleniyor", "KAPATMA" in inc)
ofis.postane.soru_sor("cinar", "demir", "Kargo firmasi hangisi?",
                      gorev_no=g["no"])
_bek = [m for m in ofis.postane.ajana_bekleyenler()
        if m["govde"] == "Kargo firmasi hangisi?"]
sina("DANISMA kurallari goruyor",
     bool(_bek) and "OFIS KURALLARI" in ofis.danisma.soru_metni(_bek[0]))
# Bos projede kunye yazilmaz (uydurma baslik yok).
db2 = Veritabani(kok / "bos.sqlite3")
o2 = Ofis.proje_ac(db2, "Bos")
sina("bos kunye HIC yazilmiyor", o2.brifing.kunye_ozeti() == "")

# --------------------------------------------------------------------------
print("\n5. UYANIS -- baskasinin yazdigi bilgi ve kural gorunur")
son = bel.son_olay_id()
bel.bilgi_ekle("para birimi", "TL", yazan="demir")
bel.kural_ekle("Fiyatlar KDV dahil gosterilir.", "Yasal zorunluluk.")
u = [x["tur"] for x in bel.uyanis_ozeti("cinar", son)]
sina("yeni bilgi uyanista", "olgu" in u, str(u))
sina("yeni kural uyanista", "kural" in u, str(u))

# --------------------------------------------------------------------------
print("\n6. LIDER INCELEMESI BILGI CIKARIYOR -- ikinci kanal")
#
# OLCULDU: iki gercek haiku turunda isci, ZORUNLU talimata ragmen
# `bilgi_yaz`i hic cagirmadi. Hafiza yalniz iscinin iyi niyetine
# birakilamaz; lider isi kanitla okuyor ve `DERS:` gibi `BILGI:` yazar.
from ofis import Koltuk
from ofis.motor.sahte import SahteMotor

kt = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(
    senaryo="basarili", cevap="Bitti.\nKANIT dosya: rapor.md -> yazildi"))


# 4. bolumde cinar lidere soru sordu (bekliyor); temiz bir isci gerekli.
ofis.kadro.ise_al("kerem", "backend", kanat_id=kanat, motor="sahte",
                  klasor=str(kok))


def incelemeye(baslik):
    g_ = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h",
                             kabul_olcutu="k", kanat_id=kanat)
    list(kt.akit(g_["no"], "kerem"))
    return g_


g6 = incelemeye("Port raporu")
sina("sahne: is incelemede", ofis.tahta.gorev(g6["no"])["durum"] == "inceleme")
hk = ("KARAR: kapat\n"
      "BILGI: servis portu -> 8123 (ayar.txt)\n"
      "BILGI: Iade suresi -> 30 gun\n")
s6 = ofis.lider._hukmu_uygula(g6["no"], hk, "demir", "kerem")
_p = bel.gecerli_olgular(["servis portu"])
sina("KAPANAN isin bilgisi hafizaya yazildi",
     s6.get("bilgi") == ["servis portu"] and bool(_p)
     and _p[0]["icerik"] == "8123 (ayar.txt)", str(s6))
sina("  kaynagi lider + gorev", bool(_p) and _p[0]["kaynak"] == f"ajan:demir #{g6['no']}")
sina("insanin bilgisini lider de DEVIREMEDI, ret SOYLENDI",
     s6.get("bilgi_ret") == ["Iade suresi"]
     and bel.gecerli_olgular(["Iade suresi"])[0]["icerik"] == "14 gun")
g6b = incelemeye("Yarim is")
s6b = ofis.lider._hukmu_uygula(
    g6b["no"], "KARAR: geri -- rapor eksik\nBILGI: yanlis deger -> 99", "demir",
    "kerem")
sina("GERI GONDERILEN isin bilgisi YAZILMADI",
     s6b["hukum"] == "geri" and not bel.gecerli_olgular(["yanlis deger"]))
g6c = incelemeye("Cok bilgi")
s6c = ofis.lider._hukmu_uygula(
    g6c["no"], "KARAR: kapat\n" + "".join(f"BILGI: konu{i} -> d{i}\n"
                                          for i in range(9)), "demir", "kerem")
sina("bir incelemeden en fazla 5 bilgi", len(s6c.get("bilgi", [])) == 5,
     str(s6c.get("bilgi")))
sina("inceleme istemi BILGI satirini tarif ediyor",
     "BILGI: <kisa konu> -> <deger (nereden)>"
     in ofis.lider.inceleme_metni(g6c["no"]))
# OLCULDU (gercek haiku turu): isci `servis portu`, lider `Servis port
# numarasi` yazdi -- ayni olgu iki konuya bolundu. Lider hafizayi GORMELI.
bel.bilgi_ekle("depo kapasitesi", "500 palet (depo.csv)", yazan="kerem",
               gorev_no=g6c["no"])
_im = ofis.lider.inceleme_metni(g6c["no"])
sina("inceleme bu iste ZATEN yazilan bilgiyi gosteriyor",
     "Bu iste ZATEN yazilanlar" in _im and "depo kapasitesi: 500 palet" in _im)
# Hafiza 40'tan buyuk (arsiv gurultusu): ILGILI konu adi yine listede mi?
_imp = ofis.lider.inceleme_metni(g6["no"])
_satir = [x for x in _imp.splitlines() if x.startswith("Hafizadaki konu adlari:")]
sina("  hafiza buyukken ILGILI konu adi listede (ayni adi kullansin diye)",
     bool(_satir) and "servis portu" in _satir[0]
     and "daha)" in _satir[0], (_satir or [""])[0][:160])

shutil.rmtree(kok, ignore_errors=True)
print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
