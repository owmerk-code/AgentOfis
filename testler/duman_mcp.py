# -*- coding: utf-8 -*-
"""Ofis MCP sunucusu duman testi.

Iki katmanda sinanir:

1. **Protokol** -- sunucu AYRI BIR SUREC olarak baslatilip stdio uzerinden
   gercek JSON-RPC konusulur. Islevleri dogrudan cagirmak yetmez: sunucu
   CLI tarafindan boyle calistirilacak ve protokol hatasi ancak boyle
   yakalanir.
2. **Kapilar** -- gerekcesiz karar, kanitsiz iddia, iscinin gorev acmaya
   calismasi, kimlik sahtekarligi.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.mcp_sunucu import yapilandirma, SUNUCU_ADI

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


class Sunucu:
    """Sunucuyu ayri surec olarak baslatip gercek JSON-RPC konusur."""

    def __init__(self, ortam: dict) -> None:
        cevre = os.environ.copy()
        cevre.update(ortam)
        self.p = subprocess.Popen(
            [sys.executable,
             str(Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1, env=cevre,
        )
        self.sayac = 0

    def _yolla(self, paket: dict) -> None:
        self.p.stdin.write(json.dumps(paket, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def bildir(self, yontem: str, parametre: dict = None) -> None:
        """Bildirimin `id`si YOKTUR ve yaniti BEKLENMEZ.

        Bu ayrimi kacirmak sessiz bir kilitlenme uretir: id gonderip yanit
        beklersin, sunucu bildirime yanit vermez, iki taraf da birbirini
        bekler. Testin ilk surumu tam bu tuzaga dustu.
        """
        paket = {"jsonrpc": "2.0", "method": yontem}
        if parametre is not None:
            paket["params"] = parametre
        self._yolla(paket)

    def cagir(self, yontem: str, parametre: dict = None):
        self.sayac += 1
        istek = {"jsonrpc": "2.0", "id": self.sayac, "method": yontem}
        if parametre is not None:
            istek["params"] = parametre
        self._yolla(istek)
        satir = self.p.stdout.readline()
        if not satir.strip():
            raise RuntimeError(
                "Sunucu yanit vermeden kapandi. stderr:\n"
                + (self.p.stderr.read() or "")[:2000])
        return json.loads(satir)

    def arac(self, ad: str, **argumanlar) -> str:
        y = self.cagir("tools/call", {"name": ad, "arguments": argumanlar})
        return y["result"]["content"][0]["text"]

    def hatali_mi(self, ad: str, **argumanlar) -> bool:
        y = self.cagir("tools/call", {"name": ad, "arguments": argumanlar})
        return bool(y["result"].get("isError"))

    def kapat(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


print("== ofis MCP sunucusu duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-mcp-"))
db_yolu = kok / "ofis.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "MCP Projesi", amac="Araclari sinamak",
                     basari_olcutu="Kapilar kapali")
kanat = ofis.kanat_ac("URUN", "UR")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(kok / "demir"), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", klasor=str(kok / "cinar"), motor="sahte")
ofis.bellek.olgu_yaz("iade suresi", "30 gun", kaynak="insan")

g = ofis.tahta.gorev_ac("API yaz", neden="Siparis alinamiyor",
                        ana_hedef="Magaza canliya cikacak",
                        kabul_olcutu="pytest yesil",
                        yazma_alani=["api/"], kanat_id=kanat)
ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])

# --------------------------------------------------------------------------
print("1. PROTOKOL -- gercek surec, gercek JSON-RPC")
s = Sunucu({"OFIS_DB": str(db_yolu), "OFIS_PROJE": ofis.proje_id,
            "OFIS_AJAN": "cinar", "OFIS_GOREV": str(g["no"])})

y = s.cagir("initialize", {"protocolVersion": "2025-06-18",
                           "capabilities": {},
                           "clientInfo": {"name": "test", "version": "1"}})
sina("initialize yanit veriyor", y is not None and "result" in y)
sina("sunucu adini bildiriyor",
     y["result"]["serverInfo"]["name"] == SUNUCU_ADI)
sina("arac yetenegini bildiriyor", "tools" in y["result"]["capabilities"])
sina("istemcinin protokol surumunu yansitiyor",
     y["result"]["protocolVersion"] == "2025-06-18")

s.bildir("notifications/initialized", {})
sina("initialized bildiriminden sonra sunucu AYAKTA",
     "result" in s.cagir("ping"))

y = s.cagir("tools/list")
adlar = [a["name"] for a in y["result"]["tools"]]
sina("on bes arac yayinlaniyor (giris_iste, sohbete_yaz dahil)", len(adlar) == 15 and "giris_iste" in adlar and "sohbete_yaz" in adlar, f"-- {adlar}")
# `izin_sor` ajanin cagirdigi bir arac DEGIL: CLI'in izin
# kancasi. Yine de yayinlanmak ZORUNDA -- CLI onu ada gore
# arar ve bulamazsa izin gerektiren her cagri sessizce reddedilir.
sina("izin_sor yayinda (CLI kancasi)", "izin_sor" in adlar)
sina("gorsel_uret yayinda", "gorsel_uret" in adlar)
# `gorsel_iste`: otomatik uretim mumkun degilse (anahtar yok, kota dolu)
# istemi ajan yazar, INSAN uretir. Tarayiciyla ChatGPT'yi surmek teknik
# olarak mumkun ama OpenAI tuketici urunune programatik erisimi
# yasakliyor -- hesap kullanicinin olsa bile kisitlanan sey YONTEM.
sina("gorsel_iste yayinda (insan koprusu)", "gorsel_iste" in adlar)
sina("kanit_ekle yayinda", "kanit_ekle" in adlar)
sina("her aracin sema ve aciklamasi var",
     all(a.get("description") and a.get("inputSchema")
         for a in y["result"]["tools"]))
sina("bilinmeyen yontem hata donduruyor",
     "error" in s.cagir("yok/boyle/bir/sey"))

# --------------------------------------------------------------------------
print("\n2. DURUM -- ajan kendi goruntusunu alabiliyor")
metin = s.arac("durum")
sina("gorevi gosteriyor", "#1 API yaz" in metin)
sina("kabul olcutunu gosteriyor", "pytest yesil" in metin)
# Yollar normalize saklanir (tahta.yol_normalle): "api/" -> "api".
sina("yazma alanini gosteriyor", "api" in metin)
sina("GECERLI olgu gorunuyor", "30 gun" in metin)

# --------------------------------------------------------------------------
print("\n3. KANIT -- metin sozlesmesinin yerini alan cagri")
sina("bos icerikli kanit REDDEDILIYOR",
     s.hatali_mi("kanit_ekle", tur="terminal", baslik="pytest", icerik=""))
sina("reddedilen kanit tahtaya gecmedi", ofis.tahta.kanitlar(g["no"]) == [])

cevap = s.arac("kanit_ekle", tur="terminal", baslik="python -m pytest -q",
               icerik="9 passed in 0.03s")
sina("kanit eklendi", "Kanit eklendi" in cevap)
kanitlar = ofis.tahta.kanitlar(g["no"])
sina("kanit tahtada", len(kanitlar) == 1)
sina("kanit AJANIN adina yazildi", kanitlar[0]["ekleyen"] == "cinar")
sina("kanit DOGRU goreve yazildi (arguman sorulmadi)",
     kanitlar[0]["baslik"] == "python -m pytest -q")
sina("bilinmeyen kanit turu reddediliyor",
     s.hatali_mi("kanit_ekle", tur="ruya", baslik="b", icerik="i"))

# --------------------------------------------------------------------------
print("\n4. KARAR -- gerekce zorunlu")
sina("gerekcesiz karar REDDEDILIYOR",
     s.hatali_mi("karar_yaz", karar="Postgres kullanalim", gerekce=""))
sina("reddedilen karar gunluge gecmedi", ofis.bellek.son_kararlar(5) == [])
s.arac("karar_yaz", karar="Tarihler UTC saklanacak",
       gerekce="Yerel saat kaydedilirse gecmis karsilastirilamaz.")
son = ofis.bellek.son_kararlar(1)[0]
sina("karar gunluge dustu", son["karar"] == "Tarihler UTC saklanacak")
sina("karari AJAN verdi", son["veren"] == "cinar")

# --------------------------------------------------------------------------
print("\n4b. BILGI -- olgu katmaninin ajana acilan kapisi")
# OLCULDU (24.09): gercek ofiste 0 olgu vardi; uretimde olgu yazan tek bir
# yol yoktu. Kapi burada: kimlik ORTAMDAN, insanin yazdigi devrilemez.
_c = s.arac("bilgi_yaz", konu="Node surumu", icerik="Proje Node 22 kullanir.")
_o = ofis.bellek.gecerli_olgular(["Node surumu"])
sina("ajan bilgi yazabiliyor", "yazildi" in _c and len(_o) == 1, _c)
sina("  kaynak ORTAMDAKI kimlik + gorev (ajan secemez)",
     bool(_o) and _o[0]["kaynak"] == f"ajan:cinar #{g['no']}",
     str(_o))
_c = s.arac("bilgi_yaz", konu="node SÜRÜMÜ", icerik="Proje Node 22 kullanir.",
            kaynak="insan")
sina("ayni icerik yeni surum ACMIYOR (konu adi normallesiyor)",
     "Zaten biliniyor" in _c and len(ofis.bellek.konu_gecmisi("Node surumu")) == 1,
     _c)
sina("  kaynak argumani YOK SAYILDI (insan gibi yazamaz)",
     ofis.bellek.gecerli_olgular(["Node surumu"])[0]["kaynak"].startswith("ajan:"))
ofis.bellek.bilgi_ekle("iade suresi", "14 gun", yazan="insan")
_c = s.arac("bilgi_yaz", konu="Iade suresi", icerik="30 gun")
sina("insanin yazdigini ajan DEVIREMIYOR", "HATA" in _c and "soru_sor" in _c,
     _c)
sina("  bilgi degismedi",
     ofis.bellek.gecerli_olgular(["iade suresi"])[0]["icerik"] == "14 gun")
_c = s.arac("bilgi_yaz", konu="Kargo", icerik="Kargo [[lojistik anlasmasi]]"
            " sartlarina gore secilir.")
sina("kirik bag SOYLENIYOR", "hedefi henuz yok" in _c and "lojistik" in _c, _c)
sina("cok uzun bilgi reddediliyor",
     s.hatali_mi("bilgi_yaz", konu="x", icerik="a" * 700))
ofis.bellek.kural_ekle("Tarihler UTC saklanir.", "Karsilastirma bozulmasin.")
sina("durum KURALLARI gosteriyor",
     "OFIS KURALLARI" in s.arac("durum")
     and "Tarihler UTC saklanir." in s.arac("durum"))

# --------------------------------------------------------------------------
print("\n5. SORU -- ajan durabiliyor (mesaj tablosu artik yasiyor)")
sina("bos soru reddediliyor", s.hatali_mi("soru_sor", soru=""))
cevap = s.arac("soru_sor", soru="Iade suresi 30 mu 45 gun mu?")
sina("soru iletildi", "bekleniyor" in cevap)
sina("ajana DUR deniyor", "DUR" in cevap)
bekleyen = ofis.postane.bekleyen_sorular()
sina("soru tabloda", len(bekleyen) == 1)
sina("soru LIDERE gitti", bekleyen[0]["alici"] == "demir")
sina("soru goreve bagli", bekleyen[0]["gorev_no"] == g["no"])
hal = ofis.postane.bekliyor_mu("cinar")
sina("ajan 'bekliyor' halinde", hal["bekliyor"] and hal["tur"] == "soru")
sina("gorev durumu DEGISMEDI (turetilmis hal)",
     ofis.tahta.gorev(g["no"])["durum"] == "calisiyor")

ofis.postane.cevapla(bekleyen[0]["id"], "30 gun. Guncel olgu bu.",
                     cevaplayan="demir")
sina("cevaplanan soru bekleyenden cikti", ofis.postane.bekleyen_sorular() == [])
sina("ajan artik beklemiyor", ofis.postane.bekliyor_mu("cinar")["bekliyor"] is False)
sina("cevap ajana ulasabiliyor",
     "30 gun" in ofis.postane.cevaplar("cinar")[0]["cevap"])
try:
    b2 = ofis.postane.soru_sor("cinar", "demir", "ikinci soru")
    ofis.postane.cevapla(b2["id"], "   ")
    sina("bos cevap REDDEDILIYOR", False, "-- kabul edildi!")
except Exception:
    sina("bos cevap REDDEDILIYOR", True)
ofis.postane.cevapla(b2["id"], "cevap")

# --------------------------------------------------------------------------
print("\n6. ONAY -- riskli adim insana takiliyor")
sina("bos eylem reddediliyor", s.hatali_mi("onay_iste", eylem=""))
cevap = s.arac("onay_iste", eylem="Reklam kampanyasini yayina al",
               ayrinti="gunluk 500 TL", risk="yuksek")
sina("onay kaydedildi", "bekleniyor" in cevap)
sina("ajana DUR deniyor", "DUR" in cevap)
onaylar = ofis.postane.bekleyen_onaylar()
sina("onay tabloda", len(onaylar) == 1)
sina("risk tasindi", onaylar[0]["risk"] == "yuksek")
hal = ofis.postane.bekliyor_mu("cinar")
sina("ajan 'onay' bekliyor", hal["bekliyor"] and hal["tur"] == "onay")

try:
    ofis.postane.onay_cevapla(onaylar[0]["id"], onayla=False, not_="")
    sina("gerekcesiz RET reddediliyor", False, "-- kabul edildi!")
except Exception:
    sina("gerekcesiz RET reddediliyor", True)
ofis.postane.onay_cevapla(onaylar[0]["id"], onayla=False,
                          not_="Butce onaylanmadi, once teklif hazirla.")
sina("onay cevaplandi", ofis.postane.bekleyen_onaylar() == [])
try:
    ofis.postane.onay_cevapla(onaylar[0]["id"], onayla=True)
    sina("ikinci kez cevaplanamiyor", False, "-- kabul edildi!")
except Exception:
    sina("ikinci kez cevaplanamiyor", True)

# --------------------------------------------------------------------------
print("\n7. YETKI -- isci gorev acamaz")
cevap = s.arac("gorev_ac", baslik="Kendime is actim", neden="n",
               ana_hedef="h", kabul_olcutu="k")
sina("ISCI gorev acamiyor", "HATA" in cevap and "lidere aittir" in cevap)
sina("gorev gercekten acilmadi", len(ofis.tahta.liste()) == 1)
s.kapat()

# --------------------------------------------------------------------------
print("\n8. KIMLIK ORTAMDAN GELIYOR -- sahtekarlik yapilamiyor")
s2 = Sunucu({"OFIS_DB": str(db_yolu), "OFIS_PROJE": ofis.proje_id,
             "OFIS_AJAN": "demir", "OFIS_GOREV": str(g["no"])})
s2.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
# Lider olarak baslatildi: gorev acabilmeli.
cevap = s2.arac("gorev_ac", baslik="Sepet ekrani", neden="Sepet gorunmuyor",
                ana_hedef="Magaza canliya cikacak", kabul_olcutu="Ekran goruntusu",
                yazma_alani=["web/"])
sina("LIDER gorev acabiliyor", "Gorev acildi" in cevap)
sina("gorev tahtaya dustu", len(ofis.tahta.liste()) == 2)

# Ajan "ben cinarim" diye arguman gonderse bile kimlik degismez.
s2.arac("kanit_ekle", tur="dosya", baslik="x.py", icerik="yazildi")
sonuncu = ofis.tahta.kanitlar(g["no"])[-1]
sina("kanit ORTAMDAKI kimlikle yazildi (demir), argumanla degil",
     sonuncu["ekleyen"] == "demir")
sina("belirtimsiz gorev acilamiyor",
     "HATA" in s2.arac("gorev_ac", baslik="Yarim is", neden="",
                       ana_hedef="h", kabul_olcutu="k"))
s2.kapat()

# --------------------------------------------------------------------------
print("\n9. KIMLIKSIZ SUNUCU sessizce calismiyor")
s3 = Sunucu({"OFIS_DB": "", "OFIS_PROJE": "", "OFIS_AJAN": ""})
s3.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
sina("kimliksiz sunucu arac cagrisinda HATA donduruyor",
     s3.hatali_mi("durum"))
s3.kapat()

print("\nGORELI YOL TUZAGI -- ajan BASKA bir veritabanina yazmasin")
# OLCULDU (19.09.2026), SESSIZ VE AGIR: kabuk `--db veri/ofis.sqlite3`
# ile GORELI yol aliyordu. MCP sunucusu her tur icin ayri surec olarak
# AJANIN KLASORUNDE kosar; ayni goreli yol baska bir yere cozuldu ve
# `calisma/veri/ofis.sqlite3` diye BOMBOS bir veritabani yaratildi.
#
# Hata vermedi. Iki sonucu vardi:
#   * `kanit_ekle` "gorev bulunamadi" dedi -- is bitmisti, defterde
#     bitmemis kaldi (uc tur, sifir kanit);
#   * `durum` BOS bir ofis dondurdu -- ajan OFISIN YANLIS RESMINI gordu.
# Ikincisi daha kotu: eksik kayit fark edilir, YANLIS bilgi fark edilmez.

import os as _os
import subprocess as _sp
import json as _json2

_kok9 = Path(tempfile.mkdtemp(prefix="ofis-goreli-"))
_alt = _kok9 / "calisma" / "cinar"
_alt.mkdir(parents=True, exist_ok=True)

_onceki_cwd = _os.getcwd()
_os.chdir(_kok9)
try:
    _db9 = Veritabani("veri/o.sqlite3")          # GORELI verildi
    sina("Veritabani yolu MUTLAK tutuyor", _db9.yol.is_absolute(),
         f"({_db9.yol})")

    _o9 = Ofis.proje_ac(_db9, "Goreli", amac="a", basari_olcutu="b")
    _k9 = _o9.kanat_ac("U", "U")
    _o9.kadro.ise_al("cinar", "backend", kanat_id=_k9, tur="eller", motor="sahte",
                     model="haiku", klasor=str(_alt))
    _g9 = _o9.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k",
                             govde="g", kanat_id=_k9, yazma_alani=["a/"])
    _o9.tahta.sahiplen(_g9["no"], "cinar", _g9["revizyon"])

    # MCP sunucusunu AJANIN KLASORUNDE kostur -- gercek hayattaki gibi.
    _ortam = dict(_os.environ, OFIS_DB=str(_db9.yol), OFIS_PROJE=_o9.proje_id,
                  OFIS_AJAN="cinar", OFIS_GOREV=str(_g9["no"]))
    _p9 = _sp.Popen([sys.executable, str(Path(_onceki_cwd) / "ofis" / "mcp_sunucu.py")],
                    cwd=str(_alt), env=_ortam, stdin=_sp.PIPE, stdout=_sp.PIPE,
                    stderr=_sp.PIPE, text=True, encoding="utf-8")
    _istek = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "kanit_ekle",
                    "arguments": {"tur": "baglanti", "baslik": "kaynak",
                                  "icerik": "https://ornek"}}},
    ]
    _cikti, _hata9 = _p9.communicate(
        "".join(_json2.dumps(i) + chr(10) for i in _istek), timeout=30)
    _yanit = [_json2.loads(x) for x in _cikti.splitlines()
              if x.strip().startswith("{")]
    _k = [y for y in _yanit if y.get("id") == 2]
    sina("AJANIN KLASORUNDEN kanit eklenebiliyor",
         bool(_k) and not _k[0].get("result", {}).get("isError"),
         f"({_k[0] if _k else _hata9[:200]})")
    sina("kanit GERCEK tahtaya dustu",
         len(_o9.tahta.kanitlar(_g9["no"])) == 1,
         f"({len(_o9.tahta.kanitlar(_g9['no']))})")
    sina("ajan klasorunde HAYALET veritabani olusmadi",
         not (_alt / "veri").exists(), f"({list(_alt.iterdir())})")
finally:
    _os.chdir(_onceki_cwd)

print("\nYANLIS DEFTER NOBETCISI -- bos ofis dondurmek yerine BAGIRIR")
# Iki hata modundan KOTU olani "durum BOS ofis dondurdu"ydu: ajan
# ofisin yanlis resmini gordu ve buna gore akil yurutta. Eksik kayit fark
# edilir, YANLIS bilgi fark edilmez. Nobetci onu kapatiyor.

_bos = Path(tempfile.mkdtemp(prefix="ofis-bos-")) / "bos.sqlite3"
_ortam2 = dict(_os.environ, OFIS_DB=str(_bos), OFIS_PROJE="olmayan-proje",
               OFIS_AJAN="cinar", OFIS_GOREV="5")
_p10 = _sp.Popen([sys.executable, str(Path(__file__).resolve().parent.parent
                                      / "ofis" / "mcp_sunucu.py")],
                 env=_ortam2, stdin=_sp.PIPE, stdout=_sp.PIPE, stderr=_sp.PIPE,
                 text=True, encoding="utf-8")
_istek2 = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "durum", "arguments": {}}},
]
_c10, _e10 = _p10.communicate(
    "".join(_json2.dumps(i) + chr(10) for i in _istek2), timeout=30)
_y10 = [_json2.loads(x) for x in _c10.splitlines() if x.strip().startswith("{")]
_d10 = [y for y in _y10 if y.get("id") == 2]
_metin10 = (_d10[0]["result"]["content"][0]["text"] if _d10 else "")

sina("yanlis defterde `durum` HATA donduruyor",
     bool(_d10) and _d10[0]["result"].get("isError") is True,
     f"({_metin10[:120]})")
sina("bos ofis DONDURMUYOR", "projesi YOK" in _metin10, f"({_metin10[:120]})")
sina("hangi veritabanina bakildigini SOYLUYOR", str(_bos) in _metin10)
sina("goreli yol suphesini aciklikla soyluyor", "goreli yol" in _metin10)
sina("araclarin guvenilmez oldugunu soyluyor", "guvenilir degildir" in _metin10)

print("\nEMOJI VE TURKCE -- stdio kodlamasi tuzagi")
# OLCULDU (19.09.2026): Windows konsolu cp1254. Sunucu stdin'i yerel
# kodlamayla okuyordu; emoji tek basina VEKIL karaktere donusuyor ve
# SQLite'a yazarken "surrogates not allowed" ile patliyordu.
#
# Gercek bir turda ajan bunu DOGRU teshis etti ve duz Turkce soyledi:
#   "Emoji karakterler soruna neden oldu. Duz metin ile tekrar deneyecegim."
# Hata gorunurdu ama SEBEBI sistemdeydi, ajanda degil. Ajanlar Turkce ve
# emoji yazar; kanit kaybolursa is kapanmaz.

_kok11 = Path(tempfile.mkdtemp(prefix="ofis-emoji-"))
_db11 = Veritabani(_kok11 / "o.sqlite3")
_o11 = Ofis.proje_ac(_db11, "Emoji", amac="a", basari_olcutu="b")
_k11 = _o11.kanat_ac("U", "U")
_o11.kadro.ise_al("cinar", "backend", kanat_id=_k11, tur="eller", motor="sahte",
                  model="haiku", klasor=str(_kok11))
_g11 = _o11.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k",
                           govde="g", kanat_id=_k11, yazma_alani=["a/"])
_o11.tahta.sahiplen(_g11["no"], "cinar", _g11["revizyon"])

_s11 = Sunucu({"OFIS_DB": str(_db11.yol), "OFIS_PROJE": _o11.proje_id,
               "OFIS_AJAN": "cinar", "OFIS_GOREV": str(_g11["no"])})
_s11.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})

# chr() ile kuruluyor: kaynak dosyada ham emoji birakmak, bu dosyayi
# duzenleyen her aracin ayni kodlama tuzagina dusmesini davet eder.
_emoji = chr(0x2705) + " " + chr(0x1F680)
_tr = "Turkce " + chr(0x11F) + chr(0xFC) + chr(0x15F) + chr(0xF6) + chr(0xE7)
_cevap11 = _s11.arac("kanit_ekle", tur="dosya",
                     baslik=_emoji + " baslik", icerik=_tr + " " + _emoji)
sina("EMOJI iceren kanit kabul ediliyor", "Kanit eklendi" in _cevap11,
     f"({_cevap11[:120]})")
_k = _o11.tahta.kanitlar(_g11["no"])
sina("emoji tahtaya BOZULMADAN dustu",
     bool(_k) and _emoji in _k[0]["baslik"], f"({_k[0]['baslik'] if _k else None})")
sina("Turkce karakterler korundu",
     bool(_k) and chr(0x15F) in _k[0]["icerik"])
_s11.kapat()

# ---------------------------------------------------------------------------
# 12. VIDEO ARACLARI -- ajan `video.py`ye ULASABILIYOR MU
#
# Bu bolum bir dersten dogdu: `video.py` yazildi, `video` rolu eklendi ve
# ajanin ona ulasacagi HICBIR yol yoktu. Rol tam olarak kendi
# yasakladigimiz haldeydi: *"araci olmayan rol, rol degildir."*
# ---------------------------------------------------------------------------
print("\n-- 12. video araclari --")

from ofis import mcp_sunucu as _ms
from ofis import video as _vid

_adlar = [_a["name"] for _a in _ms.ARACLAR]
sina("video_uret yayinda", "video_uret" in _adlar)
# Ayri arac, cunku is dakikalarca surer ve bekleyen ajan kilidini tutar.
sina("video_durum yayinda (beklemek bir SECIM)", "video_durum" in _adlar)
# Bugun ucretsiz olan TEK yol: video API'lerinde ucretsiz katman yok.
sina("video_iste yayinda (insan koprusu)", "video_iste" in _adlar)


class _SahteVideoUretici(_vid.Uretici):
    """Senaryolu uretici: ag'a cikmadan is modelini sinar."""
    ad = "sahtevideo"
    ucretli = True
    saniye_basi_usd = 0.01
    baslatma_sayisi = 0

    def musait_mi(self):
        return True

    def baslat(self, istem, *, saniye, model="", cozunurluk="720p"):
        _SahteVideoUretici.baslatma_sayisi += 1
        return {"is_id": "is-42", "uretici": self.ad, "model": "sahte-1",
                "saniye": int(saniye), "cozunurluk": cozunurluk}

    def durum(self, is_id):
        return {"bitti": True, "basarili": True, "hata": "", "ham": {}}

    def indir(self, is_id, hedef):
        _h = Path(hedef)
        _h.parent.mkdir(parents=True, exist_ok=True)
        _h.write_bytes(b"MP4")
        return {"yol": str(_h), "bayt": 3, "tip": "video/mp4"}


