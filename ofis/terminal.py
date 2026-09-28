"""TERMINAL -- panelin icinde GERCEK bir terminal (Windows ConPTY).

"Devral" icin var (PLAN E18, `ofis/devral.py`): insan bir ajanin isini
alir ve ajanin KENDI oturumunu gercek bir terminalde surdurur.

Neden sahte bir "komut kutusu" degil: ajanlarin CLI'lari (claude, codex)
TUI'dir -- imlec, renk, secim listeleri. Onlari ancak gercek bir terminal
dogru calistirir. OLCULDU (26.09 A7 + 28.09): `pywinpty` (ConPTY) ile
PowerShell, `claude --resume` ve `codex resume` acildi, yazildi, boyut
degisti, kapandi; artik surec kalmadi.

Kurallar:

* **Okuma AYRI IPLIKTE.** `PtyProcess.read` veri yokken ENGELLER --
  olculdu: ilk olcum betigi sonsuza kadar bekledi.
* **Kapanis DUZGUN once.** Motorun kendi kapanis girdisi (`/exit`,
  `/quit`) yazilir, surec kendiliginden biterse iyi; bitmezse zorla.
  Zorla oldurmek, CLI'in diske yazmadigi seyi kaybettirebilir.
* **Kafes.** Terminalin baslattigi her sey `SurecKafesi`ne girer; terminal
  kapaninca yetimler dahil hepsi biter (26.09'da ajanin biraktigi
  `http.server` ders oldu).
* **Tampon sinirli** (`AZAMI_TAMPON`): uzun bir oturum bellegi sisirmesin;
  panel yeniden baglaninca son kisim gosterilir.

Bu modul KARAR VERMEZ -- kimin, hangi isi, ne zaman devralacagi
`devral.py`nin isidir. Burasi yalnizca terminal.
"""

from __future__ import annotations

import re
import threading
import time

#: Bellekte tutulan ekran gecmisi (ham, renk kodlariyla). Yeniden
#: baglanan panel bunu alir.
AZAMI_TAMPON = 512 * 1024

#: Duzgun kapanisa ne kadar sans verilir.
KAPANIS_BEKLEME_SN = 15.0

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")


class TerminalHatasi(RuntimeError):
    pass


def pty_durumu() -> str:
    """Bos dize = gercek terminal acilabilir; degilse SEBEP (uydurmaz)."""
    try:
        import winpty  # noqa: F401
    except ImportError:
        return ("gercek terminal icin `pywinpty` paketi kurulu degil "
                "(kur: python -m pip install pywinpty; baslat.bat kendisi kurar)")
    return ""


def duz_metin(ham: str) -> str:
    """Renk/imlec kodlarini atar -- DEFTERE yazilacak dokum icin."""
    return _ANSI.sub("", ham or "").replace("\r", "")


