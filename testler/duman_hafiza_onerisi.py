# -*- coding: utf-8 -*-
"""SOHBETTEN HAFIZA ONERISI (06.10.2026, Asama 2 / E31). Jeton yakmaz.

Patron sohbette kalici bir bilgi soyler ("iade suresi 30 gun"); bu bilgi
hicbir yere yazilmiyordu. Simdi lider triyajda `bilgi` onerir, ofis alintiyi
patronun mesajina karsi denetler, "Senden bekleniyor"a kart duser, YAZAN
patrondur.

Sinanan: triyaj istemi alani tarif ediyor · gecerli oneri kart olur ·
uydurma alinti (mesajda yok) kart OLMAZ ve uyari yazilir · Turkce harf
farki alintiyi bozmaz · hafizada AYNEN olan oneri kart olmaz · ayni oneri
iki kez kart olmaz · 3 oneri tavani · "Yaz" -> bilgi INSANIN bilgisi ·
"Yazma" -> hafizaya girmez · iki kez cevaplanamaz · ajan cevaplayamaz ·
panel uclari.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani  # noqa: E402
from ofis.bellek import BellekHatasi  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


kok = Path(tempfile.mkdtemp(prefix="ofis-hafiza-onerisi-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Oneri", amac="a", basari_olcutu="b", kok_klasor=str(kok))
kn = ofis.kanat_ac("GENEL", "GE")
ofis.kadro.ise_al("lale", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(kok))
kutu = {"cevap": ""}
sohbet = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(cevap=kutu["cevap"]))


def konus(mesaj, bilgi):
    kutu["cevap"] = "```json\n" + json.dumps(
        {"karar": "cevap", "gerekce": "bilgi verdi", "cevap": "Tamam, not ettim.", "bilgi": bilgi},
        ensure_ascii=False) + "\n```"
    return list(sohbet.konus(mesaj))


def uyarilar():
    with db.baglanti() as c:
        return [r[0] for r in c.execute("SELECT govde FROM olay WHERE tur='uyari' ORDER BY rowid")]


print("== sohbetten hafiza onerisi ==\n")
print("1. triyaj istemi")
ist = sohbet.triyaj_metni("deneme")
sina("istem `bilgi` alanini ve alinti kuralini tarif ediyor",
     '"bilgi"' in ist and "KELIMESI KELIMESINE" in ist and "en fazla 3" in ist)

print("\n2. oneriler")
konus("Bu arada iade süremiz 30 gün, kargo da Yurtiçi ile gidiyor.", [
    {"konu": "iade süresi", "icerik": "30 gün", "alinti": "iade süremiz 30 gün"},
    {"konu": "kargo firmasi", "icerik": "Yurtici Kargo", "alinti": "kargo da yurtici ile gidiyor"},
    {"konu": "indirim orani", "icerik": "%20", "alinti": "her ay yuzde 20 indirim yapariz"},
])
b = ofis.bellek.bekleyen_hafiza_onerileri()
konular = sorted(o["konu"] for o in b)
sina("gecerli iki oneri kart oldu (Turkce harf farki alintiyi bozmadi)",
     konular == ["iade süresi", "kargo firmasi"], str(konular))
sina("uydurma alinti kart OLMADI ve uyari yazildi",
     "indirim orani" not in konular and any("indirim orani" in u for u in uyarilar()), str(uyarilar()))
sina("cevap yine patrona gitti (oneri sohbeti durdurmaz)",
     any(o["tur"] == "cevap" for o in konus("iade süremiz 30 gün", [
         {"konu": "iade süresi", "icerik": "30 gün", "alinti": "iade süremiz 30 gün"}])))
sina("ayni oneri iki kez kart olmadi", len(ofis.bellek.bekleyen_hafiza_onerileri()) == 2)
konus("a b c d e: bir iki uc dort bes alti", [
    {"konu": f"k{i}", "icerik": f"d{i}", "alinti": "bir iki uc dort"} for i in range(6)])
sina("tek mesajdan en fazla 3 oneri", len(ofis.bellek.bekleyen_hafiza_onerileri()) == 5,
     str(len(ofis.bellek.bekleyen_hafiza_onerileri())))
ofis.bellek.bilgi_ekle("magaza adi", "Semu Parfum", yazan="insan")
konus("Magaza adi Semu Parfum, unutma.", [
    {"konu": "Magaza adi", "icerik": "Semu Parfum", "alinti": "magaza adi semu parfum"}])
sina("hafizada AYNEN olan oneri kart olmadi",
     not any(o["konu"].lower() == "magaza adi" for o in ofis.bellek.bekleyen_hafiza_onerileri()))

print("\n3. patronun karari")
iade = next(o for o in ofis.bellek.bekleyen_hafiza_onerileri() if o["konu"] == "iade süresi")
kargo = next(o for o in ofis.bellek.bekleyen_hafiza_onerileri() if o["konu"] == "kargo firmasi")
try:
    ofis.bellek.hafiza_onerisi_cevapla(iade["id"], yaz=True, kim="lale")
    sina("ajan/lider oneriyi cevaplayamaz", False)
except BellekHatasi:
    sina("ajan/lider oneriyi cevaplayamaz", True)
r = ofis.bellek.hafiza_onerisi_cevapla(iade["id"], yaz=True)
olgu = ofis.bellek.gecerli_olgular(["iade süresi"])
sina("'Yaz' -> bilgi hafizada, kaynagi INSAN", r["durum"] == "yazildi" and olgu
     and olgu[0]["icerik"] == "30 gün" and olgu[0]["kaynak"] == "insan", str(olgu))
ofis.bellek.hafiza_onerisi_cevapla(kargo["id"], yaz=False)
sina("'Yazma' -> hafizaya girmedi", not ofis.bellek.gecerli_olgular(["kargo firmasi"]))
try:
    ofis.bellek.hafiza_onerisi_cevapla(kargo["id"], yaz=True)
    sina("iki kez cevaplanamaz", False)
except BellekHatasi:
    sina("iki kez cevaplanamaz", True)
try:
    ofis.bellek.bilgi_ekle("iade süresi", "14 gün", yazan="lale")
    sina("patronun yazdirdigi bilgiyi ajan devremez", False)
except BellekHatasi:
    sina("patronun yazdirdigi bilgiyi ajan devremez", True)

print("\n4. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(kok / "o.sqlite3"))
j = ist.get("/api/oneriler").json()
sina("oneriler ucu hafiza kartlarini veriyor", len(j.get("hafiza", [])) == 3, str(len(j.get("hafiza", []))))
h = j["hafiza"][0]
r = ist.post(f"/api/hafiza_onerisi/{h['id']}", json={"yaz": True})
sina("panelden 'Yaz' calisiyor", r.status_code == 200 and r.json()["durum"] == "yazildi", r.text[:120])
r = ist.post(f"/api/hafiza_onerisi/{h['id']}", json={"yaz": True})
sina("cevaplanmis oneri 400", r.status_code == 400)
r = ist.post("/api/hafiza_onerisi/yok-boyle", json={"yaz": False})
sina("olmayan oneri 400", r.status_code == 400)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
