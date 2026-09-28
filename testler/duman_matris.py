# -*- coding: utf-8 -*-
"""MOTOR MATRISININ KENDISI -- jeton yakmadan (B5).

Matris yeni bir motorun kapisi. Kapi iki yonde de sinanir:

* **Durust** bir sahte motor (iddia ettigini yapar, etmedigini "yok" diye
  bildirir) KABUL edilmeli -- "yok" kusur degildir.
* **Yalanci** bir sahte motor (kanca, kanal, tavan, arac kapatma IDDIA
  eder ama yapmaz; yazma yasagini cigner; oturumu hatirlamaz) REDDEDILMELI
  ve her yalan ADIYLA sayilmali.

Hic reddetmeyen kapi kapi degildir; her seyi reddeden de.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matris as M                         # noqa: E402
from ofis.motor import motor_kaydet        # noqa: E402
from ofis.yollar import OFIS_EVI           # noqa: E402

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


print("\n0. YALITIM")
_gercek = (Path.home() / ".agentofis").resolve()
sina("son olcum dosyasi gecici kokte (gercek ~/.agentofis degil)",
     _gercek not in Path(M.SON_OLCUM).resolve().parents, str(M.SON_OLCUM))

motor_kaydet(M.DurustSahte)
motor_kaydet(M.YalanciSahte)

print("\n1. DURUST sahte motor -- KABUL")
d = M.olc(M.DurustSahte(), "sahte")
h = d["hucreler"]
sina("hukum KABUL", d["hukum"]["karar"] == "KABUL", str(d["hukum"]))
for z in M.ZORUNLU:
    sina(f"  zorunlu {z} var", h.get(z, {}).get("durum") == "var", str(h.get(z)))
for ad in ("onay_kapisi", "araclar_kapali", "butce_tavani", "tarayici", "baglayici"):
    sina(f"  {ad} 'yok' (bayrak kapali, durust)", h.get(ad, {}).get("durum") == "yok", str(h.get(ad)))
sina("  tur ici not ULASTI", h["tur_ici_not"]["durum"] == "var", str(h["tur_ici_not"]))
sina("  durdurma turu KESTI", h["durdurma"]["durum"] == "var", str(h["durdurma"]))
sina("  'yok' hucreler hukmu bozmadi, tam_dolu degil", d["hukum"]["tam_dolu"] is False)
sina("  kanit kanali bayraga gore soyleniyor", "metin koprusu" in h["kanit"]["not"])

print("\n2. YALANCI sahte motor -- RED, yalanlar adiyla")
y = M.olc(M.YalanciSahte(), "sahte")
hy = y["hucreler"]
sina("hukum RED", y["hukum"]["karar"] == "RED", str(y["hukum"]))
for ad in ("onay_kapisi", "tur_ici_not", "butce_tavani", "araclar_kapali"):
    sina(f"  {ad} YALAN", hy.get(ad, {}).get("durum") == "YALAN", str(hy.get(ad)))
sina("  yalan listesi dort hucreyi sayiyor",
     set(y["hukum"]["yalan"]) >= {"onay_kapisi", "tur_ici_not", "butce_tavani", "araclar_kapali"},
     str(y["hukum"]["yalan"]))
sina("  yazma yasagini cigneyince zorunlu KALDI",
     hy["kafa_yazamaz"]["durum"] == "KALDI" and "kafa_yazamaz" in y["hukum"]["zorunlu_eksik"])
sina("  oturumu hatirlamayinca zorunlu KALDI",
     hy["oturum_surer"]["durum"] == "KALDI" and "oturum_surer" in y["hukum"]["zorunlu_eksik"])
sina("  bayraklar raporda (iddia ile olcum yan yana)",
     y["bayraklar"].get("izin_kancasi") is True and d["bayraklar"].get("izin_kancasi") is False)

print("\n3. HUKUM kurali")
sina("yalniz 'yok' -> KABUL", M.hukum(
    {z: {"durum": "var"} for z in M.ZORUNLU} | {"onay_kapisi": {"durum": "yok"}})["karar"] == "KABUL")
sina("tek YALAN -> RED", M.hukum(
    {z: {"durum": "var"} for z in M.ZORUNLU} | {"onay_kapisi": {"durum": "YALAN"}})["karar"] == "RED")
sina("zorunlu olculemedi -> RED (kabul edilmez)", M.hukum(
    {z: {"durum": "var"} for z in M.ZORUNLU} | {"kanit": {"durum": "olculemedi"}})["karar"] == "RED")
sina("bayrakli hucre hata -> BILINMIYOR (KABUL degil)", M.hukum(
    {z: {"durum": "var"} for z in M.ZORUNLU} | {"tarayici": {"durum": "hata"}})["karar"] == "BILINMIYOR")
sina("hepsi var -> tam dolu", M.hukum(
    {ad: {"durum": "var"} for ad, *_ in M.HUCRELER})["tam_dolu"] is True)

print("\n4. SINANAN MOTOR TEK BASINA")
s = M.Sahne(M.DurustSahte(), "sahte")
try:
    baska = s.fabrika("claude")
    sina("fabrika baska motoru KOSTURULAMAZ verir (zincir devredemez)",
         not baska.musait_mi(), baska.durum_notu())
finally:
    s.kapat()

print("\n5. SON OLCUM YAZIMI")
M.son_olcumu_yaz(d)
M.son_olcumu_yaz(y)
import json  # noqa: E402
kayit = json.loads(M.SON_OLCUM.read_text(encoding="utf-8"))
sina("iki motor ayri anahtarda", {"durust", "yalanci"} <= set(kayit))
sina("hukum ve zaman yazildi", kayit["durust"]["hukum"]["karar"] == "KABUL"
     and bool(kayit["durust"].get("zaman")))

print("\n6. TEK HUCRE yeniden olcumu -- onceki TAM olcume islenir")
parca = {"motor": "durust", "hucreler": {"onay_kapisi": {"durum": "YALAN", "not": "x"}}}
M.son_olcumu_yaz(parca, yalniz_hucreler=True)
kayit = json.loads(M.SON_OLCUM.read_text(encoding="utf-8"))
sina("hucre islendi, oteki hucreler DURUYOR",
     kayit["durust"]["hucreler"]["onay_kapisi"]["durum"] == "YALAN"
     and kayit["durust"]["hucreler"]["tur"]["durum"] == "var")
sina("hukum YENIDEN hesaplandi (RED)", kayit["durust"]["hukum"]["karar"] == "RED")
M.son_olcumu_yaz({"motor": "hic-olculmemis", "hucreler": {"tur": {"durum": "var", "not": ""}}},
                 yalniz_hucreler=True)
kayit = json.loads(M.SON_OLCUM.read_text(encoding="utf-8"))
sina("onceki tam olcum yoksa parca YAZILMAZ (tam sanilmasin)", "hic-olculmemis" not in kayit)

# ------------------------------------------------------------ motor karti
print("\n-- MOTOR KARTI (E60): olcumden gelir, iddiadan degil --")
from ofis import motor_karti as MK   # noqa: E402


class _KartMotor:
    ad = "kartsiz"
    izin_kancasi = True          # iddia ediyor
    tur_ici_mesaj = False        # dürüstçe yok
    araclar_kapatilabilir = False
    butce_destegi = False
    mcp_konusur = True
    baglayici_tasir = False

    def musait_mi(self):
        return True

    def durum_notu(self):
        return ""


def _fab(ad):
    return _KartMotor()


k0 = MK.kart("kartsiz", None, _fab)
h0 = {h["ad"]: h["durum"] for h in k0["hucreler"]}
sina("olcum yokken iddia edilen yetenek 'olculmedi' (iddia olcum degildir)",
     h0["onay_kapisi"] == "olculmedi", str(h0))
sina("olcum yokken bildirilmeyen yetenek 'yok'", h0["tur_ici_not"] == "yok", str(h0))
sina("olcum yokken zorunlu hucre de 'olculmedi'", h0["tur"] == "olculmedi", str(h0))
sina("olcum yokken hukum yok, olculdu=False", k0["hukum"] is None and not k0["olculdu"])
olc = {"hucreler": {"tur": {"durum": "var", "not": "x"},
                    "onay_kapisi": {"durum": "YALAN", "not": "kapi durdurmadi"},
                    "tarayici": {"durum": "var", "not": "ok"}},
       "bayraklar": {"izin_kancasi": True, "mcp_konusur": False},
       "hukum": {"karar": "RED"}, "zaman": "2026-09-28T10:00:00", "model": "m"}
h1 = {h["ad"]: h["durum"] for h in MK.kart("kartsiz", olc, _fab)["hucreler"]}
sina("olculen 'var' karta gecer", h1["tur"] == "var")
sina("YALAN gizlenmez", h1["onay_kapisi"] == "YALAN", str(h1))
sina("bayrak olcumden sonra degistiyse 'bayat'", h1["tarayici"] == "bayat", str(h1))
sina("kartta her hucre var (tek liste)", len(MK.kart("kartsiz", olc, _fab)["hucreler"]) == len(M.HUCRELER))
sina("matris ile kart AYNI hucre listesini kullanir", M.HUCRELER is MK.HUCRELER)
sina("sahte motor kartlarda YOK", all(x["motor"] != "sahte" for x in MK.kartlar()))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
