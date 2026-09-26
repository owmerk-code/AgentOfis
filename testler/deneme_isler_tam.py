# -*- coding: utf-8 -*-
"""DENEME SETI -- TAM set isleri (PLAN §5): D03 D04 D06 D07 D08 D11 D12 D13.

Hizli setle ayni sozlesme (`deneme_isler.py`): fikstur · gorev ·
dogrula · kuru_iyi · kuru_kotu. Yeni alanlar:

* `mod="hedef"` -- is tahtaya dogrudan acilmaz, LIDERE hedef olarak
  verilir; bolme karari onundur (D11).
* `insan_cevabi` -- ajan insana soru sorarsa kosturucu insan yerine bu
  cevabi verir ve halkayi surdurur (D12).
* `fabrika_sar(fabrika, bag)` -- motor fabrikasini sarar; tur ortasinda
  limit ENJEKTE etmek icin (D13).
* `isci_sayisi` -- birden cok isci (D11).
"""

from __future__ import annotations

import asyncio
import html.parser
import json
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import deneme_isler as H
from ofis.motor.sahte import SahteMotor
from ofis.motor.tip import MotorOlayi


# ======================================================================= D03

class _Etiketler(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.etiketler = []          # (etiket, attrs)

    def handle_starttag(self, tag, attrs):
        self.etiketler.append((tag, dict(attrs)))


def d03_fikstur(kok, bag):
    pass


D03_GOREV = dict(
    baslik="Kahve dukkani acilis sayfasi",
    ana_hedef=("'Kose Kahve' icin tek sayfalik statik acilis sayfasi: "
               "index.html ve stil.css."),
    kabul_olcutu=("index.html: bir <h1>; id='ozellikler' olan bolumde "
                  "class='ozellik' tasiyan EN AZ 3 oge; id='iletisim' bolumunde "
                  "mailto: baglantisi; bir <footer>. stil.css index.html'e "
                  "bagli. 375 px genislikte (telefon) yatay kaydirma YOK."),
    yazma_alani=["index.html", "stil.css"],
    rol="arayuz")


def _cdp_olc(html_yolu: Path) -> dict:
    """Gercek Chrome (bassiz), 375 px mobil: yatay tasma + ekran goruntusu."""
    from ofis import kabin as KB, tarayici as T
    chrome = KB.calistirilabilir_bul()
    if not chrome:
        return {"hata": "Chrome yok -- olculemedi"}
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    kapi = s.getsockname()[1]
    s.close()
    profil = tempfile.mkdtemp(prefix="ofis-d03-prof-")
    tmp = tempfile.mkdtemp(prefix="ofis-d03-tmp-")
    import os
    sur = subprocess.Popen(T.kabin_komutu(chrome, profil=profil, kapi=kapi,
                                          baslangic="about:blank"),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=dict(os.environ, TEMP=tmp, TMP=tmp))
    try:
        for _ in range(80):
            if KB.acik_mi(kapi):
                break
            time.sleep(0.25)

        async def olc():
            import websockets
            async with websockets.connect(KB.sayfa_ws(kapi), max_size=None) as c:
                n = [0]

                async def cdp(yontem, par=None):
                    n[0] += 1
                    await c.send(json.dumps({"id": n[0], "method": yontem,
                                             "params": par or {}}))
                    while True:
                        v = json.loads(await c.recv())
                        if v.get("id") == n[0]:
                            return v.get("result") or {}
                await cdp("Emulation.setDeviceMetricsOverride",
                          {"width": 375, "height": 800, "deviceScaleFactor": 1,
                           "mobile": True})
                await cdp("Page.enable")
                await cdp("Page.navigate", {"url": html_yolu.resolve().as_uri()})
                await asyncio.sleep(1.5)
                # `file://` sayfada `cssRules` okumak SecurityError atabilir
                # (olculdu: ilk surum KeyError 'value' ile dustu). Kurallari
                # degil, stil.css'in UYGULANDIGINI olceriz: body'nin hesaplanan
                # stili varsayilandan farkli mi -- ve her parca kendi try'inda.
                r = await cdp("Runtime.evaluate", {"expression": (
                    "(() => { let css = false; try { css = [...document.styleSheets]"
                    ".some(s => (s.href||'').endsWith('stil.css')); } catch (e) {}"
                    " return JSON.stringify({sw: document.documentElement.scrollWidth,"
                    " iw: window.innerWidth, css: css}); })()"),
                    "returnByValue": True})
                if "value" not in (r.get("result") or {}):
                    return {"hata": "olcum ifadesi deger dondurmedi: "
                            + json.dumps(r.get("exceptionDetails") or r)[:200]}
                deger = json.loads(r["result"]["value"])
                g = await cdp("Page.captureScreenshot", {"format": "png"})
                deger["ekran_bayt"] = len(g.get("data", ""))
                return deger
        return asyncio.run(olc())
    except Exception as exc:          # noqa: BLE001
        return {"hata": f"{exc.__class__.__name__}: {exc}"}
    finally:
        # Surec AGACI: alt surecler gecici klasoru tutmasin.
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(sur.pid)],
                           capture_output=True)
        else:
            sur.kill()
        try:
            sur.wait(timeout=10)
        except Exception:             # noqa: BLE001
            pass


