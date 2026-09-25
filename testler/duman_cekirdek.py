# -*- coding: utf-8 -*-
"""Cekirdek duman testi: bes yasanin kodda gercekten durup durmadigi.

Bu dosya konfor degil SIGORTA. Sinanan seylerin hepsi, ihlal edildiginde
sistemi PATLATMAYAN ama sessizce guvenilmez yapan seylerdir: cakisan
yazma, dongu, bayat yazar, kanitsiz kapanis. Bunlar calismadiginda tahta
calisiyor gorunur ve hicbir sey ilerlemez -- en pahali hata turu budur.

Her sinamanin basligi, hangi yasayi korudugunu soyler.

Konsol cp1254 oldugu icin cikti ASCII: '->' yazilir, ok isareti degil.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.kadro import KadroHatasi
from ofis.tahta import TahtaHatasi, KilitCakismasi, RevizyonCakismasi
from ofis.bellek import BellekHatasi

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


def reddetmeli(baslik: str, cagri, hata_sinifi) -> None:
    """Bir seyin REDDEDILDIGINI sinar -- uyarildigini degil.

    Ayrim onemli: uyari gorulmez, ret gorulur. Bu projedeki kurallarin
    cogu bilerek serttir; sessizce izin veren bir kural, kural degildir.
    """
    try:
        cagri()
        sina(baslik, False, "-- sessizce izin verildi!")
    except hata_sinifi:
        sina(baslik, True)


print("== cekirdek duman testi ==\n")

gecici = Path(tempfile.mkdtemp(prefix="ofis-duman-")) / "ofis.sqlite3"
db = Veritabani(gecici)
ofis = Ofis.proje_ac(
    db, "Duman Projesi",
    amac="Cekirdegin degismezlerini sinamak",
    basari_olcutu="Butun kapilar reddediyor",
    kapsam_disi="Panel, motor",
    kisitlar="Yerel, tek makine",
)
kanat = ofis.kanat_ac("URUN", "UR")

# --------------------------------------------------------------------------
print("1. KADRO -- ad geri donmez, lider tektir")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(gecici.parent / "demir"))
ofis.kadro.ise_al("cinar", "backend", klasor=str(gecici.parent / "cinar"))
ofis.kadro.ise_al("bilge", "arastirma", tur="kafa")

reddetmeli("ad tekrari reddediliyor",
           lambda: ofis.kadro.ise_al("demir", "test"), KadroHatasi)
reddetmeli("ikinci lider reddediliyor",
           lambda: ofis.kadro.ise_al("ayaz", "lider", lider_mi=True, kanat_id=kanat),
           KadroHatasi)
reddetmeli("kafa lider olamaz (yargi verilmez)",
           lambda: ofis.kadro.ise_al("kafa-lider", "lider", lider_mi=True, tur="kafa"),
           KadroHatasi)
reddetmeli("gecersiz ad reddediliyor (ad hem adres hem kimlik)",
           lambda: ofis.kadro.ise_al("Demir Bey!", "test"), KadroHatasi)
reddetmeli("bilinmeyen motor reddediliyor",
           lambda: ofis.kadro.ise_al("ayaz", "test", motor="gpt5"), KadroHatasi)

# --------------------------------------------------------------------------
print("\n2. BELLEK -- cift-zamanlilik: eski olgu kapanir, gecmis durur")
ofis.bellek.olgu_yaz("iade suresi", "14 gun", kaynak="magaza")
ofis.bellek.olgu_yaz("marka tonu", "sade, abartisiz", kaynak="insan")
ofis.bellek.olgu_yaz("iade suresi", "30 gun", kaynak="insan")   # devirir

gecerli = {o["konu"]: o["icerik"] for o in ofis.bellek.gecerli_olgular()}
sina("yeni olgu gecerli", gecerli.get("iade suresi") == "30 gun")
sina("eski olgu artik gecerli degil",
     len([o for o in ofis.bellek.gecerli_olgular() if o["konu"] == "iade suresi"]) == 1)
gecmis = ofis.bellek.konu_gecmisi("iade suresi")
sina("gecmis SILINMEDI, okunabiliyor", len(gecmis) == 2)
sina("eski olgunun bitis tarihi var",
     any(g["gecerli_bitis"] for g in gecmis))

reddetmeli("gerekcesiz karar reddediliyor",
           lambda: ofis.bellek.karar_yaz("Bolmuyorum", "", "demir"), BellekHatasi)
ofis.bellek.karar_yaz(
    "Isi bolmuyorum, tek ajanda kosuyor.",
    "Kollar bagimsiz degil; coklu ajan ~15x jeton yakar ve yalnizca "
    "genislik-oncelikli iste kazanir.",
    "demir", tur="dagitim",
)
sina("fan-out karari gunluge dustu",
     ofis.bellek.son_kararlar(5)[0]["tur"] == "dagitim")

# Zaman damgasi saniye cozunurluklu; ayni saniyeye dusen kararlar
# yalnizca zamana gore siralanirsa EN ESKISI USTTE gelir. Brifing bu
# listeyi "en yenisi ustte" ve "baglayicidir" diye sunar -- yani devrilmis
# bir karar gecerli sanilir. Olculdu, duzeltildi (rowid ile beraberlik bozma).
for etiket in ("SIRA-1", "SIRA-2", "SIRA-3"):
    ofis.bellek.karar_yaz(etiket, "siralama sinamasi", "demir")
sirali = [k["karar"] for k in ofis.bellek.son_kararlar(3)]
sina("ayni saniyedeki kararlar EN YENISI USTTE geliyor",
     sirali == ["SIRA-3", "SIRA-2", "SIRA-1"], f"-- {sirali}")

# --------------------------------------------------------------------------
print("\n3. TAHTA -- belirtim zorunlu (MAST %41,8)")
reddetmeli("neden'siz gorev acilmiyor",
           lambda: ofis.tahta.gorev_ac("Is", neden="", ana_hedef="h",
                                       kabul_olcutu="k"), TahtaHatasi)
reddetmeli("kabul olcutusuz gorev acilmiyor",
           lambda: ofis.tahta.gorev_ac("Is", neden="n", ana_hedef="h",
                                       kabul_olcutu=""), TahtaHatasi)

g1 = ofis.tahta.gorev_ac(
    "Siparis API'sini yaz", neden="Magaza siparis alamiyor",
    ana_hedef="Magaza canliya cikacak", kabul_olcutu="pytest yesil, 3 uc nokta",
    yazma_alani=["api/"], kanat_id=kanat,
)
g2 = ofis.tahta.gorev_ac(
    "Arayuz sepet ekrani", neden="Musteri sepeti goremiyor",
    ana_hedef="Magaza canliya cikacak", kabul_olcutu="Ekran goruntusu",
    yazma_alani=["web/"], kanat_id=kanat,
)
g3 = ofis.tahta.gorev_ac(
    "Siparis API'sine odeme ekle", neden="Odeme alinamiyor",
    ana_hedef="Magaza canliya cikacak", kabul_olcutu="Test odemesi gecer",
    yazma_alani=["api/odeme"], kanat_id=kanat,
)
sina("gorev numaralari sirali", (g1["no"], g2["no"], g3["no"]) == (1, 2, 3))

# --------------------------------------------------------------------------
print("\n4. DAG -- dongu reddedilir (yoksa hicbir is asla hazir olmaz)")
ofis.tahta.bagimlilik_ekle(g3["no"], g1["no"])      # 3, 1'i bekler
sina("bagimli gorev 'bekliyor'a dustu",
     ofis.tahta.gorev(g3["no"])["durum"] == "bekliyor")
reddetmeli("dongu reddediliyor",
           lambda: ofis.tahta.bagimlilik_ekle(g1["no"], g3["no"]), TahtaHatasi)
reddetmeli("blokcusu bitmemis gorev sahiplenilemiyor",
           lambda: ofis.tahta.sahiplen(g3["no"], "cinar",
                                       ofis.tahta.gorev(g3["no"])["revizyon"]),
           TahtaHatasi)

# --------------------------------------------------------------------------
print("\n5. YAZMA KILIDI -- Yasa 1: cakisan alan REDDEDILIR")
g1 = ofis.tahta.gorev(g1["no"])
ofis.tahta.sahiplen(g1["no"], "cinar", g1["revizyon"])
sina("kilit alindi, gorev calisiyor",
     ofis.tahta.gorev(g1["no"])["durum"] == "calisiyor")

# ayrik alan: paralel calisabilmeli
g2 = ofis.tahta.gorev(g2["no"])
ofis.tahta.sahiplen(g2["no"], "bilge", g2["revizyon"])
sina("AYRIK alan paralel calisiyor (web/ ile api/)",
     ofis.tahta.gorev(g2["no"])["durum"] == "calisiyor")

# cakisan alan: api/odeme, api/ oneki altinda
sina("cakisma tespit ediliyor (api/odeme <- api/)",
     len(ofis.tahta.cakisan_kilitler(["api/odeme"])) == 1)

g4 = ofis.tahta.gorev_ac(
    "API'de log duzelt", neden="Hata izlenemiyor",
    ana_hedef="Magaza canliya cikacak", kabul_olcutu="Log dosyasi olusuyor",
    yazma_alani=["api/log"], kanat_id=kanat,
)
reddetmeli("CAKISAN yazma alani reddediliyor (uyari degil, ret)",
           lambda: ofis.tahta.sahiplen(g4["no"], "demir", g4["revizyon"]),
           KilitCakismasi)

# --------------------------------------------------------------------------
print("\n6. CAS -- bayat yazar reddedilir")
guncel = ofis.tahta.gorev(g1["no"])
reddetmeli("bayat revizyonla incelemeye verilemiyor",
           lambda: ofis.tahta.incelemeye_ver(g1["no"], guncel["revizyon"] - 1),
           RevizyonCakismasi)

# --------------------------------------------------------------------------
print("\n7. KANIT KAPISI -- 'calisiyor' demek kanit degil, iddiadir")
reddetmeli("KANITSIZ incelemeye verilemiyor",
           lambda: ofis.tahta.incelemeye_ver(g1["no"], guncel["revizyon"]),
           TahtaHatasi)
reddetmeli("KANITSIZ kapatilamiyor",
           lambda: ofis.tahta.kapat(g1["no"], guncel["revizyon"], kapatan="demir"),
           TahtaHatasi)

ofis.tahta.kanit_ekle(g1["no"], "terminal", "pytest -q", "9 passed", "cinar")
guncel = ofis.tahta.gorev(g1["no"])
ofis.tahta.incelemeye_ver(g1["no"], guncel["revizyon"])
sina("kanitla incelemeye gecti",
     ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")
sina("kilit incelemede DE duruyor (lider geri gonderebilir)",
     len(ofis.tahta.cakisan_kilitler(["api/"])) == 1)

# lider geri gonderir -- gerekce zorunlu
guncel = ofis.tahta.gorev(g1["no"])
reddetmeli("gerekcesiz geri gonderme reddediliyor",
           lambda: ofis.tahta.geri_gonder(g1["no"], guncel["revizyon"],
                                          gerekce="", gonderen="demir"),
           TahtaHatasi)
ofis.tahta.geri_gonder(g1["no"], guncel["revizyon"],
                       gerekce="Kenar durumu yok: bos sepet", gonderen="demir")
sina("geri gonderilen is 'calisiyor'a dondu",
     ofis.tahta.gorev(g1["no"])["durum"] == "calisiyor")

# --------------------------------------------------------------------------
print("\n8. DERS -- kisiye ozel sicil, tekrar sayaci")
ofis.kadro.ders_yaz("cinar", "Kenar durumlarini kabul olcutune yaz", g1["id"])
ofis.kadro.ders_yaz("cinar", "Kenar durumlarini kabul olcutune yaz", g1["id"])
dersler = ofis.kadro.dersler("cinar")
sina("ayni ders yeni satir acmadi", len(dersler) == 1)
sina("tekrar sayaci arttI (2)", dersler[0]["tekrar"] == 2)
with ofis.db.baglanti() as _c:
    _dg = [r["govde"] for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='ders' ORDER BY rowid").fetchall()]
sina("tekrar OLAYDA da gorunuyor (ayni cumle iki kez basilmiyor)",
     len(_dg) >= 2 and "[2. kez]" in _dg[-1] and "kez]" not in _dg[-2], str(_dg[-2:]))
sina("ders KISIYE ozel, baskasina yapismiyor",
     ofis.kadro.dersler("bilge") == [])

# --------------------------------------------------------------------------
print("\n9. KAPANIS -- kanit varsa kapanir, bagimlilar cozulur")
guncel = ofis.tahta.gorev(g1["no"])
ofis.tahta.kapat(g1["no"], guncel["revizyon"], kapatan="demir")
sina("kanitla kapandi", ofis.tahta.gorev(g1["no"])["durum"] == "bitti")
sina("kapanista kilit birakildi", ofis.tahta.cakisan_kilitler(["api/"]) == [])
sina("blokcusu biten gorev 'hazir'a gecti",
     ofis.tahta.gorev(g3["no"])["durum"] == "hazir")

# --------------------------------------------------------------------------
print("\n10. BRIFING -- K3 taze uretilir, eski olgu SIZMAZ")
g3 = ofis.tahta.gorev(g3["no"])
ofis.tahta.sahiplen(g3["no"], "cinar", g3["revizyon"])
b = ofis.brifing.uret(g3["no"], "cinar", diske_yaz=False)
metin = b["metin"]

sina("dort katman da var",
     all(k in metin for k in ("K1 —", "K2 —", "K3 —", "K4 —")))
sina("GECERLI olgu brifingde (30 gun)", "30 gun" in metin)
sina("ESKI olgu brifinge SIZMIYOR (14 gun)", "14 gun" not in metin,
     "-- bayat bilgi ajana gitti!")
sina("baskasinin ne yaptigi gorunuyor (bilge)", "bilge" in metin)
sina("ajanin KENDI dersi brifingde",
     "Kenar durumlarini kabul olcutune yaz" in metin)
sina("gorevin NEDEN'i brifingde", "Odeme alinamaz" in metin or "Odeme alinamiyor" in metin)
sina("yazma alani brifingde", "api/odeme" in metin)
sina("jeton tahmini makul (<6000)", b["jeton_tahmini"] < 6000,
     f"-- {b['jeton_tahmini']} jeton")
sina("brifing kaydedildi (ajan ne biliyordu sorusu)", bool(b["id"]))

# --------------------------------------------------------------------------
print("\n10b. OLGU SECIMI -- buyuyen hafiza brifingi sisirmiyor")
# OLCULDU: secim yokken 2000 olgu brifingi 36.398 jetona cikariyordu
# ve %100u o ise gereksizdi. Secimle 1.491 jeton -- 24 kat. Isabet
# her olcekte %100 kaldi.
for _i in range(120):
    ofis.bellek.olgu_yaz(f"arsiv konusu {_i}", f"kayit-{_i:05d}-son")
ofis.bellek.olgu_yaz("odeme saglayicisi", "Iyzico kullaniliyor")
gs = ofis.tahta.gorev_ac(
    "Odeme ekrani", neden="Odeme saglayicisi gorunmuyor",
    ana_hedef="Magaza canliya cikacak",
    kabul_olcutu="Ekranda odeme saglayicisi yazsin",
    yazma_alani=["odeme/"], kanat_id=kanat)
bs = ofis.brifing.uret(gs["no"], "bilge", diske_yaz=False)
sina("gereken olgu secimden GECTI", "Iyzico" in bs["metin"])
sina("brifing sismedi", bs["jeton_tahmini"] < 6000,
     f"-- {bs['jeton_tahmini']} jeton")
# Gizli eksiltme UYDURMANIN kapisini acar: ajan gorusunun tam
# oldugunu sanirsa olmayan bilgiyi tahmin eder.
sina("secim yapildigi ajana SOYLENIYOR", "BU ISE GORE secildi" in bs["metin"])
sina("uydurma yasagi ve sorma yolu veriliyor",
     "UYDURMA" in bs["metin"] and "lidere danis" in bs["metin"])

# --------------------------------------------------------------------------
print("\n11. UYANIS -- devam eden oturuma yalniz DEGISEN verilir")
isaret = ofis.bellek.son_olay_id()
ofis.bellek.karar_yaz("Odeme saglayicisi: Iyzico", "Turkiye'de kart orani en dusuk.",
                      "demir", tur="teknik")
ofis.bellek.olgu_yaz("iade suresi", "45 gun", kaynak="insan")
uyanis = ofis.brifing.uyanis_metni("cinar", isaret)
sina("uyanis metni degisikligi tasiyor", "Iyzico" in uyanis)
sina("uyanis metni KISA (tam brifing degil)", len(uyanis) < len(metin) / 3)
sina("ajanin KENDI olaylari uyanista tekrarlanmiyor",
     "sahiplenildi" not in uyanis)

print("\nKILIT KIRASI -- DURDURULMUS ajan olmus sayilmaz")
# OLCULDU (19.09.2026): kira 180 saniye, insan cevabi dakikalar surer.
# Yani soru soran ajanin kilidi HER SEFERINDE dusuyordu: (1) bekleyen
# isin dosyalari korumasiz kaliyor, (2) gorev `hazir`a donuyor ve cevap
# gelince is SIFIRDAN kosuyordu -- `soru_sor` kapisinin tasarrufu geri
# odeniyordu. CLAUDE.md "kilit onda kalir" diyordu; olculunce kalmiyordu.
# **Yanlis oldugu olculmemis bir kural, kural degil varsayimdir.**
import datetime as _dt

_kok2 = Path(tempfile.mkdtemp(prefix="ofis-kira-"))
_db2 = Veritabani(_kok2 / "o.sqlite3")
_o2 = Ofis.proje_ac(_db2, "Kira", amac="a", basari_olcutu="b")
_k2 = _o2.kanat_ac("U", "U")
for _ad in ("cinar", "yaprak"):
    _o2.kadro.ise_al(_ad, "backend", kanat_id=_k2, tur="eller", motor="sahte",
                     klasor=str(_kok2 / _ad))

def _is_kur(ajan, alan):
    _g = _o2.tahta.gorev_ac(f"Is {alan}", neden="n", ana_hedef="h",
                            kabul_olcutu="k", govde="g", kanat_id=_k2,
                            yazma_alani=[alan])
    _o2.tahta.sahiplen(_g["no"], ajan, _g["revizyon"])
    return _g["no"]

_bekleyen = _is_kur("cinar", "api1/")
_o2.postane.soru_sor("cinar", "insan", "Hangi yol?", gorev_no=_bekleyen)
_sessiz = _is_kur("yaprak", "api2/")

_eski = (_dt.datetime.now(_dt.UTC) - _dt.timedelta(seconds=400)).strftime(
    "%Y-%m-%dT%H:%M:%SZ")
with _db2.baglanti() as _c:
    _c.execute("UPDATE yazma_kilidi SET son_nabiz = ?", (_eski,))
_o2.tahta.kilit_dusenleri_temizle()

_gb = _o2.tahta.gorev(_bekleyen)
_gs = _o2.tahta.gorev(_sessiz)
sina("bekleyen ajanin kilidi DUSMEDI", _gb["durum"] == "calisiyor",
     f"({_gb['durum']})")
sina("bekleyen ajan gorevin SAHIBI kaldi", _gb["sahip"] == "cinar")
sina("SEBEPSIZ susan ajanin isi SERBEST kaldi", _gs["durum"] == "hazir",
     f"({_gs['durum']})")
sina("sebepsiz susanin sahipligi kalkti", _gs["sahip"] == "")

# Cevap gelince kilit yine dusebilmeli -- ajan artik durdurulmus degil.
for _m in _o2.postane.insan_bekleyenler():
    _o2.postane.cevapla(_m["id"], "Cevap")
_o2.tahta.kilit_dusenleri_temizle()
sina("cevap gelince koruma KALKIYOR (sonsuz kilit yok)",
     _o2.tahta.gorev(_bekleyen)["durum"] == "hazir")

# ---------------------------------------- YAZMA ALANI KOKTE VAR MI
print("")
print("YAZMA ALANI proje kokunde var mi (21.09.2026, $2'lik ders)")
# Olculdu: hedefte "ofis/motor icine kur" yazdim, lider onu yazma
# alani yapti, tahta KABUL ETTI ve is uc tur kostu. Ama proje koku
# .../AgentOfis/calisma -- `kok/ofis/motor` diye bir yer YOK. Ajan
# bunu turun ORTASINDA kesfetti ve bir "PROVA paketi" uydurmak
# zorunda kaldi: is yapilmis GORUNDU, hicbir yere kurulmadi.
_kok2 = Path(tempfile.mkdtemp(prefix="ofis-alan-"))
(_kok2 / "proje").mkdir()
(_kok2 / "proje" / "kaynak").mkdir()
(_kok2 / "disarida").mkdir()          # kokun DISINDA, kardes
_o2 = Ofis.proje_ac(Veritabani(_kok2 / "proje" / "o.sqlite3"), "Alan",
                    amac="a", basari_olcutu="b",
                    kok_klasor=str(_kok2 / "proje"))

def _acilir_mi(alan):
    try:
        _o2.tahta.gorev_ac("t", neden="n", ana_hedef="h",
                           kabul_olcutu="k", yazma_alani=[alan])
        return True, ""
    except TahtaHatasi as exc:
        return False, str(exc)

# (a) Kokte VAR -> sessizce gecer.
ok, _ = _acilir_mi("kaynak/yeni.py")
sina("kokte olan alan KABUL", ok)

# (b) Kokte yok ama kokun DISINDA ayni ad VAR -> guclu isaret, RED.
ok, mesaj = _acilir_mi("disarida/x.py")
sina("kokun DISINDA olan alan REDDEDILDI", not ok)
sina("  ret NEDEN oldugunu soyluyor", "DISINDA" in mesaj, mesaj[:80])
sina("  kokte NE oldugunu sayiyor", "kaynak" in mesaj, mesaj[:80])

# (c) Hicbir yerde yok -> yeni klasor acmak MESRU, gecer AMA uyarir.
#     Emin olmadigimiza "yanlis" demeyiz; sessiz de kalmayiz.
ok, _ = _acilir_mi("bambaska/yeni.py")
sina("hicbir yerde olmayan alan GECER (yeni olabilir)", ok)
with _o2.db.baglanti() as _c:
    _uy = [dict(r) for r in _c.execute(
        "SELECT * FROM olay WHERE tur='uyari' AND govde LIKE '%bambaska%'")]
sina("  ama GORUNUR bir uyari yaziliyor", len(_uy) == 1, str(len(_uy)))



# ---------------------------------------------------------------------------
# IPTAL -- ULASILABILIR AMA YONTEMI OLMAYAN DURUM, SIZDIRAN DURUMDUR
#
# `IPTAL` `DURUMLAR` icinde gecerliydi ama ona geciren hicbir yontem yoktu.
# Yani duruma ancak elle SQL ile girilebiliyordu ve o yolda kilit birakan
# da yoktu. Gercek ofiste tam bu oldu: #17 `iptal`di, iki kilidi
# duruyordu, `ofis/motor` alani baska bir ise SEBEPSIZ kapaliydi.
# ---------------------------------------------------------------------------
print("\n-- iptal: kilitler birakiliyor mu --")

_ikok = Path(tempfile.mkdtemp(prefix="ofis-iptal-"))
_ik = Ofis.proje_ac(Veritabani(_ikok / "o.sqlite3"), "Iptal",
                    amac="a", basari_olcutu="b")
_ikn = _ik.kanat_ac("URUN", "UR")
_ik.kadro.ise_al("ip", "backend", kanat_id=_ikn,
                 klasor=str(_ikok / "ip"), motor="sahte")
_ig = _ik.tahta.gorev_ac("yarim is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["api/"],
                         kanat_id=_ikn)
_ik.tahta.sahiplen(_ig["no"], "ip", _ig["revizyon"])


def _kilit_sayisi(o, gorev_id):
    with o.db.baglanti() as c:
        return c.execute(
            "SELECT COUNT(*) n FROM yazma_kilidi WHERE gorev_id = ?",
            (gorev_id,)).fetchone()["n"]


sina("kurgu: is kilitli", _kilit_sayisi(_ik, _ig["id"]) == 1)

# Sebep ZORUNLU: gerekcesiz iptal, "bu is neden yarim kaldi" sorusunu
# alti ay sonra cevapsiz birakir.
try:
    _ik.tahta.iptal_et(_ig["no"], sebep="   ", iptal_eden="insan")
    sina("sebepsiz iptal reddediliyor", False)
except TahtaHatasi:
    sina("sebepsiz iptal reddediliyor", True)
sina("reddedilen iptal durumu DEGISTIRMEDI",
     _ik.tahta.gorev(_ig["no"])["durum"] == "calisiyor")

_ik.tahta.iptal_et(_ig["no"], sebep="hedef yanlis yazilmisti",
                   iptal_eden="insan")
sina("iptal durumu yaziliyor",
     _ik.tahta.gorev(_ig["no"])["durum"] == "iptal")
sina("IPTAL KILITLERI BIRAKIYOR (olu is dosyalari rehin tutmaz)",
     _kilit_sayisi(_ik, _ig["id"]) == 0)

# Asil kazanc: alan gercekten SERBEST mi.
_ig2 = _ik.tahta.gorev_ac("yeni is", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["api/"],
                          kanat_id=_ikn)
# Cakisma ISTISNASI yakalanir: mutasyon sinaminda kilit birakilmayinca
# `sahiplen` patlar ve test COKER. Coken bir test, kaldigini SOYLEYEN
# bir testten kotudur -- geri kalan sinamalar hic kosmaz.
try:
    _ik.tahta.sahiplen(_ig2["no"], "ip", _ig2["revizyon"])
    _alan_serbest = _ik.tahta.gorev(_ig2["no"])["durum"] == "calisiyor"
    _alan_not = ""
except KilitCakismasi as _exc:
    _alan_serbest, _alan_not = False, f"-- {str(_exc)[:70]}"
sina("iptalden sonra AYNI ALAN yeniden alinabiliyor",
     _alan_serbest, _alan_not)

# ZATEN IPTAL OLANI DA TEMIZLER.
# Ilk surum burada erken donuyordu ve GERCEK ofiste ise yaramadi: #17
# zaten `iptal`di (elle yapilmisti) ve kilitleri tam bu yuzden
# duruyordu. Erken donen bir temizleyici, temizlemesi gereken tek
# durumu atliyordu. Bu yontem YAN ETKISI icin cagrilir; durum zaten
# dogruysa yan etkinin de dogru oldugunu VARSAYAMAYIZ.
_ig3 = _ik.tahta.gorev_ac("elle iptal", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["web/"],
                          kanat_id=_ikn)
_ik.tahta.sahiplen(_ig3["no"], "ip", _ig3["revizyon"])
with _ik.db.baglanti() as _c:
    _c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (_ig3["id"],))
sina("kurgu: elle iptal edilmis isin kilidi DURUYOR",
     _kilit_sayisi(_ik, _ig3["id"]) == 1)
_ik.tahta.iptal_et(_ig3["no"], sebep="kilitleri temizle", iptal_eden="insan")
sina("ZATEN iptal olanin kilitleri de birakiliyor",
     _kilit_sayisi(_ik, _ig3["id"]) == 0)

# BITMIS is iptal EDILEMEZ: kanit kapisindan gecmis bir hukmu sessizce
# bozmak olurdu.
_ig4 = _ik.tahta.gorev_ac("bitmis", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["ops/"],
                          kanat_id=_ikn)
_ik.tahta.sahiplen(_ig4["no"], "ip", _ig4["revizyon"])
_ik.tahta.kanit_ekle(_ig4["no"], "terminal", "pytest", "1 passed", "ip")
_ig4 = _ik.tahta.gorev(_ig4["no"])
_ik.tahta.kapat(_ig4["no"], _ig4["revizyon"], kapatan="insan")
try:
    _ik.tahta.iptal_et(_ig4["no"], sebep="vazgectim", iptal_eden="insan")
    sina("BITMIS is iptal edilemiyor", False)
except TahtaHatasi:
    sina("BITMIS is iptal edilemiyor", True)

# Iptal bir OLAYDIR: "bu is neden yarim kaldi" alti ay sonra da
# cevaplanabilmeli.
with _ik.db.baglanti() as _c:
    _n = _c.execute(
        "SELECT COUNT(*) n FROM olay WHERE proje_id = ? AND tur = 'iptal'",
        (_ik.proje_id,)).fetchone()["n"]
sina("iptal deftere yaziliyor (sebebiyle)", _n >= 2, f"({_n})")



# ---------------------------------------------------------------------------
# MUTLAK YAZMA ALANI -- Yasa 1'i SESSIZCE deliyordu
#
# Olculdu (21.09.2026): lider `C:/.../AgentOfis/KILAVUZ.md` diye MUTLAK
# bir alan yazdi. Iki ayri sey birden bozuldu:
#
#   1. `kok / mutlak` pathlib'de koku TAMAMEN atar -> kok denetimi hic
#      calismadi; `C:/Windows/System32` bile gecerdi.
#   2. Kilit ONEK eslesmesiyle calisir; mutlak yol oldugu gibi
#      saklaninca ayni dosyayi gosteren `KILAVUZ.md` ile CAKISMADI.
#      Iki is ayni dosyaya yazabilir, kilit makinesi HIC gormez.
# ---------------------------------------------------------------------------
print("\n-- mutlak yazma alani: Yasa 1 deliniyor mu --")

import tempfile as _mtf
from pathlib import Path as _mP
from ofis import Ofis as _mOfis, Veritabani as _mVt

_mkok = _mP(_mtf.mkdtemp(prefix="ofis-mutlak-"))
(_mkok / "proje").mkdir()
(_mkok / "disarida").mkdir()
_mo = _mOfis.proje_ac(_mVt(_mkok / "proje" / "o.sqlite3"), "Mutlak",
                      amac="a", basari_olcutu="b",
                      kok_klasor=str(_mkok / "proje"))
_mkn = _mo.kanat_ac("URUN", "UR")
for _ad in ("m1", "m2"):
    _mo.kadro.ise_al(_ad, "backend", kanat_id=_mkn,
                     klasor=str(_mkok / "proje"), motor="sahte")

# 1) Kokun ALTINDAKI mutlak yol KOK-GORELI saklanir.
_mg1 = _mo.tahta.gorev_ac("m-t1", neden="n", ana_hedef="h", kabul_olcutu="k",
                          yazma_alani=[str(_mkok / "proje" / "KILAVUZ.md")],
                          kanat_id=_mkn)
sina("kokun altindaki MUTLAK alan kok-goreli saklaniyor",
     _mg1["yazma_alani"] == ["KILAVUZ.md"], f"({_mg1['yazma_alani']})")

# 2) ASIL SORU: mutlak ile goreli artik CAKISIYOR mu.
_mo.tahta.sahiplen(_mg1["no"], "m1", _mg1["revizyon"])
_mg2 = _mo.tahta.gorev_ac("m-t2", neden="n", ana_hedef="h", kabul_olcutu="k",
                          yazma_alani=["KILAVUZ.md"], kanat_id=_mkn)
try:
    _mo.tahta.sahiplen(_mg2["no"], "m2", _mg2["revizyon"])
    sina("MUTLAK ile GORELI ayni dosya sayiliyor (Yasa 1)", False,
         "-- sessizce izin verildi, kilit cakismayi gormedi")
except KilitCakismasi:
    sina("MUTLAK ile GORELI ayni dosya sayiliyor (Yasa 1)", True)

# 3) Kokun DISINDAKI mutlak yol reddedilir -- kok denetimini atlayamaz.
reddetmeli("sistem klasoru mutlak yolla GECEMIYOR",
           lambda: _mo.tahta.gorev_ac("m-t3", neden="n", ana_hedef="h",
                                      kabul_olcutu="k",
                                      yazma_alani=["C:/Windows/System32/x.dll"],
                                      kanat_id=_mkn),
           TahtaHatasi)

# 4) Ama ACILAN klasordeki mutlak yol GECER -- kapiyi asiri sikmak,
#    mesru bir isi durdurmak olurdu.
_mg4 = _mo.tahta.gorev_ac("m-t4", neden="n", ana_hedef="h", kabul_olcutu="k",
                          yazma_alani=[str(_mkok / "disarida" / "x.md")],
                          kanat_id=_mkn,
                          ek_klasorler=[str(_mkok / "disarida")])
sina("acik klasordeki mutlak yol GECIYOR",
     bool(_mg4["yazma_alani"]), f"({_mg4['yazma_alani']})")
# Kokun disinda kaldigi icin MUTLAK kalir: baska bir agac, kok-goreli
# bir yolla zaten karisamaz.
sina("kokun disindaki alan MUTLAK birakiliyor",
     _mP(_mg4["yazma_alani"][0]).is_absolute(), f"({_mg4['yazma_alani']})")


print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"veritabani: {gecici}")
sys.exit(1 if KALAN else 0)
