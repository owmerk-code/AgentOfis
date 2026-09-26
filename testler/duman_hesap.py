# -*- coding: utf-8 -*-
"""HESAP katmani: motor NASIL, hesap KIMIN adina.

Kullanici (20.09.2026): *"abonelik hesaplari degisebilir veya api ile de
kullaniriz; ilerde COKLU HESAP bile olabilir."*

Sinanan uc sey:

1. **Anahtar veritabanina YAZILMIYOR.** `ortam` bir REFERANS tutar
   (`@gizli:ISIM`); gercek deger tur aninda proje kokunun DISINDAKI
   depodan cozulur. Ajanlarin `Bash(cat *)` izni var -- anahtar
   defterde olsaydi okunabilirdi.

2. **Cozulemeyen kimlik HATA, bos deger degil.** Bos bir
   `ANTHROPIC_API_KEY` ile kosmak, hesabin kimliginin sessizce
   kaybolmasi demektir.

3. **Zincir hesaplar uzerinde yuruyor** -- ve hesabin verdigi ortam
   adaptorun varsayilanini EZIYOR. Ters olsaydi ikinci bir codex
   hesabi tanimlanabilir ama hicbir zaman kullanilamazdi.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis import hesap as H
from ofis.motor.sahte import SahteMotor
from ofis.zincir import zincir_kur

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


kok = Path(tempfile.mkdtemp(prefix="ofis-hesap-"))
print(f"klasor: {kok}")
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Hesap",
                     amac="hesap sinamasi", basari_olcutu="testler gecer")
(kok / "w").mkdir()
ofis.kadro.ise_al("cinar", "backend", motor="sahte", model="opus",
                  klasor=str(kok / "w"))

# ----------------------------------------------------------- 1. TEMEL
print("\n1. hesap ekleme ve kapilar")

h1 = H.ekle(ofis.db, ofis.proje_id, "sahte-bir", "sahte",
            tur="abonelik", plan="max5", sira=10)
sina("hesap eklendi", h1["ad"] == "sahte-bir")
sina("tur saklandi", h1["tur"] == "abonelik")
sina("plan hesaba ait", h1["plan"] == "max5")
sina("varsayilan aktif", h1["aktif"] is True)

try:
    H.ekle(ofis.db, ofis.proje_id, "sahte-bir", "sahte")
    sina("ayni ad IKI KEZ eklenemiyor", False, "-- kabul edildi!")
except H.HesapHatasi:
    sina("ayni ad IKI KEZ eklenemiyor", True)

try:
    H.ekle(ofis.db, ofis.proje_id, "kotu", "yepyeni-motor")
    sina("bilinmeyen motor reddedildi", False, "-- kabul edildi!")
except H.HesapHatasi as exc:
    sina("bilinmeyen motor reddedildi", True)
    sina("ret gecerli motorlari sayiyor", "sahte" in str(exc))

try:
    H.ekle(ofis.db, ofis.proje_id, "kotu2", "sahte", tur="sihirli")
    sina("bilinmeyen tur reddedildi", False, "-- kabul edildi!")
except H.HesapHatasi:
    sina("bilinmeyen tur reddedildi", True)

# ------------------------------------------------ 2. ANAHTAR SIZMIYOR
print("\n2. anahtar veritabanina YAZILMIYOR")
H.ekle(ofis.db, ofis.proje_id, "api-hesap", "sahte", tur="api",
       ortam={"SAHTE_API_KEY": "@gizli:SAHTE_ANAHTAR"}, sira=20)

with ofis.db.baglanti() as c:
    ham = c.execute("SELECT ortam FROM hesap WHERE ad = 'api-hesap'").fetchone()
sina("defterde REFERANS var", "@gizli:" in ham["ortam"])
# En onemlisi: gercek degerin kendisi defterde OLMAMALI.
sina("defterde GERCEK DEGER yok", "gizli-deger-123" not in ham["ortam"])

# ------------------------------- 3. COZULEMEYEN KIMLIK HATA, BOS DEGIL
print("\n3. cozulemeyen kimlik HATA")
h_api = H.hesap(ofis.db, ofis.proje_id, "api-hesap")
try:
    H.ortam_coz(h_api)
    sina("eksik anahtar HATA veriyor", False, "-- sessizce gecti!")
except H.HesapHatasi as exc:
    sina("eksik anahtar HATA veriyor", True)
    sina("hata ANAHTAR ADINI soyluyor", "SAHTE_ANAHTAR" in str(exc))
    sina("hata NASIL eklenecegini soyluyor", "anahtar ekle" in str(exc))

olur = H.kullanilabilir_mi(h_api)
sina("kullanilamaz sayiliyor", olur["olur"] is False)
sina("sebep soyleniyor", bool(olur["sebep"]))

# Anahtar eklenince cozulmeli.
from ofis import gizli                                      # noqa: E402
gizli.ekle("SAHTE_ANAHTAR", "gizli-deger-123")
try:
    cozulen = H.ortam_coz(H.hesap(ofis.db, ofis.proje_id, "api-hesap"))
    sina("anahtar eklenince COZULUYOR",
         cozulen.get("SAHTE_API_KEY") == "gizli-deger-123")
finally:
    gizli.sil("SAHTE_ANAHTAR")

# Duz metin deger (sir degil, ornegin bir yol) oldugu gibi gecmeli.
H.ekle(ofis.db, ofis.proje_id, "ev-hesap", "sahte",
       ortam={"SAHTE_HOME": "~/sahte-ev"}, sira=30)
duz = H.ortam_coz(H.hesap(ofis.db, ofis.proje_id, "ev-hesap"))
sina("duz metin deger gecti", duz["SAHTE_HOME"].endswith("sahte-ev"))
sina("~ genisletildi", "~" not in duz["SAHTE_HOME"])

# ------------------------------------------ 4. KAPATMA gecmisi silmiyor
print("\n4. hesap kapatilabiliyor (silinmeden)")
H.ayarla(ofis.db, ofis.proje_id, "ev-hesap", aktif=False)
sina("kapatildi", H.hesap(ofis.db, ofis.proje_id, "ev-hesap")["aktif"] is False)
sina("kayit DURUYOR (gecmis okunabilir)",
     any(h["ad"] == "ev-hesap" for h in H.liste(ofis.db, ofis.proje_id)))
sina("aktif listede YOK",
     not any(h["ad"] == "ev-hesap"
             for h in H.liste(ofis.db, ofis.proje_id, yalniz_aktif=True)))
sina("kullanilamaz sayiliyor",
     H.kullanilabilir_mi(H.hesap(ofis.db, ofis.proje_id, "ev-hesap"))["olur"]
     is False)

# ------------------------------------------------- 5. ZINCIR hesaplarda
print("\n5. ZINCIR hesaplar uzerinde yuruyor")
ajan = ofis.kadro.ajan("cinar")


def _fab(ad, **k):
    return SahteMotor(cevap="ok")


hesaplar = [dict(H.hesap(ofis.db, ofis.proje_id, "sahte-bir"),
                 _cozulmus_ortam={"SAHTE_EV": "/bir"})]
b = zincir_kur(ajan, fabrika=_fab, hesaplar=hesaplar)
sina("ilk basamak AJANIN kendi ayari",
     (b[0]["motor"], b[0]["model"]) == ("sahte", "opus"))
sina("hesap basamagi ARKAYA eklendi",
     any(x["hesap"] == "sahte-bir" for x in b), str(b))
hb = [x for x in b if x["hesap"] == "sahte-bir"][0]
sina("hesap basamagi KIMLIK tasiyor", hb["ortam"] == {"SAHTE_EV": "/bir"})
sina("kapali hesap zincire girmiyor",
     not any(x.get("hesap") == "ev-hesap" for x in b))

# ---------------------------------- 6. KIMLIK TURA ULASIYOR MU
print("\n6. kimlik MOTORA ulasiyor mu")
# "Sessizce yok sayilan ayar, ayar degildir." Hesap tanimlanip ortami
# hic gecmeseydi bu bolum yakalardi.


class _Kaydeden(SahteMotor):
    son: dict = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


CEVAP = "Bitti.\nKANIT terminal: pytest -> 1 passed"
g = ofis.tahta.gorev_ac("Is", neden="s", ana_hedef="s", kabul_olcutu="y")
Koltuk(ofis, motor_fabrikasi=lambda ad, **k: _Kaydeden(cevap=CEVAP)
       ).kos(g["no"], "cinar")
# Ajanin KENDI basamagi kimlik kurmaz -- bugunku davranis korunur.
sina("ajanin kendi basamaginda kimlik YOK",
     not _Kaydeden.son.get("ek_ortam"),
     str(_Kaydeden.son.get("ek_ortam")))
sina("sozlesme ek_ortam parametresini TASIYOR",
     "ek_ortam" in _Kaydeden.son)

# --------------------------------- 7. GERIYE DONUK UYUM
print("\n7. hesapsiz ofis calismaya devam ediyor")
k2 = Path(tempfile.mkdtemp(prefix="ofis-hesapsiz-"))
o2 = Ofis.proje_ac(Veritabani(k2 / "o.sqlite3"), "Hesapsiz",
                   amac="a", basari_olcutu="b")
ortuk = H.zincir_hesaplari(o2.db, o2.proje_id)
sina("hic hesap yokken ORTUK listeye dusuyor",
     all(h.get("ortuk") for h in ortuk) if ortuk else True)
sina("ortuk hesap ORTAM KURMUYOR",
     all(not h["ortam"] for h in ortuk))

# ---------------------------------- IKINCI CODEX HESABI (22.09.2026)
#
# Kullanicinin ikinci Plus hesabini eklerken iki SESSIZ kusur bulundu;
# ikisi de ilk limit devrinde, tam ihtiyac duyuldugu anda patlardi:
#
#   1. Adaptor hep VARSAYILAN evi hazirliyordu, tur ise HESABIN evinde
#      kosuyordu -> ikinci hesap guven kaydi/sandbox olmadan, salt-okunur.
#   2. `kullanilabilir_mi` ofisin varsayilan evine bakiyordu -> girissiz
#      ikinci hesap HAZIR gorunuyordu.
#
# GERCEK CODEX KOSMAZ: `calistirilabilir` bosaltiliyor, komut bos kaliyor,
# surec hic baslamiyor. Bir sinama kullanicinin limitine dokunamamali.
print("")
print("9. IKINCI CODEX HESABI -- kendi evinde olculur ve hazirlanir")
import base64 as _b64
import json as _js
import tempfile as _tf
from pathlib import Path as _P
from ofis import hesap as _H
from ofis.motor.codex import CodexMotoru as _CM

_ev2 = _P(_tf.mkdtemp(prefix="codex2-"))
_h2 = {"ad": "codex2", "motor": "codex", "tur": "abonelik", "aktif": True,
       "ortam": {"CODEX_HOME": str(_ev2)}}

_o = _H.kullanilabilir_mi(_h2)
sina("GIRISSIZ ikinci ev HAZIR gorunmuyor", not _o["olur"], str(_o))
sina("sebep giris KOMUTUNU soyluyor", "codex login" in _o.get("sebep", ""),
     _o.get("sebep", ""))

_govde = _b64.urlsafe_b64encode(_js.dumps({
    "email": "iki@ornek.com",
    "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
}).encode()).decode().rstrip("=")
(_ev2 / "auth.json").write_text(
    _js.dumps({"tokens": {"id_token": "a." + _govde + ".c"}}), encoding="utf-8")
_o2 = _H.kullanilabilir_mi(_h2)
sina("girisli ikinci ev HAZIR", _o2["olur"], str(_o2))
# Hangi hesap oldugu SOYLENMELI: iki hesap varken "girisli" demek yetmez,
# yanlis aboneligi tuketmenin ilk isareti buradan gorunur.
sina("hangi hesap oldugu okunuyor", _o2.get("eposta") == "iki@ornek.com", str(_o2))

# OLU OTURUM (25.09.2026): auth.json DURUYOR ama sunucu 401 donduruyor.
# Ofis bunu HATIRLAR; dosyanin varligi hesabi HAZIR gostermemeli.
# Defter gecici -- kullanicinin ~/.agentofis'ine yazilmaz.
from ofis.motor import codex as _cxm
_eski_od = _cxm.OTURUM_DEFTERI
_cxm.OTURUM_DEFTERI = _ev2 / "oturum_sinama.json"
try:
    _cxm.oturum_olu_yaz(str(_ev2))
    _o3 = _H.kullanilabilir_mi(_h2)
    sina("OLU oturumlu hesap HAZIR gorunmuyor (dosya dursa bile)",
         not _o3["olur"], str(_o3))
    sina("sebep 'KAPANMIS' ve giris komutu", "KAPANMIS" in _o3.get("sebep", "")
         and "codex login" in _o3.get("sebep", ""), _o3.get("sebep", ""))
    import os as _os3
    _st3 = (_ev2 / "auth.json").stat()
    _os3.utime(_ev2 / "auth.json",
               ns=(_st3.st_atime_ns, _st3.st_mtime_ns + 2_000_000_000))
    sina("yeniden giris sonrasi hesap yine HAZIR",
         _H.kullanilabilir_mi(_h2)["olur"])
finally:
    _cxm.OTURUM_DEFTERI = _eski_od

_kok = _P(_tf.mkdtemp(prefix="codexkok-"))
_m = _CM()
_m.calistirilabilir = ""
_olaylar = list(_m.tur_kos("x", klasor=str(_kok),
                           ek_ortam={"CODEX_HOME": str(_ev2)}))
sina("gercek codex KOSMADI (sinama limite dokunmuyor)",
     any(getattr(x, "tur", "") == "hata" for x in _olaylar))
sina("HESABIN KENDI evi hazirlandi (config.toml)",
     (_ev2 / "config.toml").exists(), str(list(_ev2.iterdir())))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
