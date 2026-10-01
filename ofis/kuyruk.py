# -*- coding: utf-8 -*-
"""KUYRUK -- patronun isleri siraya girer, donuste tek ozet (01.10.2026).

Kullanici: *"gece bilgisayari acik birakamayabilirim ... gunduz herseyi
yapabiliriz"*; istenen sey "ben yokken" calisan ofis: birkac isi birakip
baska ise gecebilmek, dondugunde ne oldugunu tek yerde gormek.

Olculmus bosluk: lider kosarken gelen ikinci mesaj panelde 409 ile
REDDEDILIYORDU ("bitmesini bekle"). Insan beklemek zorundaydi.

Nasil:
* Lidere giden HER mesaj buradan gecer (lider bosken de). Kural tek yerde:
  iki yol olsaydi (bosken dogrudan, mesgulken sira) donus raporu birini
  unuturdu.
* Sira DEFTERDE durur (`kuyruk` tablosu): panel kapanip acilsa da
  kaybolmaz.
* `seri`: ara vermeden islenen isler. Seri bitince, iki ya da daha fazla
  is islendiyse DONUS RAPORU yazilir. Rapor MODELSIZ kurulur (defterden):
  kota harcamaz, uydurmaz -- defterde ne varsa o.
* Bu modul sirayi tutar; isi KOSTURMAZ. Kosturan yuzeydir (panel), cunku
  "lider su an kosuyor mu" bilgisi onda.
"""

from __future__ import annotations

import json
import uuid

from . import surec as _surec
from .db import simdi


class KuyrukHatasi(ValueError):
    pass


DURUMLAR = ("bekliyor", "kosuyor", "bitti", "hata", "iptal")
OLAY = "donus_raporu"


def ekle(ofis, metin: str, lider_ad: str, *, atanan: str = "",
         tarayici_alani=None, kabin: bool = False, kaynak: str = "insan") -> dict:
    """Isi siranin sonuna koyar. Doner: kayit + `sira` (1 = siradaki)."""
    metin = (metin or "").strip()
    if not metin:
        raise KuyrukHatasi("Bos is siraya girmez.")
    if not (lider_ad or "").strip():
        raise KuyrukHatasi("Isin liderini belirt.")
    kayit = {"id": uuid.uuid4().hex, "proje_id": ofis.proje_id, "metin": metin,
             "lider_ad": lider_ad, "atanan": atanan or "",
             "tarayici_alani": json.dumps(list(tarayici_alani or []), ensure_ascii=False),
             "kabin": 1 if kabin else 0, "kaynak": kaynak, "durum": "bekliyor",
             "olusturuldu": simdi()}
    with ofis.db.baglanti() as c:
        c.execute("INSERT INTO kuyruk (id, proje_id, metin, lider_ad, atanan, tarayici_alani, "
                  "kabin, kaynak, durum, olusturuldu) VALUES (:id, :proje_id, :metin, "
                  ":lider_ad, :atanan, :tarayici_alani, :kabin, :kaynak, :durum, :olusturuldu)",
                  kayit)
        sira = c.execute("SELECT COUNT(*) FROM kuyruk WHERE proje_id = ? AND durum = 'bekliyor'",
                         (ofis.proje_id,)).fetchone()[0]
    return dict(kayit, sira=sira)


def _sozluk(r) -> dict:
    d = dict(r)
    try:
        d["tarayici_alani"] = json.loads(d.get("tarayici_alani") or "[]")
    except ValueError:
        d["tarayici_alani"] = []
    return d


def bekleyenler(ofis) -> list:
    with ofis.db.baglanti() as c:
        rows = c.execute("SELECT * FROM kuyruk WHERE proje_id = ? AND durum = 'bekliyor' "
                         "ORDER BY olusturuldu, rowid", (ofis.proje_id,)).fetchall()
    return [_sozluk(r) for r in rows]


