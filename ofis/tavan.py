# -*- coding: utf-8 -*-
"""TAVAN -- kacan turu OFIS durdurur, motor degil.

Kullanici (22.09.2026): *"bizde cok motorlu bir AI agent sistemi
olacak; DeepSeek, Qwen, Kimi, Grok da ekliyecegim."*

Bu dosya o cumlenin onundeki duvari kaldirmak icin var.

## OLCULMUS SORUN: tavan istemek, motoru KAPATMAK demekti

Tur basina harcama tavanini bugune kadar CLI uyguluyordu
(`claude --max-budget-usd`). Uygulayamayan motor, tavan istenen her
iste **atlaniyordu**:

    uyari | Zincirde atlandi: codex/gpt-5.6-sol --
            tur basina butce tavani uygulayamiyor

Atlama dogruydu (*para kontrolleri kapali kalarak basarisiz olur*) ama
sonucu agirdi: `cinar` aylarca `codex` ayarliydi ve **her turu Claude'da
kosti**. Yani "tavan koy" demek pratikte "codex'i kapat" demekti.

Yeni eklenecek her motor ayni duvara carpar. Ve bir yetenegi her
motordan tek tek beklemek, bu projede alti kez odenen desendir: bir
adaptorde vardir, otekinde unutulur.

> **Motorlardan bekledigimiz her yetenek, motor sayisiyla carpilan bir
> borctur. Ofisin kendi uygulayabildigi sey, ofiste durur.**

## OFIS NEYI OLCEBILIR -- ve neyi olcemez

Durust olmak sart, cunku "tavan koydum" sanmak tavansiz kosmaktan
kotudur.

| sinyal | tur ORTASINDA | tur SONUNDA |
|---|---|---|
| gecen sure | **var** | var |
| arac cagrisi sayisi | **var** | var |
| uretilen metin | **var** | var |
| JETON | **yok** (codex/gemini sonda bildiriyor) | **var** |
| DOLAR | yok | yalniz claude bildiriyor |

Buradan iki ayri kapi cikiyor ve ikisi de durust adlandirilmali:

1. **KACAK FRENI** (tur ortasi) -- sure · arac sayisi · cikti hacmi.
   Bu bir PARA tavani DEGIL; kacan bir turu durdurur. Adini "butce"
   koymak, olcmedigimiz seyi olcuyormus gibi gostermek olurdu.

2. **BIRIKMIS JETON TAVANI** (turlar arasi) -- jeton her motorda
   OLCULUYOR (codex `turn.completed`, gemini `stats`, claude usage).
   Bir gorevin toplam jetonu tavani asarsa **sonraki tur baslamaz**.
   Bu kesin bir olcum; tahmin degil.

Neden jeton, dolar degil: fiyat tablosu bayatlar (bu projede model
adlari icin bir kez odendi -> `kademe`), ve kullanicinin gercek kisiti
zaten abonelik kullanimi, yani jeton.

## ISI OLDURMEZ, TURU DURDURUR

Zincirin kurali burada da gecerli: kaynak tukenmesi bir hata degildir.
Tavan dolunca is `hazir`a doner, sebep yazilir, insan gorur. Sessizce
devam etmek de, isi olu birakmak da yanlis olurdu.
"""

from __future__ import annotations

import json

#: Kacak freni varsayilanlari. Hepsi OLCULMUS is profillerinden:
#:
#:     kod (GuvenKart QA)        241.571 jeton ·  ~10 arac cagrisi
#:     arastirma (17 arama)      208.148 jeton ·  ~20
#:     tarayici (31 cagri)     1.407.411 jeton ·   31
#:     dokuman/icerik          4.860.234 jeton ·  cok
#:
#: Degerler en agir olculen isin BIR KAT ustune konuldu: fren gercek
#: bir kacagi durdurmali ama normal isi kesmemeli. Her seye "sorun"
#: diyen bir gosterge de gostergesizlikten farksizdir.
#:
#: 08.10.2026 (OLCULDU, canli Brave): Flow'u suren video ajani 121. cagrida
#: KESILDI -- klip uretilmis, kurguya geciyordu. Cagrilar cesitliydi (bul,
#: tikla, yukle, yaz, denetle): ILERLEME, dongu degil. Kor sayi guc kisiyordu
#: (patron kurali: guc kisan kisit yok). Artik DONGU olculur (asagida); sert
#: sinir yalniz gercekten olagan disi bir tur icin.
VARSAYILAN_AZAMI_ARAC = 1000
VARSAYILAN_AZAMI_CIKTI_HARF = 400_000
#: DONGU: ayni cagri (arac + girdi ozeti) art arda bu kadar kez...
DONGU_ART_ARDA = 50
#: ...ya da son bu kadar cagrida en cok iki farkli cagri (A-B-A-B).
DONGU_PENCERE = 80

