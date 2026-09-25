# -*- coding: utf-8 -*-
"""Motor kayit defteri: `ajan.motor` alanindaki addan bir adaptor uretir.

Neden kayit defteri, dogrudan `import` degil:

Cekirdek (koltuk, lider, panel) hicbir motor modulunu import ETMEZ.
Yalnizca `motor_ac(ajan["motor"])` cagirir. Bunun bedeli bir sozluk,
karsiligi sudur: yeni bir motor eklemek TEK dosya yazip TEK satir
kaydetmektir; cekirdekte hicbir yer degismez. Rakipte 11 motor var ve
biz onlari taklit edecegiz -- taklit ucuz olsun diye kapi burada dar
tutuluyor.

Ikinci sebep: **kurulu olmayan motor, ajan ise alinirken yakalanmali.**
`musait_motorlar()` paneli besler; kurulu olmayan bir motora ajan
atamak, hatayi ilk gorev dagitilana kadar gizler -- ve o an ajan zaten
bir gorev sahiplenmis, kilidi almis olur.
"""

from __future__ import annotations

from .tip import (
    Motor, MotorOlayi, MotorHatasi, MotorYokHatasi, MotorLimitHatasi,
    OLAY_TURLERI,
)
from .claude import ClaudeMotoru
from .codex import CodexMotoru
from .sahte import SahteMotor

__all__ = [
    "Motor", "MotorOlayi", "MotorHatasi", "MotorYokHatasi", "MotorLimitHatasi",
    "OLAY_TURLERI", "ClaudeMotoru", "CodexMotoru", "SahteMotor",
    "motor_ac", "motor_kaydet", "musait_motorlar", "kayitli_motorlar",
]

#: ad -> adaptor sinifi. `kadro.MOTORLAR` ile ayni sozlugu konusur.
_DEFTER = {
    ClaudeMotoru.ad: ClaudeMotoru,
    # Bu adaptoru OFIS KENDI YAZDI (18.09.2026): hedef verildi, lider
    # dagitti, isci `codex --help` kosturup gercek bayraklari ogrendi,
    # 13 sozlesme testiyle kanitladi. Buraya tek satirla takildi --
    # cekirdekte hicbir yer degismedi. "Fise takilir" tam bu demekti.
    CodexMotoru.ad: CodexMotoru,
    # GEMINI DEFTERDEN CIKARILDI (24.09.2026, kullanici karari): "free
    # hesapla bu is olmayacak, claude + codex yeterli." Olculmustu:
    # ucretsiz kota (`limit: 20`) iki gercek turu oldurdu, tarayici ve
    # izin kancasi yok, ek izinli dokuz rolde tur hic baslamiyor.
    #
    # Dosya (`motor/gemini.py`) SILINMEDI: hesap degisirse geri takmak
    # tek satirdir. Ama defterde durdugu surece `musait_motorlar()` onu
    # "hazir" gosteriyor, ekip onerisi ve lider zinciri onu seciyordu --
    # kullanilmayacak bir motoru "hazir" gostermek yanlis gosteren
    # gostergedir.
    SahteMotor.ad: SahteMotor,
}


def motor_kaydet(sinif) -> None:
    """Yeni bir adaptoru deftere yazar (codex, opencode, api...)."""
    ad = getattr(sinif, "ad", "")
    if not ad:
        raise MotorHatasi("Motor sinifinin 'ad' alani bos olamaz.")
    _DEFTER[ad] = sinif


def kayitli_motorlar() -> tuple:
    return tuple(sorted(_DEFTER))


def motor_ac(ad: str, **ayar) -> Motor:
    """Ad'dan adaptor uretir. Bilinmeyen ad SESSIZ GECILMEZ.

    Yanlis yazilmis bir motor adi varsayilana dusurulseydi, ajan farkli
    bir motorla kosar ve kimse fark etmezdi -- fatura ve davranis
    beklenenden baska olurdu.
    """
    ad = str(ad or "").strip().lower()
    sinif = _DEFTER.get(ad)
    if sinif is None:
        raise MotorHatasi(
            f"Bilinmeyen motor: {ad!r}. Kayitli olanlar: {', '.join(kayitli_motorlar())}"
        )
    return sinif(**ayar)


def musait_motorlar() -> dict:
    """ad -> bu makinede kosturulabilir mi.

    Panel 'ekip onizlemesi' ekraninda bunu gosterir: kurulu olmayan motor
    secilemesin. Rakibin uc durumlu entegrasyon rozeti mantigi -- ASLA
    UYDURMAZ, baglantiyi olcer.
    """
    sonuc = {}
    for ad, sinif in _DEFTER.items():
        try:
            sonuc[ad] = bool(sinif().musait_mi())
        except Exception:
            sonuc[ad] = False
    return sonuc
