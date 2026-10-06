# -*- coding: utf-8 -*-
"""ANLAMSAL ARAMA OLCUMU (06.10.2026, Asama 2 / E69). Jeton yakmaz.

Soru: hafiza ve belge aramasina "anlamla arama" eklemek kazandirir mi?
Kural: kazandirdigi OLCULMEDEN eklenmez.

Mevcut `olcum_hafiza.py` gorev metninin olguyla AYNI kelimeleri kullandigi
sentetik bir sahne kurar -- anlamsal aramanin farkini GOREMEZ. Bu set
bilerek iki tur sorgu tasir:

* **kolay**: sorgu bilgiyle kelime paylasir ("iade suresi kac gun").
* **zor**: kelime paylasmaz ("musteri urunu kac gun icinde geri yollayabilir"
  -> `iade suresi`). Patron boyle konusur.

Olcut: dogru bilgi ilk 3 sonuc icinde mi (isabet@3) ve ortalama ters sira
(MRR). Yontemler: (A) bugunku kelime/onek aramasi, (B) harf dizisi
benzerligi (bagimlilik yok), (C) yerel anlam modeli (model2vec, kuruluysa).

    python testler/olcum_anlamsal.py
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ofis.bellek import _kelimeler, _ortak, _sadelestir  # noqa: E402

BILGILER = {
    "iade suresi": "30 gün içinde iade kabul edilir",
    "geri ödeme": "iade onaylanınca 5 iş günü içinde karta yatırılır",
    "kargo firması": "Yurtiçi Kargo ile gönderilir",
    "kargo ücreti": "300 TL üzeri ücretsiz, altı 49 TL",
    "kapıda ödeme": "mevcut, 49 TL ek ücret",
    "teslim süresi": "siparişler 2 iş gününde kargoya verilir",
    "marka tonu": "müşteriye siz diye hitap edilir, emoji kullanılmaz",
    "iletişim telefonu": "0501 611 36 67",
    "destek e-postası": "iletisim@semuparfum.com",
    "satıcı adresi": "Çobançeşme Mah. Halitpaşa Sk. No: 2 Bahçelievler İstanbul",
    "servis portu": "8742 (servis/ayar.toml)",
    "veritabanı sürümü": "PostgreSQL 16.4",
    "test komutu": "python -m pytest -q",
    "dağıtım": "main dalına push edilince Vercel otomatik yayınlar",
    "ön yüz çatısı": "React 19 ve Vite",
    "ödeme altyapısı": "iyzico, taksit 6 aya kadar",
    "en çok satan": "Belle 50 ml",
    "ürün fiyatı": "Belle 1.490 TL KDV dahil",
    "stok uyarısı": "stok 5'in altına inince patrona bildir",
    "rapor biçimi": "patron raporları Excel olarak ister",
    "çalışma saatleri": "hafta içi 09:00-18:00",
    "tatil": "pazar günleri sipariş hazırlanmaz",
    "hediye paketi": "ücretsiz, not kartı eklenebilir",
    "indirim kodu": "HOSGELDIN10 ilk siparişte yüzde 10",
    "sosyal medya": "Instagram hesabı @semuparfum",
    "reklam bütçesi": "aylık 15.000 TL, Meta reklamları",
    "hedef kitle": "25-40 yaş kadınlar, İstanbul ağırlıklı",
    "rakip": "Kozmetik Dünyası benzer ürünleri daha pahalı satıyor",
    "fatura": "e-arşiv fatura otomatik kesilir",
    "muhasebe": "aylık beyanname mali müşavir Ayşe Hanım'da",
    "sunucu": "Hetzner, 4 çekirdek 8 GB",
    "yedekleme": "veritabanı her gece 03:00'te yedeklenir",
    "hata takibi": "Sentry kullanılıyor",
    "dil": "site Türkçe ve İngilizce",
    "logo": "logo dosyası marka/logo.svg",
    "renk paleti": "lacivert #1B2A4A ve altın #C9A227",
    "yazı tipi": "başlıklar Playfair Display, metin Inter",
    "ambalaj": "kutu geri dönüştürülmüş karton",
    "tedarikçi": "esanslar Grasse'tan ithal",
    "garanti": "kusurlu üründe ücretsiz değişim",
}

#: (sorgu, dogru konu, zor mu)
SORGULAR = [
    ("iade süresi kaç gün", "iade suresi", False),
    ("müşteri ürünü kaç gün içinde geri yollayabilir", "iade suresi", True),
    ("para ne zaman hesaba geçer", "geri ödeme", True),
    ("geri ödeme ne kadar sürer", "geri ödeme", False),
    ("siparişleri hangi taşıyıcıyla yolluyoruz", "kargo firması", True),
    ("kargo bedava mı", "kargo ücreti", True),
    ("teslimatta nakit alıyor muyuz", "kapıda ödeme", True),
    ("sipariş ne zaman yola çıkar", "teslim süresi", True),
    ("müşterilere nasıl bir dille yazmalıyız", "marka tonu", True),
    ("bizi aramak isteyen hangi numarayı arar", "iletişim telefonu", True),
    ("mail adresimiz ne", "destek e-postası", True),
    ("depo nerede", "satıcı adresi", True),
    ("uygulama hangi porttan dinliyor", "servis portu", True),
    ("db versiyonu ne", "veritabanı sürümü", True),
    ("testleri nasıl çalıştırırım", "test komutu", False),
    ("canlıya nasıl çıkıyoruz", "dağıtım", True),
    ("frontend hangi kütüphaneyle yazıldı", "ön yüz çatısı", True),
    ("kredi kartı ödemesini kim alıyor", "ödeme altyapısı", True),
    ("en popüler parfüm hangisi", "en çok satan", True),
    ("Belle kaç lira", "ürün fiyatı", True),
    ("ürün azalınca ne yapalım", "stok uyarısı", True),
    ("rapor hangi formatta olsun", "rapor biçimi", False),
    ("mesai saatleri", "çalışma saatleri", True),
    ("pazar günü kargo çıkar mı", "tatil", False),
    ("hediye paketi ücretli mi", "hediye paketi", False),
    ("yeni müşteriye kupon var mı", "indirim kodu", True),
    ("Meta'ya ayda ne kadar harcıyoruz", "reklam bütçesi", True),
    ("müşterilerimiz kim", "hedef kitle", True),
    ("site hangi barındırmada", "sunucu", True),
    ("markanın renkleri", "renk paleti", True),
]


def a_kelime(sorgu: str) -> list:
    """Bugunku hafiza secimi (bellek.ilgili_olgular puani)."""
    q = _kelimeler(sorgu)
    puan = [(_ortak(_kelimeler(k + " " + v), q), k) for k, v in BILGILER.items()]
    puan.sort(key=lambda x: (-x[0], x[1]))
    return [k for p, k in puan if p > 0]


def _ngram(metin: str) -> Counter:
    t = " " + " ".join(re.sub(r"[^0-9a-z]+", " ", _sadelestir(metin)).split()) + " "
    c = Counter()
    for n in (3, 4, 5):
        for i in range(len(t) - n + 1):
            g = t[i:i + n]
            if g.strip():
                c[g] += 1
    return c


_BELGE_NG = {k: _ngram(k + " " + v) for k, v in BILGILER.items()}
_DF = Counter(g for c in _BELGE_NG.values() for g in c)
_N = len(BILGILER)


def _vektor(c: Counter) -> dict:
    v = {g: (1 + math.log(f)) * math.log(1 + _N / (1 + _DF.get(g, 0))) for g, f in c.items()}
    n = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {g: x / n for g, x in v.items()}


_BELGE_V = {k: _vektor(c) for k, c in _BELGE_NG.items()}


def b_harf(sorgu: str) -> list:
    q = _vektor(_ngram(sorgu))
    puan = [(sum(q[g] * v.get(g, 0) for g in q), k) for k, v in _BELGE_V.items()]
    puan.sort(key=lambda x: (-x[0], x[1]))
    return [k for p, k in puan if p > 0.02]


def c_model():
    try:
        from model2vec import StaticModel
    except ImportError:
        return None
    import numpy as np
    m = StaticModel.from_pretrained("minishlab/potion-multilingual-128M")
    anahtarlar = list(BILGILER)
    bv = m.encode([f"{k}: {v}" for k, v in BILGILER.items()])
    bv = bv / (np.linalg.norm(bv, axis=1, keepdims=True) + 1e-9)

    def ara(sorgu: str) -> list:
        q = m.encode([sorgu])[0]
        q = q / (np.linalg.norm(q) + 1e-9)
        s = bv @ q
        return [anahtarlar[i] for i in np.argsort(-s)]
    return ara


def olc(ad: str, islev) -> dict:
    sonuc = {"kolay": [0, 0, 0.0], "zor": [0, 0, 0.0]}
    for sorgu, dogru, zor in SORGULAR:
        liste = islev(sorgu)
        tur = "zor" if zor else "kolay"
        sonuc[tur][1] += 1
        if dogru in liste[:3]:
            sonuc[tur][0] += 1
        if dogru in liste:
            sonuc[tur][2] += 1 / (liste.index(dogru) + 1)
    toplam = sum(v[0] for v in sonuc.values()), sum(v[1] for v in sonuc.values())
    print(f"{ad:28} isabet@3: kolay {sonuc['kolay'][0]}/{sonuc['kolay'][1]} · "
          f"zor {sonuc['zor'][0]}/{sonuc['zor'][1]} · toplam {toplam[0]}/{toplam[1]} "
          f"(%{100 * toplam[0] // toplam[1]}) · MRR {sum(v[2] for v in sonuc.values()) / toplam[1]:.2f}")
    return sonuc


if __name__ == "__main__":
    print(f"{len(BILGILER)} bilgi, {len(SORGULAR)} sorgu "
          f"({sum(1 for s in SORGULAR if s[2])} zor)\n")
    olc("A kelime/onek (bugunku)", a_kelime)
    olc("B harf dizisi (3-5 gram)", b_harf)
    c = c_model()
    if c is None:
        print("C yerel anlam modeli: model2vec KURULU DEGIL (olculmedi)")
    else:
        olc("C model2vec (cok dilli)", c)
        # Karma: A'nin buldugu once, sonra C'nin sirasi.
        olc("A + C karma", lambda q: list(dict.fromkeys(a_kelime(q)[:2] + c(q))))
