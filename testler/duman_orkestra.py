# -*- coding: utf-8 -*-
"""Orkestra duman testi: halka insan olmadan donuyor mu, kapilar tutuyor mu.

Sahte motorla kosar. Sinanan sey liderin zekasi degil KAPILAR:
gerekcesiz plan geciyor mu · cakisan kollar geciyor mu · kafa ajana dosya
isi verilebiliyor mu · ret lidere OGRETIYOR mu · bekleyen is ilerleme
sayiliyor mu · ilerleme durunca dongu duruyor mu.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Orkestra, OrkestraHatasi
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


print("== orkestra duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-ork-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Orkestra Projesi", amac="Halkayi dondurmek",
                     basari_olcutu="Insan mudahalesi olmadan donsun")
kanat = ofis.kanat_ac("URUN", "UR")
for ad, meslek, lider_mi, tur in (("demir", "lider", True, "eller"),
                                  ("cinar", "backend", False, "eller"),
                                  ("yaprak", "arayuz", False, "eller"),
                                  ("bilge", "arastirma", False, "kafa")):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi,
                      tur=tur, motor="sahte", klasor=str(kok / ad))
    (kok / ad).mkdir(parents=True, exist_ok=True)

#: Liderin verecegi cevabi test yonetir -- kapilari sinamak icin bilerek
#: bozuk planlar uretecegiz.
kutu = {"cevap": "", "isci_cevap": "", "sayac": 0, "istekler": []}


def fabrika(ad, **ayar):
    return SahteMotor(cevap=kutu["cevap"])


def plan(bol, gerekce, kollar):
    return "```json\n" + json.dumps(
        {"bol": bol, "gerekce": gerekce, "kollar": kollar},
        ensure_ascii=False) + "\n```"


class IzleyenMotor(SahteMotor):
    """Lidere giden metni kaydeder -- 'ret ogretiyor mu' sinamasi icin."""

    def tur_kos(self, metin, **ayar):
        kutu["istekler"].append(metin)
        kutu["sayac"] += 1
        return super().tur_kos(metin, **ayar)


def izleyen_fabrika(ad, **ayar):
    return IzleyenMotor(cevap=kutu["cevap"])


ork = Orkestra(ofis, motor_fabrikasi=izleyen_fabrika)

TEK_KOL = [{"baslik": "API yaz", "sahip": "cinar", "neden": "Siparis alinamiyor",
            "kabul_olcutu": "pytest yesil", "govde": "yaz",
            "yazma_alani": ["api/"]}]

# --------------------------------------------------------------------------
print("1. PLAN KAPILARI -- bozuk plan gecmiyor")

kutu["cevap"] = plan(False, "", TEK_KOL)          # gerekce YOK
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("gerekcesiz plan REDDEDILIYOR", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("gerekcesiz plan REDDEDILIYOR", "gerekce" in str(exc).lower())
sina("reddedilen plandan gorev ACILMADI", ofis.tahta.liste() == [])

kutu["cevap"] = plan(True, "g", [
    {"baslik": "A", "sahip": "cinar", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["api/"]},
    {"baslik": "B", "sahip": "yaprak", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["api/odeme"]},          # api/ altinda -- CAKISIR
])
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("CAKISAN kollar reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("CAKISAN kollar reddediliyor", "ayrik" in str(exc).lower())

kutu["cevap"] = plan(False, "g", [
    {"baslik": "A", "sahip": "bilge", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["rapor/"]},             # bilge KAFA, yazamaz
])
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("KAFA ajana dosya isi reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("KAFA ajana dosya isi reddediliyor", "yazamaz" in str(exc).lower())

kutu["cevap"] = plan(False, "g", [
    {"baslik": "A", "sahip": "cinar", "neden": "", "kabul_olcutu": "k",
     "yazma_alani": []},
])
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("neden'siz kol reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("neden'siz kol reddediliyor", "neden" in str(exc).lower())

kutu["cevap"] = plan(False, "g", [
    {"baslik": "A", "sahip": "demir", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": []},                      # demir LIDER
])
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("LIDERE is atanamiyor", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("LIDERE is atanamiyor", "lider" in str(exc).lower())

kutu["cevap"] = "Bence su isi yapalim, bolmeye gerek yok."   # JSON YOK
try:
    ork.hedef_ver("Hedef", deneme=1)
    sina("JSON'suz cevap reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi:
    sina("JSON'suz cevap reddediliyor", True)

# --------------------------------------------------------------------------
print("\n2. RET OGRETIYOR -- lider sebebi GORUYOR")
kutu["istekler"].clear()
kutu["cevap"] = plan(False, "", TEK_KOL)      # hep bozuk -> iki deneme
try:
    ork.hedef_ver("Hedef", deneme=2)
except OrkestraHatasi:
    pass
sina("iki kez denendi", len(kutu["istekler"]) == 2,
     f"-- {len(kutu['istekler'])} deneme")
sina("IKINCI istekte ret sebebi lidere yazildi",
     "REDDEDILDI" in kutu["istekler"][1] and
     "gerekce" in kutu["istekler"][1].lower())
sina("ilk istekte ret sebebi YOK", "REDDEDILDI" not in kutu["istekler"][0])

# --------------------------------------------------------------------------
print("\n3. KADRO ve KURALLAR lidere veriliyor")
istek = kutu["istekler"][0]
sina("kadro isimleriyle veriliyor", "cinar" in istek and "yaprak" in istek)
sina("kafa ajanin YAZAMAZ oldugu soyleniyor",
     "bilge" in istek and "YAZAMAZ" in istek)
sina("bolmenin bedeli soyleniyor (15 kat)", "15 KAT" in istek)
sina("ayrik alan kurali soyleniyor", "ayrik" in istek.lower())
sina("lider kadroda GORUNMUYOR (kendine is veremesin)",
     "- **demir**" not in istek)

# --------------------------------------------------------------------------
print("\n4. GECERLI PLAN -- gorevler aciliyor, karar gunluge dusuyor")
kutu["cevap"] = plan(True, "Iki kol ayri dosyalara dokunuyor, paralel kazanir.", [
    {"baslik": "API yaz", "sahip": "cinar", "neden": "Siparis alinamiyor",
     "kabul_olcutu": "pytest yesil", "govde": "API yaz", "yazma_alani": ["api/"]},
    {"baslik": "Arayuz yaz", "sahip": "yaprak", "neden": "Ekran yok",
     "kabul_olcutu": "Ekran goruntusu", "govde": "Ekran yap", "yazma_alani": ["web/"]},
])
sonuc = ork.hedef_ver("Magaza canliya ciksin")
sina("iki gorev acildi", len(sonuc["gorevler"]) == 2)
sina("bol=True bildirildi", sonuc["bol"] is True)
sina("UST HEDEF her kola tasindi",
     all(g["ana_hedef"] == "Magaza canliya ciksin" for g in sonuc["gorevler"]))
sina("sahipler plandan geldi",
     {g["sahip"] for g in sonuc["gorevler"]} == {"cinar", "yaprak"})
son = ofis.bellek.son_kararlar(1)[0]
sina("dagitim karari gunluge dustu", son["tur"] == "dagitim")
sina("gerekce saklandi", "paralel kazanir" in son["gerekce"])

# --------------------------------------------------------------------------
print("\n4b. BIRLESTIRME KOLU -- parcalar kendiliginden butun olmaz")
# Kullanici istegi (18.09.2026): lider isi dagitsin, sonra TOPLASIN.
# Ihtiyac gercek -- ama birlestirme bir GOREVDIR, liderin ayricaligi
# degil: kendi kabul olcutu, kendi kaniti olur ve otekileri BEKLER.
kutu["cevap"] = plan(True, "Iki bagimsiz parca + birlestirme.", [
    {"baslik": "Parca A", "sahip": "cinar", "neden": "n",
     "kabul_olcutu": "k", "yazma_alani": ["a/"]},
    {"baslik": "Parca B", "sahip": "yaprak", "neden": "n",
     "kabul_olcutu": "k", "yazma_alani": ["b/"]},
    {"baslik": "Birlestir", "sahip": "cinar",
     "neden": "Parcalar tek basina calismaz",
     "kabul_olcutu": "Uctan uca kosuyor",
     "yazma_alani": ["birlesik/"], "bekler": [0, 1]},
])
sonuc = ork.hedef_ver("Birlestirmeli hedef")
birlesim = sonuc["gorevler"][2]
sina("birlestirme kolu acildi", birlesim["baslik"] == "Birlestir")
blok = ofis.tahta.blokcular(birlesim["no"])
sina("birlestirme otekileri BEKLIYOR", len(blok) == 2,
     f"-- {len(blok)} blokci")
sina("birlestirme HAZIR degil, bekliyor",
     ofis.tahta.gorev(birlesim["no"])["durum"] == "bekliyor")

# Sonraki kolu ONCEKI degil SONRAKI bekleyemez: dongu olur.
kutu["cevap"] = plan(True, "g", [
    {"baslik": "A", "sahip": "cinar", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["x/"], "bekler": [1]},
    {"baslik": "B", "sahip": "yaprak", "neden": "n", "kabul_olcutu": "k",
     "yazma_alani": ["y/"]},
])
try:
    ork.hedef_ver("Dongulu hedef", deneme=1)
    sina("ileri bagimlilik reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi as exc:
    sina("ileri bagimlilik reddediliyor", "bekleyemez" in str(exc).lower())

# --------------------------------------------------------------------------
print("\n5. HALKA DONUYOR -- isci kosar, lider inceler, is kapanir")
ork2 = Orkestra(ofis, motor_fabrikasi=fabrika)


def cevap_ver(metin):
    kutu["cevap"] = metin


# Isciler kanit uretir, lider kapatir.
kutu["cevap"] = ("Bitti.\nKANIT terminal: pytest -q -> 9 passed\n"
                 "KARAR: kapat")
adimlar = list(ork2.kos(azami_tik=6))
son_adim = adimlar[-1]
sina("dongu kendi kendine durdu", son_adim.get("bitti") is True)
sina("durma sebebi SOYLENIYOR", bool(son_adim.get("sebep")))
# Sabit sayi yerine DURUM sinanir: yeni bolumler is ekledikce sabit
# sayi kirilir ve test, davranis bozulmadan "kirmizi" verir.
kapanan = [g for g in ofis.tahta.liste() if g["durum"] == "bitti"]
acik = [g for g in ofis.tahta.liste()
        if g["durum"] in ("hazir", "calisiyor", "inceleme")]
sina("isler kapandi (insan mudahalesi YOK)", len(kapanan) >= 2 and not acik,
     f"-- {len(kapanan)} kapandi, {len(acik)} acik")
sina("kapanista kilitler birakildi",
     ofis.tahta.cakisan_kilitler(["api/", "web/"]) == [])
calisan = [a for a in adimlar if a.get("baslatilan")]
sina("en az bir tikta is baslatildi", len(calisan) >= 1)
incelenen = [a for a in adimlar if a.get("incelenen")]
sina("en az bir tikta inceleme yapildi", len(incelenen) >= 1)

# --------------------------------------------------------------------------
print("\n6. BEKLEYEN IS ILERLEME SAYILMIYOR")
kutu["cevap"] = plan(False, "Tek is, bolmeye gerek yok.", [
    {"baslik": "Bekleyen is", "sahip": "cinar", "neden": "n",
     "kabul_olcutu": "k", "yazma_alani": ["yeni/"]},
])
ork.hedef_ver("Ikinci hedef")
g = ofis.tahta.liste(durum="hazir")[0]
ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
# INSANA sorulan soru: ofis bunu cozemez, dongu durmali.
# (Bir AJANA sorulan soruyu ofis kendi cozer -- 6b'de sinaniyor.)
ofis.postane.soru_sor("cinar", "insan", "Hangi yol?", gorev_no=g["no"])

ozet = ork2.tik()
sina("bekleyen soru bildiriliyor",
     any(b["tur"] == "soru" for b in ozet["bekleyen"]))
sina("bekleyen ajana yeni is VERILMIYOR",
     not any(b["ajan"] == "cinar" for b in ozet["baslatilan"]))
sina("cevap UYDURULMADI", ofis.postane.insan_bekleyenler() != [])

adimlar = list(ork2.kos(azami_tik=3))
son_adim = adimlar[-1]
# Kelimeyi degil ANLAMI sina: durma sebebi insan bekleme olmali ve
# bekleyen istek listeyle birlikte gelmeli.
sina("dongu insan cevabi bekleyerek duruyor",
     son_adim.get("bitti") is True
     and "bekleniyor" in son_adim.get("sebep", "").lower()
     and any(b["tur"] == "soru" for b in son_adim.get("bekleyen", [])),
     f"-- {son_adim.get('sebep')}")

# --------------------------------------------------------------------------
print("\n6b. AJANA SORULAN SORUYU OFIS KENDI COZUYOR")
# KAPATILAN SESSIZ HATA: `soru_sor` aracinin varsayilan alicisi "lider"di
# ve lider bir AJANDIR. Lidere sorulan soru kimseye ulasmiyor, insanin
# kuyruguna dusup orada duruyordu -- ofis, liderin cevaplamasi gereken
# seyi sessizce insana havale ediyordu. Hata vermiyordu.
for x in ofis.postane.insan_bekleyenler():
    ofis.postane.cevapla(x["id"], "Insan cevabi")
g6 = ofis.tahta.liste(durum="calisiyor")[0]
ofis.postane.soru_sor("cinar", "demir", "Lidere sorum var", gorev_no=g6["no"])
sina("soru once AJAN kuyrugunda",
     len(ofis.postane.ajana_bekleyenler()) == 1)
sina("soru INSANIN kuyruguna DUSMEDI", ofis.postane.insan_bekleyenler() == [])

kutu["cevap"] = "Kendi klasorune yaz."
ozet = ork2.tik()
sina("ofis soruyu TESLIM ETTI",
     any(d["durum"] == "cevaplandi" for d in ozet["danisilan"]),
     f"-- {ozet['danisilan']}")
sina("ajan kuyrugu bosaldi", ofis.postane.ajana_bekleyenler() == [])
sina("danisma ILERLEME sayildi", ozet["ilerleme"] is True)
sina("cevap soran ajana ULASTI",
     any("kendi klasorune" in (c["cevap"] or "").lower()
         for c in ofis.postane.cevaplar("cinar")))

# --------------------------------------------------------------------------
print("\n7. CEVAP GELINCE IS SURUYOR (kilitlenme sinamasi)")
# OLCULDU: soru sorup cevap alan ajan, kendi yarim isini surdururken
# "mesgul" sayiliyordu; mesgul oldugu is tam da surdurmesi gereken isti
# ve dongu sonsuza kadar "ilerleme yok" diyordu.
# 6b insanin kuyrugunu bosaltti; bu sinama kendi sorusunu kurar.
g7 = ofis.tahta.liste(durum="calisiyor")[0]
ofis.postane.soru_sor("cinar", "insan", "Nereye yazayim?", gorev_no=g7["no"])
bekleyen_soru = ofis.postane.insan_bekleyenler()[0]
ofis.postane.cevapla(bekleyen_soru["id"], "Kendi klasorune yaz.")
kutu["cevap"] = "Tamam. KANIT terminal: pytest -q -> 3 passed"
ozet = ork2.tik()
sina("cevap gelince ajan KENDI isini surduruyor",
     any(i["ajan"] == "cinar" for i in ozet["baslatilan"]),
     f"-- baslatilan: {ozet['baslatilan']}")
sina("ilerleme kaydedildi", ozet["ilerleme"] is True)

# --------------------------------------------------------------------------
print("\n7b. GERCEK PARALELLIK -- ayrik isler AYNI ANDA kosuyor")
# OLCULDU: once bloke calisiyordu. Uc ayrik is, her biri ~0.55 sn,
# toplam 1.64 sn -- duvar saati islerin TOPLAMI idi. Kilit makinesi
# hic gercek cekisme gormemisti.
import time as _t
import tempfile as _tf
from ofis import Orkestra as _Ork


def _paralel_ofis(adet=3):
    _kok = Path(_tf.mkdtemp(prefix="ofis-par-"))
    _db = Veritabani(_kok / "o.sqlite3")
    _o = Ofis.proje_ac(_db, "Paralel", amac="a", basari_olcutu="b",
                       kok_klasor=str(_kok))
    _k = _o.kanat_ac("A", "A")
    _o.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=_k,
                    motor="sahte", klasor=str(_kok))
    for _i in range(adet):
        _o.kadro.ise_al(f"a{_i}", "yazilim", kanat_id=_k, motor="sahte",
                        klasor=str(_kok))
        _o.tahta.gorev_ac(f"Is {_i}", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=[f"alan{_i}/"],
                          kanat_id=_k)
    return _o


def _yavas_fabrika(ad, **ayar):
    return SahteMotor(gecikme=0.2,
                      cevap="Bitti KANIT terminal: kos -> gecti")


_sureler = {}
for _p in (1, 3):
    _o = _paralel_ofis()
    _ork = _Ork(_o, motor_fabrikasi=_yavas_fabrika)
    _bas = _t.monotonic()
    _oz = _ork.tik(paralel=_p)
    _sureler[_p] = _t.monotonic() - _bas
    if _p == 3:
        _ajanlar = [x["ajan"] for x in _oz["baslatilan"]]

sina("uc is de kosuldu", len(_ajanlar) == 3, f"-- {_ajanlar}")
# Ayni ajana iki is verilemez: atama tek iplikte yapilip ajan REZERVE
# edilmeseydi, iki iplik ayni bos ajani secerdi.
sina("AYNI ajana iki is verilmedi", len(set(_ajanlar)) == 3,
     f"-- {_ajanlar}")
sina("paralel SIRALIDAN hizli", _sureler[3] < _sureler[1] * 0.8,
     f"-- sirali {_sureler[1]:.2f} sn, paralel {_sureler[3]:.2f} sn")

# --------------------------------------------------------------------------
print("\n8. BOS HEDEF")
try:
    ork.hedef_ver("   ")
    sina("bos hedef reddediliyor", False, "-- kabul edildi!")
except OrkestraHatasi:
    sina("bos hedef reddediliyor", True)


# ---------------------------------------------------------------------------
# YAZMA ALANI RETTI LIDERE OGRETILIYOR MU -- yoksa COKUYOR mu
#
# Olculmus hata (21.09.2026): kapi yalniz `tahta.gorev_ac`taydi, yani
# plan kapilarindan SONRA calisiyordu ve oradan atilan istisna "ret
# ogretir" dongusunun DISINDA kaldi. `kabuk konus` bir Python
# traceback'iyle coktu; lider sebebi hic ogrenmedi.
#
# Ofisin kurali zaten yaziliydi: *"Erken ret ucuz."*
# ---------------------------------------------------------------------------
print("\n-- yazma alani retti: ogretiyor mu, cokuyor mu --")

import json as _json
import tempfile as _tf
from pathlib import Path as _P
from ofis import Ofis, Veritabani
from ofis.orkestra import Orkestra
from ofis.motor.tip import Motor, MotorOlayi

_akok = _P(_tf.mkdtemp(prefix="ofis-alanret-"))
(_akok / "proje").mkdir()
(_akok / "proje" / "kaynak").mkdir()
(_akok / "disarida").mkdir()          # kokun DISINDA, kardes
_ao = Ofis.proje_ac(Veritabani(_akok / "proje" / "o.sqlite3"), "AlanRet",
                    amac="a", basari_olcutu="b",
                    kok_klasor=str(_akok / "proje"))
_akn = _ao.kanat_ac("URUN", "UR")
_ao.kadro.ise_al("lidera", "lider", lider_mi=True, kanat_id=_akn,
                 klasor=str(_akok / "proje"), motor="sahte")
_ao.kadro.ise_al("iscia", "backend", kanat_id=_akn,
                 klasor=str(_akok / "proje"), motor="sahte")


class _PlanMotoru(Motor):
    """Once KOTU alan verir, ret metnini gorunce DUZELTIR.

    Boylece iki sey birden olculur: ret dongue giriyor mu, ve sebep
    gercekten lidere ULASIYOR mu. Yalniz "cokmedi" demek yetmez --
    cokmeyip sessizce yanlis plana devam etmek de bir hata olurdu.
    """
    ad = "planmotoru"
    mcp_konusur = False
    butce_destegi = False
    araclar_kapatilabilir = True
    #: Lidere gonderilen istemler -- ret sebebi icinde mi diye bakilir.
    istemler = []

    def musait_mi(self):
        return True

    def tur_kos(self, metin, **kw):
        _PlanMotoru.istemler.append(metin)
        # Ret metni isteme yazildiysa lider "ogrenmis" demektir.
        ogrendi = "proje kokunde YOK" in metin
        alan = "kaynak/yeni.py" if ogrendi else "disarida/motor"
        plan = {"boldu": False,
                "gerekce": "Tek is; bolmek jeton israfi olur.",
                "kollar": [{"baslik": "is", "neden": "n",
                            "ana_hedef": "h", "kabul_olcutu": "k",
                            "sahip": "iscia", "yazma_alani": [alan],
                            "bekler": []}]}
        yield MotorOlayi("basladi", "")
        yield MotorOlayi("metin", _json.dumps(plan, ensure_ascii=False))
        yield MotorOlayi("bitti", "", ek={"basarili": True, "jeton": 10,
                                          "maliyet_usd": 0.0})


_aork = Orkestra(_ao, motor_fabrikasi=lambda ad=None, **k: _PlanMotoru())

# Kotu alan verildiginde: COKMEMELI, plan gecmeli (ikinci denemede).
_hata_cikti = None
try:
    _aplan = _aork.hedef_ver("bir is yap", kanat_id=_akn, deneme=2)
except Exception as _exc:                       # noqa: BLE001 -- sinama
    _hata_cikti = f"{type(_exc).__name__}: {_exc}"

sina("kotu yazma alani COKERTMIYOR (traceback yok)",
     _hata_cikti is None, f"({_hata_cikti})")
# Donen sozlukteki anahtar `gorevler` -- ilk surumde `acilan` diye
# tahmin ettim ve sinama KALDI. Kod dogruydu, olcu yanlisti.
sina("ikinci denemede plan KABUL edildi",
     bool(_hata_cikti is None and _aplan and _aplan.get("gorevler")),
     f"({sorted(_aplan) if _hata_cikti is None else '-'})")

# RET GERCEKTEN OGRETILDI MI -- sebep lidere yazildi mi.
# "Cokmedi" yetmez: sessizce yanlis planla devam etmek de olurdu.
_ikinci = _PlanMotoru.istemler[1] if len(_PlanMotoru.istemler) > 1 else ""
sina("ret SEBEBI lidere iletildi (ret ogretir)",
     "proje kokunde YOK" in _ikinci,
     f"({_ikinci[-160:] if _ikinci else 'ikinci istem yok'})")
sina("acilan gorevin alani DUZELTILMIS olan",
     bool(_hata_cikti is None
          and _ao.tahta.liste() and
          "kaynak" in (_ao.tahta.liste()[0]["yazma_alani"] or [""])[0]),
     f"({_ao.tahta.liste()[0]['yazma_alani'] if _ao.tahta.liste() else None})")



# ---------------------------------------------------------------------------
# KAYNAK TUKENMESIYLE BIRAKILAN IS, ONCE ESKI SAHIBINE
#
# Olculdu (21.09.2026), bedeli $0,68: kilavuz isi butce tavaninda
# kesildi, `birak` sahibi bosaltti, bir sonraki tik BASKA bir bos ajani
# secti (cinar -> bilge) ve yeni ajan isi SIFIRDAN kostu. 1,15M jetonluk
# baglam cope gitti.
#
# "Kesilen tur bastan kosmasin" duzeltmesi zaten vardi ama oturum
# ajan+gorev ciftine ait: duzeltme yalnizca isi AYNI ajan geri alirsa
# calisiyordu ve bunu garanti eden hicbir sey yoktu.
# ---------------------------------------------------------------------------
print("\n-- kaynak tukenmesi: is eski sahibine mi donuyor --")

import tempfile as _stf
from pathlib import Path as _sP
from ofis import Ofis as _sOfis, Veritabani as _sVt
from ofis.orkestra import Orkestra as _sOrk

_skok = _sP(_stf.mkdtemp(prefix="ofis-sahip-"))
_so = _sOfis.proje_ac(_sVt(_skok / "o.sqlite3"), "Sahip",
                      amac="a", basari_olcutu="b", kok_klasor=str(_skok))
_skn = _so.kanat_ac("URUN", "UR")
# Adlar bilerek alfabetik: kadro sirasi "acinar"i once verir, yani
# tercih CALISMAZSA test yanlislikla gecmez.
for _ad in ("acinar", "bbilge"):
    _so.kadro.ise_al(_ad, "backend", kanat_id=_skn,
                     klasor=str(_skok), motor="sahte")
_sork = _sOrk(_so)


def _sahne(baslik, alan, sebep):
    """Isi bbilge alir, sonra VERILEN SEBEPLE birakilir."""
    _g = _so.tahta.gorev_ac(baslik, neden="n", ana_hedef="h",
                            kabul_olcutu="k", yazma_alani=[alan],
                            kanat_id=_skn)
    _so.tahta.sahiplen(_g["no"], "bbilge", _g["revizyon"])
    _so.tahta.birak(_g["no"], sebep=sebep)
    return _so.tahta.gorev(_g["no"])


sina("butce tavani -> ESKI sahibe donuyor",
     _sork._uygun_ajan(_sahne("t1", "api", "butce tavani doldu")) == "bbilge")
sina("kullanim limiti -> ESKI sahibe donuyor",
     _sork._uygun_ajan(_sahne("t2", "web", "kullanim limiti")) == "bbilge")
# TERS YON: gercek hatadan sonra tercih YAPILMAZ. Yoksa sinama "her
# zaman eski sahip" diyen bir kodla da gecerdi.
sina("GERCEK HATA -> tercih yok, temiz baslangic",
     _sork._uygun_ajan(_sahne("t3", "ops", "tur basarisiz (cikis 1)")) == "acinar")
sina("eski sahip REZERVE ise takilip kalmiyor",
     _sork._uygun_ajan(_sahne("t4", "x", "butce tavani doldu"),
                       rezerve={"bbilge"}) == "acinar")
# Sebep tanimi ODUNC alinmali, kopyalanmamali: devam karari veren yer
# ile sahip secen yer ayni tanimi kullanmazsa biri "devam edilebilir"
# der, oteki baska ajan secer ve devam HIC olmaz.
from ofis.koltuk import Koltuk as _sKoltuk
sina("sebep tanimi Koltuk'tan ODUNC alinmis (ikinci kopya yok)",
     all(_sork._kaynak_yuzunden_birakan(
         _sahne(f"s{_i}", f"z{_i}", _s)) == "bbilge"
         for _i, _s in enumerate(_sKoltuk.KAYNAK_SEBEPLERI)))

# EN SONA BIRAKILDI: faz makinesi TEK YONLUDUR, `basarisiz`tan geri
# donulemez (kadro.py'nin kendi kurali). Testin ilk surumu fazi geri
# almaya calisti ve dogru sekilde REDDEDILDI -- sinamanin kurdugu sahne,
# sinadigi sistemin kurallarina da uymak zorunda.
_so.kadro.faz_ayarla("bbilge", "basarisiz")
sina("eski sahip BASARISIZ fazda ise secilmiyor",
     _sork._uygun_ajan(_sahne("t5", "y", "butce tavani doldu")) == "acinar")


print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
