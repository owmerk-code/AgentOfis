# -*- coding: utf-8 -*-
"""GERCEK SETIN OLCUM ARACI -- jeton yakmadan (30.09.2026).

Gercek set her gece gercek motorla kosar; ama olcum araci bozuksa gecenin
sonucu anlamsizdir. Burada:
  1. Her isin dogrulayicisi iyi sonuca GECTI, kotuye KALDI diyor mu (kuru).
  2. Kalite kaliplari: liderin "yapamam"i ve rapordaki ic konusma, 30.09'da
     GERCEKTEN goruldugu haliyle yakalaniyor; temiz cumleye dokunulmuyor.
  3. Gece kosusu zamanlama komutu dogru kuruluyor (gorev adi, saat).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- ILK ice aktarma: koku gecici klasore cevirir

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gercek_set as GS  # noqa: E402
import gece_kos as GK  # noqa: E402

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("\n-- 1. dogrulayicilar (kuru) --")
for no in GS.ISLER:
    iyi = GS.is_kos(no, "sahte", kuru="kuru_iyi")
    kotu = GS.is_kos(no, "sahte", kuru="kuru_kotu")
    sina(f"{no} iyiye GECTI, kotuye KALDI", iyi["durum"] == "gecti" and kotu["durum"] == "kaldi",
         f"iyi={iyi['durum']} kotu={kotu['durum']} {iyi.get('hata') or kotu.get('hata') or ''}")

print("\n-- 2. kalite kaliplari (30.09'da gorulen cumleler) --")
sina("'acamiyorum, sen at' yakalanir",
     bool(GS._YAPAMAM.search("Bu oturumda example.com'u açıp ekran görüntüsü alamıyorum. "
                             "Ekran görüntüsünü buraya ekleyebilir misin?")))
sina("'dogrulama yapamadim' (sen yap degil) SAYILMAZ",
     not GS._YAPAMAM.search("rapor.md dogru. Ayri bir komutla dogrulama yapamadim."))
sina("temiz cevap 'yapamam' SAYILMAZ",
     not GS._YAPAMAM.search("Ekran görüntüsü sohbette. Sayfa sorunsuz açıldı."))
sina("'Önce dosyaya bakıyorum' ic konusma yakalanir",
     bool(GS._IC_KONUSMA.search("Önce dosyanın gerçekten var olup olmadığına bakıyorum.\n\nPatron...")))
sina("'KANIT dosya:' satiri yakalanir",
     bool(GS._IC_KONUSMA.search("Istenen yapildi.\n\nKANIT dosya: a.png -> dogrulandi")))
sina("sade 'Kanıt:' cumlesi ic konusma SAYILMAZ",
     not GS._IC_KONUSMA.search("Yapildi.\nKanıt: ekran görüntüsü sohbette."))
sina("temiz rapor ic konusma SAYILMAZ",
     not GS._IC_KONUSMA.search("Toplam ciro 11.185 TL, en cok satan Cay. Rapor rapor.md'de."))

print("\n-- 3. gece zamanlamasi --")
sina("gorev adi ve saat tanimli", GK.GOREV_ADI and GK.SAAT == "03:30")
sina("iki motor SIRAYLA kosuyor (kod)", "for motor in (\"claude\", \"codex\")"
     in Path(GK.__file__).read_text(encoding="utf-8"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
