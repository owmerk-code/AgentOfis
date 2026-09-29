# -*- coding: utf-8 -*-
"""Panel duman testi: API sozlesmesi ve guvenlik kapilari.

Sinanan sey arayuzun GORUNUSU degil, altindaki sozlesme:
oda dogru turetiliyor mu · panel karar veriyor mu (vermemeli) ·
`0.0.0.0` reddediliyor mu · yol enjeksiyonu kapali mi · gerekcesiz ret
panelden gecebiliyor mu.

Arayuzun kendisi tarayicida gozle dogrulanir; burada olcultebilir olan
sinanir.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from ofis import Ofis, Veritabani
from ofis.panel import olustur, kos, SUTUNLAR

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


print("== panel duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-panel-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Panel Projesi", amac="Paneli sinamak",
                     basari_olcutu="Sozlesme tutuyor")
kanat = ofis.kanat_ac("URUN", "UR")
kanat2 = ofis.kanat_ac("PAZARLAMA", "PZ")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(kok / "demir"), motor="sahte")
ofis.kadro.ise_al("ruzgar", "lider", lider_mi=True, kanat_id=kanat2,
                  klasor=str(kok / "ruzgar"), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", kanat_id=kanat,
                  klasor=str(kok / "cinar"), motor="sahte")
ofis.kadro.ise_al("bilge", "arastirma", kanat_id=kanat, tur="kafa",
                  klasor=str(kok / "bilge"), motor="sahte")
ofis.bellek.olgu_yaz("konu", "eski deger")
ofis.bellek.olgu_yaz("konu", "yeni deger")          # devirir

g1 = ofis.tahta.gorev_ac("Calisan is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["api/"],
                         kanat_id=kanat)
ofis.tahta.sahiplen(g1["no"], "cinar", g1["revizyon"])
g2 = ofis.tahta.gorev_ac("Incelemedeki is", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["web/"],
                         kanat_id=kanat)
ofis.tahta.sahiplen(g2["no"], "bilge", g2["revizyon"]) if False else None

istemci = TestClient(olustur(db_yolu))

# GERCEK MOTOR YASAK. Panel artik insan cevap verince halkayi KENDISI
# dondurebiliyor (`surdur`); bir sinama yanlislikla gercek motora uzanirsa
# kullanicinin hesabindan yer. Bu fabrika yalniz `sahte`yi uretir, gerisi
# PATLAR -- zincir musaitlik sorarken istisnayi "kurulu degil" sayar, yani
# gercek motorlar testte YOK hukmundedir. *Bir test kullanicinin parasina
# dokunamamali.*
import ofis.panel as _P
from ofis.motor.sahte import SahteMotor as _Sahte


def _yalniz_sahte(ad, **kw):
    if str(ad).strip().lower() != "sahte":
        raise RuntimeError(f"SINAMA gercek motora uzandi: {ad}")
    return _Sahte(**kw)


_P.MOTOR_FABRIKASI = _yalniz_sahte

# --------------------------------------------------------------------------
print("1. OFIS GORUNTUSU")
o = istemci.get("/api/ofis").json()
sina("proje donuyor", o["proje"]["ad"] == "Panel Projesi")
sina("kanatlar donuyor", len(o["kanatlar"]) == 2)
sina("bes sutun sayiliyor", set(o["sayim"]) == set(SUTUNLAR))
sina("motor durumu OLCULUYOR (uydurulmuyor)",
     isinstance(o["motorlar"], dict) and o["motorlar"]["sahte"] is True)
sina("baglam sagligi geliyor", "gecerli_olgu" in o["baglam"])
sina("devrilmis olgu AYRI sayiliyor", o["baglam"]["eski_olgu"] == 1)

# --------------------------------------------------------------------------
print("\n2. ODA TURETILIYOR (saklanmiyor)")
oda = {a["ad"]: a["oda"] for a in o["ajanlar"]}
sina("calisan ajan MASADA", oda["cinar"] == "masa")
sina("isi olmayan ajan MOLADA", oda["bilge"] == "mola")
sina("isi olmayan lider de MOLADA", oda["demir"] == "mola")

# lider kendi kanadinin incelemesine bakar
ofis.tahta.kanit_ekle(g1["no"], "terminal", "test", "9 passed", "cinar")
ofis.tahta.incelemeye_ver(g1["no"], ofis.tahta.gorev(g1["no"])["revizyon"])
oda = {a["ad"]: a["oda"] for a in istemci.get("/api/ofis").json()["ajanlar"]}
sina("kendi kanadinin lideri INCELEME ODASINDA", oda["demir"] == "inceleme")
sina("BASKA kanadin lideri inceleme odasina GIRMIYOR", oda["ruzgar"] == "mola",
     "-- kanat filtresi yok!")

# soru sorunca bekleme odasi
# Iki soru, iki ayri alici: biri INSANA (onun eylem kuyruguna dusmeli),
# biri AJANA (ofis kendi cozer; insana gosterilir ama cevaplatilmaz).
ofis.postane.soru_sor("cinar", "insan", "Bir sorum var", gorev_no=g1["no"])
ofis.postane.soru_sor("cinar", "demir", "Lidere sorum var", gorev_no=g1["no"])
oda = {a["ad"]: a["oda"] for a in istemci.get("/api/ofis").json()["ajanlar"]}
sina("soru soran ajan BEKLEME ODASINDA", oda["cinar"] == "bekleme")
sina("gorev durumu DEGISMEDI (bekleme turetilmis hal)",
     ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")

onay = ofis.postane.onay_iste("bilge", "Riskli bir sey", risk="yuksek")
oda = {a["ad"]: a["oda"] for a in istemci.get("/api/ofis").json()["ajanlar"]}
sina("onay bekleyen ajan ONAY KAPISINDA", oda["bilge"] == "onay_kapisi")

# -- KAT PLANININ BESLENDIGI ALANLAR ---------------------------------------
# Piksel kat plani uc seyi cizer ve UCU DE OLCUME BAGLIDIR: ajanin odasi,
# balonundaki not, ve asma kilit. Kilit BIZE OZGU -- rakipte karsiligi yok
# ve ofis gorunumunde gorunmesi Yasa 1'i ekrana tasiyan sey.
#
# Burasi bir arayuz testi degil, BESLEME testi: alan API'den gelmezse
# kat planinda sessizce hicbir sey cizilmez. *Sessizce yok sayilan ayar,
# ayar degildir.*
ajanlar = {a["ad"]: a for a in istemci.get("/api/ofis").json()["ajanlar"]}
sina("her ajan `oda` tasiyor",
     all("oda" in a for a in ajanlar.values()))
sina("her ajan `sicil` tasiyor",
     all(isinstance(a.get("sicil"), dict) for a in ajanlar.values()))
sina("KILIT ajan yukune ulasiyor (kat planinin asma kilidi)",
     ajanlar["cinar"]["sicil"]["kilit"] == ["api"],
     ajanlar["cinar"]["sicil"]["kilit"])
sina("kilitsiz ajanin kilidi BOS (uydurmuyor)",
     ajanlar["bilge"]["sicil"]["kilit"] == [])
sina("balonun besledigi `not` alani var",
     all("not" in a for a in ajanlar.values()))

# -- KULLANIM KARTI: OLCULMUS SIFIR ile OLCULEMEMIS ayri --------------------
# Bu ayrim kartin tek kritik kurali. `maliyet_usd = 0.0` gercek bir
# olcumdur (sahte motor, ya da tamamen onbellekten donen tur); `None`
# ise motorun HIC bildirmedigidir. Ikisini toplarken ayni saymak,
# bilinmeyen maliyeti sifir ilan etmektir -- *gorunmeyen butce, butce
# degildir* kuralinin sessizce delinmesi.
import json as _j
from ofis.panel import _kullanim


def _satir(gorev_no, **alan):
    return {"govde": _j.dumps(alan), "gorev_no": gorev_no}


k = _kullanim([
    _satir(1, jeton=100, maliyet_usd=0.0),     # OLCULMUS sifir
    _satir(1, jeton=200, maliyet_usd=0.5),
    _satir(1, jeton=300, maliyet_usd=None),    # OLCULEMEMIS
])
sina("jeton toplaniyor", k["tum"]["jeton"] == 600, k["tum"]["jeton"])
sina("olculmus 0.0 FIYATLI sayiliyor", k["tum"]["fiyatli"] == 2,
     k["tum"]["fiyatli"])
sina("olculemeyen tur FIYATSIZ sayiliyor", k["tum"]["fiyatsiz"] == 1)
sina("toplam yalniz FIYATLI turlari icerir",
     abs(k["tum"]["maliyet_usd"] - 0.5) < 1e-9, k["tum"]["maliyet_usd"])
sina("ise gore kirilim var", k["ise_gore"][1]["tur"] == 3)

hic = _kullanim([_satir(2, jeton=50, maliyet_usd=None)])
sina("HICBIRI fiyatlanamadiysa toplam None -- 0.0 DEGIL",
     hic["tum"]["maliyet_usd"] is None, repr(hic["tum"]["maliyet_usd"]))
sina("fiyatlanamayan turda jeton yine sayilir", hic["tum"]["jeton"] == 50)

sifir = _kullanim([_satir(3, jeton=10, maliyet_usd=0.0)])
sina("yalniz olculmus sifir varsa toplam 0.0 -- None DEGIL",
     sifir["tum"]["maliyet_usd"] == 0.0 and sifir["tum"]["fiyatli"] == 1)

sina("gorevsiz tur (gorev_no None) kirilima girmez, toplama girer",
     _kullanim([_satir(None, jeton=7, maliyet_usd=0.1)])["ise_gore"] == {})

# --------------------------------------------------------------------------
print("\n3. TAHTA")
t = istemci.get("/api/tahta").json()
sina("bes sutun donuyor", set(t) == set(SUTUNLAR))
kart = t["inceleme"][0]
sina("kart kilidi GORUNUR", kart["kilitli"] is True)
sina("kart yazma alanini tasiyor", kart["yazma_alani"] == ["api"])
sina("kart kanit sayisini tasiyor", kart["kanit"] == 1)
t2 = istemci.get("/api/tahta?kanat=" + kanat2).json()
sina("kanat filtresi calisiyor",
     sum(len(v) for v in t2.values()) == 0)

# --------------------------------------------------------------------------
print("\n4. GOREV DETAYI")
d = istemci.get(f"/api/gorev/{g1['no']}").json()
sina("kanitlar detayda", len(d["kanitlar"]) == 1)
sina("brifing jetonu detayda", d["brifing"] is None or "jeton_tahmini" in d["brifing"])
sina("olmayan gorev 404", istemci.get("/api/gorev/999").status_code == 404)

# --------------------------------------------------------------------------
print("\n5. HAFIZA -- eski olgu SILINMEZ ama AYRILIR")
h = istemci.get("/api/hafiza").json()
sina("gecerli olgu ayri", [x["icerik"] for x in h["gecerli"]] == ["yeni deger"])
sina("devrilmis olgu GORUNUYOR ama ayri", h["eski"][0]["icerik"] == "eski deger")

# --------------------------------------------------------------------------
print("\n6. INSANIN MUDAHALESI")
sorular = istemci.get("/api/bekleyenler").json()["sorular"]
y = istemci.post(f"/api/soru/{sorular[0]['id']}/cevap",
                 json={"metin": "Cevabim", "surdur": False})
sina("soru cevaplanabiliyor", y.status_code == 200)
sina("cevaplanan soru kuyruktan cikti",
     istemci.get("/api/bekleyenler").json()["sorular"] == [])

# AJANA sorulan soru insanin EYLEM kuyruguna girmez ama GORUNUR:
# ayni kuyruga koymak insana kendisine dusmeyen isi gosterirdi,
# tamamen gizlemek ise ofisi sessiz kilardi.
bek = istemci.get("/api/bekleyenler").json()
sina("ajana sorulan soru insanin kuyruguna DUSMEDI",
     all(x["alici"] == "insan" for x in bek["sorular"]))
sina("ajana sorulan soru ayri anahtarda GORUNUYOR",
     any(x["alici"] == "demir" for x in bek["danisilanlar"]))

# -- ZIYARET: soran ajan SORULANIN yanina yurur ----------------------------
# Ofis haritasi ajana soru soran ajani sorulanin masasina/odasina
# yurutur; bunu `kime` besler. Alan gelmezse harita soran HER ajani
# bekleme odasina koyar ve "lidere mi sordu, sana mi" ayrimi ekrandan
# SESSIZCE kaybolur. Insana sorulan soru az once cevaplandi: cinar'in
# bekleyen tek sorusu artik demir'e.
ajanlar = {a["ad"]: a for a in istemci.get("/api/ofis").json()["ajanlar"]}
sina("ajana soru soran ajanin `kime`si O AJAN",
     ajanlar["cinar"]["oda"] == "bekleme"
     and ajanlar["cinar"].get("kime") == "demir",
     f'{ajanlar["cinar"]["oda"]} / {ajanlar["cinar"].get("kime")!r}')
sina("onay bekleyenin `kime`si insan", ajanlar["bilge"].get("kime") == "insan")
# "Yok" ile "bos" ayirt edilebilmeli: alan HER ajanda var, beklemeyende bos.
sina("`kime` HER ajanda var",
     all("kime" in a for a in ajanlar.values()))
sina("beklemeyen ajanin `kime`si BOS (uydurmuyor)",
     ajanlar["ruzgar"]["kime"] == "", repr(ajanlar["ruzgar"].get("kime")))

# Gerekcesiz ret PANELDEN DE gecmemeli: kural cekirdekte, panel atlatamaz.
y = istemci.post(f"/api/onay/{onay['id']}", json={"onayla": False, "not_": ""})
sina("gerekcesiz RET panelden de REDDEDILIYOR", y.status_code == 400,
     f"-- {y.status_code}")
sina("onay hala kuyrukta",
     len(istemci.get("/api/bekleyenler").json()["onaylar"]) == 1)
y = istemci.post(f"/api/onay/{onay['id']}",
                 json={"onayla": False, "not_": "Butce yok", "surdur": False})
sina("gerekceli ret geciyor", y.status_code == 200)

# -- KOMUT CUBUGU GERCEKTEN KOSTURUYOR MU ----------------------------------
# OLCULMUS KUSUR (21.09.2026): bu uc yalnizca `mesaj` tablosuna satir
# yaziyordu ve HICBIR SEY onu kosturmuyordu. Insan yaziyor, hata almiyor,
# hicbir sey olmuyordu -- gorunur bir eylem sunup arkasinda kosturan
# koymamak, olmayan bir dugme cizmektir.
import time as _t
from ofis.motor.sahte import SahteMotor

_P.MOTOR_FABRIKASI = lambda ad, **kw: SahteMotor(
    cevap='{"yol": "cevap", "gerekce": "bilgi sorusu", '
          '"cevap": "Ofiste 4 ajan var."}')
try:
    # COK LIDERLI OFIS: kanat verilmeden SESSIZCE biri secilmez.
    # Ilk surumum `kadro[0]` aliyordu -- isi yanlis kanada vermenin en
    # sessiz yolu; panelde hicbir sey yanlis gorunmezdi.
    # 29.09 (GENEL KANAL): ret yerine ONERI doner -- ofis yine SECMEZ,
    # lider kosmaz, insan takimi secer.
    y0 = istemci.post("/api/lidere", json={"metin": "kanatsiz"})
    j0 = y0.json() if y0.status_code == 200 else {}
    sina("cok liderli ofiste KANATSIZ istek: ofis SECMEZ, oneri doner",
         j0.get("yol") == "oneri" and j0.get("kosuyor") is False, y0.text[:160])
    sina("  oneri secilecek takimlari sayiyor", bool(j0.get("oneriler")))

    y = istemci.post("/api/lidere",
                     json={"metin": "Ofiste ne durumdayiz?", "kanat": kanat})
    sina("lidere mesaj gidiyor", y.status_code == 200, y.text[:120])
    sina("mesaj LIDERE ulasti", y.json()["alici"] in ("demir", "ruzgar"))
    sina("cevap KOSTUGUNU soyluyor", y.json().get("kosuyor") is True)
    # TAVAN ZORUNLU: panelde klavyenin basinda kimse yok.
    # 27.09 KARARI: abonelikte dolar tavani yok; kacagi ofis freni durdurur.
    sina("panel turlarinda DOLAR tavani yok", "tavan_usd" not in y.json()
         and _P.PANEL_TUR_TAVANI_USD is None)

    # TEK UCUS: ikinci istek REDDEDILIR. Cift tiklama jetonu ikiye
    # katlar ve iki lider ayni ise ayri kararlar verir.
    y2 = istemci.post("/api/lidere",
                      json={"metin": "Bir daha", "kanat": kanat})
    sina("ikinci lider turu REDDEDILIYOR (tek ucus)", y2.status_code == 409,
         str(y2.status_code))

    # Gercekten kostu mu: lider turu bir `tur_ozeti` birakmali.
    #
    # BEKLEME SURESI OLCULDU, tahmin degil: tur ~9 saniye suruyor ve
    # bunun cogu triyajdaki `claude mcp list` baglayici olcumu (onbellege
    # girene kadar). Kisa bir bekleme, CALISAN bir ozelligi bozuk
    # gosterirdi -- ilk surumum 6 saniye bekliyordu ve tam bunu yapti.
    n = 0
    for _ in range(600):
        with ofis.db.baglanti() as c:
            n = c.execute("SELECT COUNT(*) n FROM olay WHERE tur='tur_ozeti'"
                          ).fetchone()["n"]
        if n:
            break
        _t.sleep(0.1)
    sina("panelden baslatilan lider GERCEKTEN kostu", n > 0,
         "-- komut cubugu hicbir seyi kosturmuyor")

    # INSANIN MESAJI BIR KEZ yaziliyor. Uc de yazip `Sohbet.konus` da
    # yazinca deftere IKI kez dusuyordu (olculdu) ve liderin baglami
    # "son 6 konusma" ozetinden geldigi icin kopya onu dogrudan kirletir.
    with ofis.db.baglanti() as c:
        kopya = c.execute(
            "SELECT COUNT(*) n FROM mesaj WHERE gonderen='insan' "
            "AND govde LIKE '%Ofiste ne durumdayiz%'").fetchone()["n"]
    sina("insanin mesaji BIR kez yazildi", kopya == 1, f"{kopya} kez")

    for _ in range(600):
        if not istemci.get("/api/lider-durum").json()["calisiyor"]:
            break
        _t.sleep(0.1)
    sina("kosu bitince nobetci SERBEST kaliyor",
         istemci.get("/api/lider-durum").json()["calisiyor"] is False,
         "-- kilit takili kaldi, panel bir daha is alamaz")
finally:
    _P.MOTOR_FABRIKASI = _yalniz_sahte


def _kosu_bitsin(sn=60.0):
    for _ in range(int(sn * 10)):
        if not istemci.get("/api/lider-durum").json()["calisiyor"]:
            return True
        _t.sleep(0.1)
    return False


# -- OGE SECICI: kabinde isaret edilen oge lidere GIDIYOR --------------------
# Secilen ogenin bilgisi DEFTERE ve bir MODELE gider. Istemciden gelen oge
# guvenilmez girdidir: sunucu yeniden suzer, metni kendisi kurar.
_P.MOTOR_FABRIKASI = lambda ad, **kw: SahteMotor(
    cevap='{"karar": "cevap", "gerekce": "bilgi sorusu", "cevap": "Tamam."}')
# Kabin KAPALI sahnesi ACIKCA kurulur. 30.09 olculdu: kullanici kendi
# kabinini acinca bu sinama kaldi -- gercek 9222'ye bakiyordu.
from ofis import kabin as _kb_mod  # noqa: E402
_kb_durum_asil = _kb_mod.Kabin.durum
_kb_mod.Kabin.durum = lambda self, *a, **k: {"acik": False}
try:
    _oge = {"etiket": "button", "secici": "#al", "essiz": True,
            "metin": "Satin al", "url": "https://a.com/sepet?sid=TOKSIR9",
            "nitelik": {"value": "sifre-degeri", "href": "/x?tok=TOKSIR8"},
            "kutu": {"x": 0.1, "y": 0.1, "en": 0.1, "boy": 0.05}}
    y = istemci.post("/api/lidere", json={"metin": "bu dugmenin rengini kontrol et",
                                          "kanat": kanat, "oge": _oge})
    sina("oge ile lidere yazmak kabul ediliyor", y.status_code == 200, y.text[:160])
    sina("  isaret edilen sayfanin KAYNAGI tarayici alani oluyor",
         y.json().get("tarayici") == ["https://a.com"], y.text[:160])
    sina("  kabin kapaliyken 'paylasildi' DENMIYOR", y.json().get("kabin") is False)
    sina("oge ile kosu bitti", _kosu_bitsin())
    with ofis.db.baglanti() as c:
        _mg = [r["govde"] for r in c.execute(
            "SELECT govde FROM mesaj WHERE gonderen='insan' AND govde LIKE "
            "'%bu dugmenin rengini%'").fetchall()]
        _ot = [r["govde"] for r in c.execute(
            "SELECT govde FROM olay WHERE tur='tarayici_alani' AND govde LIKE "
            "'%Patron mesaji%'").fetchall()]
    sina("mesaja SECILEN OGE blogu eklendi (sunucu kurdu)",
         len(_mg) == 1 and "KABINDE SECILEN OGE" in _mg[0] and "#al" in _mg[0],
         str(_mg)[:300])
    sina("  deftere SIR dusmedi (sorgu, value)",
         # Isaret AYIRT EDICI olmali: ilk surum "GIZLI" ariyordu ve blogun
         # kendi "GIZLILIK" kelimesine takildi -- sizinti yokken kaldi.
         bool(_mg) and "TOKSIR" not in _mg[0] and "sifre-degeri" not in _mg[0],
         str(_mg)[:300])
    sina("  tarayici acilisi KAYDA gecti (cevap yolunda bile)",
         any("https://a.com" in g for g in _ot), str(_ot))
    y = istemci.post("/api/lidere", json={"metin": "x", "kanat": kanat,
                                          "oge": {"etiket": "<script>"}})
    sina("bozuk oge REDDEDILIYOR (sessizce dusurulmuyor)", y.status_code == 400,
         y.text[:120])
finally:
    _P.MOTOR_FABRIKASI = _yalniz_sahte
    _kosu_bitsin()
    _kb_mod.Kabin.durum = _kb_durum_asil

_js_o = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
_bas = _js_o.index("img.onmousedown")
_govde = _js_o[_bas:_js_o.index("img.onmouseup", _bas)]
sina("SECIM KIPINDE fare sayfaya GITMIYOR (secKipi 'fare'den ONCE)",
     "K.secKipi" in _govde and _govde.index("K.secKipi") < _govde.index('tur: "fare"'))
sina("secilen oge lidere gidiyor", "oge: D.secilenOge" in _js_o)
_py_o = (Path(__file__).resolve().parent.parent / "ofis" / "panel.py").read_text(encoding="utf-8")
sina("oge ifadesi SUNUCUDA kuruluyor (istemciden ifade alinmiyor)",
     "kabin.oge_ifadesi(" in _py_o and '"expression": istek' not in _py_o)
sina("sayfadan donen oge de SUZULUYOR", "kabin.oge_ozeti(deger" in _py_o)


# --------------------------------------------------------------------------
print("\n6b. PANEL EYLEMLERI -- CLI'ya yollamadan karar")
# OLCULMUS KUSUR (23.09.2026): panel onay ve soru cevaplatiyor ama isi
# SURDURECEK bir sey yoktu (kabuk "`kabuk devam`" diyordu, panelde dugme
# yoktu); ekip ve guncelleme onerilerini sayip insani komut satirina
# yolluyordu; "is boyunca" onay ve gorev iptali yalniz CLI'daydi.

# -- onay KAPSAMI sunucuda dogrulanir -------------------------------------
o1 = ofis.postane.onay_iste("cinar", "Yayina al", risk="yuksek",
                            gorev_no=g2["no"])
o2 = ofis.postane.onay_iste("cinar", "Musteriye e-posta gonder", risk="orta",
                            gorev_no=g2["no"])
y = istemci.post(f"/api/onay/{o1['id']}",
                 json={"onayla": True, "kapsam": "hep", "surdur": False})
sina("bilinmeyen kapsam REDDEDILIYOR (sessizce 'eylem'e dusmuyor)",
     y.status_code == 400, str(y.status_code))
y = istemci.post(f"/api/onay/{o1['id']}", json={"onayla": True, "kapsam": "is"})
sina("'is boyunca' onayi panelden verilebiliyor",
     y.status_code == 200 and y.json().get("kapsam") == "is", y.text[:160])
# BASKA ISTEK BEKLERKEN HALKA DONMEZ ve sebebi SOYLENIR.
sina("baska istek beklerken halka SURDURULMUYOR",
     y.json().get("surduruldu") is False, y.text[:160])
sina("  ve sebebi soyleniyor (insan 'neden bir sey olmadi' diye sormamali)",
     "SENI bekliyor" in (y.json().get("sebep") or ""))
sina("varsayilan kapsam DAR: kapsam verilmeyen onay 'eylem'",
     _P.OnayGovdesi(onayla=True).kapsam == "eylem")

# SON istek cevaplaninca halka KENDILIGINDEN doner.
with ofis.db.baglanti() as c:
    _once = c.execute("SELECT COALESCE(MAX(rowid),0) n FROM olay").fetchone()["n"]
y = istemci.post(f"/api/onay/{o2['id']}", json={"onayla": True})
sina("SON istek cevaplaninca halka SURDURULUYOR",
     y.json().get("surduruldu") is True, y.text[:200])
sina("surdurulen halka kosuyor gorunuyor",
     istemci.get("/api/lider-durum").json()["calisiyor"] is True
     or _kosu_bitsin(0.1))
sina("halka bitince nobetci SERBEST", _kosu_bitsin(),
     "-- halka takili kaldi, panel bir daha is alamaz")
with ofis.db.baglanti() as c:
    _yeni = [r["tur"] for r in c.execute(
        "SELECT tur FROM olay WHERE rowid > ? ORDER BY rowid", (_once,)).fetchall()]
# KOSTUGU KAYITTAN OLCULUR. Ilk surum "kosuyor gorunuyor VEYA bitti"
# diyordu -- hic kosmayan bir halka da onu geciyordu (mutasyon gosterdi).
sina("halka GERCEKTEN kostu (defterde yeni tur_ozeti var)",
     "tur_ozeti" in _yeni, str(_yeni))
with ofis.db.baglanti() as c:
    dus = c.execute("SELECT COUNT(*) n FROM olay WHERE tur='hata' AND govde "
                    "LIKE 'Panelden baslatilan halka dustu%'").fetchone()["n"]
sina("halka DUSMEDI (hata olayi yok)", dus == 0, f"{dus} hata")

# -- /api/devam: elle surdur ---------------------------------------------
y = istemci.post("/api/devam")
sina("'surdur' dugmesi acik is varken kosturuyor",
     y.status_code == 200 and y.json().get("kosuyor") is True, y.text[:160])
y2 = istemci.post("/api/devam")
sina("ikinci 'surdur' TEK UCUS geregi reddediliyor (ya da ilki bitmis)",
     y2.status_code in (409, 200), str(y2.status_code))
_kosu_bitsin()

# -- DURDUR: yumusak, SESSIZ DEGIL ----------------------------------------
y = istemci.post("/api/durdur")
sina("kosan bir sey yokken 'durdur' 400 ve sebebini soyluyor",
     y.status_code == 400 and "Kosan bir sey yok" in y.text, y.text[:120])
# Zamanlamaya bagli olmasin: bayrak ONCEDEN kurulur, halka ESZAMANLI kosar.
with ofis.db.baglanti() as c:
    _once = c.execute("SELECT COALESCE(MAX(rowid),0) n FROM olay").fetchone()["n"]
_P._KOSU.update(calisiyor=True, dur=True, mesaj="sinama")
_P._halkayi_kostur(db_yolu, "")
with ofis.db.baglanti() as c:
    _dur = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE rowid > ? AND tur='uyari'", (_once,)).fetchall()]
sina("durdurulan halka DEFTERE yaziyor (sessiz durmuyor)",
     any("DURDURULDU" in x for x in _dur), str(_dur)[:160])
sina("durdurma sonrasi nobetci ve bayrak TEMIZ",
     _P._KOSU["calisiyor"] is False and _P._KOSU["dur"] is False, str(_P._KOSU))

# -- iptal: sebep zorunlu, kilitler OLCULEREK birakilir -------------------
acik = [g for g in ofis.tahta.liste() if g["durum"] not in ("bitti", "iptal")]
y = istemci.post(f"/api/gorev/{acik[0]['no']}/iptal", json={"sebep": ""})
sina("sebepsiz iptal REDDEDILIYOR", y.status_code == 400, str(y.status_code))
for g in acik:
    y = istemci.post(f"/api/gorev/{g['no']}/iptal",
                     json={"sebep": "sinama sahnesi temizleniyor"})
sina("gerekceli iptal geciyor", y.status_code == 200
     and y.json().get("durum") == "iptal", y.text[:160])
sina("iptal birakilan ve kalan kilitleri OLCUP soyluyor",
     "birakilan" in y.json() and y.json().get("kalan") == [], y.text[:160])
y = istemci.post("/api/devam")
sina("acik is yokken 'surdur' REDDEDILIYOR ve sebebini soyluyor",
     y.status_code == 400 and "Acik is yok" in y.text, y.text[:160])

# -- ekip onerisi panelden karara baglaniyor ------------------------------
e1 = ofis.ekip._sakla("sinama kadrosu", {"gerekce": "kadroda rol yok", "uyeler": [
    {"ad": "selin", "rol": "arayuz", "motor": "sahte", "gerekce": "arayuz yok"}]},
    "demir", kanat)
e2 = ofis.ekip._sakla("ikinci kadro", {"gerekce": "kadroda rol yok", "uyeler": [
    {"ad": "kerem", "rol": "kalite", "motor": "sahte", "gerekce": "test yok"}]},
    "demir", kanat)
on = istemci.get("/api/oneriler").json()
sina("bekleyen ekip onerileri panele geliyor (uyeleriyle)",
     len(on["ekip"]) == 2 and on["ekip"][0]["uyeler"][0]["ad"] == "selin",
     str(on)[:200])
sina("guncelleme onerileri ayri anahtarda", "guncelleme" in on)
y = istemci.post(f"/api/ekip/{e1['no']}/kur")
sina("ekip panelden KURULUYOR", y.status_code == 200
     and y.json()["alinan"][0]["ad"] == "selin", y.text[:160])
sina("  kurulan ajan GERCEKTEN kadroda",
     any(a["ad"] == "selin" for a in ofis.kadro.liste()))
y = istemci.post(f"/api/ekip/{e1['no']}/kur")
sina("ayni oneri IKINCI kez kurulamiyor", y.status_code == 400, str(y.status_code))
y = istemci.post(f"/api/ekip/{e2['no']}/red", json={"sebep": ""})
sina("gerekcesiz ekip reddi REDDEDILIYOR", y.status_code == 400)
y = istemci.post(f"/api/ekip/{e2['no']}/red", json={"sebep": "simdilik gerek yok"})
sina("gerekceli ekip reddi geciyor", y.status_code == 200)
sina("reddedilen kadro ISE ALINMADI",
     not any(a["ad"] == "kerem" for a in ofis.kadro.liste()))
sina("karar verilince oneri kuyruktan cikiyor",
     istemci.get("/api/oneriler").json()["ekip"] == [])

# -- KADRO panelden yonetiliyor: kurallar kadro'da, panel yalniz kapi ----
sec = istemci.get("/api/kadro/secenek").json()
from ofis import roller as _R
sina("secenekler rol kutuphanesinin TAMAMINI veriyor",
     len(sec["roller"]) == len(_R.ROLLER), str(len(sec["roller"])))
sina("motorlar OLCULUYOR (sahte kurulu)", sec["motorlar"].get("sahte") is True)
sina("efor listesinde 'max' YOK (yapiyla kapali)", "max" not in sec["eforlar"])
y = istemci.post("/api/ajan", json={"ad": "tuna", "meslek": "metin",
                                    "motor": "yokmotor"})
sina("kurulu olmayan motorla ISE ALINMIYOR", y.status_code == 400
     and "kurulu degil" in y.text, y.text[:120])
y = istemci.post("/api/ajan", json={"ad": "tuna", "meslek": "uydurma_rol",
                                    "motor": "sahte"})
sina("tanimsiz rolle ise alinmiyor (kadro kapisi)", y.status_code == 400,
     y.text[:120])
y = istemci.post("/api/ajan", json={"ad": "Tuna", "meslek": "metin",
                                    "motor": "sahte", "kanat": kanat})
sina("panelden ISE ALINIYOR", y.status_code == 200 and y.json()["ad"] == "tuna",
     y.text[:160])
sina("  tur ROLDEN doldu (metin -> eller)", y.json().get("tur") == "eller")
_kok = ofis.kok_klasoru()
sina("  ajan projenin ORTAK kokunde (karar 18.09)",
     bool(_kok) and Path(y.json()["klasor"]).resolve() == Path(_kok).resolve(),
     f'{y.json().get("klasor")} / {_kok}')
y = istemci.post("/api/ajan", json={"ad": "tuna", "meslek": "metin",
                                    "motor": "sahte"})
sina("ayni adla ikinci ise alma REDDEDILIYOR", y.status_code == 400)
y = istemci.post("/api/ajan/tuna/ayar", json={"efor": "max"})
sina("bozuk efor REDDEDILIYOR (cekirdekte, panelde degil)", y.status_code == 400,
     y.text[:120])
y = istemci.post("/api/ajan/tuna/ayar", json={"efor": "yuksek", "meslek": "seo"})
sina("ajan ayari degisiyor ve SONUC donuyor",
     y.status_code == 200 and y.json().get("efor") == "yuksek"
     and y.json().get("meslek") == "seo", y.text[:160])
sina("  degisiklik DEFTERDE (ofisin kendi okumasi)",
     ofis.kadro.ajan("tuna")["meslek"] == "seo")

# -- YETENEK: kasa ve hesaplar panelden ---------------------------------
# KULLANICININ GERCEK KASASINA DOKUNULMAZ: yol gecici dosyaya cevrilir ve
# bunun gercekten oldugu AYRICA olculur (yanlis yola yazan bir sinama,
# kullanicinin anahtarlarini silebilirdi).
import os as _os
from ofis import gizli as _gz
_os.environ["OFIS_GIZLI_YOLU"] = str(kok / "gizli-sinama.env")
sina("sinama kasasi GECICI dosyada (gercek kasa korunuyor)",
     _gz.depo_yolu() == (kok / "gizli-sinama.env").resolve(), str(_gz.depo_yolu()))
y = istemci.post("/api/anahtar", json={"ad": "bozuk ad!", "deger": "x"})
sina("gecersiz anahtar adi REDDEDILIYOR", y.status_code == 400)
_deger = "sk-SINAMA-" + "9" * 24
y = istemci.post("/api/anahtar", json={"ad": "deneme_anahtari", "deger": _deger})
sina("anahtar kasaya yaziliyor", y.status_code == 200
     and y.json()["ad"] == "DENEME_ANAHTARI", y.text[:120])
sina("  DEGER cevapta YOK (yalniz parmak izi)", _deger not in y.text)
t = istemci.get("/api/yetenek")
sina("yetenek taramasi paneline geliyor (gruplar + para kilidi durumu)",
     t.status_code == 200 and "gruplar" in t.json()
     and isinstance(t.json().get("para_kilidi"), bool), t.text[:160])
sina("  kasadaki anahtar ADIYLA gorunuyor, DEGERI gorunmuyor",
     "DENEME_ANAHTARI" in t.text and _deger not in t.text)
sina("  hizli taramada baglayicilarin ATLANDIGI soyleniyor",
     "(atlandi)" in t.text)
y = istemci.post("/api/anahtar/deneme_anahtari/sil")
sina("anahtar siliniyor", y.status_code == 200)
y = istemci.post("/api/anahtar/deneme_anahtari/sil")
sina("olmayan anahtari silmek 404 (uydurmuyor)", y.status_code == 404)
from ofis import hesap as _H
_H.ekle(ofis.db, ofis.proje_id, "is-hesabi", "claude")
y = istemci.post("/api/hesap/is-hesabi/aktif", json={"aktif": False})
sina("hesap zincirden CIKARILIYOR (kayit duruyor)", y.status_code == 200
     and y.json()["aktif"] is False and y.json().get("ortam") is None, y.text[:160])
sina("  kapali hesap listede HALA var (gecmis okunur)",
     any(h["ad"] == "is-hesabi" and not h["aktif"]
         for h in istemci.get("/api/yetenek").json()["hesaplar"]))
y = istemci.post("/api/hesap/yok-hesap/aktif", json={"aktif": True})
sina("olmayan hesap 400", y.status_code == 400)

# -- TAKIM (kanat) panelden ------------------------------------------------
y = istemci.post("/api/kanat", json={"ad": "studyo", "onek": "ST", "renk": "#E8A33C"})
sina("panelden takim kuruluyor", y.status_code == 200 and y.json()["ad"] == "STUDYO",
     y.text[:120])
y = istemci.post("/api/kanat", json={"ad": "studyo", "onek": "ST", "renk": "#E8A33C"})
sina("ayni adla ikinci takim REDDEDILIYOR (sessizce eskisi donmuyor)",
     y.status_code == 400, y.text[:120])
y = istemci.post("/api/kanat", json={"ad": "tasarim", "onek": "T*", "renk": "#E8A33C"})
sina("bozuk onek reddediliyor", y.status_code == 400)
y = istemci.post("/api/kanat", json={"ad": "tasarim", "onek": "TS", "renk": "mavi"})
sina("bozuk renk reddediliyor", y.status_code == 400)
sina("yeni takim ofiste gorunuyor",
     any(k["ad"] == "STUDYO" for k in istemci.get("/api/ofis").json()["kanatlar"]))

# -- SOHBET: liderin TAM cevabi panelde okunur ---------------------------
sh = istemci.get("/api/sohbet").json()
_m = [m for m in sh["mesajlar"] if "Ofiste ne durumdayiz" in m["govde"]]
sina("insanin lidere yazdigi sohbette", len(_m) == 1, str(sh)[:200])
sina("  liderin cevabi TAM geliyor (olay satiri gibi kesilmiyor)",
     bool(_m) and "Ofiste 4 ajan var." in (_m[0]["cevap"] or ""),
     str(_m)[:200])
sina("  kosu durumu da geliyor (cevap yoksa 'dusunuyor' diyebilsin)",
     "calisiyor" in sh["kosu"])

# -- AKIS: cevabi YAZILAN mesaj panelde akiyor (29.09.2026) --------------
from ofis.sohbet import AkisYazici as _AY
_ak_m = ofis.postane.soru_sor("insan", "demir", "Akis denemesi", mod="uyandiran")
_ay = _AY(ofis.db, ofis.proje_id, _ak_m["id"])
_ay('{"karar": "cevap", "gerekce": "g", "cevap": "Yaziliyor')
_ay._yaz(zorla=True)
_sa = [m for m in istemci.get("/api/sohbet").json()["mesajlar"]
       if m["govde"] == "Akis denemesi"]
sina("cevapsiz mesaj panele AKAN metinle geliyor",
     bool(_sa) and _sa[0]["akis"] == "Yaziliyor", str(_sa)[:160])
_ya = istemci.get("/api/sohbet/akis").json()
sina("  ayri akis ucu da veriyor (JSON ayiklanmis)",
     _ya["akis"].get(str(_ak_m["id"])) == "Yaziliyor", str(_ya)[:160])
ofis.postane.cevapla(_ak_m["id"], "Tam cevap", cevaplayan="demir")
_sa = [m for m in istemci.get("/api/sohbet").json()["mesajlar"]
       if m["govde"] == "Akis denemesi"]
sina("  cevap dusunce YARIM metin gosterilmiyor (kayit silinmemis olsa bile)",
     bool(_sa) and _sa[0]["akis"] == "" and _sa[0]["cevap"] == "Tam cevap")
_ay.bitir()
sina("  bitince akis ucu bos", str(_ak_m["id"]) not in
     istemci.get("/api/sohbet/akis").json()["akis"])
_js_ak = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
sina("panel akisi YOKLUYOR ve balonun ICINI degistiriyor",
     '"/api/sohbet/akis"' in _js_ak and "sohbetAkisIzle" in _js_ak
     and ".sohbet-yazi" in _js_ak)

# -- AJANA SOR: danisma insana acildi, yukseltme YOK ----------------------
_P.MOTOR_FABRIKASI = lambda ad, **kw: _Sahte(cevap="Webhook'ta ustel geri cekilme kullan.")
try:
    y = istemci.post("/api/ajana-sor", json={"ajan": "cinar", "metin": ""})
    sina("bos soru reddediliyor", y.status_code == 400)
    y = istemci.post("/api/ajana-sor", json={"ajan": "yok-boyle", "metin": "x"})
    sina("olmayan ajana soru reddediliyor", y.status_code == 400)
    y = istemci.post("/api/ajana-sor", json={"ajan": "cinar",
                                            "metin": "Retry nasil olmali?"})
    sina("ajana soru soruluyor", y.status_code == 200, y.text[:120])
    for _ in range(100):
        if not _P._DANISMA["calisiyor"]:
            break
        _t.sleep(0.1)
    sh = istemci.get("/api/sohbet").json()["mesajlar"]
    _s = [m for m in sh if m["govde"] == "Retry nasil olmali?"]
    sina("  cevap SOHBETTE, cevaplayan ajan", bool(_s) and _s[0]["alici"] == "cinar"
         and "ustel geri" in (_s[0]["cevap"] or ""), str(_s)[:200])
    sina("  insanin sorusu insanin KUYRUGUNA DUSMEDI (yukseltme yok)",
         not any(x["govde"] == "Retry nasil olmali?"
                 for x in istemci.get("/api/bekleyenler").json()["sorular"]))
    sina("  soru ajanin BEKLEYEN sorusu sayilmiyor (halka ikinci kez teslim etmez)",
         not any(x["govde"] == "Retry nasil olmali?"
                 for x in ofis.postane.ajana_bekleyenler()))
    _P.MOTOR_FABRIKASI = lambda ad, **kw: _Sahte(cevap="")
    istemci.post("/api/ajana-sor", json={"ajan": "cinar", "metin": "Bos donecek"})
    for _ in range(100):
        if not _P._DANISMA["calisiyor"]:
            break
        _t.sleep(0.1)
    _b = [m for m in istemci.get("/api/sohbet").json()["mesajlar"]
          if m["govde"] == "Bos donecek"]
    sina("  cevap alinamazsa SEBEBI cevap olarak yaziliyor (sessiz kalmiyor)",
         bool(_b) and "cevap alinamadi" in (_b[0]["cevap"] or ""), str(_b)[:160])
finally:
    _P.MOTOR_FABRIKASI = _yalniz_sahte

# -- ARAMA: tek kutu, Turkce katlama ------------------------------------
r = istemci.get("/api/ara", params={"q": "İPTAL"}).json()["sonuclar"]
sina("arama Turkce harfi KATLIYOR ('İPTAL' -> iptal kayitlari)",
     any(x["tur"] == "olay" for x in r), str(r[:2])[:160])
r = istemci.get("/api/ara", params={"q": "incelemedeki"}).json()["sonuclar"]
sina("arama GOREVI buluyor ve gorev no veriyor",
     any(x["tur"] == "gorev" and x["gorev_no"] == g2["no"] for x in r), str(r)[:160])
r = istemci.get("/api/ara", params={"q": "yeni deger"}).json()["sonuclar"]
sina("arama HAFIZAYI (olgu) buluyor", any(x["tur"] == "olgu" for x in r))
r = istemci.get("/api/ara", params={"q": "eski deger"}).json()["sonuclar"]
sina("  devrilmis bilgi ESKI diye isaretleniyor",
     any(x["tur"] == "olgu" and "ESKİ" in x["baslik"] for x in r), str(r)[:160])
sina("tek harflik arama bos (her seyi dokmuyor)",
     istemci.get("/api/ara", params={"q": "a"}).json()["sonuclar"] == [])

# -- guncelleme onerisi panelden reddediliyor (deneme turu KOSMAZ) --------
import json as _json
from ofis import guncelleme as _G
ofis.db.ayar_yaz(ofis.proje_id, _G.ANAHTAR_BEKLEYEN, _json.dumps([{
    "no": 1, "tur": "model", "motor": "codex", "eski": "a", "yeni": "b",
    "kademeler": [], "ajanlar": [], "sebep": "sinama",
    "anahtar": "model:codex:a->b", "ozet": "codex a -> b (sinama)"}]))
# OTOMATIK MOD (29.09.2026): ayni aile onerisi insana DUSMEZ (ofis
# kendisi dener); otomatik kapaliyken eski davranis -- karar insanda.
_on = istemci.get("/api/oneriler").json()
sina("otomatik ACIKKEN ayni aile onerisi insana DUSMUYOR",
     _on["guncelleme"] == [] and _on.get("otomatik") is True, str(_on)[:160])
_G.otomatik_ayarla(ofis.db, ofis.proje_id, False)
sina("guncelleme onerisi panele geliyor (otomatik kapali)",
     len(istemci.get("/api/oneriler").json()["guncelleme"]) == 1)
y = istemci.post("/api/guncelle/1/reddet", json={"sebep": ""})
sina("gerekcesiz guncelleme reddi REDDEDILIYOR", y.status_code == 400)
y = istemci.post("/api/guncelle/1/reddet", json={"sebep": "simdi degil"})
sina("gerekceli guncelleme reddi geciyor", y.status_code == 200, y.text[:160])
sina("reddedilen guncelleme kuyruktan cikiyor",
     istemci.get("/api/oneriler").json()["guncelleme"] == [])
y = istemci.post("/api/guncelle/9/onayla", json={"kademe": ""})
sina("olmayan guncelleme onayi 400 (uydurmuyor)", y.status_code == 400)

# otomatik UYGULANAN kart + GERI AL panelden
ofis.db.ayar_yaz(ofis.proje_id, _G.TAKMA_AD_ONEKI + "sonnet", "claude-sonnet-5-5")
ofis.db.ayar_yaz(ofis.proje_id, _G.ANAHTAR_GECMIS, _json.dumps([{
    "sira": 1, "tur": "takma_ad", "motor": "claude", "ad": "sonnet",
    "eski": "claude-sonnet-5", "yeni": "claude-sonnet-5-5", "veren": "ofis",
    "anahtar": "takma_ad:sonnet:claude-sonnet-5-5", "durum": "uygulandi",
    "goruldu": False, "zaman": "2026-09-29T00:00:00+00:00", "deneme": "OK"}]))
_on = istemci.get("/api/oneriler").json()
sina("otomatik UYGULANAN guncelleme kart olarak geliyor",
     len(_on.get("uygulanan") or []) == 1, str(_on)[:160])
y = istemci.post("/api/guncelle/gecmis/1/geri_al", json={"sebep": "begenmedim"})
sina("panelden GERI AL calisiyor", y.status_code == 200
     and _G.model_coz(ofis.db, ofis.proje_id, "claude", "sonnet") == "claude-sonnet-5",
     y.text[:160])
sina("geri alinan kart kalkiyor",
     istemci.get("/api/oneriler").json()["uygulanan"] == [])
y = istemci.post("/api/guncelle/gecmis/1/geri_al", json={"sebep": "x"})
sina("ikinci geri alma 400", y.status_code == 400)
sina("panel GERI AL yolunu bagliyor", "/geri_al`" in (Path(__file__).resolve()
     .parent.parent / "web" / "panel.js").read_text(encoding="utf-8"))

# -- panel bunlari GERCEKTEN kullaniyor (besleme sinamasi) ----------------
_js6 = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(
    encoding="utf-8")
sina("panel onerileri okuyor", '"/api/oneriler"' in _js6)
sina("panel 'surdur' dugmesini bagliyor", '"/api/devam"' in _js6)
sina("panel 'is boyunca' onay veriyor", 'kapsam: "is"' in _js6)
sina("panel iptal yolunu bagliyor", "/iptal`" in _js6)
sina("panel kosarken DURDUR dugmesi sunuyor", '"/api/durdur"' in _js6)
sina("panel yetenek panosunu bagliyor", '"/api/yetenek' in _js6)
sina("panel aramayi bagliyor", '"/api/ara?q="' in _js6)
sina("panel TAKIM SOHBETINI gosteriyor (lider + ajanlar tek akis)",
     '"/api/takim' in _js6)
sina("panel takim kurmayi bagliyor", '"/api/kanat"' in _js6)
sina("panel ajana sormayi bagliyor", '"/api/ajana-sor"' in _js6)
_ara_js = _js6[_js6.index("async function araAc"):_js6.index("async function araAc") + 2500]
sina("arama sonucu METIN olarak basiliyor (innerHTML yok)",
     "innerHTML" not in _ara_js and "createTextNode" in _ara_js)
sina("panel para kilidini ACAMIYOR (yalniz gosterir)",
     "para_harca" not in _js6 and "/api/para" not in _js6)
sina("panel ise alma formunu bagliyor", '"/api/ajan"' in _js6
     and '"/api/kadro/secenek"' in _js6)
sina("panel ajan ayarini bagliyor", "/ayar`" in _js6)
sina("pano basligi hesabin OLCULEN limitini gosteriyor",
     "hesapPenceresi(sonTur.motor, sonTur.hesap)" in _js6)
sina("  son tur HESABI da tasiyor (yanlis hesaba bakilmasin)",
     '"hesap": d.get("hesap")' in Path(_P.__file__).read_text(encoding="utf-8"))
sina("kart olarak cizilen istekler bulgu olarak IKINCI kez sayilmiyor",
     '"insan_kuyrugu"' in _js6 and '"ekip_onerisi"' in _js6)
sina("panel artik insani ekip icin CLI'ya YOLLAMIYOR",
     "kabuk ekip liste" not in _js6)

# --------------------------------------------------------------------------
print("\n7. GUVENLIK KAPILARI")
try:
    kos("0.0.0.0")
    sina("0.0.0.0 REDDEDILIYOR", False, "-- kabul edildi!")
except SystemExit:
    sina("0.0.0.0 REDDEDILIYOR", True)
try:
    kos("::")
    sina(":: REDDEDILIYOR", False, "-- kabul edildi!")
except SystemExit:
    sina(":: REDDEDILIYOR", True)

sina("varlik yolu enjeksiyonu kapali",
     istemci.get("/varlik/..%2F..%2FCLAUDE.md").status_code == 404)
sina("olmayan varlik 404", istemci.get("/varlik/yok.css").status_code == 404)
sina("panel.css servis ediliyor", istemci.get("/varlik/panel.css").status_code == 200)
sina("sayfa aciliyor", istemci.get("/").status_code == 200)
# ONBELLEK: panel guncellenince tarayici ESKI arayuzu gostermesin.
# Olculdu (23.09.2026): basliksiz dosyada tarayici tazeligi kendi
# tahminiyle uyduruyor; sunucu yeni harita kodunu verirken sayfa eski
# kart izgarasini ciziyordu -- hata vermeden.
sina("sayfa ONBELLEKSIZ (kullanmadan once sorulur)",
     istemci.get("/").headers.get("cache-control") == "no-cache",
     repr(istemci.get("/").headers.get("cache-control")))
sina("varlik ONBELLEKSIZ (kullanmadan once sorulur)",
     istemci.get("/varlik/panel.js").headers.get("cache-control") == "no-cache")

# LIMIT PENCERELERI panele ULASIYOR. Saglayici her turda bildiriyordu ve
# ofis ATIYORDU (23.09.2026); simdi deftere yaziliyor -- ama panele
# ulasmazsa insan icin yine yok hukmunde. Besleme sinamasi: alan geliyor
# ve tarihleri JSON'a cevrilebiliyor. `hesap_durumu` gercek CLI'a
# (`claude auth status`) soruyor; sinama kullanicinin hesabina dokunmasin.
import time as _tm
import ofis.kullanim as _K
from ofis.motor.tip import limit_penceresi as _lp
_eski_hd = _K.hesap_durumu
_K.hesap_durumu = lambda: []
try:
    _K.tur_ozeti_yaz(ofis.db, ofis.proje_id, {"jeton": 1, "limit_pencere": _lp(
        {"5s": {"kullanim": 0.42, "yenilenme": int(_tm.time()) + 3600}},
        kaynak="sinama")}, motor="claude")
    _ku = istemci.get("/api/kullanim").json()
finally:
    _K.hesap_durumu = _eski_hd
_pen = _ku.get("pencereler") or []
sina("kullanim ucu limit PENCERELERINI veriyor",
     any(p.get("motor") == "claude"
         and (p.get("pencereler", {}).get("5s") or {}).get("kullanim") == 0.42
         for p in _pen), str(_ku)[:200])
sina("  pencere yenilenme ani JSON'da (tarih cevrilebildi)",
     bool(_pen) and isinstance(_pen[0]["pencereler"]["5s"]["yenilenme"], str))

# --------------------------------------------------------------------------
print("\n8. OLAY AKISI")
olaylar = istemci.get("/api/olaylar?adet=10").json()
sina("olaylar donuyor", len(olaylar) > 0)
sina("olaylar ESKIDEN YENIYE sirali",
     all(olaylar[i]["id"] < olaylar[i + 1]["id"] for i in range(len(olaylar) - 1)))
son = olaylar[-1]["id"]
sina("sonra= filtresi calisiyor",
     all(x["id"] > son for x in istemci.get(f"/api/olaylar?sonra={son}").json()))

# ---------------------------------------- 12. KAT PLANI ic tutarliligi
#
# Kat plani tamamen ISTEMCI tarafinda ve panelin JS'i icin bir kosum
# YOK -- yani bir odanin mobilyasiz kalmasi hicbir yerde ates etmez.
# Bu, `roller.py`de bir kez odenen lintin aynisi: kutuphanenin KENDI
# ic tutarliligini denetlemek. Cizimi olcmuyor, SOZLESMEYI olcuyor.
#
# Regex KULLANILMIYOR: desenin kendisi bir tuzak oldu (kacis
# katmanlari yuzunden uc kez yanlis kuruldu). Duz ayristirma hem
# okunur hem de neyi okudugunu gizlemiyor.
print("")
print("12. KAT PLANI -- her odanin mobilyasi var mi")

_web = Path(__file__).resolve().parent.parent / "web"
_js = _web.joinpath("panel.js").read_text(encoding="utf-8")
_css = _web.joinpath("panel.css").read_text(encoding="utf-8")


def _blok(metin, bas_im):
    govde = metin.split(bas_im, 1)[1]
    return govde.split("];", 1)[0] if bas_im.endswith("[") else         govde.split("};", 1)[0]


def _tirnakli_ilk(satir):
    """Satirdaki ILK tirnakli degeri dondurur ('masa', ...)."""
    if satir.count(chr(34)) < 2:
        return ""
    return satir.split(chr(34))[1]


_odalar = [_tirnakli_ilk(r) for r in _blok(_js, "const ODALAR = [").splitlines()
           if r.strip().startswith("[")]
_odalar = [o for o in _odalar if o]
sina("ODALAR okunabildi", len(_odalar) >= 5, str(_odalar))

_mob_anahtar = [r.split(":", 1)[0].strip()
                for r in _blok(_js, "const MOBILYA = {").splitlines()
                if ":" in r and r.strip() and not r.strip().startswith("//")
                and r.strip()[0].isalpha()]
sina("MOBILYA okunabildi", len(_mob_anahtar) >= 5, str(_mob_anahtar))

# Mobilyasiz oda = bos bir kutu. Kullanici tam bunu gosterdi
# (22.09.2026): "ofis bosken dort kez 'bos' yaziyor". Yeni bir oda
# eklenip mobilyasi unutulursa ayni kusur SESSIZCE geri gelir.
_eksik = [o for o in _odalar if o not in _mob_anahtar]
sina("HER odanin mobilyasi var", not _eksik, "mobilyasiz: " + str(_eksik))
# Ters yon: olmayan bir odaya mobilya yazilmis mi (olu kayit).
_fazla = [k for k in _mob_anahtar if k not in _odalar]
sina("olmayan odaya mobilya YOK", not _fazla, str(_fazla))

# "bos" yazisi GERI GELMESIN: sayac zaten basliktadir, ve odayi bos
# bir kutuya ceviren sey o yaziydi.
sina("bos oda 'bos' YAZMIYOR", "kat-bos" not in _js)
sina("'.kat-bos' stili de kalkmis", ".kat-bos" not in _css)

# Kat plani TEK SUTUNA zorlanmasin -- bir kez oyle yapilmisti ve
# "kat plani" dedigimiz sey pratikte dikey bir LISTEYDI.
sina("sutun icinde kat plani tek kolona ZORLANMIYOR",
     ".sutun .kat-plani { grid-template-columns: 1fr; }" not in _css)

# ------------------------------------- 13. TERMINAL SUTUNU BOS KALMASIN
#
# Kullanici (22.09.2026): *"terminaller gelmiyor."* Iki ayri hata
# vardi ve ikisi de OLCUMLE cikti:
#
#   1. Panolar yalnizca `oda !== "mola"` olan ajanlar icin ciziliyordu,
#      yani ofis dinlenirken sutun TAMAMEN bos kaliyordu. Defterde 249
#      ajanli olay, ekranda 0 pano.
#   2. `cizCanli()` acilista `D.olaylar` DOLMADAN once kosuyordu ve
#      bir daha cizilmiyordu -- yani ilk boyama her zaman bos.
#
# Bunlar istemci tarafinda ve panelin JS'i icin kosum yok; bu yuzden
# olculen sey CIZIM degil SOZLESME. Ama iki regresyon da tek satirla
# geri gelebilir, ve geldiginde hicbir sey ates etmezdi.
print("")
print("13. TERMINAL -- ofis dinlenirken de dolu")

_canli = _js.split("function cizCanli()", 1)[1].split(
    chr(10) + "function ", 1)[0]

# GECMIS yolu duruyor mu: kosan yoksa son turlar gosterilmeli.
# Degiskenin VARLIGINA bakmak yetmiyor: mutasyonda `gecmis` duruyor
# ama kullanilmiyordu ve test GECTI. Olculen sey artik DUSUSUN
# KENDISI -- kosan yoksa gecmise gecen ifade.
sina("kosan yokken GECMIS turlara DUSUYOR",
     "calisan.length ? calisan : gecmis" in _canli, _canli[:200])
# Ve canli SANILMASIN: bosluğun sebebi yaziliyor.
sina("gecmis oldugu ACIKCA yaziliyor",
     "SON TURLARIN" in _canli or "son tur" in _js)
# Eski kusur: tek sart olarak mola suzgeci.
sina("mola suzgeci TEK BASINA pano engellemiyor",
     'a.oda !== "mola");' not in _canli
     or "gosterilecek" in _canli, _canli[:120])

# Acilista olaylar yuklendikten SONRA yeniden cizim.
_acilis = _js.split("D.olaylar = await al(", 1)[1].split("baglan();", 1)[0]
sina("olaylar yuklenince terminal YENIDEN ciziliyor",
     "cizCanli()" in _acilis, _acilis[-160:])
sina("olaylar yuklenince ofis de yeniden ciziliyor",
     "cizOfis()" in _acilis)

# Panolar DOSENEBILMELI: sutun icinde tek kolona zorlanmasin -- kat
# planindakiyle ayni sinif hata, ayni dosyada iki satir arayla.
sina("panolar sutun icinde tek kolona ZORLANMIYOR",
     ".sutun .canli-izle { grid-template-columns: 1fr; }" not in _css)
# Ve izgara esigi sutun genisligine SIGMALI: 420px'te iki pano 852px
# isterdi ve sutun hicbir zaman o kadar genis olmadi.
# Ilk surum blogun BUTUN rakamlarini sayiyordu (dolgu 16px, bosluk
# 12px dahil) ve `min()` her zaman <= 300 cikiyordu: kapi hic
# kapanmadi. Yalniz `minmax(` ILK argumani okunuyor.
_izgara = _css.split(".canli-izle {", 1)[1].split("}", 1)[0]
_mm = _izgara.split("minmax(", 1)[1].split(",", 1)[0].replace("px", "").strip()
sina("pano izgara esigi <= 300px", _mm.isdigit() and int(_mm) <= 300, _mm)

# --------------------------------------------- 14. OFIS HARITASI -- sozlesme
#
# Harita tek parca bir kat plani ve ucu de OLCULMUS uc kusuru var
# (23.09.2026). Hepsi istemci tarafinda; bu bolum SOZLESMEYI olcer,
# cizimi degil -- geometri 15. bolumde CALISTIRILARAK olculur.
print("")
print("14. OFIS HARITASI -- sozlesme")


def _css_blok(secici):
    govde = _css.split(chr(10) + secici + " {", 1)
    return govde[1].split("}", 1)[0] if len(govde) == 2 else ""


# 1) Balon metni DOLGUSUZ ic ogede kirpilir. Kirpma balonun kendisindeyken
#    `overflow` DOLGU kutusunda kesiyor, ucuncu satirin ust yarisi alt
#    dolguda gorunuyordu -- 21.09'da "max-height ile kapatildi" sanilan
#    dilimin ta kendisi.
sina("balonun kendisi KIRPMIYOR (dolgu kutusunda dilim birakirdi)",
     "line-clamp" not in _css_blok(".balon"), _css_blok(".balon")[:80])
sina("kirpma DOLGUSUZ ic ogede",
     "line-clamp" in _css_blok(".balon-yazi")
     and "padding" not in _css_blok(".balon-yazi"))
sina("balon metni ic ogeye yaziliyor", '"balon-yazi"' in _js)

_ciz_ofis = _js.split("function cizOfis()", 1)[1].split(
    chr(10) + "function ", 1)[0]
# 2) YURUYUS KESILMESIN: panel her olayda haritayi yeniden kurar; yolda
#    olanin yeri kurulumdan ONCE okunmazsa ajan hedefine isinlanir.
_oku = _ciz_ofis.find("yoldakileriOku(kap)")
_sil = _ciz_ofis.find('kap.innerHTML = ""')
sina("yoldakiler yeniden kurulumdan ONCE okunuyor",
     0 <= _oku < _sil, f"oku@{_oku} sil@{_sil}")
# 3) Balonlar son yerlerinde OLCULUP yerlesiyor -- harita DOM'a girdikten
#    sonra (olcum ancak orada mumkun).
_ekle = _ciz_ofis.find("kap.append(harita)")
_can = _ciz_ofis.find("haritaCanlandir(harita)")
sina("harita DOM'a girince canlandiriliyor",
     0 <= _ekle < _can, f"ekle@{_ekle} can@{_can}")
_canlandir = _js.split("function haritaCanlandir(", 1)[1].split(
    chr(10) + "function ", 1)[0]
sina("canlandirma balonlari OLCEREK yerlestiriyor",
     "balonlariYerlestir(h)" in _canlandir)
# Yer kalmayan balon gizlenir ama bilgi KAYBOLMAZ: isaret + uzerine gelince.
sina("gizlenen balonun ISARETI var", ".hr-ajan.suskun::before" in _css)
sina("gizlenen balon uzerine gelince ACILIYOR",
     ".hr-ajan.suskun:hover .balon" in _css)

# ------------------------------------ 15. HARITA GEOMETRISI (Node'da CALISIR)
#
# Panelin JS'i icin kosum YOKTU -- ofis kendisi yazdi (#23, bilge:
# `calisma/cinar/test_panel_js.mjs`): saf islevler parantez eslestirmeyle
# ayiklanip Node'da degerlendiriliyor. Ayni teknik harita icin: konum, yol
# ve ziyaretci yerlesimi SAF islevler ve CALISTIRILARAK olculur.
import shutil as _sh
import subprocess as _sp

print("")
print("15. HARITA GEOMETRISI -- saf islevler Node'da CALISTIRILIYOR")
_node = _sh.which("node")
if not _node:
    # Olcemedigimize "iyi" demeyiz: node yoksa bolum GECMEZ, ATLANIR ve
    # bunu soyler.
    print("  [ATLANDI] node bulunamadi -- harita geometrisi OLCULMEDI")
else:
    _c = _sp.run([_node, str(Path(__file__).with_name("panel_harita.mjs"))],
                 capture_output=True, text=True, encoding="utf-8", timeout=120)
    _cikti = [x for x in _c.stdout.splitlines()
              if x.startswith(("GECTI ", "KALDI "))]
    sina("harita kosumu calisti ve sonuc verdi",
         bool(_cikti) and "SONUC" in _c.stdout, (_c.stderr or "")[-300:])
    for _x in _cikti:
        _tur, _, _ad = _x.partition(" ")
        _ad, _, _detay = _ad.partition(" -- ")
        sina("  " + _ad, _tur == "GECTI", _detay)

# ------------------------------------ 16. PANO YERLESIMI (Node'da CALISIR)
#
# Kullanici (23.09.2026): panolar surukle-birak ile tasinsin, sekme
# olsun, bolunsun, boyutlansin. Duzen bir VERI modelidir ve tarayicida
# saklanir; saklanan duzen bozulursa rakibin yasadigi "paneller
# kayboldu" hatasi dogar. Bu yuzden onarim ve tasima SAF islevler ve
# bir DEGISMEZLE sinanir: her pano tam bir kez, her sayi sonlu.
print("")
print("16. PANO YERLESIMI -- saf islevler Node'da CALISTIRILIYOR")
if not _node:
    print("  [ATLANDI] node bulunamadi -- yerlesim OLCULMEDI")
else:
    _c = _sp.run([_node, str(Path(__file__).with_name("panel_yerlesim.mjs"))],
                 capture_output=True, text=True, encoding="utf-8", timeout=120)
    _cikti = [x for x in _c.stdout.splitlines()
              if x.startswith(("GECTI ", "KALDI "))]
    sina("yerlesim kosumu calisti ve sonuc verdi",
         bool(_cikti) and "SONUC" in _c.stdout, (_c.stderr or "")[-300:])
    for _x in _cikti:
        _tur, _, _ad = _x.partition(" ")
        _ad, _, _detay = _ad.partition(" -- ")
        sina("  " + _ad, _tur == "GECTI", _detay)

# Sozlesme: panolar depoda dogar ve TASINIR (yeniden cizilmez), sifirlama
# var, acilista duzen onarilir, sabit izgara geri gelmedi.
_html = _web.joinpath("index.html").read_text(encoding="utf-8")
sina("panolar DEPODA dogar (yeniden cizilmez, tasinir)",
     'id="pano-depo"' in _html and _html.count('class="pano-govde"') == 12)
# 28.09: ayri Hesap panosu KALDIRILDI (hesap panosunun tekrariydi); ondan
# kalan iki bilgi yerine tasindi, kaybolmadi.
sina("ayri Hesap panosu YOK", 'data-pano="hesap"' not in _html
     and 'hesap:    {' not in _js)
sina("  bagam sagligi Hafiza panosunda",
     _html.index('data-pano="hafiza"') < _html.index('id="baglam"') < _html.index('data-pano="kararlar"'))
sina("  ofisin tukettigi hesap panosunda", "c.append(hesapTuketim(D.kullanim))" in _js
     and "D.kullanim = k;" in _js)
sina("duzeni sifirla dugmesi var", 'id="duzen-sifirla"' in _html)
sina("acilista yerlesim yuklenir ve ONARILIR",
     "D.yerlesim = yerlesimYukle();" in _js
     and "yerlesimOnar(h ? JSON.parse(h) : null)" in _js)
sina("JS alt siniri CSS ile AYNI (220px sutun, 80px yigin)",
     "const SUTUN_ALT_PX = 220, YIGIN_ALT_PX = 80;" in _js
     and "min-width: 220px" in _css and "min-height: 80px" in _css)
sina("sabit sutun izgarasi geri gelmedi",
     "grid-template-columns: minmax(360px" not in _css)

print("")
print("17. CANLI IZLEME -- /api/canli ve Kod panosu")
from ofis import degisim as _dg
_ck = {"yol": "api/canli.py", "hal": "eklendi", "beyan_disi": False,
       "eklenen": 2, "silinen": 0, "yama": "+a\n+b\n", "olculemedi": ""}
_g_kosan = ofis.tahta.gorev_ac("Canli kosan", neden="n", ana_hedef="h",
                               kabul_olcutu="k", yazma_alani=["api/canli"],
                               kanat_id=kanat)
ofis.tahta.sahiplen(_g_kosan["no"], "cinar", _g_kosan["revizyon"])
_dg.canli_yaz(db, ofis.proje_id, _g_kosan["id"], "cinar", [_ck])
_g_hazir = ofis.tahta.gorev_ac("Kosmayan", neden="n", ana_hedef="h",
                               kabul_olcutu="k", kanat_id=kanat)
_dg.canli_yaz(db, ofis.proje_id, _g_hazir["id"], "cinar",
              [dict(_ck, yol="api/bayat.py")])
_rc = istemci.get("/api/canli")
_jc = _rc.json() if _rc.status_code == 200 else {}
_yc = [k["yol"] for k in _jc.get("kayitlar", [])]
sina("/api/canli kosan isin ara farkini veriyor",
     _rc.status_code == 200 and "api/canli.py" in _yc, str(_jc)[:200])
sina("  KOSMAYAN isin artigi gosterilmiyor", "api/bayat.py" not in _yc,
     str(_yc))
_k0 = (_jc.get("kayitlar") or [{}])[0]
sina("  gorev no + kanat + bayraklar tasiniyor",
     _k0.get("gorev_no") == _g_kosan["no"] and _k0.get("kanat_id") == kanat
     and _k0.get("beyan_disi") is False and "damga" in _k0, str(_k0)[:200])
_dg.canli_sil(db, ofis.proje_id, _g_kosan["id"])
_dg.canli_sil(db, ofis.proje_id, _g_hazir["id"])

_jsc = _web.joinpath("panel.js").read_text(encoding="utf-8")
_i0 = _jsc.find("function canliSuz()")
_i1 = _jsc.find("function kodSatiri(")
_canli_js = _jsc[_i0:_i1] if 0 <= _i0 < _i1 else ""
sina("Kod panosu canli bloku ciziyor", "function canliBlokCiz()" in _canli_js
     and "kod-canli" in _jsc)
sina("canli yoklama acilista KURULUYOR", "canliYoklamaKur();" in _jsc)
sina("ilk dokunus olayi yoklamayi beklemeden gosteriyor",
     'o.tur === "dosya_canli"' in _jsc and "canliTazele()" in _jsc)
sina("yoklama yalniz Kod panosu ekrandayken istek atiyor",
     'if (!panoGorunur("kod")) return;' in _canli_js)
sina("degismeyen veri yeniden CIZILMIYOR (kaydirma korunur)",
     "D.canliImza" in _canli_js)
# SALT OKUNUR: panelden duzenleme yazma kilidinin gormedigi ikinci yazar
# olurdu (Yasa 1). Rakipte "Kaydet" var; bizde bilerek yok.
sina("canli blok SALT OKUNUR (duzenleme/kaydetme yok)",
     bool(_canli_js) and "contenteditable" not in _canli_js
     and "textarea" not in _canli_js and "method: \"POST\"" not in _canli_js)
sina("olay sozlugu dosya_canli'yi Turkce okuyor", "dosya_canli:" in _jsc)

print("")
print("18. HAFIZA -- bilgi, bag, kural panelden; cizge Node'da")
_r = istemci.post("/api/bilgi", json={"konu": "Kargo", "icerik":
                  "Aras; sure icin [[lojistik anlasmasi]]"})
sina("panelden bilgi yaziliyor (kaynak insan)",
     _r.status_code == 200 and _r.json().get("kaynak") == "insan", _r.text[:200])
_r = istemci.post("/api/bilgi", json={"konu": "", "icerik": "x"})
sina("bos konu 400 (cekirdek reddediyor)", _r.status_code == 400)
_h = istemci.get("/api/hafiza").json()
_kg = [o for o in _h["gecerli"] if o["konu"] == "Kargo"]
sina("hafiza bagi SUNUCUDA cikariyor (brifingle ayni ayristirici)",
     bool(_kg) and _kg[0]["baglar"] == [{"konu": "lojistik anlasmasi",
                                          "anahtar": "lojistik anlasmasi",
                                          "kirik": True}], str(_kg)[:200])
_r = istemci.post("/api/bilgi", json={"konu": "Lojistik anlasmasi",
                                      "icerik": "Yillik sozlesme"})
_kg = [o for o in istemci.get("/api/hafiza").json()["gecerli"]
       if o["konu"] == "Kargo"]
sina("  hedef yazilinca bag KIRIK DEGIL",
     bool(_kg) and _kg[0]["baglar"][0]["kirik"] is False)
_r = istemci.post("/api/kural", json={"metin": "KDV dahil", "gerekce": ""})
sina("gerekcesiz kural 400", _r.status_code == 400)
_r = istemci.post("/api/kural", json={"olgu": "kargo", "gerekce": "Her iste"})
sina("bilgi panelden KURALA YUKSELTILIYOR",
     _r.status_code == 200 and _r.json().get("kaynak_tur") == "olgu",
     _r.text[:200])
_h = istemci.get("/api/hafiza").json()
sina("kural listede + yuku olculuyor",
     len(_h["kurallar"]) == 1 and _h["kural_maliyeti"]["adet"] == 1)
_kid = _h["kurallar"][0]["id"]
_r = istemci.post(f"/api/kural/{_kid}/kaldir", json={"sebep": ""})
sina("sebepsiz kaldirma 400", _r.status_code == 400)
_r = istemci.post(f"/api/kural/{_kid[:8]}/kaldir", json={"sebep": "deneme"})
sina("kural KISA kimlikle kaldiriliyor", _r.status_code == 200, _r.text[:200])
sina("  gecerli kural kalmadi", istemci.get("/api/hafiza").json()["kurallar"] == [])
_gc = istemci.get("/api/hafiza/gecmis", params={"konu": "KARGO"}).json()
sina("gecmis konu adi normallesmis olarak okunuyor",
     _gc["konu"] == "Kargo" and len(_gc["gecmis"]) == 1)

if not _node:
    print("  [ATLANDI] node bulunamadi -- cizge OLCULMEDI")
else:
    _c = _sp.run([_node, str(Path(__file__).with_name("panel_hafiza.mjs"))],
                 capture_output=True, text=True, encoding="utf-8", timeout=120)
    _cikti = [x for x in _c.stdout.splitlines()
              if x.startswith(("GECTI ", "KALDI "))]
    sina("cizge kosumu calisti ve sonuc verdi",
         bool(_cikti) and "SONUC" in _c.stdout, (_c.stderr or "")[-300:])
    for _x in _cikti:
        _tur, _, _ad = _x.partition(" ")
        _ad, _, _detay = _ad.partition(" -- ")
        sina("  " + _ad, _tur == "GECTI", _detay)
_jsh = _web.joinpath("panel.js").read_text(encoding="utf-8")
sina("kural olayi Hafiza'yi TAZELIYOR", '"kural",' in _jsh
     and "const TAZELE" in _jsh)
sina("gerekce satir icinde soruluyor (prompt YOK)", "prompt(" not in _jsh)
# Olculdu: her canli olay sekme panolarini bastan ciziyordu ve insanin
# yarim yazdigi bilgi bir ajanin kanitiyla SILINIYORDU.
_cs = _jsh[_jsh.find("async function cizSekme()"):]
_cs = _cs[:_cs.find("\n}\n")]
sina("insan YAZARKEN sekme panosu yeniden cizilmiyor",
     "document.activeElement" in _cs and "odak.value" in _cs
     and _cs.find("odak.value") < _cs.find('kap.textContent = ""'))

print("")
print("19. PANO BUYUT / BOL -- sozlesme")
_jsb = _web.joinpath("panel.js").read_text(encoding="utf-8")
_cssb = _web.joinpath("panel.css").read_text(encoding="utf-8")
sina("buyutme DUZENE yazilmiyor (gorunum hali)",
     "buyuk:" not in _jsb[_jsb.find("function yerlesimVarsayilan()"):
                          _jsb.find("function yerlesimOnar(")]
     and "D.buyuk" not in _jsb[_jsb.find("function yerlesimKaydet()"):
                               _jsb.find("function yerlesimKaydet()") + 300])
sina("bolme SINANMIS panoTasi'yi kullaniyor (yeni kural yok)",
     "yerlesimUygula(panoTasi(D.yerlesim, sec.dataset.pano," in _jsb)
sina("tek panolu yiginda bolme dugmesi CIZILMIYOR",
     "if (gorunen.length > 1) {" in _jsb and 'd.dataset.bol = yer;' in _jsb)
_esc = _jsb[_jsb.find('if (e.key !== "Escape" || !D.buyuk) return;'):]
_esc = _esc[:_esc.find("});")]
sina("Esc yazi alanini ve odakli kabini EZMIYOR",
     "INPUT|TEXTAREA" in _esc and ".kabin-alan.odakli" in _esc)
sina("buyutulen yigin kaybolunca hal DUSUYOR",
     'if (D.buyuk && !document.querySelector(".yigin.buyuk")) D.buyuk = null;'
     in _jsb)
sina("buyutulen yigin sabit katman ve alani olculuyor",
     ".yigin.buyuk { position: fixed;" in _cssb
     and 'getBoundingClientRect()' in _jsb[_jsb.find("function buyukKonumla()"):
                                          _jsb.find("function buyukKonumla()") + 400])

print("")
print("20. SABLONDAN EKIP -- panel uclari")
_sl = istemci.get("/api/sablonlar").json()
sina("sablonlar listeleniyor (roller ile)",
     any(s["ad"] == "yazilim" and "backend" in s["roller"] for s in _sl))
_once = len(ofis.kadro.liste())
_r = istemci.post("/api/sablon", json={"ad": "arastirma", "kanat": kanat})
sina("panelden sablon ONERI uretiyor", _r.status_code == 200
     and _r.json().get("durum") == "bekliyor", _r.text[:200])
sina("  ama KIMSEYI ISE ALMIYOR (kurmak insanin karari)",
     len(ofis.kadro.liste()) == _once)
sina("  oneri SENDEN BEKLENIYOR kuyrugunda",
     any(o["no"] == _r.json().get("no")
         for o in istemci.get("/api/oneriler").json().get("ekip", [])))
_r = istemci.post("/api/sablon", json={"ad": "yok-boyle", "kanat": kanat})
sina("bilinmeyen sablon 400", _r.status_code == 400)
_jss = _web.joinpath("panel.js").read_text(encoding="utf-8")
sina("ise alma cekmecesi sablonlari gosteriyor",
     'al("/api/sablonlar")' in _jss and 'eylem("/api/sablon"' in _jss)


print("")
print("21. LIMIT YENILENME ANI -- 'dolan limit ne zaman acilir'")
import json as _jy
from datetime import datetime as _dty, timezone as _tzy
from ofis.motor.tip import limit_penceresi as _lpy
_simdi_y = _dty.now(_tzy.utc).timestamp()
ofis.db.olay_yaz(ofis.proje_id, "tur_ozeti", _jy.dumps({
    "motor": "codex", "hesap": "", "limit_pencere": _lpy(
        {"5s": {"kullanim": 1.0, "yenilenme": int(_simdi_y + 4080)},
         "7g": {"kullanim": 0.19, "yenilenme": int(_simdi_y + 6 * 86400)}},
        kaynak="sinama")}))
_py = istemci.get("/api/ofis").json().get("para", {})
_hy = [h for h in _py.get("limitler", []) if h["ad"] == "codex"]
sina("rayda hesabin yenilenme anlari var",
     bool(_hy) and set((_hy[0].get("yenilenmeler") or {})) == {"5s", "7g"},
     str(_hy)[:300])
if _hy:
    _an = _dty.fromisoformat(_hy[0]["yenilenmeler"]["5s"]).timestamp()
    sina("  an MUTLAK (saglayicinin bildirdigi an)", abs(_an - (_simdi_y + 4080)) < 2)
_jsy = _web.joinpath("panel.js").read_text(encoding="utf-8")
# 27.09: hesap basina cip KALKTI -- rayda tek dugme, ayrinti hesap panosunda.
sina("rayda hesap basina cip YOK, tek hesap dugmesi var",
     "p.limitler || []" not in _jsy and 'el("button", "hesap-hap")' in _jsy
     and "hesapDugmesiCiz(hd" in _jsy)
sina("dolu pencerenin kalan suresi ozet yazisinda (doluKalan)",
     "doluKalan(dolu[0]" in _jsy and "↻" in _jsy)
if not _node:
    print("  [ATLANDI] node bulunamadi -- kalanSure OLCULMEDI")
else:
    _bas = _jsy.find("function kalanSure(")
    _govde = _jsy[_bas:_jsy.find("\n}\n", _bas) + 2]
    _betik = _govde + """
