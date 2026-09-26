# -*- coding: utf-8 -*-
"""Rol kutuphanesi: TANIM mi, yoksa yine ETIKET mi.

Bu dosyanin sinadigi sey tek cumlede: **rol, bos alanlari gercekten
dolduruyor mu ve doldurdugu sey motora ULASIYOR mu.**

Ikisi de gerekli. Kutuphane guzel gorunup hicbir yere baglanmasaydi
"sessizce yok sayilan ayar" olurdu -- bu projede o hata bir kez odendi
(orkestra motor fabrikasini alip hicbir yere gecirmiyordu).

En kritik sinama 4. bolumde: `arastirma` rolunun `kafa` olarak ise
alinabilmesinin ARTIK MUMKUN OLMAMASI. Gercek ofiste tam bu oldu --
`bilge` ve `deniz` dosya yazamaz halde kaldi ve kimse fark etmedi.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis import roller as R
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


# ------------------------------------------------- 1. kutuphanenin kendisi
print("\n1. kutuphane KENDI ICINDE tutarli mi")

sina("kutuphane bos degil", len(R.ROLLER) >= 10)
sina("kategoriler var", len(R.kategoriler()) >= 4)

# Rol, tahtanin KABUL ETMEDIGI bir kanit turu isteseydi ajan o kaniti
# hic ekleyemezdi -- rol karsilanamaz bir sey istemis olurdu.
kotu_kanit = [(a, k) for a, r in R.ROLLER.items()
              for k in r.kanit_turleri if k not in R.GECERLI_KANITLAR]
sina("her kanit turu tahtanin sozlugunden", not kotu_kanit, str(kotu_kanit))
sina("her tur gecerli",
     all(r.tur in R.TURLER for r in R.ROLLER.values()))
sina("her kademe gecerli",
     all(r.kademe in R.KADEMELER for r in R.ROLLER.values()))
# Olcutsuz rol, incelenecek seyi olmayan roldur (MAST %41,8).
sina("HER rolun olcut sablonu var",
     all(r.olcut_sablonu.strip() for r in R.ROLLER.values()))
# Kutuphane yazilimla sinirli kalmamali: kullanicinin isinin %90'i
# kod disi (magaza, reklam, icerik, arastirma).
sina("kutuphane yazilimla SINIRLI degil",
     len({r.kategori for r in R.ROLLER.values()} - {"YAZILIM"}) >= 3)

print("\n2. KAPI REDDEDIYOR mu")
try:
    R.coz("pazarlamaci")
    sina("bilinmeyen rol reddedildi", False, "-- kabul edildi!")
except R.RolHatasi as exc:
    sina("bilinmeyen rol reddedildi", True)
    # Ret ogretir: gecerli adlari saymayan bir ret, insani tahmine iter.
    sina("ret GECERLI ADLARI sayiyor", "backend" in str(exc))
try:
    R.coz("")
    sina("bos rol reddedildi", False, "-- kabul edildi!")
except R.RolHatasi:
    sina("bos rol reddedildi", True)

print("\n3. eski adlar KIRILMIYOR")
# Gercek ofiste kutuphane oncesi yazilmis kayitlar var.
sina("'yazilim' -> backend", R.coz("yazilim") == "backend")
sina("'test' -> kalite", R.coz("test") == "kalite")
sina("'icerik' -> metin", R.coz("icerik") == "metin")
sina("buyuk/kucuk harf onemsiz", R.coz("Backend") == "backend")

# -------------------------------------------------- 4. ASIL HATA KAPANDI MI
print("\n4. bilge/deniz hatasi YAPISAL olarak kapandi mi")
kok = Path(tempfile.mkdtemp(prefix="ofis-roller-"))
print(f"klasor: {kok}")
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Rol",
                     amac="rol sinamasi", basari_olcutu="testler gecer")
(kok / "w").mkdir(exist_ok=True)

a = ofis.kadro.ise_al("bilge", "arastirma", motor="sahte",
                      klasor=str(kok / "w"))
# ISTE BU: arastirma rolu DOSYA URETIR. 'kafa' olarak ise alinamaz.
sina("arastirma ajani ELLER olarak ise alindi", a["tur"] == "eller")
d = ofis.kadro.ise_al("deniz", "metin", motor="sahte", klasor=str(kok / "w"))
sina("icerik ajani ELLER olarak ise alindi", d["tur"] == "eller")
sina("arastirma rolu 'dosya' kanitini bekliyor",
     "dosya" in R.rol("arastirma").kanit_turleri)
# Arastirma kod isinin ~7 kati yakiyor; tavan farki rolde yazili olmali.
sina("arastirmanin butce alt siniri koddan YUKSEK",
     R.rol("arastirma").butce_alt_siniri > R.rol("backend").butce_alt_siniri)

print("\n5. rol BOS alanlari dolduruyor, DOLU olanlara dokunmuyor")
c = ofis.kadro.ise_al("cinar", "backend", motor="claude")
sina("model rolden doldu (claude/guclu -> opus)", c["model"] == "opus")
k = ofis.kadro.ise_al("kerem", "backend", motor="codex")
sina("ayni rol, baska motor -> baska model",
     k["model"] == "gpt-5.6-sol")
ozel = ofis.kadro.ise_al("ozel", "backend", motor="claude", model="haiku")
# Rol bir VARSAYILANDIR, dayatma degil: kullanicinin sectigini sessizce
# iptal etmek, zincirin "ajanin KENDI motorundan baslar" kuraliyla
# ayni sinifta bir hata olurdu.
sina("ACIKCA verilen model kazaniyor", ozel["model"] == "haiku")

print("\n6. kademe -> model eslemesi")
try:
    R.model_sec("claude", "sihirli")
    sina("bilinmeyen kademe reddedildi", False, "-- kabul edildi!")
except R.RolHatasi:
    sina("bilinmeyen kademe reddedildi", True)
# Bilinmeyen motor PATLAMAMALI: yeni adaptor takmak tek dosya, kutuphane
# onu bilmiyor olabilir ve bu ise alimi engellememeli.
sina("bilinmeyen motor bos donuyor, patlamiyor",
     R.model_sec("yepyeni", "guclu") == "")

print("\n7. fable ve astra HICBIR kademede YOK")
# Kullanicinin olcumu: "tek promptta 5 saatlik limiti bitiriyordu."
# Bir kademeye koysaydik donguye girerlerdi.
tum_modeller = [m for d in R.KADEME_MODEL.values() for m in d.values()]
sina("fable kademelerde yok",
     not any("fable" in (m or "") for m in tum_modeller))
sina("astra kademelerde yok",
     not any("astra" in (m or "") for m in tum_modeller))
sina("ikisi de KAPI modeli olarak kayitli",
     {"fable", "astra"} <= set(R.KAPI_MODELLERI))
# Para kontrolu kapali kalarak basarisiz olur.
sina("kapi modelleri TAVAN ZORUNLU isaretli",
     all(v["tavan_zorunlu"] for v in R.KAPI_MODELLERI.values()))
# codex tavan uygulayamiyor -- bu astra'nin notunda yazili olmali,
# yoksa biri onu otomatik bir yola baglar.
sina("astra'nin notu codex kisitini soyluyor",
     "ELLE" in R.KAPI_MODELLERI["astra"]["not"])

# --------------------------------------------- 8. BRIFINGE ULASIYOR MU
print("\n8. rol tanimi BRIFINGE giriyor mu")
brf = ofis.brifing
k1 = brf.k1_anayasa("bilge")
sina("brifingde rol basligi var", "ROLUN: arastirma" in k1)
sina("brifing dosya yazip yazamayacagini SOYLUYOR",
     "Dosya yazabilir misin: EVET" in k1)
sina("brifing beklenen kanit turunu soyluyor", "baglanti" in k1)
sina("brifing 'bitti' ne demek onu soyluyor", "KAYNAK" in k1)
# Baglayici bekleyen rol bunu ajanin YUZUNE soylemeli.
m = ofis.kadro.ise_al("mert", "magaza", motor="sahte", klasor=str(kok / "w"))
sina("baglayici uyarisi brifinge giriyor",
     "Shopify" in brf.k1_anayasa("mert"))

# ------------------------------------- 9. EK IZINLER MOTORA ULASIYOR MU
print("\n9. rolun EK IZINLERI motora ulasiyor mu")
# "Sessizce yok sayilan ayar, ayar degildir." Kutuphane guzel gorunup
# hicbir yere baglanmasaydi bu bolum yakalamazdi.


class _Kaydeden(SahteMotor):
    son: dict = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


kal = ofis.kadro.ise_al("sol", "kalite", motor="sahte", klasor=str(kok / "w"))
g = ofis.tahta.gorev_ac("Testleri kostur", neden="s", ana_hedef="s",
                        kabul_olcutu="yesil")
_f = lambda ad, **kw: _Kaydeden(cevap="Bitti.\nKANIT terminal: pytest -> 3 passed")  # noqa: E731
Koltuk(ofis, motor_fabrikasi=_f).kos(g["no"], "sol")
alinan = list(_Kaydeden.son.get("izinli_araclar") or ())
sina("KALITE rolunun ek izni motora ulasti", "Bash(npx *)" in alinan,
     str(alinan))

# Ise ozel izin de kaybolmamali -- rol onu EZMEMELI.
g2 = ofis.tahta.gorev_ac("Ikinci", neden="s", ana_hedef="s", kabul_olcutu="y")
Koltuk(ofis, motor_fabrikasi=_f).kos(g2["no"], "sol",
                                     izinli_araclar=("Bash(deploy *)",))
alinan2 = list(_Kaydeden.son.get("izinli_araclar") or ())
sina("ise ozel izin de gecti", "Bash(deploy *)" in alinan2)
sina("rol izni ise ozel izinle BIRLIKTE var", "Bash(npx *)" in alinan2)

# Gercekten kurulan komut satirinda mi -- listede olmak yetmez.
cm = ClaudeMotoru(calistirilabilir="claude")
komut = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                      model="", efor="normal", yazabilir=True,
                      ek_klasorler=(), butce_usd=None,
                      izinli_araclar=R.rol("kalite").ek_izinler)
sina("komut satirinda gercekten var",
     "Bash(npx *)" in komut[komut.index("--allowedTools") + 1:])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