def d03_dogrula(kok, ofis, bag):
    yol = kok / "index.html"
    s = [("index.html var", yol.exists(), "")]
    if not yol.exists():
        return s
    p = _Etiketler()
    p.feed(yol.read_text(encoding="utf-8", errors="replace"))
    et = p.etiketler
    s.append(("<h1> var", any(t == "h1" for t, _ in et), ""))
    oz = sum(1 for _, a in et if "ozellik" in (a.get("class") or "").split())
    s.append(("en az 3 .ozellik", oz >= 3, f"{oz}"))
    s.append(("#ozellikler bolumu", any(a.get("id") == "ozellikler" for _, a in et), ""))
    s.append(("#iletisim + mailto", any(a.get("id") == "iletisim" for _, a in et)
              and any((a.get("href") or "").startswith("mailto:") for t, a in et
                      if t == "a"), ""))
    s.append(("<footer> var", any(t == "footer" for t, _ in et), ""))
    o = _cdp_olc(yol)
    if o.get("hata"):
        s.append(("mobil olcum", False, o["hata"]))
    else:
        # SABIT telefon genisligine gore: mobil oykunmede Chrome genis icerigi
        # sigdirmak icin sayfayi kucultur ve innerWidth'i BUYUTUR -- ilk surum
        # innerWidth ile kiyasliyordu ve 1400 px'lik serit de "tasma yok" gecti.
        s.append(("375 px'te yatay tasma YOK", o["sw"] <= 376,
                  f"scrollWidth={o['sw']} innerWidth={o['iw']}"))
        s.append(("stil.css sayfaya bagli ve yuklendi", bool(o["css"]), ""))
        s.append(("ekran goruntusu alindi", o["ekran_bayt"] > 1000,
                  f"{o['ekran_bayt']} bayt"))
    return s


def _d03_sayfa(genis: bool):
    govde = ("<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
             "<meta name='viewport' content='width=device-width, initial-scale=1'>"
             "<link rel='stylesheet' href='stil.css'><title>Kose Kahve</title>"
             "</head><body><header><h1>Kose Kahve</h1></header>"
             "<section id='ozellikler'>"
             "<div class='ozellik'>Taze kavrum</div>"
             "<div class='ozellik'>Ev yapimi kek</div>"
             "<div class='ozellik'>Sessiz calisma kosesi</div></section>"
             "<section id='iletisim'><a href='mailto:merhaba@kosekahve.example'>"
             "Yaz</a></section>"
             + ("<div style='width:1400px'>genis serit</div>" if genis else "")
             + "<footer>2026</footer></body></html>")
    return govde


def d03_kuru_iyi(kok, ofis, bag):
    (kok / "index.html").write_text(_d03_sayfa(False), encoding="utf-8")
    (kok / "stil.css").write_text("body{margin:0;font-family:sans-serif}"
                                  ".ozellik{padding:8px}", encoding="utf-8")
    return "KANIT dosya: index.html -> sayfa yazildi"


def d03_kuru_kotu(kok, ofis, bag):
    (kok / "index.html").write_text(_d03_sayfa(True), encoding="utf-8")
    (kok / "stil.css").write_text("body{margin:0}", encoding="utf-8")
    return "KANIT dosya: index.html -> sayfa yazildi"


# ======================================================================= D04

# Olculebilir gercek: python.org'un kendi yayin tarihleri.
D04_GERCEK = {"3.12": "2023-10-02", "3.13": "2024-10-07", "3.14": "2025-10-07"}

D04_GOREV = dict(
    baslik="Python surum tarihleri -- kaynakli tablo",
    ana_hedef=("Python 3.12, 3.13 ve 3.14'un ilk kararli surumlerinin (x.y.0) "
               "yayin tarihlerini python.org kaynagiyla surumler.md'ye tablo yap."),
    kabul_olcutu=("surumler.md: her satirda surum, tarih (YYYY-AA-GG) ve o bilgiyi "
                  "veren python.org baglantisi. Tahmin/uydurma yok; bulamadigini "
                  "'bulunamadi' yaz."),
    yazma_alani=["surumler.md"],
    rol="arastirma")


