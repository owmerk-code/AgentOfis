# -*- coding: utf-8 -*-
"""Motor arayuzu: cekirdegin motora bakan tek yuzu.

Bu dosya, "dayanikli kismi cekirdege gom, curuyecek kismi fise tak"
kuralinin sinir cizgisidir. Cekirdek (tahta, kilit, kanit kapisi, brifing)
hangi motorun kostugunu BILMEZ; yalnizca su sozlesmeyi bilir:

    motor.tur_kos(metin, klasor=..., oturum_id=...) -> MotorOlayi akisi

Neden akis (generator), geri cagirma (callback) degil:

* **Nabiz cagirani kalmali.** Yazma kilidi bir KIRADIR (db.py): nabiz
  gecmezse kilit duser. Nabzi motor atarsa, motor donarken kilit de yanlis
  yere canli kalir. Akis tersini saglar -- kilidi tutan koltuk, akisi
  tuketirken kendi nabzini atar. Motor sessizken bile: bkz. `nabiz` olayi.
* **Durdurma cagiranda kalmali.** `for` dongusunden cikmak sureci
  sonlandirir (generator'un finally'si). Callback modelinde caginin
  elinde durdurma kolu yoktur.
* **Kismi cikti kaybolmaz.** Bir tur yarida patlarsa o ana kadar akan
  metin zaten tuketilmis ve olaya cevrilmistir. Istisna firlatip akisi
  koparmak, kanit olabilecek ciktiyi coper.

Neden istisna yerine son olay:

Akis HER ZAMAN `bitti` olayiyla kapanir; `bitti.ek["basarili"]` turun
sonucunu soyler. Hata da bir olaydir, akisin kopmasi degil. Boylece
koltuk, basarisiz turun ciktisini da gorev gecmisine yazabilir --
"neden basarisiz oldu" sorusunun cevabi ancak boyle durur.

Istisna yalnizca SOZLESME ihlalinde atilir: motor kurulu degil, klasor
yok, oturum kimligi bozuk. Bunlar turun sonucu degil, turun hic
baslayamamasidir.
"""

from __future__ import annotations

import os

import queue
import threading

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

#: Akista gecen olay turleri. Panel ve `olay` tablosu bu adlari kullanir;
#: yeni bir motor adaptoru kendi ozel turunu ICAT ETMEZ -- etseydi panel
#: her motoru ayri tanimak zorunda kalirdi ve motor fise takili olmazdi.
OLAY_TURLERI = (
    "basladi",     # surec ayaga kalkti
    "oturum",      # motor oturum kimligini bildirdi (kimlik burada dogar)
    "dusunce",     # dusunme akisi (varsa)
    "metin",       # ajanin urettigi metin, parca parca
    "arac",        # bir arac cagrildi (ad + kisa ozet)
    "arac_sonuc",  # aracin dondugu sonucun kisa ozeti
    "izin",        # izin istendi ya da reddedildi
    "limit",       # hesap kullanim limiti sinyali
    "nabiz",       # motor sessiz, ama hayatta -- kilidi tazelemek icin
    "hata",        # tur icinde hata
    "mesaj",       # insanin tur ici notu motora ULASTI (ek: kimlik)
    "bitti",       # akisin son olayi; her zaman gelir
)

#: Efor bizim sozlugumuzde uc kademedir (db.py). Motorlarin kendi
#: kademeleri farklidir; cevrimi adaptor yapar, cekirdek bilmez.
EFORLAR = ("dusuk", "normal", "yuksek")


@dataclass(frozen=True)
class MotorOlayi:
    """Akistan gecen tek bir olay.

    `ek` serbest bir sozluktur ama BIR kurali vardir: panelin ya da
    koltugun karar vermek icin okudugu her alan burada belgelenmis
    olmalidir. Belgesiz alan, bir sonraki adaptorde yok olur.
    """

    tur: str
    govde: str = ""
    ek: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tur not in OLAY_TURLERI:
            raise ValueError(
                f"Bilinmeyen olay turu: {self.tur!r}. "
                f"Secenekler: {', '.join(OLAY_TURLERI)}"
            )


