# -*- coding: utf-8 -*-
"""PATRONUN KREDI SINIRI (11.10.2026, patron: "mesajinda sinir verirsen o is
icin sorulmasin").

07.10'dan beri Flow'da kredi harcayan her uretim ONCE patrona soruluyordu
(senaryo paketi + `onay_iste(kredi, uretim)`). Olculdu (08.10 Brave): ajan
paketi sorup turu bitiriyor, patron onayliyor, YENI tur basliyor -- videonun
2-3 dk'si ve patronun cevap suresi bu beklemeye gidiyordu.

Kural: patron isteginde ACIKCA bir kredi SINIRI yazdiysa ("150 krediye kadar",
"toplam kredi 150'yi gecmesin", "en fazla 150 kredi"), o istekten dogan islerin
kredi paketleri TOPLAMI bu sinira kadar SORULMADAN onaylanir; ajan ayni turda
uretime gecer. Sinir asilacaksa paket her zamanki gibi patrona gider.

Sinir OFISCE okunur (lider ya da ajan yorumlamaz): patronun isteginin
kelimesi kelimesine metni (`patron_sozu` olayi). Belirsiz cumle izin DEGILDIR:
- sayi + "kredi" + sinir sozcugu ayni cumlede olmali ("1000 kredim var" izin
  degil);
- ayni cumlede "sor", "onay", "danis" varsa izin degil ("150 kredi harcamadan
  once bana sor");
- birden cok sinir yazildiysa EN KUCUGU.
Onay kaydi patronun alintisini tasir: incelemede ve kartlarda "senin sozunle
onaylandi" diye gorunur. Para kilidine dokunmaz (Flow abonelik kredisidir).
"""

from __future__ import annotations

import re
import unicodedata

#: Onay kaydinin cevap notundaki isaret (kullanilan krediyi saymak icin).
ISARET = "KREDI_IZNI(patronun sozu)"

_HARF = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
                       "â": "a", "î": "i", "û": "u"})
_AYRAC = re.compile(r"[;!?\n]|[.,:](?=\s)|\bama\b|\bfakat\b|\bancak\b")
_SINIR = re.compile(r"\b(?:kadar|en fazla|en cok|gecme\w*|gecmey\w*|asma\w*|asmay\w*|"
                    r"sinir\w*|limit\w*|maks\w*|max\w*|butce\w*|ust sinir\w*)\b|≤|<=")
# "Onayli / onayladim" IZINDIR; yalniz onay ISTEYEN bicimler soru sayilir.
# Soru CUMLE icinde aranir ("150 krediye kadar ama once onayimi al" izin degil).
_SORU = re.compile(r"\b(?:sor\w*|danis\w*|onay(?:a|i|in|ini|imi|imiz|imizi|iniz|inizi|al\w*|"
                   r"iste\w*|lat\w*))\b")
_CUMLE = re.compile(r"[;!?\n]|\.(?=\s)")
_KREDI = re.compile(r"\bkredi\w*")
_SAYI = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{3})+|\d+)(?![\w.]*\d)")


def _sade(metin: str) -> str:
    m = (metin or "").replace("İ", "i").replace("I", "ı").lower().translate(_HARF)
    return "".join(c for c in unicodedata.normalize("NFKD", m) if not unicodedata.combining(c))


def sinir(metin: str):
    """Patronun metnindeki kredi SINIRI: (sayi, alinti) ya da (None, '')."""
    bulunan = []
    parcalar = []
    for cumle in _CUMLE.split(metin or ""):
        if not _SORU.search(_sade(cumle)):
            parcalar += _AYRAC.split(cumle)
    for parca in parcalar:
        s = _sade(parca)
        if not _KREDI.search(s) or not _SINIR.search(s):
            continue
        k = _KREDI.search(s).start()
        sayilar = [(abs(m.start() - k), int(m.group(1).replace(".", ""))) for m in _SAYI.finditer(s)]
        if not sayilar:
            continue
        deger = min(sayilar)[1]
        if deger > 0:
            bulunan.append((deger, " ".join(parca.split())))
    if not bulunan:
        return None, ""
    return min(bulunan)


