# -*- coding: utf-8 -*-
"""Gorsel uretme: istemi YARGI yapan yazar, gorseli URETEBILEN uretir.

Kullanicinin anlattigi gercek akis (19.09.2026):

    *"ben normalde promptu Claude ile yazdiriyorum, GPT ile gorsel
    uretecegim diyorum, konusuyoruz, Claude'un verdigi promptu GPT'ye
    yapistiriyorum, gorseli olusturuyor."*

Yapistirma adimi insanin isi olmamali. Ofiste: lider (ya da icerik
ajani) istemi yazar, `gorsel_uret` cagrilir, dosya diske duser ve
KANIT olur.

## Bu bir MOTOR DEGILDIR

Motor tur kosturur: oturum tasir, arac cagirir, kanit uretir, nabiz
atar. Gorsel uretme bunlarin hicbirini yapmaz -- **tek cagri, tek
cikti**. `ofis/motor/` altina koymak, motor sozlesmesini (sekiz
parametre, akis, `bitti` olayi) anlamsiz yere bu ise dayatirdi.

Bu yuzden ayri bir katman ve ayri bir sozlesme: `Uretici`.

## Neden ofis surecinde kosar, ajan turunda degil

Anahtar ajanin ortamina GIRMEZ (bkz. `motor/tip.py` SIR_ONEKLERI).
Ajan `gorsel_uret` aracini cagirir; uretim ofisin kendi surecinde olur
ve ajana yalnizca DOSYA YOLU doner. Boylece:

* anahtar ajanin `echo $...` erisimine hic girmez,
* uretim tek yerden olculur (hangi uretici, hangi model, kac deneme),
* uretici degistiginde ajan brifingi degismez.

## Saglayici FISE TAKILIR

Bugun Gemini calisiyor (olculdu: anahtar 7 gorsel modeli aciyor).
OpenAI'in GORSEL API'si icin ChatGPT Plus YETMEZ -- olculdu:
`auth_mode=chatgpt`, `OPENAI_API_KEY` yok, org yok.

AMA ABONELIK YOLU VAR (25.09.2026, olculdu): codex CLI'in yerlesik
`image_gen` araci ChatGPT girisiyle, API anahtarsiz gorsel uretiyor;
bedeli Codex kullanim kotasindan duser. `CodexUretici` bunu kullanir.
Daha once "ChatGPT aboneligiyle ajanda gorsel uretilemez" diye
yazmistim -- `codex features list` tam okunmadan kurulmus yanlis bir
hukumdu.

**Anahtari olmayan uretici SESSIZCE atlanmaz**, "musait degil" der ve
sebebini soyler. Sessizce atlanan saglayici, "neden hep Gemini
kullaniyor" sorusunu cevapsiz birakir.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from .yollar import OFIS_EVI

#: Tek bir uretim denemesinin ust siniri. Gorsel uretimi saniyeler surer;
#: dakikalarca bekleyen bir cagri, cagiran ajani da bekletir.
ZAMAN_ASIMI = 180.0


def anahtar_oku(ad: str) -> str:
    """Bir API anahtarini OFISIN KASASINDAN, yoksa ortamdan okur.

    OLCULMUS HATA (20.09.2026): `GEMINI_API_KEY` kasada duruyordu
    (`gizli.liste()` onu gosteriyordu) ama `musait_ureticiler()`
    *"kurulu degil"* diyordu -- cunku bu dosya YALNIZCA `os.environ`a
    bakiyordu ve kasaya hic bakmiyordu.

    Hatanin kapali bir dongusu vardi: uretici *"`kabuk anahtar ekle`
    calistir"* diyordu, o komut anahtari KASAYA yaziyordu, kod ise
    kasayi hic okumuyordu. **Ofis, kendi verdigi talimat izlendiginde
    bile calismiyordu.**

    Sira: once ORTAM, sonra kasa.

    Ilk yazisinda TERS koymustum (once kasa) ve **sinama yakaladi**:
    `duman_gorsel.py` 6. bolum anahtari `os.environ`a koyup "anahtar
    hata metnine sizmasin" diye olcuyor. Kasa oncelikli olunca kod
    kasadaki GERCEK anahtari maskeledi, testin koydugu anahtar
    maskesiz gecti -- yani sinamanin kurdugu sahne artik olcmek
    istedigi seye ulasamiyordu.

    Dogru sira ofisin kendi kuralindan geliyor: *"acikca verilen deger
    HER ZAMAN kazanir; varsayilan bir dayatma degildir"* (rolun turu,
    zincirin ilk basamagi -- ayni ilke). Ortam degiskeni o sureç icin
    ACIKCA verilmis bir degerdir; kasa ise kalici VARSAYILAN.

    Bu ayrica testi yeniden YALITILABILIR yapiyor: kullanicinin gercek
    kasasi bir sinamanin sonucunu degistiremez. *Deterministik olmayan
    test, sinadigi seyi degil kendini olcer.*

    Tek bir yardimci: her uretici bunu cagirir. Her uretici kendi
    okumasini yazsaydi, yarin eklenen bir saglayici ayni bosluğu
    yeniden acardi -- bu dosyada bu hata zaten UC uretici birden
    tasiyordu.

    Deger DONDURULUR ama hicbir yere YAZILMAZ: kasa proje kokunun
    disindadir cunku ajanlarin `Bash(cat *)` izni var.
    """
    # GERCEKLESTIRME `gizli.py`YE TASINDI ve burasi DELEGE ediyor.
    # Sebep olculdu: ayni okuma `motor/gemini.py`de de gerekiyordu ve
    # bir MOTORUN gorsel modulunu ithal etmesi katmanlamaya aykiriydi
    # -- o yuzden motor kendi kopyasini yazmadi, HIC OKUMADI ve ayni
    # kapali dongu ikinci kez cikti. Kasa sorusunun cevabi kasanin
    # modulunde durmali. Ad burada KALIYOR: sinamalar ve ureticiler
    # bunu ithal ediyor.
    try:
        from ofis import gizli
        return gizli.anahtar_oku(ad)
    except Exception:
        # Kasa okunamiyorsa (dosya yok, izin yok) SESSIZ kalmayiz:
        # cagiran `musait_mi` "kurulu degil" diyecek ve sebep gorunecek.
        return ""


#: Kota hafizasi. Proje kokunun DISINDA, kasayla ayni klasorde: bu bir
#: calisma durumu, proje verisi degil -- ve ofis kurulmadan da (`kabuk
#: gorsel durum`) okunabilmeli.
KOTA_DEFTERI = OFIS_EVI / "kota.json"

#: Kota kaydinin "taze" sayildigi sure. Ucretsiz kotalar gunluk
#: yenilenir; 12 saatten eski bir kayit bugunku hali SOYLEMEZ ve
#: gosterilmesi yaniltir.
KOTA_TAZE_SANIYE = 12 * 3600


def kota_yaz(uretici: str, gunluk: bool) -> None:
    """Kota dolduguna dair OLCUMU kaydeder.

    OLCULMUS HATA (21.09.2026): `musait_ureticiler()` gemini icin
    `musait=True` diyordu ve `kabuk gorsel durum` **MUSAIT** basiyordu
    -- ama gunluk kota doluydu ve saglayici hicbir sey uretemiyordu.

    Sebep: `musait_mi()` yalnizca ANAHTARIN VARLIGINI olcuyor. Anahtarin
    olmasi ile URETEBILIYOR olmak ayri iki seydir, ve gosterge ikincisini
    iddia ediyordu.

    > Yanlis gosteren bir gosterge, gostergesizlikten kotudur.

    Kotayi her `durum` cagrisinda OLCEMEYIZ: olcmek bir istek harcar ve
    ucretsiz kotayi daha da tuketir. O yuzden **tahmin etmiyoruz, hatirl-
    iyoruz**: gercek bir uretim denemesi kotaya carparsa o an yazilir ve
    gosterge "anahtar var, ama N dk once kota doluydu" der.

    `saglik.py` kurali: olcemedigimize hukum vermeyiz, sessiz de kalmayiz.
    """
    try:
        KOTA_DEFTERI.parent.mkdir(parents=True, exist_ok=True)
        veri = {}
        if KOTA_DEFTERI.is_file():
            veri = json.loads(KOTA_DEFTERI.read_text(encoding="utf-8")) or {}
        veri[uretici] = {"an": time.time(), "gunluk": bool(gunluk)}
        gecici = KOTA_DEFTERI.with_suffix(".json.tmp")
        gecici.write_text(json.dumps(veri, ensure_ascii=False),
                          encoding="utf-8")
        gecici.replace(KOTA_DEFTERI)
    except (OSError, ValueError):
        # Hafiza tutulamiyorsa is DURMAZ -- bu bir kolaylik, bir kapi
        # degil. Yazamamak, uretimi engellememelidir.
        pass


def kota_notu(uretici: str) -> str:
    """Son kota olcumunun insan diliyle hali -- yoksa bos dize."""
    try:
        if not KOTA_DEFTERI.is_file():
            return ""
        kayit = (json.loads(KOTA_DEFTERI.read_text(encoding="utf-8"))
                 or {}).get(uretici)
        if not kayit:
            return ""
        yas = time.time() - float(kayit.get("an") or 0)
        if yas > KOTA_TAZE_SANIYE:
            return ""      # bayat kayit bugunku hali SOYLEMEZ
        dk = int(yas // 60)
        ne_zaman = f"{dk} dk once" if dk < 90 else f"{dk // 60} saat once"
        return ("GUNLUK kota doluydu" if kayit.get("gunluk")
                else "dakikalik kota doluydu") + f" ({ne_zaman})"
    except (OSError, ValueError):
        return ""


#: Ofis ayarlari. Kotayla ayni klasorde ve ayni sebeple: bu bir calisma
#: durumu, proje verisi degil -- ve `gorsel.py` bilerek ofisten
#: BAGIMSIZDIR (veritabanina baglamak onu ofise baglardi).
AYAR_DEFTERI = OFIS_EVI / "ayar.json"


def ucretsiz_sadece_mi() -> bool:
    """Ofis para harcayabilir mi. VARSAYILAN: HAYIR, harcayamaz.

    Kullanicinin kisiti (21.09.2026): *"openrouter hesabimda bakiye var
    baska bot icin kullaniyorum, sadece free -- para kesmiycek."*

    Bu ifade edilemiyordu. `TERCIH_SIRASI` ucretsiz gemini'den UCRETLI
    openrouter'a duser; anahtar eklendigi an bir sonraki uretim baska
    bir botun bakiyesinden keserdi ve bunu SOYLEYEN hicbir sey yoktu.

    OLCULDU (21.09.2026, openrouter.ai/api/v1/models): gorsel cikti
    veren **11 modelin HEPSI ucretli**; OpenRouter'da bedava gorsel
    modeli YOK. Yani "openrouter ekleyelim ama ucretsizini kullanalim"
    diye bir yol yok -- ancak ODEMEK ya da HIC KULLANMAMAK var.

    VARSAYILAN NEDEN KAPALI: para harcamak ACIK bir tercih olmali.
    Ofisin kendi kurali: *para kontrolleri KAPALI KALARAK basarisiz
    olur.* Yanlis yonde yanilmanin bedeli farkli: kapaliyken yanilmak
    "uretemedim" der, acikken yanilmak fatura yazar.
    """
    ortam = (os.environ.get("OFIS_PARA_HARCA") or "").strip().lower()
    if ortam:
        return ortam not in ("1", "acik", "evet", "true")
    try:
        if AYAR_DEFTERI.is_file():
            veri = json.loads(AYAR_DEFTERI.read_text(encoding="utf-8")) or {}
            return not bool(veri.get("para_harca"))
    except (OSError, ValueError):
        pass
    return True


def para_harca_ayarla(acik: bool) -> None:
    """Para harcamayi acar/kapatir. Acan kisi neyi kabul ettigini gorur."""
    veri = {}
    try:
        if AYAR_DEFTERI.is_file():
            veri = json.loads(AYAR_DEFTERI.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        veri = {}
    veri["para_harca"] = bool(acik)
    AYAR_DEFTERI.parent.mkdir(parents=True, exist_ok=True)
    gecici = AYAR_DEFTERI.with_suffix(".json.tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    gecici.replace(AYAR_DEFTERI)


#: Ucretli bir uretici para kilidi acikken istendiginde verilen metin.
#: Sebebi ve CARESI birlikte: teshis koyup care soylemeyen gosterge,
#: insani bir kez daha dusunmeye zorlar.
PARA_KILIDI_METNI = (
    "PARA KILIDI ACIK: '{ad}' ucretli ve ofis su an para harcamiyor.\n"
    "  Bu kilit bilerek VARSAYILAN: harcamak acik bir tercih olmali.\n"
    "  Acmak icin: `python -m ofis.kabuk gorsel para ac`\n"
    "  (tek seferlik: `--para-harca`)")


class GorselHatasi(RuntimeError):
    pass


class ParaKilidi(GorselHatasi):
    """Ucretli uretici istendi ama para kilidi acik.

    AYRI SINIF, cunku cagiran bunu gercek bir hatadan AYIRT edebilmeli:
    bu bir ariza degil bir KARAR. Tek sinif olsaydi ajan "tekrar dene"
    der ve kilit bir yavaslatmaya donusurdu -- `video.ButceAsimi` ile
    ayni gerekce.
    """


class Uretici:
    """Gorsel ureticisinin sozlesmesi. Motor sozlesmesinden AYRIDIR."""

    ad = ""
    #: Uretici para harciyor mu? Ucretsiz kotayla calisan ile fatura
    #: kesen ayni sey degildir; insan hangisini kullandigini gormeli.
    ucretli = False

    def musait_mi(self) -> bool:
        raise NotImplementedError

    def neden_musait_degil(self) -> str:
        """Musait DEGILSE sebebi. Sessiz atlama yasak."""
        return "bilinmiyor"

    def uret(self, istem: str, hedef: Path, *, model: str = "",
             kalite: str = "") -> dict:
        """`kalite` destegi ureticiye baglidir; desteklemeyen YOK SAYMAZ,
        gormezden gelmek yerine acikca bildirir (bkz. Gemini)."""
        raise NotImplementedError


class GeminiUretici(Uretici):
    """Google AI Studio anahtariyla gorsel uretir.

    OLCULDU (19.09.2026): anahtar su modelleri aciyor --
    gemini-3-pro-image · gemini-3.1-flash-image ·
    gemini-3.1-flash-lite-image · gemini-2.5-flash-image ·
    nano-banana-pro-preview

    Ucretsiz katmanda UC AYRI kota var (olculdu, tahmin degil):
    dakika basina jeton · dakika basina istek · GUNLUK istek. Dolunca
    429 + `RESOURCE_EXHAUSTED` doner. Bu bir hata degil, kaynagin
    tukenmesidir -- tipki motor limitinde oldugu gibi; ama cari
    dakikalik kota ile GUNLUK kota ayni sey degildir: birinde 20 saniye
    beklemek yeter, otekinde bugun bitmistir. `_kota_mesaji` hangisinin
    dolduğunu API'nin kendi yanitindan okur.
    """

    ad = "gemini"
    ucretli = False
    VARSAYILAN_MODEL = "gemini-3.1-flash-image"

    def musait_mi(self) -> bool:
        return bool(anahtar_oku("GEMINI_API_KEY"))

    def neden_musait_degil(self) -> str:
        return ("GEMINI_API_KEY kurulu degil. "
                "`python -m ofis.kabuk anahtar ekle GEMINI_API_KEY`")

    def uret(self, istem: str, hedef: Path, *, model: str = "",
             kalite: str = "") -> dict:
        # Gemini'de kalite kademesi YOK. Sessizce yutmak, kullanicinin
        # "yuksek kalite istedim" sanmasina yol acar -- sessizce yok
        # sayilan ayar, ayar degildir.
        if kalite:
            raise GorselHatasi(
                f"Gemini kalite kademesi almiyor ({kalite}). Kaliteyi "
                "kaldir ya da `--uretici openai` kullan "
                "(low/medium/high/xhigh/max).")
        anahtar = anahtar_oku("GEMINI_API_KEY")
        if not anahtar:
            raise GorselHatasi(self.neden_musait_degil())
        model = model or self.VARSAYILAN_MODEL
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={anahtar}")
        govde = {"contents": [{"parts": [{"text": istem}]}]}
        istek = urllib.request.Request(
            url, data=json.dumps(govde).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
                d = json.load(yanit)
        except urllib.error.HTTPError as exc:
            ham = ""
            try:
                ham = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            # ANAHTAR HATA METNINE SIZMASIN: url'de anahtar var.
            ham = ham.replace(anahtar, "<ANAHTAR>")
            kota = exc.code == 429 or "RESOURCE_EXHAUSTED" in ham
            if kota:
                mesaj = self._kota_mesaji(ham)
                # OLCUMU KAYDET. Bir sonraki `durum`/`yetenek` cagrisi
                # "MUSAIT" diye yalan soylemesin: anahtarin olmasi ile
                # URETEBILIYOR olmak ayri iki seydir.
                kota_yaz(self.ad, "GUNLUK" in mesaj)
                raise GorselHatasi(mesaj) from None
            raise GorselHatasi(
                f"Gemini reddetti ({exc.code}): {ham[:300]}") from None
        except Exception as exc:
            raise GorselHatasi(f"Gemini'ye ulasilamadi: {exc}") from None

        adaylar = d.get("candidates") or []
        if not adaylar:
            raise GorselHatasi("Gemini hicbir sonuc dondurmedi.")
        metin = []
        for parca in (adaylar[0].get("content") or {}).get("parts") or []:
            if "inlineData" in parca:
                ham = base64.b64decode(parca["inlineData"]["data"])
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_bytes(ham)
                return {"uretici": self.ad, "model": model,
                        "yol": str(hedef), "bayt": len(ham),
                        "tip": parca["inlineData"].get("mimeType", "")}
            if "text" in parca:
                metin.append(str(parca["text"]))
        # GORSEL YERINE METIN DONDU. Bu SESSIZCE basari sayilmaz:
        # cagiran "gorsel uretildi" sanip olmayan bir dosyaya kanit yazar.
        raise GorselHatasi(
            "Gemini gorsel yerine metin dondurdu: "
            + (" ".join(metin)[:300] or "(bos)"))


    @staticmethod
    def _kota_mesaji(ham: str) -> str:
        """Kota hatasini API'NIN KENDI SOYLEDIGIYLE anlatir.

        Ilk surum "dakika basina sinirli" diye TAHMIN ediyordu. Olculunce
        uc ayri kota cikti ve biri GUNLUK:

            GenerateContentInputTokensPerModelPerMinute-FreeTier
            GenerateRequestsPerMinutePerProjectPerModel-FreeTier
            GenerateRequestsPerDayPerProjectPerModel-FreeTier

        Fark onemli: dakikalik kotada 20 saniye beklemek yeter, GUNLUK
        kotada beklemek bugun ise yaramaz. Yanlis tesis edilen bir umut,
        kullaniciyi bosuna bekletir. API ayrica `retryDelay` doner --
        tahmin etmek yerine ONU soyluyoruz.
        """
        try:
            d = json.loads(ham)
        except Exception:
            return ("Gemini kotasi doldu (ayrinti okunamadi). "
                    "Biraz bekleyip tekrar dene.")
        gecikme = ""
        kotalar = []
        for det in (d.get("error", {}).get("details") or []):
            tip = str(det.get("@type", ""))
            if "RetryInfo" in tip:
                gecikme = str(det.get("retryDelay") or "")
            if "QuotaFailure" in tip:
                kotalar += [str(v.get("quotaId") or "")
                            for v in (det.get("violations") or [])]
        gunluk = any("PerDay" in k for k in kotalar)
        satir = ["Gemini ucretsiz kotasi doldu."]
        if kotalar:
            satir.append("  dolan kotalar: " + ", ".join(sorted(set(kotalar))))
        if gunluk:
            satir.append("  GUNLUK kota da dolmus -- beklemek bugun ise "
                         "yaramayabilir.")
        if gecikme:
            satir.append(f"  API'nin onerdigi bekleme: {gecikme}")
        satir.append("  Secenekler: bekle · ucretli katmana gec · "
                     "`--uretici openai` (OPENAI_API_KEY gerekir).")
        return chr(10).join(satir)


class OpenAIUretici(Uretici):
    """OpenAI gorsel API'siyle uretir -- AYRI bir API anahtari ister.

    OLCULDU (19.09.2026): kullanicinin ChatGPT **Plus** aboneligi API
    erisimi VERMIYOR. Codex kimligi `auth_mode=chatgpt`, `OPENAI_API_KEY`
    yok, organizasyon yok. ChatGPT uygulamasinda gorsel uretmek ile API
    ile uretmek AYRI urunlerdir ve ayri faturalanir.

    Bu yuzden uretici burada duruyor ama anahtar gelene kadar "musait
    degil" diyor -- ve SEBEBINI soyluyor. Sessizce yok saymak,
    kullanicinin "neden GPT kullanilmiyor" sorusunu cevapsiz birakirdi.
    """

    ad = "openai"
    ucretli = True          # gorsel basina ucret; ucretsiz kota yok
    # GUNCEL MODEL -- 20.09.2026'da resmi belgeden DOGRULANDI.
    #
    # Iki kez yanlis yazdim ve ikisinin de sebebi ayni: ikincil kaynaga
    # guvenip BIRINCIL kaynaga bakmamak.
    #   1. `gpt-image-1`   -> 23 Ekim 2026'da emekli oluyor
    #   2. `gpt-image-1.5` -> zaten gecmisti; GPT Image 2.5 8 Eylul'de cikmis
    #
    # Emekliye ayrilmis bir modele baglanan varsayilan, tarihi gelince
    # SESSIZCE bozulur: kod degismez, hata gecikmeli gelir ve sebebi
    # gorunmez. Bu projenin karsi kuruldugu hata sinifi.
    #
    # developers.openai.com/api/docs/models/gpt-image-2.5-flare (dogrulandi):
    #   model id : gpt-image-2.5-flare · gpt-image-2.5-sunburst
    #   endpoint : v1/images/generations · v1/images/edits
    #   kalite   : low · medium · high · xhigh · max · auto
    #   fiyat    : metin girdi $5/1M · gorsel girdi $8/1M · CIKTI $30/1M
    #
    # `flare` varsayilan: "hizli, gunluk yuksek kalite". `sunburst` daha
    # detayli ama yavas -- isteyen `--model` ile secer.
    VARSAYILAN_MODEL = "gpt-image-2.5-flare"

    #: Kalite MALIYETI belirler; varsayilan `auto` degil `medium`.
    #: `auto` modelin sectigi kalite demektir ve fatura ongorulemez olur
    #: -- para kontrolleri tahmin edilebilir kalmali.
    VARSAYILAN_KALITE = "medium"
    KALITELER = ("low", "medium", "high", "xhigh", "max", "auto")

    def musait_mi(self) -> bool:
        return bool(anahtar_oku("OPENAI_API_KEY"))

    def neden_musait_degil(self) -> str:
        return ("OPENAI_API_KEY kurulu degil. DIKKAT: ChatGPT Plus "
                "aboneligi API erisimi VERMEZ (olculdu: auth_mode=chatgpt, "
                "org yok). platform.openai.com'dan ayri bir API anahtari "
                "alinmali -- gorsel basina ucretlidir. Sonra: "
                "`python -m ofis.kabuk anahtar ekle OPENAI_API_KEY`")

    def uret(self, istem: str, hedef: Path, *, model: str = "",
             kalite: str = "") -> dict:
        anahtar = anahtar_oku("OPENAI_API_KEY")
        if not anahtar:
            raise GorselHatasi(self.neden_musait_degil())
        model = model or self.VARSAYILAN_MODEL
        kalite = kalite or self.VARSAYILAN_KALITE
        if kalite not in self.KALITELER:
            raise GorselHatasi(
                f"Bilinmeyen kalite: {kalite}. "
                f"Secenekler: {', '.join(self.KALITELER)}")
        istek = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=json.dumps({"model": model, "prompt": istem,
                             "quality": kalite, "n": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {anahtar}"})
        try:
            with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
                d = json.load(yanit)
        except urllib.error.HTTPError as exc:
            ham = ""
            try:
                ham = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            ham = ham.replace(anahtar, "<ANAHTAR>")
            raise GorselHatasi(f"OpenAI reddetti ({exc.code}): {ham[:300]}") from None
        except Exception as exc:
            raise GorselHatasi(f"OpenAI'ye ulasilamadi: {exc}") from None

        veri = (d.get("data") or [{}])[0]
        if veri.get("b64_json"):
            ham = base64.b64decode(veri["b64_json"])
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_bytes(ham)
            return {"uretici": self.ad, "model": model, "yol": str(hedef),
                    "bayt": len(ham), "tip": "image/png"}
        if veri.get("url"):
            try:
                with urllib.request.urlopen(veri["url"], timeout=ZAMAN_ASIMI) as r:
                    ham = r.read()
            except Exception as exc:
                raise GorselHatasi(f"Gorsel indirilemedi: {exc}") from None
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_bytes(ham)
            return {"uretici": self.ad, "model": model, "yol": str(hedef),
                    "bayt": len(ham), "tip": "image/png"}
        raise GorselHatasi("OpenAI gorsel dondurmedi.")


class OpenRouterUretici(Uretici):
    """Tek anahtarla cok saglayici -- ve MALIYETI OLCULU dondurur.

    Neden onemli: OpenAI'in kendi belgesi GPT Image 2.5 icin kalite
    basina JETON tablosu YAYINLAMIYOR (20.09.2026'da dogrulandi; sayfa
    "hesaplayiciyi kullanin" diyor, hesaplayici da henuz yok). Ikincil
    kaynaklar GPT Image 2'den TAHMIN uretiyor ve kendileri soyluyor:
    *"planlama araligi, fatura degil."*

    Bu projede tahminle para kontrolu kurmayiz. OpenRouter'in
    `/api/v1/images` uc noktasi yanitta `usage.cost` donduruyor --
    yani gorselin GERCEK maliyeti. Olculen sayi, tahmin edilen sayiyi
    her zaman yener; ustelik model degisince tahmin bayatlar, olcum
    bayatlamaz.

    OLCULDU (20.09.2026, openrouter.ai/api/v1/models): 11 gorsel modeli.
    Jeton basina `image_output` fiyatlari:

        openai/gpt-5-image-mini      $0,000008   (en ucuz OpenAI)
        openai/gpt-5.4-image-2       $0,00003
        openai/gpt-5-image           $0,00004
        google/gemini-3.1-flash-image $0,00006   (Nano Banana 2)
        google/gemini-3-pro-image    $0,00012    (Nano Banana Pro)

    NOT: OpenRouter'da HENUZ `gpt-image-2.5` yok (12 gun onceki surum).
    En yeni OpenAI gorsel modeli `gpt-5.4-image-2`. Olmayan bir modeli
    varsayilan yapmak, ilk cagrida sessizce baska bir seye dusmek
    demektir -- varsayilan, GERCEKTEN listede olandir.
    """

    ad = "openrouter"
    ucretli = True
    VARSAYILAN_MODEL = "openai/gpt-5.4-image-2"
    #: OpenRouter'in kendi kalite kademeleri (belgeden): auto/low/medium/high.
    #: `auto` varsayilan DEGIL: modelin sectigi kalite, ongorulemez fatura.
    VARSAYILAN_KALITE = "medium"
    KALITELER = ("low", "medium", "high", "auto")

    def musait_mi(self) -> bool:
        return bool(anahtar_oku("OPENROUTER_API_KEY"))

    def neden_musait_degil(self) -> str:
        return ("OPENROUTER_API_KEY kurulu degil. Tek anahtarla hem OpenAI "
                "hem Gemini gorsel modellerine erisir ve GERCEK maliyeti "
                "dondurur. `python -m ofis.kabuk anahtar ekle OPENROUTER_API_KEY`")

    def uret(self, istem: str, hedef: Path, *, model: str = "",
             kalite: str = "") -> dict:
        anahtar = anahtar_oku("OPENROUTER_API_KEY")
        if not anahtar:
            raise GorselHatasi(self.neden_musait_degil())
        model = model or self.VARSAYILAN_MODEL
        kalite = kalite or self.VARSAYILAN_KALITE
        if kalite not in self.KALITELER:
            raise GorselHatasi(
                f"Bilinmeyen kalite: {kalite}. "
                f"Secenekler: {', '.join(self.KALITELER)}")

        govde = {"model": model, "prompt": istem, "quality": kalite, "n": 1}
        istek = urllib.request.Request(
            "https://openrouter.ai/api/v1/images",
            data=json.dumps(govde).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {anahtar}"})
        try:
            with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
                d = json.load(yanit)
        except urllib.error.HTTPError as exc:
            ham = ""
            try:
                ham = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            ham = ham.replace(anahtar, "<ANAHTAR>")
            if exc.code == 429:
                raise GorselHatasi(
                    "OpenRouter kotasi/limiti doldu. Bakiyeni ya da hiz "
                    f"limitini kontrol et. {ham[:200]}") from None
            if exc.code in (401, 403):
                raise GorselHatasi(
                    "OpenRouter anahtari reddedildi (yetki). Anahtari "
                    f"yeniden ekle. {ham[:200]}") from None
            raise GorselHatasi(
                f"OpenRouter reddetti ({exc.code}): {ham[:300]}") from None
        except Exception as exc:
            raise GorselHatasi(f"OpenRouter'a ulasilamadi: {exc}") from None

        veriler = d.get("data") or []
        if not veriler or not veriler[0].get("b64_json"):
            raise GorselHatasi(
                "OpenRouter gorsel dondurmedi: "
                + json.dumps(d, ensure_ascii=False)[:300])
        ham = base64.b64decode(veriler[0]["b64_json"])
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(ham)

        # MALIYET OLCULUR, TAHMIN EDILMEZ. Yanit `usage.cost` donduruyor.
        kullanim = d.get("usage") or {}
        sonuc = {"uretici": self.ad, "model": model, "kalite": kalite,
                 "yol": str(hedef), "bayt": len(ham),
                 "tip": veriler[0].get("media_type", "image/png")}
        if kullanim.get("cost") is not None:
            sonuc["maliyet_usd"] = float(kullanim["cost"])
        if kullanim.get("completion_tokens"):
            sonuc["jeton"] = int(kullanim["completion_tokens"])
        return sonuc


class CodexUretici(Uretici):
    """ChatGPT ABONELIGIYLE gorsel -- codex CLI'in yerlesik `image_gen`i.

    OLCULDU (25.09.2026): ofisin codex evinde, `codex exec` ile tek tur:
    codex kendi `imagegen` skill'ini okudu, yerlesik araci cagirdi,
    gorsel `$CODEX_HOME/generated_images/<thread>/` altina dustu, ajan
    onu klasore kopyaladi (1,19 MB). `OPENAI_API_KEY` GEREKMEDI.

    UCRETLI DEGIL -- ama BEDAVA DA DEGIL: fatura kesmez, Codex kullanim
    kotasindan duser ve resmi belgeye gore gorselli bir tur kotayi
    ~3-5 kat hizli yer. Ayni kota codex'li ajanlarin (cinar) da kotasi.

    Uretim ofisin surecinde koser (`gorsel_uret` MCP araci), ajanin
    turunda degil -- modulun ilk kurali. Motor sozlesmesi burada
    **odunc alinir** (`CodexMotoru.tur_kos`): ev hazirligi, surec agaci
    kesme, zaman asimi, olu oturum tespiti ikinci kez yazilmaz.

    MODEL SECILEMEZ: yerlesik arac modeli sunucuda secer (skill ad
    sabitlemiyor). Kullanicinin "hep en guncel" sarti bu yolda
    saglayicinin kendi secimiyle karsilanir. `model` verilirse
    REDDEDILIR -- sessizce yok saymak, "sunu istedim" sanmaya yol acar.
    Akista model adi YOK; hangi modelin kostugu OLCULEMIYOR ve sonuc
    bunu oyle yazar.
    """

    ad = "codex"
    ucretli = False
    #: Olculen tur ~60 sn. Uzun istemde uzayabilir; MCP istemcisinin
    #: kendi zaman asimi olculmedi (video'daki gibi) -- bilinen sinir.
    ZAMAN_ASIMI = 360.0
    #: Proje kokunun DISINDA sabit bir klasor. Her uretimde yeni gecici
    #: klasor acsaydik `_evi_hazirla` her biri icin config.toml'a ayri
    #: bir guven satiri eklerdi ve dosya sisip giderdi.
    CALISMA = OFIS_EVI / "gorsel-codex"
    ISTEM = (
        "Yerlesik gorsel uretme aracini (image_gen) kullanarak ASAGIDAKI "
        "tarif icin TEK bir gorsel uret. Kod yazma, betik calistirma, API "
        "anahtari kullanma. Uretilen gorsel dosyasini calisma klasorune "
        "`{ad}` adiyla KOPYALA. Sonunda yalnizca dosya adini yaz.\n\n"
        "TARIF:\n{istem}\n")

    @staticmethod
    def _motor():
        from .motor.codex import CodexMotoru
        # `exec` KIPI -- bilerek. Gorsel yolu gercek turla YALNIZ exec'te
        # olculdu (25.09.2026); app-server'da olculmedi ve olcmek ~220k
        # jeton yakar. Olculmemis yola sessizce gecmek yerine olculeni
        # acikca seciyoruz (codex.py dosya basi, kip notu).
        return CodexMotoru(kip="exec")

    def musait_mi(self) -> bool:
        try:
            return bool(self._motor().musait_mi())
        except Exception:
            return False

    def neden_musait_degil(self) -> str:
        from .motor.codex import oturum_olu_mu, oturum_olu_metni
        try:
            m = self._motor()
        except Exception as exc:
            return f"codex motoru acilamadi: {exc}"
        if not m.calistirilabilir:
            return "codex CLI kurulu degil (`codex --version`)."
        ev = m._ev_bul()
        if oturum_olu_mu(ev):
            return oturum_olu_metni(ev)
        return (f"ofisin codex evinde giris YOK: {ev} -- PowerShell: "
                f"$env:CODEX_HOME=\"{ev}\"; codex login")

    def uret(self, istem: str, hedef: Path, *, model: str = "",
             kalite: str = "") -> dict:
        import shutil
        import uuid

        if model:
            raise GorselHatasi(
                f"codex aboneligi yolunda model SECILEMEZ ({model}): "
                "yerlesik arac modeli saglayici tarafinda secer. Modeli "
                "kaldir ya da API anahtarli bir uretici kullan.")
        if kalite:
            raise GorselHatasi(
                f"codex aboneligi yolu kalite kademesi almiyor ({kalite}); "
                "istenen kaliteyi TARIFE yaz.")
        m = self._motor()
        if not m.musait_mi():
            raise GorselHatasi(self.neden_musait_degil())
        ev = m._ev_bul()
        self.CALISMA.mkdir(parents=True, exist_ok=True)
        ad = f"gorsel-{uuid.uuid4().hex[:12]}.png"
        son, hatalar = {}, []
        for o in m.tur_kos(self.ISTEM.format(ad=ad, istem=istem),
                           klasor=str(self.CALISMA), efor="dusuk",
                           yazabilir=True, zaman_asimi=self.ZAMAN_ASIMI):
            if o.tur in ("hata", "limit"):
                hatalar.append(o.govde)
            elif o.tur == "bitti":
                son = o.ek or {}
        thread = str(son.get("oturum_id") or "")
        uretilen = (Path(ev) / "generated_images" / thread) if thread else None
        try:
            if not son.get("basarili"):
                sebep = (hatalar[-1] if hatalar else "") or str(son.get("sebep") or "")
                if son.get("limit"):
                    raise GorselHatasi(
                        "Codex kullanim limiti dolu -- gorsel su an "
                        f"uretilemez. ({sebep[:300]})")
                raise GorselHatasi(f"codex gorsel turu basarisiz: {sebep[:600]}")
            # KAYNAK: once ajanin kopyaladigi dosya; yoksa BU turun
            # (thread) klasorundeki en yeni gorsel. Baska bir turun
            # gorselini almak, olmayan bir isi yapilmis saymak olurdu.
            kaynak = self.CALISMA / ad
            if not kaynak.is_file() and uretilen and uretilen.is_dir():
                adaylar = sorted(
                    (p for p in uretilen.iterdir()
                     if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")),
                    key=lambda p: p.stat().st_mtime)
                kaynak = adaylar[-1] if adaylar else kaynak
            if not kaynak.is_file():
                raise GorselHatasi(
                    "codex turu basarili dedi ama GORSEL DOSYASI YOK -- "
                    "uydurulmaz. (image_gen cagrilmamis olabilir.)")
            hedef = Path(hedef)
            if hedef.suffix.lower() != kaynak.suffix.lower():
                hedef = hedef.with_suffix(kaynak.suffix.lower())
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kaynak, hedef)
        finally:
            # Temizlik: gorseller hesabin evinde BIRIKMESIN.
            try:
                (self.CALISMA / ad).unlink()
            except OSError:
                pass
            if uretilen is not None:
                shutil.rmtree(uretilen, ignore_errors=True)
        tip = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp"}.get(hedef.suffix.lower(), "image/png")
        sonuc = {"uretici": self.ad,
                 "model": "saglayici secer (olculemiyor)",
                 "yol": str(hedef), "bayt": hedef.stat().st_size, "tip": tip,
                 "kota": "Codex abonelik kotasi (fatura yok)"}
        if son.get("jeton"):
            sonuc["jeton"] = int(son["jeton"])
        return sonuc


#: Kayit defteri. Sira TERCIH sirasidir: ucretsiz olan once denenir.
#: Para harcayan bir saglayiciya sessizce dusmek, kullanicinin
#: istemedigi bir fatura demektir.
_DEFTER = {
    CodexUretici.ad: CodexUretici,
    GeminiUretici.ad: GeminiUretici,
    OpenRouterUretici.ad: OpenRouterUretici,
    OpenAIUretici.ad: OpenAIUretici,
}
#: Once ABONELIK (codex: fatura yok, olculdu calisiyor), sonra UCRETSIZ
#: kota (gemini: olculen gunlerin cogunda gunluk kotasi DOLUYDU), sonra
#: maliyeti OLCULEBILEN (openrouter), en son maliyeti yalnizca TAHMIN
#: edilebilen (openai dogrudan). Olculen maliyet, tahmin edilenden
#: iyidir: fatura surpriz olmaz.
TERCIH_SIRASI = ("codex", "gemini", "openrouter", "openai")


def uretici_kaydet(sinif) -> None:
    _DEFTER[sinif.ad] = sinif


def uretici_ac(ad: str) -> Uretici:
    sinif = _DEFTER.get(ad)
    if sinif is None:
        raise GorselHatasi(
            f"Bilinmeyen gorsel ureticisi: {ad}. "
            f"Secenekler: {', '.join(sorted(_DEFTER))}")
    return sinif()


def musait_ureticiler() -> dict:
    """Her uretici icin: anahtar var mi, yoksa NEDEN, ve son kota olcumu.

    `musait` alani YALNIZCA anahtarin varligini soyler -- uretebilirligi
    DEGIL. Ikisi ayri seydir ve bir kez karistirildi: gunluk kota
    doluyken gosterge **MUSAIT** basiyordu (21.09.2026).

    Kotayi burada OLCMEYIZ: olcmek bir istek harcar ve tam tuketmeye
    calistigimiz seyi tuketir. Onun yerine son gercek denemenin sonucu
    HATIRLANIR (`kota_notu`) ve cagiran onu gostermek zorundadir.
    """
    sonuc = {}
    for ad, sinif in _DEFTER.items():
        u = sinif()
        var = u.musait_mi()
        sonuc[ad] = {"musait": var, "ucretli": u.ucretli,
                     "sebep": "" if var else u.neden_musait_degil(),
                     "kota_notu": kota_notu(ad) if var else ""}
    return sonuc


def uret(istem: str, hedef, *, uretici: str = "", model: str = "",
         kalite: str = "", ucretsiz_sadece: bool = None) -> dict:
    """Istemi gorsele cevirir. Doner: `{uretici, model, yol, bayt, tip}`.

    `uretici` verilmezse TERCIH SIRASI denenir ve ilk musait olan
    kullanilir. Denenen ama musait olmayan her saglayici sonuca
    `atlananlar` olarak yazilir -- gorunmeyen bir bosluk, sonra
    "neden bu saglayici kullanilmadi" sorusunu cevapsiz birakir.
    """
    istem = (istem or "").strip()
    if not istem:
        raise GorselHatasi("Bos istemle gorsel uretilemez.")
    hedef = Path(hedef).expanduser()
    if not hedef.suffix:
        hedef = hedef.with_suffix(".png")

    adaylar = [uretici] if uretici else list(TERCIH_SIRASI)
    kilit = ucretsiz_sadece_mi() if ucretsiz_sadece is None else ucretsiz_sadece
    atlananlar = []
    for ad in adaylar:
        u = uretici_ac(ad)
        # PARA KILIDI, MUSAITLIKTEN ONCE. Ucretli bir ureticinin
        # anahtari olmasi onu kullanilabilir YAPMAZ; kilit acikken
        # anahtarin varligi bir davet degildir.
        if kilit and u.ucretli:
            if uretici:
                # ACIKCA istendi: sessizce atlamak yerine REDDET.
                # Sessizce atlanan bir istek, kullanicinin istedigini
                # yaptigini sanmasi demektir.
                raise ParaKilidi(PARA_KILIDI_METNI.format(ad=ad))
            atlananlar.append({"uretici": ad,
                               "sebep": "ucretli -- para kilidi acik"})
            continue
        if not u.musait_mi():
            atlananlar.append({"uretici": ad, "sebep": u.neden_musait_degil()})
            continue
        sonuc = u.uret(istem, hedef, model=model, kalite=kalite)
        sonuc["atlananlar"] = atlananlar
        return sonuc

    satirlar = ["Hicbir gorsel ureticisi musait degil:"]
    satirlar += [f"  - {a['uretici']}: {a['sebep']}" for a in atlananlar]
    raise GorselHatasi("\n".join(satirlar))


def lider_blogu() -> str:
    """Liderin GORDUGU medya yetenegi: uretebiliyor muyuz, uretemiyorsak neden.

    OLCULMUS BOSLUK (21.09.2026): lider medya hakkinda HICBIR SEY
    gormuyordu -- ne para kilidini, ne kotayi, ne ureticileri. Patron
    *"markamiz icin kapak gorseli yapalim"* dediginde lider ya is acip
    ortada patlayacak, ya yapabilecegini varsayacakti.

    Baglayici ve klasor envanterleriyle ayni sinif ve ayni cozum:
    **gormeden karar vermek tahmindir.**

    Blok UC seyi soyler ve ucu de OLCULUR, tahmin edilmez:
      1. Para kilidi acik mi (ucretli uretici kullanilabilir mi)
      2. Her ureticinin su anki hali -- son GERCEK denemenin kota sonucu
      3. INSAN KOPRUSU: uretim mumkun olmasa bile `gorsel_iste` /
         `video_iste` ile istem yazilabilir. Bunu soylemeseydik lider
         "yapilamaz" deyip dururdu; oysa yapilabilir, yalnizca son
         adimi insan atar.

    `video` LAZY ithal edilir: `video.py` bu modulu ithal ediyor, ters
    yonde modul duzeyinde ithal dairesel olurdu.
    """
    from . import video as _video

    kilit = ucretsiz_sadece_mi()
    satir = ["# MEDYA URETIMI (gorsel / video)", "",
             "PARA KILIDI: " + ("KAPALI -- ofis su an PARA HARCAMIYOR."
                                if kilit else "ACIK -- ucretli uretim mumkun."),
             ""]

    def _grup(baslik, durumlar):
        out = [f"{baslik}:"]
        kullanilabilir = False
        for ad, h in durumlar.items():
            if h["ucretli"] and kilit:
                out.append(f"  {ad:11} UCRETLI -- para kilidi yuzunden KAPALI")
                continue
            if not h["musait"]:
                # "anahtar yok" her uretici icin dogru DEGIL: codex'in
                # anahtari yok, GIRISI var (ve oturumu olmus olabilir).
                # Yanlis sebep, lidere yanlis cozumu soyletir.
                sebep = "anahtar yok" if ad != "codex" else (
                    "oturum KAPALI -- yeniden giris gerekir"
                    if "KAPANMIS" in (h.get("sebep") or "")
                    else "giris yok / CLI yok")
                out.append(f"  {ad:11} {sebep}")
                continue
            not_ = h.get("kota_notu") or ""
            if not_:
                out.append(f"  {ad:11} anahtar var ama son denemede {not_}")
            else:
                out.append(f"  {ad:11} KULLANILABILIR")
            kullanilabilir = True
        return out, kullanilabilir

    g_satir, g_var = _grup("gorsel", musait_ureticiler())
    v_satir, v_var = _grup("video", _video.musait_ureticiler())
    satir += g_satir + v_satir + [""]

    if not (g_var or v_var):
        satir.append("Su an OTOMATIK medya uretimi MUMKUN DEGIL.")
    satir += [
        "KURALLAR:",
        "- Uretim mumkun degilse IS ACMA. Patrona NE YAPMASI gerektigini",
        "  soyle (kilidi acmak, anahtar eklemek, ya da kotanin yenilenmesi).",
        "- UCUNCU BIR YOL VAR ve genelde en dogrusu: `gorsel_iste` /",
        "  `video_iste`. Istemi AJAN yazar (isin zor kismi zaten odur),",
        "  patron kendi aracinda uretip tahtaya koyar. PARA HARCANMAZ.",
        "- Para kilidini SEN ACAMAZSIN. Para karari patronundur; sen",
        "  yalnizca durumu ve secenegi soylersin.",
        "- Gorsel isinde ajana OFISIN `gorsel_uret` aracini kullandir",
        "  (`uretici: codex` gibi). CLI'i elle cagirtma, sarmalayici betik",
        "  yazdirma: o yol para/kota kapisini atlar ve bir resim icin",
        "  yuz binlerce jeton yakar (olculdu 01.10: ~800 bin jeton, 4 dk).",
        "- `codex` gorseli ABONELIKTEN uretir (fatura yok) ama Codex",
        "  kotasini gorselsiz bir turdan ~3-5 kat hizli yer ve o kota",
        "  codex'li ajanlarla ORTAK. Toplu gorsel isini buna gore planla.",
    ]
    return "\n".join(satir)
