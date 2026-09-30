# -*- coding: utf-8 -*-
"""Lider duman testi: uc kapi gercekten kapali mi.

Sinanan sey liderin zekasi degil KAPILAR:
fan-out gerekcesiz gecebiliyor mu · cakisan kollar planlamada yakalaniyor
mu · inceleme transkript goruyor mu · hukumsuz inceleme sessizce kapatiyor
mu.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, Lider, LiderHatasi
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


def reddetmeli(baslik, cagri, hata_sinifi):
    try:
        cagri()
        sina(baslik, False, "-- sessizce izin verildi!")
    except hata_sinifi:
        sina(baslik, True)


print("== lider duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-lider-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Lider Projesi", amac="Kapilari sinamak",
                     basari_olcutu="Uc kapi da kapali", kok_klasor=str(kok))
kanat = ofis.kanat_ac("URUN", "UR")

ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(kok / "demir"), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", klasor=str(kok / "cinar"), motor="sahte")
for a in ("demir", "cinar"):
    (kok / a).mkdir(parents=True, exist_ok=True)

kutu = {"senaryo": "basarili", "cevap": ""}
izler = []


def sahte_fabrika(ad, **ayar):
    m = SahteMotor(senaryo=kutu["senaryo"], cevap=kutu["cevap"])
    izler.append(m)
    return m


koltuk = Koltuk(ofis, motor_fabrikasi=sahte_fabrika)
lider = Lider(ofis, motor_fabrikasi=sahte_fabrika)

# --------------------------------------------------------------------------
print("1. FAN-OUT KAPISI -- gerekce zorunlu, iki yon de yazilir")
reddetmeli("gerekcesiz dagitim karari reddediliyor",
           lambda: lider.dagitim_karari("Magaza canliya", bol=True,
                                        gerekce="", lider_ad="demir"),
           LiderHatasi)

lider.dagitim_karari("Magaza canliya", bol=False,
                     gerekce="Kollar bagimsiz degil; tek ajanda daha ucuz.",
                     lider_ad="demir")
son = ofis.bellek.son_kararlar(1)[0]
sina("BOLMEME karari da gunluge yaziliyor", son["tur"] == "dagitim")
sina("bolmeme karari metninde 'bolunmedi' geciyor", "bolunmedi" in son["karar"])
sina("gerekce saklandi", "bagimsiz degil" in son["gerekce"])

# --------------------------------------------------------------------------
print("\n2. AYRIK ALAN KAPISI -- cakisma PLANLAMADA yakalaniyor")
cakisan = [
    {"baslik": "API yaz", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["api/"]},
    {"baslik": "Odeme ekle", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["api/odeme"]},        # api/ altinda -- cakisir
]
reddetmeli("cakisan kollar planlamada reddediliyor",
           lambda: lider.kollari_dogrula(cakisan), LiderHatasi)
reddetmeli("cakisan dagitim hic acilmiyor",
           lambda: lider.dagit("Hedef", cakisan, gerekce="g",
                               lider_ad="demir", kanat_id=kanat),
           LiderHatasi)
sina("cakisan dagitimda HIC gorev acilmadi", ofis.tahta.liste() == [])

ayrik = [
    {"baslik": "API yaz", "neden": "Siparis alinamiyor", "kabul_olcutu": "pytest yesil",
     "yazma_alani": ["api/"]},
    {"baslik": "Sepet ekrani", "neden": "Sepet gorunmuyor", "kabul_olcutu": "Ekran goruntusu",
     "yazma_alani": ["web/"]},
]
acilan = lider.dagit("Magaza canliya cikacak", ayrik,
                     gerekce="Iki kol ayri dosyalara dokunuyor, paralel kazanir.",
                     lider_ad="demir", kanat_id=kanat)
sina("ayrik kollar acildi", len(acilan) == 2)
sina("UST HEDEF her kola tasindi",
     all(g["ana_hedef"] == "Magaza canliya cikacak" for g in acilan))
sina("bolme karari gunluge dustu",
     ofis.bellek.son_kararlar(1)[0]["karar"].endswith("2 kola bolundu."))

# --------------------------------------------------------------------------
print("\n3. INCELEME ON KOSULLARI")
g1 = acilan[0]
reddetmeli("incelemede olmayan is incelenemiyor",
           lambda: lider.incele(g1["no"]), LiderHatasi)

kutu["cevap"] = "Bitti.\nKANIT terminal: pytest -q -> 9 passed"
koltuk.kos(g1["no"], "cinar")
sina("is incelemeye geldi", ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")

# --------------------------------------------------------------------------
print("\n4. TEMIZ BAGLAM (Yasa 4) -- lider transkript GORMUYOR")
metin = lider.inceleme_metni(g1["no"])
sina("ust hedef incelemede", "Magaza canliya cikacak" in metin)
sina("kabul olcutu incelemede", "pytest yesil" in metin)
sina("KANIT incelemede", "9 passed" in metin)
sina("iscinin ANLATISI incelemede YOK", "guven bana" not in metin)
# OLCULDU (20.09.2026, QUANTBOT isi): ajan ayni soruya iki kanit yazdi
# ve sayilar FARKLIYDI (385 / 384). Bagimsiz sayim ikincisini dogruladi.
# Lider ikisini de gordu, celiskiyi hic anmadan "kanitlar olcutu
# karsiliyor" deyip KAPATTI. Celisen kanit kanit degildir: hangisine
# dayanacagini bilmeyen bir defter kayit tutmuyor demektir.
sina("inceleme, kanitlarin BIRBIRIYLE tutarliligini soruyor",
     "BIRBIRIYLE tutarli" in metin)
# Yasa 4 anonimlik degil, CERCEVE devralmama kuralidir: lider iscinin
# raporunu, olay akisini, denediklerini gormez. Isin NEREDE oldugunu
# gormek zorundadir -- gormezse bulamadigini "yapilmamis" sanar (olculdu).
sina("iscinin RAPORU incelemede yok",
     "Is bitti" not in metin and "KANIT terminal:" not in metin.split("### Sunulan")[0])
sina("olay akisi/transkript incelemede yok",
     "sahiplenildi" not in metin and "arac_sonuc" not in metin)
sina("ISIN YERI incelemede var (bulamayip 'yok' demesin)",
     "Isin bulundugu yer" in metin and "cinar" in metin)
sina("hukum bicimi ogretiliyor", "KARAR: kapat" in metin)

# --------------------------------------------------------------------------
print("\n5. HUKUMSUZ INCELEME SESSIZCE KAPATMIYOR")
kutu["cevap"] = "Bence gayet iyi gorunuyor, eline saglik."   # KARAR satiri yok
sonuc = lider.incele(g1["no"], lider_ad="demir")
sina("hukum 'belirsiz'", sonuc["hukum"] == "belirsiz")
sina("is INCELEMEDE BEKLIYOR, kapanmadi",
     ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")
# INCELEME TURU OLCULUYOR -- hic yazilmiyordu. Hakem (fable) tam bu turda
# kosuyor; yazilmazsa haftalik kapi butcesi en pahali harcamayi GORMEZ.
import json as _json
with ofis.db.baglanti() as _c:
    _oz = [_json.loads(r["govde"]) for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='tur_ozeti' AND gorev_id=?",
        (g1["id"],)).fetchall()]
sina("inceleme turu tur_ozeti YAZIYOR (gorevle etiketli)",
     any(o.get("yol") == "inceleme" for o in _oz), str(_oz)[:160])
sina("  ve motorunu yaziyor",
     any(o.get("yol") == "inceleme" and o.get("motor") == "sahte" for o in _oz))



# --------------------------------------------------------------------------
print("\n6. LIDER TEMIZ OTURUMDA VE YAZAMAZ olarak aciliyor")
cagri = izler[-1].cagrilar[-1]
sina("lider TEMIZ oturumda acildi (oturum_id bos)", cagri["oturum_id"] == "")
sina("lider YAZAMAZ olarak acildi", cagri["yazabilir"] is False)

# --------------------------------------------------------------------------
print("\n7. GERI GONDERME -- gerekce zorunlu, ders istege bagli")
kutu["cevap"] = "KARAR: geri"          # gerekcesiz
sonuc = lider.incele(g1["no"], lider_ad="demir")
sina("gerekcesiz geri gonderme 'belirsiz' sayiliyor",
     sonuc["hukum"] == "belirsiz")
sina("is hala incelemede", ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")

kutu["cevap"] = ("KARAR: geri -- Bos sepet kenar durumu test edilmemis\n"
                 "DERS: Kenar durumlarini kabul olcutune yaz")
sonuc = lider.incele(g1["no"], lider_ad="demir")
sina("geri gonderildi", sonuc["hukum"] == "geri")
sina("gerekce tasindi", "Bos sepet" in sonuc["gerekce"])
sina("is 'calisiyor'a dondu",
     ofis.tahta.gorev(g1["no"])["durum"] == "calisiyor")
sina("kilit ISCIDE kaldi (ayni ajan devam edecek)",
     ofis.tahta.cakisan_kilitler(["api/"])[0]["ajan_ad"] == "cinar")
dersler = ofis.kadro.dersler("cinar")
sina("ders ajanin siciline yazildi", len(dersler) == 1)
sina("ders KISIYE ozel", ofis.kadro.dersler("demir") == [])

# --------------------------------------------------------------------------
print("\n8. DERS OTOMATIK YAZILMIYOR (tekrar sayaci anlamini korusun)")
kutu["cevap"] = "Bitti.\nKANIT terminal: pytest -q -> 11 passed"
koltuk.kos(g1["no"], "cinar")
kutu["cevap"] = "KARAR: geri -- Hala eksik"      # DERS satiri YOK
lider.incele(g1["no"], lider_ad="demir")
sina("DERS satiri yoksa yeni ders yazilmiyor",
     len(ofis.kadro.dersler("cinar")) == 1)
sina("mevcut dersin sayaci da artmadi",
     ofis.kadro.dersler("cinar")[0]["tekrar"] == 1)

# --------------------------------------------------------------------------
print("\n9. KAPATMA -- kanit kapisi lider icin de gecerli")
kutu["cevap"] = "Bitti.\nKANIT terminal: pytest -q -> 12 passed"
koltuk.kos(g1["no"], "cinar")
kutu["cevap"] = "Kanitlar olcutu karsiliyor.\nKARAR: kapat"
sonuc = lider.incele(g1["no"], lider_ad="demir")
sina("hukum 'kapat'", sonuc["hukum"] == "kapat")
sina("gorev BITTI", ofis.tahta.gorev(g1["no"])["durum"] == "bitti")
sina("kapanista kilit birakildi", ofis.tahta.cakisan_kilitler(["api/"]) == [])
sina("kapanis karar gunlugune dustu",
     any("#1 kapatildi" in k["karar"] for k in ofis.bellek.son_kararlar(5)))

# --------------------------------------------------------------------------
print("\n9b. YAPAN INCELEYEMEZ")
# Lider birlestirme isini kendi ustlenebilir -- ama kendi isini
# inceleyemez: kanit kapisi kendi isini onaylamis olur ve Yasa 4
# (temiz baglam) coker. Inceleme o zaman INSANA duser.
gk = ofis.tahta.gorev_ac(
        "Liderin kendi isi", neden="Parcalari birlestirmek gerek",
        ana_hedef="Magaza canliya cikacak",
        kabul_olcutu="Uctan uca kosuyor",
        yazma_alani=["birlesik/"], kanat_id=kanat, acan="demir")
ofis.tahta.sahiplen(gk["no"], "demir", gk["revizyon"])
ofis.tahta.kanit_ekle(gk["no"], "terminal", "kos", "gecti", "demir")
ofis.tahta.incelemeye_ver(gk["no"], ofis.tahta.gorev(gk["no"])["revizyon"])
reddetmeli("lider KENDI isini inceleyemiyor",
           lambda: lider.incele(gk["no"], lider_ad="demir"), LiderHatasi)
sina("is incelemede BEKLIYOR (insana kaldi)",
     ofis.tahta.gorev(gk["no"])["durum"] == "inceleme")

# --------------------------------------------------------------------------
print("\n10. KANITSIZ IS INCELENEMEZ")
g2 = acilan[1]
ofis.tahta.sahiplen(g2["no"], "cinar", ofis.tahta.gorev(g2["no"])["revizyon"])
reddetmeli("kanitsiz is lidere gitmiyor",
           lambda: lider.incele(g2["no"], lider_ad="demir"), LiderHatasi)

# 01.10 (gercek set G16): hukum satiri UNUTULDUYSA bir kez kisa tur sorulur.
_gh = ofis.tahta.gorev_ac("Hukumu unutulan is", neden="n", ana_hedef="unutulan hukum",
                         kabul_olcutu="dosyalar", yazma_alani=["hukum/"], kanat_id=kanat)
ofis.tahta.sahiplen(_gh["no"], "cinar", _gh["revizyon"])
ofis.tahta.kanit_ekle(_gh["no"], "terminal", "yazildi", "ok", "cinar")
ofis.tahta.incelemeye_ver(_gh["no"], ofis.tahta.gorev(_gh["no"])["revizyon"])
from ofis.lider import Lider as _Lider  # noqa: E402
_sorular = []


class _UnutanHakem(SahteMotor):
    def tur_kos(self, metin, **ayar):
        _sorular.append(metin)
        self.cevap = ("KARAR: kapat\nPATRONA: Dosyalar yazildi." if "HUKUM SATIRI YOK" in metin
                      else "Kanitlar tutarli, dosyalar dogru, fazladan satir yok.")
        return super().tur_kos(metin, **ayar)


_s5 = _Lider(ofis, motor_fabrikasi=lambda ad, **a: _UnutanHakem(cevap="")).incele(_gh["no"], lider_ad="demir")
sina("hukumsuz incelemeden sonra kisa HUKUM sorusu soruldu", any("HUKUM SATIRI YOK" in m for m in _sorular),
     str(len(_sorular)))
sina("  ve is KAPANDI", _s5["hukum"] == "kapat" and ofis.tahta.gorev(_gh["no"])["durum"] == "bitti",
     str(_s5))


# 01.10 (patronun ofis kopyasi): PATRONA'nin altina yazilan inceleme notu
# patrona gitmez.
from ofis.lider import patrona_ayikla as _pa
_pm = _pa('KARAR: kapat\nPATRONA: Gorsel hazir.\n\nNot: Gorseli actim, karalama/yazi.py.\nBILGI: a -> b')
sina("PATRONA metni 'Not:' satirinda biter", _pm == 'Gorsel hazir.', repr(_pm))
sina("'Not' ile baslayan kelime (Nota) kesmez",
     _pa('KARAR: kapat\nPATRONA: Nota gore yazildi.') == 'Nota gore yazildi.')

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
