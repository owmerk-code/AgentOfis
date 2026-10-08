# -*- coding: utf-8 -*-
"""MASAUSTU KULLANIMI -- ajanin bilgisayardaki uygulamalari fare ve
klavyeyle kullanmasi (D1, 08.10.2026).

NEDEN OFISIN KENDI ARACI: iki CLI da ajana masaustu araci VERMIYOR
(26.09 olculdu; 08.10'da codex 0.161'de yeniden olculdu: `computer_use`
bayragi acik ama ajanin 14 aracinin hicbiri masaustu degil). Arac ofisin
MCP'sinde olunca uc motorda AYNI calisir ve TEK kapidan gecer.

KURALLAR (patron, 30.09 + 41-liste #29):
* Canli masaustu onaysiz surulmez: ilk masaustu eylemi patrona SORULUR
  ("bu is boyunca" onayi o isin masaustu eylemlerini acar). Ekrana BAKMAK
  da eylemdir (patronun ekraninda ne varsa ajan gorur).
* Riskli adim (gonder, sil, ode, satin al, yayinla...) HER SEFERINDE
  sorulur: tiklanan ogenin ADI Windows'un erisilebilirlik katmanindan
  okunur (tarayici kapisinin dugme yazisini okumasinin karsiligi).
* PATRON BILGISAYARI KULLANIYORSA ajan DURUR: ofisin son eyleminden sonra
  klavye/fare hareketi olduysa eylem yapilmaz, ajana soylenir.

Bu dosya yalniz DUSUK DUZEY: ekran goruntusu, fare/klavye (SendInput),
pencereler, oge adlari (UI Automation, PowerShell uzerinden -- yeni paket
kurmadan; olculdu ~0,6 sn). Kapi kararlari `riskli.masaustu_degerlendir`
ve `mcp_sunucu`da.

KOORDINAT: ajan ekran goruntusunun PIKSELIYLE konusur (goruntu kucultulur);
cevirme `Goruntu.ekrana` ile. Goruntu alinmadan koordinatli eylem yok.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .surec import PENCERE_YOK

WINDOWS = sys.platform == "win32"

#: Modele giden goruntunun uzun kenari (piksel). Motorlar daha buyugunu
#: zaten kucultur; kucuk goruntu jeton ve sure kazandirir.
AZAMI_KENAR = 1568

#: Patron eylemi sayilmayan pay: SendInput'un kendisi de "son girdi"
#: zamanini gunceller; ofisin eyleminden sonraki bu kadar ms yok sayilir.
KENDI_PAYI_MS = 400


class MasaustuHatasi(RuntimeError):
    pass


def _gerekli():
    if not WINDOWS:
        raise MasaustuHatasi("Masaustu kullanimi yalniz Windows'ta.")


_DPI_KURULDU = False


def _dpi():
    """Fiziksel piksel: olcekli ekranda (125%/150%) koordinatlar kaymasin."""
    global _DPI_KURULDU
    if _DPI_KURULDU or not WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:                         # noqa: BLE001 -- eski Windows
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:                     # noqa: BLE001
            pass
    _DPI_KURULDU = True


def sanal_ekran() -> tuple:
    """(sol, ust, genislik, yukseklik) -- butun ekranlar birlikte."""
    _gerekli()
    _dpi()
    m = ctypes.windll.user32.GetSystemMetrics
    return m(76), m(77), m(78), m(79)


# -- ekran goruntusu --------------------------------------------------------

@dataclass
class Goruntu:
    yol: str
    genislik: int          # goruntunun pikseli
    yukseklik: int
    sol: int               # sanal ekranin sol ustu (ekran pikseli)
    ust: int
    olcek: float           # ekran pikseli / goruntu pikseli
    zaman: float

    def ekrana(self, x, y) -> tuple:
        x, y = float(x), float(y)
        if not (0 <= x <= self.genislik and 0 <= y <= self.yukseklik):
            raise MasaustuHatasi(
                f"Koordinat ({x:g},{y:g}) goruntunun disinda "
                f"({self.genislik}x{self.yukseklik}). Son ekran goruntusunun "
                "pikseliyle ver.")
        return (self.sol + int(round(x * self.olcek)),
                self.ust + int(round(y * self.olcek)))

    def goruntuye(self, ex, ey) -> tuple:
        return (int(round((ex - self.sol) / self.olcek)),
                int(round((ey - self.ust) / self.olcek)))


def goruntu_al(hedef: Path, *, kutu: tuple = None, azami: int = AZAMI_KENAR) -> Goruntu:
    """Ekranin (ya da `kutu` = ekran pikseliyle sol,ust,sag,alt) goruntusu."""
    _gerekli()
    _dpi()
    from PIL import ImageGrab
    sol, ust, gen, yuk = sanal_ekran()
    if kutu:
        resim = ImageGrab.grab(bbox=tuple(int(v) for v in kutu), all_screens=True)
        sol, ust = int(kutu[0]), int(kutu[1])
    else:
        resim = ImageGrab.grab(all_screens=True)
    olcek = max(resim.width, resim.height) / float(azami)
    if olcek > 1:
        resim = resim.resize((int(resim.width / olcek), int(resim.height / olcek)))
    else:
        olcek = 1.0
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    resim.save(hedef, "PNG", optimize=True)
    return Goruntu(str(hedef), resim.width, resim.height, sol, ust, olcek, time.time())


def base64_png(yol) -> str:
    return base64.b64encode(Path(yol).read_bytes()).decode("ascii")


# -- girdi (SendInput) ------------------------------------------------------

if WINDOWS:
    from ctypes import wintypes as W

    class _FARE(ctypes.Structure):
        _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                    ("dwFlags", W.DWORD), ("time", W.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    class _KLAVYE(ctypes.Structure):
        _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                    ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _DONANIM(ctypes.Structure):
        _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]

    class _BIRLIK(ctypes.Union):
        _fields_ = [("mi", _FARE), ("ki", _KLAVYE), ("hi", _DONANIM)]

    class _GIRDI(ctypes.Structure):
        _fields_ = [("type", W.DWORD), ("u", _BIRLIK)]

    class _SONGIRDI(ctypes.Structure):
        _fields_ = [("cbSize", W.UINT), ("dwTime", W.DWORD)]

_FARE_TUR, _KLAVYE_TUR = 0, 1
_MOVE, _ABS, _SANAL = 0x0001, 0x8000, 0x4000
_DUGMELER = {"sol": (0x0002, 0x0004), "sag": (0x0008, 0x0010), "orta": (0x0020, 0x0040)}
_TEKER = 0x0800
_K_UP, _K_UNICODE, _K_EXT = 0x0002, 0x0004, 0x0001

#: Tus adlari -> sanal tus kodu. Turkce ve Ingilizce adlar.
TUSLAR = {
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
    "space": 0x20, "bosluk": 0x20, "backspace": 0x08, "geri": 0x08,
    "delete": 0x2E, "del": 0x2E, "sil": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "yukari": 0x26, "down": 0x28, "asagi": 0x28,
    "left": 0x25, "sol": 0x25, "right": 0x27, "sag": 0x27,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
_GENIS = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27, 0x5B}

_KILIT = threading.Lock()
_SON_EYLEM_TIK = [0]          # GetTickCount, ofisin son girdisinden sonra


def _gonder(girdiler: list) -> None:
    dizi = (_GIRDI * len(girdiler))(*girdiler)
    n = ctypes.windll.user32.SendInput(len(girdiler), dizi, ctypes.sizeof(_GIRDI))
    if n != len(girdiler):
        raise MasaustuHatasi(
            "Windows girdiyi kabul etmedi (SendInput). Ekran kilitli olabilir ya da "
            "on plandaki pencere yonetici yetkisiyle calisiyor olabilir.")


def _fare(dx=0, dy=0, bayrak=0, veri=0):
    g = _GIRDI()
    g.type = _FARE_TUR
    g.u.mi = _FARE(dx, dy, veri, bayrak, 0, 0)
    return g


def _tus(vk=0, *, birak=False, unicode_kar=None):
    g = _GIRDI()
    g.type = _KLAVYE_TUR
    if unicode_kar is not None:
        g.u.ki = _KLAVYE(0, unicode_kar, _K_UNICODE | (_K_UP if birak else 0), 0, 0)
    else:
        g.u.ki = _KLAVYE(vk, 0, (_K_UP if birak else 0) | (_K_EXT if vk in _GENIS else 0), 0, 0)
    return g


def _normal(ex, ey) -> tuple:
    sol, ust, gen, yuk = sanal_ekran()
    nx = int(round((ex - sol) * 65535 / max(1, gen - 1)))
    ny = int(round((ey - ust) * 65535 / max(1, yuk - 1)))
    return nx, ny


def _isaretle():
    _SON_EYLEM_TIK[0] = ctypes.windll.kernel32.GetTickCount()


def patron_etkin_mi(pay_ms: int = KENDI_PAYI_MS) -> bool:
    """Ofisin son eyleminden SONRA klavye/fare kullanildi mi?

    Ilk eylemden once (ofis henuz hic girdi gondermediyse) bilinmez ->
    son 3 sn icinde girdi varsa evet."""
    _gerekli()
    s = _SONGIRDI()
    s.cbSize = ctypes.sizeof(_SONGIRDI)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(s)):
        return False
    simdi = ctypes.windll.kernel32.GetTickCount()
    if not _SON_EYLEM_TIK[0]:
        return (simdi - s.dwTime) & 0xFFFFFFFF < 3000
    return ((s.dwTime - _SON_EYLEM_TIK[0]) & 0xFFFFFFFF) > pay_ms \
        and ((s.dwTime - _SON_EYLEM_TIK[0]) & 0xFFFFFFFF) < 0x7FFFFFFF


def tikla(ex: int, ey: int, *, dugme: str = "sol", kez: int = 1) -> None:
    _gerekli()
    asagi, yukari = _DUGMELER.get(dugme, _DUGMELER["sol"])
    nx, ny = _normal(ex, ey)
    with _KILIT:
        _gonder([_fare(nx, ny, _MOVE | _ABS | _SANAL)])
        time.sleep(0.05)
        for i in range(max(1, min(int(kez), 3))):
            _gonder([_fare(nx, ny, asagi | _ABS | _SANAL), _fare(nx, ny, yukari | _ABS | _SANAL)])
            if i + 1 < kez:
                time.sleep(0.06)
        _isaretle()


def surukle(ex1, ey1, ex2, ey2) -> None:
    _gerekli()
    a, b = _normal(ex1, ey1), _normal(ex2, ey2)
    asagi, yukari = _DUGMELER["sol"]
    with _KILIT:
        _gonder([_fare(*a, _MOVE | _ABS | _SANAL)])
        _gonder([_fare(*a, asagi | _ABS | _SANAL)])
        for i in range(1, 11):
            x = a[0] + (b[0] - a[0]) * i // 10
            y = a[1] + (b[1] - a[1]) * i // 10
            _gonder([_fare(x, y, _MOVE | _ABS | _SANAL)])
            time.sleep(0.02)
        _gonder([_fare(*b, yukari | _ABS | _SANAL)])
        _isaretle()


def kaydir(ex: int, ey: int, adim: int) -> None:
    """adim > 0 yukari, < 0 asagi (bir adim = bir teker centigi)."""
    _gerekli()
    nx, ny = _normal(ex, ey)
    with _KILIT:
        _gonder([_fare(nx, ny, _MOVE | _ABS | _SANAL)])
        _gonder([_fare(0, 0, _TEKER, ctypes.c_uint32(int(adim) * 120).value)])
        _isaretle()


def yaz(metin: str) -> None:
    """Metni KARAKTER KARAKTER yazar (Turkce harfler dahil; klavye
    duzeninden bagimsiz). Satir sonu Enter'dir."""
    _gerekli()
    with _KILIT:
        for ch in str(metin):
            if ch == "\n":
                _gonder([_tus(0x0D), _tus(0x0D, birak=True)])
                continue
            if ch == "\r":
                continue
            kod = ord(ch)
            if kod > 0xFFFF:                  # UTF-16 vekil cifti
                kod -= 0x10000
                parca = (0xD800 + (kod >> 10), 0xDC00 + (kod & 0x3FF))
            else:
                parca = (kod,)
            for p in parca:
                _gonder([_tus(unicode_kar=p), _tus(unicode_kar=p, birak=True)])
            time.sleep(0.004)
        _isaretle()


