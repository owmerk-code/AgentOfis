# -*- coding: utf-8 -*-
"""SUREC KIMLIGI -- bir isi kosturan surec hala yasiyor mu (01.10.2026).

Neden: panel (ya da bilgisayar) is ortasinda kapanirsa defterde `calisiyor`
gorunen is kalir. Acilista "bu isi kosturan surec oldu mu" sorusuna KESIN
cevap gerekir: yasayan bir surecin (orn. ayni anda kabuktan kosan halka)
isini elinden almak Yasa 1'i deler; olmus surecin isini beklemek onu
sonsuza kadar asili birakir.

Kimlik `pid:olusma` -- yalniz pid yetmez: Windows pid'leri yeniden dagitir,
kapanan surecin numarasini baska bir surec alabilir. Olusma ani (100 ns)
ikisini ayirir.

Bagimlilik yok (psutil kurulu degil): Windows'ta ctypes, digerinde
`os.kill(pid, 0)`. Olculemeyen durumda `None` -- "bilmiyorum" ile "oldu"
ayri tutulur; cagiran bilmedigi sureci OLU SAYMAZ.
"""

from __future__ import annotations

import os
import sys

_STILL_ACTIVE = 259


def _olusma(pid: int):
    """Surecin olusma ani (Windows FILETIME, 100 ns) -- yoksa/okunamazsa None.
    Ikinci deger: surec yasiyor mu (True/False/None)."""
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return 0, True
        except ProcessLookupError:
            return None, False
        except OSError:
            return None, None
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    tut = k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    if not tut:
        hata = ctypes.get_last_error()
        # 87 = ERROR_INVALID_PARAMETER: boyle bir surec YOK. 5 (erisim yok)
        # surecin VAR oldugunu ama okunamadigini soyler -> bilinmiyor.
        return None, (False if hata == 87 else None)
    try:
        kod = wintypes.DWORD()
        if not k32.GetExitCodeProcess(tut, ctypes.byref(kod)):
            return None, None
        if kod.value != _STILL_ACTIVE:
            return None, False
        ft = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(tut, *[ctypes.byref(f) for f in ft]):
            return None, True
        return (ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime, True
    finally:
        k32.CloseHandle(tut)


def kimlik(pid: int = None) -> str:
    """`pid:olusma` -- bu surecin (ya da verilen pid'in) kimligi."""
    pid = int(pid or os.getpid())
    olusma, _ = _olusma(pid)
    return f"{pid}:{olusma or 0}"


def yasiyor(kim: str):
    """True: AYNI surec hala yasiyor. False: oldu (ya da pid baska surecte).
    None: olculemedi -- cagiran OLU SAYMAZ."""
    try:
        pid_s, olusma_s = str(kim or "").split(":", 1)
        pid, olusma = int(pid_s), int(olusma_s)
    except ValueError:
        return None
    simdiki, canli = _olusma(pid)
    if canli is False:
        return False
    if canli is None:
        return None
    if olusma and simdiki and simdiki != olusma:
        return False                    # numara baska bir surecte
    return True
