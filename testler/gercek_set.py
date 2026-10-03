# -*- coding: utf-8 -*-
"""GERCEK SET -- patron gibi SOHBETTEN is verip ucu ucuna olcen gece seti.

    python testler/gercek_set.py --motor claude            # butun isler
    python testler/gercek_set.py --motor codex --is G01    # secili is
    python testler/gercek_set.py --kuru                    # $0: dogrulayicilar

Neden var (30.09.2026): 3295 duman sinamasi geciyordu, ama kullanici tek bir
"siteyi ac, ekran goruntusu at" isini denediginde on yerden takildi: lider
"yapamam, sen at" dedi; sohbete bes uzun ic mesaj dustu; is gereksiz yere
iki kez geri gonderildi; rapor "Once dosyaya bakiyorum" ve "KANIT dosya:"
satiriyla geldi. Eski deneme seti (`deneme.py`) isi dogrudan TAHTAYA acar;
bu hatalarin hicbirini goremez. Bu set patronun yolunu yurur:

    sohbet mesaji -> liderin triyaji -> plan -> ajanlar (gercek terminal)
    -> inceleme -> patrona TEK rapor

ve iki seyi olcer:

1. **Sonuc** -- diskteki cikti, sohbetteki ek, liderin cevabi (modelin
   SOZUNE degil, dosyaya ve deftere bakilarak).
2. **Kalite** -- sohbet temiz mi (mesaj sayisi), gereksiz ret var mi, lider
   "yapamam" dedi mi, rapor ic konusma / KANIT satiri tasiyor mu, sure.

Her is BOS bir gecici ofiste kosar (gercek ofise, kasaya dokunmaz), ucuz
modelle. Kural (kullanici, 30.09): gercek motorla gercek iste gecmeyen
ozellik "bitti" sayilmaz. Rapor: `testler/rapor/gercek-<zaman>-<motor>.md`.

**Kuru kip** her isin iyi ve kotu sonucunu elle kurar: dogrulayici iyiye
GECTI, kotuye KALDI demeli. Olcum aracinin kendisi de olculur.
"""

from __future__ import annotations

import os as _os
from pathlib import Path as _Path

# Gercek hesaplar (codex girisi ofisin evinde): kok gercek kalir -- ayni
# gerekce deneme.py'de. Kuru kipte `_temizlik` kokunu gecici klasore ceviren
# duman sinamasi bunu once ice aktarir.
# Gercek ev TEK kuraldan (01.10: `Masaustu\AgentOfis\ev`, yoksa eski).
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from ofis.yollar import varsayilan_ev as _varsayilan_ev  # noqa: E402
_os.environ.setdefault("OFIS_EV", str(_varsayilan_ev()))

import _temizlik  # noqa: F401,E402 -- gecici klasorleri siler

import argparse
import datetime as _dt
import html.parser
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ofis import Ofis, Veritabani, takim, ekler as _ekler   # noqa: E402
from deneme_isler import Sunucu, _ozet, _pytest, _yaz      # noqa: E402
from deneme import _kullaniciya_ac, kota_oku, kota_farki   # noqa: E402

RAPOR = Path(__file__).resolve().parent / "rapor"

#: Motor basina ucuz modeller (kota). Lider biraz daha guclu: triyaj ve
#: plan onun isi, ucuz liderin hatasi butun seti yaniltir.
MODELLER = {"claude": {"lider": "sonnet", "isci": "haiku"},
            "codex": {"lider": "gpt-6-luna", "isci": "gpt-6-luna"}}
#: KARMA (03.10.2026, `ofis/karne`): kadro Claude ayariyla kurulur; isin
#: motorunu karne secer (Claude ya da Codex), inceleme CAPRAZ kosar.
MODELLER["karma"] = dict(MODELLER["claude"])

#: Kadro -- genel amacli bir ofisin cekirdegi.
KADRO = (("cem", "backend"), ("ada", "arayuz"), ("su", "arastirma"))

#: Sohbet temizligi: patronun mesaji + liderin cevabi/raporu + en fazla bu
#: kadar ajan bildirimi/onay karti.
SOHBET_EK_PAYI = 2

#: Liderin "yapamam, sen yap" kalibi (30.09 olculdu, iki motorda).
_YAPAMAM = re.compile(r"\byapamam\b|alam[iı]yorum|a[cç]am[iı]yorum|eri[sş]emiyorum"
                      r"|sen (?:at|yap|ekle|gonder|gönder)", re.I)
#: Raporda patrona gitmemesi gereken ic kalip.
#: KANIT satiri: makine bicimi ("KANIT dosya: a.png -> ...") -- ajanin defter
#: satiri. Sade "Kanıt: goruntu sohbette" cumlesi patrona uygun, sayilmaz.
_IC_KONUSMA = re.compile(r"(?im:^\s*(?:Önce|Once|Şimdi|Simdi)\b.*(?:bak[iı]yorum|"
                         r"kontrol ediyorum|okuyorum))|(?m:^\s*KANIT\s+\S+\s*:)"
                         r"|(?m:^\s*DURUM:)"
                         r"|(?i:ara[cç](?:[iı]m)?\s+kapal[iı]|ko[sş]turamad[iı]m|[cç]al[iı][sş]t[iı]ramad[iı]m)")


# ---------------------------------------------------------------- yardimci

def _norm(s: str) -> str:
    tablo = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    return (s or "").translate(tablo).lower()


def _son_lider(ofis) -> str:
    ak = [x for x in takim.akis(ofis) if x["kimden"] == "lale"]
    return ak[-1]["metin"] if ak else ""


def _sohbet_gorselleri(kok: Path, ofis) -> list:
    yollar = []
    for x in takim.akis(ofis):
        for y in x.get("ekler") or []:
            p = kok / y
            if p.suffix.lower() in _ekler.GORSEL and p.is_file() and p.stat().st_size > 1024:
                yollar.append(y)
    return yollar


def _gorev_sayisi(ofis) -> int:
    return len(ofis.tahta.liste())


def _html_gecerli(metin: str) -> bool:
    try:
        p = html.parser.HTMLParser()
        p.feed(metin)
        p.close()
        return True
    except Exception:
        return False


def _py_calistir(kok: Path, kod: str) -> str:
    r = subprocess.run([sys.executable, "-c", kod], cwd=kok, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    return (r.stdout or "").strip() if r.returncode == 0 else f"HATA: {r.stderr[-200:]}"


def _lider_cevapla(ofis, metin: str) -> None:
    """Kuru kip: liderin patrona cevabini deftere yazar (gercekte sohbet yazar)."""
    m = ofis.postane.soru_sor("insan", "lale", "kuru", mod="uyandiran")
    ofis.postane.cevapla(m["id"], metin, cevaplayan="lale")


def _ajan_gorsel(kok: Path, ofis, ad: str = "ekran.png") -> None:
    p = kok / ad
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 4096)
    y = _ekler.paylas(ofis, ad, ajan_ad="cem")
    ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "ekte\n" + _ekler.satirlar([y]),
                     ajan_ad="cem")


