# -*- coding: utf-8 -*-
"""TESLIME PUAN (06.10.2026, Asama 2 / E78).

Lider isi "kabul olcutunu karsiliyor" diye kapatir; ama patronun ISINE
yaradi mi, onu yalniz patron bilir. Patron kapanan ise 1-5 puan verir:

* **Gerekce ders olur.** 3 ve alti puanin gerekcesi ZORUNLUDUR ve isi yapan
  ajanin ders siciline girer (her brifinginin 1. katmani): ajan ayni seyi
  bir daha yapmasin. Gerekcesiz dusuk puan ogretmez.
* **Puan karneye gider.** 2 ve alti puanli is karnede "temiz gecis"
  sayilmaz -- lider kapatmis olsa bile (motor secimi ve tahmin bunu gorur).
* **Yalniz patron puanlar**; ayni ise yeni puan eskisinin yerine gecer
  (gecmis olayda durur).
"""

from __future__ import annotations

from .db import simdi

#: Bu puan ve alti icin gerekce zorunlu ve ders olur.
DERS_ESIGI = 3
#: Bu puan ve alti karnede temiz gecis sayilmaz.
KOTU_ESIGI = 2


class PuanHatasi(ValueError):
    pass


def ver(ofis, no: int, puan: int, gerekce: str = "", *, kim: str = "insan") -> dict:
    if kim != "insan":
        raise PuanHatasi("Teslimi yalniz patron puanlar.")
    try:
        puan = int(puan)
    except (TypeError, ValueError):
        raise PuanHatasi("Puan 1 ile 5 arasinda bir sayi olmali.")
    if not 1 <= puan <= 5:
        raise PuanHatasi("Puan 1 ile 5 arasinda olmali.")
    gerekce = " ".join((gerekce or "").split())
    if puan <= DERS_ESIGI and not gerekce:
        raise PuanHatasi(f"{puan}/5 icin gerekce zorunlu: ajan neyi farkli yapacagini bilmeli.")
    g = ofis.tahta.gorev(no)
    if g["durum"] != "bitti":
        raise PuanHatasi(f"#{no} henuz kapanmadi ({g['durum']}); yalniz biten is puanlanir.")
    with ofis.db.baglanti() as c:
        c.execute("INSERT OR REPLACE INTO teslim_puani (gorev_id, proje_id, puan, gerekce, veren, "
                  "olusturuldu) VALUES (?,?,?,?,?,?)",
                  (g["id"], ofis.proje_id, puan, gerekce[:500], kim, simdi()))
    ders = None
    if puan <= DERS_ESIGI and g.get("sahip"):
        ders = ofis.kadro.ders_yaz(g["sahip"], f"Patron #{no} isini {puan}/5 puanladi: {gerekce[:300]}",
                                   gorev_id=g["id"])
    from . import karne
    try:
        motor, model, _s = karne.isin_motoru(ofis.db, ofis.proje_id, g)
        meslek = (ofis.kadro.ajan(g["sahip"]).get("meslek") or "") if g.get("sahip") else ""
        karne.puan_yaz(gorev_id=g["id"], puan=puan, meslek=meslek, zorluk=g.get("zorluk") or "",
                       motor=motor, model=model)
    except Exception as exc:                          # noqa: BLE001 -- karne gosterge; puan yazildi
        ofis.db.olay_yaz(ofis.proje_id, "uyari", f"Puan karneye yazilamadi: {exc}", gorev_id=g["id"])
    ofis.db.olay_yaz(ofis.proje_id, "puan", f"#{no}: {puan}/5" + (f" -- {gerekce[:200]}" if gerekce else ""),
                     ajan_ad=kim, gorev_id=g["id"])
    return {"no": no, "puan": puan, "gerekce": gerekce, "ders": bool(ders and ders.get("id"))}


def oku(db, proje_id: str, gorev_id: str) -> dict | None:
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT puan, gerekce, olusturuldu FROM teslim_puani WHERE gorev_id = ? "
                          "AND proje_id = ?", (gorev_id, proje_id)).fetchone()
    except Exception:                                 # noqa: BLE001 -- eski defter
        return None
    return dict(r) if r else None
