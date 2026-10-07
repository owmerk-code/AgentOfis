# -*- coding: utf-8 -*-
"""URETIM KREDISI KAPISI (07.10.2026). Jeton ve kredi yakmaz.

Patron: "videoyu uretmeden once bana gelsin." OLCULDU (06.10 gosteri):
Flow'da "Oluşturmaya başla" kapidan SORULMADAN gecti, ajan 4 krediyi kendisi
harcadi. Sinanan:
  * kredi sitesinde uretim tiklamasi / Enter / buyutme indirmesi SORULUR;
  * olculmus katalogda 0 kredi olan uretim (Nano Banana taslak karesi)
    SORULMAZ; katalog yoksa ya da ayar okunamazsa SORULUR;
  * baska sitede ayni yazi ("Oluştur") sorulmaz; Flow'da "Yükselt" PARA;
  * patronun sozu ve "bu projede hep" kredi kapisini ACMAZ;
  * vekil uretim ayarini sayfanin anlik goruntusunden okur; "bu is boyunca"
    onayi ayni isteki sonraki uretimleri sormaz (tarayici kapisi bunu
    bilmiyordu), "bir kez" onayi tukenir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

KOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOD))

from ofis import Ofis, Veritabani, flow as F, izin, riskli  # noqa: E402
from ofis import tarayici_kapi as K  # noqa: E402

GECEN = KALAN = 0
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


FLOW = "https://flow.google.com/project/abc"
VIDEO_AYARI = "Video · 720p · 10 sn. x1"          # 07.10 gercek ekrandan
RESIM_AYARI = "🍌 Nano Banana 2.1 · 9:16 · x2"
KATALOG = {
    "olculdu": "2026-10-07T00:00:00+00:00", "kredi_bakiyesi": 1046,
    "video": [{"kip": "Video", "tur": "Kareler", "model": "Omni 1.1 Flash",
               "bedel": [{"cozunurluk": "720p", "sure": "10 sn.", "kredi": 15}]},
              {"kip": "Video", "tur": "Kareler", "model": "Veo 3.1 - Quality",
               "bedel": [{"cozunurluk": None, "sure": None, "kredi": 100}]}],
    "resim": [{"kip": "Resim", "tur": None, "model": "Nano Banana 2.1",
               "bedel": [{"cozunurluk": None, "sure": None, "kredi": 0}]},
              {"kip": "Resim", "tur": None, "model": "Nano Banana Pro",
               "bedel": [{"cozunurluk": None, "sure": None, "kredi": 0}]}],
}


def tikla(yazi, url=FLOW, ayar=VIDEO_AYARI, arac="browser_click", **ek):
    arg = {"element": yazi, "target": "e9", **ek}
    return riskli.degerlendir(arac, arg, url=url, sayfa_metni=yazi, uretim_ayari=ayar)


print("1. katalogsuz: her uretim SORULUR (bilinmeyen = sor)")
sina("katalog yokken resim uretimi de soruluyor",
     (tikla("Oluşturmaya başla", ayar=RESIM_AYARI) or {}).get("sinif") == "kredi")
F.kaydet(KATALOG)

print("\n2. kredi sitesi")
b = tikla("Oluşturmaya başla")
sina("video uretimi SORULUR (kredi)", (b or {}).get("sinif") == "kredi", str(b))
sina("kartta uretim ayari yazili", b and VIDEO_AYARI in b["hedef"] and VIDEO_AYARI in b["sebep"])
sina("kartta senaryo paketi isteniyor", b and "senaryo paketi" in b["sebep"])
sina("resim (katalogda 0 kredi) SORULMAZ -- taslak kareler serbest",
     tikla("Oluşturmaya başla", ayar=RESIM_AYARI) is None)
sina("ayar okunamadiysa SORULUR", (tikla("Oluşturmaya başla", ayar="") or {}).get("sinif") == "kredi")
sina("Enter (istem gonderimi) SORULUR",
     (riskli.degerlendir("browser_press_key", {"key": "Enter"}, url=FLOW,
                         uretim_ayari=VIDEO_AYARI) or {}).get("sinif") == "kredi")
sina("yazip Enter'la gonderme (submit) SORULUR",
     (riskli.degerlendir("browser_type", {"element": "istem", "target": "e3", "text": "a bottle",
                                          "submit": True}, url=FLOW, sayfa_metni="textbox",
                         uretim_ayari=VIDEO_AYARI) or {}).get("sinif") == "kredi")
sina("istemi YAZMAK (gondermeden) serbest",
     riskli.degerlendir("browser_type", {"element": "istem", "target": "e3", "text": "a bottle"},
                        url=FLOW, sayfa_metni="textbox", uretim_ayari=VIDEO_AYARI) is None)
sina("ayar menusunde model secmek serbest", tikla("Veo 3.1 - Quality") is None)
sina("1080p Yükseltilmiş indirme (buyutme) SORULUR",
     (tikla("1080p Yükseltilmiş") or {}).get("sinif") == "kredi")
sina("720p Orijinal indirme serbest", tikla("720p Orijinal boyut") is None)
sina("Flow'da 'Yükselt' (plan) PARA", (tikla("Yükselt") or {}).get("sinif") == "para")
sina("Flow'da 'Sil' yine SILME", (tikla("Sil") or {}).get("sinif") == "silme")
sina("adres bilinmiyorken Flow'un dugme adi yeter",
     (tikla("Oluşturmaya başla", url="") or {}).get("sinif") == "kredi")
sina("alt alan adi da kredi sitesi (labs.google)", riskli.kredi_sitesi_mi("https://www.labs.google/fx/tr"))
sina("benzer ama baska alan adi DEGIL", not riskli.kredi_sitesi_mi("https://flow.google.com.kotu.site/"))

print("\n3. baska sitede ayni yazi")
sina("baska sitede 'Oluştur' sorulmaz", tikla("Oluştur", url="https://ornek.com/") is None)
sina("baska sitede Enter sorulmaz",
     riskli.degerlendir("browser_press_key", {"key": "Enter"}, url="https://www.google.com/") is None)

print("\n4. izin")
sina("kredi her zaman sorulan siniflarda (patronun sozu acmaz)", "kredi" in izin.HER_ZAMAN_SORULUR)
_k = izin.karttan_izin({"ayrinti": "sinif : kredi\ndesen : browser_click\n"})
sina("'bu projede hep' kredi kartindan VERILMEZ", not _k["verilebilir"], str(_k))

print("\n5. uretim ayari anlik goruntuden")
_h = {"e33": "text Ne oluşturmak istiyorsunuz?",
      "e34": "button Ayarlar tetikleyicisi : Video · 720p · 10 sn. x1",
      "e35": "button Oluşturmaya başla"}
sina("ayar okundu", riskli.uretim_ayari(_h) == "Video · 720p · 10 sn. x1", repr(riskli.uretim_ayari(_h)))
sina("ayar dugmesi yoksa bos", riskli.uretim_ayari({"e1": "button Oluşturmaya başla"}) == "")
sina("katalog: Nano Banana ucretsiz, video degil",
     F.ucretsiz_mi(RESIM_AYARI) and not F.ucretsiz_mi(VIDEO_AYARI))
sina("katalog: bilinmeyen model ucretsiz SAYILMAZ", not F.ucretsiz_mi("Yeni Model X · x1"))
sina("katalog: ayarda kredili model adi varsa ucretsiz SAYILMAZ",
     not F.ucretsiz_mi("Veo 3.1 - Quality · 9:16 · x1"))

print("\n6. vekil: okur, sorar, 'bu is boyunca' tuketilmez")
KOK = Path(tempfile.mkdtemp(prefix="ofis-kredi-"))
COCUK = KOK / "sahte_cocuk.py"
COCUK.write_text("import sys\nwhile True:\n    s = sys.stdin.readline()\n    if not s:\n        break\n",
                 encoding="utf-8")


class SahteVekil(K.Vekil):
    def __init__(self, harita) -> None:
        super().__init__([sys.executable, str(COCUK)])
        self.ajana, self.cocuga, self.harita = [], [], harita

    def sayfa_haritasi(self, zaman_asimi: float = 20.0):
        return self.harita

    def _ajana(self, nesne):
        self.ajana.append(nesne)

    def _cocuga(self, satir):
        self.cocuga.append(satir)


def cagri(arac, argumanlar, i=1):
    return json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                       "params": {"name": arac, "arguments": argumanlar}})


def son_metin(v) -> str:
    if not v.ajana:
        return ""
    return v.ajana[-1].get("result", {}).get("content", [{}])[0].get("text", "")


db = Veritabani(str(KOK / "o.sqlite3"))
o = Ofis.proje_ac(db, "Kredi", amac="a", basari_olcutu="b", kok_klasor=str(KOK))
o.kadro.ise_al("vera", "video", motor="sahte")
g = o.tahta.gorev_ac("Reels", neden="s", ana_hedef="s", kabul_olcutu="y", yazma_alani=["x"])
os.environ.update({"OFIS_DB": str(db.yol), "OFIS_PROJE": o.proje_id, "OFIS_AJAN": "vera",
                   "OFIS_GOREV": str(g["no"])})
v = SahteVekil(dict(_h))
try:
    v.durum.sonuctan_ogren(f"### Page\n- Page URL: {FLOW}\n")
    v.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}))
    bek = o.postane.bekleyen_onaylar("vera")
    sina("video uretimi DURDU (cocuga gitmedi)", not v.cocuga and len(bek) == 1, str(bek))
    sina("kartta ayar (vekil ekrandan okudu)", bek and VIDEO_AYARI in bek[0]["eylem"] + bek[0]["ayrinti"])
    sina("ajana senaryo paketini gondermesi soyleniyor", "sohbete_yaz" in son_metin(v)
         and "TOPLAM" in son_metin(v), son_metin(v)[:300])
    # Resim kipine gecildi: ayni dugme ucretsiz
    v.harita["e34"] = "button Ayarlar tetikleyicisi : " + RESIM_AYARI
    v.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}, 2))
    sina("resim uretimi SORULMADAN gecti", len(v.cocuga) == 1)
    v.harita["e34"] = "button Ayarlar tetikleyicisi : " + VIDEO_AYARI
    if bek:
        o.postane.onay_cevapla(bek[0]["id"], onayla=True, kapsam="is")
    for i in (3, 4, 5):
        v.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}, i))
    sina("'bu is boyunca' onayi: uc klip de gecti, yeni kart YOK",
         len(v.cocuga) == 4 and not o.postane.bekleyen_onaylar("vera"), f"{len(v.cocuga)}")
    # Baska is: onay oraya tasinmaz
    g2 = o.tahta.gorev_ac("Baska", neden="s", ana_hedef="s", kabul_olcutu="y", yazma_alani=["y"])
    os.environ["OFIS_GOREV"] = str(g2["no"])
    v2 = SahteVekil(dict(_h))
    v2.durum.sonuctan_ogren(f"- Page URL: {FLOW}\n")
    v2.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}, 6))
    sina("onay BASKA ISE tasinmaz", not v2.cocuga and len(o.postane.bekleyen_onaylar("vera")) == 1)
    b2 = o.postane.bekleyen_onaylar("vera")
    if b2:
        o.postane.onay_cevapla(b2[0]["id"], onayla=True)        # bir kez
    v2.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}, 7))
    v2.istegi_isle(cagri("browser_click", {"element": "Oluşturmaya başla", "target": "e35"}, 8))
    sina("'bir kez' onayi TUKENIR (ikinci klip yeniden sorulur)",
         len(v2.cocuga) == 1 and len(o.postane.bekleyen_onaylar("vera")) == 1, f"{len(v2.cocuga)}")
finally:
    for a in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV"):
        os.environ.pop(a, None)
    for x in [v] + ([v2] if "v2" in dir() else []):
        try:
            x.cocuk.stdin.close()
            x.cocuk.wait(timeout=5)
        except Exception:
            pass

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