class MotorHatasi(RuntimeError):
    """Tur baslayamadi ya da sozlesme ihlal edildi."""


class MotorYokHatasi(MotorHatasi):
    """Motorun calistirilabiliri makinede bulunamadi."""


class MotorLimitHatasi(MotorHatasi):
    """Hesap kullanim limiti. Ayri tutulur cunku CAREsi farklidir:

    hata duzeltilir, limit BEKLENIR ya da baska motora gecilir.
    """


class TurKanali:
    """Tur SURERKEN motora giden tek kanal: insanin notu ve durdurma istegi.

    Akis tek yonluydu: motor konusur, koltuk dinler. Insan bir ajana
    "dur, sunu degistir" diyemiyordu -- ancak tur bitince, bir sonraki
    brifingle. Yirmi dakikalik bir turda yirmi dakika yanlis yone gitmek
    demekti bu.

    OLCULDU (26.09.2026):
    * claude `--input-format stream-json`: tur surerken yazilan mesaj
      bir sonraki ARAC SINIRINDA ayni tura girer (sleep bittiginde, 21,8.
      sn); arac siniri yoksa ikinci bir tur acar. `--replay-user-messages`
      yankisi mesajin GERCEKTEN ulastigi ani verir.
    * codex app-server: `turn/steer` tur surerken kabul edildi (2/2).
    * ikisinde de durdurma calisiyor (claude `control_request interrupt`,
      codex `turn/interrupt`).

    Kanal is parcacigi guvenlidir: koltuk YAZAR, adaptor OKUR. Adaptor
    metni bicimlendirmez -- ne soylenecegini koltuk bilir, nasil
    iletilecegini motor. Ulasan her not bir `mesaj` olayiyla bildirilir;
    bildirilmeyen not ulasmamis sayilir ve bir sonraki turun basinda
    iletilir. Yani kanaldan alinip motora VARAMAYAN not kaybolmaz.
    """

    def __init__(self) -> None:
        self._kuyruk: "queue.Queue" = queue.Queue()
        self._dur = threading.Event()

    def gonder(self, kimlik: str, metin: str) -> None:
        self._kuyruk.put((str(kimlik), str(metin)))

    def al(self) -> list:
        """Bekleyen notlari BOSALTIR: [(kimlik, metin), ...]."""
        cikan = []
        while True:
            try:
                cikan.append(self._kuyruk.get_nowait())
            except queue.Empty:
                return cikan

    def bos_mu(self) -> bool:
        return self._kuyruk.empty()

    def durdur(self) -> None:
        self._dur.set()

    @property
    def durdurulsun(self) -> bool:
        return self._dur.is_set()


