# -*- coding: utf-8 -*-
"""KARAR EKRANI (08.10.2026, B1): secenekli soru, onerilen secili, toplu kabul.
Jeton yakmaz.

Sinanan: secim kurallari (2-6 ayri secenek, onerilen sira ya da ayni metin);
ajan araci secenekli soru sorar, gecersiz secimde sebebi ajana soylenir;
bekleyen soru secimiyle doner; toplu kabul YALNIZ onerilenli sorulari
cevaplar -- serbest soru ve onay kartlari (para, silme, yayin) dokunulmaz;
panel ucu ve arayuz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, mcp_sunucu as M  # noqa: E402
from ofis.postane import Postane, PostaneHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("1. secim kurallari")
sina("secenek yoksa serbest soru", Postane.secim_dogrula(None) == {})
r = Postane.secim_dogrula(["Mavi tema", "Koyu tema", "Acik tema"], "Koyu tema")
sina("onerilen AYNI metinle", r == {"secenekler": ["Mavi tema", "Koyu tema", "Acik tema"], "onerilen": 1}, str(r))
sina("onerilen sirayla", Postane.secim_dogrula(["a", "b"], 0)["onerilen"] == 0)
sina("onerilen yazim farkina dayanikli (harf, bosluk)",
     Postane.secim_dogrula(["Evet, yayinla", "Hayir"], "  evet,  YAYINLA ")["onerilen"] == 0)
sina("onerilensiz secenekli soru", Postane.secim_dogrula(["a", "b"])["onerilen"] is None)
for kotu, neden in ((["tek"], "tek secenek"), (["a", "b", "c", "d", "e", "f", "g"], "7 secenek"),
                    (["a", "A"], "ayni secenek"), (["a", ""], "bos secenek"), ("a,b", "liste degil")):
    try:
        Postane.secim_dogrula(kotu)
        sina(f"reddedildi: {neden}", False)
    except PostaneHatasi:
        sina(f"reddedildi: {neden}", True)
for oneri in ("yok-boyle", 5):
    try:
        Postane.secim_dogrula(["a", "b"], oneri)
        sina(f"gecersiz onerilen reddedildi ({oneri!r})", False)
    except PostaneHatasi:
        sina(f"gecersiz onerilen reddedildi ({oneri!r})", True)

print("\n2. ajan araci ve bekleyenler")
d = Path(tempfile.mkdtemp(prefix="ofis-karar-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Karar", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("can", "metin", kanat_id=KA, motor="sahte", klasor=str(d))
g = ofis.tahta.gorev_ac("tema", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
g = ofis.tahta.sahiplen(g["no"], "ece", g["revizyon"])


class _Oturum:
    def __init__(self, ajan, no):
        self.ofis, self.ajan_ad, self.gorev_no, self.proje_id = ofis, ajan, no, ofis.proje_id

    def gorev(self):
        return ofis.tahta.gorev(self.gorev_no)


cevap = M.arac_soru_sor(_Oturum("ece", g["no"]), {
    "soru": "Hangi tema?", "kime": "insan",
    "secenekler": ["Koyu tema", "Acik tema", "Sistem temasi"], "onerilen": "Koyu tema"})
sina("ajan secenekli soru sordu", "iletildi" in cevap, cevap)
cevap = M.arac_soru_sor(_Oturum("ece", g["no"]), {
    "soru": "Bozuk", "kime": "insan", "secenekler": ["tek"]})
sina("gecersiz secim: HATA ve sebep ajana", cevap.startswith("HATA") and "2-6" in cevap, cevap)
ofis.postane.soru_sor("can", "insan", "Baslik ne olsun?", secenekler=["Kisa", "Uzun"], onerilen=1)
ofis.postane.soru_sor("can", "insan", "Serbest soru: rengi sen soyle")
ofis.postane.soru_sor("lale", "insan", "Secenekli ama onerisiz", secenekler=["X", "Y"])
onay = ofis.postane.onay_iste("ece", "git push", risk="yuksek", gorev_no=g["no"])
b = ofis.postane.insan_bekleyenler()
tema = next(s for s in b if s["govde"] == "Hangi tema?")
sina("bekleyen soru secimiyle doner", tema["secim"] == {
    "secenekler": ["Koyu tema", "Acik tema", "Sistem temasi"], "onerilen": 0}, str(tema.get("secim")))
sina("serbest sorunun secimi yok", next(s for s in b if s["govde"].startswith("Serbest"))["secim"] is None)
sina("gecersiz secimli soru deftere GIRMEDI", not any(s["govde"] == "Bozuk" for s in b))

print("\n3. toplu kabul")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
pb = ist.get("/api/bekleyenler").json()
sina("panel bekleyenleri secimle veriyor",
     any((s.get("secim") or {}).get("onerilen") == 0 for s in pb["sorular"]), str(pb["sorular"])[:200])
r = ist.post("/api/sorular/onerilenleri_kabul", json={})
cev = {x["cevap"] for x in r.json().get("cevaplanan", [])}
sina("toplu kabul: yalniz onerilenli iki soru", r.status_code == 200 and cev == {"Koyu tema", "Uzun"}, r.text[:300])
kalan = {s["govde"] for s in ofis.postane.insan_bekleyenler()}
sina("serbest soru ve onerisiz secenekli soru BEKLEMEDE",
     kalan == {"Serbest soru: rengi sen soyle", "Secenekli ama onerisiz"}, str(kalan))
sina("onay karti DOKUNULMADI (push hala bekliyor)",
     any(o["id"] == onay["id"] for o in ofis.postane.bekleyen_onaylar()))
with db.baglanti() as c:
    m = c.execute("SELECT cevap FROM mesaj WHERE govde = 'Hangi tema?'").fetchone()[0]
    ol = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'toplu_kabul'").fetchone()[0]
sina("ajan cevabi secenegin metni olarak aldi", m == "Koyu tema", m)
sina("toplu kabul kayda gecti", ol == 1)
r = ist.post("/api/sorular/onerilenleri_kabul", json={})
sina("ikinci basista cevaplanacak bir sey yok", r.json().get("cevaplanan") == [])

print("\n4. arayuz")
JS = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
sina("toplu kabul dugmesi ve onerilen isareti panelde",
     "Önerilenlerin hepsini kabul et" in JS and "★ önerilen" in JS and "secenek" in JS)
araclar = {a["name"]: a for a in M.ARACLAR} if hasattr(M, "ARACLAR") else {}
sema = json.dumps(araclar.get("soru_sor", {}).get("inputSchema", {})) if araclar else ""
sina("soru_sor aracinda secenekler ve onerilen alani", (not araclar) or ("secenekler" in sema and "onerilen" in sema), sema[:200])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