def sira_al(ofis, seri: str):
    """Siradaki isi ALIR (bekliyor -> kosuyor). Yoksa None.

    Tek satirlik kosullu guncelleme: iki iplik ayni isi alamaz (ikincisinin
    `durum = 'bekliyor'` kosulu tutmaz, 0 satir degisir).
    """
    while True:
        with ofis.db.baglanti() as c:
            r = c.execute("SELECT id FROM kuyruk WHERE proje_id = ? AND durum = 'bekliyor' "
                          "ORDER BY olusturuldu, rowid LIMIT 1", (ofis.proje_id,)).fetchone()
            if not r:
                return None
            sinir = c.execute("SELECT COALESCE(MAX(rowid), 0) FROM gorev").fetchone()[0]
            # KESINTIDEN DEVAM eden satirin ILK baslangici ve is siniri
            # KORUNUR (01.10 canli deneme: uzerine yazilinca ilk kosuda
            # acilan isler bu istege baglanamiyordu).
            n = c.execute("UPDATE kuyruk SET durum = 'kosuyor', seri = ?, "
                          "basladi = COALESCE(basladi, ?), kosan_surec = ?, "
                          "gorev_sinir = CASE WHEN gorev_sinir > 0 THEN gorev_sinir ELSE ? END "
                          "WHERE id = ? AND durum = 'bekliyor'",
                          (seri, simdi(), _surec.kimlik(), sinir, r["id"])).rowcount
            if n:
                return _sozluk(c.execute("SELECT * FROM kuyruk WHERE id = ?",
                                         (r["id"],)).fetchone())


def bitir(ofis, kayit_id: str, durum: str = "bitti", not_: str = "") -> None:
    if durum not in DURUMLAR or durum in ("bekliyor", "kosuyor"):
        raise KuyrukHatasi(f"Gecersiz bitis durumu: {durum}")
    with ofis.db.baglanti() as c:
        c.execute("UPDATE kuyruk SET durum = ?, not_ = ?, bitti = ? WHERE id = ?",
                  (durum, (not_ or "")[:500], simdi(), kayit_id))


def iptal(ofis, kayit_id: str) -> dict:
    """YALNIZ bekleyen is iptal edilir; kosan is Durdur ile durur."""
    kayit_id = (kayit_id or "").strip()
    if len(kayit_id) < 4:
        raise KuyrukHatasi("Is kimligini ver (en az 4 harf).")
    with ofis.db.baglanti() as c:
        rows = c.execute("SELECT * FROM kuyruk WHERE proje_id = ? AND id LIKE ?",
                         (ofis.proje_id, kayit_id + "%")).fetchall()
        if len(rows) != 1:
            raise KuyrukHatasi("Bu kimlikle tek bir is bulunamadi.")
        r = rows[0]
        if r["durum"] != "bekliyor":
            raise KuyrukHatasi(f"Is '{r['durum']}' durumunda; yalniz siradaki is iptal "
                               "edilir (kosan isi Durdur ile durdur).")
        c.execute("UPDATE kuyruk SET durum = 'iptal', not_ = 'insan iptal etti', bitti = ? "
                  "WHERE id = ? AND durum = 'bekliyor'", (simdi(), r["id"]))
    ofis.db.olay_yaz(ofis.proje_id, "uyari", f"Siradaki is iptal edildi: {r['metin'][:80]}",
                     ajan_ad="insan")
    return _sozluk(r)


def seri_ogeleri(ofis, seri: str) -> list:
    with ofis.db.baglanti() as c:
        rows = c.execute("SELECT * FROM kuyruk WHERE proje_id = ? AND seri = ? "
                         "ORDER BY basladi, rowid", (ofis.proje_id, seri)).fetchall()
    return [_sozluk(r) for r in rows]


def acilan_gorevler(c, proje_id: str, k: dict) -> list:
    """Bu istek SIRASINDA acilan isler: rowid, alinirken kaydedilen sinirdan
    buyuk VE sonraki istek alinmadan once. Tek yer: rapor ve toparlama."""
    ust = c.execute("SELECT MIN(gorev_sinir) FROM kuyruk WHERE proje_id = ? "
                    "AND gorev_sinir > ? AND id != ? AND basladi IS NOT NULL",
                    (proje_id, int(k.get("gorev_sinir") or 0), k["id"])).fetchone()[0]
    sorgu = ("SELECT no, baslik, durum FROM gorev WHERE proje_id = ? AND rowid > ?"
             + (" AND rowid <= ?" if ust else "") + " ORDER BY no")
    arg = (proje_id, int(k.get("gorev_sinir") or 0)) + ((ust,) if ust else ())
    return [dict(r) for r in c.execute(sorgu, arg)]


DURUM_ADI = {"bitti": "bitti", "hata": "HATA", "iptal": "iptal", "kosuyor": "yarida",
             "bekliyor": "sirada"}
GOREV_ADI = {"bitti": "bitti", "iptal": "iptal", "inceleme": "incelemede",
             "calisiyor": "calisiyor", "hazir": "sirada", "bekliyor": "bekliyor"}


def _kisa(metin: str, n: int) -> str:
    metin = " ".join((metin or "").split())
    return metin if len(metin) <= n else metin[:n - 1].rstrip() + "…"


