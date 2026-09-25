# -*- coding: utf-8 -*-
"""SARTNAME KAPISI -- kabul olcutunu KAPI MODELI denetler.

CLAUDE.md'de fable'in **1 numarali yeri** aylardir yaziliydi ve
**hic baglanmamisti**: *"Kabul olcutu / sartname -- MAST %41,8; Gemini
adaptoru tam bundan kullanilamaz cikti."*

O facianin ozeti: kabul olcutu *"pytest yesil ve sinif Motor'dan
turuyor"* idi. Ajan bunu **TAM** karsiladi. Kanit kapisi calisti, lider
dogru davrandi, olcut karsilandi -- ve teslim yine **kurulamaz** cikti,
cunku sozlesmenin sekiz parametresi yok sayilmisti.

> **Kapi, kendisine verilen olcutten daha iyi olamaz.**

Olcutu yazan kisi (lider, ya da onu isteyen insan) yaniliyorsa hicbir
kapi bunu yakalamaz. Bu dosya o bosluga bakiyor.

## IKINCI BIR YAZAR DEGIL, BIR KAPI

Onemli tasarim karari: kapi modeli olcutu **YAZMAZ**, denetler.

Yazsaydi ayni soruya iki yazar olurdu ve bu projede "iki kopya" hatasi
**bes kez** cikti. Ayrica lider planinin sahibi olmaktan cikardi --
oysa fan-out gerekcesi, yazma alani ve olcut tek bir tutarli plandir.

Bulgu varsa plan **mevcut "ret ogretir" yolundan** geri doner: bulgular
`hata` olarak lidere yazilir, lider duzeltip yeniden verir. Yeni bir
mekanizma eklenmiyor; var olan kapinin girdisi zenginlesiyor.

## PARA KORKULUKLARI (ucu de daha once odendi)

1. **TAVAN ZORUNLU.** Tavansiz kapi modeli kosmaz. Verilmemisse rolun
   alt sinirina duseriz.
2. **HAFTALIK PAY DOLDUYSA ATLANIR** -- ve atlama **gorunur** bir
   `uyari` olur. Sessizce atlanan kapi, olmayan bir guvencedir.
3. **TAVAN UYGULANAMIYORSA YAPILMAZ.** Para kontrolleri kapali kalarak
   basarisiz olur.

## UYDURMAZ

Model bulgu uretemezse (dustu, bos dondu, bicimi bozuk) kapi **"sorun
yok" DEMEZ**: gecmesine izin verir ama sebebi gorunur bir olaya yazar.
Calismayan bir denetimi "temiz" saymak, `saglik.py`de reddettigimiz
seyin ta kendisi.
"""

from __future__ import annotations

import json as _json

from . import butce, kullanim, roller
# `plan` ADIYLA ICE AKTARMIYORUZ: `denetle`nin parametresi de
# `plan` (plan sozlugu) ve modulu golgelerdi -- `plan.oku(...)`
# sessizce bir sozluk uzerinde cagrilir, kapi ATLANIRDI. Golgeleme
# hatanin en sessiz kurulma bicimlerinden biri.
from .plan import oku as plan_oku

#: Kapi turu KISA DEGIL. Tasarlarken "plan JSON'u kucuk" demistim ve
#: yanildim: kapiya gercek klasor + okuma araclari verilince kod
#: tabanini geziyor. Olculdu: 46.773 jeton, 7 arac cagrisi, 47 sn.
ZAMAN_ASIMI_SN = 240

#: OLCULMUS tur bedeli. Tahmin degil: ilk gercek kapi turu **$0,5571**
#: tuttu. $0,60 tavanla kosan ikinci tur bulgulari yazamadan oldu --
#: yani tavan, isin gercek boyuna gore DAR secilmisti.
#:
#: Bu rakam haftalik $5 payin %11'i. Kapi bu yuzden gorev basina
#: BIR KEZ kosar (bkz. orkestra: `sira == 0`); her denemede kosaydi
#: haftalik pay 4-5 hedefte biterdi.
OLCULEN_TUR_USD = 0.56
VARSAYILAN_TAVAN_USD = 0.85

