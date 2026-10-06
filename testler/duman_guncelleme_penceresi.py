# -*- coding: utf-8 -*-
"""GUNCELLEME PENCERESI (06.10.2026, Asama 3 / E82). Jeton yakmaz.

Model ve CLI degisikligi yalniz ofis BOSKEN uygulanir. Once yalniz CLI,
yalniz `calisiyor` iste erteleniyordu; model is ortasinda degisebiliyor,
sirada bekleyen patron mesaji sayilmiyordu.

Sinanan `guncelleme.mesgul`: canli surecin isi mesgul · olu surecten kalan
"calisiyor" kaydi mesgul DEGIL (cokme guncellemeyi sonsuza dek kilitlemez) ·
kimliksiz kayit temkinle mesgul · sirada bekleyen mesaj mesgul · olu
surecin "kosuyor" sira kaydi degil · incelemedeki is degil. Otomatik
ilerleme mesgulken HICBIR oneriyi uygulamaz (model dahil), bosken uygular.
Insan CLI onayi mesgulken reddedilir, model onayi gecer.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, guncelleme as G, surec  # noqa: E402
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


d = Path(tempfile.mkdtemp(prefix="ofis-gpencere-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Pencere", amac="a", basari_olcutu="b", kok_klasor=str(d))
kn = ofis.kanat_ac("GENEL", "GE")
PID = ofis.proje_id
g = ofis.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)


def gorev_durumu(durum, kim):
    with db.baglanti() as c:
        c.execute("UPDATE gorev SET durum = ?, kosan_surec = ? WHERE id = ?", (durum, kim, g["id"]))


def kuyruk(durum, kim=""):
    with db.baglanti() as c:
        c.execute("DELETE FROM kuyruk")
        if durum:
            c.execute("INSERT INTO kuyruk (id, proje_id, metin, lider_ad, durum, kosan_surec, olusturuldu) "
                      "VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, PID, "x", "lale", durum, kim, simdi()))


OLU = "999999:12345"
print("== guncelleme penceresi ==\n")
print("1. mesgul mu")
gorev_durumu("hazir", "")
sina("bos ofis: mesgul degil", G.mesgul(db, PID) == "")
gorev_durumu("calisiyor", surec.kimlik())
sina("canli surecin isi: MESGUL", "is calisiyor" in G.mesgul(db, PID), G.mesgul(db, PID))
gorev_durumu("calisiyor", OLU)
sina("olu surecten kalan kayit: mesgul DEGIL", G.mesgul(db, PID) == "", G.mesgul(db, PID))
gorev_durumu("calisiyor", "")
sina("kimliksiz kayit: temkinle MESGUL", bool(G.mesgul(db, PID)))
gorev_durumu("inceleme", surec.kimlik())
sina("incelemedeki is: mesgul degil (kosmuyor)", G.mesgul(db, PID) == "", G.mesgul(db, PID))
kuyruk("bekliyor")
sina("sirada bekleyen patron mesaji: MESGUL", "sirada 1 mesaj" in G.mesgul(db, PID))
kuyruk("kosuyor", OLU)
sina("olu surecin 'kosuyor' sira kaydi: mesgul degil", G.mesgul(db, PID) == "")
kuyruk("kosuyor", surec.kimlik())
sina("canli 'kosuyor' sira kaydi: MESGUL", bool(G.mesgul(db, PID)))

print("\n2. otomatik ilerleme")
cagri = []
G.otomatik_mi = lambda db_, pid: True
G.otomatik_uygulanir_mi = lambda db_, pid, o: True
_oneri = [{"no": 1, "tur": "model", "anahtar": "model:x", "ozet": "codex model x -> y"},
          {"no": 2, "tur": "cli", "anahtar": "cli:claude", "ozet": "claude CLI 1 -> 2"}]
G.bekleyenler = lambda db_, pid: list(_oneri)
G.uygula = lambda o, no, **k: (cagri.append(no), {"basarili": True})[1]
r = G._otomatik_ilerle(ofis)
sina("mesgulken MODEL de uygulanmadi", not cagri and all(x.get("ertelendi") for x in r), str(r))
sina("erteleme sebebi soyleniyor", all("mesgul" in x.get("mesaj", "") for x in r))
kuyruk("")
gorev_durumu("bitti", "")
r = G._otomatik_ilerle(ofis)
sina("bosken iki oneri de uygulandi (once CLI)", cagri == [2, 1], str(cagri))

print("\n3. insan onayi")
import importlib  # noqa: E402
importlib.reload(G)
gorev_durumu("calisiyor", surec.kimlik())
G._bul = lambda db_, pid, no: {"tur": "cli", "anahtar": "cli:claude", "ozet": "x", "motor": "claude"}
try:
    G.uygula(ofis, 1, veren="insan")
    sina("mesgulken insan CLI onayi reddedildi", False)
except G.GuncellemeHatasi as exc:
    sina("mesgulken insan CLI onayi reddedildi", "mesgul" in str(exc), str(exc))
gorev_durumu("bitti", "")

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
