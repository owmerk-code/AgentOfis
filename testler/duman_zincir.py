# -*- coding: utf-8 -*-
"""Nobet zinciri duman testi: limit gelince is duruyor mu, devrediyor mu.

Olculmus ihtiyac (kullanicinin kendi sozleri): codex limiti dolmus,
fable tek promptta 5 saatlik limiti bitiriyor. Limit gunluk gercek.

Sinanan sey: limit gelince tur OLMUYOR, sonraki basamakla TEKRAR kosuyor;
devir karar gunlugune gerekcesiyle dusuyor; butce uygulayamayan basamak
butce istendiginde ATLANIYOR ve atlama gorunur oluyor; zincir tukenince
DURULUYOR.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis.motor import MotorHatasi
from ofis.motor.sahte import SahteMotor
from ofis.zincir import zincir_kur, elenenler, sonraki, ZincirBitti

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


print("== nobet zinciri duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-zincir-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Zincir Projesi", amac="Limit gelince is durmasin",
                     basari_olcutu="Devrediyor", kok_klasor=str(kok))
kanat = ofis.kanat_ac("ANA", "AN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  motor="sahte", model="sonnet", klasor=str(kok))
ofis.kadro.ise_al("cinar", "yazilim", kanat_id=kanat,
                  motor="sahte", model="opus", klasor=str(kok))

# --------------------------------------------------------------------------
print("1. ZINCIR KURULUMU")


def sahte_fabrika(ad, **ayar):
    # Gercek `motor_ac` bilinmeyen adi REDDEDER; test sahtesi de
    # reddetmeli, yoksa "kurulu degil" durumu hic olusmaz ve zincirin
    # eleme kapisi sinanmamis olur.
    if ad != "sahte":
        raise MotorHatasi(f"Bilinmeyen motor: {ad}")
    return SahteMotor(**ayar)


ajan = ofis.kadro.ajan("cinar")
zincir = [("sahte", "haiku"), ("sahte", "ucuz")]
basamaklar = zincir_kur(ajan, zincir=zincir, fabrika=sahte_fabrika)
# Basamak sozlugu BUYUYEBILIR (hesap katmani `hesap`/`ortam` ekledi).
# Tam esitlik aramak, her yeni alanda bu testi kirardi -- oysa sinanan
# sey "ilk basamak ajanin kendi ayari mi", sozlugun bicimi degil.
sina("ILK basamak ajanin KENDI ayari",
     (basamaklar[0]["motor"], basamaklar[0]["model"]) == ("sahte", "opus"),
     f"-- {basamaklar[0]}")
# Ortuk (hesapsiz) basamak, bugunku davranisi korur: CLI kendi oturumu.
sina("hesapsiz basamak KIMLIK KURMUYOR",
     basamaklar[0]["hesap"] == "" and basamaklar[0]["ortam"] == {})
sina("yedekler arkaya eklendi", len(basamaklar) == 3)
sina("tekrar eden basamak elenmis",
     len({(b["motor"], b["model"]) for b in basamaklar}) == 3)

# Kurulu olmayan motor atlanir -- olmayan motora devretmek turu bir kez
# daha oldururdu.
basamaklar_yok = zincir_kur(ajan, zincir=[("yokmotor", "")],
                            fabrika=sahte_fabrika)
sina("kurulu olmayan motor zincire ALINMIYOR",
     all(b["motor"] != "yokmotor" for b in basamaklar_yok))

# --------------------------------------------------------------------------
print("\n2. BUTCE KAPISI -- atlamak YOK, OFIS FRENI var")
# SOZLESME DEGISTI (22.09.2026). Onceden: tavan uygulayamayan basamak
# ATLANIYORDU. Mantik dogruydu ama olculmus sonucu agirdi -- "tavan
# koy" demek pratikte "codex'i KAPAT" demekti ve `cinar` aylarca codex
# ayarliyken her turu Claude'da kosti. Kullanici cok motorlu bir
# sistem istiyor; her yeni motor ayni duvara carpardi.
#
# GEVSEME DEGIL, YER DEGISTIRME: kontrol CLI'dan OFISE tasindi.
# Basamak kosar ama `ofis_freni` ile isaretlenir; koltuk o turda kacak
# freni + birikmis jeton tavani uygular ve dolar tavaninin
# UYGULANMADIGINI gorunur bir uyariyla soyler.
b_butceli = zincir_kur(ajan, butce_usd=1.0, zincir=zincir,
                       fabrika=sahte_fabrika)
sina("butcesiz basamak ARTIK ATLANMIYOR", len(b_butceli) >= 1,
     f"-- {b_butceli}")
sina("ama OFIS FRENI ile isaretleniyor",
     all(b.get("ofis_freni") for b in b_butceli),
     str([b.get("ofis_freni") for b in b_butceli]))
# Ters yon: tavan ISTENMEDIYSE fren bayragi da yanmamali -- yoksa
# "hep fren" diyen bir kod da sinamayi gecerdi.
b_tavansiz = zincir_kur(ajan, zincir=zincir, fabrika=sahte_fabrika)
sina("tavan istenmediyse fren bayragi YOK",
     not any(b.get("ofis_freni") for b in b_tavansiz))
# Ve "butce uygulayamiyor" ARTIK bir eleme sebebi degil: calisan bir
# basamagi insana "elendi" diye gostermek, yanlis gosteren gostergedir.
elenen = elenenler(ajan, butce_usd=1.0, zincir=zincir, fabrika=sahte_fabrika)
sina("butce artik ELEME sebebi degil",
     not any("butce" in e["sebep"] for e in elenen), f"-- {elenen}")

# --------------------------------------------------------------------------
print("\n3. ZINCIR TUKENIRSE DURULUR")
try:
    sonraki(basamaklar, len(basamaklar) - 1)
    sina("zincir sonunda DURULUYOR", False, "-- devam etti!")
except ZincirBitti:
    sina("zincir sonunda DURULUYOR", True)

# --------------------------------------------------------------------------
print("\n4. GERCEK DEVIR -- ilk basamak limit, ikincisi basarili")
#: Senaryo cagri SAYISINA degil MODELE baglanir: `zincir_kur` musaitlik
#: sorarken de fabrikayi cagiriyor ve sayac erken tukeniyordu.
#: Deterministik olmayan test, sinadigi seyi degil kendini olcer.
kosanlar = []


class ModeleGoreMotor(SahteMotor):
    """Ilk basamak (opus) LIMIT verir, sonraki basamaklar calisir."""

    def tur_kos(self, metin, **ayar):
        model = ayar.get("model") or ""
        kosanlar.append(model)
        self.senaryo = "limit" if model == "opus" else "basarili"
        return super().tur_kos(metin, **ayar)


def devirli_fabrika(ad, **ayar):
    if ad != "sahte":
        raise MotorHatasi(f"Bilinmeyen motor: {ad}")
    return ModeleGoreMotor(
        cevap="Bitti." + chr(10) + "KANIT terminal: pytest -q -> 7 passed")


koltuk = Koltuk(ofis, motor_fabrikasi=devirli_fabrika,
                zincir=[("sahte", "haiku")])
g = ofis.tahta.gorev_ac("Devir sinamasi", neden="Limit gelince durmasin",
                        ana_hedef="Zincir calissin",
                        kabul_olcutu="Kanit gelsin", yazma_alani=["a/"],
                        kanat_id=kanat)

olaylar = []
for o in koltuk.akit(g["no"], "cinar", zaman_asimi=5):
    olaylar.append(o)

turler = [o["tur"] for o in olaylar]
sina("limit olayi gorunur oldu", "limit" in turler)
sina("ONCE opus kostu, SONRA baska model", 
     len(kosanlar) >= 2 and kosanlar[0] == "opus" and kosanlar[1] != "opus",
     f"-- {kosanlar}")
sina("devir sonrasi is BASARILI bitti",
     any(o["tur"] == "tur_bitti" and o["ek"].get("basarili") for o in olaylar))
sina("kanit tahtaya dustu", len(ofis.tahta.kanitlar(g["no"])) == 1)
sina("gorev INCELEMEYE gitti",
     ofis.tahta.gorev(g["no"])["durum"] == "inceleme")

devir_karari = [k for k in ofis.bellek.son_kararlar(10)
                if "ile kosuldu" in k["karar"]]
sina("devir KARAR GUNLUGUNE yazildi", len(devir_karari) == 1,
     f"-- {len(devir_karari)}")
sina("devir kararinin gerekcesi var",
     bool(devir_karari and "limit" in devir_karari[0]["gerekce"].lower()))

# --------------------------------------------------------------------------
print("\n5. ZINCIR TUKENIRSE IS OLMEZ, BEKLER")
sayac2 = {"n": 0}


class HepLimitMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        # KOSAN turu say, musaitlik sorgusunu degil.
        sayac2["n"] += 1
        return super().tur_kos(metin, **ayar)


def hep_limit(ad, **ayar):
    if ad != "sahte":
        raise MotorHatasi(f"Bilinmeyen motor: {ad}")
    return HepLimitMotor(senaryo="limit")


koltuk2 = Koltuk(ofis, motor_fabrikasi=hep_limit,
                 zincir=[("sahte", "haiku")])
g2 = ofis.tahta.gorev_ac("Hep limit", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["b/"], kanat_id=kanat)
olaylar2 = [o for o in koltuk2.akit(g2["no"], "cinar", zaman_asimi=5)]
sina("butun basamaklar GERCEKTEN kosuldu", sayac2["n"] == 2,
     f"-- {sayac2['n']} tur")
sina("zincir bitti UYARISI verildi",
     any(o["tur"] == "uyari" and o["ek"].get("zincir_bitti")
         for o in olaylar2))
sina("is basarisiz isaretlendi",
     any(o["tur"] == "tur_bitti" and not o["ek"].get("basarili")
         for o in olaylar2))
sina("kilit birakildi (is yeniden dagitilabilir)",
     ofis.tahta.cakisan_kilitler(["b/"]) == [])

# ------------------------------------------------ IKINCI HESAP SIRASI
#
# OLCULMUS KUSUR (22.09.2026): ikinci Plus hesabi eklenince gercek
# ofiste codex ajaninin zinciri su oldu -- ikinci hesap 6. sirada,
# onunde AYNI dolmus hesabi iki kez deneyen ve MODELSIZ (hesabin
# varsayilanina dusen) basamaklar. "Limit dolunca oteki hesaba gec"
# pratikte calismiyordu; is Claude'a gidiyordu.
print("")
print("9. IKINCI HESAP -- ilk yedek, ayni model, tekrar yok, modelsiz yok")
from ofis import roller as _roller


def _hepsi_fabrika(ad, **ayar):
    if ad not in ("sahte", "claude", "codex", "gemini"):
        raise MotorHatasi(f"Bilinmeyen motor: {ad}")
    return SahteMotor(**ayar)


_codex_ajan = {"ad": "c", "motor": "codex", "model": "gpt-5.6-sol",
               "meslek": "backend"}
_hesaplar = [
    {"ad": "claude", "motor": "claude", "aktif": True, "ortam": {},
     "_cozulmus_ortam": {}},
    {"ad": "codex", "motor": "codex", "aktif": True, "ortam": {},
     "_cozulmus_ortam": {}},
    {"ad": "codex2", "motor": "codex", "aktif": True,
     "ortam": {"CODEX_HOME": "~/x2"}, "_cozulmus_ortam": {"CODEX_HOME": "/x2"}},
]
_z = zincir_kur(_codex_ajan, zincir=[("claude", "sonnet"), ("codex", "")],
                fabrika=_hepsi_fabrika, hesaplar=_hesaplar)
_ozet = [(b["motor"], b["model"], b["hesap"]) for b in _z]
sina("ayni motorun ikinci hesabi ILK YEDEK", len(_z) > 1 and _z[1]["hesap"] == "codex2",
     str(_ozet))
sina("ikinci hesap ajanin MODELINI koruyor",
     len(_z) > 1 and _z[1]["model"] == "gpt-5.6-sol", str(_ozet))
sina("kimliksiz ayni-motor hesabi (dolmus hesabin kendisi) ATLANDI",
     not any(b["hesap"] == "codex" for b in _z), str(_ozet))
sina("genel zincirde ayni motorun MODELSIZ tekrari ATLANDI",
     not any(b["motor"] == "codex" and not b["model"] for b in _z), str(_ozet))
_kademe = _roller.rol("backend").kademe
_claude_hesap = [b for b in _z if b["hesap"] == "claude"]
sina("baska motora gecen hesap KADEMEDEN model aliyor (bos degil)",
     bool(_claude_hesap) and _claude_hesap[0]["model"]
     == _roller.KADEME_MODEL["claude"][_kademe], str(_ozet))

# Kural 2'nin TEK BASINA yakaladigi hal: kimliksiz hesaba acikca BASKA
# model verilmis. Tekrar-kapisi (motor, model) esitligine baktigi icin
# bunu goremez -- ama kimlik ayni, yani dolmus hesabi baska modelle
# denemek. Bu sinama olmasaydi kural 2 ates edemeyen bir kapi olurdu.
_h_model = [dict(_hesaplar[1], model="gpt-5.6-luna")]
_zm = zincir_kur(_codex_ajan, zincir=[], fabrika=_hepsi_fabrika, hesaplar=_h_model)
sina("kimliksiz ayni-motor hesabi ACIK modelle de atlaniyor",
     not any(b["hesap"] == "codex" for b in _zm),
     str([(b["motor"], b["model"], b["hesap"]) for b in _zm]))

# Ters yon: liderin codex yedegi de modelsiz kalmamali -- bos model
# codex'in varsayilanina duser (olculmedi; Astra olabilir, otomatik
# yollardan bilerek cikarilmis tavansiz model).
_lider = {"ad": "l", "motor": "claude", "model": "opus", "meslek": "lider"}
_zl = zincir_kur(_lider, zincir=[("claude", "sonnet"), ("codex", "")],
                 fabrika=_hepsi_fabrika, hesaplar=_hesaplar)
_ozl = [(b["motor"], b["model"], b["hesap"]) for b in _zl]
sina("genel zincirin baska-motor yedegi MODELSIZ degil",
     all(b["model"] for b in _zl if b["motor"] == "codex"), str(_ozl))
_kim = [(b["motor"], b["model"], tuple(sorted(b["ortam"].items()))) for b in _zl]
sina("ayni kimlik+model IKI KEZ denenmiyor", len(_kim) == len(set(_kim)), str(_ozl))


# ---------------------------------------------------------------------------
print("\n-- LIDERIN ZINCIRI: limit dolunca lider DURMAZ --")
# Olculen bosluk: zincir yalniz iscilerdeydi. Liderin turlari dogrudan
# kendi motorunda kosuyordu; Claude limiti dolunca lider -- ve onunla
# butun ofis -- dururdu.
import json as _json
from ofis.orkestra import Orkestra
from ofis.lider import Lider
from ofis.zincir import LIDER_ZINCIRI, limitte_devret

def _sorgu(sql, arg=()):
    with db.baglanti() as c:
        return [dict(r) for r in c.execute(sql, arg).fetchall()]

# (a) limitte_devret -- saf davranis
_cagri, _devir = [], []
def _kos(b):
    _cagri.append(b["motor"])
    return ({"limit": b["motor"] == "a", "basarili": b["motor"] != "a"}, ["x"])
_s = limitte_devret([{"motor": "a"}, {"motor": "b"}, {"motor": "c"}], _kos,
                    devir=lambda e, y: _devir.append((e["motor"], y["motor"])))
sina("limitte SONRAKI basamak kosuyor", _s[0]["motor"] == "b" and _cagri == ["a", "b"], str(_cagri))
sina("devir tam BIR kez cagriliyor", _devir == [("a", "b")], str(_devir))
_cagri.clear(); _devir.clear()
limitte_devret([{"motor": "b"}, {"motor": "c"}], _kos, devir=lambda e, y: _devir.append(1))
sina("limit yoksa yedek HIC kosmuyor", _cagri == ["b"] and not _devir, str(_cagri))
_cagri.clear()
_s = limitte_devret([{"motor": "a"}, {"motor": "a"}], _kos, devir=lambda e, y: None)
sina("zincir tukenince SON sonuc donuyor (sonsuz devir yok)",
     _cagri == ["a", "a"] and _s[1].get("limit"), str(_cagri))
try:
    limitte_devret([], _kos, devir=lambda e, y: None)
    sina("bos zincir reddediliyor", False)
except ZincirBitti:
    sina("bos zincir reddediliyor", True)

# (b) GERCEK yol: orkestra lider turu. claude limit verir, codex tamamlar.
_kayit = []
class _Kayitli(SahteMotor):
    def __init__(self, ad, **kw):
        super().__init__(**kw); self.ad = ad
        # claude tavan uygular, codex uygulamaz -- gercegi taklit et.
        self.butce_destegi = ad == "claude"
    def tur_kos(self, metin, **ayar):
        _kayit.append((self.ad, ayar.get("model"), ayar.get("butce_usd")))
        yield from super().tur_kos(metin, **ayar)

def _lider_fabrika(ad, **kw):
    if ad == "claude":
        return _Kayitli("claude", senaryo=_CLAUDE_SENARYO[0], cevap="CLAUDE-PLAN")
    if ad == "codex":
        return _Kayitli("codex", cevap="CODEX-PLAN\nKARAR: kapat")
    raise MotorHatasi(f"{ad} kurulu degil")
_CLAUDE_SENARYO = ["limit"]

ofis.kadro.ise_al("lale", "lider", motor="claude", model="opus",
                  klasor=str(kok / "lale"), lider_mi=True,
                  kanat_id=ofis.kanat_ac("LIDERLIK", "LD"))
_lale = ofis.kadro.ajan("lale")
_ork = Orkestra(ofis, motor_fabrikasi=_lider_fabrika)
_sayi0 = len(_sorgu("SELECT id FROM karar WHERE proje_id=?", (ofis.proje_id,)))
_kayit.clear()
# Cokmez: lider turu dusse bile (eski davranis) geri kalan sinamalar kossun.
try:
    _metin = _ork._lideri_kostur(_lale, "plan yap", 0.5, 30)
except Exception as _exc:
    _metin = f"DUSTU: {_exc}"
sina("claude LIMITTE -> lider codex'te TAMAMLADI", "CODEX-PLAN" in _metin, _metin[:60])
sina("once claude, sonra codex denendi",
     [k[0] for k in _kayit] == ["claude", "codex"], str(_kayit))
from ofis import roller as _rl
_guclu = _rl.kademe_haritasi(db, ofis.proje_id)["codex"]["guclu"]
sina("codex yedegi rolun KADEMESINDEN model aldi (bos degil)",
     len(_kayit) > 1 and _kayit[1][1] == _guclu, str(_kayit))
sina("dolar tavani yalniz UYGULAYABILENE gitti (codex'e None)",
     len(_kayit) > 1 and _kayit[0][2] == 0.5 and _kayit[1][2] is None, str(_kayit))
_kararlar = _sorgu("SELECT karar, tur FROM karar WHERE proje_id=? ORDER BY rowid",
                     (ofis.proje_id,))
_devir_k = [k for k in _kararlar[_sayi0:] if "yerine" in k["karar"]]
sina("devir KARAR gunlugune yazildi", bool(_devir_k) and _devir_k[0]["tur"] == "teknik",
     str([k["karar"] for k in _kararlar[_sayi0:]]))
_lim = _sorgu("SELECT govde FROM olay WHERE proje_id=? AND tur='limit' AND ajan_ad='lale'",
                (ofis.proje_id,))
sina("devir GORUNUR limit olayi", any("codex" in o["govde"] for o in _lim), str(_lim))
_oz = [_json.loads(o["govde"]) for o in _sorgu(
    "SELECT govde FROM olay WHERE proje_id=? AND tur='tur_ozeti' AND ajan_ad='lale'",
    (ofis.proje_id,))]
sina("IKI tur da olculdu, dogru motorla",
     sorted(o.get("motor") for o in _oz if o.get("yol") == "lider") == ["claude", "codex"],
     str([(o.get("motor"), o.get("yol")) for o in _oz]))

# Ters yon: claude calisiyorsa codex HIC uyanmaz.
_CLAUDE_SENARYO[0] = "basarili"
_kayit.clear()
_metin = _ork._lideri_kostur(_lale, "plan yap", None, 30)
sina("limit yoksa yedek HIC kosmuyor (gercek yol)",
     [k[0] for k in _kayit] == ["claude"] and "CLAUDE-PLAN" in _metin, str(_kayit))

# (c) INCELEME de zincirli: claude limitte, codex hukum verir, is kapanir.
_CLAUDE_SENARYO[0] = "limit"
ofis.kadro.ise_al("ilke", "backend", motor="claude", model="sonnet",
                  klasor=str(kok / "ilke"), kanat_id=_lale["kanat_id"])
_g = ofis.tahta.gorev_ac("Zincirli inceleme", neden="s", ana_hedef="s",
                         kabul_olcutu="y", sahip="ilke", kanat_id=_lale["kanat_id"])
ofis.tahta.sahiplen(_g["no"], "ilke", _g["revizyon"])
ofis.tahta.kanit_ekle(_g["no"], "terminal", "pytest", "2 passed", "ilke")
ofis.tahta.incelemeye_ver(_g["no"], ofis.tahta.gorev(_g["no"])["revizyon"])
_kayit.clear()
Lider(ofis, motor_fabrikasi=_lider_fabrika).incele(_g["no"], lider_ad="lale")
sina("inceleme claude limitinde codex'te HUKUM verdi -> is kapandi",
     ofis.tahta.gorev(_g["no"])["durum"] == "bitti",
     f"{ofis.tahta.gorev(_g['no'])['durum']} {_kayit}")
_gk = _sorgu("SELECT karar FROM karar WHERE proje_id=? AND gorev_id=? AND karar LIKE '%yerine%'",
               (ofis.proje_id, _g["id"]))
sina("incelemenin devri GOREVLE etiketli kayitta", bool(_gk), str(_gk))


# ---------------------------------------------------------------------------
print("\n-- ISCI DEVIR PAKETI: yeni motor KALDIGI YERDEN devam etsin --")
# Olculen iki bosluk: (1) devam turunda limit gelince yeni motora yalniz
# UYANIS FARKI gidiyordu -- oturumu olmayan motor isin ne oldugunu
# bilmiyordu. (2) Yeni motor yarida kalan turda diskte ne degistigini,
# ajanin son notunu hic gormuyordu.
from ofis.motor.tip import MotorOlayi
from ofis.koltuk import Koltuk as _Koltuk

_metinler = {}

class _DevirMotoru(SahteMotor):
    # Ilk basamak claude gibi KANCALI, ikincisi codex gibi KANCASIZ ve
    # kanca verilince turu HIC baslatmiyor. Olculen hata tam buydu:
    # kanca devirde codex'e tasiniyordu.
    def __init__(self, kanca=True, **kw):
        super().__init__(**kw)
        self.izin_kancasi = kanca

    def tur_kos(self, metin, **ayar):
        model = ayar.get("model")
        if not self.izin_kancasi and ayar.get("izin_araci"):
            raise MotorHatasi("izin kancasini uygulayamiyor")
        _metinler[model] = metin
        yield MotorOlayi("oturum", "m", {"oturum_id": "oturum-" + model})
        if model == "birinci":
            hedef = Path(ayar["klasor"]) / "devir"
            hedef.mkdir(exist_ok=True)
            (hedef / "a.txt").write_text("ilk yarim\n", encoding="utf-8")
            yield MotorOlayi("metin", "a.txt yazildi.\nDURUM: a.txt yazildi | sirada b.txt\n")
            yield MotorOlayi("limit", "exhausted", {"status": "exhausted"})
            yield MotorOlayi("bitti", "", {"basarili": False, "limit": True,
                                           "oturum_id": "oturum-birinci",
                                           "model": model, "jeton": 10})
            return
        yield MotorOlayi("metin", "b.txt de yazildi.\nKANIT dosya: devir/a.txt -> var\n")
        yield MotorOlayi("bitti", "", {"basarili": True, "limit": False,
                                       "oturum_id": "oturum-ikinci",
                                       "model": model, "jeton": 10})

def _devir_fabrika(ad, **kw):
    if ad == "sahte":
        return _DevirMotoru(kanca=True)
    if ad == "sahte2":
        return _DevirMotoru(kanca=False)
    raise MotorHatasi(f"Bilinmeyen motor: {ad}")

ofis.kadro.ise_al("ela", "yazilim", kanat_id=kanat, motor="sahte",
                  model="birinci", klasor=str(kok))
_g = ofis.tahta.gorev_ac("Devir isi", neden="s", ana_hedef="s",
                         kabul_olcutu="a.txt ve b.txt", sahip="ela",
                         yazma_alani=["devir"], kanat_id=kanat)
# DEVAM kosulunu KUR: gorev ajanda ve calisiyor, oturum var. Hatanin
# yasadigi sahne tam bu -- kurulmazsa test sinira hic ulasmaz.
ofis.tahta.sahiplen(_g["no"], "ela", _g["revizyon"])
ofis.kadro.oturum_kaydet("ela", "eski-oturum")

_Koltuk(ofis, motor_fabrikasi=_devir_fabrika,
        zincir=[("sahte2", "ikinci")]).kos(_g["no"], "ela")
_bir, _iki = _metinler.get("birinci", ""), _metinler.get("ikinci", "")
sina("sahne sinira ulasti: ilk tur DEVAM metniyle kostu (K1 yok)",
     bool(_bir) and "K1" not in _bir, _bir[:80])
# K1 ile ayirt edilir: devam metni de K4 tasir, yani "K4 var" eski
# hatayi GORMEZDI (mutasyon bunu gosterdi).
sina("yeni motor TAM brifing aldi (K1 + K4 var)", "K1" in _iki and "K4" in _iki, _iki[:80])
sina("yeni motor DEVIR paketini aldi", "DEVIR" in _iki)
sina("paket kesilen turun DISK farkini tasiyor",
     "devir/a.txt" in _iki.replace(chr(92), "/"))
sina("paket ajanin DURUM notunu tasiyor", "sirada b.txt" in _iki)
sina("paket kesilen turun son sozunu tasiyor", "Kesilen turun son sozu" in _iki)

def _sorgu2(sql, arg=()):
    with db.baglanti() as c:
        return [dict(r) for r in c.execute(sql, arg).fetchall()]

_notlar = _sorgu2("SELECT govde FROM olay WHERE tur='durum_notu' AND gorev_id=?",
                  (_g["id"],))
sina("durum notu DEFTERE yazildi (tek kez)", len(_notlar) == 1, str(_notlar))
_dg = [r["yol"] for r in _sorgu2("SELECT yol FROM degisim WHERE gorev_id=?",
                                 (_g["id"],))]
sina("devir brifingi ajanin degisikligi gibi GORUNMUYOR (BRIFING.md yok)",
     not any("BRIFING" in y for y in _dg), str(_dg))
sina("is yeni motorda bitti, incelemeye gitti",
     ofis.tahta.gorev(_g["no"])["durum"] == "inceleme",
     ofis.tahta.gorev(_g["no"])["durum"])

# Ayni not ikinci kez yazilmaz.
_Koltuk(ofis, motor_fabrikasi=_devir_fabrika)._durum_notu_yaz(
    _g["no"], "ela", ofis.tahta.gorev(_g["no"]), ["DURUM: a.txt yazildi | sirada b.txt"])
# Gercek akisin bicimi: parcalar arasinda YENI SATIR YOK. Olculen hata
# tam buydu -- satir basi arayan desen bunu kaciriyordu.
_g4 = ofis.tahta.gorev_ac("Parcali akis", neden="s", ana_hedef="s",
                          kabul_olcutu="y", kanat_id=kanat)
_Koltuk(ofis, motor_fabrikasi=_devir_fabrika)._durum_notu_yaz(
    _g4["no"], "ela", ofis.tahta.gorev(_g4["no"]),
    ["Kanit ekliyorum.", "DURUM: x.txt yazildi | sirada y.txt"])
_n4 = _sorgu2("SELECT govde FROM olay WHERE tur='durum_notu' AND gorev_id=?",
              (ofis.tahta.gorev(_g4["no"])["id"],))
sina("PARCALI akista (yeni satirsiz) durum notu yakalaniyor",
     [r["govde"] for r in _n4] == ["x.txt yazildi | sirada y.txt"], str(_n4))
_g5 = ofis.tahta.gorev_ac("Siradan metin", neden="s", ana_hedef="s",
                          kabul_olcutu="y", kanat_id=kanat)
_Koltuk(ofis, motor_fabrikasi=_devir_fabrika)._durum_notu_yaz(
    _g5["no"], "ela", ofis.tahta.gorev(_g5["no"]),
    ["Genel durum: iyi gidiyor, devam."])
sina("siradan 'durum:' kelimesi not SAYILMIYOR",
     not _sorgu2("SELECT id FROM olay WHERE tur='durum_notu' AND gorev_id=?",
                 (ofis.tahta.gorev(_g5["no"])["id"],)))
sina("ayni durum notu TEKRAR yazilmiyor",
     len(_sorgu2("SELECT id FROM olay WHERE tur='durum_notu' AND gorev_id=?",
                 (_g["id"],))) == 1)

# Sonraki TAZE tur (baska ajan, oturumsuz) defterden paketi alir.
_b2 = ofis.brifing.uret(_g["no"], "cinar", diske_yaz=False)["metin"]
sina("sonraki taze tur paketi DEFTERDEN aliyor",
     "DEVIR" in _b2 and "sirada b.txt" in _b2 and "devir/a.txt" in _b2.replace(chr(92), "/"))
# Ters yon: gecmisi olmayan is paket TASIMAZ -- uydurma gecmis yok.
_g3 = ofis.tahta.gorev_ac("Yepyeni is", neden="s", ana_hedef="s",
                          kabul_olcutu="y", kanat_id=kanat)
sina("gecmisi olmayan iste DEVIR blogu YOK",
     "DEVIR" not in ofis.brifing.uret(_g3["no"], "cinar", diske_yaz=False)["metin"])
sina("tam brifing DURUM talimatini veriyor",
     "DURUM:" in ofis.brifing.uret(_g3["no"], "cinar", diske_yaz=False)["metin"])


# ---------------------------------------------------------------------------
print("\n-- ONCEDEN GECIS: dolmak UZERE olan hesaba yeni tur baslatilmaz --")
import time as _time
from ofis import kullanim as _kul
from ofis.zincir import basamaklari_kur as _bk

def _olcum_yaz(motor, k5, *, yenilenme=None):
    _kul.tur_ozeti_yaz(db, ofis.proje_id, {"limit_pencere": {
        "kaynak": "test", "hal": "allowed", "plan": "",
        "pencereler": {"5s": {"kullanim": k5,
                              "yenilenme": yenilenme or int(_time.time()) + 3600}}}},
        motor=motor, hesap="")

_ela = ofis.kadro.ajan("ela")
def _sira(rol="isci"):
    b, u = _bk(db, ofis.proje_id, _ela, fabrika=_devir_fabrika,
               zincir=[("sahte2", "ikinci")], rol=rol)
    return [x["motor"] for x in b], u

_m, _u = _sira()
sina("olcum yokken sira DEGISMIYOR", _m[:2] == ["sahte", "sahte2"], str(_m))
_olcum_yaz("sahte", 0.90)
_m, _u = _sira()
sina("isci: %90 (esik %80) -> hesap SONA alindi", _m[:2] == ["sahte2", "sahte"], str(_m))
sina("gecis GORUNUR not uretiyor",
     any("ONCEDEN GECIS" in x and "%90" in x for x in _u), str(_u))
sina("hesap SILINMIYOR, yalniz sona aliniyor", "sahte" in _m)
_m, _u = _sira("lider")
sina("lider: %90 (esik %95) -> sira DEGISMIYOR", _m[0] == "sahte", str(_m))
db.ayar_yaz(ofis.proje_id, "gecis_esigi:isci:5s", "0.95")
_m, _u = _sira()
sina("esik AYARDAN okunuyor (0.95 -> gecis yok)", _m[0] == "sahte", str(_m))
db.ayar_yaz(ofis.proje_id, "gecis_esigi:isci:5s", "bozuk")
_m, _u = _sira()
sina("bozuk ayar varsayilana duser ve SOYLENIR",
     _m[0] == "sahte2" and any("okunamadi" in x for x in _u), str(_u))
db.ayar_yaz(ofis.proje_id, "gecis_esigi:isci:5s", "")
db.ayar_yaz(ofis.proje_id, "onceden_gecis", "kapali")
_m, _u = _sira()
sina("onceden gecis KAPATILABILIYOR", _m[0] == "sahte", str(_m))
db.ayar_yaz(ofis.proje_id, "onceden_gecis", "acik")

# Uctan uca: koltuk bu tur KANCASIZ ikinci motorla baslar.
_metinler.clear()
_g6 = ofis.tahta.gorev_ac("Gecis isi", neden="s", ana_hedef="s", kabul_olcutu="y",
                          sahip="ela", yazma_alani=["gecis"], kanat_id=kanat)
_Koltuk(ofis, motor_fabrikasi=_devir_fabrika,
        zincir=[("sahte2", "ikinci")]).kos(_g6["no"], "ela")
sina("koltuk turu DOLMAK UZERE olmayan hesapla baslatti",
     list(_metinler) == ["ikinci"], str(list(_metinler)))
sina("gecis tur olaylarinda GORUNUR",
     bool(_sorgu2("SELECT id FROM olay WHERE tur='uyari' AND gorev_id=? "
                  "AND govde LIKE '%ONCEDEN GECIS%'", (ofis.tahta.gorev(_g6["no"])["id"],))))

_olcum_yaz("sahte2", 0.95)
_m, _u = _sira()
sina("hepsi esikteyse sira DEGISMIYOR ve soyleniyor",
     _m[0] == "sahte" and any("butun hesaplar" in x for x in _u), str(_u))
_olcum_yaz("sahte", 0.99, yenilenme=int(_time.time()) - 60)
_olcum_yaz("sahte2", 0.10)
_m, _u = _sira()
sina("YENILENMIS pencerenin eski yuzdesi gecis SEBEBI olmuyor", _m[0] == "sahte", str(_m))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
