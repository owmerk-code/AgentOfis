# -*- coding: utf-8 -*-
"""ARAMA SIRALAMASI (06.10.2026, Asama 2 / E69). Jeton yakmaz.

`ofis.arama.sirala` hafiza secimi ve belge aramasinin TEK kuralidir. Olculen
kazanc (`olcum_anlamsal.py`): eski kelime aramasi 13/30, bu kural 15/30, ve
alakasiz sorgu bos doner. Bu sinama kazancin GERI GITMEDIGINI ve
alakasizin girmedigini bekler.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import olcum_anlamsal as O  # noqa: E402
from ofis.arama import sirala  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


anahtarlar = list(O.BILGILER)
metinler = [f"{k} {v}" for k, v in O.BILGILER.items()]


def yeni(q):
    return [anahtarlar[i] for i, _k, _h in sirala(q, metinler)]


print("== arama siralamasi ==\n")
isabet = sum(1 for s, d, _z in O.SORGULAR if d in yeni(s)[:3])
eski = sum(1 for s, d, _z in O.SORGULAR if d in O.a_kelime(s)[:3])
sina(f"isabet@3 eski kelime aramasindan iyi ({isabet} > {eski})", isabet > eski)
sina("isabet@3 en az 15/30 (olculen deger geri gitmedi)", isabet >= 15, str(isabet))
sina("kolay sorgularin hepsi ilk 3'te",
     all(d in yeni(s)[:3] for s, d, z in O.SORGULAR if not z))
for q in ("uzay roketi yakıt", "futbol maçı skoru", "yarın hava nasıl"):
    sina(f"alakasiz sorgu bos: {q}", yeni(q) == [], str(yeni(q)[:3]))
sina("bos sorgu bos", sirala("", metinler) == [] and sirala("ve ile", metinler) == [])
sina("Turkce ek farki: 'iadesi' -> iade suresi", yeni("iadesi ne zaman")[:1] == ["iade suresi"],
     str(yeni("iadesi ne zaman")[:3]))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
