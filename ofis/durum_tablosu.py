# -*- coding: utf-8 -*-
"""DURUM TABLOSU (08.10.2026, PLAN B2 + B4): her isin GERCEK durumu, her ajanin
ne yaptigi, sirada ne oldugu -- TEK ekranda, NEDENIYLE.

Patron (29.09): "her is gercek durumuyla" ekrani; "lider durum tablosu: kim
calisiyor, sirada ne var, neden". Kanban yalniz tahtadaki sutunu soyler
(`calisiyor`); is o an senin onayini mi, bir girisi mi, kredi onayini mi,
baska bir isi mi bekliyor -- orada yazmaz. Burada her isin "nerede" satiri
olculmus kayittan (onay, soru, bagimlilik, surec, son arac adimi) cikar.

UYDURMAZ: olculemeyen alan bos kalir. Yeni kural koymaz: teshisler var olan
kaynaklardan okunur (postane, tahta, surec, kuyruk, giris, tarayici).
"""

from __future__ import annotations

from datetime import datetime, timezone

ACIK_DURUMLAR = ("bekliyor", "hazir", "calisiyor", "inceleme")

#: "nerede" satirinin TURU -- panel renk ve sira icin kullanir. Sira: once
#: SENI bekleyenler, sonra durmus olanlar, sonra calisanlar, sonra sirada.
TUR_SIRASI = {"sen": 0, "durdu": 1, "calisiyor": 2, "inceleme": 3, "bekliyor": 4, "sirada": 5}


def _yas_sn(zaman: str):
    try:
        t = datetime.fromisoformat(str(zaman).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - t).total_seconds()))
    except (ValueError, TypeError):
        return None


def _onay_turu(o: dict) -> str:
    from . import giris
    from .tarayici import KREDI_PAKETI_ISARETI
    if giris.giris_mi(o):
        return "giris"
    metin = f"{o.get('eylem') or ''} {o.get('ayrinti') or ''}"
    if KREDI_PAKETI_ISARETI in metin or "KREDI" in metin.upper():
        return "kredi"
    return "onay"


def isler(ofis) -> list:
    """Acik her is: nerede, neyi bekliyor, son adim. En acil ustte."""
    from . import surec
    db, pid = ofis.db, ofis.proje_id
    onaylar = ofis.postane.bekleyen_onaylar()
    sorular = ofis.postane.bekleyen_sorular()
    with db.baglanti() as c:
        gorevler = [dict(r) for r in c.execute(
            "SELECT g.*, k.ad AS takim FROM gorev g LEFT JOIN kanat k ON k.id = g.kanat_id "
            "WHERE g.proje_id = ? AND g.silindi = 0 AND g.durum IN (?, ?, ?, ?) "
            "ORDER BY g.no", (pid, *ACIK_DURUMLAR))]
        son_adim = {}
        for r in c.execute(
                "SELECT gorev_id, tur, govde, olusturuldu FROM olay WHERE proje_id = ? "
                "AND gorev_id IS NOT NULL AND tur IN ('arac', 'kanit', 'not_iletildi', "
                "'incelemede', 'ret', 'birakildi', 'hata') ORDER BY rowid", (pid,)):
            son_adim[r["gorev_id"]] = dict(r)
        retler = {r[0]: r[1] for r in c.execute(
            "SELECT gorev_id, COUNT(*) FROM olay WHERE proje_id = ? AND tur = 'ret' "
            "GROUP BY gorev_id", (pid,))}
    kadro = {a["ad"]: a for a in ofis.kadro.liste()}
    out = []
    for g in gorevler:
        no = g["no"]
        bekleyen_onay = [o for o in onaylar if o.get("gorev_no") == no]
        bekleyen_soru = [s for s in sorular if s.get("gorev_no") == no]
        tur, nerede = "", ""
        if bekleyen_onay:
            o = bekleyen_onay[0]
            ot = _onay_turu(o)
            tur = "sen"
            nerede = {"giris": "giriş bekliyor — gömülü tarayıcıda senin girmen gerekiyor",
                      "kredi": "kredi onayını bekliyor — üretim senin onayınla başlar",
                      }.get(ot, f"onayını bekliyor: {str(o.get('eylem') or '')[:120]}")
        elif bekleyen_soru:
            s = bekleyen_soru[0]
            if s.get("alici") == "insan":
                tur, nerede = "sen", f"cevabını bekliyor: {str(s.get('govde') or '')[:120]}"
            else:
                tur, nerede = "bekliyor", f"sordu → {s.get('alici')}, cevabını bekliyor"
        elif g.get("duraklatildi"):
            tur, nerede = "durdu", "durduruldu — devam için Sürdür"
        elif g["durum"] == "calisiyor":
            canli = surec.yasiyor(g.get("kosan_surec") or "") if g.get("kosan_surec") else None
            if canli is False:
                tur, nerede = "durdu", "çalışan süreç kapanmış — kesintiden devam bekliyor"
            else:
                tur, nerede = "calisiyor", "çalışıyor"
        elif g["durum"] == "inceleme":
            try:
                lider = ofis.kadro.gorevin_lideri(g)["ad"]
            except Exception:                    # noqa: BLE001
                lider = "lider"
            tur, nerede = "inceleme", f"{lider} inceliyor / incelemesini bekliyor"
        else:
            blok = ofis.tahta.blokcular(no)
            if blok:
                tur = "bekliyor"
                nerede = "önce bitmesi gereken: " + ", ".join(f"#{b['no']} {b['baslik'][:40]}" for b in blok)
            else:
                sahip = g.get("sahip") or ""
                mesgul = [x for x in gorevler if x["sahip"] == sahip and x["durum"] == "calisiyor"
                          and x["no"] != no] if sahip else []
                tur = "sirada"
                nerede = (f"sırada — {sahip} şu an #{mesgul[0]['no']} üzerinde" if mesgul
                          else "sırada — ajan boşalınca başlar")
        adim = son_adim.get(g["id"]) or {}
        ajan = kadro.get(g.get("sahip") or "") or {}
        out.append({
            "no": no, "baslik": g["baslik"], "takim": g.get("takim") or "",
            "sahip": g.get("sahip") or "", "durum": g["durum"], "tur": tur, "nerede": nerede,
            "model": g.get("patron_modeli") or "/".join(x for x in (ajan.get("motor"), ajan.get("model")) if x),
            "ret": int(retler.get(g["id"]) or 0),
            "son_adim": (str(adim.get("govde") or "").splitlines() or [""])[0][:140] if adim else "",
            "son_adim_turu": adim.get("tur") or "",
            "son_adim_yas_sn": _yas_sn(adim.get("olusturuldu")) if adim else None,
            "yas_sn": _yas_sn(g.get("guncellendi")),
        })
    out.sort(key=lambda x: (TUR_SIRASI.get(x["tur"], 9), x["no"]))
    return out