#: Bulgu yoksa modelin yazmasi gereken tam sozcuk. Serbest metinden
#: "temiz mi" cikarmak, modelin o gunku uslubuna bagimli olur -- kanit
#: metin koprusunde tam bunu yasadik.
TEMIZ = "OLCUTLER YETERLI"


def istem(hedef: str, plan: dict, klasor_duzeni: str = "") -> str:
    """Kapi modeline verilen metin. TEMIZ baglam: transkript yok.

    `klasor_duzeni` ARACLARIN YERINE gecer. Kapi araçsiz kosuyor
    (olculdu: arac verilince geziyor ve bitiremiyor), ama bulgunun
    somut olmasi icin dosya adlarini GORMESI gerek -- tek gercek
    basarili turda bulgu `test_gemini.py`yi adiyla saymisti.
    Cozum: gezdirmek yerine ONUNE KOYMAK.
    """
    satir = [
        "Sen bir SARTNAME denetcisisin. Isi YAPMIYORSUN, planin KABUL",
        "OLCUTLERINI denetliyorsun.",
        "",
        "## NEDEN BURADASIN -- olculmus bir hata",
        "",
        "Bir teslimde kabul olcutu 'pytest yesil ve sinif Motor'dan",
        "turuyor' idi. Ajan bunu TAM karsiladi, testler yesildi, kanit",
        "kapisi gecti -- ve teslim yine KURULAMAZ cikti: sozlesmenin",
        "sekiz parametresi sessizce yok sayilmisti. Olcut, isin",
        "BITTIGINI degil, yalnizca bir kismini olcuyordu.",
        "",
        "Senin isin bu bosluga bakmak: **olcut karsilandigi halde is",
        "yine de basarisiz olabilir mi?**",
        "",
        "## HEDEF",
        "",
        hedef,
        "",
        "## PLANIN KOLLARI",
        "",
    ]
    if klasor_duzeni:
        satir = satir[:-2] + [
            "## CALISMA KLASORU (arac yok -- gordugun bu kadar)",
            "",
            "```", klasor_duzeni, "```", "",
            "## PLANIN KOLLARI", "",
        ]
    for i, kol in enumerate(plan.get("kollar") or []):
        satir += [
            f"### Kol {i}: {kol.get('baslik', '?')}",
            f"- neden: {kol.get('neden', '')}",
            f"- KABUL OLCUTU: {kol.get('kabul_olcutu', '')}",
            f"- yazma alani: {', '.join(kol.get('yazma_alani') or []) or '(yok)'}",
            "",
        ]
    satir += [
        "## HER KOL ICIN SOR",
        "",
        "1. Olcut OLCULEBILIR mi? 'iyi olsun' degil, 'su komut su ciktiyi",
        "   versin' / 'su dosyada su alan dolu olsun'.",
        "2. Olcut karsilandigi halde is BASARISIZ olabilir mi? Olabiliyorsa",
        "   eksik olan SARTI yaz.",
        "3. Olcut isin yalnizca bir PARCASINI mi olcuyor?",
        "4. Kanit NASIL uretilecek? Uretilemeyecek bir olcut, olcut degildir.",
        "",
        "## BICIM -- buna harfiyen uy",
        "",
        f"Butun olcutler yeterliyse TEK SATIR yaz: {TEMIZ}",
        "",
        "Yeterli DEGILSE, her sorun icin tek satir:",
        "KOL <no>: <eksik olan sart, SOMUT>",
        "",
        "Kural: plani YENIDEN YAZMA, kol EKLEME, isi YAPMA. Yalnizca",
        "olcutlerin eksigini soyle. Emin olmadigin bir sey icin bulgu",
        "UYDURMA -- bulgu yoksa yoktur.",
    ]
    return "\n".join(satir)


