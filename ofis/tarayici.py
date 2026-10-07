# -*- coding: utf-8 -*-
"""TARAYICI -- ajanin web'e dokunmasi.

Kullanici: *"tarayiciyi acip tiklama, gezinme yapabilecekler mi?"*

**Evet, ve ayri bir arac yazmadik: `@playwright/mcp` zaten kurulu.**
Olculdu (20.09.2026): `npx @playwright/mcp` ayaga kalkiyor ve **25 arac**
veriyor -- `browser_navigate`, `browser_click`, `browser_type`,
`browser_fill_form`, `browser_snapshot`, `browser_evaluate`,
`browser_take_screenshot`, `browser_file_upload`, `browser_tabs`...

## Neden baglayici sorunu buna UYGULANMIYOR

Hesabin claude.ai baglayicilarini ajana vermek olculdu ve pahali:
131.543 jeton, `Prompt is too long`. Playwright MCP ise **yerel bir
stdio sureci** -- OAuth yok, hesaba dokunmuyor. Dogrudan
`--mcp-config`e yazilir. Yani tarayici, magaza/reklam baglayicilarini
BEKLEMEDEN acilabilir.

## "Piksele tiklama" degil -- erisilebilirlik agaci

Model ekran goruntusune bakip koordinat tiklamiyor: her oge bir `ref`
ile geliyor ve model `ref`e tikliyor. Daha guvenilir, daha ucuz.

**OLCULMUS TUZAK:** tam sayfa anlik goruntusu kolayca patlar -- bu
oturumda bir `browser_snapshot` **105.727 karakter** dondu ve yanit
sinirini asti. Bu yuzden varsayilanlar dar: `--mobile` (Playwright'in
kendi belgesi *"mobil sayfalar daha hafif, jeton tasarrufu"* diyor) ve
kisa eylem zaman asimi.

## Bayraklar bizim kavramlara oturuyor -- icat etmiyoruz, esliyoruz

| bizim kavram | playwright bayragi |
|---|---|
| yazma alani (kilit) | `--allowed-origins` -- is hangi siteye dokunabilir |
| hesap (kimlik) | `--user-data-dir` -- ayri profil, ayri oturum |
| tekrarlanabilir tur | `--isolated` -- profil bellekte, diske yazmaz |
| gorsel kaniti | `browser_take_screenshot` |
| jeton tavani | `--mobile` |
| donma korkulugu | `--timeout-action` / `--timeout-navigation` |

## TARAYICI ISIN OZELLIGIDIR, AJANIN DEGIL

Klasorle ayni kural: acikligi **is** beyan eder. `tarayici_alani` bos
olan gorev tarayici HIC gormez. Ajana yazsaydik bir kez acilan erisim
o ajanin butun gelecek islerinde acik kalirdi -- kimse fark etmeden
genisleyen bir yetki.

## OLCULMUS SINIR -- kapi YONLENDIRMEDE gecirgen (20.09.2026)

`--allowed-origins` yazma kilidinin web hali ama **birebir ayni degil.**
Ilk gercek tarayici isinde catisan iki gozlem cikti ve olculdu:

| gidis | sonuc |
|---|---|
| DOGRUDAN beyan disi (`docs.claude.com`) | **ENGELLENDI** (`ERR_BLOCKED_BY_CLIENT`) |
| beyan edilenden YONLENDIRME (`www.anthropic.com/api` -> `claude.com`) | **GECTI** |

Yani kapi *dogrudan* gidisi tutuyor, ama **beyan edilen bir kaynak seni
baska bir yere gonderirse oraya gidilir.** Guven sinirimiz "su kaynak"
degil, "su kaynak VE onun yonlendirdigi yerler".

Bu bir kusur degil bir **sinirdir** ve yazili olmasi gerekiyordu;
kesfedilmesi degil. Yazma kilidiyle farki onemli: kilit disariya
YAZMAYA asla izin vermez, bu kapi disariyi OKUMAYA yonlendirmeyle izin
verebilir. Bu yuzden tarayici alani verirken *"bu siteye guveniyor
muyum"* sorusu, *"bu site beni nereye gonderebilir"* sorusunu da
icerir.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

#: MCP yapilandirmasindaki sunucu adi. Araclar ajana
#: `mcp__tarayici__browser_*` olarak gorunur.
SUNUCU_ADI = "tarayici"

#: Ajanin izin listesine eklenecek onek (bkz. motor/claude.py).
IZIN_ONEKI = "mcp__tarayici"

#: OKUMA ARACLARI -- siteye ETKI ETMEZ, yalnizca bakar.
#:
#: Bu ayrim bir liste degil bir KAPIDIR ve yapiyla uygulanir: yazma
#: araci ISE VERILMEZSE ajan tiklayamaz. Brifingde "dikkatli ol" demek
#: kural degildir -- `tur='kafa'` ajanin yazamamasi da boyle, aracin
#: HIC OLMAMASIYLA saglaniyor.
#:
#: NEDEN VARSAYILAN OKUMA: bir tarayici hesabina giris yapilmissa,
#: oradaki bir tiklama fiyat degistirebilir, yayina alabilir, PARA
#: HARCAYABILIR. Ofisin kendi kurali zaten yaziliydi -- *"kod yazmak
#: sormaz; para harcamak, yayina almak, disariya yazmak sorar"* -- ama
#: tarayicida hic uygulanmiyordu. Burasi o kuralin tarayici hali.
TARAYICI_OKUMA = (
    "browser_navigate", "browser_navigate_back", "browser_snapshot",
    "browser_find", "browser_take_screenshot", "browser_console_messages",
    "browser_network_request", "browser_network_requests",
    "browser_wait_for", "browser_tabs", "browser_resize",
    "browser_close", "browser_emulate_media",
)

#: YAZMA ARACLARI -- siteye ETKI EDER. Ise ACIKCA verilmedikce yok.
#:
#: `browser_evaluate` BURADA, ve bu ayrimin en onemli yeri: adi
#: "degerlendir" oldugu icin okuma sanilir, oysa ISTEDIGI JavaScript'i
#: kosturur -- tiklar, form gonderir, sayfayi degistirir. Okuma
#: listesine koysaydik kapi HIC KAPANMAZDI; hic reddetmeyen kapi, kapi
#: degildir.
#:
#: BEDELI OLCULDU VE KABUL EDILDI: ilk gercek tarayici isinde ajan
#: `browser_evaluate`i 7 kez HEDEFLI OKUMA icin kullanmisti ve bu
#: `browser_snapshot`tan cok daha ucuzdu (bir anlik goruntu 105.727
#: karakterle yaniti patlatmisti). Salt okunur kipte o ucuz yol kapali;
#: yerine `browser_find` var. Jeton biraz artar, kapi gercekten kapanir.
TARAYICI_YAZMA = (
    "browser_click", "browser_type", "browser_fill_form",
    "browser_press_key", "browser_select_option", "browser_hover",
    "browser_drag", "browser_drop", "browser_file_upload",
    "browser_handle_dialog", "browser_evaluate", "browser_run_code_unsafe",
)


#: Ofisin HIC SUNMADIGI araclar. Vekil bunlari `tools/list`ten duserir;
#: izin listesi de ayni listeyi kullanir.
#:
#: TEK KAYNAK OLMAK ZORUNDA: iki ayri liste tutsaydik biri gunun birinde
#: otekinden ayrisirdi ve izin listesi, ajanin hic goremeyecegi bir araci
#: "acik" gosterirdi -- yanlis gosteren bir gosterge.
#:
#: `browser_run_code_unsafe` burada cunku Playwright'in kendisi ona
#: "unsafe" diyor: istedigi JavaScript'i kosturur, yani riskli eylem
#: kapisinin okuyabilecegi bir hedefi YOKTUR. Bu, kullanicinin itiraz
#: ettigi "tiklamayi engellemek" degil -- gezmek ve tiklamak serbest.
SUNULMAYAN = ("browser_run_code_unsafe",)


def izinli_araclar(yazma: bool = True) -> tuple:
    """Ise verilecek tarayici araclarinin TAM listesi.

    ## VARSAYILAN ARTIK ACIK -- ve sebebi bir kullanici karari

    Bu islev bir sure `yazma=False` varsayiliyla kosti: tarayici acilan
    is gezebiliyor ama tiklayamiyordu. Kullanici itiraz etti ve hakliydi:

        "ajanlarin tarayicida gezmesini tiklamasini engellemek bana
         sacma geldi; ajanlar calissin tiklasin gezsin bilgi alsin is
         varsa yapsin."

    Guvenlik o cite degil, **kapiya** tasindi (`tarayici_kapi.py`):
    tiklamak serbest, riskli tiklama insana sorulur. Citin bedeli
    olculmustu -- `browser_evaluate` kapali kalinca ajan pahali
    `browser_snapshot`a dusuyordu (bir olcumde 105.727 karakter).

    `yazma=False` SILINMEDI: bir isi bilerek salt okunur yapmak hala
    mesru (ornegin rakip fiyat taramasi -- orada tiklamaya hic gerek
    yok ve vermemek en ucuz koruma). Ama artik VARSAYILAN degil,
    ACIK BIR DARALTMA.

    Onek (`mcp__tarayici`) yerine ARAC ARAC verilir: onek verseydik
    yarin Playwright'in ekledigi bir arac, biz hic gormeden ajanin
    eline gecerdi.
    """
    adlar = list(TARAYICI_OKUMA) + (list(TARAYICI_YAZMA) if yazma else [])
    adlar = [a for a in adlar if a not in SUNULMAYAN]
    return tuple(f"{IZIN_ONEKI}__{a}" for a in adlar)


#: Varsayilan bayraklar. Hepsi bir OLCUME dayaniyor:
#: - `--mobile`     : tam sayfa anlik goruntusu 105.727 karakterle yaniti
#:                    patlatti; mobil sayfalar daha hafif.
#: - `--isolated`   : profil diske yazilmaz -> tur tekrarlanabilir olur
#:                    ve ajan insanin gercek oturumlarini gormez.
#: - eylem 8sn      : donmus bir tiklama turu sonsuza kadar bekletmesin.
#: - gezinme 30sn   : agir sayfalar icin daha genis ama sinirsiz degil.
VARSAYILAN_BAYRAKLAR = (
    "--mobile",
    "--isolated",
    "--timeout-action", "8000",
    "--timeout-navigation", "30000",
    "--block-service-workers",
    "--allow-unrestricted-file-access",
)
# `--allow-unrestricted-file-access` (01.10.2026). OLCULDU (gercek set G18,
# claude): ajan kendi yazdigi todo uygulamasini `file:///...` ile acmak
# istedi; Playwright MCP "Access to file: protocol is blocked" dedi (--help:
# file:// VARSAYILAN KAPALI), is geri dondu. Bayrak tarayiciya kok disini
# da acar -- ama ajanin kabuk erisimi zaten diski okuyabiliyor; yeni bir
# yetenek degil, kendi sayfasini GORMESI. Brifing de `file:///` diyor.


class TarayiciHatasi(Exception):
    pass


#: Vekilin onay kaydina yazdigi, koltugun okudugu yeni-site satiri.
#: Iki uc AYNI sabiti kullanir -- iki ayri yazim ayrisirsa onaylanan site
#: bir sonraki turda sessizce acilmazdi.
KAYNAK_ISARETI = "KAYNAK:"
#: Kredi paketi onayinin `ayrinti` ilk satiri (07.10.2026). Yazan MCP
#: `onay_iste(kredi, uretim)`, okuyan tarayici kapisi.
KREDI_PAKETI_ISARETI = "KREDI_PAKETI:"


def kaynak_normalle(deger: str) -> str:
    """Bir URL'yi ORIGIN'e indirger: `https://a.com/x/y?z` -> `https://a.com`.

    Kullanici tam adres yazar, Playwright origin bekler. Cevirmeseydik
    `--allowed-origins`e yol iceren bir deger giderdi ve eslesme
    sessizce tutmazdi -- ajan "erisemedim" derdi, sebebi gorunmezdi.
    """
    metin = (deger or "").strip()
    if not metin:
        raise TarayiciHatasi("Bos kaynak verilemez.")
    if "://" not in metin:
        # Sema yoksa https varsayilir; http'ye DUSMEYIZ -- sessizce
        # sifrelenmemis baglantiya gecmek, kullanicinin beklemedigi bir
        # guvenlik gevsemesidir.
        metin = "https://" + metin
    p = urlparse(metin)
    if not p.scheme or not p.netloc:
        raise TarayiciHatasi(
            f"Kaynak cozulemedi: {deger!r}. Ornek: https://ornek.com")
    if p.scheme not in ("http", "https"):
        raise TarayiciHatasi(
            f"Yalniz http/https: {deger!r}. `file://` erisimi kapalidir "
            "(Playwright varsayilani da boyle).")
    return f"{p.scheme}://{p.netloc}"


def kaynaklari_dogrula(hamlar) -> list:
    """Coklu hal. Sira ve benzersizlik korunur."""
    out = []
    for h in (hamlar or ()):
        k = kaynak_normalle(h)
        if k not in out:
            out.append(k)
    return out


def sunucu_girdisi(kaynaklar, *, profil: str = "", gorunur: bool = False,
                   cdp: str = "", ek_bayraklar=(), kimlik: dict = None,
                   serbest: bool = False, kabin_izleme: bool = False) -> dict:
    """`--mcp-config` icin tarayici sunucusu girdisi.

    `kaynaklar` BOS ve `serbest=False` ise `None` doner: tarayici
    verilmez.

    SERBEST TARAYICI (24.09.2026, kullanici karari): *"claude code ve
    codex'i terminalde nasil kullaniyorsam ajanlar da oyle calissin."*
    Claude Code bir siteyi acmak icin izin istemez; asil koruma
    TIKLAMADADIR ve o vekilde (`tarayici_kapi.py`) her kipte duruyor:
    geri alinamaz / disari cikan / para iceren eylem patrona sorulur.
    Bu yuzden `serbest=True` ve kaynak listesi bossa `--allowed-origins`
    HIC verilmez. Liste doluysa (insan bilerek daraltmis) eskisi gibi
    o sitelerle sinirlidir.

    KABIN (cdp) SERBEST OLMAZ: orada insanin oturumlari (magaza paneli,
    e-posta) yasar. Kabin yalniz insanin isaret ettigi kaynaklarla acilir.
    TEK ISTISNA `kabin_izleme=True`: patron paneldeki "Ajanlar kabinde"
    anahtarini BILEREK acti (29.09.2026, kullanici: "muratin sisteminde
    ajanlar gomulu tarayiciyi kullaniyor, bizde de olmali"). O zaman kabin
    serbesttir; koruma yine tiklamada (vekil) ve sifre kuralinda durur.
    Yetki insandan gelir: anahtar kapaliyken bu kip HIC kurulmaz.

    ## Playwright DOGRUDAN verilmez -- ofisin KAPISI uzerinden verilir

    Ajan `@playwright/mcp` ile konusmaz; `ofis/tarayici_kapi.py` ile
    konusur ve o Playwright'i cocuk surec olarak kosturur. Sebep
    kullanicinin kurali: *"ajanlar calissin tiklasin gezsin, fakat
    riskli durumlarda onay isteyip yapicaklar."* Bir tiklamanin riskli
    olup olmadigina ancak ARADA DURAN biri bakabilir.

    Dogrudan verilseydi tek alternatif izin listesini kismaktir ve o
    liste MOTORA BAGLIDIR: Claude uygular, codex uygulamaz, gemini
    `izinli_araclar` verilince turu hic baslatmaz. Kapi vekilde
    yasayinca kural **her motorda** ayni.

    `kimlik`: vekilin onay defterine ulasmasi icin ortam (OFIS_DB,
    OFIS_PROJE, OFIS_AJAN, OFIS_GOREV). Verilmezse vekil yine kosar ama
    riskli eylemi **reddeder** -- onay isteyemedigi icin kapali kalarak
    basarisiz olur.

    `profil`: hesabin tarayici profili (`--user-data-dir`). Verilirse
    `--isolated` DUSER -- ikisi celisir: biri profili diske yazmayi
    ister, oteki yazmamayi. Celiskiyi sessizce cozmek yerine acikca
    seciyoruz: profil verildiyse kimlik istenmistir.
    """
    kaynaklar = list(kaynaklar or ())
    if not kaynaklar and (not serbest or (cdp and not kabin_izleme)):
        return None

    if cdp:
        # KABIN KIPI: tarayici ZATEN acik, biz ona bagleniyoruz.
        #
        # Baslatma bayraklari burada UYGULANAMAZ (`--mobile`,
        # `--isolated`, `--user-data-dir`, `--headless` hepsi acilis
        # ayaridir). Onlari yine de gecirseydik "sessizce yok sayilan
        # ayar" olurlardi -- bu projede alti kez odenen sinif. O yuzden
        # ACIKCA dusuruluyorlar ve bedeli yazili:
        #
        #   `--mobile` DUSER. Olculmus bedeli var: mobil olmayan tam
        #   sayfa anlik goruntusu bir kez 105.727 karakterle yaniti
        #   patlatmisti. Kabin kipinde ajan `browser_snapshot` yerine
        #   hedefli `browser_find`/`browser_evaluate` tercih etmeli.
        #
        # KALAN VE OLCULEN: `--allowed-origins` CDP'de de TUTUYOR
        # (beyan disi gidis `net::ERR_BLOCKED_BY_CLIENT` ile reddedildi).
        # Tutmasaydi kabin, yazma kilidinin web halini sessizce
        # kaldirirdi ve bu ozellik hic yazilmazdi.
        bayraklar = ["--cdp-endpoint", cdp, "--allow-unrestricted-file-access",
                     "--timeout-action", "8000",
                     "--timeout-navigation", "30000"]
    else:
        bayraklar = [b for b in VARSAYILAN_BAYRAKLAR]
        if profil:
            bayraklar = [b for b in bayraklar if b != "--isolated"]
            bayraklar += ["--user-data-dir", profil]
        if not gorunur:
            bayraklar.append("--headless")
    # Beyan edilmeyen kaynak acilmaz -- yazma kilidinin web hali.
    # Serbest kipte liste yoktur: her site acilir, riskli EYLEM vekilde
    # sorulur (vekil liste gormeyince yeni-site sorusunu da sormaz).
    if kaynaklar:
        bayraklar += ["--allowed-origins", ";".join(kaynaklar)]
    bayraklar += list(ek_bayraklar or ())

    # Vekil MUTLAK yolla cagrilir. Goreli yol verseydik surec sinirini
    # gecen bir tuzak kurardik: MCP sunucusu AJANIN klasorunde kosar ve
    # ayni goreli yol oradan baska bir yere cozulur -- "hayalet
    # veritabani" tam boyle olmustu.
    vekil = str(Path(__file__).resolve().parent / "tarayici_kapi.py")
    return {
        "command": sys.executable,
        "args": [vekil, "--"] + bayraklar,
        "env": dict(kimlik or {}),
        # Tarayici isi verilen turda araclar ERTELENMEZ (02.10.2026): her
        # tarayici adiminda once arama yapmak bos tur ve jeton olurdu.
        "alwaysLoad": True,
    }


def ozet(kaynaklar, *, profil: str = "", gorunur: bool = False,
          cdp: str = "", yazma: bool = True, kabin_izleme: bool = False) -> str:
    """Insana tek satirda: tarayici ne kadar acik."""
    kip = "tiklayabilir (riskli eylem ONAYA duser)" if yazma else \
        "SALT OKUNUR (bilerek daraltildi)"
    if not kaynaklar and cdp and kabin_izleme:
        return (f"tarayici[{kip}]: SERBEST · KABIN ({cdp}) -- panelde CANLI "
                "izleniyor, patronun oturumlariyla (\"Ajanlar kabinde\" acik)")
    if not kaynaklar:
        if cdp:
            return "tarayici: YOK (kabin yalniz isaret edilen sitelerle acilir)"
        return (f"tarayici[{kip}]: SERBEST -- her site acilabilir"
                f" · {'gorunur' if gorunur else 'gizli'}"
                f" · profil: {profil or 'yalitilmis (diske yazmaz)'}")
    if cdp:
        return (f"tarayici[{kip}]: {len(kaynaklar)} kaynak ({', '.join(kaynaklar)})"
                f" · KABIN ({cdp}) -- panelde gorunur, insanla PAYLASILIR"
                " · --mobile dusuyor (jeton pahalisi)")
    return (f"tarayici[{kip}]: {len(kaynaklar)} kaynak ({', '.join(kaynaklar)})"
            f" · {'gorunur' if gorunur else 'gizli'}"
            f" · profil: {profil or 'yalitilmis (diske yazmaz)'}")


# ---------------------------------------------------------------------------
# KABIN -- panelin ICINDE gorunen, ajanla PAYLASILAN tarayici
# ---------------------------------------------------------------------------
#
# Kullanici: *"sistemden cikip baska yerden chrome acip ugrasmak istemem,
# sistemin icinde tarayici olsa daha iyi olur."*
#
# ONCE YANLIS OLCTUM. "Gomulu tarayici yapilamaz" derken `iframe`i
# olcmustum ve `X-Frame-Options: SAMEORIGIN` yuzunden tam kullanicinin
# calistigi yerler (Shopify admin, Gmail) cerceveye girmiyordu. Bundan
# "ancak Tauri ile olur" sonucunu cikardim -- YANLISTI.
#
# ChatGPT'nin ajan tarayicisi da iframe kullanmaz: uzaktaki bir
# tarayicinin KARELERINI akitir. O yol bir web sayfasinda aciktir.
#
# OLCULDU (22.09.2026), gercek Chrome ile:
#   ilk kare 445 ms · kare ~16,8 KB (jpeg q60) · ~0,03 MB/sn
#   `Input.dispatchMouseEvent` ile TIKLAMA gonderildi, hata yok
# Yani yalnizca izlenmiyor, KULLANILABILIYOR.
#
# VE ASIL KAPI OLCULDU -- mimariyi bu belirledi:
#
#   CDP'ye baglanan Playwright MCP'de `--allowed-origins` HALA TUTUYOR.
#     beyan edilen  example.com    -> gecti
#     beyan disi    wikipedia.org  -> net::ERR_BLOCKED_BY_CLIENT
#
# Tutmasaydi panel-ici tarayici, yazma kilidinin web halini SESSIZCE
# kaldirirdi -- projenin karsi kuruldugu hata sinifi. Tuttugu icin tek
# bir tarayici hem insanin hem ajanin olabiliyor.
#
# AYRI PROFIL, BILEREK: kabin kullanicinin gunluk Chrome'u DEGILDIR.
# Ayni profili kullansaydik ajan, insanin butun oturumlarini (banka,
# e-posta) gorurdu. Kabin kendi profilinde yasar; oraya ne ile giris
# yapildigi insanin acik tercihidir.

#: Kabinin CDP kapisi. 127.0.0.1'e baglidir -- Chrome uzak hata
#: ayiklamayi disariya zaten acmaz, ama bu bir YEREL arka kapidir:
#: makinede kosan her sey o tarayiciyi surebilir. Panelin `0.0.0.0`
#: reddiyle ayni sinifta bir karar, ve yazili olmasi gerekiyor.
#:
#: F3 / E25 (28.09) -- NE KORUNUYOR, NE KORUNMUYOR:
#:   * WEB SAYFALARI kabini SUREMEZ: Chrome, Origin basligi tasiyan
#:     WebSocket baglantisini `--remote-allow-origins` verilmedikce
#:     reddeder. Kabin bu bayragi TASIMAZ (sinaniyor) -- yani insanin
#:     kendi tarayicisinda acilan kotu niyetli bir site kabine baglanamaz.
#:   * Kabin VARSAYILAN KAPALI ve AYRI profilde (kisisel Chrome degil).
#:   * KORUNMAYAN: bu bilgisayarda zaten kosan yerel bir program. Ona
#:     karsi koruma isletim sisteminin isi; yazili sinir.
#: SINAMA AYRI KAPIDA (02.10.2026): "ajanlar kabinde" varsayilan ACIK
#: olunca gecici ofislerdeki sinama/deneme ajanlari patronun ACIK kabinine
#: (9222) girebilirdi. Sinama surecleri `OFIS_KABIN_KAPI` ile baska kapi
#: kullanir (`testler/_temizlik.py`, `ofis_kopyasi.py`).
import os as _os
KABIN_KAPISI = int(_os.environ.get("OFIS_KABIN_KAPI") or 9222)

#: Kabin profili proje kokunun DISINDA durur (kasayla ayni klasor):
#: cerez ve oturum bir CALISMA DURUMUDUR, proje verisi degil -- ve
#: ajanlarin `Bash(cat *)` izni proje kokunde geciyor.
KABIN_PROFIL_ADI = "tarayici-kabini"


def kabin_komutu(calistirilabilir: str, *, profil: str,
                 kapi: int = KABIN_KAPISI, baslangic: str = "about:blank",
                 en: int = 1280, boy: int = 800,
                 gorunur: bool = False) -> list:
    """Paylasilan tarayiciyi baslatan komut satiri.

    Saf: surec BASLATMAZ, yalnizca argumanlari kurar. Boylece
    sinanabilir -- bu modulun geri kalani da oyle. Sureci panel
    yonetir, cunku omru panelin omrudur.

    ## BASSIZ VARSAYILAN -- olculdu (22.09.2026), duzeltilen bir kusur

    Bu komut bir sure `--headless` TASIMIYORDU ve kabin arkada
    GORUNUR bir Chrome penceresi aciyordu. Panel onu yansitiyordu,
    yani "panelin ICINDE tarayici" degil "ayri bir Chrome'un aynasi"
    olmustu. Kullanici bunu kullanirken gordu ve hakliydi.

    Benim hatam bir OLCUMDEN degil bir CIKARIMDAN geliyordu: `iframe`in
    `X-Frame-Options` ile kapali oldugunu olcup "gomulemez" diye
    genellemistim. **Bir yolun kapali oldugunu olcmek, butun yollarin
    kapali oldugunu gostermez.**

    Bassiz kip olculdu ve UC sey birden dogrulandi:

        gorunur pencere (PID suzgecli)  : 0   (basliyken 1)
        ilk kare                        : 20 ms   (basliyken 445 ms)
        Input.dispatchMouseEvent        : tiklama GECTI

    Ve kabinin var olma sarti yeniden olculdu -- degisen bir sey
    olsaydi kabin, yazma kilidinin web halini SESSIZCE kaldirirdi:

        Playwright MCP --cdp-endpoint   : bassiz Chrome'a BAGLANDI
        beyan EDILEN kaynak             : GECTI
        beyan DISI kaynak               : REDDEDILDI

    ## AMA `gorunur` KOLU DURUYOR -- ve sebebi olculmemis bir risk

    Bazi siteler bassiz tarayiciyi tanir ve girise izin vermez. Bunu
    OLCMEDIK; olcmedigimiz bir sey yuzunden insani kilitli birakmamak
    icin kol var. Kolu cevirmek bir KARARDIR: pencere gorunur olur,
    kabin artik "gomulu" degildir, ve panel yalnizca aynadir.
    """
    if not str(calistirilabilir or "").strip():
        raise TarayiciHatasi("Tarayici calistirilabiliri bulunamadi.")
    if not str(profil or "").strip():
        # Profilsiz baslatmak, kullanicinin GERCEK Chrome profilini
        # kullanmak demektir (Chrome varsayilani). Ajan o tarayiciya
        # baglanacagi icin bu, butun kisisel oturumlari ajana acardi.
        raise TarayiciHatasi(
            "Kabin profilsiz acilmaz: ajan bu tarayiciya baglanir ve "
            "kisisel profil onun eline gecerdi.")
    return [
        str(calistirilabilir),
        f"--remote-debugging-port={int(kapi)}",
        f"--user-data-dir={profil}",
        "--no-first-run",
        "--no-default-browser-check",
        # Ilk sekme hakkinda soru sormasin; kabin bir arac, urun degil.
        "--disable-features=Translate,OptimizationHints",
        # Pencere ACILMAZ; kabin yalnizca panelde yasar. `--headless=new`
        # eski bassiz kipten farkli: gercek Chrome motoru, ayni render.
        # KIMLIK (02.10.2026 OLCULDU): bassiz Chrome kendini
        # "HeadlessChrome" diye tanitiyordu ve Google aramayi "sorry"
        # sayfasiyla ENGELLEDI (patron: "youtube deyince calismiyor").
        # Ayni Chrome kendi gercek surumuyle tanitilinca arama acildi
        # (pencereli kip de acti). Tarayici gercek Chrome; ad ona uyar.
        *(() if gorunur else ("--headless=new",
                              f"--user-agent={chrome_kimligi(calistirilabilir)}")),
        f"--window-size={int(en)},{int(boy)}",
        str(baslangic),
    ]


def chrome_kimligi(calistirilabilir) -> str:
    """Gercek Chrome'un tarayici kimligi (bassiz kip icin). Ana surum
    kurulum klasorundeki surum adli klasorden okunur (`154.0.8037.58`);
    Chrome'un kendisi de yalniz ana surumu soyler (`154.0.0.0`).
    Bulunamazsa surumsuz kimlik -- uydurma bir numara YAZILMAZ."""
    import re as _re
    ana = ""
    try:
        for d in Path(str(calistirilabilir)).parent.iterdir():
            m = _re.fullmatch(r"(\d+)\.\d+\.\d+\.\d+", d.name)
            if d.is_dir() and m and int(m.group(1)) > int(ana or 0):
                ana = m.group(1)
    except OSError:
        pass
    surum = f"Chrome/{ana}.0.0.0" if ana else "Chrome"
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) {surum} Safari/537.36")


def cdp_adresi(kapi: int = KABIN_KAPISI) -> str:
    """Playwright MCP'ye verilecek `--cdp-endpoint`."""
    return f"http://127.0.0.1:{int(kapi)}"
