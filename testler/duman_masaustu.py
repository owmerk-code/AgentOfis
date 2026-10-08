# -*- coding: utf-8 -*-
"""MASAUSTU KULLANIMI (D1, 08.10.2026) -- kapi, onay akisi, fren, gorsel donus.

Gercek masaustu SURULMEZ (patron kurali: canli masaustu onaysiz surulmez;
sinama patron oyundayken de kosar): `ofis.masaustu`nun dusuk duzey
islevleri sahteyle degistirilir, gerisi (riskli olcutu, tek kapi, postane,
MCP protokolu) gercek. Gercek dusuk duzeyden yalniz OKUMA sinanir (tus
cozumu, koordinat cevirisi).
"""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import base64
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani, riskli as R  # noqa: E402
from ofis import masaustu as MS  # noqa: E402
from ofis import mcp_sunucu as M  # noqa: E402
from ofis.postane import Postane  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("1. olcut (riskli.masaustu_degerlendir)")
d = R.masaustu_degerlendir
b_bak = d("bak")
b_dosya = d("tikla", oge={"ad": "Dosya", "tur": "MenuItem"}, pencere={"baslik": "Belge - Not Defteri", "uygulama": "notepad.exe"})
sina("ekrana bakmak da SORULUR (masaustu sinifi)", b_bak["sinif"] == "masaustu" and b_bak["sorulur"])
sina("siradan tiklama masaustu; imzasi bakmakla AYNI ('bu is boyunca' hepsini acar)",
     b_dosya["sinif"] == "masaustu" and Postane.imza(b_bak) == Postane.imza(b_dosya))
for ad, oge, beklenen in (
        ("Gonder dugmesi", {"ad": "Gönder", "tur": "Button"}, "gonderim"),
        ("Send", {"ad": "Send", "tur": "Button"}, "gonderim"),
        ("Sil", {"ad": "Sil", "tur": "Button"}, "silme"),
        ("Satin al", {"ad": "Satın al", "tur": "Button"}, "para"),
        ("Yayinla", {"ad": "Yayınla", "tur": "Button"}, "yayin")):
    b = d("tikla", oge=oge, pencere={"baslik": "Uygulama", "uygulama": "app.exe"})
    sina(f"'{ad}' tiklamasi -> {beklenen} (her seferinde sorulur)", b["sinif"] == beklenen, b["sinif"])
b_gon = d("tikla", oge={"ad": "Gönder", "tur": "Button"}, pencere={"baslik": "Posta", "uygulama": "outlook.exe"})
sina("riskli dugmenin imzasi siradan masaustu onayindan AYRI",
     Postane.imza(b_gon) != Postane.imza(b_bak))
sina("odak 'Gonder'deyken Enter -> gonderim",
     d("tus", oge={"ad": "Gönder", "tur": "Button"}, tuslar="enter")["sinif"] == "gonderim")
sina("odak siradan alandayken Enter -> masaustu",
     d("tus", oge={"ad": "Arama", "tur": "Edit"}, tuslar="enter")["sinif"] == "masaustu")
sina("shift+delete -> silme (kalici)", d("tus", tuslar="shift+delete")["sinif"] == "silme")
sina("sifre alanina yazmak -> kimlik, deger karta GIRMEZ",
     (lambda b: b["sinif"] == "kimlik" and "gizli123" not in json.dumps(b))(
         d("yaz", oge={"ad": "Parola", "tur": "Edit", "sifre": True}, metin="gizli123")))
sina("adi 'Password' olan alan da kimlik",
     d("yaz", oge={"ad": "Password", "tur": "Edit"}, metin="x")["sinif"] == "kimlik")
b = d("uygulama_ac", uygulama="powershell")
sina("terminal acmak REDDEDILIR (kendi kabugu var, kapiyi atlatmaz)", b.get("ret") is True, str(b)[:120])
b = d("yaz", oge={"ad": "x", "tur": "Edit"}, pencere={"baslik": "Yonetici: cmd", "uygulama": "cmd.exe"},
      metin="del /s *")
sina("terminal penceresine yazmak REDDEDILIR", b.get("ret") is True)
sina("not defteri acmak SORULUR, reddedilmez",
     (lambda b: b["sinif"] == "masaustu" and not b.get("ret"))(d("uygulama_ac", uygulama="notepad")))

print("\n2. dusuk duzey (okuma)")
sina("tus cozumu: ctrl+shift+s", MS.tus_birlesimi("ctrl+shift+s") == [0x11, 0x10, ord("S")])
try:
    MS.tus_birlesimi("ctrl+uydurma")
    sina("tanimsiz tus HATA verir", False)
except MS.MasaustuHatasi:
    sina("tanimsiz tus HATA verir", True)
g = MS.Goruntu("x.png", 1568, 882, 0, 0, 1920 / 1568, time.time())
sina("goruntu pikseli -> ekran pikseli (olcekli)", g.ekrana(784, 441) == (960, 540), str(g.ekrana(784, 441)))
try:
    g.ekrana(2000, 10)
    sina("goruntu disi koordinat HATA", False)