def _patron_metinleri(db, proje_id: str, gorev_ids) -> list:
    if not gorev_ids:
        return []
    with db.baglanti() as c:
        return [r[0] for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'patron_sozu' AND gorev_id IN (%s) "
            "ORDER BY rowid" % ",".join("?" * len(gorev_ids)), [proje_id, *gorev_ids])]


def _kardes_isler(db, proje_id: str, gorev: dict) -> list:
    """Ayni istekten dogan isler (sinir ISTEGIN toplamidir: lider iki urunu iki
    ise bolse de patronun "150 krediye kadar"i iki kez 150 olmaz)."""
    if not gorev.get("istek_id"):
        return [gorev["id"]]
    with db.baglanti() as c:
        return [r[0] for r in c.execute("SELECT id FROM gorev WHERE proje_id = ? AND istek_id = ?",
                                        (proje_id, gorev["istek_id"]))] or [gorev["id"]]


def durum(db, proje_id: str, gorev: dict) -> dict:
    """{'sinir', 'alinti', 'kullanilan', 'kalan'} ya da sinir yoksa {'sinir': None}."""
    isler = _kardes_isler(db, proje_id, gorev)
    en = (None, "")
    for metin in _patron_metinleri(db, proje_id, isler):
        d = sinir(metin)
        if d[0] is not None and (en[0] is None or d[0] < en[0]):
            en = d
    if en[0] is None:
        return {"sinir": None, "alinti": "", "kullanilan": 0, "kalan": 0}
    with db.baglanti() as c:
        notlar = [r[0] for r in c.execute(
            "SELECT ayrinti FROM onay WHERE proje_id = ? AND durum = 'onaylandi' AND cevap_notu LIKE ? "
            "AND gorev_id IN (%s)" % ",".join("?" * len(isler)), [proje_id, ISARET + "%", *isler])]
    kullanilan = 0
    for a in notlar:
        m = re.search(r"kredi=(\d+)", (a or "").splitlines()[0] if a else "")
        kullanilan += int(m.group(1)) if m else 0
    return {"sinir": en[0], "alinti": en[1], "kullanilan": kullanilan,
            "kalan": max(0, en[0] - kullanilan)}


def karar(db, proje_id: str, gorev: dict, kredi: int) -> dict:
    """Bu paket patronun sozuyle SORULMADAN onaylanabilir mi."""
    d = durum(db, proje_id, gorev)
    if d["sinir"] is None:
        return {"gecer": False, "sebep": "patron bu istekte kredi siniri yazmadi", **d}
    if kredi > d["kalan"]:
        return {"gecer": False, "sebep": (f"paket {kredi} kredi, patronun sinirindan kalan {d['kalan']} "
                                          f"(sinir {d['sinir']}, kullanilan {d['kullanilan']})"), **d}
    return {"gecer": True, "sebep": "", **d}


def not_metni(d: dict, kredi: int) -> str:
    return (f"{ISARET}: \"{d['alinti'][:200]}\" -- sinir {d['sinir']}, bu paketle "
            f"{d['kullanilan'] + kredi} kullanildi.")


def brifing_satiri(db, proje_id: str, gorev: dict) -> str:
    d = durum(db, proje_id, gorev)
    if d["sinir"] is None:
        return ""
    return (f"KREDI IZNI (patronun sozu: \"{d['alinti'][:160]}\"): bu istekte {d['sinir']} krediye "
            f"kadar (kalan {d['kalan']}) kredi paketi SORULMADAN onaylanir. Paketi yine "
            "`sohbete_yaz` ile goster ve `onay_iste(kredi, uretim)` ile yaz; cevap ONAYLANDI ise "
            "TURU BITIRME, hemen uret. Siniri asan paket patrona sorulur.")
