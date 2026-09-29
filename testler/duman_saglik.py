# -*- coding: utf-8 -*-
"""Saglik duman testi: denetimler GERCEKTEN atesliyor mu.

Hic bulgu vermeyen bir teshis araci, "sorun yok" diyen bir arizadir --
ve bu projenin karsi kuruldugu hata sinifinin ta kendisi olur. Bu yuzden
burada ofis BILEREK bozulur ve her denetimin ates ettigi gosterilir.

Ayrica tersi de sinanir: saglikli ofiste bulgu URETILMEZ. Her seye
"sorun" diyen gosterge de gostergesizlikten farksizdir -- insan ona
bakmayi birakir.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.db import simdi

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


def bulgu_var(rapor, parca) -> bool:
    return any(parca.lower() in b["baslik"].lower() for b in rapor["bulgular"])


def eskit(db, tablo, alan, saniye=600) -> None:
    eski = (dt.datetime.now(dt.UTC) - dt.timedelta(seconds=saniye)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    with db.baglanti() as c:
        c.execute(f"UPDATE {tablo} SET {alan} = ?", (eski,))


print("== saglik duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-saglik-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Saglik", amac="a", basari_olcutu="b")
urun = ofis.kanat_ac("URUN", "UR")
for ad, meslek, lider, tur, model in (
        ("demir", "lider", True, "eller", "sonnet"),
        ("cinar", "backend", False, "eller", "haiku")):
    ofis.kadro.ise_al(ad, meslek, kanat_id=urun, lider_mi=lider, tur=tur,
                      motor="sahte", model=model, klasor=str(kok / ad))
    (kok / ad).mkdir(parents=True, exist_ok=True)


def ac(baslik, alan, **ek):
    return ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h",
                               kabul_olcutu="k", govde="g", kanat_id=urun,
                               yazma_alani=[alan], **ek)


# --------------------------------------------------------------------------
print("1. SAGLIKLI OFIS -- her seye 'sorun' demiyor")

r = ofis.saglik.denetle()
sina("bos ofiste bulgu yok", r["bulgular"] == [], f"({r['bulgular']})")
sina("saglikli bayragi dogru", r["saglikli"] is True)

# --------------------------------------------------------------------------
print("\n2. TIKANAN IS -- 'calisiyor' gorunur ama kimse ilerletmiyor")
# OLCULDU (19.09.2026): lider "tamamlaninca sunacagim" dedi, is tahtada
# `calisiyor` yaziyordu, hicbir surec onu kosturmuyordu. `durum` komutu
# "1 calisiyor" diyordu -- tabloda her sey normaldi.

g1 = ac("Tikanan is", "api1/")
ofis.tahta.sahiplen(g1["no"], "cinar", g1["revizyon"])
r = ofis.saglik.denetle()
sina("YENI baslamis is tikali sayilmiyor", not bulgu_var(r, "ilerlemiyor"))

eskit(db, "gorev", "guncellendi")
r = ofis.saglik.denetle()
sina("eski is TIKALI bildiriliyor", bulgu_var(r, "ilerlemiyor"))
sina("tikali agirligi 'tikali'", r["tikali"] >= 1)
tikali = [b for b in r["bulgular"] if "ilerlemiyor" in b["baslik"]][0]
sina("care SOYLENIYOR", "devam" in tikali["care"], f"({tikali['care']})")
sina("ayrinti ne kadardir durdugunu OKUNUR soyluyor",
     "son degisiklik" in tikali["ayrinti"] and "saniyedir" not in tikali["ayrinti"],
     tikali["ayrinti"][:120])
from ofis.saglik import sure_yazi  # noqa: E402
sina("sure: 508267 sn -> 5 gun 21 saat", sure_yazi(508267) == "5 gun 21 saat", sure_yazi(508267))
sina("sure: 3 saat 12 dk", sure_yazi(3 * 3600 + 12 * 60 + 5) == "3 saat 12 dk")
sina("sure: 4 dk", sure_yazi(245) == "4 dk")
sina("sure: 40 sn", sure_yazi(40) == "40 sn")

# --------------------------------------------------------------------------
print("\n3. BEKLEYEN AJAN tikali SAYILMAZ -- durdurulmus, olmemis")

ofis.postane.soru_sor("cinar", "insan", "Hangi yol?", gorev_no=g1["no"])
r = ofis.saglik.denetle()
sina("soru soran ajanin isi TIKALI degil", not bulgu_var(r, "ilerlemiyor"))
sina("bunun yerine INSAN kuyrugu bildiriliyor", bulgu_var(r, "seni bekliyor"))
sina("insan bulgusunun agirligi 'insan'", r["insan"] >= 1)

for m in ofis.postane.insan_bekleyenler():
    ofis.postane.cevapla(m["id"], "Cevap")
ofis.tahta.birak(g1["no"])
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum='iptal' WHERE no=?", (g1["no"],))

# --------------------------------------------------------------------------
print("\n4. KOSACAK AJAN YOK -- dongu 'ilerleme yok' der, SEBEBINI demez")

pazarlama = ofis.kanat_ac("PAZARLAMA", "PZ")
g2 = ofis.tahta.gorev_ac("Kimsesiz is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", govde="g", kanat_id=pazarlama,
                         yazma_alani=["pz/"])
r = ofis.saglik.denetle()
sina("kosacak ajani olmayan is bildiriliyor", bulgu_var(r, "kosacak ajan yok"))
b = [x for x in r["bulgular"] if "KOSACAK AJAN YOK" in x["baslik"]][0]
sina("sebep soyleniyor", "ajan yok" in b["ayrinti"].lower(), f"({b['ayrinti']})")
sina("care 'ise-al' diyor", "ise-al" in b["care"])

# kafa ajan dosya yazamaz -- AYRI bir sebep, AYRI bir care
ofis.kadro.ise_al("bilge", "arastirma", kanat_id=pazarlama, tur="kafa",
                  motor="sahte", model="haiku", klasor=str(kok / "bilge"))
(kok / "bilge").mkdir(parents=True, exist_ok=True)
r = ofis.saglik.denetle()
b = [x for x in r["bulgular"] if "KOSACAK AJAN YOK" in x["baslik"]]
sina("kafa-only kanatta hala tikali", bool(b))
sina("sebep DEGISTI: kafa ajan yazamaz",
     bool(b) and "kafa" in b[0]["ayrinti"], f"({b[0]['ayrinti'] if b else None})")

with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum='iptal' WHERE no=?", (g2["no"],))

# --------------------------------------------------------------------------
print("\n5. INCELEMEDE UNUTULAN IS")

g3 = ac("Incelemede", "api3/")
ofis.tahta.sahiplen(g3["no"], "cinar", g3["revizyon"])
ofis.tahta.kanit_ekle(g3["no"], "terminal", "test", "2 passed", "cinar")
ofis.tahta.incelemeye_ver(g3["no"], ofis.tahta.gorev(g3["no"])["revizyon"])
r = ofis.saglik.denetle()
sina("YENI incelemeye giren is bildirilmiyor", not bulgu_var(r, "INCELEMEDE"))
eskit(db, "gorev", "guncellendi")
r = ofis.saglik.denetle()
sina("uzun suredir incelemedeki is bildiriliyor", bulgu_var(r, "INCELEMEDE"))

# --------------------------------------------------------------------------
print("\n6. OKSUZ KILIT -- baska isi SEBEPSIZ reddettirir")

with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum='bitti' WHERE no=?", (g3["no"],))
r = ofis.saglik.denetle()
sina("bitmis isin kilidi OKSUZ bildiriliyor", bulgu_var(r, "oksuz kilit"))
b = [x for x in r["bulgular"] if "Oksuz" in x["baslik"]][0]
sina("oksuz kilidin ZARARI aciklaniyor", "SEBEPSIZ" in b["ayrinti"])

with db.baglanti() as c:
    c.execute("DELETE FROM yazma_kilidi")

# --------------------------------------------------------------------------
print("\n7. MODELSIZ AJAN -- on kat maliyet sizintisi")

ofis.kadro.ise_al("deniz", "metin", kanat_id=urun, tur="eller",
                  motor="sahte", klasor=str(kok / "deniz"))
(kok / "deniz").mkdir(parents=True, exist_ok=True)
r = ofis.saglik.denetle()
sina("modelsiz ajan bildiriliyor", bulgu_var(r, "MODELI verilmemis"))
b = [x for x in r["bulgular"] if "MODELI" in x["baslik"]][0]
sina("olculmus sayi veriliyor", "0,88" in b["ayrinti"] or "0.88" in b["ayrinti"],
     f"({b['ayrinti']})")

# --------------------------------------------------------------------------
print("\n8. BASARISIZ AJAN")

ofis.kadro.faz_ayarla("deniz", "basarisiz")
r = ofis.saglik.denetle()
sina("basarisiz ajan bildiriliyor", bulgu_var(r, "basarisiz"))

# --------------------------------------------------------------------------
print("\n9. DENETIM DUSERSE SESSIZ KALMIYOR")

# Calismayan bir denetim, "sorun yok" demekle aynidir. Patladiginda
# bunun GORUNMESI sart.
_eski = ofis.saglik._modelsiz_ajanlar


def _patla():
    raise RuntimeError("bilerek patlatildi")


ofis.saglik._modelsiz_ajanlar = _patla
r = ofis.saglik.denetle()
sina("dusen denetim BILDIRILIYOR", bulgu_var(r, "Denetim calismadi"))
b = [x for x in r["bulgular"] if "Denetim calismadi" in x["baslik"]][0]
sina("sonucun BILINMEDIGI soyleniyor", "BILINMIYOR" in b["care"])
sina("butun rapor dusmedi", len(r["bulgular"]) > 1)
ofis.saglik._modelsiz_ajanlar = _eski

# --------------------------------------------------------------------------
print("\n10. SIRALAMA -- once isi DURDURAN seyler")

r = ofis.saglik.denetle()
agirliklar = [b["agirlik"] for b in r["bulgular"]]
sira = {"tikali": 0, "insan": 1, "uyari": 2, "bilgi": 3}
sina("bulgular agirliga gore sirali",
     agirliklar == sorted(agirliklar, key=lambda a: sira.get(a, 9)),
     f"({agirliklar})")

print("\n11. SIR TARAYICI -- kayda gecen anahtar, sir olmaktan cikar")
# Ofis dis servislerle calisacak (Gemini, Shopify, Meta) ve anahtarlar
# ORTAM DEGISKENINDE durur. Ama ajan bir anahtari yanlislikla kanita
# yazabilir: `echo $GEMINI_API_KEY` bir terminal kaniti olarak duser.
#
# Sizan anahtar GERI ALINAMAZ, yalnizca DEGISTIRILEBILIR -- bu yuzden
# care "sil" degil "once DEGISTIR, sonra sil".

_g12 = ac("Sirli is", "sir12/")
ofis.tahta.sahiplen(_g12["no"], "cinar", g1["revizyon"] if False else
                    ofis.tahta.gorev(_g12["no"])["revizyon"])

# Sahte bir anahtar: gercege benzeyen bicim, gercek olmayan icerik.
# Kaynak dosyada gercek anahtar BULUNMAZ -- test dosyasi da bir kayittir.
_sahte_anahtar = "AIza" + ("Sb3Tk9Lm2Qw7Xz1Yv4Rn8Pd6Hc0Ga5Je" + "TESTONLY")
ofis.tahta.kanit_ekle(_g12["no"], "terminal", "echo $GEMINI_API_KEY",
                      "cikti: " + _sahte_anahtar, "cinar")
# F3 / E23 (28.09): olagan yazma yolu artik MASKELER -- anahtar deftere
# hic dusmez. Saglik denetimi yine gerekli: eski kayitlar ve kapiyi
# atlayan yazmalar (sqlite3 araci, baska bir surec) icin. Sahne bu yuzden
# kapiyi ATLAYAN ham bir yazmayla kurulur.
with db.baglanti() as c:
    _mk = c.execute("SELECT icerik FROM kanit WHERE baslik=?",
                    ("echo $GEMINI_API_KEY",)).fetchone()[0]
sina("olagan yol MASKELEDI (anahtar deftere dusmedi)", _sahte_anahtar not in _mk, _mk[:80])
import sqlite3 as _sq
_ham = _sq.connect(str(db.yol))
_ham.execute("UPDATE kanit SET icerik=? WHERE baslik=?",
             ("cikti: " + _sahte_anahtar, "echo $GEMINI_API_KEY"))
_ham.commit()
_ham.close()

r = ofis.saglik.denetle()
sina("sizan anahtar YAKALANDI", bulgu_var(r, "SIR SIZMIS"),
     f"({[b['baslik'] for b in r['bulgular']]})")
_b12 = [x for x in r["bulgular"] if "SIR SIZMIS" in x["baslik"]][0]
sina("hangi TABLO/ALAN oldugu soyleniyor", "kanit." in _b12["ayrinti"])

# EN ONEMLI SINAMA: rapor, sizintinin KENDISI olmamali.
_rapor_metni = _b12["baslik"] + _b12["ayrinti"] + _b12["care"]
sina("ANAHTARIN KENDISI RAPORDA YOK", _sahte_anahtar not in _rapor_metni,
     "-- sizinti raporu sizintinin kendisi olmamali")
sina("care 'once DEGISTIR' diyor", "DEGISTIR" in _b12["care"])

with db.baglanti() as c:
    c.execute("DELETE FROM kanit WHERE icerik LIKE ?", ("%" + _sahte_anahtar + "%",))
r = ofis.saglik.denetle()
sina("kayit temizlenince bulgu KALKIYOR", not bulgu_var(r, "SIR SIZMIS"))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum='iptal' WHERE no=?", (_g12["no"],))

# ------------------------------------------- 13. BEKLEYEN EKIP ONERISI
print("")
print("13. bekleyen ekip onerisi insan kuyrugunda gorunuyor mu")
# Olculdu (20.09.2026): oneri #1 diskte `bekliyor` dururken saglik
# "senden beklenen yok" diyordu -- ekip onerisi AYRI bir tabloda yasar
# ve insan kuyrugu yalnizca soru/onay tablolarina bakiyordu.
r = ofis.saglik.denetle()
sina("ONCE: bekleyen oneri yokken SESSIZ",
     not bulgu_var(r, "ekip onerisi"),
     "-- her seye 'sorun' diyen gosterge de gostergesizdir")

with db.baglanti() as c:
    c.execute(
        "INSERT INTO ekip_onerisi (proje_id, no, hedef, oneren, gerekce,"
        " uyeler, durum, olusturuldu) VALUES (?,?,?,?,?,?,?,?)",
        (ofis.proje_id, 99, "test istegi", "demir", "test gerekcesi",
         '[{"ad": "selin", "rol": "arayuz"}]', "bekliyor", simdi()))
r = ofis.saglik.denetle()
sina("bekleyen oneri YAKALANDI", bulgu_var(r, "ekip onerisi"),
     str([b["baslik"] for b in r["bulgular"]]))
_b13 = [x for x in r["bulgular"] if "ekip onerisi" in x["baslik"]][0]
sina("insan kuyruguna dusuyor (tikali degil)", _b13["agirlik"] == "insan")
sina("HANGI oneri oldugu soyleniyor", "#99" in _b13["baslik"])
sina("care iki yolu da soyluyor (kur VE red)",
     "ekip kur" in _b13["care"] and "ekip red" in _b13["care"])

# Karara baglanan oneri kuyruktan DUSMELI: cozulmus bir seyi gostermeye
# devam eden gosterge, insanin ona bakmayi birakmasina yol acar.
with db.baglanti() as c:
    c.execute("UPDATE ekip_onerisi SET durum='reddedildi' WHERE no=99")
r = ofis.saglik.denetle()
sina("karara baglaninca bulgu KALKIYOR", not bulgu_var(r, "ekip onerisi"))


print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
