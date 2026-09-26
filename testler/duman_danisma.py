# -*- coding: utf-8 -*-
"""Danisma duman testi: ajana sorulan soru TESLIM EDILIYOR mu.

Kapatilan sessiz hata: `soru_sor` aracinin varsayilan alicisi "lider"di
ve lider bir AJANDIR. Lidere sorulan soru kimseye ulasmiyor, insanin
kuyruguna dusup orada duruyordu -- ofis, liderin cevaplamasi gereken
seyi sessizce insana havale ediyordu. Hata vermiyordu.

Sinananlar:

* Ajana sorulan soru gercekten CEVAPLANIYOR mu?
* Danisilan YAZABILIYOR mu? Yazamamali -- danisma bilgi alisverisidir;
  yazsaydi ayni anda iki ajan yaziyor olurdu (Yasa 1) ve o yazma
  hicbir kilidin altinda olmazdi.
* Danisilanin ARAC KUTUSU var mi? Olmamali -- A->B->C->A halkasi
  sayacla degil YAPIYLA kesilir.
* Cevap alinamazsa soru OLUYOR mu? Olmemeli, insana YUKSELMELI.
* Olmayan bir ajana soru sorulabiliyor mu? Sorulmamali -- yanlis
  yazilmis bir ad, sessiz bir olum sebebidir.
* Insanin kuyrugu ile ajanin kuyrugu AYRI mi?

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.danisma import Danisma
from ofis.postane import PostaneHatasi
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


print("== danisma duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-danisma-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Danisma Projesi", amac="Ajanlar birbirine dansin",
                     basari_olcutu="Soru sessizce olmesin",
                     kisitlar="Mevcut yigin")
kanat = ofis.kanat_ac("URUN", "UR")
for ad, meslek, lider_mi in (("demir", "lider", True),
                             ("cinar", "backend", False),
                             ("bilge", "arastirma", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi,
                      tur="eller", motor="sahte", klasor=str(kok / ad))
    (kok / ad).mkdir(parents=True, exist_ok=True)

ofis.bellek.olgu_yaz("bildirim kanali", "e-posta, harici servis yok",
                     kaynak="insan")

g = ofis.tahta.gorev_ac(
    "Bildirim akisi", neden="Kullanici haber alamiyor",
    ana_hedef="Bildirim gitsin", kabul_olcutu="Test kaydinda ulassin",
    govde="Akisi kur", kanat_id=kanat, yazma_alani=["akis/"])
ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])

kutu = {"cevap": "", "ayarlar": [], "istekler": []}


class IzleyenMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        kutu["istekler"].append(metin)
        kutu["ayarlar"].append(dict(ayar))
        return super().tur_kos(metin, **ayar)


def fabrika(ad, **ayar):
    return IzleyenMotor(cevap=kutu["cevap"])


danisma = Danisma(ofis, motor_fabrikasi=fabrika)

# --------------------------------------------------------------------------
print("1. ALICI DOGRULANIYOR -- olmayan ada soru sorulamaz")

try:
    ofis.postane.soru_sor("cinar", "olmayan_ajan", "Bir sorum var")
    sina("olmayan aliciya soru REDDEDILDI", False, "(kabul edildi)")
except PostaneHatasi as exc:
    sina("olmayan aliciya soru REDDEDILDI", True)
    sina("ret, gecerli adlari SOYLUYOR", "demir" in str(exc), f"({exc})")

sina("'insan' hep gecerli alici",
     bool(ofis.postane.soru_sor("cinar", "insan", "Insana sorum",
                                gorev_no=g["no"])))

# --------------------------------------------------------------------------
print("\n2. KUYRUKLAR AYRI")

m = ofis.postane.soru_sor(
    "cinar", "demir",
    "Bildirim harici servisten mi kendi akisimizdan mi gitsin?",
    gorev_no=g["no"])

insan_k = ofis.postane.insan_bekleyenler()
ajan_k = ofis.postane.ajana_bekleyenler()
sina("insan kuyrugunda yalnizca insana dusenler",
     all(x["alici"] == "insan" for x in insan_k) and len(insan_k) == 1)
sina("ajan kuyrugunda yalnizca ajana dusenler",
     all(x["alici"] != "insan" for x in ajan_k) and len(ajan_k) == 1)
sina("soran ajan BEKLIYOR sayiliyor",
     ofis.postane.bekliyor_mu("cinar")["bekliyor"])

# --------------------------------------------------------------------------
print("\n3. TESLIM -- ajana sorulan soru CEVAPLANIYOR")

kutu["cevap"] = ("Kendi akisimizdan gitsin. Harici servis kurulu degil ve "
                 "bagimlilik eklemek kapsam disi.")
sonuc = danisma.cevapla(ajan_k[0])

sina("cevap verildi", sonuc["durum"] == "cevaplandi", f"({sonuc})")
sina("cevaplayan dogru ajan", sonuc["ajan"] == "demir")
sina("cevap tahtaya gecti",
     any("kendi akisimizdan" in (c["cevap"] or "").lower()
         for c in ofis.postane.cevaplar("cinar")))
sina("soru kuyruktan cikti", ofis.postane.ajana_bekleyenler() == [])
# DANISMA TURU OLCULUYOR -- hic yazilmiyordu; ofisin harcamasi bu yolu
# gormuyordu.
import json as _json
with ofis.db.baglanti() as _c:
    _oz = [_json.loads(r["govde"]) for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='tur_ozeti' AND ajan_ad='demir'"
    ).fetchall()]
sina("danisma turu tur_ozeti YAZIYOR", any(o.get("yol") == "danisma" for o in _oz),
     str(_oz)[:160])
# Dikkat: cinar HALA bekliyor -- ama INSANA sordugu oteki soru yuzunden.
# "Bekliyor mu" sorusunun cevabi ajan geneli; burada sinanan sey, AJANA
# sorulan sorunun cozulmus olmasi. Ilk surumde bu ayrim yapilmamisti ve
# test kendi kurdugu ikinci soruya takildi -- olcum aracinin kendisi de
# olculmeli.
sina("ajana sorulan soru cinar'i ARTIK durdurmuyor",
     all(x["alici"] == "insan"
         for x in ofis.postane.bekleyen_sorular(soran="cinar")))

# --------------------------------------------------------------------------
print("\n4. DANISILANIN SINIRLARI -- yapiyla kesiliyor")

ayar = kutu["ayarlar"][-1]
sina("danisilan YAZAMAZ", ayar.get("yazabilir") is False, f"({ayar})")
sina("danisilan TEMIZ oturumda kostu", ayar.get("oturum_id") == "")
sina("danisilanin ARAC KUTUSU YOK (kendi soru soramaz)",
     not ayar.get("mcp_yapilandirma"))

metin = kutu["istekler"][-1]
sina("metinde SORAN kim yaziyor", "cinar" in metin)
sina("metinde hangi IS oldugu yaziyor", "Bildirim akisi" in metin)
sina("metinde sorunun kendisi var", "harici servis" in metin)
sina("metinde ilgili BILGI var", "bildirim kanali" in metin)
sina("dosya yazamayacagi ACIKCA soyleniyor", "Dosya YAZAMAZSIN" in metin)
sina("baskasina soramayacagi soyleniyor", "soru soramazsin" in metin)
sina("BILMIYORUM yolu aciklanmis", "BILMIYORUM" in metin)
sina("uydurma yasagi var", "UYDURMA" in metin)
sina("SORANIN transkripti VERILMEDI (taze goz)",
     "KANIT" not in metin and "tur_ozeti" not in metin)

# --------------------------------------------------------------------------
print("\n5. BILMIYORUM -- soru OLMUYOR, insana YUKSELIYOR")

m2 = ofis.postane.soru_sor("cinar", "bilge", "Rakip fiyati kac?",
                           gorev_no=g["no"])
kutu["cevap"] = "BILMIYORUM -- bu bilgi ofisin disinda, erisimim yok."
sonuc = danisma.cevapla(ofis.postane.ajana_bekleyenler()[0])

sina("bilmiyorum YUKSELTTI", sonuc["durum"] == "yukseldi", f"({sonuc})")
yukselen = [x for x in ofis.postane.insan_bekleyenler() if x["id"] == m2["id"]]
sina("soru INSANIN kuyruguna gecti", bool(yukselen))
sina("insana NEDEN dustugu yaziliyor",
     "YUKSELDI" in yukselen[0]["govde"] and "bilge" in yukselen[0]["govde"])
sina("orijinal soru KAYBOLMADI", "Rakip fiyati" in yukselen[0]["govde"])
sina("soran ajan HALA bekliyor (cevap gelmedi)",
     ofis.postane.bekliyor_mu("cinar")["bekliyor"])

# --------------------------------------------------------------------------
print("\n6. CEVAP ALINAMAZSA -- yine yukseliyor, SESSIZCE OLMUYOR")

for x in ofis.postane.insan_bekleyenler():
    ofis.postane.cevapla(x["id"], "Insan cevabi")

m3 = ofis.postane.soru_sor("cinar", "demir", "Ikinci sorum", gorev_no=g["no"])
kutu["cevap"] = ""                      # motor bos dondurur
sonuc = danisma.cevapla(ofis.postane.ajana_bekleyenler()[0])
sina("bos cevap YUKSELTTI", sonuc["durum"] == "yukseldi", f"({sonuc})")
sina("bos cevapta da sebep yaziliyor",
     any("bos cevap" in x["govde"] for x in ofis.postane.insan_bekleyenler()))

# --------------------------------------------------------------------------
print("\n7. YUKSELTME KAPISI")

try:
    ofis.postane.insana_yonlendir(m3["id"], "")
    sina("gerekcesiz yukseltme REDDEDILDI", False, "(kabul edildi)")
except PostaneHatasi:
    sina("gerekcesiz yukseltme REDDEDILDI", True)

for x in ofis.postane.insan_bekleyenler():
    ofis.postane.cevapla(x["id"], "Insan cevabi")
try:
    ofis.postane.insana_yonlendir(m3["id"], "Sebep var")
    sina("cevaplanmis soru yukseltilemiyor", False, "(kabul edildi)")
except PostaneHatasi:
    sina("cevaplanmis soru yukseltilemiyor", True)

# --------------------------------------------------------------------------
print("\n8. TOPLU TESLIM -- bir soru dusse otekiler devam eder")

ofis.postane.soru_sor("cinar", "demir", "Soru bir", gorev_no=g["no"])
ofis.postane.soru_sor("bilge", "demir", "Soru iki")
kutu["cevap"] = "Ikisine de cevabim bu."
sonuclar = danisma.bekleyenleri_cevapla()
sina("iki soru da ele alindi", len(sonuclar) == 2, f"({len(sonuclar)})")
sina("ikisi de cevaplandi",
     all(x["durum"] == "cevaplandi" for x in sonuclar))
sina("ajan kuyrugu bosaldi", ofis.postane.ajana_bekleyenler() == [])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
