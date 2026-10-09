# -*- coding: utf-8 -*-
"""COK TAKIM duman testi (01.10.2026).

Patron: *"sadece ofis diye bakma, birden fazla takim olacak, ofis sadece
tanim"*. Jeton yakmaz, sahte motorla. Iki takim (ANA: demir+cinar, WEB:
kaya+tuna) ve takimlar gelmeden acilmis eski isler. Sinanan:
  1. TEK KURAL `Orkestra.takimin_isi` (yazili takim · sahibin takimi · eski)
  2. liderin ozeti yalniz KENDI takimini gosterir, obur takimi tek satirla anar
  3. halka takim suzgeciyle yalniz o takimin isini ilerletir
  4. bir takima "naber" baska takimin isini BASLATMAZ
  5. bayat is hatirlatmasi yalniz kendi takiminin isini sayar
  6. plan: lider baska takimin ajanina is VEREMEZ
  7. takim sohbeti: ofisin ise bagli olayi (takildi) o isin takiminda gorunur
  8. suzgecsiz (tek takim / Surdur) davranis degismedi
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Orkestra, takim  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402
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


print("== cok takim duman testi ==\n")
_ANA = Path(tempfile.mkdtemp(prefix="ofis-cok-takim-"))
db = Veritabani(_ANA / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Ofisim", amac="a", basari_olcutu="b", kok_klasor=str(_ANA / "kok"))
(_ANA / "kok").mkdir()
ANA = ofis.kanat_ac("ANA", "AN")
WEB = ofis.kanat_ac("WEB", "WB")
for ad, meslek, lider, kn in (("demir", "lider", True, ANA), ("cinar", "backend", False, ANA),
                              ("kaya", "lider", True, WEB), ("tuna", "backend", False, WEB)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kn, lider_mi=lider, tur="eller", motor="sahte",
                      klasor=str(_ANA / "kok"))


def gorev(baslik, alan, kanat=None, sahip=None):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                            yazma_alani=alan, kanat_id=kanat, sahip=sahip or "")
    return ofis.tahta.gorev(g["no"])


def olay_var(g, tur):
    with db.baglanti() as c:
        return c.execute("SELECT 1 FROM olay WHERE gorev_id = ? AND tur = ?", (g["id"], tur)).fetchone()


ork = ofis.orkestra
a1 = gorev("ANA isi", ["ana/"], ANA)
w1 = gorev("WEB isi", ["web/"], WEB)
eski_c = gorev("eski is (cinar'in)", ["eski/"], None, "cinar")
eski_t = gorev("eski is (tuna'nin)", ["eski2/"], None, "tuna")
eski_0 = gorev("eski sahipsiz is", ["eski3/"], None, None)
with db.baglanti() as c:                      # takimlar gelmeden acilmis gibi
    c.execute("UPDATE gorev SET kanat_id = NULL WHERE id IN (?, ?, ?)",
              (eski_c["id"], eski_t["id"], eski_0["id"]))
eski_c, eski_t, eski_0 = (ofis.tahta.gorev(g["no"]) for g in (eski_c, eski_t, eski_0))

# ---------------------------------------------------------------------------
print("1. tek kural: is hangi takimin")
sina("takimi yazili is o takimin", ork.takimin_isi(a1, ANA) and not ork.takimin_isi(a1, WEB))
sina("takimsiz eski is SAHIBININ takiminin", ork.takimin_isi(eski_c, ANA)
     and not ork.takimin_isi(eski_c, WEB) and ork.takimin_isi(eski_t, WEB))
sina("sahipsiz eski is her takimda gorunur", ork.takimin_isi(eski_0, ANA) and ork.takimin_isi(eski_0, WEB))
sina("suzgec yoksa her is", ork.takimin_isi(w1, None))

# ---------------------------------------------------------------------------
print("\n2. liderin ozeti yalniz kendi takimi")
w_iptal = gorev("WEB'in iptal isi", ["webx/"], WEB)
ofis.tahta.iptal_et(w_iptal["no"], sebep="x", iptal_eden="insan")
ozA = ofis.sohbet.ofis_ozeti(ANA)
sina("ANA ozetinde cinar var, tuna YOK", "**cinar**" in ozA and "**tuna**" not in ozA)
sina("ANA ozetinde kendi isi var, WEB isi YOK", f"#{a1['no']} " in ozA and f"#{w1['no']} " not in ozA, ozA)
sina("  WEB'in iptal isi ANA'nin 'son isler'inde YOK", f"#{w_iptal['no']} IPTAL" not in ozA)
sina("  obur takim tek satirla aniliyor ve 'SENIN DEGIL' deniyor",
     "Obur takimlar" in ozA and "SENIN DEGIL" in ozA and "- WEB:" in ozA, ozA[-300:])
ozT = ofis.sohbet.ofis_ozeti()
sina("suzgecsiz ozet (tek takim gibi) her seyi gosterir, 'obur takimlar' YOK",
     f"#{w1['no']} " in ozT and "**tuna**" in ozT and "Obur takimlar" not in ozT)
tri = ofis.sohbet.triyaj_metni("naber", kanat_id=WEB)
sina("triyaj metni liderin takiminin ozetini tasir", "**tuna**" in tri and "**cinar**" not in tri)

# ---------------------------------------------------------------------------
print("\n3. halka takim suzgeciyle")
ork_s = Orkestra(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(cevap="KANIT terminal: x -> ok"))
list(ork_s.kos(azami_tik=2, paralel=2, kanat_id=ANA))
sina("ANA halkasi WEB isine DOKUNMADI", ofis.tahta.gorev(w1["no"])["durum"] == "hazir"
     and not olay_var(w1, "sahiplenildi"), ofis.tahta.gorev(w1["no"])["durum"])
sina("  tuna'nin eski isine de dokunmadi", not olay_var(eski_t, "sahiplenildi"))
sina("  ANA isi ilerledi", olay_var(a1, "sahiplenildi") is not None)

# ---------------------------------------------------------------------------
print("\n4. bir takima 'naber' obur takimin isini baslatmaz")


class _Cevapci(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps(
                {"karar": "cevap", "gerekce": "selam", "cevap": "Iyiyim."}) + "\n```"
        else:
            self.cevap = "KANIT terminal: x -> ok"
        return super().tur_kos(metin, **ayar)


with db.baglanti() as c:                      # ANA'da acik is kalmasin
    c.execute("UPDATE gorev SET durum = 'iptal', sahip = '' WHERE id IN (?, ?, ?)",
              (a1["id"], eski_c["id"], eski_0["id"]))
    c.execute("DELETE FROM yazma_kilidi")
s = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _Cevapci(cevap=""))
_o = list(s.konus("naber", lider_ad="demir", azami_tik=3))
_t = [x["tur"] for x in _o]
sina("demir'e 'naber': halka DONMEDI (ANA'nin isi yok)", "surduruluyor" not in _t, str(_t))
sina("  WEB isi hala el degmemis", ofis.tahta.gorev(w1["no"])["durum"] == "hazir"
     and not olay_var(w1, "sahiplenildi"))
_o2 = list(s.konus("naber", lider_ad="kaya", azami_tik=3))
sina("kaya'ya 'naber': KENDI takiminin acik isi icin halka doner",
     "surduruluyor" in [x["tur"] for x in _o2], str([x["tur"] for x in _o2]))

# ---------------------------------------------------------------------------
print("\n5. bayat is hatirlatmasi kendi takimi")
w_bayat = gorev("WEB'in dunden kalan isi", ["webb/"], WEB)
eski = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat(timespec="seconds")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET guncellendi = ? WHERE id = ?", (eski, w_bayat["id"]))
_cA = next((x["govde"] for x in s.konus("selam", lider_ad="demir", azami_tik=2) if x["tur"] == "cevap"), "")
sina("demir'in cevabi WEB'in bayat isini ANMIYOR", f"#{w_bayat['no']}" not in _cA, _cA)
_cW = next((x["govde"] for x in s.konus("selam", lider_ad="kaya", azami_tik=2) if x["tur"] == "cevap"), "")
sina("  kaya'nin cevabi kendi bayat isini aniyor (bir kez)", f"#{w_bayat['no']}" in _cW, _cW)

# ---------------------------------------------------------------------------
print("\n6. plan: lider baska takima is veremez")


def plan(sahip):
    return {"gerekce": "tek kol", "kollar": [{"baslik": "x", "neden": "n", "kabul_olcutu": "k",
                                               "sahip": sahip, "yazma_alani": ["isx/"]}]}


_r = ork._plani_dogrula(plan("tuna"), ANA, patron_sozu="x")
sina("demir'in plani tuna'ya (WEB) is VEREMEZ", "takiminda degil" in _r, _r)
sina("  kendi takimindan cinar'a verebilir", ork._plani_dogrula(plan("cinar"), ANA, patron_sozu="x") == "")
sina("  takim verilmemis eski cagri (kanat None) eskisi gibi", ork._plani_dogrula(plan("tuna"), None,
                                                                                   patron_sozu="x") == "")

# 09.10 (F1 canli): plan kapisi yazma alanini VARSAYILAN koke gore olcuyordu
# (takimin klasoru degil) ve 'yazma alani yok' uyarisini gorev_ac ile IKI kez yaziyordu.
_d4 = Path(tempfile.mkdtemp(prefix="ofis-cok-takim-alan-"))
(_d4 / "anakok").mkdir()
(_d4 / "webkok" / "sadece_web").mkdir(parents=True)
(_d4 / "sadece_web").mkdir()           # ayni ad ANA kokun DISINDA da var -> eski kod 'disarida' der
_o4 = Ofis.proje_ac(Veritabani(_d4 / "o.sqlite3"), "Alan", amac="a", basari_olcutu="b", kok_klasor=str(_d4 / "anakok"))
_a4 = _o4.kanat_ac("ANA", "AN")
_w4 = _o4.kanat_ac("WEB", "WB")
_o4.takim_klasoru_ayarla(_w4, str(_d4 / "webkok"))
_o4.kadro.ise_al("lena", "lider", kanat_id=_w4, lider_mi=True, motor="sahte", klasor=str(_d4 / "webkok"))
_o4.kadro.ise_al("rus", "backend", kanat_id=_w4, motor="sahte", klasor=str(_d4 / "webkok"))
_ork4 = _o4.orkestra


def plan4(alan):
    return {"gerekce": "tek kol", "kollar": [{"baslik": "x", "neden": "n", "kabul_olcutu": "k",
                                               "sahip": "rus", "yazma_alani": [alan]}]}


_r4 = _ork4._plani_dogrula(plan4("sadece_web/a.md"), _w4, patron_sozu="x")
sina("plan kapisi TAKIMIN kokune gore olcer (WEB kokundeki klasor gecer)", _r4 == "", _r4)


def _uyari_say():
    with _o4.db.baglanti() as c:
        return c.execute("SELECT COUNT(*) FROM olay WHERE tur='uyari' AND govde LIKE '%yeni_klasor%'").fetchone()[0]


sina("  plan kapisi 'alan yok' uyarisini YAZMAZ", _ork4._plani_dogrula(plan4("yeni_klasor/a/b.md"), _w4, patron_sozu="x") == ""
     and _uyari_say() == 0, str(_uyari_say()))
_o4.tahta.gorev_ac("y", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=_w4, yazma_alani=["yeni_klasor/a/b.md"])
sina("  gorev_ac uyariyi TEK kez yazar", _uyari_say() == 1, str(_uyari_say()))

# ---------------------------------------------------------------------------
print("\n7. takim sohbeti: ofisin ise bagli olayi o takimda")
db.olay_yaz(ofis.proje_id, "takildi", f"#{w1['no']} ust uste 3 kez dustu", ajan_ad="ofis", gorev_id=w1["id"])
db.olay_yaz(ofis.proje_id, "kesinti_toparlandi", "ofis kaldigi yerden suruyor", ajan_ad="ofis")
akA = [x["metin"] for x in takim.akis(ofis, kanat_id=ANA)]
akW = [x["metin"] for x in takim.akis(ofis, kanat_id=WEB)]
sina("WEB isinin takilmasi WEB sohbetinde gorunur (eskiden HIC gorunmuyordu)",
     any("ust uste 3" in m for m in akW))
sina("  ANA sohbetinde GORUNMEZ", not any("ust uste 3" in m for m in akA))
sina("  ise bagli olmayan ofis olayi iki takimda da gorunur",
     any("kaldigi yerden" in m for m in akA) and any("kaldigi yerden" in m for m in akW))
sina("  'Tum ofis' gorunumu hepsini gosterir", any("ust uste 3" in x["metin"] for x in takim.akis(ofis)))

# ---------------------------------------------------------------------------
print("\n8. suzgecsiz halka (Surdur) butun ofisi yurutur")
_son8 = list(ork_s.kos(azami_tik=2, paralel=3))
_incelenen = [x["no"] for a in _son8 for x in a.get("incelenen", [])]
sina("suzgecsiz halka WEB isini de ele aldi (incelemeye soktu)", w1["no"] in _incelenen,
     str(_incelenen))
sina("  halka hatasiz SONA ERDI (lideri bulunamayan is halkayi dusurmez)",
     any(x.get("bitti") for x in _son8), str(_son8[-1:]))

# ---------------------------------------------------------------------------
print("\n9. bir isin lideri (TEK KURAL: kadro.gorevin_lideri)")
from ofis.kadro import KadroHatasi  # noqa: E402
kd = ofis.kadro
sina("takimi yazili is -> o takimin lideri", kd.gorevin_lideri(w1)["ad"] == "kaya")
sina("takimsiz eski is -> SAHIBININ takiminin lideri (eskiden 'lideri yok' hatasi)",
     kd.gorevin_lideri(eski_c)["ad"] == "demir" and kd.gorevin_lideri(eski_t)["ad"] == "kaya")
try:
    kd.gorevin_lideri(eski_0)
    sina("sahipsiz eski is + iki lider -> ACIK hata", False, "hata vermedi")
except KadroHatasi as exc:
    sina("sahipsiz eski is + iki lider -> ACIK hata (tahmin yok)", "belirsiz" in str(exc), str(exc))
# Tek liderli ofis (patronun bugunku ofisi): takimsiz sahipsiz is o lidere.
_d2 = Path(tempfile.mkdtemp(prefix="ofis-tek-lider-"))
_db2 = Veritabani(_d2 / "o.sqlite3")
_o2 = Ofis.proje_ac(_db2, "Tek", amac="a", basari_olcutu="b", kok_klasor=str(_d2))
_k2 = _o2.kanat_ac("ANA", "AN")
_o2.kadro.ise_al("demir", "lider", kanat_id=_k2, lider_mi=True, motor="sahte", klasor=str(_d2))
sina("tek liderli ofiste takimsiz sahipsiz is -> o lider (eskiden 'lideri yok')",
     _o2.kadro.gorevin_lideri({"no": 1, "kanat_id": None, "sahip": ""})["ad"] == "demir")
_src = (Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py").read_text(encoding="utf-8")
sina("ajanin lidere sorusu ayni kurali kullanir (eski iste soru sessizce patrona gitmez)",
     "gorevin_lideri(g or {})" in _src)

# ---------------------------------------------------------------------------
print("\n10. takimsiz is ACILMAZ, eski takimsiz is takim alir, ajan takimdan secilir")
_y1 = ofis.tahta.gorev_ac("tuna'ya is", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                          yazma_alani=["y1/"], sahip="tuna")
sina("takimsiz acilan is SAHIBININ takimini alir", ofis.tahta.gorev(_y1["no"])["kanat_id"] == WEB)
_y2 = ofis.tahta.gorev_ac("sahipsiz", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                          yazma_alani=["y2/"])
sina("  iki liderli ofiste sahipsiz is takimsiz kalir (tahmin yok)",
     ofis.tahta.gorev(_y2["no"])["kanat_id"] is None)
_y3 = _o2.tahta.gorev_ac("tek takim", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                         yazma_alani=["y3/"])
sina("  tek liderli ofiste sahipsiz is o takimi alir", _o2.tahta.gorev(_y3["no"])["kanat_id"] == _k2)
# Ajan secimi: takimsiz eski is, sahibi mesgulken BASKA TAKIMIN ajanina gitmez.
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE durum IN ('hazir', 'calisiyor', 'inceleme')")
    c.execute("DELETE FROM yazma_kilidi")
_ey = gorev("eski is, sahibi cinar", ["ey/"], ANA, "cinar")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET kanat_id = NULL WHERE id = ?", (_ey["id"],))
_ey = ofis.tahta.gorev(_ey["no"])
_secilen = ork._uygun_ajan(_ey, rezerve={"cinar"})
sina("sahibi mesgulken takimsiz eski is WEB'in tuna'sina VERILMEZ (olculen hata)",
     _secilen != "tuna", repr(_secilen))
# Veri gocu: eski defter.
from ofis import db as _dbmod  # noqa: E402
_d3 = Path(tempfile.mkdtemp(prefix="ofis-goc-"))
_db3 = Veritabani(_d3 / "g.sqlite3")
_o3 = Ofis.proje_ac(_db3, "Goc", amac="a", basari_olcutu="b", kok_klasor=str(_d3))
_k3 = _o3.kanat_ac("ANA", "AN")
_kbos = _o3.kanat_ac("BOS", "BS")              # lidersiz ikinci takim (patronun HACKTOOL'u gibi)
_o3.kadro.ise_al("ayaz", "backend", kanat_id=_kbos, motor="sahte", klasor=str(_d3))
_o3.kadro.ise_al("demir", "lider", kanat_id=_k3, lider_mi=True, motor="sahte", klasor=str(_d3))
_o3.kadro.ise_al("cinar", "backend", kanat_id=_k3, motor="sahte", klasor=str(_d3))
_ga = _o3.tahta.gorev_ac("a", neden="n", ana_hedef="h", kabul_olcutu="k", yazma_alani=["a/"], sahip="cinar")
_gb = _o3.tahta.gorev_ac("b", neden="n", ana_hedef="h", kabul_olcutu="k", yazma_alani=["b/"])
with _db3.baglanti() as c:
    c.execute("UPDATE gorev SET kanat_id = NULL")
    c.execute("PRAGMA user_version = 1")
_db3b = Veritabani(_d3 / "g.sqlite3")             # yeniden acilis gocu kosar
with _db3b.baglanti() as c:
    _k = dict(c.execute("SELECT no, kanat_id FROM gorev").fetchall())
    _uv = c.execute("PRAGMA user_version").fetchone()[0]
sina("veri gocu: sahipli eski is sahibinin takimini aldi", _k[_ga["no"]] == _k3, str(_k))
sina("  sahipsiz eski is LIDERLI tek takimi aldi (lidersiz takim sayilmadi)", _k[_gb["no"]] == _k3)
sina("  goc surumu 2", _uv >= 2, str(_uv))

# ---------------------------------------------------------------------------
print("\n11. lidere giden triyaj metni KENDI takimi; lideri bulunamayan is halkayi dusurmez")
_giden = []


class _Izleyen(_Cevapci):
    def tur_kos(self, metin, **ayar):
        _giden.append(metin)
        return super().tur_kos(metin, **ayar)


list(Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _Izleyen(cevap="")).konus("naber", lider_ad="demir",
                                                                           azami_tik=1))
_tri = next((m for m in _giden if "# PATRONUN MESAJI" in m), "")
sina("demir'e giden GERCEK triyaj metni tuna'yi (WEB) gostermiyor", _tri and "**tuna**" not in _tri
     and "**cinar**" in _tri, _tri[:200])
# Takimsiz, sahipsiz is incelemede + iki lider: lideri belirsiz.
_bel = gorev("lideri belirsiz is", ["bel/"], ANA, "cinar")
ofis.tahta.kanit_ekle(_bel["no"], "terminal", "x", "x -> ok", ekleyen="cinar")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET kanat_id = NULL, sahip = '', durum = 'inceleme' WHERE id = ?", (_bel["id"],))
try:
    _s11 = list(ork_s.kos(azami_tik=1, paralel=1))
    _engel = [e for x in _s11 for e in x.get("engel", [])]
    sina("lideri belirsiz is halkayi DUSURMEDI, 'engel' olarak soylendi",
         any(f"#{_bel['no']}" in e and "belirsiz" in e for e in _engel), str(_engel))
except Exception as exc:                          # noqa: BLE001
    sina("lideri belirsiz is halkayi DUSURMEDI, 'engel' olarak soylendi", False, repr(exc))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
