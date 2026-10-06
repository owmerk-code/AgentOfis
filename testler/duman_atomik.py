# -*- coding: utf-8 -*-
"""ESANLI YERINDE YAZMA (06.10.2026). Jeton yakmaz.

OLCULDU (gercek set, iki kosu paralel): `ev/beceriler/kayit.json` iki
surecten ayni anda yazilinca ikincisi `PermissionError [WinError 32]` ile
dustu -- ofiste yedi yer SABIT gecici ad (`*.json.tmp`) kullaniyordu.
Ayni yuk eski yontemle 6 surecin 5'ini dusuruyordu. Kural artik tek yerde:
`ofis.dosya.atomik_yaz`.

Sinanan: (1) 6 surec x 40 yazma ayni dosyaya -- hicbiri dusmez, son dosya
gecerli, artik gecici dosya kalmaz; (2) kaynakta sabit adli gecici dosya
kalibi GERI GELMEMIS (yeni kopya acilirsa bu sinama yakalar).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== esanli yerinde yazma ==\n")
d = Path(tempfile.mkdtemp(prefix="ofis-atomik-"))
hedef = d / "kayit.json"
kod = (f"import sys,json;sys.path.insert(0,r'{KOK}');"
       "from ofis.dosya import atomik_yaz\n"
       f"for i in range(40): atomik_yaz(r'{hedef}', json.dumps({{'s': sys.argv[1], 'i': i, 'x': 'y'*2000}}))")
ps = [subprocess.Popen([sys.executable, "-c", kod, str(n)], stderr=subprocess.PIPE, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) for n in range(6)]
hatalar = [p.communicate(timeout=120)[1] for p in ps]
sina("6 surec x 40 yazma: hicbiri dusmedi", all(p.returncode == 0 for p in ps),
     str([h.strip().splitlines()[-1] for h in hatalar if h.strip()][:2]))
try:
    gecerli = isinstance(json.loads(hedef.read_text(encoding="utf-8")), dict)
except ValueError:
    gecerli = False
sina("son dosya gecerli JSON (yarim yazilmis degil)", gecerli)
sina("artik gecici dosya kalmadi", not [x for x in d.iterdir() if x.suffix == ".tmp"])
shutil.rmtree(d, ignore_errors=True)

print("\n2. kaynakta sabit adli gecici dosya yok")
kalip = re.compile(r"with_suffix\(\s*[\"']\.(?:json\.)?tmp[\"']\s*\)")
bulunan = []
for y in (KOK / "ofis").rglob("*.py"):
    for i, satir in enumerate(y.read_text(encoding="utf-8").splitlines(), 1):
        if kalip.search(satir):
            bulunan.append(f"{y.relative_to(KOK)}:{i}")
sina("`with_suffix('.tmp')` / `.json.tmp` kalibi kaynakta yok", not bulunan, str(bulunan))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
