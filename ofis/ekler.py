# -*- coding: utf-8 -*-
"""EKLER -- sohbete dosya ve gorsel (29.09.2026).

Kullanici: *"dosya ya da gorsel yukleyemiyorum."* Rakipte gorev kartina
gorsel eklenebiliyor (surukle / Ctrl+V).

Nasil:
* Dosya PROJE KOKUNUN `ekler/` klasorune yazilir -- ajanlar kokte calisir,
  yani dosyayi okuyabilir (Claude `Read` ile gorsele bakar, Codex da).
* Mesaja `[ek] ekler/<ad>` satiri eklenir. Ek kaydi AYRI bir tabloda
  tutulmaz: mesajin kendisi tasir, akis satirdan cikarir (iki yerde
  tutulan her sey en az bir kez kayar).
* Ad TEMIZLENIR (yalniz harf/rakam/._-), zaman damgasiyla benzersiz;
  klasor disina yazilamaz, okunamaz (yol degil AD alinir).
* Boyut siniri `AZAMI_BAYT`. Yazma ATOMIK (`.part` -> ad).
* `ekler/` GitHub yedegine GIRMEZ (.gitignore): ekran goruntusu ve belge
  ozel bilgi tasiyabilir; ZIP yedeginde (bilgisayar + Drive) durur.
"""

from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

AZAMI_BAYT = 20 * 1024 * 1024
KLASOR = "ekler"
SATIR_ONEKI = "[ek] "
GORSEL = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
_SATIR = re.compile(r"^\[ek\] (ekler/[A-Za-z0-9._-]+)\s*$", re.M)


class EkHatasi(ValueError):
    pass


def ad_temizle(ad: str) -> str:
    ad = unicodedata.normalize("NFKD", str(ad or "").replace("ı", "i").replace("İ", "I"))
    ad = "".join(k for k in ad if not unicodedata.combining(k))
    ad = Path(ad.replace("\\", "/")).name          # yol parcasi atilir
    ad = re.sub(r"[^A-Za-z0-9._-]+", "-", ad).strip("-.")
    return (ad or "ek")[-80:]


def klasor(ofis) -> Path:
    return Path(ofis.kok_klasoru()).resolve() / KLASOR


def kaydet(ofis, ad: str, veri: bytes) -> dict:
    if not veri:
        raise EkHatasi("Bos dosya eklenemez.")
    if len(veri) > AZAMI_BAYT:
        raise EkHatasi(f"Dosya cok buyuk ({len(veri) // 1024 // 1024} MB); "
                       f"sinir {AZAMI_BAYT // 1024 // 1024} MB.")
    k = klasor(ofis)
    k.mkdir(parents=True, exist_ok=True)
    temiz = time.strftime("%Y%m%d-%H%M%S-") + ad_temizle(ad)
    hedef = k / temiz
    sayac = 1
    while hedef.exists():
        hedef = k / f"{hedef.stem}-{sayac}{hedef.suffix}"
        sayac += 1
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_bytes(veri)
    gecici.replace(hedef)
    ofis.db.olay_yaz(ofis.proje_id, "ek_eklendi",
                     f"{KLASOR}/{hedef.name} ({len(veri)} bayt)", ajan_ad="insan")
    return {"yol": f"{KLASOR}/{hedef.name}", "ad": hedef.name, "boyut": len(veri),
            "gorsel": hedef.suffix.lower() in GORSEL}


def dosya(ofis, ad: str) -> Path:
    """Ada gore ek dosyasi; klasor disi ve olmayan dosya REDDEDILIR."""
    temiz = Path(str(ad or "")).name
    if not temiz or temiz != ad or temiz.startswith("."):
        raise EkHatasi("Gecersiz ek adi.")
    k = klasor(ofis)
    yol = (k / temiz).resolve()
    if yol.parent != k or not yol.is_file():
        raise EkHatasi("Ek bulunamadi.")
    return yol


def satirlar(yollar) -> str:
    return "\n".join(SATIR_ONEKI + y for y in yollar)


def ayikla(metin: str) -> tuple:
    """Mesaj -> (ek satirlari cikarilmis metin, [ekler/ad, ...])."""
    yollar = _SATIR.findall(metin or "")
    temiz = _SATIR.sub("", metin or "").strip()
    return temiz, yollar


def ajan_notu(yollar) -> str:
    """Isi yapacak ajana: dosyalar nerede, nasil bakilir."""
    if not yollar:
        return ""
    return ("Patron dosya ekledi (proje kokune gore yol; OKU, gorselse bak):\n"
            + "\n".join("- " + y for y in yollar))