def d04_fikstur(kok, bag):
    pass


def d04_dogrula(kok, ofis, bag):
    yol = kok / "surumler.md"
    s = [("surumler.md var", yol.exists(), "")]
    if not yol.exists():
        return s
    metin = yol.read_text(encoding="utf-8", errors="replace")
    satirlar = metin.splitlines()
    for surum, tarih in D04_GERCEK.items():
        satir = next((l for l in satirlar if re.search(
            rf"(?<![\d.]){re.escape(surum)}(\.0)?(?![\d])", l) and "|" in l), "")
        s.append((f"{surum} tarihi DOGRU ({tarih})", tarih in satir, satir[:120]))
    baglanti = re.findall(r"https?://[^\s)\]|>]+", metin)
    py = [b for b in baglanti if "python.org" in b]
    s.append(("python.org baglantilari var", len(py) >= 1, f"{len(py)}"))
    import os
    if os.environ.get("OFIS_DENEME_AGSIZ") == "1":
        # Duman takimi internete bagimli olmamali; ATLANDIGI yaziliyor.
        s.append(("baglantilar GERCEKTEN aciliyor", True, "AG SINAMASI ATLANDI (agsiz kip)"))
        return s
    acilan = 0
    for b in py[:4]:
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    b, headers={"User-Agent": "Mozilla/5.0 ofis-deneme"}),
                    timeout=15) as r:
                acilan += r.status == 200
        except Exception:             # noqa: BLE001
            pass
    s.append(("baglantilar GERCEKTEN aciliyor", py and acilan == len(py[:4]),
              f"{acilan}/{len(py[:4])}"))
    return s


def d04_kuru_iyi(kok, ofis, bag):
    (kok / "surumler.md").write_text(
        "| Surum | Tarih | Kaynak |\n|---|---|---|\n"
        + "".join(f"| {s}.0 | {t} | https://www.python.org/downloads/release/"
                  f"python-{s.replace('.', '')}0/ |\n" for s, t in D04_GERCEK.items()),
        encoding="utf-8")
    return "KANIT baglanti: python.org -> tarihler"


def d04_kuru_kotu(kok, ofis, bag):
    (kok / "surumler.md").write_text(
        "| Surum | Tarih | Kaynak |\n|---|---|---|\n"
        "| 3.12.0 | 2023-10-02 | https://www.python.org/downloads/release/python-3120/ |\n"
        "| 3.13.0 | 2024-10-01 | https://www.python.org/downloads/release/python-3130/ |\n"
        "| 3.14.0 | 2025-10-07 | https://www.python.org/downloads/release/python-3140/ |\n",
        encoding="utf-8")
    return "KANIT baglanti: python.org -> tarihler"


# ======================================================================= D06

D06_YASAK = ("en iyi", "garanti", "mucize", "%100", "yuzde yuz", "1 numara")

D06_GOREV = dict(
    baslik="Urun aciklamasi -- 3 varyant",
    ana_hedef=("'Doga' markali bambu dis fircasi icin e-ticaret urun "
               "aciklamasi yaz, 3 FARKLI varyant."),
    kabul_olcutu=("aciklama.md: '## Varyant 1', '## Varyant 2', '## Varyant 3' "
                  "basliklari; her varyant 40-90 kelime; her birinde 'bambu' "
                  "gecer; varyantlar birbirinin kopyasi degil (farkli acilis "
                  "ve vurgu). Abarti/iddia YASAK: 'en iyi', 'garanti', "
                  "'mucize', '%100', '1 numara' kullanilmaz."),
    yazma_alani=["aciklama.md"],
    rol="metin")


def d06_fikstur(kok, bag):
    pass


def _varyantlar(metin):
    parca = re.split(r"^##\s*Varyant\s*\d+.*$", metin, flags=re.M | re.I)
    return [p.strip() for p in parca[1:]]


def _kelimeler(t):
    return re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9%]+", t.lower())