def ajanlar(ofis, is_listesi: list = None) -> list:
    """Her ajan ne yapiyor: elindeki is, bekledigi sey, siradaki isi."""
    is_listesi = is_listesi if is_listesi is not None else isler(ofis)
    out = []
    for a in ofis.kadro.liste():
        elindeki = [x for x in is_listesi if x["sahip"] == a["ad"]]
        calisan = next((x for x in elindeki if x["durum"] == "calisiyor"), None)
        if calisan:
            ne = f"#{calisan['no']} {calisan['baslik'][:50]} — {calisan['nerede']}"
            hal = "sen" if calisan["tur"] == "sen" else ("durdu" if calisan["tur"] == "durdu" else "calisiyor")
        elif any(x["durum"] == "inceleme" for x in elindeki):
            x = next(x for x in elindeki if x["durum"] == "inceleme")
            ne, hal = f"#{x['no']} incelemede", "inceleme"
        else:
            ne, hal = "boşta", "bos"
        sira = [x for x in elindeki if x["tur"] in ("sirada", "bekliyor") and x is not calisan]
        out.append({"ad": a["ad"], "meslek": a.get("meslek") or "", "lider": bool(a.get("lider_mi")),
                    "takim": a.get("kanat_id") or "",
                    "model": "/".join(x for x in (a.get("motor"), a.get("model")) if x),
                    "hal": hal, "ne": ne,
                    "sirada": [f"#{x['no']} {x['baslik'][:40]}" for x in sira][:3]})
    out.sort(key=lambda x: ({"sen": 0, "durdu": 1, "calisiyor": 2, "inceleme": 3}.get(x["hal"], 4), x["ad"]))
    return out


def sira(ofis) -> list:
    """Lidere giden ama henuz baslamamis patron istekleri (is kuyrugu)."""
    from . import kuyruk
    try:
        return [{"metin": str(k.get("metin") or "")[:160], "lider": k.get("lider_ad") or "",
                 "durum": k.get("durum") or "", "yas_sn": _yas_sn(k.get("olusturuldu"))}
                for k in kuyruk.bekleyenler(ofis)]
    except Exception:                            # noqa: BLE001 -- olculemedi: bos
        return []


def tablo(ofis) -> dict:
    i = isler(ofis)
    return {"isler": i, "ajanlar": ajanlar(ofis, i), "sira": sira(ofis),
            "ozet": {t: sum(1 for x in i if x["tur"] == t) for t in TUR_SIRASI}}
