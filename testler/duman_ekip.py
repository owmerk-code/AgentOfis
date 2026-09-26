# -*- coding: utf-8 -*-
"""Ekip onerisi: lider ONERIR, insan ONAYLAR -- ve kapi REDDEDER.

Bu dosyanin sinadigi uc sey:

1. **Kapi gercekten reddediyor mu.** Hic reddetmeyen kapi, kapi
   degildir. Buradaki her ret bir SESSIZ OLUMU onluyor: tanimsiz rol ->
   araclari hic verilmemis ajan; kurulu olmayan motor -> hic kosamayacak
   ajan; tekrar eden ad -> gecmisi okunamaz sicil.

2. **Lider KURAMIYOR, yalniz onerebiliyor.** Kadro kurmak patronun
   limitini harcar. Bu, kodda bir `if` degil bir YAPI olmali.

3. **Oneri iki komut arasinda yasiyor mu.** `oner` ile `kur` arasinda
   insan dusunur; oneri diskte durmazsa onaylanacak bir sey kalmaz.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Ekip, EkipHatasi, Sohbet
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


kok = Path(tempfile.mkdtemp(prefix="ofis-ekip-"))
print(f"klasor: {kok}")
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Ekip",
                     amac="ekip sinamasi", basari_olcutu="testler gecer")
kanat = ofis.kanat_ac("URUN", "UR")
(kok / "w").mkdir()
ofis.kadro.ise_al("demir", "lider", lider_mi=True, motor="sahte",
                  kanat_id=kanat, klasor=str(kok / "w"))
ofis.kadro.ise_al("cinar", "backend", motor="sahte", kanat_id=kanat,
                  klasor=str(kok / "w"))


def _ekip(cevap) -> Ekip:
    metin = cevap if isinstance(cevap, str) else json.dumps(
        cevap, ensure_ascii=False)
    return Ekip(ofis, motor_fabrikasi=lambda ad, **k: SahteMotor(cevap=metin))


def _uye(ad="selin", rol="arayuz", motor="sahte", gerekce="ekran isi var"):
    return {"ad": ad, "rol": rol, "motor": motor, "gerekce": gerekce}


def _oneri(**ek):
    d = {"gerekce": "kadroda arayuz yok", "uyeler": [_uye()]}
    d.update(ek)
    return d


# --------------------------------------------------------------- 1. KAPILAR
print("\n1. kapi REDDEDIYOR mu")

ek = _ekip(_oneri())
red = ek.oneriyi_dogrula


def _red(baslik, oneri, beklenen_parca):
    m = red(oneri)
    sina(baslik, bool(m) and beklenen_parca.lower() in m.lower(), f"-> {m!r}")


_red("gerekcesiz oneri reddedildi", _oneri(gerekce=""), "gerekce")
_red("bos uye listesi reddedildi", _oneri(uyeler=[]), "bos")
_red("JSON nesnesi olmayan cikti reddedildi", "duz metin", "JSON")
# Tanimsiz rol = araclari hic verilmemis ajan.
_red("bilinmeyen ROL reddedildi",
     _oneri(uyeler=[_uye(rol="pazarlamaci")]), "rol")
# Kurulu olmayan motor = hic kosamayacak ajan.
_red("kurulu olmayan MOTOR reddedildi",
     _oneri(uyeler=[_uye(motor="yepyeni")]), "kurulu degil")
# Ad geri donmez: tekrar eden ad, gecmisi okunamaz kilar.
_red("kadroda OLAN ad reddedildi",
     _oneri(uyeler=[_uye(ad="cinar")]), "zaten kadroda")
_red("ayni ad iki kez reddedildi",
     _oneri(uyeler=[_uye(ad="selin"), _uye(ad="selin", rol="kalite")]),
     "iki kez")
# Gerekcesiz ajan, bos duran koltuktur.
_red("uye gerekcesi bos reddedildi",
     _oneri(uyeler=[_uye(gerekce="")]), "gerekce")
_red("cok kalabalik kadro reddedildi",
     _oneri(uyeler=[_uye(ad=f"a{i}") for i in range(9)]), "en fazla")

sina("GECERLI oneri kabul ediliyor", red(_oneri()) == "")

# ------------------------------------------------------- 2. RET OGRETIYOR mu
print("\n2. ret lidere SEBEBINI soyluyor mu")
metin = ek.oneri_metni("bir is", kanat, hata="Bilinmeyen rol: 'pazarlamaci'")
sina("ret sebebi bir sonraki istege giriyor", "pazarlamaci" in metin)
sina("istekte rol kutuphanesi TAM veriliyor",
     "arastirma" in metin and "magaza" in metin and "entegrasyon" in metin)
sina("istekte MEVCUT kadro gosteriliyor", "cinar" in metin)
sina("istekte musait motorlar gosteriliyor", "MUSAIT MOTORLAR" in metin)

# --------------------------------------------- 3. ONIZLEME ve KALICILIK
print("\n3. oneri SAKLANIYOR ve onizleme gosteriyor mu")
iyi = _oneri(uyeler=[_uye(), _uye(ad="kerem", rol="kalite",
                                 gerekce="testi kimse kosturamaz")])
o1 = _ekip(iyi).oner("uctan uca web uygulamasi")
sina("oneri numara aldi", o1["no"] == 1)
sina("durum bekliyor", o1["durum"] == "bekliyor")

# AYRI bir Ekip nesnesi ayni oneriyi gorebilmeli -- yoksa `oner` ile
# `kur` ayri komutlar oldugunda oneri kaybolurdu.
baska = Ekip(ofis)
sina("BASKA bir Ekip nesnesi oneriyi goruyor",
     baska.oneri(1)["hedef"] == "uctan uca web uygulamasi")
sina("bekleyenler listesinde", len(baska.bekleyenler()) == 1)

on = baska.onizleme(1)
sina("onizleme 'KURULMADI' diyor", "KURULMADI" in on)
sina("onizleme her uyenin gerekcesini gosteriyor", "ekran isi var" in on)
# Rolun doldurdugu tur ONIZLEMEDE gorunmeli: gorunmeyen secim,
# onay alinmamis secimdir.
sina("onizleme TURU gosteriyor (rolden geldi)", "eller" in on)
sina("onizleme kur/red komutunu soyluyor", "ekip kur 1" in on)

# --------------------------------------------------- 4. INSANIN KARARI
print("\n4. insanin karari")
oncesi = {a["ad"] for a in ofis.kadro.liste()}
alinan = baska.kur(1, klasor=str(kok / "w"))
sonrasi = {a["ad"] for a in ofis.kadro.liste()}
sina("iki ajan gercekten ise alindi", sonrasi - oncesi == {"selin", "kerem"})
sina("rol ise alimda uygulandi",
     ofis.kadro.ajan("kerem")["meslek"] == "kalite")
sina("tur rolden geldi", ofis.kadro.ajan("selin")["tur"] == "eller")
sina("oneri 'kuruldu' oldu", baska.oneri(1)["durum"] == "kuruldu")
sina("bekleyenler bosaldi", baska.bekleyenler() == [])

# Oneri bir KARARDIR: alti ay sonra "bu ajan neden alinmis" sorulabilmeli.
kararlar = [k["karar"] for k in ofis.bellek.son_kararlar(3)]
sina("karar gunlugune yazildi",
     any("Kadroya 2 ajan" in k for k in kararlar), str(kararlar))

try:
    baska.kur(1)
    sina("ayni oneri IKI KEZ kurulamiyor", False, "-- kuruldu!")
except EkipHatasi:
    sina("ayni oneri IKI KEZ kurulamiyor", True)

print("\n5. RET -- sebep zorunlu")
o2 = _ekip(_oneri(uyeler=[_uye(ad="aras", rol="seo",
                              gerekce="arama gorunurlugu")])).oner("seo isi")
# Gerekcesiz ret IKI kapidan birden reddediliyor: `Ekip.reddet`'in
# kendi kapisi ve `bellek.karar_yaz`'in gerekce zorunlulugu. Ikisi
# bagimsiz -- biri kaldirilsa oteki hala tutar. Test bu yuzden hangi
# istisna geldigine degil, REDDEDILDIGINE bakiyor.
try:
    baska.reddet(o2["no"], "")
    sina("gerekcesiz ret REDDEDILDI", False, "-- kabul edildi!")
except Exception as exc:
    sina("gerekcesiz ret REDDEDILDI", True)
    sina("ret sebebinin NEDEN zorunlu oldugu soyleniyor",
         "gerekce" in str(exc).lower() or "sebep" in str(exc).lower())
sina("basarisiz ret oneriyi BOZMADI",
     baska.oneri(o2["no"])["durum"] == "bekliyor")
red2 = baska.reddet(o2["no"], "SEO isini disaridan aliyoruz")
sina("ret kaydedildi", red2["durum"] == "reddedildi")
sina("ret sebebi saklandi", "disaridan" in red2["sebep"])
sina("reddedilen ajan ISE ALINMADI",
     "aras" not in {a["ad"] for a in ofis.kadro.liste()})

# -------------------------------------------- 6. LIDER KURAMIYOR (yapisal)
print("\n6. lider kadroyu KENDI kuramiyor")
# Bu bir `if` degil bir YAPI olmali: `oner` yalnizca kayit yazar,
# ise alma ayri bir cagridir ve onu insan tetikler.
o3 = _ekip(_oneri(uyeler=[_uye(ad="tuna", rol="analiz",
                              gerekce="sayilari kimse cikarmiyor")])).oner("analiz")
sina("oner() ISE ALMIYOR",
     "tuna" not in {a["ad"] for a in ofis.kadro.liste()})
sina("oneri onay BEKLIYOR", baska.oneri(o3["no"])["durum"] == "bekliyor")

# ------------------------------------ 7. AYAR MOTORA ULASIYOR MU
print("\n7. motor_fabrikasi gercekten kullaniliyor mu")
# Ilk surumde Ekip fabrikayi aliyor ama `ofis.orkestra`yi cagiriyordu --
# yani ayar HICBIR YERE ULASMIYORDU. Bunu bu sinama yakaladi.


class _Kaydeden(SahteMotor):
    cagrildi = False

    def tur_kos(self, metin, **ayar):
        _Kaydeden.cagrildi = True
        yield from super().tur_kos(metin, **ayar)


_Kaydeden.cagrildi = False
try:
    Ekip(ofis, motor_fabrikasi=lambda ad, **k: _Kaydeden(
        cevap=json.dumps(_oneri(uyeler=[_uye(ad="mert", rol="magaza",
                                             gerekce="magaza isi")])))
         ).oner("magaza isi")
except EkipHatasi:
    pass
sina("verilen motor fabrikasi CAGRILDI", _Kaydeden.cagrildi)

# ----------------------------------------- 8. SOHBET dorduncu yolu
print("\n8. `konus` KADRO yolunu taniyor mu")
triyaj = json.dumps({"karar": "kadro",
                     "gerekce": "arayuz rolu kadroda yok",
                     "hedef": "web uygulamasi"}, ensure_ascii=False)
kadro_cevabi = json.dumps(_oneri(uyeler=[_uye(ad="ayla", rol="metin",
                                              gerekce="metin yazacak kimse yok")]),
                          ensure_ascii=False)


class _Asamali(SahteMotor):
    sira = 0

    def tur_kos(self, metin, **ayar):
        _Asamali.sira += 1
        self.cevap = triyaj if _Asamali.sira == 1 else kadro_cevabi
        yield from super().tur_kos(metin, **ayar)


_Asamali.sira = 0
gorev_oncesi = len(ofis.tahta.liste())
turler = []
for olay in Sohbet(ofis, motor_fabrikasi=lambda ad, **k: _Asamali(cevap="")
                   ).konus("uctan uca web uygulamasi yapalim"):
    turler.append(olay["tur"])

sina("triyaj 'kadro' karari verebildi", "triyaj" in turler)
sina("ekip onerisi akisa dustu", "ekip_onerisi" in turler, str(turler))
# EN ONEMLI: is BASLAMADI. Kadro kurmak patronun onayini bekler.
sina("HICBIR GOREV ACILMADI", len(ofis.tahta.liste()) == gorev_oncesi)
sina("ajan ISE ALINMADI", "ayla" not in {a["ad"] for a in ofis.kadro.liste()})
sina("oneri onay kuyrugunda", any(
    o["hedef"] == "web uygulamasi" for o in baska.bekleyenler()))

# triyaj metni dorduncu yolu TARIF ediyor mu
tm = Sohbet(ofis).triyaj_metni("selam")
sina("triyaj metni 'kadro' yolunu tarif ediyor", "**kadro**" in tm)
sina("triyaj metni 'dort yol' diyor", "Dort yoldan" in tm)

# --------------------------------------------------------------------------
print("\n10. SABLONDAN EKIP -- lider cagrilmaz, AYNI kapi")
from ofis import sablon as _S
from ofis import roller as _R

sina("her sablon rolu kutuphanede tanimli",
     all(r in _R.ROLLER for s in _S.liste() for r, _ in s.uyeler))
sina("her sablon uyesinin gerekcesi var (ekip kapisi)",
     all(n.strip() for s in _S.liste() for _, n in s.uyeler))
sina("sablonlar AZAMI_UYE sinirinin icinde (lider eklense bile)",
     all(len(s.uyeler) + 1 <= 6 for s in _S.liste()))

_bos = ofis.kanat_ac("STUDYO", "ST")
_o = Ekip(ofis).sablondan("yazilim", kanat_id=_bos)
_roller = [u["rol"] for u in _o["uyeler"]]
sina("sablon ONERI uretti, KURMADI",
     _o["durum"] == "bekliyor" and _o["oneren"] == "sablon:yazilim"
     and not any(a["ad"] in [u["ad"] for u in _o["uyeler"]]
                 for a in ofis.kadro.liste()))
sina("lidersiz takima LIDER eklendi", _roller[0] == "lider", str(_roller))
sina("model onizlemede DOLU (kademeden)",
     all(u["model"] for u in _o["uyeler"]), str(_o["uyeler"])[:200])
_o2 = Ekip(ofis).sablondan("arastirma", kanat_id=kanat)
sina("lideri OLAN takima lider EKLENMEDI",
     "lider" not in [u["rol"] for u in _o2["uyeler"]])
sina("adlar kadroyla CAKISMIYOR",
     not {u["ad"] for u in _o2["uyeler"]} & {a["ad"] for a in ofis.kadro.liste()})
try:
    Ekip(ofis).sablondan("uzay-istasyonu", kanat_id=kanat)
    _red = False
except EkipHatasi:
    _red = True
sina("bilinmeyen sablon REDDEDILIYOR", _red)
try:
    Ekip(ofis).sablondan("yazilim")
    _red = False
except EkipHatasi as exc:
    _red = "takim" in str(exc)
sina("cok takimli ofiste takim SORULUYOR (yanlis lidere baglanmasin)", _red)
# Gemini 24.09.2026'da cikarildi: musait GORUNSE bile secilmez -- sablon
# insanin kullanmamaya karar verdigi motoru kadroya sokmamali.
sina("gemini HICBIR role onerilmiyor (cikarildi)",
     _S.motor_sec("backend", {"gemini", "claude"}) == "claude"
     and _S.motor_sec("metin", {"gemini", "codex"}) == "codex"
     and "gemini" not in _S.MOTOR_TERCIHI)
try:
    _S.motor_sec("metin", {"gemini"})
    _red = False
except _S.SablonHatasi:
    _red = True
sina("  uygun motor yoksa REDDEDILIYOR (kosamayacak ajan onerilmez)", _red)

# AYNI KAPI: uretici bozulursa (kurulu olmayan motor) oneri SAKLANMAZ.
_asil_uret = _S.oneri_uret
_S.oneri_uret = lambda *a, **k: {"gerekce": "g", "uyeler": [
    {"ad": "hayalet", "rol": "backend", "motor": "yok-motor", "gerekce": "g"}]}
try:
    Ekip(ofis).sablondan("yazilim", kanat_id=kanat)
    _red = False
except EkipHatasi as exc:
    _red = "KURULU DEGIL" in str(exc)
finally:
    _S.oneri_uret = _asil_uret
sina("sablon onerisi de EKIP KAPISINDAN geciyor (bozuk oneri saklanmaz)", _red)

# KUR: klasorsuz cagrida ORTAK KOK; lider GERCEK lider.
_al = Ekip(ofis).kur(_o["no"])
_ajanlar = {a["ad"]: a for a in ofis.kadro.liste()}
# Ciplak [0] YOK: lider eklenmezse test COKMEMELI, kalmali (mutasyonla
# goruldu -- coken test geri kalan sinamalari hic kosturmaz).
_liderler = [u["ad"] for u in _o["uyeler"] if u["rol"] == "lider"]
sina("klasorsuz kur: ajanlar ORTAK KOKTE (bos klasor yok)",
     all(_ajanlar[a["ad"]]["klasor"] == ofis.kok_klasoru() for a in _al),
     str([_ajanlar[a["ad"]]["klasor"] for a in _al]))
sina("kurulan `lider` GERCEK lider (lider_mi)",
     bool(_liderler) and _ajanlar[_liderler[0]]["lider_mi"]
     and _ajanlar[_liderler[0]]["kanat_id"] == _bos)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