def tus_birlesimi(birlesim: str) -> list:
    """"ctrl+shift+s" -> sanal tus kodlari (cozulemeyen ad HATA)."""
    kodlar = []
    for ad in str(birlesim or "").lower().replace(" ", "").split("+"):
        if not ad:
            continue
        if ad in TUSLAR:
            kodlar.append(TUSLAR[ad])
        elif len(ad) == 1 and ad.isalnum():
            kodlar.append(ord(ad.upper()))
        else:
            raise MasaustuHatasi(f"Tanimsiz tus: {ad!r}. Ornek: ctrl+s, alt+tab, enter, f5.")
    if not kodlar:
        raise MasaustuHatasi("Tus verilmedi.")
    return kodlar


def tus(birlesim: str) -> None:
    _gerekli()
    kodlar = tus_birlesimi(birlesim)
    with _KILIT:
        _gonder([_tus(k) for k in kodlar])
        time.sleep(0.03)
        _gonder([_tus(k, birak=True) for k in reversed(kodlar)])
        _isaretle()


# -- pencereler -------------------------------------------------------------

def pencereler(azami: int = 40) -> list:
    """Gorunur, basligi olan ust pencereler: hwnd, baslik, uygulama, kutu."""
    _gerekli()
    _dpi()
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    sonuc = []
    on = u.GetForegroundWindow()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)
    def _say(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.GetWindow(hwnd, 4):     # GW_OWNER
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        tampon = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, tampon, n + 1)
        r = W.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left < 40 or r.bottom - r.top < 30:
            return True
        pid = W.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        uyg = ""
        h = k.OpenProcess(0x1000, False, pid.value)             # QUERY_LIMITED
        if h:
            yol = ctypes.create_unicode_buffer(520)
            boy = W.DWORD(520)
            if k.QueryFullProcessImageNameW(h, 0, yol, ctypes.byref(boy)):
                uyg = Path(yol.value).name
            k.CloseHandle(h)
        sonuc.append({"hwnd": int(hwnd or 0), "baslik": tampon.value, "uygulama": uyg,
                      "kutu": [r.left, r.top, r.right, r.bottom],
                      "simge": bool(u.IsIconic(hwnd)), "onde": hwnd == on})
        return len(sonuc) < azami

    u.EnumWindows(_say, 0)
    return sonuc


