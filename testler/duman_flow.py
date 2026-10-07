# -*- coding: utf-8 -*-
"""FLOW KATALOGU (07.10.2026, Asama 5). Jeton ve kredi yakmaz; gercek Flow'a
DOKUNMAZ.

Gercek basliksiz Chrome, Flow'un ayar penceresini taklit eden yerel sayfaya
(`sahte_flow.html`, 07.10'da olculen rol/ad yapisi) baglanir. Sinanan: katalog
butun kip/tur/model/secenek bilesimlerini ve kredilerini dogru okur; kredi
bakiyesini okur; "Oluşturmaya başla"ya ve korumali dugmelere HIC basmaz;
fark (yeni/kalkan model, fiyat, secenek) dogru; kayit + gecmis + olay; ozet
metni olculmemisi soyler ve olcmedigi sureyi uydurmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import copy
import functools
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

KOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOD))

from ofis import Ofis, Veritabani, flow as F, kabin  # noqa: E402
from ofis.surec import PENCERE_YOK  # noqa: E402

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


print("1. koruma")
for ad in ("Oluşturmaya başla", "Projeyi sil", "Çöp kutusuna taşı", "Yükselt", "Paylaş",
           "Aboneliği yönet", "Tüm hesapların oturumlarını kapat"):
    sina(f"korumali: {ad}", not F._guvenli_mi(ad))
for ad in ("Model ailesi seçin", "720p", "Veo 3.1 - Quality", "Kareler", "9:16", "x1"):
    sina(f"serbest: {ad}", F._guvenli_mi(ad))

print("\n2. gercek Chrome + sahte Flow sayfasi")
d = Path(tempfile.mkdtemp(prefix="ofis-flow-"))
KAPI = 9394
ISTEKLER = []


class _Sessiz(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        ISTEKLER.append(self.path)
        return super().do_GET()


isleyici = functools.partial(_Sessiz, directory=str(Path(__file__).parent))
sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), isleyici)
threading.Thread(target=sunucu.serve_forever, daemon=True).start()
sayfa_url = f"http://127.0.0.1:{sunucu.server_address[1]}/sahte_flow.html"
krom = subprocess.Popen([kabin.calistirilabilir_bul(), "--headless=new", f"--remote-debugging-port={KAPI}",
                         f"--user-data-dir={d / 'profil'}", "--no-first-run", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=PENCERE_YOK)
kat, kalan = {}, None
try:
    for _ in range(60):
        if kabin.acik_mi(KAPI):
            break
        time.sleep(0.25)
    kat = F.olc(f"http://127.0.0.1:{KAPI}", proje_url=sayfa_url)
    # Sayfanin kendi bayraklari: uretim / tehlikeli dugme
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{KAPI}")
        sayfalar = [s for c in b.contexts for s in c.pages]
        sina("olcum sayfasi kapandi (iz birakmadi)", not any("sahte_flow" in s.url for s in sayfalar))
        # Flow son ayari hatirlar: olcum patronun ayarini DEGISTIRMIS kalmamali.
        s = b.contexts[0].new_page()
        s.goto(sayfa_url)
        kalan = s.evaluate("() => JSON.parse(localStorage.getItem('flowD') || 'null')")
        s.close()
    sina("ayarlar olcum oncesine GERI KONDU (Flow ayari hatirlar)",
         kat.get("ayarlar_geri_yuklendi") is True and kalan == {
             "kip": "Video", "tur": "İçerik öğeleri", "oran": "16:9", "model": "Omni 1.1 Flash",
             "coz": "720p", "sure": "10 sn.", "adet": "x2"}, f"{kat.get('ayarlar_geri_yuklendi')} {kalan}")
finally:
    try:
        kabin.cdp_kapat(KAPI)
    except Exception:
        pass
    krom.kill()
    sunucu.shutdown()

sina("'Oluşturmaya başla'ya HIC basilmadi (uretim yok)", "/URETILDI" not in ISTEKLER, str(ISTEKLER))
sina("projenin tehlikeli menusune ('Diğer seçenekler') dokunulmadi", "/TEHLIKE" not in ISTEKLER)
v = {(k["tur"], k["model"]): k for k in kat.get("video", [])}
print("  okunan video anahtarlari:", list(v))
r = {k["model"]: k for k in kat.get("resim", [])}
sina("kredi bakiyesi okundu (1.046)", kat.get("kredi_bakiyesi") == 1046, str(kat.get("kredi_bakiyesi")))
sina("video: 2 tur x 4 model", len(v) == 8, str(list(v)))
omni = v.get(("Kareler", "Omni 1.1 Flash"), {})
sina("Omni: 360p/720p ve 4 sure", omni.get("cozunurlukler") == ["360p", "720p"]
     and omni.get("sureler") == ["4 sn.", "6 sn.", "8 sn.", "10 sn."], str(omni)[:200])
bedel = {(b["cozunurluk"], b["sure"]): b["kredi"] for b in omni.get("bedel", [])}
sina("Omni bedelleri birebir (360p 4sn=4 ... 720p 10sn=15)",
     bedel.get(("360p", "4 sn.")) == 4 and bedel.get(("720p", "8 sn.")) == 12 and bedel.get(("720p", "10 sn.")) == 15,
     str(bedel))
q = v.get(("Kareler", "Veo 3.1 - Quality"), {})
sina("Veo Quality: sure secenegi yok, 100 kredi",
     q.get("sureler") == [] and [b["kredi"] for b in q.get("bedel", [])] == [100], str(q)[:200])
sina("resim: 3 model, emoji temizlendi, 5 oran, 0 kredi",
     set(r) == {"Nano Banana Pro", "Nano Banana 2 Lite", "Nano Banana 2.1"}
     and r["Nano Banana Pro"]["oranlar"] == ["16:9", "4:3", "1:1", "3:4", "9:16"]
     and r["Nano Banana Pro"]["bedel"][0]["kredi"] == 0, str(list(r)))

print("\n3. fark, kayit, ozet")
yeni = copy.deepcopy(kat)
yeni["video"] = [k for k in yeni["video"] if k["model"] != "Veo 3.1 - Lite"]
yeni["video"].append({"kip": "Video", "tur": "Kareler", "model": "Veo 4 - Ultra", "oranlar": ["9:16"],
                      "cozunurlukler": [], "sureler": [], "adetler": ["x1"], "bedel": [{"cozunurluk": None,
                                                                                         "sure": None, "kredi": 150}]})
for k in yeni["video"]:
    if k["model"] == "Veo 3.1 - Quality":
        k["bedel"] = [{"cozunurluk": None, "sure": None, "kredi": 80}]
fk = F.fark(kat, yeni)
sina("yeni model bulundu", any(x.startswith("YENI") and "Veo 4 - Ultra" in x for x in fk), str(fk))
sina("kalkan model bulundu", any(x.startswith("KALKTI") and "Veo 3.1 - Lite" in x for x in fk))
sina("fiyat degisimi bulundu", any(x.startswith("FIYAT") and "100 -> 80" in x for x in fk))
sina("ilk olcumde fark yok", F.fark({}, kat) == [])
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Flow", amac="a", basari_olcutu="b", kok_klasor=str(d))
sina("henuz olculmediyse SOYLER", "OLCULMEDI" in F.ozet_metni({}))
F.kaydet(kat, db, ofis.proje_id)
sina("katalog ofisin evine kaydedildi", F.oku().get("kredi_bakiyesi") == 1046 and F.KATALOG.is_file())
d2 = F.kaydet(yeni, db, ofis.proje_id)
with db.baglanti() as c:
    ol = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'flow_degisti'")]
sina("degisiklik olay olarak yazildi", len(ol) == 1 and "Veo 4 - Ultra" in ol[0], str(ol))
sina("gecmise yazildi", F.GECMIS.is_file() and "Veo 4 - Ultra" in F.GECMIS.read_text(encoding="utf-8"))
oz = F.ozet_metni()
sina("ozet: model, secenek ve kredi", "Veo 4 - Ultra" in oz and "150 kredi" in oz and "1046" in oz, oz)
_veo = [x for x in oz.splitlines() if "Veo" in x]
sina("ozet olcmedigi sureyi UYDURMAZ (Veo satirlarinda sure yok)",
     _veo and all("sure secenegi yok" in x and "sn" not in x.split("|")[0].replace("secenegi", "") for x in _veo),
     str(_veo))

print("\n4. kendiliginden tazeleme (gerekirse_olc) -- GERCEK kabine DOKUNULMAZ")
from ofis import guncelleme as _G  # noqa: E402
_acik, _mesgul = kabin.acik_mi, _G.mesgul
kabin.acik_mi = lambda *a, **k: (_ for _ in ()).throw(AssertionError("gercek kabine bakildi"))
OLCULEN = []


def _sahte_olcer(cdp):
    OLCULEN.append(cdp)
    k = copy.deepcopy(kat)
    k["olculdu"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return k


try:
    F._son_deneme["an"] = 0.0
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", olcer=_sahte_olcer)
    sina("taze katalog yeniden OLCULMEZ", not r["yapildi"] and "taze" in r["sebep"] and not OLCULEN, str(r))
    # Bayat katalog: 30 saat once
    eski = F.oku()
    eski["olculdu"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 30 * 3600))
    F.KATALOG.write_text(json.dumps(eski, ensure_ascii=False), encoding="utf-8")
    kabin.acik_mi = lambda *a, **k: False
    r = F.gerekirse_olc(db, ofis.proje_id, olcer=_sahte_olcer)
    sina("tarayici kapaliysa ACILMAZ, olculmez", not r["yapildi"] and "kapali" in r["sebep"] and not OLCULEN, str(r))
    _G.mesgul = lambda *a, **k: "1 is calisiyor"
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", olcer=_sahte_olcer)
    sina("ofis mesgulken olculmez (ajan tarayiciyi kullaniyor olabilir)",
         not r["yapildi"] and "mesgul" in r["sebep"] and not OLCULEN, str(r))
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", zorla=True, olcer=_sahte_olcer)
    sina("zorla bile mesgul sartini KALDIRMAZ", not r["yapildi"] and not OLCULEN, str(r))
    _G.mesgul = lambda *a, **k: ""
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", olcer=_sahte_olcer)
    sina("bayat + bos + tarayici: olculur ve kaydedilir",
         r["yapildi"] and OLCULEN == ["http://127.0.0.1:1"] and (F.yas_saat() or 99) < 1, str(r))
    with db.baglanti() as c:
        sina("olcum olay olarak gorunur", c.execute(
            "SELECT COUNT(*) FROM olay WHERE tur = 'flow_olcum'").fetchone()[0] == 1)

    def _patlayan(cdp):
        raise F.FlowHatasi("giris yapilmamis")

    F.KATALOG.write_text(json.dumps(eski, ensure_ascii=False), encoding="utf-8")
    F._son_deneme["an"] = 0.0
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", olcer=_patlayan)
    with db.baglanti() as c:
        _u = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'uyari'")]
    sina("olculemezse SOYLENIR (uyari olayi)", not r["yapildi"] and any("giris yapilmamis" in x for x in _u), str(_u))
    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", olcer=_sahte_olcer)
    sina("basarisiz denemeden sonra hemen yeniden DENENMEZ", not r["yapildi"] and "yakin" in r["sebep"], str(r))

    def _geri_konamayan(cdp):
        k = _sahte_olcer(cdp)
        k["ayarlar_geri_yuklendi"] = False
        return k

    r = F.gerekirse_olc(db, ofis.proje_id, cdp="http://127.0.0.1:1", zorla=True, olcer=_geri_konamayan)
    with db.baglanti() as c:
        _u = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'uyari'")]
    sina("ayarlar geri konamadiysa patrona SOYLENIR", any("geri KONAMADI" in x for x in _u), str(_u))
finally:
    kabin.acik_mi, _G.mesgul = _acik, _mesgul

print("\n5. lider ve video ajani katalogu GORUR")
from ofis import gorsel as _gorsel, roller as _roller  # noqa: E402
_lb = _gorsel.lider_blogu()
sina("liderin medya blogunda Flow katalogu (tek satir: model -> kredi)",
     "FLOW KATALOGU" in _lb and "Veo 3.1 - Quality 100" in _lb and "Omni 1.1 Flash 4-15" in _lb,
     _lb[-400:])
# Blok HER triyajda koşar: olculmus katalogla da sinirli kalmali. Tavan
# SISMEYI yakalar, bilgi kesmek icin degil (07.10 patron: guc kisma).
sina("olculmus katalogla lider blogu ~450 jetonun altinda", len(_lb) // 4 < 450, f"(~{len(_lb) // 4})")
ofis.kadro.ise_al("Vera", "video", motor="sahte")
ofis.kadro.ise_al("Bora", "backend", motor="sahte")
_bk = ofis.brifing
sina("video ajaninin brifinginde katalog", "FLOW KATALOGU" in _bk.k1_anayasa("vera"))
sina("ilgisiz rolun brifingine GIRMEZ (baglam sismesin)", "FLOW KATALOGU" not in _bk.k1_anayasa("bora"))
sina("Flow rolleri rol kutuphanesinde tanimli", set(_roller.FLOW_ROLLERI) <= set(_roller.ROLLER))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
