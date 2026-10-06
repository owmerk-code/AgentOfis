# -*- coding: utf-8 -*-
"""IS BASINA GIT KAYDI (06.10.2026, Asama 4 / K13). Jeton yakmaz; GERCEK git.

Patron: "is basina kayit". Lider isi kapatinca, proje git deposuysa
YALNIZ isin olculen dosyalari tek kayda girer. Sinanan:
  - kok deponun ALT klasoru (git yollari depo kokune gore);
  - patronun kendi hazirladigi (staged) degisiklik kayda KARISMAZ;
  - yoksayilan, atfi belirsiz ve `.ofis/` dosyalari alinmaz;
  - silinen dosya kayda girer; adinda `[` olan dosya (desen degil);
  - kimligi olmayan depoda "AgentOfis" kimligi;
  - depo yoksa / ayar kapaliyken hicbir sey; kanca reddederse is yine
    kapanir, uyari yazilir (`--no-verify` YOK);
  - panelden "Bu isi geri al" = `git revert` (yeni kayit, dosya geri gelir).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

d = Path(tempfile.mkdtemp(prefix="ofis-git-kaydi-"))
# Patronun KENDI git ayarlari sinamaya karismasin (kimlik, kancalar).
(d / "bos.gitconfig").write_text("", encoding="utf-8")
os.environ["GIT_CONFIG_GLOBAL"] = str(d / "bos.gitconfig")
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

from ofis import Ofis, Veritabani  # noqa: E402
from ofis.db import simdi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def git(kok, *arg) -> str:
    r = subprocess.run(["git", "-C", str(kok), *arg], capture_output=True, text=True,
                       encoding="utf-8")
    return (r.stdout or "") + (r.stderr or "")


depo = d / "depo"
kok = depo / "site"
kok.mkdir(parents=True)
git(depo, "init", "-q", "-b", "main")
(kok / "eski.txt").write_text("eski\n", encoding="utf-8")
(kok / "silinecek.txt").write_text("sil\n", encoding="utf-8")
(kok / "patron.txt").write_text("p1\n", encoding="utf-8")
(depo / ".gitignore").write_text("*.log\n", encoding="utf-8")
git(depo, "add", "-A")
git(depo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "ilk")

db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Git", amac="a", basari_olcutu="b", kok_klasor=str(kok))
KA = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("mert", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("can", "backend", kanat_id=KA, motor="sahte", klasor=str(kok))


def is_ac(baslik, alan):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=alan, kanat_id=KA)
    g = ofis.tahta.sahiplen(g["no"], "can", g["revizyon"])
    return g


def degisim(g, yol, hal="degisti", belirsiz=0):
    with db.baglanti() as c:
        c.execute("INSERT INTO degisim (id, proje_id, gorev_id, ajan_ad, yol, hal, atif_belirsiz, "
                  "olusturuldu) VALUES (?, ?, ?, 'can', ?, ?, ?, ?)",
                  (uuid.uuid4().hex, ofis.proje_id, g["id"], yol, hal, belirsiz, simdi()))


def kapat(g):
    ofis.tahta.kanit_ekle(g["no"], "terminal", "test", "ok", "can")
    g = ofis.tahta.gorev(g["no"])
    return ofis.tahta.kapat(g["no"], g["revizyon"], kapatan="mert")


def olaylar(tur, g):
    with db.baglanti() as c:
        return [r[0] for r in c.execute("SELECT govde FROM olay WHERE tur = ? AND gorev_id = ?",
                                        (tur, g["id"]))]


print("1. kayit")
g1 = is_ac("sepet sayfasi", ["sepet.html", "eski.txt", "silinecek.txt", "[a].txt"])
(kok / "sepet.html").write_text("<p>sepet</p>\n", encoding="utf-8")
(kok / "eski.txt").write_text("yeni\n", encoding="utf-8")
(kok / "silinecek.txt").unlink()
(kok / "[a].txt").write_text("koseli\n", encoding="utf-8")
(kok / "hata.log").write_text("x\n", encoding="utf-8")            # yoksayilan
(kok / "baskasi.txt").write_text("belirsiz\n", encoding="utf-8")  # atfi belirsiz
(kok / ".ofis").mkdir()
(kok / ".ofis" / "not.md").write_text("x\n", encoding="utf-8")
# Patronun KENDI hazirladigi degisiklik: kayda karismamali.
(kok / "patron.txt").write_text("p2\n", encoding="utf-8")
git(depo, "add", "site/patron.txt")
for y, h in (("sepet.html", "eklendi"), ("eski.txt", "degisti"), ("silinecek.txt", "silindi"),
             ("[a].txt", "eklendi"), ("hata.log", "eklendi"), (".ofis/not.md", "eklendi")):
    degisim(g1, y, h)
degisim(g1, "baskasi.txt", "eklendi", belirsiz=1)
kapat(g1)
son = git(depo, "log", "-1", "--format=%s|%an|%ae")
dosyalar = set(git(depo, "show", "--name-only", "--format=", "HEAD").split())
sina("kapaninca TEK kayit acildi, basligi isin numarasiyla", son.startswith("#1 sepet sayfasi|"), son)
sina("kimligi olmayan depoda AgentOfis kimligi", "|AgentOfis|agentofis@yerel" in son, son)
sina("isin dosyalari kayitta (alt klasor, depo kokune gore)",
     {"site/sepet.html", "site/eski.txt", "site/silinecek.txt", "site/[a].txt"} <= dosyalar, str(dosyalar))
sina("PATRONUN hazirladigi degisiklik kayda KARISMADI", "site/patron.txt" not in dosyalar)
sina("  ve hala hazir (staged) duruyor", "M  site/patron.txt" in git(depo, "status", "--porcelain"))
sina("yoksayilan / .ofis / atfi belirsiz dosya ALINMADI",
     not ({"site/hata.log", "site/.ofis/not.md", "site/baskasi.txt"} & dosyalar), str(dosyalar))
ok = olaylar("git_kaydi", g1)
sina("olay yazildi ve belirsiz dosyayi SOYLUYOR", len(ok) == 1 and "baskasi.txt" in ok[0], str(ok))
from ofis import git_kaydi as GK  # noqa: E402
h1 = GK.isin_kaydi(db, ofis.proje_id, g1["id"])
sina("isin kaydi okunuyor (tam kimlik)", len(h1) == 40 and git(depo, "rev-parse", "HEAD").strip() == h1)

print("\n2. kayit yapilmayan haller")
n0 = git(depo, "rev-list", "--count", "HEAD").strip()
g2 = is_ac("degismeyen", ["eski.txt"])
degisim(g2, "eski.txt")         # olcum var ama dosya artik kayitli halinde
kapat(g2)
sina("gercekte degisiklik yoksa bos kayit acilmaz", git(depo, "rev-list", "--count", "HEAD").strip() == n0)
db.ayar_yaz(ofis.proje_id, GK.AYAR, "kapali")
g3 = is_ac("ayar kapali", ["kapali.txt"])
(kok / "kapali.txt").write_text("x\n", encoding="utf-8")
degisim(g3, "kapali.txt", "eklendi")
kapat(g3)
sina("ayar KAPALIYKEN kayit yok", git(depo, "rev-list", "--count", "HEAD").strip() == n0)
db.ayar_yaz(ofis.proje_id, GK.AYAR, "acik")
kancalar = depo / ".git" / "hooks"
(kancalar / "pre-commit").write_text("#!/bin/sh\necho kanca-reddetti >&2\nexit 1\n", encoding="utf-8")
g4 = is_ac("kanca", ["kanca.txt"])
(kok / "kanca.txt").write_text("x\n", encoding="utf-8")
degisim(g4, "kanca.txt", "eklendi")
kapat(g4)
uy = olaylar("uyari", g4)
sina("kanca reddedince is YINE kapandi", ofis.tahta.gorev(g4["no"])["durum"] == "bitti")
sina("  kayit yok ve sebep uyari olarak yazildi",
     git(depo, "rev-list", "--count", "HEAD").strip() == n0 and any("git kaydi" in u for u in uy), str(uy))
(kancalar / "pre-commit").unlink()
git(depo, "reset", "-q")        # kancanin biraktigi hazirligi temizle

d2 = d / "deposuz"
d2.mkdir()
o2 = Ofis.proje_ac(db, "Deposuz", amac="a", basari_olcutu="b", kok_klasor=str(d2))
k2 = o2.kanat_ac("T", "T")
o2.kadro.ise_al("ali", "backend", kanat_id=k2, motor="sahte", klasor=str(d2))
gx = o2.tahta.gorev_ac("deposuz is", neden="n", ana_hedef="h", kabul_olcutu="k",
                       yazma_alani=["a.txt"], kanat_id=k2)
gx = o2.tahta.sahiplen(gx["no"], "ali", gx["revizyon"])
(d2 / "a.txt").write_text("x", encoding="utf-8")
o2.tahta.kanit_ekle(gx["no"], "terminal", "t", "ok", "ali")
gx = o2.tahta.gorev(gx["no"])
o2.tahta.kapat(gx["no"], gx["revizyon"], kapatan="ali")
sina("depo DEGILSE git'e dokunulmaz (init yok, uyari yok)",
     not (d2 / ".git").exists() and not olaylar("uyari", gx))

print("\n3. panelden geri alma")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol, proje_ad="Git"))
r = ist.get(f"/api/gorev/{g1['no']}")
sina("is kartinda git kaydi var", r.status_code == 200 and r.json().get("git_kaydi") == h1, r.text[:200])
git(depo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "patron kendi")
r = ist.post(f"/api/gorev/{g1['no']}/git_geri_al", json={})
sina("geri alma basarili (yeni kayit)", r.status_code == 200 and r.json().get("geri_alinan") == h1, r.text[:300])
sina("dosyalar geri geldi / gitti",
     (kok / "eski.txt").read_text(encoding="utf-8") == "eski\n" and (kok / "silinecek.txt").exists()
     and not (kok / "sepet.html").exists())
sina("gecmis silinmedi (isin kaydi hala gecmiste)", h1[:10] in git(depo, "log", "--format=%H"))
r = ist.post(f"/api/gorev/{g2['no']}/git_geri_al", json={})
sina("kaydi olmayan is: 400 ve aciklama", r.status_code == 400 and "git kaydi yok" in r.text, r.text[:200])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
