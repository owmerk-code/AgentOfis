# -*- coding: utf-8 -*-
"""KABIN -- panelin ICINDE yasayan, ajanla PAYLASILAN tarayici.

Kullanici: *"sistemden cikip baska yerden chrome acip ugrasmak
istemem; sistemin icinde tarayici olsa, hic cikmadan kullanabilsem."*

Bu modul o tarayicinin SURECINI yonetir. Kurallari ve olcumleri
`tarayici.py`nin "KABIN" bolumunde yaziyor; burada yalnizca omur
yonetimi ve CDP kopru yardimcilari var.

NEDEN AYRI MODUL: `tarayici.py` SAFTIR -- komut satiri kurar, hicbir
surec baslatmaz, bu yuzden jeton yakmadan sinanabilir. Uzun omurlu bir
Chrome sureci oraya girseydi o saflik giderdi. Panel bu modulu tutar
cunku kabinin omru panelin omrudur.

UC KURAL, ucu de olculmus bir sebebe dayaniyor:

1. **AYRI PROFIL, ZORUNLU.** Kabin kullanicinin gunluk Chrome'u
   degildir. Ajan bu tarayiciya CDP ile baglanir; ayni profil olsaydi
   butun kisisel oturumlar (banka, e-posta) ajanin eline gecerdi.
   Profil proje kokunun DISINDA (`~/.agentofis/`) -- cerez bir calisma
   durumudur, proje verisi degil, ve ajanlarin `Bash(cat *)` izni
   proje kokunde geciyor.

2. **CDP YEREL BIR ARKA KAPIDIR.** Uzak hata ayiklama kapisi
   127.0.0.1'e baglidir ama makinede kosan HER SEY o tarayiciyi
   surebilir. Panelin `0.0.0.0` reddiyle ayni siniftan bir karar; bu
   yuzden kapi yazili, varsayilan dar, ve kabin ISTENMEDIKCE ACILMAZ.

3. **UYDURMAZ.** Kabin kapaliysa "kapali" der; Chrome bulunamazsa
   hangi yollara baktigini ve hangi ortam degiskeniyle
   gecersiz kilinacagini soyler. `saglik.py` kurali: olcemedigine
   "iyi" demeyiz.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess

from .surec import PENCERE_YOK
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

from . import tarayici
from .gizli import VARSAYILAN_DEPO


class KabinHatasi(RuntimeError):
    pass


#: Olculdu (22.09.2026): kullanicinin makinesinde bu yol var.
#: Once GERCEK Chrome denenir -- kullanicinin tanidigi tarayici odur.
#: Playwright'in kendi chromium'u son care: vardir ama yabancidir.
CHROME_YOLLARI = (
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
)

#: Elle gecersiz kilma. `claude.py`nin `OFIS_CLAUDE_YOLU`suyla ayni
#: desen: bir yol tahmini her zaman yanilabilir, ve yanildiginda
#: kullanicinin elinde bir kol olmali.
ORTAM_ANAHTARI = "OFIS_CHROME_YOLU"


def calistirilabilir_bul() -> str:
    """Kabinin acacagi tarayici. Bulunamazsa NEREYE BAKTIGINI soyler."""
    elle = os.environ.get(ORTAM_ANAHTARI, "").strip()
    if elle:
        if not Path(elle).is_file():
            raise KabinHatasi(
                f"{ORTAM_ANAHTARI} gosterdigi dosya yok: {elle}")
        return elle
    for y in CHROME_YOLLARI:
        if Path(y).is_file():
            return y
    bulunan = shutil.which("chrome") or shutil.which("msedge")
    if bulunan:
        return bulunan
    # Son care: Playwright'in indirdigi chromium.
    kok = Path.home() / "AppData/Local/ms-playwright"
    if kok.is_dir():
        for alt in sorted(kok.glob("chromium-*/chrome-win/chrome.exe")):
            return str(alt)
    raise KabinHatasi(
        "Tarayici bulunamadi. Bakilan yerler: "
        + ", ".join(CHROME_YOLLARI)
        + f", PATH, ms-playwright. Elle vermek icin: {ORTAM_ANAHTARI}=...")


def profil_yolu() -> str:
    """Kabin profili -- proje kokunun DISINDA, kasayla ayni klasorde.

    `OFIS_KABIN_PROFIL` (02.10.2026): olcum paneli ofisin GERCEK evini
    (codex girisi) kullanirken kabin profili patronun canli kabininin
    profiliyle CAKISMASIN (ayni profil iki Chrome'da acilamaz)."""
    if os.environ.get("OFIS_KABIN_PROFIL"):
        p = Path(os.environ["OFIS_KABIN_PROFIL"])
        p.mkdir(parents=True, exist_ok=True)
        return str(p)
    p = Path(VARSAYILAN_DEPO).parent / tarayici.KABIN_PROFIL_ADI
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def gunluk_yolu() -> str:
    """Kabin Chrome'unun kendi hata cikisi -- profilin yaninda.

    OLCULDU (24.09.2026): kullanici "gomulu tarayici calismiyor" dedi.
    Chrome'un stderr'i DEVNULL'a gidiyordu ve kabin acilir-kapanir-olur
    hicbir yere yazilmiyordu; profilde yalniz `exit_type: Crashed`
    vardi -- ki onu terminate() de birakir. Sebebi olculemeyen bir
    arizanin tek izi, sebebi soylemeyen bir izdi.
    """
    return str(Path(profil_yolu()).parent / "kabin.log")


def _son_satirlar(yol: str, n: int = 8) -> str:
    try:
        ham = Path(yol).read_bytes()[-4000:]
    except OSError:
        return ""
    satirlar = ham.decode("utf-8", "replace").splitlines()
    return "\n".join(s for s in satirlar[-n:] if s.strip())


def _surum(kapi: int, zaman_asimi: float = 1.0):
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{kapi}/json/version",
                timeout=zaman_asimi) as y:
            return json.loads(y.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def acik_mi(kapi: int = tarayici.KABIN_KAPISI) -> bool:
    """CDP kapisi CEVAP VERIYOR mu.

    Surecin PID'ine bakmiyoruz bilerek: surec yasayip CDP'si olmeyebilir
    (cokme, port cakismasi), ve o zaman gosterge "acik" derken kabin
    kullanilamaz olurdu -- yanlis gosteren gosterge.
    """
    return _surum(kapi) is not None


def eski_kimlikli_mi(kapi: int = tarayici.KABIN_KAPISI) -> bool:
    """Kapidaki kabin kendini "HeadlessChrome" diye mi tanitiyor.

    02.10.2026 OLCULDU (patronun ekrani): duzeltmeden ONCE acilmis kabin
    panel yeniden baslayinca YENIDEN KULLANILDI; kimlik duzeltmesi hic
    devreye girmedi, Google robot dogrulamasi istedi. Bassiz kabin artik
    normal kimlikle acilir; eski kimlikli kabin yeniden baslatilmalidir."""
    s = _surum(kapi) or {}
    return "Headless" in str(s.get("User-Agent") or "")


def cdp_kapat(kapi: int = tarayici.KABIN_KAPISI, bekle_sn: float = 8.0) -> bool:
    """Kapidaki kabin Chrome'unu CDP ile KAPATIR (`Browser.close`).

    Bu panelin baslatmadigi (onceki oturumdan kalan) kabin icin: surec
    elimizde yok ama kabin kapisi bizim -- yalniz 127.0.0.1 ve kabin
    kapisi. Patronun KISISEL Chrome'u bu kapida dinlemez. Doner: kapandi mi."""
    s = _surum(kapi)
    if not s:
        return True
    try:
        from websockets.sync.client import connect
        with connect(s["webSocketDebuggerUrl"], open_timeout=5,
                     max_size=None, origin=None) as ws:
            ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
    except Exception:                    # noqa: BLE001 -- kapanirken baglanti kopar
        pass
    bitis = time.time() + bekle_sn
    while time.time() < bitis:
        if not acik_mi(kapi):
            return True
        time.sleep(0.25)
    return not acik_mi(kapi)


class IndirmeYeri:
    """Kabinin indirmelerini bir klasore yonlendirir -- BAGLANTI ACIK KALDIKCA.

    06.10.2026 canli gosteri OLCTU: ajanin Flow'dan indirdigi video patronun
    KENDI `Indirilenler` klasorune dustu; ajan oradan kopyalarken klasorun
    listesini de okudu. 07.10 OLCULDU: `Browser.setDownloadBehavior` yalniz
    onu kuran CDP baglantisi ACIKKEN gecerli -- baglanti kapaninca Chrome
    varsayilana doner (ilk surum ayarlayip baglantiyi kapatiyordu; sinama
    dosyasi patronun Indirilenler'ine dustu). Baglanti tur boyunca bir
    iplikte tutulur; `bitir()` kapatir (Chrome kendiliginden geri doner).
    """

    def __init__(self, cdp: str, yol: str) -> None:
        import re as _re
        import threading as _th
        self.tamam = False
        self._dur = _th.Event()
        self._hazir = _th.Event()
        m = _re.search(r":(\d+)", str(cdp or ""))
        s = _surum(int(m.group(1))) if m else None
        if not s:
            return
        self._ip = _th.Thread(target=self._tut, args=(s["webSocketDebuggerUrl"], str(yol)),
                              name="kabin-indirme", daemon=True)
        self._ip.start()
        self._hazir.wait(8)

    def _tut(self, ws_url: str, yol: str) -> None:
        try:
            from websockets.sync.client import connect
            with connect(ws_url, open_timeout=5, max_size=None, origin=None) as ws:
                ws.send(json.dumps({"id": 1, "method": "Browser.setDownloadBehavior",
                                    "params": {"behavior": "allow", "downloadPath": yol,
                                               "eventsEnabled": False}}))
                for _ in range(20):
                    c = json.loads(ws.recv(timeout=5))
                    if c.get("id") == 1:
                        self.tamam = "error" not in c
                        break
                self._hazir.set()
                while not self._dur.is_set():
                    try:
                        ws.recv(timeout=1.0)
                    except TimeoutError:
                        continue
        except Exception:                # noqa: BLE001 -- indirme yeri isi durdurmaz
            pass
        finally:
            self._hazir.set()

    def bitir(self) -> None:
        self._dur.set()
        ip = getattr(self, "_ip", None)
        if ip is not None:
            ip.join(5)


def indirme_yeri(cdp: str, yol: str):
    """Kabin indirmelerini `yol`a yonlendiren tutucu; kurulamazsa None (is durmaz)."""
    t = IndirmeYeri(cdp, yol)
    return t if t.tamam else None


#: Kabin acilinca ve yeni sekmede gidilen sayfa (02.10.2026, patron:
#: "chrome gibi google ile acilsa").
ACILIS_SAYFASI = "https://www.google.com/"

_SEKME_KIMLIGI = __import__("re").compile(r"^[A-Za-z0-9_-]{1,64}$")


def _cdp_json(kapi: int, yol: str, yontem: str = "GET"):
    r = urllib.request.Request(f"http://127.0.0.1:{kapi}{yol}", method=yontem)
    try:
        with urllib.request.urlopen(r, timeout=3.0) as y:
            govde = y.read().decode("utf-8")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        raise KabinHatasi(f"Kabine ulasilamadi: {exc}")
    try:
        return json.loads(govde)
    except ValueError:
        return govde


def sekmeler(kapi: int = tarayici.KABIN_KAPISI) -> list:
    """Kabindeki SAYFA sekmeleri: [{id, baslik, adres}] (Chrome'un kendi
    ic sayfalari ve eklenti arka planlari sayilmaz).

    SEKMELER (02.10.2026, patron: "tarayicida sekme acma neden yok"):
    panel yalniz ILK sekmeyi akitiyordu; yeni sekmede acilan baglanti
    panelde hic gorunmuyordu."""
    out = []
    for h in _cdp_json(kapi, "/json") or []:
        if h.get("type") != "page" or not h.get("webSocketDebuggerUrl"):
            continue
        adres = str(h.get("url") or "")
        if adres.startswith(("chrome://", "chrome-extension://", "devtools://")):
            continue
        out.append({"id": h.get("id"), "baslik": str(h.get("title") or adres)[:80],
                    "adres": adres})
    return out


def sekme_ac(kapi: int = tarayici.KABIN_KAPISI, adres: str = "") -> dict:
    """Yeni sekme (bos verilirse acilis sayfasi). Chrome `PUT /json/new`."""
    from urllib.parse import quote
    hedef = (adres or ACILIS_SAYFASI).strip()
    if not hedef.startswith(("http://", "https://", "about:")):
        raise KabinHatasi("Sekme yalniz http(s) adresiyle acilir.")
    h = _cdp_json(kapi, "/json/new?" + quote(hedef, safe=":/?&=%#+"), "PUT")
    if not isinstance(h, dict) or not h.get("id"):
        raise KabinHatasi(f"Sekme acilamadi: {h}")
    return {"id": h["id"], "baslik": h.get("title") or hedef, "adres": hedef}


def sekme_kapat(kapi: int, kimlik: str) -> None:
    if not _SEKME_KIMLIGI.match(kimlik or ""):
        raise KabinHatasi("Gecersiz sekme kimligi.")
    if len(sekmeler(kapi)) <= 1:
        # Son sekme kapanirsa Chrome bassizda sayfasiz kalir; acilis
        # sayfasina dondurmek, "tarayici gitti" sanilmasindan iyidir.
        sekme_ac(kapi)
    _cdp_json(kapi, f"/json/close/{kimlik}")


def sayfa_ws(kapi: int = tarayici.KABIN_KAPISI, sekme: str = "") -> str:
    """Akitilacak sekmenin CDP WebSocket adresi. `sekme` verilip
    bulunamazsa (kapanmis) ilk sekmeye dusulur."""
    liste = _cdp_json(kapi, "/json") or []
    sayfalar = [h for h in liste if h.get("type") == "page" and h.get("webSocketDebuggerUrl")
                and not str(h.get("url") or "").startswith(("chrome://", "chrome-extension://",
                                                             "devtools://"))]
    for h in sayfalar:
        if sekme and h.get("id") == sekme:
            return h["webSocketDebuggerUrl"]
    if sayfalar:
        return sayfalar[0]["webSocketDebuggerUrl"]
    raise KabinHatasi("Kabinde akitilacak sekme yok.")


class Kabin:
    """Paylasilan tarayicinin omru. Panel bir tane tutar."""

    def __init__(self, kapi: int = tarayici.KABIN_KAPISI) -> None:
        self.kapi = int(kapi)
        self.surec = None
        #: Bizim actigimiz kabin bassiz mi. Disarida zaten acik bir
        #: kabine baglaniyorsak BILMIYORUZ -- o zaman uydurmuyoruz.
        self.gorunur = None
        #: Kendi actigimiz surec kendiliginden oldu mu; olum BIR KEZ
        #: bildirilir (panel her durum sorusunda yeni bir olay yazmasin).
        self._olum_bildirildi = False

    def olum(self) -> dict | None:
        """Panelin actigi kabin KAPATILMADAN oldu mu. Bir kez doner.

        Kapatmayi `kapat()` yapar ve sureci unutur; yani burada olu bir
        surec gorulmesi, kimsenin istemedigi bir olumdur.
        """
        if not self.surec or self.surec.poll() is None:
            return None
        if self._olum_bildirildi:
            return None
        self._olum_bildirildi = True
        return {"cikis": self.surec.returncode,
                "son_hata": _son_satirlar(gunluk_yolu())}

    #: Chrome'un "profil baska bir Chrome'da acik" cikis kodu.
    PROFIL_KILITLI = 21

    def ac(self, baslangic: str = "about:blank", bekle_sn: float = 20.0,
           *, gorunur: bool = False) -> dict:
        """Kabini acar. PROFIL KILITLIYSE (02.10.2026 olculdu: yeni kapanan
        tarayicinin kilidi birkac saniye kalir) 3 sn bekleyip BIR KEZ
        yeniden dener. Kilidi tutan Chrome KAPATILMAZ: baska bir panelin
        CANLI kabini olabilir (olculdu: sinama paneli patronun kabininin
        profiline denk geldi). Olmazsa sebep duz soylenir."""
        try:
            return self._ac(baslangic, bekle_sn, gorunur=gorunur)
        except KabinHatasi as exc:
            if getattr(exc, "cikis", None) != self.PROFIL_KILITLI:
                raise
        time.sleep(3)
        try:
            return self._ac(baslangic, bekle_sn, gorunur=gorunur)
        except KabinHatasi as exc:
            if getattr(exc, "cikis", None) != self.PROFIL_KILITLI:
                raise
            yeni = KabinHatasi(
                "Tarayici profili baska bir Chrome'da acik (baska bir panelin "
                "tarayicisi ya da yeni kapanmis bir tarayici). O panelin "
                "tarayicisini kapat ya da biraz sonra yeniden dene. Ayrinti: "
                + str(exc)[:300])
            yeni.cikis = self.PROFIL_KILITLI
            raise yeni from exc

    def _ac(self, baslangic: str = "about:blank", bekle_sn: float = 20.0,
            *, gorunur: bool = False) -> dict:
        # ESKI KIMLIKLI KABIN yeniden kullanilmaz: kapatilir, yeni
        # ayarlarla acilir (bkz. `eski_kimlikli_mi`).
        if acik_mi(self.kapi) and not gorunur and eski_kimlikli_mi(self.kapi):
            cdp_kapat(self.kapi)
            time.sleep(1.5)                # profil kilidi birakilsin
        """Kabini acar. ZATEN ACIKSA yenisini baslatmaz.

        Ikinci bir Chrome ayni profille acilamaz (kilit) ve ayni kapiyi
        dinleyemez; sessizce denemek, kullaniciya "actim" deyip hicbir
        sey acmamak olurdu.

        `gorunur=True` pencereyi ACAR ve kabin artik "gomulu" degildir
        -- gerekcesi `tarayici.kabin_komutu` docstring'inde: bazi
        siteler bassiz tarayiciya giris vermiyor olabilir ve bunu
        OLCMEDIK. Olcmedigimiz bir sey insani kilitlemesin diye kol
        var; varsayilan degil.
        """
        if acik_mi(self.kapi):
            return self.durum()
        komut = tarayici.kabin_komutu(
            calistirilabilir_bul(), profil=profil_yolu(), kapi=self.kapi,
            baslangic=baslangic, gorunur=gorunur)
        gunluk = gunluk_yolu()
        with open(gunluk, "ab") as g:
            g.write(f"\n--- kabin aciliyor {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    f" kapi={self.kapi}\n".encode("utf-8"))
            self.surec = subprocess.Popen(
                komut, stdout=subprocess.DEVNULL, stderr=g, creationflags=PENCERE_YOK)
        # PANELLE BIRLIKTE KAPANIR (08.10.2026 OLCULDU): panel durdurulunca
        # (gosteri paneli yeniden baslatildi) kabin Chrome'u saatlerce yasadi,
        # profili kilitli tuttu; patronun panelinin tarayicisi "profil baska
        # bir Chrome'da acik" diye ACILAMADI. Is nesnesi: panel sureci olunce
        # (oldurulse bile) Windows kafesi kapatir, Chrome da biter.
        from .motor.tip import SurecKafesi
        self.kafes = SurecKafesi(self.surec)
        self.gorunur = bool(gorunur)
        self._olum_bildirildi = False
        bitis = time.time() + bekle_sn
        while time.time() < bitis:
            if acik_mi(self.kapi):
                return self.durum()
            # Surec olduyse beklemenin anlami yok -- ve sebebi soylenir.
            if self.surec.poll() is not None:
                self._olum_bildirildi = True
                # E1 (08.10.2026 OLCULDU): kayittaki "sebepsiz" olumlerin
                # hepsi profil kilidiydi (cikis 21) ama kayit cikis kodunu
                # tutmuyordu. Artik tutar.
                try:
                    with open(gunluk, "ab") as g:
                        g.write(f"--- kabin kapandi cikis={self.surec.returncode}"
                                f"{' (profil baska Chrome da acik)' if self.surec.returncode == self.PROFIL_KILITLI else ''}"
                                "\n".encode("utf-8"))
                except OSError:
                    pass
                hata = KabinHatasi(
                    f"Kabin Chrome'u acilirken kapandi (cikis "
                    f"{self.surec.returncode}). Son satirlar ({gunluk}):\n"
                    + (_son_satirlar(gunluk) or "(cikti yok)"))
                hata.cikis = self.surec.returncode
                raise hata
            time.sleep(0.25)
        # Acilmadiysa SESSIZ kalmiyoruz: "actim" deyip bosluk gostermek,
        # panelin cevapladigi tek soruyu ("neye bakmaliyim") kirletir.
        raise KabinHatasi(
            f"Kabin {bekle_sn:.0f} sn icinde CDP kapisini acmadi "
            f"(127.0.0.1:{self.kapi}). Baska bir Chrome ayni profili "
            "tutuyor olabilir.")

    def kapat(self) -> dict:
        kafes = getattr(self, "kafes", None)
        if self.surec and self.surec.poll() is None:
            self.surec.terminate()
            try:
                self.surec.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.surec.kill()
        elif acik_mi(self.kapi):
            # ONCEKI OTURUMDAN KALAN kabin (02.10.2026): surec elimizde
            # degildi ve panelin carpisi onu KAPATAMIYORDU.
            cdp_kapat(self.kapi)
        if kafes is not None:
            try:
                kafes.kapat()
            except Exception:                    # noqa: BLE001 -- zaten kapanmis olabilir
                pass
        self.kafes = None
        self.surec = None
        self.gorunur = None
        return self.durum()

    def durum(self) -> dict:
        acik = acik_mi(self.kapi)
        s = _surum(self.kapi) if acik else None
        bizim = bool(self.surec and self.surec.poll() is None)
        return {
            "acik": acik,
            "kapi": self.kapi,
            "cdp": tarayici.cdp_adresi(self.kapi),
            "surum": (s or {}).get("Browser", ""),
            # Profil YALNIZ kabini biz actiysak bilinir. Olculdu (24.09):
            # disarida gecici profille acilmis bir kabine bagliyken durum
            # yine kullanicinin kabin profilini yaziyordu -- bilmedigimize
            # "bu" demek, yanlis gosteren gostergenin en sinsi turu.
            "profil": profil_yolu() if bizim else None,
            # Kabini PANEL mi acti yoksa disarida zaten mi vardi --
            # "kapat" dugmesinin neyi kapatacagini insan bilmeli.
            "bizim_surec": bizim,
            # Pencere acik mi -- yani kabin GERCEKTEN gomulu mu.
            # Bunu gostermemek bir kez odendi: kabin aylarca gorunur
            # bir Chrome aciyordu ve hicbir gosterge bunu soylemiyordu.
            #
            # `None` = BILMIYORUZ (kabin disarida acilmis). `bool()`e
            # cevirseydik bilmedigimize "gomulu" derdik -- gostergenin
            # en kotu hali. Disaridan acilan bir Chrome basli da
            # olabilir, bassiz da; CDP bunu bildirmiyor.
            "gorunur": self.gorunur,
        }


# ============================================================ OGE SECICI
#
# Rakipte "Element Sec -> ajana gonder" var (yayindan olculdu). Bizde
# kabin vardi ama insan "SU dugme" diyemiyordu; ekran goruntusunu
# kelimelerle tarif etmek zorundaydi ve lider "hangi dugme" diye
# tahmin ediyordu. Gormeden karar vermek tahmindir.
#
# UC KURAL:
#
# 1. **SECMEK TIKLAMAK DEGILDIR.** Secim kipinde panel tiklamayi sayfaya
#    GONDERMEZ. Yoksa "Yayinla" dugmesini secmek onu basmak olurdu --
#    riskli eylem kapisinin insan tarafindaki deligi.
# 2. **IFADE SUNUCUDA KURULUR, istemciden GELMEZ.** Istemci yalnizca iki
#    sayi gonderir; sayfada kosan JavaScript burada sabittir. Istemciden
#    ifade kabul etseydik panel, tarayiciyi surmenin ikinci bir kapisi
#    olurdu (`/ws/kabin` sozlugunun kurali).
# 3. **SECICI BILGI TASIR, SIR TASIMAZ.** Secilen ogenin bilgisi lidere
#    giden mesaja yazilir, yani DEFTERE ve bir modele gider. Bu yuzden:
#    giris kutusunun DEGERI hic okunmaz (sifre olabilir), adreslerin
#    sorgu ve parca kismi atilir (oturum anahtari tasiyabilir) ve
#    atildigi SOYLENIR.

OGE_METIN_HARF = 160
OGE_NITELIK_HARF = 160
OGE_SECICI_HARF = 300
#: Okunan nitelikler. `value` BILEREK yok.
OGE_NITELIKLER = ("type", "name", "placeholder", "aria-label", "role",
                  "href", "title", "alt")

_OGE_JS = r"""(() => {
  const X = __X__, Y = __Y__;
  let e = document.elementFromPoint(X, Y), d = 0;
  while (e && e.shadowRoot && d < 5) {
    const i = e.shadowRoot.elementFromPoint(X, Y);
    if (!i || i === e) break;
    e = i; d++;
  }
  // Bos alan (html/body) bir SECIM degildir: butun sayfanin metnini
  // tasimak hem gurultu hem gereksiz ifsa olurdu.
  if (!e || e.nodeType !== 1 || /^(HTML|BODY)$/.test(e.tagName)) return null;
  const kac = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : s;
  // TEKLIK, secicinin YASADIGI kokte olculur. Olculdu: golge DOM'daki
  // bir dugme icin "button" belge duzeyinde BASKA bir dugmeyi buluyordu
  // ve "tek" deniyordu -- lider yanlis dugmeye yonlenirdi.
  const tek = (s, k) => { try { return (k || document).querySelectorAll(s).length === 1; }
                          catch (_) { return false; } };
  const parca = (n) => {
    const t = n.tagName.toLowerCase();
    if (n.id) return "#" + kac(n.id);
    for (const a of ["data-testid", "data-test", "name", "aria-label"]) {
      const v = n.getAttribute(a);
      if (v) return t + "[" + a + "=" + JSON.stringify(v) + "]";
    }
    const p = n.parentElement;
    if (!p) return t;
    const es = Array.from(p.children).filter((c) => c.tagName === n.tagName);
    return es.length > 1 ? t + ":nth-of-type(" + (es.indexOf(n) + 1) + ")" : t;
  };
  const kur = (hedef) => {
    const kok = hedef.getRootNode();
    let s = "", n = hedef;
    for (let k = 0; n && n.nodeType === 1 && k < 6; k++) {
      const p = parca(n);
      s = s ? p + " > " + s : p;
      if (tek(s, kok)) break;
      n = n.parentElement;
    }
    return { s, kok };
  };
  const ic = kur(e);
  let sec = ic.s, essiz = tek(ic.s, ic.kok), sahip = "";
  if (ic.kok !== document) {
    // Golge DOM: once SAHIBI (belgede), sonra icindeki. Yalniz tek
    // katman guvenle ifade edilir; daha derini "tek degil" sayilir.
    const dis = kur(ic.kok.host);
    sahip = dis.s;
    essiz = essiz && d === 1 && dis.kok === document && tek(dis.s, document);
  }
  const giris = /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) || e.isContentEditable;
  const nit = {};
  for (const a of __NIT__) { const v = e.getAttribute(a); if (v) nit[a] = v; }
  const r = e.getBoundingClientRect();
  return { etiket: e.tagName.toLowerCase(), secici: sec, essiz: essiz,
           golge_sahibi: sahip,
           golge: d > 0, iframe: e.tagName === "IFRAME", giris: giris,
           metin: giris ? "" : (e.innerText || e.textContent || "").slice(0, 2000),
           nitelik: nit, url: location.href, baslik: document.title,
           kutu: { x: r.left, y: r.top, en: r.width, boy: r.height } };
})()"""


def oge_ifadesi(px, py) -> str:
    """Sayfada kosacak SALT OKUNUR ifade. Girdi yalnizca iki sayidir.

    `float()` sayi olmayan her seyi reddeder; yani istemci ifadeye kod
    sokamaz -- `"1);alert(1"` bir sayi degildir.
    """
    try:
        x, y = float(px), float(py)
    except (TypeError, ValueError):
        raise KabinHatasi(f"Oge secimi icin sayi gerekir: {px!r}, {py!r}")
    if not (math.isfinite(x) and math.isfinite(y)):
        raise KabinHatasi("Oge secimi icin sonlu sayi gerekir.")
    x, y = max(0.0, x), max(0.0, y)
    return (_OGE_JS.replace("__X__", repr(x)).replace("__Y__", repr(y))
            .replace("__NIT__", json.dumps(list(OGE_NITELIKLER))))


def _adres_temizle(url: str, taban: str = ""):
    """Sorgu ve parca atilir. Doner: (temiz, atildi_mi).

    GORELI adres `taban`a gore cozulur. Olculdu: `/urun?tok=GIZLI123`
    tam adres sanilmadigi icin temizlenmeden DOGRUDAN geciyordu --
    sizmayi onlemek icin yazilan kod, en yaygin bicimi kaciriyordu.
    """
    ham = str(url or "")
    if taban:
        try:
            ham = urljoin(taban, ham)
        except ValueError:
            pass
    try:
        p = urlparse(ham)
    except ValueError:
        return "", bool(url)
    if not p.scheme:
        # Cozulemeyen goreli adres: sorguyu ELLE kes, yine de SOYLE.
        yol = ham.split("#", 1)[0].split("?", 1)[0]
        return yol[:OGE_SECICI_HARF], (yol != ham)
    if p.scheme not in ("http", "https"):
        # about:blank, data:, chrome:// -- adres bir kaynak degildir.
        return str(url or "")[:80] if p.scheme in ("about",) else "", False
    temiz = f"{p.scheme}://{p.netloc}{p.path}"
    return temiz[:OGE_SECICI_HARF], bool(p.query or p.fragment)


def _kisa(v, n) -> str:
    return " ".join(str(v or "").split())[:n]


def oge_ozeti(ham, en: float = 0.0, boy: float = 0.0):
    """Sayfadan (ya da ISTEMCIDEN) gelen oge bilgisini SUZER.

    Iki yerden cagrilir ve ikisinde de guvenilmez girdi alir: sayfanin
    kendisi (bir site ne dondurecegini secer) ve panelin gonderdigi
    govde. Tanimadigi alani atar, uzunlugu keser, `value` gibi bir sey
    sizmaya calisirsa dusurur. Oge yoksa `None` -- bos bir oge uydurmaz.

    `en`/`boy` verilirse kutu 0..1'e normallestirilir (panel cizer).
    """
    if not isinstance(ham, dict) or not ham.get("etiket"):
        return None
    etiket = _kisa(ham.get("etiket"), 24).lower()
    if not etiket.replace("-", "").isalnum():
        return None
    url, atildi = _adres_temizle(ham.get("url"))
    nit = {}
    for a in OGE_NITELIKLER:
        v = (ham.get("nitelik") or {}).get(a) if isinstance(
            ham.get("nitelik"), dict) else None
        if not v:
            continue
        if a == "href":
            # Temizlenemeyen adres TASINMAZ -- ham haliyle gecirmek,
            # temizlemenin amacini bozardi.
            v, at2 = _adres_temizle(v, taban=str(ham.get("url") or ""))
            atildi = atildi or at2
            if not v:
                continue
        nit[a] = _kisa(v, OGE_NITELIK_HARF)
    giris = bool(ham.get("giris"))
    oge = {
        "etiket": etiket,
        "secici": _kisa(ham.get("secici"), OGE_SECICI_HARF),
        "essiz": bool(ham.get("essiz")),
        "golge": bool(ham.get("golge")),
        "golge_sahibi": _kisa(ham.get("golge_sahibi"), OGE_SECICI_HARF),
        "iframe": bool(ham.get("iframe")),
        "giris": giris,
        # Giris kutusunun metni HIC tasinmaz -- sayfa gondermis olsa bile.
        "metin": "" if giris else _kisa(ham.get("metin"), OGE_METIN_HARF),
        "nitelik": nit,
        "url": url,
        "baslik": _kisa(ham.get("baslik"), 120),
        "sorgu_atildi": atildi,
    }
    kutu = ham.get("kutu") if isinstance(ham.get("kutu"), dict) else {}
    try:
        k = [float(kutu.get(a, 0)) for a in ("x", "y", "en", "boy")]
    except (TypeError, ValueError):
        k = [0.0, 0.0, 0.0, 0.0]
    if not all(math.isfinite(v) for v in k):
        k = [0.0, 0.0, 0.0, 0.0]
    if en and boy and en > 0 and boy > 0:
        k = [k[0] / en, k[1] / boy, k[2] / en, k[3] / boy]
    oge["kutu"] = {"x": k[0], "y": k[1], "en": k[2], "boy": k[3]}
    return oge


def oge_kaynagi(oge) -> str:
    """Secilen ogenin sayfasinin ORIGIN'i; kaynak degilse bos."""
    if not oge or not oge.get("url"):
        return ""
    # YALNIZ http/https. Olculdu: `about:blank` `kaynak_normalle`de
    # "sema yok" sayilip `https://about:blank`e donuyordu -- yani bos
    # sekmede secilen oge, anlamsiz bir tarayici alani acardi.
    if urlparse(str(oge["url"])).scheme not in ("http", "https"):
        return ""
    try:
        return tarayici.kaynak_normalle(oge["url"])
    except tarayici.TarayiciHatasi:
        return ""


def oge_metni(oge, *, kabin_paylasildi: bool = False) -> str:
    """Lidere giden mesaja eklenecek blok. TEK YER: panel kendi metnini
    kurmaz, burada kurulur -- iki kopya olsaydi biri kayardi."""
    if not oge:
        return ""
    s = ["[KABINDE SECILEN OGE -- patron bu ogeyi isaret etti]"]
    if oge.get("url"):
        s.append(f"sayfa  : {oge['url']}"
                 + ("  (adresin sorgu kismi GIZLILIK icin atildi)"
                    if oge.get("sorgu_atildi") else ""))
    if oge.get("baslik"):
        s.append(f"baslik : {oge['baslik']}")
    s.append(f"oge    : <{oge['etiket']}>"
             + (f' "{oge["metin"]}"' if oge.get("metin") else ""))
    s.append(f"secici : {oge.get('secici') or '(kurulamadi)'}  "
             + ("(sayfada TEK)" if oge.get("essiz")
                else "(TEK DEGIL -- baska ogeyle karisabilir)"))
    for a, v in (oge.get("nitelik") or {}).items():
        s.append(f"  {a} = {v}")
    if oge.get("giris"):
        s.append("  (giris alani: icindeki DEGER bilerek okunmadi)")
    if oge.get("iframe"):
        s.append("  (bir iframe: icindeki oge secilemedi, cerceve secildi)")
    if oge.get("golge"):
        s.append("  (golge DOM icinde; secici SAHIBININ icinde gecerli: "
                 f"sahip = {oge.get('golge_sahibi') or '?'})")
    kay = oge_kaynagi(oge)
    if kay:
        s.append(f"Bu mesajdan acilan isler {kay} kaynagina tarayiciyla "
                 "erisebilir" + (" ve PAYLASILAN kabini kullanir (patronun "
                                 "oturumu)." if kabin_paylasildi else
                                 " (kabin kapaliydi: ayri, oturumsuz "
                                 "tarayici)."))
    return "\n".join(s)
