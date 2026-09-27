# -*- coding: utf-8 -*-
"""KAPI MODELI (FABLE) KORUMASI -- saglayicinin kendi yuzdesiyle.

## Neden var

Kullanici (18.09.2026): *"fable tek promptta 5 saatlik limiti
bitiriyordu."* Fable ofiste yalniz KAPI olarak kosar (ikinci ret sonrasi
hakem, sartname denetimi) ve bu modul onun haftalik payini korur:
pay dolmak uzereyse yukseltme kapanir, IS DURMAZ -- inceleme liderin
kendi modeliyle kosar.

## 27.09.2026 KARARI -- dolar degil, hesabin kendi yuzdesi

Kullanici: *"api ile model kullanmiyorum, aboneliklerin limitini
kullanicaz; tavan felan karmasik geliyor -- kalici bir cozum bulalim."*

Bu modul once kapi turlarinin API-karsiligi DOLARINI sayiyordu ve
haftalik $5'ta kapaniyordu. Gerekcesi "Anthropic pay yuzdesi
yayinlamiyor" idi -- 23.09'da YANLIS cikti: CLI her turda pencereleri
bildiriyor. 27.09'da bir adim daha olculdu: FABLE turunda ayri bir
pencere geliyor (`seven_day_overage_included` -> `7g_kapi`, haiku
turunda YOK) -- claude.ai'deki "Haftalik -- Fable" cubugunun karsiligi.

Yani korunmasi gereken sey dogrudan olculuyor. Dolar vekiline gerek
kalmadi ve abonelikte dolar gostermek kullaniciyi yaniltiyordu.

Kurallar:

* **Esik %80** (ayar: `kapi_esigi`). Doldugunda yukseltme kapanir.
* **Olcum yoksa ya da pencere yenilendiyse ACIK.** Bilmedigimiz bir
  sayiya gore kapatmak, olmayan bir sebeple pahali ama gerekli bir
  incelemeyi engellemek olurdu. Olcum ilk fable turuyla gelir. O ilk
  turu yine TUR SINIRI tutar (asagida).
* **Tur siniri ICERIDE kalir** (`KAPI_TUR_SINIRI`, CLI'in
  `--max-budget-usd`u): tek bir fable turunun kacmasini onler. Insana
  gosterilmez, ayar da degildir -- abonelikte "dolar" kavrami yoktur,
  bu yalniz bir kacak frenidir.
* **Planda fable yoksa (Claude Pro) KAPALI** -- orada fable kredi harcar.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import plan

#: Fable haftalik payinin bu kadari dolunca yukseltme kapanir.
KAPI_ESIGI = 0.80
ANAHTAR_ESIK = "kapi_esigi"

#: Tek bir kapi turunun kacak freni (CLI `--max-budget-usd`). Olculdu
#: (20.09): bir lider turu fable'da kabaca $0,15-0,60; soguk en kucuk
#: tur $0,08 (27.09). Insana gosterilmez.
KAPI_TUR_SINIRI = 0.60

#: Saglayicinin pencere adinin bizdeki karsiligi (`motor/claude.py`).
#: 27.09 oncesi kayitlar ham adla duruyor -- ikisi de ayni pencere.
PENCERE = "7g_kapi"
HAM_AD = "seven_day_overage_included"


def _zaman(metin: str):
    try:
        t = datetime.fromisoformat(metin)
    except (ValueError, TypeError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def kapi_esigi(db, proje_id: str) -> float:
    """Etkin esik. Bozuk ayar varsayilana duser (saglik bunu soyler)."""
    try:
        deger = float(db.ayar_oku(proje_id, ANAHTAR_ESIK, "") or KAPI_ESIGI)
    except (TypeError, ValueError):
        return KAPI_ESIGI
    return deger if 0 < deger <= 1 else KAPI_ESIGI


def kapi_payi(db, proje_id: str, *, simdi_=None) -> dict | None:
    """Fable haftalik payinin EN SON olculen hali -> `None` = bilinmiyor.

    `kullanim.son_pencereler` uzerine kurulu: tur sonu olcumu ile canli
    okumanin (`kullanim.tazele`) hangisi yeniyse o. Iki ayri okuyucu
    olsaydi biri canli sayiyi, oteki bayat sayiyi gosterirdi.
    Yenilenmis pencerenin yuzdesi dondurulmez.
    """
    from . import kullanim
    for k in kullanim.son_pencereler(db, proje_id, simdi_=simdi_):
        w = k["pencereler"].get(PENCERE)
        if not w:
            continue
        if w["kullanim"] is None:
            return None          # pencere yenilendi -- eski yuzde gecersiz
        return {"kullanim": w["kullanim"], "yenilenme": w["yenilenme"],
                "olculdu": w.get("olculdu")}
    return None


def kapi_acik_mi(db, proje_id: str, *, simdi_=None) -> dict:
    """Kapi modeline yukseltme SIMDI yapilabilir mi.

    Donus: `{"acik", "kullanim", "esik", "yenilenme", "olculdu",
    "tur_siniri", "sebep"}`. `kullanim` `None` ise olculmedi.
    """
    esik = kapi_esigi(db, proje_id)
    try:
        dahil = plan.oku(db, proje_id)["kapi_dahil"]
    except Exception:
        dahil = True        # plan bir ayardir; okunamamasi isi durdurmaz
    pay = kapi_payi(db, proje_id, simdi_=simdi_)
    cikti = {"esik": esik, "tur_siniri": KAPI_TUR_SINIRI,
             "kullanim": pay["kullanim"] if pay else None,
             "yenilenme": pay["yenilenme"].isoformat() if pay else None,
             "olculdu": pay["olculdu"].isoformat() if pay and pay["olculdu"] else None}
    if not dahil:
        return dict(cikti, acik=False, sebep=(
            "Claude planinda fable yok (Pro) -- orada kredi harcar. "
            "Yukseltme kapali; inceleme liderin kendi modeliyle kosuyor."))
    if pay and pay["kullanim"] >= esik:
        return dict(cikti, acik=False, sebep=(
            f"Fable haftalik payi %{round(pay['kullanim'] * 100)} dolu "
            f"(esik %{round(esik * 100)}). Yukseltme kapali -- inceleme "
            "liderin kendi modeliyle kosuyor; pay yenilenince kendiliginden "
            "acilir."))
    return dict(cikti, acik=True, sebep="")
