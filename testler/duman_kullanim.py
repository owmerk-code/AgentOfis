# -*- coding: utf-8 -*-
"""KULLANIM: hangi hesap bagli, OFIS ne tuketti -- ve neyi OLCEMEDIGI.

Kullanici (22.09.2026): *"ben API kullanmiyorum, aboneliklerimi
kullaniyorum... hangi hesap bagli, limitleri ne durumda, anlik
kullanimi, ne zaman yenilenecegini takip edebilecegim bir alan."*

Istegin yarisi OLCULEBILIR degil ve asil sinanan sey bu: gosterge
olcemedigi seye "iyi" DEMEMELI. Bir gostergenin en kotu hali,
bilmedigini biliyormus gibi gostermesidir.

Dort soru:

1. OFISIN tukettigi DOGRU toplaniyor mu (motor/hesap kirilimiyla)?
2. Olculemeyen maliyet SIFIR sayiliyor mu? (sayilmamali -- `None`)
3. "Bu senin TOPLAM kullanimin degil" SOYLENIYOR mu?
4. Haftalik yenilenme hesabi dogru mu, ve HESAPLANAN oldugu
   isaretli mi?

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import kullanim as K

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


kok = Path(tempfile.mkdtemp(prefix="ofis-kullanim-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Kullanim", amac="olcum", basari_olcutu="dogru",
                     kok_klasor=str(kok))
ofis.kadro.ise_al("cinar", "backend", motor="claude", klasor=str(kok))
g = ofis.tahta.gorev_ac("is", neden="n", ana_hedef="h", kabul_olcutu="k")


def tur(jeton, maliyet, motor="claude", hesap="", basarili=True, model="x"):
    db.olay_yaz(ofis.proje_id, "tur_ozeti",
                json.dumps({"jeton": jeton, "maliyet_usd": maliyet,
                            "motor": motor, "hesap": hesap,
                            "model": model, "basarili": basarili}),
                ajan_ad="cinar", gorev_id=g["id"])


# --------------------------------------------------- 1. BOS OFIS
print("\n1. BOS OFIS -- uydurmuyor")
o = K.ozet(db, ofis.proje_id)
sina("tur yok", o["oturum"]["tur"] == 0)
sina("jeton yok", o["oturum"]["jeton"] == 0)
# OLCULEN sifir ile OLCULEMEYEN ayri. Hic tur yoksa maliyet
# BILINMIYOR, sifir DEGIL -- panelde bir kez odendi.
sina("maliyet SIFIR degil, BILINMIYOR", o["oturum"]["maliyet"] is None)


# ------------------------------------------------- 2. TOPLAMA
print("\n2. TOPLAMA -- motor/hesap kirilimiyla")
tur(1000, 0.10, motor="claude")
tur(2000, 0.20, motor="claude")
tur(3000, None, motor="codex", hesap="is")
o = K.ozet(db, ofis.proje_id)
p = o["oturum"]
sina("tur sayisi", p["tur"] == 3, str(p["tur"]))
sina("jeton toplandi", p["jeton"] == 6000, str(p["jeton"]))
# Fiyatsiz tur toplamdan DUSMEZ, ayri sayilir: bilinmeyen maliyeti
# sifir ilan etmek, gorunmeyen butceyi butce sanmaktir.
sina("yalniz OLCULEN maliyet toplandi",
     abs((p["maliyet"] or 0) - 0.30) < 1e-9, str(p["maliyet"]))
sina("fiyatsiz tur AYRI sayildi", p["fiyatsiz"] == 1, str(p["fiyatsiz"]))
sina("motor kirilimi var", "claude" in p["motorlar"], str(p["motorlar"].keys()))
sina("hesapli motor AYRI satir", "codex/is" in p["motorlar"],
     str(list(p["motorlar"].keys())))
sina("kirilim jetonu dogru",
     (p["motorlar"].get("claude") or {}).get("jeton") == 3000,
     str(p["motorlar"]))

# ESKI KAYIT motor tasimiyor (alan 22.09'da eklendi). Uydurmak yerine
# "kayitta yok" demek durust.
db.olay_yaz(ofis.proje_id, "tur_ozeti",
            json.dumps({"jeton": 500, "maliyet_usd": 0.01}),
            ajan_ad="cinar", gorev_id=g["id"])
p2 = K.ozet(db, ofis.proje_id)["oturum"]
sina("motorsuz ESKI kayit uydurulmuyor",
     "(kayitta yok)" in p2["motorlar"], str(list(p2["motorlar"].keys())))


# ---------------------------------------------- 3. PENCERE AYRIMI
print("\n3. PENCERE -- eski tur 5 saatlik pencereye girmiyor")
eski = (datetime.now(timezone.utc) - timedelta(hours=30)
        ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
with db.baglanti() as c:
    c.execute("INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, "
              "olusturuldu) VALUES (?, ?, ?, 'tur_ozeti', ?, ?)",
              (ofis.proje_id, "cinar", g["id"],
               json.dumps({"jeton": 99999, "maliyet_usd": 9.0,
                           "motor": "claude"}), eski))
o = K.ozet(db, ofis.proje_id)
sina("30 saat onceki tur 5 SAATLIK pencerede YOK",
     o["oturum"]["jeton"] == 6500, str(o["oturum"]["jeton"]))
sina("ama 7 GUNLUK pencerede VAR",
     o["hafta"]["jeton"] == 6500 + 99999, str(o["hafta"]["jeton"]))


# --------------------------------------------- 4. YENILENME HESABI
print("\n4. HAFTALIK YENILENME")
# Carsamba 03:00 UTC = Istanbul 06:00. OLCULDU: saglayicinin resetsAt'i.
# (Once 06:00 UTC yaziyordu -- yerel saat UTC sanilmisti.)
carsamba = datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)
y = K.haftalik_yenilenme(db, ofis.proje_id,
                         simdi_=carsamba - timedelta(hours=3))
sina("yenilenme dogru gune dusuyor", y["ne_zaman"] == carsamba,
     str(y["ne_zaman"]))
sina("kalan saat dogru", abs(y["kalan_saat"] - 3.0) < 0.2,
     str(y["kalan_saat"]))
# Tam anindaysa BIR SONRAKI haftaya gecmeli -- yoksa "0 saat kaldi"
# diye sonsuza kadar takili kalirdi.
y2 = K.haftalik_yenilenme(db, ofis.proje_id, simdi_=carsamba)
sina("yenilenme aninda SONRAKI haftaya geciyor",
     y2["ne_zaman"] == carsamba + timedelta(days=7), str(y2["ne_zaman"]))
# HESAPLANAN oldugu isaretli: olculen ile hesaplanani ayirt edememek
# bu projede video maliyetinde bir kez odendi.
sina("kaynak HESAPLANAN diye isaretli", "hesaplanan" in y["kaynak"])


# ------------------------------------- 5. OLCULMEDIYSE UYDURMUYOR
#
# Bu bolum 22.09'da "ofis claude.ai'daki yuzdeleri OKUYAMAZ" iddiasini
# SABITLIYORDU. Iddia YANLISTI (23.09.2026): CLI her turda
# `rate_limit_event` yolluyor, codex ayni seyi oturum kaydina yaziyor --
# ofis 64 kez okuyup atmisti. Ilke DEGISMEDI, olcum degisti: gosterge
# bilmedigini biliyormus gibi GOSTERMEZ. Henuz tek tur kosmamissa
# "olculmedi" der ve yuzde yazmaz.
print("\n5. OLCULMEDIYSE UYDURMUYOR")
m = K.metin(db, ofis.proje_id)
# Blok ONCEDEN GECIS'te biter: oradaki yuzdeler olcum degil ESIKTIR.
_blok = m.split("PENCERELER", 1)[1].split("ONCEDEN GECIS", 1)[0]
sina("olcum yokken 'henuz OLCULMEDI' diyor", "henuz OLCULMEDI" in _blok, _blok[:120])
sina("olcum yokken YUZDE UYDURMUYOR", "%" not in _blok, _blok[:120])
sina("'senin TOPLAM kullanimin DEGIL' hala ofisin tukettigi icin",
     "TOPLAM kullanimin DEGIL" in m)
sina("elle kullanimin ustune bineceGINI soyluyor", "yuksektir" in m.lower())
for h in K.hesap_durumu():
    sina(f"{h['motor']}: hesap satiri yuzde IDDIA ETMIYOR",
         "%" not in h["limit"], h["limit"][:60])


# --------------------------------- 6. SAGLAYICININ BILDIRDIGI OKUNUYOR
print("\n6. SAGLAYICININ BILDIRDIGI OKUNUYOR")
from ofis.motor.tip import limit_penceresi

su_an = datetime.now(timezone.utc)
ileri = lambda saat: int((su_an + timedelta(hours=saat)).timestamp())


def olcum(k5, y5, k7, y7, **ek):
    return limit_penceresi({"5s": {"kullanim": k5, "yenilenme": y5},
                            "7g": {"kullanim": k7, "yenilenme": y7}},
                           kaynak="sinama", **ek)


# Once ORTUK hesap adiyla (hesap == motor), sonra ajanin kendi
# basamagiyla (hesap == ""). IKISI AYNI HESAP: tek satir, en yenisi.
K.tur_ozeti_yaz(db, ofis.proje_id,
                {"jeton": 1, "limit_pencere": olcum(0.50, ileri(2), 0.60, ileri(50))},
                ajan_ad="cinar", motor="claude", hesap="claude")
K.tur_ozeti_yaz(db, ofis.proje_id,
                {"jeton": 1, "limit_pencere": olcum(0.71, ileri(2), 0.81, ileri(50))},
                ajan_ad="cinar", motor="claude", hesap="")
K.tur_ozeti_yaz(db, ofis.proje_id,
                {"jeton": 1, "limit_pencere": olcum(0.06, ileri(4), 0.01, ileri(120),
                                                    plan="plus")},
                ajan_ad="cinar", motor="codex", hesap="codex2")
pen = {(p["motor"], p["hesap"]): p for p in K.son_pencereler(db, ofis.proje_id)}
sina("ortuk ad ile bos hesap TEK hesap sayiliyor",
     sum(1 for k in pen if k[0] == "claude") == 1, str(list(pen)))
cl = pen.get(("claude", "")) or {"pencereler": {}}
sina("EN YENI olcum aliniyor",
     (cl["pencereler"].get("5s") or {}).get("kullanim") == 0.71, str(cl))
sina("tanimli hesap AYRI satir", ("codex", "codex2") in pen, str(list(pen)))
sina("plan tasiniyor", (pen.get(("codex", "codex2")) or {}).get("plan") == "plus")
sina("olcumun YASI biliniyor", cl.get("yas_dk") is not None and cl["yas_dk"] >= 0)
m = K.metin(db, ofis.proje_id)
sina("metin olculen yuzdeyi yaziyor", "%71" in m and "%81" in m, m[:300])
sina("metin olcumun YASINI yaziyor", "dk once" in m)
sina("metin bunun HESABIN TOPLAMI oldugunu soyluyor", "TOPLAMI" in m)
y = K.ozet(db, ofis.proje_id)["yenilenme"]
sina("haftalik yenilenme artik OLCULEN", "olculen" in y["kaynak"], y["kaynak"])
sina("olculen yenilenme saglayicinin verdigi an",
     int(y["ne_zaman"].timestamp()) == ileri(50), str(y["ne_zaman"]))


# ------------------------------------ 7. YENILENMIS PENCERE: yuzde YOK
print("\n7. YENILENMIS PENCERENIN YUZDESI GOSTERILMIYOR")
# Olcum 5 saatlik pencere yenilenmeden ONCE alindi: %37 artik yanlis.
K.tur_ozeti_yaz(db, ofis.proje_id,
                {"jeton": 1, "limit_pencere": olcum(0.37, ileri(-1), 0.83, ileri(49))},
                ajan_ad="cinar", motor="claude", hesap="")
# Cıplak indeksleme YOK: olcum hic gelmezse test COKMEMELI, KALMALI --
# coken bir test geri kalan sinamalari hic kosturmaz (mutasyonda oldu).
cl = {(p["motor"], p["hesap"]): p for p in K.son_pencereler(db, ofis.proje_id)
      }.get(("claude", ""), {})
w5 = (cl.get("pencereler") or {}).get("5s") or {}
w7 = (cl.get("pencereler") or {}).get("7g") or {}
sina("yenilenmis pencere YENILENDI isaretli", w5.get("yenilendi") is True, str(cl)[:120])
sina("yenilenmis pencerenin yuzdesi None", "kullanim" in w5 and w5["kullanim"] is None)
sina("yenilenmemis pencere yine gosteriliyor", w7.get("kullanim") == 0.83)
m = K.metin(db, ofis.proje_id)
sina("metinde bayat yuzde YOK", "%37" not in m, m[:300])
sina("metin YENILENDI diyor", "YENILENDI" in m)


# ------------------------------------- 8. YAZICI ve ADAPTORLER
print("\n8. TEK YAZICI ve ADAPTORLER")
sina("bozuk alan atiliyor (None/eksi)",
     limit_penceresi({"5s": {"kullanim": None, "yenilenme": 5},
                      "7g": {"kullanim": -1, "yenilenme": 5}}, kaynak="x") is None)
K.tur_ozeti_yaz(db, ofis.proje_id, {"jeton": 1, "limit_pencere": "bozuk"},
                motor="claude", yol="deneme")
with db.baglanti() as c:
    son_govde = c.execute("SELECT govde FROM olay WHERE tur='tur_ozeti' "
                          "ORDER BY id DESC LIMIT 1").fetchone()["govde"]
sina("sozluk olmayan olcum deftere YAZILMIYOR",
     "limit_pencere" not in json.loads(son_govde), son_govde)
sina("yol etiketi yaziliyor", json.loads(son_govde).get("yol") == "deneme")

from ofis.motor.claude import claude_pencereleri
cp = claude_pencereleri({
    "status": "allowed_warning",
    "unifiedWindows": {"five_hour": {"utilization": 0.71, "resetsAt": 1790129400},
                       "seven_day": {"utilization": 0.81, "resetsAt": 1790132400}}})
sina("claude: olculen bicim ayristiriliyor",
     cp and cp["pencereler"]["5s"]["kullanim"] == 0.71
     and cp["pencereler"]["7g"]["yenilenme"] == 1790132400, str(cp))
sina("claude: hal tasiniyor", (cp or {}).get("hal") == "allowed_warning")
tek = claude_pencereleri({"status": "allowed", "rateLimitType": "five_hour",
                          "utilization": 0.2, "resetsAt": 1790129400})
sina("claude: tek pencereli bicim de okunuyor",
     (tek or {}).get("pencereler", {}).get("5s", {}).get("kullanim") == 0.2, str(tek))
sina("claude: bilgi yoksa None (sifir DEGIL)", claude_pencereleri(None) is None
     and claude_pencereleri({"status": "allowed"}) is None)

from ofis.motor.codex import codex_pencereleri
ev = kok / "codex-ev"
kayit = ev / "sessions" / "2026" / "09" / "23"
kayit.mkdir(parents=True)
(kayit / "rollout-2026-09-23T03-21-41-aaaa-bbbb.jsonl").write_text(
    json.dumps({"type": "event_msg", "payload": {"type": "token_count",
                "rate_limits": {"primary": {"used_percent": 1.0, "window_minutes": 300,
                                            "resets_at": 1790130000}}}}) + "\n"
    + json.dumps({"type": "event_msg", "payload": {"type": "token_count",
                  "rate_limits": {"primary": {"used_percent": 6.0, "window_minutes": 300,
                                              "resets_at": 1790130903},
                                  "secondary": {"used_percent": 1.0,
                                                "window_minutes": 10080,
                                                "resets_at": 1790717703},
                                  "plan_type": "plus"}}}) + "\n",
    encoding="utf-8")
xp = codex_pencereleri(str(ev), "aaaa-bbbb")
sina("codex: SON token_count okunuyor",
     xp and xp["pencereler"]["5s"]["kullanim"] == 0.06, str(xp))
sina("codex: 10080 dk -> 7g", (xp or {}).get("pencereler", {}).get("7g", {}).get("yenilenme") == 1790717703)
sina("codex: plan tasiniyor", (xp or {}).get("plan") == "plus")
sina("codex: BASKA oturumun kaydi okunmuyor", codex_pencereleri(str(ev), "cccc") is None)
sina("codex: oturum kimligi yoksa None", codex_pencereleri(str(ev), "") is None)


# ----------------------------- 9. UCTAN UCA: koltuk olcumu deftere TASIYOR
print("\n9. UCTAN UCA -- koltuk adaptorun olcumunu deftere tasiyor")
from ofis.koltuk import Koltuk
from ofis.motor.sahte import SahteMotor

_lp = olcum(0.44, ileri(3), 0.55, ileri(60))
ofis.kadro.ise_al("ayaz", "backend", motor="sahte", klasor=str(kok))
g2 = ofis.tahta.gorev_ac("olcum isi", neden="n", ana_hedef="h",
                         kabul_olcutu="k", yazma_alani=["olcum/"])
Koltuk(ofis, motor_fabrikasi=lambda ad, **k: SahteMotor(limit_pencere=_lp)
       ).kos(g2["no"], "ayaz")
with db.baglanti() as c:
    satir = c.execute("SELECT govde FROM olay WHERE tur='tur_ozeti' AND gorev_id=? "
                      "ORDER BY id DESC LIMIT 1", (g2["id"],)).fetchone()
veri = json.loads(satir["govde"]) if satir else {}
sina("koltugun tur_ozeti'nde olcum VAR", veri.get("limit_pencere") == _lp, str(veri)[:200])
sina("koltugun tur_ozeti'nde motor VAR", veri.get("motor") == "sahte", str(veri.get("motor")))

print("\n10. ONCEDEN GECIS ESIKLERI GORUNUR -- gorunmeyen ayar, ayar degildir")
m = K.metin(db, ofis.proje_id)
sina("esikler ekranda", "ONCEDEN GECIS" in m and "isci   5s %80" in m, m[-400:])
db.ayar_yaz(ofis.proje_id, "gecis_esigi:isci:5s", "0.7")
sina("ayarlanan esik ekrana ULASIYOR", "isci   5s %70" in K.metin(db, ofis.proje_id))
db.ayar_yaz(ofis.proje_id, "onceden_gecis", "kapali")
sina("KAPALI oldugu soyleniyor", "KAPALI" in K.metin(db, ofis.proje_id))

print("\n9. E11 VERI GOCU -- eski codex 0.0 -> olculemedi")
import sqlite3 as _sq
_gdb = Veritabani(kok / "goc.sqlite3")
_go = Ofis.proje_ac(_gdb, "Goc", amac="a", basari_olcutu="b", kok_klasor=str(kok))
for _d in ({"motor": "codex", "model": "gpt-5.6-sol", "maliyet_usd": 0.0, "jeton": 9},
           {"model": "gpt-5.6-luna", "maliyet_usd": 0, "jeton": 5},
           {"motor": "claude", "model": "claude-haiku", "maliyet_usd": 0.0, "jeton": 0},
           {"motor": "codex", "maliyet_usd": None, "jeton": 3},
           {"motor": "claude", "maliyet_usd": 0.12, "jeton": 7}):
    _gdb.olay_yaz(_go.proje_id, "tur_ozeti", json.dumps(_d))
_c = _sq.connect(str(_gdb.yol))
_c.execute("PRAGMA user_version = 0")
_c.commit()
_c.close()
Veritabani(kok / "goc.sqlite3")              # acilis gocu kosturur


def _maliyetler():
    _c = _sq.connect(str(_gdb.yol))
    try:
        return [json.loads(g).get("maliyet_usd") for (g,) in _c.execute(
            "SELECT govde FROM olay WHERE tur='tur_ozeti' ORDER BY rowid")]
    finally:
        _c.close()


_m = _maliyetler()
sina("codex 0.0 -> None (motor alani ile)", _m[0] is None, str(_m))
sina("codex 0 -> None (yalniz model adi ile)", _m[1] is None, str(_m))
sina("Claude'un GERCEK sifirina dokunulmadi", _m[2] == 0.0, str(_m))
sina("zaten None olan ayni", _m[3] is None)
sina("fiyatli tur ayni", _m[4] == 0.12)
_c = _sq.connect(str(_gdb.yol))
sina("surum 1'e yazildi", _c.execute("PRAGMA user_version").fetchone()[0] >= 1)
_c.close()
_gdb.olay_yaz(_go.proje_id, "tur_ozeti", json.dumps(
    {"motor": "codex", "maliyet_usd": 0.0}))
Veritabani(kok / "goc.sqlite3")
sina("goc IKINCI KEZ kosmuyor (yeni kayda dokunmadi)", _maliyetler()[5] == 0.0)


print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
