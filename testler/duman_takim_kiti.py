# -*- coding: utf-8 -*-
"""TAKIM KITI: bitti tanimi + marka kiti (06.10.2026, Asama 4 / K15). Jeton yakmaz.

Sinanan: kit takimin isinde iscinin brifingine (K2) ve liderin kunyesine
(plan + inceleme) girer, OTEKI takima girmez; yasak kelime teslimde OLCULUR
(diskte degisen metin dosyasi + kanit; kelime siniri, Turkce I/İ); lider
retinde kit dayanak sayilir; panelden yazilir ve okunur.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, kit as KT  # noqa: E402
from ofis.db import simdi  # noqa: E402
from ofis.lider import ret_dayanagi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-takim-kiti-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Kit", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("MAGAZA", "MG")
KB = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "icerik", kanat_id=KA, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("mert", "lider", kanat_id=KB, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("can", "backend", kanat_id=KB, motor="sahte", klasor=str(d))

print("1. yazma / okuma")
sina("kitsiz takimin blogu BOS (brifing sismez)", KT.blok(db, KA) == [])
KT.yaz(db, ofis.proje_id, KA, bitti_tanimi="Mobilde de duzgun gorunur\n\nUrun fiyatlari KDV dahil yazilir",
       marka={"ses_tonu": "samimi, siz diye hitap", "renkler": "#1F6FEB lacivert",
              "yasak": "ucuz, Bedava,\nindirim, ucuz"})
k = KT.oku(db, KA)
sina("bitti tanimi satirlari (bos satir atildi)", k["bitti_tanimi"] == [
    "Mobilde de duzgun gorunur", "Urun fiyatlari KDV dahil yazilir"], str(k["bitti_tanimi"]))
sina("yasak liste ayrildi, tekrar atildi", sorted(k["yasak"]) == ["Bedava", "indirim", "ucuz"], str(k["yasak"]))
KT.yaz(db, ofis.proje_id, KA, marka={"logo": "marka/logo.png"})
k = KT.oku(db, KA)
sina("yalniz verilen alan degisir (oteki alanlar korunur)",
     k["logo"] == "marka/logo.png" and k["ses_tonu"].startswith("samimi") and len(k["bitti_tanimi"]) == 2)

print("\n2. brifing ve liderin kunyesi")
ga = ofis.tahta.gorev_ac("urun sayfasi", neden="n", ana_hedef="h", kabul_olcutu="sayfa acilir",
                         yazma_alani=["urun.html"], kanat_id=KA)
gb = ofis.tahta.gorev_ac("api", neden="n", ana_hedef="h", kabul_olcutu="testler gecer",
                         yazma_alani=["api.py"], kanat_id=KB)
ba = ofis.brifing.uret(ga["no"], "ece", diske_yaz=False)["metin"]
bb = ofis.brifing.uret(gb["no"], "can", diske_yaz=False)["metin"]
sina("takimin iscisi bitti tanimini goruyor", "TAKIMIN BITTI TANIMI" in ba and "KDV dahil" in ba)
sina("  marka kiti ve yasak kelimeler brifingde", "samimi" in ba and "YASAK KELIMELER" in ba and "Bedava" in ba)
sina("OTEKI takimin brifingine GIRMIYOR", "BITTI TANIMI" not in bb and "Bedava" not in bb)
ka, kb = ofis.brifing.kunye_ozeti(KA), ofis.brifing.kunye_ozeti(KB)
sina("liderin kunyesinde (plan + inceleme) kit var", "KDV dahil" in ka and "YASAK KELIMELER" in ka)
sina("oteki takimin liderinde yok", "KDV dahil" not in kb)

print("\n3. yasak kelime OLCULUR")
ofis.tahta.sahiplen(ga["no"], "ece", ga["revizyon"])
(d / "urun.html").write_text("<h1>Yeni sezon</h1><p>Bu ay İNDİRİM var, UCUZ fiyat!</p>", encoding="utf-8")
(d / "temiz.html").write_text("<p>ucuzluk degil kalite</p>", encoding="utf-8")
for y in ("urun.html", "temiz.html"):
    with db.baglanti() as c:
        c.execute("INSERT INTO degisim (id, proje_id, gorev_id, ajan_ad, yol, hal, olusturuldu) "
                  "VALUES (?, ?, ?, 'ece', ?, 'eklendi', ?)", (uuid.uuid4().hex, ofis.proje_id, ga["id"], y, simdi()))
ofis.tahta.kanit_ekle(ga["no"], "terminal", "ozet", "Kampanya metni: bedava kargo", "ece")
bul = KT.yasak_tara(db, KA, kok=str(d), yollar=["urun.html", "temiz.html"],
                    kanitlar=["Kampanya metni: bedava kargo"])
yerler = {(b["kelime"], b["yer"]) for b in bul}
sina("BUYUK harfli 'UCUZ' ve Turkce 'İNDİRİM' bulundu",
     ("ucuz", "urun.html") in yerler and ("indirim", "urun.html") in yerler, str(yerler))
sina("kelime SINIRI: 'ucuzluk' yasak sayilmadi", not any(y == "temiz.html" for _, y in yerler))
sina("kanittaki 'bedava' bulundu", ("Bedava", "kanit 1") in yerler, str(yerler))
im = ofis.lider.inceleme_metni(ga["no"])
sina("liderin incelemesinde 'YASAK KELIME BULUNDU' (ofisin olcumu)",
     "YASAK KELIME BULUNDU" in im and "urun.html" in im and "KAPATILMAZ" in im, im[-600:])
ofis.tahta.sahiplen(gb["no"], "can", gb["revizyon"])
(d / "api.py").write_text("# ucuz bedava\n", encoding="utf-8")
with db.baglanti() as c:
    c.execute("INSERT INTO degisim (id, proje_id, gorev_id, ajan_ad, yol, hal, olusturuldu) "
              "VALUES (?, ?, ?, 'can', 'api.py', 'eklendi', ?)", (uuid.uuid4().hex, ofis.proje_id, gb["id"], simdi()))
ofis.tahta.kanit_ekle(gb["no"], "terminal", "pytest", "ok", "can")
sina("kitsiz takimin incelemesinde tarama YOK", "YASAK KELIME" not in ofis.lider.inceleme_metni(gb["no"]))

print("\n4. ret dayanagi")
olc = ofis.lider._olcut_metinleri(ofis.tahta.gorev(ga["no"]))
sina("'OLCUT: marka kiti' gecerli dayanak", ret_dayanagi("KARAR: geri\nOLCUT: marka kiti", olc) != "")
sina("bitti taniminin satiri gecerli dayanak",
     ret_dayanagi('KARAR: geri\nOLCUT: "Urun fiyatlari KDV dahil yazilir"', olc) != "")
sina("uydurma alinti yine dayanak DEGIL", ret_dayanagi("KARAR: geri\nOLCUT: renkler daha canli olmali", olc) == "")

print("\n5. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
r = ist.post(f"/api/kanat/{KB}/duzenle", json={"bitti_tanimi": "Testler gecer", "marka": {"yasak": "hack"}})
sina("panelden kit yazildi", r.status_code == 200 and KT.oku(db, KB)["bitti_tanimi"] == ["Testler gecer"]
     and KT.oku(db, KB)["yasak"] == ["hack"], r.text[:200])
org = ist.get("/api/organizasyon").json()
kart = next(x for x in org["kanatlar"] if x["id"] == KA)
sina("organizasyon kiti veriyor", kart.get("kit", {}).get("logo") == "marka/logo.png")
r = ist.post(f"/api/kanat/{KA}/duzenle", json={"ad": "MAGAZA"})
sina("kit verilmeyen duzenleme kite dokunmuyor", len(KT.oku(db, KA)["bitti_tanimi"]) == 2)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
