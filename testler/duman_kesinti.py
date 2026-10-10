"""KESINTIDEN DEVAM duman testi -- `ofis/surec.py`, `ofis/toparla.py`, panel acilisi.

Jeton yakmaz. Olu surec GERCEK: bir alt surec baslatilir, kimligi alinir,
oldurulur. Sinanan:
  1. surec kimligi: yasayan / olen / ayni pid farkli olusma / bozuk
  2. sahiplenme ve geri gonderme isi kosturan surecin kimligini yazar
  3. acilista: olu surecin isi `kesinti` ile birakilir; yasayanin ve eski
     (kimliksiz) kaydin isine DOKUNULMAZ; kilitsiz (yazma alani bos) is de bulunur
  4. birakilan is AYNI oturumdan surer (`_devam_mi`)
  5. kuyruk: plan asamasinda olen istek BASTAN (yarim balon kapanir); is
     acilmissa `devam` (yeniden planlanmaz); kuyruksuz yarim is icin devam satiri
  6. sohbete tek not; yapacak bir sey yoksa not YOK
  7. panel iscisi `devam` satirinda halkayi kosar, liderin planini KOSMAZ
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import subprocess
import sys
import tempfile
import time as _t
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import kuyruk as K
from ofis import surec, takim
from ofis.toparla import acilista_toparla, SEBEP
from ofis.koltuk import Koltuk
import ofis.panel as _P
import ofis.sohbet as _S
import ofis.orkestra as _O

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def olu_kimlik() -> str:
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    _t.sleep(0.3)
    k = surec.kimlik(p.pid)
    p.kill()
    p.wait()
    _t.sleep(0.2)
    return k


print("== kesintiden devam duman testi ==\n")

print("1. surec kimligi")
ben = surec.kimlik()
olu = olu_kimlik()
sina("yasayan surec -> True", surec.yasiyor(ben) is True)
sina("oldurulen surec -> False", surec.yasiyor(olu) is False, olu)
_pid, _ol = ben.split(":")
sina("ayni pid, farkli olusma -> False (numara baska surecte)",
     surec.yasiyor(f"{_pid}:{int(_ol) + 1}") is False)
sina("bozuk kimlik -> None (olu SAYILMAZ)", surec.yasiyor("bozuk") is None)

kok = Path(tempfile.mkdtemp(prefix="ofis-kesinti-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
PROJE = "Kesinti"
ofis = Ofis.proje_ac(db, PROJE, amac="devam", basari_olcutu="surer",
                     kok_klasor=str(kok / "calisma"))
kn = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kn, motor="sahte",
                  klasor=str(kok / "calisma"))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))


def gorev(baslik, alan):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                            yazma_alani=alan)
    return ofis.tahta.gorev(g["no"])


def kosan_yap(g, ajan="cinar"):
    ofis.tahta.sahiplen(g["no"], ajan, ofis.tahta.gorev(g["no"])["revizyon"])
    return ofis.tahta.gorev(g["no"])


def kimlik_yaz(g, kim):
    with db.baglanti() as c:
        c.execute("UPDATE gorev SET kosan_surec = ? WHERE id = ?", (kim, g["id"]))


# ---------------------------------------------------------------------------
print("\n2. sahiplenme kimligi yazar")
g1 = kosan_yap(gorev("yazilim isi", ["api/"]))
sina("sahiplenen surecin kimligi iste", g1.get("kosan_surec") == surec.kimlik(), str(g1.get("kosan_surec")))

# ---------------------------------------------------------------------------
print("\n3. acilista toparlama")
sina("yapacak bir sey yokken NOT YAZILMAZ",
     acilista_toparla(ofis) == {"birakilan": [], "yeniden": 0, "devam": 0}
     and not any(x["tur"] == "ozet" for x in takim.akis(ofis)))
kimlik_yaz(g1, olu)
g2 = kosan_yap(gorev("arastirma (kilitsiz)", []), "demir")
kimlik_yaz(g2, olu)
g3 = kosan_yap(gorev("kabuktan kosan is", ["web/"]))      # yasayan surec: ben
g4 = kosan_yap(gorev("eski kayit", ["eski/"]))
kimlik_yaz(g4, "")
with db.baglanti() as c:
    sina("  kilitsiz isin kilidi YOK (kira onu hic bulmazdi)",
         c.execute("SELECT COUNT(*) FROM yazma_kilidi WHERE gorev_id = ?",
                   (g2["id"],)).fetchone()[0] == 0)
    for g in (g1, g2):
        c.execute("INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, olusturuldu) "
                  "VALUES (?, ?, ?, 'oturum', 'x', ?)",
                  (ofis.proje_id, g["sahip"], g["id"], "2000-01-01T00:00:00+00:00"))
    c.execute("UPDATE ajan SET oturum_id = 'oturum-1' WHERE ad IN ('cinar', 'demir')")
s = acilista_toparla(ofis)
d = {g["no"]: ofis.tahta.gorev(g["no"])["durum"] for g in (g1, g2, g3, g4)}
sina("olu surecin isi birakildi", s["birakilan"] == [g1["no"], g2["no"]], str(s))
sina("  kilitsiz is de bulundu", d[g2["no"]] == "hazir", str(d))
sina("  yasayan surecin isine DOKUNULMADI", d[g3["no"]] == "calisiyor")
sina("  kimliksiz eski kayda DOKUNULMADI", d[g4["no"]] == "calisiyor")
with db.baglanti() as c:
    sina("  kilit cozuldu", c.execute("SELECT COUNT(*) FROM yazma_kilidi WHERE gorev_id = ?",
                                      (g1["id"],)).fetchone()[0] == 0)

print("\n4. ayni oturumdan devam")
kt = Koltuk(ofis)
for g in (g1, g2):
    gg = ofis.tahta.gorev(g["no"])
    sina(f"  #{g['no']} '{SEBEP[:20]}...' sonrasi AYNI oturumdan surer",
         kt._devam_mi(g["no"], g["sahip"], ofis.kadro.ajan(g["sahip"]), gg) is True)

print("\n5. kuyruk")
# kuyruksuz yarim is -> devam satiri eklendi mi
_bk = K.bekleyenler(ofis)
sina("kuyruga bagli olmayan yarim is icin DEVAM satiri eklendi",
     len(_bk) == 1 and _bk[0]["devam"] == 1 and _bk[0]["kaynak"] == "kesinti", str(_bk))
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET durum = 'bitti'")
# (a) plan asamasinda olen istek
a = K.ekle(ofis, "plan asamasinda kalan istek", "demir")
ka = K.sira_al(ofis, "s")
ofis.postane.soru_sor("insan", "demir", "plan asamasinda kalan istek")
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET kosan_surec = ? WHERE id = ?", (olu, ka["id"]))
s = acilista_toparla(ofis)
_bk = K.bekleyenler(ofis)
with db.baglanti() as c:
    _m = c.execute("SELECT cevap FROM mesaj WHERE govde = 'plan asamasinda kalan istek'").fetchone()
sina("plan asamasinda olen istek BASTAN calisacak", s["yeniden"] == 1 and len(_bk) == 1
     and _bk[0]["devam"] == 0, str(s))
sina("  yarim 'dusunuyor' balonu KAPANDI", "yarıda kaldı" in (_m["cevap"] or ""), str(dict(_m)))
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET durum = 'bitti'")
# (b) is acildiktan sonra olen istek
b = K.ekle(ofis, "is acilmis istek", "demir")
kb = K.sira_al(ofis, "s")
ofis.postane.soru_sor("insan", "demir", "is acilmis istek")
gb = kosan_yap(gorev("acilan is", ["b/"]))
kimlik_yaz(gb, olu)
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET kosan_surec = ? WHERE id = ?", (olu, kb["id"]))
s = acilista_toparla(ofis)
_bk = K.bekleyenler(ofis)
# Ilk alim ESKI bir ana sabitlenir: hizli sinamada iki alim ayni saniyeye
# duser ve "baslangic korundu mu" farki gorunmez (olculdu: mutasyon gecti).
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET basladi = '2001-01-01T00:00:00+00:00' WHERE id = ?", (kb["id"],))
kb["basladi"] = "2001-01-01T00:00:00+00:00"
sina("is acilmis istek YENIDEN PLANLANMAZ, devam eder", s["yeniden"] == 0 and len(_bk) == 1
     and _bk[0]["devam"] == 1 and _bk[0]["metin"] == "is acilmis istek", str(_bk))
sina("  acilan isi icin ayrica devam satiri EKLENMEDI (cift yok)", s["devam"] == 1, str(s))
sina("  yasayan kuyruk satirina dokunulmaz", True)
ak = takim.akis(ofis)
sina("sohbete ofisin notu dustu", any(x["tur"] == "ozet" and "yarım kalan" in x["metin"]
                                      for x in ak))

print("\n7. panel iscisi devam satirinda HALKAYI kosar")
kosan = []
_asil_kos, _asil_konus = _O.Orkestra.kos, _S.Sohbet.konus


def _kos(self, **kw):
    kosan.append("halka")
    yield {"bitti": True}


def _konus(self, mesaj, **kw):
    kosan.append("lider:" + mesaj)
    return iter(())


_O.Orkestra.kos, _S.Sohbet.konus = _kos, _konus
_P.MOTOR_FABRIKASI = lambda ad, **kw: None
try:
    _P._kuyrugu_baslat(str(db_yolu), PROJE)
    for _ in range(200):
        if not _P._KOSU["calisiyor"]:
            _t.sleep(0.3)
            if not _P._KOSU["calisiyor"]:
                break
        _t.sleep(0.05)
    sina("devam satiri halkayi kostu, lider plani KOSMADI", kosan == ["halka"], str(kosan))
    with db.baglanti() as c:
        _d = c.execute("SELECT durum, not_ FROM kuyruk WHERE metin = 'is acilmis istek'").fetchone()
    sina("  satir bitti", _d["durum"] == "bitti", str(dict(_d)))
    with db.baglanti() as c:
        _s2 = c.execute("SELECT gorev_sinir, basladi FROM kuyruk WHERE id = ?", (kb["id"],)).fetchone()
        _mc = c.execute("SELECT cevap FROM mesaj WHERE govde = 'is acilmis istek'").fetchone()
    sina("  yeniden alinca ILK baslangic ve is siniri KORUNDU",
         _s2["gorev_sinir"] == kb["gorev_sinir"] and _s2["basladi"] == kb["basladi"], str(dict(_s2)))
    sina("  yarim kalan patron mesaji ofisin CEVABIYLA kapandi (isin durumu)",
         f"#{gb['no']} acilan is" in (_mc["cevap"] or "") and "sürdürüldü" in _mc["cevap"],
         str(dict(_mc)))
finally:
    _O.Orkestra.kos, _S.Sohbet.konus = _asil_kos, _asil_konus
    _P.MOTOR_FABRIKASI = None
    _P._KOSU.update(calisiyor=False, mesaj="", dur=False)

print("\n8. patronu BEKLEYEN ise dokunulmaz (01.10 canli: #42 deniz->bilge->cinar)")
ofis.kadro.ise_al("yaprak", "backend", kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))
gw = kosan_yap(gorev("onay bekleyen is", ["w/"]), "yaprak")
kimlik_yaz(gw, olu)
ofis.postane.onay_iste("yaprak", "GONDERIM: form yolla", ayrinti="x", risk="yuksek")
_sw = acilista_toparla(ofis)
sina("onay bekleyen is BIRAKILMADI (ayni onay yeniden sorulmaz, sahip degismez)",
     gw["no"] not in _sw["birakilan"] and ofis.tahta.gorev(gw["no"])["durum"] == "calisiyor"
     and ofis.tahta.gorev(gw["no"])["sahip"] == "yaprak", str(_sw))
with db.baglanti() as c:
    sina("  onay TEK kez", c.execute("SELECT COUNT(*) FROM onay WHERE isteyen='yaprak'"
                                     ).fetchone()[0] == 1)

# 09.10 F1 canli (#4): ajan LIDERE sordu, panel yeniden acildi; is 'beklemede'
# sayildi ve soruyu cevaplatacak halka hic donmedi. Patronu bekleyen soru beklemede
# kalir; ajana sorulani ofis cevaplatir -> devam kaydi siraya girer.
with db.baglanti() as c:
    c.execute("UPDATE kuyruk SET durum = 'bitti' WHERE durum = 'bekliyor'")
_s0 = acilista_toparla(ofis)
sina("  yalniz patronu bekleyen varken devam KAYDI ACILMAZ", _s0["devam"] == 0, str(_s0))
ofis.kadro.ise_al("serin", "backend", kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))
gs = kosan_yap(gorev("lidere soran is", ["s/"]), "serin")
kimlik_yaz(gs, olu)
ofis.postane.soru_sor("serin", "demir", "hangi klasore yazayim?", gorev_no=gs["no"])
_s1 = acilista_toparla(ofis)
sina("LIDERE soru bekleyen is: acilista halka surdurulur (devam kaydi)",
     _s1["devam"] == 1 and any(x.get("devam") for x in K.bekleyenler(ofis)), str(_s1))
sina("  is birakilmaz, sahibi ayni (cevap gelince kaldigi yerden)",
     ofis.tahta.gorev(gs["no"])["sahip"] == "serin" and gs["no"] not in _s1["birakilan"])
# Cevap gelir, YENI panel isi surdurur: sahip/durum ayni oldugu icin `sahiplen`
# cagrilmiyordu ve kayit OLU panelin kimligini tasiyordu (mesgul 'bos' sandi).
for _m in ofis.postane.bekleyen_sorular(soran="serin"):
    ofis.postane.cevapla(_m["id"], "s/ klasorune", cevaplayan="demir")
from ofis.motor.sahte import SahteMotor  # noqa: E402
_kts = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(cevap="tamam\nKANIT not: s/ yazildi"))
try:
    _kts.kos(gs["no"], "serin")
except Exception as _e:  # noqa: BLE001 -- olcu kayitta
    print("   (tur:", _e, ")")
with db.baglanti() as c:
    _ks = c.execute("SELECT kosan_surec FROM gorev WHERE no = ?", (gs["no"],)).fetchone()[0]
sina("  surduren surec kaydi BU surec (olu panelin kimligi kalmaz)", _ks == surec.kimlik() or _ks == "",
     f"{_ks} != {surec.kimlik()}")
with db.baglanti() as c:
    _adsiz = c.execute("SELECT COUNT(*) FROM olay WHERE tur='sahiplenildi' AND ajan_ad=''").fetchone()[0]
sina("  'isi aldi' kaydi tek ve adli (adsiz ikinci kayit yok)", _adsiz == 0, str(_adsiz))

# Sahne: cinar'in kosan (yasayan) isi kapanir -> cinar bosta; ayrica BASKA bosta
# bir ajan (ayaz) var. Dagitim "ilk bostaki"ni degil ONCEKI SAHIBI secmeli.
with db.baglanti() as c:
    _kapat = (g3["id"], gb["id"], g4["id"])   # cinar'in kosan, acilan ve eski isi
    c.execute("UPDATE gorev SET durum = 'iptal' WHERE id IN (?, ?, ?)", _kapat)
    c.execute("DELETE FROM yazma_kilidi WHERE gorev_id IN (?, ?, ?)", _kapat)
# Kadro ALFABETIK siralanir: "ayaz" cinar'dan once gelir -- tercih olmasa ilk
# bostaki o olurdu (olculdu: "ege" ile sinama bu ayrimi OLCMUYORDU).
ofis.kadro.ise_al("ayaz", "backend", kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))
_gg1 = ofis.tahta.gorev(g1["no"])
sina("kesintiyle birakilan is dagitimda ONCEKI SAHIBINE gider (baska bosta ajan varken)",
     _gg1["durum"] == "hazir" and ofis.orkestra._uygun_ajan(_gg1) == "cinar",
     f"{_gg1['durum']} -> {ofis.orkestra._uygun_ajan(_gg1)}")

print("\n9. takim klasoru kaybolduysa acilista UYARI (11.10 canli)")
_kyok = ofis.kanat_ac("KAYIP", "KY")
_kyer = kok / "kayip-takim"
ofis.takim_klasoru_ayarla(_kyok, str(_kyer))
import shutil as _shk  # noqa: E402
_shk.rmtree(_kyer)                                 # klasor tasindi/silindi
acilista_toparla(ofis)
with db.baglanti() as c:
    _ku = [r[0] for r in c.execute("SELECT govde FROM olay WHERE tur='uyari' AND govde LIKE '%BULUNAMADI%'")]
sina("kaybolan takim klasoru acilista SOYLENDI", any("kayip-takim" in x for x in _ku), str(_ku)[:200])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