def pencere_one(hwnd: int) -> bool:
    """Pencereyi one getirir (simge durumundaysa acar). Windows on plani
    yalniz son girdiyi alan surece verir; ALT basip birakmak bunu acar."""
    _gerekli()
    u = ctypes.windll.user32
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)                                       # SW_RESTORE
    with _KILIT:
        _gonder([_tus(0x12), _tus(0x12, birak=True)])
        _isaretle()
    u.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    return u.GetForegroundWindow() == hwnd


def pencere_bul(ad: str) -> dict | None:
    """Baslikta ya da uygulama adinda gecen ILK pencere (buyuk/kucuk harf yok)."""
    ad = str(ad or "").strip().lower()
    if not ad:
        return None
    for p in pencereler(80):
        if ad in p["baslik"].lower() or ad in p["uygulama"].lower():
            return p
    return None


def on_pencere() -> dict | None:
    for p in pencereler(80):
        if p["onde"]:
            return p
    return None


# -- ogeler (UI Automation, PowerShell) ---------------------------------------

_UIA_BAS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
function Oge($e) {
  if ($null -eq $e) { return $null }
  $c = $e.Current
  $r = $c.BoundingRectangle
  $k = $null
  if (-not $r.IsEmpty) { $k = @([int]$r.Left, [int]$r.Top, [int]$r.Right, [int]$r.Bottom) }
  return [ordered]@{ ad = [string]$c.Name; tur = ($c.ControlType.ProgrammaticName -replace 'ControlType\.', '');
                     kimlik = [string]$c.AutomationId; etkin = [bool]$c.IsEnabled; kutu = $k;
                     yardim = [string]$c.HelpText; sifre = [bool]$c.IsPassword }
}
"""


def _ps(govde: str, sure: float = 20.0):
    """PowerShell betigini kosar, JSON cevabi doner (hata -> None)."""
    betik = _UIA_BAS + govde
    kod = base64.b64encode(betik.encode("utf-16-le")).decode("ascii")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", kod],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=sure, creationflags=PENCERE_YOK, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    cikti = (p.stdout or "").strip()
    if not cikti:
        return None
    try:
        return json.loads(cikti.splitlines()[-1])
    except ValueError:
        return None


def oge_noktada(ex: int, ey: int) -> dict | None:
    """Ekran noktasindaki oge (ad, tur, kutu) + ait oldugu pencerenin adi."""
    _gerekli()
    return _ps(f"""
