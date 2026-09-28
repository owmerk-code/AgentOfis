# -*- coding: utf-8 -*-
"""Efor tavani + zorluk->efor + YENI MODEL / CLI guncelleme akisi.

Uc soru sinaniyor:

1. **Zorluk eforu belirliyor mu, tavan insanin mi, `max` gercekten
   kapali mi** -- ve belirlenen efor MOTORA ULASIYOR mu.
2. **Yeni model/CLI dogru fark ediliyor mu** -- ve fark EDILMEMESI
   gerekenler (kapi modeli, emekliye ayrilan, takma adin hedefi) gurultu
   uretmiyor mu. Bildirim gurultuye bogulursa insan bakmayi birakir.
3. **Onaylanan oneri once DENEME turu kosuyor mu, dusunce ESKISI kaliyor
   mu, CLI geri aliniyor mu.** Onaysiz hicbir sey degismiyor mu.

YALITIM SART: gercek katalog, gercek codex evleri ve gercek `npm` hic
kullanilmaz. Kullanicinin makinesi bir sinamanin sonucunu degistirmemeli
-- ve bir sinama kullanicinin makinesine HICBIR sey kurmamali.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis import guncelleme as G
from ofis import roller as R
from ofis.motor.sahte import SahteMotor
from ofis.saglik import Saglik

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


kok = Path(tempfile.mkdtemp(prefix="ofis-guncelleme-"))
print(f"klasor: {kok}")

# ------------------------------------------------------------ yalitim
KOMUTLAR = []
SURUM = {"claude": "2.1.280", "codex": "0.154.0", "gemini": "0.60.0"}
NPM = {"@anthropic-ai/claude-code": "2.1.280", "@openai/codex": "0.156.0",
       "@google/gemini-cli": "0.60.0"}


def _sahte_komut(argv, zaman_asimi=60):
    KOMUTLAR.append(list(argv))
    if argv[1:] == ["--version"]:
        return 0, SURUM.get(argv[0], "")
    if argv[:2] == ["npm", "view"]:
        return 0, NPM.get(argv[2], "")
    if argv[:3] == ["npm", "install", "-g"]:
        paket, surum = argv[3].rsplit("@", 1)
        motor = {v: k for k, v in G.PAKETLER.items()}[paket]
        SURUM[motor] = surum
        return 0, "kuruldu"
    return 1, "bilinmeyen komut"


G._komut = _sahte_komut

claude_dizin = kok / "claude-katalog"
claude_dizin.mkdir()
G.CLAUDE_KATALOG_DESENI = str(claude_dizin / "*.json")
codex_ev = kok / "codex-ev"
codex_ev.mkdir()
G.CODEX_EK_EVLER = []
G.codex_evleri = lambda db, pid: [str(codex_ev)]


def claude_katalog_yaz(opus_hedef="claude-opus-5-5"):
    modeller = [
        {"id": opus_hedef, "name": "Opus", "short_name": "Opus", "section": "main"},
        {"id": "claude-opus-5", "name": "Opus 5", "short_name": "Opus", "section": "main"},
        {"id": "claude-fable-5-1", "name": "Fable 5.1", "short_name": "Fable", "section": "main"},
        {"id": "claude-sonnet-5", "name": "Sonnet 5", "short_name": "Sonnet", "section": "main"},
        {"id": "claude-haiku-4-5-20251001", "name": "Haiku 4.5", "short_name": "Haiku",
         "section": "main"},
        {"id": "claude-opus-4-8", "name": "Opus 4.8", "short_name": "Opus", "section": "overflow"},
    ]
    (claude_dizin / "k.json").write_text(json.dumps(
        {"catalog": {"config": {"models": modeller}}}), encoding="utf-8")


def codex_katalog_yaz(ek=()):
    modeller = [
        {"slug": "gpt-6-astra", "visibility": "list", "priority": 1},
        {"slug": "gpt-6-sol", "visibility": "list", "priority": 2},
        {"slug": "gpt-6-luna", "visibility": "list", "priority": 3},
        {"slug": "gpt-reserve", "visibility": "hide", "priority": 3},
        {"slug": "gpt-5.6-sol", "visibility": "list", "priority": 4},
        {"slug": "gpt-5.6-terra", "visibility": "list", "priority": 7},
        {"slug": "gpt-5.6-luna", "visibility": "list", "priority": 8},
        {"slug": "gpt-5.5", "visibility": "list", "priority": 12,
         "upgrade": {"model": "gpt-5.6-sol", "retirement_at": "2026-10-14T19:00:00Z"}},
        *ek,
    ]
    (codex_ev / "models_cache.json").write_text(
        json.dumps({"models": modeller}), encoding="utf-8")


claude_katalog_yaz()
codex_katalog_yaz()

ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Guncelleme",
                     amac="guncelleme sinamasi", basari_olcutu="testler gecer")
(kok / "w").mkdir()
ofis.kadro.ise_al("demir", "lider", lider_mi=True, motor="claude", model="opus",
                  klasor=str(kok / "w"))
ofis.kadro.ise_al("cinar", "backend", motor="codex", model="gpt-5.6-sol",
                  klasor=str(kok / "w"))
ofis.kadro.ise_al("yaprak", "backend", motor="claude", model="sonnet",
                  klasor=str(kok / "w"))
db, pid = ofis.db, ofis.proje_id
# 1-7. bolumler ONAYLI yolu (otomatik mod KAPALI) olcer; otomatik mod 8.
# bolumde ayrica sinanir. Varsayilan ACIK -- o da burada sinaniyor.
sina("otomatik mod VARSAYILAN olarak acik", G.otomatik_mi(db, pid))
G.otomatik_ayarla(db, pid, False)

# ------------------------------------------------------ 1. efor kurallari
print("\n1. EFOR -- zorluk belirler, tavan insanin, max YOK")

sina("max efor sozlugunde YOK", "max" not in R.EFOR_SIRASI
     and "max" not in R.ZORLUK_EFOR.values())
try:
    R.efor_tavani_yaz(db, pid, "max")
    sina("tavan 'max' REDDEDILIYOR", False)
except R.RolHatasi:
    sina("tavan 'max' REDDEDILIYOR", True)
sina("varsayilan tavan cok_yuksek (cok_zor olu dogmasin)",
     R.efor_tavani(db, pid) == "cok_yuksek")
sina("cok_zor -> guclu kademe + cok_yuksek",
     R.ZORLUK_KADEME["cok_zor"] == "guclu" and R.ZORLUK_EFOR["cok_zor"] == "cok_yuksek")
sina("tavan yuksek: zor -> yuksek", R.etkin_efor("yuksek", "yuksek") == "yuksek")
sina("tavan normal: zor -> normal", R.etkin_efor("yuksek", "normal") == "normal")
sina("tavan normal: kolay -> dusuk (tavan ALTINDAKINE dokunmaz)",
     R.etkin_efor("dusuk", "normal") == "dusuk")
sina("taninmayan istek normal'e duser", R.etkin_efor("max", "yuksek") == "normal")


class _Kaydeden(SahteMotor):
    son = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


_f = lambda ad, **kw: _Kaydeden(cevap="Bitti.\nKANIT terminal: x -> ok")  # noqa: E731

g1 = ofis.tahta.gorev_ac("Zor", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="zor", zorluk_gerekce="ince hata avi")
Koltuk(ofis, motor_fabrikasi=_f).kos(g1["no"], "yaprak")
sina("ZOR is motora 'yuksek' efor GONDERDI", _Kaydeden.son.get("efor") == "yuksek",
     str(_Kaydeden.son.get("efor")))

g2 = ofis.tahta.gorev_ac("Kolay", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="kolay")
Koltuk(ofis, motor_fabrikasi=_f).kos(g2["no"], "yaprak")
sina("KOLAY is motora 'dusuk' efor GONDERDI", _Kaydeden.son.get("efor") == "dusuk",
     str(_Kaydeden.son.get("efor")))

_Kaydeden.son = {}
try:
    g4 = ofis.tahta.gorev_ac("Cok zor", neden="s", ana_hedef="s", kabul_olcutu="y",
                             zorluk="çok zor", zorluk_gerekce="mimari karar")
    Koltuk(ofis, motor_fabrikasi=_f).kos(g4["no"], "yaprak")
except Exception as exc:          # COKMEZ, KALIR -- bkz. no_bul notu
    sina("'çok zor' yazimi KABUL edildi", False, str(exc))
sina("'cok zor' yazimi normallesti ve 'cok_yuksek' GONDERILDI",
     _Kaydeden.son.get("efor") == "cok_yuksek", str(_Kaydeden.son.get("efor")))
sina("cok_zor GUCLU modele gitti", _Kaydeden.son.get("model") == "opus",
     str(_Kaydeden.son.get("model")))
try:
    ofis.tahta.gorev_ac("Gerekcesiz", neden="s", ana_hedef="s", kabul_olcutu="y",
                        zorluk="cok_zor")
    sina("gerekcesiz cok_zor REDDEDILIYOR", False)
except Exception:
    sina("gerekcesiz cok_zor REDDEDILIYOR", True)
from ofis.motor.claude import EFOR_CEVRIMI as _CC                 # noqa: E402
from ofis.motor.codex import EFOR_CEVRIMI as _XC                  # noqa: E402
sina("adaptorler cok_yuksek -> xhigh, max HICBIRINDE yok",
     _CC["cok_yuksek"] == "xhigh" == _XC["cok_yuksek"]
     and "max" not in _CC.values() and "max" not in _XC.values())

# EFOR MODU -- panelin dugmesi: sabit secilince BUTUN turlar o seviyede
R.efor_modu_yaz(db, pid, "normal")
g5 = ofis.tahta.gorev_ac("Kolay sabit", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="kolay")
Koltuk(ofis, motor_fabrikasi=_f).kos(g5["no"], "yaprak")
sina("'hepsi medium': KOLAY is de normal'de kostu",
     _Kaydeden.son.get("efor") == "normal", str(_Kaydeden.son.get("efor")))
R.efor_modu_yaz(db, pid, "yuksek")
g6 = ofis.tahta.gorev_ac("Kolay sabit2", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="kolay")
Koltuk(ofis, motor_fabrikasi=_f).kos(g6["no"], "yaprak")
sina("'hepsi high': KOLAY is yuksek'te kostu",
     _Kaydeden.son.get("efor") == "yuksek", str(_Kaydeden.son.get("efor")))
sina("lider/danisma/kapi da ayni islevden gecer (tur_eforu)",
     R.tur_eforu(db, pid, "dusuk") == "yuksek")
try:
    R.efor_modu_yaz(db, pid, "max")
    sina("efor modu 'max' REDDEDILIYOR", False)
except R.RolHatasi:
    sina("efor modu 'max' REDDEDILIYOR", True)
R.efor_modu_yaz(db, pid, "zorluk")

R.efor_tavani_yaz(db, pid, "normal")
g3 = ofis.tahta.gorev_ac("Zor2", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="zor", zorluk_gerekce="yine zor")
Koltuk(ofis, motor_fabrikasi=_f).kos(g3["no"], "yaprak")
sina("TAVAN normal iken zor is 'normal'de kostu", _Kaydeden.son.get("efor") == "normal",
     str(_Kaydeden.son.get("efor")))
with db.baglanti() as conn:
    efor_olaylari = [r["govde"] for r in conn.execute(
        "SELECT govde FROM olay WHERE proje_id=? AND tur='efor'", (pid,))]
sina("tavanin sinirladigi GORUNUR (olay)",
     any("sinirladi" in o for o in efor_olaylari), str(efor_olaylari[-1:]))
R.efor_tavani_yaz(db, pid, "cok_yuksek")

# PANEL: dugme ayara yaziyor, kural sunucuda
from fastapi.testclient import TestClient                          # noqa: E402
from ofis.panel import olustur                                     # noqa: E402
ist = TestClient(olustur(kok / "o.sqlite3"))
sina("panel efor modunu okuyor", ist.get("/api/efor").json().get("mod") == "zorluk")
sina("panel 'hepsi high' yaziyor",
     ist.post("/api/efor", json={"mod": "yuksek"}).status_code == 200
     and R.efor_modu(db, pid) == "yuksek")
sina("panel 'max' REDDEDIYOR (400)",
     ist.post("/api/efor", json={"mod": "max"}).status_code == 400)
ist.post("/api/efor", json={"mod": "zorluk"})

# ------------------------------------------------ 2. kademe ayari
print("\n2. KADEME -- kod degil ayar")

sina("ayar yokken harita = kod varsayilani",
     R.kademe_haritasi(db, pid)["codex"]["guclu"] == R.KADEME_MODEL["codex"]["guclu"])
for kotu, beklenen in ((("codex", "guclu", "gpt-6-astra"), "kapi"),
                       (("codex", "guclu", ""), "bos"),
                       (("codex", "sihirli", "gpt-6-sol"), "kademe")):
    try:
        R.kademe_yaz(db, pid, *kotu)
        sina(f"kademeye {beklenen} REDDEDILIYOR", False)
    except R.RolHatasi:
        sina(f"kademeye {beklenen} REDDEDILIYOR", True)

# ------------------------------------------------ 3. fark etme
print("\n3. FARK ETME -- dogru olanlar var, gurultu yok")

s = G.kontrol(db, pid)
o = {x["anahtar"]: x for x in s["oneriler"]}
sina("codex CLI guncellemesi onerildi", "cli:codex:0.156.0" in o, str(list(o)))
sina("guncel olan CLI onerilMEDI", not any(k.startswith("cli:claude") for k in o))
sol = o.get("model:codex:gpt-5.6-sol->gpt-6-sol")
sina("gpt-5.6-sol -> gpt-6-sol onerildi (ayni aile)", bool(sol))
sina("oneri KADEMEYI ve AJANI biliyor",
     bool(sol) and sol["kademeler"] == ["guclu"] and sol["ajanlar"] == ["cinar"],
     str(sol))
sina("gpt-5.6-luna -> gpt-6-luna onerildi", "model:codex:gpt-5.6-luna->gpt-6-luna" in o)
sina("yeni nesli olmayan terra icin oneri YOK",
     not any("gpt-5.6-terra->" in k for k in o))
sina("KAPI modeli (astra) onerilMEDI", not any("astra" in k for k in o))
sina("EMEKLIYE AYRILAN gpt-5.5 'yeni model' diye onerilMEDI",
     not any(k.endswith(":gpt-5.5") for k in o))
sina("GIZLI model onerilMEDI", not any("gpt-reserve" in k for k in o))
sina("takma adin HEDEFI (opus -> 5-5) 'yeni model' SAYILMADI",
     not any("claude-opus-5-5" in k for k in o), str(list(o)))
sina("ilk olcumde takma ad degisimi URETILMEDI",
     not any(k.startswith("takma_ad") for k in o))
sina("saglik bekleyeni GOSTERIYOR (insan)",
     any("guncelleme" in b["baslik"] and b["agirlik"] == "insan"
         for b in Saglik(ofis).denetle()["bulgular"]))

# yeni AILE + emeklilik
codex_katalog_yaz(ek=[{"slug": "gpt-6-nova", "visibility": "list", "priority": 5}])
ofis.kadro.ise_al("eski", "backend", motor="codex", model="gpt-5.5",
                  klasor=str(kok / "w"))
o = {x["anahtar"]: x for x in G.kontrol(db, pid)["oneriler"]}
sina("yeni AILE (nova) kademesiz oneri olarak geldi",
     "yeni_model:codex:gpt-6-nova" in o, str(list(o)))
emek = o.get("model:codex:gpt-5.5->gpt-5.6-sol")
sina("kullanilan modelin EMEKLILIGI tarihiyle onerildi",
     bool(emek) and "EMEKLILIK" in emek["sebep"] and "2026-10-14" in emek["sebep"],
     str(emek))

# ------------------------------------------------ 4. uygulama: model
print("\n4. UYGULAMA -- once deneme, dusen UYGULANMAZ")

def no_bul(anahtar):
    # CIPLAK next() KULLANILMAZ: oneri beklenmedik bicimde kaybolursa test
    # COKMEMELI, kalmali -- coken test geri kalan sinamalari hic kosturmaz
    # (mutasyon denetimi bunu gosterdi).
    for x in G.bekleyenler(db, pid):
        if x["anahtar"] == anahtar:
            return x["no"]
    sina(f"oneri bekliyor: {anahtar}", False)
    return -1


def uygula_guvenli(no, **kw):
    try:
        return G.uygula(ofis, no, **kw)
    except G.GuncellemeHatasi as exc:
        return {"basarili": False, "mesaj": f"HATA: {exc}"}


tamam = lambda ad, **kw: SahteMotor(cevap="OK")          # noqa: E731
bozuk = lambda ad, **kw: SahteMotor(senaryo="hata")      # noqa: E731
laf = lambda ad, **kw: SahteMotor(cevap="merhaba dunya")  # noqa: E731

r = uygula_guvenli(no_bul("model:codex:gpt-5.6-luna->gpt-6-luna"), fabrika=bozuk)
sina("deneme DUSUNCE uygulanmadi", not r["basarili"], r["mesaj"])
sina("dusen denemeden sonra kademe ESKISINDE",
     R.kademe_haritasi(db, pid)["codex"]["hizli"] == "gpt-5.6-luna")
sina("dusen oneri hala BEKLIYOR",
     any(x["anahtar"].endswith("gpt-6-luna") for x in G.bekleyenler(db, pid)))

r = uygula_guvenli(no_bul("model:codex:gpt-5.6-luna->gpt-6-luna"), fabrika=laf)
sina("beklenen cevap gelmeyince de uygulanmadi", not r["basarili"], r["mesaj"])

r = uygula_guvenli(no_bul("model:codex:gpt-5.6-sol->gpt-6-sol"), fabrika=tamam)
sina("deneme GECINCE uygulandi", r["basarili"], r["mesaj"])
sina("kademe YENI modelde",
     R.kademe_haritasi(db, pid)["codex"]["guclu"] == "gpt-6-sol")
sina("ajan (cinar) YENI modelde", ofis.kadro.ajan("cinar")["model"] == "gpt-6-sol")
sina("uygulanan oneri bir daha GELMIYOR",
     not any(x["anahtar"].endswith("gpt-6-sol") and "5.6-sol" in x["anahtar"]
             for x in G.kontrol(db, pid)["oneriler"]))
with db.baglanti() as conn:
    kararlar = [r2["karar"] for r2 in conn.execute(
        "SELECT karar FROM karar WHERE proje_id=?", (pid,))]
sina("gecis KARAR GUNLUGUNE yazildi", any("gpt-6-sol" in k for k in kararlar))

nova = no_bul("yeni_model:codex:gpt-6-nova")
try:
    G.uygula(ofis, nova, fabrika=tamam)
    sina("yeni AILE kademesiz UYGULANMIYOR", False)
except G.GuncellemeHatasi:
    sina("yeni AILE kademesiz UYGULANMIYOR", True)
r = uygula_guvenli(nova, kademe="standart", fabrika=tamam)
sina("yeni aile secilen kademeye girdi",
     r["basarili"] and R.kademe_haritasi(db, pid)["codex"]["standart"] == "gpt-6-nova")

# ------------------------------------------------ 5. uygulama: CLI
print("\n5. CLI -- guncelle, olc, dene; dusunce GERI AL")

cli = no_bul("cli:codex:0.156.0")
KOMUTLAR.clear()
r = uygula_guvenli(cli, fabrika=tamam)
sina("CLI guncellendi ve deneme gecti", r["basarili"] and SURUM["codex"] == "0.156.0",
     r["mesaj"])
sina("dogru paket@surum kuruldu",
     ["npm", "install", "-g", "@openai/codex@0.156.0"] in KOMUTLAR)

NPM["@anthropic-ai/claude-code"] = "2.1.290"
G.kontrol(db, pid)
cla = no_bul("cli:claude:2.1.290")
KOMUTLAR.clear()
r = uygula_guvenli(cla, fabrika=bozuk)
sina("deneme dusen CLI UYGULANMADI", not r["basarili"], r["mesaj"])
sina("ESKI surume GERI donuldu",
     ["npm", "install", "-g", "@anthropic-ai/claude-code@2.1.280"] in KOMUTLAR
     and SURUM["claude"] == "2.1.280", str(KOMUTLAR))

# Gemini defterden cikarildi (24.09.2026): kullanilmayan CLI icin
# guncelleme ONERILMEZ -- insanin kuyrugunu bosuna doldururdu.
sina("gemini CLI guncellemesi ONERILMIYOR",
     "gemini" not in G.PAKETLER
     and not any("cli:gemini" in x["anahtar"]
                 for x in G.kontrol(db, pid)["oneriler"]))

# ------------------------------------------------ 6. takma ad + ret
print("\n6. TAKMA AD kaymasi SESSIZ degil; ret sabitler")

claude_katalog_yaz(opus_hedef="claude-opus-6")
o = {x["anahtar"]: x for x in G.kontrol(db, pid)["oneriler"]}
tk = o.get("takma_ad:opus:claude-opus-6")
sina("`opus` kaymasi BILDIRILDI", bool(tk) and tk["eski"] == "claude-opus-5-5", str(tk))
sina("kaymanin hedefi ayrica 'yeni model' diye TEKRARLANMADI",
     "yeni_model:claude:claude-opus-6" not in o)
try:
    G.reddet(ofis, tk["no"], "")
    sina("gerekcesiz ret REDDEDILIYOR", False)
except G.GuncellemeHatasi:
    sina("gerekcesiz ret REDDEDILIYOR", True)
G.reddet(ofis, tk["no"], "once maliyetini olcelim")
sina("ret: kademe ESKI hedefe SABITLENDI",
     R.kademe_haritasi(db, pid)["claude"]["guclu"] == "claude-opus-5-5")
sina("ret: `opus` yazili ajan da SABITLENDI",
     ofis.kadro.ajan("demir")["model"] == "claude-opus-5-5")
sina("ret: takma adin SABITI eski hedefte kaldi",
     G.model_coz(db, pid, "claude", "opus") == "claude-opus-5-5")
sina("reddedilen bir daha GELMIYOR",
     not any(x["anahtar"] == tk["anahtar"] for x in G.kontrol(db, pid)["oneriler"]))

# Karar kaydinin ASIL isi: durumu DEGISTIRMEYEN ret. Luna reddedilirse
# kademe eskisinde kalir ve oneri kosulu hala dogrudur -- onu bir daha
# getirmeyen tek sey kayda gecen karardir.
luna = no_bul("model:codex:gpt-5.6-luna->gpt-6-luna")
if luna > 0:
    G.reddet(ofis, luna, "hiz bizim icin onemli degil")
sina("durumu degistirmeyen ret bir daha GELMIYOR",
     not any(x["anahtar"] == "model:codex:gpt-5.6-luna->gpt-6-luna"
             for x in G.kontrol(db, pid)["oneriler"]))
sina("ret sonrasi kademe ESKISINDE kaldi",
     R.kademe_haritasi(db, pid)["codex"]["hizli"] == "gpt-5.6-luna")

# ------------------------------------------------ 7. zincir yedegi
print("\n7. ZINCIR yedek basamagi da ONAYLANMIS haritayi kullaniyor")
from ofis.zincir import zincir_kur                                 # noqa: E402

_hep = lambda ad, **kw: SahteMotor()                               # noqa: E731
b = zincir_kur({"motor": "claude", "model": "sonnet", "meslek": "backend"},
               zincir=(("codex", ""),), fabrika=_hep,
               kademe_haritasi=R.kademe_haritasi(db, pid))
kod = [x for x in b if x["motor"] == "codex"]
sina("codex yedegi onaylanan kademe modelini aldi",
     bool(kod) and kod[0]["model"] == R.kademe_haritasi(db, pid)["codex"][
         R.rol("backend").kademe], str(kod))

# ------------------------------------------------ 8. OTOMATIK MOD
print("\n8. OTOMATIK MOD -- sormadan dener, gorunur uygular, geri alinir")

kok8 = Path(tempfile.mkdtemp(prefix="ofis-guncelleme-oto-"))
(kok8 / "w").mkdir()
claude_katalog_yaz()
codex_katalog_yaz()
SURUM.update({"claude": "2.1.280", "codex": "0.156.0"})
NPM.update({"@anthropic-ai/claude-code": "2.1.280", "@openai/codex": "0.156.0"})
of8 = Ofis.proje_ac(Veritabani(kok8 / "o.sqlite3"), "Oto",
                    amac="otomatik guncelleme", basari_olcutu="testler gecer")
of8.kadro.ise_al("lale", "lider", lider_mi=True, motor="claude", model="opus",
                 klasor=str(kok8 / "w"))
of8.kadro.ise_al("su", "backend", motor="claude", model="sonnet",
                 klasor=str(kok8 / "w"))
of8.kadro.ise_al("ay", "backend", motor="codex", model="gpt-6-sol",
                 klasor=str(kok8 / "w"))
d8, p8 = of8.db, of8.proje_id

# ilk olcum: sabit kurulur, oneri yok
G.kontrol(d8, p8, npm=False)
sina("ilk olcumde takma ad SABITLENDI (sonnet -> claude-sonnet-5)",
     d8.ayar_oku(p8, G.TAKMA_AD_ONEKI + "sonnet", "") == "claude-sonnet-5")
sina("model_coz takma adi SABITE ceviriyor",
     G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5")
sina("model_coz gercek kimlige ve codex'e DOKUNMUYOR",
     G.model_coz(d8, p8, "claude", "claude-opus-5") == "claude-opus-5"
     and G.model_coz(d8, p8, "codex", "sonnet") == "sonnet")

# ZINCIR: ajanin turu takma adla degil SABIT kimlikle kurulur
from ofis.zincir import basamaklari_kur                          # noqa: E402
_her = lambda ad, **kw: SahteMotor()                             # noqa: E731
b8, _ = basamaklari_kur(d8, p8, of8.kadro.ajan("su"), fabrika=_her, zincir=())
sina("zincirin ILK basamagi sabit kimlikle kuruldu",
     bool(b8) and b8[0]["model"] == "claude-sonnet-5", str(b8[:1]))

# Katalog yeni hedefi gosterdi: ajan KAYMAZ, bu bir ONERI olur
kat = json.loads((claude_dizin / "k.json").read_text(encoding="utf-8"))
kat["catalog"]["config"]["models"] = [
    dict(m, id="claude-sonnet-5-5") if m["id"] == "claude-sonnet-5" else m
    for m in kat["catalog"]["config"]["models"]] + [
    {"id": "claude-sonnet-5", "name": "Sonnet 5", "short_name": "Sonnet",
     "section": "overflow"}]
(claude_dizin / "k.json").write_text(json.dumps(kat), encoding="utf-8")
# Gercek ofisteki gibi: standart kademe gpt-6-sol, terra HICBIR yerde
# kullanilmiyor (yanlis alarmin cikti sahne).
R.kademe_yaz(d8, p8, "codex", "standart", "gpt-6-sol")
s8 = G.kontrol(d8, p8, npm=False)
o8 = {x["anahtar"]: x for x in s8["oneriler"]}
sina("sonnet kaymasi ONERI oldu", "takma_ad:sonnet:claude-sonnet-5-5" in o8, str(list(o8)))
sina("kayma varken ajan HALA eski kimlikte (sessiz kayma yok)",
     G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5")
sina("ESKI NESIL (gpt-5.6-terra) 'yeni model' SAYILMADI",
     not any("gpt-5.6-terra" in k for k in o8), str(list(o8)))

# insana dusenler: otomatik aciksa kayma insana DUSMEZ
sina("otomatik acikken kayma INSANA DUSMUYOR",
     not any(x["anahtar"].startswith("takma_ad") for x in G.insana_dusenler(d8, p8)))
G.otomatik_ayarla(d8, p8, False)
sina("otomatik KAPALIYKEN insana dusuyor",
     any(x["anahtar"].startswith("takma_ad") for x in G.insana_dusenler(d8, p8)))
sina("otomatik kapaliyken otomatik_ilerle HICBIR SEY yapmiyor",
     G.otomatik_ilerle(of8, fabrika=tamam) == []
     and G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5")
G.otomatik_ayarla(d8, p8, True)

# deneme DUSERSE: eskisi kalir, bir daha otomatik denenmez, insana duser
r8 = G.otomatik_ilerle(of8, fabrika=bozuk)
sina("dusen otomatik deneme UYGULANMADI",
     bool(r8) and not r8[0]["basarili"]
     and G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5", str(r8))
sina("dusen oneri INSANA DUSTU (sebebiyle)",
     any(x["anahtar"].startswith("takma_ad") and x.get("otomatik_dustu")
         for x in G.insana_dusenler(d8, p8)))
sina("dusen oneri bir daha KENDILIGINDEN denenmiyor",
     G.otomatik_ilerle(of8, fabrika=tamam) == [])
with d8.baglanti() as c:
    sina("dusme OLAY olarak gorunur",
         bool(c.execute("SELECT 1 FROM olay WHERE tur='guncelleme_dustu'").fetchone()))

# insan onaylarsa: takma ad icin de DENEME TURU kosar (once kosmuyordu)
calisan = []


def izle(ad, **kw):
    calisan.append(ad)
    return SahteMotor(cevap="OK")


no8 = next((x["no"] for x in G.bekleyenler(d8, p8)
            if x["anahtar"].startswith("takma_ad")), -1)
try:
    r = G.uygula(of8, no8, fabrika=izle)
except G.GuncellemeHatasi as exc:
    r = {"basarili": False, "mesaj": str(exc)}
sina("takma ad onayinda DENEME TURU kostu", calisan == ["claude"], str(calisan))
sina("onaydan sonra ajan YENI kimlikte",
     bool(r.get("basarili"))
     and G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5-5", str(r))
g = G.gecmis(d8, p8)
sina("uygulama GECMISE yazildi (eski/yeni, kim)",
     bool(g) and g[-1]["eski"] == "claude-sonnet-5"
     and g[-1]["yeni"] == "claude-sonnet-5-5" and g[-1]["veren"] == "insan", str(g[-1:]))
sina("gorulmemisler arasinda (panel karti)",
     bool(g) and any(k["sira"] == g[-1]["sira"] for k in G.gorulmemisler(d8, p8)))

# GERI AL: eskisi geri gelir, bir daha kendiliginden gelmez
if g:
    G.geri_al(of8, g[-1]["sira"], sebep="kalite dusuk")
sina("geri alma KARAR kaydina 'geri_alindi' olarak yazildi",
     d8.ayar_oku(p8, G.KARAR_ONEKI + "takma_ad:sonnet:claude-sonnet-5-5", "")
     .startswith("geri_alindi"))
sina("GERI AL: ajan ESKI kimlikte",
     G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5")
sina("geri alinan bir daha ONERILMIYOR",
     not any(x["anahtar"].startswith("takma_ad:sonnet")
             for x in G.kontrol(d8, p8, npm=False)["oneriler"]))
sina("geri alinan otomatikte de UYGULANMIYOR",
     G.otomatik_ilerle(of8, fabrika=tamam) == []
     and G.model_coz(d8, p8, "claude", "sonnet") == "claude-sonnet-5")
try:
    G.geri_al(of8, g[-1]["sira"] if g else -1)
    sina("ikinci geri alma REDDEDILIYOR", False)
except G.GuncellemeHatasi:
    sina("ikinci geri alma REDDEDILIYOR", True)

# OTOMATIK BASARI: ayni aile (codex) + CLI, sormadan, sirayla (once CLI)
codex_katalog_yaz(ek=[{"slug": "gpt-7-sol", "visibility": "list", "priority": 0}])
NPM["@openai/codex"] = "0.158.0"
G.kontrol(d8, p8)
r8 = G.otomatik_ilerle(of8, fabrika=tamam)
sira8 = [x["anahtar"].split(":")[0] for x in r8]
sina("OTOMATIK: CLI ve ayni aile uygulandi, once CLI",
     len(r8) >= 2 and all(x.get("basarili") for x in r8)
     and sira8[0] == "cli" and set(sira8[1:]) == {"model"},
     str(r8))
sina("ajan (ay) yeni nesilde", of8.kadro.ajan("ay")["model"] == "gpt-7-sol")
sina("CLI yeni surumde", SURUM["codex"] == "0.158.0")
g = G.gecmis(d8, p8)
sina("otomatik uygulananin VEREN'i ofis", bool(g) and g[-1]["veren"] == "ofis", str(g[-1:]))
with d8.baglanti() as c:
    kk = [r2["veren"] for r2 in c.execute(
        "SELECT veren FROM karar WHERE tur='guncelleme' ORDER BY rowid DESC LIMIT 1")]
sina("karar gunlugune 'ofis' olarak yazildi (insan onaylamis gibi degil)",
     kk == ["ofis"], str(kk))

codex_katalog_yaz(ek=[{"slug": "gpt-7-sol", "visibility": "list", "priority": 0},
                      {"slug": "gpt-7-nova", "visibility": "list", "priority": 1}])
G.kontrol(d8, p8, npm=False)
r8 = G.otomatik_ilerle(of8, fabrika=tamam)
sina("yeni AILE (nova) otomatik UYGULANMADI", not any("nova" in x["anahtar"] for x in r8))
sina("yeni aile INSANA dustu",
     any("nova" in x["anahtar"] for x in G.insana_dusenler(d8, p8)))

# IS KOSARKEN CLI DEGISMEZ
NPM["@openai/codex"] = "0.160.0"
G.kontrol(d8, p8)
of8.tahta.gorev_ac("Kosan is", ana_hedef="h", kabul_olcutu="k",
                   yazma_alani=["x.txt"], acan="lale", neden="sinama")
with d8.baglanti() as c:
    c.execute("UPDATE gorev SET durum='calisiyor' WHERE proje_id=?", (p8,))
r8 = G.otomatik_ilerle(of8, fabrika=tamam)
sina("is KOSARKEN CLI ertelendi (kurulmadi)",
     any(x.get("ertelendi") for x in r8) and SURUM["codex"] == "0.158.0", str(r8))
sina("ertelenen oneri INSANA dusmedi (sonra tekrar denenecek)",
     not any(x["anahtar"] == "cli:codex:0.160.0" for x in G.insana_dusenler(d8, p8)))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
