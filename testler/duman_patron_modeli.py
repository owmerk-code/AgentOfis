# -*- coding: utf-8 -*-
"""FABLE/ASTRA YALNIZ PATRONUN SOZUYLE (08.10.2026). Jeton yakmaz.

Patron: "fable ve astra sadece ben eklersem, istersem veya lidere soylersem
calisabilir; onun disinda agent sisteminde pek kullanmaya gerek yok".
Sinanan: lider bir kola fable/astra ancak patronun mesajindan modeli ANAN
kelimesi kelimesine alintiyla yazabilir; olumsuz cumle, uydurma alinti, kapi
disi model, listede olmayan model REDDEDILIR; gecen model ise yazilir ve is
O modelle (dogru motorda) kosar; patron demediyse ajanin kendi modeli kalir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, guncelleme, izin as IZ  # noqa: E402
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


print("1. kural (izin.plan_modeli)")
SOZ = "Raporu hazirla, bu isi fable ile yap. Kucuk duzeltmeyi normal yapin."
pm, h = IZ.plan_modeli({"baslik": "x"}, SOZ)
sina("model yoksa hicbir sey yok", pm is None and not h)
pm, h = IZ.plan_modeli({"model": "fable", "model_alinti": "bu isi fable ile yap"}, SOZ)
sina("alintili fable GECER (claude motoru)", pm and pm["motor"] == "claude" and not h, f"{pm} {h}")
for kol, neden in (
        ({"model": "opus", "model_alinti": "fable ile yap"}, "alinti baska modeli aniyor"),
        ({"model": "fable", "model_alinti": "fable ile hemen yap"}, "mesajda gecmeyen alinti"),
        ({"model": "fable", "model_alinti": "raporu hazirla"}, "alinti modeli anmiyor"),
        ({"model": "fable"}, "alintisiz"),
        ({"model": "astra", "model_alinti": "fable ile yap"}, "baska modelin alintisi")):
    pm, h = IZ.plan_modeli(kol, SOZ)
    sina(f"reddedildi: {neden}", pm is None and bool(h), str(h))
pm, h = IZ.plan_modeli({"model": "fable", "model_alinti": "fable"}, "Raporu yaz")
sina("patron sozu fable icermiyorsa reddedildi", pm is None and h)
for soz in ("Bu isi yap ama fable kullanma.", "Raporu yaz, astra olmasin.",
            "Fable istemiyorum, sonnet yeter.", "fable ile yapma"):
    ad = "astra" if "astra" in soz else "fable"
    pm, h = IZ.plan_modeli({"model": ad, "model_alinti": ad}, soz)
    sina(f"olumsuz cumle reddedildi: {soz}", pm is None and h, str(pm))
pm, h = IZ.plan_modeli({"model": "astra", "model_alinti": "astra ile calissin"},
                       "Bu analiz astra ile calissin.")
sina("astra codex motorunda", pm and pm["motor"] == "codex", str(pm))

print("\n2. gercek kimlik motorun listesinden")
_asil = guncelleme.model_listesi
guncelleme.model_listesi = lambda db, pid: {
    "claude": [{"id": "sonnet"}, {"id": "fable"}], "codex": [{"id": "gpt-6.1-sol"}, {"id": "gpt-6-astra"}],
    "gemini": []}
d = Path(tempfile.mkdtemp(prefix="ofis-pmodel-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "PModel", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "dokuman", kanat_id=KA, motor="claude", model="sonnet", klasor=str(d))
pm, h = IZ.plan_modeli({"model": "astra", "model_alinti": "astra ile calissin"},
                       "Bu analiz astra ile calissin.", db, ofis.proje_id)
sina("astra -> listedeki gercek kimlik gpt-6-astra", pm and pm["model"] == "gpt-6-astra", str(pm))
guncelleme.model_listesi = lambda db, pid: {"claude": [{"id": "sonnet"}], "codex": [], "gemini": []}
pm, h = IZ.plan_modeli({"model": "fable", "model_alinti": "fable ile yap"}, SOZ, db, ofis.proje_id)
sina("listede yoksa UYDURULMAZ, reddedilir", pm is None and "listesinde yok" in h, str(h))
guncelleme.model_listesi = lambda db, pid: {
    "claude": [{"id": "opus"}, {"id": "sonnet"}, {"id": "fable"}],
    "codex": [{"id": "gpt-6.1-sol"}, {"id": "gpt-6-astra"}],
    "gemini": [{"id": "gemini-3.8-flash-high"}]}
# Patron (08.10): "su isi su ajana su modelle yaptir" -- her model, yalniz onun sozuyle.
for soz, kol, beklenen in (
        ("Bu isi opus ile yap.", {"model": "opus", "model_alinti": "opus ile yap"}, "claude/opus"),
        ("Testleri sol modeline yaptir.", {"model": "gpt-6.1-sol", "model_alinti": "sol modeline yaptir"},
         "codex/gpt-6.1-sol"),
        ("Arastirmayi gemini flash yapsin.", {"model": "gemini-3.8-flash-high",
                                             "model_alinti": "gemini flash yapsin"},
         "gemini/gemini-3.8-flash-high")):
    pm, h = IZ.plan_modeli(kol, soz, db, ofis.proje_id)
    sina(f"patronun dedigi model GECER: {beklenen}", pm and f"{pm['motor']}/{pm['model']}" == beklenen,
         f"{pm} {h}")
pm, h = IZ.plan_modeli({"model": "opus", "model_alinti": "bu isi yap"}, "Bu isi yap.", db, ofis.proje_id)
sina("patron model demediyse opus da REDDEDILIR", pm is None and h, str(pm))
pm, h = IZ.plan_modeli({"model": "gpt-9-hayal", "model_alinti": "hayal ile"}, "hayal ile yap", db, ofis.proje_id)
sina("listede olmayan model reddedilir", pm is None and "listesinde yok" in h, str(h))
blok = IZ.plan_blogu(IZ.model_secenekleri(db, ofis.proje_id))
sina("lider tarifinde secilebilir modeller listesi", "gpt-6.1-sol" in blok and "fable" in blok, blok[-200:])

print("\n3. plan -> is -> koltuk")


def plan(model=None, alinti=None):
    kol = {"baslik": "Rapor", "sahip": "ece", "neden": "patron istedi",
           "kabul_olcutu": "rapor.md var", "govde": "raporu yaz", "yazma_alani": [],
           "zorluk": "orta"}
    if model:
        kol.update(model=model, model_alinti=alinti)
    return {"bol": False, "gerekce": "tek is", "kollar": [kol]}


r = ofis.orkestra.hedef_ver("Rapor", kanat_id=KA, patron_sozu=SOZ,
                            hazir_plan=plan("fable", "bu isi fable ile yap"))
g = r["gorevler"][0]
sina("iste patronun modeli yazili", g.get("patron_modeli") == "claude/fable", str(g.get("patron_modeli")))
with db.baglanti() as c:
    ol = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'patron_modeli'")]
sina("kayit patronun alintisini tasiyor", ol and "bu isi fable ile yap" in ol[0], str(ol))


class _Kaydeden(SahteMotor):
    son: dict = {}

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar, motor=self._ad)
        yield from super().tur_kos(metin, **ayar)


def fabrika(ad, **kw):
    m = _Kaydeden(cevap="Bitti.\nKANIT dosya: rapor.md -> var")
    m._ad = ad
    return m


Koltuk(ofis, motor_fabrikasi=fabrika).kos(g["no"], "ece")
sina("is FABLE ile kostu (ajanin sonnet'i degil)", _Kaydeden.son.get("model") == "fable",
     str(_Kaydeden.son.get("model")))
sina("  dogru motorda (claude)", _Kaydeden.son.get("motor") == "claude", str(_Kaydeden.son.get("motor")))
sina("  tavansiz (gercek terminale engel yok)", not _Kaydeden.son.get("butce_usd"))

r = ofis.orkestra.hedef_ver("Rapor 2", kanat_id=KA, patron_sozu="Raporu yaz.",
                            hazir_plan=plan())
g2 = r["gorevler"][0]
Koltuk(ofis, motor_fabrikasi=fabrika).kos(g2["no"], "ece")
sina("patron demediyse ajanin KENDI modeli (sonnet)", _Kaydeden.son.get("model") == "sonnet"
     and not g2.get("patron_modeli"), f"{_Kaydeden.son.get('model')} {g2.get('patron_modeli')}")

with db.baglanti() as c:
    once = c.execute("SELECT COUNT(*) FROM gorev").fetchone()[0]
try:
    ofis.orkestra.hedef_ver("Rapor 3", kanat_id=KA, patron_sozu="Raporu yaz, fable kullanma.",
                            hazir_plan=plan("fable", "fable kullanma"), deneme=1)
except Exception:                                 # noqa: BLE001 -- sahte lider plan veremez
    pass
with db.baglanti() as c:
    ret = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'uyari' AND govde LIKE '%olumsuz%'")]
    fable_is = c.execute("SELECT COUNT(*) FROM gorev WHERE patron_modeli LIKE '%fable%'").fetchone()[0]
sina("'fable kullanma' dendiginde lider plani REDDEDILDI (ret ogretir)", bool(ret), str(ret))
sina("  fable'la acilan yeni is YOK", fable_is == 1, str(fable_is))

print("\n4. lider tarifi")
sina("plan tarifinde ISIN MODELI bolumu var", "ISIN MODELI" in IZ.plan_blogu()
     and "kendiliginden KULLANMAZ" in IZ.plan_blogu())
guncelleme.model_listesi = _asil

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
