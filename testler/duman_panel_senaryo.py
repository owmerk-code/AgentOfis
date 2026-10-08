# -*- coding: utf-8 -*-
"""PANEL SENARYOLARI -- gercek tarayicida, gercek dugmeye tiklayarak (E55).

Panelin JS'i su ana kadar ya Node'da (saf islevler) ya da ELLE, tarayicida
DOM olculerek sinaniyordu. Elle olan tekrarlanamaz. Bu dosya ornek ofisin
GECICI kopyasini gercek bir sunucuda acar, bassiz Chrome'la baglanir ve
insanin yaptigini yapar: dugmeye tiklar, kutuya yazar. Sonucu DOM'dan
degil DEFTERDEN olcer -- dugme "tamam" dese bile kayit degismediyse KALDI.

Senaryolar:
  S1 Surdur        -> halka doner, yeni tur olculur
  S2 Bos ret       -> gerekcesiz ret ISTEK GITMEDEN durur
  S3 Bir kez       -> onay 'onaylandi', kapsam DAR ('eylem')
  S4 Cevapla       -> soru cevaplanir, cevap deftere yazilir
  S5 Ajana sor     -> cip -> cekmece -> soru -> cevap sohbette

GERCEK MOTOR YASAK (panel.MOTOR_FABRIKASI yalniz 'sahte' uretir). Chrome
yoksa ATLANDI der, gecti saymaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "testler"))

import ofis.panel as P                          # noqa: E402
from ofis import kabin as KB, tarayici as T     # noqa: E402
from ofis import Veritabani                      # noqa: E402
from ofis.motor.sahte import SahteMotor          # noqa: E402
import ornek_ofis                                # noqa: E402

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


def _bos_kapi() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    k = s.getsockname()[1]
    s.close()
    return k


def _yalniz_sahte(ad, **kw):
    if str(ad).strip().lower() != "sahte":
        raise RuntimeError(f"SINAMA gercek motora uzandi: {ad}")
    return SahteMotor(**kw)


P.MOTOR_FABRIKASI = _yalniz_sahte

chrome = KB.calistirilabilir_bul()
if not chrome:
    print("  [ATLANDI] Chrome yok -- panel senaryolari OLCULEMEDI (gecti SAYILMAZ)")
    print("\n== sonuc: 0 gecti, 0 kaldi ==")
    sys.exit(0)

ANA = Path(tempfile.mkdtemp(prefix="ofis-panel-senaryo-"))
DB = ANA / "ornek.sqlite3"
ornek_ofis.kur(DB)
db = Veritabani(DB)

import uvicorn                                   # noqa: E402
PANEL_KAPI = _bos_kapi()
sunucu = uvicorn.Server(uvicorn.Config(P.olustur(str(DB)), host="127.0.0.1",
                                       port=PANEL_KAPI, log_level="warning"))
threading.Thread(target=sunucu.run, daemon=True).start()
ADRES = f"http://127.0.0.1:{PANEL_KAPI}"
for _ in range(100):
    if sunucu.started:
        break
    time.sleep(0.1)


def api(yol):
    with urllib.request.urlopen(ADRES + yol, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def sayi(sql, *par):
    with db.baglanti() as c:
        return c.execute(sql, par).fetchone()[0]


def bekle_py(kosul, sure=30.0):
    son = time.time() + sure
    while time.time() < son:
        try:
            if kosul():
                return True
        except Exception:                        # noqa: BLE001
            pass
        time.sleep(0.25)
    return False


CDP_KAPI = _bos_kapi()
_profil = tempfile.mkdtemp(prefix="ofis-panel-prof-")
_tmp = tempfile.mkdtemp(prefix="ofis-panel-tmp-")
tarayici = subprocess.Popen(
    # Sinama tarayicisi guncelleyici CALISTIRMAZ: 27.09'da Chrome'un bileseni
    # gecici klasore `chrome_chrome_BITS_*` birakti ve silinemedi (BITS
    # hizmeti tutuyor). Kullanicinin kabinine DOKUNULMAZ; bu yalniz sinamada.
    T.kabin_komutu(chrome, profil=_profil, kapi=CDP_KAPI, baslangic="about:blank")
    + ["--disable-component-update", "--disable-background-networking"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env=dict(os.environ, TEMP=_tmp, TMP=_tmp))


async def senaryolar():
    import websockets
    for _ in range(80):
        if KB.acik_mi(CDP_KAPI):
            break
        await asyncio.sleep(0.25)
    async with websockets.connect(KB.sayfa_ws(CDP_KAPI), max_size=None) as c:
        n = [0]

        async def cdp(yontem, par=None):
            n[0] += 1
            await c.send(json.dumps({"id": n[0], "method": yontem, "params": par or {}}))
            while True:
                v = json.loads(await c.recv())
                if v.get("id") == n[0]:
                    return v.get("result") or {}

        async def js(ifade):
            r = await cdp("Runtime.evaluate", {"expression": ifade,
                                               "returnByValue": True,
                                               "awaitPromise": True})
            return (r.get("result") or {}).get("value")

        async def bekle_js(ifade, sure=20.0):
            son = time.time() + sure
            while time.time() < son:
                if await js(ifade):
                    return True
                await asyncio.sleep(0.25)
            return False

        async def not_metni():
            return await js("(document.querySelector('#eylem-notu')||{}).textContent||''")

        await cdp("Emulation.setDeviceMetricsOverride",
                  {"width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await cdp("Page.navigate", {"url": ADRES + "/"})

        print("\n0. PANEL YUKLENDI")
        sina("kuyrukta istek kartlari", await bekle_js(
            "document.querySelectorAll('.istek').length > 0"))
        hatalar = []

        # ---------------------------------------------------- S1 SURDUR
        print("\nS1. SURDUR -- halka doner, yeni tur OLCULUR")
        tur_once = sayi("SELECT count(*) FROM olay WHERE tur='tur_ozeti'")
        await js("document.querySelector('#komut-surdur').click(), true")
        # Bildirim 12 sn sonra kendiliginden silinir: halkanin bitmesini
        # BEKLEMEDEN okunur (ilk surum sonra bakip bos gordu).
        await bekle_js("(document.querySelector('#eylem-notu')||{}).textContent", 5)
        surdur_notu = (await not_metni()).lower()
        sina("tur_ozeti artti (halka gercekten dondu)", bekle_py(
            lambda: sayi("SELECT count(*) FROM olay WHERE tur='tur_ozeti'") > tur_once, 40),
            f"once {tur_once}")
        sina("halka bitti (lider-durum calismiyor)", bekle_py(
            lambda: not api("/api/lider-durum").get("calisiyor"), 60))
        sina("insana bildirildi (eylem notu)", "halka" in surdur_notu
             or "sürdür" in surdur_notu, surdur_notu)

        # ---------------------------------------------------- S2 BOS RET
        print("\nS2. GEREKCESIZ RET -- istek GITMEDEN durur")
        await bekle_js("document.querySelectorAll('.istek:not(.soru)').length > 0")
        onay_id = await js("""(() => { const k = [...document.querySelectorAll('.istek')]
            .find(x => !x.classList.contains('soru'));
            return k ? (k.querySelector('button') ? 'var' : '') : ''; })()""")
        bekleyen_once = sayi("SELECT count(*) FROM onay WHERE durum='bekliyor'")
        # Uyari tiklamayla AYNI anda okunur: kuyruk kendiliginden tazelenir
        # ve kart yeniden cizilince uyari kaybolur (olculdu, 1 sn yetti).
        ret_uyarisi = await js("""(() => { const k = [...document.querySelectorAll('.istek')]
            .find(x => !x.classList.contains('soru'));
            [...k.querySelectorAll('button')].find(b => b.textContent.trim()==='Reddet').click();
            return k.querySelector('input').placeholder; })()""") or ""
        await asyncio.sleep(1.0)
        sina("onay kartı vardı", onay_id == "var")
        sina("bos ret ISTEK YOLLAMADI (onay hala bekliyor)",
             sayi("SELECT count(*) FROM onay WHERE durum='bekliyor'") == bekleyen_once)
        # IKI KAPI var (panel + sunucu). Sinanan PANELIN kapisi: istek HIC
        # gitmemeli. Ilk surum yalniz "onay hala bekliyor"a bakiyordu ve
        # panel kapisi koparilinca sunucu reddettigi icin FARKI GORMEDI.
        sina("panel kendi uyarisini gosterdi", "gerekçesi zorunlu" in ret_uyarisi,
             ret_uyarisi)
        sina("sunucuya istek GITMEDI (hata bildirimi yok)",
             "kotu" not in (await js(
                 "(document.querySelector('#eylem-notu')||{}).className||''") or ""),
             await not_metni())

        # ---------------------------------------------------- S3 BIR KEZ
        print("\nS3. BIR KEZ -- onaylandi, kapsam DAR")
        await js("""(() => { const k = [...document.querySelectorAll('.istek')]
            .find(x => !x.classList.contains('soru'));
            [...k.querySelectorAll('button')].find(b => b.textContent.trim()==='Bir kez').click();
            return true; })()""")
        sina("onay deftere 'onaylandi' dustu", bekle_py(
            lambda: sayi("SELECT count(*) FROM onay WHERE durum='onaylandi'") >= 1, 15))
        sina("kapsam DAR ('eylem')", sayi(
            "SELECT count(*) FROM onay WHERE durum='onaylandi' AND kapsam='eylem'") >= 1)
        # Defter YAZILDIKTAN sonra panel bildirimi bir an sonra cizer; hemen
        # bakmak yaristi (27.09: yuklu makinede bos metin okundu).
        bildirim = ""
        for _ in range(30):
            bildirim = (await not_metni()).lower()
            if "bir kez" in bildirim:
                break
            await asyncio.sleep(0.2)
        sina("bildirim 'bir kez'", "bir kez" in bildirim, bildirim)

        # ---------------------------------------------------- S4 CEVAPLA
        print("\nS4. CEVAPLA -- soru cevaplanir, deftere yazilir")
        var = await bekle_js("document.querySelectorAll('.istek.soru').length > 0", 15)
        sina("insana soru karti var", var)
        cevap = "Evet, sinama cevabi 4711."
        await js(f"""(() => {{ const k = document.querySelector('.istek.soru');
            const g = k.querySelector('input'); g.value = {json.dumps(cevap)};
            g.dispatchEvent(new Event('input'));
            [...k.querySelectorAll('button')].find(b => b.textContent.trim()==='Cevapla').click();
            return true; }})()""")
        sina("cevap deftere yazildi", bekle_py(lambda: sayi(
            "SELECT count(*) FROM mesaj WHERE cevap LIKE '%4711%'") == 1, 15))
        sina("bildirim 'cevap gönderildi'", "cevap" in (await not_metni()).lower(),
             await not_metni())

        # ---------------------------------------------------- S5 AJANA SOR
        print("\nS5. AJANA SOR -- cip -> cekmece -> soru -> cevap sohbette")
        sohbet_once = len(api("/api/sohbet").get("mesajlar", api("/api/sohbet"))
                          if isinstance(api("/api/sohbet"), dict) else api("/api/sohbet"))
        ad = await js("""(() => { const c = document.querySelector('.kadro-cip');
            if (!c) return ''; c.click(); return c.textContent; })()""")
        sina("ajan cipi tiklandi", bool(ad), str(ad))
        # Cip ajanin TERMINALINI acar (ofisin icinde); cekmece oradaki
        # "ayrıntı" dugmesiyle acilir -- insanin izledigi yol.
        sina("terminalde 'ayrıntı' dugmesi", await bekle_js(
            "[...document.querySelectorAll('button')].some(b => b.textContent.trim()==='ayrıntı')", 10))
        await js("[...document.querySelectorAll('button')].find(b => b.textContent.trim()==='ayrıntı').click(), true")
        acildi = await bekle_js("""[...document.querySelectorAll('input')]
            .some(i => (i.placeholder||'').includes('bir soru'))""", 10)
        sina("cekmecede soru kutusu acildi", acildi)
        await js("""(() => { const g = [...document.querySelectorAll('input')]
            .find(i => (i.placeholder||'').includes('bir soru'));
            g.value = 'Hangi isi bitirdin?'; g.dispatchEvent(new Event('input'));
            const b = [...g.parentElement.querySelectorAll('button')]
            .find(b => b.textContent.trim()==='Sor'); b.click(); return true; })()""")
        sina("soru deftere dustu", bekle_py(lambda: sayi(
            "SELECT count(*) FROM mesaj WHERE govde LIKE '%Hangi isi bitirdin%'") == 1, 15))
        sina("ajan CEVAPLADI (sahte motor, danisma katmani)", bekle_py(lambda: sayi(
            "SELECT count(*) FROM mesaj WHERE govde LIKE '%Hangi isi bitirdin%' "
            "AND cevap != ''") == 1, 30))
        # Cevap halkayi KENDILIGINDEN surdurur; sinama kapanmadan once o
        # halkanin bitmesi beklenir -- yoksa yorumlayici kapanirken arka
        # plan halkasi "cannot schedule new futures" ile yarida kesilir.
        sina("arka plan halkasi bitti (kapanis temiz)", bekle_py(
            lambda: not api("/api/lider-durum").get("calisiyor"), 90))
        konsol = await js("window.__hatalar ? window.__hatalar.length : 0")
        return hatalar, sohbet_once, konsol


try:
    asyncio.run(senaryolar())
except Exception as exc:                         # noqa: BLE001
    sina("senaryolar COKMEDEN tamamlandi", False, f"{exc.__class__.__name__}: {exc}")
finally:
    # SUREC AGACI kapatilir: yalniz ana Chrome sureci durdurulunca alt
    # surecler gecici klasoru tutmaya devam etti ve klasor SILINEMEDI.
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(tarayici.pid)],
                       capture_output=True)
    else:
        tarayici.kill()
    try:
        tarayici.wait(timeout=10)
    except Exception:                            # noqa: BLE001
        pass
    sunucu.should_exit = True
    time.sleep(0.5)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
