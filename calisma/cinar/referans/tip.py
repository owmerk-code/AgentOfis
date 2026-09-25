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
        """

    def etiket(self) -> str:
        """Panelde pano basligindaki motor rozeti."""
        return self.ad