#: Birikmis jeton tavani. Gorev basina, turlar arasi.
#:
#: 5.000.000, olculen en agir isin (dokuman, 4,86M) hemen ustu. Bunu
#: asan bir gorev artik "surmuyor", DONUYOR demektir.
VARSAYILAN_AZAMI_JETON = 5_000_000


class TavanAsimi(RuntimeError):
    """Tavan doldu -- bu bir ARIZA degil, bir KARAR.

    Ayri sinif olmasinin sebebi `ButceAsimi` ve `ParaKilidi` ile ayni:
    cagiran bunu gercek bir hatadan ayirt edebilmeli. Tek sinif olsaydi
    "tekrar dene" denir ve tavan bir yavaslatmaya donerdi.
    """

    def __init__(self, sebep: str, olcum: dict = None) -> None:
        super().__init__(sebep)
        self.olcum = dict(olcum or {})


class KacakFreni:
    """Tur ORTASINDA olculebilen sinyallere bakar.

    Bir PARA tavani degildir ve oyle adlandirilmaz. Kacan turu
    durdurur: sonsuz donguye giren, ayni araci yuzlerce kez cagiran,
    ya da megabaytlarca metin ureten bir tur.

    Motor sozlesmesinden BAGIMSIZ: yalnizca koltugun zaten gordugu
    olaylara bakiyor. Bu yuzden yarin eklenen bir motor icin de
    calisir -- yeni motorun hicbir sey bildirmesi gerekmez.
    """

    def __init__(self, *, azami_arac: int = VARSAYILAN_AZAMI_ARAC,
                 azami_cikti_harf: int = VARSAYILAN_AZAMI_CIKTI_HARF) -> None:
        self.azami_arac = int(azami_arac or 0)
        self.azami_cikti_harf = int(azami_cikti_harf or 0)
        self.arac = 0
        self.harf = 0
        self._son = []                 # son DONGU_PENCERE cagrinin imzasi
        self._art_arda = 0
        self._dongu = ""

    def olay(self, tur: str, govde: str = "", ozet: str = "") -> None:
        """Koltuk her olayda cagirir. Sayar, karar VERMEZ. `ozet`: aracin
        girdi ozeti -- ayni ad farkli girdiyle cagrilirsa DONGU degildir."""
        if tur == "arac":
            self.arac += 1
            imza = f"{govde or ''}|{ozet or ''}"
            self._art_arda = self._art_arda + 1 if self._son and self._son[-1] == imza else 1
            self._son = (self._son + [imza])[-DONGU_PENCERE:]
            if self._art_arda >= DONGU_ART_ARDA:
                self._dongu = (f"ayni cagri art arda {self._art_arda} kez "
                               f"({(govde or '')[:60]})")
            elif len(self._son) >= DONGU_PENCERE and len(set(self._son)) <= 2:
                self._dongu = (f"son {DONGU_PENCERE} cagri yalniz "
                               f"{len(set(self._son))} farkli cagri "
                               f"({', '.join(sorted(s.split('|')[0][:40] for s in set(self._son)))})")
        elif tur in ("metin", "cikti", "dusunce"):
            self.harf += len(govde or "")

    def asildi_mi(self) -> str:
        """Asildiysa INSAN OKUNUR sebep, asilmadiysa bos dizge.

        Sebep dondurulmesinin sebebi: teshis koyup NE oldugunu
        soylemeyen bir gosterge, insani bir kez daha dusundurur.
        """
        if self._dongu:
            return f"Kacak freni: tur DONGUDE -- {self._dongu}."
        if self.azami_arac and self.arac > self.azami_arac:
            return (f"Kacak freni: {self.arac} arac cagrisi "
                    f"(tavan {self.azami_arac}). Tur donguye girmis "
                    "olabilir.")
        if self.azami_cikti_harf and self.harf > self.azami_cikti_harf:
            return (f"Kacak freni: {self.harf:,} harf cikti "
                    f"(tavan {self.azami_cikti_harf:,}).")
        return ""

    def olcum(self) -> dict:
        return {"arac": self.arac, "harf": self.harf,
                "azami_arac": self.azami_arac,
                "azami_cikti_harf": self.azami_cikti_harf}


