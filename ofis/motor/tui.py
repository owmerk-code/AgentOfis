# -*- coding: utf-8 -*-
"""GERCEK TERMINAL KIPI -- ajan, insanin kullandigi Claude/Codex terminalinde.

Kullanici (29.09.2026): *"Claude Code ve Codex'i terminalde nasil
kullaniyorsam agent sistemimizde de oyle olmali; onemli yerlerde insan
onayi istesin."*

Bu bir SARMALAYICI motordur: ic motor (claude, codex) neyi NASIL
calistiracagini bilir (`tui_plani`, `tui_cevir`); burasi hepsinde ortak
donguyu yurutur. Cekirdek hicbir seyin degistigini fark etmez -- ayni
`MotorOlayi` akisi, ayni `bitti`. Koltuk, kilit, brifing, kanit kapisi,
zincir, not ve Durdur aynen calisir.

## Nasil

1. Tur basinda ofis kapisi KENDINI SINAR (`kanca.py --oz-sinama`).
   Codex kanca dusunce komutu CALISTIRIYOR (olculdu) -- kapisi calismayan
   terminal hic acilmaz.
2. Terminal (ConPTY) acilir; guven sorusu cikarsa cevaplanir.
3. Brifing KOPYALA-YAPISTIR bicimiyle (bracketed paste) TEK mesaj gider
   (olculdu: iki motorda da cok satir tek mesaj).
4. Ajanin ne yaptigi EKRANDAN degil CLI'in oturum dosyasindan okunur --
   yapili veri, arka plan kipiyle ayni cevirici.
5. Her arac cagrisi `ofis/kanca.py`den gecer: ofisin TEK kapisi.
6. Tur bitince terminal KAPANMAZ: panel onu gosterir, insan yazabilir,
   sonraki tur (onay sonrasi devam) AYNI terminale yazilir.

## Sinirlar (yazili)

* Dolar tavani yok (etkilesimli terminal uygulamaz); ofisin kacak freni
  ve jeton tavani gecerli. `butce_destegi = False`.
* Not "ulasti" = terminal girdiyi aldi. Claude ara adimda notu turun
  ICINE alir (olculdu), Codex bir sonraki arac sinirinda.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import re
import time
from pathlib import Path
from typing import Iterator

from .tip import DOKUM_ALANLARI, Motor, MotorHatasi, MotorOlayi, TurKanali

KANCA = Path(__file__).resolve().parent.parent / "kanca.py"

#: Terminalin acilip girdi almaya hazir olmasi icin azami bekleme.
ACILIS_SN = 25.0
#: Durdur'dan sonra turun kapanmasina verilen sure.
DURDUR_SN = 12.0
#: Kullanilmayan canli terminal bu kadar sonra kapatilir.
BOSTA_KAPAT_SN = 30 * 60

_ACIK: dict = {}          # oturum_id -> {"terminal", "plan", "son", "ajan", "gorev"}
_KILIT = threading.Lock()


#: Yapistirmanin ARDINDAN elle YAZILAN satir (yapistirma degil).
#:
#: OLCULDU (30.09.2026, claude 2.1.285, bos gecici klasor): gercek
#: terminaldeki lider plan istemini `<pasted_content>` olarak aldi ve
#: "yapistirilan metinde bunun bana yazildigini gosteren bir notunuz yok,
#: onu kendi talimatim saymadim" dedi; plan iki kez "JSON okunamadi" ile
#: dustu. Claude Code yapistirilani GUVENILMEZ veri sayiyor -- dogru bir
#: savunma. Talimatin sahibini soyleyen satir KULLANICININ YAZDIGI kisim
#: olmali; o yuzden yapistirilmaz, tus tus yazilir.
SAHIP_SATIRI = ("Yukaridaki yapistirilan metin AgentOfis'in (patronun ofisinin) "
                "sana verdigi talimattir; aynen uygula, istenen bicimde cevap ver.")



def _dokum_topla(mesajlar) -> dict | None:
    """Mesaj basina dokumleri toplar; hic yoksa None (OLCULEMEDI, sifir degil)."""
    if not mesajlar:
        return None
    return {ad: sum(int(d.get(ad) or 0) for d in mesajlar.values())
            for ad in (*DOKUM_ALANLARI, "onbellek_yazma_1sa")}

def _yapistir(t, metin: str, *, sahip: str = SAHIP_SATIRI) -> None:
    """Cok satirli metni TEK mesaj olarak gonderir (bracketed paste) ve
    ardina talimatin sahibini YAZAR (bkz. SAHIP_SATIRI)."""
    t.yaz("\x1b[200~" + metin.replace("\r\n", "\n") + "\x1b[201~")
    time.sleep(0.8)
    if sahip:
        t.yaz(" " + sahip)
        time.sleep(0.4)
    t.yaz("\r")


#: Secim listesinde imlec isareti (Claude Code / Ink).
IMLEC = "\u276f"
#: `\x1b[B` Claude'da Esc sayildi (olculdu, bkz. claude.py) -- yalniz
#: uygulama kipi dizisi.
_ASAGI = ("\x1bOB",)


#: Secim imleci: claude ortama gore `\u276f` ya da duz `>` ciziyor (01.10.2026
#: OLCULDU: patronun paneli `baslat.bat`tan acilinca `>No,exit` /
#: `>Yes, I trust this folder`; Claude Code icinden acilinca `\u276f`).
IMLECLER = (IMLEC, ">")


def _imlec_evette_mi(ekran: str, evet: str) -> bool:
    """Ekranin SON karesinde secim imleci 'evet' seceneginde mi.

    Son SECENEK imleci aranir: imlec isaretinden sonra (bosluk ve `1.` gibi
    numara atlanarak) 'evet' ya da 'No' gelmeli -- ekranda baska yerde gecen
    `>` (orn. `>0q`) imlec SAYILMAZ. Bosluklar yok sayilir (ConPTY doker).
    """
    ekran = ekran or ""
    hedef = "".join(evet.split()).lower()
    for i in range(len(ekran) - 1, -1, -1):
        if ekran[i] not in IMLECLER:
            continue
        sonrasi = "".join(ekran[i + 1:i + 1 + 3 * len(evet) + 6].split())
        # SECENEK NUMARASI (01.10.2026): claude 2.1.285 `\u276f1.Yes,...` ciziyor.
        sonrasi = re.sub(r"^\d+[.)]", "", sonrasi).lower()
        if sonrasi.startswith(hedef):
            return True
        if sonrasi.startswith("no"):
            return False
    return False


def _guven_sec(t, evet: str, deneme: int = 6) -> bool:
    """Guven sorusunda 'evet'i EKRANA BAKARAK secer, sonra Enter.

    OLCULDU (30.09.2026, claude 2.1.285): sabit "asagi ok + Enter" dizisi
    yeni surumde imleci "No, exit"te birakti ve Enter Claude'u KAPATTI --
    gercek terminal kipi tamamen dustu. Otomatik guncellemenin deneme turu
    arka kipte kostugu icin bunu gormedi. Kural artik ekran: imlec evette
    degilse bir asagi, tekrar bak; evetteyse Enter. Bulamazsa Enter
    BASILMAZ (yanlis secenegi onaylamaktansa acilis zaman asimina duser).
    """
    from ..terminal import duz_metin
    for i in range(deneme):
        time.sleep(0.6)
        ekran = duz_metin(t.gecmis())
        if _imlec_evette_mi(ekran, evet):
            t.yaz("\r")
            return True
        t.yaz(_ASAGI[(i // 2) % len(_ASAGI)])
    time.sleep(0.6)
    if _imlec_evette_mi(duz_metin(t.gecmis()), evet):
        t.yaz("\r")
        return True
    return False


def _gonderildi_mi(t, dokum_bul, onceki: int, deneme: int = 4) -> bool:
    """Yapistirilan mesaj GERCEKTEN gonderildi mi -- oturum dosyasi buyudu mu.

    OLCULDU (29.09): codex uzun yapistirmayi "[Pasted Content N chars]"
    olarak giris satirinda tutuyor ve ilk Enter'i yutuyor; ikinci Enter
    gonderiyor. Ekrana degil dosyaya bakilir: dosya buyumediyse Enter
    tekrarlanir (bos Enter iki motorda da zararsiz).
    """
    # SIK YOKLAMA (01.10.2026): once her denemede SABIT 2,5 sn uyunuyordu;
    # olculdu, claude'da mesaj ~0,5 sn'de dosyaya dusuyor -- her tur ~2 sn
    # bosuna bekliyordu. Simdi 0,25 sn'de bir bakilir; 2,5 sn icinde
    # buyumezse Enter tekrarlanir (davranis ayni, yalniz bekleme kisa).
    for _ in range(deneme):
        bitis = time.monotonic() + 2.5
        while time.monotonic() < bitis:
            time.sleep(0.25)
            d = dokum_bul()
            if d is not None and d.exists() and d.stat().st_size > onceki:
                return True
        try:
            t.yaz("\r")
        except Exception:                        # noqa: BLE001
            return False
    d = dokum_bul()
    return bool(d is not None and d.exists() and d.stat().st_size > onceki)


def kanca_komutu() -> str:
    """CLI'in calistiracagi kanca komutu -- yollar tirnakli (Windows'ta
    tirnaksiz yol bosluklu klasorde bozulur; olculdu)."""
    return f'"{sys.executable}" "{KANCA}"'


def kanca_oz_sinama(ortam: dict) -> str:
    """Bos = kapi calisiyor; degilse SEBEP."""
    try:
        r = subprocess.run([sys.executable, str(KANCA), "--oz-sinama"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=ortam, timeout=60)
    except Exception as exc:                     # noqa: BLE001
        return f"kanca calistirilamadi: {exc}"
    if r.stdout.strip() != "TAMAM":
        return f"kanca riskli komutu durdurmadi: {(r.stdout + r.stderr)[-300:]}"
    return ""


def _kimlik_ortami(mcp_yapilandirma: str) -> dict:
    """Kanca kimligi ORTAMDAN okur; kimlik ofis MCP'sinin ortaminda yazili."""
    try:
        y = json.loads(mcp_yapilandirma) if mcp_yapilandirma.strip().startswith("{") \
            else json.loads(Path(mcp_yapilandirma).read_text(encoding="utf-8"))
        env = ((y.get("mcpServers") or {}).get("ofis") or {}).get("env") or {}
        return {k: str(v) for k, v in env.items() if k.startswith("OFIS_")}
    except Exception:                            # noqa: BLE001
        return {}


