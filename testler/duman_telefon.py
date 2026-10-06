# -*- coding: utf-8 -*-
"""TELEFON (06.10.2026, Asama 3 / E36, E53, E66). Jeton yakmaz.

Yol Tailscale (patron karari). Sinanan, kapinin KENDISI:

1. Uzak istek taninir: yerel adres + aktarici izi (`tailscale serve`
   istegi 127.0.0.1'den iletir) da uzaktir.
2. Eslesmemis uzak cihaz yalniz telefon sayfasini ve eslestirmeyi gorur;
   panelin geri kalani 401.
3. Kod yalniz bilgisayarda uretilir, tek kullanimlik, sureli; anahtar
   defterde OZETIYLE durur.
4. Eslesmis cihaz yalniz izinli uclara gider (bekleyenler, onay, durum,
   durdur, lidere mesaj, ek); terminal, konsol, ayar yazma, kod uretme,
   cihaz listesi 403. Websocket (kabin, terminal) HER ZAMAN reddedilir --
   once `/ws/kabin`in hic yerel denetimi yoktu.
5. Cihaz kaldirilinca aninda 401 (acil kesme).
6. Bildirim: abone cihaza VAPID ile gider; dusen abonelik (410) temizlenir;
   masaustu bildirim izleyicisi ayni olaylari telefona da yollar.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from ofis import Ofis, Veritabani, telefon as T  # noqa: E402
from ofis.panel import olustur  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-telefon-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Telefon", amac="a", basari_olcutu="b", kok_klasor=str(d))
kn = ofis.kanat_ac("GENEL", "GE")
ofis.kadro.ise_al("lale", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(d))
ist = TestClient(olustur(db.yol))
UZAK = {"x-forwarded-for": "100.101.102.103", "tailscale-user-login": "patron@example.com"}

print("== telefon ==\n")
print("1. uzak istek taninir")
sina("yerel istek yerel", ist.get("/api/telefon/durum").json()["uzak"] is False)
sina("aktarici izli (tailscale serve) istek UZAK", ist.get("/api/telefon/durum", headers=UZAK).json()["uzak"])
sina("aktarici baslik eklemese de ts.net adiyla gelen istek UZAK",
     ist.get("/api/telefon/durum", headers={"host": "ofis.tail1234.ts.net"}).json()["uzak"])
sina("bilgisayarin kendi adi (localhost:8900) yerel",
     ist.get("/api/telefon/durum", headers={"host": "localhost:8900"}).json()["uzak"] is False)
sina("yalniz x-forwarded-for de uzak",
     ist.get("/api/telefon/durum", headers={"x-forwarded-for": "1.2.3.4"}).json()["uzak"])

print("\n2. eslesmemis uzak cihaz")
sina("telefon sayfasi acik", ist.get("/telefon", headers=UZAK).status_code == 200)
sina("hizmet iscisi acik (bildirim icin)", ist.get("/sw.js", headers=UZAK).status_code == 200)
for yol in ("/", "/api/ofis", "/api/bekleyenler", "/api/tahta"):
    r = ist.get(yol, headers=UZAK)
    sina(f"panelin geri kalani kapali: {yol} -> 401", r.status_code == 401, str(r.status_code))
sina("eslesmemis cihaz kod URETEMEZ", ist.post("/api/telefon/kod", json={}, headers=UZAK).status_code == 401)

print("\n3. kod ve eslestirme")
kod = ist.post("/api/telefon/kod", json={"ad": "telefon"}).json()["kod"]
sina("kod bilgisayarda uretildi (8 harf)", len(kod) == 8)
sina("yanlis kod reddedildi", ist.post("/api/telefon/eslestir", json={"kod": "YANLIS12"},
                                       headers=UZAK).status_code == 400)
r = ist.post("/api/telefon/eslestir", json={"kod": kod.lower(), "ad": "iPhone"}, headers=UZAK)
sina("dogru kod eslestirdi (kucuk harf de gecer)", r.status_code == 200, r.text[:120])
cerez = r.headers.get("set-cookie", "")
anahtar = cerez.split(f"{T.CEREZ}=", 1)[1].split(";", 1)[0] if T.CEREZ in cerez else ""
sina("anahtar cerezle, HttpOnly + Secure + SameSite=strict",
     bool(anahtar) and "httponly" in cerez.lower() and "secure" in cerez.lower()
     and "samesite=strict" in cerez.lower(), cerez[:160])
sina("ayni kod ikinci kez gecmez", ist.post("/api/telefon/eslestir", json={"kod": kod},
                                            headers=UZAK).status_code == 400)
with db.baglanti() as c:
    satir = json.dumps([dict(x) for x in c.execute("SELECT * FROM cihaz")])
sina("anahtar defterde ACIK durmuyor (yalniz ozeti)", anahtar and anahtar not in satir)
T.KOD_OMRU_SN, _eski = -1, T.KOD_OMRU_SN
k2 = T.kod_uret()
sina("suresi gecmis kod reddedilir", ist.post("/api/telefon/eslestir", json={"kod": k2},
                                              headers=UZAK).status_code == 400)
T.KOD_OMRU_SN = _eski

print("\n4. eslesmis cihaz: yalniz izinli uclar")
CIH = dict(UZAK, **{"x-ofis-cihaz": anahtar})
sina("durum: eslesmis", ist.get("/api/telefon/durum", headers=CIH).json()["eslesmis"])
for yol in ("/api/bekleyenler", "/api/tahta", "/api/oneriler", "/api/kuyruk"):
    r = ist.get(yol, headers=CIH)
    sina(f"izinli: GET {yol}", r.status_code == 200, str(r.status_code))
r = ist.post("/api/lidere", json={"metin": "telefondan merhaba"}, headers=CIH)
sina("izinli: lidere mesaj (kapi gecirdi)", r.status_code not in (401, 403), str(r.status_code))
for yontem, yol, govde in (("GET", "/api/ofis", None), ("POST", "/api/konsol", {}),
                           ("POST", "/api/ayarlar", {"anahtar": "x", "deger": "y"}),
                           ("GET", "/api/telefon/cihazlar", None), ("POST", "/api/telefon/kod", {}),
                           ("POST", "/api/gorev/1/devral", {}), ("GET", "/", None),
                           ("POST", "/api/anahtar", {"ad": "X", "deger": "y"})):
    r = ist.request(yontem, yol, json=govde, headers=CIH)
    sina(f"TELEFONA KAPALI: {yontem} {yol}", r.status_code == 403, str(r.status_code))
for ws in ("/ws/kabin", "/ws/terminal/1", "/ws/konsol/x"):
    try:
        with ist.websocket_connect(ws, headers=CIH) as s:
            s.receive_json()
        reddedildi = False
    except WebSocketDisconnect:
        reddedildi = True
    sina(f"websocket telefona KAPALI: {ws}", reddedildi)

print("\n5. acil kesme")
cid = T.cihazlar(db)[0]["id"]
sina("telefon cihazi KALDIRAMAZ", ist.post(f"/api/telefon/cihaz/{cid}/kaldir", headers=CIH).status_code == 403)
sina("bilgisayardan kaldirildi", ist.post(f"/api/telefon/cihaz/{cid}/kaldir").status_code == 200)
sina("kaldirilan cihaz aninda 401", ist.get("/api/bekleyenler", headers=CIH).status_code == 401)

print("\n6. bildirim")
kod = T.kod_uret()
c2 = T.eslestir(db, kod, ad="Android")
T.abone_yaz(db, c2["id"], {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}})
v = T.vapid()
sina("VAPID anahtari evde uretildi (acik anahtar 87 harf)", len(v["acik"]) == 87, str(len(v["acik"])))
giden = []
r = T.gonder(db, "Onay bekliyor", "push", gonderici=lambda **k: giden.append(k))
sina("abone cihaza gitti, VAPID ile", r["gonderildi"] == 1 and giden
     and giden[0]["vapid_private_key"] == v["ozel"] and "Onay bekliyor" in giden[0]["data"], str(r))


class _Yanit:
    status_code = 410


class _Dusen(Exception):
    response = _Yanit()


def _dusur(**k):
    raise _Dusen("gone")


r = T.gonder(db, "x", "y", gonderici=_dusur)
sina("dusen abonelik (410) temizlendi", r["dustu"] == 1 and T.cihazlar(db)[0]["bildirim"] == 0, str(r))
T.abone_yaz(db, c2["id"], {"endpoint": "https://push.example/abc"})
from ofis import bildirim as B  # noqa: E402
yakalanan = []
B.GONDERICI = lambda *a, **k: None
B.ACIK = True                       # yalniz gercek panelde acik; sinama acar
B.TELEFON_GONDERICI = lambda db_, b, m: (yakalanan.append(b), {"gonderildi": 1, "hata": ""})[1]
iz = B.Izleyici(ofis)
ofis.postane.onay_iste("lale", "git push origin main", risk="yuksek")
iz.tik()
sina("masaustu izleyici ayni olayi telefona da yolladi", "Onay bekliyor" in yakalanan, str(yakalanan))
sina("tailscale durumu olculuyor (bu makinede kurulu degil)", "kurulu" in T.tailscale_durumu())

print("\n7. GERCEK web push kutuphanesi (yerel bildirim sunucusu, internetsiz)")
# Telefonun tarayicisinin bildirim sunucusu yerine yerel bir sunucu: gercek
# `pywebpush` sifreler, VAPID ile imzalar ve POST eder; sunucu istegi alir.
import base64 as _b64, http.server as _hs, os as _os, threading as _th  # noqa: E402
from cryptography.hazmat.primitives import serialization as _ser  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec as _ec  # noqa: E402
_alinan = {}


class _Sunucu(_hs.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        _alinan["basliklar"] = {k.lower(): v for k, v in self.headers.items()}
        _alinan["govde"] = self.rfile.read(int(self.headers.get("content-length", 0)))
        self.send_response(201)
        self.end_headers()

    def log_message(self, *a):
        pass


_s = _hs.HTTPServer(("127.0.0.1", 0), _Sunucu)
_th.Thread(target=_s.serve_forever, daemon=True).start()
_ab = _ec.generate_private_key(_ec.SECP256R1()).public_key().public_bytes(
    _ser.Encoding.X962, _ser.PublicFormat.UncompressedPoint)
_u = lambda b: _b64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
T.abone_yaz(db, c2["id"], {"endpoint": f"http://127.0.0.1:{_s.server_port}/push/abc",
                           "keys": {"p256dh": _u(_ab), "auth": _u(_os.urandom(16))}})
r = T.gonder(db, "Onay bekliyor", "git push origin main")
_s.shutdown()
_bas = _alinan.get("basliklar", {})
sina("gercek kutuphane gonderdi (sunucu 201)", r["gonderildi"] == 1 and not r["hata"], str(r))
sina("icerik SIFRELI (aes128gcm), duz metin yok",
     _bas.get("content-encoding") == "aes128gcm" and b"git push" not in _alinan.get("govde", b""),
     str(_bas.get("content-encoding")))
sina("VAPID imzasi tasiyor (Authorization: vapid ...)",
     _bas.get("authorization", "").startswith("vapid ") and v["acik"] in _bas.get("authorization", ""),
     _bas.get("authorization", "")[:60])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