const T = Date.parse("2026-09-27T12:00:00Z");
const d = (m) => new Date(T + m * 60000).toISOString();
console.log(JSON.stringify([kalanSure(d(68), T), kalanSure(d(6*1440+4*60+10), T),
  kalanSure(d(45), T), kalanSure(d(120), T), kalanSure(d(-5), T), kalanSure(d(1440), T)]));
"""
    _c = _sp.run([_node, "-e", _betik], capture_output=True, text=True,
                 encoding="utf-8", timeout=60)
    try:
        _r1 = _jy.loads(_c.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        _r1 = None
    sina("kalanSure calisiyor", _r1 is not None, (_c.stderr or "")[-200:])
    if _r1:
        sina("  1 sa 8 dk", _r1[0] == "1 sa 8 dk", str(_r1))
        sina("  6 gun 4 sa (dakika yuvarlanmaz, gun olunca atilir)", _r1[1] == "6 gün 4 sa", str(_r1))
        sina("  45 dk", _r1[2] == "45 dk", str(_r1))
        sina("  tam saat '2 sa'", _r1[3] == "2 sa", str(_r1))
        sina("  gecmis an BOS (uydurmaz)", _r1[4] == "", str(_r1))
        sina("  tam gun '1 gün'", _r1[5] == "1 gün", str(_r1))

print("")
print("22. HESAP PANOSU -- 'ilerde baska hesaplar olacak, karmasik olmasin'")
from ofis import hesap as _H22
_H22.ekle(ofis.db, ofis.proje_id, "codex", "codex")
# Musaitlik sahte motordan: her ad SAHTE uretir (gercek motora yine uzanilmaz).
_P.MOTOR_FABRIKASI = lambda ad, **kw: _Sahte(**kw)
_P._HESAP_ONBELLEK.clear()
_h22 = istemci.get("/api/hesaplar")
sina("/api/hesaplar 200", _h22.status_code == 200, _h22.text[:200])
_t22 = _h22.json() if _h22.status_code == 200 else {}
_hs22 = {h["ad"]: h for h in _t22.get("hesaplar", [])}
sina("codex hesabi DOLU (5s %100) ve en ustte",
     _hs22.get("codex", {}).get("durum") == "dolu"
     and (_t22.get("hesaplar") or [{}])[0].get("ad") == "codex", str(list(_hs22))[:200])
sina("kapatilan hesap listede KAPALI (gecmis okunur)",
     _hs22.get("is-hesabi", {}).get("durum") == "kapali")
sina("ozet sayilari var", "hazir" in _t22 and "toplam" in _t22 and "sira" in _t22)
sina("sinamada GERCEK motora uzanilmadi (musaitlik sahte fabrikadan)",
     all("SINAMA gercek motora" not in (h.get("sebep") or "") or h["durum"] == "kullanilamiyor"
         for h in _t22.get("hesaplar", [])))
_z22 = istemci.post("/api/hesaplar/tazele", json={})
sina("tazele 200 ve okunamayani SOYLUYOR (sahte motor yuzde vermez)",
     _z22.status_code == 200 and "okunamadi" in _z22.json(), _z22.text[:200])
_P.MOTOR_FABRIKASI = _yalniz_sahte

if not _node:
    print("  [ATLANDI] node bulunamadi -- hesap ozeti OLCULMEDI")
else:
    def _fn(ad):
        b = _jsy.find("function " + ad + "(")
        return _jsy[b:_jsy.find("\n}\n", b) + 2]
    _betik22 = "".join(_fn(a) for a in ("kalanSure", "doluKalan", "hesapOzetYazi")) + """