def denetle(ofis, hedef: str, plan: dict, *, lider_ad: str,
            motor_fabrikasi, tavan_usd: float = 0.0,
            klasor: str = "", son_sans: bool = False,
            klasor_duzeni: str = "") -> str:
    """Kabul olcutlerini kapi modeline denetletir.

    Doner: bos string = sorun yok / plan gecebilir. Dolu string =
    lidere yazilacak bulgular (mevcut "ret ogretir" yolundan doner).

    **Is DURDURMAZ.** Kapi kosulamiyorsa (butce doldu, tavan
    uygulanamiyor, motor yok) plan gecer ve sebep gorunur bir olaya
    yazilir. Sartname denetimi bir IYILESTIRMEDIR; onu zorunlu kilip
    isi durdurmak, kaynak tukendiginde isi oldurmek olurdu -- zincirde
    reddettigimiz sey.
    """
    def _uyar(sebep: str) -> str:
        ofis.db.olay_yaz(ofis.proje_id, "uyari",
                         f"Sartname denetimi ATLANDI: {sebep}",
                         ajan_ad=lider_ad)
        return ""

    hafta = butce.kapi_acik_mi(ofis.db, ofis.proje_id)
    if not hafta.get("acik"):
        return _uyar(f"haftalik kapi payi doldu ({hafta.get('sebep') or ''})")

    # `kapi_modeli` MOTORU ARGUMAN ALIR ve {"model": ...} doner --
    # motoru DONDURMEZ. Ilk yazisinda `kapi["motor"]` okumustum ve kapi
    # her seferinde `motor acilamadi: 'motor'` diyerek ATLANDI.
    # Yakalayan sey testler degil, atlamanin GORUNUR olmasiydi: o
    # `uyari` satiri olmasaydi kapinin kosup "temiz" dedigini
    # sanacaktim. *Sessizce atlanan kapi, olmayan bir guvencedir.*
    kapi_motoru = "claude"
    p = plan_oku(ofis.db, ofis.proje_id)
    try:
        kapi = roller.kapi_modeli(
            kapi_motoru, tavansiz_izinli=p.get("tavansiz_kapi_izinli", False))
    except Exception as exc:
        return _uyar(f"kapi modeli secilemedi: {exc}")
    if not kapi:
        return _uyar(f"{kapi_motoru} icin kapi modeli tanimli degil")

    # TAVAN ZORUNLU, ve kalan haftalik paydan fazlasi istenemez.
    #
    # OLCULDU (21.09.2026): $0,60 tavanla kosan ikinci kapi turu
    # **0 jeton / basarisiz** dondu -- 7 arac cagrisindan sonra tavana
    # dayanip bulgulari YAZAMADAN oldu. Yani turun butun bedeli odendi
    # ve karsiliginda hicbir sey alinmadi.
    #
    # Bu, "kanit sona birakiliyordu" dersinin aynisi: ciktisini SONDA
    # ureten bir is, tavan kesince her seyini kaybeder. Kapi tek bir
    # metin donduruyor, yani biriktirmesi MUMKUN DEGIL -- o yuzden
    # care tavani olculmus gerceklige cekmek.
    tavan = tavan_usd or VARSAYILAN_TAVAN_USD
    tavan = min(float(tavan), float(hafta.get("kalan") or tavan))
    if tavan <= 0:
        return _uyar("tavan hesaplanamadi (haftalik pay bitmis olabilir)")

    try:
        motor = motor_fabrikasi(kapi_motoru)
    except Exception as exc:
        return _uyar(f"motor acilamadi: {exc}")
    # ARACLAR KAPATILAMIYORSA KAPI KOSMAZ.
    #
    # Olculdu: araclarla kosan 4 turun 3'u ciktisini yazamadan
    # tavani bitirdi ($1,94 karsiliginda sifir bulgu). Yani araclari
    # kapatamayan bir motorla bu kapi bir IYILESTIRME degil, sadece
    # para yakan bir kumar olur. Kapali kalarak vazgeciyoruz.
    if not getattr(motor, "araclar_kapatilabilir", False):
        return _uyar(f"{kapi_motoru} butun araclari kapatamiyor; araclı kapi olculdu ve turlarin 3/4'u bulgusuz dustu")
    if not getattr(motor, "butce_destegi", False):
        # Para kontrolleri KAPALI KALARAK basarisiz olur.
        return _uyar(f"{kapi_motoru} tur basina tavan UYGULAYAMIYOR")

    parcalar = []
    basarili = False
    olcum = {}
    try:
        for olay in motor.tur_kos(
                # KLASOR ZORUNLU ve GERCEK olmali. Ilk yazisinda
                # `klasor or None` geciyordum; motor `None` ile
                # bos donuyordu ve kapi "bulgu uretmedi" diyerek
                # ATLANIYORDU -- yani kapi hic kosmadan "temiz"e
                # yakin davraniyordu. Gorunur uyari yine yakaladi.
                istem(hedef, plan, klasor_duzeni),
                klasor=klasor or str(getattr(ofis, "kok", "") or "."),
                model=kapi.get("model") or "fable",
                # Kapi turu da insanin efor tavanina uyar; `max` hic yok.
                efor=roller.tur_eforu(getattr(ofis, "db", None),
                                      getattr(ofis, "proje_id", ""), "normal"),
                yazabilir=False,          # denetci YAZMAZ
                araclar_kapali=True,      # ve GEZMEZ
                butce_usd=tavan,
                zaman_asimi=ZAMAN_ASIMI_SN):
            # OLAY TURU `metin`, ALAN `govde` -- ikisini de yanlis
            # yazmistim (`cikti` / `.metin`) ve kapi her seferinde BOS
            # dondu, yani "bulgu uretmedi" deyip atlandi. Sozlesmeyi
            # tahmin ettim; `motor/tip.py` OLAY_TURLERI'ne bakmadim.
            if olay.tur == "metin":
                parcalar.append(olay.govde or "")
            elif olay.tur == "bitti":
                olcum = dict(olay.ek or {})
                basarili = bool(olcum.get("basarili"))
    except Exception as exc:
        return _uyar(f"kapi turu dustu: {exc}")

    # HARCAMA GORUNUR OLMALI.
    #
    # Olculdu: bu kapi `koltuk`tan GECMIYOR, yani `tur_ozeti` olayi
    # yazilmiyordu ve `butce.haftalik_harcama` bu yolu HIC GORMUYORDU.
    # Yani "haftalik $5 kapi tavani" dedigimiz sey bu turlar icin
    # SESSIZCE ACIK kaliyordu -- "para kontrolleri kapali kalarak
    # basarisiz olur" kuralinin dogrudan ihlali.
    # *Sayan yer, kaydin tutuldugu yer olmali.*
    kullanim.tur_ozeti_yaz(ofis.db, ofis.proje_id, olcum, ajan_ad=lider_ad,
                           motor=kapi_motoru, yol="sartname")

    metin = "".join(parcalar).strip()
    if not basarili or not metin:
        # UYDURMAZ: calismayan bir denetim "temiz" degildir.
        return _uyar("kapi modeli bulgu uretmedi (tur basarisiz ya da bos)")

    ofis.db.olay_yaz(
        ofis.proje_id, "sartname",
        f"Kapi modeli olcutleri denetledi (tavan ${tavan:.2f})",
        ajan_ad=lider_ad)

    if TEMIZ in metin.upper():
        return ""
    bulgular = [s.strip() for s in metin.splitlines()
                if s.strip().upper().startswith("KOL")]
    if not bulgular:
        return _uyar("bulgu bicimi taninmadi -- 'temiz' SAYILMADI, atlandi")
    if son_sans:
        # KAPI OFISI KILITLEMEZ.
        #
        # Olculdu: iki denemede de bulgu cikti ve hedef TAMAMEN dustu.
        # Bu bir YARGI kapisi -- "olcut yeterli mi" sorusunun kesin bir
        # cevabi yok. Sonsuza kadar reddedebilen bir yargi kapisi, tek
        # bir modelin fikrinin ofisi kilitlemesi demektir.
        #
        # Zincirdeki ayni ayrim: kaynak (ya da mutabakat) tukenince is
        # OLMEZ. Bulgular kayda gecer, insan gorur, is yurur.
        ofis.db.olay_yaz(
            ofis.proje_id, "uyari",
            "Sartname bulgulari SON DENEMEDE de duruyor -- is yine de "
            "aciliyor. Bulgular: " + " | ".join(bulgular),
            ajan_ad=lider_ad)
        return ""
    return ("Sartname denetcisi kabul olcutlerini ZAYIF buldu. Bunlari "
            "duzelt ve plani yeniden ver:\n  " + "\n  ".join(bulgular))