class Motor(ABC):
    """Bir motor adaptorunun uymak zorunda oldugu yuz.

    Adaptor yazarken tek soru: cekirdegin bilmesi gereken bir sey mi
    ekliyorum, yoksa bu motora ozel bir ayrinti mi? Ikincisi buradan
    disari SIZMAMALI.
    """

    #: `ajan.motor` alanindaki deger. Kayit defteri bunu anahtar yapar.
    ad: str = ""

    #: Bu motor MCP konusuyor mu. Adaptor KENDI yetenegini bildirir;
    #: cekirdek tahmin etmez. Koltuk buna gore kanit kanalini secer:
    #: MCP konusan motora arac cagrisi, konusmayana metin koprusu verilir.
    #: Ikisini ayni anda acmak, ayni is icin cift kanit demektir (olculdu).
    mcp_konusur: bool = False

    #: Bu motor TUR BASINA HARCAMA TAVANI uygulayabiliyor mu.
    #: Adaptor kendi yetenegini bildirir; cekirdek tahmin etmez.
    #: Uygulayamayan bir motora butce verilirse SESSIZCE YOK SAYILMAZ --
    #: reddedilir. Butce bir para kontroludur; kapali kalmasi gerektiginde
    #: kapali kalir ("fail closed"). Sessizce yok sayilan ayar, ayar
    #: degildir.
    butce_destegi: bool = False
    #: Bu adaptor BUTUN araclari kapatabilir mi (`--tools ""`).
    #:
    #: OLCULDU (21.09.2026): sartname kapisi `yazabilir=False` ile
    #: kosuyordu, yani KAFA_IZINLI (Read/Glob/Grep) elindeydi. Fable
    #: her turda 8-11 arac cagrisi yapip kod tabanini gezdi ve
    #: **ciktisini yazamadan tavani bitirdi**: 4 turun 3'u basarisiz,
    #: $1,94 karsiliginda sifir bulgu.
    #:
    #: Bazi isler SAF YARGIDIR: metni oku, hukum ver. Onlara arac
    #: vermek yardim degil, TUZAKTIR -- model gezer ve bitiremez.
    #: (`danisma.py` bu karari zaten vermisti: "danisilanin arac
    #: kutusu yoktur".) Kapatamayan adaptor bunu BILDIRIR; cagiran
    #: kapali kalarak vazgecer.
    araclar_kapatilabilir: bool = False

    #: Izin gerektiren her arac cagrisini, kosmadan ONCE bir MCP
    #: aracina sorabiliyor mu (`--permission-prompt-tool`).
    #:
    #: Ofisin TEK kapisi bu kancaya oturuyor: tarayici, baglayici ve
    #: kabuk cagrilari ayni olcutten geciyor. Uygulayamayan motorda
    #: koltuk bayragi HIC gecirmez ve o motora baglayici da vermez --
    #: kancasiz bir motora baglayici acmak, kapisiz bir kapi acmaktir.
    #:
    #: OLCULDU (22.09.2026, claude): kanca her cagrida calisiyor,
    #: `tool_name` ve girdinin tamamini aliyor, `deny` eylemi
    #: gerceklestirmiyor.
    izin_kancasi: bool = False

    #: claude.ai BAGLAYICILARINI (Shopify, Meta, Gmail...) tasiyabilir mi.
    #: Baglayicilar HESABIN claude.ai tarafinda yasar; yalniz claude CLI
    #: onlari yukler. Izin kancasi olmak yetmez: codex app-server kancali
    #: (26.09.2026) ama bu baglayicilari hic yuklemez. Bayrak olmasaydi
    #: koltuk codex'e 'baglayici acildi' yazardi -- yanlis gosteren gosterge,
    #: ajan araci bulamaz ve 'yok' der.
    baglayici_tasir: bool = False

    #: Tur SURERKEN not alabiliyor ve durdurulabiliyor mu (`TurKanali`).
    #: Alamayan motora koltuk kanal VERMEZ; not bir sonraki turun basinda
    #: iletilir ve panel bunu soyler ("sonraki turda iletilecek"). Kanal
    #: verilen ama tasiyamayan adaptor REDDEDER -- sessizce yok saysaydi
    #: insan notunun ulastigini sanirdi.
    tur_ici_mesaj: bool = False

    @abstractmethod
    def musait_mi(self) -> bool:
        """Motor bu makinede calistirilabilir mi.

        Panel bunu ajan ise almadan ONCE sorar: kurulu olmayan bir motora
        ajan atamak, hatayi ilk gorev dagitilana kadar gizler.
        """

    @abstractmethod
    def tur_kos(
        self,
        metin: str,
        *,
        klasor: str,
        oturum_id: str = "",
        model: str = "",
        efor: str = "normal",
        yazabilir: bool = True,
        ek_klasorler: tuple = (),
        butce_usd: float = None,
        zaman_asimi: float = None,
        mcp_yapilandirma: str = "",
        izinli_araclar: tuple = (),
        ek_ortam: dict = None,
        izin_araci: str = "",
        kanal: "TurKanali" = None,
    ) -> Iterator[MotorOlayi]:
        """Tek tur kos, olaylari akit.

        metin
            Ajana verilen sey. ILK turda tam brifing (dort katman), devam
            eden turda YALNIZCA uyanis farki olur. Bu ayrimi koltuk verir,
            motor degil: motor neyin taze neyin bayat oldugunu bilemez.
        klasor
            Ajanin calisma alani; surecin cwd'si. Her ajan kendi
            klasorunde kosar -- ortak cwd, iki ajanin birbirinin gecici
            dosyasini ezmesi demektir.
        oturum_id
            Bos ise yeni oturum acilir ve kimlik `oturum` olayiyla
            bildirilir; cagiran bunu `kadro.oturum_kaydet` ile saklar.
            Dolu ise o oturum devam ettirilir -- ajanin hafizasi budur.
        yazabilir
            `ajan.tur == 'kafa'` ise False. Kafa dosya yazamaz (kadro.py);
            bu kural burada da SUREC duzeyinde uygulanir, sadece brifingde
            rica edilmez. Ricayla duran kural, kural degildir.
        izin_araci
            Izin gerektiren her arac cagrisinin SORULACAGI MCP araci
            (orn. `mcp__ofis__izin_sor`). Ofisin tek kapisi budur:
            tarayici, baglayici ve kabuk cagrilari ayni olcutten gecer.
            Motor bunu uygulayamiyorsa `izin_kancasi = False` bildirir
            ve koltuk hic gecirmez -- sessizce yok sayilan bir ayar,
            ayar degildir.
        butce_usd
            Tur basina harcama tavani. Kacan bir ajan parayi da kacirir.
        mcp_yapilandirma
            Bu ajanin bu turda gorecegi MCP sunuculari (JSON ya da dosya
            yolu). Bos ise HICBIRI. Varsayilanin "hepsi" olmamasi bilincli
            bir karardir: baglanti basina onlarca arac tanimi gelir ve
            ajanin baglami is baslamadan dolar. Ajan isinin gerektirdigini
            alir, hesabin tamamini degil.
        izinli_araclar
            Bu gorev icin ACILAN ek izinler (adaptorun varsayilan listesine
            eklenir). Listede olmayan her sey reddedilir ve gorunur bir
            `izin` olayina donusur. Ofisin kurali: kod yazmak sormaz;
            para harcamak, yayina almak, disariya yazmak sorar.
        
        `ek_ortam`: bu turun KIMLIGI. Hesap katmani buradan gelir --
        `CODEX_HOME` baska bir codex hesabina, `ANTHROPIC_API_KEY`
        baska bir Claude hesabina isaret edebilir. Motor NASIL
        konusulacagini bilir; KIMIN adina konusulacagini hesap soyler.

        Adaptor bunu `ortam_hazirla(..., ek=ek_ortam,
        izinli=tuple(ek_ortam))` ile gecirmeli: acikca yapilandirilmis
        anahtarlar sir suzgecinden GECER, gerisi gecmez.

        `kanal`: tur SURERKEN insanin notu ve durdurma istegi
        (`TurKanali`). Motor `tur_ici_mesaj = False` ise koltuk hic
        gecirmez; gecirilirse adaptor REDDEDER. Ulasan her not icin
        `mesaj` olayi (ek: `kimlik`) yayilir; durdurulan tur `bitti` ile
        `sebep="durduruldu"` kapanir.
        """

    def etiket(self) -> str:
        """Panelde pano basligindaki motor rozeti."""
        return self.ad


