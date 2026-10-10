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
surec.tur_isaretle(db, ofis.proje_id, g_canli["id"], True)   # gercek defterdeki gibi: tur kosuyor
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
bak(g_olu, "durdu", "Sürdür'e bas", "olu surec")
bak(g_canli, "calisiyor", "çalışıyor", "yasayan surec")
bak(g_inc, "inceleme", "lale", "inceleme")
bak(g_bagli, "bekliyor", f"#{g_canli['no']}", "bagimlilik")
bak(g_sira, "sirada", f"ufuk şu an #{g_canli['no']}", "ajan baska iste")
sina("son adim arac olayindan", x[g_canli["no"]]["son_adim"] == "Bash", x[g_canli["no"]]["son_adim"])
sina("geri donus sayisi", x[g_inc["no"]]["ret"] == 1)
sina("seni bekleyenler EN USTTE", [i["tur"] for i in t["isler"][:4]] == ["sen"] * 4,
     str([i["tur"] for i in t["isler"]]))
sina("ozet sayilari", t["ozet"]["sen"] == 4 and t["ozet"]["calisiyor"] == 1, str(t["ozet"]))

print("\n1b. TUR OLCUMU (#9): 'calisiyor' is, ofis o an tur kosturuyor mu?")
# Kaynak: ayar 'tur_kosuyor:<gorev_id>' (koltuk turu baslatinca yazar, bitince temizler).
# Gercek defterdeki biçim: gorev.durum='calisiyor', kosan_surec=panel sureci (YASIYOR),
# yazma_kilidi TAZE (sahiplen yazdi) -- yani eski nabiz olcumunu kandiran durum.
from datetime import datetime, timedelta, timezone  # noqa: E402
for ad in ("rana", "sema", "tuna", "vera", "zeki"):
    ofis.kadro.ise_al(ad, "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))


def isaretli_is(baslik, sahip, yol, hal):
    """hal: kosuyor (isaret taze) | eski (isaret 600 sn onceki) | bitti (isaret temizlenmis)
    | yok (hic tur baslamamis: yalniz sahiplenmis) | bozuk (isaret zamani okunamaz)."""
    g = T.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA, yazma_alani=[yol])
    g = T.sahiplen(g["no"], sahip, g["revizyon"])
    kosan(g, surec.kimlik())
    if hal != "yok":
        surec.tur_isaretle(db, ofis.proje_id, g["id"], hal != "bitti")
    deger = None
    if hal == "eski":
        eski_an = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat(timespec="seconds")
        deger = f"{surec.kimlik()}|{eski_an}"
    if hal == "bozuk":
        deger = f"{surec.kimlik()}|bozuk-zaman"
    if deger:
        with db.baglanti() as c:
            c.execute("UPDATE ayar SET deger = ? WHERE proje_id = ? AND anahtar = ?",
                      (deger, ofis.proje_id, surec.TUR_ANAHTARI + g["id"]))
    return T.gorev(g["no"])


g_tur = isaretli_is("Tur kosan", "sema", "a/tur", "kosuyor")
g_halka = isaretli_is("Isaret eski", "rana", "a/halka", "eski")
g_bitti = isaretli_is("Tur yeni bitti", "tuna", "a/bitti", "bitti")
g_yok = isaretli_is("Yeni sahiplenildi, tur baslamadi", "vera", "a/yok", "yok")
g_bozuk = isaretli_is("Isaret bozuk", "zeki", "a/bozuk", "bozuk")
t1 = DT.tablo(ofis)
x1 = {i["no"]: i for i in t1["isler"]}
sina("kilitler TAZE (olcum nabza bakmiyor, sahne eski olcumu kandiran sahne)",
     all(DT.tur_olcumu(ofis, g)[1].startswith(("ayar", "gorev")) for g in (g_tur, g_halka, g_bitti, g_yok)))
sina("(a) tur koşan: çalışıyor", x1[g_tur["no"]]["tur"] == "calisiyor" and x1[g_tur["no"]]["nerede"] == "çalışıyor",
     str(x1[g_tur["no"]]))
sina("(b) isaret 600 sn eski: durdu + Sürdür'e bas",
     x1[g_halka["no"]]["tur"] == "durdu" and x1[g_halka["no"]]["nerede"] == "durdu — Sürdür'e bas", str(x1[g_halka["no"]]))
sina("(b) tur YENI BITTI (kilit nabzi taze): durdu + Sürdür'e bas",
     x1[g_bitti["no"]]["tur"] == "durdu" and x1[g_bitti["no"]]["nerede"] == "durdu — Sürdür'e bas", str(x1[g_bitti["no"]]))
sina("(b) yeni sahiplenildi, tur HIC baslamadi (kilit taze): durdu + Sürdür'e bas",
     x1[g_yok["no"]]["tur"] == "durdu" and x1[g_yok["no"]]["nerede"] == "durdu — Sürdür'e bas", str(x1[g_yok["no"]]))
