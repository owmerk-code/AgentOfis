# -*- coding: utf-8 -*-
"""TASIMA -- ofisin evi ve patronun projeleri ayrilir (01.10.2026, ayrim asama 5).

Kullanici karari: ofisin altyapisi TEK yerde (`Masaustu\\AgentOfis`, ev
`AgentOfis\\ev`), patronun projeleri masaustunde KENDI klasorlerinde.
Olculen sebep: ajanlarin koku ofisin kod klasorunun icindeydi; Claude
ajani ofisin CLAUDE.md'sini (gelistirme anayasasi) her turda okuyordu.

Bu arac var olan kurulumu yeni duzene GUVENLE tasir:

* VARSAYILAN DENEME: `plan()` hicbir seye dokunmaz; neyin nereye gidecegini,
  engelleri ve boyutu listeler.
* `uygula()`:
  1. Engel varsa (panel acik, kosan is, hedef dolu) DURUR.
  2. Defter yedeklenir (CLAUDE.md kurali: degistirmeden once yedek).
  3. Ev KOPYALANIR (`~/.agentofis` -> `AgentOfis\\ev`): once gecici adla,
     dogrulaninca asil ada. Eski ev YERINDE kalir (geri donus).
  4. Proje dosyalari ESLENEREK kopyalanir: `ekler/` -> `.ofis/ekler/`,
     `karalama/` -> `.ofis/karalama/`; eski tasarimin ajan klasorlerindeki
     `BRIFING.md`ler projeye DEGIL evin arsivine. Her dosya boyut+ozetle
     dogrulanir.
  5. EN SON defter guncellenir (proje koku, ajan klasorleri) -- tek islemde.
  6. Eski kok SILINMEZ: evin arsivine tasinir (GitHub'a da girmez).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import sqlite3
import time
from pathlib import Path

from . import yollar as Y

ATLANAN = {"__pycache__", ".pytest_cache"}


class TasimaHatasi(RuntimeError):
    pass


def _ozet(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _boyut(kok: Path) -> int:
    t = 0
    for d, alt, adlar in os.walk(kok):
        for a in adlar:
            try:
                t += (Path(d) / a).stat().st_size
            except OSError:
                pass
    return t


def panel_acik_mi(kapi: int = 8900) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", kapi), timeout=0.5):
            return True
    except OSError:
        return False


def _esle(goreli: Path, ajan_adlari: set) -> tuple:
    """Eski kokteki bir dosya -> ('proje', yeni goreli) ya da ('arsiv', goreli)."""
    parcalar = goreli.parts
    if parcalar and parcalar[0] == "ekler":
        return "proje", Path(Y.EK_KLASORU, *parcalar[1:])
    if parcalar and parcalar[0] == "karalama":
        return "proje", Path(Y.KARALAMA, *parcalar[1:])
    if len(parcalar) == 2 and parcalar[1] == "BRIFING.md" and parcalar[0] in ajan_adlari:
        return "arsiv", goreli
    return "proje", goreli


def plan(db_yolu=None, *, masaustu: Path = None, ev_eski: Path = None, ev_yeni: Path = None,
         icinde_mi=None, kapi: int = 8900) -> dict:
    """DENEME: hicbir seye dokunmaz."""
    from .db import VARSAYILAN_YOL
    db_yolu = Path(db_yolu or VARSAYILAN_YOL)
    masaustu = Path(masaustu or Y.MASAUSTU)
    ev_eski = Path(ev_eski or Y.ESKI_EV)
    ev_yeni = Path(ev_yeni or Y.YENI_EV)
    icinde_mi = icinde_mi or Y.ofis_icinde_mi
    engeller = []
    c = sqlite3.connect(f"file:{db_yolu.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        projeler = [dict(r) for r in c.execute("SELECT id, ad, kok_klasor FROM proje")]
        ajanlar = [dict(r) for r in c.execute("SELECT ad, klasor, proje_id FROM ajan")]
        kosan = [dict(r) for r in c.execute(
            "SELECT p.ad, g.no FROM gorev g JOIN proje p ON p.id = g.proje_id "
            "WHERE g.durum IN ('calisiyor', 'inceleme')")]
    finally:
        c.close()
    if panel_acik_mi(kapi):
        engeller.append(f"Panel acik ({kapi}): once paneli kapat.")
    ev = {"kaynak": str(ev_eski), "hedef": str(ev_yeni),
          "gerekli": ev_eski.is_dir() and not ev_yeni.exists(),
          "boyut": _boyut(ev_eski) if ev_eski.is_dir() and not ev_yeni.exists() else 0}
    if ev_yeni.exists() and not ev_yeni.is_dir():
        engeller.append(f"{ev_yeni} bir dosya; ev olamaz.")
    tasinacak = []
    for p in projeler:
        kok = (p["kok_klasor"] or "").strip()
        if not kok or not icinde_mi(kok):
            continue
        kok = Path(kok)
        hedef = masaustu / Y.proje_klasor_adi(p["ad"])
        adlar = {a["ad"] for a in ajanlar if a["proje_id"] == p["id"]}
        dosyalar, arsiv = [], []
        if kok.is_dir():
            for d, alt, ds in os.walk(kok):
                alt[:] = [x for x in alt if x not in ATLANAN]
                for a in ds:
                    g = (Path(d) / a).relative_to(kok)
                    tur, yeni = _esle(g, adlar)
                    (dosyalar if tur == "proje" else arsiv).append((str(g), str(yeni)))
        if hedef.exists() and any(hedef.iterdir()):
            engeller.append(f"Hedef dolu: {hedef} (bos olmali).")
        if any(k["ad"] == p["ad"] for k in kosan):
            engeller.append(f"'{p['ad']}' projesinde kosan/incelemede is var: once bitsin.")
        tasinacak.append({
            "proje_id": p["id"], "ad": p["ad"], "eski": str(kok), "hedef": str(hedef),
            "dosyalar": dosyalar, "arsiv": arsiv,
            "ajanlar": [a["ad"] for a in ajanlar if a["proje_id"] == p["id"]
                        and a["klasor"] and _ayni_ya_da_alti(a["klasor"], kok)],
            "boyut": _boyut(kok) if kok.is_dir() else 0, "var": kok.is_dir()})
    return {"db": str(db_yolu), "ev": ev, "projeler": tasinacak, "engeller": engeller,
            "masaustu": str(masaustu)}


def _ayni_ya_da_alti(yol: str, kok: Path) -> bool:
    try:
        p = Path(yol).resolve()
        k = Path(kok).resolve()
    except (OSError, ValueError):
        return False
    return p == k or k in p.parents


def _kopyala_dogrula(kaynak: Path, hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kaynak, hedef)
    if hedef.stat().st_size != kaynak.stat().st_size or _ozet(hedef) != _ozet(kaynak):
        raise TasimaHatasi(f"Kopya dogrulanamadi: {kaynak}")


def uygula(pl: dict, *, simdi: str = None) -> dict:
    """Plani uygular. Engel varsa HIC baslamaz."""
    if pl["engeller"]:
        raise TasimaHatasi("Tasima baslamadi: " + " | ".join(pl["engeller"]))
    simdi = simdi or time.strftime("%Y%m%d-%H%M%S")
    db_yolu = Path(pl["db"])
    rapor = {"db_yedek": "", "ev": "", "projeler": [], "geri_donus": []}

    # 2) Defter yedegi (tutarli: sqlite backup).
    yedek = db_yolu.with_name(db_yolu.name + f".yedek-{simdi}")
    kaynak = sqlite3.connect(f"file:{db_yolu.as_posix()}?mode=ro", uri=True)
    hedef = sqlite3.connect(str(yedek))
    try:
        kaynak.backup(hedef)
    finally:
        kaynak.close()
        hedef.close()
    rapor["db_yedek"] = str(yedek)
    rapor["geri_donus"].append(f"Defteri geri al: {yedek} -> {db_yolu}")

    # 3) Ev: gecici adla kopyala, sonra asil ada.
    ev = pl["ev"]
    ev_yeni = Path(ev["hedef"])
    if ev["gerekli"]:
        gecici = ev_yeni.with_name(ev_yeni.name + ".tasiniyor")
        if gecici.exists():
            shutil.rmtree(gecici)
        shutil.copytree(ev["kaynak"], gecici, ignore=shutil.ignore_patterns("__pycache__"))
        sayi_k = sum(len(f) for _, _, f in os.walk(ev["kaynak"]))
        sayi_h = sum(len(f) for _, _, f in os.walk(gecici))
        if sayi_k != sayi_h:
            raise TasimaHatasi(f"Ev kopyasi eksik: {sayi_h}/{sayi_k} dosya; eski ev yerinde.")
        os.replace(gecici, ev_yeni)
        rapor["ev"] = f"{ev['kaynak']} -> {ev_yeni} ({sayi_h} dosya; eski ev YERINDE)"
        rapor["geri_donus"].append(f"Eski eve donmek icin {ev_yeni} klasorunu sil/yeniden adlandir.")
    arsiv_kok = ev_yeni / "arsiv"

    # 4) Projeler: gecici klasore eslenerek kopyala, dogrula, asil ada.
    for p in pl["projeler"]:
        if not p["var"]:
            rapor["projeler"].append(f"{p['ad']}: eski kok yok ({p['eski']}), yalniz defter guncellenir")
            continue
        eski, hedef_kok = Path(p["eski"]), Path(p["hedef"])
        gecici = hedef_kok.with_name(hedef_kok.name + ".tasiniyor")
        if gecici.exists():
            shutil.rmtree(gecici)
        for g, yeni in p["dosyalar"]:
            _kopyala_dogrula(eski / g, gecici / yeni)
        (gecici / Y.EK_KLASORU).mkdir(parents=True, exist_ok=True)
        (gecici / Y.KARALAMA).mkdir(parents=True, exist_ok=True)
        (gecici / Y.PROJE_GIZLI / ".gitignore").write_text("*\n", encoding="utf-8")
        for g, _ in p["arsiv"]:
            _kopyala_dogrula(eski / g, arsiv_kok / f"eski-brifing-{simdi}" / p["ad"] / g)
        if hedef_kok.exists():
            hedef_kok.rmdir()                     # plan bos oldugunu dogruladi
        os.replace(gecici, hedef_kok)
        rapor["projeler"].append(f"{p['ad']}: {len(p['dosyalar'])} dosya -> {hedef_kok}"
                                 + (f"; {len(p['arsiv'])} eski brifing evin arsivine" if p["arsiv"] else ""))

    # 5) Defter: tek islemde.
    c = sqlite3.connect(str(db_yolu))
    try:
        with c:
            for p in pl["projeler"]:
                c.execute("UPDATE proje SET kok_klasor = ? WHERE id = ?", (p["hedef"], p["proje_id"]))
                for a in c.execute("SELECT ad, klasor FROM ajan WHERE proje_id = ?",
                                   (p["proje_id"],)).fetchall():
                    if a[1] and _ayni_ya_da_alti(a[1], Path(p["eski"])):
                        alt = Path(a[1]).resolve().relative_to(Path(p["eski"]).resolve())
                        c.execute("UPDATE ajan SET klasor = ? WHERE ad = ? AND proje_id = ?",
                                  (str(Path(p["hedef"]) / alt), a[0], p["proje_id"]))
    finally:
        c.close()

    # 6) Eski kok evin arsivine (SILINMEZ; GitHub'a girmez).
    for p in pl["projeler"]:
        eski = Path(p["eski"])
        if eski.is_dir():
            hedef = arsiv_kok / f"eski-kok-{Y.proje_klasor_adi(p['ad'])}-{simdi}"
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(eski), str(hedef))
            rapor["geri_donus"].append(f"Eski proje klasoru: {hedef}")
    return rapor
