# -*- coding: utf-8 -*-
"""TARAYICI katmani: ajan web'e dokunabiliyor mu, ve NE KADAR.

Uc soru sinaniyor:

1. **Kapi REDDEDIYOR mu.** `file://`, `ftp://`, bos kaynak. Tarayici
   acmak bir yetki genislemesidir; beyan edilmeyen kaynak acilmaz --
   yazma kilidinin web hali. (OLCULMUS SINIR: kapi DOGRUDAN gidisi
   tutuyor, ama beyan edilen bir kaynagin YONLENDIRMESI disariya
   tasiyabiliyor -- bkz. tarayici.py docstring.)

2. **Tarayici ISIN ozelligi mi.** `tarayici_alani` bos olan gorev
   tarayici HIC gormemeli. Ajana bagli olsaydi bir kez acilan erisim
   butun gelecek islerinde acik kalirdi.

3. **ARAC VERILDIYSE IZIN DE VERILIYOR mu.** Bunu bir kez odedik:
   `WebSearch` arac listesindeydi ama IZIN listesinde degildi ve ofis
   aylarca hic arastirma yapamadi. Ayni hatayi tarayicida tekrarlamak
   cok kolaydi.

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
from ofis import tarayici as T
from ofis.mcp_sunucu import yapilandirma, SUNUCU_ADI
from ofis.motor.sahte import SahteMotor

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


# ------------------------------------------------------------ 1. KAPI
print("\n1. kaynak kapisi REDDEDIYOR mu")

sina("tam adres ORIGIN'e indi",
     T.kaynak_normalle("rakip.com/fiyatlar?x=1") == "https://rakip.com")
# Sema yoksa https varsayilir -- sessizce http'ye dusmek, kullanicinin
# beklemedigi bir guvenlik gevsemesidir.
sina("semasiz adres HTTPS varsayiyor",
     T.kaynak_normalle("ornek.com").startswith("https://"))
sina("tekrar eden kaynak bir kez",
     T.kaynaklari_dogrula(["a.com", "https://a.com/x"]) == ["https://a.com"])

for kotu, parca in (("file:///etc/passwd", ""), ("ftp://x.com", "http"),
                    ("", "Bos")):
    try:
        T.kaynak_normalle(kotu)
        sina(f"{kotu or '(bos)'} reddedildi", False, "-- kabul edildi!")
    except T.TarayiciHatasi as exc:
        sina(f"{kotu or '(bos)'} reddedildi", True)
        if parca:
            sina(f"  ret sebebi soyleniyor ({parca})", parca in str(exc))

# ----------------------------------------------- 2. YAPILANDIRMA
print("\n2. sunucu girdisi")
# BOS kaynak -> tarayici YOK. Bos listeyle "her yere gidebilir" demek,
# kapiyi kaldirmak olurdu.
sina("kaynak yoksa ve serbest istenmediyse sunucu YOK",
     T.sunucu_girdisi([]) is None)
# SERBEST TARAYICI (24.09.2026, kullanici karari): bos liste + serbest
# -> sunucu VAR ama `--allowed-origins` YOK. Kabin (cdp) asla serbest
# olmaz: orada insanin oturumlari yasar.
_sg = T.sunucu_girdisi([], serbest=True)
sina("SERBEST: bos listeyle sunucu VAR", _sg is not None)
sina("SERBEST: --allowed-origins VERILMIYOR",
     bool(_sg) and "--allowed-origins" not in _sg["args"], str(_sg))
sina("KABIN serbest OLMAZ (bos liste + cdp -> sunucu yok)",
     T.sunucu_girdisi([], serbest=True, cdp="http://127.0.0.1:9222") is None)
_dar = T.sunucu_girdisi(["https://rakip.com"], serbest=True)
sina("liste doluysa serbest bayragi DARALTMAYI kaldirmaz",
     "--allowed-origins" in _dar["args"])
sina("ozet SERBEST diyor", "SERBEST" in T.ozet([]))

g = T.sunucu_girdisi(["https://a.com", "https://b.com"])
args = " ".join(g["args"])
sina("allowed-origins yaziliyor", "--allowed-origins" in args)
sina("beyan edilen kaynaklar gecti",
     "https://a.com;https://b.com" in args)
# Olculdu: tam sayfa anlik goruntusu 105.727 karakterle yaniti patlatti.
sina("jeton korkulugu: --mobile", "--mobile" in args)
sina("donma korkulugu: eylem zaman asimi", "--timeout-action" in args)
sina("varsayilan GIZLI (headless)", "--headless" in args)
# Profil yoksa yalitilmis: tur tekrarlanabilir olur ve ajan insanin
# gercek oturumlarini gormez.
sina("profil yokken YALITILMIS", "--isolated" in args)

gp = " ".join(T.sunucu_girdisi(["https://a.com"], profil="C:/p")["args"])
sina("profil verilince user-data-dir", "--user-data-dir C:/p" in gp)
# --isolated ile --user-data-dir CELISIR; celiskiyi sessizce cozmek
# yerine acikca seciyoruz.
sina("profil verilince YALITIM DUSUYOR", "--isolated" not in gp)

gg = " ".join(T.sunucu_girdisi(["https://a.com"], gorunur=True)["args"])
sina("gorunur istenince headless YOK", "--headless" not in gg)

# --------------------------------------------- 3. MCP yapilandirmasi
print("\n3. MCP yapilandirmasina giriyor mu")
cfg = json.loads(yapilandirma("db.sqlite3", "p1", "cinar", 7,
                              ek_sunucular={"tarayici": g}))
sina("ofis sunucusu duruyor", SUNUCU_ADI in cfg["mcpServers"])
sina("tarayici sunucusu eklendi", "tarayici" in cfg["mcpServers"])
sina("ofis kimligi hala gomulu",
     cfg["mcpServers"][SUNUCU_ADI]["env"]["OFIS_AJAN"] == "cinar")

# OFISIN KENDI sunucusu EZILEMEZ: ayni adi tasiyan bir ek sunucu
# kanit/onay kanalini sessizce degistirebilirdi.
kotu = json.loads(yapilandirma("db.sqlite3", "p1", "cinar", 7,
                               ek_sunucular={SUNUCU_ADI: {"command": "kotu"}}))
sina("ofis sunucusu EZILEMIYOR",
     kotu["mcpServers"][SUNUCU_ADI]["command"] != "kotu")

# ------------------------------------------ 4. ISIN OZELLIGI mi
print("\n4. tarayici ISIN ozelligi (ajanin degil)")
kok = Path(tempfile.mkdtemp(prefix="ofis-tarayici-"))
print(f"klasor: {kok}")
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Tarayici",
                     amac="tarayici sinamasi", basari_olcutu="testler gecer")
(kok / "w").mkdir()
ofis.kadro.ise_al("cinar", "backend", motor="sahte", klasor=str(kok / "w"))


class _Kaydeden(SahteMotor):
    # `mcp_konusur` SINIF degiskeni olarak yazilamaz: SahteMotor.__init__
    # onu ORNEK degiskeni olarak kuruyor ve sinif degiskenini eziyor.
    # Yapiciya verilmeli.
    son: dict = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


CEVAP = "Bitti.\nKANIT terminal: pytest -> 1 passed"
_f = lambda ad, **kw: _Kaydeden(cevap=CEVAP, mcp_konusur=True)  # noqa: E731

g1 = ofis.tahta.gorev_ac("Tarayicisiz is", neden="s", ana_hedef="s",
                         kabul_olcutu="y")
Koltuk(ofis, motor_fabrikasi=_f).kos(g1["no"], "cinar")
cfg1 = json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
# SOZLESME DEGISTI (24.09.2026): alan YOKSA tarayici SERBEST verilir.
# Olculen sebep: gercek ofiste "siteyi musteri gozuyle analiz et" isi
# alansiz acildi, isci tarayici almadi ve uc kez "bende tarayici yok"
# diye sordu. Claude Code'u terminalde kullanan insan site acmak icin
# izin vermez; koruma TIKLAMADA (vekil), her kipte.
_s1 = cfg1.get("mcpServers", {}).get("tarayici") or {}
sina("alan YOKSA tarayici SERBEST verilir", bool(_s1),
     str(list(cfg1.get("mcpServers", {}))))
sina("serbest tarayicida --allowed-origins YOK",
     "--allowed-origins" not in " ".join(_s1.get("args", [])))
sina("serbest tarayicida da TIKLAMA izni var (riskli olan vekilde sorulur)",
     any(str(a).endswith("browser_click")
         for a in (_Kaydeden.son.get("izinli_araclar") or ())))

g2 = ofis.tahta.gorev_ac("Tarayicili is", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://rakip.com"])
sina("gorev alani sakladi", g2["tarayici_alani"] == ["https://rakip.com"])
Koltuk(ofis, motor_fabrikasi=_f).kos(g2["no"], "cinar")
cfg2 = json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
sina("alan VARSA tarayici sunucusu VAR",
     "tarayici" in cfg2.get("mcpServers", {}),
     str(list(cfg2.get("mcpServers", {}))))
sina("yalniz beyan edilen kaynak acildi",
     "https://rakip.com" in " ".join(cfg2["mcpServers"]["tarayici"]["args"]))

# ------------------------------- 5. ARAC VERILDIYSE IZIN DE VERILDI mi
print("\n5. arac verildiyse IZIN de verildi mi")
# Bir kez odenmis hata: `WebSearch` arac listesindeydi, izin listesinde
# degildi -- ofis aylarca hic arastirma yapamadi.
izinler = list(_Kaydeden.son.get("izinli_araclar") or ())
# Sozlesme DEGISTI: artik onek degil ARAC ARAC veriliyor (okuma ile
# yazma ayrildi). Ama kural ayni: arac verildiyse izin de verilir.
sina("TARAYICI IZNI verildi",
     any(a.startswith(T.IZIN_ONEKI) for a in izinler), str(izinler)[:120])
# VARSAYILAN ARTIK TIKLAYABILIR. Kullanici itiraz etti ve hakliydi:
# "tiklamasini engellemek bana sacma geldi." Koruma cite degil KAPIYA
# tasindi (`riskli.py` + `tarayici_kapi.py`): tiklamak serbest, RISKLI
# tiklama insana sorulur. O kapinin kendisi asagida sinaniyor.
sina("varsayilan olarak TIKLAMA izni VAR",
     any(a.endswith("browser_click") for a in izinler))
sina("sunulmayan arac izin listesinde de YOK",
     not any(a.endswith("browser_run_code_unsafe") for a in izinler))

# Acilis SESSIZ olmamali: yetki genislemesi kayda gecer.
with ofis.db.baglanti() as c:
    olaylar = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='tarayici_acildi'")]
# Iki is, iki acilis: serbest (alansiz) ve daraltilmis (rakip.com).
# Serbest acilis da SESSIZ olmaz -- yetki genislemesi kayda gecer.
sina("tarayici acilisi olaya yazildi (iki is, iki olay)",
     len(olaylar) == 2, str(len(olaylar)))
sina("serbest acilis SERBEST oldugunu soyluyor",
     bool(olaylar) and "SERBEST" in olaylar[0]["govde"])
sina("olay HANGI kaynagin acildigini soyluyor",
     len(olaylar) > 1 and "rakip.com" in olaylar[1]["govde"])

# ---------------------------- 6. GORUNURLUK ve PROFIL insana ULASIYOR mu
print("\n6. gorunurluk/profil bayraklari kabuktan motora ULASIYOR mu")
#
# Bunlar `koltuk.py`de ve `tarayici.py`de AYLARDIR vardi ama
# `orkestra` hicbirini iletmiyordu ve kabukta bayrak yoktu -- yani
# insan icin YOK hukmundeydiler. `video.py` bir kez tam bundan aylarca
# ajana ulasmamisti.
#
#   MODULUN VAR OLMASI BIR BAGLANTI DEGILDIR.

def _args(gorunur=False, profil=""):
    gx = ofis.tahta.gorev_ac("Tarayicili is", neden="s", ana_hedef="s",
                             kabul_olcutu="y",
                             tarayici_alani=["https://rakip.com"])
    Koltuk(ofis, motor_fabrikasi=_f).kos(
        gx["no"], "cinar", tarayici_gorunur=gorunur, tarayici_profili=profil)
    cfg = json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
    return list(cfg.get("mcpServers", {}).get("tarayici", {}).get("args", []))

gizli = _args()
gorunur = _args(gorunur=True)
sina("VARSAYILAN gizli (headless)", "--headless" in gizli)
# Ters yon SART: her zaman gorunur acan bir kod da ilk sinamayi gecerdi.
sina("bayrak verilince GORUNUR (headless kalkiyor)",
     "--headless" not in gorunur, " ".join(gorunur[-4:]))

prof = str(kok / "profil")
pargs = _args(gorunur=True, profil=prof)
sina("profil motora ULASIYOR", "--user-data-dir" in pargs)
# `--isolated` ile `--user-data-dir` CELISIR: biri "diske yazma" der,
# oteki "diske yaz". Sessizce cozmek yerine acikca secildi -- profil
# verildiyse KIMLIK istenmistir.
sina("profil verilince --isolated DUSER", "--isolated" not in pargs)
sina("profilsiz tur YALITILMIS kalir", "--isolated" in gizli)

# ORKESTRA HALKASI -- kabugun kullandigi yol. Koltuga dogrudan vermek
# calisiyor olabilir ama insanin yolu orkestradan gecer; ikisi ayri
# sinanmazsa "kodda var, ulasmiyor" hali geri gelir.
ofis.orkestra.koltuk = Koltuk(ofis, motor_fabrikasi=_f)
go = ofis.tahta.gorev_ac("Orkestradan tarayici", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://rakip.com"])
ofis.kadro.ise_al("ruzgar", "arastirma", motor="sahte", klasor=str(kok / "w"))
ofis.tahta.sahiplen(go["no"], "ruzgar", go["revizyon"])
ofis.orkestra.tik(tarayici_gorunur=True)
oargs = list(json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
             .get("mcpServers", {}).get("tarayici", {}).get("args", []))
sina("ORKESTRA gorunurlugu iletiyor",
     bool(oargs) and "--headless" not in oargs, " ".join(oargs[-3:]))

# OLCULMUS SINIR: tarayici yalnizca MCP KONUSAN motora verilir.
# codex/gemini `mcp_konusur=False` -- yani o motorlarla kosan ajan
# tarayici SUREMEZ. Bir kusur degil sinir, ve yazili olmasi gerekiyordu.
from ofis.motor import motor_ac                                   # noqa: E402
sina("claude tarayici surebilir", motor_ac("claude").mcp_konusur is True)
# 22.09: codex de surebilir -- `--approve-for-me` onay duvarini
# SANDBOX KALKMADAN asiyor (gercek turla olculdu).
sina("codex de tarayici surebilir (--approve-for-me)",
     motor_ac("codex").mcp_konusur is True)
# Gemini 24.09.2026'da defterden cikti: artik ADIYLA acilamaz, yani
# hicbir ajan ona dusup tarayicisiz kalamaz.
from ofis.motor import kayitli_motorlar                             # noqa: E402
sina("gemini motor defterinde YOK (cikarildi)",
     "gemini" not in kayitli_motorlar())

# ------------------------------------- 7. KABIN: ajan PANELDEKI tarayicida
print("\n7. KABIN -- ajan panelde gorunen tarayiciya baglaniyor mu")
#
# Kullanici: *"sistemden cikip chrome acip ugrasmak istemem."*
# Mimariyi belirleyen OLCUM: CDP'ye baglaninca `--allowed-origins`
# HALA TUTUYOR (beyan disi gidis `net::ERR_BLOCKED_BY_CLIENT`).
# Tutmasaydi kabin, yazma kilidinin web halini SESSIZCE kaldirirdi ve
# bu yol hic acilmazdi.

kabin_args = _args_kabin = None
gk = ofis.tahta.gorev_ac("Kabinde is", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://rakip.com"])
Koltuk(ofis, motor_fabrikasi=_f).kos(
    gk["no"], "cinar", tarayici_kabini=T.cdp_adresi())
kcfg = json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
kabin_args = list(kcfg.get("mcpServers", {}).get("tarayici", {}).get("args", []))

sina("kabin kipinde --cdp-endpoint VAR", "--cdp-endpoint" in kabin_args)
sina("kabin kipinde ucnokta 127.0.0.1", T.cdp_adresi() in kabin_args)
# KAPI DUSMUYOR -- bu, ozelligin var olma sartiydi.
sina("kabin kipinde --allowed-origins DURUYOR",
     "--allowed-origins" in kabin_args)
sina("beyan edilen kaynak hala listede",
     "https://rakip.com" in " ".join(kabin_args))
# Acilis bayraklari UYGULANAMAZ; gecirseydik "sessizce yok sayilan
# ayar" olurlardi. Acikca dusuruluyorlar ve bedeli yazili.
for b in ("--isolated", "--headless", "--mobile", "--user-data-dir"):
    sina(f"kabin kipinde {b} DUSTU", b not in kabin_args)
# Ozet SOYLEMELI: gostermeyen cikti, yok sayilan ayari fark ettirmez.
sina("ozet kabin kipini soyluyor",
     "KABIN" in T.ozet(["https://a.com"], cdp=T.cdp_adresi()))
sina("ozet --mobile kaybini SOYLUYOR",
     "--mobile" in T.ozet(["https://a.com"], cdp=T.cdp_adresi()))

# Kabin ISTENMEDIKCE acilmaz: cdp verilmezse eski davranis aynen kalir.
sina("kabin istenmezse eski davranis (izole, headless)",
     "--isolated" in gizli and "--headless" in gizli)

# --------------------------- 8. KABIN TEK YUZEY: iki is ayni anda GIREMEZ
print("\n8. kabin TEK yuzey -- ikinci tarayicili is BEKLETILIYOR mu")
#
# OLCULDU (22.09.2026), gercek Chrome + iki Playwright MCP istemcisi:
#   A -> example.com/?A=1 ; B -> example.com/?B=2
#   A "neredeyim" dedi -> "?B=2"
# A kendi sayfasinda SANDI, B'ninkini okudu. Hata vermedi.
# Yazma kilidi DOSYALARI korur; paylasilan bir YUZEYI korumuyordu.

# SAHNE TEMIZLENIR. Onceki bolumlerden kalan acik isler ajanlari
# tutuyordu; koruma KALKSA BILE ikinci is ajan bulamayacagi icin sinama
# ates etmiyordu -- yani test, korumayi degil ajan kitligini olcuyordu.
# *Testin kurdugu sahne, olcmek istedigi sinira ULASMALI.*
for _g in ofis.tahta.liste():
    if _g["durum"] not in ("bitti", "iptal"):
        try:
            ofis.tahta.iptal_et(_g["no"], sebep="sahne temizligi",
                                iptal_eden="cinar")
        except Exception:
            pass

ofis.kadro.ise_al("firtina", "arastirma", motor="sahte",
                  klasor=str(kok / "w"))
ofis.kadro.ise_al("bora", "arastirma", motor="sahte", klasor=str(kok / "w"))
t1 = ofis.tahta.gorev_ac("Tarayicili A", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://a.com"])
t2 = ofis.tahta.gorev_ac("Tarayicili B", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://b.com"])
ofis.orkestra.koltuk = Koltuk(ofis, motor_fabrikasi=_f)
oz = ofis.orkestra.tik(tarayici_kabini=T.cdp_adresi())

baslatilan = [b for b in oz["baslatilan"]
              if b.get("gorev_no") in (t1["no"], t2["no"])]
engel = [e for e in oz["engel"] if "kabin" in str(e.get("sebep", ""))]
sina("kabin kipinde ayni anda TEK tarayicili is",
     len(baslatilan) <= 1, f"baslatilan={len(baslatilan)}")
sina("bekletilenin SEBEBI gorunur", bool(engel), str(oz["engel"])[:120])

# TERS YON SART: kabin YOKKEN sinir UYGULANMAZ -- her is kendi
# tarayicisini alir, cakisma fiziksel olarak mumkun degil. Sinir her
# zaman uygulansaydi paralellik sebepsiz yariya inerdi.
t3 = ofis.tahta.gorev_ac("Tarayicili C", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://c.com"])
t4 = ofis.tahta.gorev_ac("Tarayicili D", neden="s", ana_hedef="s",
                         kabul_olcutu="y",
                         tarayici_alani=["https://d.com"])
oz2 = ofis.orkestra.tik()          # kabin YOK
engel2 = [e for e in oz2["engel"] if "kabin" in str(e.get("sebep", ""))]
sina("kabin YOKKEN kabin sinirlamasi UYGULANMIYOR", not engel2,
     str(engel2)[:120])

# ------------------ 9. OKUMA ile YAZMA AYRI -- kalici cozumun temeli
print("\n9. tarayicida OKUMA ile YAZMA ayri mi (arac duzeyinde)")
#
# Kullanici: *"hesaplarimi gomulu tarayiciya girmek riskli mi?"*
# Riskin kaynagi olculdu: kapi "HANGI SITEYE" sorusunu cozuyordu,
# "ORADA NE YAPABILIR" sorusunu cozmuyordu. Girisli bir hesapta tek
# tiklama fiyat degistirebilir, yayina alabilir, PARA HARCAYABILIR.
#
# Ofisin kurali zaten yaziliydi: *"kod yazmak sormaz; para harcamak,
# yayina almak, disariya yazmak sorar."* Tarayicida uygulanmiyordu.

sina("okuma/yazma listeleri ayrik",
     not (set(T.TARAYICI_OKUMA) & set(T.TARAYICI_YAZMA)))
# `browser_evaluate` ADI okuma gibi ama ISTEDIGI JS'i kosturur --
# tiklar, form gonderir. Okumada olsaydi kapi HIC KAPANMAZDI.
sina("browser_evaluate YAZMA sayiliyor",
     "browser_evaluate" in T.TARAYICI_YAZMA)
sina("browser_run_code_unsafe YAZMA sayiliyor",
     "browser_run_code_unsafe" in T.TARAYICI_YAZMA)
for a in ("browser_click", "browser_type", "browser_fill_form",
          "browser_press_key", "browser_file_upload", "browser_handle_dialog"):
    sina(f"{a} YAZMA", a in T.TARAYICI_YAZMA)

ro = T.izinli_araclar(yazma=False)     # ACIK BIR DARALTMA
rw = T.izinli_araclar()                # VARSAYILAN
sina("VARSAYILAN listede tiklama VAR",
     any(a.endswith("browser_click") for a in rw))
sina("acikca daraltilinca tiklama YOK",
     not any(a.endswith("browser_click") for a in ro))
sina("salt okunur listede gezinme VAR",
     any(a.endswith("browser_navigate") for a in ro))
sina("yazma acikken tiklama VAR",
     any(a.endswith("browser_click") for a in rw))
sina("onek verilmiyor (arac arac veriliyor)",
     T.IZIN_ONEKI not in ro and T.IZIN_ONEKI not in rw)

# GOREV ALANI: yetki ISIN ozelligi, ajanin degil.
gro = ofis.tahta.gorev_ac("Salt okunur web", neden="s", ana_hedef="s",
                          kabul_olcutu="y",
                          tarayici_alani=["https://x.com"],
                          tarayici_yazma=False)      # ACIK DARALTMA
grw = ofis.tahta.gorev_ac("Yazmali web", neden="s", ana_hedef="s",
                          kabul_olcutu="y",
                          tarayici_alani=["https://x.com"])
sina("VARSAYILAN tiklayabilir", grw["tarayici_yazma"] is True)
sina("acikca daraltilinca salt okunur", gro["tarayici_yazma"] is False)
# Alansiz yazma yetkisi anlamsiz: olmayan kapiya anahtar.
gbos = ofis.tahta.gorev_ac("Tarayicisiz", neden="s", ana_hedef="s",
                           kabul_olcutu="y", tarayici_yazma=True)
sina("alan yoksa yazma yetkisi de YOK", gbos["tarayici_yazma"] is False)

# MOTORA ULASIYOR MU -- "kabloyu bagladim" yetmez.
Koltuk(ofis, motor_fabrikasi=_f).kos(gro["no"], "cinar")
izin_ro = list(_Kaydeden.son.get("izinli_araclar") or ())
Koltuk(ofis, motor_fabrikasi=_f).kos(grw["no"], "ruzgar")
izin_rw = list(_Kaydeden.son.get("izinli_araclar") or ())
sina("acikca daraltilan turda TIKLAMA IZNI YOK",
     not any(a.endswith("browser_click") for a in izin_ro))
sina("salt okunur turda gezinme izni VAR",
     any(a.endswith("browser_navigate") for a in izin_ro))
sina("yazmali turda TIKLAMA IZNI VAR",
     any(a.endswith("browser_click") for a in izin_rw))
# Olay SOYLEMELI: gostermeyen cikti, yok sayilan yetkiyi fark ettirmez.
with ofis.db.baglanti() as c:
    olaylar = [dict(r)["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur='tarayici_alani'")]
sina("olay SALT OKUNUR/TIKLAYABILIR ayrimini soyluyor",
     any("SALT OKUNUR" in o for o in olaylar)
     and any("tiklayabilir" in o for o in olaylar), str(olaylar[-2:])[:160])

# ------------------------------------------------ 11. KABIN BASSIZ MI
#
# Kabin bir sure GORUNUR bir Chrome penceresi aciyordu ve panel onu
# yansitiyordu -- yani "panelin icinde tarayici" degil, "ayri bir
# Chrome'un aynasi". Kullanici bunu kullanirken gordu ve hakliydi.
#
# Olculdu (22.09.2026): bassiz kipte gorunur pencere 0 (PID suzgecli),
# ilk kare 20 ms (basliyken 445 ms), tiklama geciyor, ve kabinin var
# olma sarti -- `--allowed-origins` -- HALA TUTUYOR.
print("")
print("11. KABIN BASSIZ kosar -- gomulu olmanin sarti")

kb = T.kabin_komutu("chrome.exe", profil="P")
sina("kabin VARSAYILAN olarak bassiz", "--headless=new" in kb, str(kb))
# Profil yine ZORUNLU: bassiz olmak kisisel oturum korumasini
# gevsetmez. Iki kural birbirinden BAGIMSIZ kalmali.
try:
    T.kabin_komutu("chrome.exe", profil="")
    _red = False
except T.TarayiciHatasi:
    _red = True
sina("bassizken de profilsiz REDDEDIYOR", _red)

# TERS YON SART: kol CALISMALI. Yoksa "her zaman bassiz" diyen bir
# surum de sinamayi gecer ve olculmemis bir riske karsi (bassiz
# tarayiciya giris vermeyen site) insanin cikisi kalmaz.
kb_g = T.kabin_komutu("chrome.exe", profil="P", gorunur=True)
sina("gorunur KOLU calisiyor", "--headless=new" not in kb_g, str(kb_g))
sina("gorunur kipte de CDP kapisi VAR",
     any(a.startswith("--remote-debugging-port") for a in kb_g))

# Kabin DURUMU "gomulu muyum" sorusunu cevaplamali. Bunu gostermemek
# bir kez odendi: kabin aylarca gorunur bir Chrome aciyordu ve hicbir
# gosterge bunu soylemiyordu.
from ofis import kabin as _KB
_k = _KB.Kabin(kapi=59999)         # kapali kapi; surec BASLATMIYORUZ
_d = _k.durum()
sina("kabin durumu 'gorunur' alanini TASIYOR", "gorunur" in _d,
     str(list(_d.keys())))
# En onemlisi: BILMEDIGINE "gomulu" DEMIYOR. Disarida acilmis bir
# kabine bagliysak pencere halini CDP bildirmiyor.
sina("acmadigimiz kabinde gorunur BILINMIYOR (None)",
     _d["gorunur"] is None, repr(_d["gorunur"]))
# Profil de oyle: disarida acilmis kabinin profilini BILMIYORUZ.
sina("acmadigimiz kabinde profil BILINMIYOR (None)",
     _d["profil"] is None, repr(_d["profil"]))

# ----------------------------------------- 11b. KABIN OLUMU GORUNUR
# OLCULDU (24.09.2026): kullanici "gomulu tarayici calismiyor" dedi.
# Chrome'un stderr'i DEVNULL'a gidiyordu ve olum hicbir yere
# yazilmiyordu. Artik: stderr gunluge, acilirken olen surec BEKLENMEDEN
# sebebiyle bildirilir, sonradan olen surec BIR KEZ bildirilir.
# Sinama gercek Chrome ACMAZ: Chrome yerine hemen olen bir Python
# kosturulur; kullanicinin kabin profiline ve gunlugune dokunulmaz.
import shutil
import subprocess as _sp
import time as _tm
_kd = Path(tempfile.mkdtemp(prefix="ofis-kabin-olum-"))
_asil = (_KB.gunluk_yolu, _KB.profil_yolu, _KB.calistirilabilir_bul)
_KB.gunluk_yolu = lambda: str(_kd / "kabin.log")
_KB.profil_yolu = lambda: str(_kd / "profil")
_KB.calistirilabilir_bul = lambda: sys.executable   # Chrome bayraklarini
try:                                                 # tanimaz, olur
    _t0 = _tm.time()
    try:
        _KB.Kabin(kapi=59998).ac(bekle_sn=20)
        _hata = ""
    except _KB.KabinHatasi as exc:
        _hata = str(exc)
    _sure = _tm.time() - _t0
    sina("acilirken olen kabin HATA veriyor", "acilirken kapandi" in _hata,
         _hata[:120])
    sina("olum 20 sn BEKLENMEDEN bildiriliyor", _sure < 10, f"{_sure:.1f} sn")
    sina("hata olen surecin CIKTISINI tasiyor (gunlukten)",
         "usage" in _hata.lower() or "option" in _hata.lower()
         or "unknown" in _hata.lower(), _hata[-200:])
    sina("stderr gunluge YAZILDI", (_kd / "kabin.log").exists()
         and (_kd / "kabin.log").stat().st_size > 0)

    _ko = _KB.Kabin(kapi=59998)
    _ko.surec = _sp.Popen([sys.executable, "-c", "raise SystemExit(3)"])
    _ko.surec.wait(timeout=20)
    _o1 = _ko.olum()
    sina("sonradan olen kabin BILDIRILIYOR (cikis kodu ile)",
         bool(_o1) and _o1["cikis"] == 3, str(_o1))
    sina("olum BIR KEZ bildiriliyor (her durum sorusunda yeni olay yok)",
         _ko.olum() is None)
    _ko.kapat()
    sina("panelin KAPATTIGI kabin olum sayilmiyor", _ko.olum() is None)
finally:
    _KB.gunluk_yolu, _KB.profil_yolu, _KB.calistirilabilir_bul = _asil
    shutil.rmtree(_kd, ignore_errors=True)

# ------------------------------------------------------- 12. OGE SECICI
# Kabinde bir ogeyi isaret edip lidere gondermek. Uc kural sinaniyor:
# secmek tiklamak degildir · ifade istemciden gelmez · secici bilgi
# tasir, SIR tasimaz.
print("\n12. OGE SECICI -- bilgi tasir, sir tasimaz")
from ofis import kabin as _KB

# Ifade yalniz SAYI kabul eder: istemci ifadeye kod sokamaz.
for _kotu in ("1);alert(1", None, "abc", float("nan"), float("inf")):
    try:
        _KB.oge_ifadesi(_kotu, 5)
        _r = False
    except _KB.KabinHatasi:
        _r = True
    sina(f"oge ifadesi sayi olmayani REDDEDIYOR ({_kotu!r})", _r)
_if = _KB.oge_ifadesi(-5, 12.5)
sina("eksi koordinat sifira cekiliyor", "const X = 0.0, Y = 12.5" in _if)
# SALT OKUNUR: ifade giris DEGERI okumaz, tiklamaz, yazmaz.
for _yasak in (".value", ".click(", "dispatchEvent", "innerHTML =",
               "location =", "fetch("):
    sina(f"ifadede '{_yasak}' YOK", _yasak not in _if)
sina("nitelik listesinde 'value' YOK", "value" not in _KB.OGE_NITELIKLER)

_ham = {"etiket": "BUTTON", "secici": "#al", "essiz": True,
        "metin": "  Satin   al  ", "url": "https://a.com/sepet?sid=TOKSIR1#k",
        "nitelik": {"href": "/urun?tok=TOKSIR2", "value": "sifre",
                    "onclick": "x()"},
        "kutu": {"x": 100, "y": 50, "en": 200, "boy": 40},
        "fazla": "atilmali"}
_o = _KB.oge_ozeti(_ham, 1000, 500)
_oj = json.dumps(_o)
sina("oge suzuluyor", bool(_o) and _o["etiket"] == "button", _oj)
sina("sayfa adresinin SORGUSU atiliyor", _o["url"] == "https://a.com/sepet")
sina("GORELI baglantinin sorgusu da atiliyor (olculmus sizinti)",
     _o["nitelik"].get("href") == "https://a.com/urun", _oj)
sina("atildigi SOYLENIYOR", _o["sorgu_atildi"] is True)
sina("gizli sorgu hicbir yere sizmiyor", "TOKSIR" not in _oj, _oj)
sina("  lider blogunda da yok", "TOKSIR" not in _KB.oge_metni(_o))
sina("tanimsiz nitelik (value, onclick) dusuyor",
     "value" not in _o["nitelik"] and "onclick" not in _o["nitelik"])
sina("tanimsiz alan dusuyor", "fazla" not in _o)
sina("bosluklar sadelesiyor", _o["metin"] == "Satin al")
sina("kutu 0..1'e normallesiyor",
     _o["kutu"] == {"x": 0.1, "y": 0.1, "en": 0.2, "boy": 0.08}, str(_o["kutu"]))

_g = _KB.oge_ozeti({"etiket": "input", "giris": True, "metin": "cokgizli",
                    "url": "https://a.com/"})
sina("giris alaninin metni HIC tasinmiyor", _g["metin"] == "", str(_g))
for _ad, _h in (("None", None), ("dizi", [1]), ("etiketsiz", {"secici": "a"}),
                ("bozuk etiket", {"etiket": "<script>"})):
    sina(f"gecersiz oge ({_ad}) -> None, uydurulmuyor",
         _KB.oge_ozeti(_h) is None)
_nk = _KB.oge_ozeti({"etiket": "a", "kutu": {"x": "nan", "y": float("inf")}})
sina("bozuk kutu sifirlaniyor", _nk["kutu"] == {"x": 0.0, "y": 0.0, "en": 0.0, "boy": 0.0},
     str(_nk["kutu"]))

sina("kaynak = sayfanin ORIGIN'i", _KB.oge_kaynagi(_o) == "https://a.com")
sina("about:blank bir kaynak DEGIL",
     _KB.oge_kaynagi(_KB.oge_ozeti({"etiket": "div", "url": "about:blank"})) == "")
_m = _KB.oge_metni(_o, kabin_paylasildi=True)
sina("lider blogu seciciyi ve sayfayi tasiyor",
     "#al" in _m and "https://a.com/sepet" in _m, _m)
sina("lider blogu sorgunun atildigini soyluyor", "sorgu" in _m)
sina("lider blogu PAYLASILAN kabini soyluyor", "PAYLASILAN kabin" in _m)
sina("kabin kapaliysa bunu soyluyor",
     "kabin kapaliydi" in _KB.oge_metni(_o, kabin_paylasildi=False))
_o2 = dict(_o, essiz=False)
sina("tek olmayan secici ACIKCA soyleniyor",
     "TEK DEGIL" in _KB.oge_metni(_o2))

# GERCEK TARAYICIDA: kusurlarin ucu de ANCAK burada gorundu (goreli
# adres sizintisi, golge DOM'da yanlis "tek", bos alanda butun sayfa).
# Gecici profil: kullanicinin kabin profiline DOKUNULMAZ.
print("\n12b. OGE SECICI gercek Chrome'da")
try:
    _chrome = _KB.calistirilabilir_bul()
except _KB.KabinHatasi:
    _chrome = ""
if not _chrome:
    print("  ATLANDI -- Chrome bulunamadi (gecti SAYILMAZ)")
else:
    import http.server as _hs, socketserver as _ss, threading as _th
    import subprocess as _sp, tempfile as _tf, asyncio as _aio, time as _tm
    _SAYFA = ("<!doctype html><html><head><title>Deneme</title></head>"
              "<body style='margin:0'>"
              "<button id='al' style='position:absolute;left:20px;top:20px;"
              "width:120px;height:30px'>Satin al</button>"
              "<input id='sifre' type='password' style='position:absolute;"
              "left:20px;top:200px'>"
              "<a href='/urun?tok=GIZLI123#x' style='position:absolute;"
              "left:20px;top:260px'>urun</a>"
              "<my-el style='position:absolute;left:20px;top:320px;"
              "display:block;width:150px;height:30px'></my-el>"
              "<div id='sayac' style='position:absolute;left:300px;top:20px'>0</div>"
              "<script>customElements.define('my-el',class extends HTMLElement{"
              "constructor(){super();this.attachShadow({mode:'open'}).innerHTML="
              "'<button style=\"width:150px;height:30px\">golge</button>'}});"
              "document.getElementById('al').onclick=()=>{const s="
              "document.getElementById('sayac');s.textContent=+s.textContent+1};"
              "</script></body></html>").encode()

    class _H(_hs.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_SAYFA)

        def log_message(self, *a):
            pass

    _srv = _ss.ThreadingTCPServer(("127.0.0.1", 0), _H)
    _th.Thread(target=_srv.serve_forever, daemon=True).start()
    _url = f"http://127.0.0.1:{_srv.server_address[1]}/"
    _prof = _tf.mkdtemp(prefix="oge_prof_")
    _kapi = 9357
    # Chrome bilesen guncellemesi indirir ve %TEMP%'e birakir (olculdu:
    # her kosuda ~250 KB `*.tmp` + `chrome_url_fetcher_*`). Chrome'un
    # gecici klasoru SINAMANIN klasorune yonlenir; onunla birlikte silinir.
    import os as _os
    _chrome_tmp = _tf.mkdtemp(prefix="ofis-chrome-tmp-")
    _sur = _sp.Popen(T.kabin_komutu(_chrome, profil=_prof, kapi=_kapi,
                                    baslangic=_url),
                     stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                     env=dict(_os.environ, TEMP=_chrome_tmp, TMP=_chrome_tmp))
    _sonuc = {}
    try:
        for _ in range(80):
            if _KB.acik_mi(_kapi):
                break
            _tm.sleep(0.25)
        _tm.sleep(1.0)

        async def _olc():
            import websockets
            async with websockets.connect(_KB.sayfa_ws(_kapi), max_size=None) as c:
                n = [0]

                async def ev(ifade):
                    n[0] += 1
                    await c.send(json.dumps({"id": n[0], "method": "Runtime.evaluate",
                                             "params": {"expression": ifade,
                                                        "returnByValue": True}}))
                    while True:
                        v = json.loads(await c.recv())
                        if v.get("id") == n[0]:
                            return ((v.get("result") or {}).get("result") or {}).get("value")
                await ev("document.getElementById('sifre').value='cokgizli-99'")
                for ad, (x, y) in {"dugme": (60, 35), "sifre": (40, 210),
                                   "baglanti": (30, 268), "golge": (60, 335),
                                   "bos": (900, 700)}.items():
                    ham = await ev(_KB.oge_ifadesi(x, y))
                    _sonuc[ad] = (ham, _KB.oge_ozeti(ham, 1280, 800))
                _sonuc["sayac"] = await ev("document.getElementById('sayac').textContent")
                sec = _sonuc["dugme"][1]["secici"]
                _sonuc["bulunan"] = await ev(
                    "document.querySelector(%s).id" % json.dumps(sec))
        _aio.run(_olc())
    finally:
        _sur.terminate()
        try:
            _sur.wait(timeout=8)
        except _sp.TimeoutExpired:
            _sur.kill()
        _srv.shutdown()
        # Gecici profil SILINIR: test artiklari bir kez diski doldurdu.
        import shutil as _sh
        _tm.sleep(0.5)
        _sh.rmtree(_prof, ignore_errors=True)

    _d = (_sonuc.get("dugme") or (None, None))[1] or {}
    sina("gercek: dugme bulundu, secici tek", _d.get("secici") == "#al"
         and _d.get("essiz") is True, str(_d))
    sina("gercek: secici GERCEKTEN o ogeyi buluyor", _sonuc.get("bulunan") == "al")
    _s = _sonuc.get("sifre") or (None, None)
    sina("gercek: sifre kutusunun DEGERI ham sonucta bile YOK",
         "cokgizli" not in json.dumps(_s[0]), json.dumps(_s[0])[:200])
    sina("gercek: sifre kutusu giris olarak isaretli",
         bool(_s[1]) and _s[1]["giris"] is True)
    _b = (_sonuc.get("baglanti") or (None, None))[1] or {}
    sina("gercek: goreli baglantinin gizli sorgusu ATILDI",
         "GIZLI" not in json.dumps(_b) and _b.get("sorgu_atildi") is True, str(_b))
    _gl = (_sonuc.get("golge") or (None, None))[1] or {}
    sina("gercek: golge DOM ogesi SAHIBIYLE veriliyor",
         _gl.get("golge") is True and _gl.get("golge_sahibi") == "my-el", str(_gl))
    sina("gercek: bos alan SECIM DEGIL (butun sayfa tasinmiyor)",
         (_sonuc.get("bos") or (1, 1))[1] is None)
    sina("gercek: secim sayfaya TIKLAMADI", _sonuc.get("sayac") == "0",
         repr(_sonuc.get("sayac")))

# --------------------------------------- 12d. ONAYLANAN SITE SONRAKI TURDA
print("\n12d. ONAYLANAN yeni site bir SONRAKI turda aciliyor")
g12d = ofis.tahta.gorev_ac("Fiyat taramasi", neden="s", ana_hedef="s",
                           kabul_olcutu="y",
                           tarayici_alani=["https://rakip.com"])
_o12 = ofis.postane.onay_iste(
    "cinar", "Beyan edilmemis siteye gitmek: https://yeni.com",
    ayrinti="IMZA:x\nKAYNAK:https://yeni.com", gorev_no=g12d["no"])
_o12b = ofis.postane.onay_iste(
    "cinar", "Beyan edilmemis siteye gitmek: https://red.com",
    ayrinti="IMZA:y\nKAYNAK:https://red.com", gorev_no=g12d["no"])
ofis.postane.onay_cevapla(_o12["id"], onayla=True)
ofis.postane.onay_cevapla(_o12b["id"], onayla=False, not_="hayir")
Koltuk(ofis, motor_fabrikasi=_f).kos(g12d["no"], "cinar")
_c12 = json.loads(_Kaydeden.son.get("mcp_yapilandirma") or "{}")
_a12 = " ".join(_c12.get("mcpServers", {}).get("tarayici", {}).get("args", []))
sina("ONAYLANAN site tarayicinin izin listesinde", "https://yeni.com" in _a12,
     _a12[-200:])
sina("REDDEDILEN site listede YOK", "https://red.com" not in _a12)
sina("beyan edilen site duruyor", "https://rakip.com" in _a12)
sina("gorevin kendi alani DEGISMEDI (genisleme onaydan turetiliyor)",
     ofis.tahta.gorev(g12d["no"])["tarayici_alani"] == ["https://rakip.com"])
with ofis.db.baglanti() as _c:
    _ev = [r[0] for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='tarayici_alani' AND gorev_id=?",
        (g12d["id"],)).fetchall()]
sina("genisleme KAYDA gecti", any("yeni.com" in e for e in _ev), str(_ev))
_k4 = ofis.brifing.k4_gorev(g12d["no"])
sina("brifing izinli siteleri ve SORULACAGINI soyluyor",
     "Izinli siteler:** https://rakip.com" in _k4 and "patrona sorar" in _k4)

# --------------------------------------- 12c. KABIN ISE YAZILIR
# Olculmus bosluk (24.09): oge seciciyle baslayan is kesilip panelden
# "Surdur"le devam edince kabin kayboluyordu -- kabin halkanin bir
# kosusuna aitti, ISE degil. Is artik oturumsuz tarayicida kosuyordu.
print("\n12c. KABIN ISE YAZILIR -- Surdur'de kaybolmuyor")
for _g in ofis.tahta.liste():
    if _g["durum"] not in ("bitti", "iptal"):
        try:
            ofis.tahta.iptal_et(_g["no"], sebep="sahne temizligi",
                                iptal_eden="cinar")
        except Exception:
            pass
ofis.kadro.ise_al("lale", "lider", motor="sahte", lider_mi=True,
                  klasor=str(kok / "w"))
_acilan = ofis.lider.dagit(
    "sayfadaki dugmeyi incele",
    [{"baslik": "Insanin sayfasi", "neden": "n", "kabul_olcutu": "k"},
     {"baslik": "Liderin sectigi site", "neden": "n", "kabul_olcutu": "k",
      "tarayici_alani": ["https://baska.com"]}],
    gerekce="iki ayri kaynak", lider_ad="lale",
    tarayici_alani=["https://a.com/x?y=1"], tarayici_kabin=True)
_k1, _k2 = _acilan[0], _acilan[1]
sina("isaret edilen kaynagin isine kabin YAZILDI",
     ofis.tahta.gorev(_k1["no"])["tarayici_kabin"] is True)
sina("liderin sectigi BASKA siteye kabin VERILMEDI (patronun oturumu)",
     ofis.tahta.gorev(_k2["no"])["tarayici_kabin"] is False)
_k3 = ofis.tahta.gorev_ac("Kabinsiz", neden="n", ana_hedef="h",
                          kabul_olcutu="k", tarayici_alani=["https://a.com"])
sina("verilmezse kabin YOK (varsayilan dar)", _k3["tarayici_kabin"] is False
     if "tarayici_kabin" in _k3 else
     ofis.tahta.gorev(_k3["no"])["tarayici_kabin"] is False)
_k4 = ofis.tahta.gorev_ac("Alansiz", neden="n", ana_hedef="h",
                          kabul_olcutu="k", tarayici_kabin=True)
sina("tarayici alani yoksa kabin bayragi YAZILMAZ",
     ofis.tahta.gorev(_k4["no"])["tarayici_kabin"] is False)

# Halka KABINSIZ (Surdur gibi); kabin KAPALI -> is bekletilir.
_giden = {}
_asil_kos = ofis.orkestra.koltuk.kos


def _izle(no, ajan, **ayar):
    _giden[no] = ayar.get("tarayici_kabini", "")
    return _asil_kos(no, ajan, **ayar)


ofis.orkestra.koltuk.kos = _izle
ofis.orkestra.kabin_ucnoktasi = lambda: ""
_oz = ofis.orkestra.tik()
_eng = [e for e in _oz["engel"] if isinstance(e, dict)
        and e.get("gorev_no") == _k1["no"]]
sina("kabin KAPALIYKEN kabinli is BEKLETILIYOR (oturumsuz kosmuyor)",
     _k1["no"] not in _giden and bool(_eng), str(_oz["engel"])[:200])
sina("  sebebi SOYLENIYOR", bool(_eng) and "KAPALI" in _eng[0]["sebep"])
# Kabin ACIK -> ayni is, kabinsiz halkada bile KABINLE kosar.
ofis.orkestra.kabin_ucnoktasi = lambda: "http://127.0.0.1:9222"
_giden.clear()
for _ in range(3):
    ofis.orkestra.tik()
    if _k1["no"] in _giden:
        break
sina("kabin ACIKKEN is 'Surdur'de de KABINLE kosuyor",
     _giden.get(_k1["no"]) == "http://127.0.0.1:9222", str(_giden))
sina("kabinsiz is kabin ALMIYOR (baska site / bayraksiz)",
     all(v == "" for n, v in _giden.items() if n != _k1["no"]), str(_giden))
ofis.orkestra.koltuk.kos = _asil_kos

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