_vid.uretici_kaydet(_SahteVideoUretici)

# BU BOLUM UCRETLI YOLU SINIYOR: sahte uretici `ucretli=True` (gercegi
# oyle) ve PARA KILIDI varsayilan olarak aciktir. Kilidi gevsetmek
# yerine muafiyeti ACIKCA soyluyoruz -- kilidin kendisi ayrica
# sinaniyor (12i).
os.environ["OFIS_PARA_HARCA"] = "1"


class _SahteOturum:
    """Gercek ofisi kullanan, yalniz KIMLIGI sabitlenmis oturum.

    Kimlik ortamdan gelir (`OFIS_AJAN`/`OFIS_GOREV`); burada onun
    yerine dogrudan veriliyor, cunku sinanan sey kimlik degil araclar.
    """

    def __init__(self, ofis, ajan_ad, gorev_no):
        self.ofis = ofis
        self.ajan_ad = ajan_ad
        self.gorev_no = gorev_no

    def ajan(self):
        return self.ofis.kadro.ajan(self.ajan_ad)

    def gorev(self):
        if self.gorev_no is None:
            raise RuntimeError("Bu turda acik bir gorev yok.")
        return self.ofis.tahta.gorev(self.gorev_no)


_vo = _SahteOturum(ofis, "cinar", g["no"])

