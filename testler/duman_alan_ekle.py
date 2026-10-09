# -*- coding: utf-8 -*-
"""YAZMA ALANI GENISLETME (09.10.2026, F1 canli #6): ajan `web/panel.js`
gerektigini lidere sordu; lider "alani ben genisletemem" dedi -- yol yoktu,
soru patrona dustu. Simdi isin LIDERI danisma cevabina `ALAN_EKLE:` yazar,
ofis olcer (takim koku, baska isin kilidi) ve sonucu cevaba ekler."""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani  # noqa: E402
from ofis.danisma import ALAN_EKLE, Danisma  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.tahta import KilitCakismasi, TahtaHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


K = Path(tempfile.mkdtemp(prefix="ofis-alan-ekle-"))
for d in ("ofis", "web", "testler"):
    (K / d).mkdir()
ofis = Ofis.proje_ac(Veritabani(K / "o.sqlite3"), "Alan", amac="a", basari_olcutu="b", kok_klasor=str(K))
kn = ofis.kanat_ac("GEL", "GL")
ofis.kadro.ise_al("ada", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(K))
ofis.kadro.ise_al("asli", "backend", kanat_id=kn, motor="sahte", klasor=str(K))
ofis.kadro.ise_al("baris", "kalite", kanat_id=kn, motor="sahte", klasor=str(K))

g = ofis.tahta.gorev_ac("kart modeli", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn,
                        yazma_alani=["ofis/"])
g = ofis.tahta.sahiplen(g["no"], "asli", g["revizyon"])
g2 = ofis.tahta.gorev_ac("baska is", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn,
                         yazma_alani=["testler/"])
ofis.tahta.sahiplen(g2["no"], "baris", g2["revizyon"])

print("1. tahta.alan_ekle")
e = ofis.tahta.alan_ekle(g["no"], ["web/panel.js"], ekleyen="ada")
g = ofis.tahta.gorev(g["no"])
with ofis.db.baglanti() as c:
    kil = [r[0] for r in c.execute("SELECT yol_oneki FROM yazma_kilidi WHERE gorev_id = ?", (g["id"],))]
sina("yol eklendi, KILIDI de alindi (Yasa 1)", e == ["web/panel.js"] and "web/panel.js" in g["yazma_alani"]
     and "web/panel.js" in kil, str((e, g["yazma_alani"], kil)))
sina("  ayni yol ikinci kez eklenmez", ofis.tahta.alan_ekle(g["no"], ["web/panel.js"], ekleyen="ada") == [])
try:
    ofis.tahta.alan_ekle(g["no"], ["testler/duman_x.py"], ekleyen="ada")
    sina("  baska isin kilidindeki yol RET", False)
except KilitCakismasi:
    sina("  baska isin kilidindeki yol RET", "testler/duman_x.py" not in ofis.tahta.gorev(g["no"])["yazma_alani"])
try:
    ofis.tahta.alan_ekle(g["no"], ["."], ekleyen="ada")
    sina("  kokun tamami eklenmez (ayni kapi)", False)
except TahtaHatasi:
    sina("  kokun tamami eklenmez (ayni kapi)", True)

print("\n2. danisma: lider ALAN_EKLE yazar, ofis uygular ve sonucu cevaba ekler")
CEVAP = {"metin": ""}
dan = Danisma(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(cevap=CEVAP["metin"]))
m = ofis.postane.soru_sor("asli", "ada", "web/kart.css de lazim, alan genisler mi?", gorev_no=g["no"])
m = next(x for x in ofis.postane.bekleyen_sorular() if x["id"] == m["id"])
sina("lidere giden metinde ALAN_EKLE talimati var", ALAN_EKLE in dan.soru_metni(m))
CEVAP["metin"] = f"Evet, gerekli.\n{ALAN_EKLE} web/kart.css"
r = dan.cevapla(m)
sina("  alan eklendi ve ajan bunu cevapta goruyor",
     "web/kart.css" in ofis.tahta.gorev(g["no"])["yazma_alani"] and "yazma alanina eklendi: web/kart.css" in r["cevap"],
     r["cevap"])
m2 = ofis.postane.soru_sor("asli", "ada", "testler/ de lazim", gorev_no=g["no"])
m2 = next(x for x in ofis.postane.bekleyen_sorular() if x["id"] == m2["id"])
CEVAP["metin"] = f"Tamam.\n{ALAN_EKLE} testler/duman_y.py"
r = dan.cevapla(m2)
sina("  kilit cakisinca EKLENMEZ ve sebep cevaba yazilir (uydurma 'ekledim' yok)",
     "GENISLETILMEDI" in r["cevap"] and "testler/duman_y.py" not in ofis.tahta.gorev(g["no"])["yazma_alani"], r["cevap"])

print("\n3. yetki: yalniz isin LIDERI, isin SAHIBINE")
m3 = ofis.postane.soru_sor("asli", "baris", "alan genisler mi?", gorev_no=g["no"])
m3 = next(x for x in ofis.postane.bekleyen_sorular() if x["id"] == m3["id"])
sina("lider olmayana giden metinde talimat YOK", ALAN_EKLE not in dan.soru_metni(m3))
CEVAP["metin"] = f"Bence ekle.\n{ALAN_EKLE} web/baska.js"
r = dan.cevapla(m3)
sina("  lider olmayanin ALAN_EKLE satiri UYGULANMAZ, sebep yazilir",
     "web/baska.js" not in ofis.tahta.gorev(g["no"])["yazma_alani"] and "uygulanmadi" in r["cevap"], r["cevap"])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
