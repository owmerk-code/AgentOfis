# -*- coding: utf-8 -*-
"""Degisim duman testi: ajanin ANLATTIGI degil diskte OLCULEN.

Sinanan sey bir arayuz degil bir OLCUM: tur oncesi/sonrasi anlik
goruntunun farki dogru mu, beyan edilen yazma alaniyla gercek yazma
karsilastiriliyor mu, ve olcum YANLIS SUCLAMA uretmiyor mu.

Son madde bu dosyadaki en onemli sinama: paralel turlar ayni kokte
kosar ve o zaman fark "kim yazdi" sorusunu cevaplayamaz. Bastirmayan
bir denetim, komsu ajanin dosyasini bu ajana yazip onu beyan disina
yazmakla suclardi -- bu projede bir kez odenen hata sinifi.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk
from ofis import degisim
from ofis.motor.sahte import SahteMotor

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


print("== degisim duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-degisim-"))
proje_kok = kok / "calisma"
proje_kok.mkdir()

# --------------------------------------------------------------------------
print("1. ANLIK GORUNTU -- neyi olcer, neyi olcmez")

(proje_kok / "a.txt").write_text("bir\niki\n", encoding="utf-8")
(proje_kok / "alt").mkdir()
(proje_kok / "alt" / "b.py").write_text("x = 1\n", encoding="utf-8")
(proje_kok / "__pycache__").mkdir()
(proje_kok / "__pycache__" / "c.txt").write_text("gurultu", encoding="utf-8")
(proje_kok / "ikili.bin").write_bytes(b"AB\x00CD" + b"z" * 50)
(proje_kok / "dev.log").write_text("x" * (degisim.AZAMI_DOSYA_BAYT + 10),
                                   encoding="utf-8")

an = degisim.anlik(proje_kok)

# Satir sonu Windows'ta CRLF yazilir; olcum onu OLDUGU GIBI okur --
# normalize etseydik "dosya degisti mi" sorusu yanlis cevaplanirdi.
sina("metin dosyasi olculdu",
     [x.strip() for x in an["a.txt"]["metin"]] == ["bir", "iki"])
sina("alt klasor kok-goreli ve '/' ayracli", "alt/b.py" in an)
sina("__pycache__ ATLANDI", not any(y.startswith("__pycache__") for y in an))
sina("ikili dosya isaretlendi, icerigi okunmadi",
     an["ikili.bin"]["metin"] is None
     and an["ikili.bin"]["olculemedi"] == "ikili dosya")
sina("cok buyuk dosya isaretlendi",
     an["dev.log"]["metin"] is None
     and "cok buyuk" in an["dev.log"]["olculemedi"])
# Olculemeyen dosyanin da OZETI var: nasil degistigi bilinmese de
# DEGISTIGI bilinir. Ozet olmasaydi buyuk bir dosyanin degisimi hic
# gorunmezdi -- sessizce eksik gosteren bir olcum.
sina("olculemeyen dosyanin da ozeti var", bool(an["ikili.bin"]["ozet"]))
sina("olmayan kok bos doner", degisim.anlik(kok / "yok") == {})
# DEGISMEZ: `olculemedi` dolu olan her kayitta `metin` None'dir.
# Yamanin bos kalmasi bir kapiya degil BUNA dayaniyor -- kapi denedim,
# mutasyonda hicbir sey ates etmedi cunku kapi hicbir sey yapmiyordu.
# Kirilirsa okunmamis bir dosyaya yama uydurulur.
sina("DEGISMEZ: olculemedi varsa metin None",
     all(v["metin"] is None for v in an.values() if v["olculemedi"]))
sina("DEGISMEZ: metin varsa olculemedi bos",
     all(not v["olculemedi"] for v in an.values() if v["metin"] is not None))

# --------------------------------------------------------------------------
print("\n2. KARSILASTIRMA -- eklendi / degisti / silindi")

once = degisim.anlik(proje_kok)
(proje_kok / "a.txt").write_text("bir\nIKI\nuc\n", encoding="utf-8")
(proje_kok / "yeni.md").write_text("selam\n", encoding="utf-8")
(proje_kok / "alt" / "b.py").unlink()
sonra = degisim.anlik(proje_kok)

fark = {k["yol"]: k for k in degisim.karsilastir(once, sonra)}

sina("degisen dosya yakalandi", fark["a.txt"]["hal"] == "degisti")
sina("eklenen dosya yakalandi", fark["yeni.md"]["hal"] == "eklendi")
sina("silinen dosya yakalandi", fark["alt/b.py"]["hal"] == "silindi")
sina("dokunulmayan dosya farkta YOK", "ikili.bin" not in fark)
sina("yama gercek unified diff", "--- a/a.txt" in fark["a.txt"]["yama"]
     and "+IKI" in fark["a.txt"]["yama"])
sina("satir sayaci dogru",
     fark["a.txt"]["eklenen"] == 2 and fark["a.txt"]["silinen"] == 1)

# Icerigi hic okunmamis bir dosyanin yamasini uretmek UYDURMA olurdu.
(proje_kok / "ikili.bin").write_bytes(b"AB\x00CD" + b"q" * 90)
f2 = {k["yol"]: k for k in
      degisim.karsilastir(once, degisim.anlik(proje_kok))}
# YENI EKLENEN ikili/buyuk dosya AYRI bir yoldur: "degisti" dalinda yama
# zaten bos kalir, ama "eklendi" dalinda difflib bos listeyle cagrilir ve
# yama URETILEBILIR. Mutasyon bunu gosterdi: ilk surumde bu sinama yoktu
# ve kapiyi kopardigimda HICBIR sey ates etmedi -- yani test, kapinin
# varligini degil komsu bir dalin davranisini olcuyordu.
o2b = degisim.anlik(proje_kok)
(proje_kok / "yeni.bin").write_bytes(b"XY" + bytes(1) + b"Z" * 40)
(proje_kok / "yeni_buyuk.txt").write_text(
    "y" * (degisim.AZAMI_DOSYA_BAYT + 5), encoding="utf-8")
f2b = {k["yol"]: k for k in
       degisim.karsilastir(o2b, degisim.anlik(proje_kok))}
sina("YENI ikili dosyaya yama UYDURULMUYOR",
     f2b["yeni.bin"]["hal"] == "eklendi" and f2b["yeni.bin"]["yama"] == ""
     and f2b["yeni.bin"]["eklenen"] == 0)
sina("YENI cok buyuk dosyaya yama UYDURULMUYOR",
     f2b["yeni_buyuk.txt"]["yama"] == ""
     and "cok buyuk" in f2b["yeni_buyuk.txt"]["olculemedi"])

sina("ikili degisti ama YAMA YOK",
     f2["ikili.bin"]["hal"] == "degisti" and f2["ikili.bin"]["yama"] == ""
     and f2["ikili.bin"]["olculemedi"] == "ikili dosya")

# --------------------------------------------------------------------------
print("\n3. UZUN YAMA -- kesilir ama KESILDIGINI SOYLER")

(proje_kok / "uzun.txt").write_text("", encoding="utf-8")
o3 = degisim.anlik(proje_kok)
(proje_kok / "uzun.txt").write_text(
    "".join(f"satir {i}\n" for i in range(degisim.AZAMI_YAMA_SATIR + 200)),
    encoding="utf-8")
k3 = {k["yol"]: k for k in degisim.karsilastir(o3, degisim.anlik(proje_kok))}
sina("uzun yama kesildi", "kesildi" in k3["uzun.txt"]["yama"])
# Sayac KESILMEDEN once sayilir: kesilmis yamadan sayarsak "kac satir
# degisti" sorusu yanlis cevaplanir ve kirpma gorunmez hale gelir.
sina("satir sayaci kirpmadan ETKILENMEZ",
     k3["uzun.txt"]["eklenen"] >= degisim.AZAMI_YAMA_SATIR + 200)

# --------------------------------------------------------------------------
print("\n4. BEYAN DENETIMI -- kilit bir BEYANDIR, gercekle sinanir")

sina("beyan icindeki dosya temiz",
     degisim.beyan_disi_mi("api/odeme.py", ["api"]) is False)
sina("beyan disindaki dosya isaretlenir",
     degisim.beyan_disi_mi("web/panel.js", ["api"]) is True)
sina("tam esleme de beyan icidir",
     degisim.beyan_disi_mi("KILAVUZ.md", ["KILAVUZ.md"]) is False)
# Beyan BOSSA denetim yapilmaz: yazma alani olmayan is (triyaj,
# arastirma) hicbir sey beyan etmemistir. Her dosyasina "sorun" demek,
# her seye sorun diyen gosterge olurdu -- ona insan bakmayi birakir.
sina("beyan bossa denetim YOK",
     degisim.beyan_disi_mi("her/yer.txt", []) is False)

o4 = degisim.anlik(proje_kok)
(proje_kok / "disarida.txt").write_text("kacak\n", encoding="utf-8")
k4 = {k["yol"]: k for k in
      degisim.karsilastir(o4, degisim.anlik(proje_kok), beyan=["api"])}
sina("karsilastirma beyan_disi tasiyor", k4["disarida.txt"]["beyan_disi"])

# --------------------------------------------------------------------------
print("\n5. PARALEL TUR -- atif belirsizse SUCLAMA YOK")

k5 = {k["yol"]: k for k in
      degisim.karsilastir(o4, degisim.anlik(proje_kok), beyan=["api"],
                          atif_belirsiz=True)}
sina("paralelde beyan_disi BASTIRILIR",
     k5["disarida.txt"]["beyan_disi"] is False)
# Ama fark YINE kaydedilir: diskte gercekten olan sey odur. Bastirilan
# sey suclama, olcum degil.
sina("paralelde fark yine kaydedilir", k5["disarida.txt"]["hal"] == "eklendi")
sina("belirsizlik gorunur kalir", k5["disarida.txt"]["atif_belirsiz"] is True)

# --------------------------------------------------------------------------
print("\n6. OZET ve KAPSAM NOTU")

o = degisim.ozet(list(k4.values()))
sina("ozet dosya sayar", o["dosya"] == len(k4))
sina("ozet beyan disini sayar", o["beyan_disi"] == 1)
sina("kapsam notu bos klasorde SESSIZ", degisim.kapsam_notu([]) == "")
sina("kapsam notu dis klasoru SOYLER",
     "C:/proje" in degisim.kapsam_notu(["C:/proje"]))

# --------------------------------------------------------------------------
print("\n7. DEFTER -- yazilir, okunur, en yenisi ustte")

db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Degisim Projesi", amac="Diski olcmek",
                     basari_olcutu="Fark deftere dusuyor",
                     kok_klasor=str(proje_kok))
kanat = ofis.kanat_ac("URUN", "UR")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(proje_kok), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", klasor=str(proje_kok), motor="sahte")

g = ofis.tahta.gorev_ac("Olcum isi", neden="Test", ana_hedef="Fark olculsun",
                        kabul_olcutu="Defterde kayit var",
                        yazma_alani=["api"], kanat_id=kanat)

n = degisim.yaz(db, ofis.proje_id, g["id"], "cinar", list(k4.values()))
sina("kayitlar yazildi", n == len(k4))
okunan = degisim.oku(db, ofis.proje_id)
sina("defterden okunuyor", len(okunan) == len(k4))
sina("beyan_disi defterde korundu",
     any(r["beyan_disi"] and r["yol"] == "disarida.txt" for r in okunan))
sina("gorev suzgeci calisiyor",
     len(degisim.oku(db, ofis.proje_id, gorev_id=g["id"])) == len(k4))
sina("baska gorev bos doner",
     degisim.oku(db, ofis.proje_id, gorev_id="yok") == [])
sina("bos kayit listesi yazmaz",
     degisim.yaz(db, ofis.proje_id, g["id"], "cinar", []) == 0)


# --------------------------------------------------------------------------
print("\n8. UCTAN UCA -- koltuk gercekten olcuyor mu")
#
# Modulun var olmasi bir baglanti DEGILDIR. `video.py` tam bu yuzden
# aylarca ajana ulasmiyordu: yazilmisti, cagrilmiyordu. O yuzden burada
# sinanan sey `degisim.py` degil, KOLTUGUN onu cagirdigi.

class YazanMotor(SahteMotor):
    """Tur sirasinda gercekten dosya yazan sahte motor."""

    def __init__(self, hedefler, **ayar):
        super().__init__(**ayar)
        self.hedefler = hedefler

    def tur_kos(self, metin, **ayar):
        for yol, icerik in self.hedefler:
            p = proje_kok / yol
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(icerik, encoding="utf-8")
        return super().tur_kos(metin, **ayar)


kutu = {"hedefler": [("api/odeme.py", "def ode():\n    return 1\n")],
        "senaryo": "basarili"}


def fabrika(ad, **ayar):
    return YazanMotor(kutu["hedefler"], senaryo=kutu["senaryo"],
                      cevap="Bitti.\nKANIT dosya: api/odeme.py -> yazildi")


koltuk = Koltuk(ofis, motor_fabrikasi=fabrika)

g8 = ofis.tahta.gorev_ac("Odeme yaz", neden="Test", ana_hedef="Dosya yazilsin",
                         kabul_olcutu="api/odeme.py var",
                         yazma_alani=["api"], kanat_id=kanat)
olaylar = list(koltuk.akit(g8["no"], "cinar"))
turler = [o["tur"] for o in olaylar]
kayit8 = degisim.oku(db, ofis.proje_id, gorev_id=g8["id"])

sina("koltuk degisim olayi akitti", "degisim" in turler)
sina("yazilan dosya deftere dustu",
     any(r["yol"] == "api/odeme.py" and r["hal"] == "eklendi"
         for r in kayit8))
sina("beyan ICINDE yazildi -- suclama YOK",
     all(not r["beyan_disi"] for r in kayit8))
# Ters yon: her seye "beyan disi" diyen bir kod da testi gecerdi.
sina("temiz turda uyari YOK",
     not any(o["tur"] == "uyari" and "DISINA" in o["govde"] for o in olaylar))
# Ofisin kendi yazdigi BRIFING.md farkta GORUNMEMELI: anlik goruntu
# brifingden SONRA alinir, yoksa her turun farki ofisin kendi dosyasini
# ajanin isi gibi gosterirdi.
sina("BRIFING.md farka karismadi",
     not any(r["yol"].endswith("BRIFING.md") for r in kayit8))

# --------------------------------------------------------------------------
ofis.tahta.iptal_et(g8["no"], sebep="Olcum bitti", iptal_eden="demir")

print("\n9. BEYAN DISI YAZMA -- gercek turda yakalaniyor mu")

kutu["hedefler"] = [("web/panel.js", "// kacak yazma\n")]
g9 = ofis.tahta.gorev_ac("Baska yere yaz", neden="Test",
                         ana_hedef="Beyan disi yakalansin",
                         kabul_olcutu="Uyari cikiyor",
                         yazma_alani=["api"], kanat_id=kanat)
olaylar9 = list(koltuk.akit(g9["no"], "cinar"))
kayit9 = degisim.oku(db, ofis.proje_id, gorev_id=g9["id"])

sina("beyan disi kayit dustu",
     any(r["yol"] == "web/panel.js" and r["beyan_disi"] for r in kayit9))
sina("gorunur uyari uretildi",
     any(o["tur"] == "uyari" and "DISINA" in o["govde"] for o in olaylar9))
# Is DURDURULMAZ: kilit bir beyandir ve beyan disina yazmak 18.09'da
# kabul edilmis bir bedeldi. Burada yapilan ilk kez OLCMEK; kesmek,
# bugune kadar sessizce olan bir seyi bir anda kirmak olurdu.
sina("is DURDURULMADI, yalnizca gorunur oldu",
     any(o["tur"] == "tur_bitti" and o["ek"].get("basarili")
         for o in olaylar9))

# --------------------------------------------------------------------------
ofis.tahta.iptal_et(g9["no"], sebep="Olcum bitti", iptal_eden="demir")

print("\n10. BASARISIZ TUR DA OLCULUR")
#
# "Is bitmedi" ile "hicbir sey degismedi" AYRI iki seydir. Ikincisini
# varsaymak, diskte duran bir degisikligi gorunmez kilardi.

kutu["hedefler"] = [("api/yarim.py", "# yarim kalan is\n")]
kutu["senaryo"] = "hata"
g10 = ofis.tahta.gorev_ac("Yarim is", neden="Test", ana_hedef="Dussun",
                          kabul_olcutu="Olculsun", yazma_alani=["api"],
                          kanat_id=kanat)
olaylar10 = list(koltuk.akit(g10["no"], "cinar"))
kayit10 = degisim.oku(db, ofis.proje_id, gorev_id=g10["id"])
kutu["senaryo"] = "basarili"

sina("tur gercekten basarisiz",
     any(o["tur"] == "tur_bitti" and not o["ek"].get("basarili")
         for o in olaylar10))
sina("basarisiz turun yazdigi dosya YINE olculdu",
     any(r["yol"] == "api/yarim.py" for r in kayit10))

# --------------------------------------------------------------------------
print("\n11. PANEL UCU -- veri istemciye ulasiyor mu")

from fastapi.testclient import TestClient      # noqa: E402
from ofis import panel as panel_modulu          # noqa: E402

istemci = TestClient(panel_modulu.olustur(db.yol, "Degisim Projesi"))
y = istemci.get("/api/degisim").json()

sina("uc kok bildiriyor", y["kok"].replace("\\", "/").endswith("calisma"))
sina("uc kayit donduruyor", len(y["kayitlar"]) > 0)
ilk = y["kayitlar"][0]
sina("satirda gorev no var", ilk.get("gorev_no") is not None)
sina("satirda kanat var", bool(ilk.get("kanat_id")))
sina("beyan_disi bool olarak geliyor", isinstance(ilk["beyan_disi"], bool))
sina("kapsam notu alani var", "kapsam_notu" in ilk)
sina("gorev suzgeci ucta calisiyor",
     all(r["gorev_no"] == g9["no"] for r in
         istemci.get(f"/api/degisim?gorev_no={g9['no']}").json()["kayitlar"]))
# En yenisi ustte: `simdi()` saniye cozunurluklu, ayni turda yazilan
# dosyalar ayni damgayi tasir. rowid ile beraberlik bozulmasaydi
# "once sunu, sonra sunu degistirdi" okumasi yalan olurdu.
sina("en yeni kayit ustte",
     y["kayitlar"][0]["olusturuldu"] >= y["kayitlar"][-1]["olusturuldu"])

# --------------------------------------------------------------------------
# SESSIZCE YAVASLAMAK YOK: esik dusurulunce uyari CIKMALI, normalde
# CIKMAMALI. Yalnizca birini sinasaydik "hep uyaran" ya da "hic
# uyarmayan" bir kod da testi gecerdi.
_esik = degisim.YAVAS_ESIK_SN
degisim.YAVAS_ESIK_SN = -1.0
gy = ofis.tahta.gorev_ac("Yavaslik sinamasi", neden="Test",
                         ana_hedef="Uyari ciksin", kabul_olcutu="Uyari",
                         yazma_alani=["api"], kanat_id=kanat)
kutu["hedefler"] = [("api/hiz.py", "x = 1" + chr(10))]
olaylar_y = list(koltuk.akit(gy["no"], "cinar"))
degisim.YAVAS_ESIK_SN = _esik
ofis.tahta.iptal_et(gy["no"], sebep="sahne", iptal_eden="demir")
sina("esik asilinca GORUNUR uyari",
     any(o["tur"] == "uyari" and "olcumu yavas" in o["govde"]
         for o in olaylar_y))

gy2 = ofis.tahta.gorev_ac("Normal hiz", neden="Test",
                          ana_hedef="Uyari cikmasin", kabul_olcutu="Sessiz",
                          yazma_alani=["api"], kanat_id=kanat)
kutu["hedefler"] = [("api/hiz2.py", "y = 2" + chr(10))]
olaylar_n = list(koltuk.akit(gy2["no"], "cinar"))
ofis.tahta.iptal_et(gy2["no"], sebep="sahne", iptal_eden="demir")
sina("normal hizda SESSIZ",
     not any(o["tur"] == "uyari" and "olcumu yavas" in o["govde"]
             for o in olaylar_n))

print("\n12. INCELEME METNI -- kapinin elinde artik OLCUM var")
#
# Kapi, kendisine verilen olcutten iyi olamaz -- ama elindeki OLCUDEN de
# iyi olamaz. Gercek ofiste 16 `diff` KANITI vardi ve hepsi ajanin kendi
# anlatisiydi; lider karsilastiracagi bagimsiz bir olcume sahip degildi.

from ofis import Lider                                    # noqa: E402

lider = Lider(ofis, motor_fabrikasi=fabrika)
metin9 = lider.inceleme_metni(g9["no"])

sina("inceleme metninde OLCUM bolumu var", "Diskte OLCULEN" in metin9)
sina("olculen dosya adiyla geciyor", "web/panel.js" in metin9)
sina("BEYAN DISI lidere SOYLENIYOR", "BEYAN DISI" in metin9)
sina("lidere ne yapacagi soyleniyor",
     "hukmunde ANMADAN gecme" in metin9)
# TERS YON: dosya degistirmeyen bir iste bolum HIC cikmamali.
# "Hicbir sey degismedi" demek, olcmedigimiz bir seye hukum vermektir --
# arastirma/inceleme isleri zaten dosya yazmaz.
gbos = ofis.tahta.gorev_ac("Dosyasiz is", neden="Test",
                           ana_hedef="Olcum bolumu cikmasin",
                           kabul_olcutu="Bos", yazma_alani=[],
                           kanat_id=kanat)
sina("olcum yoksa bolum HIC yazilmiyor",
     "Diskte OLCULEN" not in lider.inceleme_metni(gbos["no"]))

# --------------------------------------------------------------------------
print("\n13. CANLI IZLEME -- izleyici (sahte saat)")
#
# Kaynak DISK: `arac` olayinin govdesi yalniz arac adini tasiyor
# (olculdu), hangi dosyaya dokunuldugu defterde yok. Izleyici tur
# ONCESI anlik goruntuye gore olcer -- bir onceki taramaya gore degil.

import os as _os
import time as _time

ck = Path(tempfile.mkdtemp(prefix="ofis-canli-"))
(ck / "eski.py").write_text("a = 1\n", encoding="utf-8")
(ck / "sabit.py").write_text("s = 1\n", encoding="utf-8")
_saat = [100.0]
iz = degisim.CanliIzleyici(ck, degisim.anlik(ck), beyan=["api"],
                           aralik=2.0, saat=lambda: _saat[0])

sina("zamani gelmeden TARAMA YOK", iz.belki_tara() is None)
sina("  zamani_mi da hayir diyor", not iz.zamani_mi())

(ck / "api").mkdir()
(ck / "api" / "yeni.py").write_text("x = 1\n", encoding="utf-8")
_saat[0] += 2.0
r1 = iz.belki_tara()
sina("yeni dosya OLCULDU", r1 and [k["yol"] for k in r1["degisen"]]
     == ["api/yeni.py"], str(r1))
sina("  hal 'eklendi', +1", r1 and r1["degisen"][0]["hal"] == "eklendi"
     and r1["degisen"][0]["eklenen"] == 1)
sina("  ILK dokunus olarak isaretlendi", r1 and r1["yeni"] == ["api/yeni.py"])
sina("  beyan icinde -- suclama yok",
     r1 and not r1["degisen"][0]["beyan_disi"])

# Ikinci duzenleme: fark ONCE'ye gore birikir (+2), ilk dokunus DEGIL.
_p = ck / "api" / "yeni.py"
_p.write_text("x = 1\ny = 2\n", encoding="utf-8")
_os.utime(_p, ns=(_time.time_ns(), _time.time_ns() + 10**9))
_saat[0] += 2.0
r2 = iz.belki_tara()
sina("ikinci duzenleme yine olculdu, fark BIRIKIMLI (+2)",
     r2 and r2["degisen"] and r2["degisen"][0]["eklenen"] == 2, str(r2))
sina("  ilk dokunus DEGIL (defter buyumez)", r2 and r2["yeni"] == [])

# Yalniz zaman damgasi: icerik ayni -> kayit yok.
_os.utime(_p, ns=(_time.time_ns(), _time.time_ns() + 3 * 10**9))
_saat[0] += 2.0
r3 = iz.belki_tara()
sina("yalniz zaman damgasi degisti -> degisen YOK",
     r3 is not None and r3["degisen"] == [], str(r3))

# Beyan disi + atif belirsiz aynen tasinir.
(ck / "web.js").write_text("// kacak\n", encoding="utf-8")
_saat[0] += 2.0
r4 = iz.belki_tara()
sina("beyan DISI canli olcumde de isaretleniyor",
     r4 and r4["degisen"] and r4["degisen"][0]["beyan_disi"], str(r4))
(ck / "web.js").write_text("// kacak 2\n", encoding="utf-8")
_os.utime(ck / "web.js", ns=(_time.time_ns(), _time.time_ns() + 5 * 10**9))
_saat[0] += 2.0
r4b = iz.belki_tara(atif_belirsiz=True)
sina("paralel turda suclama BASTIRILIYOR",
     r4b and r4b["degisen"] and not r4b["degisen"][0]["beyan_disi"]
     and r4b["degisen"][0]["atif_belirsiz"], str(r4b))

# Once haline donen dosya canli listeden KALKAR.
(ck / "eski.py").write_text("a = 2\n", encoding="utf-8")
_saat[0] += 2.0
iz.belki_tara()
(ck / "eski.py").write_text("a = 1\n", encoding="utf-8")
_os.utime(ck / "eski.py", ns=(_time.time_ns(), _time.time_ns() + 7 * 10**9))
_saat[0] += 2.0
r5 = iz.belki_tara()
sina("once haline DONEN dosya kalkiyor", r5 and r5["kalkan"] == ["eski.py"],
     str(r5))

# Tur icinde acilip silinen dosya iz birakmaz.
(ck / "gecici.txt").write_text("g\n", encoding="utf-8")
_saat[0] += 2.0
iz.belki_tara()
(ck / "gecici.txt").unlink()
_saat[0] += 2.0
r6 = iz.belki_tara()
sina("acilip SILINEN dosya kalkiyor", r6 and r6["kalkan"] == ["gecici.txt"],
     str(r6))

# Once VAR olan dosya silindi -> 'silindi'.
(ck / "sabit.py").unlink()
_saat[0] += 2.0
r7 = iz.belki_tara()
sina("once var olan dosyanin SILINMESI olculdu",
     r7 and r7["degisen"] and r7["degisen"][0]["hal"] == "silindi", str(r7))

# Tarama basina SINIR: kalanlar KAYBOLMAZ, sonraki taramaya kalir.
ck2 = Path(tempfile.mkdtemp(prefix="ofis-canli2-"))
iz2 = degisim.CanliIzleyici(ck2, {}, aralik=0, azami_dosya=2,
                            saat=lambda: _saat[0])
for _i in range(5):
    (ck2 / f"d{_i}.txt").write_text(str(_i) + "\n", encoding="utf-8")
_goren = []
_turlar = []
for _ in range(4):
    _r = iz2.belki_tara()
    _turlar.append(len(_r["degisen"]))
    _goren += [k["yol"] for k in _r["degisen"]]
sina("tarama basina en fazla 2 dosya okunuyor", max(_turlar) <= 2,
     str(_turlar))
sina("  kalanlar KAYBOLMADI (5 dosyanin 5'i goruldu)",
     sorted(_goren) == [f"d{_i}.txt" for _i in range(5)], str(_goren))

# Buyuk dosya: icerik degil ozet; yama UYDURULMAZ ve sebep soylenir.
iz3 = degisim.CanliIzleyici(ck2, degisim.anlik(ck2), aralik=0,
                            azami_bayt=10, saat=lambda: _saat[0])
(ck2 / "buyuk.txt").write_text("x" * 50 + "\n", encoding="utf-8")
_r = iz3.belki_tara()
_b = [k for k in _r["degisen"] if k["yol"] == "buyuk.txt"]
sina("canli sinirin ustundeki dosya 'cok buyuk' der, yama yok",
     _b and "cok buyuk" in _b[0]["olculemedi"] and _b[0]["yama"] == "",
     str(_b))

# AYNI TIK YARISI (olculdu, 24.09.2026): Windows'ta damga kaba artiyor;
# ayni tikte yapilan, boyutu degistirmeyen yazma damga+boyut taramasina
# gorunmez. Sinama bir kosuda tam bu yuzden kaldi. Burada o hal ZORLA
# kuruluyor: icerik degisiyor, damga ve boyut AYNI birakiliyor.
(ck2 / "yaris.txt").write_text("aaaa\n", encoding="utf-8")
iz5 = degisim.CanliIzleyici(ck2, degisim.anlik(ck2), aralik=0,
                            saat=lambda: _saat[0])
_m0 = (ck2 / "yaris.txt").stat().st_mtime_ns
(ck2 / "yaris.txt").write_text("bbbb\n", encoding="utf-8")
_os.utime(ck2 / "yaris.txt", ns=(_m0, _m0))
_r5 = iz5.belki_tara()
sina("ayni tikte, ayni boyutta yazma da GORULUYOR (yaris payi)",
     any(k["yol"] == "yaris.txt" for k in _r5["degisen"]), str(_r5))
_r5b = iz5.belki_tara()
sina("  ayni icerik ikinci kez RAPORLANMIYOR",
     not any(k["yol"] == "yaris.txt" for k in _r5b["degisen"]), str(_r5b))

# YAVAS tarama canli izlemeyi o tur icin KAPATIR -- ve sebep soylenir.
iz4 = degisim.CanliIzleyici(ck2, {}, aralik=0, yavas_sn=-1,
                            saat=lambda: _saat[0])
iz4.belki_tara()
sina("yavas tarama izlemeyi KAPATTI, sebep yazili",
     "KAPATILDI" in iz4.kapali, iz4.kapali)
sina("  kapaliyken bir daha taramiyor", iz4.belki_tara(zorla=True) is None)

# Ayni gezinti kurallari: `anlik`in atladigini canli da atlar.
(ck2 / "__pycache__").mkdir()
(ck2 / "__pycache__" / "x.pyc").write_bytes(b"\x00")
(ck2 / "node_modules").mkdir()
(ck2 / "node_modules" / "p.js").write_text("1\n", encoding="utf-8")
_tara = degisim.tarama(ck2)
sina("canli tarama anlik ile AYNI klasorleri atliyor",
     not any(y.startswith(("__pycache__", "node_modules")) for y in _tara)
     and set(_tara) == set(degisim.anlik(ck2)), str(sorted(_tara)))
# 01.10 (G17): yardimci betiklerin yeri `karalama/`; ofis orayi olcmez.
(ck2 / "karalama").mkdir()
(ck2 / "karalama" / "yap.py").write_text("1\n", encoding="utf-8")
sina("karalama/ olculmuyor (yardimci betik beyan disi sayilmaz)",
     not any(y.startswith("karalama") for y in degisim.tarama(ck2))
     and not any(y.startswith("karalama") for y in degisim.anlik(ck2)))

# --------------------------------------------------------------------------
print("\n14. CANLI DEFTER -- tek satir, kosan is, temizlik")

g13 = ofis.tahta.gorev_ac("Canli defter", neden="Test", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["api"],
                          kanat_id=kanat)
_k = {"yol": "api/a.py", "hal": "eklendi", "beyan_disi": False,
      "eklenen": 1, "silinen": 0, "yama": "+a\n", "olculemedi": ""}
degisim.canli_yaz(db, ofis.proje_id, g13["id"], "cinar", [_k])
degisim.canli_yaz(db, ofis.proje_id, g13["id"], "cinar",
                  [dict(_k, eklenen=3)])
with db.baglanti() as _c:
    _n = _c.execute("SELECT COUNT(*) FROM canli_degisim WHERE gorev_id=?",
                    (g13["id"],)).fetchone()[0]
    _e = _c.execute("SELECT eklenen FROM canli_degisim WHERE gorev_id=?",
                    (g13["id"],)).fetchone()[0]
sina("(gorev, yol) basina TEK satir -- guncelleniyor", _n == 1 and _e == 3,
     f"{_n} satir, eklenen {_e}")
sina("hazir (kosmayan) isin canli kaydi GOSTERILMIYOR",
     not any(r["gorev_id"] == g13["id"]
             for r in degisim.canli_oku(db, ofis.proje_id)))
ofis.tahta.sahiplen(g13["no"], "cinar", g13["revizyon"])
sina("kosan isin canli kaydi gosteriliyor",
     any(r["gorev_id"] == g13["id"]
         for r in degisim.canli_oku(db, ofis.proje_id)))
degisim.canli_yaz(db, ofis.proje_id, g13["id"], "cinar", [],
                  kalkan=["api/a.py"])
sina("kalkan dosya siliniyor",
     not degisim.canli_oku(db, ofis.proje_id))
degisim.canli_yaz(db, ofis.proje_id, g13["id"], "cinar", [_k])
sina("canli_sil gorevin kaydini temizliyor",
     degisim.canli_sil(db, ofis.proje_id, g13["id"]) == 1
     and not degisim.canli_oku(db, ofis.proje_id))
ofis.tahta.iptal_et(g13["no"], sebep="Olcum bitti", iptal_eden="demir")
# Gecici klasorler SILINIR: sinama artiklari bir kez diski doldurdu.
import shutil as _sh
_sh.rmtree(ck, ignore_errors=True)
_sh.rmtree(ck2, ignore_errors=True)

# --------------------------------------------------------------------------
print("\n15. CANLI IZLEME -- koltuk TUR SURERKEN yaziyor mu")
#
# Modulun var olmasi bir baglanti degildir. Burada sinanan: koltuk tur
# ORTASINDA taramayi cagiriyor mu, tur bitince ara kaydi siliyor mu,
# ve onceki bir surecin artigini tur basinda temizliyor mu.

from ofis.motor.tip import MotorOlayi as _MO

_eski_aralik = degisim.CANLI_ARALIK_S
degisim.CANLI_ARALIK_S = 0.0
_gozlem = []


class CanliYazan(SahteMotor):
    def tur_kos(self, metin, **ayar):
        _gozlem.append(("bas", [r["yol"] for r in
                                degisim.canli_oku(db, ofis.proje_id)]))
        _a = proje_kok / "api" / "canli.py"
        _a.parent.mkdir(parents=True, exist_ok=True)
        _a.write_text("v = 1\n", encoding="utf-8")
        yield _MO("nabiz", "")
        yield _MO("nabiz", "")
        _gozlem.append(("a", [(r["yol"], r["eklenen"]) for r in
                              degisim.canli_oku(db, ofis.proje_id)]))
        _a.write_text("v = 1\nw = 2\n", encoding="utf-8")
        _os.utime(_a, ns=(_time.time_ns(), _time.time_ns() + 10**9))
        (proje_kok / "api" / "ikinci.py").write_text("z\n", encoding="utf-8")
        yield _MO("nabiz", "")
        yield _MO("nabiz", "")
        _gozlem.append(("b", [(r["yol"], r["eklenen"]) for r in
                              degisim.canli_oku(db, ofis.proje_id)]))
        # Ayni dosya TEK BASINA bir kez daha: defter buyumemeli.
        _a.write_text("v = 1\nw = 2\nq = 3\n", encoding="utf-8")
        _os.utime(_a, ns=(_time.time_ns(), _time.time_ns() + 3 * 10**9))
        yield _MO("nabiz", "")
        yield _MO("nabiz", "")
        _gozlem.append(("c", [(r["yol"], r["eklenen"]) for r in
                              degisim.canli_oku(db, ofis.proje_id)]))
        yield from super().tur_kos(metin, **ayar)


koltuk14 = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: CanliYazan(
    senaryo="basarili", cevap="Bitti.\nKANIT dosya: api/canli.py -> yazildi"))
g14 = ofis.tahta.gorev_ac("Canli yaz", neden="Test", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["api"],
                          kanat_id=kanat)
# Onceki bir surecin dusup silemedigi ARTIK:
degisim.canli_yaz(db, ofis.proje_id, g14["id"], "cinar",
                  [dict(_k, yol="api/artik.py")])
try:
    ol14 = list(koltuk14.akit(g14["no"], "cinar"))
finally:
    degisim.CANLI_ARALIK_S = _eski_aralik
_g = dict(_gozlem)
sina("tur basinda onceki surecin ARTIGI temizlendi",
     "api/artik.py" not in _g.get("bas", ["api/artik.py"]), str(_g))
sina("tur ORTASINDA yazilan dosya canli kayitta",
     ("api/canli.py", 1) in _g.get("a", []), str(_g.get("a")))
sina("  ikinci duzenleme ayni satiri guncelledi (+2), ikinci dosya geldi",
     ("api/canli.py", 2) in _g.get("b", [])
     and any(y == "api/ikinci.py" for y, _ in _g.get("b", [])),
     str(_g.get("b")))
with db.baglanti() as _c:
    _dc = [r[0] for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='dosya_canli' AND gorev_id=?",
        (g14["id"],)).fetchall()]
sina("  ucuncu duzenleme de izlendi (+3)",
     ("api/canli.py", 3) in _g.get("c", []), str(_g.get("c")))
sina("kayit defterine yalniz ILK dokunus yazildi (2 dosya -> 2 olay)",
     len(_dc) == 2, str(_dc))
with db.baglanti() as _c:
    _kalan = _c.execute("SELECT COUNT(*) FROM canli_degisim WHERE gorev_id=?",
                        (g14["id"],)).fetchone()[0]
sina("tur BITINCE ara kayit silindi", _kalan == 0, str(_kalan))
sina("  yerini KESIN kayit aldi",
     {"api/canli.py", "api/ikinci.py"}
     <= {r["yol"] for r in degisim.oku(db, ofis.proje_id,
                                       gorev_id=g14["id"])})
ofis.tahta.iptal_et(g14["no"], sebep="Olcum bitti", iptal_eden="demir")

# --------------------------------------------------------------------------
print("\n16. OFISIN KENDI DEFTERI olcumden HARIC")
#
# OLCULDU (24.09.2026, gercek haiku turu): defter proje kokunun ICINDE
# oldugunda her tur `o.sqlite3`u "beyan disina yazildi" diye isaretledi.
# Yazan ofisin kendisiydi -- sahte bir suclama.
kok16 = Path(tempfile.mkdtemp(prefix="ofis-degisim16-"))
db16 = Veritabani(kok16 / "o.sqlite3")
o16 = Ofis.proje_ac(db16, "Ic Defter", amac="a", kok_klasor=str(kok16))
k16 = o16.kanat_ac("ANA", "AN")
o16.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=k16,
                 klasor=str(kok16), motor="sahte")
o16.kadro.ise_al("cinar", "backend", klasor=str(kok16), motor="sahte",
                 kanat_id=k16)


class YazanMotor16(SahteMotor):
    def tur_kos(self, metin, **ayar):
        (kok16 / "rapor.md").write_text("port 8123\n", encoding="utf-8")
        return super().tur_kos(metin, **ayar)


kt16 = Koltuk(o16, motor_fabrikasi=lambda ad, **a: YazanMotor16(
    senaryo="basarili", cevap="Bitti.\nKANIT dosya: rapor.md -> yazildi"))
g16 = o16.tahta.gorev_ac("Rapor", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["rapor.md"], kanat_id=k16)
ol16 = list(kt16.akit(g16["no"], "cinar"))
yol16 = {r["yol"] for r in degisim.oku(db16, o16.proje_id, gorev_id=g16["id"])}
sina("ajanin dosyasi olculdu", "rapor.md" in yol16, str(yol16))
sina("ofisin KENDI defteri farkta YOK (sahte suclama yok)",
     not any(y.startswith("o.sqlite3") for y in yol16), str(yol16))
sina("  'beyan disi' uyarisi CIKMADI",
     not any(o["tur"] == "uyari" and "DISINA" in o["govde"] for o in ol16))
sina("ofis_dosyalari yan dosyalari da kapsiyor",
     set(degisim.ofis_dosyalari("x.db")) == {"x.db", "x.db-wal", "x.db-shm",
                                               "x.db-journal"})
import shutil as _sh16
_sh16.rmtree(kok16, ignore_errors=True)

# --------------------------------------------------------------------------
print("\nPENCERE -- komsu tur BU TURUN ICINDE bitirdiyse suclama YOK")
# Olculdu (26.09.2026, deneme D11): isci2'nin turu surerken oteki iki isci
# yazip BITIRDI; tur sonunda "baska is calisiyor mu" sorusu HAYIR dedi,
# fark komsularin dosyalarini isci2'ye yazdi, lider isi haksiz geri
# gonderdi. Sahne: A'nin turu icinde B dosya yazar ve tur_ozeti'ni yazar.
_kp = Path(tempfile.mkdtemp(prefix="ofis-pencere-"))
_op = Ofis.proje_ac(Veritabani(_kp / "o.sqlite3"), "Pencere", amac="a",
                    basari_olcutu="b", kok_klasor=str(_kp))
_knp = _op.kanat_ac("U", "U")
_op.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=_knp, klasor=str(_kp),
                 motor="sahte")
_op.kadro.ise_al("cinar", "backend", klasor=str(_kp), motor="sahte")
_op.kadro.ise_al("bilge", "backend", klasor=str(_kp), motor="sahte")


class _KomsuYazan(SahteMotor):
    def tur_kos(self, metin, **ayar):
        (_kp / "a.py").write_text("x = 1\n", encoding="utf-8")        # A'nin kendi isi
        (_kp / "komsu.py").write_text("y = 2\n", encoding="utf-8")    # B'nin isi
        _op.db.olay_yaz(_op.proje_id, "tur_ozeti", "{}", ajan_ad="bilge")
        return super().tur_kos(metin, **ayar)


_ga = _op.tahta.gorev_ac("A", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["a.py"], kanat_id=_knp)
list(Koltuk(_op, motor_fabrikasi=lambda ad, **a: _KomsuYazan(
    cevap="ok\nKANIT dosya: a.py -> x")).akit(_ga["no"], "cinar"))
_kay = {r["yol"]: r for r in degisim.oku(_op.db, _op.proje_id, gorev_id=_ga["id"])}
sina("komsunun dosyasi farkta var (olcum dogru)", "komsu.py" in _kay)
sina("ama BEYAN DISI suclamasi YOK", not _kay.get("komsu.py", {}).get("beyan_disi"),
     str(_kay.get("komsu.py")))
sina("atif belirsiz isaretli", bool(_kay.get("komsu.py", {}).get("atif_belirsiz")))

# Ters yon: komsu YOKKEN ayni yazma yine YAKALANIR (kapi gevsemedi).
_gb = _op.tahta.gorev_ac("B", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["b.py"], kanat_id=_knp)


class _TekYazan(SahteMotor):
    def tur_kos(self, metin, **ayar):
        (_kp / "b.py").write_text("b = 1\n", encoding="utf-8")
        (_kp / "kacak.py").write_text("k = 1\n", encoding="utf-8")
        return super().tur_kos(metin, **ayar)


list(Koltuk(_op, motor_fabrikasi=lambda ad, **a: _TekYazan(
    cevap="ok\nKANIT dosya: b.py -> x")).akit(_gb["no"], "cinar"))
_kb = {r["yol"]: r for r in degisim.oku(_op.db, _op.proje_id, gorev_id=_gb["id"])}
sina("komsu YOKKEN beyan disi yazma YINE yakalaniyor",
     bool(_kb.get("kacak.py", {}).get("beyan_disi")), str(_kb.get("kacak.py")))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