# --- 12a. bekle=False: kimlik doner, beklenmez ---
_vc = _ms.arac_video_uret(_vo, {"istem": "denizde gun batimi", "saniye": 4,
                                "bekle": False, "uretici": "sahtevideo"})
sina("bekle=false is kimligini donduruyor", "is-42" in _vc, f"({_vc[:90]})")
sina("bekle=false beklemiyor (indirme yok)", "indirildi" not in _vc)

# --- 12b. EN KRITIK: kimlik BEKLEMEDEN ONCE deftere yazildi mi ---
# Parasi odenmis bir is, tur kesilirse kaybolmamali. Arastirma isinde
# bir kez odenen dersin (208.148 jeton, 0 kanit) para tarafi.
_vk = _ms._video_isi_bul(_vo, "is-42")
sina("is kimligi DEFTERE yazildi (kesilen tur kaybetmez)",
     _vk.get("is_id") == "is-42", f"({_vk})")
sina("defterde uretici de var (ajan tekrar yazmak zorunda degil)",
     _vk.get("uretici") == "sahtevideo")
sina("defterde tahmini maliyet var (olcmedigimiz sey yonetilemez)",
     _vk.get("tahmini_maliyet_usd") == 0.04, f"({_vk.get('tahmini_maliyet_usd')})")

