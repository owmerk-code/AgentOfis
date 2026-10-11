# -*- coding: utf-8 -*-
"""PATRONUN KREDI SINIRI (11.10.2026, patron: "mesajinda sinir verirsen o is
icin sorulmasin"). Jeton ve kredi yakmaz.

Sinanan:
  1. sinir OFISCE okunur: sayi + kredi + sinir sozcugu; "sor/onayimi al"
     iceren cumle izin degil; "onayli" izindir; birden cok sinirda en kucugu
  2. sinir icindeki paket SORULMADAN onaylanir, ajana "TURU BITIRME" denir;
     kayit patronun alintisini tasir; onay_istendi / onay_cevabi YAZILMAZ
     (bildirim ve "onay tur surerken geldi" kurali tetiklenmez)
  3. tarayici kapisi bu paketle uretim tiklamasini SORMADAN gecirir
  4. sinir ISTEGIN toplamidir (ayni istekten iki is) -- asan paket patrona gider
  5. sinir yazilmadiysa her sey eskisi gibi (paket sorulur)
  6. brifing ve sohbet karti izni gosterir
  7. MUTASYON: sinir denetimi kaldirilinca 4. madde ates eder
"""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from ofis import Ofis, Veritabani, kredi_izni as KI  # noqa: E402
from ofis import mcp_sunucu as S  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("1. sinir okuma")
ORNEK = [
    ("150 krediye kadar onaylı", 150), ("Toplam kredi 150'yi geçmesin.", 150),
    ("video ≤150 kredi", 150), ("en fazla 150 kredi harca", 150),
    ("Brave ve Belle, toplam 1.000 krediye kadar. Sonra bana sor.", 1000),
    ("100 kredilik bütçe", 100), ("en fazla 200 kredi; 150'yi geçme kredi", 150),
    ("1000 kredim var", None), ("150 kredi harcamadan önce bana sor", None),
    ("150 krediye kadar ama önce onayımı al", None), ("en fazla 150 kredi, onaya gönder", None),
    ("kredi harcama", None), ("150 kredi ile yap", None), ("0 krediye kadar", None),
]
for metin, bek in ORNEK:
    sina(f"{metin!r} -> {bek}", KI.sinir(metin)[0] == bek, str(KI.sinir(metin)))

D = Path(tempfile.mkdtemp(prefix="ofis-kredi-izni-"))
o = Ofis.proje_ac(Veritabani(D / "o.sqlite3"), "Kredi", amac="a", basari_olcutu="b", kok_klasor=str(D))
kn = o.kanat_ac("ANA", "AN")
o.kadro.ise_al("ada", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(D))
o.kadro.ise_al("kerem", "video", kanat_id=kn, motor="sahte", klasor=str(D))


def is_ac(baslik, soz, istek=""):
    g = o.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn,
                         yazma_alani=[baslik.replace(" ", "_") + "/"])
    if istek:
        with o.db.baglanti() as c:
            c.execute("UPDATE gorev SET istek_id = ? WHERE id = ?", (istek, g["id"]))
    o.db.olay_yaz(o.proje_id, "patron_sozu", soz, ajan_ad="insan", gorev_id=g["id"])
    return o.tahta.gorev(g["no"])


def oturum(no):
    class _Ot:
        ofis, ajan_ad, gorev_no = o, "kerem", no

        def gorev(self):
            return o.tahta.gorev(no)
    return _Ot()


def olay_say(tur, gid):
    with o.db.baglanti() as c:
        return c.execute("SELECT COUNT(*) FROM olay WHERE tur = ? AND gorev_id = ?", (tur, gid)).fetchone()[0]


SOZ = "Brave ve Belle için 15 sn video yap, toplam 150 krediye kadar onaylı."
print("\n2. sinir icindeki paket sorulmaz")
ga = is_ac("brave video", SOZ, istek="istek-1")
cev = S.arac_onay_iste(oturum(ga["no"]), {"eylem": "Brave paketi", "ayrinti": "3 klip", "kredi": 60, "uretim": 3})
with o.db.baglanti() as c:
    kay = [dict(r) for r in c.execute("SELECT * FROM onay WHERE gorev_id = ?", (ga["id"],))]
sina("cevap ONAYLANDI + TURU BITIRME", "ONAYLANDI" in cev and "TURU BITIRME" in cev and "SIMDI DUR" not in cev, cev)
sina("  kayit onaylandi, patronun alintisi notta", len(kay) == 1 and kay[0]["durum"] == "onaylandi"
     and "150 krediye kadar onaylı" in kay[0]["cevap_notu"] and kay[0]["cevap_notu"].startswith(KI.ISARET), str(kay)[:300])
sina("  bekleyen onay YOK", not o.postane.bekleyen_onaylar("kerem"))
sina("  onay_istendi / onay_cevabi YAZILMADI (bildirim yok, koltuk 'onay geldi' saymaz)",
     olay_say("onay_istendi", ga["id"]) == 0 and olay_say("onay_cevabi", ga["id"]) == 0
     and olay_say("kredi_izni", ga["id"]) == 1)