except MS.MasaustuHatasi:
    sina("goruntu disi koordinat HATA", True)

print("\n3. tek kapi + onay akisi (dusuk duzey SAHTE)")
D = Path(tempfile.mkdtemp(prefix="ofis-masaustu-"))
db = Veritabani(D / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Masaustu", amac="a", basari_olcutu="b", kok_klasor=str(D))
ofis.kadro.ise_al("lale", "lider", lider_mi=True, motor="sahte", klasor=str(D))
ofis.kadro.ise_al("ece", "bilgisayar", motor="sahte", klasor=str(D))
gr = ofis.tahta.gorev_ac("excel raporu", neden="n", ana_hedef="h", kabul_olcutu="k")
gr = ofis.tahta.sahiplen(gr["no"], "ece", gr["revizyon"])


class _Oturum:
    def __init__(self, ajan, no):
        self.ofis, self.ajan_ad, self.gorev_no, self.proje_id = ofis, ajan, no, ofis.proje_id
        self.kanat = ""

    def gorev(self):
        return ofis.tahta.gorev(self.gorev_no)


YAPILAN = []
_PATRON = [False]
_OGE = [{"ad": "Kaydet", "tur": "Button"}]


def _sahte_goruntu(hedef, **k):
    from PIL import Image
    Path(hedef).parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 90), (20, 40, 60)).save(hedef)
    return MS.Goruntu(str(hedef), 160, 90, 0, 0, 12.0, time.time())


MS.goruntu_al = _sahte_goruntu
MS.pencereler = lambda azami=40: [{"hwnd": 7, "baslik": "Rapor.xlsx - Excel", "uygulama": "EXCEL.EXE",
                                   "kutu": [0, 0, 1920, 1080], "simge": False, "onde": True}]
MS.on_pencere = lambda: MS.pencereler()[0]
MS.ogeler = lambda hwnd, azami=150: [{"ad": "Kaydet", "tur": "Button", "kutu": [100, 100, 140, 120], "etkin": True}]
MS.oge_noktada = lambda x, y: dict(_OGE[0])
MS.odak_ogesi = lambda: {"ad": "Hucre A1", "tur": "Edit"}
MS.patron_etkin_mi = lambda pay_ms=400: _PATRON[0]
MS.tikla = lambda x, y, **k: YAPILAN.append(("tikla", x, y, k))
MS.yaz = lambda metin: YAPILAN.append(("yaz", metin))
MS.tus = lambda t: YAPILAN.append(("tus", t))
M._MASAUSTU.update(goruntu=None, sayac=0)

O = _Oturum("ece", gr["no"])


def onaylar():
    with db.baglanti() as c:
        return c.execute("SELECT id, eylem, durum FROM onay ORDER BY rowid").fetchall()


r = M.arac_masaustu_bak(O, {})
sina("ilk bakis: ONAY ISTENDI, ekran ALINMADI",
     isinstance(r, str) and "ONAY ISTENDI" in r and M._MASAUSTU["goruntu"] is None and len(onaylar()) == 1, str(r)[:160])
r = M.arac_masaustu_bak(O, {})
sina("onay beklerken ikinci deneme yeni kart ACMAZ", "ZATEN BEKLIYOR" in str(r) and len(onaylar()) == 1)
ofis.postane.onay_cevapla(onaylar()[0][0], onayla=True, kapsam="is")
r = M.arac_masaustu_bak(O, {})
sina("'bu is boyunca' onayindan sonra bakis: goruntu + pencere + ogeler",
     isinstance(r, dict) and Path(r["gorseller"][0]).is_file() and "Excel" in r["metin"]
     and "Kaydet" in r["metin"], str(r)[:200])
sina("goruntu isin karalama klasorunde (.ofis/karalama/masaustu)",
     isinstance(r, dict) and ".ofis" in r["gorseller"][0].replace("\\", "/") and "masaustu" in r["gorseller"][0])
r = M.arac_masaustu_eylem(O, {"eylem": "tikla", "x": 10, "y": 9, "bak": False})
sina("siradan tiklama ayni onayla SORULMADAN gecti, koordinat olcekle cevrildi",
     str(r).startswith("YAPILDI") and YAPILAN and YAPILAN[-1][:3] == ("tikla", 120, 108), str(r)[:160])
_OGE[0] = {"ad": "Gönder", "tur": "Button"}
n = len(YAPILAN)
r = M.arac_masaustu_eylem(O, {"eylem": "tikla", "x": 10, "y": 9})
sina("'Gonder' dugmesi siradan onayla ACILMAZ: yeni kart, tiklama YOK",
     "ONAY ISTENDI" in str(r) and len(YAPILAN) == n and len(onaylar()) == 2, str(r)[:160])
