"""TAKIM SOHBETI duman testi -- `ofis/takim.py` ve baglandigi uc yuzey.

Jeton yakmaz: butun motorlar `sahte`. Sinanan:
  1. `@ad` ayristirma (is: oneki, Turkce harf, adres yok)
  2. yonlendirme: lider / not / soru / is -- ve REDDETTIKLERI
  3. tek akis: mesaj + cevap + not + ajan->ajan + olaylar, kanat suzgeci
  4. `@ajan is:` -> triyaj SORULMAZ, plan o ajana verilmek ZORUNDA
     (baska sahip reddedilir ve ret lidere ogretilir), olcut kapisi durur
  5. panel: /api/lidere yonlendirir, /api/takim akisi verir
  6. kabuk: `konus "@ad ..."` ayni yonlendiriciden gecer
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
import time as _t
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from ofis import Ofis, Veritabani
from ofis import takim
from ofis.sohbet import Sohbet, SohbetHatasi
from ofis.motor.sahte import SahteMotor
import ofis.panel as _P

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== takim sohbeti duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-takim-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Takim", amac="Takim sohbeti", basari_olcutu="yonlenir")
kn1 = ofis.kanat_ac("URUN", "UR")
kn2 = ofis.kanat_ac("PAZARLAMA", "PZ")
kn3 = ofis.kanat_ac("LIDERSIZ", "LS")
for ad, meslek, kn, lider in (("demir", "lider", kn1, True),
                              ("cinar", "backend", kn1, False),
                              ("bilge", "arastirma", kn1, False),
                              ("ruzgar", "lider", kn2, True),
                              ("ege", "metin", kn2, False),
                              ("yalniz", "metin", kn3, False)):
    (kok / ad).mkdir()
    ofis.kadro.ise_al(ad, meslek, kanat_id=kn, lider_mi=lider, tur="eller",
                      motor="sahte", klasor=str(kok / ad))

# ---------------------------------------------------------------------------
print("1. AYRISTIRMA")
a = takim.ayristir("@cinar iş: sayilar.py yaz")
sina("`@ad is:` -> is", a == {"ad": "cinar", "metin": "sayilar.py yaz", "is_mi": True}, str(a))
a = takim.ayristir("@cinar IS - sunu yap")
sina("buyuk harf ve tire ile de is", a["is_mi"] and a["metin"] == "sunu yap", str(a))
a = takim.ayristir("@bilge, kaynak neydi?")
sina("virgul yutulur, is DEGIL", a == {"ad": "bilge", "metin": "kaynak neydi?", "is_mi": False}, str(a))
a = takim.ayristir("ofis ne durumda @cinar")
sina("adres yalniz BASTA sayilir", a["ad"] == "" and a["metin"].startswith("ofis"), str(a))
sina("Turkce harfli ad", takim.ayristir("@çınar selam")["ad"] == "çınar")
sina("'isler' kelimesi is oneki sayilmaz",
     not takim.ayristir("@cinar isler nasil")["is_mi"])

# ---------------------------------------------------------------------------
print("\n2. YONLENDIRME")
y = takim.yonlendir(ofis, "merhaba")
sina("adres yok -> lider", y["yol"] == "lider" and y["lider"] == "", str(y))
y = takim.yonlendir(ofis, "@ruzgar kampanya nasil")
sina("@lider_adi -> o lider", y["yol"] == "lider" and y["lider"] == "ruzgar", str(y))
y = takim.yonlendir(ofis, "@lider selam")
sina("@lider -> lider (kanattan secilir)", y["yol"] == "lider" and y["lider"] == "")
y = takim.yonlendir(ofis, "@bilge kaynak neydi")
sina("bosta ajan -> SORU", y["yol"] == "soru" and y["ajan"] == "bilge", str(y))
y = takim.yonlendir(ofis, "@Bilge kaynak neydi")
sina("buyuk/kucuk harf farki ayni kisi", y["ajan"] == "bilge", str(y))
g = ofis.tahta.gorev_ac("Calisan is", neden="n", ana_hedef="h", kabul_olcutu="k",
                        yazma_alani=["api/"], kanat_id=kn1)
ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
y = takim.yonlendir(ofis, "@cinar portu 8080 yap")
sina("elinde is olan ajan -> NOT (tur surerken ulasir)",
     y["yol"] == "not" and y["gorev_no"] == g["no"], str(y))
y = takim.yonlendir(ofis, "@ege iş: slogan yaz")
sina("`is:` -> IS, plani o takimin LIDERI yazar",
     y["yol"] == "is" and y["ajan"] == "ege" and y["lider"] == "ruzgar", str(y))
y = takim.yonlendir(ofis, "@cinar iş: ikinci is")
sina("elinde is olsa da `is:` IS'tir (not degil)", y["yol"] == "is", str(y))
for metin, beklenen in (("@yok selam", "diye biri yok"),
                        ("@demir iş: kendin yap", "lider"),
                        ("@yalniz iş: yaz", "lider yok"),
                        ("@cinar", "Bos mesaj")):
    try:
        takim.yonlendir(ofis, metin)
        sina(f"'{metin}' REDDEDILIYOR", False, "ret yok")
    except takim.TakimHatasi as exc:
        sina(f"'{metin}' REDDEDILIYOR ve sebebi soyleniyor", beklenen in str(exc), str(exc))
try:
    takim.yonlendir(ofis, "@yok selam")
except takim.TakimHatasi as exc:
    sina("  bilinmeyen adda gecerli adlar SAYILIYOR", "@cinar" in str(exc) and "@ege" in str(exc))
y = takim.yonlendir(ofis, "@yalniz selam")
sina("lidersiz takimda SORU yine gider (lider gerekmez)", y["yol"] == "soru", str(y))

# ---------------------------------------------------------------------------
print("\n3. TEK AKIS")
m1 = ofis.postane.soru_sor("insan", "demir", "ne durumdayiz", mod="uyandiran")
ofis.postane.cevapla(m1["id"], "iyiyiz", cevaplayan="demir")
ofis.postane.not_birak("cinar", "portu 8080 yap")
m3 = ofis.postane.soru_sor("cinar", "bilge", "kaynak ne?", gorev_no=g["no"])
ofis.postane.soru_sor("insan", "ege", "slogan fikrin?", mod="uyandiran")
ofis.db.olay_yaz(ofis.proje_id, "rapor", "cinar'in raporu", ajan_ad="cinar",
                 gorev_id=g["id"])
ofis.db.olay_yaz(ofis.proje_id, "arac", "Bash", ajan_ad="cinar")   # girmemeli
ak = takim.akis(ofis)
turler = [(x["kimden"], x["kime"], x["tur"]) for x in ak]
sina("insan->lider SOHBET ve cevabi", ("insan", "demir", "sohbet") in turler
     and ("demir", "insan", "cevap") in turler, str(turler))
sina("cevap sorusundan SONRA", turler.index(("insan", "demir", "sohbet"))
     < turler.index(("demir", "insan", "cevap")))
notlar = [x for x in ak if x["tur"] == "not"]
sina("not akista, ULASMADI diye", notlar and notlar[0]["ulasti"] is False, str(notlar))
sina("ajan->ajan sorusu akista (haritada kalmiyor)", ("cinar", "bilge", "soru") in turler)
sina("cevapsiz soru BEKLIYOR isaretli",
     any(x["id"] == m3["id"] and x["bekliyor"] for x in ak))
sina("rapor olayi akista", any(x["tur"] == "rapor" and x["gorev_no"] == g["no"] for x in ak))
sina("terminal olayi (arac) akista YOK", not any(x["metin"] == "Bash" for x in ak))
sina("sessiz mesaj akista YOK", all(x["tur"] != "" for x in ak))
ak2 = takim.akis(ofis, kanat_id=kn2)
sina("kanat suzgeci: PAZARLAMA yalniz kendi ajanlari",
     ak2 and all(x["kimden"] in ("insan", "ege", "ruzgar") and x["kime"] in ("", "insan", "ege", "ruzgar")
                 for x in ak2), str([(x["kimden"], x["kime"]) for x in ak2]))
sina("akis adet siniri", len(takim.akis(ofis, adet=2)) == 2)
# OLCULDU (29.09.2026): ilk surum 600 harfte KESIYORDU; liderin cevabi
# panelde "**3..." diye yarida kaldi. Katlamak arayuzun isi.
uzun = "madde " * 500
mu = ofis.postane.soru_sor("insan", "demir", "uzun anlat", mod="uyandiran")
ofis.postane.cevapla(mu["id"], uzun.strip(), cevaplayan="demir")
cev = [x for x in takim.akis(ofis) if x["id"] == mu["id"] and x["tur"] == "cevap"]
sina("uzun cevap KESILMEDEN geliyor", cev and len(cev[0]["metin"]) == len(uzun.strip()),
     str(cev and len(cev[0]["metin"])))
sina("konusanin meslegi geliyor (demir · lider)", cev and cev[0]["meslek"] == "lider")
rap = [x for x in takim.akis(ofis) if x["tur"] == "rapor"]
sina("is etiketi isin SU ANKI durumu", rap and rap[0]["gorev_durum"] == "calisiyor",
     str(rap and rap[0]["gorev_durum"]))
_js = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
_balon = _js.split("function takimBalonu")[1].split("async function cizSohbet")[0]
sina("panel: uzun metin 'Tamamini oku' ile katlaniyor",
     "Tamamını oku" in _balon and "katli" in _balon)
sina("panel: ajan mesajinda 'Terminalde goster'", "Terminalde göster" in _balon)
sina("panel: ajan metni innerHTML ile BASILMIYOR",
     "innerHTML" not in _balon and "innerHTML" not in _js.split("function kalinYaz")[1].split("}\n")[0])

# ---------------------------------------------------------------------------
print("\n3b. PATRONUN SORUSU TAKIMIN SON KONUSMASINI GORUR")
ms = ofis.postane.soru_sor("insan", "bilge", "hangisi daha iyi?", mod="uyandiran")
with ofis.db.baglanti() as c:
    ms = dict(c.execute("SELECT m.*, g.no AS gorev_no FROM mesaj m LEFT JOIN gorev g "
                        "ON g.id = m.gorev_id WHERE m.id = ?", (ms["id"],)).fetchone())
mt = ofis.danisma.soru_metni(ms)
sina("patronun sorusunda takim sohbeti blogu var", "TAKIM SOHBETINDE SON" in mt)
sina("  son konusma iceride (lider cevabi)", "iyiyiz" in mt, mt[-600:])
sina("  sorunun KENDISI blokta tekrar etmiyor",
     mt.count("hangisi daha iyi?") == 1, str(mt.count("hangisi daha iyi?")))
with ofis.db.baglanti() as c:
    ma = dict(c.execute("SELECT m.*, g.no AS gorev_no FROM mesaj m LEFT JOIN gorev g "
                        "ON g.id = m.gorev_id WHERE m.id = ?", (m3["id"],)).fetchone())
sina("ajanlar ARASI danismada blok YOK (taze goz bilincli)",
     "TAKIM SOHBETINDE SON" not in ofis.danisma.soru_metni(ma))
sina("blok SINIRLI (8 oge)",
     mt.split("TAKIM SOHBETINDE SON")[1].split("## SORUSU")[0].count("\n- ") <= 8)

# ---------------------------------------------------------------------------
print("\n4. `@ajan is:` -- lider planlar, sahip patronun secimi")


class Sirali(SahteMotor):
    """Her turda siradaki cevabi verir; biterse sonuncuyu tekrarlar."""
    kuyruk: list = []
    istemler: list = []

    # Cevap TURDA secilir, kurulusta degil: zincir musaitlik sorarken de
    # fabrikayi cagirir; kurulusta secseydik kuyruk yanlis anda tukenirdi
    # (duman_zincir'de bir kez odenen tuzak).
    def __init__(self, **k):
        super().__init__(cevap="")

    def tur_kos(self, metin, **ayar):
        Sirali.istemler.append(metin)
        self.cevap = Sirali.kuyruk.pop(0) if len(Sirali.kuyruk) > 1 else Sirali.kuyruk[0]
        return super().tur_kos(metin, **ayar)


def plan(sahip):
    return json.dumps({"gerekce": "tek parca is", "kollar": [
        {"baslik": "Slogan", "neden": "kampanya", "kabul_olcutu": "3 slogan dosyada",
         "sahip": sahip, "yazma_alani": ["slogan.md"]}]})


Sirali.kuyruk = [plan("ruzgar_degil_ege_olmali"), plan("ege"), "rapor: yapildi"]
Sirali.istemler = []
s = Sohbet(ofis, motor_fabrikasi=lambda ad, **k: Sirali())
olaylar = list(s.konus("uc slogan yaz", lider_ad="ruzgar", atanan="ege", azami_tik=0))
ilk = Sirali.istemler[0] if Sirali.istemler else ""
sina("TRIYAJ SORULMADI (ilk tur dogrudan planlama)",
     "PATRON ISI KIME" in ilk and '"karar": "cevap"' not in ilk, ilk[:120])
sina("  plan istemi ajani soyluyor", "**ege**" in ilk)
sina("yanlis sahipli plan REDDEDILDI ve ret lidere ogretildi",
     len(Sirali.istemler) >= 2 and "Patron bu isi ege'a verdi" in Sirali.istemler[1],
     str(len(Sirali.istemler)))
acilan = [x for x in ofis.tahta.liste() if x["baslik"] == "Slogan"]
sina("is ACILDI ve sahibi ege", acilan and acilan[0]["sahip"] in ("ege", ""),
     str([(x["no"], x["sahip"]) for x in acilan]))
sina("  kabul olcutu plandan geldi (kapi atlanmadi)",
     acilan and acilan[0]["kabul_olcutu"] == "3 slogan dosyada")
with ofis.db.baglanti() as c:
    govde = c.execute("SELECT govde FROM mesaj WHERE gonderen='insan' AND alici='ruzgar' "
                      "ORDER BY rowid DESC LIMIT 1").fetchone()["govde"]
sina("sohbete `@ege is:` diye yazildi", govde.startswith("@ege is:"), govde)
with ofis.db.baglanti() as c:
    kararlar = c.execute("SELECT 1 FROM karar WHERE proje_id=? AND gerekce LIKE ?",
                         (ofis.proje_id, "%dogrudan @ege%")).fetchall()
sina("karar gunlugune 'patron dogrudan verdi' yazildi", bool(kararlar))
tri = [o for o in olaylar if o["tur"] == "triyaj"]
sina("triyaj olayi yine akiyor (yol=dagit)", tri and tri[0]["govde"] == "dagit")
for atanan, beklenen in (("yok", "diye bir ajan yok"), ("ruzgar", "lider"),
                         ("cinar", "takiminda degil")):
    try:
        list(Sohbet(ofis, motor_fabrikasi=lambda ad, **k: Sirali()).konus(
            "x", lider_ad="ruzgar", atanan=atanan, azami_tik=0))
        sina(f"atanan={atanan} REDDEDILIYOR", False, "ret yok")
    except SohbetHatasi as exc:
        sina(f"atanan={atanan} REDDEDILIYOR", beklenen in str(exc), str(exc))

# ---------------------------------------------------------------------------
print("\n5. PANEL")


def _yalniz_sahte(ad, **kw):
    if ad != "sahte":
        raise RuntimeError("testte gercek motor YASAK")
    return SahteMotor(cevap="Cevabim: kaynak resmi belge.")


_P.MOTOR_FABRIKASI = _yalniz_sahte
istemci = TestClient(_P.olustur(db_yolu))
r = istemci.post("/api/lidere", json={"metin": "@cinar portu 9090 yap", "kanat": ""})
sina("@calisan ajan -> NOT", r.status_code == 200 and r.json().get("yol") == "not", r.text[:160])
r = istemci.post("/api/lidere", json={"metin": "@bilge kaynak neydi", "kanat": ""})
sina("@bosta ajan -> SORU (danisma)", r.status_code == 200 and r.json().get("yol") == "soru", r.text[:160])
for _ in range(100):
    if not _P._DANISMA["calisiyor"]:
        break
    _t.sleep(0.05)
r = istemci.post("/api/lidere", json={"metin": "@hayalet selam", "kanat": ""})
sina("bilinmeyen ad 400 ve adlar sayiliyor", r.status_code == 400 and "@cinar" in r.text, r.text[:160])
r = istemci.post("/api/lidere", json={"metin": "@demir iş: yap", "kanat": ""})
sina("lidere is: 400", r.status_code == 400, r.text[:120])
t = istemci.get("/api/takim").json()
tt = [(x["kimden"], x["kime"], x["tur"]) for x in t["ogeler"]]
sina("/api/takim not'u gosteriyor", ("insan", "cinar", "not") in tt, str(tt[-6:]))
sina("/api/takim soru ve CEVABI gosteriyor",
     ("insan", "bilge", "soru") in tt and ("bilge", "insan", "cevap") in tt, str(tt[-6:]))
t2 = istemci.get("/api/takim", params={"kanat": kn2}).json()
sina("/api/takim kanat suzgeci", all(x["kimden"] in ("insan", "ege", "ruzgar")
                                     for x in t2["ogeler"]))
sina("/api/takim bekleyene akis alani koyuyor",
     all("akis" in x for x in t["ogeler"]))
# is yolu: lider arka planda kosar; planin ege'ye gittigi olculur
Sirali.kuyruk = [plan("ege"), "rapor"]
_P.MOTOR_FABRIKASI = lambda ad, **kw: Sirali()
r = istemci.post("/api/lidere", json={"metin": "@ege iş: iki slogan daha", "kanat": ""})
sina("@ajan is: -> lider kosuyor, atanan ege",
     r.status_code == 200 and r.json().get("atanan") == "ege" and r.json().get("alici") == "ruzgar",
     r.text[:160])
for _ in range(200):
    if not _P._KOSU["calisiyor"]:
        break
    _t.sleep(0.05)
yeni = [x for x in ofis.tahta.liste() if x["baslik"] == "Slogan"]
sina("  panelden verilen is de ege'ye acildi", len(yeni) >= 2, str(len(yeni)))
_P.MOTOR_FABRIKASI = _yalniz_sahte

# ---------------------------------------------------------------------------
print("\n6. KABUK")
from ofis import kabuk
import io
import contextlib


def kabuk_konus(mesaj):
    ns = SimpleNamespace(db=str(db_yolu), proje="Takim", mesaj=mesaj, klasor=[],
                         lider="", zaman_asimi=None, azami_tik=0, paralel=1, izin=[])
    tampon = io.StringIO()
    try:
        with contextlib.redirect_stdout(tampon):
            kabuk.komut_konus(ns)
        return tampon.getvalue(), None
    except SystemExit as exc:
        return tampon.getvalue(), str(exc)
    except Exception as exc:   # cokme KALDI sayilir; geri kalan sinamalar kossun
        return tampon.getvalue(), f"COKTU: {type(exc).__name__}: {exc}"


cikti, hata = kabuk_konus("@cinar portu 7070 yap")
sina("kabuk: @calisan ajan -> NOT", hata is None and "NOT -> cinar" in cikti, (hata or cikti)[-200:])
cikti, hata = kabuk_konus("@hayalet selam")
sina("kabuk: bilinmeyen ad REDDEDILIYOR", hata is not None and "@cinar" in hata, str(hata))
cikti, hata = kabuk_konus("adres yok, iki lider var")
sina("kabuk: iki liderli ofiste adressiz mesaj COKMEDEN reddediliyor",
     hata is not None and "COKTU" not in hata and "lider" in hata, str(hata))
with ofis.db.baglanti() as c:
    n = c.execute("SELECT COUNT(*) FROM mesaj WHERE mod='yonlendirme' AND alici='cinar'").fetchone()[0]
sina("kabuk ve panel AYNI defteri kullandi (3 not)", n == 3, str(n))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
