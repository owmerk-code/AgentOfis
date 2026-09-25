# -*- coding: utf-8 -*-
"""KAPI MODELI HAFTALIK BUTCESI -- pahali modelin ustunde bir tavan daha.

Tur basina tavanimiz vardi (`--max-budget-usd`), haftalik olani YOKTU.
Fark onemli: tur basina tavan tek bir turun kacmasini onler, haftalik
tavan **cok sayida makul turun toplamda limiti bitirmesini** onler.
Kullanicinin yasadigi sey ikincisiydi.

## Neden dolar sayiyoruz, "pay" degil

Anthropic mutlak sayi yayinlamiyor -- limitler "Pro'nun 5 kati" gibi
CARPAN olarak veriliyor ve gercek kapasite istem uzunluguna, modele,
dosya boyutuna gore degisiyor. Yani "haftalik payinin %50'si" ifadesini
bir sayiya cevirmenin dogru yolu yok.

Cevirmeye CALISMIYORUZ. Bunun yerine kendi harcamamizi sayiyoruz:
CLI'in her turda bildirdigi `maliyet_usd` (API karsiligi). Bu, gercek
faturanin kendisi degil -- abonelikle kosuyoruz -- ama **tuketimin
dogru vekili** ve bizim olcebildigimiz tek sey.

> Olcemedigimiz bir seyi tahmin edip ona gore kapi kurmak, kapiyi
> varsayima dayandirmak olurdu. Olcebildigimizi sayariz ve neyi
> saydigimizi SOYLERIZ.

## Varsayilan tavan nereden geliyor

Olculdu (20.09.2026, gercek ofis gecmisi): 30 turda **3** is ikinci kez
geri dondu -- yani kapi turlarin ~%10'unda atesler. Bir lider turu
25-95K jeton; fable'da kabaca $0,15-0,60. Bugunku hizla haftada
**~$1-2**.

Varsayilan **$5** bunun 3-5 kati: gercek bir durdurucu ama normal
kullanimda hic karsina cikmaz. Kullanici degistirebilir --
sabit kodlanmis bir tavan, farkli plani olan herkesi kodu degistirmeye
zorlardi (zincirde ayni karar verildi).

Max **5x** icin secildi; 20x'te rahatca yukseltilebilir.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import plan, roller

#: Kapi modellerine haftada en fazla bu kadar (API karsiligi $).
#: Gerekcesi modul docstring'inde; degistirilebilir olmasi bilincli.
#: Plan okunamazsa dusulecek deger. ASIL kaynak `ofis/plan.py` --
#: burasi yalnizca son care. Sifir yapsaydik plan okunamadiginda
#: yukseltme tamamen kapanirdi; yuksek yapsaydik tavan anlamsizlasirdi.
HAFTALIK_TAVAN_USD = 5.00

#: Pencere. Anthropic'in haftalik penceresiyle AYNI uzunluk secildi --
#: baska bir uzunluk secseydik sayacimiz onun penceresiyle kayardi ve
#: "bu hafta ne harcadim" sorusu iki farkli cevap verirdi.
PENCERE_GUN = 7


def _an(metin: str) -> datetime:
    try:
        t = datetime.fromisoformat(metin)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _kapi_model_mi(model_adi: str) -> bool:
    """Bu tur bir KAPI modelinde mi kosmus.

    Olaydaki ad tam model kimligidir (`claude-fable-5-1`), bizim kisa
    adimiz degil -- bu yuzden ALT DIZE bakilir. Tam esitlik arasaydik
    sayac sessizce SIFIR gosterirdi: harcama olur, sayac gormezdi.
    Bu projede "yanlis gosteren gosterge, gostergesizlikten kotudur".
    """
    ad = (model_adi or "").lower()
    return any(k in ad for k in roller.KAPI_MODELLERI)


def haftalik_harcama(db, proje_id: str, *, gun: int = PENCERE_GUN) -> dict:
    """Son `gun` gunde KAPI modellerine giden harcama.

    Donus: `{"usd", "tur", "pencere_gun", "modeller"}`.
    """
    sinir = datetime.now(timezone.utc) - timedelta(days=gun)
    toplam = 0.0
    adet = 0
    modeller = {}
    with db.baglanti() as conn:
        rows = conn.execute(
            "SELECT govde, olusturuldu FROM olay "
            "WHERE proje_id = ? AND tur = 'tur_ozeti'",
            (proje_id,)).fetchall()
    for r in rows:
        if _an(r["olusturuldu"]) < sinir:
            continue
        try:
            d = json.loads(r["govde"] or "{}")
        except (ValueError, TypeError):
            # Bozuk kayit SESSIZCE atlanir ama sayimi bozmaz: bir
            # satirin okunamamasi butun raporu susturmamali.
            continue
        ad = d.get("model") or ""
        if not _kapi_model_mi(ad):
            continue
        tutar = float(d.get("maliyet_usd") or 0.0)
        toplam += tutar
        adet += 1
        modeller[ad] = modeller.get(ad, 0.0) + tutar
    return {"usd": round(toplam, 4), "tur": adet, "pencere_gun": gun,
            "modeller": modeller}


def kapi_acik_mi(db, proje_id: str, *, tavan: float = None,
                 gun: int = PENCERE_GUN) -> dict:
    """Kapi modeline yukseltme SIMDI yapilabilir mi.

    Donus: `{"acik", "harcanan", "tavan", "kalan", "sebep"}`.

    Tavan asilmissa yukseltme YAPILMAZ -- ve bu, isin durmasi degildir:
    inceleme liderin kendi modeliyle yine kosar. Pahali olan basamak
    kapanir, is kapanmaz. (Nobet zincirinde de ayni ayrim var: kaynak
    tukenince is olmez, baska kaynaga gecer ya da normalde devam eder.)
    """
    # Tavan PLANDAN gelir, sabitten degil. Kullanici yarin Max 20x
    # alirsa tek yapmasi gereken `kabuk plan --claude max20` -- kod
    # degismez. ("Sabit kodlanmis zincir, farkli hesap duzeni olan
    # herkesi kodu degistirmeye zorlardi.")
    if tavan is None:
        try:
            tavan = plan.oku(db, proje_id)["kapi_haftalik_usd"]
        except Exception:
            # Plan okunamiyorsa KAPALI KALARAK degil, VARSAYILANLA
            # devam ederiz: plan bir ayardir, yoklugu isi durdurmamali.
            # Ama tavan yine de vardir -- tavansiz kosmak yok.
            tavan = HAFTALIK_TAVAN_USD
    tavan = float(tavan)
    h = haftalik_harcama(db, proje_id, gun=gun)
    kalan = round(tavan - h["usd"], 4)
    acik = kalan > 0
    return {
        "acik": acik,
        "harcanan": h["usd"],
        "tur": h["tur"],
        "tavan": tavan,
        "kalan": max(kalan, 0.0),
        "pencere_gun": gun,
        "sebep": "" if acik else (
            f"Son {gun} gunde kapi modellerine ${h['usd']:.2f} gitti, "
            f"tavan ${tavan:.2f}. Yukseltme kapali -- inceleme liderin "
            "kendi modeliyle kosuyor. Tavan PLANDAN geliyor -- "
            "`python -m ofis.kabuk plan` ile bak, "
            "`plan --claude max20` ile yukselt."),
    }