def d06_dogrula(kok, ofis, bag):
    yol = kok / "aciklama.md"
    s = [("aciklama.md var", yol.exists(), "")]
    if not yol.exists():
        return s
    metin = yol.read_text(encoding="utf-8", errors="replace")
    v = _varyantlar(metin)
    s.append(("tam 3 varyant", len(v) == 3, f"{len(v)}"))
    uzun = [len(_kelimeler(x)) for x in v]
    s.append(("her varyant 40-90 kelime", v and all(40 <= n <= 90 for n in uzun),
              str(uzun)))
    s.append(("her varyantta 'bambu'", v and all("bambu" in x.lower() for x in v), ""))
    kucuk = metin.lower().replace("ı", "i")
    yasak = [y for y in D06_YASAK if y in kucuk]
    s.append(("yasak ifade YOK", not yasak, ", ".join(yasak)))
    en_benzer = 0.0
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            a, b = set(_kelimeler(v[i])), set(_kelimeler(v[j]))
            en_benzer = max(en_benzer, len(a & b) / max(1, len(a | b)))
    s.append(("varyantlar FARKLI (kelime benzerligi < 0,6)", en_benzer < 0.6,
              f"{en_benzer:.2f}"))
    return s


_D06_V = [
    "Sabah rutininize dogadan bir dokunus: Doga bambu dis fircasi, bambu sapi ve "
    "yumusak kilciklariyla dislerinizi nazikce temizler. Plastik yerine yenilenebilir "
    "bambu tercih ederek her fircalamada cevreye kucuk ama anlamli bir katki "
    "sunarsiniz. Hafif govdesi elde rahat durur, seyahat cantasinda yer kaplamaz.",
    "Plastik atigini azaltmak isteyenler icin Doga, bambu govdeli bir dis fircasi "
    "sunuyor. Hizli yetisen bambu kimyasal gubre gerektirmeden buyur; sap "
    "kullanim sonrasi kompost edilebilir. Orta sertlikte kilciklar dis etlerini "
    "yormadan plagi uzaklastirir. Dort kisilik aile paketiyle banyonuza sade bir "
    "duzen gelir ve her firca ayri renkli isaretle ayrilir.",
    "Kucuk degisiklikler buyuk aliskanliklara donusur. Doga bambu dis fircasinin "
    "dogal dokulu sapi islenmemis ahsap hissi verir, tutusu kaymaz. Kilciklar BPA "
    "icermeyen naylondan uretilir ve uc kisimlari incelttildigi icin dar alanlara "
    "ulasir. Kutusu geri donusturulmus kartondan, murekkebi bitkisel. Ucuncu ayin "
    "sonunda degistirmeniz onerilir.",
]


def d06_kuru_iyi(kok, ofis, bag):
    (kok / "aciklama.md").write_text("".join(
        f"## Varyant {i + 1}\n\n{t}\n\n" for i, t in enumerate(_D06_V)), encoding="utf-8")
    return "KANIT dosya: aciklama.md -> 3 varyant"


def d06_kuru_kotu(kok, ofis, bag):
    (kok / "aciklama.md").write_text("".join(
        f"## Varyant {i + 1}\n\n{_D06_V[0]} Piyasanin en iyi bambu fircasi.\n\n"
        for i in range(3)), encoding="utf-8")
    return "KANIT dosya: aciklama.md -> 3 varyant"


# ======================================================================= D07

D07_SAYAC = ('"""Metin dosyasindaki kelimeleri sayar."""\n'
             "import argparse\nimport sys\n\n\n"
             "def say(metin):\n    return len(metin.split())\n\n\n"
             "def main():\n    a = argparse.ArgumentParser(description='kelime sayaci')\n"
             "    a.add_argument('dosya')\n"
             "    a.add_argument('--en-uzun', action='store_true', "
             "help='en uzun kelimeyi de yaz')\n"
             "    ar = a.parse_args()\n"
             "    metin = open(ar.dosya, encoding='utf-8').read()\n"
             "    print(say(metin))\n"
             "    if ar.en_uzun:\n        print(max(metin.split(), key=len))\n\n\n"
             "if __name__ == '__main__':\n    main()\n")


def d07_fikstur(kok, bag):
    (kok / "sayac.py").write_text(D07_SAYAC, encoding="utf-8")
    (kok / "ornek.txt").write_text("bir iki uc dort besinci\n", encoding="utf-8")


D07_GOREV = dict(
    baslik="sayac.py icin README",
    ana_hedef="sayac.py'nin nasil kullanildigini anlatan README.md yaz.",
    kabul_olcutu=("README.md: 'Kullanim' bolumu; komutlar ```bash kod "
                  "bloklarinda, proje klasorunden AYNEN kopyalanip calistirilabilir "
                  "(ornek.txt ile). En az iki komut: biri --help, biri --en-uzun. "
                  "Yazdigin her komutu KENDIN calistirip ciktisini kanit olarak ekle."),
    yazma_alani=["README.md"],
    rol="dokuman")


