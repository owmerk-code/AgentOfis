"""AJANLAR KABINDE -- izleme kabini duman testi.

Kullanici (29.09.2026): *"muratin sisteminde ajanlar gomulu tarayiciyi
kullaniyor, orda oynuyor, bizde de olmali."* Sinanan:

  1. tarayici katmani: kabin (cdp) + serbest YALNIZ `kabin_izleme` ile
     kurulur; anahtar yokken eski kural (kabin yalniz isaret edilen
     sitelerle) aynen durur
  2. halka: anahtar ACIK + kabin acik -> tarayici kullanacagi en belli
     olan TEK is kabine; kapaliyken HICBIRI; kabin kapaliyken hicbiri;
     insanin isaret ettigi kabinli is varken izleme verilmez
  3. koltuk: izlemedeki ajana kabine bagli, SERBEST tarayici sunucusu +
     "paylasilan kabin" notu; izlemede olmayan ajana not YOK
  4. panel: /api/kabin/izle okunur/yazilir, kayda gecer

Jeton yakmaz, gercek Chrome acmaz: kabin ucnoktasi sahte bir adrestir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from ofis import Ofis, Veritabani, tarayici
from ofis.koltuk import Koltuk, KABIN_IZLEME_NOTU
from ofis.motor.sahte import SahteMotor
from ofis.orkestra import Orkestra, KABIN_IZLE_ANAHTARI
import ofis.panel as _P

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== ajanlar kabinde duman testi ==\n")
CDP = "http://127.0.0.1:59999"

# ---------------------------------------------------------------------------
print("1. TARAYICI KATMANI")
g = tarayici.sunucu_girdisi([], cdp=CDP, serbest=True)
sina("anahtar yokken kabin SERBEST kurulmaz (eski kural)", g is None)
g = tarayici.sunucu_girdisi([], cdp=CDP, serbest=True, kabin_izleme=True)
arg = " ".join(g["args"]) if g else ""
sina("izleme kipinde kabine BAGLANIR", g is not None and "--cdp-endpoint" in arg and CDP in arg, arg)
sina("  ve SERBEST (izinli site listesi yok)", "--allowed-origins" not in arg)
sina("  tarayici VEKIL uzerinden (riskli tiklama kapisi)", "tarayici_kapi.py" in arg)
g = tarayici.sunucu_girdisi(["https://a.com"], cdp=CDP, kabin_izleme=True)
sina("alanli iste liste YINE uygulanir", g and "--allowed-origins" in " ".join(g["args"]))
oz = tarayici.ozet([], cdp=CDP, kabin_izleme=True)
sina("ozet 'CANLI' ve oturumlari soyluyor", "CANLI" in oz and "oturum" in oz, oz)

# ---------------------------------------------------------------------------
print("\n2. HALKA KABINI KIME VERIR")
kok = Path(tempfile.mkdtemp(prefix="ofis-izle-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Izle", amac="kabin", basari_olcutu="izlenir")
kn = ofis.kanat_ac("GENEL", "GN")
(kok / "w").mkdir()
for ad, meslek, lider in (("lale", "lider", True), ("ali", "backend", False),
                          ("ece", "arastirma", False), ("cem", "metin", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kn, lider_mi=lider, tur="eller",
                      motor="sahte", klasor=str(kok / "w"))
g_kod = ofis.tahta.gorev_ac("hesap.py yaz", neden="n", ana_hedef="topla islevi",
                            kabul_olcutu="k", yazma_alani=["hesap.py"], kanat_id=kn)
g_web = ofis.tahta.gorev_ac("Siteyi incele", neden="n",
                            ana_hedef="https://ornek.com sayfasini tarayicida gez",
                            kabul_olcutu="k", yazma_alani=["rapor.md"], kanat_id=kn)

ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **k: SahteMotor(cevap="tamam"))
cagrilar = []


def _sahte_kos(no, ajan, **ayar):
    cagrilar.append({"no": no, "ajan": ajan, "cdp": ayar.get("tarayici_kabini", ""),
                     "izleme": ayar.get("kabin_izleme", False)})
    return {"basarili": True, "kanit": 0}


ork.koltuk.kos = _sahte_kos
ork.kabin_ucnoktasi = lambda: CDP


def tik_koş():
    cagrilar.clear()
    ork.tik(paralel=3)
    return {c["no"]: c for c in cagrilar}


# VARSAYILAN ACIK (02.10.2026, patron: "tarayici her zaman kullanilabilir
# olmali, otomatik olmali"). Ayar hic yazilmamisken bir is kabine gider.
c = tik_koş()
sina("ayar yokken (varsayilan) TEK is kabinde",
     len([x for x in c.values() if x["izleme"]]) == 1, str(c))
db.ayar_yaz(ofis.proje_id, KABIN_IZLE_ANAHTARI, "kapali")
c = tik_koş()
sina("anahtar acikca KAPATILINCA hicbir is kabine gitmedi",
     c and not any(x["izleme"] or x["cdp"] for x in c.values()), str(c))
db.ayar_yaz(ofis.proje_id, KABIN_IZLE_ANAHTARI, "acik")
c = tik_koş()
izlenen = [x for x in c.values() if x["izleme"]]
sina("anahtar ACIK: TEK is kabinde", len(izlenen) == 1, str(c))
sina("  o is TARAYICI isi (site incele), kod isi degil",
     izlenen and izlenen[0]["no"] == g_web["no"], str(izlenen))
sina("  kabine giden isin ucnoktasi kabin", izlenen and izlenen[0]["cdp"] == CDP)
sina("  oteki is YINE kostu (kendi gorunmez tarayicisiyla)",
     g_kod["no"] in c and not c[g_kod["no"]]["cdp"])
ork.kabin_ucnoktasi = lambda: ""
c = tik_koş()
sina("kabin KAPALIYKEN izleme verilmez, isler yine kosar",
     len(c) == 2 and not any(x["izleme"] for x in c.values()), str(c))
ork.kabin_ucnoktasi = lambda: CDP
# Insanin isaret ettigi is SIRADA SONRA gelsin: izleme adayi (g_web) once
# islenir. Oncelik sira tesadufune kalsaydi izleme kabini kapar, insanin
# isi "kabin baska iste" diye beklerdi.
g_ins = ofis.tahta.gorev_ac("Isaretli sayfa", neden="n", ana_hedef="isaretlenen sayfa",
                            kabul_olcutu="k", yazma_alani=["isaret.md"], kanat_id=kn)
with db.baglanti() as conn:
    conn.execute("UPDATE gorev SET tarayici_kabin = 1, tarayici_alani = ? WHERE id = ?",
                 (json.dumps(["https://ornek.com"]), g_ins["id"]))
c = tik_koş()
sina("insanin isaret ettigi kabinli is varken izleme VERILMEZ (oncelik onun)",
     not any(x["izleme"] for x in c.values()), str(c))
sina("  insanin isi KABINDE kostu (sirada sonra olsa da)",
     g_ins["no"] in c and c[g_ins["no"]]["cdp"] == CDP, str(c))
sina("  izleme adayi BEKLETILMEDI, kendi tarayicisiyla kostu",
     g_web["no"] in c and not c[g_web["no"]]["cdp"], str(c))
ofis.tahta.iptal_et(g_ins["no"], sebep="sinama bitti", iptal_eden="insan")
# KREDI SITESI KABINDE (11.10.2026 canli, Brave+Belle #14): patronun mesajinda
# Flow adresi yoktu -> lider kabin isaretlemedi -> video isi BOS gizli
# tarayicida Flow'un tanitim sayfasina dustu, patrona "giris yap" denildi;
# kabini tarayiciya ihtiyaci olmayan is "izleme" icin almisti.
g_flow = ofis.tahta.gorev_ac("Flow klipleri", neden="n", ana_hedef="flow'da video",
                             kabul_olcutu="k", yazma_alani=["video.md"], kanat_id=kn,
                             tarayici_alani=["https://flow.google.com"])
sina("Flow isinde kabin isareti YOK (lider vermedi)", not ofis.tahta.gorev(g_flow["no"])["tarayici_kabin"])
c = tik_koş()
sina("Flow isi yine de KABINDE kostu (patronun 04.10 kalici karari)",
     g_flow["no"] in c and c[g_flow["no"]]["cdp"] == CDP, str(c))
sina("  Flow isi varken kabin IZLEME icin baska ise verilmedi",
     not any(x["izleme"] for x in c.values()), str(c))
ofis.tahta.iptal_et(g_flow["no"], sebep="sinama bitti", iptal_eden="insan")

# ---------------------------------------------------------------------------
print("\n3. KOLTUK: izlemedeki ajan ne aliyor")
kayit = {}


class Kaydeden(SahteMotor):
    mcp_konusur = True

    def tur_kos(self, metin, **ayar):
        kayit["metin"] = metin
        kayit["mcp"] = json.dumps(ayar.get("mcp_yapilandirma"), default=str)
        return super().tur_kos(metin, **ayar)


def koltuk_kos(no, ajan, **ayar):
    k = Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: Kaydeden(cevap="tamam", mcp_konusur=True))
    kayit.clear()
    try:
        k.kos(no, ajan, **ayar)
    except Exception as exc:     # cokme KALDI sayilir, sinamalar kossun
        kayit["hata"] = f"{type(exc).__name__}: {exc}"
    return kayit


g3 = ofis.tahta.gorev_ac("Sayfayi gez", neden="n", ana_hedef="siteyi gez",
                         kabul_olcutu="k", yazma_alani=["gez.md"], kanat_id=kn)
k = koltuk_kos(g3["no"], "cem", tarayici_kabini=CDP, kabin_izleme=True)
m = k.get("mcp", "")
sina("izlemedeki ajana tarayici KABINE bagli", "--cdp-endpoint" in m and "59999" in m,
     k.get("hata", "") or m[:200])
sina("  izinli liste YOK (serbest)", "--allowed-origins" not in m)
sina("  ajana 'paylasilan kabin' NOTU gitti", KABIN_IZLEME_NOTU[:40] in k.get("metin", ""))
with db.baglanti() as conn:
    o = conn.execute("SELECT govde FROM olay WHERE tur='tarayici_acildi' "
                     "ORDER BY rowid DESC LIMIT 1").fetchone()
sina("  kayda 'CANLI izleniyor' diye gecti", o and "CANLI" in o["govde"], o and o["govde"])
g4 = ofis.tahta.gorev_ac("Baska is", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["baska.md"], kanat_id=kn)
k = koltuk_kos(g4["no"], "ece", tarayici_kabini="", kabin_izleme=False)
m = k.get("mcp", "")
sina("izlemede OLMAYAN ajan kendi gorunmez tarayicisi (kabine bagli degil)",
     "tarayici_kapi.py" in m and "--cdp-endpoint" not in m, k.get("hata", "") or m[:200])
sina("  ona kabin notu GITMEDI", KABIN_IZLEME_NOTU[:40] not in k.get("metin", ""))
g5 = ofis.tahta.gorev_ac("Ucuncu is", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["uc.md"], kanat_id=kn)
k = koltuk_kos(g5["no"], "ali", tarayici_kabini=CDP, kabin_izleme=False)
m = k.get("mcp", "")
sina("cdp verilip IZLEME verilmezse eski kural: kabinde serbest tarayici YOK",
     "--cdp-endpoint" not in m, m[:200])

# ---------------------------------------------------------------------------
print("\n4. PANEL")
istemci = TestClient(_P.olustur(kok / "ofis.sqlite3"))
db.ayar_yaz(ofis.proje_id, KABIN_IZLE_ANAHTARI, "kapali")
sina("GET kapali", istemci.get("/api/kabin/izle").json() == {"acik": False})
r = istemci.post("/api/kabin/izle", json={"acik": True})
sina("POST ac", r.status_code == 200 and r.json()["acik"] is True, r.text[:120])
sina("  ayara yazildi", db.ayar_oku(ofis.proje_id, KABIN_IZLE_ANAHTARI) == "acik")
with db.baglanti() as conn:
    o = conn.execute("SELECT govde, ajan_ad FROM olay WHERE tur='kabin_izle' "
                     "ORDER BY rowid DESC LIMIT 1").fetchone()
sina("  kayda gecti, ACAN insan", o and o["ajan_ad"] == "insan" and "ACIK" in o["govde"])
istemci.post("/api/kabin/izle", json={"acik": False})
sina("POST kapat", istemci.get("/api/kabin/izle").json() == {"acik": False})
_js = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
_html = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")
sina("panelde 'ajanlar' dugmesi var ve uca bagli",
     'id="kabin-izle"' in _html and '"/api/kabin/izle"' in _js)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