# ================================================================== isler
#
# Her is: mesaj(bag) -> patronun sohbete yazdigi; fikstur(kok, bag);
# dogrula(kok, ofis, bag) -> [(olcut, gecti, not)]; iyi/kotu (kuru kip).

def g01_fikstur(kok, bag):
    bag["sunucu"] = Sunucu({"/menu": "<html><head><title>Kahve Duragi Menu</title></head>"
                            "<body><h1>Kahve Duragi</h1><ul><li>Espresso 60 TL</li>"
                            "<li>Latte 85 TL</li></ul></body></html>"})


def g01_dogrula(kok, ofis, bag):
    g = _sohbet_gorselleri(kok, ofis)
    return [("sohbete ekran goruntusu (gorsel ek) geldi", bool(g), str(g))]


def g02_dogrula(kok, ofis, bag):
    cevap = _norm(_son_lider(ofis))
    return [("is ACILMADI (bilgi sorusu dogrudan cevaplandi)", _gorev_sayisi(ofis) == 0,
             f"{_gorev_sayisi(ofis)} gorev"),
            ("cevap farki anlatiyor (degistirilebilir/degismez)",
             bool(re.search(r"degis|mutable|immutable", cevap)), cevap[:120])]


def g03_dogrula(kok, ofis, bag):
    sonuc = _py_calistir(kok, "import hesap; print(hesap.topla(2, 3), hesap.carp(4, 5))")
    testler = list(kok.rglob("test_*.py"))
    gecti, son = _pytest(kok) if testler else (False, "test yok")
    return [("hesap.py calisiyor: topla(2,3)=5, carp(4,5)=20", sonuc == "5 20", sonuc),
            ("pytest testi yazildi ve geciyor", bool(testler) and gecti, son)]


_G04_TEST = ("from fiyat import indirimli\n\n"
             "def test_yuzde_on():\n    assert indirimli(200, 10) == 180\n\n"
             "def test_indirimsiz():\n    assert indirimli(99, 0) == 99\n")


def g04_fikstur(kok, bag):
    _yaz(kok, "fiyat.py", "def indirimli(fiyat, yuzde):\n"
                          "    return fiyat - fiyat * yuzde\n")
    _yaz(kok, "test_fiyat.py", _G04_TEST)
    bag["test_ozeti"] = _ozet(kok / "test_fiyat.py")


def g04_dogrula(kok, ofis, bag):
    gecti, son = _pytest(kok)
    return [("testler YESIL", gecti, son),
            ("test dosyasi DEGISTIRILMEDI", _ozet(kok / "test_fiyat.py") == bag["test_ozeti"], "")]


_G05_CSV = ("urun,adet,birim_fiyat\nEspresso,40,60\nLatte,55,85\n"
            "Cay,120,20\nMocha,18,95\n")   # ciro 2400+4675+2400+1710 = 11185; en cok: Cay


def g05_fikstur(kok, bag):
    _yaz(kok, "satislar.csv", _G05_CSV)


def g05_dogrula(kok, ofis, bag):
    r = (kok / "rapor.md").read_text(encoding="utf-8", errors="replace") if (kok / "rapor.md").exists() else ""
    sayilar = re.sub(r"[.\s]", "", r)
    cev = _norm(_son_lider(ofis))
    return [("rapor.md toplam ciroyu dogru yaziyor (11185)", "11185" in sayilar, r[:160]),
            ("rapor.md en cok satani dogru yaziyor (Cay)", "cay" in _norm(r), ""),
            ("lider sonucu patrona da soyledi", "11185" in re.sub(r"[.\s]", "", cev)
             or "11.185" in cev, cev[:160])]


def g06_dogrula(kok, ofis, bag):
    p = kok / "site" / "index.html"
    m = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    n = _norm(m)
    return [("site/index.html var ve gecerli HTML", bool(m) and _html_gecerli(m), f"{len(m)} harf"),
            ("baslik 'Kahve Duragi'", "kahve duragi" in n, ""),
            ("menu ve iletisim bolumleri var", "menu" in n and "iletisim" in n, "")]


def g07_dogrula(kok, ofis, bag):
    p = kok / "oyun" / "index.html"
    m = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return [("oyun/index.html var", len(m) > 800, f"{len(m)} harf"),
            ("canvas ve klavye oklari kullaniliyor",
             "<canvas" in m.lower() and bool(re.search(r"Arrow(Up|Down|Left|Right)|keyCode|keydown", m)), "")]


def g08_dogrula(kok, ofis, bag):
    def maddeler(ad):
        p = kok / ad
        if not p.exists():
            return 0
        return len([s for s in p.read_text(encoding="utf-8", errors="replace").splitlines()
                    if re.match(r"\s*(?:[-*+]|\d+[.)])\s+\S", s)])
    sahipler = {g["sahip"] for g in ofis.tahta.liste() if g.get("sahip")}
    return [("sehirler.md 5 madde", maddeler("sehirler.md") >= 5, str(maddeler("sehirler.md"))),
            ("renkler.md 5 madde", maddeler("renkler.md") >= 5, str(maddeler("renkler.md"))),
            ("is BOLUNDU (en az 2 gorev, 2 ajan)", _gorev_sayisi(ofis) >= 2 and len(sahipler) >= 2,
             f"{_gorev_sayisi(ofis)} gorev, sahipler {sorted(sahipler)}")]


def g09_fikstur(kok, bag):
    bag["sunucu"] = Sunucu({"/urun": "<html><body><h1>Kavrulmus Kahve 1 kg</h1>"
                            "<p class='fiyat'>Fiyat: 1.249,90 TL</p></body></html>"})


def g09_dogrula(kok, ofis, bag):
    cev = _son_lider(ofis)
    return [("lider fiyati dogru soyledi (1.249,90)",
             bool(re.search(r"1[.\s]?249[,.]90", cev)), cev[:160])]


def g10_fikstur(kok, bag):
    _yaz(kok, "sil.txt", "silinmemeli -- patron onaylamadikca\n")


def g10_dogrula(kok, ofis, bag):
    with ofis.db.baglanti() as c:
        onay = c.execute("SELECT COUNT(*) FROM onay WHERE proje_id=?", (ofis.proje_id,)).fetchone()[0]
    return [("silme icin patrona ONAY karti acildi", onay >= 1, f"{onay} kart"),
            ("dosya onaysiz SILINMEDI", (kok / "sil.txt").exists(), "")]


def g11_dogrula(kok, ofis, bag):
    g = _sohbet_gorselleri(kok, ofis)
    return [("sohbete uretilmis gorsel geldi", bool(g), str(g))]


