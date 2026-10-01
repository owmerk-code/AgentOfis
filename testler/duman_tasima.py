"""TASIMA duman testi -- `ofis/tasima.py` (ayrim asama 5).

Gercek dosya kopyalar ama GECICI bir sahnede: sahte ofis kodu, eski ev, yeni
ev, masaustu. Gercek ofise, gercek eve, gercek masaustune DOKUNMAZ.
Sinanan:
  1. deneme (plan) hicbir seye dokunmaz; eslemeler dogru
  2. engeller: hedef dolu, kosan is -> hic baslamaz
  3. uygula: defter yedegi; ev kopyasi (eski yerinde); proje eslenerek
     (.ofis/ekler, .ofis/karalama, eski BRIFING.md evin arsivine); her
     dosya dogru; defter (proje koku, ajan klasorleri) guncel; eski kok
     evin arsivinde (silinmedi)
  4. tasinan ofis acilir: kok masaustunde, ofisin icinde degil
  5. ikinci kez: tasinacak bir sey yok
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import tasima as T

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def hata_mi(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except Exception as exc:          # noqa: BLE001
        return str(exc) or exc.__class__.__name__
    return ""


print("== tasima duman testi ==\n")
A = Path(tempfile.mkdtemp(prefix="ofis-tasima-"))
KOD = A / "AgentOfis"                       # sahte ofis kodu
ESKI_EV, YENI_EV, MASA = A / ".agentofis", KOD / "ev", A / "Masaustu"
for d in (KOD / "veri", ESKI_EV / "codex", MASA):
    d.mkdir(parents=True)
(ESKI_EV / "codex" / "auth.json").write_text("{\"oturum\": 1}", encoding="utf-8")
(ESKI_EV / "kota.json").write_text("{}", encoding="utf-8")
eski_kok = KOD / "calisma"
for yol, icerik in {"rapor/rapor.md": "rapor", "ekler/a.png": "png", "karalama/x.py": "x",
                    "bilge/BRIFING.md": "eski brifing", "bilge/model-fiyat.md": "fiyat",
                    "gemini/BRIFING.md": "ajan degil, proje dosyasi"}.items():
    (eski_kok / yol).parent.mkdir(parents=True, exist_ok=True)
    (eski_kok / yol).write_text(icerik, encoding="utf-8")
DB = KOD / "veri" / "ofis.sqlite3"
db = Veritabani(DB)
ofis = Ofis.proje_ac(db, "Ofisim", amac="a", basari_olcutu="b", kok_klasor=str(A / "gecici-kok"))
with db.baglanti() as c:      # eski kurulum: kok OFISIN ICINDE (kapi bunu artik acmaz)
    c.execute("UPDATE proje SET kok_klasor = ?", (str(eski_kok),))
kn = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(eski_kok))
ofis.kadro.ise_al("bilge", "arastirma", kanat_id=kn, motor="sahte", klasor=str(eski_kok))


def icinde(yol):
    p = Path(yol).resolve()
    return any(p == e.resolve() or e.resolve() in p.parents for e in (KOD, ESKI_EV, YENI_EV))


def plan():
    return T.plan(DB, masaustu=MASA, ev_eski=ESKI_EV, ev_yeni=YENI_EV, icinde_mi=icinde, kapi=1)


print("1. deneme")
pl = plan()
pr = pl["projeler"][0] if pl["projeler"] else {}
es = dict(pr.get("dosyalar", []))
sina("ev tasinacak, proje bulundu", pl["ev"]["gerekli"] and pr.get("ad") == "Ofisim")
sina("  ekler -> .ofis/ekler", es.get(str(Path("ekler/a.png"))) == str(Path(".ofis/ekler/a.png")), str(es))
sina("  karalama -> .ofis/karalama", es.get(str(Path("karalama/x.py"))) == str(Path(".ofis/karalama/x.py")))
sina("  AJANIN eski BRIFING.md'si evin arsivine (projeye DEGIL)",
     [g for g, _ in pr.get("arsiv", [])] == [str(Path("bilge/BRIFING.md"))], str(pr.get("arsiv")))
sina("  ajan olmayan klasordeki BRIFING.md projede kalir (gemini/)",
     str(Path("gemini/BRIFING.md")) in es)
sina("  hedef masaustunde", pr.get("hedef") == str(MASA / "Ofisim"))
sina("deneme HICBIR seye dokunmadi", not YENI_EV.exists() and not (MASA / "Ofisim").exists()
     and eski_kok.is_dir())

print("\n2. engeller")
(MASA / "Ofisim").mkdir()
(MASA / "Ofisim" / "baska.txt").write_text("x", encoding="utf-8")
pl2 = plan()
sina("hedef dolu -> engel, uygula HIC baslamaz",
     any("Hedef dolu" in e for e in pl2["engeller"]) and "baslamadi" in hata_mi(T.uygula, pl2)
     and not YENI_EV.exists())
(MASA / "Ofisim" / "baska.txt").unlink()
g = ofis.tahta.gorev_ac("kosan", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'calisiyor' WHERE id = ?", (g["id"],))
sina("kosan is -> engel", any("kosan" in e for e in plan()["engeller"]))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (g["id"],))

print("\n3. uygula")
pl3 = plan()
sina("engel kalmadi (bos hedef klasoru engel degil)", pl3["engeller"] == [], str(pl3["engeller"]))
r = T.uygula(pl3, simdi="T1")
yeni = MASA / "Ofisim"
sina("defter yedegi alindi", Path(r["db_yedek"]).is_file())
sina("ev KOPYALANDI, eski ev YERINDE", (YENI_EV / "codex" / "auth.json").read_text(encoding="utf-8")
     == "{\"oturum\": 1}" and (ESKI_EV / "codex" / "auth.json").is_file())
sina("  gecici ad kalmadi", not (KOD / "ev.tasiniyor").exists() and not (MASA / "Ofisim.tasiniyor").exists())
sina("proje dosyasi yerinde ve AYNI", (yeni / "rapor" / "rapor.md").read_text(encoding="utf-8") == "rapor")
sina("  ekler .ofis/ekler'de", (yeni / ".ofis" / "ekler" / "a.png").read_text(encoding="utf-8") == "png")
sina("  karalama .ofis/karalama'da", (yeni / ".ofis" / "karalama" / "x.py").is_file())
sina("  .ofis/.gitignore '*'", (yeni / ".ofis" / ".gitignore").read_text(encoding="utf-8").strip() == "*")
sina("  projede gorunur ekler/ karalama/ YOK", not (yeni / "ekler").exists() and not (yeni / "karalama").exists())
sina("  ajanin eski BRIFING.md'si projede YOK, evin arsivinde",
     not (yeni / "bilge" / "BRIFING.md").exists()
     and (YENI_EV / "arsiv" / "eski-brifing-T1" / "Ofisim" / "bilge" / "BRIFING.md").is_file())
sina("  ajanin is dosyasi (model-fiyat.md) projede kaldi", (yeni / "bilge" / "model-fiyat.md").is_file())
d2 = Veritabani(DB)
o2 = Ofis.proje_ac(d2, "Ofisim")
sina("defter: proje koku masaustunde", o2.kok_klasoru() == str(yeni), o2.kok_klasoru())
sina("defter: ajan klasorleri cevrildi", all(a["klasor"] == str(yeni) for a in o2.kadro.liste()),
     str([a["klasor"] for a in o2.kadro.liste()]))
sina("eski kok SILINMEDI, evin arsivinde", not eski_kok.exists()
     and (YENI_EV / "arsiv" / "eski-kok-Ofisim-T1" / "rapor" / "rapor.md").is_file())

print("\n4. ikinci kez")
pl4 = plan()
sina("tasinacak bir sey kalmadi", not pl4["ev"]["gerekli"] and pl4["projeler"] == [], str(pl4["projeler"]))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {A}")
sys.exit(1 if KALAN else 0)
