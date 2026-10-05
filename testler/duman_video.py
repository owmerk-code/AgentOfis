# -*- coding: utf-8 -*-
"""VIDEO katmani: para yakmadan sinanir.

Bu dosyanin en onemli ozelligi, sinadigi seyin PARA olmasi. Gorsel
isinde bir hata birkac sent; videoda 30 saniyelik tek klip $12'ye kadar
cikiyor. Bu yuzden sinamalarin cogu "uretti mi" degil **"baslamadan
REDDETTI mi"** diye soruyor.

Uc soru:

1. **Tavan BASLAMADAN tutuyor mu.** Maliyet onceden bilinebilir (saniye
   basi fiyat), yani sonradan olcmek gec kalmaktir.
2. **Yarim adaptor "hazir" gorunmuyor mu.** Higgsfield uc noktasi
   yazilmadi; sessizce hazir gorunseydi "calisiyor gorunup calismayan"
   bir yol acilirdi.
3. **Gorsel ile ayni SEKIL mi.** Ikinci bir desen, iki kopyadan birinin
   unutulmasi demek (bu projede bes kez oldu).

Hicbir sinama ag'a cikmaz: gercek istek atan tek yol `baslat()` ve o da
yalnizca sahte ureticiyle cagriliyor.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import video, gorsel, roller

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


# ------------------------------------------------ 1. MALIYET ONCEDEN
print("\n1. maliyet IS BASLAMADAN hesaplaniyor mu")
sina("saniye ile dogru orantili",
     video.tahmini_maliyet("veo", 20) == 2.5 * video.tahmini_maliyet("veo", 8))
sina("4K daha pahali",
     video.tahmini_maliyet("veo", 8, "4k") >
     video.tahmini_maliyet("veo", 8, "720p"))
sina("sifir saniye bile bir saniye sayilir (bedava is yok)",
     video.tahmini_maliyet("veo", 0) > 0)


# --------------------------------------------------- 2. TAVAN KAPISI
print("\n2. tavan BASLAMADAN mi reddediyor")
# Anahtar SINAMANIN: Veo 'musait' sayilmazsa tavan kapisina hic gelinmez.
# 27.09'a kadar kullanicinin GERCEK kasasina yaslaniyordu (kok gecici
# klasore cevrilince ortaya cikti). Cagri tavanda REDDEDILIR, aga cikmaz.
import os as _os
_vk_eski = _os.environ.get("GEMINI_API_KEY")
_os.environ["GEMINI_API_KEY"] = "AIza-sinama-video"
try:
    video.uret("x", "/tmp/yok.mp4", saniye=30, tavan_usd=0.01,
               ucretsiz_sadece=False)
    sina("tavan asimi reddedildi", False, "-- kabul edildi!")
except video.ButceAsimi as exc:
    sina("tavan asimi reddedildi", True)
    sina("  'BASLATILMADI' acikca yaziyor", "BASLATILMADI" in str(exc))
    sina("  tahmin ve tavan birlikte soyleniyor",
         "$" in str(exc) and "tavan" in str(exc))
except video.VideoHatasi as exc:
    sina("tavan asimi reddedildi", False, f"-- yanlis sinif: {exc}")
finally:
    if _vk_eski is None:
        _os.environ.pop("GEMINI_API_KEY", None)
    else:
        _os.environ["GEMINI_API_KEY"] = _vk_eski

# ButceAsimi AYRI bir siniftir: cagiran bunu gercek bir hatadan ayirt
# edebilmeli, yoksa "tekrar dene" der ve tavan yavaslatmaya doner.
sina("ButceAsimi, VideoHatasi'nin alt sinifi",
     issubclass(video.ButceAsimi, video.VideoHatasi))
sina("ama VideoHatasi ButceAsimi DEGIL",
     not issubclass(video.VideoHatasi, video.ButceAsimi))

# Sure tavani da bir PARA korkulugu: 60 sn standart klip $24.
try:
    video.uretici_ac("veo").baslat("x", saniye=999)
    sina("azami sure reddedildi", False, "-- kabul edildi!")
except video.VideoHatasi as exc:
    sina("azami sure reddedildi", True)
    sina("  sebebin PARA oldugu soyleniyor", "PARA" in str(exc))


# --------------------------------------- 3. YARIM ADAPTOR SESSIZ DEGIL
print("\n3. yazilmamis adaptor 'hazir' gorunuyor mu")
h = video.uretici_ac("higgsfield")
sina("anahtarsiz higgsfield MUSAIT DEGIL", not h.musait_mi())
sina("sebebi soyleniyor", "HIGGSFIELD_API_KEY" in h.neden_musait_degil())
try:
    h.baslat("x", saniye=5)
    sina("yarim adaptor cagrilinca DURUYOR", False, "-- sessizce gecti!")
except video.VideoHatasi as exc:
    sina("yarim adaptor cagrilinca DURUYOR", True)
    sina("  'HENUZ YAZILMADI' diyor", "YAZILMADI" in str(exc))


# ------------------------------------------------ 4. KAYIT DEFTERI
print("\n4. kayit defteri ve siralama")
try:
    video.uretici_ac("sora")
    sina("  bilinmeyen ad reddedildi", False, "-- kabul edildi!")
except video.VideoHatasi as exc:
    sina("  bilinmeyen ad reddedildi", True)
    sina("  ret gecerli adlari SAYIYOR", "veo" in str(exc))

# UCRETSIZ VIDEO API'si YOK (olculdu). "Once ucretsiz" siralamasi
# burada kullaniciya olmayan bir guvence verirdi.
sina("hicbir uretici ucretsiz degil",
     all(u["ucretli"] for u in video.musait_ureticiler().values()))
fiyat = [video.uretici_ac(a).saniye_basi_usd for a in video.TERCIH_SIRASI]
sina("siralama UCUZDAN pahaliya", fiyat == sorted(fiyat), str(fiyat))
sina("her uretici fiyatini BILDIRIYOR", all(f > 0 for f in fiyat))


# ------------------------------------------- 5. GORSEL ILE AYNI SEKIL
print("\n5. gorsel.py ile ayni sozlesme sekli")
for ad in ("uretici_ac", "uretici_kaydet", "musait_ureticiler", "uret",
           "TERCIH_SIRASI"):
    sina(f"`{ad}` iki modulde de var",
         hasattr(video, ad) and hasattr(gorsel, ad))

for ad, h2 in video.musait_ureticiler().items():
    sina(f"{ad}: musait degilse SEBEP var",
         h2["musait"] or bool(h2["sebep"]))


# ------------------------------------ 6. ANAHTAR KASADAN OKUNUYOR MU
print("\n6. anahtar KASADAN okunuyor mu (olculmus hata)")
# Olculdu (20.09.2026): `GEMINI_API_KEY` kasada duruyordu ama
# `gorsel.py` yalnizca os.environ'a bakiyordu ve "kurulu degil" diyordu.
# Ofis, KENDI verdigi talimat izlendiginde bile calismiyordu.
sina("video, gorsel'in anahtar okuyucusunu kullaniyor",
     video.anahtar_oku is gorsel.anahtar_oku)
sina("okuyucu tek yerde (her uretici kendi okumasini yazmiyor)",
     "os.environ" not in
     Path("ofis/video.py").read_text(encoding="utf-8").split(
         "def anahtar_oku")[-1])


# ------------------------------------------------- 7. ROL BAGLANTISI
print("\n7. model adi TAHMIN degil OLCUM mu")
# Olculdu (20.09.2026): ilk yazimda `veo-3.1-lite` yazilmisti -- tahmin.
# Mutasyon sinamasi tavani kapatinca cagri gercek API'ye gitti ve HTTP
# 404 dondu; gercek ad `veo-3.1-lite-generate-preview` cikti. Bu sinama
# ag'a CIKMADAN ayni hatanin tekrarini yakalar.
v = video.uretici_ac("veo")
sina("varsayilan model, OLCULEN listede",
     v.VARSAYILAN_MODEL in v.OLCULEN_MODELLER, v.VARSAYILAN_MODEL)
sina("varsayilan EN UCUZ olan (lite)", "lite" in v.VARSAYILAN_MODEL)
sina("olculen modeller bos degil", len(v.OLCULEN_MODELLER) >= 1)


print("\n8. video ROLU araca bagli mi")
# Sira onemli: ONCE arac olculdu, SONRA rol yazildi. Ayni gun araci
# olmayan bir `video` rolu eklemeyi reddetmistik.
r = roller.ROLLER.get("video")
sina("video rolu kutuphanede var", r is not None)
if r:
    sina("  kanit turleri gecerli",
         all(k in roller.GECERLI_KANITLAR for k in r.kanit_turleri))
    sina("  olcut GERCEK maliyeti istiyor",
         "maliyet" in r.olcut_sablonu.lower())
    # 04.10.2026: video Flow ile (abonelik kredisi); kredi harcayan uretim sorulur.
    sina("  uyari Flow + kredi sorusu + ucretli API ayrimi",
         all(x in (r.uyari or "") for x in ("Flow", "onay_iste", "ucretli")))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
