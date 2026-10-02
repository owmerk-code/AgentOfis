# -*- coding: utf-8 -*-
"""AYARLAR + ENTEGRASYONLAR + TAKIM IZINLERI duman testi (02.10.2026).

Sinanan:
  1. ayarlar.oku butun bolumleri verir; yaz yalniz izinli anahtari kabul eder
     ve kurali EVINDEN uygular (kapi modeli kademeye girmez, onay bildirimi
     kapanmaz, esik sinirli, para ayari panelden degismez)
  2. kapatilan bildirim turu gelmez, kapatilamayan gelir
  3. entegrasyon kartlari OLCUMDEN: bagli / giris gerekli / hesapta yok /
     olculemedi; hesapta olup katalogda olmayan "Diger"de; anahtar degeri sizmaz
  4. baglayicilar herkese acik; kapatilan ajandan cikar (takim izni kaldirildi)
     (sebebi olaya), baglayicili 'kolay' is 'orta'ya cikar; plan metni izni
     ve sema satirini yalniz izin varken gosterir
  5. panel uclari
Jeton yakmaz; `claude mcp list` ve `gh` KOSTURULMAZ (olcum yerine sahte).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici ev/kasa; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import Ofis, Veritabani, ayarlar, entegrasyon, baglayici  # noqa: E402
from ofis.bildirim import Izleyici  # noqa: E402

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
        return str(exc) or type(exc).__name__


# Olcum SAHTE: gercek `claude mcp list` / `gh` kosmaz.
SAHTE_BAG = {"Shopify": {"bagli": True, "url": "u"}, "Meta Reklamları": {"bagli": True, "url": "u"},
             "Supabase": {"bagli": False, "url": "u"}, "Spotify": {"bagli": True, "url": "u"}}
baglayici._olc = lambda zaman_asimi=90: {k: dict(v) for k, v in SAHTE_BAG.items()}
baglayici.onbellegi_bosalt()
entegrasyon.CLI_OLCER["gh"] = lambda: {"durum": "bagli", "ayrinti": "hesap: deneme"}
entegrasyon.CLI_OLCER["vercel"] = lambda: {"durum": "kurulu_degil", "ayrinti": "yok",
                                           "bagla": "npm i -g vercel ; vercel login"}

print("== ayarlar duman testi ==\n")
_d = Path(tempfile.mkdtemp(prefix="ofis-ayarlar-"))
db = Veritabani(_d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Ayar", amac="a", basari_olcutu="b", kok_klasor=str(_d))
MAG = ofis.kanat_ac("MAGAZA", "MG")
YAZ = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("ayse", "lider", kanat_id=MAG, lider_mi=True, tur="eller", motor="sahte", klasor=str(_d))
ofis.kadro.ise_al("deniz", "metin", kanat_id=MAG, tur="eller", motor="sahte", klasor=str(_d))
ofis.kadro.ise_al("demir", "lider", kanat_id=YAZ, lider_mi=True, tur="eller", motor="sahte", klasor=str(_d))

print("1. oku / yaz")
v = ayarlar.oku(ofis)
sina("butun bolumler var", all(k in v for k in ("calisma", "bildirim", "modeller", "guvenlik",
                                                 "yedek", "takimlar")), str(list(v)))
sina("iki takim, liderleriyle", {t["ad"]: t["lider"] for t in v["takimlar"]}
     == {"MAGAZA": "ayse", "YAZILIM": "demir"}, str(v["takimlar"])[:200])
ayarlar.yaz(ofis, "lider_kipi", "arka")
sina("liderin kipi yazilir", ayarlar.oku(ofis)["calisma"]["lider_kipi"] == "arka")
sina("gecersiz kip reddedilir", "arka" in hata(lambda: ayarlar.yaz(ofis, "lider_kipi", "x")))
sina("kapi modeli (fable) kademeye GIRMEZ", "KAPI" in hata(lambda: ayarlar.yaz(
    ofis, "kademe", {"motor": "claude", "kademe": "guclu", "model": "fable"})))
ayarlar.yaz(ofis, "kademe", {"motor": "claude", "kademe": "hizli", "model": "haiku"})
sina("kademe yazilir", ayarlar.oku(ofis)["modeller"]["kademe"]["claude"]["hizli"] == "haiku")
sina("esik %50 altinda reddedilir", "%50" in hata(lambda: ayarlar.yaz(
    ofis, "esik", {"rol": "isci", "pencere": "5s", "deger": 0.2})))
ayarlar.yaz(ofis, "esik", {"rol": "isci", "pencere": "5s", "deger": 0.7})
sina("esik yazilir ve zincir onu okur",
     ayarlar.oku(ofis)["modeller"]["esikler"]["isci"]["5s"] == 0.7)
sina("onay bildirimi KAPATILAMAZ", "kapatilamaz" in hata(lambda: ayarlar.yaz(
    ofis, "bildirim_turu", {"tur": "onay", "acik": False})))
sina("para ayari panelden DEGISTIRILEMEZ", "degistirilemez" in hata(
    lambda: ayarlar.yaz(ofis, "para_harca", True)))
sina("olmayan takima izin yazilamaz", "takim" in hata(lambda: ayarlar.yaz(
    ofis, "takim_izni", {"kanat_id": "yok", "adlar": ["Shopify"]})).lower())
with db.baglanti() as c:
    n = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'ayar'").fetchone()[0]
sina("her degisiklik kayda gecer", n >= 3, str(n))

print("\n2. bildirim secimi")
izl = Izleyici(ofis)
ayarlar.yaz(ofis, "bildirim_turu", {"tur": "zamanli", "acik": False})
db.olay_yaz(ofis.proje_id, "zamanli_calisti", "gece raporu", ajan_ad="ofis")
db.olay_yaz(ofis.proje_id, "onay_istendi", "push istiyor", ajan_ad="deniz")
bas = [b for b, _ in izl.topla()]
sina("kapatilan tur GELMEDI", "Zamanlanmış iş başladı" not in bas, str(bas))
sina("onay yine GELDI", "Onay bekliyor" in bas, str(bas))

print("\n3. entegrasyon kartlari")
r = entegrasyon.kartlar(taze=True)
k = {x["ad"]: x for x in r["kartlar"]}
sina("Shopify ve Meta BAGLI, Bagla yolu hazir", k["Shopify"]["durum"] == "bagli"
     and k["Meta Reklamları"]["durum"] == "bagli"
     and k["Shopify"]["kopar"]["komut"] == 'claude mcp logout "claude.ai Shopify"')
sina("Supabase giris gerekli + login komutu", k["Supabase"]["durum"] == "giris_gerekli"
     and k["Supabase"]["bagla"]["komut"] == 'claude mcp login "claude.ai Supabase"')
sina("hesapta olmayan (Gmail) 'hesapta yok'", k["Gmail"]["durum"] == "hesapta_yok")
sina("katalogda olmayan olculen (Spotify) Diger'de", k.get("Spotify", {}).get("kategori") == "Diğer")
sina("CLI kartlari: GitHub bagli, Vercel kurulu degil + kurulum komutu",
     k["GitHub"]["durum"] == "bagli" and k["Vercel"]["durum"] == "kurulu_degil"
     and "npm i -g vercel" in k["Vercel"]["bagla"]["komut"])
baglayici._olc = lambda zaman_asimi=90: {}
baglayici.onbellegi_bosalt()
r0 = entegrasyon.kartlar(taze=True)
sina("olcum kosmazsa 'olculemedi' (bagli DEMEZ)",
     {x["ad"]: x["durum"] for x in r0["kartlar"]}["Shopify"] == "olculemedi")
baglayici._olc = lambda zaman_asimi=90: {k: dict(v) for k, v in SAHTE_BAG.items()}
baglayici.onbellegi_bosalt()
baglayici.durum(taze=True)
from ofis import gizli  # noqa: E402
gizli.ekle("DENEME_ANAHTARI", "cok-gizli-deger-99")
r2 = entegrasyon.kartlar()
sina("anahtar adi + parmak izi var, DEGER YOK",
     any(a["ad"] == "DENEME_ANAHTARI" for a in r2["anahtarlar"])
     and "cok-gizli-deger-99" not in json.dumps(r2, ensure_ascii=False))
sina("kartlardaki risk cumlesi kapinin olculen kuraliyla ayni",
     "Taslak oluşturma ve düzenleme sorulmaz" in k["Shopify"]["risk"])

print("\n4. baglayicilar HERKESE acik (02.10.2026: takim izni kaldirildi)")
from ofis import kaynaklar as _KY  # noqa: E402
sina("plan metninde takim izni blogu YOK", "BAGLAYICI IZNI" not in ofis.orkestra.plan_metni("magaza isi", MAG))
sina("kartta 'ajanlara acik' varsayilan ACIK", k["Shopify"].get("ajanlara_acik") is True
     and k["Shopify"].get("grup") == "claude_baglayici")
_KY.ayarla("claude_baglayici", "Meta Reklamları", False)
_k2 = {x["ad"]: x for x in entegrasyon.kartlar()["kartlar"]}
sina("kapatilan baglayici kartta KAPALI", _k2["Meta Reklamları"]["ajanlara_acik"] is False)
sina("kapatilan baglayici ajandan CIKAR (olculen ad kurali)",
     "mcp__claude_ai_Meta_Reklamlar" in _KY.claude_bayraklari()["yasak"], str(_KY.claude_bayraklari()["yasak"]))
_KY.ayarla("claude_baglayici", "Meta Reklamları", True)
sina("acilan geri gelir", _KY.claude_bayraklari()["yasak"] == [])
sina("Takimlar ekraninda izin kutucugu YOK (ise yaramayan gosterge kalmasin)",
     "takim-izin" not in (KOK / "web" / "ayarlar.js").read_text(encoding="utf-8"))

print("\n5. panel uclari")
from fastapi.testclient import TestClient  # noqa: E402
from ofis import panel  # noqa: E402
cl = TestClient(panel.olustur(db.yol, "Ayar"))
r = cl.get("/api/ayarlar")
sina("GET /api/ayarlar", r.status_code == 200 and "takimlar" in r.json())
r = cl.post("/api/ayarlar", json={"anahtar": "bildirim_turu", "deger": {"tur": "soru", "acik": False}})
sina("POST yasak deger 400", r.status_code == 400, r.text[:120])
r = cl.post("/api/entegrasyon/anahtar", json={"ad": "PANEL_ANAHTAR", "deger": "panel-gizli-77"})
sina("anahtar ekle: deger cevapta YOK", r.status_code == 200 and "panel-gizli-77" not in r.text, r.text)
with db.baglanti() as c:
    sz = c.execute("SELECT COUNT(*) FROM olay WHERE govde LIKE '%panel-gizli-77%'").fetchone()[0]
sina("  deger deftere de YAZILMADI", sz == 0)
r = cl.post("/api/entegrasyon/anahtar/PANEL_ANAHTAR/sil")
sina("anahtar sil", r.status_code == 200 and not any(a["ad"] == "PANEL_ANAHTAR" for a in gizli.liste()))
r = cl.get("/api/entegrasyon")
sina("GET /api/entegrasyon", r.status_code == 200 and r.json()["kartlar"])
JS = (KOK / "web" / "ayarlar.js").read_text(encoding="utf-8")
HTML = (KOK / "web" / "index.html").read_text(encoding="utf-8")
sina("Ayarlar dugmesi ve betigi sayfada", 'id="ayarlar-ac"' in HTML and "/varlik/ayarlar.js" in HTML)
sina("tasinan anahtarlar ust cubukta gizli", 'id="efor-sec" hidden' in HTML
     and 'id="kip-sec" hidden' in HTML and 'id="bildirim-anahtar" hidden' in HTML)
sina("dokuz bolum (Beceriler, Eklentiler ve MCP dahil)", all(f'["{b}"' in JS for b in (
    "entegrasyon", "beceri", "kaynak", "takim", "modeller", "calisma", "bildirim", "guvenlik", "yedek"))
     and "Eklentiler ve MCP" in JS and "Yedek ve sağlık" in JS)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
