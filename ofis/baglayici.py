# -*- coding: utf-8 -*-
"""BAGLAYICI -- hesabin claude.ai connector'larini ISE baglar.

Kullanicinin asil isi burada: magaza, reklam, e-posta, sosyal medya.
Aylardir yazili olan duvar buydu:

> *"Ajanlar baglayicilara erisemiyor. Shopify, Meta, Gmail, Drive
>   hesapta bagli ama ajan HICBIRINI almiyor."*

## OLCULDU (21.09.2026) -- ve eski olcum BAYATLAMISTI

Uc sey yeniden olculdu, ikisi degismis:

| Soru | Onceki kayit | 21.09.2026 olcumu |
|---|---|---|
| Shopify baglayicisi ayakta mi | "yetki suresi dolmus" | **Bagli** (`claude mcp list`) |
| `ENABLE_TOOL_SEARCH=true` `Write`i kirar mi | **kirar** (bu yuzden kapaliydi) | **KIRMIYOR** -- ayni turda dosya yazildi VE Shopify araci gorundu |
| Tek baglayiciyi `--mcp-config` ile vermek | calismiyor | **hala calismiyor** (dogru soruyla teyit edildi) |

Yani engel kalkti; kaldiran sey bizim kodumuz degil, CLI'in degismesi.
Kendi kuralimiz: *yanlis oldugu olculmemis bir kural, kural degil
varsayimdir.*

Olculen tur:

```
CEVAP     : YAZDI=evet ARAC=mcp__claude_ai_Shopify__get-shop-info
DOSYA VAR : True
GIRDI     : 94.785 jeton | $0,0409
```

## EN ONEMLI KISIT -- BILDIRIM BIR SUZGEC DEGILDIR

`--mcp-config` ile TEK baglayici verilemiyor: OAuth oraya tasinmiyor
(olculdu, ajan "YOK" dedi). Calisan tek yol
`ENABLE_CLAUDEAI_MCP_SERVERS=true`, ve o **HEPSINI** yukler.

Yani gorevin `baglayicilar` alani teknik bir **filtre DEGIL**. Ne ise
yarar:

1. **Odemeye deger mi kararini verir.** Bos ise hicbir baglayici
   yuklenmez ve ~225k jeton hic odenmez. Dolu ise odenir.
2. **Niyeti ve gerekcesi kayda gecer** -- "hangi is hangi baglayiciya
   dokundu" sorusu alti ay sonra da cevaplanir.
3. **Brifingde ajana SOYLENIR**: hangi baglayiciyi kullanmasi bekleniyor.

Bunu "secim yapiyoruz" diye yazsaydik, **yanlis gosteren bir gosterge**
olurdu -- bu projenin en pahali hata sinifi. Ajan aslinda hesabin
TAMAMINI goruyor ve bunu bilmek, izin listesini ve riski dogru
degerlendirmek icin gerekli.

## YETKI INSANDAN GELIR, DAGITIM LIDERDEN

Klasor ve tarayicidaki kuralin aynisi. Lider baglayici SECMEZ: senin
magazana yazabilecek bir kapiyi kendi acsaydi, actigi kapinin
gerekcesini yine kendisi yazardi.

Ve aciklik **ISIN** ozelligidir, ajanin degil: is biter, aciklik biter.
"""

from __future__ import annotations

import subprocess

from .surec import PENCERE_YOK
import threading
import os
import json

#: Ajanin izin listesine eklenecek onek. Hesabin baglayicilari ajana
#: `mcp__claude_ai_<Ad>__<arac>` olarak gorunuyor (olculdu).
#:
#: ARAC VERILDIYSE IZIN DE VERILIR -- bunu bir kez odedik: `WebSearch`
#: arac listesindeydi, izin listesinde degildi ve ofis aylarca hic
#: arastirma yapamadi.
IZIN_ONEKI = "mcp__claude_ai"

