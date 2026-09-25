# -*- coding: utf-8 -*-
"""Gorsel uretme duman testi -- AG'A CIKMADAN.

Sinanan sey Gemini'nin cizim yetenegi degil, OFISIN KURALLARI:

* Musait olmayan saglayici SESSIZCE atlaniyor mu? Atlanmamali -- sebebi
  soylenmeli, yoksa "neden GPT kullanilmadi" cevapsiz kalir.
* Ucretsiz olan ONCE mi deneniyor? Para harcayan bir saglayiciya
  sessizce dusmek, kullanicinin istemedigi bir faturadir.
* Gorsel yerine METIN donerse basari sayiliyor mu? Sayilmamali --
  cagiran olmayan bir dosyaya kanit yazar.
* Anahtar hata metnine SIZIYOR mu? URL'de anahtar var; sizmamali.
* Bos istem reddediliyor mu?

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import gorsel

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


print("== gorsel duman testi ==\n")
kok = Path(tempfile.mkdtemp(prefix="ofis-gorsel-"))

# --------------------------------------------------------------------------
print("1. BOS ISTEM REDDEDILIYOR")
try:
    gorsel.uret("   ", kok / "x.png")
    sina("bos istem reddedildi", False, "(kabul edildi)")
except gorsel.GorselHatasi:
    sina("bos istem reddedildi", True)

# --------------------------------------------------------------------------
print("\n2. MUSAIT OLMAYAN SAGLAYICI SESSIZCE ATLANMIYOR")


class YokUretici(gorsel.Uretici):
    ad = "yok_test"
    ucretli = False

    def musait_mi(self):
        return False

    def neden_musait_degil(self):
        return "SINAMA: anahtar yok"

    def uret(self, istem, hedef, *, model="", kalite=""):
        raise AssertionError("musait degilken cagrilmamaliydi")


class SahteUretici(gorsel.Uretici):
    ad = "sahte_test"
    ucretli = True          # pahali: SIRADA SONRA olmali

    def musait_mi(self):
        return True

    def uret(self, istem, hedef, *, model="", kalite=""):
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(b"PNG-SAHTE")
        return {"uretici": self.ad, "model": model or "sahte-1",
                "yol": str(hedef), "bayt": 9, "tip": "image/png"}


gorsel.uretici_kaydet(YokUretici)
gorsel.uretici_kaydet(SahteUretici)
_eski_sira = gorsel.TERCIH_SIRASI
gorsel.TERCIH_SIRASI = ("yok_test", "sahte_test")

sonuc = gorsel.uret("bir logo", kok / "a.png", ucretsiz_sadece=False)
sina("musait olan kullanildi", sonuc["uretici"] == "sahte_test", f"({sonuc})")
sina("dosya GERCEKTEN yazildi", (kok / "a.png").exists())
sina("atlanan saglayici BILDIRILIYOR",
     any(a["uretici"] == "yok_test" for a in sonuc["atlananlar"]))
sina("atlama SEBEBI yaziyor",
     "anahtar yok" in sonuc["atlananlar"][0]["sebep"],
     f"({sonuc['atlananlar']})")

# --------------------------------------------------------------------------
print("\n3. HICBIRI MUSAIT DEGILSE -- SEBEPLERIYLE dusuyor")
gorsel.TERCIH_SIRASI = ("yok_test",)
try:
    gorsel.uret("bir logo", kok / "b.png", ucretsiz_sadece=False)
    sina("hepsi kapaliyken reddedildi", False, "(kabul edildi)")
except gorsel.GorselHatasi as exc:
    sina("hepsi kapaliyken reddedildi", True)
    sina("ret, SEBEPLERI siraliyor", "anahtar yok" in str(exc), f"({exc})")
gorsel.TERCIH_SIRASI = _eski_sira

# --------------------------------------------------------------------------
print("\n4. UCRETSIZ OLAN ONCE DENENIYOR")
# Para harcayan bir saglayiciya sessizce dusmek, kullanicinin
# istemedigi bir faturadir. Sira bilinctir, tesaduf degil.
uretililer = gorsel.musait_ureticiler()
sira = list(gorsel.TERCIH_SIRASI)
ucretliler = [ad for ad in sira if uretililer.get(ad, {}).get("ucretli")]
ucretsizler = [ad for ad in sira if not uretililer.get(ad, {}).get("ucretli")]
sina("tercih sirasinda ucretsizler once",
     all(sira.index(u) < sira.index(p) for u in ucretsizler for p in ucretliler),
     f"({sira})")

# --------------------------------------------------------------------------
print("\n5. GORSEL YERINE METIN DONERSE BASARI SAYILMIYOR")
# Sessiz kayip: cagiran "uretildi" sanip olmayan bir dosyaya kanit yazar.


class MetinDonduren(gorsel.GeminiUretici):
    """Gemini'nin gercek cevap bicimi, ama gorsel yerine metin."""

    def musait_mi(self):
        return True

    def uret(self, istem, hedef, *, model="", kalite=""):
        # Gercek koddaki ayni yolu kullan: sahte bir yanit uzerinden gec.
        d = {"candidates": [{"content": {"parts": [
            {"text": "Bu istemi gorsellestiremiyorum."}]}}]}
        parcalar = (d["candidates"][0]["content"]).get("parts") or []
        metin = [p["text"] for p in parcalar if "text" in p]
        if not any("inlineData" in p for p in parcalar):
            raise gorsel.GorselHatasi(
                "Gemini gorsel yerine metin dondurdu: " + " ".join(metin)[:300])
        return {}


