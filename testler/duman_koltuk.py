# -*- coding: utf-8 -*-
"""Koltuk duman testi: halkanin gercekten donup donmedigi.

Sahte motorla kosar -- sinanan sey modelin zekasi degil KOORDINASYON:
kilit dogru anda aliniyor mu, basarisiz tur kilidi birakiyor mu, koltuk
kanit uyduruyor mu, yeni is temiz oturum aliyor mu.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, KoltukHatasi
from ofis.motor.sahte import SahteMotor
from ofis.tahta import KilitCakismasi

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


def reddetmeli(baslik, cagri, hata_sinifi):
    try:
        cagri()
        sina(baslik, False, "-- sessizce izin verildi!")
    except hata_sinifi:
        sina(baslik, True)


print("== koltuk duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-koltuk-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Koltuk Projesi", amac="Halkayi dondurmek",
                     basari_olcutu="Gorev kanitla incelemeye gidiyor",
                     kok_klasor=str(kok))
kanat = ofis.kanat_ac("URUN", "UR")

ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                  klasor=str(kok / "demir"), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", klasor=str(kok / "cinar"), motor="sahte")
ofis.kadro.ise_al("bilge", "arastirma", tur="kafa", klasor=str(kok / "bilge"),
                  motor="sahte")
ofis.kadro.ise_al("ayaz", "test", klasor="", motor="sahte")   # klasorsuz

#: Testin kontrolu elinde kalsin diye motoru biz uretiyoruz -- senaryo
#: degistirilebilsin.
kutu = {"senaryo": "basarili", "cevap": ""}


def sahte_fabrika(ad, **ayar):
    return SahteMotor(senaryo=kutu["senaryo"],
                      cevap=kutu["cevap"] or SahteMotor().cevap)


koltuk = Koltuk(ofis, motor_fabrikasi=sahte_fabrika)


def gorev_ac(baslik, alan):
    return ofis.tahta.gorev_ac(
        baslik, neden="Test", ana_hedef="Halka donsun",
        kabul_olcutu="Kanit gelsin", yazma_alani=alan, kanat_id=kanat,
    )


# --------------------------------------------------------------------------
print("1. BASARILI TUR -- kanit bildirildi, is incelemeye gitti")
g1 = gorev_ac("API yaz", ["api/"])
kutu["cevap"] = "Bitti.\nKANIT terminal: pytest -q -> 9 passed\nHepsi yesil."
ozet = koltuk.kos(g1["no"], "cinar")

sina("tur basarili", ozet["basarili"] is True)
sina("kanit tahtaya gecti", len(ofis.tahta.kanitlar(g1["no"])) == 1)
# Ozetteki sayi TAHTADAN gelmeli: MCP ile kanit ayri surecte eklenir ve
# akista gorunmez; akistan sayinca gercek kanit varken 0 yaziyordu.
sina("ozet kanit sayisi TAHTADAN okunuyor", ozet["kanit"] == 1,
     f"-- {ozet['kanit']}")
kanit = ofis.tahta.kanitlar(g1["no"])[0]
sina("kanit turu dogru okundu", kanit["tur"] == "terminal")
sina("kanit icerigi AJANIN sozu", "9 passed" in kanit["icerik"])
sina("kanit ekleyeni ajan", kanit["ekleyen"] == "cinar")
sina("gorev INCELEMEYE gitti",
     ofis.tahta.gorev(g1["no"])["durum"] == "inceleme")
sina("oturum kimligi kaydedildi (ajanin hafizasi)",
     bool(ofis.kadro.ajan("cinar")["oturum_id"]))
sina("ajan 'aktif' fazina gecti",
     ofis.kadro.ajan("cinar")["faz"] == "aktif")

with db.baglanti() as conn:
    turler = [r["tur"] for r in conn.execute(
        "SELECT tur FROM olay WHERE proje_id = ? ORDER BY id", (ofis.proje_id,)).fetchall()]
sina("brifing olayi kayitta", "brifing" in turler)
sina("cikti olaya dokuldu", "cikti" in turler)
sina("rapor kaydedildi", "rapor" in turler)
# Metin parcalari tek tek yazilmamali: 'cikti' satiri sayisi, kelime
# sayisindan cok kucuk olmali.
sina("metin parcalari tek tek YAZILMADI", turler.count("cikti") <= 2,
     f"-- {turler.count('cikti')} satir")

# --------------------------------------------------------------------------
print("\n2. KANIT UYDURULMUYOR -- ajan bildirmezse is incelemeye gitmez")
g2 = gorev_ac("Sepet ekrani", ["web/"])
kutu["cevap"] = "Hepsini yaptim, her sey calisiyor, guven bana."
ozet = koltuk.kos(g2["no"], "cinar")
sina("tur basarili ama...", ozet["basarili"] is True)
sina("KANIT YOK", ofis.tahta.kanitlar(g2["no"]) == [])
sina("gorev incelemeye GITMEDI, 'calisiyor' kaldi",
     ofis.tahta.gorev(g2["no"])["durum"] == "calisiyor")

# --------------------------------------------------------------------------
print("\n3. KILIT -- cakisma yutulmuyor, yukari birakiliyor")
g3 = gorev_ac("API'ye odeme ekle", ["api/odeme"])
# g1 incelemede; kilidi hala duruyor (lider geri gonderebilir).
reddetmeli("cakisan alan koltukta da REDDEDILIYOR",
           lambda: koltuk.kos(g3["no"], "demir"), KilitCakismasi)

# --------------------------------------------------------------------------
print("\n4. BASARISIZ TUR -- kilit birakiliyor, is yeniden dagitilabilir")
g4 = gorev_ac("Log duzelt", ["log/"])
kutu["senaryo"] = "hata"
ozet = koltuk.kos(g4["no"], "cinar")
sina("tur basarisiz", ozet["basarili"] is False)
sina("gorev 'hazir'a dondu", ofis.tahta.gorev(g4["no"])["durum"] == "hazir")
sina("KILIT BIRAKILDI (rehin kalmadi)",
     ofis.tahta.cakisan_kilitler(["log/"]) == [])
sina("sahip temizlendi", ofis.tahta.gorev(g4["no"])["sahip"] == "")

kutu["senaryo"] = "limit"
ozet = koltuk.kos(g4["no"], "cinar")
sina("limit de kilidi birakiyor", ofis.tahta.cakisan_kilitler(["log/"]) == [])
sina("limit ayri isaretlendi", ozet.get("limit") is True)

kutu["senaryo"] = "zaman_asimi"
ozet = koltuk.kos(g4["no"], "cinar")
sina("zaman asimi da kilidi birakiyor",
     ofis.tahta.cakisan_kilitler(["log/"]) == [])

kutu["senaryo"] = "basarili"

# --------------------------------------------------------------------------
print("\n5. KAFA YAZAMAZ -- yazma alanli is kafa ajana verilmiyor")
g5 = gorev_ac("Dosya yazan is", ["rapor/"])
reddetmeli("yazma alanli is kafa ajana reddediliyor",
           lambda: koltuk.kos(g5["no"], "bilge"), KoltukHatasi)

#: Motoru izleyen fabrika: koltugun motora NE verdigini sinayabilmek icin.
#: Sonucu degil CAGRIYI sinamak onemli -- kafa ajanin yazamamasi, motora
#: 'yazabilir=False' gitmesiyle saglanir; ciktiya bakarak anlasilamaz.
izler = []


def izleyen_fabrika(ad, **ayar):
    m = SahteMotor(senaryo=kutu["senaryo"], cevap=kutu["cevap"])
    izler.append(m)
    return m


izleyen_koltuk = Koltuk(ofis, motor_fabrikasi=izleyen_fabrika)

g6 = gorev_ac("Rakip arastir", [])       # yazma alani yok
kutu["cevap"] = "Arastirma bitti.\nKANIT baglanti: rakip raporu -> https://ornek"
ozet = izleyen_koltuk.kos(g6["no"], "bilge")
sina("alansiz is kafa ajana verilebiliyor", ozet["basarili"] is True)
sina("kafa ajan motora 'yazabilir=False' olarak gitti",
     izler[-1].cagrilar[-1]["yazabilir"] is False)

g6b = gorev_ac("Backend isi", ["backend/"])
kutu["cevap"] = "Bitti.\nKANIT dosya: backend/a.py -> yazildi"
izleyen_koltuk.kos(g6b["no"], "cinar")
sina("eller ajan motora 'yazabilir=True' olarak gitti",
     izler[-1].cagrilar[-1]["yazabilir"] is True)
sina("ajanin efor ayari motora gecti",
     izler[-1].cagrilar[-1]["efor"] == ofis.kadro.ajan("cinar")["efor"])

# --------------------------------------------------------------------------
print("\n6. KLASOR -- her ajan kendi klasorunde, klasorsuz ajan reddediliyor")
g7 = gorev_ac("Klasorsuz is", [])
reddetmeli("klasorsuz ajan reddediliyor",
           lambda: koltuk.kos(g7["no"], "ayaz"), KoltukHatasi)
sina("ajan klasoru olusturuldu", (kok / "cinar").is_dir())
_ok = Path(ofis.kok_klasoru())
sina("ekler/ ve karalama/ is basinda HAZIR (codex betigi oraya yazar, 01.10)",
     (_ok / "ekler").is_dir() and (_ok / "karalama").is_dir(), str(_ok))
from ofis.brifing import brifing_yolu as _by  # noqa: E402
sina("brifing kopyasi AJANA OZEL yerde (ofis evi)", _by(ofis.proje_id, "cinar").is_file())
sina("ortak koke / ajan klasorune BRIFING.md YAZILMADI (30.09)",
     not (kok / "cinar" / "BRIFING.md").exists() and not (kok / "BRIFING.md").exists())
sina("brifing kendi kopyasinin yolunu soyluyor",
     str(_by(ofis.proje_id, "cinar")) in izler[-1].cagrilar[-1]["metin"])

# --------------------------------------------------------------------------
print("\n7. TEMIZ OTURUM -- yeni is birikmis baglami tasimiyor (Yasa 4)")
g8 = gorev_ac("Yeni bagimsiz is", ["yeni/"])
kutu["cevap"] = "Tamam.\nKANIT dosya: yeni/x.py -> olusturuldu"
izleyen_koltuk.kos(g8["no"], "cinar")
cagri = izler[-1].cagrilar[-1]
sina("YENI is temiz oturumla basladi (oturum_id bos gitti)",
     cagri["oturum_id"] == "", f"-- '{cagri['oturum_id']}' gitti")
sina("yeni ise TAM brifing verildi (K1..K4)",
     all(k in cagri["metin"] for k in ("K1 —", "K2 —", "K3 —", "K4 —")))
# KANIT KANALI TEK OLMALI. Motor yetenegini kendi bildirir; koltuk ona
# gore secer. Ikisi birden acilirsa ayni is icin cift kanit duser
# (olculdu: 3 arac cagrisi + 3 metin satiri = 6 kanit).
sina("MCP konusmayan motora yapilandirma GONDERILMIYOR",
     cagri["mcp_yapilandirma"] == "")
sina("MCP konusmayan motorda metin koprusu CALISIYOR",
     len(ofis.tahta.kanitlar(g8["no"])) == 1)

import json as _json

mcpli_izler = []


def mcpli_fabrika(ad, **ayar):
    m = SahteMotor(senaryo=kutu["senaryo"], cevap=kutu["cevap"],
                   mcp_konusur=True)
    mcpli_izler.append(m)
    return m


g8b = gorev_ac("MCP konusan motorla is", ["mcpli/"])
kutu["cevap"] = "Tamam.\nKANIT dosya: mcpli/x.py -> olusturuldu"
Koltuk(ofis, motor_fabrikasi=mcpli_fabrika).kos(g8b["no"], "cinar")
mcagri = mcpli_izler[-1].cagrilar[-1]

_mcp = _json.loads(mcagri["mcp_yapilandirma"])
sina("MCP konusan motora yapilandirma uretildi", "ofis" in _mcp["mcpServers"])
# Hesaba bagli connector'lar gelmez -- olculdu: hepsi yuklendiginde tur
# brifingi okumadan 53.831 jetonda dusuyordu.
# 24.09.2026'dan beri tarayici her iste SERBEST verilir (yerel stdio
# sureci; hesaba dokunmaz). Sinanan sey ayni: hesabin baglayicilari YOK.
sina("yalniz YEREL sunucular var (ofis + tarayici), hesabin connector'lari yok",
     sorted(_mcp["mcpServers"]) == ["ofis", "tarayici"],
     str(list(_mcp["mcpServers"])))
_ortam = _mcp["mcpServers"]["ofis"]["env"]
sina("kimlik ORTAMA gomuldu (argumandan gelmiyor)",
     _ortam["OFIS_AJAN"] == "cinar" and _ortam["OFIS_GOREV"] == str(g8b["no"]))
sina("proje kimligi de gomuldu", _ortam["OFIS_PROJE"] == ofis.proje_id)
sina("MCP acikken metin koprusu KAPALI (cift kanit olmasin)",
     ofis.tahta.kanitlar(g8b["no"]) == [])

# --------------------------------------------------------------------------
print("\n8. DEVAM TURU -- ayni is surerken oturum korunur, fark verilir")
# g8 incelemede; lider geri gonderir -> ayni ajan ayni oturumda devam eder.
guncel = ofis.tahta.gorev(g8["no"])
ofis.tahta.geri_gonder(g8["no"], guncel["revizyon"],
                       gerekce="Kenar durumu eksik", gonderen="demir")
ofis.bellek.karar_yaz("Odeme saglayicisi Iyzico", "Kart orani en dusuk.", "demir")
kutu["cevap"] = "Duzelttim.\nKANIT terminal: pytest -q -> 11 passed"
izleyen_koltuk.kos(g8["no"], "cinar")
cagri = izler[-1].cagrilar[-1]
sina("DEVAM turunda oturum korundu", bool(cagri["oturum_id"]))
sina("devam turunda TAM brifing TEKRARLANMADI", "K1 —" not in cagri["metin"])
sina("devam turunda gorev fisi var", "K4 —" in cagri["metin"])
sina("devam turunda DEGISEN dunya verildi", "Iyzico" in cagri["metin"])
# Sabit sinir (1500) yerine ILK turun tam brifingine gore: gorev fisine
# eklenen her kural (01.10: `karalama/`) sabit siniri asiyordu; olculen
# sey ise 'devam tam brifingi tekrarlamiyor'.
_ilk = next(c["metin"] for _iz in reversed(izler) for c in _iz.cagrilar if "K1 —" in c["metin"])
sina("devam metni tam brifingden cok daha kisa (yarisindan az)",
     len(cagri["metin"]) < len(_ilk) / 2,
     f"-- devam {len(cagri['metin'])} / tam {len(_ilk)} karakter")

print("\nKAYNAK TUKENMESINDEN SONRA DEVAM -- is bastan kosmasin")
# OLCULDU (19.09.2026): arastirma turu butce tavanina takildi, `birak`
# calisti, gorev `hazir`a dondu ve sonraki tur SIFIRDAN kostu -- 17 arama,
# 208.148 jeton yeniden. Oysa model tarafinda oturum duruyordu.
#
# Ayrimi yapan sey SEBEPTIR: kaynak tukenmesi HATA degildir, is dogru
# gidiyordu. Gercek hatadan sonra devam etmek ayni hatali durumu tasimak
# olurdu -- orada temiz baslangic dogrudur.

_kok3 = Path(tempfile.mkdtemp(prefix="ofis-devam-"))
_db3 = Veritabani(_kok3 / "o.sqlite3")
_o3 = Ofis.proje_ac(_db3, "Devam", amac="a", basari_olcutu="b")
_k3 = _o3.kanat_ac("U", "U")
_o3.kadro.ise_al("cinar", "backend", kanat_id=_k3, tur="eller", motor="sahte",
                 klasor=str(_kok3 / "cinar"))
(_kok3 / "cinar").mkdir(exist_ok=True)

_kutu3 = {"ok": False, "maliyet": 0.0}


class _ButceliMotor(SahteMotor):
    butce_destegi = True

    def tur_kos(self, metin, **ayar):
        for _ol in super().tur_kos(metin, **ayar):
            if _ol.tur == "bitti":
                _ol.ek["maliyet_usd"] = _kutu3["maliyet"]
                _ol.ek["basarili"] = _kutu3["ok"]
            yield _ol


_kolt3 = Koltuk(_o3, motor_fabrikasi=lambda ad, **a: _ButceliMotor(cevap="calisiyorum"))


def _tur(no, ok, maliyet):
    _kutu3["ok"], _kutu3["maliyet"] = ok, maliyet
    return list(_kolt3.akit(no, "cinar", butce_usd=0.60))


def _ac(baslik, alan):
    _g = _o3.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k",
                            govde="ara", kanat_id=_k3, yazma_alani=[alan])
    return _g["no"]

# -- kaynak tukenmesi: DEVAM etmeli
_n1 = _ac("Arastirma", "rapor1/")
_tur(_n1, False, 0.62)                      # butce tavani asildi
with _db3.baglanti() as _c:
    _sebep = _c.execute(
        "SELECT govde FROM olay WHERE tur='birakildi' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()["govde"]
sina("butce tukenmesi SEBEP olarak yaziliyor", "butce" in _sebep, f"({_sebep})")
sina("butce tukenince is birakildi", _o3.tahta.gorev(_n1)["durum"] == "hazir")

_olaylar = _tur(_n1, True, 0.05)
_sahip = [x for x in _olaylar if x["tur"] == "sahiplenildi"]
_brif = [x for x in _olaylar if x["tur"] == "brifing"]
sina("kaynak tukenmesinden sonra DEVAM ediliyor",
     bool(_sahip) and _sahip[0]["ek"].get("devam") is True,
     f"({_sahip[0]['ek'] if _sahip else None})")
sina("devam turunda TAM brifing degil UYANIS FARKI veriliyor",
     bool(_brif) and "uyanis" in _brif[0]["govde"], f"({_brif[0]['govde'] if _brif else None})")
with _db3.baglanti() as _c:
    sina("devam turunda KILIT YENIDEN alindi",
         _c.execute("SELECT COUNT(*) n FROM yazma_kilidi").fetchone()["n"] > 0)

# -- gercek hata: devam ETMEMELI, temiz baslamali
_n2 = _ac("Ikinci is", "rapor2/")
_tur(_n2, False, 0.01)                      # butce dolmadi -- gercek hata
_olaylar2 = _tur(_n2, True, 0.01)
_sahip2 = [x for x in _olaylar2 if x["tur"] == "sahiplenildi"]
sina("GERCEK hatadan sonra devam EDILMIYOR (temiz baslangic)",
     bool(_sahip2) and not _sahip2[0]["ek"].get("devam"),
     f"({_sahip2[0]['ek'] if _sahip2 else None})")


# ---------------------------------------------------------------------------
# TEKRARLAYAN TAVAN KESINTISI GORUNUR OLMALI
#
# Olculdu (21.09.2026): kilavuz isi $0,60 tavanda UC KEZ ust uste
# kesildi. Her kesinti tek basina DOGRU davranisti -- para kontrolu
# calisti -- ama toplamda $2,02 hicbir teslimat uretmeden yandi ve
# dorduncu tur isi $0,16'ya bitirdi. Tavan bu is turu icin yanlisti ve
# bunu SOYLEYEN hicbir sey yoktu.
#
# Ofis tavani kendi YUKSELTMEZ: para karari insanindir. Ama gormedigi
# bir seyi insan yonetemez.
# ---------------------------------------------------------------------------
print("\n-- tekrarlayan tavan kesintisi gorunuyor mu --")

import json as _tvj
import tempfile as _tvtf
from pathlib import Path as _tvP
from ofis import Ofis as _tvOfis, Veritabani as _tvVt
from ofis.koltuk import Koltuk as _tvKoltuk

_tvkok = _tvP(_tvtf.mkdtemp(prefix="ofis-tavan-"))
_tvo = _tvOfis.proje_ac(_tvVt(_tvkok / "o.sqlite3"), "Tavan",
                        amac="a", basari_olcutu="b", kok_klasor=str(_tvkok))
_tvkn = _tvo.kanat_ac("URUN", "UR")
_tvo.kadro.ise_al("tv", "backend", kanat_id=_tvkn,
                  klasor=str(_tvkok), motor="sahte")
_tvg = _tvo.tahta.gorev_ac("tavan isi", neden="n", ana_hedef="h",
                           kabul_olcutu="k", yazma_alani=["api"],
                           kanat_id=_tvkn)
_tvk = _tvKoltuk(_tvo)


def _tavan_kesintisi_yaz(kacinci):
    """Bir tavan kesintisini ve turun maliyetini deftere dusur."""
    _tvo.db.olay_yaz(_tvo.proje_id, "tur_ozeti",
                     _tvj.dumps({"maliyet_usd": 0.60, "jeton": 1000}),
                     ajan_ad="tv", gorev_id=_tvg["id"])
    _tvo.db.olay_yaz(_tvo.proje_id, "birakildi",
                     f"#{_tvg['no']} birakildi: butce tavani doldu",
                     ajan_ad="tv", gorev_id=_tvg["id"])


_tavan_kesintisi_yaz(1)
_tvu = list(_tvk._tavan_uyarisi(_tvg["no"], _tvg, 0.60))
# ILK kesintide SESSIZ: her seye "sorun" diyen gosterge de
# gostergesizlikten farksizdir (saglik.py'nin kurali).
sina("ILK kesintide sessiz kaliyor", _tvu == [], f"({len(_tvu)} olay)")

_tavan_kesintisi_yaz(2)
_tvu = list(_tvk._tavan_uyarisi(_tvg["no"], _tvg, 0.60))
sina("IKINCI kesintide uyariyor", len(_tvu) == 1 and _tvu[0]["tur"] == "uyari",
     f"({_tvu})")
_gov = _tvu[0]["govde"] if _tvu else ""
# Uyari SAYIYI soylemeli: "bir sorun var" demek, gostergesizlikten
# yalnizca biraz iyidir.
sina("kacinci kesinti oldugunu SOYLUYOR", "2. kez" in _gov, f"({_gov[:80]})")
sina("bu ise giden TOPLAM parayi soyluyor", "$1.20" in _gov, f"({_gov[:110]})")
sina("olculen is turu profilini veriyor (care somut)",
     "arastirma" in _gov and "dokuman" in _gov)
# Ofis KARAR VERMEZ, DUZELTMEZ -- tavani kendi yukseltmez.
sina("kararin insana ait oldugunu soyluyor", "senindir" in _gov)


# ════════ BASARISIZ TUR SEBEBINI SOYLER ════════
#
# OLCULDU (21.09.2026), ilk gercek gemini turunda: tur `cikis 41` ile
# dustu ve defterde TEK BIR aciklama yoktu -- `tur_ozeti` butun alanlari
# `null`, `birakildi` yalnizca "tur basarisiz". Neden dustugu hicbir
# yerde yazmiyordu.
#
# Adaptor sebebi `bitti.ek["hata"]` icinde veriyordu (codex `hata`
# OLAYI da yaziyor, gemini yazmiyordu). Kural KOLTUGUN kurali oldugu
# icin duzeltme de burada: her adaptorde tekrarlanan bir kural en az
# birinde unutulur.
print("\nBASARISIZ TUR SEBEBINI SOYLUYOR MU")
from ofis.motor.tip import MotorOlayi as _MO


class _SessizDusen(SahteMotor):
    """Gemini'nin sekli: `hata` OLAYI yok, sebep yalniz `bitti.ek`te."""

    def tur_kos(self, metin, **ayar):
        yield _MO("basladi", "basladi", {"oturum_id": "z"})
        yield _MO("bitti", "", {
            "basarili": False, "cikis": 41, "sebep": "cikis",
            "hata": "Please set an Auth method ... GEMINI_API_KEY",
            "model": None, "jeton": None, "maliyet_usd": None,
        })


