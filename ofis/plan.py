# -*- coding: utf-8 -*-
"""ABONELIK PLANI -- kod degil AYAR.

Kullanici (20.09.2026): *"hesaplar degisebilir, yarin bir gun gpt hesapta
pro olabilir veya claude 20x aliriz, o zaman butun modelleri kullanirim;
o yuzden ona gore yap."*

Haklı: plani koda gomduk ve yanlisti. `HAFTALIK_TAVAN_USD = 5.00`
satirinin yaninda "Max 5x icin secildi" yaziyordu -- yani her plan
degisikligi bir KOD degisikligi olacakti. Bu, zincirde bir kez
ogrendigimiz hatanin aynisi:

> *"Sabit kodlanmis zincir, farkli hesap duzeni olan herkesi kodu
> degistirmeye zorlardi."*

Plan artik `ayar` tablosunda yasiyor ve `kabuk plan` ile degisiyor.

## Planin BELIRLEDIGI iki sey

1. **Kapi modelinin koruma esigi plandan DEGIL, saglayicinin kendi
   yuzdesinden gelir** (27.09.2026, `butce.py`). Dolar karsiligi bir
   haftalik tavan (`kapi_haftalik_usd`) KALDIRILDI: abonelikte dolar
   yok ve fable payi artik dogrudan olculuyor.

2. **Kapi modeli VAR MI.** Claude Pro'da fable plana DAHIL DEGIL
   (dogrudan krediyle calisir), o yuzden Pro'da otomatik yukseltme
   varsayilan olarak KAPALI -- kullanicinin haberi olmadan kredi
   harcamak, para kontrolunu varsayima birakmaktir.

## Planin BELIRLEMEDIGI sey -- ve bu onemli

**`astra`nin durumu plana bagli DEGIL.** Sebep modelin pahaliligi ya da
payin darligi degil: `codex` tur basina tavan UYGULAYAMIYOR
(`butce_destegi=False`). GPT Pro 20x alsan bile kacan bir astra turunu
DURDURACAK bir seyimiz olmaz -- yalnizca daha fazla payimiz olur.

Bu yuzden astra'yi acan sey plan degil, ACIK BIR TERCIH:
`tavansiz_kapi_izinli`. Varsayilani `False` ve acan kisi neyi kabul
ettigini gorur. Para kontrolleri KAPALI KALARAK basarisiz olur; acmak
insanin bilincli karari olmali, planin yan etkisi degil.
"""

from __future__ import annotations

#: Ayar anahtarlari. Tek yerde durur -- iki yerde yazilan bir anahtar,
#: birinde duzeltilip otekinde unutulur (bu projede bes kez oldu).
ANAHTAR_CLAUDE = "plan.claude"
ANAHTAR_GPT = "plan.gpt"
ANAHTAR_TAVANSIZ = "plan.tavansiz_kapi_izinli"

#: Claude planlari. `kapi_dahil`: fable bu plana dahil mi. Pro'da
#: DEGIL -- orada kredi harcar, otomatik yukseltme kapali gelir.
#: Payin ne kadarinin kullanildigi plandan degil, saglayicinin kendi
#: bildiriminden okunur (`butce.kapi_payi`).
CLAUDE_PLANLARI = {
    "pro": {"ad": "Claude Pro", "kapi_dahil": False,
            "not": "fable plana dahil degil -- dogrudan kredi harcar. "
                   "Otomatik yukseltme KAPALI gelir."},
    "max5": {"ad": "Claude Max 5x", "kapi_dahil": True,
             "not": "fable haftalik payin %50'sine kadar dahil."},
    "max20": {"ad": "Claude Max 20x", "kapi_dahil": True,
              "not": "fable haftalik payin %50'sine kadar dahil, pay 4 kat."},
}

#: GPT planlari. Bunlar kapi tavanini BELIRLEMEZ (codex tavan
#: uygulamiyor); yalnizca isci modellerinin ne kadar rahat kosacagini
#: soyler ve insana gosterilir.
#:
#: OLCULDU: Plus'ta astra icin 5 saatte tahminen 5-45 mesaj ve astra
#: Sol/Terra/Luna ile AYNI havuzdan yer -- yani astra kullanmak isciyi
#: durdurmaktir. OpenAI'in kendi rehberi: "yeterliyse Sol kullanin."
GPT_PLANLARI = {
    "plus": {"ad": "ChatGPT Plus", "carpan": 1,
             "not": "Astra icin DAR pay (5 saatte ~5-45 mesaj) ve pay "
                    "isci modelleriyle ORTAK. Sol yeterliyse Sol."},
    "pro100": {"ad": "ChatGPT Pro $100", "carpan": 5,
               "not": "Plus'in 5 kati. Astra yine ortak havuzdan yer."},
    "pro200": {"ad": "ChatGPT Pro $200", "carpan": 20,
               "not": "Plus'in 20 kati. Astra yine ortak havuzdan yer "
                      "ve codex hala tavan uygulayamiyor."},
}

