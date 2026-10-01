# -*- coding: utf-8 -*-
"""OFIS KOPYASI -- patronun GERCEK ofisinin kopyasinda, gercek islerle deneme.

    python testler/ofis_kopyasi.py            # varsayilan dort is
    python testler/ofis_kopyasi.py --is 1     # tek is

Neden (01.10.2026): gercek set bos gecici ofiste, ucuz modellerle kosar.
Patronun ofisi baskadir: Opus lider, guclu codex modeli, dolu hafiza
(olgular, kurallar, kalici izinler), dolu `calisma/` klasoru. "Senin
ofisinde hic sinanmadi" acigi bununla kapanir.

Dokunulmayanlar: gercek defter (`veri/ofis.sqlite3`) ve gercek `calisma/`.
Ikisi de gecici klasore KOPYALANIR; kopyada ajan klasorleri kopyaya cevrilir.
Yan etki (deneme.py ile ayni, bilincli): ajanlarin brifing kopyasi ve kota
olcumleri ofis evine (`~/.agentofis`) yazilir -- gercek olcumdur.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "testler"))
for _a in (sys.stdout, sys.stderr):
    try:
        _a.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os as _os                                  # noqa: E402
# Kopya ofis patronun ACIK kabinine (9222) girmesin.
_os.environ.setdefault("OFIS_KABIN_KAPI", "9399")
from ofis import Ofis, Veritabani, takim          # noqa: E402

PROJE = "Ofisim"
LIDER = "demir"

ISLER = [
    "semuparfum.com sitesinin ana sayfasini ac ve bana ekran goruntusunu gonder.",
    ("'2026'da yapay zeka ajan sistemleri' hakkinda kisa bir arastirma yap: en onemli 3 gelisme, "
     "her biri icin kaynak. rapor.md olarak hazirla ve bana gonder."),
    "Kahve Duragi adli kafe icin sade bir Instagram gonderi gorseli uret ve bana gonder.",
    "calisma klasorunde neler var? Kisa bir ozet ver: hangi klasorler, ne ise yariyorlar.",
]


def kopya_kur(yer: str = "") -> tuple:
    # `yer` (01.10.2026): kopya Claude'un HIC gormedigi bir klasorde kurulur ki
    # guven sorusu GERCEKTEN ciksin. Gecici klasor Claude'un zaten guvendigi
    # altta oldugu icin soru cikmiyordu (tasimadan sonra canli yakalanan hata).
    ana = Path(tempfile.mkdtemp(prefix="ofis-kopya-", dir=yer or None))
    db_yol = ana / "ofis.sqlite3"
    kaynak = sqlite3.connect(f"file:{KOK / 'veri' / 'ofis.sqlite3'}?mode=ro", uri=True)
    hedef = sqlite3.connect(db_yol)
    kaynak.backup(hedef)                     # tutarli kopya (acik panel yazsa bile)
    kaynak.close()
    # Projenin GERCEK koku defterden okunur (01.10.2026 ayrim: kok artik
    # masaustunde, `AgentOfis\\calisma` degil). Sabit yol tasimadan sonra
    # olmayan bir klasoru kopyalamaya calisirdi.
    _r = hedef.execute("SELECT kok_klasor FROM proje WHERE ad = ?", (PROJE,)).fetchone()
    kaynak_kok = Path((_r[0] if _r else "") or (KOK / "calisma"))
    calisma = ana / "calisma"
    shutil.copytree(kaynak_kok, calisma,
                    ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__"))
    gercek = str(kaynak_kok.resolve()).lower().replace("\\", "/")
    for r in hedef.execute("SELECT ad, klasor FROM ajan").fetchall():
        if (r[1] or "").lower().replace("\\", "/").rstrip("/") == gercek:
            hedef.execute("UPDATE ajan SET klasor=? WHERE ad=?", (str(calisma), r[0]))
    # Projenin KOKU ayri tutulur (`proje.kok_klasor`); ajan klasoru gibi
    # o da kopyaya cevrilir. Olculdu (01.10): ilk kosuda yalniz ajanlar
    # cevrilmisti, `main`deki denetim isi baslamadan durdurdu.
    for r in hedef.execute("SELECT id, kok_klasor FROM proje").fetchall():
        if (r[1] or "").lower().replace("\\", "/").rstrip("/") == gercek:
            hedef.execute("UPDATE proje SET kok_klasor=? WHERE id=?", (str(calisma), r[0]))
    # Kalan her gercek-kok izi SOYLENIR (sessiz kalan yol, gercek klasore yazar).
    for (tablo,) in hedef.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        sutunlar = [c[1] for c in hedef.execute(f"PRAGMA table_info({tablo})")]
        for sut in sutunlar:
            try:
                n = hedef.execute(f"SELECT COUNT(*) FROM {tablo} WHERE lower(replace(CAST({sut} AS TEXT),'\\','/')) "
                                  f"LIKE ?", (gercek + "%",)).fetchone()[0]
            except sqlite3.Error:
                continue
            if n and tablo not in ("olay", "kanit", "gorev", "karar", "mesaj"):
                print(f"UYARI: kopyada gercek koku gosteren {n} kayit: {tablo}.{sut}")
    # Kopyada yarim kalmis is/onay patronun gercek kuyrugunu taklit etmesin.
    hedef.execute("UPDATE gorev SET durum='iptal' WHERE durum IN ('bekliyor','hazir','calisiyor','inceleme')")
    hedef.commit()
    hedef.close()
    return ana, db_yol, calisma


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--is", dest="isler", type=int, action="append", default=[])
    ap.add_argument("--yer", default="", help="kopyanin kurulacagi ust klasor (guvenilmemis)")
    a = ap.parse_args()
    ana, db_yol, calisma = kopya_kur(a.yer)
    db = Veritabani(db_yol)
    ofis = Ofis.proje_ac(db, PROJE)
    assert Path(ofis.kok_klasoru()).resolve() == calisma.resolve(), ofis.kok_klasoru()
    print(f"kopya: {ana} (lider {LIDER}, kok {ofis.kok_klasoru()})")
    from ofis.sohbet import Sohbet
    from ofis.motor import tui
    sonuclar = []
    for i in (a.isler or range(1, len(ISLER) + 1)):
        mesaj = ISLER[i - 1]
        onceki = len(takim.akis(ofis, adet=300))
        t0 = time.time()
        hata = ""
        try:
            for _ in Sohbet(ofis).konus(mesaj, lider_ad=LIDER, zaman_asimi=600, azami_tik=8, paralel=2):
                pass
        except Exception as exc:              # noqa: BLE001
            hata = f"{exc.__class__.__name__}: {exc}"
        sure = time.time() - t0
        yeni = takim.akis(ofis, adet=300)[onceki:]
        print(f"\n=== {i}. {mesaj[:70]}  ({sure:.0f} sn){'  HATA ' + hata if hata else ''}")
        for x in yeni:
            print(f"  {x['kimden']}/{x['tur']} ekler={x.get('ekler') or ''} | "
                  f"{x['metin'][:500].replace(chr(10), ' / ')}")
        sonuclar.append({"no": i, "mesaj": mesaj, "sure_sn": round(sure), "hata": hata,
                         "sohbet": [f"{x['kimden']}/{x['tur']}: {x['metin']}" for x in yeni]})
        for x in tui.acik_oturumlar():
            tui.kapat(x["oturum_id"])
    rapor = KOK / "testler" / "rapor" / f"ofis-kopyasi-{_dt.datetime.now():%Y%m%d-%H%M%S}.json"
    rapor.parent.mkdir(exist_ok=True)
    rapor.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nrapor: {rapor}\nkopya klasoru (incelemek icin birakildi): {ana}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
