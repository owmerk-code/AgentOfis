# -*- coding: utf-8 -*-
"""VIDEO -- hareketli gorsel uretimi. `gorsel.py`nin KARDESI, kopyasi degil.

Kullanici (20.09.2026): *"ilerde gorsel video olusturabilen altyapisi
hazir sistem olmali... e-ticaret magazami, reklam hesabimi, sosyal medya
hesaplarimi yonetebilmek, markayi buyutmek icin."*

Ayni sekle bilerek oturuyor -- uretici sozlesmesi, kayit defteri,
`musait_ureticiler()`, maliyet OLCULUR. Ikinci bir desen icat etseydik
bu projede bes kez yasanan sey olurdu: iki kopyadan biri duzeltilir,
oteki unutulur.

## Ama UC yapisal fark var, ve ucu de olcume dayaniyor

**1. VIDEO ESZAMANSIZDIR.** Gorsel saniyeler surer; `gorsel.py` bu
yuzden tek bir zaman asimiyla bekleyebiliyor. Video DAKIKALAR surer.
Ayni sekilde bekleseydik cagiran ajan dakikalarca bloke olurdu -- ve
koltugun nabzi motorun akisindan gelir, burada oyle bir akis yok. Bu
yuzden sozlesme bir **is modeli**: `baslat()` bir is kimligi doner,
`durum()` sorar, `indir()` bitirir. Ajan bekleyecekse BILEREK bekler.

**2. VIDEO PAHALIDIR, kacarsa cok pahalidir.** Olculdu (20.09.2026,
resmi fiyat sayfasi): Veo 3.1 standart **$0,40/saniye** -- 30 saniyelik
tek klip **$12**. Gorselde bir hata birkac sent, burada iki haneli
dolar. Bu yuzden maliyet **baslamadan once** hesaplanir; tavan
asiliyorsa is HIC BASLAMAZ. Ofisin kurali: *para kontrolleri kapali
kalarak basarisiz olur.*

**3. UCRETSIZ KATMAN YOK.** `gorsel.py`nin tercih sirasi "once
ucretsiz" idi; burada o siralama YANLIS olurdu, cunku ucretsiz secenek
yok (olculdu: Veo'nun gelistirici API'sinde ucretsiz katman yok;
Google Flow'un gunluk 50 kredisi tuketici arayuzunde, API'de degil).
Siralama bunun yerine **saniye basi olculmus fiyata** gore: ucuz once.

> Ucretsiz olmayan bir seyi "once ucretsizi dene" diye siralamak,
> kullaniciya olmayan bir guvence vermektir.

## Neden Veo ILK saglayici

Ofisin kasasinda ZATEN `GEMINI_API_KEY` var (gorsel icin kurulmus) ve
Veo ayni anahtarla calisir. Yani video icin yeni bir kimlik yolu
kurulmuyor; faturalandirma acilinca var olan yol calisir. Baska bir
saglayiciyi ilk siraya koysaydik, hic denenmemis ikinci bir kimlik
yolunu varsayilan yapmis olurduk.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from ofis import gorsel
from ofis.gorsel import anahtar_oku

#: Bir isin tamamlanmasi icin beklenecek en uzun sure. Video dakikalar
#: surer, bu yuzden gorseldekinden cok genis. Yine de SINIRSIZ degil:
#: donmus bir is sonsuza kadar sorgulanmamali.
AZAMI_BEKLEME_SN = 600

#: Iki durum sorgusu arasi. Siklastirmak kotayi bosa yakar.
YOKLAMA_ARALIGI_SN = 10

#: Tek istekte uretilebilecek en uzun video. Bu TEKNIK bir sinir degil,
#: bir PARA korkulugu: 60 saniyelik standart Veo klibi $24 eder. Daha
#: uzunu parcalara bolunur ve her parca ayri bir karar olur.
AZAMI_SANIYE = 30

#: Varsayilan tur tavani ($). Asilirsa is HIC BASLAMAZ. Varsayilanin
#: DAR olmasi genis olmasindan iyidir: dar tavan gorunur bir ret
#: uretir, genis tavan gorunmez bir fatura.
VARSAYILAN_TAVAN_USD = 2.00


class VideoHatasi(RuntimeError):
    pass


class ParaKilidi(VideoHatasi):
    """Ucretli uretici istendi ama para kilidi acik.

    `ButceAsimi` ile ayni gerekce ve ayni sinifta: bu bir ariza degil
    bir KARAR. Cagiran bunu gercek bir hatadan ayirt edebilmeli, yoksa
    "tekrar dene" der ve kilit bir yavaslatmaya donusur.
    """


class ButceAsimi(VideoHatasi):
    """Tahmini maliyet tavani asti; is BASLATILMADI.

    Ayri bir sinif, cunku cagiran bunu gercek bir hatadan AYIRT
    edebilmeli: burada hicbir sey bozulmadi, bir sinir calisti. Tek bir
    `VideoHatasi` olsaydi cagiran "tekrar dene" diyebilirdi ve tavan bir
    yavaslatmadan ibaret kalirdi.
    """


class Uretici:
    """Video ureticisinin sozlesmesi.

    `gorsel.Uretici`den AYRI: orada `uret()` tek adimdir, burada is
    modeli var. Ikisini tek bir taban sinifa zorlamak, birinin
    sozlesmesini otekine uydurmak olurdu.
    """

    ad = ""
    #: Video ureticilerinin bugun HEPSI ucretli. Alan yine de duruyor:
    #: yarin ucretsiz bir saglayici cikarsa siralamanin onu ayirt
    #: etmesi gerekiyor.
    ucretli = True
    #: Saniye basi OLCULMUS fiyat ($) -- saglayicinin yayinladigi rakam,
    #: tahmin degil. Siralama ve tavan hesabi buna bakar.
    saniye_basi_usd = 0.0

    def musait_mi(self) -> bool:
        raise NotImplementedError

    def neden_musait_degil(self) -> str:
        """Musait DEGILSE sebebi. Sessiz atlama yasak (gorsel.py ile ayni)."""
        return "bilinmiyor"

    def baslat(self, istem: str, *, saniye: int, model: str = "",
               cozunurluk: str = "720p") -> dict:
        """Uretimi baslatir, BEKLEMEDEN doner: `{is_id, uretici, model}`."""
        raise NotImplementedError

    def durum(self, is_id: str) -> dict:
        """`{bitti, basarili, hata}` -- bittiyse indirme icin gereken de."""
        raise NotImplementedError

    def indir(self, is_id: str, hedef: Path) -> dict:
        """Biten isi dosyaya yazar: `{yol, bayt, tip}`."""
        raise NotImplementedError


def tahmini_maliyet(uretici_ad: str, saniye: int,
                    cozunurluk: str = "720p") -> float:
    """Is BASLAMADAN once maliyeti hesaplar.

    `gorsel.py`de olmayan tek islev ve var olma sebebi olculdu: video
    saniye basi fiyatlanir, yani maliyet isteme degil SUREYE baglidir ve
    **onceden bilinebilir**. Onceden bilinebilen bir maliyeti sonradan
    olcmek tavani anlamsiz kilardi -- para yandiktan sonra "tavan
    asildi" demek gec kalmaktir.
    """
    u = uretici_ac(uretici_ad)
    carpan = 1.5 if str(cozunurluk).lower().startswith("4") else 1.0
    return round(u.saniye_basi_usd * max(1, int(saniye)) * carpan, 4)


class VeoUretici(Uretici):
    """Google Veo -- ofisin ZATEN sahip oldugu `GEMINI_API_KEY` ile.

    OLCULDU (20.09.2026, resmi fiyat sayfasi): Veo 3.1 standart
    **$0,40/sn** (720p/1080p), 4K **$0,60/sn**, Lite **$0,03/sn**.
    Varsayilan LITE'tir -- en ucuz olan varsayilan olmali, cunku pahali
    bir varsayilan sessizce odenir.

    **Gelistirici API'sinde UCRETSIZ KATMAN YOK.** Anahtar kurulu olsa
    bile faturalandirma acik degilse istek reddedilir; o ret burada
    YUTULMAZ, sebebiyle yukari verilir -- kullanici "neden calismiyor"
    diye tahmin etmemeli.
    """

    ad = "veo"
    ucretli = True
    saniye_basi_usd = 0.03            # lite; standart 0.40
    TABAN = "https://generativelanguage.googleapis.com/v1beta"

    #: OLCULDU (20.09.2026) -- anahtarin GERCEKTEN gordugu video
    #: modelleri, `v1beta/models` listesinden okundu:
    #:   veo-3.1-lite-generate-preview   (en ucuz)
    #:   veo-3.1-fast-generate-preview
    #:   veo-3.1-generate-preview        (standart)
    #:
    #: BENIM HATAM: ilk yazisinda buraya `veo-3.1-lite` yazmistim --
    #: TAHMIN. Mutasyon sinamasi tavan kapisini kapatinca cagri gercek
    #: API'ye gitti ve **HTTP 404** dondu; model adi boyle ortaya cikti.
    #: Ayni dosyada Higgsfield'i *"belgeye bakmadan uc nokta yazmak
    #: tahmindir"* diyerek yarim birakmistim ve hemen yaninda model
    #: adini tahmin etmisim. Kural, onu yazana da uygulanir.
    #:
    #: `-preview` eki bu modellerin ADININ DEGISEBILECEGINI soyluyor:
    #: 404 alinirsa once bu liste yeniden olculmeli.
    OLCULEN_MODELLER = ("veo-3.1-lite-generate-preview",
                        "veo-3.1-fast-generate-preview",
                        "veo-3.1-generate-preview")
    VARSAYILAN_MODEL = "veo-3.1-lite-generate-preview"

    def _anahtar(self) -> str:
        return anahtar_oku("GEMINI_API_KEY")

    def musait_mi(self) -> bool:
        return bool(self._anahtar())

    def neden_musait_degil(self) -> str:
        return ("GEMINI_API_KEY kurulu degil. "
                "`python -m ofis.kabuk anahtar ekle GEMINI_API_KEY`. "
                "NOT: anahtar tek basina YETMEZ -- Veo'nun ucretsiz "
                "katmani yoktur, faturalandirma da acik olmali.")

    def _istek(self, yol: str, govde=None, yontem: str = "POST") -> dict:
        url = f"{self.TABAN}/{yol}"
        veri = json.dumps(govde).encode("utf-8") if govde is not None else None
        r = urllib.request.Request(url, data=veri, method=yontem)
        r.add_header("x-goog-api-key", self._anahtar())
        r.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(r, timeout=60) as y:
                return json.loads(y.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            ham = exc.read().decode("utf-8", "replace")[:600]
            # Fatura kapaliligi en olasi ret sebebi. Tahmin etmek yerine
            # sunucunun KENDI metnini gosterip ipucunu yaninda veriyoruz.
            ek = ""
            if exc.code in (400, 403):
                ek = ("\n  IPUCU: Veo'nun ucretsiz katmani yok. Google "
                      "Cloud projesinde faturalandirma acik mi?")
            elif exc.code == 404:
                # Olculdu: model adlari `-preview` ekli, yani DEGISEBILIR.
                # 404'u "sunucu bozuk" diye okumak yanlis yola sokar.
                ek = ("\n  IPUCU: model adi bayatlamis olabilir "
                      f"(su an: {self.VARSAYILAN_MODEL}). Listeyi yeniden "
                      "olc: GET v1beta/models -- adlar `-preview` ekli ve "
                      "degisebilir.")
            raise VideoHatasi(
                f"Veo istegi reddedildi (HTTP {exc.code}): {ham}{ek}") from None
        except urllib.error.URLError as exc:
            raise VideoHatasi(f"Veo'ya ulasilamadi: {exc.reason}") from None

    def baslat(self, istem: str, *, saniye: int, model: str = "",
               cozunurluk: str = "720p") -> dict:
        model = model or self.VARSAYILAN_MODEL
        if saniye > AZAMI_SANIYE:
            raise VideoHatasi(
                f"{saniye} sn istendi, tavan {AZAMI_SANIYE} sn. Bu teknik "
                "bir sinir degil PARA korkulugu -- daha uzunu parcalara "
                "bolunur ve her parca ayri bir karar olur.")
        d = self._istek(
            f"models/{model}:predictLongRunning",
            {"instances": [{"prompt": istem}],
             "parameters": {"durationSeconds": int(saniye),
                            "resolution": cozunurluk}})
        is_id = d.get("name") or ""
        if not is_id:
            raise VideoHatasi(f"Veo is kimligi dondurmedi: {str(d)[:300]}")
        return {"is_id": is_id, "uretici": self.ad, "model": model,
                "saniye": int(saniye), "cozunurluk": cozunurluk}

    def durum(self, is_id: str) -> dict:
        d = self._istek(is_id, yontem="GET")
        if not d.get("done"):
            return {"bitti": False, "basarili": False, "hata": ""}
        if d.get("error"):
            return {"bitti": True, "basarili": False,
                    "hata": str(d["error"])[:400]}
        return {"bitti": True, "basarili": True, "hata": "", "ham": d}

    def indir(self, is_id: str, hedef: Path) -> dict:
        h = self.durum(is_id)
        if not h["bitti"]:
            raise VideoHatasi("Is henuz bitmedi; once `durum()` ile bekle.")
        if not h["basarili"]:
            raise VideoHatasi(f"Is basarisiz: {h['hata']}")
        yanit = (h.get("ham") or {}).get("response") or {}
        ornekler = ((yanit.get("generateVideoResponse") or {}).get(
            "generatedSamples") or yanit.get("videos") or [])
        if not ornekler:
            raise VideoHatasi(f"Yanitta video yok: {str(yanit)[:300]}")
        ilk = ornekler[0]
        ham = None
        kaynak = ilk.get("video") if isinstance(ilk.get("video"), dict) else ilk
        if isinstance(kaynak, dict):
            b64 = kaynak.get("bytesBase64Encoded")
            if b64:
                ham = base64.b64decode(b64)
            elif kaynak.get("uri"):
                r = urllib.request.Request(kaynak["uri"])
                r.add_header("x-goog-api-key", self._anahtar())
                with urllib.request.urlopen(r, timeout=300) as y:
                    ham = y.read()
        if ham is None:
            raise VideoHatasi(f"Video verisi cozulemedi: {str(ilk)[:300]}")
        hedef = Path(hedef)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(ham)
        return {"yol": str(hedef), "bayt": len(ham), "tip": "video/mp4"}


class HiggsfieldUretici(Uretici):
    """Higgsfield -- kullandikca ode, aylik taahhut YOK.

    Kullanici bu saglayiciyi adiyla istedi. Olculdu (20.09.2026): uretim
    basina fiyatlandirir ($0,20-$3,23/klip, modele gore) ve **basarisiz
    uretimi ucretlendirmez, iade eder**. Bu, ofisin *"maliyet olculur,
    tahmin edilmez"* kuralina Veo'dan bile iyi oturur.

    HENUZ ANAHTAR YOK, bu yuzden `musait_mi()` **False** doner -- sessizce
    "hazir" gorunmez. Gerceklestirmenin kalani anahtar gelince GERCEK bir
    istekle olculecek: uc noktayi belgesine bakmadan yazmak tahmin
    olurdu, ve bu projede tahmin edilen her sozlesme en az bir kez
    yanlis cikti.
    """

    ad = "higgsfield"
    ucretli = True
    saniye_basi_usd = 0.07            # ~$0,70 / 10 sn (Kling 2.6, olculdu)

    def musait_mi(self) -> bool:
        return bool(anahtar_oku("HIGGSFIELD_API_KEY"))

    def neden_musait_degil(self) -> str:
        return ("HIGGSFIELD_API_KEY kurulu degil. Kullandikca ode, aylik "
                "taahhut yok; basarisiz uretim ucretlendirilmiyor. "
                "`python -m ofis.kabuk anahtar ekle HIGGSFIELD_API_KEY`")

    def baslat(self, istem, *, saniye, model="", cozunurluk="720p"):
        # KASITLI EKSIK: anahtar gelmeden uc nokta YAZILMIYOR. Yarim bir
        # gerceklestirme "calisiyor gorunup calismayan" bir yol acardi --
        # bu projenin karsi kuruldugu sinif.
        raise VideoHatasi(
            "Higgsfield adaptoru HENUZ YAZILMADI. Anahtar eklenince "
            "gercek bir istekle olculup tamamlanacak; belgeye bakmadan "
            "uc nokta yazmak tahmindir.")


_DEFTER = {
    VeoUretici.ad: VeoUretici,
    HiggsfieldUretici.ad: HiggsfieldUretici,
}

#: Siralama saniye basi OLCULMUS fiyata gore, ucuz once. `gorsel.py`deki
#: "once ucretsiz" burada YANLIS olurdu: ucretsiz video API'si yok, ve
#: olmayan bir seye gore siralamak kullaniciya olmayan bir guvence verir.
TERCIH_SIRASI = ("veo", "higgsfield")


def uretici_kaydet(sinif) -> None:
    _DEFTER[sinif.ad] = sinif


def uretici_ac(ad: str) -> Uretici:
    sinif = _DEFTER.get(ad)
    if sinif is None:
        raise VideoHatasi(
            f"Bilinmeyen video ureticisi: {ad}. "
            f"Secenekler: {', '.join(sorted(_DEFTER))}")
    return sinif()


def musait_ureticiler() -> dict:
    """Her uretici icin: musait mi, degilse NEDEN, saniye basi kac para."""
    sonuc = {}
    for ad, sinif in _DEFTER.items():
        u = sinif()
        m = u.musait_mi()
        sonuc[ad] = {"musait": m, "ucretli": u.ucretli,
                     "saniye_basi_usd": u.saniye_basi_usd,
                     "sebep": "" if m else u.neden_musait_degil()}
    return sonuc


def uret(istem: str, hedef, *, saniye: int = 8, uretici: str = "",
         model: str = "", cozunurluk: str = "720p",
         tavan_usd: float = VARSAYILAN_TAVAN_USD,
         bekle: bool = True, ucretsiz_sadece: bool = None) -> dict:
    """Istemi videoya cevirir.

    `bekle=False` ise is baslatilir ve is kimligi donulur; cagiran kendi
    bekler. Uzun bir isi bekleyen ajan KILIDINI TUTARAK bekler ve o sure
    boyunca hicbir sey uretmez -- bu yuzden secim cagirana birakildi.

    TAVAN ONCE: maliyet is baslamadan hesaplanir, asiliyorsa `ButceAsimi`
    atilir. Once baslatip sonra olcseydik tavan, parayi yandiktan sonra
    bildiren bir gosterge olurdu.
    """
    # PARA KILIDI. Video'da UCRETSIZ KATMAN HIC YOK (olculdu): butun
    # ureticiler ucretli, yani kilit acikken video uretimi TAMAMEN
    # kapalidir. Bu bir eksik degil, kullanicinin kisitinin dogrudan
    # sonucu -- ve acikca soylenmesi gerekir, sessizce denenip fatura
    # yazilmasi degil.
    #
    # Kilit `gorsel.py`den ODUNC alinir, burada yeniden tanimlanmaz:
    # iki kopyadan biri duzeltilip oteki unutuldugu icin bu projede
    # bes kez hata cikti. Anahtar okumasi da ayni sebeple oradan gelir.
    kilit = (gorsel.ucretsiz_sadece_mi() if ucretsiz_sadece is None
             else ucretsiz_sadece)
    adaylar = [uretici] if uretici else list(TERCIH_SIRASI)
    sebepler = []
    for ad in adaylar:
        u = uretici_ac(ad)
        if kilit and u.ucretli:
            if uretici:
                raise ParaKilidi(
                    gorsel.PARA_KILIDI_METNI.format(ad=ad)
                    + "\n  NOT: video uretiminde UCRETSIZ KATMAN YOK --"
                      " kilit acikken video hic uretilemez.")
            sebepler.append(f"{ad}: ucretli -- para kilidi acik")
            continue
        if not u.musait_mi():
            sebepler.append(f"{ad}: {u.neden_musait_degil()}")
            continue

        tahmin = tahmini_maliyet(ad, saniye, cozunurluk)
        if tahmin > tavan_usd:
            raise ButceAsimi(
                f"{ad} ile {saniye} sn {cozunurluk} video ~${tahmin} tutar, "
                f"tavan ${tavan_usd}. Is BASLATILMADI. Tavani bilerek "
                "yukseltmek ya da sureyi kisaltmak gerekir.")

        is_bilgi = u.baslat(istem, saniye=saniye, model=model,
                            cozunurluk=cozunurluk)
        is_bilgi["tahmini_maliyet_usd"] = tahmin
        if not bekle:
            return is_bilgi

        basla = time.time()
        while True:
            h = u.durum(is_bilgi["is_id"])
            if h["bitti"]:
                if not h["basarili"]:
                    raise VideoHatasi(f"{ad} isi basarisiz: {h['hata']}")
                break
            if time.time() - basla > AZAMI_BEKLEME_SN:
                # Is SUNUCUDA devam ediyor olabilir; kimligi geri
                # veriyoruz ki sonra sorulabilsin. Kimligi atsaydik,
                # parasi odenmis bir isi kaybederdik.
                raise VideoHatasi(
                    f"{ad} isi {AZAMI_BEKLEME_SN} sn'de bitmedi. Is "
                    f"kimligi: {is_bilgi['is_id']} -- sunucuda devam "
                    "ediyor olabilir, `durum()` ile sorulabilir.")
            time.sleep(YOKLAMA_ARALIGI_SN)

        sonuc = u.indir(is_bilgi["is_id"], Path(hedef))
        sonuc.update(is_bilgi)
        return sonuc

    raise VideoHatasi(
        "Hicbir video ureticisi musait degil:\n  " + "\n  ".join(sebepler))
