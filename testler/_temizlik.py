# -*- coding: utf-8 -*-
"""Sinamalarin gecici klasorlerini sinama bitince SILER -- ve olcer.

PLAN F1, E05. Olculdu (26.09.2026): tam takim bir kez kosunca
`%TEMP%`'te ~45 `ofis-*` klasoru kaliyordu; birikmis 302 klasor
(~60 MB) bulundu. Diski bir kez dolduran da buydu.

Her dosyada ayri ayri `finally: rmtree` yazmak, 22 dosyadan birinde
unutulmanin garantisiydi (bu projede iki kopyadan biri alti kez
unutuldu). Bunun yerine: sinamanin EN BASINDA ice aktarilir,
`tempfile.mkdtemp` sarmalanir, acilan her klasor kaydedilir ve surec
biterken silinir.

* Git nesneleri Windows'ta SALT OKUNUR: silmeden once yazilabilir yapilir.
* Alt surec (MCP sunucusu, tarayici) dosyayi kisa sure tutabilir:
  birkac kez denenir.
* Silinemeyen kalirsa SESSIZ kalinmaz: stderr'e yazilir ve cikis kodu
  basarisiza cevrilir -- artik birakan sinama gecmis sayilmaz.
* Golge depolar (`geri_al.py`) de bu surecin gecici klasorune yonlenir;
  yoksa her sinama gecici klasorde bir golge depo birakirdi.
"""

from __future__ import annotations

import atexit
import gc
import os
import shutil
import sys
import tempfile
import time

_ACILAN: list = []
_ASIL_MKDTEMP = tempfile.mkdtemp


def _kaydeden_mkdtemp(*a, **kw):
    yol = _ASIL_MKDTEMP(*a, **kw)
    _ACILAN.append(yol)
    return yol


tempfile.mkdtemp = _kaydeden_mkdtemp

if not os.environ.get("OFIS_GOLGE_KOK"):
    os.environ["OFIS_GOLGE_KOK"] = tempfile.mkdtemp(prefix="ofis-golge-sinama-")


def _yazilabilir_yap(islev, yol, _hata):
    try:
        os.chmod(yol, 0o700)
        islev(yol)
    except FileNotFoundError:
        pass


def temizle() -> list:
    gc.collect()
    kalan = []
    for yol in reversed(_ACILAN):
        for _ in range(5):
            if not os.path.exists(yol):
                break
            try:
                shutil.rmtree(yol, onexc=_yazilabilir_yap)
            except OSError:
                time.sleep(0.4)
        if os.path.exists(yol):
            kalan.append(yol)
    _ACILAN.clear()
    return kalan


def _cikista():
    kalan = temizle()
    if kalan:
        print(f"\n[ARTIK] {len(kalan)} gecici klasor SILINEMEDI:", file=sys.stderr)
        for y in kalan:
            print(f"  {y}", file=sys.stderr)
        # Artik birakan sinama gecmis sayilmaz (sys.exit(0) cagrilmis olsa bile).
        os._exit(3)


atexit.register(_cikista)
