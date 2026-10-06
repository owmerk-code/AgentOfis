# -*- coding: utf-8 -*-
"""TELEFON (06.10.2026, Asama 3 / E36, E53, E66) -- patron disaridayken ofis.

Yol: Tailscale (patron karari 06.10). Telefon ile bilgisayar ayni OZEL agda;
panel `tailscale serve` ile o aga HTTPS'le acilir, ev agina ve internete
acilmaz. Uc kapi ust uste:

1. **Uzak istek TANINIR** (`uzak_mi`): adres yerel degilse YA DA araya giren
   bir aktaricinin izi varsa (`tailscale serve` istegi 127.0.0.1'den
   ILETIR; yalniz adrese bakan kapi telefona bilgisayarin terminalini
   acardi -- bu sinif tam olarak bunu onler).
2. **Cihaz anahtari**: telefon bir kez ESLESTIRILIR (bilgisayardaki panelde
   tek kullanimlik kod); sonra her istek cihazin anahtarini tasir. Cihaz
   tek tikla KALDIRILIR (kayip telefon = acil kesme). Anahtar defterde
   yalniz OZETIYLE durur.
3. **Izin listesi**: telefondan yalniz telefonun isi gorulur -- bekleyenler,
   onay/ret, soru cevabi, islerin durumu, durdurma, lidere mesaj ve
   fotograf. Terminal, devralma, ayar yazma, anahtar, kabin, takim kurma
   TELEFONA KAPALI (bilgisayarda yapilir).

Bildirim: Web Push (telefonun tarayicisi; icerik uctan uca sifreli, VAPID
anahtari ofisin evinde). Masaustu bildirimiyle AYNI olaylardan beslenir.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import uuid

from .db import simdi

#: Yerel sayilan adresler (`testclient` Starlette'in sinama istemcisi).
YEREL = ("127.0.0.1", "::1", "localhost", "testclient")
#: Panelin kendi adresleri (Host basligi). `testserver` sinama istemcisinin adi.
YEREL_ADLAR = ("127.0.0.1", "localhost", "::1", "testserver")
#: Araya giren aktaricinin izleri: varsa istek UZAKTAN gelmistir.
AKTARICI_BASLIKLARI = ("x-forwarded-for", "forwarded", "x-real-ip",
                       "tailscale-user-login", "tailscale-user-name")
CEREZ = "ofis_cihaz"
#: Eslestirme kodunun omru: kisa -- kod ekranda gorunur.
KOD_OMRU_SN = 600

#: Telefondan erisilebilen uclar (yontem, yol deseni). Disindaki her sey 403.
IZINLI = (
    ("GET", r"/telefon"), ("GET", r"/telefon/.*"), ("GET", r"/sw\.js"),
    ("GET", r"/favicon\.ico"),
    ("GET", r"/api/telefon/.*"), ("POST", r"/api/telefon/.*"),
    ("GET", r"/api/bekleyenler"), ("GET", r"/api/oneriler"),
    ("POST", r"/api/onay/[^/]+"), ("POST", r"/api/soru/[^/]+/cevap"),
    ("POST", r"/api/hafiza_onerisi/[^/]+"),
    ("GET", r"/api/tahta"), ("GET", r"/api/kuyruk"), ("GET", r"/api/takim"),
    ("POST", r"/api/durdur"), ("POST", r"/api/lidere"),
    ("POST", r"/api/ek"), ("GET", r"/api/ek/[^/]+"),
)
#: Anahtarsiz (henuz eslesmemis) telefona acik olanlar.
ESLESMESIZ = (("GET", r"/telefon"), ("GET", r"/telefon/.*"), ("GET", r"/sw\.js"),
              ("GET", r"/favicon\.ico"), ("POST", r"/api/telefon/eslestir"),
              ("GET", r"/api/telefon/durum"))

_KODLAR: dict = {}           # kod ozeti -> (bitis, ad)


class TelefonHatasi(ValueError):
    pass


def _ozet(metin: str) -> str:
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


def uzak_mi(baglanti) -> bool:
    """Istek (ya da websocket) bu bilgisayardan mi, yoksa uzaktan mi."""
    istemci = getattr(baglanti, "client", None)
    if istemci is None or istemci.host not in YEREL:
        return True
    basliklar = getattr(baglanti, "headers", {}) or {}
    if any(b in basliklar for b in AKTARICI_BASLIKLARI):
        return True
    # IKINCI ISARET: istek bilgisayarin kendi adina degil (orn. `ofis.xx.ts.net`)
    # gelmisse araya bir aktarici girmistir -- aktarici baslik eklemese de.
    ad = str(basliklar.get("host", "") or "").rsplit(":", 1)[0].strip("[]").lower()
    return bool(ad) and ad not in YEREL_ADLAR


def izinli_mi(yontem: str, yol: str, *, eslesmis: bool) -> bool:
    liste = IZINLI if eslesmis else ESLESMESIZ
    return any(yontem.upper() == y and re.fullmatch(d, yol) for y, d in liste)


# ------------------------------------------------------------------ cihazlar

def kod_uret(ad: str = "telefon") -> str:
    """Bilgisayardaki panelde gosterilen TEK KULLANIMLIK eslestirme kodu."""
    for ozet, (bitis, _a) in list(_KODLAR.items()):
        if bitis < time.time():
            _KODLAR.pop(ozet, None)
    kod = "".join(secrets.choice("23456789ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(8))
    _KODLAR[_ozet(kod)] = (time.time() + KOD_OMRU_SN, (ad or "telefon")[:40])
    return kod


def eslestir(db, kod: str, *, ad: str = "") -> dict:
    """Kod dogruysa cihaz kaydi + ANAHTAR (yalniz bir kez doner)."""
    kayit = _KODLAR.pop(_ozet((kod or "").strip().upper()), None)
    if not kayit or kayit[0] < time.time():
        raise TelefonHatasi("Kod gecersiz ya da suresi doldu. Bilgisayardaki panelden yeni kod al.")
    anahtar = secrets.token_urlsafe(32)
    cid = uuid.uuid4().hex
    with db.baglanti() as c:
        c.execute("INSERT INTO cihaz (id, ad, anahtar_ozet, olusturuldu, son_gorulme) "
                  "VALUES (?,?,?,?,?)", (cid, (ad or kayit[1])[:40], _ozet(anahtar), simdi(), simdi()))
    return {"id": cid, "ad": (ad or kayit[1])[:40], "anahtar": anahtar}


def cihaz_bul(db, anahtar: str) -> dict | None:
    if not anahtar:
        return None
    with db.baglanti() as c:
        r = c.execute("SELECT * FROM cihaz WHERE anahtar_ozet = ? AND kaldirildi IS NULL",
                      (_ozet(anahtar),)).fetchone()
        if r:
            c.execute("UPDATE cihaz SET son_gorulme = ? WHERE id = ?", (simdi(), r["id"]))
    return dict(r) if r else None


def cihazlar(db) -> list:
    with db.baglanti() as c:
        rows = c.execute("SELECT id, ad, olusturuldu, son_gorulme, "
                         "(push_abonelik != '') AS bildirim FROM cihaz "
                         "WHERE kaldirildi IS NULL ORDER BY olusturuldu").fetchall()
    return [dict(r) for r in rows]


def kaldir(db, cihaz_id: str) -> dict:
    with db.baglanti() as c:
        n = c.execute("UPDATE cihaz SET kaldirildi = ? WHERE id = ? AND kaldirildi IS NULL",
                      (simdi(), cihaz_id)).rowcount
    if not n:
        raise TelefonHatasi("Cihaz bulunamadi.")
    return {"id": cihaz_id, "kaldirildi": True}


def abone_yaz(db, cihaz_id: str, abonelik: dict) -> None:
    if not isinstance(abonelik, dict) or not abonelik.get("endpoint"):
        raise TelefonHatasi("Bildirim aboneligi gecersiz.")
    with db.baglanti() as c:
        c.execute("UPDATE cihaz SET push_abonelik = ? WHERE id = ?",
                  (json.dumps(abonelik)[:4000], cihaz_id))


# ------------------------------------------------------------------ bildirim (Web Push)

def _vapid_yolu():
    from .yollar import ofis_evi
    return ofis_evi() / "vapid.json"


def vapid() -> dict:
    """Ofisin VAPID anahtar cifti (yoksa uretilir, evde durur).

    `ozel`: PKCS8 DER, base64url -- `pywebpush`in bekledigi bicim. OLCULDU
    (06.10.2026, gercek kutuphane + yerel bildirim sunucusu): PEM verilince
    "Could not deserialize key data" ile HIC gonderilmiyordu; sahte
    gondericiyle sinama bunu gormemisti.
    """
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    yol = _vapid_yolu()
    ozel = None
    if yol.is_file():
        try:
            v = json.loads(yol.read_text(encoding="utf-8"))
            if v.get("ozel") and v.get("acik"):
                return v
            if v.get("ozel_pem"):                     # eski bicim: ayni anahtar korunur
                ozel = serialization.load_pem_private_key(v["ozel_pem"].encode(), None)
        except (OSError, ValueError):
            pass
    ozel = ozel or ec.generate_private_key(ec.SECP256R1())
    ham = ozel.public_key().public_bytes(serialization.Encoding.X962,
                                         serialization.PublicFormat.UncompressedPoint)
    der = ozel.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
    b64 = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")  # noqa: E731
    v = {"ozel": b64(der), "acik": b64(ham)}
    from .dosya import atomik_yaz
    atomik_yaz(yol, json.dumps(v))
    return v


def gonder(db, baslik: str, govde: str, *, adres: str = "/telefon", gonderici=None) -> dict:
    """Bildirimi aboneligi olan her cihaza yollar. Dusen abonelik (410/404)
    temizlenir. Doner: {gonderildi, dustu, hata}."""
    with db.baglanti() as c:
        rows = c.execute("SELECT id, push_abonelik FROM cihaz WHERE kaldirildi IS NULL "
                         "AND push_abonelik != ''").fetchall()
    if not rows:
        return {"gonderildi": 0, "dustu": 0, "hata": ""}
    v = vapid()
    yuk = json.dumps({"baslik": baslik[:120], "govde": govde[:300], "adres": adres})
    if gonderici is None:
        from pywebpush import webpush as gonderici
    sonuc = {"gonderildi": 0, "dustu": 0, "hata": ""}
    for r in rows:
        try:
            gonderici(subscription_info=json.loads(r["push_abonelik"]), data=yuk,
                      vapid_private_key=v["ozel"],
                      vapid_claims={"sub": "mailto:ofis@localhost"}, ttl=3600)
            sonuc["gonderildi"] += 1
        except Exception as exc:                      # noqa: BLE001 -- bir cihaz digerini durdurmaz
            kod = getattr(getattr(exc, "response", None), "status_code", None)
            if kod in (404, 410):
                with db.baglanti() as c:
                    c.execute("UPDATE cihaz SET push_abonelik = '' WHERE id = ?", (r["id"],))
                sonuc["dustu"] += 1
            else:
                sonuc["hata"] = f"{exc.__class__.__name__}: {str(exc)[:200]}"
    return sonuc


# ------------------------------------------------------------------ tailscale

def tailscale_durumu() -> dict:
    """Bu bilgisayarda Tailscale kurulu mu, bagli mi, adresi ne.

    Kurulum ve giris PATRONUN isidir; ofis yalniz OLCER ve ne yapilacagini
    soyler. Olculemeyen alan None.
    """
    import shutil
    import subprocess
    from .surec import PENCERE_YOK
    exe = shutil.which("tailscale") or (
        r"C:\Program Files\Tailscale\tailscale.exe"
        if __import__("os").path.isfile(r"C:\Program Files\Tailscale\tailscale.exe") else "")
    if not exe:
        return {"kurulu": False, "bagli": None, "adres": None, "ad": None}
    try:
        r = subprocess.run([exe, "status", "--json"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10, creationflags=PENCERE_YOK)
        v = json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"kurulu": True, "bagli": None, "adres": None, "ad": None}
    ben = v.get("Self") or {}
    adresler = [a for a in (ben.get("TailscaleIPs") or []) if a.startswith("100.")]
    return {"kurulu": True, "bagli": v.get("BackendState") == "Running",
            "adres": adresler[0] if adresler else None,
            "ad": (ben.get("DNSName") or "").rstrip(".") or None}