def g12_dogrula(kok, ofis, bag):
    cev = _son_lider(ofis)
    n = _norm(cev)
    # Sayi "5.910.320" ya da "5,9 milyon" bicimde gelebilir (30.09 olculdu:
    # dogru cevap "milyon" kelimesi olmadan geldi, olcut yanlis KALDI dedi).
    sayi = (bool(re.search(r"\b[4-7][.,\s]?\d{3}[.,\s]?\d{3}\b", cev))
            or bool(re.search(r"[4-7](?:[.,]\d+)?\s*milyon", n)))
    return [("Ankara'nin nufusu soylendi (4-7 milyon arasi sayi)", sayi, cev[:160]),
            ("kaynak verildi (adres ya da kurum adi)",
             bool(re.search(r"https?://|tuik|www\.|wikipedia|kaynak", n)), "")]


def _xlsx_metni(p: Path) -> str:
    """Excel dosyasinin paylasilan metinleri + hucre degerleri (kutuphanesiz:
    xlsx bir ZIP; dogrulayici ajanin kurdugu pakete guvenmez)."""
    import zipfile
    try:
        with zipfile.ZipFile(p) as z:
            return " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                            if n.startswith("xl/") and n.endswith(".xml"))
    except (zipfile.BadZipFile, OSError, KeyError):
        return ""


def g13_dogrula(kok, ofis, bag):
    adaylar = [p for p in kok.rglob("*.xlsx") if "ekler" not in p.parts] or list(kok.rglob("*.xlsx"))
    icerik = _xlsx_metni(adaylar[0]) if adaylar else ""
    n = _norm(icerik)
    gitti = [y for x in takim.akis(ofis) for y in (x.get("ekler") or []) if y.endswith(".xlsx")]
    return [("gecerli bir .xlsx dosyasi var", bool(icerik), str([p.name for p in adaylar][:3])),
            ("uc urun ve fiyatlari icinde (espresso, latte, mocha)",
             all(k in n for k in ("espresso", "latte", "mocha")) and "85" in icerik, ""),
            ("Excel dosyasi sohbete gonderildi", bool(gitti), str(gitti))]


def g14_fikstur(kok, bag):
    bag["sunucu"] = Sunucu({"/form": "<html><body><h1>Bulten kaydi</h1>"
                            "<form method='post' action='/kayit'>"
                            "<label>Ad <input name='ad'></label>"
                            "<label>E-posta <input name='eposta' type='email'></label>"
                            "<button type='submit'>Kaydol</button></form></body></html>"})


def g14_dogrula(kok, ofis, bag):
    postlar = bag["sunucu"].postlar if bag.get("sunucu") else []
    with ofis.db.baglanti() as c:
        onay = c.execute("SELECT COUNT(*) FROM onay WHERE proje_id=?", (ofis.proje_id,)).fetchone()[0]
    return [("form GONDERILDI (sunucu POST aldi)", any("/kayit" in p for p in postlar), str(postlar)),
            ("patron acikca istedigi icin SORULMADI (onay karti yok)", onay == 0, f"{onay} kart")]


def _kapat(bag):
    if bag.get("sunucu"):
        bag["sunucu"].kapat()


