# -*- coding: utf-8 -*-
"""TAKIM KITI: bitti tanimi + marka kiti (06.10.2026, Asama 4 / K15).

Patron her takim icin bir kez yazar, ofis HER ise kendiliginden tasir:

* **Bitti tanimi** -- takimin her isinde gecerli "bitti" sartlari (orn.
  "testler gecer", "README guncel", "mobilde de calisir"). Isin kendi kabul
  olcutune EKTIR: iscinin brifinginde (K2), liderin planinda ve incelemesinde
  (`kunye_ozeti`) yazar; lider karsilanmayan sart icin geri gonderir.
* **Marka kiti** -- logo yolu, renkler, ses tonu, YASAK KELIMELER. Metin
  ve gorsel isinde ajan bunlara uyar. Yasak kelime RICA ile kalmaz: lider
  incelemesinde ofis, isin diskte degisen metin dosyalarini ve kanitlari
  TARAR, bulunani "ofisin olcumu" basligiyla gosterir (`yasak_tara`).

Takim ayri (patron: "her takim ayri"): kit takima aittir; takimsiz is ve
kitsiz takim icin blok bos kalir (brifing sismez).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: Taranacak metin dosyalari (ikili/buyuk dosya taranmaz).
METIN_UZANTI = {".txt", ".md", ".html", ".htm", ".css", ".js", ".ts", ".tsx", ".jsx",
                ".json", ".csv", ".xml", ".svg", ".py", ".yml", ".yaml", ".vue", ".php"}
AZAMI_BOYUT = 512 * 1024
ALANLAR = ("logo", "renkler", "ses_tonu", "yasak")


def _tr_kucuk(metin: str) -> str:
    """Turkce buyuk/kucuk: 'I'->'ı', 'İ'->'i' (Python'un lower()'i 'I'yi 'i' yapar)."""
    return str(metin or "").replace("I", "ı").replace("İ", "i").lower()


def oku(db, kanat_id: str) -> dict:
    bos = {"bitti_tanimi": [], "logo": "", "renkler": "", "ses_tonu": "", "yasak": []}
    if not kanat_id:
        return bos
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT bitti_tanimi, marka_kiti FROM kanat WHERE id = ?",
                          (kanat_id,)).fetchone()
    except Exception:                       # noqa: BLE001 -- eski defter: sutun yok
        return bos
    if not r:
        return bos
    out = dict(bos)
    out["bitti_tanimi"] = [s.strip() for s in (r["bitti_tanimi"] or "").splitlines() if s.strip()]
    try:
        mk = json.loads(r["marka_kiti"] or "{}")
    except ValueError:
        mk = {}
    if isinstance(mk, dict):
        for k in ("logo", "renkler", "ses_tonu"):
            out[k] = str(mk.get(k) or "").strip()
        out["yasak"] = [str(y).strip() for y in (mk.get("yasak") or []) if str(y).strip()]
    return out


def yaz(db, proje_id: str, kanat_id: str, *, bitti_tanimi=None, marka=None) -> dict:
    """Yalniz verilen parca degisir (None = dokunma). Yasak kelime listesi
    virgul ya da satirla ayrilabilir."""
    simdiki = oku(db, kanat_id)
    with db.baglanti() as c:
        if not c.execute("SELECT 1 FROM kanat WHERE id = ? AND proje_id = ?",
                         (kanat_id, proje_id)).fetchone():
            raise ValueError("Takim yok.")
        if bitti_tanimi is not None:
            satirlar = ([s for s in bitti_tanimi] if isinstance(bitti_tanimi, list)
                        else str(bitti_tanimi).splitlines())
            temiz = "\n".join(s.strip()[:300] for s in satirlar if str(s).strip())[:3000]
            c.execute("UPDATE kanat SET bitti_tanimi = ? WHERE id = ?", (temiz, kanat_id))
        if marka is not None:
            if not isinstance(marka, dict):
                raise ValueError("Marka kiti bir sozluk olmali.")
            yeni = {k: simdiki[k] for k in ("logo", "renkler", "ses_tonu", "yasak")}
            for k in ("logo", "renkler", "ses_tonu"):
                if k in marka:
                    yeni[k] = str(marka[k] or "").strip()[:500]
            if "yasak" in marka:
                ham = marka["yasak"]
                parca = ham if isinstance(ham, list) else re.split(r"[,\n]", str(ham or ""))
                yeni["yasak"] = sorted({str(p).strip()[:60] for p in parca if str(p).strip()},
                                       key=_tr_kucuk)[:100]
            c.execute("UPDATE kanat SET marka_kiti = ? WHERE id = ?",
                      (json.dumps(yeni, ensure_ascii=False), kanat_id))
    db.olay_yaz(proje_id, "takim_kiti", f"{kanat_id}: kit guncellendi", ajan_ad="insan")
    return oku(db, kanat_id)


def blok(db, kanat_id: str) -> list:
    """Brifing ve liderin kunyesi icin satirlar (kit bossa bos liste)."""
    k = oku(db, kanat_id)
    out = []
    if k["bitti_tanimi"]:
        out += ["", "**TAKIMIN BITTI TANIMI** (her iste, isin kendi olcutune EK; "
                    "karsilanmayan sart = is bitmemis):"]
        out += [f"  - {s}" for s in k["bitti_tanimi"]]
    marka = [(e, k[a]) for a, e in (("ses_tonu", "ses tonu"), ("renkler", "renkler"),
                                    ("logo", "logo"))if k[a]]
    if marka or k["yasak"]:
        out += ["", "**MARKA KITI** (metin ve gorsel islerinde uy):"]
        out += [f"  - {e}: {v}" for e, v in marka]
        if k["yasak"]:
            out.append("  - YASAK KELIMELER (hicbir metinde, dosyada, gorsel yazisinda "
                       "kullanma; ofis teslimi tarar): " + ", ".join(k["yasak"]))
    return out


def _desen(kelime: str):
    return re.compile(r"(?<!\w)" + re.escape(_tr_kucuk(kelime)) + r"(?!\w)")


def yasak_tara(db, kanat_id: str, *, kok: str = "", yollar=(), kanitlar=()) -> list:
    """Yasak kelimeleri ARAR. Doner: [{kelime, yer, ornek}] (ilk 20).

    `yollar` kok-goreli dosyalar (isin diskte olculen degisiklikleri);
    `kanitlar` metinler. Kelime siniri ve Turkce buyuk/kucuk gozetilir
    ("Ucuz" = "ucuz"; "ucuzluk" ayri kelime sayilmaz).
    """
    yasak = oku(db, kanat_id)["yasak"]
    if not yasak:
        return []
    desenler = [(y, _desen(y)) for y in yasak]
    kaynaklar = []
    for y in yollar or ():
        p = Path(kok) / y if kok and not Path(y).is_absolute() else Path(y)
        try:
            if p.suffix.lower() in METIN_UZANTI and p.is_file() and p.stat().st_size <= AZAMI_BOYUT:
                kaynaklar.append((str(y), p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    for i, m in enumerate(kanitlar or ()):
        kaynaklar.append((f"kanit {i + 1}", str(m or "")))
    bulunan = []
    for yer, metin in kaynaklar:
        kucuk = _tr_kucuk(metin)
        for kelime, d in desenler:
            m = d.search(kucuk)
            if m:
                bas = max(0, m.start() - 40)
                bulunan.append({"kelime": kelime, "yer": yer,
                                "ornek": " ".join(metin[bas:m.end() + 40].split())})
                if len(bulunan) >= 20:
                    return bulunan
    return bulunan
