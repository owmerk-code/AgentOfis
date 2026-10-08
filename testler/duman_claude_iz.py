# -*- coding: utf-8 -*-
"""E4: gercek motor betiklerinin Claude oturum kaydi cikista silinir; baskasina dokunulmaz."""
import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

import _claude_iz as Z

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


proj = Path(tempfile.mkdtemp(prefix="ofis-claude-iz-"))
deneme = Path(tempfile.mkdtemp(prefix="ofis-deneme-9-"))
baska = Path(tempfile.mkdtemp(prefix="ofis-baska-"))
for k in (deneme, deneme / "calisma", baska):
    (proj / Z.ad(k)).mkdir(parents=True, exist_ok=True)
(proj / "c--Users-pc-Desktop-AgentOfis").mkdir()
Z.kaydet(deneme)
silinen = Z.temizle(proj)
kalan = sorted(p.name for p in proj.iterdir())
sina("kaydedilen klasorun ve alt klasorunun Claude kaydi silindi",
     not (proj / Z.ad(deneme)).exists() and not (proj / Z.ad(deneme / "calisma")).exists(), str(silinen))
sina("baska klasorun ve gercek projenin kaydina DOKUNULMADI",
     Z.ad(baska) in kalan and "c--Users-pc-Desktop-AgentOfis" in kalan, str(kalan))
sina("ad kurali: harf/rakam disi '-'", Z.ad(Path("C:/a_b.c")).endswith("a-b-c"))
Z._KOKLER.clear()
print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