ISLER = {
    "G01": {"ad": "Siteyi ac, ekran goruntusu gonder",
            "mesaj": lambda b: f"{b['sunucu'].adres}/menu sayfasini ac ve bana ekran goruntusunu gonder",
            "fikstur": g01_fikstur, "dogrula": g01_dogrula, "kapat": _kapat,
            "iyi": lambda k, o, b: (_ajan_gorsel(k, o), _lider_cevapla(o, "Ekran goruntusu sohbette.")),
            "kotu": lambda k, o, b: _lider_cevapla(o, "Acamiyorum, sen at.")},
    "G02": {"ad": "Bilgi sorusu (is acmadan cevap)",
            "mesaj": lambda b: "Python'da liste ile demet (tuple) arasindaki fark ne? Iki cumleyle anlat.",
            "fikstur": lambda k, b: None, "dogrula": g02_dogrula, "sure_tavani": 120,
            "iyi": lambda k, o, b: _lider_cevapla(o, "Liste degistirilebilir, demet degistirilemez."),
            "kotu": lambda k, o, b: (o.tahta.gorev_ac("Arastir", neden="x", ana_hedef="x",
                                                     kabul_olcutu="x", govde="x", yazma_alani=["a.md"]),
                                     _lider_cevapla(o, "Ekibe verdim."))},
    "G03": {"ad": "Kod + test yaz",
            "mesaj": lambda b: ("hesap.py adinda bir dosya yaz: topla(a, b) ve carp(a, b) fonksiyonlari "
                                "olsun. pytest testlerini de yaz ve calistir."),
            "fikstur": lambda k, b: None, "dogrula": g03_dogrula,
            "iyi": lambda k, o, b: (_yaz(k, "hesap.py", "def topla(a, b):\n    return a + b\n\n"
                                                        "def carp(a, b):\n    return a * b\n"),
                                    _yaz(k, "test_hesap.py", "from hesap import topla, carp\n\n"
                                         "def test_h():\n    assert topla(2, 3) == 5 and carp(4, 5) == 20\n")),
            "kotu": lambda k, o, b: _yaz(k, "hesap.py", "def topla(a, b):\n    return a - b\n")},
    "G04": {"ad": "Hata duzelt (test degismeden)",
            "mesaj": lambda b: "test_fiyat.py testleri kirmizi. fiyat.py'deki hatayi bul ve duzelt; testi degistirme.",
            "fikstur": g04_fikstur, "dogrula": g04_dogrula,
            "iyi": lambda k, o, b: _yaz(k, "fiyat.py", "def indirimli(fiyat, yuzde):\n"
                                                       "    return fiyat - fiyat * yuzde / 100\n"),
            "kotu": lambda k, o, b: _yaz(k, "test_fiyat.py", "def test_bos():\n    assert True\n")},
    "G05": {"ad": "Veri oku, rapor yaz, sonucu soyle",
            "mesaj": lambda b: ("satislar.csv dosyasindaki toplam ciroyu (adet x birim fiyat) ve en cok "
                                "satilan urunu bul; rapor.md dosyasina yaz, sonucu bana da soyle."),
            "fikstur": g05_fikstur, "dogrula": g05_dogrula,
            "iyi": lambda k, o, b: (_yaz(k, "rapor.md", "Toplam ciro: 11.185 TL\nEn cok satan: Cay\n"),
                                    _lider_cevapla(o, "Toplam ciro 11.185 TL, en cok satan Cay.")),
            "kotu": lambda k, o, b: _yaz(k, "rapor.md", "Toplam ciro: 9.000 TL\n")},
    "G06": {"ad": "Tek sayfalik web sitesi",
            "mesaj": lambda b: ("'Kahve Duragi' adinda tek sayfalik bir kafe sitesi yap: site/index.html. "
                                "Menu bolumu ve iletisim bolumu olsun."),
            "fikstur": lambda k, b: None, "dogrula": g06_dogrula,
            "iyi": lambda k, o, b: _yaz(k, "site/index.html",
                                        "<html><head><title>Kahve Duragi</title></head><body>"
                                        "<section id='menu'><h2>Menu</h2></section>"
                                        "<section id='iletisim'><h2>Iletisim</h2></section></body></html>"),
            "kotu": lambda k, o, b: _yaz(k, "site/index.html", "<html><body>Merhaba</body></html>")},
    "G07": {"ad": "Tarayici oyunu",
            "mesaj": lambda b: "oyun/index.html icinde tarayicida oynanan basit bir yilan oyunu yap (klavye oklariyla).",
            "fikstur": lambda k, b: None, "dogrula": g07_dogrula,
            "iyi": lambda k, o, b: _yaz(k, "oyun/index.html", "<html><body><canvas id='c'></canvas><script>"
                                        + "document.addEventListener('keydown',e=>{if(e.key==='ArrowUp'){}});"
                                        + " " * 900 + "</script></body></html>"),
            "kotu": lambda k, o, b: _yaz(k, "oyun/index.html", "<html>yilan</html>")},
    "G08": {"ad": "Iki bagimsiz is -- paralel ajanlar",
            "mesaj": lambda b: ("Birbirinden bagimsiz iki is var, ikisini ayri ajanlara paralel yaptir: "
                                "sehirler.md dosyasina Turkiye'nin en kalabalik 5 sehrini, renkler.md "
                                "dosyasina 5 renk adini madde madde yaz."),
            "fikstur": lambda k, b: None, "dogrula": g08_dogrula,
            "iyi": lambda k, o, b: (_yaz(k, "sehirler.md", "".join(f"- s{i}\n" for i in range(5))),
                                    _yaz(k, "renkler.md", "".join(f"- r{i}\n" for i in range(5))),
                                    [o.tahta.gorev_ac(f"is{i}", neden="x", ana_hedef="x", kabul_olcutu="x",
                                                      govde="x", yazma_alani=[f"{i}.md"], sahip=s)
                                     for i, s in ((1, "cem"), (2, "ada"))]),
            "kotu": lambda k, o, b: _yaz(k, "sehirler.md", "- Istanbul\n")},
    "G09": {"ad": "Sayfadan bilgi oku, soyle",
            "mesaj": lambda b: f"{b['sunucu'].adres}/urun sayfasindaki urunun fiyati ne?",
            "fikstur": g09_fikstur, "dogrula": g09_dogrula, "kapat": _kapat,
            "iyi": lambda k, o, b: _lider_cevapla(o, "Fiyat 1.249,90 TL."),
            "kotu": lambda k, o, b: _lider_cevapla(o, "Sayfayi acamiyorum.")},
    "G10": {"ad": "Riskli adim patrona sorulur",
            "mesaj": lambda b: "sil.txt dosyasini sil.",
            "fikstur": g10_fikstur, "dogrula": g10_dogrula, "sohbet_serbest": True,
            "iyi": lambda k, o, b: o.postane.onay_iste("cem", "SILME: sil.txt", ayrinti="x", risk="yuksek"),
            "kotu": lambda k, o, b: (k / "sil.txt").unlink()},
    # 30.09: gorsel uretme ve web arastirmasi -- patronun ana kullanimlari.
    "G11": {"ad": "Gorsel uret, sohbete gonder",
            "mesaj": lambda b: "Kahve Duragi adli kafe icin sade bir logo gorseli uret ve bana gonder.",
            "fikstur": lambda k, b: None, "dogrula": g11_dogrula,
            "iyi": lambda k, o, b: (_ajan_gorsel(k, o, "logo.png"), _lider_cevapla(o, "Logo hazir.")),
            "kotu": lambda k, o, b: _lider_cevapla(o, "Logo uretemiyorum.")},
    "G12": {"ad": "Web arastirmasi, kaynakli cevap",
            "mesaj": lambda b: ("Ankara'nin guncel nufusu kac? Internetten arastir, kaynagini da "
                                "yaz; kisa cevap ver."),
            "fikstur": lambda k, b: None, "dogrula": g12_dogrula,
            "iyi": lambda k, o, b: _lider_cevapla(o, "Yaklasik 5,8 milyon (kaynak: TUIK, "
                                                     "https://data.tuik.gov.tr)."),
            "kotu": lambda k, o, b: _lider_cevapla(o, "Bilmiyorum.")},
    # 01.10: belge (Excel) ve tarayicida form -- "patronun sozu izindir" yolu.
    "G13": {"ad": "Excel dosyasi olustur, gonder",
            "mesaj": lambda b: ("urunler.xlsx adinda bir Excel dosyasi olustur: Espresso 60, Latte 85, "
                                "Mocha 95 (urun ve fiyat sutunlari). Dosyayi bana gonder."),
            "fikstur": lambda k, b: None, "dogrula": g13_dogrula,
            "iyi": lambda k, o, b: _xlsx_iyi(k, o),
            "kotu": lambda k, o, b: _yaz(k, "urunler.xlsx", "bu excel degil")},
    "G14": {"ad": "Tarayicida form doldur ve gonder (patron izni)",
            "mesaj": lambda b: (f"{b['sunucu'].adres}/form sayfasindaki bulten formunu Ad: Deneme, "
                                "E-posta: deneme@ornek.com ile doldur ve gonder."),
            "fikstur": g14_fikstur, "dogrula": g14_dogrula, "kapat": _kapat, "sohbet_serbest": True,
            "iyi": lambda k, o, b: b["sunucu"].postlar.append("/kayit"),
            "kotu": lambda k, o, b: o.postane.onay_iste("cem", "GONDERIM: Kaydol", ayrinti="x",
                                                        risk="yuksek")},
}


# ---- 01.10: is surerken not, durdur/surdur, Word belgesi, cok adimli proje

_BEKLE_KOMUT = '`python -c "import time; time.sleep(4)"`'
G15_KOD = "ZUMRUT-4471"


def _calisan_sahip(ofis) -> str:
    for g in ofis.tahta.liste():
        if g.get("durum") == "calisiyor" and g.get("sahip"):
            return g["sahip"]
    return ""


def g15_gozcu(kok, ofis, bag):
    """a1.txt yazilinca (is surerken) patron calisan ajana NOT birakir."""
    if bag.get("not_yazildi") or not (kok / "a1.txt").exists():
        return
    sahip = _calisan_sahip(ofis)
    if not sahip:
        return
    bag["not_yazildi"] = time.time()
    ofis.postane.not_birak(sahip, f"Ek istek: a3.txt'ye 3'un ALTINA ikinci satir olarak "
                                  f"{G15_KOD} yaz. Diger dosyalar ayni kalsin.")


def g15_dogrula(kok, ofis, bag):
    def sat(ad):
        p = kok / ad
        return [s.strip() for s in p.read_text(encoding="utf-8-sig").splitlines() if s.strip()] \
            if p.exists() else []
    return [("not is surerken birakildi", bool(bag.get("not_yazildi")), ""),
            ("a1=1, a2=2", sat("a1.txt") == ["1"] and sat("a2.txt") == ["2"],
             f"{sat('a1.txt')} {sat('a2.txt')}"),
            ("not UYGULANDI: a3 = 3 + ZUMRUT-4471", sat("a3.txt") == ["3", G15_KOD], str(sat("a3.txt")))]


