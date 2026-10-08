# -*- coding: utf-8 -*-
"""GERCEK MOTORLA KOSAN DENEME BETIKLERI CLAUDE'DA IZ BIRAKMAZ (E4, 08.10.2026).

Claude Code her calisma klasoru icin `~/.claude/projects/<klasorun adi>`
altinda oturum kaydi tutar. Gercek motorla koşan deneme betikleri (deneme,
gercek set, matris, carpan) gecici klasorlerde calisir ve bu kayitlar
birikiyordu (olculdu: 1.365 kayit, ~220 MB; 08.10'da 4 yeni). Duman
sinamalari zaten ayri Claude evi kullanir (`_temizlik`), bu dosya YALNIZ
gercek motor betikleri icin.

Kullanim: betik gecici klasoru acinca `kaydet(klasor)`; cikista kendi
kendine temizlenir. Yalniz KAYDEDILEN klasorlerin (ve alt klasorlerinin)
kaydi silinir -- patronun ve gelistiricinin gercek oturumlarina dokunulmaz.
"""

from __future__ import annotations

import atexit
import re
import shutil
from pathlib import Path

_KOKLER: set = set()


def ad(klasor) -> str:
    """Claude Code'un klasor adlandirmasi: harf/rakam disi her sey '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(klasor).resolve()))


def kaydet(klasor) -> None:
    _KOKLER.add(str(Path(klasor).resolve()))


def temizle(projeler: Path = None) -> list:
    proj = Path(projeler) if projeler else Path.home() / ".claude" / "projects"
    if not proj.is_dir():
        return []
    silinen = []
    for k in list(_KOKLER):
        onek = ad(k).lower()
        for p in proj.iterdir():
            n = p.name.lower()
            if p.is_dir() and (n == onek or n.startswith(onek + "-")):
                shutil.rmtree(p, ignore_errors=True)
                silinen.append(p.name)
    return silinen


atexit.register(temizle)