_OGE[0] = {"ad": "Kaydet", "tur": "Button"}
_PATRON[0] = True
r = M.arac_masaustu_eylem(O, {"eylem": "yaz", "metin": "Toplam"})
sina("patron klavye/fareyi kullaniyorsa eylem YAPILMAZ", "PATRON SU AN" in str(r) and len(YAPILAN) == n, str(r)[:120])
_PATRON[0] = False
r = M.arac_masaustu_eylem(O, {"eylem": "yaz", "metin": "Toplam"})
sina("yazi gecti ve sonraki ekran goruntusu dondu",
     isinstance(r, dict) and YAPILAN[-1] == ("yaz", "Toplam") and r["gorseller"], str(r)[:160])
M._MASAUSTU["goruntu"].zaman -= M.MASAUSTU_GORUNTU_OMRU_SN + 5
r = M.arac_masaustu_eylem(O, {"eylem": "tikla", "x": 10, "y": 9})
sina("eski goruntuyle tiklanmaz", "eski" in str(r) and YAPILAN[-1][0] == "yaz", str(r)[:120])
r = M.arac_masaustu_eylem(O, {"eylem": "uygulama_ac", "uygulama": "cmd"})
sina("terminal acma REDDI (kart acilmaz)", str(r).startswith("HATA") and "kabugun" in str(r) and len(onaylar()) == 2)
with db.baglanti() as c:
    olaylar = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'masaustu'")]
sina("yapilan her masaustu eylemi deftere yazildi (bak, tikla, yaz)",
     any(x.startswith("bak") for x in olaylar) and any(x.startswith("tikla") for x in olaylar)
     and any(x.startswith("yaz") for x in olaylar), str(olaylar)[:200])
ofis.kadro.ise_al("mert", "bilgisayar", motor="sahte", klasor=str(D))
gm = ofis.tahta.gorev_ac("mertin isi", neden="n", ana_hedef="h", kabul_olcutu="k")
gm = ofis.tahta.sahiplen(gm["no"], "mert", gm["revizyon"])
OM = _Oturum("mert", gm["no"])
r = M.arac_masaustu_bak(OM, {})
_kart = [x for x in onaylar() if x[2] == "bekliyor"][-1]
ofis.postane.onay_cevapla(_kart[0], onayla=True, kapsam="is")
M.arac_masaustu_bak(OM, {})
n = len(YAPILAN)
r = M.arac_masaustu_eylem(OM, {"eylem": "yaz", "metin": "x", "bak": False})
sina("TEK SURUCU: ece suruyorken mert'in eylemi YAPILMAZ, kim surdugu soylenir",
     "ece" in str(r) and "KULLANIYOR" in str(r) and len(YAPILAN) == n, str(r)[:140])
sina("kira sahibi susarsa (5 dk) duser",
     MS.kira_al("mert (#9)", simdi=time.time() + MS.KIRA_SN + 1) is None)
MS.kira_birak("mert (#9)")
gi = ofis.tahta.gorev_ac("baska is", neden="n", ana_hedef="h", kabul_olcutu="k")
gi = ofis.tahta.sahiplen(gi["no"], "ece", gi["revizyon"])
r = M.arac_masaustu_bak(_Oturum("ece", gi["no"]), {})
sina("onay ISE bagli: baska iste yeniden sorulur", "ONAY ISTENDI" in str(r), str(r)[:120])

print("\n4. izin_sor ayni karar yolunu kullaniyor (ortak isleve ayrildi)")
r = json.loads(M.arac_izin_sor(O, {"tool_name": "Bash", "input": {"command": "git push"}}))
sina("izin_sor hala soruyor (git push)", r["behavior"] == "deny" and "ONAY ISTENDI" in r["message"], str(r)[:160])
r = json.loads(M.arac_izin_sor(O, {"tool_name": "Bash", "input": {"command": "ls"}}))
sina("izin_sor serbesti geciriyor (ls)", r["behavior"] == "allow")

print("\n5. MCP protokolu: gorsel ICERIK doner")
o_es = M.Oturum()
o_es.db_yolu, o_es.proje_id, o_es.ajan_ad, o_es.gorev_no = str(D / "o.sqlite3"), ofis.proje_id, "ece", gr["no"]
cevap = M.istegi_isle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "masaustu_bak", "arguments": {}}}, o_es)
icerik = (cevap or {}).get("result", {}).get("content", [])
gorsel = [c for c in icerik if c.get("type") == "image"]
sina("tools/call sonucunda metin + PNG gorsel blogu",
     icerik and icerik[0]["type"] == "text" and gorsel and gorsel[0]["mimeType"] == "image/png"
     and base64.b64decode(gorsel[0]["data"])[:4] == b"\x89PNG", str(cevap)[:200])
adlar = [a["name"] for a in M.ARACLAR]
sina("araclar listede", "masaustu_bak" in adlar and "masaustu_eylem" in adlar)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
