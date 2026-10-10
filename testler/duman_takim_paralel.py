# -*- coding: utf-8 -*-
"""TAKIMLAR PARALEL (10.10.2026, F1 canli olculdu): sira TEK seritti; GENEL'in
isi kosarken OFIS GELISTIRME'nin istegi 4 dk bekledi, sonra GENEL'in
incelemesi oteki takimin turunu bekledi. Simdi takim basina serit.

Sinanan (jeton yakmaz; lider turu sahte):
  1. iki takimin istegi AYNI ANDA kosar; ayni takiminki SIRAYLA
  2. takim seridi yalniz KENDI takiminin yeni istegine yol verir (ara_ver)
  3. kesintiden devam (butun ofisin halkasi) TEK BASINA kosar
  4. Durdur butun seritleri durdurur; ofis SON serit bitince bosalir
  5. kabin ofis genelinde TEK kiraci (iki takimin halkasi ayni kabini iki ise veremez)
  6. danisma: ayni bekleyen soru iki halkada BIR KEZ cevaplanir
"""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
import threading
import time as _t
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani  # noqa: E402
from ofis import kuyruk as K  # noqa: E402
from ofis import orkestra as _O  # noqa: E402
import ofis.panel as _P  # noqa: E402
import ofis.sohbet as _S  # noqa: E402
from ofis.danisma import Danisma  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


D = Path(tempfile.mkdtemp(prefix="ofis-takim-paralel-"))
db_yolu = D / "o.sqlite3"
PROJE = "Paralel"
ofis = Ofis.proje_ac(Veritabani(db_yolu), PROJE, amac="a", basari_olcutu="b", kok_klasor=str(D / "kok"))
A = ofis.kanat_ac("GENEL", "GN")
B = ofis.kanat_ac("GELISTIRME", "GL")
ofis.kadro.ise_al("arda", "lider", lider_mi=True, kanat_id=A, motor="sahte", klasor=str(D / "kok"))
ofis.kadro.ise_al("ada", "lider", lider_mi=True, kanat_id=B, motor="sahte", klasor=str(D / "kok"))
ofis.kadro.ise_al("ece", "backend", kanat_id=A, motor="sahte", klasor=str(D / "kok"))

ARALIK, ARA_VER = [], {}
_KILIT = threading.Lock()
_asil_konus = _S.Sohbet.konus


def _sahte_konus(self, mesaj, **kw):
    bas = _t.monotonic()
    ara = kw.get("ara_ver")
    if "DURDUR" in mesaj:
        _P._KOSU["dur"] = True
    _t.sleep(0.6)
    if ara is not None and mesaj not in ARA_VER:
        ARA_VER[mesaj] = ara()
    with _KILIT:
        ARALIK.append((mesaj, bas, _t.monotonic()))
    return iter(())


def _bekle(sn=20.0) -> bool:
    son = _t.time() + sn
    while _t.time() < son:
        if not _P._KOSU["calisiyor"]:
            _t.sleep(0.4)
            if not _P._KOSU["calisiyor"]:
                return True
        _t.sleep(0.05)
    return False


def _cakisir(a, b) -> bool:
    (_, a1, a2), (_, b1, b2) = a, b
    return a1 < b2 and b1 < a2


def _aralik(metin):
    return next(x for x in ARALIK if x[0] == metin)


