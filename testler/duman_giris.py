# -*- coding: utf-8 -*-
"""GIRIS ISTEGI duman testi -- jeton yakmadan (28.09.2026).

Kullanici: *"ajanlar bir is yaptiklarinda calismalari icin gerekli hesap
girisini isteyecek, giris yaparim, devam eder."*

Sinananlar:
  1. `giris.iste` kapilari (tur, hizmet, neden, adres, gorev).
  2. Istek onay defterine duser, ajan BEKLER, kart ayristirilir.
  3. Web "giris yaptim" -> is PAYLASILAN KABINE tasinir (kaynak + tiklama).
  4. "Yapamam" gerekcesiz reddedilir, gerekceyle ajana gider.
  5. Baglayici "yaptim" OLCULUR: bagli degilse KABUL EDILMEZ.
  6. Kapanmis ise giris uygulanmaz.
  7. MCP araci: sifre almaz, kimlik ortamdan gelir.
  8. Kapi: sifre alanina ajan yazamaz, yazilan DEGER karta girmez.
  9. Panel: kart `giris` alaniyla gelir; siradan onay yolu ARKA KAPI olamaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, baglayici, giris, riskli  # noqa: E402

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def hata_mi(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except Exception as exc:                     # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


_KOK = Path(tempfile.mkdtemp(prefix="ofis-giris-"))
db = Veritabani(_KOK / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Giris", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
k = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=k, motor="sahte", klasor=str(_KOK))
ofis.kadro.ise_al("isci", "arastirma", kanat_id=k, motor="sahte", klasor=str(_KOK))


def is_ac(ad):
    g = ofis.tahta.gorev_ac(ad, neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=[ad.lower() + ".md"], kanat_id=k)
    ofis.tahta.sahiplen(g["no"], "isci", g["revizyon"])
    return g["no"]


def bekleyen(no):
    return [o for o in ofis.postane.bekleyen_onaylar() if o.get("gorev_no") == no]


print("\n-- 1. iste: kapilar --")
n1 = is_ac("Web")
sina("bilinmeyen tur reddedilir",
     "tur" in hata_mi(giris.iste, ofis, "isci", n1, tur="uzay", hizmet="x", neden="y"))
sina("hizmet bos reddedilir",
     bool(hata_mi(giris.iste, ofis, "isci", n1, tur="web", hizmet="", neden="y",
                  adres="https://a.com")))
sina("neden bos reddedilir",
     bool(hata_mi(giris.iste, ofis, "isci", n1, tur="web", hizmet="x", neden="",
                  adres="https://a.com")))
sina("web adresi yoksa reddedilir",
     bool(hata_mi(giris.iste, ofis, "isci", n1, tur="web", hizmet="x", neden="y")))
sina("gorevsiz istek reddedilir",
     bool(hata_mi(giris.iste, ofis, "isci", None, tur="diger", hizmet="x", neden="y")))
sina("reddedilen istek onay acmadi", not bekleyen(n1))

print("\n-- 2. iste: defter, bekleme, ayristirma --")
r = giris.iste(ofis, "isci", n1, tur="web", hizmet="Magaza yonetimi",
               adres="https://admin.ornek.com/giris?x=1", neden="siparisleri okumak icin")
kart = bekleyen(n1)
sina("onay defterine TEK kart dustu", len(kart) == 1, str(kart))
sina("kart giris olarak taninir", kart and giris.giris_mi(kart[0]))
v = giris.ayristir(kart[0]) if kart else {}
sina("kaynak origin'e indirgendi", v.get("kaynak") == "https://admin.ornek.com", str(v))
sina("insan talimati kabini ve SIFREYI YAZMAMAYI soyler",
     "kabin" in giris.insan_talimati(v) and "YAZMA" in giris.insan_talimati(v))
sina("ajan BEKLIYOR sayilir (kilit korunur, oda bekleme)",
     bool(ofis.postane.bekliyor_mu("isci")))
with db.baglanti() as c:
    ol = c.execute("SELECT COUNT(*) FROM olay WHERE tur='giris_istendi'").fetchone()[0]
sina("giris_istendi olayi yazildi", ol == 1, str(ol))
sina("siradan onay ayristirilmaz", giris.ayristir({"eylem": "YAYIN: x", "ayrinti": ""}) is None)

print("\n-- 3. web: giris yaptim -> kabin --")
g_once = ofis.tahta.gorev(n1)
sina("once: kabin kapali, alan bos", not g_once["tarayici_kabin"] and not g_once["tarayici_alani"])
giris.cevapla(ofis, kart[0]["id"], yapildi=True, not_="girdim")
g = ofis.tahta.gorev(n1)
sina("is PAYLASILAN KABINE tasindi", g["tarayici_kabin"] is True, str(g["tarayici_kabin"]))
sina("kaynak tarayici alanina eklendi", g["tarayici_alani"] == ["https://admin.ornek.com"],
     str(g["tarayici_alani"]))
sina("tiklama acik (riskli eylem yine kapida)", bool(g["tarayici_yazma"]))
sina("istek cevaplandi (bekleyen kalmadi)", not bekleyen(n1))
with db.baglanti() as c:
    o = c.execute("SELECT durum, cevap_notu FROM onay WHERE id=?", (kart[0]["id"],)).fetchone()
sina("onay 'onaylandi'", o["durum"] == "onaylandi", o["durum"])
sina("ajana giden not kabini ve patronun notunu tasir",
     "KABIN" in o["cevap_notu"] and "girdim" in o["cevap_notu"], o["cevap_notu"][:200])
sina("ayni kart ikinci kez cevaplanamaz",
     bool(hata_mi(giris.cevapla, ofis, kart[0]["id"], yapildi=True)))

print("\n-- 4. yapamam --")
n2 = is_ac("Red")
giris.iste(ofis, "isci", n2, tur="diger", hizmet="SMS onayi", neden="kod telefona gelir")
kid = bekleyen(n2)[0]["id"]
sina("gerekcesiz 'yapamam' reddedilir",
     "gerekce" in hata_mi(giris.cevapla, ofis, kid, yapildi=False).lower())
sina("...ve istek hala bekliyor", len(bekleyen(n2)) == 1)
hata_mi(giris.cevapla, ofis, kid, yapildi=False, not_="telefon yaninda degil")
with db.baglanti() as c:
    o = c.execute("SELECT durum, cevap_notu FROM onay WHERE id=?", (kid,)).fetchone()
sina("gerekceli 'yapamam' reddedildi, gerekce ajana", o["durum"] == "reddedildi"
     and "telefon" in o["cevap_notu"], dict(o).__repr__())
sina("reddedilen giris isi DEGISTIRMEDI", not ofis.tahta.gorev(n2)["tarayici_kabin"])

print("\n-- 5. baglayici: 'yaptim' OLCULUR --")
n3 = is_ac("Bag")
giris.iste(ofis, "isci", n3, tur="baglayici", hizmet="Shopify", neden="urunleri okumak")
bid = bekleyen(n3)[0]["id"]
_eski_durum, _eski_dogrula = baglayici.durum, baglayici.dogrula
olcum = {"bagli": False, "taze": 0}


def sahte_durum(*a, taze=False, **k):
    olcum["taze"] += 1 if taze else 0
    return {"Shopify": {"bagli": olcum["bagli"]}}


def sahte_dogrula(adlar, *, mevcut=None):
    if not olcum["bagli"]:
        raise baglayici.BaglayiciHatasi("'Shopify' yetki bekliyor")
    return ["Shopify"]


baglayici.durum, baglayici.dogrula = sahte_durum, sahte_dogrula
try:
    h = hata_mi(giris.cevapla, ofis, bid, yapildi=True)
    sina("bagli DEGILKEN 'yaptim' kabul edilmez", "BAGLI" in h, h)
    sina("...istek hala bekliyor, is degismedi",
         len(bekleyen(n3)) == 1 and not ofis.tahta.gorev(n3)["baglayicilar"])
    sina("olcum TAZE yapildi (bayat onbellek degil)", olcum["taze"] >= 1)
    olcum["bagli"] = True
    giris.cevapla(ofis, bid, yapildi=True)
    sina("baglaninca ise acildi", ofis.tahta.gorev(n3)["baglayicilar"] == ["Shopify"],
         str(ofis.tahta.gorev(n3)["baglayicilar"]))
    sina("istek cevaplandi", not bekleyen(n3))
finally:
    baglayici.durum, baglayici.dogrula = _eski_durum, _eski_dogrula

print("\n-- 6. kapanmis is --")
n4 = is_ac("Kapali")
giris.iste(ofis, "isci", n4, tur="web", hizmet="x", adres="https://x.com", neden="y")
ofis.tahta.iptal_et(n4, sebep="vazgecildi", iptal_eden="insan")
iid = [o for o in ofis.postane.bekleyen_onaylar() if o.get("gorev_no") == n4]
if iid:
    sina("iptal edilmis ise giris uygulanmaz",
         bool(hata_mi(giris.cevapla, ofis, iid[0]["id"], yapildi=True)))
else:
    sina("iptal edilmis ise giris uygulanmaz (bekleyen yok, uygulanmadi)",
         not ofis.tahta.gorev(n4)["tarayici_kabin"])
sina("iptal edilen is kabine tasinmadi", not ofis.tahta.gorev(n4)["tarayici_kabin"])
sina("iptal edilen isin giris karti kuyruktan KALKTI", not bekleyen(n4))
n6 = is_ac("Soru")
ofis.postane.soru_sor("isci", "insan", "hangi hesap?", gorev_no=n6)
ofis.tahta.iptal_et(n6, sebep="gerek kalmadi", iptal_eden="insan")
sina("iptal edilen isin SORUSU da kuyruktan kalkti",
     not [s for s in ofis.postane.bekleyen_sorular() if s.get("gorev_no") == n6])

print("\n-- 7. MCP araci --")
from ofis import mcp_sunucu as S   # noqa: E402
n5 = is_ac("Mcp")
os.environ.update(OFIS_DB=str(db.yol), OFIS_PROJE=ofis.proje_id,
                  OFIS_AJAN="isci", OFIS_GOREV=str(n5))
otur = S.Oturum()
araclar = {a["name"]: a for a in S.ARACLAR}
sina("giris_iste araci kayitli", "giris_iste" in araclar)
ozellik = set(araclar.get("giris_iste", {}).get("inputSchema", {}).get("properties", {}))
sina("arac SIFRE ALMAZ (sema)", not any(x in ozellik for x in
     ("sifre", "password", "parola", "kullanici", "username")), str(ozellik))
cevap = S.arac_giris_iste(otur, {"tur": "web", "hizmet": "Panel",
                                  "adres": "https://panel.ornek.com", "neden": "rapor",
                                  "sifre": "hunter2"})
sina("arac ajana DUR der", "DUR" in cevap, cevap[:120])
kb = bekleyen(n5)
sina("kart ortamdaki ajan+gorev adina acildi", len(kb) == 1 and kb[0]["isteyen"] == "isci")
sina("ajanin yolladigi 'sifre' deftere GIRMEDI", not kb or "hunter2" not in json.dumps(kb))
sina("hatali istek HATA doner, kart acmaz",
     S.arac_giris_iste(otur, {"hizmet": "", "neden": ""}).startswith("HATA"))

print("\n-- 8. kapi: sifre alanina yazma --")
b = riskli.degerlendir("browser_type", {"element": "Password", "target": "e3",
                                         "text": "hunter2"})
sina("sifre alanina yazma DURUR", b is not None and b["sinif"] == "kimlik", str(b))
sina("yazilan DEGER karta girmez", b is not None and "hunter2" not in json.dumps(b), str(b))
b = riskli.degerlendir("browser_type", {"element": "textbox", "target": "e3", "text": "gizli1"},
                       sayfa_metni="textbox Şifre")
sina("ajan 'textbox' dese de SAYFADAKI ad (Sifre) yakalanir", b is not None and b["sinif"] == "kimlik")
b = riskli.degerlendir("browser_fill_form", {"fields": [
    {"name": "E-posta", "type": "textbox", "value": "a@b.c"},
    {"name": "Doğrulama kodu", "type": "textbox", "value": "123456"}]})
sina("form icinde dogrulama kodu DURUR", b is not None and b["sinif"] == "kimlik")
sina("form degeri karta girmez", b is not None and "123456" not in json.dumps(b))
sina("arama kutusuna yazma SERBEST",
     riskli.degerlendir("browser_type", {"element": "Arama", "target": "e2", "text": "termos"}) is None)
sina("e-posta kutusuna yazma SERBEST",
     riskli.degerlendir("browser_type", {"element": "E-posta", "target": "e2", "text": "a@b"}) is None)
blok = riskli.brifing_blogu(True, serbest=True)
sina("brifing giris kuralini tasir", "giris_iste" in blok and "ISTEME" in blok)
sina("brifing .playwright-mcp'yi silme der (E80)", ".playwright-mcp" in blok)

print("\n-- 9. panel --")
from fastapi.testclient import TestClient   # noqa: E402
from ofis.panel import olustur              # noqa: E402
ist = TestClient(olustur(db.yol))
bk = ist.get("/api/bekleyenler").json()
gk = [o for o in bk.get("onaylar", []) if o.get("giris")]
sina("panel karti `giris` alaniyla gelir", len(gk) == 1, str(bk.get("onaylar"))[:200])
sina("kart insan talimatini tasir", bool(gk) and "kabin" in gk[0]["giris"]["talimat"])
yan = ist.post(f"/api/onay/{kb[0]['id']}", json={"onayla": False, "not_": "", "surdur": False})
sina("panelde gerekcesiz 'yapamam' 400", yan.status_code == 400, str(yan.status_code))
iyi = ist.post(f"/api/onay/{kb[0]['id']}",
               json={"onayla": True, "not_": "", "kapsam": "is", "surdur": False})
sina("panel 'giris yaptim' 200", iyi.status_code == 200, iyi.text[:200])
sina("siradan onay yolu ARKA KAPI degil: is kabine tasindi",
     ofis.tahta.gorev(n5)["tarayici_kabin"] is True)
with db.baglanti() as c:
    kap = c.execute("SELECT kapsam FROM onay WHERE id=?", (kb[0]["id"],)).fetchone()
sina("'bu is boyunca' giriste YOK sayilir (tek seferlik)",
     kap is None or (dict(kap).get("kapsam") or "eylem") == "eylem", str(dict(kap) if kap else ""))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
