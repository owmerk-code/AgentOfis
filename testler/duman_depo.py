# -*- coding: utf-8 -*-
"""DEPO: GitHub gonderiminin UC SERT kapisi -- ve gercekten gonderdigi.

Kullanicinin endisesi: *"yanlis hesaba yukleme."* Sinanan:

1. origin BEKLENEN adres degilse gonderim reddediliyor mu?
2. Depo gizli degilse (ya da olculemediyse) reddediliyor mu?
3. Kasadaki bir anahtar degeri dosyada gecerse reddediliyor ve DEGER
   soylenmeden DOSYA soyleniyor mu? Reddedince sahneleme geri aliniyor mu?
4. Kapilar gecince gercekten gonderiyor mu; degisiklik yoksa bos commit
   atmiyor mu; defter METIN olarak ve tutarli yaziliyor mu?

GERCEK GitHub'a ve gercek depoya DOKUNMAZ: uzak depo gecici bir `--bare`
klasordur, gorunurluk sorusu sahtedir, ayar gecici dosyadadir.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ANA = Path(tempfile.mkdtemp(prefix="ofis-depo-sinama-"))
os.environ["OFIS_DEPO_AYAR"] = str(ANA / "depo.json")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import depo as D   # noqa: E402

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


def git(kok, *a):
    return subprocess.run(["git", *a], cwd=kok, capture_output=True, text=True)


GIZLI = "gercek-anahtar-DEGERI-" + "x" * 20
OZEL = lambda _u: "PRIVATE"      # noqa: E731

try:
    uzak = ANA / "uzak.git"
    git(ANA, "init", "-q", "--bare", str(uzak))
    kok = ANA / "proje"
    kok.mkdir()
    git(kok, "init", "-q")
    git(kok, "config", "user.name", "sinama")
    git(kok, "config", "user.email", "sinama@yerel")
    git(kok, "config", "core.autocrlf", "false")
    (kok / "a.py").write_text("print(1)\n", encoding="utf-8")
    git(kok, "add", "-A")
    git(kok, "commit", "-q", "-m", "ilk")
    git(kok, "remote", "add", "origin", str(uzak))
    db = ANA / "o.sqlite3"
    c = sqlite3.connect(str(db))
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE olgu (konu TEXT, deger TEXT)")
    c.execute("INSERT INTO olgu VALUES ('iade', '14 gun')")
    c.commit()
    D.ayar_yaz({"uzak": str(uzak), "son": "", "acik": True})

    def gonder(**kw):
        kw.setdefault("gorunurluk", OZEL)
        kw.setdefault("degerler", [GIZLI])
        return D.gonder("sinama", kok=kok, db_yolu=db, **kw)

    def uzakta_commit():
        return git(uzak, "rev-list", "--all", "--count").stdout.strip() or "0"

    # ------------------------------------------------ 0. YALITIM
    print("\n0. YALITIM")
    sina("ayar gecici", str(D.ayar_yolu()).startswith(str(ANA)))

    # ------------------------------------------------ 1. ADRES
    print("\n1. ADRES -- beklenmeyen origin'e gonderilmez")
    # Yanlis adres de YEREL bir sahte depo: ilk surum github.com'da olmayan
    # bir adresi kullaniyordu ve kapi koparilinca sinama INTERNETE cikti.
    baska = ANA / "BASKASI.git"
    git(ANA, "init", "-q", "--bare", str(baska))
    git(kok, "remote", "set-url", "origin", str(baska))
    r = gonder()
    sina("yanlis adres REDDEDILDI", r["durum"] == "reddedildi", str(r))
    sina("sebep adresi soyluyor", "BASKASI" in r["sebep"])
    sina("yanlis adrese HICBIR SEY gitmedi",
         (git(baska, "rev-list", "--all", "--count").stdout.strip() or "0") == "0")
    git(kok, "remote", "remove", "origin")
    sina("origin yoksa REDDEDILDI", gonder()["durum"] == "reddedildi")
    git(kok, "remote", "add", "origin", str(uzak))
    sina("uzakta hala commit yok", uzakta_commit() == "0")

    # ------------------------------------------------ 2. GIZLILIK
    print("\n2. GIZLILIK -- herkese acik ya da bilinmeyen depoya gonderilmez")
    for gor, ad in (("PUBLIC", "herkese acik"), ("", "olculemedi")):
        r = gonder(gorunurluk=lambda _u, g=gor: g)
        sina(f"{ad} REDDEDILDI", r["durum"] == "reddedildi", str(r))
    sina("uzakta hala commit yok", uzakta_commit() == "0")

    # ------------------------------------------------ 3. SIR
    print("\n3. SIR -- kasadaki deger dosyadaysa gonderilmez")
    (kok / "not.md").write_text(f"anahtar: {GIZLI}\n", encoding="utf-8")
    r = gonder()
    sina("sirli dosya REDDEDILDI", r["durum"] == "reddedildi", str(r))
    sina("sebep DOSYAYI soyluyor", "not.md" in r["sebep"])
    sina("sebep DEGERI soylemiyor", GIZLI not in r["sebep"])
    sahnede = git(kok, "diff", "--cached", "--name-only").stdout.strip()
    sina("sahneleme geri alindi", sahnede == "", sahnede)
    sina("yerelde commit ATILMADI",
         git(kok, "rev-list", "--count", "HEAD").stdout.strip() == "1")
    (kok / "not.md").write_text("anahtar: ghp_" + "a" * 36 + "\n", encoding="utf-8")
    sina("bilinen anahtar bicimi de REDDEDILDI", gonder()["durum"] == "reddedildi")
    (kok / "not.md").unlink()

    # ------------------------------------------------ 4. GONDERIM
    print("\n4. GONDERIM -- kapilar gecince gercekten gider")
    r = gonder()
    sina("gonderildi", r["durum"] == "gonderildi", str(r))
    sina("uzakta commit var", uzakta_commit() == "2", uzakta_commit())
    sql_yol = kok / D.DISARI
    sql = sql_yol.read_text(encoding="utf-8") if sql_yol.exists() else ""
    sina("defter METIN olarak yazildi", "14 gun" in sql and "CREATE TABLE" in sql)
    sina("son gonderim ayara yazildi", bool(D.ayar_oku()["son"]))
    r2 = gonder()
    sina("degisiklik yoksa bos commit ATMAZ", r2["durum"] == "degisiklik_yok", str(r2))
    sina("uzakta commit sayisi degismedi", uzakta_commit() == "2")
    c.execute("INSERT INTO olgu VALUES ('kargo', 'ucretsiz')")
    c.commit()
    r3 = gonder()
    sina("defter degisince yeni gonderim", r3["durum"] == "gonderildi", str(r3))
    fark = git(kok, "show", "--stat", "HEAD").stdout
    sina("yalniz defter metni degisti", "ofis.sql" in fark and "a.py" not in fark)

    # ------------------------------------------------ 5. KAPALI + BUYUK
    print("\n5. KAPALI AYAR ve BUYUK DOSYA")
    a = D.ayar_oku()
    a["acik"] = False
    D.ayar_yaz(a)
    sina("kapaliyken gondermez", gonder()["durum"] == "reddedildi")
    a["acik"] = True
    D.ayar_yaz(a)
    eski = D.AZAMI_DOSYA_MB
    D.AZAMI_DOSYA_MB = 0.00001
    (kok / "b.txt").write_text("x" * 200, encoding="utf-8")
    r = gonder()
    D.AZAMI_DOSYA_MB = eski
    sina("sinir ustu dosya REDDEDILDI", r["durum"] == "reddedildi"
         and "b.txt" in r["sebep"], str(r))
    c.close()
finally:
    # Git nesneleri Windows'ta SALT OKUNUR; duz rmtree onlari atlar ve
    # %TEMP%'te artik kalir (ilk kosu birakti). Silmeden once yazilabilir yap.
    def _sil(islev, yol, _hata):
        os.chmod(yol, 0o700)
        islev(yol)
    shutil.rmtree(ANA, onexc=_sil)
    sina("gecici klasor silindi (artik yok)", not ANA.exists())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
