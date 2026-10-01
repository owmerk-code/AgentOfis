# -*- coding: utf-8 -*-
"""YEDEK: arsiv alinir, OLCULUR, geri yuklenir -- ve yanlis seyi almaz.

Bes soru:

1. Yazilmakta olan (WAL) defter TUTARLI mi aliniyor? Duz kopya yarim
   hali alirdi ve bu ancak geri yuklenince fark edilirdi.
2. SIR arsive giriyor mu? (girmemeli -- arsiv buluta gidecek)
3. Bozulmus arsiv "saglam" gorunuyor mu? (gorunmemeli)
4. Budama yalniz BIZIM arsivlerimizi mi siliyor?
5. Geri yukleme canli klasorun uzerine yaziyor mu? (yazmamali)

GERCEK yedek klasorune ve ayara DOKUNMAZ: ikisi de ortam degiskeniyle
gecici klasore cevrilir ve bunun gercekten oldugu ayrica olculur.
Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ANA = Path(tempfile.mkdtemp(prefix="ofis-yedek-sinama-"))
os.environ["OFIS_YEDEK_KOK"] = str(ANA / "yedekler")
os.environ["OFIS_YEDEK_AYAR"] = str(ANA / "yedek.json")
os.environ.pop("OFIS_YEDEK_KAPALI", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import yedek as Y   # noqa: E402

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


def kur_proje() -> Path:
    kok = ANA / "proje"
    (kok / "ofis").mkdir(parents=True)
    (kok / "ofis" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (kok / "ofis" / "__pycache__").mkdir()
    (kok / "ofis" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"x")
    (kok / "veri").mkdir()
    (kok / "gizli.env").write_text("ANAHTAR=cok-gizli-1234\n", encoding="utf-8")
    (kok / "calisma").mkdir()
    (kok / "calisma" / "rapor.md").write_text("rapor\n", encoding="utf-8")
    (kok / "eski.tar.gz").write_bytes(b"eski")
    # OFISIN EVI (01.10.2026): kok/ev arsive girmez; ama ayni adli ALT klasor
    # (kullanicinin projesinde `ev/` olabilir) girer.
    (kok / "ev" / "kabin").mkdir(parents=True)
    (kok / "ev" / "kabin" / "Cookies").write_bytes(b"cerez")
    (kok / "calisma" / "ev").mkdir()
    (kok / "calisma" / "ev" / "plan.md").write_text("ev plani\n", encoding="utf-8")
    return kok


try:
    # ------------------------------------------------ 0. YALITIM
    print("\n0. YALITIM -- gercek yedek klasoru kullanilmiyor")
    sina("yedek koku gecici", str(Y.yedek_koku()).startswith(str(ANA)))
    sina("ayar gecici", str(Y.ayar_yolu()).startswith(str(ANA)))
    sina("sinama defteri gercek sayilmiyor",
         not Y.gercek_defter_mi(ANA / "o.sqlite3"))
    os.environ["OFIS_YEDEK_KAPALI"] = "1"
    from ofis.db import VARSAYILAN_YOL
    sina("KAPALI bayragi gercek defteri de kapatir",
         not Y.gercek_defter_mi(VARSAYILAN_YOL))
    os.environ.pop("OFIS_YEDEK_KAPALI")

    kok = kur_proje()

    # --------------------------------------- 1. WAL DEFTERI TUTARLI
    print("\n1. YAZILMAKTA OLAN DEFTER tutarli aliniyor")
    dbyol = kok / "veri" / "o.sqlite3"
    yazan = sqlite3.connect(str(dbyol))
    yazan.execute("PRAGMA journal_mode=WAL")
    yazan.execute("PRAGMA wal_autocheckpoint=0")
    yazan.execute("CREATE TABLE t (x INTEGER)")
    yazan.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(500)])
    yazan.commit()
    # Satirlar su an WAL'da; ana dosyada DEGIL. Duz kopya bunlari kacirir.
    ana_kopya = ANA / "duz.sqlite3"
    shutil.copyfile(dbyol, ana_kopya)
    c = sqlite3.connect(str(ana_kopya))
    try:
        duz_sayi = c.execute("SELECT count(*) FROM t").fetchone()[0]
    except sqlite3.Error:
        duz_sayi = -1
    finally:
        # Acik kalan baglanti Windows'ta dosyayi kilitler ve gecici klasor
        # SILINEMEZ -- ilk surum %TEMP%'te 29 artik birakti.
        c.close()
    sina("(sahne) duz kopya WAL'daki satirlari KACIRIYOR", duz_sayi != 500,
         f"duz={duz_sayi}")

    s = Y.al("sinama", kok=kok, ek_hedefler=[])
    arsiv = Path(s["arsiv"])
    sina("arsiv yazildi", arsiv.exists())
    sina("yarim .part kalmadi", not list(arsiv.parent.glob("*.part")))
    with zipfile.ZipFile(arsiv) as z:
        adlar = set(z.namelist())
        acilan = ANA / "acilan.sqlite3"
        acilan.write_bytes(z.read("veri/o.sqlite3"))
    c = sqlite3.connect(str(acilan))
    try:
        arsiv_sayi = c.execute("SELECT count(*) FROM t").fetchone()[0]
    except sqlite3.Error as exc:
        # Cokme degil KALDI: cokerse geri kalan sinamalar hic kosmaz.
        arsiv_sayi = f"okunamadi: {exc}"
    finally:
        c.close()
    sina("arsivdeki defterde 500 satir var", arsiv_sayi == 500, str(arsiv_sayi))
    sina("defter butunlugu olculdu",
         s["db"] and s["db"][0]["butunluk"] == "ok")
    sina("-wal/-shm arsive girmedi",
         not any(a.endswith(("-wal", "-shm")) for a in adlar))
    yazan.close()

    # --------------------------------------------- 2. SIR GIRMIYOR
    print("\n2. SIR arsive GIRMIYOR, atlandigi SOYLENIYOR")
    sina("gizli.env arsivde YOK", "gizli.env" not in adlar)
    icerik = b"".join(zipfile.ZipFile(arsiv).read(a) for a in adlar)
    sina("sirrin DEGERI hicbir dosyada yok", b"cok-gizli-1234" not in icerik)
    sina("atlandigi raporlandi", "gizli.env" in s["sirlar_atlandi"])
    sina("pycache ve eski tar.gz girmedi",
         not any("__pycache__" in a or a.endswith(".tar.gz") for a in adlar))
    sina("kod ve ajan ciktisi girdi",
         {"ofis/a.py", "calisma/rapor.md"} <= adlar)
    sina("ofisin EVI (kok/ev: cerez, oturum, yedekler) arsive GIRMEDI",
         not any(a.startswith("ev/") for a in adlar), str(sorted(a for a in adlar if "ev/" in a)))
    sina("  ayni adli ALT klasor (calisma/ev) girdi", "calisma/ev/plan.md" in adlar)

    # --------------------------------------------- 3. DOGRULAMA
    print("\n3. DOGRULAMA bozulmayi yakaliyor")
    sina("saglam arsiv SAGLAM", Y.dogrula(arsiv)["tamam"])
    bozuk = ANA / "bozuk.zip"
    with zipfile.ZipFile(arsiv) as zi, zipfile.ZipFile(bozuk, "w") as zo:
        for a in zi.namelist():
            veri = zi.read(a)
            if a == "ofis/a.py":
                veri = b"print('DEGISTI')\n"
            zo.writestr(a, veri)
    d = Y.dogrula(bozuk)
    sina("icerigi degismis arsiv BOZUK", not d["tamam"], str(d["bulgular"]))
    sina("hangi dosya oldugu soyleniyor",
         any("ofis/a.py" in b for b in d["bulgular"]))
    yarim = ANA / "yarim.zip"
    yarim.write_bytes(arsiv.read_bytes()[: arsiv.stat().st_size // 2])
    sina("yarim kesilmis arsiv BOZUK", not Y.dogrula(yarim)["tamam"])

    # --------------------------------------------- 4. BUDAMA
    print("\n4. BUDAMA yalniz bizim arsivleri siler")
    bk = ANA / "budama"
    bk.mkdir()
    for i in range(5):
        (bk / f"{Y.AD_ONEKI}2026010{i}-000000-x.zip").write_bytes(b"z")
    (bk / "kullanicinin-dosyasi.zip").write_bytes(b"k")
    silinen = Y.budama(bk, 3)
    sina("en eski 2 silindi", len(silinen) == 2 and "20260100" in silinen[0])
    sina("son 3 kaldi", len(Y.arsivler(bk)) == 3)
    sina("baskasinin dosyasina DOKUNULMADI",
         (bk / "kullanicinin-dosyasi.zip").exists())
    sina("saklanan 0 verilse bile en az 1 kalir",
         (Y.budama(bk, 0) or True) and len(Y.arsivler(bk)) == 1)

    # ------------------------------------------ 5. EK HEDEF
    print("\n5. EK HEDEF -- ulasilamazsa is durmaz, SOYLENIR")
    drive = ANA / "drive"
    drive.mkdir()
    s2 = Y.al("hedefli", kok=kok, ek_hedefler=[str(drive), str(ANA / "yok")])
    durum = {Path(h["klasor"]).name: h["durum"] for h in s2["hedefler"]}
    sina("var olan hedefe kopyalandi", durum.get("drive") == "tamam"
         and (drive / Path(s2["arsiv"]).name).exists())
    sina("olmayan hedef 'ulasilamadi' dedi", durum.get("yok") == "ulasilamadi")
    sina("buna ragmen yerel yedek alindi", Path(s2["arsiv"]).exists())

    for kotu, neden in ((r"goreli\klasor", "goreli"),
                        (str(ANA / "olmayan"), "olmayan"),
                        (str(Y.PROJE_KOKU / "veri"), "proje ici")):
        try:
            Y.hedef_ekle(kotu)
            sina(f"{neden} hedef reddedildi", False)
        except Y.YedekHatasi:
            sina(f"{neden} hedef reddedildi", True)
    sina("gecerli hedef eklendi", Y.hedef_ekle(str(drive)) == str(drive.resolve()))
    sina("ayara yazildi", str(drive.resolve()) in Y.ayar_oku()["hedefler"])

    # ------------------------------------------ 6. GERI YUKLEME
    print("\n6. GERI YUKLEME bos klasore; canliya ASLA")
    hedef = ANA / "geri"
    r = Y.geri_yukle(arsiv, hedef)
    sina("dosyalar acildi", (hedef / "ofis" / "a.py").read_text(
        encoding="utf-8") == "print('a')\n")
    c = sqlite3.connect(str(hedef / "veri" / "o.sqlite3"))
    try:
        geri_sayi = c.execute("SELECT count(*) FROM t").fetchone()[0]
    except sqlite3.Error as exc:
        geri_sayi = f"okunamadi: {exc}"
    finally:
        c.close()
    sina("geri yuklenen defter 500 satir", geri_sayi == 500, str(geri_sayi))
    sina("manifest disari cikmadi", not (hedef / "_manifest.json").exists())
    # "Canli kok" GECICI sahte projedir. Ilk surum gercek kokle sinaniyordu
    # ve kapi mutasyonla koparilinca arsiv GERCEK projenin icine acildi
    # (calisma/x). Sinama, korudugu seyi bozabilecek bir sahnede kosmamali.
    asil_kok = Y.PROJE_KOKU
    Y.PROJE_KOKU = kok.resolve()
    try:
        for yer, neden in ((hedef, "dolu klasor"), (kok, "canli kok"),
                           (kok / "calisma" / "x", "canli kokun ici")):
            try:
                Y.geri_yukle(arsiv, yer)
                sina(f"{neden} reddedildi", False)
            except Y.YedekHatasi:
                sina(f"{neden} reddedildi", True)
        sina("canli kokun icine hicbir sey acilmadi",
             not (kok / "calisma" / "x").exists())
    finally:
        Y.PROJE_KOKU = asil_kok
    try:
        Y.geri_yukle(bozuk, ANA / "geri2")
        sina("bozuk arsiv acilmadi", False)
    except Y.YedekHatasi:
        sina("bozuk arsiv acilmadi", not (ANA / "geri2").exists())
    kacis = ANA / "kacis.zip"
    with zipfile.ZipFile(arsiv) as zi, zipfile.ZipFile(kacis, "w") as zo:
        for a in zi.namelist():
            zo.writestr(a, zi.read(a))
        zo.writestr("../disari.txt", "x")
    try:
        Y.geri_yukle(kacis, ANA / "geri3")
        sina("zip yol kacisi reddedildi", False)
    except Y.YedekHatasi:
        sina("zip yol kacisi reddedildi", not (ANA / "disari.txt").exists())

    # ------------------------------------- 6b. PROJELER (01.10 ayrim)
    print("\n6b. masaustundeki PROJELER arsive girer; ev ve karalama girmez")
    pk = ANA / "Masaustu" / "Ofisim"
    (pk / "semuparfum-rapor").mkdir(parents=True)
    (pk / "semuparfum-rapor" / "rapor.md").write_text("r\n", encoding="utf-8")
    (pk / ".ofis" / "ekler").mkdir(parents=True)
    (pk / ".ofis" / "ekler" / "a.png").write_bytes(b"png")
    (pk / ".ofis" / "karalama").mkdir(parents=True)
    (pk / ".ofis" / "karalama" / "x.py").write_text("x", encoding="utf-8")
    (pk / ".env").write_text("SIR=1", encoding="utf-8")
    sp = Y.al("proje", kok=kok, ek_hedefler=[], projeler=[("Ofisim", pk), ("Kayip", ANA / "yok")])
    with zipfile.ZipFile(sp["arsiv"]) as z:
        pa = set(z.namelist())
    sina("proje dosyasi arsivde (projeler/Ofisim/...)", "projeler/Ofisim/semuparfum-rapor/rapor.md" in pa)
    sina("  sohbet ekleri (.ofis/ekler) arsivde", "projeler/Ofisim/.ofis/ekler/a.png" in pa)
    sina("  yardimci betik (.ofis/karalama) arsivde YOK", not any("karalama" in a for a in pa))
    sina("  projedeki sir (.env) YOK, atlandigi soylendi",
         not any(a.endswith(".env") for a in pa) and any(s.endswith(".env") for s in sp["sirlar_atlandi"]))
    sina("  klasoru bulunamayan proje SOYLENDI", any("Kayip" in b for b in sp["projeler_bulunamayan"]))
    sina("  arsiv dogrulamadan gecti (manifest proje dosyalarini da tasiyor)", Y.dogrula(Path(sp["arsiv"]))["tamam"])
    sina("sinama koku (gercek ofis degil) gercek projeleri OKUMADI",
         not any(a.startswith("projeler/") for a in adlar))
    # Yedek klasoru kok/ev icinde OLABILIR (ev arsive girmez); kokun baska yerinde olamaz.
    try:
        Y.al("ev", kok=kok, ek_hedefler=[], projeler=[], hedef_kok=kok / "ev" / "yedekler")
        sina("yedek klasoru kok/ev icinde kabul", True)
    except Y.YedekHatasi as exc:
        sina("yedek klasoru kok/ev icinde kabul", False, str(exc))
    try:
        Y.al("ic", kok=kok, ek_hedefler=[], projeler=[], hedef_kok=kok / "calisma" / "yedek")
        sina("  kokun baska yerinde REDDEDILIR", False)
    except Y.YedekHatasi:
        sina("  kokun baska yerinde REDDEDILIR", True)

    # ------------------------------------------ 7. GUNLUK KAPI
    print("\n7. GUNLUK KAPI -- 24 saat dolmadan tekrar almaz")
    sina("son yedek az once", Y.son_yedek_saat() < 1)
    olaylar = []
    sina("24 saat dolmadan almiyor",
         Y.gerekirse_al(lambda t, g: olaylar.append((t, g))) == {})
    a = Y.ayar_oku()
    a["son"] = "2020-01-01T00:00:00"
    Y.ayar_yaz(a)
    # Proje kokunu gecici koke cevir ki gercek proje arsivlenmesin.
    asil_kok = Y.PROJE_KOKU
    Y.PROJE_KOKU = kok
    # Gercek proje listesi OKUNMAMALI: sonuca bakmak yetmez (gercek defterde
    # klasoru olan proje yoksa fark gorunmez -- olculdu, mutasyon gecti).
    _gp_cagri, _gp_asil = [], Y.gercek_projeler
    Y.gercek_projeler = lambda: _gp_cagri.append(1) or []
    try:
        g = Y.gerekirse_al(lambda t, g: olaylar.append((t, g)))
    finally:
        Y.PROJE_KOKU = asil_kok
        Y.gercek_projeler = _gp_asil
    sina("gecici kokle yedek alinirken GERCEK proje listesi OKUNMADI", _gp_cagri == [])
    sina("sure dolunca aldi", bool(g.get("arsiv")))
    # PROJE_KOKU geciciye cevrildi: gercek ofis SANILIP patronun gercek
    # projeleri bu gecici arsive KOPYALANMAMALI (01.10 olculdu, duzeltildi).
    with zipfile.ZipFile(g["arsiv"]) as _zg:
        _gn = _zg.namelist()
    sina("  gecici kokle alinan gunluk yedege GERCEK projeler girmedi",
         not any(n.startswith("projeler/") for n in _gn), str([n for n in _gn if n.startswith("projeler/")][:3]))
    sina("olay yazildi", any(t == "yedek_alindi" for t, _ in olaylar))
    sina("bayat ayar tazelendi", Y.son_yedek_saat() < 1)
    (ANA / "yedek.json").write_text("{bozuk", encoding="utf-8")
    try:
        Y.ayar_oku()
        sina("bozuk ayar SESSIZCE bos sayilmadi", False)
    except Y.YedekHatasi:
        sina("bozuk ayar SESSIZCE bos sayilmadi", True)
finally:
    shutil.rmtree(ANA, ignore_errors=True)
    # Artik SAYILIR, varsayilmaz (PLAN E05).
    sina("gecici klasor silindi (artik yok)", not ANA.exists())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