# --- 12c. video_durum kimligi DEFTERDEN bulup indiriyor ---
_vonce = len(ofis.tahta.kanitlar(g["no"]))
_vc = _ms.arac_video_durum(_vo, {"is_id": "is-42"})
sina("video_durum indiriyor", "indirildi" in _vc, f"({_vc[:90]})")
sina("video_durum KANIT yaziyor",
     len(ofis.tahta.kanitlar(g["no"])) == _vonce + 1)

# --- 12d. YAZMA ALANININ ICINE yazildi mi (Yasa 1) ---
# Yol `baslik` alaninda durur, `icerik`te degil -- `gorsel_uret` ile
# ayni duzen. (Testin ilk surumu ters bakti ve dogru sekilde KALDI.)
_vkanit = [k for k in ofis.tahta.kanitlar(g["no"]) if ".mp4" in k["baslik"]]
sina("video yazma alaninin ICINE yazildi",
     bool(_vkanit) and ("api" + os.sep) in _vkanit[0]["baslik"],
     f"({_vkanit[0]['baslik'] if _vkanit else None})")

# --- 12e. bilinmeyen kimlik SESSIZCE gecmiyor ---
sina("bilinmeyen is kimligi reddediliyor",
     _ms.arac_video_durum(_vo, {"is_id": "olmayan-is"}).startswith("HATA"))