#: Baglayicilari acan ortam degiskenleri.
#:
#: `ENABLE_TOOL_SEARCH` BIR ZAMANLAR maliyeti ucte bire indiriyordu
#: (131.543 -> 42.662 jeton, 19.09.2026). 22.09.2026'da yeniden
#: olculdu ve **ARTIK HICBIR SEY YAPMIYOR**:
#:
#:     baglayici ACIK + tool-search ACIK   : 225.765 jeton
#:     baglayici ACIK + tool-search KAPALI : 225.764 jeton
#:
#: Bir jeton fark. Kol olmus. Yine de KAPATILMIYOR: zararsiz, ve
#: yarin geri gelirse kendiliginden ise yarar. Ama ona GUVENEREK
#: maliyet hesabi yapilmaz.
#:
#: *Yanlis oldugu olculmemis bir kural, kural degil varsayimdir.*
ACAN_ORTAM = {
    "ENABLE_CLAUDEAI_MCP_SERVERS": "true",
    "ENABLE_TOOL_SEARCH": "true",
}

#: Baglayici acmanin OLCULMUS bedeli (jeton). Tahmin degil.
#:
#: OLCUM GECMISI -- sayi surekli BUYUYOR ve bu kaydin kendisi bir
#: uyaridir: hesaba her eklenen baglayici, baglayici kullanan HER
#: turu pahalilastirir.
#:
#:     19.09.2026   131.543  (tool-search yokken)
#:     21.09.2026    94.785  (tool-search ise yariyordu)
#:     22.09.2026   225.765  (tool-search olmus; katalog 223 arac)
#:
#: 22.09 dagilimi: Meta 96 arac (%43) · Atria 46 · Shopify 42 ·
#: Gmail 23 · Docs 8 · Drive 8. Baglayicisiz taban 7.688 jeton --
#: yani baglayicilar yuku **28 kata** cikariyor.
#:
#: BUNUN SERT BIR SONUCU VAR: 225k, haiku'nun 200k penceresine
#: SIGMIYOR. Baglayicili is haiku'da HIC kosamaz; sonnet ya da opus
#: sart. Rol kademesi `hizli` olan bir magaza ajani calismaz.
OLCULEN_EK_JETON = 225_000

#: Baglayicili is bu modellerde kosamaz -- katalog pencereye sigmiyor.
#: Tahmin degil, olculdu: haiku'da "Prompt is too long (~225.765 /
#: 200.000)".
#: 02.10.2026: ERTELENMIS YUKLEMEYLE (ENABLE_TOOL_SEARCH) haiku butun
#: baglayicilarla 18.848 jeton/tur kosar (olculdu) -- engel KALKTI.
DAR_PENCERELI_MODELLER = ()


class BaglayiciHatasi(RuntimeError):
    pass


#: Olcum ONBELLEGI. `claude mcp list` saglik denetimi yapiyor ve
#: ~15-20 sn suruyor; her sohbet mesajinda odenemez. Ama onbellek SESSIZ
#: olmaz: `olcum_zamani()` ne zaman olculdugunu soyler, boylece kimse
#: bayat bir sayiyi canli sanmaz.
#:
#: OLCULDU (29.09.2026): liderin "naber"e cevabi 29 sn surdu ve bunun
#: ~20 sn'si model DUSUNMEYE BASLAMADAN once bu olcumdu. Onbellek yalniz
#: surecin BELLEGINDEYDI: panel yeniden acilinca ve kabuktaki her `konus`ta
#: olcum bastan yapiliyordu. Artik DISKTE de durur ve lider onu
#: BEKLEMEDEN okur; bayatsa arka planda tazelenir.
_ONBELLEK = {"an": None, "veri": None}

#: Bu sureden eski olcum arka planda tazelenir (lider yine BEKLEMEZ, eski
#: olcumu zamaniyla gorur). Baglayici durumu dakikalar icinde degismez;
#: degistiginde insan zaten `claude mcp login` yapmistir ve o yol
#: (giris istegi) TAZE olcer.
BAYAT_SN = 30 * 60
_TAZELEME = {"kosuyor": False}
_KILIT = threading.Lock()


def _disk_yolu():
    from .yollar import ofis_evi
    return ofis_evi() / "baglayici_durum.json"


def _diskten_oku() -> bool:
    try:
        d = json.loads(_disk_yolu().read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("veri"), dict) and d.get("an"):
            _ONBELLEK["an"], _ONBELLEK["veri"] = d["an"], d["veri"]
            return True
    except (OSError, ValueError):
        pass
    return False


def _diske_yaz() -> None:
    """Atomik: yarim yazilmis bir dosya bir sonraki acilisi yaniltmasin."""
    try:
        yol = _disk_yolu()
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_suffix(".part")
        gecici.write_text(json.dumps({"an": _ONBELLEK["an"], "veri": _ONBELLEK["veri"]},
                                     ensure_ascii=False), encoding="utf-8")
        os.replace(gecici, yol)
    except OSError:
        pass     # yazamamak isi DURDURMAZ -- bir sonraki olcum yine dener


