# -*- coding: utf-8 -*-
"""Zorluk -> model eslemesi ve KAPI MODELI yukseltmesi.

Iki ayri soru sinaniyor:

1. **Zorluk gercekten modeli belirliyor mu** -- ve belirledigi model
   MOTORA ULASIYOR mu. Rol KIMIN yapacagini soyler, zorluk NE KADAR
   GUCLE. Ikisi ayri sorudur.

2. **Kapi modeli (fable/astra) dogru yerde ve dogru KORKULUKLA mi
   devreye giriyor.** En kritik sinama 4. bolumde: tavan uygulayamayan
   bir motorda yukseltme YAPILMAMALI. Sebep modelin gucu degil bizim
   korkulugumuz -- kullanicinin olcumu: *"tek promptta 5 saatlik limiti
   bitiriyordu."* Tavansiz otomatik pahali model, o acinin kaynagi olur.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, Lider
from ofis import roller as R
from ofis.lider import YUKSELTME_ESIGI
from ofis.motor.sahte import SahteMotor
from ofis.tahta import TahtaHatasi

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


kok = Path(tempfile.mkdtemp(prefix="ofis-zorluk-"))
print(f"klasor: {kok}")
ofis = Ofis.proje_ac(Veritabani(kok / "o.sqlite3"), "Zorluk",
                     amac="zorluk sinamasi", basari_olcutu="testler gecer")
(kok / "w").mkdir()
ofis.kadro.ise_al("demir", "lider", lider_mi=True, motor="sahte",
                  klasor=str(kok / "w"))
ofis.kadro.ise_al("cinar", "backend", motor="sahte", klasor=str(kok / "w"))

# ------------------------------------------------------------- 1. KAPI
print("\n1. zorluk KAPISI")

g = ofis.tahta.gorev_ac("Kolay is", neden="s", ana_hedef="s",
                        kabul_olcutu="y", zorluk="kolay")
sina("gecerli zorluk kabul edildi", g["zorluk"] == "kolay")

gb = ofis.tahta.gorev_ac("Zorluksuz", neden="s", ana_hedef="s", kabul_olcutu="y")
# Bos birakilabilmeli: o zaman ajanin KENDI modeli kullanilir.
sina("zorluk BOS birakilabiliyor", gb["zorluk"] == "")

try:
    ofis.tahta.gorev_ac("Kotu", neden="s", ana_hedef="s", kabul_olcutu="y",
                        # `cok-zor` artik GECERLI (23.09: dorduncu seviye
                        # `cok_zor`, yazim normallesiyor); bilinmeyen ornek
                        # gercekten bilinmeyen olmali.
                        zorluk="imkansiz")
    sina("bilinmeyen zorluk reddedildi", False, "-- kabul edildi!")
except TahtaHatasi as exc:
    sina("bilinmeyen zorluk reddedildi", True)
    sina("ret gecerli secenekleri sayiyor", "kolay" in str(exc))

# PAHALI SECIM GEREKCE ISTER -- fan-out kapisinin ayni mantigi.
# Gerekcesiz 'zor', her isi guclu modele kaydirmanin en kolay yolu.
try:
    ofis.tahta.gorev_ac("Zor ama sebepsiz", neden="s", ana_hedef="s",
                        kabul_olcutu="y", zorluk="zor")
    sina("gerekcesiz 'zor' REDDEDILDI", False, "-- kabul edildi!")
except TahtaHatasi:
    sina("gerekcesiz 'zor' REDDEDILDI", True)

gz = ofis.tahta.gorev_ac("Zor ve gerekceli", neden="s", ana_hedef="s",
                         kabul_olcutu="y", zorluk="zor",
                         zorluk_gerekce="belirsiz tasarim, yargi gerekiyor")
sina("gerekceli 'zor' kabul edildi", gz["zorluk"] == "zor")
sina("gerekce saklandi", "belirsiz" in gz["zorluk_gerekce"])
# 'kolay' ve 'orta' gerekce ISTEMEZ: ucuza inmek para riski degildir.
go = ofis.tahta.gorev_ac("Orta", neden="s", ana_hedef="s", kabul_olcutu="y",
                         zorluk="orta")
sina("'orta' gerekce istemiyor", go["zorluk"] == "orta")

# --------------------------------------------------- 2. KADEME ESLEMESI
print("\n2. zorluk -> model eslemesi")
sina("claude kolay -> haiku", R.model_sec("claude", "hizli") == "haiku")
sina("claude zor -> opus", R.model_sec("claude", "guclu") == "opus")
sina("codex kolay -> luna", R.model_sec("codex", "hizli") == "gpt-6-luna")
sina("codex zor -> sol", R.model_sec("codex", "guclu") == "gpt-6.1-sol")

# ------------------------------------------- 3. MODEL MOTORA ULASIYOR MU
print("\n3. secilen model MOTORA ulasiyor mu")
# "Sessizce yok sayilan ayar, ayar degildir." Zorluk yazilip modele hic
# donusmeseydi bu bolum yakalardi.


class _Kaydeden(SahteMotor):
    son: dict = {}
    # claude'un YERINE geciyor: claude tavan uygular. Sahte motorun
    # varsayilani (False) burada gercegi yanlis taklit ederdi -- lider
    # turu artik tavani yalniz UYGULAYABILEN motora veriyor.
    butce_destegi = True

    def tur_kos(self, metin, **ayar):
        _Kaydeden.son = dict(ayar)
        yield from super().tur_kos(metin, **ayar)


CEVAP = "Bitti.\nKANIT terminal: pytest -> 2 passed"
_f = lambda ad, **kw: _Kaydeden(cevap=CEVAP)          # noqa: E731

# Ajan claude'a alinsin ki kademe eslemesi gercek model adlari uretsin.
ofis.kadro.ise_al("yaprak", "backend", motor="claude", model="sonnet",
                  klasor=str(kok / "w"))

k1 = ofis.tahta.gorev_ac("Kolay kod", neden="s", ana_hedef="s",
                         kabul_olcutu="y", zorluk="kolay")
Koltuk(ofis, motor_fabrikasi=_f).kos(k1["no"], "yaprak")
sina("KOLAY is ucuz modele dustu", _Kaydeden.son.get("model") == "haiku",
     str(_Kaydeden.son.get("model")))

k2 = ofis.tahta.gorev_ac("Zor kod", neden="s", ana_hedef="s",
                         kabul_olcutu="y", zorluk="zor",
                         zorluk_gerekce="ince hata avi")
Koltuk(ofis, motor_fabrikasi=_f).kos(k2["no"], "yaprak")
sina("ZOR is guclu modele cikti", _Kaydeden.son.get("model") == "opus",
     str(_Kaydeden.son.get("model")))

k3 = ofis.tahta.gorev_ac("Zorluksuz kod", neden="s", ana_hedef="s",
                         kabul_olcutu="y")
Koltuk(ofis, motor_fabrikasi=_f).kos(k3["no"], "yaprak")
# Zorluk yoksa AJANIN KENDI modeli kalir -- kullanicinin sectigini
# sessizce iptal etmek, zincirin "kendi motorundan baslar" kuraliyla
# ayni sinifta bir hata olurdu.
sina("zorluk yoksa AJANIN modeli kaliyor",
     _Kaydeden.son.get("model") == "sonnet", str(_Kaydeden.son.get("model")))

# Degisim SESSIZ olmamali.
with ofis.db.baglanti() as c:
    olaylar = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur = 'zorluk_modeli'")]
sina("model degisimi olaya yazildi", len(olaylar) == 2, str(len(olaylar)))
sina("olay hangi modele cikildigini soyluyor",
     any("opus" in o["govde"] for o in olaylar))

# ------------------------------------------------- 4. KAPI MODELI
print("\n4. kapi modeli -- fable ACIK, astra KAPALI")
sina("claude -> fable (tavan uygulanabilir)",
     (R.kapi_modeli("claude") or {}).get("model") == "fable")
# EN KRITIK SINAMA: codex tur basina tavan UYGULAYAMIYOR
# (butce_destegi=False), bu yuzden astra otomatik bir yola BAGLANAMAZ.
sina("codex -> YOK (astra otomatiklestirilemez)",
     R.kapi_modeli("codex") is None)
sina("sahte -> YOK", R.kapi_modeli("sahte") is None)
# Karar tahmine degil ADAPTORE dayanmali: yarin codex tavan destegi
# eklerse bu islev kendiliginden dogru cevabi vermeli.
sina("karar adaptorun bayragindan okunuyor",
     R.KAPI_MODELLERI["astra"]["motor"] == "codex")

print("\n5. yukseltme -- ikinci retten sonra")
sina("esik 2", YUKSELTME_ESIGI == 2)
sina("fable HICBIR kademede yok",
     not any("fable" in (m or "")
             for d in R.KADEME_MODEL.values() for m in d.values()))

# Yukseltme gercekten oluyor mu: ret olaylarini kurup incelemeyi kostur.
ofis.kadro.ise_al("ceren", "lider", lider_mi=True, motor="claude",
                  model="sonnet", klasor=str(kok / "w"),
                  kanat_id=ofis.kanat_ac("IKINCI", "IK"))
gy = ofis.tahta.gorev_ac("Takilan is", neden="s", ana_hedef="s",
                         kabul_olcutu="y", sahip="cinar")
ofis.tahta.sahiplen(gy["no"], "cinar", gy["revizyon"])
ofis.tahta.kanit_ekle(gy["no"], "terminal", "pytest", "2 passed", "cinar")
ofis.tahta.incelemeye_ver(gy["no"], ofis.tahta.gorev(gy["no"])["revizyon"])
for _ in range(YUKSELTME_ESIGI):
    guncel = ofis.tahta.gorev(gy["no"])
    if guncel["durum"] != "inceleme":
        ofis.tahta.incelemeye_ver(gy["no"], guncel["revizyon"])
        guncel = ofis.tahta.gorev(gy["no"])
    ofis.tahta.geri_gonder(gy["no"], guncel["revizyon"],
                           gerekce="eksik", gonderen="ceren")
sina("ret sayaci calisiyor",
     ofis.tahta.ret_sayisi(gy["no"]) == YUKSELTME_ESIGI,
     str(ofis.tahta.ret_sayisi(gy["no"])))

guncel = ofis.tahta.gorev(gy["no"])
if guncel["durum"] != "inceleme":
    ofis.tahta.incelemeye_ver(gy["no"], guncel["revizyon"])

_Kaydeden.son = {}
try:
    Lider(ofis, motor_fabrikasi=_f).incele(gy["no"], lider_ad="ceren")
except Exception:
    pass                                   # hukum onemli degil, MODEL onemli
sina("inceleme KAPI MODELINE yukseldi",
     _Kaydeden.son.get("model") == "fable", str(_Kaydeden.son.get("model")))
# TAVANSIZ kosmaz: kullanicinin olcumu "tek promptta 5 saatlik limit".
sina("yukseltilen tur TAVANLI kostu",
     bool(_Kaydeden.son.get("butce_usd")), str(_Kaydeden.son.get("butce_usd")))

with ofis.db.baglanti() as c:
    y = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur = 'yukseltme'")]
sina("yukseltme GORUNUR bir olay", len(y) == 1)
sina("olay tavani da soyluyor", bool(y) and "$" in y[0]["govde"])

print("\n6. tavan uygulanamayan motorda yukseltme YAPILMIYOR")
# codex liderde astra'ya cikmak, tavansiz pahali model demekti.
ofis.kadro.ise_al("kaan", "lider", lider_mi=True, motor="codex",
                  model="gpt-5.6-sol", klasor=str(kok / "w"),
                  kanat_id=ofis.kanat_ac("UCUNCU", "UC"))
g6 = ofis.tahta.gorev_ac("Codex takilan", neden="s", ana_hedef="s",
                         kabul_olcutu="y", sahip="cinar")
ofis.tahta.sahiplen(g6["no"], "cinar", g6["revizyon"])
ofis.tahta.kanit_ekle(g6["no"], "terminal", "pytest", "ok", "cinar")
ofis.tahta.incelemeye_ver(g6["no"], ofis.tahta.gorev(g6["no"])["revizyon"])
for _ in range(YUKSELTME_ESIGI):
    gg = ofis.tahta.gorev(g6["no"])
    if gg["durum"] != "inceleme":
        ofis.tahta.incelemeye_ver(g6["no"], gg["revizyon"])
        gg = ofis.tahta.gorev(g6["no"])
    ofis.tahta.geri_gonder(g6["no"], gg["revizyon"], gerekce="eksik",
                           gonderen="kaan")
gg = ofis.tahta.gorev(g6["no"])
if gg["durum"] != "inceleme":
    ofis.tahta.incelemeye_ver(g6["no"], gg["revizyon"])

_Kaydeden.son = {}
try:
    Lider(ofis, motor_fabrikasi=_f).incele(g6["no"], lider_ad="kaan")
except Exception:
    pass
sina("codex liderde ASTRA'YA CIKILMADI",
     _Kaydeden.son.get("model") != "astra", str(_Kaydeden.son.get("model")))
# Atlanan yukseltme de GORUNUR olmali: gorunmeyen bosluk, "neden hala
# ayni hukum geliyor" sorusunu cevapsiz birakir.
with ofis.db.baglanti() as c:
    u = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='uyari' AND govde LIKE '%kapi modeli yok%'")]
sina("atlanan yukseltme UYARI olarak gorunuyor", len(u) >= 1)

# --------------------------------------------- 7. FABLE KORUMASI
print("\n7. fable korumasi -- saglayicinin KENDI yuzdesiyle")
# 27.09.2026 KARARI: abonelikte dolar yok. Fable'in haftalik payi CLI'in
# bildirdigi pencereden okunur (`7g_kapi`; eski kayitlarda ham ad
# `seven_day_overage_included`). Esikte yukseltme kapanir, IS DURMAZ.
import json as _json                                        # noqa: E402
import time as _time                                        # noqa: E402

from ofis import butce                                      # noqa: E402

bos = butce.kapi_acik_mi(ofis.db, ofis.proje_id)
sina("olcum yokken kapi ACIK (bilinmeyene gore kapatilmaz)", bos["acik"])
sina("olcum yokken kullanim None (sifir uydurulmaz)", bos["kullanim"] is None)
sina("tur siniri iceride bir kacak freni", bos["tur_siniri"] > 0)

_GELECEK = int(_time.time()) + 3 * 86400


def _tur_yaz(pencereler, model="claude-haiku-4-5-20251001"):
    """Gercek `tur_ozeti` olayinin aynisi -- koruma ONU okuyor."""
    ofis.db.olay_yaz(ofis.proje_id, "tur_ozeti", _json.dumps({
        "model": model, "jeton": 1000, "basarili": True, "motor": "claude",
        "limit_pencere": {"kaynak": "s", "pencereler": pencereler}}),
        ajan_ad="ceren")


# Haiku turu Fable penceresi TASIMAZ: koruma onu gormemeli.
_tur_yaz({"7g": {"kullanim": 0.95, "yenilenme": _GELECEK}})
sina("genel haftalik %95 FABLE payi sayilmiyor",
     butce.kapi_acik_mi(ofis.db, ofis.proje_id)["kullanim"] is None)

# Eski kayit, ham adla -- yine taninmali.
_tur_yaz({"seven_day_overage_included": {"kullanim": 0.40, "yenilenme": _GELECEK}},
         model="claude-fable-5-1")
h = butce.kapi_acik_mi(ofis.db, ofis.proje_id)
sina("ham adli eski kayit TANINIYOR", h["kullanim"] == 0.40, str(h))
sina("esik altinda kapi acik", h["acik"])

# Daha yeni bir HAIKU turu Fable olcumunu SILMEMELI (yalniz fable turu tasir).
_tur_yaz({"5s": {"kullanim": 0.1, "yenilenme": _GELECEK}})
sina("sonraki haiku turu Fable olcumunu silmedi",
     butce.kapi_acik_mi(ofis.db, ofis.proje_id)["kullanim"] == 0.40)
from ofis import kullanim as _kul                            # noqa: E402
_p = [p for p in _kul.son_pencereler(ofis.db, ofis.proje_id) if p["motor"] == "claude"]
sina("kullanim ekrani da Fable penceresini koruyor",
     bool(_p) and "7g_kapi" in _p[0]["pencereler"], str(_p[:1]))

_tur_yaz({"7g_kapi": {"kullanim": 0.85, "yenilenme": _GELECEK}},
         model="claude-fable-5-1")
dolu = butce.kapi_acik_mi(ofis.db, ofis.proje_id)
sina("esikte (%80) kapi KAPANIYOR", not dolu["acik"])
sina("kapanma sebebi yuzdeyi soyluyor", "%85" in dolu["sebep"], dolu["sebep"])
sina("sebep DOLAR soylemiyor", "$" not in dolu["sebep"])

# Esik AYAR.
ofis.db.ayar_yaz(ofis.proje_id, butce.ANAHTAR_ESIK, "0.9")
sina("esik ayari okunuyor (0.9 -> %85 acik)",
     butce.kapi_acik_mi(ofis.db, ofis.proje_id)["acik"])
ofis.db.ayar_yaz(ofis.proje_id, butce.ANAHTAR_ESIK, "bozuk")
sina("bozuk esik varsayilana dusuyor", butce.kapi_esigi(ofis.db, ofis.proje_id)
     == butce.KAPI_ESIGI)

# Yenilenmis pencerenin yuzdesiyle KAPATILMAZ.
_tur_yaz({"7g_kapi": {"kullanim": 0.99, "yenilenme": int(_time.time()) - 60}},
         model="claude-fable-5-1")
sina("yenilenmis pencere kapatmiyor",
     butce.kapi_acik_mi(ofis.db, ofis.proje_id)["acik"])
_tur_yaz({"7g_kapi": {"kullanim": 0.85, "yenilenme": _GELECEK}},
         model="claude-fable-5-1")

# EN ONEMLI: pay doluyken IS DURMAZ, yalnizca pahali basamak kapanir.
g7 = ofis.tahta.gorev_ac("Tavan doluyken", neden="s", ana_hedef="s",
                         kabul_olcutu="y", sahip="cinar")
ofis.tahta.sahiplen(g7["no"], "cinar", g7["revizyon"])
ofis.tahta.kanit_ekle(g7["no"], "terminal", "pytest", "ok", "cinar")
ofis.tahta.incelemeye_ver(g7["no"], ofis.tahta.gorev(g7["no"])["revizyon"])
for _ in range(YUKSELTME_ESIGI):
    gg = ofis.tahta.gorev(g7["no"])
    if gg["durum"] != "inceleme":
        ofis.tahta.incelemeye_ver(g7["no"], gg["revizyon"])
        gg = ofis.tahta.gorev(g7["no"])
    ofis.tahta.geri_gonder(g7["no"], gg["revizyon"], gerekce="eksik",
                           gonderen="ceren")
gg = ofis.tahta.gorev(g7["no"])
if gg["durum"] != "inceleme":
    ofis.tahta.incelemeye_ver(g7["no"], gg["revizyon"])

_Kaydeden.son = {}
try:
    Lider(ofis, motor_fabrikasi=_f).incele(g7["no"], lider_ad="ceren")
except Exception:
    pass
sina("pay doluyken FABLE'A CIKILMADI",
     _Kaydeden.son.get("model") != "fable", str(_Kaydeden.son.get("model")))
sina("inceleme yine de KOSTU (is durmadi)",
     _Kaydeden.son.get("model") == "sonnet", str(_Kaydeden.son.get("model")))
with ofis.db.baglanti() as c:
    at = [dict(r) for r in c.execute(
        "SELECT * FROM olay WHERE tur='uyari' "
        "AND govde LIKE '%yukseltme ATLANDI%'")]
sina("atlanan yukseltme GORUNUR", len(at) >= 1)

bulgular = ofis.saglik.denetle()["bulgular"]
sina("saglik Fable payini raporluyor",
     any("Fable" in b["baslik"] for b in bulgular),
     str([b["baslik"] for b in bulgular]))

# ------------------------------------------------- 8. PLAN bir AYAR
print("\n8. plan KOD DEGIL AYAR")
# Kullanici: "hesaplar degisebilir, yarin gpt pro veya claude 20x
# aliriz." Plani koda gomseydik her plan degisikligi bir kod
# degisikligi olurdu -- zincirde ayni karari bir kez verdik.
from ofis import plan as P                                   # noqa: E402

p0 = ofis.plan
sina("varsayilan plan max5", p0["claude"] == "max5")
sina("max5 planinda fable DAHIL", p0["kapi_dahil"] is True)
sina("tavansiz kapi VARSAYILAN OLARAK yasak",
     p0["tavansiz_kapi_izinli"] is False)

P.yaz(ofis.db, ofis.proje_id, claude="max20", gpt="pro200")
p1 = ofis.plan
sina("plan yukseltildi", p1["claude"] == "max20")
sina("max20 planinda fable DAHIL", p1["kapi_dahil"] is True)
P.yaz(ofis.db, ofis.proje_id, claude="pro")
sina("Pro planinda fable YOK -> kapi kapali (kredi harcamaz)",
     not butce.kapi_acik_mi(ofis.db, ofis.proje_id)["acik"])
P.yaz(ofis.db, ofis.proje_id, claude="max20")

# EN ONEMLI AYRIM: plan yukseltmek ASTRA'yi ACMAZ.
# Sebep payin darligi degil, kacan turu DURDURACAK bir seyin olmamasi.
sina("PLAN YUKSELTMEK astra'yi ACMIYOR",
     R.kapi_modeli("codex") is None)
sina("astra yalniz ACIK TERCIHLE aciliyor",
     (R.kapi_modeli("codex", tavansiz_izinli=True) or {}).get("model") == "astra")
sina("acik tercihte bile TAVAN YOK diye isaretli",
     R.kapi_modeli("codex", tavansiz_izinli=True)["tavan_zorunlu"] is False)

try:
    P.yaz(ofis.db, ofis.proje_id, claude="sihirli-plan")
    sina("bilinmeyen plan reddedildi", False, "-- kabul edildi!")
except P.PlanHatasi as exc:
    sina("bilinmeyen plan reddedildi", True)
    sina("ret gecerli planlari sayiyor", "max20" in str(exc))

ozet = P.ozet(ofis.plan)
sina("ozet fable durumunu gosteriyor, dolar YOK", "plana dahil" in ozet and not any("$" in x for x in ozet.splitlines() if "fable" in x.lower() or "kapi" in x.lower()), ozet)
sina("ozet astra kuralini ACIKCA soyluyor",
     "Plan yukseltmek bunu ACMAZ" in ozet)

# Plani geri al ki sonraki calistirmalar etkilenmesin.
P.yaz(ofis.db, ofis.proje_id, claude="max5", gpt="plus")

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
