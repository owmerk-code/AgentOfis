"""KUYRUK duman testi -- `ofis/kuyruk.py` ve paneldeki sira iscisi.

Jeton yakmaz: lider turu sahte (`Sohbet.konus` yerine konan kosucu).
Sinanan:
  1. ekle / sira / iptal: bos is reddi, siranin sirasi, yalniz bekleyen iptal
  2. iki iplik AYNI isi alamaz (`sira_al` kosullu guncelleme)
  3. donus raporu: modelsiz, defterden; tek iste YAZILMAZ; cevap, acilan is,
     sana dusen onay, hata sebebi
  4. panel iscisi: sirayi bosaltir, dusen is sirayi DURDURMAZ, seri sonunda
     rapor; Durdur'da kosan is biter, bekleyenler KORUNUR, kendiliginden SURMEZ
  5. ofis mesgulken (halka) siraya giren is, ofis bosalinca kendiliginden baslar
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
import threading
import time as _t
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import kuyruk as K
from ofis import takim
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


print("== kuyruk duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-kuyruk-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
PROJE = "Kuyruk"
ofis = Ofis.proje_ac(db, PROJE, amac="sira", basari_olcutu="sira bosalir",
                     kok_klasor=str(kok / "calisma"))
kn = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kn, motor="sahte",
                  klasor=str(kok / "calisma"))

# ---------------------------------------------------------------------------
print("1. ekle / sira / iptal")
sina("bos is reddedilir", "Bos" in hata_mi(K.ekle, ofis, "  ", "demir"))
sina("lidersiz is reddedilir", bool(hata_mi(K.ekle, ofis, "x", "")))
a = K.ekle(ofis, "birinci is", "demir")
b = K.ekle(ofis, "ikinci is", "demir")
c = K.ekle(ofis, "ucuncu is", "demir")
sina("sira numarasi artiyor", (a["sira"], b["sira"], c["sira"]) == (1, 2, 3))
sina("bekleyenler eklenme sirasinda",
     [x["metin"] for x in K.bekleyenler(ofis)] == ["birinci is", "ikinci is", "ucuncu is"])
sina("sohbette 'sirada' balonlari EN ALTTA ve sirali",
     [x["metin"] for x in takim.akis(ofis) if x["tur"] == "sirada"]
     == ["birinci is", "ikinci is", "ucuncu is"]
     and takim.akis(ofis)[-1]["tur"] == "sirada")
K.iptal(ofis, b["id"][:8])
sina("bekleyen is iptal edildi", [x["metin"] for x in K.bekleyenler(ofis)] == ["birinci is", "ucuncu is"])
sina("iptal edilen tekrar iptal edilemez", "iptal" in hata_mi(K.iptal, ofis, b["id"][:8]))
sina("kisa kimlik reddedilir", bool(hata_mi(K.iptal, ofis, "ab")))
x1 = K.sira_al(ofis, "s0")
sina("sira_al ILK isi alir ve kosuyor yapar", x1["metin"] == "birinci is" and x1["durum"] == "kosuyor")
sina("kosan is iptal EDILEMEZ (Durdur ile durur)", "Durdur" in hata_mi(K.iptal, ofis, x1["id"][:8]))
K.bitir(ofis, x1["id"], "bitti")
sina("gecersiz bitis durumu reddedilir", bool(hata_mi(K.bitir, ofis, x1["id"], "kosuyor")))
x3 = K.sira_al(ofis, "s0")
K.bitir(ofis, x3["id"], "bitti")
sina("sira bosalinca None", K.sira_al(ofis, "s0") is None)

# ---------------------------------------------------------------------------
print("\n2. iki iplik ayni isi ALAMAZ")
for i in range(20):
    K.ekle(ofis, f"yaris {i}", "demir")
alinan, kilit = [], threading.Lock()
# HER IPLIK KENDI `Veritabani`si: ayni nesne iplikleri kendi RLock'uyla
# sirayla gecirir ve yaris HIC olusmaz (olculdu: kosul kaldirilinca da
# geciyordu -- sinama ölçtügünü sandigi seyi olcmuyordu). Gercek risk iki
# SUREC (panel + kabuk) ayni defteri okurken; ayri baglanti onu taklit eder.
_bariyer = threading.Barrier(4)


def _al():
    o2 = Ofis(Veritabani(db_yolu), ofis.proje_id)
    _bariyer.wait()
    while True:
        k = K.sira_al(o2, "yaris")
        if k is None:
            return
        with kilit:
            alinan.append(k["id"])


ipler = [threading.Thread(target=_al) for _ in range(4)]
for t in ipler:
    t.start()
for t in ipler:
    t.join()
sina("20 is, 4 iplik: her is TAM BIR kez alindi", len(alinan) == 20 and len(set(alinan)) == 20,
     f"{len(alinan)} alim, {len(set(alinan))} essiz")
with db.baglanti() as cn:
    cn.execute("UPDATE kuyruk SET durum='bitti' WHERE seri='yaris'")

# ---------------------------------------------------------------------------
print("\n3. donus raporu (modelsiz)")
tek = K.ekle(ofis, "yalniz bir is", "demir")
k = K.sira_al(ofis, "seri-tek")
K.bitir(ofis, k["id"], "bitti")
sina("tek isli seride rapor YAZILMAZ (cevap zaten sohbette)", K.raporu_yaz(ofis, "seri-tek") == "")

r1 = K.ekle(ofis, "rapor hazirla", "demir")
r2 = K.ekle(ofis, "gorsel uret", "demir")
k1 = K.sira_al(ofis, "seri-r")
ofis.postane.soru_sor("insan", "demir", "rapor hazirla")
with db.baglanti() as cn:
    cn.execute("UPDATE mesaj SET cevap = ?, cevaplandi = ? WHERE govde = 'rapor hazirla'",
               ("Rapor hazir, ekte.\n[ek] ekler/rapor.md", "2099-01-01T00:00:00+00:00"))
g = ofis.tahta.gorev_ac("Raporu yaz", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g")
K.bitir(ofis, k1["id"], "bitti")
k2 = K.sira_al(ofis, "seri-r")
K.bitir(ofis, k2["id"], "hata", "motor dustu: baglanti koptu")
ofis.postane.onay_iste("demir", "GONDERIM: e-posta yolla", ayrinti="x", risk="yuksek")
rap = K.raporu_yaz(ofis, "seri-r")
sina("rapor iki isi sayiyor", "2 iş" in rap, rap[:80])
sina("  liderin cevabi var, ek SATIRI yok ama sayisi var",
     "Rapor hazir" in rap and "[ek]" not in rap and "1 dosya ekli" in rap, rap)
sina("  seri sirasinda acilan is ve durumu", f"#{g['no']} Raporu yaz" in rap)
sina("  dusen is HATA ve sebebiyle", "HATA" in rap and "baglanti koptu" in rap)
sina("  sana dusen onay listeleniyor", "Sana düşen" in rap and "e-posta yolla" in rap)
with db.baglanti() as cn:
    _ol = cn.execute("SELECT ajan_ad FROM olay WHERE tur = 'donus_raporu'").fetchall()
sina("  rapor deftere 'donus_raporu' olarak yazildi", len(_ol) == 1 and _ol[0]["ajan_ad"] == "ofis")
sina("  sohbet akisinda 'ozet' olarak gorunuyor",
     any(x["tur"] == "ozet" and x["kimden"] == "ofis" for x in takim.akis(ofis)))
# 01.10 canli deneme: rapor, son isin cevabiyla AYNI SANIYEDE yazildi ve onun
# ustune dustu. Ayni an verilir; rapor sonda olmali.
_an = "2099-01-01T00:00:00+00:00"
with db.baglanti() as cn:
    cn.execute("UPDATE olay SET olusturuldu = ? WHERE tur = 'donus_raporu'", (_an,))
# Sirada ve Iletilemedi bilerek EN ALTA sabit (patrondan is bekliyorlar).
_ak = [x for x in takim.akis(ofis) if x["tur"] not in ("sirada", "iletilemedi")]
sina("  ayni saniyedeki CEVAPTAN SONRA geliyor (son oge rapor)",
     _ak[-1]["tur"] == "ozet" and any(x["tur"] == "cevap" and x["an"] == _an for x in _ak),
     str([(x["tur"], x["an"]) for x in _ak[-3:]]))

# ---------------------------------------------------------------------------
print("\n4. panel iscisi")
kostu, _asil_konus = [], _S.Sohbet.konus


def _sahte_konus(self, mesaj, **kw):
    kostu.append(mesaj)
    if "PATLA" in mesaj:
        # Gercek konus once mesaji yazar, sonra lideri kosturur; dusus
        # mesaj yazildiktan SONRA olursa mesaj cevapsiz asili kaliyordu.
        self.ofis.postane.soru_sor("insan", "demir", mesaj, mod="uyandiran")
        raise RuntimeError("bilerek dusuruldu")
    if "DURDUR" in mesaj:
        _P._KOSU["dur"] = True
    _t.sleep(0.05)
    return iter(())


def _bekle(sn=20.0) -> bool:
    son = _t.time() + sn
    while _t.time() < son:
        if not _P._KOSU["calisiyor"]:
            _t.sleep(0.3)               # finally'deki yeniden yoklama
            if not _P._KOSU["calisiyor"]:
                return True
        _t.sleep(0.05)
    return False


_S.Sohbet.konus = _sahte_konus
_P.MOTOR_FABRIKASI = lambda ad, **kw: None
try:
    for m in ("is A", "is PATLA", "is C"):
        K.ekle(ofis, m, "demir")
    sina("isci basladi", _P._kuyrugu_baslat(str(db_yolu), PROJE))
    sina("  ikinci baslatma TEK UCUS geregi baslamaz", _P._kuyrugu_baslat(str(db_yolu), PROJE) is False)
    sina("  sira bosaldi, nobetci serbest", _bekle())
    sina("  uc is SIRAYLA kostu", kostu == ["is A", "is PATLA", "is C"], str(kostu))
    with db.baglanti() as cn:
        _d = {r["metin"]: r["durum"] for r in cn.execute("SELECT metin, durum FROM kuyruk "
                                                        "WHERE metin LIKE 'is %'")}
        _h = cn.execute("SELECT COUNT(*) FROM olay WHERE tur='hata' AND govde LIKE '%bilerek%'"
                        ).fetchone()[0]
        _rp = [r["govde"] for r in cn.execute("SELECT govde FROM olay WHERE tur='donus_raporu'")]
    sina("  dusen is HATA oldu ama sira SURDU", _d == {"is A": "bitti", "is PATLA": "hata",
                                                     "is C": "bitti"}, str(_d))
    sina("  dusus deftere yazildi (yutulmadi)", _h == 1)
    # ILETILEMEDI (02.10.2026): mesaj cevapsiz ASILI kalmaz, sohbette kalir.
    def _uyari(metin):
        return [x for x in takim.akis(ofis) if x["tur"] == "iletilemedi" and x["metin"] == metin]
    with db.baglanti() as cn:
        _m = cn.execute("SELECT cevap FROM mesaj WHERE govde = 'is PATLA'").fetchone()
    sina("  dusen isin mesaji ofisin cevabiyla KAPANDI (asili degil)",
         bool(_m) and (_m["cevap"] or "").startswith(K.DUSUS_ONEKI)
         and "bilerek dusuruldu" in _m["cevap"], str(_m and dict(_m)))
    _il = _uyari("is PATLA")
    sina("  sohbette ILETILEMEDI ogesi, sebebiyle",
         len(_il) == 1 and "bilerek" in _il[0]["sebep"], str(_il)[:200])
    _bul = _il[0]["id"] if _il else "xxxx"
    try:
        _ty = K.tekrar_dene(ofis, _bul)
    except K.KuyrukHatasi as _e:          # cokmez: asagidaki denetimler KALDI der
        _ty = {"sira": 0, "id": "", "hata": str(_e)}
    sina("  Tekrar dene: ayni metin siranin sonunda",
         [x["metin"] for x in K.bekleyenler(ofis)] == ["is PATLA"] and _ty["sira"] == 1)
    sina("  ...ve uyari sohbetten KALKTI", not _uyari("is PATLA"))
    sina("  ele alinmis is ikinci kez denenmez", "durumunda" in hata_mi(K.tekrar_dene, ofis, _bul))
    if _ty["id"]:
        K.iptal(ofis, _ty["id"])
    _k2 = K.ekle(ofis, "is KAPAT", "demir")
    K.bitir(ofis, _k2["id"], "hata", "x")
    sina("  (sahne) kapatilacak uyari gorunuyor", len(_uyari("is KAPAT")) == 1)
    K.dusuk_kapat(ofis, _k2["id"])
    sina("  Kapat: uyari kalkar, is yeniden siraya GIRMEZ",
         not _uyari("is KAPAT") and not K.bekleyenler(ofis))
    sina("  seri sonunda rapor (3 is, hata gorunur)", len(_rp) == 2 and "3 iş" in _rp[-1]
         and "HATA" in _rp[-1], (_rp[-1][:200] if _rp else ""))

    print("\n   Durdur")
    kostu.clear()
    for m in ("is DURDUR", "is E", "is F"):
        K.ekle(ofis, m, "demir")
    _P._kuyrugu_baslat(str(db_yolu), PROJE)
    sina("  durdurulan sira bitti", _bekle())
    sina("  yalniz kosan is kostu, sira DURDU", kostu == ["is DURDUR"], str(kostu))
    sina("  bekleyenler KORUNDU", [x["metin"] for x in K.bekleyenler(ofis)] == ["is E", "is F"])
    _t.sleep(0.5)
    sina("  durdurulan sira kendiliginden SURMEDI", kostu == ["is DURDUR"] and not _P._KOSU["calisiyor"])

    print("\n   mesgulken siraya giren is")
    kostu.clear()
    # Ofis mesgul (halka kosuyor gibi): baslatma bir sey yapmaz...
    with _P._KUYRUK_KILIDI:
        _P._KOSU.update(calisiyor=True, mesaj="halka", dur=False)
    sina("  ofis mesgulken isci baslamaz", _P._kuyrugu_baslat(str(db_yolu), PROJE) is False)
    # ...mesgul is `_arkada_calistir` ile biter; bitince sira yoklanir.
    _P._arkada_calistir(str(db_yolu), PROJE, lambda o: None, "halka")
    sina("  is bitince bekleyenler KENDILIGINDEN basladi", _bekle() and kostu == ["is E", "is F"],
         str(kostu))
finally:
    _S.Sohbet.konus = _asil_konus
    _P.MOTOR_FABRIKASI = None
    _P._KOSU.update(calisiyor=False, mesaj="", dur=False)

print("\n5. ASKIDA KALAN ISTEK (08.10 canli: Durdur -> Surdur, mesaj cevapsiz, panel 3 sn'de bir cizdi)")
from ofis import kuyruk as _KQ  # noqa: E402
with ofis.db.baglanti() as _c:
    _c.execute("UPDATE kuyruk SET durum = 'iptal' WHERE durum IN ('bekliyor', 'kosuyor')")
_k = _KQ.ekle(ofis, "askida istek", "demir")
_al = _KQ.sira_al(ofis, "seri-askida")
_m = ofis.postane.soru_sor("insan", "demir", "askida istek", mod="uyandiran")
_g = ofis.tahta.gorev_ac("Askida is", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
_KQ.bitir(ofis, _k["id"], "bitti")          # Durdur: sira bitti, mesaj cevapsiz
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "teslim" + chr(10) + "[ek] .ofis/ekler/son.mp4",
                 ajan_ad="demir", gorev_id=_g["id"])


def _cevap():
    with ofis.db.baglanti() as _c:
        return _c.execute("SELECT cevap, cevaplandi FROM mesaj WHERE id = ?", (_m["id"],)).fetchone()


sina("is SURERKEN istege dokunulmaz", _KQ.askida_kalanlari_kapat(ofis) == 0 and not _cevap()["cevaplandi"])
with ofis.db.baglanti() as _c:
    _c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (_g["id"],))
_k2 = _KQ.ekle(ofis, "sonraki istek", "demir")
sina("sirada istek varken dokunulmaz", _KQ.askida_kalanlari_kapat(ofis) == 0 and not _cevap()["cevaplandi"])
_KQ.iptal(ofis, _k2["id"])
sina("isleri bitmis, sira bos: istek ofisin ozetiyle KAPANDI",
     _KQ.askida_kalanlari_kapat(ofis) == 1 and _cevap()["cevaplandi"]
     and f"#{_g['no']}" in (_cevap()["cevap"] or ""), str(dict(_cevap())))
sina("  cevap teslim dosyasini tasiyor ([ek] satiri)",
     "[ek] .ofis/ekler/son.mp4" in (_cevap()["cevap"] or ""), _cevap()["cevap"])
sina("ikinci cagri bir sey yapmaz", _KQ.askida_kalanlari_kapat(ofis) == 0)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