#: HESABIN KULLANIM PENCERELERI -- `bitti.ek["limit_pencere"]`.
#:
#: OLCULDU (23.09.2026): saglayici bunu BILDIRIYOR ve ofis ATIYORDU.
#: claude `stream-json` her turda `rate_limit_event` yollar
#: (`unifiedWindows.five_hour/seven_day` -> `utilization`, `resetsAt`);
#: codex ayni seyi oturum kaydina yazar (`token_count.rate_limits`:
#: `primary`/`secondary` -> `used_percent`, `window_minutes`,
#: `resets_at`). Defterde gerceklerde 64 `limit` olayi vardi ve
#: hepsinde yuzde kaybolmustu; `kullanim.py` insana "OLCULEMIYOR"
#: diyordu.
#:
#: Bicim TEK YERDE tanimli ki her adaptor ayni sekli uretsin ve cekirdek
#: motoru bilmeden okuyabilsin:
#:
#:     {"kaynak": str, "hal": str, "plan": str,
#:      "pencereler": {"5s": {"kullanim": 0.71, "yenilenme": 1790129400},
#:                     "7g": {"kullanim": 0.81, "yenilenme": 1790132400}}}
#:
#: `kullanim` 0..1 kesir (HESABIN TOPLAMI -- insanin elle kullanimi da
#: dahil), `yenilenme` UNIX saniyesi. Olcemeyen motor anahtari HIC koymaz;
#: bozuk alan yazilmaz, uydurulmaz.
PENCERE_DAKIKA_ADI = {300: "5s", 10080: "7g"}


