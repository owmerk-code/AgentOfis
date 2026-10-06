# -*- coding: utf-8 -*-
"""ONIZLEME (06.10.2026, Asama 4 / K14). Jeton yakmaz; GERCEK yerel sunucu.

Yayin onayi bekleyen isin sitesi patronun bilgisayarinda acilir. Sinanan:
giris sayfasi olculur (kok, dist/), derlenmis sitenin KOK-MUTLAK yollari
calisir (`/assets/...`), gizli yollar (`.env`, `.ofis`) ve kok disi
verilmez, sunucu yalniz 127.0.0.1'de, ayni klasor tek sunucu; onay kartinda
yalniz YAYIN onayinda ve sayfa varsa dugme; uzaktan (telefon) acilmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, onizleme as OZ  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def getir(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):     # sunucu yok: KALDI, cokme degil
        return 0, ""


d = Path(tempfile.mkdtemp(prefix="ofis-onizleme-"))
print("1. giris sayfasi olculur")
bos = d / "bos"
bos.mkdir()
sina("sayfa yoksa giris yok", OZ.giris(bos) == "")
try:
    OZ.ac(bos)
    sina("sayfa yoksa acilmaz (aciklamali)", False)
except ValueError as exc:
    sina("sayfa yoksa acilmaz (aciklamali)", "index.html" in str(exc))
site = d / "site"
(site / "dist" / "assets").mkdir(parents=True)
(site / "dist" / "index.html").write_text(
    '<html><script src="/assets/app.js"></script><body>ONIZLEME_SAYFASI</body></html>',
    encoding="utf-8")
(site / "dist" / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
(site / "dist" / ".env").write_text("GIZLI=1", encoding="utf-8")
(site / "kaynak.txt").write_text("KOK_DISI", encoding="utf-8")
sina("derleme klasoru bulundu (dist/index.html)", OZ.giris(site) == "dist/index.html", OZ.giris(site))

print("\n2. yerel sunucu")
try:
    r = OZ.ac(site)
except ValueError as exc:      # coken sinama kalandan kotudur: KALDI yazilir
    r = {"url": "http://127.0.0.1:9/"}
    sina("dist/ sitesi acildi", False, str(exc))
sina("adres yalniz bu bilgisayar (127.0.0.1)", r["url"].startswith("http://127.0.0.1:"), r["url"])
k, govde = getir(r["url"])
sina("sayfa geliyor", k == 200 and "ONIZLEME_SAYFASI" in govde, f"{k}")
k, govde = getir(r["url"] + "assets/app.js")
sina("KOK-MUTLAK yol (/assets/app.js) calisiyor", k == 200 and "console.log" in govde, f"{k}")
sina("gizli dosya (.env) VERILMEZ", getir(r["url"] + ".env")[0] == 404)
sina("klasor disi VERILMEZ", "KOK_DISI" not in getir(r["url"] + "../kaynak.txt")[1]
     and "KOK_DISI" not in getir(r["url"] + "..%2fkaynak.txt")[1])
try:
    _ikinci = OZ.ac(site)["url"]
except ValueError:
    _ikinci = ""
sina("ayni klasor ayni sunucu", _ikinci == r["url"])

print("\n3. panel")
kok = d / "proje"
kok.mkdir()
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Oniz", amac="a", basari_olcutu="b", kok_klasor=str(kok))
KA = ofis.kanat_ac("WEB", "WB")
web = d / "WebKok"
ofis.takim_klasoru_ayarla(KA, str(web))
(web / "index.html").write_text("<p>TAKIM_SITESI</p>", encoding="utf-8")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(web))
ofis.kadro.ise_al("ece", "arayuz", kanat_id=KA, motor="sahte", klasor=str(web))
g = ofis.tahta.gorev_ac("site", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
ofis.postane.onay_iste("ece", "YAYIN / CANLIYA ALMA: netlify deploy", risk="yuksek", gorev_no=g["no"])
ofis.postane.onay_iste("ece", "GONDERIM: git push", risk="orta", gorev_no=g["no"])
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
on = ist.get("/api/bekleyenler").json()["onaylar"]
yayin = next(o for o in on if "YAYIN" in o["eylem"])
push = next(o for o in on if "GONDERIM" in o["eylem"])
sina("YAYIN onay kartinda onizleme var", yayin.get("onizleme") is True, str(yayin.get("onizleme")))
sina("yayin olmayan kartta yok", push.get("onizleme") is False)
sina("is kartinda onizleme bilgisi", ist.get(f"/api/gorev/{g['no']}").json().get("onizleme") is True)
r = ist.post("/api/onizleme", json={"gorev": g["no"]})
sina("panelden acildi; TAKIMIN klasoru", r.status_code == 200 and "TAKIM_SITESI" in getir(r.json()["url"])[1],
     r.text[:200])
g2 = ofis.tahta.gorev_ac("bos", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
(web / "index.html").unlink()
r = ist.post("/api/onizleme", json={"gorev": g2["no"]})
sina("sayfa yoksa 400 ve sebep", r.status_code == 400 and "index.html" in r.text, r.text[:200])
r = ist.post("/api/onizleme", json={"gorev": g["no"]}, headers={"x-forwarded-for": "100.64.0.9"})
sina("UZAKTAN (telefon/ag) acilmaz", r.status_code in (401, 403), str(r.status_code))
OZ.kapat_hepsi()

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
