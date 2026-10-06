# -*- coding: utf-8 -*-
"""KARNE -- hangi motor hangi isi daha iyi yapiyor? Ofis KENDI tecrubesinden ogrenir.

Patron (03.10.2026): *"Claude mu GPT mi, hangisi hangi isde daha iyi? Ikisi de
surekli yeni model cikariyor, onune gecemeyiz."* Bu yuzden "Claude kodda iyi"
gibi bir kural koda SABITLENMEZ -- ilk yeni modelde eskir. Onun yerine:

* Her kapanan is bir satir yazar: is turu (rol + zorluk), motor, model, kac kez
  geri gonderildi, sure (`kaydet`). Satirlar ofisin EVINDE (`ev/karne.jsonl`)
  durur: gercek ofis ve gercek is seti ayni karneyi besler; sinamalar gecici
  evde kalir.
* Yeni isin motoru karneye ve iki aboneligin limit doluluguna gore secilir
  (`sec`). Kural kisa ve acik:
    1. Aday: kademe ayarinda modeli tanimli ve bu makinede calisan motorlar.
       Yeni motor (Gemini vb.) kademe ayarina girince kod degismeden aday olur.
    2. Limit esigindeki hesabin motoru (zincirin esigi) aday olmaz -- hepsi
       esikteyse sira degismez.
    3. DENEME PAYI: bir motorun bu tur iste `AZ_ORNEK`ten az kaydi varsa once
       ona is verilir. Yeni model kendini gosterebilsin; karne bos baslamasin.
    4. Yeterli kayit varsa TEMIZ GECME ORANI (geri gonderilmeden kapanan isler)
       yuksek olan secilir; fark `YAKIN`dan kucukse limiti daha BOS olan.
* DOLAR KARSILASTIRMASI YOK: Codex dolar bildirmiyor; iki aboneligin bedeli
  limit dolulugudur (madde 2 ve 4). Uydurma bir kur ile karsilastirmak
  yanlis gosteren gosterge olurdu.
* Secim GEREKCESIYLE doner ve kayda gecer (`motor_secimi` olayi). Karar
  ofisindir ama gorunmez degildir; Ayarlar'dan "ajanin kendi motoru"na
  donulebilir (`AYAR`).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

#: Ayar anahtari: "ajan" (VARSAYILAN: ajanin kendi motoru) ya da "karne".
#:
#: PATRON KARARI (04.10.2026): "Murat gibi yapalim, artik tartismayalim."
#: Her ajanin sabit motoru/modeli var; lider isi dogru AJANA verir; motor
#: kendiliginden DEGISMEZ (sistem stabil, surpriz yok). Karne olcmeye ve
#: kapanan isi yazmaya devam eder; otomatik secim yalniz bilerek acilirsa
#: (Ayarlar / gercek set `--motor karma`).
AYAR = "motor_secimi"
#: Capraz kontrol ayari: isi yapan motorun TERSI inceler ("acik"/"kapali").
CAPRAZ_AYAR = "capraz_inceleme"
#: Bu tur iste bundan az kaydi olan motora once is verilir (deneme payi).
AZ_ORNEK = 3
#: Temiz gecme oranlari bu kadar yakinsa limit dengesi karar verir.
YAKIN = 0.10
#: Okunacak en fazla satir (en yeniler) -- eski tecrube yeni modeli ezmesin.
PENCERE = 400

_KILIT = threading.Lock()


def _dosya():
    from .yollar import ofis_evi
    return ofis_evi() / "karne.jsonl"


def secim_acik_mi(db, proje_id: str) -> bool:
    return (db.ayar_oku(proje_id, AYAR, "ajan") or "ajan") == "karne"


def capraz_acik_mi(db, proje_id: str) -> bool:
    return (db.ayar_oku(proje_id, CAPRAZ_AYAR, "acik") or "acik") != "kapali"


def kaydet(*, meslek: str, zorluk: str, motor: str, model: str, gecti: bool,
           ret: int, sure_sn=None, jeton=None, gorev_id: str = "") -> None:
    """Kapanan (ya da birakilan) bir isin karne satiri. Yazilamazsa is durmaz."""
    if not motor:
        return
    satir = {"zaman": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "meslek": meslek or "", "zorluk": zorluk or "", "motor": motor,
             "model": model or "", "gecti": bool(gecti), "ret": int(ret or 0),
             "sure_sn": sure_sn}
    # JETON (06.10.2026, on tahmin E74): isci turlarinin toplami; tahmin
    # bunun ortancasindan kota yuzdesi cikarir (`ofis/tahmin.py`).
    if jeton:
        satir["jeton"] = int(jeton)
    if gorev_id:
        satir["gorev"] = gorev_id              # patronun puani buna baglanir
    try:
        with _KILIT:
            yol = _dosya()
            yol.parent.mkdir(parents=True, exist_ok=True)
            with open(yol, "a", encoding="utf-8") as f:
                f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    except OSError:
        pass                                   # karne bir gosterge; is durmaz


def _ham() -> list:
    try:
        with open(_dosya(), encoding="utf-8") as f:
            ham = f.readlines()[-PENCERE * 2:]
    except OSError:
        return []
    sonuc = []
    for s in ham:
        try:
            v = json.loads(s)
        except ValueError:
            continue
        if isinstance(v, dict):
            sonuc.append(v)
    return sonuc


def satirlar() -> list:
    """Is satirlari (en yeni PENCERE). Patron PUANI dusukse (<= 2) is
    `gecti` olsa da temiz sayilmaz: `puan` alani satira islenir."""
    hepsi = _ham()
    puan = {v["gorev"]: v["puan"] for v in hepsi
            if v.get("tur") == "puan" and v.get("gorev") and v.get("puan")}
    sonuc = []
    for v in hepsi:
        if v.get("tur") == "puan" or not v.get("motor"):
            continue
        if v.get("gorev") in puan:
            v = dict(v, puan=puan[v["gorev"]])
        sonuc.append(v)
    return sonuc[-PENCERE:]


def puan_yaz(*, gorev_id: str, puan: int, meslek: str, zorluk: str, motor: str, model: str) -> None:
    """Patronun teslim puani karneye (ayni ise sonraki puan oncekini ezer)."""
    satir = {"tur": "puan", "zaman": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "gorev": gorev_id, "puan": int(puan), "meslek": meslek or "", "zorluk": zorluk or "",
             "motor": motor or "", "model": model or ""}
    try:
        with _KILIT:
            yol = _dosya()
            yol.parent.mkdir(parents=True, exist_ok=True)
            with open(yol, "a", encoding="utf-8") as f:
                f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    except OSError:
        pass


def ozet(meslek: str = "", zorluk: str = "", kayitlar=None) -> dict:
    """{motor: {n, temiz, oran}} -- once (meslek, zorluk), yoksa meslek, yoksa hepsi.

    -> {"kova": "<hangi duzeyde bakildi>", "motorlar": {...}}
    """
    kayitlar = satirlar() if kayitlar is None else kayitlar
    for kova, suz in ((f"{meslek}/{zorluk}", lambda r: r.get("meslek") == meslek
                       and r.get("zorluk") == zorluk),
                      (meslek or "-", lambda r: r.get("meslek") == meslek),
                      ("hepsi", lambda r: True)):
        secilen = [r for r in kayitlar if suz(r)]
        if not secilen and kova != "hepsi":
            continue
        motorlar: dict = {}
        for r in secilen:
            m = motorlar.setdefault(r["motor"], {"n": 0, "temiz": 0})
            m["n"] += 1
            # Patronun dusuk puani (<= 2) lider kapatmis olsa da temiz degildir.
            if r.get("gecti") and not r.get("ret") and not (r.get("puan") and r["puan"] <= 2):
                m["temiz"] += 1
        for m in motorlar.values():
            m["oran"] = round(m["temiz"] / m["n"], 3) if m["n"] else 0.0
        return {"kova": kova, "motorlar": motorlar}
    return {"kova": "hepsi", "motorlar": {}}


def isin_motoru(db, proje_id: str, gorev: dict) -> tuple:
    """Isi FIILEN yapan motor/model (son isci turu; devir olduysa sonuncusu)
    ve isci turlarinin toplam suresi -> (motor, model, sure_sn)."""
    try:
        with db.baglanti() as c:
            rows = c.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'tur_ozeti' ORDER BY rowid", (proje_id, gorev["id"])).fetchall()
    except Exception:                          # noqa: BLE001
        rows = []
    motor = model = ""
    sure = 0.0
    for r in rows:
        try:
            v = json.loads(r[0] or "{}")
        except ValueError:
            continue
        if v.get("yol"):                       # lider / inceleme turu
            continue
        motor, model = v.get("motor") or motor, v.get("model") or model
        sure += float(v.get("sure_ms") or 0) / 1000
    return (motor or (gorev.get("motor_secimi") or ""), model, round(sure, 1) or None)


def isin_jetonu(db, proje_id: str, gorev: dict) -> int:
    """Isci turlarinin toplam jetonu (lider / inceleme turlari haric)."""
    toplam = 0
    try:
        with db.baglanti() as c:
            rows = c.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'tur_ozeti'", (proje_id, gorev["id"])).fetchall()
    except Exception:                          # noqa: BLE001
        return 0
    for r in rows:
        try:
            v = json.loads(r[0] or "{}")
        except ValueError:
            continue
        if not v.get("yol"):
            toplam += int(v.get("jeton") or 0)
    return toplam


def _doluluk(db, proje_id: str) -> dict:
    """{motor: en dolu penceresinin yuzdesi (0..1)} -- olcum yoksa motor YOK."""
    from . import kullanim
    sonuc: dict = {}
    try:
        for p in kullanim.son_pencereler(db, proje_id):
            for pen in (p.get("pencereler") or {}).values():
                k = (pen or {}).get("kullanim")
                if k is not None:
                    sonuc[p["motor"]] = max(sonuc.get(p["motor"], 0.0), float(k))
    except Exception:                          # noqa: BLE001 -- olcum yoksa denge yok
        return {}
    return sonuc


def gercek_motorlar(harita: dict) -> list:
    """Kademe ayarinda GERCEK modeli olan motorlar (sahte'nin modelleri bos)."""
    return [m for m, k in (harita or {}).items() if any((k or {}).values())]


def adaylar(ajan_motoru: str, *, fabrika, harita: dict) -> list:
    """Kademe ayarinda GERCEK modeli olan ve CALISAN motorlar (ajaninki dahil).

    Kademe haritasinda `sahte` de var (modelleri BOS): modeli olmayan motor
    aday degildir ve sahte ajanin motoru HIC degismez -- yoksa sinamalardaki
    sahte ajan gercek Claude'a gecerdi.
    """
    gercek = gercek_motorlar(harita)
    if ajan_motoru not in gercek:
        return []                              # sahte / bilinmeyen motor: secim yok
    sonuc = []
    for motor in gercek:
        try:
            if fabrika(motor).musait_mi():
                sonuc.append(motor)
        except Exception:                      # noqa: BLE001 -- acilamayan motor aday degil
            continue
    return sonuc


def sec(db, proje_id: str, *, ajan_motoru: str, meslek: str, zorluk: str,
        fabrika, harita: dict, kayitlar=None, doluluk=None, esik=None):
    """-> (motor, gerekce) ya da (None, sebep): None = ajanin kendi motoru kalir."""
    aday = adaylar(ajan_motoru, fabrika=fabrika, harita=harita)
    if len(aday) < 2:
        return None, "secilecek ikinci motor yok"
    dolu = _doluluk(db, proje_id) if doluluk is None else doluluk
    if esik is None:
        from .zincir import gecis_esikleri
        esikler, _ = gecis_esikleri(db, proje_id, "isci")
        esik = min((esikler or {}).values(), default=None)
    if esik is not None:
        bos = [m for m in aday if dolu.get(m, 0.0) < esik]
        if bos and len(bos) < len(aday):
            if len(bos) == 1:
                return bos[0], (f"oteki hesap(lar) limit esiginde (%{round(esik * 100)}); "
                                f"{bos[0]} %{round(dolu.get(bos[0], 0.0) * 100)}")
            aday = bos
    o = ozet(meslek, zorluk, kayitlar)
    m = o["motorlar"]

    def _bosluk(x):                            # limiti BOS olan once; olcum yoksa orta
        return dolu.get(x, 0.5)

    az = [x for x in aday if m.get(x, {}).get("n", 0) < AZ_ORNEK]
    if az:
        secilen = min(az, key=lambda x: (m.get(x, {}).get("n", 0), _bosluk(x), x))
        return secilen, (f"deneme payi: {secilen} bu tur iste ({o['kova']}) "
                         f"{m.get(secilen, {}).get('n', 0)} kez calisti")
    def _oran(x):
        return (m.get(x) or {}).get("oran", 0.0)

    sirali = sorted(aday, key=lambda x: (-_oran(x), _bosluk(x), x))
    ilk, ikinci = sirali[0], sirali[1]
    if _oran(ilk) - _oran(ikinci) < YAKIN:
        secilen = min((ilk, ikinci), key=lambda x: (_bosluk(x), x))
        return secilen, (f"karne yakin ({o['kova']}: {ilk} %{round(_oran(ilk) * 100)}, "
                         f"{ikinci} %{round(_oran(ikinci) * 100)} temiz); limiti daha bos "
                         f"olan {secilen}" + (f" (%{round(dolu[secilen] * 100)})"
                                              if secilen in dolu else ""))
    return ilk, (f"karne ({o['kova']}): {ilk} %{round(_oran(ilk) * 100)} temiz, "
                 f"{ikinci} %{round(_oran(ikinci) * 100)}")
