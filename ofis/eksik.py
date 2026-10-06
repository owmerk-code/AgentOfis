# -*- coding: utf-8 -*-
"""OFIS KENDI EKSIGINI ONERIR (06.10.2026, Asama 4 / K17, E84).

Ofis kendi defterinden TEKRAR EDEN sorunlari bulur ve patrona oneri olarak
sunar. Model YOK (bedava, uydurmaz): her oneri olculmus kayitlara dayanir
ve kanitini (kac kez, ornekler) tasir. Kaynaklar (son 7 gun):

* ayni sebeple tekrar DUSEN is (`hata`)  * TAKILAN isler (`takildi`)
* tekrar eden ofis UYARISI (`uyari`)    * ayni iste ret DONGUSU (`ret` >= 3)
* takimin CANLI engeline tekrar takilmasi (`canli_engel`)
* takimin KOTA PAYININ tekrar dolmasi (`kota_payi_dolu`)
* saglik denetiminin UYARI bulgulari (panelde ayrica gosterilmeyenler)

Patron karar verir: **Onayla** = "bu duzeltilsin" -> `ev/ofis_eksikleri.jsonl`
(gelistiricinin is listesi; `kabuk eksikler`). Ofis kendini KURMAZ
(kurulus karari): oneriyi kaydeder, duzeltmeyi insan inceler ve kurar.
**Gereksiz** = ayni oneri bir daha gelmez. Karar verilen oneri gizlenir.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

AYAR = "eksik_kararlari"
GUN = 7
#: Ayni sebebin kac tekrari "desen" sayilir.
ESIK = {"hata": 2, "takildi": 2, "uyari": 3, "ret": 3, "canli_engel": 2, "kota_payi_dolu": 2}


def _norm(metin: str) -> str:
    m = str(metin or "").lower()
    m = re.sub(r"#\d+", "#", m)
    m = re.sub(r"\[[^\]]*\]", "", m)                 # olay isaretleri
    m = re.sub(r"\([^)]*\)", "", m)                  # parantezdeki is adi (#3 sepet)
    m = re.sub(r"\d+", "0", m)
    m = re.sub(r"[a-f0-9]{8,}", "x", m)               # kimlikler
    return " ".join(m.split())[:120]


def _anahtar(tur: str, norm: str) -> str:
    return hashlib.sha1(f"{tur}|{norm}".encode("utf-8")).hexdigest()[:12]


def kararlar(db, proje_id: str) -> dict:
    try:
        v = json.loads(db.ayar_oku(proje_id, AYAR, "{}") or "{}")
    except ValueError:
        v = {}
    return v if isinstance(v, dict) else {}


def _oneri(tur, norm, baslik, ornekler, oneri, sayi):
    return {"anahtar": _anahtar(tur, norm), "tur": tur, "baslik": baslik, "sayi": sayi,
            "ornekler": [str(o)[:200] for o in ornekler[:3]], "oneri": oneri}


_SAGLIK_ONBELLEK: dict = {}
SAGLIK_OMRU = 300


def _saglik_bulgulari(ofis) -> list:
    import time
    k = (str(ofis.db.yol), ofis.proje_id)
    v = _SAGLIK_ONBELLEK.get(k)
    if v and time.time() - v[0] < SAGLIK_OMRU:
        return v[1]
    from .saglik import Saglik
    b = Saglik(ofis).denetle()["bulgular"]
    _SAGLIK_ONBELLEK[k] = (time.time(), b)
    return b


def topla(ofis, *, simdi_=None) -> list:
    """Olculmus tekrar eden sorunlar -> oneri listesi (karar verilenler HARIC)."""
    db, pid = ofis.db, ofis.proje_id
    esik = ((simdi_ or datetime.now(timezone.utc)) - timedelta(days=GUN)
            ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with db.baglanti() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT o.tur, o.govde, o.gorev_id, g.no AS gorev_no, g.kanat_id "
            "FROM olay o LEFT JOIN gorev g ON g.id = o.gorev_id WHERE o.proje_id = ? "
            "AND o.olusturuldu >= ? AND o.tur IN ('hata', 'takildi', 'uyari', 'ret', "
            "'canli_engel', 'kota_payi_dolu') ORDER BY o.rowid DESC",
            (pid, esik))]
        adlar = {r[0]: r[1] for r in c.execute("SELECT id, ad FROM kanat WHERE proje_id = ?", (pid,))}
    out = []
    # 1-3) ayni sebebin tekrari
    gruplar: dict = {}
    for r in rows:
        if r["tur"] in ("hata", "uyari", "takildi"):
            n = _norm(r["govde"]) if r["tur"] != "takildi" else "takildi"
            gruplar.setdefault((r["tur"], n), []).append(r["govde"])
    for (tur, n), ornek in gruplar.items():
        if len(ornek) < ESIK[tur]:
            continue
        if tur == "hata":
            out.append(_oneri(tur, n, f"Aynı sebeple {len(ornek)} kez düşüş", ornek,
                              "Bu düşüşün kök sebebi ofiste düzeltilmeli; her seferinde iş yeniden koşuyor.",
                              len(ornek)))
        elif tur == "uyari":
            out.append(_oneri(tur, n, f"Aynı uyarı {len(ornek)} kez", ornek,
                              "Tekrar eden uyarı bir ayar ya da kod eksiğine işaret ediyor.", len(ornek)))
        else:
            out.append(_oneri(tur, n, f"{len(ornek)} iş takıldı", ornek,
                              "İşler aynı yerde takılıyorsa (izin, kilit, motor) ofis tarafında çözüm gerekir.",
                              len(ornek)))
    # 4) ret dongusu (is basina)
    retler: dict = {}
    for r in rows:
        if r["tur"] == "ret" and r["gorev_no"]:
            retler.setdefault(r["gorev_no"], []).append(r["govde"])
    for no, ornek in retler.items():
        if len(ornek) >= ESIK["ret"]:
            out.append(_oneri("ret", f"#{no}", f"#{no} işi {len(ornek)} kez geri gönderildi", ornek,
                              "Ölçüt ile iş birbirini tutmuyor: kabul ölçütü ya da işçinin talimatı düzeltilmeli.",
                              len(ornek)))
    # 5-6) takim basina
    for tur, baslik, oneri in (
            ("canli_engel", "takımı canlıya çıkmaya {n} kez takıldı",
             "Bu takım canlıya çıkmak istiyor: gerekiyorsa Ayarlar > Canlı kip'i aç; gerekmiyorsa işler önizlemeyle bitsin."),
            ("kota_payi_dolu", "takımının kota payı {n} kez doldu",
             "Payı artırmayı ya da işleri dağıtmayı düşün (Ayarlar > Takım kota payı).")):
        tk: dict = {}
        for r in rows:
            if r["tur"] == tur:
                kid = r["kanat_id"] or ""
                if tur == "kota_payi_dolu":
                    m = re.search(r"\[([0-9a-f]{8,}):", r["govde"] or "")
                    kid = m.group(1) if m else kid
                tk.setdefault(kid, []).append(r["govde"])
        for kid, ornek in tk.items():
            if len(ornek) >= ESIK[tur]:
                ad = adlar.get(kid, "takımsız")
                out.append(_oneri(tur, kid, f"{ad} " + baslik.format(n=len(ornek)),
                                  [o.rsplit(" [", 1)[0] for o in ornek], oneri, len(ornek)))
    # 7) saglik uyarilari (panel yalniz tikali/insan gosteriyor). Denetim
    # motorlari yoklar; panel bunu sik sorar -> 5 dakikalik onbellek.
    try:
        for b in _saglik_bulgulari(ofis):
            if b["agirlik"] == "uyari":
                n = _norm(b["baslik"])
                out.append(_oneri("saglik", n, b["baslik"], [b.get("ayrinti") or ""],
                                  b.get("care") or "Sağlık denetiminin uyarısı.", 1))
    except Exception:                       # noqa: BLE001 -- denetim olmazsa oneri eksik kalir
        pass
    kar = kararlar(db, pid)
    goruldu, temiz = set(), []
    for o in out:
        if o["anahtar"] in kar or o["anahtar"] in goruldu:
            continue
        goruldu.add(o["anahtar"])
        temiz.append(o)
    temiz.sort(key=lambda o: -o["sayi"])
    return temiz


def karar_ver(ofis, anahtar: str, karar: str, *, notu: str = "") -> dict:
    """Patronun karari. `onayla` -> gelistirici listesine yazilir."""
    if karar not in ("onayla", "gereksiz"):
        raise ValueError("Karar 'onayla' ya da 'gereksiz' olmali.")
    db, pid = ofis.db, ofis.proje_id
    bul = next((o for o in topla(ofis) if o["anahtar"] == anahtar), None)
    if bul is None:
        raise ValueError("Bu oneri artik yok ya da karari verilmis.")
    kar = kararlar(db, pid)
    an = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    kar[anahtar] = {"karar": karar, "an": an, "baslik": bul["baslik"]}
    db.ayar_yaz(pid, AYAR, json.dumps(kar, ensure_ascii=False))
    if karar == "onayla":
        from .dosya import atomik_yaz
        from .yollar import ofis_evi
        yol = ofis_evi() / "ofis_eksikleri.jsonl"
        try:
            eski = yol.read_text(encoding="utf-8") if yol.exists() else ""
        except OSError:
            eski = ""
        satir = json.dumps({**bul, "an": an, "not": notu, "proje": pid}, ensure_ascii=False)
        atomik_yaz(yol, eski + satir + "\n")
    db.olay_yaz(pid, "ofis_eksigi", f"{karar}: {bul['baslik']}", ajan_ad="insan")
    return {"anahtar": anahtar, "karar": karar}


def liste(proje_id: str = "") -> list:
    """Onaylanmis eksikler (gelistiricinin listesi)."""
    from .yollar import ofis_evi
    yol = ofis_evi() / "ofis_eksikleri.jsonl"
    out = []
    try:
        for s in yol.read_text(encoding="utf-8").splitlines():
            try:
                v = json.loads(s)
            except ValueError:
                continue
            if not proje_id or v.get("proje") == proje_id:
                out.append(v)
    except OSError:
        pass
    return out
