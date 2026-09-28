# -*- coding: utf-8 -*-
"""F3 GUVENLIK duman testi -- jeton yakmadan.

1. ANAHTAR MASKELEME (E23): deftere yazan HER yol (olay, kanit, mesaj,
   cevap, degisim yamasi, koltuktan gelen ajan ciktisi) anahtari
   "[GIZLI: AD]" olarak yazar. Kapi baglantinin kendisinde; her yol ayri
   ayri sinanir ki kapi bir yola ulasmiyorsa gorulsun.

Kasa GECICI dosyadir (OFIS_GIZLI_YOLU): kullanicinin gercek kasasi bir
sinamanin sonucunu degistirmez, gercek anahtar da hicbir yere basilmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_KOK = Path(tempfile.mkdtemp(prefix="ofis-guv-"))
os.environ["OFIS_GIZLI_YOLU"] = str(_KOK / "kasa.env")

from ofis import Ofis, Veritabani, gizli          # noqa: E402
from ofis.motor.sahte import SahteMotor            # noqa: E402

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


DEGER = "kasadaki-gercek-deger-" + "x7Q9" * 4
gizli.ekle("DENEME_API_KEY", DEGER)
BICIM = "sk-ant-api03-" + "A1b2C3d4" * 4          # kasada YOK, bicimden yakalanir

print("\n-- 1. maskele() --")
m = gizli.maskele(f"once {DEGER} sonra")
sina("kasa degeri AD ile degisir", m == "once [GIZLI: DENEME_API_KEY] sonra", m)
m = gizli.maskele(f"cli dedi ki: key={BICIM} gecersiz")
sina("kasada olmayan bilinen BICIM de maskelenir", BICIM not in m and "[GIZLI: anahtar]" in m, m)
for ornek in ("ghp_" + "a" * 36, "AIza" + "B" * 35, "github_pat_" + "c" * 40):
    sina(f"bicim yakalanir: {ornek[:8]}...", ornek not in gizli.maskele("x " + ornek + " y"))
sina("sinama uydurmasi (AIza-SINAMA) yakalanmaz", "AIza-SINAMA-deneme" in
     gizli.maskele("ornek AIza-SINAMA-deneme-anahtari burada"))
sina("kisa deger dokunulmaz", gizli.maskele("kisa metin") == "kisa metin")
sina("metin olmayan deger aynen doner", gizli.maskele(12345) == 12345 and gizli.maskele(None) is None)
os.environ["BIR_SERVIS_TOKEN"] = "ortamdaki-token-" + "z" * 16
m = gizli.maskele("token ortamdaki-token-" + "z" * 16 + " sizdi")
sina("ortamdaki *_TOKEN degeri de maskelenir", "[GIZLI: BIR_SERVIS_TOKEN]" in m, m)
gizli.ekle("YENI_KEY", "sonradan-eklenen-deger-12345")
sina("kasaya sonradan eklenen deger hemen maskelenir (onbellek bayatlamaz)",
     "[GIZLI: YENI_KEY]" in gizli.maskele("x sonradan-eklenen-deger-12345 y"))

print("\n-- 2. deftere yazan HER yol --")
db = Veritabani(_KOK / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Guv", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
k = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=k, motor="sahte", klasor=str(_KOK))
ofis.kadro.ise_al("isci", "backend", kanat_id=k, motor="sahte", klasor=str(_KOK))
ofis.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k",
                    yazma_alani=["alan/"], kanat_id=k)


def defterde_var(deger: str) -> list:
    """Defterin HER tablosunda, her metin sutununda arar."""
    bulunan = []
    with db.baglanti() as c:
        for (tablo,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            for r in c.execute(f"SELECT * FROM {tablo}"):
                if any(isinstance(v, str) and deger in v for v in tuple(r)):
                    bulunan.append(tablo)
                    break
    return bulunan


db.olay_yaz(ofis.proje_id, "cikti", f"cikti: {DEGER}")
ofis.tahta.kanit_ekle(1, "terminal", "baslik " + BICIM, f"icerik {DEGER}", ekleyen="isci")
sid = ofis.postane.soru_sor("isci", "insan", f"bu anahtar dogru mu: {DEGER}")
mid = sid["id"] if isinstance(sid, dict) else sid
ofis.postane.cevapla(mid, f"evet, {BICIM} de var")                     # UPDATE yolu
sina("olay / kanit / soru / cevap: defterde DEGER yok", not defterde_var(DEGER),
     str(defterde_var(DEGER)))
sina("olay / kanit / soru / cevap: defterde BICIM yok", not defterde_var(BICIM),
     str(defterde_var(BICIM)))
with db.baglanti() as c:
    kanit = c.execute("SELECT icerik FROM kanit").fetchone()[0]
sina("kanit AD'la okunur (ne sizdigi bilinir)", "[GIZLI: DENEME_API_KEY]" in kanit, kanit)

print("\n-- 3. koltuk: ajanin ciktisi ve disk farki --")
(_KOK / "alan").mkdir(exist_ok=True)


class SizanMotor(SahteMotor):
    """Ciktisinda anahtar basan VE diske anahtarli dosya yazan ajan."""

    def tur_kos(self, metin, **kw):
        (_KOK / "alan" / ".env").write_text(f"API_KEY={DEGER}\n", encoding="utf-8")
        yield from super().tur_kos(metin, **kw)


from ofis.koltuk import Koltuk   # noqa: E402
koltuk = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SizanMotor(
    cevap=f"Buldum: {DEGER} ve {BICIM}\nKANIT terminal: kos -> gecti"))
koltuk.kos(1, "isci")
sina("koltuk sonrasi: defterin HICBIR tablosunda DEGER yok", not defterde_var(DEGER),
     str(defterde_var(DEGER)))
sina("koltuk sonrasi: defterin HICBIR tablosunda BICIM yok", not defterde_var(BICIM),
     str(defterde_var(BICIM)))
with db.baglanti() as c:
    yama = [r[0] for r in c.execute("SELECT yama FROM degisim WHERE yol LIKE '%.env'")]
sina("disk farki (.env yamasi) olculdu ve maskeli",
     bool(yama) and all(DEGER not in (y or "") for y in yama) and
     any("[GIZLI: DENEME_API_KEY]" in (y or "") for y in yama), str(yama)[:200])
sina("okuma dokunulmaz: dosyanin kendisi diskte ayni (maske yalniz defterde)",
     DEGER in (_KOK / "alan" / ".env").read_text(encoding="utf-8"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
