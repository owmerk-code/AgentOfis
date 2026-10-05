# -*- coding: utf-8 -*-
"""Organizasyon duman testi -- meslek katalogu, sirket agaci, takimin Yonet'i.

Patron (05.10.2026): "her takimin yonet kismi olsun; motorlari, modelleri,
ajanlari buradan yonetelim" + rakibin "Organizasyon -- Sirket agaci".

Sinanan: meslek katalogu (varsayilan, ayarla ezme, geri donme, kapi modeli
reddi, kurulu olmayan motorda yedek) · katalogdan ise alma · tasi / cikar
(arsiv) / lider yap kurallari (acik is, lider, ad geri donmez) · karakter ·
panel uclari (organizasyon, kadro secenek, ise alma, takim duzenle/sil,
katalog, sablon kaydet) · cok takim.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import ofis.motor as _motor
import ofis.panel as _panel
from ofis import Ofis, Veritabani, roller as R, sablon as S
from ofis.kadro import KadroHatasi
from ofis.ekip import Ekip

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


def reddedilir(islev, parca: str = "") -> bool:
    try:
        islev()
    except (KadroHatasi, R.RolHatasi, S.SablonHatasi) as exc:
        return parca.lower() in str(exc).lower()
    return False


# Makinede hangi motorun kurulu oldugu sinamayi DEGISTIRMEZ: uc motor da var.
MUSAIT = {"claude": True, "codex": True, "gemini": True, "sahte": True}
_motor.musait_motorlar = lambda: dict(MUSAIT)
_panel.musait_motorlar = lambda: dict(MUSAIT)
S.musait_motorlar = lambda: dict(MUSAIT)
import ofis.ekip as _ekip_mod
_ekip_mod.musait_motorlar = lambda: dict(MUSAIT)

print("== organizasyon duman testi ==\n")
kok = Path(tempfile.mkdtemp(prefix="ofis-org-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Org Projesi", amac="sina", basari_olcutu="tutar")
pid = ofis.proje_id
web = ofis.kanat_ac("WEB", "WE")
magaza = ofis.kanat_ac("MAGAZA", "MG")

# --------------------------------------------------------------------------
print("1. MESLEK KATALOGU")
k = R.meslek_katalogu(db, pid)
sina("her rolun katalog satiri var", set(k) == set(R.ROLLER) == set(R.MESLEK_BASLIK))
sina("lider claude/opus, kod claude/sonnet",
     (k["lider"]["motor"], k["lider"]["model"]) == ("claude", "opus")
     and k["backend"]["motor"] == "claude" and k["arayuz"]["model"] == "sonnet")
sina("arastirma ve video gemini, test ve plan codex 6.1, tarayici codex 5.6",
     k["arastirma"]["motor"] == k["video"]["motor"] == "gemini"
     and (k["kalite"]["motor"], k["kalite"]["model"]) == ("codex", "gpt-6.1-sol")
     and (k["bilgisayar"]["motor"], k["bilgisayar"]["model"]) == ("codex", "gpt-5.6-sol"))
sina("katalogda haiku ve 3.1 pro YOK",
     not any(v["model"] in ("haiku", "gemini-3.1-pro-high") for v in k.values()))
R.meslek_yaz(db, pid, "metin", "claude", "sonnet")
sina("ayar koddaki varsayilani EZER (ve isaretlenir)",
     R.meslek_katalogu(db, pid)["metin"] == {"motor": "claude", "model": "sonnet", "ayar": True})
R.meslek_yaz(db, pid, "metin", "", "")
sina("bos motor varsayilana DONER", R.meslek_katalogu(db, pid)["metin"]["motor"] == "gemini")
sina("kapi modeli kataloga konmaz",
     reddedilir(lambda: R.meslek_yaz(db, pid, "lider", "claude", "fable"), "KAPI"))
sina("bilinmeyen motor reddedilir",
     reddedilir(lambda: R.meslek_yaz(db, pid, "lider", "yok-motor", "x"), "motor"))
m, mo, not_ = R.meslek_motoru("arastirma", db, pid, {"claude": True, "codex": True})
sina("katalogun motoru kurulu degilse YEDEK + sebep",
     m == "claude" and mo == "sonnet" and "kurulu degil" in not_, f"{m} {mo} {not_}")

# --------------------------------------------------------------------------
print("\n2. KATALOGDAN ISE ALMA")
ofis.kadro.katalogdan_al("demir", "lider", kanat_id=web, lider_mi=True, klasor=str(kok))
ofis.kadro.katalogdan_al("bilge", "arastirma", kanat_id=web, klasor=str(kok))
ofis.kadro.katalogdan_al("ayna", "arayuz", kanat_id=web, klasor=str(kok))
ofis.kadro.katalogdan_al("ozel", "arastirma", kanat_id=web, klasor=str(kok), motor="claude")
d, b, o = (ofis.kadro.ajan(x) for x in ("demir", "bilge", "ozel"))
sina("lider katalogdan claude/opus", (d["motor"], d["model"]) == ("claude", "opus"))
sina("arastirmaci katalogdan gemini 3.8 flash high",
     (b["motor"], b["model"]) == ("gemini", "gemini-3.8-flash-high"), f"{b['motor']} {b['model']}")
sina("acikca verilen motor KAZANIR, model o motorun kademesinden",
     (o["motor"], o["model"]) == ("claude", "sonnet"), f"{o['motor']} {o['model']}")

# --------------------------------------------------------------------------
print("\n3. TASI / CIKAR / LIDER")
ofis.kadro.katalogdan_al("kaya", "lider", kanat_id=magaza, lider_mi=True, klasor=str(kok))
ofis.kadro.tasi("ayna", magaza)
sina("tasindi: yeni takimda", ofis.kadro.ajan("ayna")["kanat_id"] == magaza)
sina("lider TASINMAZ", reddedilir(lambda: ofis.kadro.tasi("demir", magaza), "LIDERI"))
sina("olmayan takima tasinmaz", reddedilir(lambda: ofis.kadro.tasi("bilge", "yok"), "takim yok"))
g = ofis.tahta.gorev_ac("acik is", neden="s", ana_hedef="s", kabul_olcutu="y",
                        sahip="bilge", kanat_id=web)
sina("acik isi olan TASINMAZ", reddedilir(lambda: ofis.kadro.tasi("bilge", magaza), "acik"))
sina("acik isi olan CIKARILMAZ", reddedilir(lambda: ofis.kadro.cikar("bilge"), "acik"))
ofis.tahta.iptal_et(g["no"], sebep="sinama", iptal_eden="insan")
ofis.kadro.cikar("bilge")
sina("cikarilan ARSIVDE, kadroda yok",
     ofis.kadro.ajan("bilge")["arsiv"] == 1
     and "bilge" not in [a["ad"] for a in ofis.kadro.liste()]
     and "bilge" in [a["ad"] for a in ofis.kadro.liste(arsivli=True)])
sina("ad geri DONMEZ (arsivdeki adla ise alinmaz)",
     reddedilir(lambda: ofis.kadro.katalogdan_al("bilge", "metin", kanat_id=web,
                                                  klasor=str(kok)), "kullanilmis"))
sina("baska ajani olan takimin lideri cikarilmaz",
     reddedilir(lambda: ofis.kadro.cikar("demir"), "LIDERI"))
ofis.kadro.lider_yap("ozel")
sina("lider degisti: tek lider kurali korundu",
     ofis.kadro.lider(web)["ad"] == "ozel" and not ofis.kadro.ajan("demir")["lider_mi"])
sina("eski lider artik tasinabilir", ofis.kadro.tasi("demir", magaza)["kanat_id"] == magaza)
ofis.kadro.karakter_yaz("ayna", "2:1:3")
sina("karakter yazildi", ofis.kadro.ajan("ayna")["karakter"] == "2:1:3")
sina("bozuk karakter reddedilir", reddedilir(lambda: ofis.kadro.karakter_yaz("ayna", "x"), "bicim"))

# --------------------------------------------------------------------------
print("\n4. SABLON: KATALOG MOTORU + PATRONUN SABLONU")
sina("sablonlar lider haric en fazla 5 uye",
     all(len(s.uyeler) <= 5 for s in S.liste()))
sina("istenen sablonlar var (magaza, mobil, saas, bot, icerik, studyo, tarayici)",
     {"ticaret", "mobil", "urun", "bot", "icerik", "studyo", "bilgisayar"} <= set(S.SABLONLAR))
bos = ofis.kanat_ac("MOBIL", "MB")
o1 = Ekip(ofis).sablondan("mobil", kanat_id=bos)
motor_rol = {u["rol"]: (u["motor"], u["model"]) for u in o1["uyeler"]}
sina("sablon onerisi motoru KATALOGDAN aldi",
     motor_rol.get("lider") == ("claude", "opus") and motor_rol.get("kalite") == ("codex", "gpt-6.1-sol")
     and motor_rol.get("arayuz") == ("claude", "sonnet"), str(motor_rol))
S.ozel_kaydet(db, pid, "web-ekibi", "Web ekibi", "deneme",
              [("lider", "x"), ("arayuz", "ekran"), ("seo", "")])
oz = S.bul("web-ekibi", db, pid)
sina("patronun sablonu kaydedildi (lider sayilmaz, bos neden doldu)",
     oz and [r for r, _ in oz.uyeler] == ["arayuz", "seo"] and all(n for _, n in oz.uyeler))
sina("hazir sablonun adi ezilemez",
     reddedilir(lambda: S.ozel_kaydet(db, pid, "mobil", "x", "", [("seo", "y")]), "hazir"))
bos2 = ofis.kanat_ac("BOS", "BO")
o2 = Ekip(ofis).sablondan("web-ekibi", kanat_id=bos2)
sina("patronun sablonundan oneri uretildi (lidersiz takima lider eklendi)",
     [u["rol"] for u in o2["uyeler"]] == ["lider", "arayuz", "seo"], str(o2["uyeler"])[:200])

# --------------------------------------------------------------------------
print("\n5. PANEL UCLARI")
ist = TestClient(_panel.olustur(db_yolu))
org = ist.get("/api/organizasyon").json()
adlar = {k_["ad"]: [a["ad"] for a in k_["ajanlar"]] for k_ in org["kanatlar"]}
sina("organizasyon: takimlar ve ajanlari",
     set(adlar) >= {"WEB", "MAGAZA"} and "ozel" in adlar["WEB"] and "ayna" in adlar["MAGAZA"],
     str(adlar))
sina("organizasyon: arsiv ayri listede", [a["ad"] for a in org["arsiv"]] == ["bilge"])
w = next(k_ for k_ in org["kanatlar"] if k_["ad"] == "WEB")
sina("takimin lideri ve ajanin motor/model/Turkce meslek adi",
     w["lider"] == "ozel" and any(a["meslek_baslik"] == "Araştırma" and a["motor"] == "claude"
                                  for a in w["ajanlar"]))
sec = ist.get("/api/kadro/secenek").json()
sina("secenekler: katalog + motor durumu + model secenekleri",
     sec["katalog"]["video"]["motor"] == "gemini"
     and set(sec["motor_durum"]) >= {"claude", "codex", "gemini"}
     and "gpt-5.6-sol" in sec["model_secenek"]["codex"]
     and "gemini-3.8-flash-high" in sec["model_secenek"]["gemini"])
sina("gemini durumunda video notu DURUSTCE yazili",
     any("video" in n for n in sec["motor_durum"]["gemini"]["notlar"]))
r = ist.post("/api/ajan", json={"ad": "sahne", "meslek": "video", "kanat": magaza,
                                "karakter": "1:0:2"})
sina("panelden ise alma: motor bos -> katalog (gemini) + karakter",
     r.status_code == 200 and r.json()["motor"] == "gemini" and r.json()["karakter"] == "1:0:2",
     r.text[:200])
r = ist.post("/api/ajan/kaya/tasi", json={"kanat": web})
sina("lider tasima 400 + sebep", r.status_code == 400 and "LIDER" in r.text)
r = ist.post("/api/ajan/sahne/tasi", json={"kanat": web})
sina("tasi ucu calisiyor", r.status_code == 200 and r.json()["kanat_id"] == web)
sina("lider ucu calisiyor", ist.post("/api/ajan/sahne/lider").status_code == 200
     and ofis.kadro.lider(web)["ad"] == "sahne")
r = ist.post("/api/kanat/" + bos2 + "/duzenle", json={"ad": "Web-2", "renk": "#112233"})
sina("takim duzenle (ad buyuk harf)", r.status_code == 200 and r.json()["ad"] == "WEB-2")
r = ist.post("/api/kanat/" + magaza + "/sil")
sina("icinde ajan olan takim SILINMEZ", r.status_code == 400 and "ajan" in r.text)
kapali = ofis.tahta.gorev_ac("eski is", neden="s", ana_hedef="s", kabul_olcutu="y",
                             kanat_id=bos2)
ofis.tahta.iptal_et(kapali["no"], sebep="sinama", iptal_eden="insan")
r = ist.post("/api/kanat/" + bos2 + "/sil")
sina("bos takim silindi; kapanmis isi KAYITTA kaldi (bagi cozuldu)",
     r.status_code == 200 and ofis.tahta.gorev(kapali["no"])["kanat_id"] is None, r.text[:200])
sina("bekleyen sablon onerisi takimla birlikte kapandi",
     Ekip(ofis).oneri(o2["no"])["durum"] == "reddedildi")
r = ist.post("/api/katalog", json={"rol": "seo", "motor": "codex", "model": "gpt-6.1-sol"})
sina("katalog ucu yazar", r.status_code == 200 and R.meslek_katalogu(db, pid)["seo"]["motor"] == "codex")
kat = {x["rol"]: x for x in ist.get("/api/katalog").json()}
sina("katalog listesi varsayilani da gosterir",
     kat["seo"]["ayar"] and kat["seo"]["varsayilan"]["motor"] == "gemini")
r = ist.post("/api/sablon/kaydet", json={"kanat": web, "ad": "web-takimi", "baslik": "Web"})
sina("takimdan sablon kaydedildi (lider haric)",
     r.status_code == 200 and "arastirma" in r.json()["roller"]
     and "video" not in r.json()["roller"], r.text[:200])
sab = {x["ad"]: x for x in ist.get("/api/sablonlar").json()}
sina("sablon listesi patronunkileri isaretli gosterir",
     sab["web-takimi"]["ozel"] and not sab["mobil"]["ozel"])

print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