def lider_freni(db, proje_id: str, fren: KacakFreni, olay, *, ajan_ad: str,
                gorev_id: str = None, motor: str = "", hesap: str = "",
                yol: str = "lider") -> dict | None:
    """Lider turlarinda (triyaj, planlama, rapor, inceleme) kacak freni.

    28.09.2026 (PLAN E08): fren yalniz ISCI turunda (koltuk) vardi; lider
    turu donguye girse hicbir sey onu kesmezdi -- ve lider codex'e
    devrettiginde dolar tavani da yok. Cagiran her olayda cagirir; fren
    asildiysa GORUNUR bir uyari yazar, kesilen turu da OLCER (kesilen tur
    da bir harcamadir; `bitti` hic gelmeyecegi icin tur_ozeti burada
    yazilir) ve basarisiz `ek`i dondurur -- cagiran dongudan cikar.
    Asilmadiysa `None`.
    """
    fren.olay(olay.tur, olay.govde or "", str((olay.ek or {}).get("ozet") or ""))
    sebep = fren.asildi_mi()
    if not sebep:
        return None
    from . import kullanim
    db.olay_yaz(proje_id, "uyari", sebep + " " + json.dumps(fren.olcum()),
                ajan_ad=ajan_ad, gorev_id=gorev_id)
    ek = {"basarili": False, "sebep": "kacak freni", "hata": sebep}
    kullanim.tur_ozeti_yaz(db, proje_id, ek, ajan_ad=ajan_ad,
                           gorev_id=gorev_id, motor=motor, hesap=hesap, yol=yol)
    return ek


def gorev_jetonu(db, proje_id: str, gorev_id: str) -> int:
    """Bu goreve bugune kadar harcanan TOPLAM jeton.

    Kaynak `tur_ozeti` olayi -- yani KAYDIN TUTULDUGU YER. Koltugun
    kendi sayacindan okumak, MCP ile ayri surecte olan seyleri
    kacirirdi; bu projede "sayan yer, kaydin tutuldugu yer olmali"
    dersi bir kez odendi.
    """
    import json
    toplam = 0
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
            "AND tur = 'tur_ozeti'", (proje_id, gorev_id)).fetchall()
    for r in satirlar:
        try:
            veri = json.loads(dict(r)["govde"])
        except (ValueError, TypeError):
            continue
        if isinstance(veri, dict):
            toplam += tur_jetonu(veri)
    return toplam


def tur_jetonu(ozet: dict) -> int:
    """Bir turun TAVANA sayilan jetonu: YENI jeton (girdi + cikti + onbellege
    yazma). 08.10.2026 OLCULDU (canli): Claude terminal turunun `jeton`u
    onbellekten OKUNANI da iceriyordu (Sonnet'in tek Flow turu ~2,8 M), Gemini
    icermiyordu; 15 sn'lik video isi "19,9 M jeton, tavan 5 M" diye DURDURULDU.
    Tavan (en agir olculen is 4,86 M) yeni jetonla olculmustu. Dokum yoksa
    motorun bildirdigi toplam."""
    d = ozet.get("jeton_dokumu")
    try:
        if isinstance(d, dict) and d:
            return int(sum(int(d.get(k) or 0) for k in
                           ("girdi", "cikti", "onbellek_yazma", "onbellek_yazma_1sa")))
        return int(ozet.get("jeton") or 0)
    except (TypeError, ValueError):
        return 0


def jeton_tavani_denetle(db, proje_id: str, gorev_id: str, *,
                         azami_jeton: int = VARSAYILAN_AZAMI_JETON) -> str:
    """Yeni bir tur BASLAMADAN once bakilir.

    Asildiysa insan okunur sebep doner. Tur ortasinda bakilamaz cunku
    codex ve gemini jetonu yalnizca turun SONUNDA bildiriyor
    (olculdu) -- bilmedigimiz bir sayiya gore kesmek, tavan koymus
    gibi gorunup kesmemek olurdu.
    """
    if not azami_jeton:
        return ""
    harcanan = gorev_jetonu(db, proje_id, gorev_id)
    if harcanan <= azami_jeton:
        return ""
    return (f"Jeton tavani doldu: bu goreve {harcanan:,} jeton harcandi "
            f"(tavan {azami_jeton:,}). Is OLMEDI -- yeni tur "
            "baslatilmiyor. Tavani yukseltmek ya da isi bolmek senin "
            "kararin.")


def motor_tavani_uygular_mi(motor) -> bool:
    """Motorun KENDI tavani var mi (`--max-budget-usd` gibi).

    Varsa dolar tavani ona verilir -- daha kesin, cunku saglayicinin
    kendi muhasebesinden okur. Yoksa ofisin freni devreye girer.
    Ikisi birbirinin yerine gecmez, TAMAMLAR.
    """
    return bool(getattr(motor, "butce_destegi", False))
