# -*- coding: utf-8 -*-
"""Yerinde dosya yazma -- TEK kural (06.10.2026).

Yerinde yazma ATOMIK olmali ('w' once dosyayi bosaltir; yari yazilmis
defter okunursa bozuk sayilir). Ofiste bunun yedi kopyasi vardi ve hepsi
SABIT bir gecici ad kullaniyordu (`kayit.json.tmp`). OLCULDU (gercek set,
iki kosu paralel): iki surec ayni anda `ev/beceriler/kayit.json` yazinca
ikincisi `PermissionError [WinError 32]` ile dustu ve is HATA verdi. Panel
ile kabuk, ya da iki ajan turu ayni anda yazdiginda gercek ofiste de olur.

Iki duzeltme: (1) her yazan kendi benzersiz gecici dosyasini acar,
(2) Windows'ta hedef bir an baska surecte acik olabilir -- `os.replace`
kisa araliklarla birkac kez denenir. Son deneme de duserse hata YUKSELIR
(yutulmaz; cagiran kendi kararini verir).
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

#: Windows'ta hedef kilitliyken yeniden deneme: toplam ~1,5 sn.
DENEME = 8
BEKLEME_SN = 0.03


def atomik_yaz(yol, metin: str, *, encoding: str = "utf-8", newline: str = None) -> None:
    """`metin`i `yol`a atomik yazar; esanli yazanlar birbirini bozmaz."""
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=str(yol.parent), prefix=yol.name + ".",
                                  suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            f.write(metin)
        for i in range(DENEME):
            try:
                os.replace(gecici, yol)
                return
            except PermissionError:
                if i == DENEME - 1:
                    raise
                time.sleep(BEKLEME_SN * (i + 1))
    finally:
        if os.path.exists(gecici):
            try:
                os.unlink(gecici)
            except OSError:
                pass
