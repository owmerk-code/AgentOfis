# -*- coding: utf-8 -*-
"""TAKIM KOTA PAYI (06.10.2026, Asama 4). Jeton yakmaz.

Patron: "olsun, ayarlanabilir" -- varsayilan sinirsiz; takim payini
doldurunca YENI isi bekler, oteki takimlar surer, patrona pencere basina
bir kez soylenir, pencere yenilenince kendiliginden surer.

Sinanan: olcum (hesabin pencere dolulugu x takimin jeton orani), pencere
basindan onceki turlar sayilmaz, olculmeyen/yenilenmis pencere BILINMIYOR
(durdurmaz), kuyruk dolu takimin mesajini atlar ama otekini alir, halka
dolu takimin hazir isini baslatmaz (sebebi soyler), bildirim bir kez,
panel ayari ve kapisi.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, kullanim as K, kuyruk as Q, pay as P  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.orkestra import Orkestra  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-takim-payi-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Pay", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("MAGAZA", "MG")
KB = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "icerik", kanat_id=KA, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("mert", "lider", kanat_id=KB, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("can", "icerik", kanat_id=KB, motor="sahte", klasor=str(d))

simdi = datetime.now(timezone.utc)
yen5 = int((simdi + timedelta(hours=2)).timestamp())
yen7 = int((simdi + timedelta(days=3)).timestamp())


def tur(ajan, jeton, k5=0.5, k7=0.2, motor="claude", hesap="", gorev_id=None):
    K.tur_ozeti_yaz(db, ofis.proje_id, {
        "jeton": jeton, "basarili": True,
        "limit_pencere": {"pencereler": {"5s": {"kullanim": k5, "yenilenme": yen5},
                                         "7g": {"kullanim": k7, "yenilenme": yen7}}}},
        ajan_ad=ajan, motor=motor, hesap=hesap, gorev_id=gorev_id)


print("1. olcum")
sina("varsayilan pay SINIRSIZ (0) -> dolu degil", P.payi(db, KA) == 0
     and P.dolu_mu(db, ofis.proje_id, KA) is None)
# Pencere basindan ONCE bir tur (sayilmamali): 5 saatlik pencere yen5-5sa'te basladi.
eski = (datetime.fromtimestamp(yen5, timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
tur("can", 100000)
with db.baglanti() as c:
    c.execute("UPDATE olay SET olusturuldu = ? WHERE rowid = (SELECT MAX(rowid) FROM olay)", (eski,))
ga = ofis.tahta.gorev_ac("magaza isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
tur("ece", 900, gorev_id=ga["id"])          # MAGAZA isi
tur("can", 100)                             # YAZILIM (issiz tur -> kosanin takimi)
tur("lale", 0)                              # sifir jetonlu tur
P.pay_yaz(db, ofis.proje_id, KA, 40)
k = {s["pencere"]: s for s in P.kullanim(db, ofis.proje_id, KA) if s["motor"] == "claude"}
sina("5 saat: takim orani 0.9 (eski tur sayilmadi)", k.get("5s", {}).get("oran") == 0.9, str(k.get("5s")))
sina("5 saat: takim % = 0.5 x 0.9 = 0.45", k.get("5s", {}).get("takim_yuzde") == 0.45)
sina("7 gun: eski tur 7 gunluk pencereye GIRIYOR (orani dusuruyor)",
     k.get("7g", {}).get("oran") is not None and k["7g"]["oran"] < 0.1, str(k.get("7g")))
dl = P.dolu_mu(db, ofis.proje_id, KA)
sina("pay %40 < %45 -> DOLU (5 saatlik pencere)", dl is not None and dl["pencere"] == "5s", str(dl))
sina("payi olmayan oteki takim dolu DEGIL", P.dolu_mu(db, ofis.proje_id, KB) is None)
P.pay_yaz(db, ofis.proje_id, KA, 50)
sina("pay %50 -> dolu degil", P.dolu_mu(db, ofis.proje_id, KA) is None)
P.pay_yaz(db, ofis.proje_id, KA, 40)
for kotu in (-1, 101, "x"):
    try:
        P.pay_yaz(db, ofis.proje_id, KA, kotu)
        sina(f"gecersiz pay reddedildi ({kotu})", False)
    except ValueError:
        sina(f"gecersiz pay reddedildi ({kotu})", True)
tur("ece", 5000, k5=0.1, k7=0.05, motor="codex", gorev_id=ga["id"])     # BASKA hesap
k2 = {s["pencere"]: s for s in P.kullanim(db, ofis.proje_id, KA) if s["motor"] == "claude"}
sina("baska hesabin turu bu hesabin oranina girmiyor", k2["5s"]["oran"] == 0.9, str(k2["5s"]))
gelecek = datetime.now(timezone.utc) + timedelta(hours=3)
sina("pencere YENILENINCE pay bilinmiyor -> durdurmaz",
     P.dolu_mu(db, ofis.proje_id, KA, simdi_=gelecek) is None)

print("\n2. bildirim (pencere basina bir kez)")
dt = P.dolu_takimlar(db, ofis.proje_id)
P.dolu_takimlar(db, ofis.proje_id)
with db.baglanti() as c:
    n = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'kota_payi_dolu'").fetchone()[0]
    govde = (c.execute("SELECT govde FROM olay WHERE tur = 'kota_payi_dolu'").fetchone() or [""])[0]
sina("dolu takimlar listesi yalniz MAGAZA", list(dt) == [KA], str(list(dt)))
sina("patrona BIR KEZ soylendi", n == 1, str(n))
sina("metin kota dilinde ve ne zaman surecegini soyluyor",
     "MAGAZA" in govde and "%45" in govde and "yenilenince" in govde and "$" not in govde, govde)
from ofis import bildirim as B  # noqa: E402
iz = B.Izleyici(ofis)
iz.son_olay = 0
og = iz.topla()
sina("bildirim izleyicisi olayi aliyor (isaret metinde yok)",
     any(b == "Takımın kota payı doldu" and "[" not in m for b, m in og), str(og))

print("\n3. kuyruk: dolu takimin mesaji bekler, oteki surer")
qa = Q.ekle(ofis, "magaza mesaji", "lale")
qb = Q.ekle(ofis, "yazilim mesaji", "mert")
al = Q.sira_al(ofis, "seri1", atla_takimlar={KA})
sina("sira dolu MAGAZA'yi atlayip YAZILIM'i aldi", al and al["lider_ad"] == "mert", str(al and al["metin"]))
sina("MAGAZA mesaji BEKLIYOR (silinmedi)", any(x["lider_ad"] == "lale" for x in Q.bekleyenler(ofis)))
sina("yalniz dolu takim kaldiysa sira bos doner", Q.sira_al(ofis, "seri1", atla_takimlar={KA}) is None)
sina("pay kalkinca (atlanacak yok) MAGAZA mesaji alinir",
     (Q.sira_al(ofis, "seri1") or {}).get("lider_ad") == "lale")

print("\n4. halka: dolu takimin hazir isi baslamaz")
gb = ofis.tahta.gorev_ac("yazilim isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KB)
ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(cevap="KANIT terminal: x -> ok"))
oz = ork.tik(paralel=1)
eng = json.dumps(oz["engel"], ensure_ascii=False)
sina("MAGAZA isi baslamadi", ofis.tahta.gorev(ga["no"])["durum"] == "hazir", ofis.tahta.gorev(ga["no"])["durum"])
sina("sebep gorunur (kota payi)", f'"gorev_no": {ga["no"]}' in eng and "kota pay" in eng, eng[:300])
sina("YAZILIM isi basladi", ofis.tahta.gorev(gb["no"])["durum"] != "hazir", ofis.tahta.gorev(gb["no"])["durum"])
P.pay_yaz(db, ofis.proje_id, KA, 0)
ork.tik(paralel=1)
sina("pay kaldirilinca MAGAZA isi basladi", ofis.tahta.gorev(ga["no"])["durum"] != "hazir")

print("\n5. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
r = ist.post(f"/api/kanat/{KA}/duzenle", json={"kota_payi": 30})
sina("panelden pay yazildi", r.status_code == 200 and P.payi(db, KA) == 30, r.text[:200])
r = ist.post(f"/api/kanat/{KA}/duzenle", json={"kota_payi": 150})
sina("gecersiz pay 400", r.status_code == 400 and P.payi(db, KA) == 30, r.text[:200])
org = ist.get("/api/organizasyon").json()
kart = next(x for x in org["kanatlar"] if x["id"] == KA)
sina("organizasyon payi ve olculen kullanimi gosteriyor",
     kart.get("kota_payi") == 30 and isinstance(kart.get("kota_kullanim"), list)
     and any(s["pencere"] == "5s" and s["takim_yuzde"] == 0.45 for s in kart["kota_kullanim"]),
     str(kart.get("kota_kullanim"))[:300])
r = ist.post(f"/api/kanat/{KA}/duzenle", json={"ad": "MAGAZA"})
sina("pay verilmeyen duzenleme paya dokunmuyor", r.status_code == 200 and P.payi(db, KA) == 30)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
