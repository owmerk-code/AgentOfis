"""ZAMANLAYICI duman testi -- `ofis/zamanlayici.py`, triyajda `zamanla`, panel turu.

Jeton yakmaz (lider SahteMotor). Zaman SABIT verilir (yerel saate cevrilerek):
sinama makinenin saat dilimine ve gunune bagli olmasin. Sinanan:
  1. kural dogrulama: gecerli bicimler; yanlis saat/gun/aralik/tur reddi
  2. sonraki vakit: gunluk (once/sonra), haftalik (dogru gun), bir kez, aralik
  3. vadesi gelen: kuyruga BIR kez girer; kacirilan gunler BIRIKMEZ; "gec kaldi";
     bir kezlik is sonra etkin degil; iki surec ayni anda baksa da TEK kez
  4. iptal ve triyaj blogu
  5. sohbet: lider `zamanla` der, OFIS kaydeder ve cevabi kurar; yanlis zaman
     kayit ACMAZ ve sorar; `iptal` ile kaldirir; triyaj metni ZAMANI gosterir
  6. panel turu: vakti gelen isi siraya koyar, sirayi baslatir
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
import time as _t
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import kuyruk as K
from ofis import zamanlayici as Z
from ofis.sohbet import Sohbet
from ofis.motor.sahte import SahteMotor
import ofis.panel as _P
import ofis.sohbet as _S

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


def yerel(y, a, g, sa, dk):
    """Yerel saatle verilen ani UTC'ye cevirir (makinenin dilimi)."""
    return datetime(y, a, g, sa, dk).astimezone().astimezone(timezone.utc)


print("== zamanlayici duman testi ==\n")

print("1. dogrulama")
sina("gunluk gecerli", Z.dogrula({"tur": "gunluk", "saat": "9:05"}) == {"tur": "gunluk", "saat": "09:05"})
sina("haftalik gunler siralanir, tekrar atilir",
     Z.dogrula({"tur": "haftalik", "saat": "14:00", "gunler": [3, 0, 3]})["gunler"] == [0, 3])
for yanlis, ne in ((({"tur": "gunluk", "saat": "25:00"}), "saat 25"),
                   (({"tur": "haftalik", "saat": "10:00", "gunler": [7]}), "gun 7"),
                   (({"tur": "aralik", "dakika": 5}), "5 dakikalik aralik (kota)"),
                   (({"tur": "bir_kez", "tarih": "yarin", "saat": "10:00"}), "tarih metin"),
                   (({"tur": "her_zaman"}), "bilinmeyen tur"), ("dokuzda", "serbest metin")):
    sina(f"  reddedildi: {ne}", bool(hata_mi(Z.dogrula, yanlis)))

print("\n2. sonraki vakit")
s = yerel(2026, 10, 1, 8, 0)           # persembe 08:00
sina("gunluk 09:00, saat 08:00 -> BUGUN 09:00",
     Z.sonraki_an({"tur": "gunluk", "saat": "09:00"}, s) == yerel(2026, 10, 1, 9, 0))
sina("gunluk 07:00, saat 08:00 -> YARIN 07:00",
     Z.sonraki_an({"tur": "gunluk", "saat": "07:00"}, s) == yerel(2026, 10, 2, 7, 0))
sina("haftalik pazartesi 10:00, persembe gunu -> sonraki PAZARTESI (5 Ekim)",
     Z.sonraki_an({"tur": "haftalik", "saat": "10:00", "gunler": [0]}, s) == yerel(2026, 10, 5, 10, 0))
sina("haftalik persembe 08:00, tam o an -> GELECEK persembe (8 Ekim)",
     Z.sonraki_an({"tur": "haftalik", "saat": "08:00", "gunler": [3]}, s) == yerel(2026, 10, 8, 8, 0))
sina("bir kez gelecekte -> o an",
     Z.sonraki_an({"tur": "bir_kez", "tarih": "2026-10-02", "saat": "10:30"}, s) == yerel(2026, 10, 2, 10, 30))
sina("bir kez gecmiste -> None",
     Z.sonraki_an({"tur": "bir_kez", "tarih": "2026-09-30", "saat": "10:30"}, s) is None)
sina("aralik 30 dk", Z.sonraki_an({"tur": "aralik", "dakika": 30}, s) == s + timedelta(minutes=30))
sina("insan metni", Z.insan_metni({"tur": "haftalik", "saat": "14:00", "gunler": [0, 3]})
     == "her pazartesi, perşembe 14:00")