_S.Sohbet.konus = _sahte_konus
_P.MOTOR_FABRIKASI = lambda ad, **kw: None
try:
    print("1. iki takim AYNI ANDA; ayni takim SIRAYLA")
    K.ekle(ofis, "A1", "arda")
    K.ekle(ofis, "A2", "arda")
    K.ekle(ofis, "B1", "ada")
    sina("seritler basladi", _P._kuyrugu_baslat(str(db_yolu), PROJE))
    sina("  iki takimin seridi ayni anda acik", len(_P._KOSU.get("takimlar", set())) == 2, str(_P._KOSU.get("takimlar", set())))
    sina("  ayni takim icin ikinci serit ACILMAZ", _P._kuyrugu_baslat(str(db_yolu), PROJE) is False)
    sina("  sira bosaldi, ofis bosaldi", _bekle() and not _P._KOSU.get("takimlar", set()))
    sina("  GENEL'in A1'i ile GELISTIRME'nin B1'i AYNI ANDA kostu (eskiden B1 A1'i beklerdi)",
         _cakisir(_aralik("A1"), _aralik("B1")), str(ARALIK))
    sina("  ayni takimin A1 ve A2'si CAKISMADI (sirayla)", not _cakisir(_aralik("A1"), _aralik("A2")))

    print("\n2. takim seridi yalniz KENDI takiminin istegine yol verir")
    sina("  A1 kosarken siradaki A2 (ayni takim) -> ara_ver EVET", ARA_VER.get("A1") is True, str(ARA_VER))
    sina("  B1 kosarken oteki takimin istegi ara_ver'i TETIKLEMEDI", ARA_VER.get("B1") is False, str(ARA_VER))

    print("\n3. kesintiden devam TEK BASINA")
    ARALIK.clear()
    _devam_kos, _asil_kos = [], _O.Orkestra.kos

    def _sahte_kos(self, **kw):
        bas = _t.monotonic()
        _t.sleep(0.6)
        with _KILIT:
            ARALIK.append(("DEVAM", bas, _t.monotonic()))
        _devam_kos.append(sorted(_P._KOSU.get("takimlar", set())))
        return iter(())

    _O.Orkestra.kos = _sahte_kos
    try:
        K.ekle(ofis, "A3", "arda")
        _dv = K.ekle(ofis, "devam", "arda")
        with ofis.db.baglanti() as c:
            c.execute("UPDATE kuyruk SET devam = 1 WHERE id = ?", (_dv["id"],))
        K.ekle(ofis, "B2", "ada")
        _P._kuyrugu_baslat(str(db_yolu), PROJE)
        sina("  devamdan ONCEKI A3 kosar, devam ve arkasindaki B2 BEKLER",
             _P._KOSU.get("takimlar", set()) == {A}, str(_P._KOSU.get("takimlar", set())))
        _bekle()
        sina("  devam ancak ofis bosken ve TEK BASINA kostu", _devam_kos == [["*"]], str(_devam_kos))
        sina("  devam hicbir seritle CAKISMADI",
             not any(_cakisir(_aralik("DEVAM"), x) for x in ARALIK if x[0] != "DEVAM"), str(ARALIK))
        sina("  arkasindaki B2 de kostu (asili kalmadi)", any(x[0] == "B2" for x in ARALIK))
    finally:
        _O.Orkestra.kos = _asil_kos

    print("\n4. Durdur butun seritleri durdurur")
    ARALIK.clear()
    K.ekle(ofis, "A DURDUR", "arda")
    K.ekle(ofis, "A5", "arda")
    K.ekle(ofis, "B5", "ada")
    K.ekle(ofis, "B6", "ada")
    _P._kuyrugu_baslat(str(db_yolu), PROJE)
    sina("  durdurulan seritler bitti, ofis bosaldi", _bekle())
    _kosan = {x[0] for x in ARALIK}
    sina("  kosan istekler bitti, yenisi baslamadi (A5 ve B6 BEKLIYOR)",
         "A5" not in _kosan and "B6" not in _kosan, str(_kosan))
    sina("  bekleyenler KORUNDU", {x["metin"] for x in K.bekleyenler(ofis)} >= {"A5", "B6"})
    for x in K.bekleyenler(ofis):
        K.iptal(ofis, x["id"])

    print("\n5. kabin ofis genelinde TEK kiraci")
    sina("kabin bos, #1 kiralar", _O.kabin_kirala(1) and _O.kabin_kiracisi() == 1)
    sina("  #2 (baska takim) kiralayamaz", _O.kabin_kirala(2) is False)
    _O.kabin_birak(2)
    sina("  kiraci olmayan birakamaz", _O.kabin_kiracisi() == 1)
    _O.kabin_birak(1)
    sina("  kiraci birakinca bos", _O.kabin_kiracisi() is None)
    g = ofis.tahta.gorev_ac("site oku", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=A,
                            yazma_alani=["rapor.md"], tarayici_alani=["https://example.com"])
    ork = ofis.orkestra
    _gor = {}
    _asil_kostur = ork.koltuk.kos

    def _sahte_koltuk(no, ajan, **kw):
        _gor["kiraci"] = _O.kabin_kiracisi()
        _gor["cdp"] = kw.get("tarayici_kabini")
        return {"sonuc": "tamam"}

    ork.koltuk.kos = _sahte_koltuk
    try:
        _O.kabin_kirala(999)                      # baska takimin isi kabinde
        oz = ork.tik(tarayici_kabini="http://127.0.0.1:1/kabin")
        sina("  kabin baskasindayken tarayicili is KOSMAZ, sebep gorunur",
             not _gor and any("baska takim" in str(e) for e in oz["engel"]), str(oz["engel"])[:200])
        _O.kabin_birak(999)
        oz = ork.tik(tarayici_kabini="http://127.0.0.1:1/kabin")
        sina("  kabin bosken is kabini KIRALAYARAK kostu", _gor.get("kiraci") == g["no"], str(_gor))
        sina("  tur bitince kira BIRAKILDI", _O.kabin_kiracisi() is None)
    finally:
        ork.koltuk.kos = _asil_kostur

    print("\n6. danisma: ayni soru iki halkada BIR KEZ")
    _cagri = []

    class _YavasMotor(SahteMotor):
        def tur_kos(self, metin, **ayar):
            _cagri.append(1)
            _t.sleep(0.5)
            self.cevap = "Su klasore yaz."
            return super().tur_kos(metin, **ayar)

    ofis.postane.soru_sor("ece", "arda", "hangi klasor?", gorev_no=g["no"])
    d1 = Danisma(ofis, motor_fabrikasi=lambda ad, **a: _YavasMotor(cevap=""))
    d2 = Danisma(ofis, motor_fabrikasi=lambda ad, **a: _YavasMotor(cevap=""))
    _s = []
    _th = [threading.Thread(target=lambda d=d: _s.append(d.bekleyenleri_cevapla())) for d in (d1, d2)]
    for x in _th:
        x.start()
    for x in _th:
        x.join(20)
    with ofis.db.baglanti() as c:
        _ce = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'danisma'").fetchone()[0]
    sina("iki halka ayni anda: soru BIR KEZ cevaplandi (tek tur, tek cevap)",
         len(_cagri) == 1 and _ce == 1, f"tur={len(_cagri)} cevap={_ce}")
    print("\n7. seritler surerken gelen onay: seridi KAPALI takimin halkasi hemen doner (10.10 canli: #11 1,5 dk bekledi)")
    _halka_kos, _asil_kos2 = [], _O.Orkestra.kos

    def _kos_kaydet(self, **kw):
        _halka_kos.append(kw.get("kanat_id"))
        return iter(())

    _O.Orkestra.kos = _kos_kaydet
    try:
        gb = ofis.tahta.gorev_ac("B isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=B)
        ofis.kadro.ise_al("asli", "backend", kanat_id=B, motor="sahte", klasor=str(D / "kok"))
        gb = ofis.tahta.sahiplen(gb["no"], "asli", gb["revizyon"])
        C = ofis.kanat_ac("UCUNCU", "UC")
        ofis.kadro.ise_al("cem", "backend", kanat_id=C, motor="sahte", klasor=str(D / "kok"))
        gc = ofis.tahta.gorev_ac("C onay bekleyen", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=C)
        gc = ofis.tahta.sahiplen(gc["no"], "cem", gc["revizyon"])
        ofis.postane.onay_iste("cem", "git push", gorev_no=gc["no"])
        _P._KOSU.update(calisiyor=True, takimlar={"baska"})            # baska takimin seridi suruyor
        _ac = _P._takim_halkalarini_baslat(str(db_yolu), PROJE)
        sina("onayi gelen B isinin takimi icin halka HEMEN acildi", B in _ac, str(_ac))
        sina("  yalniz insani bekleyen isi olan takim (C) icin ACILMADI (bos dongu yok)", C not in _ac, str(_ac))
        _son = _t.time() + 10
        while _t.time() < _son and set(_ac) & _P._KOSU.get("takimlar", set()):
            _t.sleep(0.05)
        sina("  her halka KENDI takimiyla kostu, bitince seritler kapandi",
             sorted(_halka_kos) == sorted(_ac) and _P._KOSU.get("takimlar") == {"baska"}, str((_halka_kos, _P._KOSU.get("takimlar"))))
        _P._KOSU.update(calisiyor=True, takimlar=set())                # tek basina genel halka
        sina("  tek basina genel halka kosarken takim halkasi ACILMAZ", _P._takim_halkalarini_baslat(str(db_yolu), PROJE) == [])
        _py = (Path(__file__).resolve().parent.parent / "ofis" / "panel.py").read_text(encoding="utf-8")
        sina("  seritten cikarken ve onay gelince cagriliyor",
             _py.count("_takim_halkalarini_baslat") >= 3)
    finally:
        _O.Orkestra.kos = _asil_kos2
        _P._KOSU.update(calisiyor=False, takimlar=set())
    print("\n8. degisim atfi: BASKA klasordeki takimin turu belirsizlik DEGIL (10.10 canli: #11 kabuk.py kayda girmedi)")
    from ofis.koltuk import Koltuk as _Kol  # noqa: E402
    _kokB = D / "kokB"
    _kokB.mkdir(exist_ok=True)
    with ofis.db.baglanti() as c:
        c.execute("UPDATE gorev SET durum = 'iptal' WHERE durum IN ('hazir', 'calisiyor', 'inceleme')")
        c.execute("DELETE FROM yazma_kilidi")
    ofis.takim_klasoru_ayarla(B, str(_kokB))
    ofis.kadro.ise_al("ali", "backend", kanat_id=A, motor="sahte", klasor=str(D / "kok"))
    ofis.kadro.ise_al("bora", "backend", kanat_id=B, motor="sahte", klasor=str(_kokB))
    ofis.kadro.ise_al("can", "backend", kanat_id=A, motor="sahte", klasor=str(D / "kok"))
    g8 = ofis.tahta.gorev_ac("A isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=A, yazma_alani=["a8/"])
    g8 = ofis.tahta.sahiplen(g8["no"], "ali", g8["revizyon"])
    _kol = _Kol(ofis)
    with ofis.db.baglanti() as c:
        _bas = c.execute("SELECT COALESCE(MAX(rowid), 0) FROM olay").fetchone()[0]
    gB = ofis.tahta.gorev_ac("B isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=B, yazma_alani=["b8/"])
    gB = ofis.tahta.sahiplen(gB["no"], "bora", gB["revizyon"])
    ofis.db.olay_yaz(ofis.proje_id, "arac", "bora yazdi", ajan_ad="bora", gorev_id=gB["id"])
    _kol._tur_basi[g8["id"]] = _bas
    sina("BASKA klasorde kosan takimin turu: atif BELIRSIZ DEGIL", _kol._komsu_kostu_mu(g8, "ali") is False)
    gA2 = ofis.tahta.gorev_ac("A ikinci", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=A, yazma_alani=["a9/"])
    gA2 = ofis.tahta.sahiplen(gA2["no"], "can", gA2["revizyon"])
    _kol._tur_basi[g8["id"]] = _bas
    sina("  AYNI klasorde kosan is: atif BELIRSIZ (eskisi gibi)", _kol._komsu_kostu_mu(g8, "ali") is True)
finally:
    _S.Sohbet.konus = _asil_konus
    _P.MOTOR_FABRIKASI = None
    _P._KOSU.update(calisiyor=False, mesaj="", dur=False)
    _P._KOSU["takimlar"] = set()

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