def donus_raporu(ofis, seri: str) -> str:
    """Serinin ozeti -- MODELSIZ, defterden. Iki isten azsa bos doner
    (tek isin cevabi zaten sohbette; ozet tekrar olurdu)."""
    from . import ekler as _ek
    ogeler = seri_ogeleri(ofis, seri)
    if len(ogeler) < 2:
        return ""
    satir = [f"**Dönüş raporu** — sıradaki {len(ogeler)} iş işlendi."]
    with ofis.db.baglanti() as c:
        for i, k in enumerate(ogeler, 1):
            bas, son = k.get("basladi") or "", k.get("bitti") or simdi()
            satir.append(f"\n{i}. «{_kisa(k['metin'], 90)}» — {DURUM_ADI.get(k['durum'], k['durum'])}")
            m = c.execute("SELECT cevap FROM mesaj WHERE proje_id = ? AND gonderen = 'insan' "
                          "AND alici = ? AND olusturuldu >= ? ORDER BY rowid LIMIT 1",
                          (ofis.proje_id, k["lider_ad"], bas)).fetchone()
            if m and (m["cevap"] or "").strip():
                metin, yollar = _ek.ayikla(m["cevap"])
                satir.append(f"   cevap: {_kisa(metin, 220)}"
                             + (f" ({len(yollar)} dosya ekli)" if yollar else ""))
            gorevler = acilan_gorevler(c, ofis.proje_id, k)
            for g in gorevler:
                satir.append(f"   #{g['no']} {_kisa(g['baslik'], 60)} — "
                             f"{GOREV_ADI.get(g['durum'], g['durum'])}")
            if k["durum"] == "hata" and k.get("not_"):
                satir.append(f"   sebep: {_kisa(k['not_'], 160)}")
    onaylar = ofis.postane.bekleyen_onaylar()
    sorular = ofis.postane.insan_bekleyenler()
    if onaylar or sorular:
        satir.append("\n**Sana düşen:**")
        for o in onaylar[:5]:
            satir.append(f"- {o['isteyen']} onay istiyor: {_kisa(o['eylem'], 100)}")
        for s in sorular[:5]:
            satir.append(f"- {s['gonderen']} soruyor: {_kisa(s['govde'], 100)}")
    kalan = bekleyenler(ofis)
    if kalan:
        satir.append(f"\nSırada {len(kalan)} iş daha bekliyor (sıra durduruldu).")
    return "\n".join(satir)


def devam_cevabi(ofis, kayit_id: str) -> str:
    """Kesintiden sonra SURDURULEN istegin cevabi -- modelsiz, defterden.

    01.10.2026 canli deneme: lider cevabini yazarken panel oldu; is
    surduruldu ama patronun mesaji CEVAPSIZ kaldi ("cevap gelmedi" balonu
    asili). Ofis, isteğe bagli islerin GERCEK durumunu cevap olarak yazar.
    """
    with ofis.db.baglanti() as c:
        r = c.execute("SELECT * FROM kuyruk WHERE id = ?", (kayit_id,)).fetchone()
        if not r:
            return ""
        k = _sozluk(r)
        gorevler = acilan_gorevler(c, ofis.proje_id, k)
    satir = ["Ofis kapanmadan önce başlamıştı; kaldığı yerden sürdürüldü."]
    for g in gorevler:
        satir.append(f"- #{g['no']} {_kisa(g['baslik'], 70)} — {GOREV_ADI.get(g['durum'], g['durum'])}")
    onaylar = ofis.postane.bekleyen_onaylar()
    if onaylar:
        satir.append("Sana düşen:")
        satir += [f"- {o['isteyen']} onay istiyor: {_kisa(o['eylem'], 100)}" for o in onaylar[:5]]
    metin = "\n".join(satir)
    with ofis.db.baglanti() as c:
        m = c.execute("SELECT id FROM mesaj WHERE proje_id = ? AND gonderen = 'insan' AND alici = ? "
                      "AND olusturuldu >= ? AND (cevap = '' OR cevap IS NULL) ORDER BY rowid LIMIT 1",
                      (ofis.proje_id, k["lider_ad"], k.get("basladi") or k["olusturuldu"])).fetchone()
        if m:
            c.execute("UPDATE mesaj SET cevap = ?, cevaplandi = ? WHERE id = ?",
                      (metin, simdi(), m["id"]))
    return metin


def raporu_yaz(ofis, seri: str) -> str:
    metin = donus_raporu(ofis, seri)
    if metin:
        ofis.db.olay_yaz(ofis.proje_id, OLAY, metin, ajan_ad="ofis")
    return metin