# --- 12f. TAVAN: is HIC baslamiyor ---
_vsay = _SahteVideoUretici.baslatma_sayisi
_SahteVideoUretici.saniye_basi_usd = 10.0
_vc = _ms.arac_video_uret(_vo, {"istem": "pahali", "saniye": 30,
                                "tavan_usd": 1.0, "uretici": "sahtevideo"})
sina("tavan asilinca TAVAN donuyor (HATA degil -- karar)",
     _vc.startswith("TAVAN"), f"({_vc[:90]})")
sina("tavan asilinca surec HIC baslamiyor",
     _SahteVideoUretici.baslatma_sayisi == _vsay)
sina("tavan asilinca 'tekrar deneme' deniyor", "Tekrar deneme" in _vc)
_SahteVideoUretici.saniye_basi_usd = 0.01

# AJANIN VERDIGI TAVAN GERCEKTEN ULASIYOR MU.
# Ustteki sinama yetmiyordu: maliyet VARSAYILAN tavani da asiyordu, yani
# `tavan_usd` hic gecmese bile ret geliyordu. Mutasyon bunu gosterdi --
# tavan sessizce yok sayilirken test GECIYORDU. Simdi maliyet varsayilan
# tavanin ALTINDA, yalniz ajanin verdiginin ustunde: ret gelirse sebebi
# yalnizca ajanin tavani olabilir.
# (Sessizce yok sayilan ayar, ayar degildir -- bu projede besinci kez.)
_vsay = _SahteVideoUretici.baslatma_sayisi
_vtahmin = _vid.tahmini_maliyet("sahtevideo", 30)       # 0.01 * 30 = 0.30
sina("kurgu dogru: maliyet VARSAYILAN tavanin altinda",
     _vtahmin < _vid.VARSAYILAN_TAVAN_USD, f"({_vtahmin})")
_vc = _ms.arac_video_uret(_vo, {"istem": "orta", "saniye": 30,
                                "tavan_usd": 0.10, "uretici": "sahtevideo"})
sina("AJANIN verdigi tavan motora ULASIYOR", _vc.startswith("TAVAN"),
     f"({_vc[:90]})")
sina("ajanin tavani asilinca surec HIC baslamiyor",
     _SahteVideoUretici.baslatma_sayisi == _vsay)
# Ters yon: ayni is, tavan yeterliyse GECMELI. Yoksa sinama "her sey
# reddediliyor" dese de gecerdi.
_vc = _ms.arac_video_uret(_vo, {"istem": "orta", "saniye": 30,
                                "tavan_usd": 5.0, "uretici": "sahtevideo",
                                "bekle": False})
sina("yeterli tavanla is BASLIYOR (kapi her seyi reddetmiyor)",
     "BASLATILDI" in _vc, f"({_vc[:90]})")

# --- 12g. gorevsiz / bos istem reddediliyor ---
_vo2 = _SahteOturum(ofis, "cinar", None)
sina("gorevsiz turda video_uret reddediliyor",
     _ms.arac_video_uret(_vo2, {"istem": "x"}).startswith("HATA"))
sina("gorevsiz turda video_iste reddediliyor",
     _ms.arac_video_iste(_vo2, {"istem": "x"}).startswith("HATA"))
sina("bos istemle video uretilmiyor",
     _ms.arac_video_uret(_vo, {"istem": "  "}).startswith("HATA"))

# --- 12h. video_iste INSAN kuyruguna dusuyor, ajana DUR diyor ---
_vonay = len(ofis.postane.bekleyen_onaylar())
_vc = _ms.arac_video_iste(_vo, {"istem": "marka tanitimi", "saniye": 8})
sina("video_iste insan ONAY kuyruguna dusuruyor",
     len(ofis.postane.bekleyen_onaylar()) == _vonay + 1)
sina("video_iste ajana DUR diyor", "SIMDI DUR" in _vc)
# Insana birakilan komut GERCEKTEN var olmali. `gorsel.py`nin kapali
# dongusu (kod kasaya bakmiyordu, ama hata mesaji kasaya yaz diyordu)
# tam bu siniftaydi: ofis kendi verdigi talimat izlendiginde bile
# calismiyordu.
_vbek = ofis.postane.bekleyen_onaylar()[-1]
sina("video_iste'nin verdigi komut `video ekle`",
     "video ekle" in (_vbek["ayrinti"] or ""))
sina("insana ucretsiz yol soyleniyor", "Flow" in (_vbek["ayrinti"] or ""))

# --- 12i. AJAN PARA KILIDINI ASAMAZ ---
# En onemli sinama: para karari INSANINDIR. Ajan kilidi acikken ucretli
# bir uretim baslatabilseydi, kilidin hicbir anlami kalmazdi -- ve ajan
# bunu kotu niyetle degil, isini yapmaya calisirken yapardi.
os.environ.pop("OFIS_PARA_HARCA", None)
_vsay = _SahteVideoUretici.baslatma_sayisi
_vc = _ms.arac_video_uret(_vo, {"istem": "kilit denemesi", "saniye": 4,
                                "uretici": "sahtevideo", "bekle": False})