def acik_oturumlar() -> list:
    """Panel icin: canli ajan terminalleri."""
    with _KILIT:
        return [{"oturum_id": k, "ajan": v.get("ajan"), "gorev": v.get("gorev"),
                 "terminal": v["terminal"]}
                for k, v in _ACIK.items() if v["terminal"].canli()]


def oturum_terminali(oturum_id: str):
    with _KILIT:
        k = _ACIK.get(oturum_id)
    return k["terminal"] if k and k["terminal"].canli() else None


def kapat(oturum_id: str) -> str:
    with _KILIT:
        k = _ACIK.pop(oturum_id, None)
    return k["terminal"].kapat(duzgun=True, bekle=8) if k else "yok"


#: Ayar anahtari (koltuk da bunu okur): 'arka' | 'gercek'.
KIP_AYARI = "terminal_kipi"


#: Liderin turlari (triyaj, plan, inceleme, rapor) icin AYRI ayar:
#: 'arka' (varsayilan) | 'gercek'. OLCULDU (01.10.2026, ayni kucuk tur):
#: arka kip claude 3 sn / codex 4-6 sn, gercek terminal claude ~10 sn /
#: codex ~9 sn (hazir-isareti yamasindan SONRA bile; farkin cogu CLI'in
#: kendi acilisi). Lider bir iste 3-4 tur kosar -> is basina ~20 sn.
#: Liderin turlari kisa ve sonucu patron sohbette gorur; isci terminali
#: gorunur kalir. Isteyen lideri de gercek terminale alir (tek ayar).
LIDER_KIP_AYARI = "lider_terminal_kipi"