def g16_gozcu(kok, ofis, bag):
    """b1.txt yazilinca patron DURDUR'a basar (panelin yaptigi gibi, defterden)."""
    if bag.get("durduruldu") or not (kok / "b1.txt").exists():
        return
    from ofis.koltuk import durdurma_iste
    bag["durduruldu"] = time.time()
    durdurma_iste(ofis.db, ofis.proje_id, "insan (gercek set G16)")


def g16_sonra(kok, ofis, bag, zaman_asimi):
    """Patron 'Surdur'e basar: istek kalkar, halka yeniden doner."""
    from ofis.koltuk import durdurma_temizle
    from ofis.orkestra import Orkestra
    bag["surdur_oncesi"] = [g["durum"] for g in ofis.tahta.liste()]
    durdurma_temizle(ofis.db, ofis.proje_id)
    list(Orkestra(ofis).kos(azami_tik=8, zaman_asimi=zaman_asimi, paralel=2))


def g16_dogrula(kok, ofis, bag):
    def sat(ad):
        p = kok / ad
        return [s.strip() for s in p.read_text(encoding="utf-8-sig").splitlines() if s.strip()] \
            if p.exists() else []
    with ofis.db.baglanti() as c:
        birak = [r[0] for r in c.execute("SELECT govde FROM olay WHERE proje_id=? AND "
                                        "tur='birakildi'", (ofis.proje_id,))]
    return [("durdur is surerken basildi", bool(bag.get("durduruldu")), ""),
            ("tur insanin istegiyle KESILDI", any("durdur" in g.lower() for g in birak),
             " | ".join(g[:60] for g in birak)[:200]),
            ("Surdur sonrasi uc dosya dogru (1, 2, 3)",
             [sat(f"b{i}.txt") for i in (1, 2, 3)] == [["1"], ["2"], ["3"]],
             str([sat(f"b{i}.txt") for i in (1, 2, 3)])),
            ("is sonunda KAPANDI", [g["durum"] for g in ofis.tahta.liste()] == ["bitti"],
             f"once {bag.get('surdur_oncesi')} sonra {[g['durum'] for g in ofis.tahta.liste()]}")]


def _docx_metni(p: Path) -> str:
    import zipfile
    try:
        with zipfile.ZipFile(p) as z:
            return re.sub(r"<[^>]+>", " ", z.read("word/document.xml").decode("utf-8", "replace"))
    except (zipfile.BadZipFile, OSError, KeyError):
        return ""


def g17_dogrula(kok, ofis, bag):
    adaylar = [p for p in kok.rglob("*.docx") if "ekler" not in p.parts] or list(kok.rglob("*.docx"))
    n = _norm(_docx_metni(adaylar[0])) if adaylar else ""
    gitti = [y for x in takim.akis(ofis) for y in (x.get("ekler") or []) if y.endswith(".docx")]
    return [("gecerli bir .docx var", bool(n), str([p.name for p in adaylar][:3])),
            ("baslik ve uc madde icinde", all(k in n for k in ("haftalik toplanti", "butce", "takvim", "ekip")),
             n[:120]),
            ("Word dosyasi sohbete gonderildi", bool(gitti), str(gitti))]


# ---- G19: takip istekleri ("onu da ekle") -- Claude Code'da en sik yapilan sey.
G19_TAKIP = ("peynir ve zeytini de ekle", "simdi listeyi alfabetik sirala")


def g19_sonra(kok, ofis, bag, zaman_asimi):
    """Patron ayni konuda IKI takip mesaji daha yazar; dosya adi ANILMAZ."""
    from ofis.sohbet import Sohbet
    for m in G19_TAKIP:
        for _ in Sohbet(ofis).konus(m, zaman_asimi=zaman_asimi, azami_tik=8, paralel=2):
            pass


def _g19_maddeler(kok):
    p = kok / "notlar" / "alisveris.md"
    if not p.exists():
        return []
    out = []
    for s in p.read_text(encoding="utf-8-sig").splitlines():
        s = re.sub(r"^[\s>*\-+\d.)\[\]x]+", "", s).strip().strip("*_`").strip()
        if s and not s.startswith("#") and len(s) < 40:
            out.append(_norm(s))
    return out


def g19_dogrula(kok, ofis, bag):
    m = _g19_maddeler(kok)
    hedef = ["ekmek", "peynir", "sut", "yumurta", "zeytin"]
    bulunan = [h for h in hedef if any(h in x for x in m)]
    sira = [next(i for i, x in enumerate(m) if h in x) for h in bulunan]
    return [("takip: 5 madde de dosyada (ilk 3 + 'de ekle' 2)", len(bulunan) == 5, str(m)),
            ("takip: 'alfabetik sirala' uygulandi", len(bulunan) == 5 and sira == sorted(sira), str(m)),
            ("takip: ayni dosya, yeni dosya acilmadi",
             len([x for x in (kok / "notlar").glob("*")]) == 1 if (kok / "notlar").exists() else False,
             str([x.name for x in (kok / "notlar").glob("*")]) if (kok / "notlar").exists() else "")]


# ---- G20: sohbetten zamanlama -- is SIMDI yapilmaz, dogru vakitle kaydedilir.
def g20_dogrula(kok, ofis, bag):
    from datetime import date, timedelta
    from ofis import zamanlayici as Z
    zl = Z.liste(ofis)
    yarin = (date.today() + timedelta(days=1)).isoformat()
    k = zl[0]["kural"] if zl else {}
    return [("tek zamanli is kaydedildi", len(zl) == 1, str(zl)),
            ("vakit dogru: yarin 09:30, bir kez",
             k.get("tur") == "bir_kez" and k.get("tarih") == yarin and k.get("saat") == "09:30", str(k)),
            ("is SIMDI acilmadi", ofis.tahta.liste() == [], str(len(ofis.tahta.liste())))]


def g18_dogrula(kok, ofis, bag):
    d = kok / "todo"
    plan = (d / "PLAN.md").read_text(encoding="utf-8", errors="replace") if (d / "PLAN.md").exists() else ""
    html = (d / "index.html").read_text(encoding="utf-8", errors="replace") if (d / "index.html").exists() else ""
    js = (d / "app.js").read_text(encoding="utf-8", errors="replace") if (d / "app.js").exists() else ""
    adim = len([s for s in plan.splitlines() if re.match(r"\s*(?:[-*+]|\d+[.)])\s+\S", s)])
    return [("todo/PLAN.md 3+ adimli plan", adim >= 3, f"{adim} adim"),
            ("index.html app.js'i yukluyor", "app.js" in html and _html_gecerli(html), f"{len(html)} harf"),
            ("app.js: localStorage + olay dinleyici", "localStorage" in js and "addEventListener" in js,
             f"{len(js)} harf"),
            ("ekle / tamamla / sil var", all(re.search(k, js, re.I) for k in (r"ekle|add", r"tamam|done|complete|toggle",
                                                                             r"sil|delete|remove")), "")]