sina("PARA KILIDI acikken ajan video URETEMIYOR",
     "PARA KILIDI" in _vc or _vc.startswith("HATA"), f"({_vc[:90]})")
sina("kilit acikken surec HIC baslamiyor",
     _SahteVideoUretici.baslatma_sayisi == _vsay)
# Ret, NE YAPILACAGINI da soylemeli: teshis koyup care soylemeyen
# gosterge insani bir kez daha dusunmeye zorlar.
sina("ret, kilidin nasil acilacagini soyluyor", "gorsel para ac" in _vc,
     f"({_vc[:150]})")

# --- 12i. MALIYET ETIKETI: hesaplanan ile OLCULEN karistirilmiyor ---
# `gorsel_uret` maliyeti API yanitindan OKUR; video'da okunamaz, ilan
# edilen fiyattan hesaplanir. Ayni etiketi koymak, hesaplanani olculen
# sanmaya davet olurdu -- ve `video` rolunun olcutu acikca "GERCEK
# maliyet (tahmin degil)" istiyor.
sina("video kanitinda maliyet 'fatura DEGIL' diye isaretli",
     bool(_vkanit) and "faturasi DEGIL" in _vkanit[0]["icerik"],
     f"({_vkanit[0]['icerik'][:120] if _vkanit else None})")


# --------------------------------------------------------------------------
print("\n13. IZIN_SOR -- ofisin TEK kapisi, gercek surecte")

# Bu arac ajanin cagirdigi bir sey DEGIL: CLI her izin gerektiren arac
# cagrisinda otomatik soruyor. Sozlesmesi de ofisin degil CLI'in:
# yanit `{"behavior": "allow"|"deny"}` JSON'u olmali. Bicim tutmazsa
# CLI onu anlamaz ve -- olculmedigi surece -- kapi kurulmus SANILIR.
import json as _json                                        # noqa: E402

# TAZE SUREC: yukaridaki `s` kapatilmisti. Kapali bir boruya yazmak
# testi COKERTIR ve geri kalan sinamalar hic kosmaz -- coken bir test,
# kaldigini soyleyenden kotudur.
_si = Sunucu({"OFIS_DB": str(db_yolu), "OFIS_PROJE": ofis.proje_id,
              "OFIS_AJAN": "cinar", "OFIS_GOREV": str(g["no"])})
_si.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "t", "version": "1"}})
_si.bildir("notifications/initialized", {})


def _izin(arac_adi: str, girdi: dict) -> dict:
    return _json.loads(_si.arac("izin_sor", tool_name=arac_adi, input=girdi))


# OKUMA serbest -- her seyi durduran bir kapi da karar vermiyordur.
for _okuma, _g in (("mcp__claude_ai_Shopify__get-shop-info", {}),
                   ("mcp__claude_ai_Meta_Reklamlar__ads_get_ad_accounts", {}),
                   ("Read", {"file_path": "a.txt"})):
    sina(f"okuma serbest: {_okuma.split('__')[-1]}",
         _izin(_okuma, _g).get("behavior") == "allow")

# Ofisin KENDI araclari bu kapidan gecmez: kendi kapilarini zaten
# tasiyorlar (para kilidi, kimlik ortamdan) ve iki kez sormak insana
# ayni seyi iki kez cevaplatmak olurdu.
sina("ofisin kendi araci kapidan gecmiyor",
     _izin("mcp__ofis__kanit_ekle", {}).get("behavior") == "allow")
sina("tarayici araci kapidan gecmiyor (kendi vekili var)",
     _izin("mcp__tarayici__browser_click", {}).get("behavior") == "allow")

# DEGISTIREN ama riskli olmayan: SORULMAZ, KAYDEDILIR.
with ofis.db.baglanti() as _c:
    _onceki = _c.execute(
        "SELECT COUNT(*) FROM olay WHERE tur='arac_degisikligi'").fetchone()[0]
sina("kayit sinifi serbest gecer",
     _izin("mcp__claude_ai_Atria__write_note",
           {"text": "not"}).get("behavior") == "allow")
with ofis.db.baglanti() as _c:
    _sonraki = _c.execute(
        "SELECT COUNT(*) FROM olay WHERE tur='arac_degisikligi'").fetchone()[0]
sina("kayit sinifi DEFTERE yazildi", _sonraki > _onceki)

# RISKLI: reddedilir ve onay kaydi acilir.
_once = len(ofis.postane.bekleyen_onaylar("cinar"))
_c1 = _izin("mcp__claude_ai_Meta_Reklamlar__ads_activate_entity",
            {"entity_id": "123"})
sina("riskli cagri REDDEDILDI", _c1.get("behavior") == "deny")
sina("ret metni ne yapacagini soyluyor",
     "SIMDI DUR" in (_c1.get("message") or ""))
_bek = ofis.postane.bekleyen_onaylar("cinar")
sina("onay kaydi acildi", len(_bek) == _once + 1)
sina("onay IMZA tasiyor", bool(_bek) and "IMZA:" in _bek[-1]["ayrinti"])
sina("onay kartinda ARAC ADI var",
     bool(_bek) and "ads_activate_entity" in _bek[-1]["ayrinti"])

# TANINMAYAN arac SORULUR -- yarin eklenen bir arac sessizce iceri
# girmemeli. Polarite bilincli: okuma beyaz listede, gerisi kapida.
sina("taninmayan arac REDDEDILDI",
     _izin("mcp__claude_ai_Yeni__frobnicate_widget",
           {}).get("behavior") == "deny")

# ONAYLANINCA gecer -- ve BIR KEZ.
_onay = _bek[-1]
ofis.postane.onay_cevapla(_onay["id"], onayla=True, not_="Deneme.")
sina("onaylanan cagri GECIYOR",
     _izin("mcp__claude_ai_Meta_Reklamlar__ads_activate_entity",
           {"entity_id": "123"}).get("behavior") == "allow")
sina("IKINCI kez gecmiyor (tuketildi)",
     _izin("mcp__claude_ai_Meta_Reklamlar__ads_activate_entity",
           {"entity_id": "123"}).get("behavior") == "deny")

# KAPSAM 'is': bu gorev boyunca tekrar sorulmaz. Kapi artik baglayici
# araclarini da kapsiyor ve ayni eylem bir iste onlarca kez gecebilir
# (20 urun -> 20 soru); tek kademeli onay, kullanicinin itiraz ettigi
# engellemeye baska kapidan geri donmek olurdu.
_bek2 = ofis.postane.bekleyen_onaylar("cinar")
ofis.postane.onay_cevapla(_bek2[-1]["id"], onayla=True, not_="Is boyunca.",
                          kapsam="is")
_ad = "mcp__claude_ai_Meta_Reklamlar__ads_activate_entity"
sina("kapsam=is: birinci gecis",
     _izin(_ad, {"entity_id": "123"}).get("behavior") == "allow")