sina("olcumun KAYNAGI satirda yazili (ayar tur_kosuyor)",
     all("ayar tur_kosuyor" in x1[g["no"]]["olcum"] for g in (g_halka, g_bitti, g_yok)), x1[g_yok["no"]]["olcum"])
sina("(d) olculemiyor (isaret zamani bozuk): eskisi gibi çalışıyor",
     DT.tur_kosuyor_mu(ofis, g_bozuk) is None and x1[g_bozuk["no"]]["tur"] == "calisiyor", str(x1[g_bozuk["no"]]))
sina("tur_kosuyor_mu: True / False / None",
     DT.tur_kosuyor_mu(ofis, g_tur) is True and DT.tur_kosuyor_mu(ofis, g_bitti) is False
     and DT.tur_kosuyor_mu(ofis, g_bozuk) is None)
a1 = {j["ad"]: j for j in t1["ajanlar"]}
sina("ajan satiri ayni olcumu kullanir (rana durdu, sema calisiyor)",
     a1["rana"]["hal"] == "durdu" and a1["sema"]["hal"] == "calisiyor", f"{a1['rana']['hal']} {a1['sema']['hal']}")
# (c) onay/soru bekleyen is, isareti eski olsa da 'sen' kalir (once onay, sonra olcum)
g_onay2 = isaretli_is("Onay bekleyen", "ece", "a/onay", "eski")
ofis.postane.onay_iste("ece", "git push origin dev", risk="yuksek", gorev_no=g_onay2["no"])
g_soru2 = isaretli_is("Soru bekleyen", "ali", "a/soru", "eski")
ofis.postane.soru_sor("ali", "insan", "Hangi font?", gorev_no=g_soru2["no"])
g_dur2 = isaretli_is("Duraklatilmis", "oya", "a/dur", "eski")
T.duraklat(g_dur2["no"])
x1 = {i["no"]: i for i in DT.tablo(ofis)["isler"]}
sina("(c) onay bekleyen: seni bekliyor (sen)", x1[g_onay2["no"]]["tur"] == "sen", str(x1[g_onay2["no"]]))
sina("(c) soru bekleyen: seni bekliyor (sen)", x1[g_soru2["no"]]["tur"] == "sen", str(x1[g_soru2["no"]]))
sina("duraklatilmis: 'durduruldu' kalir (olcum ezmez)", "durduruldu" in x1[g_dur2["no"]]["nerede"], str(x1[g_dur2["no"]]))
# GECIS (eski kod): isaret yazmayan kodla baslamis is, isaret yok diye 'durdu' SAYILMAZ
ofis.kadro.ise_al("oya2", "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))
g_eski = isaretli_is("Eski kodla baslamis", "oya2", "a/eski", "yok")
eski_an = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
with db.baglanti() as c:                         # isaret kaynagindan ONCE sahiplenilmis
    c.execute("UPDATE gorev SET guncellendi = ? WHERE id = ?", (eski_an, g_eski["id"]))
    c.execute("UPDATE olay SET olusturuldu = ? WHERE gorev_id = ? AND tur = 'sahiplenildi'", (eski_an, g_eski["id"]))
g_eski = T.gorev(g_eski["no"])
sina("gecis: kaynaktan ONCE baslamis, isaretsiz is -> None (olculemez), pano 'calisiyor'",
     DT.tur_kosuyor_mu(ofis, g_eski) is None
     and {i["no"]: i for i in DT.isler(ofis)}[g_eski["no"]]["tur"] == "calisiyor",
     str(DT.tur_olcumu(ofis, g_eski)))
# kaynak bu defterde HIC yazilmamis (isaret ureten kod hic kosmamis) -> None
d2 = Path(tempfile.mkdtemp(prefix="ofis-durumt2-"))
db2 = Veritabani(d2 / "o.sqlite3")
ofis2 = Ofis.proje_ac(db2, "Eski", amac="a", basari_olcutu="b", kok_klasor=str(d2))
ka2 = ofis2.kanat_ac("GENEL", "GN")
ofis2.kadro.ise_al("lale", "lider", kanat_id=ka2, lider_mi=True, motor="sahte", klasor=str(d2))
ofis2.kadro.ise_al("ece", "arayuz", kanat_id=ka2, motor="sahte", klasor=str(d2))
g2 = ofis2.tahta.gorev_ac("Eski defter", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=ka2)
g2 = ofis2.tahta.sahiplen(g2["no"], "ece", g2["revizyon"])
sina("kaynak hic yazilmamis defter -> None, pano 'calisiyor' (eskisi gibi)",
     DT.tur_kosuyor_mu(ofis2, g2) is None and DT.isler(ofis2)[0]["tur"] == "calisiyor",
     str(DT.tur_olcumu(ofis2, g2)))
# koltuk gercekten isaretliyor mu: akit sarmalayicisi isareti yazar ve temizler
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.koltuk import Koltuk  # noqa: E402
g_k = T.gorev_ac("Koltuk isareti", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
gozlem = []


class GozlemMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        gozlem.append(surec.tur_isareti(db, ofis.proje_id, g_k["id"]))
        return super().tur_kos(metin, **ayar)


try:
    Koltuk(ofis, motor_fabrikasi=lambda ad, **a: GozlemMotor(cevap="Yazdim.")).kos(g_k["no"], "oya")
except Exception as exc:                         # noqa: BLE001
    gozlem.append(("HATA", repr(exc)))
son = surec.tur_isareti(db, ofis.proje_id, g_k["id"])
sina("koltuk: tur SIRASINDA isaret dolu (bu surec), tur SONRA temizlenmis",
     bool(gozlem) and gozlem[0] and gozlem[0][0] == surec.kimlik() and son is not None and son[0] == "",
     f"{gozlem} {son}")
# test sonraki bolumlerin sayilarini bozmasin: bu ekstra isleri kapat
with db.baglanti() as c:
    for g_ in (g_tur, g_halka, g_bitti, g_yok, g_bozuk, g_onay2, g_soru2, g_dur2, g_k):
        c.execute("UPDATE gorev SET durum = 'iptal' WHERE id = ?", (g_["id"],))
        c.execute("DELETE FROM yazma_kilidi WHERE gorev_id = ?", (g_["id"],))
    c.execute("UPDATE onay SET durum = 'reddedildi' WHERE durum = 'bekliyor' AND eylem = 'git push origin dev'")

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

print("\n4. deger ozeti (B5)")
import json as _json  # noqa: E402
from ofis import deger as DG  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
eski = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(timespec="seconds")
with db.baglanti() as c:
    for g_, ret_ in ((g_onay, False), (g_giris, True), (g_kredi, False)):
        c.execute("INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, olusturuldu) VALUES (?,?,?,?,?,datetime('now'))",
                  (ofis.proje_id, "lale", g_["id"], "kapandi", "kapandi"))
        if ret_:
            c.execute("INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, olusturuldu) VALUES (?,?,?,?,?,datetime('now'))",
                      (ofis.proje_id, "lale", g_["id"], "ret", "eksik"))
    # 20 gun onceki kapanis HAFTAYA girmez
    c.execute("INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, olusturuldu) VALUES (?,?,?,?,?,?)",
              (ofis.proje_id, "lale", g_soru["id"], "kapandi", "eski", eski))
    c.execute("INSERT INTO teslim_puani (gorev_id, proje_id, puan, gerekce, veren, olusturuldu) VALUES (?,?,?,?,?,datetime('now'))",
              (g_onay["id"], ofis.proje_id, 4, "iyi", "insan"))
    c.execute("INSERT INTO teslim_puani (gorev_id, proje_id, puan, gerekce, veren, olusturuldu) VALUES (?,?,?,?,?,datetime('now'))",
              (g_kredi["id"], ofis.proje_id, 5, "cok iyi", "insan"))
for motor, hesap, jeton in (("claude", "", 1000), ("claude", "", 500), ("codex", "codex2", 300)):
    db.olay_yaz(ofis.proje_id, "tur_ozeti", _json.dumps({"motor": motor, "hesap": hesap, "jeton": jeton,
                                                          "sure_ms": 60000}), ajan_ad="ece")
v = DG.ozet(db, ofis.proje_id)
sina("bu hafta biten 3 (20 gun onceki sayilmaz)", v["biten"] == 3, str(v["biten"]))
sina("ilk seferde 2 / oran %67", v["ilk_seferde"] == 2 and v["ilk_seferde_oran"] == 0.67, str(v))
sina("geri donen is sayisi (bu hafta ret alan)", v["geri_donen"] >= 1, str(v["geri_donen"]))
sina("puan ortalamasi 4,5 (2 is)", v["puan_ort"] == 4.5 and v["puanli"] == 2)
h = {(x["motor"], x["hesap"]): x for x in v["harcama"]}
sina("hesap basina harcama: claude 2 tur 1500 jeton, codex2 300",
     h[("claude", "")]["tur"] == 2 and h[("claude", "")]["jeton"] == 1500 and h[("codex", "codex2")]["jeton"] == 300,
     str(v["harcama"]))
sina("insandan istenen soru/onay sayilari", v["insana"]["soru"] >= 1 and v["insana"]["onay"] >= 3, str(v["insana"]))
sina("7 gunluk seri, bugun 3", len(v["gunluk"]) == 7 and v["gunluk"][-1]["biten"] == 3, str(v["gunluk"]))

print("\n5. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
_ist = TestClient(olustur(db.yol))
rd = _ist.get("/api/deger?gun=7")
sina("GET /api/deger", rd.status_code == 200 and rd.json()["biten"] == 3, rd.text[:200])
r = _ist.get("/api/durum")
sina("GET /api/durum", r.status_code == 200 and r.json()["isler"], r.text[:200])
JS = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
HTML = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")
sina("Durum panosu kayitli ve cizici var",
     'durum:    { ad: "Durum"' in JS and "async function cizDurum" in JS and 'id="pano-durum"' in HTML)
sina("deger bolumu Durum panosunda", "async function cizDeger" in JS and "BU HAFTA" in JS)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
