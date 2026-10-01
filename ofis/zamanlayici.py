# -*- coding: utf-8 -*-
"""ZAMANLAYICI -- "her gun 09:00'da sunu yap" (01.10.2026, F5/4).

Kullanici: ofis "ben yokken" calisacak; altyapi hazir olsun ama sinama
GUNDUZ, yakin saatle (hafiza: gunduz-canli-test). Kurmak Claude Code'da
konusur gibi olmali: patron sohbete yazar, lider anlar (`karar=zamanla`),
saati OFIS dogrular -- lider serbest metinle zaman uydurmaz.

Kural (yapi, metin degil):
  {"tur": "gunluk",   "saat": "09:00"}
  {"tur": "haftalik", "saat": "14:00", "gunler": [0, 3]}   # 0 = pazartesi
  {"tur": "bir_kez",  "tarih": "2026-10-02", "saat": "10:30"}
  {"tur": "aralik",   "dakika": 30}                         # en az 15

Zamanlar YEREL saatle konusulur (patron Turkiye saatinde dusunur), defterde
UTC durur (`db.simdi` kurali). Vakti gelen is KUYRUGA girer -- ayri bir
kosturucu yok: kuyruk, bildirim, donus raporu aynen calisir.

Kacirilan (PC kapaliydi): acilista BIR KEZ kosar, birikmez; "gec kaldi"
diye soylenir. Ardindan bir sonraki vakit hesaplanir.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from . import kuyruk as _kuyruk
from .db import simdi

GUNLER = ("pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar")
AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık")
EN_AZ_ARALIK_DK = 15
#: Kacirilan is bundan eskiyse "gec kaldi" denir (yine de BIR KEZ kosar).
GEC_ESIGI = timedelta(minutes=10)



class ZamanHatasi(ValueError):
    pass


def _saat(s) -> tuple:
    try:
        sa, dk = str(s).strip().split(":")
        sa, dk = int(sa), int(dk)
    except ValueError:
        raise ZamanHatasi(f"Saat 'SS:DD' bicimde olmali ('{s}').")
    if not (0 <= sa <= 23 and 0 <= dk <= 59):
        raise ZamanHatasi(f"Gecersiz saat: '{s}'.")
    return sa, dk


def dogrula(kural) -> dict:
    """Liderin verdigi kurali OFIS dogrular; temiz kopya doner."""
    if isinstance(kural, str):
        try:
            kural = json.loads(kural)
        except ValueError:
            raise ZamanHatasi("Zaman kurali okunamadi.")
    if not isinstance(kural, dict):
        raise ZamanHatasi("Zaman kurali bir nesne olmali.")
    tur = kural.get("tur")
    if tur == "gunluk":
        _saat(kural.get("saat"))
        return {"tur": tur, "saat": "%02d:%02d" % _saat(kural["saat"])}
    if tur == "haftalik":
        g = kural.get("gunler")
        if not isinstance(g, list) or not g or not all(isinstance(x, int) and 0 <= x <= 6 for x in g):
            raise ZamanHatasi("Haftalik kuralda `gunler` 0 (pazartesi) .. 6 (pazar) listesi olmali.")
        return {"tur": tur, "saat": "%02d:%02d" % _saat(kural.get("saat")),
                "gunler": sorted(set(g))}
    if tur == "bir_kez":
        try:
            t = date.fromisoformat(str(kural.get("tarih")))
        except ValueError:
            raise ZamanHatasi("Bir kezlik kuralda `tarih` YYYY-AA-GG olmali.")
        return {"tur": tur, "tarih": t.isoformat(), "saat": "%02d:%02d" % _saat(kural.get("saat"))}
    if tur == "aralik":
        try:
            dk = int(kural.get("dakika"))
        except (TypeError, ValueError):
            raise ZamanHatasi("Aralik kuralinda `dakika` sayi olmali.")
        if dk < EN_AZ_ARALIK_DK:
            raise ZamanHatasi(f"En sik {EN_AZ_ARALIK_DK} dakikada bir (kota korunur).")
        return {"tur": tur, "dakika": dk}
    raise ZamanHatasi("Zaman turu: gunluk, haftalik, bir_kez ya da aralik.")


def _yerel(simdi_utc: datetime) -> datetime:
    return simdi_utc.astimezone()


def sonraki_an(kural: dict, simdi_utc: datetime):
    """Simdiden SONRAKI ilk vakit (UTC). Bir kezlik gecmisse None."""
    yer = _yerel(simdi_utc)
    if kural["tur"] == "aralik":
        return simdi_utc + timedelta(minutes=kural["dakika"])
    sa, dk = _saat(kural["saat"])
    if kural["tur"] == "bir_kez":
        t = date.fromisoformat(kural["tarih"])
        an = yer.replace(year=t.year, month=t.month, day=t.day, hour=sa, minute=dk,
                         second=0, microsecond=0)
        return an.astimezone(timezone.utc) if an > yer else None
    for ileri in range(0, 8):
        gun = (yer + timedelta(days=ileri)).replace(hour=sa, minute=dk, second=0, microsecond=0)
        if gun <= yer:
            continue
        if kural["tur"] == "haftalik" and gun.weekday() not in kural["gunler"]:
            continue
        return gun.astimezone(timezone.utc)
    return None


def insan_metni(kural: dict) -> str:
    if kural["tur"] == "gunluk":
        return f"her gün {kural['saat']}"
    if kural["tur"] == "haftalik":
        return f"her {', '.join(GUNLER[g] for g in kural['gunler'])} {kural['saat']}"
    if kural["tur"] == "aralik":
        return f"her {kural['dakika']} dakikada bir"
    t = date.fromisoformat(kural["tarih"])
    return f"{t.day} {AYLAR[t.month - 1]} {kural['saat']} (bir kez)"


def an_metni(an_utc_iso: str) -> str:
    if not an_utc_iso:
        return "-"
    an = datetime.fromisoformat(an_utc_iso).astimezone()
    bugun = datetime.now().astimezone().date()
    gun = ("bugün" if an.date() == bugun else "yarın" if an.date() == bugun + timedelta(days=1)
           else f"{an.day} {AYLAR[an.month - 1]}")
    return f"{gun} {an:%H:%M}"


def ekle(ofis, metin: str, lider_ad: str, kural, *, kaynak: str = "insan",
         simdi_utc: datetime = None) -> dict:
    metin = (metin or "").strip()
    if not metin:
        raise ZamanHatasi("Zamanlanacak isin metni bos.")
    k = dogrula(kural)
    simdi_utc = simdi_utc or datetime.now(timezone.utc)
    sonraki = sonraki_an(k, simdi_utc)
    if sonraki is None:
        raise ZamanHatasi("Bu vakit gecmiste kaldi.")
    with ofis.db.baglanti() as c:
        no = c.execute("SELECT COALESCE(MAX(no), 0) + 1 FROM zamanli WHERE proje_id = ?",
                       (ofis.proje_id,)).fetchone()[0]
        kayit = {"id": uuid.uuid4().hex, "proje_id": ofis.proje_id, "no": no, "metin": metin,
                 "lider_ad": lider_ad, "kural": json.dumps(k, ensure_ascii=False),
                 "sonraki": sonraki.isoformat(timespec="seconds"), "kaynak": kaynak,
                 "olusturuldu": simdi()}
        c.execute("INSERT INTO zamanli (id, proje_id, no, metin, lider_ad, kural, sonraki, kaynak, "
                  "olusturuldu) VALUES (:id, :proje_id, :no, :metin, :lider_ad, :kural, :sonraki, "
                  ":kaynak, :olusturuldu)", kayit)
    ofis.db.olay_yaz(ofis.proje_id, "zamanli_eklendi",
                     f"Z{no}: {insan_metni(k)} — {metin[:80]}", ajan_ad=lider_ad)
    return dict(kayit, kural=k)


def liste(ofis, *, hepsi: bool = False) -> list:
    with ofis.db.baglanti() as c:
        rows = c.execute("SELECT * FROM zamanli WHERE proje_id = ?" + ("" if hepsi else " AND etkin = 1")
                         + " ORDER BY no", (ofis.proje_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["kural"] = json.loads(d["kural"])
        d["ne_zaman"] = insan_metni(d["kural"])
        d["sonraki_metin"] = an_metni(d["sonraki"]) if d["etkin"] else "-"
        out.append(d)
    return out


def iptal(ofis, no) -> dict:
    try:
        no = int(str(no).lstrip("Zz"))
    except ValueError:
        raise ZamanHatasi("Zamanli is numarasi (orn. Z2) gerekli.")
    with ofis.db.baglanti() as c:
        r = c.execute("SELECT * FROM zamanli WHERE proje_id = ? AND no = ? AND etkin = 1",
                      (ofis.proje_id, no)).fetchone()
        if not r:
            raise ZamanHatasi(f"Z{no} diye etkin bir zamanli is yok.")
        c.execute("UPDATE zamanli SET etkin = 0, sonraki = NULL WHERE id = ?", (r["id"],))
    ofis.db.olay_yaz(ofis.proje_id, "zamanli_iptal", f"Z{no} iptal edildi: {r['metin'][:80]}")
    return dict(r)


def vadesi_gelenleri_sirala(ofis, simdi_utc: datetime = None) -> list:
    """Vakti gelen her isi KUYRUGA koyar, sonraki vakti hesaplar.

    Kacirilan vakitler BIRIKMEZ: kac vakit gecmis olursa olsun bir kez
    kosar. Doner: siraya giren kayitlar."""
    simdi_utc = simdi_utc or datetime.now(timezone.utc)
    giren = []
    with ofis.db.baglanti() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM zamanli WHERE proje_id = ? AND etkin = 1 AND sonraki IS NOT NULL "
            "AND sonraki <= ?", (ofis.proje_id, simdi_utc.isoformat(timespec="seconds")))]
    for r in rows:
        k = json.loads(r["kural"])
        gec = simdi_utc - datetime.fromisoformat(r["sonraki"]) > GEC_ESIGI
        sonraki = sonraki_an(k, simdi_utc)
        with ofis.db.baglanti() as c:
            # Kosullu: ayni vakit iki kez siraya girmesin (iki panel / iki tur).
            n = c.execute("UPDATE zamanli SET sonraki = ?, son_calisma = ?, etkin = ? "
                          "WHERE id = ? AND sonraki = ?",
                          (sonraki.isoformat(timespec="seconds") if sonraki else None,
                           simdi(), 1 if sonraki else 0, r["id"], r["sonraki"])).rowcount
        if not n:
            continue
        _kuyruk.ekle(ofis, f"[Zamanlanmış iş Z{r['no']} · {insan_metni(k)}] {r['metin']}",
                     r["lider_ad"], kaynak="zamanlayici")
        ofis.db.olay_yaz(ofis.proje_id, "zamanli_calisti",
                         f"Zamanlanmış iş Z{r['no']} başladı"
                         + (f" (geç kaldı: {an_metni(r['sonraki'])} vaktindeydi, bilgisayar kapalıydı)"
                            if gec else "") + f": {r['metin'][:100]}", ajan_ad="ofis")
        giren.append(r)
    return giren


def triyaj_blogu(ofis) -> str:
    """Liderin triyajina: kayitli zamanli isler (iptal icin numara)."""
    ogeler = liste(ofis)
    if not ogeler:
        return ""
    return "\n".join(["# ZAMANLANMIŞ İŞLER (kayıtlı)", ""]
                     + [f"- Z{z['no']}: {z['ne_zaman']} — {z['metin'][:100]} (sonraki: {z['sonraki_metin']})"
                        for z in ogeler])