sina("kapsam=is: ikinci de geciyor (TUKENMIYOR)",
     _izin(_ad, {"entity_id": "123"}).get("behavior") == "allow")
with ofis.db.baglanti() as _c:
    _cevaplar = [dict(r)["govde"] for r in _c.execute(
        "SELECT govde FROM olay WHERE tur='onay_cevabi'")]
# Gostermeyen cikti, sessizce genisleyen bir yetkiyi fark ettirmez.
sina("kapsam kayda gecti",
     any("BU IS BOYUNCA" in x for x in _cevaplar), str(_cevaplar[-1:])[:120])

# REDDEDILEN ogretir ve tekrar sorulmaz.
_r = _izin("mcp__claude_ai_Shopify__create-discount", {"percent": 20})
sina("para sinifi reddedildi", _r.get("behavior") == "deny")
_rbek = ofis.postane.bekleyen_onaylar("cinar")
ofis.postane.onay_cevapla(_rbek[-1]["id"], onayla=False,
                          not_="Indirim politikasi once konusulacak.")
_r2 = _izin("mcp__claude_ai_Shopify__create-discount", {"percent": 20})
sina("ret ajana iletiliyor", "REDDEDILDI" in (_r2.get("message") or ""))
sina("ret GEREKCESI iletiliyor",
     "Indirim politikasi" in (_r2.get("message") or ""))

_si.kapat()

# SUNUCU BETIK OLARAK KOSAR -- goreli ice aktarma YASAK (25.09.2026).
# Koltuk bu dosyayi `python ofis/mcp_sunucu.py` diye baslatir; orada
# `from . import gorsel` "attempted relative import with no known parent
# package" ile patlar. Gercek ajan turunda olculdu: `gorsel_uret`,
# `video_uret`, `video_durum` HIC calismiyordu. Bu dosyadaki sinamalar
# modulu PAKET olarak yukledigi icin goremiyordu. Ayni sinif 22.09'da
# `tarayici_kapi.py`de odenmisti. Lint: gecmesi dogrulugu gostermez ama
# gecmemesi tuzagin geri geldigini KESIN gosterir.
import re as _re_rel
_rel_yol = Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py"
_rel = _re_rel.findall(r"^\s+from \.[\w.]* import .*$",
                       _rel_yol.read_text(encoding="utf-8"), _re_rel.M)
sina("mcp_sunucu'da islev ici GORELI ice aktarma yok (betik olarak kosar)",
     not _rel, f"({_rel})")

# Dogrudan olcum: sunucu GERCEKTEN betik olarak baslatilip medya araci
# cagrildiginda ice aktarma hatasi DONMUYOR. Bos istem -> aracin KENDI
# HATA'si; yani ice aktarma asamasi gecildi. Gercek uretici CAGRILMAZ.
import subprocess as _sp_rel
import json as _js_rel
_istek = "".join(_js_rel.dumps(x) + "\n" for x in (
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "gorsel_uret", "arguments": {"istem": ""}}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "video_durum", "arguments": {"is_id": ""}}},
))
_rel_r = _sp_rel.run([sys.executable, str(_rel_yol)], input=_istek,
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=60,
                     env=dict(os.environ, OFIS_DB="", OFIS_PROJE=""))
_rel_cevap = [l for l in _rel_r.stdout.splitlines() if l.strip()]
sina("betik sunucu iki arac cagrisina da cevap verdi",
     len(_rel_cevap) >= 3, f"({_rel_r.stdout[-300:]} | {_rel_r.stderr[-200:]})")
sina("betik sunucuda medya araclari ice aktarma hatasi VERMIYOR",
     "relative import" not in _rel_r.stdout, f"({_rel_r.stdout[-300:]})")

print("\n-- 13. MEDYA HEDEFI: yazma alani DOSYA ise tam oraya --")
# Olculdu (26.09.2026, deneme D08): alan `kapak.png` idi, gorsel
# `kapak.png/kapak.png` icine yazildi -- `kapak.png` bir KLASOR oldu. Karar
# dort yerde kopyaydi (MCP gorsel/video, kabuk gorsel/video ekle); simdi
# `tahta.medya_hedefi` TEK yer.
from ofis import gorsel as _gor              # noqa: E402
from ofis.tahta import medya_hedefi as _mh, TahtaHatasi as _TH  # noqa: E402


class _SahteGorselUretici(_gor.Uretici):
    ad = "sahtegorsel"
    ucretli = False

    def musait_mi(self):
        return True

    def uret(self, istem, hedef, *, model="", kalite=""):
        _h = Path(hedef)
        _h.parent.mkdir(parents=True, exist_ok=True)
        _h.write_bytes(b"\x89PNG\r\n\x1a\nsahte")
        return {"yol": str(_h), "bayt": 13, "uretici": self.ad, "model": "s",
                "maliyet_usd": None}


_gor.uretici_kaydet(_SahteGorselUretici)
_mk = Path(tempfile.mkdtemp(prefix="ofis-medya-"))
(_mk / "web").mkdir()
sina("dosya alani -> tam o dosya", _mh(_mk, ["kapak.png"], "g-1.png") == _mk / "kapak.png")
sina("klasor alani -> icine", _mh(_mk, ["web"], "x.png") == _mk / "web" / "x.png")
sina("uzantisi uyan dosya secilir",
     _mh(_mk, ["rapor.md", "kapak.png"], "g.png") == _mk / "kapak.png")
try:
    _mh(_mk, ["rapor.md"], "g.png")
    sina("baska turde dosyanin USTUNE yazilmaz (ret)", False)
except _TH:
    sina("baska turde dosyanin USTUNE yazilmaz (ret)", True)

_gm = ofis.tahta.gorev_ac("Kapak", neden="n", ana_hedef="h", kabul_olcutu="k",
                          yazma_alani=["kapak.png"], sahip="cinar")
_mo = _SahteOturum(ofis, "cinar", _gm["no"])
_mc = _ms.arac_gorsel_uret(_mo, {"istem": "kahve", "dosya_adi": "kapak.png",
                                 "uretici": "sahtegorsel"})
_kok_c = Path(ofis.kadro.ajan("cinar")["klasor"])
sina("gorsel_uret alan DOSYA iken dosyaya yazdi (klasor ACMADI)",
     (_kok_c / "kapak.png").is_file(), _mc[:120])
_gm2 = ofis.tahta.gorev_ac("Rapor", neden="n", ana_hedef="h", kabul_olcutu="k",
                           yazma_alani=["rapor.md"], sahip="cinar")
(_kok_c / "rapor.md").write_text("metin", encoding="utf-8")
try:
    _mc2 = _ms.arac_gorsel_uret(_SahteOturum(ofis, "cinar", _gm2["no"]),
                                {"istem": "x", "uretici": "sahtegorsel"})
except Exception as _exc:                     # noqa: BLE001 -- cokme degil KALDI
    _mc2 = f"COKTU: {_exc}"
sina("uygun alan yoksa ajana HATA ANLATILIR", _mc2.startswith("HATA"), _mc2[:120])
sina("rapor.md'nin ustune YAZILMADI",
     (_kok_c / "rapor.md").read_text(encoding="utf-8") == "metin")

