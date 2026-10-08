"""AYRIM duman testi -- ofisin kendi yeri ile patronun projeleri karismaz (01.10.2026).

Kullanici: *"agent sistemimizin altyapisi, kodlari, ajanlari, hafizasi ... tek
bir yerde, arka planda; projeler masaustunde kendi klasorlerinde."* Olculdu:
ajanlarin koku ofisin kod klasorunun icindeydi ve Claude ajani ofisin
CLAUDE.md'sini (gelistirme anayasasi) her turda okuyordu.

Jeton yakmaz. Sinanan:
  1. `ofis_icinde_mi`: ofisin kodu, yeni ev, eski ev -> icinde; masaustu -> degil
  2. proje koku ofisin icinde ACILAMAZ (yapi, rica degil)
  3. gercek defterde koksuz proje MASAUSTUNDE (ofisin icine dusmez)
  4. masaustu klasor adi Windows'ta gecerli
  5. acilista: koku ofisin icinde kalmis proje icin UYARI (sessiz kalinmaz)
  6. lider plani: ajan adli klasor yok, tek is is adli klasorde
  7. ornek ofisin koku de ofisin disinda
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ofis as _ofis_paket
from ofis import Ofis, Veritabani
from ofis import yollar as Y
from ofis import db as _dbmod

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== ayrim duman testi ==\n")

print("1. ofisin yeri")
sina("ofisin kod klasoru icinde -> True", Y.ofis_icinde_mi(Y.OFIS_KODU / "calisma"))
sina("yeni ev icinde -> True", Y.ofis_icinde_mi(Y.YENI_EV / "x"))
sina("eski ev icinde -> True", Y.ofis_icinde_mi(Y.ESKI_EV / "codex"))
sina("masaustundeki proje -> False", not Y.ofis_icinde_mi(Y.MASAUSTU / "Ofisim"))
sina("ad benzeri ama DISARIDA (AgentOfis-Projeler) -> False",
     not Y.ofis_icinde_mi(Y.OFIS_KODU.parent / (Y.OFIS_KODU.name + "-Projeler")))

kok = Path(tempfile.mkdtemp(prefix="ofis-ayrim-"))
db = Veritabani(kok / "o.sqlite3")

print("\n2. kok ofisin icinde ACILAMAZ")
for yer in (Y.OFIS_KODU / "calisma", Y.YENI_EV / "proje", Y.ESKI_EV / "p"):
    try:
        Ofis.proje_ac(db, f"Yasak {yer.name}", kok_klasor=str(yer))
        sina(f"  reddedildi: {yer}", False, "ACILDI")
    except ValueError as exc:
        sina(f"  reddedildi: {yer.name}", "ofisin kendi yerinde" in str(exc))
o = Ofis.proje_ac(db, "Disarida", kok_klasor=str(kok / "proje"))
sina("ofis disindaki kok kabul", o.kok_klasoru() == str((kok / "proje").resolve()))

print("\n3. gercek defterde koksuz proje MASAUSTUNDE")
_asil_yol, _asil_masa = _dbmod.VARSAYILAN_YOL, Y.MASAUSTU
sahte_masa = kok / "Masaustu"
try:
    _dbmod.VARSAYILAN_YOL = kok / "gercek.sqlite3"
    Y.MASAUSTU = sahte_masa
    gdb = Veritabani(_dbmod.VARSAYILAN_YOL)
    g = Ofis.proje_ac(gdb, "Yeni Proje")
    sina("gercek defterde yeni proje -> Masaustu\\Yeni Proje",
         g.kok_klasoru() == str(sahte_masa / "Yeni Proje"), g.kok_klasoru())
    with gdb.baglanti() as c:
        c.execute("UPDATE proje SET kok_klasor = '' WHERE id = ?", (g.proje_id,))
    sina("koku bos kalmis gercek proje ofisin icine (veri/calisma) DUSMEZ",
         g.kok_klasoru() == str(sahte_masa / "Yeni Proje")
         and not Y.ofis_icinde_mi(g.kok_klasoru()), g.kok_klasoru())
    t = Ofis.proje_ac(db, "Sinama Projesi")
    sina("sinama defterinde eski davranis (defterin yani)",
         t.kok_klasoru() == str(kok / "calisma"), t.kok_klasoru())
finally:
    _dbmod.VARSAYILAN_YOL, Y.MASAUSTU = _asil_yol, _asil_masa

print("\n4. klasor adi")
sina("Windows'ta yasak isaretler atilir", Y.proje_klasor_adi('Musteri: "Site"/v2?') == "Musteri- -Site-v2",
     Y.proje_klasor_adi('Musteri: "Site"/v2?'))
sina("bos ad -> 'Proje'", Y.proje_klasor_adi("  ") == "Proje")

print("\n5. acilista uyari")
from ofis.toparla import acilista_toparla  # noqa: E402
eski = Ofis(db, o.proje_id)
with db.baglanti() as c:
    c.execute("UPDATE proje SET kok_klasor = ? WHERE id = ?", (str(Y.OFIS_KODU / "calisma"), o.proje_id))
acilista_toparla(eski)
with db.baglanti() as c:
    u = c.execute("SELECT govde FROM olay WHERE tur = 'uyari' AND govde LIKE '%ofisin KENDI yerinde%'").fetchall()
sina("koku ofisin icinde kalmis proje SOYLENDI (tasima komutuyla)", len(u) == 1 and "kabuk tasi" in u[0]["govde"])
with db.baglanti() as c:
    c.execute("UPDATE proje SET kok_klasor = ? WHERE id = ?", (str(kok / "proje"), o.proje_id))
acilista_toparla(eski)
with db.baglanti() as c:
    n = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'uyari' AND govde LIKE '%ofisin KENDI yerinde%'").fetchone()[0]
sina("  disaridaki kokte uyari YOK", n == 1)

print("\n6. lider plani")
(kok / "proje").mkdir(exist_ok=True)
(kok / "proje" / "a.txt").write_text("x", encoding="utf-8")
from ofis.orkestra import Orkestra  # noqa: E402
ofis = Ofis(db, o.proje_id)
ofis.kadro.ise_al("demir", "lider", lider_mi=True, motor="sahte", klasor=str(kok / "proje"))
pm = Orkestra(ofis).plan_metni("bir rapor hazirla", None)
sina("plan: ajan adli klasor ACMA", "ajan adiyla klasor" in pm and "ACMA ve KULLANMA" in pm)
sina("plan: tek is is adli klasore", "ISININ ADIYLA" in pm or "isi ISININ ADIYLA" in pm)

print("\n7. ornek ofis")
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("ornek_ofis", Y.OFIS_KODU / "testler" / "ornek_ofis.py")
oo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oo)
odb = kok / "ornek.sqlite3"
oo.kur(odb)
ork = Ofis.proje_ac(Veritabani(odb), "Ornek Ofis")
sina("ornek ofisin koku ofisin DISINDA", not Y.ofis_icinde_mi(ork.kok_klasoru()), ork.kok_klasoru())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
