# -*- coding: utf-8 -*-
"""AYNI BILGININ IKI KAYDINI BIRLESTIRME (06.10.2026, Asama 2 / E32). Jeton yakmaz.

Olculdu (24.09.2026): isci `servis portu`, lider ayni degeri `Servis port
numarasi` diye yazdi -- ayni olgu iki konuya bolundu; biri degisince oteki
eski degeriyle brifinge girmeye devam ederdi.

Sinanan: aday OLCULUR (ortak konu kelimesi + ortak deger; yalniz biri
yetmez) · birlestirme yalniz insan · takmanin bilgisi kapanir ama SILINMEZ ·
asilin icerigi kalir · takma ada sonradan yazilan bilgi ASILA gider ·
`[[takma]]` bagi asili brifinge ceker · zincir olusmaz · panel uclari.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


kok = Path(tempfile.mkdtemp(prefix="ofis-birlestir-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Birlestir", amac="a", basari_olcutu="b", kok_klasor=str(kok))
B = ofis.bellek
B.bilgi_ekle("servis portu", "8080 (ayar.toml)", yazan="cinar", gorev_no=1)
B.bilgi_ekle("Servis port numarasi", "8080", yazan="demir", gorev_no=1)
B.bilgi_ekle("iade suresi", "30 gun", yazan="insan")
B.bilgi_ekle("iade adresi", "Istanbul depo", yazan="insan")
B.bilgi_ekle("kargo firmasi", "Yurtici", yazan="insan")
B.bilgi_ekle("kargo ucreti", "Yurtici ile 49 TL", yazan="insan")
B.bilgi_ekle("dagitim", "sunucu [[Servis port numarasi]] uzerinden", yazan="insan")

print("== birlestirme ==\n")
print("1. adaylar")
ad = B.birlesim_adaylari()
ciftler = {frozenset((x["a"], x["b"])) for x in ad}
sina("servis portu / Servis port numarasi ADAY (ortak kelime + ortak deger 8080)",
     frozenset(("servis portu", "Servis port numarasi")) in ciftler, str(ad))
sina("iade suresi / iade adresi aday DEGIL (ortak deger yok)",
     frozenset(("iade suresi", "iade adresi")) not in ciftler)
sina("kargo firmasi / kargo ucreti aday (ortak deger 'Yurtici') -- karar insanin",
     frozenset(("kargo firmasi", "kargo ucreti")) in ciftler)

print("\n2. birlestir")
try:
    B.birlestir("servis portu", "Servis port numarasi", kim="demir")
    sina("ajan/lider birlestiremez", False)
except BellekHatasi:
    sina("ajan/lider birlestiremez", True)
r = B.birlestir("servis portu", "Servis port numarasi")
gec = {o["konu"]: o["icerik"] for o in B.gecerli_olgular()}
sina("takmanin bilgisi kapandi, asilin icerigi kaldi",
     "Servis port numarasi" not in gec and gec.get("servis portu") == "8080 (ayar.toml)", str(gec))
sina("takmanin bilgisi SILINMEDI (gecmiste)",
     any(x["icerik"] == "8080" for x in B.konu_gecmisi("Servis port numarasi")))
sina("birlesmis cift artik aday degil",
     frozenset(("servis portu", "Servis port numarasi")) not in
     {frozenset((x["a"], x["b"])) for x in B.birlesim_adaylari()})

print("\n3. takma ad yonlendirmesi")
y = B.bilgi_ekle("servis port numarasi", "9090 (ayar.toml degisti)", yazan="cinar", gorev_no=2)
gec = {o["konu"]: o["icerik"] for o in B.gecerli_olgular()}
sina("takma ada yazilan bilgi ASIL konuya gitti",
     y["konu"] == "servis portu" and gec.get("servis portu", "").startswith("9090")
     and "Servis port numarasi" not in gec and "servis port numarasi" not in gec, str(gec))
for i in range(45):          # secim esigini asmak icin ilgisiz bilgiler
    B.bilgi_ekle(f"ilgisiz konu {i}", f"deger {i}", yazan="insan")
sec = B.ilgili_olgular("dagitim nasil yapilir")
sina("`[[takma]]` bagi asil konuyu brifinge cekti",
     any(o["konu"] == "servis portu" for o in sec["secilen"]),
     str([o["konu"] for o in sec["secilen"]][:8]))

print("\n4. zincir olusmaz")
B.bilgi_ekle("uygulama portu", "9090", yazan="insan")
B.birlestir("uygulama portu", "servis portu")
h = B.takma_haritasi()
sina("eski takma da yeni asile yonlendi (zincir yok)",
     h.get("servis port numarasi") == "uygulama portu" and h.get("servis portu") == "uygulama portu", str(h))
try:
    B.birlestir("uygulama portu", "servis portu")
    sina("ayni konu kendisiyle birlestirilemez", False)
except BellekHatasi:
    sina("ayni konu kendisiyle birlestirilemez", True)

print("\n5. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(kok / "o.sqlite3"))
j = ist.get("/api/hafiza").json()
sina("hafiza ucu adaylari veriyor", any({x["a"], x["b"]} == {"kargo firmasi", "kargo ucreti"}
                                       for x in j.get("birlesim", [])), str(j.get("birlesim"))[:200])
r = ist.post("/api/hafiza/birlestir", json={"asil": "kargo firmasi", "takma": "kargo ucreti"})
sina("panelden birlestirme calisiyor", r.status_code == 200, r.text[:120])
r = ist.post("/api/hafiza/birlestir", json={"asil": "yok", "takma": "kargo firmasi"})
sina("gecersiz birlestirme 400", r.status_code == 400)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
