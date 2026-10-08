# -*- coding: utf-8 -*-
"""DURUM TABLOSU (08.10.2026, B2 + B4). Jeton yakmaz.

Her acik isin "nerede" satiri olculmus kayittan cikar: senin onayin, giris,
kredi onayi, senin cevabin, baska ajana soru, durdurulmus is, olu surec,
calisan surec, inceleme, bagimlilik, sira (ajan baska iste). Son adim arac
olayindan, geri donus sayisi ret olayindan. Seni bekleyenler en ustte. Ajan
satiri ne yaptigini ve sirasini soyler; lidere giden sira kuyruktan. Panel
ucu ve pano.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, durum_tablosu as DT, giris, kuyruk, surec  # noqa: E402
from ofis.tarayici import KREDI_PAKETI_ISARETI  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-durumt-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Durum", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
for ad in ("ece", "can", "nil", "ali", "oya", "efe", "ada", "ufuk"):
    ofis.kadro.ise_al(ad, "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))
T = ofis.tahta


def is_ac(baslik, sahip, *, calistir=True):
    g = T.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
    if calistir:
        g = T.sahiplen(g["no"], sahip, g["revizyon"])
    return g


def kosan(g, kim):
    with db.baglanti() as c:
        c.execute("UPDATE gorev SET kosan_surec = ? WHERE id = ?", (kim, g["id"]))


g_onay = is_ac("Push", "ece")
ofis.postane.onay_iste("ece", "git push origin main", risk="yuksek", gorev_no=g_onay["no"])
g_giris = is_ac("Magaza girisi", "can")
ofis.postane.onay_iste("can", giris.ONEK + " shopify", ayrinti="giris", gorev_no=g_giris["no"])
g_kredi = is_ac("Video", "nil")
ofis.postane.onay_iste("nil", "KREDI PAKETI (100 kredi, 1 uretim): reklam", ayrinti=KREDI_PAKETI_ISARETI + " 1",
                       gorev_no=g_kredi["no"])
g_soru = is_ac("Tema", "ali")
ofis.postane.soru_sor("ali", "insan", "Hangi renk?", gorev_no=g_soru["no"])
g_ajan = is_ac("Metin", "oya")
ofis.postane.soru_sor("oya", "efe", "Baslik ne olsun?", gorev_no=g_ajan["no"])
g_dur = is_ac("Durdurulan", "efe")
T.duraklat(g_dur["no"])
g_olu = is_ac("Coken", "ada")
kosan(g_olu, "999999:1")
g_canli = is_ac("Calisan", "ufuk")
kosan(g_canli, surec.kimlik())
db.olay_yaz(ofis.proje_id, "arac", "Bash\nnpm test", ajan_ad="ufuk", gorev_id=g_canli["id"])
g_inc = is_ac("Incelenecek", "ece", calistir=False)
g_inc = T.sahiplen(g_inc["no"], "ece", g_inc["revizyon"])
T.kanit_ekle(g_inc["no"], "terminal", "pytest", "ok", "ece")
T.incelemeye_ver(g_inc["no"], T.gorev(g_inc["no"])["revizyon"])
db.olay_yaz(ofis.proje_id, "ret", "eksik", gorev_id=g_inc["id"])
g_bagli = is_ac("Birlestir", "", calistir=False)
T.bagimlilik_ekle(g_bagli["no"], g_canli["no"])
g_sira = T.gorev_ac("Sonraki", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA, sahip="ufuk")
kuyruk.ekle(ofis, "Raporu da hazirla", "lale")

print("1. her isin nerede satiri")
t = DT.tablo(ofis)
x = {i["no"]: i for i in t["isler"]}


def bak(g, tur, parca, ad):
    i = x.get(g["no"]) or {}
    sina(f"{ad}: {tur} / '{parca}'", i.get("tur") == tur and parca in i.get("nerede", ""),
         f"{i.get('tur')} | {i.get('nerede')}")


bak(g_onay, "sen", "onayını bekliyor: git push", "onay")
bak(g_giris, "sen", "giriş bekliyor", "giris istegi")
bak(g_kredi, "sen", "kredi onayını", "kredi paketi")
bak(g_soru, "sen", "cevabını bekliyor: Hangi renk?", "patrona soru")
bak(g_ajan, "bekliyor", "efe, cevab", "baska ajana soru")
bak(g_dur, "durdu", "durduruldu", "durdurulan is")
bak(g_olu, "durdu", "süreç kapanmış", "olu surec")
bak(g_canli, "calisiyor", "çalışıyor", "yasayan surec")
bak(g_inc, "inceleme", "lale", "inceleme")
bak(g_bagli, "bekliyor", f"#{g_canli['no']}", "bagimlilik")
bak(g_sira, "sirada", f"ufuk şu an #{g_canli['no']}", "ajan baska iste")
sina("son adim arac olayindan", x[g_canli["no"]]["son_adim"] == "Bash", x[g_canli["no"]]["son_adim"])
sina("geri donus sayisi", x[g_inc["no"]]["ret"] == 1)
sina("seni bekleyenler EN USTTE", [i["tur"] for i in t["isler"][:4]] == ["sen"] * 4,
     str([i["tur"] for i in t["isler"]]))
sina("ozet sayilari", t["ozet"]["sen"] == 4 and t["ozet"]["calisiyor"] == 1, str(t["ozet"]))

print("\n2. ajanlar ve sira")
a = {j["ad"]: j for j in t["ajanlar"]}
sina("ufuk calisiyor, sirasinda siradaki is", a["ufuk"]["hal"] == "calisiyor"
     and any(f"#{g_sira['no']}" in s for s in a["ufuk"]["sirada"]), str(a["ufuk"]))
sina("ali seni bekliyor", a["ali"]["hal"] == "sen", str(a["ali"]))
sina("ada durdu", a["ada"]["hal"] == "durdu")
sina("lider bosta ve lider isaretli", a["lale"]["hal"] == "bos" and a["lale"]["lider"])
sina("seni bekleyen ajanlar ustte", t["ajanlar"][0]["hal"] == "sen")
sina("lidere giden sira kuyruktan", any("Raporu da hazirla" in k["metin"] for k in t["sira"]), str(t["sira"]))

print("\n3. kapanan is tabloda yok")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'bitti' WHERE id = ?", (g_onay["id"],))
sina("biten is listede degil", g_onay["no"] not in {i["no"] for i in DT.isler(ofis)})

print("\n4. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
r = TestClient(olustur(db.yol)).get("/api/durum")
sina("GET /api/durum", r.status_code == 200 and r.json()["isler"], r.text[:200])
JS = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
HTML = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")
sina("Durum panosu kayitli ve cizici var",
     'durum:    { ad: "Durum"' in JS and "async function cizDurum" in JS and 'id="pano-durum"' in HTML)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