_gd = ofis.tahta.gorev_ac("sessizce dusen tur", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["sessiz/alan"])
Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: _SessizDusen()).kos(_gd["no"], "cinar")
with ofis.db.baglanti() as _c:
    _gid = _c.execute("SELECT id FROM gorev WHERE no = ?", (_gd["no"],)).fetchone()["id"]
    _hatalar = [r["govde"] for r in _c.execute(
        "SELECT govde FROM olay WHERE gorev_id = ? AND tur = 'hata'", (_gid,))]
sina("dusen tur GORUNUR bir hata olayi birakiyor", bool(_hatalar),
     "-- defterde sebep YOK, is neden dustu bilinmiyor")
sina("  sebep metni tasiniyor",
     any("GEMINI_API_KEY" in h for h in _hatalar), str(_hatalar)[:90])

# Ters yon: BASARILI turda gereksiz hata olayi UYDURULMAZ.
_gb = ofis.tahta.gorev_ac("basarili tur", neden="n", ana_hedef="h",
                          kabul_olcutu="k", yazma_alani=["basarili/alan"])
Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: SahteMotor(
    cevap="Bitti.\nKANIT dosya: x -> y")).kos(_gb["no"], "cinar")
with ofis.db.baglanti() as _c:
    _gid2 = _c.execute("SELECT id FROM gorev WHERE no = ?", (_gb["no"],)).fetchone()["id"]
    _n = _c.execute("SELECT COUNT(*) n FROM olay WHERE gorev_id = ? AND tur = 'hata'",
                    (_gid2,)).fetchone()["n"]
sina("basarili turda hata olayi YOK (uydurmuyor)", _n == 0, f"{_n} hata")


print("\nDURDURULAN IS SURDURULUNCE ajana ne oldugu soylenir (01.10, gercek set G16)")
_gd = gorev_ac("Durdurulan is", ["durdur/"])
ofis.db.olay_yaz(ofis.proje_id, "birakildi", f"#{_gd['no']} birakildi: insan durdurdu",
                 ajan_ad="cinar", gorev_id=_gd["id"])
_dm = koltuk._devam_metni(_gd["no"], "cinar")
sina("devam metni 'patron durdurdu, araclarin calisiyor' diyor",
     "DURDURULDU" in _dm and "araclarin calisiyor" in _dm, _dm[:200])
sina("durdurulmamis iste bu not YOK", "DURDURULDU" not in koltuk._devam_metni(g1["no"], "cinar"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
