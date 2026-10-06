# -*- coding: utf-8 -*-
"""TESLIM PUANI ve ON TAHMIN (06.10.2026, Asama 2 / E78, E74). Jeton yakmaz.

Puan: yalniz biten is, yalniz patron, 1-5; 3 ve altinda gerekce zorunlu ve
ajanin DERSI olur; puan karneye gider, 2 ve alti "temiz gecis" sayilmaz.

Tahmin: karnedeki ayni tur islerin ortanca suresi ve jetonu; kota yuzdesi
yalniz saglayicinin pencere olcumleri TUTARLIYSA (dis kullanim sisirmesi
olculdu) -- yoksa "bilinmiyor". Dagitimda tahmin deftere ve patronun
gordugu satira yazilir; kapanista gerceklesenle yan yana.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, karne, kullanim, puan as P, tahmin as T  # noqa: E402
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


def hata(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except P.PuanHatasi as exc:
        return str(exc)
    return ""


d = Path(tempfile.mkdtemp(prefix="ofis-puan-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Puan", amac="a", basari_olcutu="b", kok_klasor=str(d))
kn = ofis.kanat_ac("GENEL", "GE")
ofis.kadro.ise_al("lale", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="claude", model="sonnet", klasor=str(d))


def biten_is(baslik, *, sure_ms=60000, jeton=40000):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn,
                            zorluk="orta")
    ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
    kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"sure_ms": sure_ms, "jeton": jeton, "model": "sonnet"},
                           ajan_ad="cinar", gorev_id=g["id"], motor="claude")
    ofis.tahta.kanit_ekle(g["no"], "dosya", "r.md", "yazildi", "cinar")
    ofis.tahta.incelemeye_ver(g["no"], ofis.tahta.gorev(g["no"])["revizyon"])
    ofis.lider._hukmu_uygula(g["no"], "KARAR: kapat\nHAFIZA: yok", "lale", "cinar")
    return ofis.tahta.gorev(g["no"])


print("== teslim puani ve on tahmin ==\n")
print("1. karne jetonu ve tahmin")
g1 = biten_is("Bir", sure_ms=60000, jeton=40000)
sina("is kapandi", g1["durum"] == "bitti", g1["durum"])
s = [x for x in karne.satirlar() if x.get("gorev") == g1["id"]]
sina("karne satiri jeton ve gorev tasiyor", s and s[0].get("jeton") == 40000, str(s))
t = T.tahmin(db, ofis.proje_id, meslek="backend", zorluk="orta", motor="claude")
sina("tek isle tahmin YOK (en az 2 ornek)", t["ornek"] == 0 and "tahmin yok" in T.metin(t), str(t))
g2 = biten_is("Iki", sure_ms=120000, jeton=60000)
t = T.tahmin(db, ofis.proje_id, meslek="backend", zorluk="orta", motor="claude")
sina("iki isle tahmin: ortanca sure ve jeton", t["ornek"] == 2 and t["sure_sn"] == 90.0
     and t["jeton"] == 50000, str(t))
sina("pencere olcumu yokken kota yuzdesi BILINMIYOR", t["yuzde_5s"] is None
     and "bilinmiyor" in T.metin(t, "claude"), T.metin(t, "claude"))


def pencere_turu(kullanim_, jeton, yen=1791240431):
    kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"jeton": jeton, "model": "sonnet",
                           "limit_pencere": {"pencereler": {"5s": {"kullanim": kullanim_, "yenilenme": yen}}}},
                           ajan_ad="cinar", motor="claude", yol="olcum")


for i in range(7):                       # tutarli: her 100 bin jetona %2
    pencere_turu(0.10 + 0.02 * i, 100000)
o = T.oran(db, ofis.proje_id, "claude")
sina("tutarli pencere olcumunden oran (100 bin jeton = %2)", o is not None and abs(o * 1e5 - 0.02) < 1e-6, str(o))
t = T.tahmin(db, ofis.proje_id, meslek="backend", zorluk="orta", motor="claude")
sina("tahmin kota yuzdesini veriyor (50 bin jeton = %1)", t["yuzde_5s"] == 1.0, str(t))
# Dis kullanim (patronun kendi oturumu) ayni hesabi doldurdugunda ardisik
# olcumler arasi artis aradaki jetonla orantisiz yayilir: oran VERILMEZ.
for k in (0.30, 0.31, 0.45, 0.46, 0.80, 0.81, 0.83):
    kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"jeton": 100000, "model": "gpt-6-luna",
                           "limit_pencere": {"pencereler": {"5s": {"kullanim": k, "yenilenme": 1}}}},
                           ajan_ad="cinar", motor="codex", yol="olcum")
sina("TUTARSIZ olcumde oran verilmez (dis kullanim sisirmesi)",
     T.oran(db, ofis.proje_id, "codex") is None, str(T.oran(db, ofis.proje_id, "codex")))

print("\n2. dagitimda tahmin, kapanista gerceklesen")
KOL = [{"baslik": "API yaz", "sahip": "cinar", "neden": "n", "kabul_olcutu": "pytest yesil",
        "govde": "yaz", "yazma_alani": ["api/"], "zorluk": "orta"}]


class Asamali(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps({"karar": "dagit", "gerekce": "is", "hedef": "API",
                                                   "plan": {"bol": False, "gerekce": "tek", "kollar": KOL}},
                                                  ensure_ascii=False) + "\n```"
        else:
            self.cevap = "tamam"
        return super().tur_kos(metin, **ayar)


from ofis import sohbet as _S  # noqa: E402
_notlar = []
_asil_not = _S.AkisYazici.not_yaz
_S.AkisYazici.not_yaz = lambda self, metin: (_notlar.append(metin), _asil_not(self, metin))[1]
sohbet = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: Asamali(cevap=""))
olaylar = list(sohbet.konus("api yaz", azami_tik=0))
_S.AkisYazici.not_yaz = _asil_not
with db.baglanti() as c:
    th = [r[0] for r in c.execute("SELECT govde FROM olay WHERE tur='tahmin'")]
    akis = " ".join(r[0] for r in c.execute("SELECT govde FROM olay WHERE tur IN ('akis','cevap_akisi','sohbet_akis') "
                                            "OR govde LIKE '%Tahmin:%'"))
sina("dagitimda tahmin deftere yazildi", len(th) >= 1 and json.loads(th[-1]).get("ornek") == 2, str(th[-1:]))
sina("patronun gordugu (canli) satirda 'Tahmin:' var", any("Tahmin:" in n for n in _notlar), str(_notlar)[-300:])
gd = ofis.tahta.liste()[-1]
T.gerceklesen_yaz(db, ofis.proje_id, gd, sure_sn=75.0, jeton=45000)
with db.baglanti() as c:
    tg = [json.loads(r[0]) for r in c.execute("SELECT govde FROM olay WHERE tur='tahmin_gercek'")]
sina("kapanista tahmin gerceklesenle yan yana", tg and tg[-1]["gercek_jeton"] == 45000
     and tg[-1]["tahmin_jeton"] == 50000, str(tg[-1:]))

print("\n3. teslim puani")
sina("biten olmayan is puanlanmaz", "kapanmadi" in hata(P.ver, ofis, gd["no"], 4))
sina("ajan puanlayamaz", "patron" in hata(P.ver, ofis, g1["no"], 5, kim="lale"))
sina("6 puan reddedilir", bool(hata(P.ver, ofis, g1["no"], 6)))
sina("3 ve altinda gerekce zorunlu", "gerekce zorunlu" in hata(P.ver, ofis, g1["no"], 2))
r = P.ver(ofis, g1["no"], 2, "rapor Excel degil Word geldi")
dersler = [x["ders"] for x in ofis.kadro.dersler("cinar")]
sina("dusuk puanin gerekcesi ajanin DERSI oldu", r["ders"] and any("Excel degil Word" in x for x in dersler),
     str(dersler))
s = [x for x in karne.satirlar() if x.get("gorev") == g1["id"]]
sina("karne satiri puani tasiyor", s and s[0].get("puan") == 2, str(s))
oz = karne.ozet("backend", "orta")["motorlar"].get("claude", {})
sina("2/5 puanli is karnede TEMIZ sayilmadi", oz.get("n") == 2 and oz.get("temiz") == 1, str(oz))
P.ver(ofis, g1["no"], 5)
oz = karne.ozet("backend", "orta")["motorlar"].get("claude", {})
sina("yeni puan eskisinin yerine gecti (5/5 -> temiz)", oz.get("temiz") == 2, str(oz))
sina("puan okunuyor", P.oku(db, ofis.proje_id, g1["id"])["puan"] == 5)
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
r = ist.post(f"/api/gorev/{g2['no']}/puan", json={"puan": 4, "gerekce": ""})
sina("panelden puan", r.status_code == 200 and r.json()["puan"] == 4, r.text[:120])
sina("gorev cevabi puani tasiyor", ist.get(f"/api/gorev/{g2['no']}").json().get("puan", {}).get("puan") == 4)
r = ist.post(f"/api/gorev/{g2['no']}/puan", json={"puan": 1, "gerekce": ""})
sina("panel gerekcesiz dusuk puani 400 ile reddediyor", r.status_code == 400)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
