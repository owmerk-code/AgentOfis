# -*- coding: utf-8 -*-
"""DEGER OZETI (08.10.2026, PLAN B5): ofis bu hafta NE URETTI, NEYE MAL OLDU.

Patron: "haftalik is, geri donen is, hesap basina kota". Sayilar olculmus
kayittan: `kapandi` (biten is), `ret` (geri donus), `teslim_puani`, `tur_ozeti`
(jeton, sure, motor, hesap), insana giden soru/onay, hesap pencereleri
(saglayicinin kendi bildirimi). UYDURMAZ: olculemeyen alan None.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone

GUN_AD = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def _zaman(s):
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def ozet(db, proje_id: str, *, gun: int = 7, simdi_=None) -> dict:
    simdi = simdi_ or datetime.now(timezone.utc)
    bas = simdi - timedelta(days=gun)
    bas_s = bas.isoformat(timespec="seconds")
    with db.baglanti() as c:
        kapanan = [dict(r) for r in c.execute(
            "SELECT o.gorev_id, o.olusturuldu AS kapandi, g.olusturuldu AS acildi, g.sahip "
            "FROM olay o JOIN gorev g ON g.id = o.gorev_id WHERE o.proje_id = ? "
            "AND o.tur = 'kapandi' AND o.olusturuldu >= ?", (proje_id, bas_s))]
        ret_olan = {r[0] for r in c.execute(
            "SELECT DISTINCT gorev_id FROM olay WHERE proje_id = ? AND tur = 'ret'", (proje_id,))}
        geri_donen = c.execute(
            "SELECT COUNT(DISTINCT gorev_id) FROM olay WHERE proje_id = ? AND tur = 'ret' "
            "AND olusturuldu >= ?", (proje_id, bas_s)).fetchone()[0]
        iptal = c.execute(
            "SELECT COUNT(*) FROM gorev WHERE proje_id = ? AND durum = 'iptal' AND guncellendi >= ?",
            (proje_id, bas_s)).fetchone()[0]
        puanlar = {r[0]: r[1] for r in c.execute(
            "SELECT gorev_id, puan FROM teslim_puani WHERE proje_id = ?", (proje_id,))}
        turlar = [r[0] for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'tur_ozeti' AND olusturuldu >= ?",
            (proje_id, bas_s))]
        soru = c.execute(
            "SELECT COUNT(*) FROM mesaj WHERE proje_id = ? AND alici = 'insan' AND mod = 'bekleyen' "
            "AND olusturuldu >= ?", (proje_id, bas_s)).fetchone()[0]
        onay = c.execute(
            "SELECT COUNT(*) FROM onay WHERE proje_id = ? AND olusturuldu >= ?",
            (proje_id, bas_s)).fetchone()[0]
    biten = len(kapanan)
    ilk = sum(1 for k in kapanan if k["gorev_id"] not in ret_olan)
    sureler = []
    for k in kapanan:
        a, b = _zaman(k["acildi"]), _zaman(k["kapandi"])
        if a and b and b >= a:
            sureler.append((b - a).total_seconds() / 60)
    p = [puanlar[k["gorev_id"]] for k in kapanan if k["gorev_id"] in puanlar]
    gunluk = []
    for i in range(gun - 1, -1, -1):
        g = (simdi - timedelta(days=i)).date()
        gunluk.append({"gun": GUN_AD[g.weekday()], "tarih": g.isoformat(),
                       "biten": sum(1 for k in kapanan if (_zaman(k["kapandi"]) or simdi).date() == g)})
    harcama: dict = {}
    ajan_jeton: dict = {}
    for govde in turlar:
        try:
            v = json.loads(govde or "{}")
        except ValueError:
            continue
        anahtar = (v.get("motor") or "?", v.get("hesap") or "")
        h = harcama.setdefault(anahtar, {"motor": anahtar[0], "hesap": anahtar[1], "tur": 0,
                                         "jeton": 0, "sure_dk": 0.0})
        h["tur"] += 1
        h["jeton"] += int(v.get("jeton") or 0)
        h["sure_dk"] += float(v.get("sure_ms") or 0) / 60000
    pencereler = []
    try:
        from . import kullanim
        for pn in kullanim.son_pencereler(db, proje_id):
            pencereler.append({"motor": pn.get("motor"), "hesap": pn.get("hesap") or "",
                               "pencereler": {ad: (w or {}).get("kullanim")
                                              for ad, w in (pn.get("pencereler") or {}).items()}})
    except Exception:                            # noqa: BLE001 -- olculemedi: bos
        pass
    return {
        "gun": gun, "baslangic": bas_s,
        "biten": biten, "ilk_seferde": ilk,
        "ilk_seferde_oran": round(ilk / biten, 2) if biten else None,
        "geri_donen": geri_donen, "iptal": iptal,
        "sure_dk_orta": round(statistics.median(sureler), 1) if sureler else None,
        "puan_ort": round(sum(p) / len(p), 1) if p else None, "puanli": len(p),
        "insana": {"soru": soru, "onay": onay},
        "gunluk": gunluk,
        "harcama": sorted(({**h, "sure_dk": round(h["sure_dk"], 1)} for h in harcama.values()),
                          key=lambda h: -h["jeton"]),
        "pencereler": pencereler,
    }
