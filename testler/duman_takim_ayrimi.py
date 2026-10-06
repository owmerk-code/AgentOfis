# -*- coding: utf-8 -*-
"""TAKIM AYRIMI -- sizinti 0 (06.10.2026, Asama 4 / E40). Jeton yakmaz.

Patron karari: "her takim ayri" + ORTAK hafiza. Bir takimin bilgisi,
kurali, belgesi, karari ve isleri BASKA takimin ajanina, liderine,
incelemesine, on kapisina, planina, danismasina, uyanis ozetine ve ajan
araclarina (MCP durum / belge_ara / bilgi_yaz) GIRMEZ; ortak her yere girer;
ayni konuda takiminki ortaktakini ezer (yalniz o takim icin).

Sahne: MAGAZA ve YAZILIM takimlari; her birinin kendine ozgu (benzersiz
isaretli) bilgisi, kurali, belgesi, karari ve calisan isi; bir ortak bilgi.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, belge as B  # noqa: E402
from ofis.danisma import Danisma  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-takim-ayrimi-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Ayrim", amac="a", basari_olcutu="b", kok_klasor=str(d))
KM = ofis.kanat_ac("MAGAZA", "MG")
KY = ofis.kanat_ac("YAZILIM", "YZ")
ofis.kadro.ise_al("lale", "lider", kanat_id=KM, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("mert", "lider", kanat_id=KY, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "icerik", kanat_id=KM, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("can", "backend", kanat_id=KY, motor="sahte", klasor=str(d))

# --- ortak
ofis.bellek.bilgi_ekle("rapor bicimi", "Excel ORTAK_ISARET", yazan="insan")
ofis.bellek.bilgi_ekle("teslim suresi", "3 gun ORTAK_TESLIM", yazan="insan")
# --- magaza
MAG = ofis.bellek.kapsam(KM)
MAG.bilgi_ekle("iade suresi", "30 gun MAG_GIZLI_BILGI", yazan="ece")
MAG.bilgi_ekle("teslim suresi", "1 gun MAG_TESLIM", yazan="insan")
ofis.bellek.kural_ekle("Musteriye siz diye hitap et MAG_GIZLI_KURAL", "marka", kanat_id=KM)
B.yukle(ofis, "iade.txt", "Iade politikasi: iade suresi 30 gun MAG_GIZLI_BELGE.".encode(), kanat_id=KM)
gm = ofis.tahta.gorev_ac("MAG_GIZLI_IS sepet kampanyasi", neden="n", ana_hedef="h",
                         kabul_olcutu="k", kanat_id=KM)
ofis.tahta.sahiplen(gm["no"], "ece", gm["revizyon"])
ofis.bellek.karar_yaz("MAG_GIZLI_KARAR kampanya yuzde 20", "patron istedi", "lale", gorev_id=gm["id"])
# --- yazilim
YAZ = ofis.bellek.kapsam(KY)
YAZ.bilgi_ekle("servis portu", "8742 YAZ_GIZLI_BILGI", yazan="can")
ofis.bellek.kural_ekle("Testsiz commit yok YAZ_GIZLI_KURAL", "kalite", kanat_id=KY)
B.yukle(ofis, "api.txt", "API belgesi: iade uc noktasi YAZ_GIZLI_BELGE.".encode(), kanat_id=KY)
gy = ofis.tahta.gorev_ac("YAZ_GIZLI_IS iade suresi ekrani", neden="iade suresini goster",
                         ana_hedef="iade", kabul_olcutu="iade suresi gorunur", kanat_id=KY)
ofis.tahta.sahiplen(gy["no"], "can", gy["revizyon"])
ofis.bellek.karar_yaz("YAZ_GIZLI_KARAR REST kullan", "basit", "mert", gorev_id=gy["id"])

MAG_IZ = ("MAG_GIZLI_BILGI", "MAG_GIZLI_KURAL", "MAG_GIZLI_BELGE", "MAG_GIZLI_KARAR", "MAG_GIZLI_IS",
          "MAG_TESLIM")
YAZ_IZ = ("YAZ_GIZLI_BILGI", "YAZ_GIZLI_KURAL", "YAZ_GIZLI_BELGE", "YAZ_GIZLI_KARAR", "YAZ_GIZLI_IS")


def sizinti(metin: str, izler) -> list:
    return [i for i in izler if i in (metin or "")]


def denetle(ad: str, metin: str, *, kendi, yabanci, ortak=True):
    s = sizinti(metin, yabanci)
    sina(f"{ad}: baska takimdan HICBIR iz yok", not s, str(s))
    if ortak:
        sina(f"{ad}: ortak bilgi var", "ORTAK_ISARET" in (metin or ""))
    if kendi:
        eksik = [i for i in kendi if i not in (metin or "")]
        sina(f"{ad}: kendi takiminin izleri var", not eksik, str(eksik))


print("== takim ayrimi ==\n")
print("1. iscinin brifingi")
by = ofis.brifing.uret(gy["no"], "can", diske_yaz=False)["metin"]
denetle("YAZILIM iscisi brifingi", by, kendi=("YAZ_GIZLI_BILGI", "YAZ_GIZLI_KURAL", "YAZ_GIZLI_KARAR"),
        yabanci=MAG_IZ)
sina("YAZILIM brifingi: ayni konuda ORTAK deger (3 gun)", "ORTAK_TESLIM" in by)
sina("YAZILIM brifingi: kendi belgesi (iade kelimesi iki belgede de var)", "YAZ_GIZLI_BELGE" in by, by[-400:])
bm = ofis.brifing.uret(gm["no"], "ece", diske_yaz=False)["metin"]
denetle("MAGAZA iscisi brifingi", bm, kendi=("MAG_GIZLI_BILGI", "MAG_GIZLI_KURAL", "MAG_GIZLI_KARAR"),
        yabanci=YAZ_IZ)
sina("MAGAZA brifingi: takiminki ortaktakini EZDI (1 gun, 3 gun yok)",
     "MAG_TESLIM" in bm and "ORTAK_TESLIM" not in bm)

print("\n2. lider: inceleme, on kapi, plan")
ofis.tahta.kanit_ekle(gy["no"], "dosya", "x", "y", "can")
ofis.tahta.incelemeye_ver(gy["no"], ofis.tahta.gorev(gy["no"])["revizyon"])
denetle("YAZILIM lideri incelemesi", ofis.lider.inceleme_metni(gy["no"]),
        kendi=("YAZ_GIZLI_KURAL",), yabanci=MAG_IZ, ortak=False)
soh = Sohbet(ofis, motor_fabrikasi=lambda a, **k: SahteMotor())
tri = soh.triyaj_metni("iade suresi kac gun? belgeye bak", kanat_id=KY)
denetle("YAZILIM lideri on kapisi (triyaj)", tri, kendi=("YAZ_GIZLI_BELGE", "YAZ_GIZLI_KURAL"),
        yabanci=MAG_IZ)
tri_m = soh.triyaj_metni("iade suresi kac gun? belgeye bak", kanat_id=KM)
denetle("MAGAZA lideri on kapisi", tri_m, kendi=("MAG_GIZLI_BELGE", "MAG_GIZLI_BILGI"), yabanci=YAZ_IZ)
plan = ofis.orkestra.plan_metni("iade ekrani", KY)
sina("YAZILIM plan istemi: baska takimdan iz yok", not sizinti(plan, MAG_IZ), str(sizinti(plan, MAG_IZ)))

print("\n3. ajan araclari (gercek MCP sureci)")
from ofis import mcp_sunucu as M  # noqa: E402
_eski = {k: os.environ.get(k) for k in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV")}
os.environ.update({"OFIS_DB": str(db.yol), "OFIS_PROJE": ofis.proje_id, "OFIS_AJAN": "can",
                   "OFIS_GOREV": str(gy["no"])})
ot = M.Oturum()
denetle("YAZILIM ajaninin `durum` araci", M.arac_durum(ot, {}), kendi=("YAZ_GIZLI_BILGI",), yabanci=MAG_IZ)
ba = M.arac_belge_ara(ot, {"sorgu": "iade suresi"})
sina("YAZILIM ajaninin `belge_ara`si: magaza belgesi YOK", "MAG_GIZLI_BELGE" not in ba
     and "YAZ_GIZLI_BELGE" in ba, ba[:200])
M.arac_bilgi_yaz(ot, {"konu": "api surumu", "icerik": "v3 YAZ_YENI"})
sina("YAZILIM ajaninin yazdigi bilgi YAZILIM takiminda",
     any(o["konu"] == "api surumu" for o in YAZ.gecerli_olgular())
     and not any(o["konu"] == "api surumu" for o in MAG.gecerli_olgular()))
for k, v in _eski.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v

print("\n4. danisma ve uyanis")
isaret = ofis.bellek.son_olay_id()
MAG.bilgi_ekle("kargo", "Yurtici MAG_YENI_OLAY", yazan="ece")
ofis.bellek.karar_yaz("MAG_YENI_KARAR kargo degisti", "fiyat", "lale", gorev_id=gm["id"])
YAZ.bilgi_ekle("veritabani", "PostgreSQL YAZ_YENI_OLAY", yazan="can")
uy = ofis.brifing.uyanis_metni("can", isaret)
sina("YAZILIM uyanis ozeti: magaza olaylari YOK", "MAG_YENI" not in uy, uy[:300])
sina("YAZILIM uyanis ozeti: kendi takimininki VAR", "YAZ_YENI_OLAY" in uy, uy[:300])
_m = ofis.postane.soru_sor("mert", "can", "iade suresi ne?", gorev_no=gy["no"])
with db.baglanti() as _c:
    m = dict(_c.execute("SELECT * FROM mesaj WHERE id = ?", (_m["id"],)).fetchone())
dm = Danisma(ofis).soru_metni(m)
sina("YAZILIM ajanina danisma: baska takimdan iz yok", not sizinti(dm, MAG_IZ), str(sizinti(dm, MAG_IZ)))

print("\n5. liderin incelemedeki BILGI satiri ve sohbet onerisi")
ofis.lider._hukmu_uygula(gy["no"], "KARAR: kapat\nBILGI: dagitim -> Vercel YAZ_LIDER", "mert", "can")
sina("YAZILIM liderinin BILGI'si YAZILIM takiminda",
     any("YAZ_LIDER" in o["icerik"] for o in YAZ.gecerli_olgular())
     and not any("YAZ_LIDER" in o["icerik"] for o in MAG.gecerli_olgular()))
on = MAG.sohbet_onerileri([{"konu": "hediye paketi", "icerik": "ucretsiz", "alinti": "hediye paketi ucretsiz"}],
                          "hediye paketi ucretsiz olsun", oneren="lale")
ofis.bellek.hafiza_onerisi_cevapla(on[0]["id"], yaz=True)
sina("'Takima yaz': bilgi MAGAZA takiminda, YAZILIM gormuyor",
     any(o["konu"] == "hediye paketi" for o in MAG.gecerli_olgular())
     and not any(o["konu"] == "hediye paketi" for o in YAZ.gecerli_olgular()))
on = MAG.sohbet_onerileri([{"konu": "calisma saati", "icerik": "9-18", "alinti": "9-18 arasi"}],
                          "9-18 arasi calisiyoruz", oneren="lale")
ofis.bellek.hafiza_onerisi_cevapla(on[0]["id"], yaz=True, herkese=True)
sina("'Herkese yaz': bilgi ORTAK, iki takim da goruyor",
     any(o["konu"] == "calisma saati" for o in YAZ.gecerli_olgular())
     and any(o["konu"] == "calisma saati" for o in MAG.gecerli_olgular()))

print("\n6. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
hy = json.dumps(ist.get(f"/api/hafiza?kanat={KY}").json())
sina("panel: YAZILIM secili -> magaza bilgisi/kurali yok", not sizinti(hy, MAG_IZ), str(sizinti(hy, MAG_IZ)))
ht = ist.get("/api/hafiza").json()
sina("panel: butun gorunum hepsini takim adiyla veriyor",
     {o["kanat_ad"] for o in ht["gecerli"]} >= {"MAGAZA", "YAZILIM", "ortak"})
r = ist.post("/api/bilgi", json={"konu": "panelden", "icerik": "x", "kanat": KM})
sina("panelden takima yazilan bilgi o takimda", r.status_code == 200 and r.json().get("kanat_id") == KM)
bel = ist.get(f"/api/belgeler?kanat={KY}").json()["belgeler"]
sina("panel belge listesi takima gore", [b["ad"] for b in bel] == ["api.txt"], str([b["ad"] for b in bel]))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
