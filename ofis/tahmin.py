# -*- coding: utf-8 -*-
"""ON TAHMIN: is baslamadan "yaklasik ne kadar surer, ne kadar kota yer"
(06.10.2026, Asama 2 / E74).

Patron abonelik kullanir; bedel dolar degil KOTA dilidir (5 saatlik / 7
gunluk pencere yuzdesi). Tahmin UYDURULMAZ, olculur:

* **Sure ve jeton**: karnedeki (ev/karne.jsonl) ayni meslek + zorluk +
  motordaki son islerin ORTANCASI. Yeterli ornek yoksa once meslek, sonra
  motor duzeyine bakilir; hic yoksa "BILINMIYOR" -- yanlis gosteren
  gosterge, gostergesizlikten kotudur.
* **Kota yuzdesi**: saglayicinin KENDI bildirdigi pencere doluluklari
  (`tur_ozeti.limit_pencere`) arasindaki artis / aradaki turlarin jetonu =
  "jeton basina yuzde" orani; motor basina ortanca. Olcum yetmezse yuzde
  verilmez (Claude dokumu pencere yuzdesi tasimiyor -- canli okuma
  biriktikce acilir).

Is kapaninca tahmin GERCEKLESENLE yan yana yazilir (`tahmin_gercek` olayi):
tahminin kendisi de olculur.
"""

from __future__ import annotations

import json
import statistics

#: Bir kovadan tahmin vermek icin en az kac is.
AZ_ORNEK = 2
#: Oran icin en az kac olcum cifti.
AZ_CIFT = 5
#: Olcumler bu kattan fazla yayiliyorsa (q75/q25) oran guvenilmez.
YAYILIM_TAVANI = 3.0


def _kovalar(meslek: str, zorluk: str, motor: str):
    yield "meslek+zorluk+motor", lambda s: (s.get("meslek") == meslek and s.get("zorluk") == zorluk
                                           and s.get("motor") == motor)
    yield "meslek+motor", lambda s: s.get("meslek") == meslek and s.get("motor") == motor
    yield "motor", lambda s: s.get("motor") == motor


def oran(db, proje_id: str, motor: str, pencere: str = "5s") -> float | None:
    """Jeton basina pencere dolulugu (0..1 olcekte) -- ortanca; olcum yoksa None."""
    try:
        with db.baglanti() as c:
            rows = c.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'tur_ozeti' "
                "ORDER BY id DESC LIMIT 600", (proje_id,)).fetchall()
    except Exception:                               # noqa: BLE001
        return None
    turlar = []
    for r in reversed(rows):
        try:
            v = json.loads(r[0] or "{}")
        except ValueError:
            continue
        if v.get("motor") == motor:
            turlar.append(v)
    oranlar, onceki, ara_jeton = [], None, 0
    for v in turlar:
        ara_jeton += int(v.get("jeton") or 0)
        p = ((v.get("limit_pencere") or {}).get("pencereler") or {}).get(pencere) or {}
        k, yen = p.get("kullanim"), p.get("yenilenme")
        if k is None:
            continue
        if onceki and onceki[1] == yen and k > onceki[0] and ara_jeton > 0:
            oranlar.append((k - onceki[0]) / ara_jeton)
        onceki, ara_jeton = (k, yen), 0
    # TUTARLILIK KAPISI (06.10.2026 OLCULDU, gercek defter): hesap ofis
    # DISINDA da kullaniliyor (patronun kendi Claude Code'u); aradaki dis
    # kullanim artisi sisiriyor -- ayni motorda oranlar 10 kat yayildi ve 7
    # gunluk pencere 5 saatlikten "hizli" doluyor gorundu. Yayilim genisse
    # yuzde VERILMEZ: yanlis gosteren gosterge, gostergesizlikten kotudur.
    if len(oranlar) < AZ_CIFT:
        return None
    q = statistics.quantiles(oranlar, n=4)
    if q[0] <= 0 or q[2] / q[0] > YAYILIM_TAVANI:
        return None
    return statistics.median(oranlar)


def tahmin(db, proje_id: str, *, meslek: str, zorluk: str, motor: str) -> dict:
    """{sure_sn, jeton, yuzde_5s, ornek, kova} -- bilinmeyen alan None."""
    from . import karne
    kayit = karne.satirlar()
    for ad, uyar in _kovalar(meslek or "", zorluk or "", motor or ""):
        ornek = [s for s in kayit if uyar(s) and s.get("gecti")]
        if len(ornek) >= AZ_ORNEK:
            break
    else:
        return {"sure_sn": None, "jeton": None, "yuzde_5s": None, "ornek": 0, "kova": ""}
    sureler = [float(s["sure_sn"]) for s in ornek if s.get("sure_sn")]
    jetonlar = [int(s["jeton"]) for s in ornek if s.get("jeton")]
    sure = statistics.median(sureler) if len(sureler) >= AZ_ORNEK else None
    jeton = int(statistics.median(jetonlar)) if len(jetonlar) >= AZ_ORNEK else None
    o = oran(db, proje_id, motor)
    yuzde = round(jeton * o * 100, 1) if (jeton and o) else None
    return {"sure_sn": sure, "jeton": jeton, "yuzde_5s": yuzde, "ornek": len(ornek), "kova": ad}


def _sure_metni(sn) -> str:
    if sn is None:
        return "?"
    sn = float(sn)
    return f"{int(sn)} sn" if sn < 90 else f"{round(sn / 60)} dk"


def metin(t: dict, motor: str = "") -> str:
    """Patrona okunur tek satir; bilinmeyen BILINMIYOR der."""
    if not t or not t.get("ornek"):
        return "tahmin yok (karnede bu tur is henuz yok)"
    parca = [f"~{_sure_metni(t['sure_sn'])}"]
    if t.get("jeton"):
        parca.append(f"~{round(t['jeton'] / 1000)} bin jeton")
    parca.append(f"~%{t['yuzde_5s']} {motor} 5 saatlik kota" if t.get("yuzde_5s") is not None
                 else "kota yuzdesi: bilinmiyor (olcum az ya da tutarsiz)")
    return " · ".join(parca) + f" ({t['ornek']} isten)"


def kaydet(db, proje_id: str, gorev: dict, t: dict, motor: str) -> None:
    """Tahmin deftere: is kapaninca gerceklesenle karsilastirilir."""
    db.olay_yaz(proje_id, "tahmin", json.dumps(dict(t, motor=motor), ensure_ascii=False),
                gorev_id=gorev["id"])


def gerceklesen_yaz(db, proje_id: str, gorev: dict, *, sure_sn, jeton) -> None:
    """Kapanista: tahmin vardiysa gerceklesenle yan yana (tahminin olcumu)."""
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? AND tur = 'tahmin' "
                          "ORDER BY rowid DESC LIMIT 1", (proje_id, gorev["id"])).fetchone()
        if not r:
            return
        t = json.loads(r[0])
    except Exception:                               # noqa: BLE001
        return
    db.olay_yaz(proje_id, "tahmin_gercek", json.dumps({
        "tahmin_sure_sn": t.get("sure_sn"), "gercek_sure_sn": sure_sn,
        "tahmin_jeton": t.get("jeton"), "gercek_jeton": jeton}, ensure_ascii=False),
        gorev_id=gorev["id"])
