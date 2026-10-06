# -*- coding: utf-8 -*-
"""Metin siralama -- hafiza secimi ve belge aramasi icin TEK kural (06.10.2026).

OLCULDU (`testler/olcum_anlamsal.py`, 40 bilgi / 30 sorgu, 24'u patronun
konustugu gibi kelime PAYLASMAYAN "zor" sorgu):

    kelime/onek (eski)            13/30   (zor 8/24)
    harf dizisi (3-5 gram)        16/30   (zor 10/24) ama alakasizi ayiramiyor
    KELIME KAPISI + HARF SIRASI   15/30   (zor 9/24), alakasiz sorgu bos doner  <- bu
    yerel anlam modeli (model2vec) 19/30  (zor 13/24), 1 GB model + bagimlilik

Secilen: aday KELIME eslesmesiyle belirlenir (alakasiz metin girmesin),
adaylar harf dizisi benzerligiyle yeniden siralanir (Turkce ekleri ve yakin
yazimi tolere eder), kelime eslesmesi olmayan metin yalniz YUKSEK harf
benzerligiyle (>= `HARF_ESIGI`) sona eklenir. Yerel anlam modeli olculdu,
alinmadi: kazanc +4 isabet, bedel 1 GB ve yeni bagimlilik (karar kaydi:
GUNLUK 06.10).
"""

from __future__ import annotations

import math
import re
from collections import Counter

#: Kelime eslesmesi olmayan metnin listeye girmesi icin harf benzerligi.
#: Olculdu: alakasiz sorgularin en yuksegi 0,06 / 0,03 ("ortak kelime" tasiyan
#: 0,18-0,21'ler zaten kelime kapisindan gecer).
HARF_ESIGI = 0.15

_CEVRIM = str.maketrans("çğıİöşüÇĞÖŞÜâîû", "cgiiosucgosuaiu")
_DURAK = frozenset("""
ve veya ile icin gibi ama fakat ancak cunku yani hem her bir bu su o
olan olarak olsun olmali var yok daha cok az en de da mi mu ki ise
uzere gore kadar sonra once simdi yeni eski tum butun bazi kendi
nedir nasil hangi neler kac ne the and for
""".split())


def sade(metin: str) -> str:
    return (metin or "").translate(_CEVRIM).lower()


def kelimeler(metin: str) -> set:
    temiz = re.sub(r"[^0-9a-z]+", " ", sade(metin))
    return {k for k in temiz.split() if (len(k) >= 4 or k.isdigit()) and k not in _DURAK}


def _ortak(a: set, b: set) -> int:
    """Kac kelime ortak; ONEK eslesmesi sayilir ("iade" / "iadesi")."""
    n = 0
    for x in a:
        for y in b:
            if x == y or x.startswith(y[:4]) or y.startswith(x[:4]):
                n += 1
                break
    return n


def _ngram(metin: str) -> Counter:
    t = " " + " ".join(re.sub(r"[^0-9a-z]+", " ", sade(metin)).split()) + " "
    c = Counter()
    for n in (3, 4, 5):
        for i in range(len(t) - n + 1):
            g = t[i:i + n]
            if g.strip():
                c[g] += 1
    return c


def sirala(sorgu: str, metinler: list, *, harf_esigi: float = HARF_ESIGI) -> list:
    """`metinler` icinden sorguya ilgili olanlar, en ilgili once:
    `[(indeks, kelime_puani, harf_puani), ...]`. Ilgisiz metin donmez."""
    q = kelimeler(sorgu)
    if not q or not metinler:
        return []
    ng = [_ngram(m) for m in metinler]
    df = Counter(g for c in ng for g in c)
    n = len(metinler)

    def vek(c: Counter) -> dict:
        v = {g: (1 + math.log(f)) * math.log(1 + n / (1 + df.get(g, 0))) for g, f in c.items()}
        boy = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / boy for g, x in v.items()}

    qv = vek(_ngram(sorgu))
    sonuc = []
    for i, m in enumerate(metinler):
        mv = vek(ng[i])
        harf = sum(qv[g] * mv.get(g, 0.0) for g in qv)
        kel = _ortak(kelimeler(m), q)
        if kel > 0 or harf >= harf_esigi:
            sonuc.append((i, kel, round(harf, 4)))
    # Kelime eslesmesi olanlar once (cok eslesen once), esitlikte harf sirasi.
    sonuc.sort(key=lambda x: (-(x[1] > 0), -x[1], -x[2], x[0]))
    return sonuc
