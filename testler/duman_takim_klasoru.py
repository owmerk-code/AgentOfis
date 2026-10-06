# -*- coding: utf-8 -*-
"""TAKIM KLASORU (06.10.2026, Asama 4 / E40). Jeton yakmaz.

Patron karari: "her takim ayri" -- her takimin kendi klasoru olur
(gercek ofiste `Masaustu\\<takim>`). Sinanan:
  - isin koku isin TAKIMINA gore cozulur (tahta, Ofis, brifing, ekler, konsol);
  - farkli koklerdeki ayni adli dosya iki ayri dosyadir -> kilit cakismaz;
    ayni kokteki iki is yine cakisir (Yasa 1 delinmez);
  - takimin klasoru calisan is varken degismez; ofisin icine ve goreli yola
    acilmaz; yalitilmis ajanin kendi klasoruna dokunulmaz;
  - yeni takim baskasinin kokunu almaz (ad cakismasi -> `-2`);
  - panel: takim kurulurken klasor acilir, organizasyon gosterir, duzenle degistirir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, ekler as E  # noqa: E402
from ofis.konsol import _ofis_kokunde_mi  # noqa: E402
from ofis.tahta import TahtaHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def ayni(a, b) -> bool:
    return str(Path(a).resolve()).lower() == str(Path(b).resolve()).lower()


d = Path(tempfile.mkdtemp(prefix="ofis-takim-klasoru-"))
kok = d / "proje"
kok.mkdir()
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Klasor", amac="a", basari_olcutu="b", kok_klasor=str(kok))
KM = ofis.kanat_ac("MAGAZA", "MG")
KY = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("lale", "lider", kanat_id=KM, lider_mi=True, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("ece", "icerik", kanat_id=KM, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("yalniz", "icerik", kanat_id=KM, motor="sahte", klasor=str(d / "yalniz"))
ofis.kadro.ise_al("mert", "lider", kanat_id=KY, lider_mi=True, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("can", "backend", kanat_id=KY, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("cem", "backend", kanat_id=KY, motor="sahte", klasor=str(kok))

print("1. kok cozumu")
sina("klasoru olmayan takim projenin kokunde", ayni(ofis.kok_klasoru(KM), kok))
mag = d / "MagazaKok"
r = ofis.takim_klasoru_ayarla(KM, str(mag))
sina("takim klasoru ayarlandi ve diskte acildi", mag.is_dir() and ayni(r["klasor"], mag))
sina("Ofis.kok_klasoru takimin kokunu veriyor", ayni(ofis.kok_klasoru(KM), mag))
sina("tahta.kok_klasor ayni kurali kullaniyor", ayni(ofis.tahta.kok_klasor(KM), mag))
sina("oteki takim projenin kokunde kaldi", ayni(ofis.kok_klasoru(KY), kok))
sina("takimin kokunu kullanan ajanlar yeni koke gecti",
     ayni(ofis.kadro.ajan("ece")["klasor"], mag) and ayni(ofis.kadro.ajan("lale")["klasor"], mag))
sina("YALITILMIS ajanin kendi klasoruna dokunulmadi",
     ayni(ofis.kadro.ajan("yalniz")["klasor"], d / "yalniz"))
sina("kokler listesi proje + takim", any(ayni(k, mag) for k in ofis.kokler())
     and any(ayni(k, kok) for k in ofis.kokler()))

print("\n2. isler ve kilitler")
(mag / "index.html").write_text("m", encoding="utf-8")
(kok / "index.html").write_text("y", encoding="utf-8")
gm = ofis.tahta.gorev_ac("magaza sayfasi", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["index.html"], kanat_id=KM)
gy = ofis.tahta.gorev_ac("yazilim sayfasi", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["index.html"], kanat_id=KY)
sina("isin koku isin takimina gore",
     ayni(ofis.tahta.gorev_koku(gm), mag) and ayni(ofis.isin_koku(gm["id"]), mag)
     and ayni(ofis.isin_koku(gy), kok))
ofis.tahta.sahiplen(gm["no"], "ece", gm["revizyon"])
try:
    ofis.tahta.sahiplen(gy["no"], "can", gy["revizyon"])
    ok = True
except TahtaHatasi as exc:
    ok, _h = False, str(exc)
sina("FARKLI koklerde ayni adli dosya: kilit CAKISMIYOR", ok)
gy2 = ofis.tahta.gorev_ac("yazilim ikinci", neden="n", ana_hedef="h", kabul_olcutu="k",
                          yazma_alani=["index.html"], kanat_id=KY)
try:
    ofis.tahta.sahiplen(gy2["no"], "cem", gy2["revizyon"])
    cakisti = False
except TahtaHatasi:
    cakisti = True
sina("AYNI kokteki iki is yine CAKISIYOR (Yasa 1)", cakisti)
sina("cakisan_kilitler koke gore suzuyor",
     [c["ajan_ad"] for c in ofis.tahta.cakisan_kilitler(["index.html"], kok=str(mag))] == ["ece"]
     and [c["ajan_ad"] for c in ofis.tahta.cakisan_kilitler(["index.html"], kok=str(kok))] == ["can"])
def _red(alan, kanat):
    try:
        ofis.tahta.gorev_ac("kok adi", neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=[alan], kanat_id=kanat)
        return ""
    except TahtaHatasi as exc:
        return str(exc)
sina("yazma alani TAKIMIN kokune gore dogrulaniyor (takim kokunun adi yola eklenmis -> ret)",
     "KOKUN KENDI ADI" in _red("MagazaKok/index.html", KM)
     and "KOKUN KENDI ADI" in _red("proje/index.html", KY)
     and "KOKUN KENDI ADI" not in _red("proje/index.html", KM))
(mag / "src").mkdir()
try:
    ofis.tahta.gorev_ac("takim kokunde var", neden="n", ana_hedef="h", kabul_olcutu="k",
                        yazma_alani=["src/a.py"], kanat_id=KM)
    kabul = True
except TahtaHatasi:
    kabul = False
sina("takimin kokunde VAR olan agac kabul (projenin kokunde yok)", kabul and not (kok / "src").exists())
alan = ofis.brifing._alan_satiri("index.html", ofis.tahta.gorev_koku(gm))
sina("brifing alan turunu takimin kokunde olcuyor", "DOSYA" in alan, alan)

print("\n3. klasor degistirme kapilari")
try:
    ofis.takim_klasoru_ayarla(KM, str(d / "baska"))
    kapi = False
except ValueError as exc:
    kapi = "calisan" in str(exc).lower()
sina("calisan isi olan takimin klasoru DEGISMEZ", kapi and not (d / "baska").exists())
try:
    ofis.takim_klasoru_ayarla(KY, "goreli/yol")
    goreli = False
except ValueError:
    goreli = True
sina("goreli yol reddedildi", goreli)
from ofis.yollar import OFIS_KODU  # noqa: E402
icerde = Path(OFIS_KODU) / "takim-denemesi-olmamali"
try:
    ofis.takim_klasoru_ayarla(KY, str(icerde))
    ic = False
except ValueError:
    ic = True
sina("ofisin kendi yerine klasor ACILMADI", ic and not icerde.exists())

print("\n4. tasima ve yeni takim")
ofis.tahta.birak(gy2["no"], sebep="sinama") if ofis.tahta.gorev(gy2["no"])["durum"] == "calisiyor" else None
KX = ofis.kanat_ac("EK", "EK")
ofis.takim_klasoru_ayarla(KX, str(d / "EkKok"))
ofis.kadro.tasi("cem", KX)
sina("tasinan ajan yeni takimin kokune gecti", ayni(ofis.kadro.ajan("cem")["klasor"], d / "EkKok"))
ofis.kadro.tasi("yalniz", KX)
sina("yalitilmis ajan tasininca kendi klasorunde kaldi",
     ayni(ofis.kadro.ajan("yalniz")["klasor"], d / "yalniz"))
y1 = ofis.yeni_takim_koku("Satis")
sina("sinama defterinde yeni takim koku projenin icinde (masaustune dokunulmaz)",
     ayni(Path(y1).parent, kok), y1)
(Path(y1)).mkdir()
KS = ofis.kanat_ac("SATIS", "SA")
ofis.takim_klasoru_ayarla(KS, y1)
y2 = ofis.yeni_takim_koku("Satis")
sina("ayni adla ikinci takim baskasinin kokunu ALMIYOR (-2)", Path(y2).name == "Satis-2", y2)

print("\n5. ekler ve konsol")
e = E.kaydet(ofis, "not.txt", b"x", kanat_id=KM)
sina("ek takimin kokune yazildi", (mag / ".ofis" / "ekler").is_dir()
     and any((mag / ".ofis" / "ekler").iterdir()), str(e))
sina("ek adla bulunuyor (butun koklere bakilir)", E.dosya(ofis, Path(e["yol"]).name).is_file())
sina("konsol takim kokunu ofisin koku sayiyor", _ofis_kokunde_mi(ofis, mag / "src"))
sina("konsol ilgisiz klasoru saymiyor", not _ofis_kokunde_mi(ofis, d / "yalniz"))

print("\n6. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
r = ist.post("/api/takim/kur", json={"ad": "Destek", "uyeler": [
    {"ad": "nil", "rol": "lider", "motor": "sahte"}]})
j = r.json()
kid = j.get("id")
yeni = ofis.kok_klasoru(kid) if kid else ""
sina("takim kurulurken kendi klasoru acildi", r.status_code == 200 and Path(yeni).is_dir()
     and not ayni(yeni, kok), f"{r.status_code} {j} {yeni}")
sina("kurulan ajan takimin klasorunde", kid and ayni(ofis.kadro.ajan("nil")["klasor"], yeni))
org = ist.get("/api/organizasyon").json()
kart = next((k for k in org["kanatlar"] if k["id"] == kid), {})
sina("organizasyon klasoru ve 'kendi' bilgisini veriyor",
     kart.get("kendi_klasoru") is True and ayni(kart.get("klasor", ""), yeni), str(kart.get("klasor")))
hedef = d / "DestekYeni"
r = ist.post(f"/api/kanat/{kid}/duzenle", json={"klasor": str(hedef)})
sina("duzenle ile klasor degisti", r.status_code == 200 and ayni(r.json().get("klasor", ""), hedef)
     and ayni(ofis.kadro.ajan("nil")["klasor"], hedef), r.text[:200])
r = ist.post(f"/api/kanat/{KM}/duzenle", json={"klasor": str(d / "olmaz")})
sina("panel: calisan isli takimda klasor degismiyor (400, aciklamali)",
     r.status_code == 400 and "calisan" in r.text.lower() and not (d / "olmaz").exists(), r.text[:200])
r = ist.post(f"/api/kanat/{KY}/duzenle", json={"ad": "YAZILIM"})
sina("klasor verilmeyen duzenleme klasora dokunmuyor",
     r.status_code == 200 and ayni(ofis.kok_klasoru(KY), kok))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
