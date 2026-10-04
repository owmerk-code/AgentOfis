# -*- coding: utf-8 -*-
"""Pencere duman testi -- alt surec konsol penceresi ACMAZ.

Neden: agent sistemi konsolsuz kosarsa (gizli acilis, konsolsuz motor) her
`git`/`npm` cagrisi ekrana bos bir pencere acar; patron oyun oynarken
`git.exe` penceresi one geldi (04.10). Kural `ofis.surec.PENCERE_YOK`'ta;
bu sinama `ofis/` altindaki HER `subprocess` cagrisini kaynaktan tarar.

Sinanan: tarayici ayarsiz cagriyi yakalar (mutasyon) · `ofis/`te ayarsiz
cagri yok · `os.system`/`os.popen` yok · git cagrisi pencere acmaz, girdi
beklemez (sifre sorusu kapali).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import ast
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import depo
from ofis.surec import PENCERE_YOK

GECEN = 0
KALAN = 0

SUREC_ISLEVLERI = ("run", "Popen", "check_output", "call", "check_call")


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def ayarsizlar(kaynak: str) -> list:
    """`subprocess.X(...)` cagrisinda `creationflags` yoksa satir no."""
    bulunan = []
    for n in ast.walk(ast.parse(kaynak)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in SUREC_ISLEVLERI
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"
                and not any(k.arg in ("creationflags", None) for k in n.keywords)):
            bulunan.append(n.lineno)
    return bulunan


def os_kabugu(kaynak: str) -> list:
    return [n.lineno for n in ast.walk(ast.parse(kaynak))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("system", "popen")
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"]


print("1) tarayicinin kendisi")
sina("ayarsiz cagriyi yakalar",
     ayarsizlar("import subprocess\nsubprocess.run(['git', 'status'])\n") == [2])
sina("ayarli cagriyi gecirir",
     ayarsizlar("import subprocess\nsubprocess.run(['git'], creationflags=1)\n") == [])
sina("os.system'i yakalar", os_kabugu("import os\nos.system('git status')\n") == [2])

print("2) ofis/ altindaki butun cagrilar")
eksik, kabuk = [], []
for f in sorted((KOK / "ofis").rglob("*.py")):
    s = f.read_text(encoding="utf-8")
    eksik += [f"{f.relative_to(KOK)}:{n}" for n in ayarsizlar(s)]
    kabuk += [f"{f.relative_to(KOK)}:{n}" for n in os_kabugu(s)]
sina("her subprocess cagrisi creationflags tasir", not eksik, str(eksik))
sina("os.system / os.popen yok", not kabuk, str(kabuk))
if sys.platform == "win32":
    sina("PENCERE_YOK = CREATE_NO_WINDOW", PENCERE_YOK == subprocess.CREATE_NO_WINDOW)

print("3) git cagrisi (depo) pencere acmaz, girdi beklemez")
_gercek = subprocess.run
yakalanan = {}


def _kaydet(argv, **kw):
    yakalanan.update(kw, argv=argv)
    return subprocess.CompletedProcess(argv, 0, "", "")


subprocess.run = _kaydet
try:
    depo._git(KOK, "status")
finally:
    subprocess.run = _gercek
sina("git: creationflags = PENCERE_YOK", yakalanan.get("creationflags") == PENCERE_YOK)
sina("git: stdin kapali", yakalanan.get("stdin") == subprocess.DEVNULL)
sina("git: sifre sorusu kapali",
     (yakalanan.get("env") or {}).get("GIT_TERMINAL_PROMPT") == "0")

print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