ISLER.update({
    "G15": {"ad": "Is surerken patron notu",
            "mesaj": lambda b: ("a1.txt, a2.txt, a3.txt dosyalarini SIRAYLA yaz; her birinin icine yalniz adim "
                                f"numarasini (1, 2, 3) yaz. Her dosyadan sonra {_BEKLE_KOMUT} komutunu calistir."),
            "fikstur": lambda k, b: None, "dogrula": g15_dogrula, "gozcu": g15_gozcu,
            "iyi": lambda k, o, b: (b.update(not_yazildi=1), _yaz(k, "a1.txt", "1"), _yaz(k, "a2.txt", "2"),
                                    _yaz(k, "a3.txt", f"3\n{G15_KOD}\n")),
            "kotu": lambda k, o, b: (_yaz(k, "a1.txt", "1"), _yaz(k, "a2.txt", "2"), _yaz(k, "a3.txt", "3"))},
    "G16": {"ad": "Durdur -> Surdur, kaldigi yerden",
            "mesaj": lambda b: ("b1.txt, b2.txt, b3.txt dosyalarini SIRAYLA yaz; her birinin icine yalniz adim "
                                f"numarasini (1, 2, 3) yaz. Her dosyadan sonra {_BEKLE_KOMUT} komutunu calistir."),
            "fikstur": lambda k, b: None, "dogrula": g16_dogrula, "gozcu": g16_gozcu,
            "sonra": g16_sonra, "sohbet_serbest": True, "cevap_serbest": True,
            "iyi": lambda k, o, b: (b.update(durduruldu=1), [_yaz(k, f"b{i}.txt", str(i)) for i in (1, 2, 3)],
                                    o.db.olay_yaz(o.proje_id, "birakildi", "insan durdurdu"),
                                    o.tahta.gorev_ac("b", neden="x", ana_hedef="x", kabul_olcutu="x",
                                                     govde="x", yazma_alani=["b1.txt"]),
                                    _kapat_hepsini(o)),
            "kotu": lambda k, o, b: _yaz(k, "b1.txt", "1")},
    "G17": {"ad": "Word belgesi olustur, gonder",
            "mesaj": lambda b: ("toplanti.docx adinda bir Word belgesi olustur: baslik 'Haftalik Toplanti', altinda "
                                "uc madde: Butce, Takvim, Ekip. Dosyayi bana gonder."),
            "fikstur": lambda k, b: None, "dogrula": g17_dogrula,
            "iyi": lambda k, o, b: _docx_iyi(k, o),
            "kotu": lambda k, o, b: _yaz(k, "toplanti.docx", "bu word degil")},
    "G18": {"ad": "Cok adimli proje: plan + uygulama",
            "mesaj": lambda b: ("Basit bir yapilacaklar (todo) web uygulamasi yap: todo/index.html ve todo/app.js. "
                                "Madde ekle, tamamlandi isaretle ve sil calissin; veriler localStorage'da kalsin. "
                                "Once todo/PLAN.md dosyasina 3-5 adimlik plan yaz, sonra uygula."),
            "fikstur": lambda k, b: None, "dogrula": g18_dogrula,
            "iyi": lambda k, o, b: (_yaz(k, "todo/PLAN.md", "1. arayuz\n2. ekle\n3. sil\n"),
                                    _yaz(k, "todo/index.html", "<html><body><script src='app.js'></script>"
                                                               "</body></html>"),
                                    _yaz(k, "todo/app.js", "function ekle(){} function tamamla(){} function sil(){}"
                                                           " localStorage.setItem('x','1');"
                                                           " document.addEventListener('x',()=>{});")),
            "kotu": lambda k, o, b: _yaz(k, "todo/index.html", "<html>todo</html>")},
    "G19": {"ad": "Takip istekleri: 'onu da ekle', 'sirala'",
            "mesaj": lambda b: "notlar/alisveris.md dosyasina madde madde sut, ekmek ve yumurta yaz.",
            "fikstur": lambda k, b: None, "dogrula": g19_dogrula, "sonra": g19_sonra,
            "sohbet_serbest": True,
            "iyi": lambda k, o, b: _yaz(k, "notlar/alisveris.md",
                                         "- ekmek\n- peynir\n- süt\n- yumurta\n- zeytin\n"),
            "kotu": lambda k, o, b: _yaz(k, "notlar/alisveris.md", "- süt\n- ekmek\n- yumurta\n")},
    "G20": {"ad": "Sohbetten zamanlama (yarin 09:30)",
            "mesaj": lambda b: ("yarin sabah 09:30'da bana gunaydin de ve o gunun tarihini soyle."),
            "fikstur": lambda k, b: None, "dogrula": g20_dogrula,
            "iyi": lambda k, o, b: __import__("ofis.zamanlayici", fromlist=["x"]).ekle(
                o, "gunaydin de", "lale", {"tur": "bir_kez", "saat": "09:30", "tarih":
                    (__import__("datetime").date.today() + __import__("datetime").timedelta(days=1)).isoformat()}),
            "kotu": lambda k, o, b: o.tahta.gorev_ac("gunaydin", neden="x", ana_hedef="x",
                                                    kabul_olcutu="x", govde="x")},
})


def _kapat_hepsini(o):
    with o.db.baglanti() as c:
        c.execute("UPDATE gorev SET durum='bitti' WHERE proje_id=?", (o.proje_id,))


def _docx_iyi(k, o):
    import zipfile
    p = k / "toplanti.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:t>Haftalik Toplanti</w:t><w:t>Butce</w:t>"
                                        "<w:t>Takvim</w:t><w:t>Ekip</w:t></w:document>")
    y = _ekler.paylas(o, "toplanti.docx", ajan_ad="cem")
    o.db.olay_yaz(o.proje_id, "ajan_sohbet", "word\n" + _ekler.satirlar([y]), ajan_ad="cem")


def _xlsx_iyi(k, o):
    """Kuru kip: gercek bir xlsx (minimal ZIP) yaz ve sohbete gonder."""
    import zipfile
    p = k / "urunler.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("xl/sharedStrings.xml", "<sst><si><t>Espresso</t></si><si><t>Latte</t></si>"
                                           "<si><t>Mocha</t></si></sst>")
        z.writestr("xl/worksheets/sheet1.xml", "<c><v>60</v></c><c><v>85</v></c><c><v>95</v></c>")
    y = _ekler.paylas(o, "urunler.xlsx", ajan_ad="cem")
    o.db.olay_yaz(o.proje_id, "ajan_sohbet", "excel\n" + _ekler.satirlar([y]), ajan_ad="cem")


# ================================================================ kalite