# 01.10 (gercek set G11): ajanin SECTIGI uretici duserse ofis otomatik siraya
# doner. Sira burada yalniz sahte uretici -- gercek codex uretimi KOSMAZ.
_asil_sira = _gor.TERCIH_SIRASI
_gor.TERCIH_SIRASI = ("sahtegorsel",)
try:
    _gm3 = ofis.tahta.gorev_ac("Logo", neden="n", ana_hedef="h", kabul_olcutu="k",
                               yazma_alani=["logo.png"], sahip="cinar")
    _mc3 = _ms.arac_gorsel_uret(_SahteOturum(ofis, "cinar", _gm3["no"]),
                                {"istem": "logo", "dosya_adi": "logo.png", "uretici": "openai"})
    sina("secilen ucretli uretici (para kilidi) dusunce OTOMATIK siraya donuldu",
         _mc3.startswith("Gorsel uretildi") and "otomatik sira" in _mc3, _mc3[:200])
    sina("  para kilidi yine korundu (ucretli kullanilmadi)", "openai" not in _mc3.split("\n")[1])
finally:
    _gor.TERCIH_SIRASI = _asil_sira

# --------------------------------------------------------------------------
print("\nSOHBETE_YAZ -- ajan takim sohbetine kendisi yazar (29.09)")
_ss = Sunucu({"OFIS_DB": str(db_yolu), "OFIS_PROJE": ofis.proje_id,
              "OFIS_AJAN": "cinar", "OFIS_GOREV": str(g["no"])})
_ss.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "t", "version": "1"}})
_ss.bildir("notifications/initialized", {})
_c = _ss.arac("sohbete_yaz", metin="api/ altinda eksik test buldum, ekliyorum", ajan="baskasi")
sina("bildirim yazildi", "yazildi" in _c, _c[:120])
with ofis.db.baglanti() as _cn:
    _r = _cn.execute("SELECT ajan_ad, govde FROM olay WHERE tur='ajan_sohbet' "
                     "ORDER BY rowid DESC LIMIT 1").fetchone()
sina("kimlik ORTAMDAN (argumandaki 'baskasi' yok sayildi)", _r and _r["ajan_ad"] == "cinar")
from ofis import takim as _tk  # noqa: E402
_akis = _tk.akis(ofis)
sina("takim akisinda 'bildirim' olarak gorunuyor",
     any(x["tur"] == "bildirim" and x["kimden"] == "cinar" for x in _akis))
sina("bos mesaj reddedilir", _ss.arac("sohbete_yaz", metin="  ").startswith("HATA"))
# EKLER (30.09): ajan sohbete DOSYA gonderir -- gercek sunucu surecinden.
_kok_s = Path(ofis.kok_klasoru())
(_kok_s / "cikti").mkdir(parents=True, exist_ok=True)
(_kok_s / "cikti" / "grafik.png").write_bytes(b"\x89PNG grafik")
_c = _ss.arac("sohbete_yaz", metin="grafik hazir", ekler=["cikti/grafik.png"])
sina("ekli bildirim yazildi", "1 dosya eklendi" in _c, _c[:160])
_x = [x for x in _tk.akis(ofis) if x["tur"] == "bildirim"][-1]
sina("balonda ek gorunuyor, metin temiz",
     _x["metin"] == "grafik hazir" and len(_x["ekler"]) == 1
     and (_kok_s / _x["ekler"][0]).read_bytes() == b"\x89PNG grafik", str(_x)[:200])
_c = _ss.arac("sohbete_yaz", metin="bak", ekler=["yok.png"])
sina("olmayan ek: HATA ve hicbir sey yazilmadi", _c.startswith("HATA") and "YAZILMADI" in _c, _c[:160])
for _i in range(10):
    _son = _ss.arac("sohbete_yaz", metin=f"bildirim {_i}")
sina("is basina ust sinir uygulaniyor", _son.startswith("HATA") and "6 kez" in _son, _son[:120])
with ofis.db.baglanti() as _cn:
    _n = _cn.execute("SELECT COUNT(*) FROM olay WHERE tur='ajan_sohbet' AND ajan_ad='cinar'").fetchone()[0]
sina("sinirdan fazlasi deftere GIRMEDI (ekli bildirim dahil)", _n == 6, str(_n))

print("\nAJANIN KENDI YENI DOSYASINI SILMESI SORULMAZ (01.10, gercek set G11)")
import time as _tm  # noqa: E402
_kk = Path(ofis.kok_klasoru())
_kk.mkdir(parents=True, exist_ok=True)
(_kk / "eski_dosya.txt").write_text("patronun", encoding="utf-8")
_tm.sleep(1.2)                                   # ctime saniye cozunurlugu
_gs = ofis.tahta.gorev_ac("Logo", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                          yazma_alani=["logo/"], sahip="cinar")
_tm.sleep(1.2)
(_kk / "preview.html").write_text("ara dosya", encoding="utf-8")
_so = _SahteOturum(ofis, "cinar", _gs["no"])
_so.proje_id = ofis.proje_id


def _izin(komut):
    return json.loads(_ms.arac_izin_sor(_so, {"tool_name": "Bash", "input": {"command": komut}}))


_iz1 = _izin(f"cd '{_kk.as_posix()}' && \\\nrm -f preview.html && \\\necho ok")
sina("isten SONRA yaratilan kendi dosyasini silmek SORULMADI", _iz1.get("behavior") == "allow",
     str(_iz1)[:200])
sina("  ve dosya gercekten silinebilir durumda (kanca izin verdi, komut ajanda)",
     (_kk / "preview.html").exists())
with ofis.db.baglanti() as _c:
    sina("  kayda gecti", bool(_c.execute(
        "SELECT 1 FROM olay WHERE tur='kendi_dosyasini_sildi'").fetchone()))
_iz2 = _izin("rm -f eski_dosya.txt")
sina("isten ONCE var olan dosyayi silmek SORULDU", _iz2.get("behavior") == "deny", str(_iz2)[:200])
_iz3 = _izin("rm -f preview.html eski_dosya.txt")
sina("hedeflerden biri eskiyse hepsi SORULUR", _iz3.get("behavior") == "deny", str(_iz3)[:200])
# 01.10 (G17, codex): ayni komut karalama/'da dosya yazip siliyor; dosya
# kapi sorulurken HENUZ YOK. karalama/ icindeki silme serbest.
_iz5 = _izin("$v = @'\nimport zipfile\nprint(f'OK: {p}')\n'@ | Set-Content -Encoding utf8 .ofis/karalama/none\nif (Test-Path .ofis/karalama/none) { Remove-Item .ofis/karalama/none }\npython karalama/x.py")
sina("karalama/'daki (henuz olmayan) yardimci dosyayi silmek SORULMADI",
     _iz5.get("behavior") == "allow", str(_iz5)[:200])
_iz6 = _izin("Remove-Item .ofis/karalama")
sina("  karalama klasorunun KENDISINI silmek SORULUR", _iz6.get("behavior") == "deny", str(_iz6)[:200])
_iz4 = _izin("rm -rf logo")
sina("ozyinelemeli silme SORULUR", _iz4.get("behavior") == "deny", str(_iz4)[:200])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