def limit_penceresi(pencereler: dict, *, kaynak: str, hal: str = "",
                    plan: str = "") -> dict | None:
    """Saglayicinin ham pencerelerini ortak bicime cevirir.

    Sayi olmayan ya da eksi olan alan ATILIR -- yarim bir olcumu tam
    gostermek, yanlis gosteren bir gostergedir. Hicbir pencere
    kalmazsa `None`: "olculemedi", "sifir" DEGIL.
    """
    temiz = {}
    for ad, p in (pencereler or {}).items():
        if not isinstance(p, dict):
            continue
        try:
            kullanim = float(p.get("kullanim"))
            yenilenme = int(p.get("yenilenme"))
        except (TypeError, ValueError):
            continue
        if kullanim < 0 or yenilenme <= 0:
            continue
        temiz[str(ad)] = {"kullanim": round(kullanim, 4), "yenilenme": yenilenme}
    if not temiz:
        return None
    return {"kaynak": kaynak, "hal": str(hal or ""), "plan": str(plan or ""),
            "pencereler": temiz}


#: Ajanin turuna GIRMEMESI gereken ortam degiskenleri (onek eslesmesi).
#:
#: OLCULDU (19.09.2026): koltuk ajan surecine `os.environ.copy()`
#: veriyordu -- yani makinedeki HER anahtar ajanin eline geciyordu. Ve
#: `ELLER_IZINLI` listesinde `Bash(echo *)` ile `Bash(cat *)` var. Yani
#: bir ajan `echo $GEMINI_API_KEY` yazip anahtari TERMINAL KANITI olarak
#: tahtaya dusurebilirdi. Kotu niyet gerekmez: "ortam degiskenlerini
#: kontrol edeyim" diye dusunen bir ajan yeter.
#:
#: Kural, MCP yalitimindaki kuralin aynisi: **ajan, isinin gerektirdigini
#: alir; hesabin tamamini degil.** Orada 131.543 jeton maliyetti, burada
#: bedeli bir sirrin kaybi -- ve sizan anahtar geri alinamaz, yalnizca
#: degistirilebilir.
#:
#: Bir MOTOR kendi anahtarina ihtiyac duyarsa onu ACIKCA gecirir
#: (`ortam_hazirla(izinli=("GEMINI_API_KEY",))`). Beyan edilmeyen sir
#: gecmez: varsayilan KAPALI, cunku unutulan bir yasak sizdirir, unutulan
#: bir izin yalnizca calismaz.
SIR_ONEKLERI = (
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI", "GOOGLE_APPLICATION",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AWS_SECRET", "AWS_SESSION",
    "AZURE_", "GH_TOKEN", "GITHUB_TOKEN", "SHOPIFY_", "META_", "FB_",
    "SLACK_", "STRIPE_", "SENDGRID_", "TWILIO_", "SUPABASE_", "N8N_",
)

#: Icinde bu gecen her degisken de sir sayilir -- ad listesi eksik kalir,
#: desen kalmaz. "Bir seyi kisitlarken kisitlamak istemedigini de
#: kisitlarsin" dersinin tersi burada gecerli: fazla kisitlamak yalnizca
#: bir ozelligi calistirmaz, eksik kisitlamak SIR SIZDIRIR.
SIR_PARCALARI = ("_API_KEY", "_SECRET", "_TOKEN", "_PASSWORD", "APIKEY",
                 "PRIVATE_KEY", "CREDENTIAL")


