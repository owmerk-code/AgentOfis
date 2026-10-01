# -*- coding: utf-8 -*-
"""TAKILAN / BAYAT / IPTAL EDILEN IS duman testi (01.10.2026, #37 olayi).

Jeton yakmaz, sahte motorla. Gercek ofiste olculen uc hata:
  1. Patron #37'yi iptal etti; 9 sn sonra kosan tur dustu ve `tahta.birak`
     isi yeniden `hazir` yapti -- iptal sessizce geri alindi.
  2. #37 ayni hatayla 13 kez ~20 sn arayla yeniden kostu (durmayan dongu).
  3. #37 bir gun once acilmisti; patron "naber" yazinca cevap yolunun
     halkasi onu KENDILIGINDEN baslatti.
Sinanan: iptal/bitti ezilmez · 3 dususten sonra is bekletilir, patrona BIR
kez soylenir · Surdur ve not sayaci sifirlar · eski dusus sayilmaz · bayat
is halkada secilmez, sohbette bir kez hatirlatilir, Surdur'le kosar.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Orkestra
from ofis.sohbet import Sohbet
from ofis.motor.sahte import SahteMotor
from ofis import bildirim, takim

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== takilan / bayat / iptal is duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-takilma-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Takilma", amac="a", basari_olcutu="b",
                     kok_klasor=str(kok / "calisma"))
kanat = ofis.kanat_ac("GENEL", "GN")
for ad, meslek, lider_mi in (("demir", "lider", True), ("cinar", "backend", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi, tur="eller",
                      motor="sahte", klasor=str(kok / "calisma"))


def gorev(baslik, alan):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k",
                            govde="g", kanat_id=kanat, yazma_alani=alan)
    return ofis.tahta.gorev(g["no"])


def olaylar(g, tur):
    with db.baglanti() as c:
        return c.execute("SELECT govde FROM olay WHERE gorev_id = ? AND tur = ?",
                         (g["id"], tur)).fetchall()


def eskit(sql_tablo, saat, kosul, arg):
    eski = (datetime.now(timezone.utc) - timedelta(hours=saat)).isoformat(timespec="seconds")
    with db.baglanti() as c:
        c.execute(f"UPDATE {sql_tablo} SET {kosul[0]} = ? WHERE {kosul[1]}", (eski, *arg))


# ---------------------------------------------------------------------------
print("1. iptal / bitti `birak` ile EZILMEZ")
g1 = gorev("iptal edilecek", ["a/"])
ofis.tahta.sahiplen(g1["no"], "cinar", g1["revizyon"])
ofis.tahta.iptal_et(g1["no"], sebep="patron istemedi", iptal_eden="insan")
ofis.tahta.birak(g1["no"], sebep="tur basarisiz")          # kosan tur sonra duser
sina("iptal edilen is, tur dusunce IPTAL kalir", ofis.tahta.gorev(g1["no"])["durum"] == "iptal",
     ofis.tahta.gorev(g1["no"])["durum"])
g2 = gorev("bitmis is", ["b/"])
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (g2["id"],))
ofis.tahta.birak(g2["no"], sebep="x")
sina("bitmis is BITTI kalir", ofis.tahta.gorev(g2["no"])["durum"] == "bitti")
g3 = gorev("normal", ["c/"])
ofis.tahta.sahiplen(g3["no"], "cinar", g3["revizyon"])
ofis.tahta.birak(g3["no"], sebep="x")
sina("  calisan is birakilinca yine HAZIR olur (eski davranis)",
     ofis.tahta.gorev(g3["no"])["durum"] == "hazir" and not ofis.tahta.gorev(g3["no"])["sahip"])
with db.baglanti() as c:
    sina("  iptal edilenin kilidi yine de birakildi",
         c.execute("SELECT COUNT(*) FROM yazma_kilidi WHERE gorev_id = ?", (g1["id"],)).fetchone()[0] == 0)
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (g3["id"],))

# ---------------------------------------------------------------------------
print("\n2. ust uste dusen is BEKLETILIR")
ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(senaryo="hata"))
_iz = bildirim.Izleyici(ofis)          # dusus OLMADAN once kurulur
g4 = gorev("hep dusen is", ["d/"])
list(ork.kos(azami_tik=10, paralel=1))
_dusus = [r for r in olaylar(g4, "birakildi") if "tur basarisiz" in r["govde"]]
sina("10 tikte en fazla 3 kez denendi (eskiden her tikte)", 0 < len(_dusus) <= 2 * 3,
     f"{len(_dusus)} birakma")
_tak = olaylar(g4, "takildi")
sina("patrona BIR kez soylendi ('takildi')", len(_tak) == 1, str(len(_tak)))
sina("  mesaj bekleme suresini ve Surdur'u soyler",
     _tak and "30 dk" in _tak[0]["govde"] and "Sürdür" in _tak[0]["govde"])
sina("  takilma sohbet akisinda gorunur",
     any("üst üste" in (x.get("metin") or "") for x in takim.akis(ofis)))
sina("  takilma masaustu bildirimine girer",
     any("takıldı" in b for b, _ in _iz.topla()))
_once = len(_dusus)
list(ork.kos(azami_tik=5, paralel=1))
_sonra = len([r for r in olaylar(g4, "birakildi") if "tur basarisiz" in r["govde"]])
sina("bekleme suresince yeniden KOSMADI", _sonra == _once, f"{_once} -> {_sonra}")
sina("  ikinci kez soylenmedi", len(olaylar(g4, "takildi")) == 1)

print("\n3. Surdur / not sayaci sifirlar")
db.olay_yaz(ofis.proje_id, "surdur_istendi", "Patron Surdur'e basti", ajan_ad="insan")
sina("Surdur'den sonra takili DEGIL", not ork._takildi_mi(ofis.tahta.gorev(g4["no"])))
list(ork.kos(azami_tik=10, paralel=1))
_sonra2 = len([r for r in olaylar(g4, "birakildi") if "tur basarisiz" in r["govde"]])
sina("  Surdur'den sonra yeniden denendi", _sonra2 > _sonra, f"{_sonra} -> {_sonra2}")
sina("  yine 3 dususte durdu ve YENIDEN soylendi", len(olaylar(g4, "takildi")) == 2)
db.olay_yaz(ofis.proje_id, "not", "insan -> cinar: sunu dene", ajan_ad="cinar", gorev_id=g4["id"])
sina("o ise yazilan not da sayaci sifirlar", not ork._takildi_mi(ofis.tahta.gorev(g4["no"])))
db.olay_yaz(ofis.proje_id, "not", "baska ise not", ajan_ad="cinar", gorev_id=g1["id"])
for _ in range(3):
    db.olay_yaz(ofis.proje_id, "birakildi", f"#{g4['no']} birakildi. tur basarisiz", gorev_id=g4["id"])
sina("  BASKA ise yazilan not sifirlamaz", ork._takildi_mi(ofis.tahta.gorev(g4["no"])))
eskit("olay", 1, ("olusturuldu", "gorev_id = ? AND tur = 'birakildi'"), (g4["id"],))
sina("son dusus 30 dk'dan eskiyse bekleme biter", not ork._takildi_mi(ofis.tahta.gorev(g4["no"])))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (g4["id"],))
g5 = gorev("arada basarili", ["e/"])
for govde in ("tur basarisiz", "limit doldu", "tur basarisiz"):
    db.olay_yaz(ofis.proje_id, "birakildi", f"#{g5['no']} birakildi. {govde}", gorev_id=g5["id"])
sina("farkli sebepli birakma (limit) zinciri BOZAR", not ork._takildi_mi(ofis.tahta.gorev(g5["no"])))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (g5["id"],))

# ---------------------------------------------------------------------------
print("\n4. BAYAT is kendiliginden kosmaz")
# Bolum 3'teki Surdur'ler simdi; gercekte haftalar once basilmis olsun.
eskit("olay", 14, ("olusturuldu", "tur = 'surdur_istendi'"), ())
g6 = gorev("dunden kalan is", ["f/"])
eskit("gorev", 13, ("guncellendi", "id = ?"), (g6["id"],))
sina("13 saattir dokunulmamis hazir is BAYAT", ork.bayat_mi(ofis.tahta.gorev(g6["no"])))
g7 = gorev("yeni is", ["g/"])
sina("  yeni is bayat DEGIL", not ork.bayat_mi(ofis.tahta.gorev(g7["no"])))
_g8 = gorev("eski surdurlu", ["h/"])
eskit("gorev", 20, ("guncellendi", "id = ?"), (_g8["id"],))
db.olay_yaz(ofis.proje_id, "surdur_istendi", "x", ajan_ad="insan")
eskit("olay", 13, ("olusturuldu", "tur = 'surdur_istendi'"), ())
sina("  isten SONRA ama 13 saat once basilan Surdur bayatligi KALDIRMAZ",
     ork.bayat_mi(ofis.tahta.gorev(_g8["no"])))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (_g8["id"],))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (g7["id"],))


class _Cevapci(SahteMotor):
    """Triyajda 'cevap' der ('naber'); isci turunda kanit uretir."""

    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps(
                {"karar": "cevap", "gerekce": "selam", "cevap": "Iyiyim, sen?"}) + "\n```"
        else:
            self.cevap = "KANIT terminal: pytest -> 2 passed"
        return super().tur_kos(metin, **ayar)


s = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _Cevapci(cevap=""))
_o = list(s.konus("naber", azami_tik=3))
_tur = [x["tur"] for x in _o]
_cevap = next((x["govde"] for x in _o if x["tur"] == "cevap"), "")
sina("'naber' bayat isi BASLATMADI (halka donmedi)", "surduruluyor" not in _tur, str(_tur))
sina("  bayat is el degmeden HAZIR, sahipsiz",
     ofis.tahta.gorev(g6["no"])["durum"] == "hazir" and not ofis.tahta.gorev(g6["no"])["sahip"])
sina("  cevap bayat isi HATIRLATTI", f"#{g6['no']}" in _cevap and "Sürdür" in _cevap, _cevap)
_o2 = list(s.konus("naber", azami_tik=3))
_cevap2 = next((x["govde"] for x in _o2 if x["tur"] == "cevap"), "")
sina("  ikinci sohbette TEKRAR hatirlatmadi", f"#{g6['no']}" not in _cevap2, _cevap2)
list(Orkestra(ofis, motor_fabrikasi=lambda ad, **a: _Cevapci(cevap="")).kos(azami_tik=2, paralel=1))
sina("halka da bayat isi SECMEDI", ofis.tahta.gorev(g6["no"])["durum"] == "hazir"
     and not olaylar(ofis.tahta.gorev(g6["no"]), "sahiplendi"))
db.olay_yaz(ofis.proje_id, "surdur_istendi", "Patron Surdur'e basti", ajan_ad="insan")
sina("Surdur'den sonra bayat DEGIL", not ork.bayat_mi(ofis.tahta.gorev(g6["no"])))
list(Orkestra(ofis, motor_fabrikasi=lambda ad, **a: _Cevapci(cevap="")).kos(azami_tik=3, paralel=1))
sina("  Surdur'den sonra is KOSTU", ofis.tahta.gorev(g6["no"])["durum"] != "hazir"
     or len(ofis.tahta.kanitlar(g6["no"])) > 0, ofis.tahta.gorev(g6["no"])["durum"])

# ---------------------------------------------------------------------------
print("\n5. Surdur dugmesi ve kabuk devam olay yazar")
_p = Path(__file__).resolve().parent.parent / "ofis"
sina("panel api_devam 'surdur_istendi' yazar",
     "\"surdur_istendi\"" in (_p / "panel.py").read_text(encoding="utf-8"))
sina("kabuk devam 'surdur_istendi' yazar",
     "\"surdur_istendi\"" in (_p / "kabuk.py").read_text(encoding="utf-8"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
