# -*- coding: utf-8 -*-
"""TAKIM KOTA PAYI (06.10.2026, Asama 4; patron: "olsun, ayarlanabilir").

Abonelik hesabi butun takimlarin ORTAK havuzu. Bir takim (orn. gece
calisan bir arastirma) havuzu bitirirse oteki takimlar is yapamaz. Patron
takim basina bir PAY koyabilir: "MAGAZA bu hesabin 5 saatlik / 7 gunluk
penceresinin en fazla %40'ini kullanabilir". Varsayilan SINIRSIZ (0).

## Takimin kullanimi nasil OLCULUR (uydurulmaz)

Saglayici yalniz HESABIN toplam dolulugunu bildirir (`tur_ozeti.limit_pencere`
ve canli okuma -- `kullanim.son_pencereler`). Takimin payi:

    takim % = hesabin pencere dolulugu
              x (pencere basindan beri takimin turlarinin jetonu
                 / ayni surede ofisin o hesaptaki butun turlarinin jetonu)

Yani ofisin harcadigi kisim takimlara jetonla bolunur. Patronun ofis
DISINDAKI kullanimi (kendi Claude Code'u) da bu oranla dagilir -- takimin
payi oldugundan BUYUK gorunebilir, asla kucuk degil (kapali kalan taraf).
Pencere olculmemisse ya da yenilenmisse payi bilinmez: BILINMIYOR denir,
is DURDURULMAZ (olcemedigimize hukum vermeyiz) ve bu SOYLENIR.

## Dolunca ne olur

Takimin YENI isi baslamaz: siradaki mesaji beklemede kalir (oteki takimlarin
mesajlari surer), halka o takimin hazir isini baslatmaz. Calisan tur
kesilmez (yarim is, yarim kanit). Patrona pencere basina BIR KEZ soylenir
(`kota_payi_dolu` olayi -> bildirim). Pencere yenilenince is kendiliginden
surer.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

#: Pencerelerin uzunlugu. `7g_kapi` (Fable kapisi) payla yonetilmez:
#: kapi modeli kendi tavanina tabi (`butce.py`).
PENCERE_SURESI = {"5s": timedelta(hours=5), "7g": timedelta(days=7)}
PENCERE_ETIKETI = {"5s": "5 saatlik", "7g": "7 günlük"}


def payi(db, kanat_id: str) -> int:
    """Takimin payi (yuzde, 1..100); 0 = sinirsiz."""
    if not kanat_id:
        return 0
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT kota_payi FROM kanat WHERE id = ?", (kanat_id,)).fetchone()
    except Exception:                       # noqa: BLE001 -- eski defter: sutun yok
        return 0
    try:
        return max(0, min(100, int((r["kota_payi"] if r else 0) or 0)))
    except (TypeError, ValueError):
        return 0


def pay_yaz(db, proje_id: str, kanat_id: str, yuzde) -> int:
    try:
        y = int(yuzde or 0)
    except (TypeError, ValueError):
        raise ValueError("Kota payi 0-100 arasi tam sayi olmali (0 = sinirsiz).")
    if not 0 <= y <= 100:
        raise ValueError("Kota payi 0-100 arasi olmali (0 = sinirsiz).")
    with db.baglanti() as c:
        n = c.execute("UPDATE kanat SET kota_payi = ? WHERE id = ? AND proje_id = ?",
                      (y, kanat_id, proje_id)).rowcount
    if not n:
        raise ValueError("Takim yok.")
    db.olay_yaz(proje_id, "kota_payi", f"{kanat_id}: %{y}" if y else f"{kanat_id}: sinirsiz",
                ajan_ad="insan")
    return y


def _hesap(motor: str, hesap: str) -> str:
    hesap = (hesap or "").strip()
    return "" if hesap == (motor or "").strip() else hesap


def _zaman(metin):
    try:
        z = datetime.fromisoformat(str(metin))
    except (TypeError, ValueError):
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def kullanim(db, proje_id: str, kanat_id: str, *, simdi_=None) -> list:
    """Takimin her hesap/pencere icin olculen kullanimi.

    Doner: [{motor, hesap, pencere, hesap_yuzde, oran, takim_yuzde, yenilenme}]
    -- `takim_yuzde` 0..1 olcekte; olculemeyen pencere `None`.
    """
    from . import kullanim as _k
    su_an = simdi_ or datetime.now(timezone.utc)
    pencereler = _k.son_pencereler(db, proje_id, simdi_=su_an)
    if not pencereler:
        return []
    en_eski = min(su_an - PENCERE_SURESI[ad] for ad in PENCERE_SURESI)
    with db.baglanti() as c:
        rows = c.execute(
            "SELECT o.govde, o.olusturuldu, o.ajan_ad, g.kanat_id AS g_kanat "
            "FROM olay o LEFT JOIN gorev g ON g.id = o.gorev_id "
            "WHERE o.proje_id = ? AND o.tur = 'tur_ozeti' AND o.olusturuldu >= ?",
            (proje_id, en_eski.strftime("%Y-%m-%dT%H:%M:%S+00:00"))).fetchall()
        uye = {r[0]: (r[1] or "") for r in c.execute(
            "SELECT ad, kanat_id FROM ajan WHERE proje_id = ?", (proje_id,))}
    turlar = []
    for r in rows:
        try:
            v = json.loads(r["govde"] or "{}")
        except ValueError:
            continue
        if not isinstance(v, dict):
            continue
        try:
            jeton = int(v.get("jeton") or 0)
        except (TypeError, ValueError):
            jeton = 0
        # Turun takimi: isin takimi; issiz tur (lider triyaji, danisma)
        # turu kosanin takimi.
        takim = r["g_kanat"] if r["g_kanat"] is not None else uye.get(r["ajan_ad"] or "", "")
        turlar.append((_zaman(r["olusturuldu"]), (v.get("motor") or "").strip(),
                       _hesap(v.get("motor"), v.get("hesap")), jeton, takim or ""))
    cikti = []
    for p in pencereler:
        for ad, w in p["pencereler"].items():
            if ad not in PENCERE_SURESI:
                continue
            satir = {"motor": p["motor"], "hesap": p["hesap"], "pencere": ad,
                     "hesap_yuzde": w["kullanim"], "oran": None, "takim_yuzde": None,
                     "yenilenme": w["yenilenme"]}
            if w["kullanim"] is not None:
                bas = w["yenilenme"] - PENCERE_SURESI[ad]
                hepsi = takimin = 0
                for z, motor, hesap, jeton, takim in turlar:
                    if z is None or z < bas or motor != p["motor"] or hesap != p["hesap"]:
                        continue
                    hepsi += jeton
                    if takim == kanat_id:
                        takimin += jeton
                oran = (takimin / hepsi) if hepsi else 0.0
                satir["oran"] = round(oran, 4)
                satir["takim_yuzde"] = round(w["kullanim"] * oran, 4)
            cikti.append(satir)
    return cikti


def dolu_mu(db, proje_id: str, kanat_id: str, *, simdi_=None):
    """Takimin payi doldu mu? Doluysa en kotu pencerenin bilgisi, degilse None.

    Pay yoksa (0) olcum bile yapilmaz -- sinirsiz takima bedel binmez.
    """
    pay = payi(db, kanat_id)
    if not pay:
        return None
    sinir = pay / 100.0
    en = None
    for s in kullanim(db, proje_id, kanat_id, simdi_=simdi_):
        if s["takim_yuzde"] is not None and s["takim_yuzde"] >= sinir:
            if en is None or s["takim_yuzde"] > en["takim_yuzde"]:
                en = s
    if en is None:
        return None
    return {**en, "pay": pay}


def takim_adi(db, kanat_id: str) -> str:
    with db.baglanti() as c:
        r = c.execute("SELECT ad FROM kanat WHERE id = ?", (kanat_id,)).fetchone()
    return (r["ad"] if r else "") or kanat_id


def sebep_metni(db, kanat_id: str, d: dict) -> str:
    """Patronun okuyacagi tek cumle (kota dili; dolar yok)."""
    yen = d["yenilenme"]
    try:
        yerel = yen.astimezone().strftime("%d.%m %H:%M")
    except (AttributeError, ValueError, OSError):
        yerel = str(yen)
    return (f"{takim_adi(db, kanat_id)} takımının kota payı doldu: "
            f"{d['motor']} {PENCERE_ETIKETI.get(d['pencere'], d['pencere'])} penceresinin "
            f"%{round(d['takim_yuzde'] * 100)}'ini kullandı (pay %{d['pay']}). "
            f"Yeni işleri bekliyor; pencere {yerel}'de yenilenince kendiliğinden sürer. "
            "Payı Ayarlar'dan değiştirebilirsin.")


def bildir(db, proje_id: str, kanat_id: str, d: dict) -> bool:
    """Patrona pencere basina BIR KEZ soyler (her tikte tekrar bildirim
    yorgunluk olurdu). Doner: yeni yazildi mi."""
    anahtar = f"[{kanat_id}:{d['motor']}:{d['pencere']}:{d['yenilenme']:%Y%m%d%H%M}]"
    with db.baglanti() as c:
        if c.execute("SELECT 1 FROM olay WHERE proje_id = ? AND tur = 'kota_payi_dolu' "
                     "AND govde LIKE ?", (proje_id, f"%{anahtar}%")).fetchone():
            return False
    db.olay_yaz(proje_id, "kota_payi_dolu", f"{sebep_metni(db, kanat_id, d)} {anahtar}")
    return True


def dolu_takimlar(db, proje_id: str, *, simdi_=None) -> dict:
    """Payi dolu takimlar: {kanat_id: bilgi}. Patrona bir kez soylenir."""
    with db.baglanti() as c:
        try:
            idler = [r[0] for r in c.execute(
                "SELECT id FROM kanat WHERE proje_id = ? AND kota_payi > 0", (proje_id,))]
        except Exception:                   # noqa: BLE001 -- eski defter
            return {}
    out = {}
    for kid in idler:
        d = dolu_mu(db, proje_id, kid, simdi_=simdi_)
        if d:
            out[kid] = d
            try:
                bildir(db, proje_id, kid, d)
            except Exception:               # noqa: BLE001 -- bildirim isi durdurmaz
                pass
    return out