kok = Path(tempfile.mkdtemp(prefix="ofis-zaman-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
PROJE = "Zaman"
ofis = Ofis.proje_ac(db, PROJE, amac="zaman", basari_olcutu="kosar", kok_klasor=str(kok / "calisma"))
kn = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))

print("\n3. vadesi gelen")
z1 = Z.ekle(ofis, "siparisleri kontrol et", "demir", {"tur": "gunluk", "saat": "09:00"}, simdi_utc=s)
sina("eklendi, sonraki bugun 09:00", z1["sonraki"] == yerel(2026, 10, 1, 9, 0).isoformat(timespec="seconds"))
sina("vakti gelmeden siraya GIRMEZ", Z.vadesi_gelenleri_sirala(ofis, yerel(2026, 10, 1, 8, 59)) == [])
uc_gun_sonra = yerel(2026, 10, 4, 11, 0)             # PC uc gun kapali kaldi
giren = Z.vadesi_gelenleri_sirala(ofis, uc_gun_sonra)
bk = K.bekleyenler(ofis)
sina("kacirilan UC gun BIRIKMEDI: tek kez siraya girdi", len(giren) == 1 and len(bk) == 1, str(len(bk)))
sina("  kuyruk metni isin zamanli oldugunu soyluyor",
     bk and bk[0]["metin"].startswith("[Zamanlanmış iş Z1 · her gün 09:00] siparisleri"), bk[0]["metin"] if bk else "")
z1b = Z.liste(ofis)[0]
sina("  sonraki vakit SIMDIDEN sonraki ilk 09:00 (5 Ekim)",
     z1b["sonraki"] == yerel(2026, 10, 5, 9, 0).isoformat(timespec="seconds"), z1b["sonraki"])
with db.baglanti() as c:
    _g = c.execute("SELECT govde FROM olay WHERE tur = 'zamanli_calisti'").fetchone()
sina("  'gec kaldi, bilgisayar kapaliydi' soylendi", _g and "geç kaldı" in _g["govde"], str(_g and _g["govde"]))
sina("ayni an ikinci bakis siraya YENIDEN koymaz", Z.vadesi_gelenleri_sirala(ofis, uc_gun_sonra) == [])
with db.baglanti() as c:
    c.execute("DELETE FROM kuyruk")
z2 = Z.ekle(ofis, "bir kez rapor", "demir", {"tur": "bir_kez", "tarih": "2026-10-02", "saat": "10:30"},
            simdi_utc=s)
an = yerel(2026, 10, 2, 10, 31)
Z.vadesi_gelenleri_sirala(ofis, an)
sina("bir kezlik is vaktinde siraya girdi",
     len([x for x in K.bekleyenler(ofis) if "bir kez rapor" in x["metin"]]) == 1)
# IKI SUREC AYNI ANDA (panel + kabuk): ayri baglanti, ayni an, BARIYER. Art
# arda cagri yarisi HIC olusturmaz (olculdu: kosul kaldirilinca da geciyordu).
import threading as _th
cift = 0
for deneme in range(15):
    zr = Z.ekle(ofis, f"yaris {deneme}", "demir", {"tur": "aralik", "dakika": 15}, simdi_utc=s)
    with db.baglanti() as c:
        c.execute("UPDATE zamanli SET sonraki = ? WHERE id = ?", (s.isoformat(timespec="seconds"), zr["id"]))
    bar = _th.Barrier(4)

    def _bak():
        o = Ofis(Veritabani(db_yolu), ofis.proje_id)
        bar.wait()
        Z.vadesi_gelenleri_sirala(o, s + timedelta(minutes=1))
    ip = [_th.Thread(target=_bak) for _ in range(4)]
    [t.start() for t in ip]
    [t.join() for t in ip]
    n = len([x for x in K.bekleyenler(ofis) if x["metin"].endswith(f"yaris {deneme}")])
    cift += n != 1
    Z.iptal(ofis, zr["no"])
sina("4 surec AYNI ANDA bakti (15 deneme): her vakit TEK kez siraya girdi", cift == 0, f"{cift} denemede cift")
sina("bir kezlik is calistiktan sonra ETKIN DEGIL",
     not any(z["no"] == z2["no"] for z in Z.liste(ofis)))
with db.baglanti() as c:
    _bk = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur = 'zamanli_calisti' AND govde LIKE '%bir kez%'")]
