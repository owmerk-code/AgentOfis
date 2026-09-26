# -*- coding: utf-8 -*-
"""Ofis disi klasor acma: kapi ACIYOR mu, ve ACARKEN KURALA baglaniyor mu.

Iki yonlu sinanir ve ikisi de gerekli:

* Kapi gercekten aciliyor mu -- yani ayar MOTORA ULASIYOR mu. Bu projede
  "sessizce yok sayilan ayar, ayar degildir" dersi bir kez odendi
  (orkestra motor fabrikasini alip hicbir yere gecirmiyordu).
* Kapi yanlis seyleri REDDEDIYOR mu. Hic reddetmeyen kapi, kapi degildir.

En kritik iki sinama: **isci** ve **inceleyici** klasoru goruyor mu.
Yalniz lidere verseydik lider, iscinin DOKUNAMAYACAGI bir klasore gore
plan yapardi; inceleyiciye vermeseydik o da yazilan dosyalari bulamayip
isi haksiz yere reddederdi. Ikisi de olculmus, yasanmis hatalar.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, Lider, Orkestra, Sohbet
from ofis.klasor import KlasorHatasi, klasor_dogrula, klasorleri_dogrula, metinler
from ofis.motor.claude import ClaudeMotoru
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


kok = Path(tempfile.mkdtemp(prefix="ofis-klasor-"))
print(f"klasor: {kok}")
dis = kok / "disarida"
dis.mkdir()
(dis / "veri.txt").write_text("merhaba", encoding="utf-8")

# ----------------------------------------------------------------- 1. kapi
print("\n1. klasor dogrulama -- REDDEDIYOR mu")

try:
    klasor_dogrula(str(kok / "boyle-bir-sey-yok"))
    sina("var olmayan klasor reddedildi", False, "-- kabul edildi!")
except KlasorHatasi as exc:
    # Bu en onemli ret: yanlis yazilmis bir yol sessizce calisiyormus
    # gibi gorunur ve ancak ajan "bulamadim" dediginde ortaya cikar.
    sina("var olmayan klasor reddedildi", True)
    sina("ret, sebebi SOYLUYOR", "YOK" in str(exc))

try:
    klasor_dogrula(str(dis / "veri.txt"))
    sina("dosya (klasor degil) reddedildi", False, "-- kabul edildi!")
except KlasorHatasi:
    sina("dosya (klasor degil) reddedildi", True)

try:
    klasor_dogrula(str(Path(kok.anchor)))
    sina("surucu koku reddedildi", False, "-- kabul edildi!")
except KlasorHatasi:
    sina("surucu koku reddedildi", True)

try:
    klasor_dogrula("")
    sina("bos yol reddedildi", False, "-- kabul edildi!")
except KlasorHatasi:
    sina("bos yol reddedildi", True)

# Sistem klasoru: gercekten varsa sina, yoksa atlama SESSIZ olmasin.
sistem = Path("C:/Windows")
if sistem.is_dir():
    try:
        klasor_dogrula(str(sistem))
        sina("sistem klasoru reddedildi", False, "-- kabul edildi!")
    except KlasorHatasi:
        sina("sistem klasoru reddedildi", True)
else:
    print("  [atlandi] sistem klasoru sinamasi -- C:/Windows yok")

print("\n2. klasor dogrulama -- MUTLAKLASTIRIYOR mu")
# Hayalet veritabani dersi: MCP sunucusu AYRI surecte, BASKA calisma
# klasorunde kosar. Oraya giden goreli yol baska bir yere cozulur ve
# kimse fark etmez. Surec sinirini gecen her sey mutlak olmali.
goreli = klasor_dogrula(".")
sina("goreli yol mutlaklasti", goreli.is_absolute())

cokla = klasorleri_dogrula([str(dis), str(dis), str(kok)])
sina("tekrar eden klasor bir kez sayildi", len(cokla) == 2)
sina("sira korundu (ilk verilen ilk)", cokla[0] == dis.resolve())
sina("metinler() mutlak metin veriyor",
     all(Path(m).is_absolute() for m in metinler(cokla)))

# ------------------------------------------------------------- 3. goc
print("\n3. sema gocu -- eski veritabani KIRILMIYOR mu")
eski_yol = kok / "eski.sqlite3"
ham = sqlite3.connect(str(eski_yol))
ham.executescript(
    "CREATE TABLE gorev (id TEXT PRIMARY KEY, baslik TEXT);"
    "INSERT INTO gorev VALUES ('a', 'eski is');")
ham.commit()
ham.close()

db_eski = Veritabani(eski_yol)
with db_eski.baglanti() as c:
    sutunlar = {s["name"] for s in c.execute("PRAGMA table_info(gorev)")}
    kalan = c.execute("SELECT baslik FROM gorev WHERE id='a'").fetchone()
sina("goc eksik sutunu ekledi", "ek_klasorler" in sutunlar)
sina("goc VAR OLAN veriyi korudu", bool(kalan) and kalan["baslik"] == "eski is")

# ------------------------------------------------------- 4. tahta saklama
print("\n4. gorev klasoru sakliyor ve GERI VERIYOR mu")
ofis = Ofis.proje_ac(Veritabani(kok / "ofis.sqlite3"), "Deneme",
                     amac="klasor sinamasi", basari_olcutu="testler gecer")
for _ad, _meslek, _lider in (("demir", "lider", True),
                             ("cinar", "backend", False)):
    (kok / _ad).mkdir(parents=True, exist_ok=True)
    ofis.kadro.ise_al(_ad, _meslek, lider_mi=_lider, tur="eller",
                      motor="sahte", klasor=str(kok / _ad))

g = ofis.tahta.gorev_ac(
    "Dis klasordeki isi yap", neden="sinama", ana_hedef="sinama",
    kabul_olcutu="testler gecer", ek_klasorler=[str(dis)])
sina("gorev klasoru sakladi", g["ek_klasorler"] == [str(dis.resolve())])
sina("saklanan yol MUTLAK", Path(g["ek_klasorler"][0]).is_absolute())
sina("liste() de cozup veriyor",
     ofis.tahta.liste()[0]["ek_klasorler"] == [str(dis.resolve())])

g2 = ofis.tahta.gorev_ac("Klasorsuz is", neden="s", ana_hedef="s",
                         kabul_olcutu="s")
sina("klasorsuz gorev bos liste veriyor", g2["ek_klasorler"] == [])

try:
    ofis.tahta.gorev_ac("Kotu", neden="s", ana_hedef="s", kabul_olcutu="s",
                        ek_klasorler=[str(kok / "yok-boyle")])
    sina("tahta var olmayan klasoru reddetti", False, "-- kabul edildi!")
except KlasorHatasi:
    sina("tahta var olmayan klasoru reddetti", True)

print("\n5. klasor acmak KAYDA GECIYOR mu")
# Yetki genislemesi sessizce olmaz: "hangi klasor hangi ise, kimin
# istegiyle acildi" sorusu alti ay sonra da cevaplanabilmeli.
with ofis.db.baglanti() as c:
    olaylar = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='klasor_acildi'")]
sina("klasor acilisi olaya yazildi", len(olaylar) == 1)
sina("olay HANGI klasoru soyluyor",
     bool(olaylar) and str(dis.resolve()) in olaylar[0]["govde"])
sina("olay HANGI ise ait oldugunu soyluyor",
     bool(olaylar) and f"#{g['no']}" in olaylar[0]["govde"])

# --------------------------------------------- 6. AYAR MOTORA ULASIYOR MU
print("\n6. ayar MOTORA ulasiyor mu (sessizce yok sayilan ayar, ayar degildir)")

cm = ClaudeMotoru(calistirilabilir="claude")
komut = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                      model="", efor="normal", yazabilir=True,
                      ek_klasorler=(str(dis),), butce_usd=None)
sina("komut satirinda --add-dir var", "--add-dir" in komut)
sina("--add-dir DOGRU klasoru gosteriyor",
     "--add-dir" in komut and komut[komut.index("--add-dir") + 1] == str(dis))

komut_bos = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                          model="", efor="normal", yazabilir=True,
                          ek_klasorler=(), butce_usd=None)
sina("klasor yoksa --add-dir DE yok", "--add-dir" not in komut_bos)


class _Kaydeden(SahteMotor):
    """Aldigi ayarlari kaydeder. Olcmedigimiz sey yonetilemez."""

    son: dict = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


# Kanit bildirilmezse is `inceleme`ye HIC gecmez (kanit kapisi dogru
# davranir) ve 7. bolum "inceleme" turunu olcemez. Testin kendi kurdugu
# sahne, olcmek istedigi sinirin otesine gecmeli.
_CEVAP = "Bitti.\nKANIT terminal: pytest -q -> 3 passed"
_fabrika = lambda ad, **a: _Kaydeden(cevap=_CEVAP)          # noqa: E731
Koltuk(ofis, motor_fabrikasi=_fabrika).kos(g["no"], "cinar")
sina("ISCI turu klasoru aldi",
     [str(x) for x in (_Kaydeden.son.get("ek_klasorler") or ())]
     == [str(dis.resolve())])

# ------------------------------------------------ 7. INCELEYICI de goruyor
print("\n7. inceleyici de goruyor mu")
# Yasanmis hata: inceleme liderin BOS klasorunde kostu, dosyalari
# bulamadi, isi "kanit dogrulanamiyor" diye reddetti ve isciye HAKSIZ
# yere "kanit uydurma" dersi yazdi.
_Kaydeden.son = {}
try:
    Lider(ofis, motor_fabrikasi=_fabrika).incele(g["no"])
except Exception:
    pass                                  # hukum onemli degil, AYAR onemli
alinan = [str(x) for x in (_Kaydeden.son.get("ek_klasorler") or ())]
sina("INCELEME turu isin klasorunu aldi", str(dis.resolve()) in alinan)

# ------------------------------------------------- 8. lider GORUYOR mu
print("\n8. lider planlarken klasoru GORUYOR mu")
# Gormeden yol yazmak tahmindir; ilk gercek iste tam bu yuzden var
# olmayan bir klasor (`calisma/demir`) yazilmisti.
_ork = Orkestra(ofis, motor_fabrikasi=_fabrika)
metin = _ork.plan_metni("bir sey yap", None, ek_klasorler=[str(dis)])
sina("plan metninde klasor yazili", str(dis.resolve()) in metin)
sina("plan metni MUTLAK yol istiyor", "MUTLAK" in metin)
sina("klasorsuz plan metninde bolum YOK",
     "OFIS DISI KLASOR" not in _ork.plan_metni("bir sey yap", None))

_soh = Sohbet(ofis, motor_fabrikasi=_fabrika)
triyaj = _soh.triyaj_metni("su klasorde ne var?", ek_klasorler=[str(dis)])
sina("triyaj metninde klasor yazili", str(dis.resolve()) in triyaj)
sina("triyaj 'once BAK' diyor", "BAK" in triyaj)
sina("klasorsuz triyajda bolum YOK",
     "PATRONUN ACTIGI KLASOR" not in _soh.triyaj_metni("selam"))

print("\n9. `cevap` yolunda da KAYDA GECIYOR mu")
# OLCULDU gercek turda: klasor acilisi yalnizca GOREV acilinca
# yaziliyordu. Lider `cevap` yolunda gorev acmaz -- klasor acilmisti
# ama hicbir yerde gorunmuyordu. Yetkinin yarisi kayitli, yarisi
# gorunmez olmaz.
_CEVAPLAYAN = ('{"karar": "cevap", "gerekce": "bilgi sorusu", '
               '"cevap": "Icinde bir metin dosyasi var."}')
for _ol in Sohbet(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(
        cevap=_CEVAPLAYAN)).konus("su klasorde ne var?",
                                  ek_klasorler=[str(dis)]):
    pass
with ofis.db.baglanti() as c:
    kayit = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='klasor_acildi' AND gorev_id IS NULL")]
sina("cevap yolunda klasor acilisi yazildi", len(kayit) == 1)
sina("kayit HANGI klasoru soyluyor",
     bool(kayit) and str(dis.resolve()) in kayit[0]["govde"])

print("\n10. LIDER turu olculuyor mu")
# "Olcmedigimiz sey yonetilemez." Bu bosluk bir kez odendi (basarisiz
# isci turlari kayda gecmiyordu); ayni bosluk lider tarafinda kalmisti.
with ofis.db.baglanti() as c:
    ozet = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='tur_ozeti' AND ajan_ad='demir'")]
sina("lider turu tur_ozeti yazdi", len(ozet) >= 1)
sina("ozet maliyet alanini tasiyor",
     bool(ozet) and "maliyet_usd" in ozet[-1]["govde"])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
