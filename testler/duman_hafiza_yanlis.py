# -*- coding: utf-8 -*-
"""HAFIZA: Yanlis / Duzelt, arama, geri bag duman testi (03.10.2026).

Rakip videosunda (IgkwSECTjfI) hafiza notunda "Yanlis / Duzelt" ve "Bagli
hafizalar 17" goruldu; bizde yanlis bilgiyi kapatmanin yolu yoktu (yanlis
bilgi her brifinge girip ajanlari yaniltir). Sinanan:
  1. bilgi YANLIS diye kapatilir: sebep zorunlu, yalniz insan, brifinge girmez,
     gecmiste 'yanlis' etiketiyle durur
  2. ajan AYNI yanlisi geri yazamaz; farkli icerik yazabilir; insan yazabilir
  3. ders YANLIS diye kaldirilir: K1'e girmez, kural adayi olmaz, geri gelmez
  4. arama: bilgi/ders/kural/karar, Turkce harf farki yok, butun kelimeler
  5. geri bag: bu bilgiye baglananlar
  6. panel uclari ve dugmeler
Jeton yakmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- ILK

import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import Ofis, Veritabani  # noqa: E402
from ofis.bellek import BellekHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def hata(cagri) -> str:
    try:
        cagri()
        return ""
    except Exception as exc:  # noqa: BLE001
        return str(exc)


print("== hafiza yanlis/ara/geri bag ==\n")
_d = Path(tempfile.mkdtemp(prefix="ofis-hfy-"))
db = Veritabani(_d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Hafiza", amac="a", basari_olcutu="b", kok_klasor=str(_d))
kn = ofis.kanat_ac("ANA", "AN")
ofis.kadro.ise_al("demir", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(_d))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(_d))
bel = ofis.bellek
bel.bilgi_ekle("servis portu", "8123 (ayar.txt)", yazan="cinar")
bel.bilgi_ekle("dağıtım", "Önce [[servis portu]] açılır, sonra yayın.", yazan="demir")
bel.bilgi_ekle("iade süresi", "14 gün", yazan="insan")
g = ofis.tahta.gorev_ac("port ayarla", neden="n", ana_hedef="servis portu ayari", kabul_olcutu="k",
                        kanat_id=kn, govde="servis portu nedir")

print("1. bilgi yanlis")
sina("sebepsiz kapatilamaz", "Sebep" in hata(lambda: bel.olgu_yanlis("servis portu", " ")))
sina("ajan kapatamaz", "insan" in hata(lambda: bel.olgu_yanlis("servis portu", "x", kim="cinar")))
sina("olmayan konu kapatilamaz", "yok" in hata(lambda: bel.olgu_yanlis("olmayan", "x")))
_once = ofis.brifing.k2_kunye(g["no"])
sina("(sahne) bilgi brifingde", "8123" in _once)
sina("insan kapatir (konu harf farkiyla bulunur)",
     not hata(lambda: bel.olgu_yanlis("Servis Portu", "port 9000'e tasindi")))
sina("kapatilan bilgi gecerli listede YOK", not bel.gecerli_olgular(["servis portu"]))
sina("kapatilan bilgi brifinge GIRMIYOR", "8123" not in ofis.brifing.k2_kunye(g["no"]))
with db.baglanti() as c:
    r = c.execute("SELECT yanlis FROM olgu WHERE konu='servis portu'").fetchone()
    tur = {x[0] for x in c.execute("SELECT tur FROM olay")}
sina("gecmiste sebebiyle duruyor (silinmedi)", r and r[0] == "port 9000'e tasindi")
sina("olay yazildi", "olgu_yanlis" in tur)

print("\n2. geri yazma")
sina("ajan AYNI yanlisi geri yazamaz", "YANLIS" in hata(
    lambda: bel.bilgi_ekle("servis portu", "8123  (ayar.txt)", yazan="cinar")))
sina("ajan FARKLI (dogru) degeri yazabilir", not hata(
    lambda: bel.bilgi_ekle("servis portu", "9000 (yeni ayar.txt)", yazan="cinar")))
bel.olgu_yanlis("servis portu", "deneme")
sina("insan eski degeri yazabilir (yetki insanda)", not hata(
    lambda: bel.bilgi_ekle("servis portu", "8123 (ayar.txt)", yazan="insan")))

print("\n3. ders yanlis")
d1 = ofis.kadro.ders_yaz("cinar", "commit oncesi test kosmayi unutma")
for _ in range(3):
    ofis.kadro.ders_yaz("cinar", "commit oncesi test kosmayi unutma")
sina("(sahne) ders K1'de ve kural adayi", "commit oncesi" in ofis.brifing.k1_anayasa("cinar")
     and any(x["id"] == d1["id"] for x in bel.kural_adaylari()))
sina("sebepsiz kaldirilamaz", "Sebep" in hata(lambda: ofis.kadro.ders_yanlis(d1["id"], "")))
ofis.kadro.ders_yanlis(d1["id"], "zaten CI kosuyor")
sina("kaldirilan ders K1'e GIRMIYOR", "commit oncesi" not in ofis.brifing.k1_anayasa("cinar"))
sina("kural adayi OLMAKTAN cikti", not any(x["id"] == d1["id"] for x in bel.kural_adaylari()))
r = ofis.kadro.ders_yaz("cinar", "commit oncesi test kosmayi unutma")
sina("lider yeniden yazsa da GERI GELMEZ", r.get("reddedildi") and not ofis.kadro.dersler("cinar"))

print("\n4. arama")
bel.karar_yaz("SQLite kullan", "tek dosya, kurulum yok", "demir")
sina("Turkce harf farki yok (dagitim)", any(x["baslik"] == "dağıtım" for x in bel.ara("dagitim")))
sina("butun kelimeler gecmeli", not bel.ara("dagitim olmayankelime"))
s = bel.ara("servis portu")
sina("gecerli ve eski surumler, gecerli once", s and s[0]["durum"] == "gecerli"
     and any(x["durum"] == "yanlis" for x in s), str([(x["durum"], x["metin"]) for x in s]))
sina("karar da aranir", any(x["tur"] == "karar" for x in bel.ara("sqlite")))
sina("kaldirilan ders 'yanlis' durumuyla bulunur", any(x["tur"] == "ders" and x["durum"] == "yanlis"
                                                     for x in bel.ara("commit")))
sina("bos sorgu bos sonuc", bel.ara("  ") == [])

print("\n5. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis import panel  # noqa: E402
cl = TestClient(panel.olustur(_d / "o.sqlite3", "Hafiza"))
h = cl.get("/api/hafiza").json()
sp = next(o for o in h["gecerli"] if o["konu"] == "servis portu")
sina("geri bag: 'servis portu'na 'dağıtım' bagli", sp.get("geri") == ["dağıtım"], str(sp.get("geri")))
sina("eski listede yanlis sebebi var", any(o.get("yanlis") for o in h["eski"]))
sina("kaldirilan ders panel listesinde YOK", not any("commit" in x["ders"] for x in h["dersler"]))
r = cl.get("/api/hafiza/ara", params={"q": "iade"})
sina("GET /api/hafiza/ara", r.status_code == 200 and r.json()["sonuc"][0]["baslik"] == "iade süresi")
r = cl.post("/api/hafiza/yanlis", json={"konu": "iade süresi", "sebep": ""})
sina("sebepsiz yanlis 400", r.status_code == 400)
r = cl.post("/api/hafiza/yanlis", json={"konu": "iade süresi", "sebep": "30 gune cikti"})
sina("panelden yanlis", r.status_code == 200 and not bel.gecerli_olgular(["iade süresi"]))
JS = (KOK / "web" / "panel.js").read_text(encoding="utf-8")
sina("dugmeler: ara, duzelt, yanlis (bilgi + ders), geri bag", all(x in JS for x in (
    '"hafızada ara…"', '"düzelt"', '"/api/hafiza/yanlis", { konu', '"/api/hafiza/yanlis", { ders_id',
    "bağlı`")))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