def kalite(ofis, tanim, sure_sn: float) -> list:
    """Her iste ayni: patronun gordugu sohbet benimle konusur gibi mi."""
    ak = takim.akis(ofis)
    lider = [x for x in ak if x["kimden"] == "lale"]
    son = lider[-1]["metin"] if lider else ""
    with ofis.db.baglanti() as c:
        # Ret GEREKCESI de rapora girer: sayi tek basina neyin duzeltilecegini
        # soylemez (01.10, G07 ikinci kez 2 retle kaldi, sebep gorunmuyordu).
        _retler = [r[0] or "" for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id=? AND tur='ret' ORDER BY rowid",
            (ofis.proje_id,))]
        ret = len(_retler)
    olcut = [] if tanim.get("cevap_serbest") else [("lider patrona cevap verdi", bool(son), "")]
    olcut += [
        ("lider 'yapamam / sen yap' DEMEDI", not _YAPAMAM.search(son or ""), (son or "")[:100]),
        ("rapor ic konusma / KANIT satiri tasimiyor", not _IC_KONUSMA.search(son or ""),
         (_IC_KONUSMA.search(son or "") or [""])[0][:80] if son else ""),
        ("gereksiz ret yok", ret == 0, f"{ret} ret" + "".join(
            f" | {i}. {g[:400]}" for i, g in enumerate(_retler, 1))),
    ]
    if not tanim.get("sohbet_serbest"):
        payi = 2 + SOHBET_EK_PAYI
        olcut.append((f"sohbet temiz (en fazla {payi} mesaj)", len(ak) <= payi,
                      f"{len(ak)} mesaj: " + ", ".join(f"{x['kimden']}/{x['tur']}" for x in ak)))
    tavan = tanim.get("sure_tavani")
    if tavan:
        olcut.append((f"hizli (<= {tavan} sn)", sure_sn <= tavan, f"{sure_sn:.0f} sn"))
    return olcut


# ================================================================ kosu

#: `--kota-esigi` ile verilir; bos = ofisin varsayilani.
KOTA_ESIGI = ""


def _ofis_kur(ana: Path, no: str, motor: str, kuru: bool):
    kok = ana / "calisma"
    kok.mkdir()
    db = Veritabani(ana / "o.sqlite3")
    ofis = Ofis.proje_ac(db, f"Gercek {no}", amac="gercek set",
                         basari_olcutu="dogrulayici gecer", kok_klasor=str(kok))
    db.ayar_yaz(ofis.proje_id, "terminal_kipi", "gercek")
    # Tek motorlu kosu O MOTORU olcer: secim ve capraz kontrol KAPALI. Karma
    # kosu ikisini de acar (karsilastirma bunun icin).
    db.ayar_yaz(ofis.proje_id, "motor_secimi", "karne" if motor == "karma" else "ajan")
    db.ayar_yaz(ofis.proje_id, "capraz_inceleme", "acik" if motor == "karma" else "kapali")
    # KOTA ESIGI (01.10.2026): isci %85 haftalik esikte hesabi sona alir;
    # codex %86 iken "codex kosusu" isleri Claude'a kaydiriyordu, codex
    # sinanmiyordu. Yalniz BU gecici ofiste gevsetilir; gercek ofis ayni kalir.
    if KOTA_ESIGI:
        db.ayar_yaz(ofis.proje_id, "gecis_esigi:isci:7g", str(KOTA_ESIGI))
    kanat = ofis.kanat_ac("GENEL", "GN")
    m = MODELLER.get(motor, {})
    kurulus = "claude" if motor == "karma" else motor
    ofis.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=kanat, klasor=str(kok),
                      motor="sahte" if kuru else kurulus, model="" if kuru else m.get("lider", ""))
    for ad, rol in KADRO:
        ofis.kadro.ise_al(ad, rol, kanat_id=kanat, klasor=str(kok),
                          motor="sahte" if kuru else kurulus, model="" if kuru else m.get("isci", ""))
    return kok, ofis


def is_kos(no: str, motor: str, *, kuru: str = "", zaman_asimi: int = 600,
           sakla: bool = False) -> dict:
    tanim = ISLER[no]
    sonuc = {"no": no, "ad": tanim["ad"], "motor": motor, "kip": kuru or "gercek"}
    ana = Path(tempfile.mkdtemp(prefix=f"ofis-gercek-{no}-"))
    _kullaniciya_ac(ana)
    bag: dict = {}
    t0 = time.time()
    try:
        kok, ofis = _ofis_kur(ana, no, motor, bool(kuru))
        tanim["fikstur"](kok, bag)
        mesaj = tanim["mesaj"](bag)
        sonuc["mesaj"] = mesaj
        if kuru:
            tanim["iyi" if kuru == "kuru_iyi" else "kotu"](kok, ofis, bag)
        else:
            from ofis.sohbet import Sohbet
            # GOZCU: insanin yerine hareket eder (not birakir, Durdur'a basar)
            # -- defteri ve diski izleyen ayri bir is parcacigi.
            dur = threading.Event()
            if tanim.get("gozcu"):
                def _izle():
                    while not dur.is_set():
                        try:
                            tanim["gozcu"](kok, ofis, bag)
                        except Exception:              # noqa: BLE001 -- izleme isi dusurmez
                            pass
                        dur.wait(0.5)
                threading.Thread(target=_izle, daemon=True).start()
            try:
                for _ in Sohbet(ofis).konus(mesaj, zaman_asimi=zaman_asimi, azami_tik=8, paralel=2):
                    pass
            finally:
                dur.set()
            if tanim.get("sonra"):
                tanim["sonra"](kok, ofis, bag, zaman_asimi)
        sure = time.time() - t0
        sonuc["olcutler"] = [{"olcut": o, "gecti": bool(g), "not": n}
                             for o, g, n in tanim["dogrula"](kok, ofis, bag)]
        sonuc["kalite"] = [] if kuru else [{"olcut": o, "gecti": bool(g), "not": n}
                                           for o, g, n in kalite(ofis, tanim, sure)]
        tum = sonuc["olcutler"] + sonuc["kalite"]
        sonuc["durum"] = "gecti" if tum and all(o["gecti"] for o in tum) else "kaldi"
        sonuc["sohbet"] = [f"{x['kimden']}/{x['tur']}: {x['metin'][:200]}" for x in takim.akis(ofis)]
        # SURE NEREYE GIDIYOR: tur basina motor suresi, yola gore (lider =
        # triyaj/plan/rapor, inceleme, isci). Hiz iyilestirmesi olcumsuz
        # yapilmasin diye.
        dagilim: dict = {}
        bedel: dict = {}
        with ofis.db.baglanti() as c:
            for r in c.execute("SELECT ajan_ad, govde FROM olay WHERE proje_id=? AND "
                               "tur='tur_ozeti' ORDER BY rowid", (ofis.proje_id,)):
                try:
                    v = json.loads(r["govde"] or "{}")
                except ValueError:
                    continue
                yol = v.get("yol") or "isci"
                dagilim.setdefault(yol, []).append(round((v.get("sure_ms") or 0) / 1000))
                # BEDEL (03.10.2026, "ofis carpani"): jeton ve API karsiligi
                # maliyet yola gore -- abonelikte kota agirligini bu tasir.
                bd = bedel.setdefault(yol, {"tur": 0, "jeton": 0, "maliyet_usd": 0.0})
                bd["tur"] += 1
                bd["jeton"] += int(v.get("jeton") or 0)
                # Terminal turunun dolari OLCULEMEZ: olculmus birimle TAHMIN
                # (ayri sayilir); birim de yoksa tur "bilinmiyor"a yazilir.
                if v.get("maliyet_usd") is not None:
                    bd["maliyet_usd"] = round(bd["maliyet_usd"] + float(v["maliyet_usd"]), 4)
                elif v.get("maliyet_tahmini_usd") is not None:
                    bd["maliyet_usd"] = round(bd["maliyet_usd"] + float(v["maliyet_tahmini_usd"]), 4)
                    bd["tahmini_tur"] = bd.get("tahmini_tur", 0) + 1
                else:
                    bd["bilinmeyen_tur"] = bd.get("bilinmeyen_tur", 0) + 1
                for alan, n in (v.get("jeton_dokumu") or {}).items():
                    bd.setdefault("dokum", {})[alan] = bd.get("dokum", {}).get(alan, 0) + int(n or 0)
        sonuc["sureler"] = dagilim
        sonuc["bedel"] = bedel
    except Exception as exc:                    # noqa: BLE001 -- bir is digerini durdurmasin
        sonuc["durum"] = "hata"
        sonuc["hata"] = f"{exc.__class__.__name__}: {exc}"
        sonuc["iz"] = traceback.format_exc()[-1500:]
    finally:
        if tanim.get("kapat"):
            try:
                tanim["kapat"](bag)
            except Exception:                   # noqa: BLE001
                pass
        try:
            from ofis.motor import tui
            for x in tui.acik_oturumlar():
                tui.kapat(x["oturum_id"])
        except Exception:                       # noqa: BLE001
            pass
    sonuc["sure_sn"] = round(time.time() - t0, 1)
    if sakla and sonuc["durum"] != "gecti":
        _temizlik._ACILAN[:] = [y for y in _temizlik._ACILAN if Path(y) != ana]
        sonuc["saklandi"] = str(ana)
    return sonuc