class Terminal:
    """Tek bir gercek terminal oturumu."""

    def __init__(self, argv: list, *, klasor: str, ortam: dict = None,
                 kapat_girdisi: str = "", sutun: int = 120, satir: int = 32):
        durum = pty_durumu()
        if durum:
            raise TerminalHatasi(durum)
        from winpty import PtyProcess
        from .motor.tip import SurecKafesi
        try:
            self._p = PtyProcess.spawn(list(argv), cwd=klasor or None, env=ortam,
                                       dimensions=(int(satir), int(sutun)))
        except Exception as exc:          # noqa: BLE001 -- sebep soylenir
            raise TerminalHatasi(f"terminal acilamadi: {exc}") from exc
        self.argv = list(argv)
        self.kapat_girdisi = kapat_girdisi or ""
        self.acildi = time.time()
        self._tampon: list = []
        self._boy = 0
        self._kilit = threading.Lock()
        self._dinleyiciler: list = []
        self._bitti = threading.Event()
        self.kafes = SurecKafesi()
        self.kafes.ekle_pid(self._p.pid)
        threading.Thread(target=self._oku, daemon=True,
                         name="terminal-oku").start()

    # -- akis -------------------------------------------------------------
    def _oku(self) -> None:
        while True:
            try:
                veri = self._p.read(4096)
            except Exception:              # noqa: BLE001 -- EOF: surec bitti
                break
            if not veri:
                if not self._p.isalive():
                    break
                time.sleep(0.02)
                continue
            with self._kilit:
                self._tampon.append(veri)
                self._boy += len(veri)
                while self._boy > AZAMI_TAMPON and len(self._tampon) > 1:
                    self._boy -= len(self._tampon.pop(0))
                dinleyiciler = list(self._dinleyiciler)
            for d in dinleyiciler:
                try:
                    d(veri)
                except Exception:          # noqa: BLE001 -- bir dinleyici digerini durdurmasin
                    pass
        self._bitti.set()
        for d in list(self._dinleyiciler):
            try:
                d(None)                    # None = terminal kapandi
            except Exception:              # noqa: BLE001
                pass

    def dinle(self, geri_cagri) -> str:
        """Yeni veriyi `geri_cagri(str)` ile bildirir; o ana kadarki
        gecmisi DONDURUR (yeniden baglanan ekran bos acilmasin)."""
        with self._kilit:
            self._dinleyiciler.append(geri_cagri)
            return "".join(self._tampon)

    def birak(self, geri_cagri) -> None:
        with self._kilit:
            if geri_cagri in self._dinleyiciler:
                self._dinleyiciler.remove(geri_cagri)

    def gecmis(self) -> str:
        with self._kilit:
            return "".join(self._tampon)

    def dokum(self, azami: int = 6000) -> str:
        """Ekranin DUZ METIN son kismi -- deftere yazilacak olan."""
        return duz_metin(self.gecmis())[-azami:]

    # -- girdi ------------------------------------------------------------
    def yaz(self, veri: str) -> None:
        if not self.canli():
            raise TerminalHatasi("terminal kapali")
        self._p.write(veri)

    def boyutla(self, sutun: int, satir: int) -> None:
        sutun, satir = max(20, min(int(sutun), 500)), max(5, min(int(satir), 200))
        try:
            self._p.setwinsize(satir, sutun)
        except Exception:                  # noqa: BLE001 -- boyut bir kolaylik
            pass

    # -- yasam ------------------------------------------------------------
    def canli(self) -> bool:
        try:
            return bool(self._p.isalive()) and not self._bitti.is_set()
        except Exception:                  # noqa: BLE001
            return False

    def kapat(self, *, duzgun: bool = True,
              bekle: float = KAPANIS_BEKLEME_SN) -> str:
        """Kapatir; NASIL kapandigini soyler: 'duzgun' | 'zorla' | 'zaten'."""
        nasil = "zaten"
        if self.canli():
            nasil = "zorla"
            if duzgun and self.kapat_girdisi:
                try:
                    # Satirda yarim kalmis bir girdi varsa once temizlenir
                    # (Ctrl+U); sonra kapanis komutu.
                    self._p.write("\x15")
                    for ch in self.kapat_girdisi:
                        self._p.write(ch)
                    time.sleep(0.5)
                    self._p.write("\r")
                    son = time.time() + bekle
                    while time.time() < son and self.canli():
                        time.sleep(0.2)
                    if not self.canli():
                        nasil = "duzgun"
                except Exception:          # noqa: BLE001 -- zorla kapatmaya dus
                    pass
            if self.canli():
                try:
                    self._p.terminate(force=True)
                except Exception:          # noqa: BLE001
                    pass
        self.kafes.kapat()
        return nasil


# ---------------------------------------------------------------- kayit
# Acik terminaller BELLEKTE yasar (panel sureci). Anahtar gorev kimligi:
# ayni is icin ikinci terminal acilmaz. Panel yeniden baslarsa terminal
# gider -- devral kaydi defterde kalir ve "geri ver" yine calisir
# (terminalsiz; olcum yapilamadigi SOYLENIR).
_ACIK: dict = {}
_ACIK_KILIT = threading.Lock()


def kaydet(anahtar: str, terminal: Terminal, **ek) -> None:
    with _ACIK_KILIT:
        if anahtar in _ACIK and _ACIK[anahtar]["terminal"].canli():
            raise TerminalHatasi("bu is icin zaten acik bir terminal var")
        _ACIK[anahtar] = {"terminal": terminal, **ek}


def al(anahtar: str) -> dict | None:
    with _ACIK_KILIT:
        return _ACIK.get(anahtar)


def cikar(anahtar: str) -> dict | None:
    with _ACIK_KILIT:
        return _ACIK.pop(anahtar, None)