const T = Date.parse("2026-09-27T12:00:00Z");
const d = (m) => new Date(T + m * 60000).toISOString();
const dolu = {ad: "codex", durum: "dolu", en_yuksek: 1,
  pencereler: [{kullanim: 1, yenilenme: d(68)}, {kullanim: 0.19, yenilenme: d(9000)}]};
const iyi = {ad: "claude", durum: "hazir", en_yuksek: 0.53, pencereler: []};
const dik = {ad: "claude", durum: "dikkat", en_yuksek: 0.82, pencereler: []};
const boz = {ad: "codex2", durum: "kullanilamiyor", pencereler: []};
const kap = {ad: "eski", durum: "kapali", pencereler: []};
console.log(JSON.stringify([
  hesapOzetYazi({hesaplar: [dolu, iyi]}, T),
  hesapOzetYazi({hesaplar: [iyi, kap]}, T),
  hesapOzetYazi({hesaplar: [dik, iyi]}, T),
  hesapOzetYazi({hesaplar: [dolu, boz, iyi]}, T),
  hesapOzetYazi({hesaplar: [kap]}, T),
]));
"""
    _c22 = _sp.run([_node, "-e", _betik22], capture_output=True, text=True,
                   encoding="utf-8", timeout=60)
    try:
        _r22 = _jy.loads(_c22.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        _r22 = None
    sina("hesap ozeti calisiyor", _r22 is not None, (_c22.stderr or "")[-200:])
    if _r22:
        sina("  tek dolu hesap: ad + kalan sure", _r22[0] == {"sinif": "k", "yazi": "codex dolu · ↻ 1 sa 8 dk"}, str(_r22[0]))
        sina("  sorun yoksa 'hepsi rahat' (kapali sayilmaz)", _r22[1]["yazi"] == "hepsi rahat", str(_r22[1]))
        sina("  dikkat: en dolu yuzde", _r22[2] == {"sinif": "u", "yazi": "claude %82"}, str(_r22[2]))
        sina("  birden cok sorun SAYILIR", _r22[3]["yazi"] == "1 dolu · codex2 kullanılamıyor", str(_r22[3]))
        sina("  yalniz kapali hesap -> 'hesap yok'", _r22[4]["yazi"] == "hesap yok", str(_r22[4]))

# 29.09: TAKIM SOHBETI PANOSUNUN KENDI YAZMA KUTUSU. Kullanici "takim
# sohbetine yazamiyorum" demisti. Kutu akisin DISINDA (akis yeniden
# cizilir, yazilan kaybolmasin) ve alttaki satirla AYNI gondericiyi
# kullanir (iki kopya olmasin); takim onerisi kutunun ustunde cikar.
_h2 = _web.joinpath("index.html").read_text(encoding="utf-8")
_j2 = _web.joinpath("panel.js").read_text(encoding="utf-8")
_sy = _h2.find('id="sohbet-yaz"')
sina("sohbet panosunda yazma kutusu var", _sy > 0 and 'id="sohbet-girdi"' in _h2)
sina("  kutu akisin DISINDA (yeniden cizimde silinmez)",
     _sy > _h2.find('id="pano-sohbet"') and
     _h2[_h2.find('id="pano-sohbet"'):_sy].count("</div>") >= 1)
sina("  ayni gonderici (komutGonder) kutuyla cagriliyor",
     'komutGonder($("#sohbet-girdi"), f)' in _j2)
sina("  oneri yazilan yerin ustunde cikar (yer parametresi)",
     "takimOneriGoster(metin, r.oneriler || [], girdi, oneriYeri)" in _j2)
# 30.09: "dosya ekleme butonu belli olsun, ses ile gondermek de olsun".
sina("  dosya dugmesi YAZIYLA gorunur (yalniz simge degil)", " Dosya</button>" in _h2 and "📎" not in _h2[_h2.find('id="ek-sec"')-200:_h2.find('id="ek-sec"')+900])
sina("  cok satirli alan: Enter gonderir, Shift+Enter satir",
     '<textarea id="sohbet-girdi"' in _h2 and 'e.key === "Enter" && !e.shiftKey' in _j2)
sina("  sesle yaz dugmesi kutuda ve tek islev iki yerde",
     'id="sohbet-ses"' in _h2 and "sesleYaz(sg, sb)" in _j2
     and 'sesleYaz($("#komut-girdi"), $("#komut-ses"))' in _j2)
sina("  ses metni GONDERILMEZ, kutuya yazilir (insan duzeltir)",
     "komutGonder" not in _j2[_j2.find("function sesleYaz"):_j2.find("function sesleYaz") + 2000])
sina("  surukle-birak ekler", '"drop"' in _j2 and "ekYukle([...e.dataTransfer.files])" in _j2)
sina("  video/ses balonda oynar", "sohbet-ek-oynat" in _j2)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