def ortam_hazirla(temel: dict = None, *, ek: dict = None,
                  izinli: tuple = ()) -> dict:
    """Ajan turu icin ortam kurar ve SIRLARI ayiklar.

    `izinli`: bu motorun GERCEKTEN ihtiyac duydugu degisken adlari.
    Yalnizca onlar gecer; gerisi -- adi ne olursa olsun -- dusurulur.
    """
    ortam = dict(temel if temel is not None else os.environ)
    izinli = tuple(izinli or ())
    for ad in list(ortam):
        if ad in izinli:
            continue
        buyuk = ad.upper()
        if (any(buyuk.startswith(o) for o in SIR_ONEKLERI)
                or any(p in buyuk for p in SIR_PARCALARI)):
            ortam.pop(ad, None)
    if ek:
        ortam.update(ek)
    return ortam


class SurecKafesi:
    """Bir turun sureci ve ONUN BASLATTIGI HER SEY -- tur bitince hepsi biter.

    OLCULDU (26.09.2026, deneme seti D03): ajan sayfasini denemek icin
    arkada `python -m http.server 8000` baslatti. Tur bitti, deneme seti
    bitti -- sunucu CALISMAYA DEVAM ETTI: port tutuyor, klasoru kilitliyor.
    `_surec_agacini_kes` yalniz tur zaman asimina ugrarsa kosuyordu ve o
    anda bile ebeveyni olmus bir sureci BULAMAZ (psutil `children` ebeveyn
    kimligiyle arar). Uzun kosan bir ofiste her turun biraktigi yetim
    surecler birikir; belirtisi "bilgisayar agirlasti"dan ibaret kalir.

    Windows'ta IS NESNESI (Job Object): surec baslar baslamaz kafese
    girer; baslattigi alt surecler kendiliginden ayni kafese dogar.
    `kapat()` kafesi kapatir ve icindeki HER SEY sonlanir (yetimler dahil).
    Kafes kurulamazsa is DURMAZ (eski davranis) ama `kuruldu` False kalir
    ve sebebi `hata`da durur -- sessizce kurulmus sayilmaz.

    POSIX'te bugun etkisiz (proje Windows'ta kosuyor); `kuruldu` False der.
    """

    _KILL_ON_JOB_CLOSE = 0x2000
    _EXTENDED_LIMIT = 9

    def __init__(self, surec=None) -> None:
        self._is = None
        self.kuruldu = False
        self.hata = ""
        if os.name != "nt":
            self.hata = "POSIX: is nesnesi yok"
            return
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class _Temel(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class _GS(ctypes.Structure):
                _fields_ = [(ad, ctypes.c_uint64) for ad in (
                    "ReadOperationCount", "WriteOperationCount",
                    "OtherOperationCount", "ReadTransferCount",
                    "WriteTransferCount", "OtherTransferCount")]

            class _Genis(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", _Temel),
                            ("IoInfo", _GS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]

            k32.CreateJobObjectW.restype = wintypes.HANDLE
            is_ = k32.CreateJobObjectW(None, None)
            if not is_:
                raise OSError(ctypes.get_last_error(), "CreateJobObject")
            bilgi = _Genis()
            bilgi.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(
                    wintypes.HANDLE(is_), self._EXTENDED_LIMIT,
                    ctypes.byref(bilgi), ctypes.sizeof(bilgi)):
                k32.CloseHandle(wintypes.HANDLE(is_))
                raise OSError(ctypes.get_last_error(), "SetInformationJobObject")
            self._k32, self._is = k32, is_
            if surec is not None:
                self.ekle(surec)
        except Exception as exc:          # noqa: BLE001 -- is durmasin, ama soylensin
            self.hata = f"{exc.__class__.__name__}: {exc}"

    def ekle(self, surec) -> bool:
        if not self._is:
            return False
        from ctypes import wintypes
        tutamac = getattr(surec, "_handle", None)
        if tutamac is None or not self._k32.AssignProcessToJobObject(
                wintypes.HANDLE(self._is), wintypes.HANDLE(int(tutamac))):
            self.hata = "surec kafese eklenemedi"
            return False
        self.kuruldu = True
        return True

    def kapat(self) -> None:
        """Kafesi kapatir: icindeki butun surecler sonlanir."""
        if not self._is:
            return
        from ctypes import wintypes
        try:
            self._k32.TerminateJobObject(wintypes.HANDLE(self._is), 1)
        finally:
            self._k32.CloseHandle(wintypes.HANDLE(self._is))
            self._is = None