def kipe_gore(db, proje_id: str, motor, *, ajan_ad: str = "",
              butce_usd=None, lider: bool = False):
    """TEK KURAL, uc cagiran (isci turu, liderin planlama/triyaj/rapor
    turu, liderin incelemesi): ayar 'gercek' ve motor destekliyorsa
    gercek terminal; degilse motorun kendisi.

    TUR BASINA DOLAR TAVANI GEREKEN tur (fable hakemi, API hesabi) ARKADA
    kalir: gercek terminal tavan uygulayamaz ve tavani sessizce dusurmek
    kapi modelinin "tavan zorunlu" kuralini delerdi. Desteklemeyen motor
    da arkada kalir ve bu GORUNUR bir uyari olur.
    """
    if db.ayar_oku(proje_id, KIP_AYARI, "arka") != "gercek":
        return motor
    if lider and db.ayar_oku(proje_id, LIDER_KIP_AYARI, "arka") != "gercek":
        return motor
    if butce_usd:
        return motor
    if not getattr(motor, "tui_destegi", False):
        db.olay_yaz(proje_id, "uyari",
                    f"{getattr(motor, 'ad', '?')} gercek terminal kipini "
                    "desteklemiyor; bu tur ARKA PLANDA kosuyor.", ajan_ad=ajan_ad)
        return motor
    return TuiMotoru(motor, ajan_ad=ajan_ad)


