# -*- coding: utf-8 -*-
"""ISCININ HAFIZA SATIRI (06.10.2026, Asama 2 / E30). Jeton yakmaz.

OLCULDU: sifirlamadan onceki gercek defterde biten 20 isin YALNIZ BIRINDE
isci hafizaya yazmisti; brifingdeki "tetikleyici olursa bilgi_yaz" ricasi
tutmuyordu. Yapi: isci bitirirken ZORUNLU satir yazar (`BILGI: konu ->
deger` ya da `HAFIZA: yok`), ofis onu `bilgi_onerisi` / `hafiza_yok` olarak
kaydeder (hafizaya DOGRUDAN yazmaz), lider incelemede oneriyi gorur ve
dogruladigini kendi `BILGI:` satiriyla yazar; `hafiza_adimi` iscinin
satirini da sayar.

Sinanan: brifing satiri istiyor · gercek koltuk turunda oneri kaydedilir
ve hafizaya GECMEZ · parca parca akan metin (satir basi yok) yakalanir ·
`HAFIZA: yok` · satirsiz tur kayit uretmez · ayni oneri tekrar yazilmaz ·
5 oneri tavani · inceleme metni oneriyi gosterir · lider yazinca hafizada ·
`hafiza_adimi` isci durumunu (onerdi / yok / atladi) tasir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Koltuk, Ofis, Veritabani  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


_d = Path(tempfile.mkdtemp(prefix="ofis-hafiza-satiri-"))
db = Veritabani(_d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Hafiza", amac="a", basari_olcutu="b", kok_klasor=str(_d))
kn = ofis.kanat_ac("GENEL", "GE")
ofis.kadro.ise_al("demir", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(_d))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(_d))


def olaylar(tur, gorev_id):
    with db.baglanti() as c:
        return [r[0] for r in c.execute(
            "SELECT govde FROM olay WHERE tur=? AND gorev_id=? ORDER BY rowid", (tur, gorev_id))]


def is_kostur(baslik, cevap):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
    kt = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(senaryo="basarili", cevap=cevap))
    list(kt.akit(g["no"], "cinar"))
    return ofis.tahta.gorev(g["no"])


print("== iscinin hafiza satiri ==\n")
print("1. brifing")
g0 = ofis.tahta.gorev_ac("brifing", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
_k4 = ofis.brifing.k4_gorev(g0["no"])
sina("isin brifingi ZORUNLU hafiza satirini sablonuyla istiyor",
     "HAFIZA SATIRI -- ISI BITIRIRKEN ZORUNLU" in _k4 and "BILGI: <kisa konu> -> " in _k4
     and "HAFIZA: yok" in _k4)

print("\n2. gercek koltuk turu")
ga = is_kostur("port isi", "Bitti.\nKANIT dosya: r.md -> yazildi\n"
               "BILGI: servis portu -> 8080 (ayar.toml)\nBILGI: veritabani surumu -> PostgreSQL 16 (compose.yml)")
on = olaylar("bilgi_onerisi", ga["id"])
sina("oneri deftere kaydedildi (iki satir)", len(on) == 1 and on[0].count("->") == 2, str(on))
sina("oneri hafizaya DOGRUDAN gecmedi", not ofis.bellek.gecerli_olgular(), str(ofis.bellek.gecerli_olgular()))
gb = is_kostur("bos isi", "Bitti.\nKANIT dosya: r.md -> yazildi\nHAFIZA: yok")
sina("'HAFIZA: yok' kaydedildi", olaylar("hafiza_yok", gb["id"]) == ["HAFIZA: yok"])
gc = is_kostur("sessiz isi", "Bitti.\nKANIT dosya: r.md -> yazildi")
sina("satirsiz tur kayit uretmez",
     not olaylar("hafiza_yok", gc["id"]) and not olaylar("bilgi_onerisi", gc["id"]))

print("\n3. ayristirma")
kt = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor())
gd = ofis.tahta.gorev_ac("parca", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
kt._hafiza_satiri_yaz(gd["no"], "cinar", gd, ["Dosyayi yazdim.BIL", "GI: api adresi -> https://x.test (README)"])
sina("parca parca akan metin (satir basi yok) yakalandi",
     olaylar("bilgi_onerisi", gd["id"]) == ["api adresi -> https://x.test (README)"],
     str(olaylar("bilgi_onerisi", gd["id"])))
kt._hafiza_satiri_yaz(gd["no"], "cinar", gd, ["BILGI: api adresi -> https://x.test (README)"])
sina("ayni oneri tekrar yazilmaz", len(olaylar("bilgi_onerisi", gd["id"])) == 1)
ge = ofis.tahta.gorev_ac("cok", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
kt._hafiza_satiri_yaz(ge["no"], "cinar", ge, ["\n".join(f"BILGI: k{i} -> d{i}" for i in range(9))])
sina("en fazla 5 oneri", olaylar("bilgi_onerisi", ge["id"])[0].count("->") == 5)
gf = ofis.tahta.gorev_ac("kucuk", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
kt._hafiza_satiri_yaz(gf["no"], "cinar", gf, ["bilgi: kucuk harf -> sayilmaz\nhafiza: belki"])
sina("kucuk harf 'bilgi:' oneri sayilmaz (sablon buyuk harf)",
     not olaylar("bilgi_onerisi", gf["id"]) and not olaylar("hafiza_yok", gf["id"]))

print("\n4. lider incelemesi")
metin = ofis.lider.inceleme_metni(ga["no"])
sina("inceleme metni iscinin onerisini gosteriyor",
     "HAFIZA ONERISI" in metin and "servis portu -> 8080 (ayar.toml)" in metin)
sina("inceleme 'HAFIZA: yok' dedigini gosteriyor",
     "HAFIZA: yok' dedi" in ofis.lider.inceleme_metni(gb["no"]))
ofis.lider._hukmu_uygula(ga["no"], "KARAR: kapat\nBILGI: servis portu -> 8080 (ayar.toml)",
                         "demir", "cinar")
ofis.lider._hukmu_uygula(gb["no"], "KARAR: kapat\nHAFIZA: yok", "demir", "cinar")
ofis.lider._hukmu_uygula(gc["no"], "KARAR: kapat", "demir", "cinar")
sina("lider dogrulayinca hafizada", any(o["konu"] == "servis portu" and o["icerik"].startswith("8080")
                                       for o in ofis.bellek.gecerli_olgular()))
sina("lider YAZMADIGI oneri hafizaya girmedi",
     not any(o["konu"] == "veritabani surumu" for o in ofis.bellek.gecerli_olgular()))
ad = {g: olaylar("hafiza_adimi", x["id"]) for g, x in (("a", ga), ("b", gb), ("c", gc))}
sina("hafiza_adimi: isci onerdi", "isci: onerdi" in "".join(ad["a"]), str(ad["a"]))
sina("hafiza_adimi: isci yok dedi", "isci: yok" in "".join(ad["b"]), str(ad["b"]))
sina("hafiza_adimi: isci atladi", "isci: atladi" in "".join(ad["c"]), str(ad["c"]))

print("\n5. E3: lider yazmazsa iscinin onerisi patrona KART olur (kaybolmaz)")
gh = is_kostur("onerili is", "Bitti.\nKANIT dosya: r.md -> yazildi\n"
               "BILGI: kargo suresi -> 2 is gunu (magaza ayarlari)")
ofis.lider._hukmu_uygula(gh["no"], "KARAR: kapat\nHAFIZA: yok", "demir", "cinar")
_kart = [k for k in ofis.bellek.bekleyen_hafiza_onerileri() if k["konu"] == "kargo suresi"]
sina("lider 'HAFIZA: yok' dedi ama oneri KART oldu (hafizaya yazilmadi)",
     len(_kart) == 1 and _kart[0]["icerik"].startswith("2 is gunu") and _kart[0]["oneren"] == "cinar"
     and f"#{gh['no']}" in _kart[0]["alinti"]
     and not any(o["konu"] == "kargo suresi" for o in ofis.bellek.gecerli_olgular()), str(_kart))
_r = ofis.bellek.hafiza_onerisi_cevapla(_kart[0]["id"], yaz=True) if _kart else {}
sina("patron 'Yaz' deyince hafizada (patronun bilgisi olarak)",
     any(o["konu"] == "kargo suresi" for o in ofis.bellek.kapsam(kn).gecerli_olgular()), str(_r))
gi = is_kostur("onerili is 2", "Bitti.\nKANIT dosya: r.md -> yazildi\n"
               "BILGI: iade suresi -> 14 gun (sozlesme)\nBILGI: renk kodu -> #111 (marka)")
ofis.lider._hukmu_uygula(gi["no"], "KARAR: kapat\nBILGI: iade suresi -> 14 gun (sozlesme)",
                         "demir", "cinar")
sina("lider en az BIR bilgi yazdiysa kart ACILMAZ (lider karar vermis)",
     not any(k["konu"] in ("iade suresi", "renk kodu") for k in ofis.bellek.bekleyen_hafiza_onerileri()))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