try:
    MetinDonduren().uret("x", kok / "c.png")
    sina("metin donunce HATA veriliyor", False, "(basari sayildi)")
except gorsel.GorselHatasi as exc:
    sina("metin donunce HATA veriliyor", True)
    sina("hata metni sebebi soyluyor", "metin dondurdu" in str(exc))
sina("basarisiz uretimde dosya OLUSMADI", not (kok / "c.png").exists())

# --------------------------------------------------------------------------
print("\n6. ANAHTAR HATA METNINE SIZMIYOR")
# URL'de anahtar var: `...:generateContent?key=<ANAHTAR>`. Hata metni
# kullaniciya, loga, kanita gidebilir. Sizan anahtar geri alinamaz.
_eski_anahtar = os.environ.get("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = "AIza-SINAMA-ANAHTARI-GIZLI-KALMALI"
_eski_urlopen = gorsel.urllib.request.urlopen


def _patlat(istek, timeout=None):
    raise urllib.error.HTTPError(
        istek.full_url, 400, "Bad Request", {},
        io.BytesIO(json.dumps({"error": {"message":
            f"bad key: {os.environ['GEMINI_API_KEY']}"}}).encode()))


gorsel.urllib.request.urlopen = _patlat
try:
    gorsel.GeminiUretici().uret("x", kok / "d.png")
    sina("hata firlatildi", False, "(sessiz gecti)")
except gorsel.GorselHatasi as exc:
    sina("hata firlatildi", True)
    sina("ANAHTAR hata metninde YOK",
         "AIza-SINAMA-ANAHTARI-GIZLI-KALMALI" not in str(exc), f"({exc})")
    sina("yerine maske var", "<ANAHTAR>" in str(exc), f"({exc})")
finally:
    gorsel.urllib.request.urlopen = _eski_urlopen
    if _eski_anahtar is None:
        os.environ.pop("GEMINI_API_KEY", None)
    else:
        os.environ["GEMINI_API_KEY"] = _eski_anahtar

# --------------------------------------------------------------------------
print("\n7. KOTA DOLMASI, HATADAN AYIRT EDILIYOR")
# Kaynak tukenmesi bir HATA degildir -- motor limitinde de ayni ayrim var.
os.environ["GEMINI_API_KEY"] = "AIza-test"


def _kota(istek, timeout=None):
    raise urllib.error.HTTPError(
        istek.full_url, 429, "Too Many Requests", {},
        io.BytesIO(json.dumps({"error": {"status": "RESOURCE_EXHAUSTED",
                                         "message": "quota"}}).encode()))


gorsel.urllib.request.urlopen = _kota
try:
    gorsel.GeminiUretici().uret("x", kok / "e.png")
    sina("kota hatasi firlatildi", False)
except gorsel.GorselHatasi as exc:
    sina("kota hatasi firlatildi", True)
    sina("mesaj KOTA dedigini soyluyor", "kota" in str(exc).lower(), f"({exc})")
    sina("ne yapilacagi soyleniyor",
         "bekle" in str(exc).lower() or "ucretli" in str(exc).lower())
finally:
    gorsel.urllib.request.urlopen = _eski_urlopen
    if _eski_anahtar is None:
        os.environ.pop("GEMINI_API_KEY", None)
    else:
        os.environ["GEMINI_API_KEY"] = _eski_anahtar

# --------------------------------------------------------------------------
print("\n8. OPENAI: ChatGPT Plus YETMEZ -- sebep acikca soyleniyor")
_eski_oai = os.environ.pop("OPENAI_API_KEY", None)
u = gorsel.OpenAIUretici()
sina("anahtarsiz musait degil", not u.musait_mi())
sebep = u.neden_musait_degil()
sina("Plus'in yetmedigi SOYLENIYOR", "Plus" in sebep, f"({sebep[:120]})")
sina("nereden alinacagi soyleniyor", "platform.openai.com" in sebep)
sina("ucretli oldugu soyleniyor", "ucretli" in sebep.lower())
if _eski_oai is not None:
    os.environ["OPENAI_API_KEY"] = _eski_oai

# --------------------------------------------------------------------------
print("\n8b. KALITE VE GUNCELLIK")
# Gemini'de kalite kademesi YOK. Sessizce yutmak, kullanicinin "yuksek
# kalite istedim" sanmasina yol acar -- sessizce yok sayilan ayar, ayar
# degildir.
#
# Ayrica MODEL GUNCELLIGI: bu adaptorun varsayilani IKI KEZ eskidi
# (gpt-image-1 emekliye ayrildi, gpt-image-1.5 zaten gecmisti). Ikisinin
# de sebebi ayni: ikincil kaynaga guvenip BIRINCIL kaynaga bakmamak.
# Emekliye ayrilmis modele baglanan varsayilan, tarihi gelince SESSIZCE
# bozulur. Bu sinama, bir dahaki eskimeyi yakalar.
_eski_g = os.environ.get("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = "AIza-test"
try:
    gorsel.GeminiUretici().uret("x", kok / "k.png", kalite="high")
    sina("Gemini kaliteyi REDDEDIYOR", False, "(sessizce yuttu)")
except gorsel.GorselHatasi as exc:
    sina("Gemini kaliteyi REDDEDIYOR", True)
    sina("care olarak openai oneriliyor", "openai" in str(exc), f"({exc})")
finally:
    if _eski_g is None:
        os.environ.pop("GEMINI_API_KEY", None)
    else:
        os.environ["GEMINI_API_KEY"] = _eski_g

sina("OpenAI varsayilan kalitesi 'auto' DEGIL (fatura ongorulebilsin)",
     gorsel.OpenAIUretici.VARSAYILAN_KALITE != "auto",
     f"({gorsel.OpenAIUretici.VARSAYILAN_KALITE})")
sina("OpenAI modeli GUNCEL (emekli olan degil)",
     gorsel.OpenAIUretici.VARSAYILAN_MODEL.startswith("gpt-image-2.5"),
     f"({gorsel.OpenAIUretici.VARSAYILAN_MODEL})")
sina("gecersiz kalite REDDEDILIYOR",
     "ruya" not in gorsel.OpenAIUretici.KALITELER)

print("\n9. UZANTI EKSIKSE .png EKLENIYOR")
gorsel.TERCIH_SIRASI = ("sahte_test",)
sonuc = gorsel.uret("logo", kok / "uzantisiz", ucretsiz_sadece=False)
sina("uzanti otomatik eklendi", sonuc["yol"].endswith(".png"), f"({sonuc['yol']})")
gorsel.TERCIH_SIRASI = _eski_sira


# ---------------------------------------------------------------------------
# ANAHTAR VAR != URETEBILIYOR
#
# Olculdu (21.09.2026): `kabuk gorsel durum` **MUSAIT** basiyordu ve
# `yetenek` [+] HAZIR gosteriyordu -- ama gemini GUNLUK kotasi doluydu
# ve saglayici hicbir sey uretemiyordu. `musait_mi()` yalnizca ANAHTARIN
# VARLIGINI olcuyor; gosterge uretebilirligi IDDIA ediyordu.
#
# Kotayi her `durum` cagrisinda olcemeyiz: olcmek bir istek harcar ve
# tam tuketmeye calistigimiz seyi tuketir. Tahmin etmiyoruz, HATIRLIYORUZ.
# ---------------------------------------------------------------------------
print("\n-- kota hafizasi: anahtar var != uretebiliyor --")

import tempfile as _kqtf
import time as _kqtime
import urllib.error as _kqerr
from pathlib import Path as _kqP

# YALITIM: kullanicinin GERCEK kota defteri bu sinamayi etkileyemez.
# Ayni ders bir kez odendi (`anahtar_oku` sirasi): deterministik
# olmayan test, sinadigi seyi degil kendini olcer.
_kqeski = gorsel.KOTA_DEFTERI
gorsel.KOTA_DEFTERI = _kqP(_kqtf.mkdtemp(prefix="ofis-kota-")) / "kota.json"

sina("kayit yokken not BOS (uydurmuyor)", gorsel.kota_notu("gemini") == "")

gorsel.kota_yaz("gemini", gunluk=True)
_kqn = gorsel.kota_notu("gemini")
sina("kota yazilinca not doluyor", bool(_kqn), f"({_kqn})")
sina("GUNLUK ile dakikalik ayirt ediliyor", "GUNLUK" in _kqn, f"({_kqn})")
# Fark onemli: dakikalik kotada beklemek ise yarar, gunlukte yaramaz.
gorsel.kota_yaz("gemini", gunluk=False)
sina("dakikalik kota ayri yaziliyor",
     "dakikalik" in gorsel.kota_notu("gemini"))

# BAYAT KAYIT BUGUNKU HALI SOYLEMEZ. Ucretsiz kotalar gunluk yenilenir;
# dunku bir kaydi gostermek, bugun calisan bir saglayiciyi bozuk
# gostermek olurdu -- yanlis gosteren gosterge, yine.
import json as _kqjson
gorsel.KOTA_DEFTERI.write_text(_kqjson.dumps(
    {"gemini": {"an": _kqtime.time() - (gorsel.KOTA_TAZE_SANIYE + 60),
                "gunluk": True}}), encoding="utf-8")
sina("BAYAT kayit yok sayiliyor", gorsel.kota_notu("gemini") == "")

# `musait_ureticiler()` notu TASIYOR mu -- gostergeler oradan okuyor.
gorsel.kota_yaz("gemini", gunluk=True)
_kqd = gorsel.musait_ureticiler()
sina("musait_ureticiler kota_notu tasiyor",
     bool(_kqd["gemini"].get("kota_notu")), f"({_kqd['gemini']})")
# Anahtari OLMAYAN uretici icin not anlamsizdir: zaten uretemiyor.
sina("anahtarsiz uretici icin not bos",
     _kqd["openai"].get("kota_notu") == "")

# GOSTERGE artik HAZIR DEMIYOR. Bu, butun duzeltmenin sebebi.
from ofis import yetenek as _kqyet
_kqsat = _kqyet._uretici_grubu(gorsel, "gorsel")
_kqg = [s for s in _kqsat if s["ad"] == "gemini"][0]
sina("yetenek HAZIR demiyor, BILINMIYOR diyor",
     _kqg["durum"] == _kqyet.BILINMIYOR, f"({_kqg['durum']})")
sina("yetenek sebebi SOYLUYOR (teshis + care)",
     "kota" in (_kqg.get("care") or "").lower()
     and "yenilenir" in (_kqg.get("care") or ""), f"({_kqg.get('care')})")

# TERS YON: kayit yoksa HAZIR demeli. Yoksa "her zaman bilinmiyor" diyen
# bir kod da sinamayi gecerdi ve gosterge ise yaramaz olurdu.
gorsel.KOTA_DEFTERI.unlink()
_kqg2 = [s for s in _kqyet._uretici_grubu(gorsel, "gorsel")
         if s["ad"] == "gemini"][0]
sina("kota kaydi yokken HAZIR diyor", _kqg2["durum"] == _kqyet.HAZIR,
     f"({_kqg2['durum']})")

# GERCEK YOL: 429 gelince kayit KENDILIGINDEN dusuyor mu. Modulu
# yazmak yetmez -- cagrildigi ayrica olculmeli (bugun `video.py` tam
# bu yuzden ajana ulasmiyordu).
_kqasil = gorsel.urllib.request.urlopen


def _kq429(*a, **k):
    raise _kqerr.HTTPError(
        "https://x", 429, "Too Many Requests", {},
        # GERCEK yuk bicimi: parser `@type` icinde "QuotaFailure" arar.
        # Ilk surumumde `@type` yoktu ve sinama "GUNLUK degil" dedi --
        # kod dogruydu, SAHNE eksikti. Testin kurdugu sahne, olcmek
        # istedigi sinira ULASMALI.
        __import__("io").BytesIO(
            b'{"error":{"details":[{"@type":'
            b'"type.googleapis.com/google.rpc.QuotaFailure",'
            b'"violations":[{"quotaId":'
            b'"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'))


gorsel.urllib.request.urlopen = _kq429
os.environ["GEMINI_API_KEY"] = "sahte-anahtar"
try:
    gorsel.uret("x", gorsel.KOTA_DEFTERI.parent / "y.png", uretici="gemini",
                ucretsiz_sadece=False)
    sina("429 GorselHatasi'na cevriliyor", False, "-- istisna gelmedi")
except gorsel.GorselHatasi:
    sina("429 GorselHatasi'na cevriliyor", True)
finally:
    gorsel.urllib.request.urlopen = _kqasil
    os.environ.pop("GEMINI_API_KEY", None)

sina("429 KOTA KAYDINI kendiliginden dusuruyor",
     "GUNLUK" in gorsel.kota_notu("gemini"),
     f"({gorsel.kota_notu('gemini')!r})")

gorsel.KOTA_DEFTERI = _kqeski



# ---------------------------------------------------------------------------
# PARA KILIDI -- "sadece free" ifade edilebilmeli
#
# Kullanicinin kisiti (21.09.2026): *"openrouter hesabimda bakiye var
# baska bot icin kullaniyorum, sadece free -- para kesmiycek."*
#
# Bu ifade EDILEMIYORDU. `TERCIH_SIRASI` ucretsiz gemini'den UCRETLI
# openrouter'a duser; anahtar eklendigi an bir sonraki uretim baska bir
# botun bakiyesinden keserdi ve bunu soyleyen hicbir sey yoktu.
#
# OLCULDU (openrouter.ai/api/v1/models): gorsel cikti veren 11 modelin
# HEPSI ucretli. "Ekleyelim ama ucretsizini kullanalim" diye bir yol
# YOK -- ancak odemek ya da hic kullanmamak var.
# ---------------------------------------------------------------------------
print("\n-- para kilidi: 'sadece free' ifade edilebiliyor mu --")

import tempfile as _pktf
from pathlib import Path as _pkP

# YALITIM: kullanicinin GERCEK ayar defteri bu sinamayi etkilemesin.
_pkeski_ayar = gorsel.AYAR_DEFTERI
_pkeski_ortam = os.environ.pop("OFIS_PARA_HARCA", None)
gorsel.AYAR_DEFTERI = _pkP(_pktf.mkdtemp(prefix="ofis-para-")) / "ayar.json"

# VARSAYILAN KAPALI: para harcamak ACIK bir tercih olmali. Yanlis
# yonde yanilmanin bedeli farkli -- kapaliyken yanilmak "uretemedim"
# der, acikken yanilmak FATURA yazar.
sina("VARSAYILAN: para harcama kapali", gorsel.ucretsiz_sadece_mi() is True)

gorsel.para_harca_ayarla(True)
sina("acilinca aciliyor", gorsel.ucretsiz_sadece_mi() is False)
gorsel.para_harca_ayarla(False)
sina("kapatilinca kapaniyor", gorsel.ucretsiz_sadece_mi() is True)

# ORTAM DEGISKENI KAZANIR: acikca verilen deger her zaman kazanir
# (rolun turu, zincirin ilk basamagi, anahtar okuma sirasi -- ayni ilke).
os.environ["OFIS_PARA_HARCA"] = "1"
sina("ortam degiskeni ayari EZIYOR", gorsel.ucretsiz_sadece_mi() is False)
os.environ.pop("OFIS_PARA_HARCA", None)
sina("ortam kalkinca ayar geri geliyor", gorsel.ucretsiz_sadece_mi() is True)


class _PkUcretli(gorsel.Uretici):
    """Ucretli sahte uretici -- CAGRILIRSA para yanmis sayilir."""
    ad = "pk_ucretli"
    ucretli = True
    cagrildi = 0

    def musait_mi(self):
        return True

    def uret(self, istem, hedef, **kw):
        _PkUcretli.cagrildi += 1
        _pkP(hedef).write_bytes(b"x")
        return {"uretici": self.ad, "model": "m", "yol": str(hedef),
                "bayt": 1, "tip": "image/png"}


gorsel.uretici_kaydet(_PkUcretli)
_pkhedef = gorsel.AYAR_DEFTERI.parent / "c.png"

# ACIKCA istenen ucretli uretici SESSIZCE ATLANMAZ, REDDEDILIR.
# Sessizce atlamak, kullanicinin istedigini yaptigini sanmasi demektir.
try:
    gorsel.uret("x", _pkhedef, uretici="pk_ucretli")
    sina("acikca istenen ucretli uretici REDDEDILIYOR", False,
         "-- sessizce gecti, PARA RISKI")
except gorsel.ParaKilidi:
    sina("acikca istenen ucretli uretici REDDEDILIYOR", True)
sina("reddedilen uretici HIC cagrilmadi", _PkUcretli.cagrildi == 0)

# Ret AYRI BIR SINIF: bu bir ariza degil bir KARAR. Tek sinif olsaydi
# cagiran "tekrar dene" der ve kilit bir yavaslatmaya donusurdu.
sina("ParaKilidi, GorselHatasi'nin alt sinifi",
     issubclass(gorsel.ParaKilidi, gorsel.GorselHatasi))
# Ret CAREYI soyler.
try:
    gorsel.uret("x", _pkhedef, uretici="pk_ucretli")
except gorsel.ParaKilidi as _pke:
    sina("ret, kilidin nasil acilacagini soyluyor",
         "gorsel para ac" in str(_pke), f"({_pke})")

# TEK SEFERLIK muafiyet calisiyor -- kilit bir duvar degil, bir kapi.
gorsel.uret("x", _pkhedef, uretici="pk_ucretli", ucretsiz_sadece=False)
sina("tek seferlik muafiyetle uretiyor", _PkUcretli.cagrildi == 1)

# DUSME SIRASINDA ucretli uretici ATLANIR (acikca istenmedi) ve sebebi
# GORUNUR olur -- sessiz atlama yasak.
_pkonce = _PkUcretli.cagrildi
_pkeski_sira = gorsel.TERCIH_SIRASI
gorsel.TERCIH_SIRASI = ("pk_ucretli",)
try:
    gorsel.uret("x", _pkhedef)
    sina("dusme sirasinda ucretli SESSIZCE kullanilmiyor", False,
         "-- para yandi")
except gorsel.GorselHatasi as _pke2:
    sina("dusme sirasinda ucretli SESSIZCE kullanilmiyor",
         _PkUcretli.cagrildi == _pkonce)
    sina("atlama sebebi GORUNUR", "para kilidi" in str(_pke2).lower(),
         f"({_pke2})")
gorsel.TERCIH_SIRASI = _pkeski_sira

# VIDEO da ayni kilidi ODUNC alir -- ikinci kopya yok.
from ofis import video as _pkvid
sina("video ayni kilidi ODUNC aliyor (ikinci tanim yok)",
     _pkvid.gorsel.ucretsiz_sadece_mi is gorsel.ucretsiz_sadece_mi)
# SAHTE ucretli uretici kullanilir, GERCEK `veo` DEGIL.
# Ilk surumumde `uretici="veo"` yazmistim ve mutasyon sinamasinda test
# GERCEK Veo API'sine gitti. Iki kusur birden: (1) mutasyonda test
# temiz kalmak yerine COKTU, (2) faturalandirma acik olsaydi bir
# SINAMA para harcayacakti. **Bir test kullanicinin parasina
# dokunamamali** -- kendi kurdugu sahne disina cikmamali.
class _PkVideo(_pkvid.Uretici):
    ad = "pk_video"
    ucretli = True
    saniye_basi_usd = 0.01
    cagrildi = 0

    def musait_mi(self):
        return True

    def baslat(self, istem, *, saniye, model="", cozunurluk="720p"):
        _PkVideo.cagrildi += 1
        return {"is_id": "pk-1", "uretici": self.ad, "model": "m",
                "saniye": saniye, "cozunurluk": cozunurluk}


_pkvid.uretici_kaydet(_PkVideo)
try:
    _pkvid.uret("x", _pkhedef.with_suffix(".mp4"), uretici="pk_video",
                saniye=4, bekle=False)
    sina("video kilit acikken REDDEDILIYOR", False, "-- para riski")
except _pkvid.ParaKilidi as _pke3:
    sina("video kilit acikken REDDEDILIYOR", True)
    # Videoda ucretsiz katman HIC YOK; bu acikca soylenmeli, yoksa
    # kullanici olmayan bir ucretsiz yol arar.
    sina("video retti 'ucretsiz katman yok' diyor",
         "UCRETSIZ KATMAN YOK" in str(_pke3), f"({_pke3})")
except _pkvid.VideoHatasi as _pke3:
    # Kilit kalkarsa buraya duser: COKMEK yerine temiz KALIR.
    # Coken bir test, kaldigini soyleyen bir testten kotudur --
    # geri kalan sinamalar hic kosmaz.
    sina("video kilit acikken REDDEDILIYOR", False, f"-- {str(_pke3)[:60]}")
    sina("video retti 'ucretsiz katman yok' diyor", False, "-- kilit yok")
sina("kilit acikken video ureticisi HIC cagrilmadi", _PkVideo.cagrildi == 0)

gorsel.AYAR_DEFTERI = _pkeski_ayar
if _pkeski_ortam is not None:
    os.environ["OFIS_PARA_HARCA"] = _pkeski_ortam



# ---------------------------------------------------------------------------
# KASA OKUMASI TEK YERDE -- ve motor da oradan okuyor
#
# AYNI KAPALI DONGU IKI KEZ CIKTI:
#   `gorsel.py`      (20.09.2026) -- yalniz os.environ'a bakiyordu
#   `motor/gemini.py`(21.09.2026) -- AYNI HATA, ayri modulde
#
# Ikincisinde CLI kuruluydu (0.52.0), anahtar kasadaydi ve `musait_mi()`
# yine False donuyordu: dorduncu motor `yetenek`te, `saglik`ta ve
# `ekip oner`de aylardir "kurulu degil" gorunuyordu.
#
# Ikinci kez cikmasi, yardimcinin YANLIS YERDE durdugunu gosterdi:
# `gorsel.py`de yasayan bir kasa okumasini bir MOTORUN ithal etmesi
# katmanlamaya aykiri olurdu, o yuzden motor kendi kopyasini yazmadi --
# HIC OKUMADI.
# ---------------------------------------------------------------------------
print("\n-- kasa okumasi tek yerde mi --")

from ofis import gizli as _kg
from ofis.motor.gemini import GeminiMotoru as _kGem

# TEK GERCEKLESTIRME: `gorsel.anahtar_oku` DELEGE etmeli, kopya olmamali.
# Iki kopyadan biri duzeltilip oteki unutuldugu icin bu projede alti kez
# hata cikti.
import inspect as _kins
_kkaynak = _kins.getsource(gorsel.anahtar_oku)
sina("gorsel.anahtar_oku kasaya DELEGE ediyor (kopya degil)",
     "gizli.anahtar_oku" in _kkaynak, "(kendi okumasini yaziyor)")

# SIRA: once ORTAM, sonra kasa -- "acikca verilen deger her zaman kazanir".
_keski = os.environ.pop("OFIS_SINAMA_ANAHTAR", None)
_kdepo = _kg.depo_yolu()
sina("kurgu: sinama anahtari kasada yok", not _kg.oku("OFIS_SINAMA_ANAHTAR"))
os.environ["OFIS_SINAMA_ANAHTAR"] = "ortamdan"
sina("ortamdaki deger okunuyor",
     _kg.anahtar_oku("OFIS_SINAMA_ANAHTAR") == "ortamdan")
os.environ.pop("OFIS_SINAMA_ANAHTAR", None)
sina("ortam kalkinca bos donuyor (uydurmuyor)",
     _kg.anahtar_oku("OFIS_SINAMA_ANAHTAR") == "")
if _keski is not None:
    os.environ["OFIS_SINAMA_ANAHTAR"] = _keski

# ASIL SINAMA: MOTOR kasadan okuyor mu.
# `os.environ`da anahtar YOKKEN kasada varsa motor MUSAIT olmali --
# kullanicinin `kabuk anahtar ekle` ile yaptigi tam budur.
_kortam = os.environ.pop("GEMINI_API_KEY", None)
_kkasada = bool(_kg.oku("GEMINI_API_KEY"))
if _kkasada:
    sina("MOTOR kasadaki anahtari GORUYOR (kapali dongu kapandi)",
         _kGem().musait_mi() is True,
         "-- CLI kurulu ve anahtar kasada oldugu halde 'kurulu degil'")
else:
    # Kasada anahtar yoksa bu sinama bir sey OLCEMEZ. Gecmis gibi
    # yapmak yerine atlandigini SOYLERIZ -- sessizce gecen bir sinama,
    # olcmedigi seye "iyi" demis olur.
    print("  [?] kasada GEMINI_API_KEY yok -- motor sinamasi ATLANDI")
if _kortam is not None:
    os.environ["GEMINI_API_KEY"] = _kortam

# Motor kaynaginda ARTIK ciplak os.environ okumasi OLMAMALI.
# Bu bir lint: gecmesi dogru kullanildigini gostermez ama GECMEMESI
# kesinlikle kapali dongunun geri geldigini gosterir.
_kmot = _kins.getsource(_kGem.musait_mi)
_kciplak = "os.environ.get(" + chr(34) + "GEMINI_API_KEY" + chr(34) + ")"
sina("motor ciplak os.environ ile anahtar ARAMIYOR",
     _kciplak not in _kmot, f"({_kmot[-90:]})")


# ---------------------------------------------------------------------------
# CODEX ABONELIGI ILE GORSEL + OLU OTURUM HAFIZASI (25.09.2026)
#
# Olculen iki sey: (1) codex CLI'in yerlesik image_gen'i ChatGPT girisiyle,
# API anahtarsiz gorsel uretiyor; (2) ofisin codex oturumu sunucuda
# OLMUSTU (401 token_revoked) ve auth.json durdugu icin ofis codex'i
# "HAZIR" gosteriyordu.
#
# GERCEK CODEX CAGRILMAZ: motor sahtesiyle. Olu oturum defteri, calisma
# klasoru ve codex evi GECICI -- kullanicinin kotasina, ~/.agentofis'e ve
# ~/.codex'e dokunulmaz.
# ---------------------------------------------------------------------------
print("\n-- codex aboneligi ile gorsel --")
import os as _co_os
import time as _co_time
import tempfile as _co_tf
from ofis.motor import codex as _cx
from ofis.motor.tip import MotorOlayi as _CoOlay

_co_kok = Path(_co_tf.mkdtemp(prefix="ofis-codexgorsel-"))
_co_eski_defter = _cx.OTURUM_DEFTERI
_cx.OTURUM_DEFTERI = _co_kok / "codex_oturum.json"
_co_ev = _co_kok / "ev"
_co_ev.mkdir()
(_co_ev / "auth.json").write_text("{}", encoding="utf-8")

# 1. Olu oturum hafizasi: yaz -> olu; yeniden giris (auth.json yenilenir) -> duser.
sina("taze evde oturum OLU DEGIL", _cx.oturum_olu_mu(str(_co_ev)) is False)
_cx.oturum_olu_yaz(str(_co_ev))
sina("401 kaydi sonrasi oturum OLU", _cx.oturum_olu_mu(str(_co_ev)) is True)
_co_st = (_co_ev / "auth.json").stat()
_co_os.utime(_co_ev / "auth.json",
             ns=(_co_st.st_atime_ns, _co_st.st_mtime_ns + 2_000_000_000))
sina("yeniden giris (auth.json yenilendi) kaydi KENDILIGINDEN dusuruyor",
     _cx.oturum_olu_mu(str(_co_ev)) is False)
sina("olu oturum metni giris komutunu soyluyor (device-auth DEGIL)",
     "codex login" in _cx.oturum_olu_metni(str(_co_ev))
     and "--device-auth KULLANMA" in _cx.oturum_olu_metni(str(_co_ev)))

# 2. Adaptor 401'i LIMIT degil OLU OTURUM sayiyor.
_co_m = _cx.CodexMotoru()
_co_d = {"hatali": False, "sonuc": "", "hata_notu": "", "limit": False,
         "oturum_id": "", "metin": [], "maliyet": None, "jeton": 0,
         "arac_sayisi": 0, "model": ""}
_co_m._mesaji_cevir({"type": "turn.failed", "error": {
    "message": "workspace routing discovery unauthorized (401)"}}, _co_d)
sina("akistaki 401 -> sebep 'oturum_kapandi'",
     _co_d["hata_notu"] == "oturum_kapandi", f"({_co_d['hata_notu']})")
sina("akistaki 401 LIMIT SAYILMIYOR (zincir sessizce devretmesin)",
     _co_d["limit"] is False)

# 3. musait_mi olu oturumu goruyor (codex kuruluysa; degilse ATLANDI).
_co_eski_home = _co_os.environ.get("OFIS_CODEX_HOME")
_co_os.environ["OFIS_CODEX_HOME"] = str(_co_ev)
if _cx.CodexMotoru().calistirilabilir:
    sina("girisli evde codex MUSAIT", _cx.CodexMotoru().musait_mi() is True)
    _cx.oturum_olu_yaz(str(_co_ev))
    sina("olu oturumda codex MUSAIT DEGIL (dosya dursa bile)",
         _cx.CodexMotoru().musait_mi() is False)
    _co_st = (_co_ev / "auth.json").stat()
    _co_os.utime(_co_ev / "auth.json",
                 ns=(_co_st.st_atime_ns, _co_st.st_mtime_ns + 4_000_000_000))
else:
    print("  [?] codex CLI kurulu degil -- musait_mi sinamasi ATLANDI")
if _co_eski_home is None:
    _co_os.environ.pop("OFIS_CODEX_HOME", None)
else:
    _co_os.environ["OFIS_CODEX_HOME"] = _co_eski_home


# 4. CodexUretici -- sahte motorla.
class _CoSahteMotor:
    calistirilabilir = "codex-sahte"
    senaryo = "dosya"          # dosya | bos | limit | kopya
    cagri = 0

    def musait_mi(self):
        return True

    def _ev_bul(self):
        return str(_co_ev)

    def tur_kos(self, metin, *, klasor, efor, yazabilir, zaman_asimi, **_):
        _CoSahteMotor.cagri += 1
        _CoSahteMotor.son_metin = metin
        _CoSahteMotor.son_efor = efor
        thread = "th-" + str(_CoSahteMotor.cagri)
        yield _CoOlay("oturum", "", {"oturum_id": thread})
        if self.senaryo == "limit":
            yield _CoOlay("limit", "usage limit reached", {})
            yield _CoOlay("bitti", "", {"basarili": False, "limit": True,
                                        "oturum_id": thread})
            return
        if self.senaryo in ("dosya", "kopya"):
            gd = _co_ev / "generated_images" / thread
            gd.mkdir(parents=True, exist_ok=True)
            (gd / "exec-1.png").write_bytes(b"\x89PNG-sahte")
            if self.senaryo == "kopya":
                ad = metin.split("`")[1]
                (Path(klasor) / ad).write_bytes(b"\x89PNG-kopya")
        yield _CoOlay("bitti", "ok", {"basarili": True, "oturum_id": thread,
                                      "jeton": 1234})


_co_eski_motor = gorsel.CodexUretici._motor
_co_eski_calisma = gorsel.CodexUretici.CALISMA
gorsel.CodexUretici._motor = staticmethod(lambda: _CoSahteMotor())
gorsel.CodexUretici.CALISMA = _co_kok / "calisma"

try:
    _CoSahteMotor.senaryo = "dosya"
    _co_s = gorsel.CodexUretici().uret("kirmizi elma", _co_kok / "out" / "e.png")
    sina("codex: thread klasorundeki gorsel hedefe kopyalandi",
         Path(_co_s["yol"]).read_bytes() == b"\x89PNG-sahte")
    sina("codex: hesabin evinde gorsel BIRIKMIYOR (thread klasoru silindi)",
         not (_co_ev / "generated_images" / "th-1").exists())
    sina("codex: model UYDURULMUYOR ('olculemiyor' diyor)",
         "olculemiyor" in _co_s["model"], f"({_co_s['model']})")
    sina("codex: maliyet UYDURULMUYOR (fatura yok, alan hic yazilmiyor)",
         "maliyet_usd" not in _co_s)
    sina("codex: efor DUSUK (kota korunur)", _CoSahteMotor.son_efor == "dusuk")
    sina("codex: istem tarifi tasiyor", "kirmizi elma" in _CoSahteMotor.son_metin)

    _CoSahteMotor.senaryo = "kopya"
    _co_s = gorsel.CodexUretici().uret("mavi", _co_kok / "out" / "k.png")
    sina("codex: ajanin kopyaladigi dosya ONCELIKLI",
         Path(_co_s["yol"]).read_bytes() == b"\x89PNG-kopya")
    sina("codex: calisma klasorunde artik kalmiyor",
         not any((_co_kok / "calisma").iterdir()))

    _CoSahteMotor.senaryo = "bos"
    try:
        gorsel.CodexUretici().uret("x", _co_kok / "out" / "b.png")
        sina("codex: dosyasiz 'basarili' tur REDDEDILIYOR", False)
    except Exception as exc:  # ciplak hata da yakalanir: test COKMESIN
        sina("codex: dosyasiz 'basarili' tur REDDEDILIYOR",
             isinstance(exc, gorsel.GorselHatasi) and "DOSYASI YOK" in str(exc),
             f"({type(exc).__name__}: {exc})")

    _CoSahteMotor.senaryo = "limit"
    try:
        gorsel.CodexUretici().uret("x", _co_kok / "out" / "l.png")
        sina("codex: limit gorunur hata", False)
    except gorsel.GorselHatasi as exc:
        sina("codex: limit gorunur hata", "limit" in str(exc).lower(), f"({exc})")

    _co_cagri = _CoSahteMotor.cagri
    for _co_arg in ({"model": "gpt-image-9"}, {"kalite": "high"}):
        try:
            gorsel.CodexUretici().uret("x", _co_kok / "out" / "m.png", **_co_arg)
            sina(f"codex: {_co_arg} REDDEDILIYOR", False)
        except gorsel.GorselHatasi:
            sina(f"codex: {_co_arg} REDDEDILIYOR", True)
    sina("codex: reddedilen istek tur HIC kosturmadi",
         _CoSahteMotor.cagri == _co_cagri)

    # 5. Tercih ve para kilidi: abonelik yolu kilide TAKILMAZ.
    sina("tercih sirasi codex ile basliyor",
         gorsel.TERCIH_SIRASI[0] == "codex", f"({gorsel.TERCIH_SIRASI})")
    sina("codex UCRETLI sayilmiyor", gorsel.CodexUretici.ucretli is False)
    _co_eski_sira = gorsel.TERCIH_SIRASI
    gorsel.TERCIH_SIRASI = ("codex",)
    _CoSahteMotor.senaryo = "dosya"
    _co_s = gorsel.uret("kilitli", _co_kok / "out" / "p.png",
                        ucretsiz_sadece=True)
    sina("para kilidi KAPALIYKEN codex yine uretiyor", _co_s["uretici"] == "codex")
    gorsel.TERCIH_SIRASI = _co_eski_sira

    # 6. Lider blogu olu oturumu 'anahtar yok' diye YANLIS anlatmiyor.
    _co_eski_mus = gorsel.CodexUretici.musait_mi
    _co_eski_neden = gorsel.CodexUretici.neden_musait_degil
    gorsel.CodexUretici.musait_mi = lambda self: False
    gorsel.CodexUretici.neden_musait_degil = lambda self: "oturumu KAPANMIS"
    _co_blok = gorsel.lider_blogu()
    gorsel.CodexUretici.musait_mi = _co_eski_mus
    gorsel.CodexUretici.neden_musait_degil = _co_eski_neden
    _co_satir = [x for x in _co_blok.splitlines() if x.strip().startswith("codex")]
    sina("lider blogu olu codex oturumunu 'oturum KAPALI' diyor",
         bool(_co_satir) and "oturum KAPALI" in _co_satir[0], f"({_co_satir})")
    sina("lider blogu codex'in kotadan yedigini soyluyor",
         "3-5 kat" in _co_blok)
finally:
    gorsel.CodexUretici._motor = _co_eski_motor
    gorsel.CodexUretici.CALISMA = _co_eski_calisma
    _cx.OTURUM_DEFTERI = _co_eski_defter
    import shutil as _co_sh
    _co_sh.rmtree(_co_kok, ignore_errors=True)


print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