def _bostakileri_kapat() -> None:
    simdi = time.time()
    with _KILIT:
        eski = [k for k, v in _ACIK.items()
                if not v.get("kosuyor") and simdi - v["son"] > BOSTA_KAPAT_SN]
    for k in eski:
        kapat(k)


class TuiMotoru(Motor):
    """Ic motoru gercek terminalde kosturan sarmalayici."""

    izin_kancasi = True
    tur_ici_mesaj = True
    butce_destegi = False
    araclar_kapatilabilir = False

    def __init__(self, ic: Motor, *, ajan_ad: str = "") -> None:
        if not getattr(ic, "tui_destegi", False):
            raise MotorHatasi(f"{ic.ad} gercek terminal kipini desteklemiyor.")
        self.ic = ic
        #: Panelin terminali hangi ajana baglayacagi. Isci turunda kimlik
        #: MCP ortamindan da gelir; lider turunda MCP yoktur, buradan gelir.
        self.ajan_ad = ajan_ad
        self.ad = ic.ad
        self.mcp_konusur = ic.mcp_konusur
        self.baglayici_tasir = getattr(ic, "baglayici_tasir", False)

    def musait_mi(self) -> bool:
        from ..terminal import pty_durumu
        return self.ic.musait_mi() and not pty_durumu()

    def durum_notu(self) -> str:
        from ..terminal import pty_durumu
        return pty_durumu() or self.ic.durum_notu()

    def limit_oku(self, *, ek_ortam: dict = None):
        return self.ic.limit_oku(ek_ortam=ek_ortam)

    def etiket(self) -> str:
        return f"{self.ic.etiket()} (terminal)"

    # ------------------------------------------------------------------ tur
    def tur_kos(self, metin: str, *, klasor: str, oturum_id: str = "",
                model: str = "", efor: str = "normal", yazabilir: bool = True,
                ek_klasorler: tuple = (), butce_usd: float = None,
                zaman_asimi: float = None, mcp_yapilandirma: str = "",
                izinli_araclar: tuple = (), ek_ortam: dict = None,
                izin_araci: str = "", kanal: TurKanali = None,
                araclar_kapali: bool = False) -> Iterator[MotorOlayi]:
        from ..terminal import Terminal, TerminalHatasi, duz_metin
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        if butce_usd:
            raise MotorHatasi("Gercek terminal kipi tur basina dolar tavani "
                              "uygulayamaz; ofisin kacak freni gecerli.")
        _bostakileri_kapat()
        kimlik = _kimlik_ortami(mcp_yapilandirma)
        basladi = time.monotonic()

        with _KILIT:
            kayit = _ACIK.get(oturum_id) if oturum_id else None
        if kayit and not kayit["terminal"].canli():
            with _KILIT:
                _ACIK.pop(oturum_id, None)
            kayit = None

        if kayit is None:
            import os
            sinama_ortami = dict(os.environ, **kimlik)
            neden = kanca_oz_sinama(sinama_ortami)
            if neden:
                # KAPALI KALIR: kapisi calismayan terminal acilmaz.
                yield MotorOlayi("hata", f"Ofis kapisi calismiyor, tur BASLAMADI: {neden}",
                                 {"sebep": "kapi"})
                yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "kapi",
                                               "oturum_id": oturum_id})
                return
            gecici = Path(tempfile.gettempdir()) / "agentofis-tui"
            gecici.mkdir(exist_ok=True)
            plan = self.ic.tui_plani(
                oturum_id=oturum_id, model=model, efor=efor, yazabilir=yazabilir,
                ek_klasorler=ek_klasorler, mcp_yapilandirma=mcp_yapilandirma,
                izinli_araclar=izinli_araclar, ek_ortam=ek_ortam,
                kanca_komutu=kanca_komutu(), gecici=gecici)
            ortam = dict(plan["ortam"], **kimlik)
            try:
                t = Terminal(plan["argv"], klasor=klasor, ortam=ortam,
                             kapat_girdisi=plan.get("kapat", ""), sutun=140, satir=40)
            except TerminalHatasi as exc:
                yield MotorOlayi("hata", str(exc), {"sebep": "cikis"})
                yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "cikis",
                                               "oturum_id": oturum_id})
                return
            oturum_id = plan["oturum_id"] or f"yeni-{time.time_ns()}"
            sahibi = kimlik.get("OFIS_AJAN", "") or self.ajan_ad
            # AYNI AJANIN eski (kosmayan) terminali kapanir: lider her turu
            # TEMIZ oturumla acar (Yasa 4); panoda son terminal gorunur,
            # eskiler birikmez.
            if sahibi:
                with _KILIT:
                    eski = [k for k, v in _ACIK.items()
                            if v.get("ajan") == sahibi and not v.get("kosuyor")]
                for k in eski:
                    kapat(k)
            # Motorun sistem eki bayrakla verilemiyorsa (codex) ilk mesaja.
            metin = plan.get("ilk_on_ek", "") + metin
            kayit = {"terminal": t, "plan": plan, "son": time.time(),
                     "ajan": sahibi,
                     "gorev": kimlik.get("OFIS_GOREV", ""), "ofset": 0}
            with _KILIT:
                _ACIK[oturum_id] = kayit
            yield MotorOlayi("basladi", "gercek terminal", {"oturum_id": oturum_id})
            # Acilis: guven sorusu + ekranin durulmasi.
            son_boy, durgun, bas = -1, 0.0, time.monotonic()
            while time.monotonic() - bas < ACILIS_SN and t.canli():
                ekran = duz_metin(t.gecmis())
                if plan.get("guven_isareti") and plan["guven_isareti"] in ekran.lower() \
                        and not kayit.get("guvenildi"):
                    if plan.get("guven_evet"):
                        # CEVAPLANAMAYAN GUVEN SORUSU (01.10.2026): once secilemese
                        # de "guvenildi" sayilip brifing sorunun USTUNE
                        # yapistiriliyordu; sonraki "gonderilmedi" hatasi asil
                        # sebebi sakliyordu. Iki kez daha denenir; olmazsa tur
                        # ACIK sebeple ve ekranin tamamiyla duser.
                        if not _guven_sec(t, plan["guven_evet"]):
                            kayit["guven_deneme"] = kayit.get("guven_deneme", 0) + 1
                            if kayit["guven_deneme"] < 3:
                                time.sleep(0.5)
                                continue
                            kayit["guven_cevapsiz"] = duz_metin(t.gecmis())[-1500:]
                            break
                    else:
                        for tus in plan.get("guven") or ():
                            t.yaz(tus)
                            time.sleep(0.5)
                    kayit["guvenildi"] = True
                    son_boy, durgun = -1, 0.0
                # HAZIR ISARETI (01.10.2026): CLI giris kutusunu cizdiyse
                # beklemeye gerek yok. Olculdu: onayli klasorde claude ve
                # codex ~4. sn'de hazir; "2 sn durgun + en az 4 sn" kurali
                # her tura ~2-3 sn ekliyordu. Isaret yoksa eski kural.
                hazir = plan.get("hazir_mi")
                if hazir is not None and hazir(ekran) and "trust" not in ekran[-900:].lower():
                    time.sleep(0.4)
                    break
                if len(ekran) == son_boy:
                    durgun += 0.5
                    if durgun >= 2.0 and time.monotonic() - bas > 4:
                        break
                else:
                    son_boy, durgun = len(ekran), 0.0
                time.sleep(0.5)
        t = kayit["terminal"]
        plan = kayit["plan"]
        if kayit.pop("guven_cevapsiz", None) is not None:
            ekran = duz_metin(t.gecmis())[-1500:]
            yield MotorOlayi("hata", "Klasor guven sorusu CEVAPLANAMADI (evet secenegi ekranda "
                             "bulunamadi); brifing yapistirilmadi. Ekran: " + ekran,
                             {"sebep": "guven"})
            # Kayittan ONCE silinmez: `kapat` terminali kayittan bulur.
            # (01.10.2026 olculdu: once silinince `kapat` "yok" deyip
            # hicbir seyi kapatmadi, CLI sureci arkada acik kaldi.)
            kapat(oturum_id)
            yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "guven",
                                           "oturum_id": oturum_id})
            return
        kayit["kosuyor"] = True
        if not t.canli():
            with _KILIT:
                _ACIK.pop(oturum_id, None)
            yield MotorOlayi("hata", "Terminal acilirken kapandi: "
                             + duz_metin(t.gecmis())[-400:], {"sebep": "cikis"})
            yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "cikis",
                                           "oturum_id": oturum_id})
            return

        durum = {"oturum_id": oturum_id, "metin": [], "kullanim": {}}
        # Oturum dosyasinda bu turdan ONCEKI satirlar okunmaz.
        dokum = plan["dokum"]()
        if dokum and dokum.exists():
            kayit["ofset"] = dokum.stat().st_size
        _yapistir(t, metin)
        if not _gonderildi_mi(t, plan["dokum"], kayit["ofset"]):
            # OLCULDU (30.09.2026, gercek set G01, claude): mesaj gitmedi,
            # tur yine de zaman asimina (10 dk) kadar "bitti" bekledi -- hic
            # gelmeyecek bir sonu. Gonderilemeyen tur HEMEN duser; ekranin
            # son hali sebebi gosterir (tahmin degil).
            ekran = duz_metin(t.gecmis())[-700:]
            yield MotorOlayi("hata",
                             "Brifing terminale yapistirildi ama GONDERILMEDI "
                             "(oturum dosyasi buyumedi). Ekranin sonu: " + ekran,
                             {"sebep": "gonderilemedi"})
            kapat(oturum_id)
            yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "gonderilemedi",
                                           "oturum_id": oturum_id})
            return
        kayit["son"] = time.time()

        sinir = float(zaman_asimi or 1800)
        bitti = False
        sebep = ""
        durduruldu_an = None
        son_nabiz = time.monotonic()
        artik = b""
        while True:
            simdi = time.monotonic()
            # kanal: patronun notu terminale yazilir; Durdur Esc gonderir
            if kanal is not None:
                for kimlik_, not_ in kanal.al():
                    try:
                        _yapistir(t, not_)
                        yield MotorOlayi("mesaj", not_, {"kimlik": kimlik_})
                    except TerminalHatasi:
                        pass
                if kanal.durdurulsun and durduruldu_an is None:
                    durduruldu_an = simdi
                    try:
                        t.yaz(plan.get("durdur", "\x1b"))
                    except TerminalHatasi:
                        pass
            if dokum is None or not dokum.exists():
                dokum = plan["dokum"]()
            if dokum is not None and dokum.exists():
                with open(dokum, "rb") as f:
                    f.seek(kayit["ofset"])
                    yeni = f.read()
                kayit["ofset"] += len(yeni)
                artik += yeni
                *satirlar, artik = artik.split(b"\n")
                for ham in satirlar:
                    try:
                        k = json.loads(ham.decode("utf-8", "replace"))
                    except ValueError:
                        continue
                    olaylar, son = self.ic.tui_cevir(k, durum)
                    for o in olaylar:
                        yield o
                    if son:
                        bitti = True
            if bitti:
                break
            if not t.canli():
                sebep = "cikis"
                break
            if durduruldu_an is not None and simdi - durduruldu_an > DURDUR_SN:
                sebep = "durduruldu"
                break
            if simdi - basladi > sinir:
                try:
                    t.yaz(plan.get("durdur", "\x1b"))
                except TerminalHatasi:
                    pass
                sebep = "zaman_asimi"
                break
            if simdi - son_nabiz >= 1.0:
                son_nabiz = simdi
                yield MotorOlayi("nabiz", "", {})
            time.sleep(0.3)

        kayit["kosuyor"] = False
        kayit["son"] = time.time()
        # Kimligi oturum dosyasindan ogrenen motor (codex): kayit yeni
        # kimlikle tutulur ki sonraki tur AYNI terminale yazsin.
        gercek = durum.get("oturum_id") or ""
        if gercek and gercek != oturum_id:
            with _KILIT:
                _ACIK.pop(oturum_id, None)
                _ACIK[gercek] = kayit
            oturum_id = gercek
        if durduruldu_an is not None and not sebep:
            sebep = "durduruldu"
        if sebep == "cikis":
            with _KILIT:
                _ACIK.pop(oturum_id, None)
        if sebep:
            yield MotorOlayi("hata", {"durduruldu": "Tur insanin istegiyle DURDURULDU.",
                                      "zaman_asimi": f"Tur {sinir:.0f} sn'de bitmedi.",
                                      "cikis": "Terminal kapandi."}.get(sebep, sebep)
                             + ("" if sebep == "durduruldu" else
                                " Ekranin sonu: " + " ".join(
                                    duz_metin(t.gecmis()).split())[-500:]),
                             {"sebep": sebep})
        basarili = not sebep
        yield MotorOlayi("bitti", "".join(durum["metin"]).strip() if basarili else "", {
            "basarili": basarili, "oturum_id": oturum_id,
            "model": durum.get("model") or model,
            "sure_ms": round((time.monotonic() - basladi) * 1000, 1),
            # Etkilesimli terminal dolar bildirmiyor: OLCULEMEDI (None),
            # sifir DEGIL.
            "maliyet_usd": None,
            "jeton": sum(durum.get("kullanim", {}).values()),
            # Dokumu bildiren ic motor (claude) icin; bildirmeyende None.
            "jeton_dokumu": _dokum_topla(durum.get("dokum_mesaj")),
            "arac_sayisi": durum.get("arac_sayisi", 0),
            "limit": bool(durum.get("limit")), "limit_pencere": None,
            "sebep": sebep, "kip": "terminal",
        })