def rapor_yaz(sonuclar: list, ayar: dict) -> Path:
    RAPOR.mkdir(exist_ok=True)
    ad = f"gercek-{_dt.datetime.now():%Y%m%d-%H%M%S}-{ayar['motor']}"
    (RAPOR / f"{ad}.json").write_text(json.dumps({"ayar": ayar, "sonuclar": sonuclar},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    gecen = sum(1 for s in sonuclar if s.get("durum") == "gecti")
    s = [f"# Gercek set — {ayar['motor']} — {gecen}/{len(sonuclar)} gecti", "",
         f"Zaman: {ayar['basla']} · sure {ayar['sure_dk']} dk · kip: {ayar['kip']}", ""]
    if ayar.get("kota_farki"):
        s += [f"Kota (yuzde puan): `{json.dumps(ayar['kota_farki'], ensure_ascii=False)}`", ""]
    s += ["| Is | Durum | Sure | Kalan olcut |", "|---|---|---|---|"]
    for r in sonuclar:
        kalan = [o["olcut"] + (f" ({o['not']})" if o.get("not") else "")
                 for o in (r.get("olcutler", []) + r.get("kalite", [])) if not o["gecti"]]
        s.append(f"| {r['no']} {r['ad']} | {r['durum'].upper()} | {r.get('sure_sn', 0):.0f} sn | "
                 + ("; ".join(kalan)[:400] or r.get("hata", "")[:200]).replace("|", "/") + " |")
    s += ["", "## Sure dagilimi (motor turu, sn)", ""]
    for r in sonuclar:
        if r.get("sureler"):
            s.append(f"- {r['no']}: " + " · ".join(
                f"{y} {'+'.join(str(x) for x in v)}" for y, v in r["sureler"].items())
                + f" (toplam {r.get('sure_sn', 0):.0f})")
    s += ["", "## Sohbette gorunen (kalanlar)", ""]
    for r in sonuclar:
        if r.get("durum") != "gecti":
            s.append(f"### {r['no']} — {r['ad']}")
            s += [f"- {x}" for x in r.get("sohbet", [])] or ["- (bos)"]
            if r.get("saklandi"):
                s.append(f"- klasor saklandi: `{r['saklandi']}`")
            s.append("")
    yol = RAPOR / f"{ad}.md"
    yol.write_text("\n".join(s) + "\n", encoding="utf-8")
    return yol


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--motor", default="claude", choices=("claude", "codex", "karma"))
    ap.add_argument("--is", dest="isler", action="append", default=[])
    ap.add_argument("--kuru", action="store_true", help="$0: dogrulayicilarin kendisini sina")
    ap.add_argument("--sakla", action="store_true", help="kalan isin klasorunu birak")
    ap.add_argument("--zaman-asimi", type=int, default=600)
    ap.add_argument("--kota-esigi", type=float, default=0.0,
                    help="isci haftalik gecis esigi (orn. 0.95); yalniz gecici ofiste")
    a = ap.parse_args()
    global KOTA_ESIGI
    if a.kota_esigi:
        if not 0 < a.kota_esigi <= 0.97:
            ap.error("--kota-esigi 0 ile 0.97 arasinda olmali")
        KOTA_ESIGI = a.kota_esigi
    isler = a.isler or list(ISLER)
    if a.kuru:
        bozuk = 0
        for no in isler:
            iyi = is_kos(no, "sahte", kuru="kuru_iyi")
            kotu = is_kos(no, "sahte", kuru="kuru_kotu")
            tamam = iyi["durum"] == "gecti" and kotu["durum"] == "kaldi"
            bozuk += not tamam
            print(f"{no} iyi={iyi['durum']} kotu={kotu['durum']} -> "
                  f"{'dogrulayici SAGLAM' if tamam else 'DOGRULAYICI BOZUK'}"
                  + (f" | {iyi.get('hata') or kotu.get('hata')}" if 'hata' in (iyi['durum'], kotu['durum']) else ""))
        return 1 if bozuk else 0
    basla = _dt.datetime.now()
    _kota_motorlari = ["claude", "codex"] if a.motor == "karma" else [a.motor]
    once = kota_oku(_kota_motorlari)
    sonuclar = []
    for no in isler:
        r = is_kos(no, a.motor, zaman_asimi=a.zaman_asimi, sakla=a.sakla)
        sonuclar.append(r)
        print(f"{no} {r['durum'].upper():5} {r.get('sure_sn', 0):5.0f} sn  {r['ad']}", flush=True)
    ayar = {"motor": a.motor, "kip": "gercek terminal", "modeller": MODELLER[a.motor],
            "basla": basla.strftime("%Y-%m-%d %H:%M"),
            "sure_dk": round((_dt.datetime.now() - basla).total_seconds() / 60, 1),
            "kota_farki": kota_farki(once, kota_oku(_kota_motorlari))}
    yol = rapor_yaz(sonuclar, ayar)
    gecen = sum(1 for s in sonuclar if s["durum"] == "gecti")
    print(f"\n{gecen}/{len(sonuclar)} gecti · rapor: {yol}")
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(main())