VARSAYILAN_CLAUDE = "max5"
VARSAYILAN_GPT = "plus"


class PlanHatasi(Exception):
    pass


def oku(db, proje_id: str) -> dict:
    """Ofisin su anki plani. Hic yazilmadiysa varsayilana duser."""
    c = db.ayar_oku(proje_id, ANAHTAR_CLAUDE, VARSAYILAN_CLAUDE)
    g = db.ayar_oku(proje_id, ANAHTAR_GPT, VARSAYILAN_GPT)
    # Tanimsiz bir deger saklanmissa (elle duzenleme, eski surum)
    # SESSIZCE varsayilana dusmeyiz -- yanlis plan, yanlis tavan demek.
    if c not in CLAUDE_PLANLARI:
        raise PlanHatasi(
            f"Kayitli Claude plani taninmiyor: {c!r}. "
            f"Secenekler: {', '.join(CLAUDE_PLANLARI)}")
    if g not in GPT_PLANLARI:
        raise PlanHatasi(
            f"Kayitli GPT plani taninmiyor: {g!r}. "
            f"Secenekler: {', '.join(GPT_PLANLARI)}")
    tavansiz = db.ayar_oku(proje_id, ANAHTAR_TAVANSIZ, "0") == "1"
    return {
        "claude": c, "gpt": g,
        "claude_ad": CLAUDE_PLANLARI[c]["ad"],
        "gpt_ad": GPT_PLANLARI[g]["ad"],
        "kapi_dahil": CLAUDE_PLANLARI[c]["kapi_dahil"],
        "tavansiz_kapi_izinli": tavansiz,
        "claude_not": CLAUDE_PLANLARI[c]["not"],
        "gpt_not": GPT_PLANLARI[g]["not"],
    }


def yaz(db, proje_id: str, *, claude: str = None, gpt: str = None,
        tavansiz_kapi: bool = None) -> dict:
    """Plani degistirir. Bilinmeyen plan REDDEDILIR.

    Sessizce kabul edilen yanlis bir plan adi, yanlis bir tavan demek --
    ve tavanin yanlis oldugunu ancak fatura soylerdi.
    """
    if claude is not None:
        if claude not in CLAUDE_PLANLARI:
            raise PlanHatasi(
                f"Bilinmeyen Claude plani: {claude!r}. "
                f"Secenekler: {', '.join(CLAUDE_PLANLARI)}")
        db.ayar_yaz(proje_id, ANAHTAR_CLAUDE, claude)
    if gpt is not None:
        if gpt not in GPT_PLANLARI:
            raise PlanHatasi(
                f"Bilinmeyen GPT plani: {gpt!r}. "
                f"Secenekler: {', '.join(GPT_PLANLARI)}")
        db.ayar_yaz(proje_id, ANAHTAR_GPT, gpt)
    if tavansiz_kapi is not None:
        db.ayar_yaz(proje_id, ANAHTAR_TAVANSIZ, "1" if tavansiz_kapi else "0")
    return oku(db, proje_id)


def ozet(p: dict) -> str:
    """Insana gosterilecek hali."""
    satir = [
        f"PLAN",
        f"  claude : {p['claude_ad']:<18} ({p['claude']})",
        f"           {p['claude_not']}",
        f"  gpt    : {p['gpt_ad']:<18} ({p['gpt']})",
        f"           {p['gpt_not']}",
        "",
        f"  kapi modeli (fable)        : "
        f"{'plana dahil' if p['kapi_dahil'] else 'plana DAHIL DEGIL'}",
    ]
    if not p["kapi_dahil"]:
        satir.append("      -> otomatik yukseltme KAPALI (plana dahil degil)")
    else:
        satir.append("      -> haftalik payi %80 dolunca yukseltme kapanir "
                     "(saglayicinin kendi yuzdesiyle; `kullanim` ekraninda)")
    satir += [
        f"  tavansiz kapi modeli       : "
        f"{'IZINLI' if p['tavansiz_kapi_izinli'] else 'YASAK (varsayilan)'}",
    ]
    if not p["tavansiz_kapi_izinli"]:
        satir.append(
            "      -> astra otomatik kosmaz: codex tur basina tavan "
            "UYGULAYAMIYOR.")
        satir.append(
            "      -> Plan yukseltmek bunu ACMAZ; ayri bir tercihtir.")
    else:
        satir.append(
            "      -> UYARI: kacan bir turu durduracak tavan YOK.")
    return "\n".join(satir)