def d07_dogrula(kok, ofis, bag):
    yol = kok / "README.md"
    s = [("README.md var", yol.exists(), "")]
    if not yol.exists():
        return s
    bloklar = re.findall(r"```(?:bash|sh|shell|console|powershell|ps1|cmd)?\s*\n(.*?)```",
                         yol.read_text(encoding="utf-8", errors="replace"), re.S)
    komutlar = []
    for b in bloklar:
        for l in b.splitlines():
            l = l.strip().lstrip("$>").strip()
            if l.startswith(("python ", "python3 ", "py ")):
                komutlar.append(re.sub(r"^(python3|py)\s", "python ", l))
    s.append(("en az 2 python komutu", len(komutlar) >= 2, f"{len(komutlar)}"))
    s.append(("--help ve --en-uzun var",
              any("--help" in k for k in komutlar)
              and any("--en-uzun" in k for k in komutlar), ""))
    hatali = []
    for k in komutlar[:8]:
        r = subprocess.run([sys.executable] + k.split()[1:], cwd=kok,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            hatali.append(f"{k} -> {r.returncode}")
    s.append(("dogrulayici komutlari KENDISI kosturdu, hepsi calisti",
              bool(komutlar) and not hatali, "; ".join(hatali)))
    return s


def d07_kuru_iyi(kok, ofis, bag):
    (kok / "README.md").write_text(
        "# sayac\n\n## Kullanim\n\n```bash\npython sayac.py --help\n"
        "python sayac.py ornek.txt --en-uzun\n```\n", encoding="utf-8")
    return "KANIT terminal: python sayac.py ornek.txt --en-uzun -> 5 besinci"


def d07_kuru_kotu(kok, ofis, bag):
    (kok / "README.md").write_text(
        "# sayac\n\n## Kullanim\n\n```bash\npython sayac.py --help\n"
        "python sayac.py --en-uzun ornek.md\n```\n", encoding="utf-8")
    return "KANIT terminal: python sayac.py --en-uzun ornek.md -> calisti"


# ======================================================================= D08

D08_GOREV = dict(
    baslik="Kose Kahve kapak gorseli",
    ana_hedef=("Kose Kahve'nin sosyal medya kapagi icin gorsel uret ve "
               "kapak.png olarak kaydet (gorsel_uret araci)."),
    kabul_olcutu=("kapak.png: gecerli PNG, genislik >= 512 px. Ureten saglayici "
                  "ve maliyet/kota bilgisi kanitta yazili."),
    yazma_alani=["kapak.png"],
    rol="tasarim")


def d08_fikstur(kok, bag):
    pass


def _png_boyut(yol: Path):
    # Klasor de olabilir (olculdu: gorsel araci `kapak.png`yi KLASOR yapti
    # ve dogrulayici PermissionError ile COKTU). Cokme degil KALDI.
    ham = yol.read_bytes()[:32] if yol.is_file() else b""
    if ham[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", ham[16:24])


def d08_dogrula(kok, ofis, bag):
    boyut = _png_boyut(kok / "kapak.png")
    with ofis.db.baglanti() as c:
        kanit = c.execute("SELECT count(*) FROM kanit k JOIN gorev g ON g.id=k.gorev_id "
                          "WHERE g.proje_id=?", (ofis.proje_id,)).fetchone()[0]
    return [("kapak.png gecerli PNG", boyut is not None, ""),
            ("genislik >= 512 px", bool(boyut) and boyut[0] >= 512, str(boyut)),
            ("kanit tahtada", kanit >= 1, f"{kanit}")]


def _png(genislik):
    import zlib
    satir = b"\x00" + b"\x80\x40\x20" * genislik
    ham = zlib.compress(satir * 4)

    def parca(t, v):
        return struct.pack(">I", len(v)) + t + v + struct.pack(
            ">I", zlib.crc32(t + v) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + parca(b"IHDR", struct.pack(">IIBBBBB", genislik,
            4, 8, 2, 0, 0, 0)) + parca(b"IDAT", ham) + parca(b"IEND", b""))


def d08_kuru_iyi(kok, ofis, bag):
    (kok / "kapak.png").write_bytes(_png(1024))
    return "KANIT gorsel: kapak.png -> codex, abonelik kotasi"


def d08_kuru_kotu(kok, ofis, bag):
    (kok / "kapak.png").write_bytes(_png(256))
    return "KANIT gorsel: kapak.png -> uretildi"


# ======================================================================= D11

D11_HEDEF = ("Uc BAGIMSIZ kucuk modul yazilsin, her biri kendi testiyle: "
             "sayilar.py (topla(a,b), carp(a,b)), metin.py (ters(s): metni ters "
             "cevirir), tarih.py (gun_farki(a,b): iki ISO tarih (YYYY-AA-GG) "
             "arasindaki gun sayisi, mutlak deger). Sonra hepsi.py'de ozet() "
             "islevi ucunu kullanarak su sozlugu dondursun: "
             "{'toplam': topla(2,3), 'ters': ters('abc'), "
             "'gun': gun_farki('2026-01-01','2026-01-31')}. Uc modul birbirinden "
             "bagimsiz, paralel yazilabilir; hepsi.py ucunu bekler. "
             "`python -m pytest -q` yesil olmali.")


def d11_fikstur(kok, bag):
    pass


def d11_dogrula(kok, ofis, bag):
    s = []
    yesil, son = H._pytest(kok)
    s.append(("pytest yesil", yesil, son))
    r = subprocess.run([sys.executable, "-c",
                        "import hepsi,json;print(json.dumps(hepsi.ozet(),sort_keys=True))"],
                       cwd=kok, capture_output=True, text=True, timeout=60)
    beklenen = json.dumps({"toplam": 5, "ters": "cba", "gun": 30}, sort_keys=True)
    s.append(("hepsi.ozet() DOGRU (dogrulayici kendi cagirdi)",
              r.stdout.strip() == beklenen, (r.stdout or r.stderr).strip()[-160:]))
    with ofis.db.baglanti() as c:
        gorevler = c.execute("SELECT id FROM gorev WHERE proje_id=? AND silindi=0",
                             (ofis.proje_id,)).fetchall()
        bag_sayi = c.execute("SELECT count(*) FROM gorev_bagimlilik b JOIN gorev g ON "
                             "g.id=b.gorev_id WHERE g.proje_id=?",
                             (ofis.proje_id,)).fetchone()[0]
        sahipler = {r[0] for r in c.execute(
            "SELECT DISTINCT ajan_ad FROM olay WHERE proje_id=? AND tur='sahiplenildi' "
            "AND ajan_ad LIKE 'isci%'", (ofis.proje_id,))}
    s.append(("lider BOLDU (>= 3 gorev)", len(gorevler) >= 3, f"{len(gorevler)}"))
    s.append(("birlestirme otekileri BEKLEDI (bagimlilik var)", bag_sayi >= 1, f"{bag_sayi}"))
    s.append(("en az 2 isci calisti", len(sahipler) >= 2, str(sorted(sahipler))))
    s.append(("PARALEL kostu (ayni tikte >= 2 is)", bag.get("paralel_en", 1) >= 2,
              f"{bag.get('paralel_en', 1)}"))
    return s


def _d11_hepsi(kok, bozuk=False):
    H._yaz(kok, "sayilar.py", "def topla(a, b):\n    return a + b\n\n\n"
           "def carp(a, b):\n    return a * b\n")
    H._yaz(kok, "metin.py", "def ters(s):\n    return s[::-1]\n")
    H._yaz(kok, "tarih.py", "from datetime import date\n\n\ndef gun_farki(a, b):\n"
           "    return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)\n")
    H._yaz(kok, "hepsi.py", "from sayilar import topla\nfrom metin import ters\n"
           "from tarih import gun_farki\n\n\ndef ozet():\n"
           "    return {'toplam': topla(2, 3), 'ters': ters('abc'), "
           + ("'gun': 31}\n" if bozuk else "'gun': gun_farki('2026-01-01', '2026-01-31')}\n"))
    H._yaz(kok, "test_hepsi.py", "from hepsi import ozet\n\n\ndef test_ozet():\n"
           "    assert ozet()['toplam'] == 5\n")


def d11_kuru_iyi(kok, ofis, bag):
    _d11_hepsi(kok)
    return "KANIT terminal: python -m pytest -q -> 1 passed"


def d11_kuru_kotu(kok, ofis, bag):
    _d11_hepsi(kok, bozuk=True)
    return "KANIT terminal: python -m pytest -q -> 1 passed"


def d11_kuru_gorevler(ofis, kanat):
    """Kuru kipte lider YOK: plan elle kurulur (dogrulayiciyi sinamak icin)."""
    t = ofis.tahta
    a = t.gorev_ac("sayilar", neden="d", ana_hedef="h", kabul_olcutu="k",
                   yazma_alani=["sayilar.py"], kanat_id=kanat)
    b = t.gorev_ac("metin", neden="d", ana_hedef="h", kabul_olcutu="k",
                   yazma_alani=["metin.py"], kanat_id=kanat)
    t.gorev_ac("hepsi", neden="d", ana_hedef="h", kabul_olcutu="k",
               yazma_alani=["hepsi.py", "tarih.py", "test_hepsi.py"],
               kanat_id=kanat, bagli_oldugu=[a["no"], b["no"]])


# ======================================================================= D12

D12_CEVAP = "Kurumsal renk #1F6FEB, logo dosyasinin adi marka-logo.svg."

D12_GOREV = dict(
    baslik="Marka kunyesi",
    ana_hedef=("kunye.md'ye musterinin KURUMSAL renk kodunu (HEX) ve logo "
               "dosyasinin adini yaz."),
    kabul_olcutu=("kunye.md'de musterinin GERCEK renk kodu ve logo dosya adi. Bu "
                  "bilgi sende yoksa UYDURMA: sor."),
    yazma_alani=["kunye.md"],
    rol="metin")


def d12_fikstur(kok, bag):
    pass


def d12_dogrula(kok, ofis, bag):
    yol = kok / "kunye.md"
    metin = yol.read_text(encoding="utf-8", errors="replace") if yol.exists() else ""
    hexler = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", metin)}
    return [("once SORDU (uydurmadi)", bag.get("soruldu", 0) >= 1,
             f"cevaplanan soru: {bag.get('soruldu', 0)}"),
            ("cevaptaki renk yazildi", "#1F6FEB" in hexler, str(hexler)),
            ("uydurma renk YOK", hexler <= {"#1F6FEB"}, str(hexler)),
            ("logo adi yazildi", "marka-logo.svg" in metin, "")]


def d12_kuru_iyi(kok, ofis, bag):
    bag["cagri"] = bag.get("cagri", 0) + 1
    if bag["cagri"] == 1:
        no = ofis.tahta.liste()[0]["no"]
        ofis.postane.soru_sor("isci", "insan", "Musterinin renk kodu ve logo adi nedir?",
                              gorev_no=no)
        return "Bilgi bende yok; sordum."
    (kok / "kunye.md").write_text("Renk: #1F6FEB\nLogo: marka-logo.svg\n", encoding="utf-8")
    return "KANIT dosya: kunye.md -> yazildi"


def d12_kuru_kotu(kok, ofis, bag):
    (kok / "kunye.md").write_text("Renk: #FF5733\nLogo: logo.png\n", encoding="utf-8")
    return "KANIT dosya: kunye.md -> yazildi"


# ======================================================================= D13

D13_GOREV = dict(
    baslik="Uc adimli rapor",
    ana_hedef=("adim1.txt, adim2.txt, adim3.txt dosyalarini SIRAYLA yaz; her "
               "birinin icine yalniz adim numarasini (1, 2, 3) yaz."),
    kabul_olcutu=("Uc dosya var ve iceriklerinde sirasiyla 1, 2, 3 yaziyor. "
                  "Tamamlanmis bir adim TEKRARLANMAZ."),
    yazma_alani=["adim1.txt", "adim2.txt", "adim3.txt"],
    rol="backend")


def d13_fikstur(kok, bag):
    pass


class _LimitliIlkMotor(SahteMotor):
    """Birinci adimi yapar, DURUM yazar ve kullanim LIMITINE carpar."""

    def __init__(self, kok, bag):
        super().__init__(senaryo="limit")
        self.kok, self.bag = kok, bag

    def tur_kos(self, metin, **ayar):
        self.bag["limit_atildi"] = True
        if not (self.kok / "adim1.txt").exists():
            (self.kok / "adim1.txt").write_text("1\n", encoding="utf-8")
            self.bag["adim1_zaman"] = (self.kok / "adim1.txt").stat().st_mtime_ns
        yield MotorOlayi("metin", "DURUM: adim1.txt yazildi | sirada adim2.txt ve adim3.txt\n")
        yield from super().tur_kos(metin, **ayar)


def d13_fabrika_sar(fabrika, bag, kok):
    """Iscinin ILK basamagi ('sahte' motor) birinci adimi yapip limit
    carpar; zincir sonraki basamaga (gercek motor) devreder.

    Isci 'sahte' motorla ise alinir: kadro yalniz kayitli motor adini
    kabul eder ve ilk basamagi ayirt etmenin tek kararli yolu budur (lider
    de claude kosuyor; "ilk claude cagrisi" hangisi, belirsizdi).
    """
    def sarili(ad, **a):
        if ad == "sahte" and not bag.get("limit_atildi"):
            return _LimitliIlkMotor(kok, bag)
        return fabrika(ad, **a)
    return sarili


def d13_dogrula(kok, ofis, bag):
    s = []
    for i in (1, 2, 3):
        p = kok / f"adim{i}.txt"
        s.append((f"adim{i}.txt = {i}", p.exists()
                  and p.read_text(encoding="utf-8").strip() == str(i), ""))
    a1 = kok / "adim1.txt"
    s.append(("biten adim TEKRARLANMADI (adim1 degismedi)",
              a1.exists() and a1.stat().st_mtime_ns == bag.get("adim1_zaman"), ""))
    with ofis.db.baglanti() as c:
        devir = c.execute("SELECT count(*) FROM olay WHERE proje_id=? AND tur='limit'",
                          (ofis.proje_id,)).fetchone()[0]
        motorlar = [json.loads(r[0] or "{}").get("motor") for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id=? AND tur='tur_ozeti' AND ajan_ad='isci'",
            (ofis.proje_id,))]
    s.append(("limit gorundu ve devredildi", devir >= 1, f"{devir}"))
    s.append(("isi BASKA motor bitirdi",
              any(m and m != "sahte" for m in motorlar), str(motorlar)))
    return s


def d13_kuru_iyi(kok, ofis, bag):
    for i in (2, 3):
        (kok / f"adim{i}.txt").write_text(f"{i}\n", encoding="utf-8")
    return "KANIT dosya: adim2.txt adim3.txt -> yazildi"


def d13_kuru_kotu(kok, ofis, bag):
    for i in (1, 2, 3):              # biten adimi YENIDEN yazar
        time.sleep(0.02)
        (kok / f"adim{i}.txt").write_text(f"{i}\n", encoding="utf-8")
    return "KANIT dosya: adimlar -> yazildi"


# ================================================================== KATALOG

ISLER = {
    "D03": dict(ad="Statik acilis sayfasi", set="tam", fikstur=d03_fikstur,
                gorev=D03_GOREV, dogrula=d03_dogrula, kuru_iyi=d03_kuru_iyi,
                kuru_kotu=d03_kuru_kotu),
    "D04": dict(ad="Kaynakli arastirma tablosu", set="tam", fikstur=d04_fikstur,
                gorev=D04_GOREV, dogrula=d04_dogrula, kuru_iyi=d04_kuru_iyi,
                kuru_kotu=d04_kuru_kotu),
    "D06": dict(ad="Urun aciklamasi, 3 varyant", set="tam", fikstur=d06_fikstur,
                gorev=D06_GOREV, dogrula=d06_dogrula, kuru_iyi=d06_kuru_iyi,
                kuru_kotu=d06_kuru_kotu),
    "D07": dict(ad="README yaz ve adimlari calistir", set="tam", fikstur=d07_fikstur,
                gorev=D07_GOREV, dogrula=d07_dogrula, kuru_iyi=d07_kuru_iyi,
                kuru_kotu=d07_kuru_kotu),
    "D08": dict(ad="Kapak gorseli uret", set="tam", fikstur=d08_fikstur,
                gorev=D08_GOREV, dogrula=d08_dogrula, kuru_iyi=d08_kuru_iyi,
                kuru_kotu=d08_kuru_kotu),
    "D11": dict(ad="Iki kol + birlestirme (lider boler)", set="tam", mod="hedef",
                hedef=D11_HEDEF, isci_sayisi=3, fikstur=d11_fikstur,
                dogrula=d11_dogrula, kuru_iyi=d11_kuru_iyi, kuru_kotu=d11_kuru_kotu,
                kuru_gorevler=d11_kuru_gorevler, rol="backend"),
    "D12": dict(ad="Eksik bilgiyle is -- sorar, uydurmaz", set="tam",
                fikstur=d12_fikstur, gorev=D12_GOREV, dogrula=d12_dogrula,
                kuru_iyi=d12_kuru_iyi, kuru_kotu=d12_kuru_kotu,
                insan_cevabi=D12_CEVAP),
    "D13": dict(ad="Tur ortasinda limit (enjekte)", set="tam", fikstur=d13_fikstur,
                gorev=D13_GOREV, dogrula=d13_dogrula, kuru_iyi=d13_kuru_iyi,
                kuru_kotu=d13_kuru_kotu, fabrika_sar=d13_fabrika_sar,
                isci_motor="sahte"),
}
