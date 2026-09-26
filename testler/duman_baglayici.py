# -*- coding: utf-8 -*-
"""BAGLAYICI + YETENEK: ag'a cikmadan, para yakmadan.

Dort soru:

1. **Kapi KAPALI KALARAK mi basarisiz oluyor.** Yetkisi olmayan ya da
   var olmayan bir baglayiciyla is acmak, ~95k jetonu odenmis ama
   calismayacak bir tur demektir.
2. **Bos bildirim BEDAVA mi.** `baglayicilar` bos olan gorev hicbir ek
   jeton odememeli -- ne ortam degiskeni, ne izin.
3. **Bildirim bir SUZGEC OLMADIGINI soyluyor mu.** Ortam degiskeni
   hesabin TUMUNU yukluyor (olculdu). "Sectik" demek, yanlis gosteren
   bir gosterge olurdu.
4. **`yetenek` UYDURUYOR mu.** Olcemedigine "iyi" dememeli; patlayan
   bir olcum sessiz kalmamali.

Hicbir sinama `claude mcp list` kosturmaz: durum disaridan verilir.
Gercek komuta baglanan bir test, kullanicinin o anki hesabini olcer --
*deterministik olmayan test, sinadigi seyi degil kendini olcer.*
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, yetenek
from ofis import baglayici as B
from ofis.motor.sahte import SahteMotor

GECEN = 0
KALAN = 0

#: Sahte olcum: gercek `claude mcp list` cagrilmaz.
SAHNE = {
    "Shopify": {"bagli": True, "url": "https://setup.shopify.com/mcp"},
    "Meta Reklamları": {"bagli": True, "url": "https://mcp.facebook.com/ads"},
    "Higgsfield": {"bagli": False, "url": "https://mcp.higgsfield.ai/mcp"},
}


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


# --------------------------------------------------- 1. KAPI
print("")
print("1. kapi KAPALI KALARAK mi reddediyor")
sina("bagli baglayici gecti", B.dogrula(["Shopify"], mevcut=SAHNE) == ["Shopify"])
sina("buyuk/kucuk harf onemsiz",
     B.dogrula(["shopify"], mevcut=SAHNE) == ["Shopify"])
sina("tekrar eden bir kez",
     B.dogrula(["Shopify", "shopify"], mevcut=SAHNE) == ["Shopify"])
sina("bos istek bos doner", B.dogrula([], mevcut=SAHNE) == [])

for istek, parca in ((["Higgsfield"], "yetki bekliyor"),
                     (["Olmayan"], "YOK")):
    try:
        B.dogrula(istek, mevcut=SAHNE)
        sina(f"{istek[0]} reddedildi", False, "-- kabul edildi!")
    except B.BaglayiciHatasi as exc:
        sina(f"{istek[0]} reddedildi", True)
        sina(f"  sebep soyleniyor ({parca})", parca in str(exc), f"({exc})")

# Ret, gecerli adlari SAYAR -- yanlis yazilmis bir ad sessiz bir olum
# sebebidir; insan neyi yazabilecegini gormeli.
try:
    B.dogrula(["Olmayan"], mevcut=SAHNE)
except B.BaglayiciHatasi as exc:
    sina("  ret GECERLI adlari sayiyor", "Shopify" in str(exc))

# OLCEMEDIYSEK "bagli" demeyiz.
try:
    B.dogrula(["Shopify"], mevcut={})
    sina("olculemeyen durum reddedildi", False, "-- 'bagli' varsayildi!")
except B.BaglayiciHatasi as exc:
    sina("olculemeyen durum reddedildi", True)
    sina("  'OLCULEMEDI' diyor", "OLCULEMEDI" in str(exc))


# ------------------------------------------- 2. BOS BILDIRIM BEDAVA
print("")
print("2. bos bildirim BEDAVA mi")
sina("bos -> ortam BOS", B.ortam([]) == {})
sina("dolu -> iki degisken birden", set(B.ortam(["Shopify"])) == {
    "ENABLE_CLAUDEAI_MCP_SERVERS", "ENABLE_TOOL_SEARCH"})
sina("bos ozet 'odenmiyor' diyor", "odenmiyor" in B.ozet([]))


# ------------------------------- 3. BILDIRIM SUZGEC DEGIL, SOYLENIYOR
print("")
print("3. bildirim bir SUZGEC OLMADIGINI soyluyor mu")
oz = B.ozet(["Shopify"])
sina("ozet 'TUMU yukleniyor' diyor", "TUM" in oz, oz)
sina("ozet olculmus bedeli soyluyor", str(B.OLCULEN_EK_JETON // 1000) in oz
     or "95" in oz, oz)
sina("olculen bedel gercekci (>50k)", B.OLCULEN_EK_JETON > 50_000)


# ------------------------------------------- 4. ZINCIR: GOREV -> MOTOR
print("")
print("4. gorevden motora ULASIYOR mu")
kok = Path(tempfile.mkdtemp(prefix="ofis-bag-"))
(kok / "w").mkdir()
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Bag",
                     amac="baglayici sinamasi", basari_olcutu="testler gecer")
ofis.kadro.ise_al("cinar", "magaza", motor="sahte", klasor=str(kok / "w"))

_ger = B.durum
B.durum = lambda *a, **k: dict(SAHNE)     # ag'a CIKMA


class _K(SahteMotor):
    """Baglayici TASIYABILEN sahte motor.

    `izin_kancasi = True` SART: 22.09'dan beri baglayici, izin kancasi
    olmayan motora VERILMIYOR. Sebebi olculmus bir delikti --
    baglayicilar onekle (`mcp__claude_ai`) aciliyordu, yani
    `ads_activate_entity` (reklami baslatir, PARA HARCAR) ya da
    `graphql_mutation` hicbir kapidan gecmiyordu. Kancasiz bir motorda
    o cagrilar yine kapisiz kalirdi; kapisiz bir kapi acmaktansa
    kapali kalmak.
    """

    son: dict = {}
    izin_kancasi = True
    # Baglayiciyi YALNIZ claude yukler (26.09.2026): kancali ama yukleyemeyen
    # motor (codex app-server) baglayici ALMAZ. Bu sahte motor claude'u
    # taklit ediyor -- ikisini de tasimali.
    baglayici_tasir = True

    def tur_kos(self, metin, **ayar):
        _K.son = dict(ayar)
        ayar.pop("izin_araci", None)      # sahte motor kancayi uygulamaz
        yield from super().tur_kos(metin, **ayar)


_f = lambda ad, **kw: _K(cevap="Bitti.\nKANIT dosya: x -> y",  # noqa: E731
                         mcp_konusur=True)

try:
    g1 = ofis.tahta.gorev_ac("magaza isi", neden="n", ana_hedef="h",
                             kabul_olcutu="k", baglayicilar=["Shopify"])
    sina("gorev baglayiciyi sakladi", g1["baglayicilar"] == ["Shopify"])
    Koltuk(ofis, motor_fabrikasi=_f).kos(g1["no"], "cinar")
    ort = _K.son.get("ek_ortam") or {}
    sina("ORTAM motora ulasti",
         ort.get("ENABLE_CLAUDEAI_MCP_SERVERS") == "true", str(ort))
    sina("tool-search de acildi", ort.get("ENABLE_TOOL_SEARCH") == "true")
    # SOZLESME DEGISTI (22.09.2026) -- ve sebebi olculmus bir delik.
    #
    # Once `mcp__claude_ai` oneki izin listesine giriyordu: HER
    # baglayici araci aciliyordu. `create-discount` (para),
    # `ads_activate_entity` (reklami baslatir), `graphql_mutation`
    # (her seyi yapar) -- hicbiri hicbir kapidan gecmiyordu. Ayni
    # hatayi tarayicida bir gun once kapatmistik.
    #
    # Simdi onek VERILMIYOR ve yerine CLI'in izin kancasi geciyor:
    # her cagri ofise soruluyor, okuma serbest, riskli insana dusuyor.
    # Bu iki sinama BIRLIKTE anlamli -- biri kalkarsa oteki deligi
    # gosterir.
    sina("baglayici oneki ARTIK VERILMIYOR",
         B.IZIN_ONEKI not in (_K.son.get("izinli_araclar") or ()),
         str(_K.son.get("izinli_araclar")))
    sina("yerine IZIN KANCASI verildi",
         (_K.son.get("izin_araci") or "").endswith("__izin_sor"),
         str(_K.son.get("izin_araci")))

    # KANCALI AMA BAGLAYICI YUKLEYEMEYEN MOTOR (26.09.2026: codex
    # app-server). "Acildi" denirse ajan araci bulamaz ve "yok" der --
    # yanlis gosteren gosterge. Verilmemeli ve bu GORUNUR olmali.
    class _KancaliTasiyamaz(_K):
        baglayici_tasir = False
    _K.son = {}
    g_cx = ofis.tahta.gorev_ac("codex baglayici", neden="n", ana_hedef="h",
                               kabul_olcutu="k", baglayicilar=["Shopify"])
    Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: _KancaliTasiyamaz(
        cevap="Bitti.\nKANIT dosya: x -> y", mcp_konusur=True)).kos(g_cx["no"], "cinar")
    sina("tasiyamayan motora baglayici ORTAMI verilmedi",
         "ENABLE_CLAUDEAI_MCP_SERVERS" not in (_K.son.get("ek_ortam") or {}),
         str(_K.son.get("ek_ortam")))
    with ofis.db.baglanti() as _c:
        _ol = [(r["tur"], r["govde"]) for r in _c.execute(
            "SELECT tur, govde FROM olay WHERE gorev_id=?", (g_cx["id"],))]
    sina("'acildi' YAZILMADI", not any(t == "baglayici_acildi" for t, _ in _ol), str(_ol)[:200])
    sina("vazgecme GORUNUR (uyari + sebep)",
         any(t == "uyari" and "yukleyemez" in g for t, g in _ol), str(_ol)[:200])
    sina("kanca yine VERILDI (kapi baglayicidan bagimsiz)",
         (_K.son.get("izin_araci") or "").endswith("__izin_sor"))

    # DAR PENCERE KAPISI -- olculdu: katalog 225.765 jeton, haiku'nun
    # penceresi 200.000. Sessizce baglayicisiz kosturmak daha kotu
    # olurdu: is yapilir GIBI gorunur, ajan araci bulamaz, sebebini
    # kimse bilmez.
    from ofis.kadro import Kadro as _Kadro                   # noqa: F401
    ofis.kadro.motor_ayarla("cinar", model="haiku")
    g_dar = ofis.tahta.gorev_ac("dar pencere", neden="n", ana_hedef="h",
                                kabul_olcutu="k", baglayicilar=["Shopify"])
    try:
        Koltuk(ofis, motor_fabrikasi=_f).kos(g_dar["no"], "cinar")
        sina("haiku + baglayici REDDEDILIYOR", False, "-- kabul edildi!")
    except Exception as _dexc:
        sina("haiku + baglayici REDDEDILIYOR", "SIGMAZ" in str(_dexc),
             str(_dexc)[:120])
        # Teshis koyup CARE soylemeyen gosterge, insani bir kez daha
        # dusundurur.
        sina("ret CAREYI soyluyor", "ajan degistir" in str(_dexc))
    ofis.kadro.motor_ayarla("cinar", model="sonnet")
    # Ters yon: genis pencerede ayni is GECMELI, yoksa "her seyi
    # reddeden" bir kapi da sinamayi gecerdi.
    g_genis = ofis.tahta.gorev_ac("genis pencere", neden="n", ana_hedef="h",
                                  kabul_olcutu="k", baglayicilar=["Shopify"])
    Koltuk(ofis, motor_fabrikasi=_f).kos(g_genis["no"], "cinar")
    sina("sonnet + baglayici GECIYOR",
         (_K.son.get("ek_ortam") or {}).get("ENABLE_CLAUDEAI_MCP_SERVERS")
         == "true")

    g2 = ofis.tahta.gorev_ac("normal is", neden="n", ana_hedef="h",
                             kabul_olcutu="k")
    Koltuk(ofis, motor_fabrikasi=_f).kos(g2["no"], "cinar")
    ort2 = _K.son.get("ek_ortam") or {}
    sina("baglayicisiz -> ortam YOK",
         "ENABLE_CLAUDEAI_MCP_SERVERS" not in ort2, str(ort2))
    sina("baglayicisiz -> izin YOK",
         B.IZIN_ONEKI not in (_K.son.get("izinli_araclar") or ()))

    # Yetki genislemesi SESSIZ olmaz.
    with ofis.db.baglanti() as c:
        acildi = [dict(r) for r in c.execute(
            "SELECT * FROM olay WHERE tur='baglayici_acildi'")]
        istendi = [dict(r) for r in c.execute(
            "SELECT * FROM olay WHERE tur='baglayici_istendi'")]
    # SAYIYA degil VARLIGA bakiliyor. Buyuyen bir sahneye tam esitlikle
    # bakmak kirilgan: sonradan eklenen her baglayicili gorev testi
    # kirar ve kirilan sey OLCULEN degil KURGUdur. Sinanan sey "yetki
    # genislemesi SESSIZ olmuyor".
    sina("acilis olaya yazildi", len(acildi) >= 1, str(len(acildi)))
    sina("istek de olaya yazildi", len(istendi) >= 1, str(len(istendi)))
    # Reddedilen is ACILIS yazmamali: acilmayan bir yetki, acilmis
    # gibi gorunmemeli.
    sina("her istek acilisa donusmuyor (reddedilen var)",
         len(istendi) > len(acildi), f"{len(istendi)} istek / {len(acildi)} acilis")
    sina("olay HANGI baglayici oldugunu soyluyor",
         bool(acildi) and "Shopify" in acildi[0]["govde"])
finally:
    B.durum = _ger


# ------------------------------------------------- 5. YETENEK UYDURMAZ
print("")
print("5. yetenek UYDURUYOR mu")
r = yetenek.tara(ofis, baglayici_dahil=False)
adlar = [g["ad"] for g in r["gruplar"]]
for beklenen in ("Motorlar", "Hesaplar", "Anahtar kasasi",
                 "Video ureticileri"):
    sina(f"'{beklenen}' grubu var", beklenen in adlar, str(adlar))

bag = [g for g in r["gruplar"] if "baglayici" in g["ad"].lower()][0]
# Atlanan olcum SESSIZ kalmaz: "yok" degil "bilinmiyor" der.
sina("atlanan olcum BILINMIYOR diyor",
     bag["satirlar"][0]["durum"] == yetenek.BILINMIYOR,
     bag["satirlar"][0]["durum"])
sina("  atlandigini SOYLUYOR", "atlan" in bag["satirlar"][0]["ad"].lower())

# Sahiplik ayrimi: "bagla" diyip yapamamak yanlis gosterge olurdu.
sahip = {g["ad"]: g["sahiplik"] for g in r["gruplar"]}
sina("baglayici grubu 'dis' (yonetilmez)",
     sahip.get("claude.ai baglayicilari") == "dis")
sina("hesaplar grubu 'ofis' (yonetilir)", sahip.get("Hesaplar") == "ofis")

# Patlayan olcum sessiz kalmamali.
_eski = yetenek._motorlar
yetenek._motorlar = lambda: (_ for _ in ()).throw(RuntimeError("bilerek"))
try:
    r2 = yetenek.tara(ofis, baglayici_dahil=False)
    mg = [g for g in r2["gruplar"] if g["ad"] == "Motorlar"][0]
    sina("PATLAYAN olcum bilinmiyor doner",
         mg["satirlar"][0]["durum"] == yetenek.BILINMIYOR)
    sina("  'sorun yok demek degil' uyarisi var",
         "degil" in mg["satirlar"][0]["care"])
finally:
    yetenek._motorlar = _eski

# SIR GOSTERMEZ.
r3 = yetenek.tara(ofis, baglayici_dahil=False)
metin = str(r3)
sina("anahtar DEGERI raporda yok",
     not any(len(str(s.get("not", ""))) > 0 and "AIza" in str(s.get("not", ""))
             for g in r3["gruplar"] for s in g["satirlar"]), "-- sizinti!")

# ══════════════ DORDUNCU DURUM: SON CAGRI DUSTU ══════════════
#
# Bu durum SORULARAK ogrenilemez: `claude mcp list` yalnizca
# "Connected / Needs authentication" doner, kapsam bilgisi YOKTUR
# (olculdu 21.09.2026). Rakipteki "scope short" rozetini oldugu gibi
# kopyalasaydik, olcemedigimiz bir seye hukum vermis olurduk.
#
# Ogrenilebilen tek gercek: bir ajan araci GERCEKTEN cagirdi ve dustu.
print("\n9. BAGLAYICI SORUN HAFIZASI")

import tempfile as _tf
from pathlib import Path as _P

_eski_defter = B.SORUN_DEFTERI
B.SORUN_DEFTERI = _P(_tf.mkdtemp(prefix="ofis-bagsorun-")) / "s.json"
# YALITIM SART: kullanicinin GERCEK defteri bir sinamanin sonucunu
# degistirememeli. Ayni ders `anahtar_oku` ve kota defterinde odendi.
try:
    sina("kayit yokken not YOK", B.sorun_notu("Shopify") is None)

    B.sorun_yaz("Shopify", "403 insufficient scope")
    n = B.sorun_notu("Shopify")
    sina("gercek cagri dusunce KAYDEDILIYOR", n is not None)
    sina("  mesaj saklaniyor", n and "scope" in n["mesaj"])
    sina("  kac dakika once oldugu var", n and n["dakika"] == 0)
    sina("ad sadelestirmesi calisiyor (buyuk/kucuk, bosluk)",
         B.sorun_notu("shopify") is not None)
    sina("baska baglayici ETKILENMEZ",
         B.sorun_notu("Gmail") is None)

    # BASARILI cagri kaydi DUSURUR. Duzelmis bir baglayiciyi bozuk
    # gostermeye devam etmek, yanlis gosteren gostergenin ta kendisi.
    B.sorunu_temizle("Shopify")
    sina("basarili cagri kaydi DUSURUYOR",
         B.sorun_notu("Shopify") is None)

    # BAYAT kayit yok sayilir: yetki yenilenir, sunucu duzelir.
    B.sorun_yaz("Canva", "bozuk")
    _t = B.SORUN_TAZE_SANIYE
    B.SORUN_TAZE_SANIYE = -1
    try:
        sina("BAYAT kayit yok sayiliyor",
             B.sorun_notu("Canva") is None)
    finally:
        B.SORUN_TAZE_SANIYE = _t

    # Arac adindan baglayici cikarma -- dedektorun girisi.
    sina("arac adindan baglayici cikariliyor",
         B.arac_adindan("mcp__claude_ai_Shopify__get-shop-info")
         == "Shopify")
    sina("OFISIN kendi araci baglayici SAYILMAZ",
         B.arac_adindan("mcp__ofis__kanit_ekle") is None)
    sina("tarayici araci baglayici SAYILMAZ",
         B.arac_adindan("mcp__tarayici__browser_click") is None)
    sina("duz arac baglayici SAYILMAZ",
         B.arac_adindan("Write") is None)

    # DORDUNCU HAL LIDERE ULASIYOR -- ayri satirda, "bagli" listesine
    # karistirilmadan: dusen bir baglayiciyi saglam gostermek olurdu.
    B.sorun_yaz("Shopify", "403")
    sahte_durum = {
        "Shopify": {"bagli": True, "url": "x",
                    "sorun": B.sorun_notu("Shopify")},
        "Gmail": {"bagli": True, "url": "y", "sorun": None},
        "Canva": {"bagli": False, "url": "z", "sorun": None},
    }
    blok = B.lider_blogu(sahte_durum)
    sina("dorduncu hal lider blogunda", "SON GERCEK CAGRI DUSTU" in blok)
    sina("  sorunlu baglayici 'BAGLI' satirinda DEGIL",
         "Shopify" not in blok.split("SON GERCEK")[0].split("BAGLI (")[1]
         .split("\n")[0])
    sina("  saglam baglayici BAGLI satirinda", "Gmail" in blok)
    sina("  lidere ne yapacagi soyleniyor", "kanitini KOY" in blok)

    # ---- DEDEKTOR GERCEKTEN ATESLIYOR MU (uctan uca) ----
    # `video.py` bir kez tam bu yuzden ise yaramamisti: modul yazildi,
    # rol eklendi, ama ajan ona ULASAMIYORDU. *Bir yetenek koda girdiyse,
    # CAGRILDIGI ayrica olculmelidir.*
    from ofis.motor.tip import MotorOlayi

    class _Baglayicili(SahteMotor):
        """Baglayici aracini cagirip DUSEN bir tur."""
        def __init__(self, **kw):
            super().__init__(**kw)
            self.hatali = kw.pop("_hatali", True)

        def tur_kos(self, metin, **ayar):
            yield MotorOlayi("basladi", "basladi", {"oturum_id": "x"})
            yield MotorOlayi("oturum", "sahte-model",
                             {"oturum_id": "x", "model": "sahte-model"})
            yield MotorOlayi("arac",
                             "mcp__claude_ai_Shopify__get-shop-info", {})
            yield MotorOlayi("arac_sonuc",
                             "403 insufficient scope: read_products",
                             {"hatali": _DURUM["hatali"]})
            yield MotorOlayi("metin", "Bitti.\nKANIT dosya: x -> y")
            yield MotorOlayi("bitti", "", {"basarili": True, "jeton": 10,
                                           "maliyet_usd": 0.0,
                                           "model": "sahte-model"})

    _DURUM = {"hatali": True}
    B.sorunu_temizle("Shopify")
    g9 = ofis.tahta.gorev_ac("baglayici dedektoru", neden="n", ana_hedef="h",
                             kabul_olcutu="k")
    Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: _Baglayicili()).kos(
        g9["no"], "cinar")
    sina("DUSEN gercek cagri koltuktan kaydedildi",
         B.sorun_notu("Shopify") is not None,
         "-- dedektor koltuga BAGLANMAMIS")

    # Ters yon: BASARILI cagri kaydi dusurmeli.
    _DURUM["hatali"] = False
    g10 = ofis.tahta.gorev_ac("baglayici duzeldi", neden="n", ana_hedef="h",
                              kabul_olcutu="k")
    Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: _Baglayicili()).kos(
        g10["no"], "cinar")
    sina("BASARILI gercek cagri kaydi DUSURDU",
         B.sorun_notu("Shopify") is None,
         "-- duzelmis baglayici bozuk gosteriliyor")
finally:
    B.SORUN_DEFTERI = _eski_defter

print("")
print(f"== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