def olcum_zamani() -> str:
    """Onbellekteki olcum NE ZAMAN alindi. Bos ise hic olculmemis."""
    if _ONBELLEK["an"] is None:
        _diskten_oku()
    return _ONBELLEK["an"] or ""


def olcum_yasi_sn() -> float | None:
    an = olcum_zamani()
    if not an:
        return None
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(an)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds()
    except ValueError:
        return None


def onbellegi_bosalt() -> None:
    """Kullanici `claude mcp login` calistirdiktan sonra cagrilir."""
    _ONBELLEK["an"] = None
    _ONBELLEK["veri"] = None
    try:
        _disk_yolu().unlink()
    except OSError:
        pass


def _olc(zaman_asimi: int = 90) -> dict:
    """`claude mcp list`i GERCEKTEN kosturur. Sinamada bu islev degistirilir."""
    try:
        p = subprocess.run(["claude", "mcp", "list"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=zaman_asimi, shell=True, stdin=subprocess.DEVNULL,
                           creationflags=PENCERE_YOK)
    except Exception:
        return {}
    sonuc = {}
    for satir in (p.stdout or "").splitlines():
        if ":" not in satir or "claude.ai" not in satir:
            continue
        ad, _, kalan = satir.partition(":")
        ad = ad.replace("claude.ai", "").strip()
        if not ad:
            continue
        sonuc[ad] = {
            "bagli": "Connected" in kalan or chr(10004) in kalan,
            "url": kalan.split(" - ")[0].strip(),
        }
    return sonuc


def _sorunlari_isle(sonuc: dict) -> dict:
    # DORDUNCU HAL: bagli gorunuyor ama son GERCEK cagri dustu.
    # Bu bilgi `claude mcp list`ten gelmez -- ancak bir ajan o araci
    # gercekten cagirip basarisiz oldugunda ogrenilir (bkz. sorun_yaz).
    # Onbellekten okunurken de YENIDEN islenir: sorun hafizasi olcumden
    # bagimsiz degisir.
    for ad, kayit in sonuc.items():
        kayit["sorun"] = sorun_notu(ad) if kayit.get("bagli") else None
    return sonuc


def durum(zaman_asimi: int = 90, *, taze: bool = False) -> dict:
    """GERCEK baglayici durumu. `taze=True` olcumu BEKLER.

    Sabit bir liste tutmuyoruz. Tutsaydik kullanici bir baglayiciyi
    baglayinca ya da yetkisi dolunca liste bayatlardi -- ve bu dosyada
    zaten bir kez yasandi: "Shopify yetkisi dolmus" diye yazili olan
    sey olculdugunde **bagliydi**.

    Doner: `{ad: {"bagli": bool, "url": str}}`. Komut kosturulamazsa
    BOS doner ve cagiran bunu "bilinmiyor" diye ele alir -- olcemedigimize
    "iyi" demeyiz. Onbellek (bellek, yoksa disk) varsa beklemeden doner;
    hic olcum yoksa bir kez BEKLEYEREK olcer.
    """
    if not taze:
        if _ONBELLEK["veri"] is None:
            _diskten_oku()
        if _ONBELLEK["veri"] is not None:
            return _sorunlari_isle({a: dict(v) for a, v in _ONBELLEK["veri"].items()})
    sonuc = _olc(zaman_asimi)
    if sonuc:
        from .db import simdi
        _ONBELLEK["an"] = simdi()
        _ONBELLEK["veri"] = {a: {"bagli": v["bagli"], "url": v["url"]}
                             for a, v in sonuc.items()}
        _diske_yaz()
    return _sorunlari_isle(sonuc)


def arkada_tazele() -> bool:
    """Olcum bayatsa arka planda tazeler; BEKLEMEZ. Ayni anda tek tazeleme."""
    yas = olcum_yasi_sn()
    if yas is not None and yas < BAYAT_SN:
        return False
    with _KILIT:
        if _TAZELEME["kosuyor"]:
            return False
        _TAZELEME["kosuyor"] = True

    def is_():
        try:
            durum(taze=True)
        finally:
            _TAZELEME["kosuyor"] = False

    threading.Thread(target=is_, name="baglayici-tazele", daemon=True).start()
    return True


def lider_blogu(mevcut: dict = None) -> str:
    """Liderin GORDUGU baglayici envanteri.

    Kullanici sordu: *"ajan farkedebilecek mi bagli mi degil mi,
    soracak mi?"* -- cevap, lider envanteri GORMEDEN hayirdi. Klasorde
    aynisini bir kez odedik: lider dosya duzenini gormeden yol yazmis
    ve var olmayan bir klasor uydurmustu. **Gormeden karar vermek
    tahmindir.**

    DORT DURUM, ve asla uydurulmaz:
      - `BAGLI`      : CLI o baglayiciya erisebiliyor
      - `YETKI YOK`  : tanimli ama Claude Code girisi yapilmamis
      - `OLCULEMEDI` : komut kosmadi -- "yok" demek YANLIS olurdu
      - `SON CAGRI DUSTU` : bagli gorunuyor ama bir ajanin GERCEK
        cagrisi basarisiz oldu. Sebebi SOYLENMEZ cunku bilinmiyor;
        teshisi uydurmak gostergeyi yanlis gosteren yapardi.

    **OLCULMUS TUZAK (21.09.2026):** claude.ai WEB arayuzu ile CLI ayni
    seyi soylemiyor. Web'de Canva/Higgsfield/n8n/Supabase "bagli"
    gorunurken CLI "yetki bekliyor" diyor; `GitHub Integration` web'de
    var, CLI listesinde HIC YOK. Iki ayri kimlik deposu. Ofis CLI
    uzerinden kostugu icin **gecerli olan CLI'in gordugudur.**
    """
    # BEKLEMEZ: onbellek (bellek/disk) okunur, bayatsa arka planda
    # tazelenir. Liderin her mesaji ~20 sn olcumu bekliyordu (olculdu).
    if mevcut is None:
        d = durum()
        arkada_tazele()
    else:
        d = mevcut
    if not d:
        return ("## BAGLAYICILAR\n\nOLCULEMEDI -- `claude mcp list` "
                "kosmadi. Bir baglayici gerekiyorsa VARSAYMA, insana sor.")
    bagli = sorted(a for a in d if d[a]["bagli"] and not d[a].get("sorun"))
    sorunlu = sorted(a for a in d if d[a]["bagli"] and d[a].get("sorun"))
    yok = sorted(a for a in d if not d[a]["bagli"])
    satir = ["## BAGLAYICILAR (olculdu: " + (olcum_zamani() or "?") + ")", ""]
    satir.append("BAGLI (ise verilebilir): "
                 + (", ".join(bagli) if bagli else "(hicbiri)"))
    if sorunlu:
        # Ayri satir: "bagli" listesine karistirmak, dusen bir baglayiciyi
        # saglam gostermek olurdu.
        satir.append("BAGLI ama SON GERCEK CAGRI DUSTU (dikkat): "
                     + ", ".join(
                         f"{a} ({d[a]['sorun']['dakika']} dk once)"
                         for a in sorunlu))
    satir.append("YETKI YOK (verilemez): "
                 + (", ".join(yok) if yok else "(yok)"))
    satir += [
        "",
        "Kurallar:",
        "- Baglayici SECEMEZSIN. Yetki insandan gelir; sen yalnizca",
        "  GEREKTIGINI soylersin.",
        "- Bir is BAGLI olmayan bir baglayici gerektiriyorsa: isi ACMA,",
        "  patrona soyle ve hangi komutu calistirmasi gerektigini yaz",
        "  (`claude mcp login \"claude.ai <Ad>\"`).",
        "- Baglayici acmak turu ~225.000 jeton pahalilastirir (olculdu,",
        "  22.09.2026) ve HAIKU'YA SIGMAZ -- baglayicili is sonnet/opus",
        "  ister. Gerekmiyorsa isteme; tek bir ekrandan okunacak bilgi",
        "  icin TARAYICI cok daha ucuzdur.",
        "- BAGLI olmasi o hesabin BIZIM oldugunu KANITLAMAZ. Hangi hesaba",
        "  bagli oldugu bir OLGUdur; bilmiyorsan sor, varsayma.",
        "- SON CAGRI DUSTU isaretli bir baglayiciya is verebilirsin ama",
        "  kabul olcutune 'cagri gercekten calisti' kanitini KOY; sebebini",
        "  bilmiyoruz, yalnizca dustugunu biliyoruz.",
    ]
    return "\n".join(satir)


def _anahtarla(ad: str) -> str:
    """Karsilastirma icin sadelestirir: 'Meta Reklamlari' -> 'metareklamlari'."""
    return "".join(ch for ch in (ad or "").lower() if ch.isalnum())


# ══════════════════════ SORUN HAFIZASI ══════════════════════
#
# DORDUNCU DURUM -- ama UYDURULAN degil, OLCULEN.
#
# Rakipte entegrasyon rozeti dort hal gosteriyor ve biri "CONNECTED ·
# SCOPE SHORT" (bagli ama yetki dar, eksik izni adiyla soyler). Ayni
# dorduncu hali biz de yazacaktik; once olculdu:
#
#     `claude mcp list` YALNIZCA iki sey doner:
#         "Connected"  /  "Needs authentication"
#     Kapsam (scope) bilgisi HIC YOK.
#
# Yani "yetki dar" durumunu SORARAK ogrenemeyiz. Onu ekleseydik,
# olcemedigimiz bir seye hukum vermis olurduk -- bu dosyanin ilk
# cumlesi tam bunun aksini soyluyor.
#
# Ama ogrenilebilecek GERCEK bir sey var: bir ajan o baglayiciyi
# GERCEKTEN cagirdi ve cagri DUSTU. Bu bir olcumdur. `gorsel.py`de
# ayni deseni bir kez kurduk ve kendini kanitladi: *kotayi olcmek bir
# istek harcar, o yuzden tahmin etmiyoruz -- HATIRLIYORUZ.*
#
# Bu yuzden dorduncu durumun adi "YETKI DAR" DEGIL:
#
#     BAGLI ama SON GERCEK CAGRI DUSTU
#
# Sebebini soylemiyoruz cunku bilmiyoruz -- yetki dar olabilir, uzak
# sunucu bozuk olabilir, arac adi degismis olabilir. Tesihisi uydurmak,
# gostergeyi yanlis gosteren yapardi.

import json as _json
import os as _os
from pathlib import Path as _Path
from .yollar import OFIS_EVI as _OFIS_EVI

#: Defter proje kokunun DISINDA -- kasa ve kota defteriyle ayni yerde.
#: Bu bir CALISMA DURUMU, proje verisi degil; ayrica ofis kurulmadan da
#: okunabilmeli.
SORUN_DEFTERI = _OFIS_EVI / "baglayici_sorun.json"

#: Bayat kayit yok sayilir. Yetki yenilenir, sunucu duzelir -- dunku bir
#: arizayi bugun gostermek, calisan bir baglayiciyi bozuk gostermek
#: olurdu ve bu tam duzeltmeye calistigimiz hatanin aynasi.
SORUN_TAZE_SANIYE = 12 * 3600


def sorun_yaz(ad: str, mesaj: str) -> None:
    """Bir baglayiciya yapilan GERCEK cagrinin dustugunu kaydeder.

    Yazamamak isi DURDURMAZ: hafiza bir kolayliktir, bir kapi degil.
    """
    try:
        SORUN_DEFTERI.parent.mkdir(parents=True, exist_ok=True)
        defter = {}
        if SORUN_DEFTERI.exists():
            defter = _json.loads(SORUN_DEFTERI.read_text(encoding="utf-8"))
        from .db import simdi
        defter[_anahtarla(ad)] = {"ad": ad, "an": simdi(),
                                  "mesaj": (mesaj or "")[:300]}
        gecici = SORUN_DEFTERI.with_suffix(".tmp")
        gecici.write_text(_json.dumps(defter, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        gecici.replace(SORUN_DEFTERI)          # yerinde yazma ATOMIK olmali
    except (OSError, ValueError, TypeError):
        pass


def sorun_notu(ad: str) -> dict | None:
    """Taze bir ariza kaydi varsa doner, yoksa None."""
    try:
        if not SORUN_DEFTERI.exists():
            return None
        defter = _json.loads(SORUN_DEFTERI.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    kayit = defter.get(_anahtarla(ad))
    if not isinstance(kayit, dict):
        return None
    from .db import simdi
    from datetime import datetime
    try:
        gecen = (datetime.fromisoformat(simdi())
                 - datetime.fromisoformat(kayit["an"])).total_seconds()
    except (ValueError, KeyError, TypeError):
        return None
    if gecen > SORUN_TAZE_SANIYE:
        return None
    kayit = dict(kayit)
    kayit["dakika"] = int(gecen // 60)
    return kayit


def sorunu_temizle(ad: str) -> None:
    """Basarili bir cagri gelince kaydi duser.

    Bu SART: duzelmis bir baglayiciyi bozuk gostermeye devam etmek,
    yanlis gosteren gostergenin ta kendisi olurdu.
    """
    try:
        if not SORUN_DEFTERI.exists():
            return
        defter = _json.loads(SORUN_DEFTERI.read_text(encoding="utf-8"))
        if defter.pop(_anahtarla(ad), None) is None:
            return
        gecici = SORUN_DEFTERI.with_suffix(".tmp")
        gecici.write_text(_json.dumps(defter, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        gecici.replace(SORUN_DEFTERI)
    except (OSError, ValueError, TypeError):
        pass


def arac_adindan(arac: str) -> str | None:
    """`mcp__claude_ai_Shopify__get-shop-info` -> `Shopify`.

    Baska bir arac adi (`Write`, `mcp__ofis__kanit_ekle`, `mcp__tarayici__…`)
    None doner -- yalnizca hesabin baglayicilari sayilir.
    """
    onek = IZIN_ONEKI + "_"
    if not arac or not arac.startswith(onek):
        return None
    kalan = arac[len(onek):]
    ad, _, _arac = kalan.partition("__")
    return ad.replace("_", " ").strip() or None


def dogrula(adlar, *, mevcut: dict = None) -> list:
    """Istenen baglayicilari dogrular. Sira ve benzersizlik korunur.

    REDDEDER:
      - **Tanimsiz ad.** Yanlis yazilmis bir baglayici adi sessiz bir
        olum sebebidir: is acilir, ~225k jeton odenir, ajan aradigini
        bulamaz ve sebebini kimse bilmez.
      - **Yetki bekleyen baglayici.** KAPALI KALARAK basarisiz oluruz:
        kimlik dogrulamasi olmayan bir baglayiciyi ise baglamak, parasi
        odenmis ama calismayacak bir tur demektir. Insan once
        `claude mcp login <ad>` calistirmali.
    """
    istenen = [a for a in (adlar or []) if str(a).strip()]
    if not istenen:
        return []
    mevcut = durum() if mevcut is None else mevcut
    if not mevcut:
        raise BaglayiciHatasi(
            "Baglayici durumu OLCULEMEDI (`claude mcp list` kosmadi). "
            "Olcemedigimize 'bagli' demeyiz; is baglayicisiz acilmali "
            "ya da once komut elle denenmeli.")

    harita = {_anahtarla(a): a for a in mevcut}
    out, hatalar = [], []
    for ham in istenen:
        anah = _anahtarla(ham)
        gercek = harita.get(anah)
        if gercek is None:
            hatalar.append(
                f"'{ham}' diye bir baglayici YOK. Gecerli olanlar: "
                + ", ".join(sorted(mevcut)))
        elif not mevcut[gercek]["bagli"]:
            hatalar.append(
                f"'{gercek}' yetki bekliyor -- once `claude mcp login "
                f"\"claude.ai {gercek}\"` calistirilmali. Yetkisiz "
                "baglayiciyla is acmak, odenmis ama calismayan bir tur olur.")
        elif gercek not in out:
            out.append(gercek)
    if hatalar:
        raise BaglayiciHatasi(" | ".join(hatalar))
    return out


def ortam(baglayicilar) -> dict:
    """Turun ortam eklentisi. Bos istekte BOS doner -- yani hicbir
    baglayici yuklenmez ve ~225k jeton hic odenmez."""
    return dict(ACAN_ORTAM) if baglayicilar else {}


def ozet(baglayicilar) -> str:
    """Insana tek satir: ne acildi, kaca mal oluyor, ve HEPSI aciliyor."""
    if not baglayicilar:
        return "baglayici: YOK (gorev bildirmemis, ek jeton odenmiyor)"
    return (f"baglayici: {', '.join(baglayicilar)} isin niyeti olarak kayitli"
            f" · hesabin baglayicilari her turda ERTELENMIS yuklu (02.10.2026)")