print("\n3. tarayici kapisi bu paketle uretimi sormaz")
os.environ.update({"OFIS_DB": str(D / "o.sqlite3"), "OFIS_PROJE": o.proje_id, "OFIS_AJAN": "kerem",
                   "OFIS_GOREV": str(ga["no"])})
try:
    from ofis.tarayici_kapi import OfisBagi  # noqa: E402
    bag = OfisBagi()
    bulgu = {"sinif": "kredi", "arac": "browser_click", "hedef": "Oluşturmaya başla",
             "element": "Oluşturmaya başla", "eylem": "uret", "url": "https://flow.google.com/x",
             "esles": "x", "risk": "orta", "sebep": "kredi", "ad": "URETIM KREDISI"}
    gecen = [bag.karar(dict(bulgu))["izin"] for _ in range(4)]
    sina("paketteki 3 uretim gecti, 4. SORULDU", gecen == [True, True, True, False], str(gecen))
finally:
    for a in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV"):
        os.environ.pop(a, None)

print("\n4. sinir ISTEGIN toplami: ikinci is kalandan fazlasini sorar")
gb = is_ac("belle video", SOZ, istek="istek-1")
d = KI.durum(o.db, o.proje_id, gb)
sina("kardes iste kullanilan 60, kalan 90", d["kullanilan"] == 60 and d["kalan"] == 90, str(d))
cev2 = S.arac_onay_iste(oturum(gb["no"]), {"eylem": "Belle paketi", "kredi": 100, "uretim": 4})
sina("100 kredilik paket patrona GITTI (sinir asiliyor)", "SIMDI DUR" in cev2 and "kalan 90" in cev2
     and len([x for x in o.postane.bekleyen_onaylar("kerem") if "Belle paketi" in x["eylem"]]) == 1, cev2)
cev3 = S.arac_onay_iste(oturum(gb["no"]), {"eylem": "Belle paketi kucuk", "kredi": 80, "uretim": 4})
sina("80 kredilik paket sorulmadan gecti (kalan 90)", "ONAYLANDI" in cev3, cev3)
sina("  simdi kalan 10", KI.durum(o.db, o.proje_id, gb)["kalan"] == 10)

print("\n5. sinir yazilmadiysa paket eskisi gibi sorulur")
gc = is_ac("baska video", "Belle için 15 sn reels yap.")
cev4 = S.arac_onay_iste(oturum(gc["no"]), {"eylem": "paket", "kredi": 20, "uretim": 1})
sina("sinirsiz istekte paket SORULDU", "SIMDI DUR" in cev4 and "sinir" not in cev4.split("(")[0], cev4)
gd = is_ac("ayri istek", "Tek video, 500 krediye kadar.", istek="istek-2")
sina("baska istegin siniri bu isteki sayaci etkilemez",
     KI.durum(o.db, o.proje_id, gd)["kalan"] == 500, str(KI.durum(o.db, o.proje_id, gd)))

print("\n6. brifing ve sohbet karti")
satir = KI.brifing_satiri(o.db, o.proje_id, gb)
sina("brifing satiri: sinir, kalan, TURU BITIRME", "150" in satir and "kalan 10" in satir and "TURU BITIRME" in satir, satir)
sina("sinirsiz iste brifing satiri yok", KI.brifing_satiri(o.db, o.proje_id, gc) == "")
from ofis import takim as T  # noqa: E402
sina("kredi_izni sohbet akisinda", "kredi_izni" in T.AKIS_OLAYLARI)

print("\n7. MUTASYON: sinir denetimi kaldirilinca asan paket gecer (test yakaliyor)")
_asil = KI.karar
KI.karar = lambda db, pid, g, kredi: {**_asil(db, pid, g, 0), "gecer": True}
try:
    ge = is_ac("mutasyon", SOZ, istek="istek-1")
    cev5 = S.arac_onay_iste(oturum(ge["no"]), {"eylem": "asan", "kredi": 1000, "uretim": 9})
    sina("denetimsiz kodda asan paket GECTI (4. madde bu farki yakalar)", "ONAYLANDI" in cev5, cev5)
finally:
    KI.karar = _asil

print("\n8. Flow tanitim sayfasindaki GIRIS dugmesi kredi tiklamasi DEGIL (11.10 canli: paketten hak dustu)")
from ofis import riskli as R  # noqa: E402


def _tik(url):
    return (R.degerlendir("browser_click", {"element": "Google Flow ile oluştur", "target": "e1"}, url=url,
                          sayfa_metni="Google Flow ile oluştur", uretim_ayari="Video · 720p · 8 sn. x1")
            or {}).get("sinif")


sina("/about sayfasinda 'Google Flow ile oluştur' kredi sayilmaz", _tik("https://flow.google.com/about") is None)
sina("ana sayfada da sayilmaz", _tik("https://flow.google.com/") is None)
sina("PROJE sayfasinda ayni dugme kredi (sorulur)", _tik("https://flow.google.com/project/x") == "kredi")

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
