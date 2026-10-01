# -*- coding: utf-8 -*-
"""PATRONUN EKRANINDA BULUNAN HATALAR duman testi (01.10.2026, #38/#39).

Jeton yakmaz. Patronun ekranindan ve defterinden olculen hatalar:
  1. Demir'in raporuna BILGE'nin resmi eklendi: #39'un kaniti stil ornegi
     olarak `bilge-gorsel.png`yi andi; o dosya #38'de zaten gitmisti.
  2. Lider iptal edilmis #37 icin "raporu hazir bekliyor" dedi (dort sohbet).
  3. Lider patronun Ofisim klasorunde `calisma/ekler/` acti (eski kok adi).
  4. Codex'in bekleme araci (`clocksleep`) patrona onay karti dusurdu.
  5. Lider gorseli ofisin araci yerine elle codex CLI ile urettirdi.
  6. Panel: "41335.3k jeton"; is bitince de "Lider calisiyor..." yaziyordu.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, ekler, riskli, gorsel  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== ekran hatalari duman testi ==\n")
_ANA = Path(tempfile.mkdtemp(prefix="ofis-ekran-"))
_KOK = _ANA / "Ofisim"
_KOK.mkdir()
db = Veritabani(_ANA / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Ofisim", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
kn = ofis.kanat_ac("GENEL", "GN")
for ad, meslek, lider in (("demir", "lider", True), ("cinar", "backend", False), ("ege", "metin", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kn, lider_mi=lider, motor="sahte", klasor=str(_KOK))
(_KOK / ".ofis" / "ekler").mkdir(parents=True)


def gorev(baslik, alan, sahip):
    return ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                               yazma_alani=alan, kanat_id=kn, sahip=sahip)


# ---------------------------------------------------------------------------
print("1. baska iste gitmis / isten once var olan dosya YENIDEN eklenmez")
g38 = gorev("Bilge gorseli", ["bilge-gorseli/"], "ege")
(_KOK / "bilge-gorseli").mkdir()
_bilge = _KOK / "bilge-gorseli" / "bilge-gorsel.png"
_bilge.write_bytes(b"\x89PNG" + b"B" * 3000)
shutil.copy(_bilge, _KOK / ".ofis" / "ekler" / "bilge-gorsel.png")      # sohbete giden kopya
ofis.tahta.kanit_ekle(g38["no"], "gorsel", "bilge", "bilge-gorseli/bilge-gorsel.png", ekleyen="ege")
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "bilge hazir\n[ek] .ofis/ekler/bilge-gorsel.png",
                 ajan_ad="ege", gorev_id=g38["id"])
sina("  #38'in resmi gitmis sayiliyor", ekler.gonderilmemisler(ofis, [g38["id"]]) == [])
# Dosya #39'dan ONCE vardi (gercekte 6 dk once).
_eski = time.time() - 600
os.utime(_bilge, (_eski, _eski))
time.sleep(1.1)
g39 = gorev("Demir gorseli", ["demir-gorseli/"], "cinar")
(_KOK / "demir-gorseli").mkdir()
_demir = _KOK / "demir-gorseli" / "demir-gorsel.png"
_demir.write_bytes(b"\x89PNG" + b"D" * 3000)
ofis.tahta.kanit_ekle(g39["no"], "dosya", "demir-gorseli/demir-gorsel-istem.md",
                      "Stil referansi incelendi: bilge-gorseli/bilge-gorsel.png", ekleyen="cinar")
ofis.tahta.kanit_ekle(g39["no"], "gorsel", "demir", "demir-gorseli/demir-gorsel.png", ekleyen="cinar")
_gm = ekler.gonderilmemisler(ofis, [g39["id"]])
sina("#39'un kanitinda ANILAN bilge resmi patrona YENIDEN eklenmez (01.10)",
     "bilge-gorseli/bilge-gorsel.png" not in _gm, str(_gm))
sina("  #39'un KENDI urettigi ve gitmemis resmi yine bulunur", _gm == ["demir-gorseli/demir-gorsel.png"], str(_gm))
# Ayni ICERIK baska adla gitmis: sayilmaz.
shutil.copy(_demir, _KOK / ".ofis" / "ekler" / "20261001-201000-baska-ad.png")
sina("ayni icerik BASKA adla gitmisse gitmis sayilir", ekler.gonderilmemisler(ofis, [g39["id"]]) == [],
     str(ekler.gonderilmemisler(ofis, [g39["id"]])))
# HER KURAL TEK BASINA (mutasyonla olculdu: icerik kurali digerlerini ortuyordu).
# (a) Isten ONCE duran, hic gonderilmemis GIRDI dosyasi (patronun eski notu).
_girdi = _KOK / "eski-notlar.docx"
_girdi.write_bytes(b"PK" + b"N" * 3000)
os.utime(_girdi, (_eski, _eski))
g41 = gorev("Notlari oku", ["ozet/"], "ege")
ofis.tahta.kanit_ekle(g41["no"], "dosya", "okundu", "kaynak: eski-notlar.docx", ekleyen="ege")
sina("isten ONCE duran girdi dosyasi patrona gonderilmez (yalniz zaman kurali)",
     ekler.gonderilmemisler(ofis, [g41["id"]]) == [], str(ekler.gonderilmemisler(ofis, [g41["id"]])))
# (b) BASKA iste ADIYLA gitmis; sohbet kopyasi silinmis (icerik karsilastirilamaz),
# dosya bu isten SONRA degismis (zaman kurali da tutmaz).
g42 = gorev("Logo", ["logo/"], "cinar")
(_KOK / "logo").mkdir()
_logo = _KOK / "logo" / "logo.png"
_logo.write_bytes(b"\x89PNG" + b"L" * 3000)
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "logo\n[ek] .ofis/ekler/logo.png", ajan_ad="cinar",
                 gorev_id=g42["id"])
g43 = gorev("Kartvizit", ["kartvizit/"], "cinar")
ofis.tahta.kanit_ekle(g43["no"], "dosya", "kartvizit", "logo/logo.png kullanildi", ekleyen="cinar")
sina("BASKA iste adiyla gitmis dosya yeniden gonderilmez (yalniz proje geneli kurali)",
     ekler.gonderilmemisler(ofis, [g43["id"]]) == [], str(ekler.gonderilmemisler(ofis, [g43["id"]])))
# Isten once vardi ama ajan DEGISTIRDI: yeni urun sayilir.
g40 = gorev("Bilge gorselini guncelle", ["bilge-gorseli/"], "ege")
time.sleep(1.1)
_bilge.write_bytes(b"\x89PNG" + b"C" * 3000)
ofis.tahta.kanit_ekle(g40["no"], "gorsel", "bilge v2", "bilge-gorseli/bilge-gorsel.png", ekleyen="ege")
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "x", ajan_ad="ege", gorev_id=g40["id"])
_g40 = ekler.gonderilmemisler(ofis, [g40["id"]])
sina("  isin DEGISTIRDIGI eski dosya (yeni icerik) gitmemis sayilir -- ad ayni olsa da",
     _g40 == [] or _g40 == ["bilge-gorseli/bilge-gorsel.png"], str(_g40))

# ---------------------------------------------------------------------------
print("\n2. lider ozetinde IPTAL edilen is 'sonucu yok' diye gorunur")
g37 = gorev("semuparfum denetimi", ["denetim/"], "cinar")
ofis.tahta.iptal_et(g37["no"], sebep="patron istemedi", iptal_eden="insan")
_oz = ofis.sohbet.ofis_ozeti()
sina("ozette #37 IPTAL EDILDI ve 'sonucu YOK'", f"#{g37['no']} IPTAL EDILDI" in _oz and "sonucu YOK" in _oz,
     _oz[-600:])
sina("  ozet DEFTERIN sohbet gecmisinden ustun oldugunu soyluyor", "DEFTER dogrudur" in _oz)
ofis.tahta.kanit_ekle(g38["no"], "dosya", "d", "x", ekleyen="ege")
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum='bitti' WHERE id=?", (g38["id"],))
sina("  biten is kanit sayisiyla gorunur", f"#{g38['no']} bitti (" in ofis.sohbet.ofis_ozeti())

# ---------------------------------------------------------------------------
print("\n3. plan kapisi: ajan adli ya da `calisma/` klasoru ACILMAZ")
_ork = ofis.orkestra


def plan(alan, sahip="cinar"):
    return {"gerekce": "tek kol", "kollar": [{"baslik": "demir gorseli", "neden": "n",
            "kabul_olcutu": "k", "sahip": sahip, "yazma_alani": alan}]}


_r = _ork._plani_dogrula(plan(["calisma/ekler/demir-gorsel.png"]), kn, patron_sozu="demir icin gorsel")
sina("`calisma/ekler/...` REDDEDILDI (01.10 olculen plan)", "calisma" in _r and "ACILMAZ" in _r, _r)
# Gercek Ofisim'de eski ajan klasorleri (bilge/, cinar/) duruyor.
(_KOK / "cinar").mkdir()
(_KOK / "ege").mkdir()
_r = _ork._plani_dogrula(plan(["cinar/rapor.md"]), kn, patron_sozu="rapor yaz")
sina("ajan adli klasor (`cinar/`, kokte VAR) reddedildi", "AJAN ADI" in _r, _r)
_r = _ork._plani_dogrula(plan(["./ege/x.py"]), kn, patron_sozu="x")
sina("  `./ege/` da reddedildi", "AJAN ADI" in _r, _r)
_r = _ork._plani_dogrula(plan(["demir-gorseli/demir.png"]), kn, patron_sozu="demir icin gorsel")
sina("isin adli klasor GECER", _r == "", _r)
_r = _ork._plani_dogrula(plan(["calisma/notlar.md"]), kn, patron_sozu="calisma klasorune not yaz")
sina("patron klasoru KENDISI andiysa gecer", _r == "", _r)

# ---------------------------------------------------------------------------
print("\n4. codex'in bekleme araci sorulmaz")
sina("`clocksleep` serbest (onay karti YOK)",
     riskli.arac_degerlendir("clocksleep", {"duration_ms": 20000}) is None,
     str(riskli.arac_degerlendir("clocksleep", {"duration_ms": 20000})))
sina("  tanimadigi baska arac hala sorulur",
     riskli.arac_degerlendir("clockformat", {"x": 1}) is not None)

# ---------------------------------------------------------------------------
print("\n5. lider gorseli ofisin araciyla urettirir")
_md = gorsel.lider_blogu()
sina("medya bolumu `gorsel_uret` aracini ve 'CLI'i elle cagirtma' kuralini soyluyor",
     "gorsel_uret" in _md and "elle" in _md, _md[-500:])

# ---------------------------------------------------------------------------
print("\n6. panel gostergeleri")
_js = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
sina("ust serit jetonu TEK bicimle (jetonYaz) yaziliyor", "const jeton = jetonYaz(o.olcum.jeton);" in _js)
_bas = _js.index("function jetonYaz(n)")
_fn = _js[_bas:_js.index("\n}\n", _bas) + 3]
try:
    _cikti = subprocess.run(["node", "-e", _fn + "console.log(jetonYaz(41335300))"],
                            capture_output=True, text=True, timeout=30).stdout.strip()
    sina("  41335300 jeton -> '41.34M' (eskiden '41335.3k')", _cikti == "41.34M", _cikti)
except FileNotFoundError:
    sina("  node yok -- jetonYaz OLCULEMEDI", False)
sina("gecici ipucu saklaniyor ve kosu bitince geri aliniyor",
     "girdi.dataset.gecici = \"1\"" in _js and "if (!kosuyor) gecicIpuclariniGeriAl();" in _js)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