sina("  zamaninda calistiysa 'gec kaldi' DENMEDI", _bk and all("geç" not in g for g in _bk), str(_bk))
with db.baglanti() as c:
    c.execute("DELETE FROM kuyruk")

print("\n4. iptal")
sina("triyaj blogu numarayla listeliyor", "Z1: her gün 09:00" in Z.triyaj_blogu(ofis))
Z.iptal(ofis, "Z1")
sina("iptal edilen listede yok, blok bos", Z.liste(ofis) == [] and Z.triyaj_blogu(ofis) == "")
sina("olmayan numara reddedilir", bool(hata_mi(Z.iptal, ofis, "Z99")))

print("\n5. sohbet (lider sahte)")


def lider_der(karar: dict):
    return lambda ad, **kw: SahteMotor(cevap=json.dumps(karar, ensure_ascii=False))


so = Sohbet(ofis, motor_fabrikasi=lider_der({
    "karar": "zamanla", "gerekce": "patron her sabah istiyor",
    "hedef": "semuparfum siparislerini kontrol et", "zaman": {"tur": "gunluk", "saat": "09:00"}}))
ol = list(so.konus("her sabah 9'da semuparfum siparislerini kontrol et", lider_ad="demir"))
cev = next((o["govde"] for o in ol if o["tur"] == "cevap"), "")
zl = Z.liste(ofis)
sina("lider 'zamanla' dedi -> OFIS kaydetti", len(zl) == 1 and zl[0]["metin"] == "semuparfum siparislerini kontrol et", str(zl))
sina("  cevabi ofis kurdu: numara, ne zaman, ilk calisma",
     bool(zl) and f"Z{zl[0]['no']}" in cev and "her gün 09:00" in cev and "İlk çalışma" in cev, cev)
sina("  hicbir is ACILMADI (simdi yapilmaz)", ofis.tahta.liste() == [])
so = Sohbet(ofis, motor_fabrikasi=lider_der({
    "karar": "zamanla", "gerekce": "x", "hedef": "rapor", "zaman": {"tur": "gunluk", "saat": "dokuzda"}}))
cev = next((o["govde"] for o in so.konus("her gun dokuzda rapor", lider_ad="demir") if o["tur"] == "cevap"), "")
sina("yanlis zaman kayit ACMADI ve patrona soruldu",
     "kaydedemedim" in cev and "Ne zaman" in cev and len(Z.liste(ofis)) == 1, cev)
so = Sohbet(ofis, motor_fabrikasi=lider_der({
    "karar": "zamanla", "gerekce": "iptal istendi", "hedef": "",
    "zaman": {"tur": "iptal", "no": zl[0]["no"] if zl else 1}}))
cev = next((o["govde"] for o in so.konus("sabah siparis kontrolunu iptal et", lider_ad="demir") if o["tur"] == "cevap"), "")
sina("'iptal et' -> kaldirildi", "iptal edildi" in cev and Z.liste(ofis) == [], cev)
tm = Sohbet(ofis).triyaj_metni("yarin 10:30'da hatirlat")
sina("triyaj metni bugunun tarihini ve gununu GOSTERIYOR",
     "Simdi (patronun yerel saati)" in tm and datetime.now().astimezone().strftime("%Y-%m-%d") in tm)
sina("  karar listesinde 'zamanla' var", "**zamanla**" in tm and '"tur": "iptal"' in tm)

print("\n6. panel turu")
kostu, _asil = [], _S.Sohbet.konus


def _konus(self, mesaj, **kw):
    kostu.append(mesaj)
    return iter(())


_S.Sohbet.konus = _konus
_P.MOTOR_FABRIKASI = lambda ad, **kw: None
try:
    zz = Z.ekle(ofis, "yedek al", "demir", {"tur": "aralik", "dakika": 15})
    with db.baglanti() as c:      # vakti GECMIS gibi
        c.execute("UPDATE zamanli SET sonraki = ? WHERE id = ?",
                  ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds"), zz["id"]))
    n = _P.zamanlayici_tik(str(db_yolu), PROJE)
    for _ in range(100):
        if kostu and not _P._KOSU["calisiyor"]:
            break
        _t.sleep(0.05)
    sina("panel turu vakti geleni siraya koydu ve lider KOSTU",
         n == 1 and kostu and "yedek al" in kostu[0], f"{n} {kostu}")
finally:
    _S.Sohbet.konus = _asil
    _P.MOTOR_FABRIKASI = None
    _P._KOSU.update(calisiyor=False, mesaj="", dur=False)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