$e = $A::FromPoint((New-Object System.Windows.Point({int(ex)}, {int(ey)})))
$o = Oge $e
$w = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$p = $e; $kok = $null
while ($p -ne $null) {{ $u = $w.GetParent($p); if ($u -eq $null -or $u -eq $A::RootElement) {{ $kok = $p; break }}; $p = $u }}
if ($kok -ne $null) {{ $o['pencere'] = [string]$kok.Current.Name }}
$o | ConvertTo-Json -Compress -Depth 4
""")


def odak_ogesi() -> dict | None:
    _gerekli()
    return _ps("""
$e = $A::FocusedElement
$o = Oge $e
$o | ConvertTo-Json -Compress -Depth 4
""")


def ogeler(hwnd: int, azami: int = 150) -> list:
    """Pencerenin ADI OLAN, ekranda gorunen ogeleri (dugme, alan, menu...)."""
    _gerekli()
    sonuc = _ps(f"""
$k = $A::FromHandle([IntPtr]{int(hwnd)})
$s = New-Object System.Windows.Automation.PropertyCondition($A::IsOffscreenProperty, $false)
$hep = $k.FindAll([System.Windows.Automation.TreeScope]::Descendants, $s)
$l = New-Object System.Collections.ArrayList
foreach ($e in $hep) {{
  if ($l.Count -ge {int(azami)}) {{ break }}
  try {{ $o = Oge $e }} catch {{ continue }}
  if ($o.kutu -eq $null) {{ continue }}
  if ([string]::IsNullOrWhiteSpace($o.ad) -and $o.tur -notin @('Edit','Document','ComboBox')) {{ continue }}
  [void]$l.Add($o)
}}
ConvertTo-Json -InputObject @($l) -Compress -Depth 4
""", sure=30.0)
    return sonuc if isinstance(sonuc, list) else []


# -- tek surucu (kira kilidi) ---------------------------------------------------

#: Masaustu TEK: iki ajan ayni anda fareyi surerse birbirinin tiklamasini
#: bozar (Yasa 1: yazma tek iplikli). Kira her eylemde yenilenir; sahibi
#: susarsa KIRA_SN sonra duser (cokmus ajan masaustunu kilitli birakmasin).
KIRA_SN = 300


def _kilit_yolu() -> Path:
    from .yollar import ofis_evi
    return Path(ofis_evi()) / "masaustu_kilit.json"


_KIRA_KILIDI = threading.Lock()


def kira_al(sahip: str, *, simdi: float = None) -> str | None:
    """Kirayi alir ya da yeniler. Doner: None = sende; metin = su an suren."""
    simdi = time.time() if simdi is None else simdi
    yol = _kilit_yolu()
    with _KIRA_KILIDI:
        try:
            k = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            k = {}
        if k.get("sahip") and k.get("sahip") != sahip and simdi - float(k.get("zaman") or 0) < KIRA_SN:
            return str(k["sahip"])
        from .dosya import atomik_yaz
        yol.parent.mkdir(parents=True, exist_ok=True)
        atomik_yaz(yol, json.dumps({"sahip": sahip, "zaman": simdi}))
        return None


def kira_birak(sahip: str) -> None:
    yol = _kilit_yolu()
    with _KIRA_KILIDI:
        try:
            k = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if k.get("sahip") == sahip:
            try:
                yol.unlink()
            except OSError:
                pass


# -- uygulama acma ------------------------------------------------------------

def uygulama_ac(komut: str, argumanlar: list = None) -> int:
    """Uygulamayi baslatir (yol ya da PATH'teki ad: notepad, calc, excel...).
    Doner: surec kimligi."""
    _gerekli()
    komut = str(komut or "").strip()
    if not komut:
        raise MasaustuHatasi("Acilacak uygulama verilmedi.")
    try:
        p = subprocess.Popen([komut, *[str(a) for a in (argumanlar or [])]],
                             creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        return p.pid
    except OSError:
        pass
    # Kayitli uygulama adi (ornek "excel", "winword"): kabugun "baslat"i.
    os.startfile(komut)                                             # noqa: S606
    return 0
