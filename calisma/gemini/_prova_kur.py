# -*- coding: utf-8 -*-
"""PROVA: kurulmaya hazir dosyalari sahte bir `ofis.motor` paketinde kosturur.

NEDEN: gercek ofis/motor/ bu oturumda yazilamiyor. Kurulum yapilamadan
donusturulmus kodun (paket ici import, patch hedefleri) dogru olup
olmadigini bilmek icin, calisma/gemini/_prova/ altinda ayni paket
duzenini kuruyoruz. Tip/kayit dosyalari calisma/cinar/referans/ icindeki
REFERANS kopyalardan aliniyor.

Bu KABUL OLCUTU DEGILDIR -- gercek ofis/motor/ ile referans kopyanin ayni
oldugu dogrulanamiyor. Yalnizca donusumun kendisini riskten arindirir.
"""

import shutil
from pathlib import Path

KOK = Path(__file__).parent
CALISMA = KOK.parent
REFERANS = CALISMA / "cinar" / "referans"
HAZIR = KOK / "kurulum_hazir"
PROVA = KOK / "_prova"

if PROVA.exists():
    shutil.rmtree(PROVA)
motor = PROVA / "ofis" / "motor"
(motor / "testler").mkdir(parents=True)

(PROVA / "ofis" / "__init__.py").write_text("", encoding="utf-8")
(motor / "testler" / "__init__.py").write_text("", encoding="utf-8")

shutil.copy(REFERANS / "tip.py", motor / "tip.py")
shutil.copy(REFERANS / "sahte.py", motor / "sahte.py")
shutil.copy(HAZIR / "gemini.py", motor / "gemini.py")
shutil.copy(HAZIR / "test_gemini.py", motor / "testler" / "test_gemini.py")

# Referans __init__.py `.claude` import ediyor ama referans klasorde dosya
# claude_ornek.py. Prova icin o satiri dusuruyoruz; DEGISTIRDIGIMIZ tek sey bu
# ve gercek pakette boyle bir duzenleme GEREKMEYECEK.
init = (REFERANS / "__init__.py").read_text(encoding="utf-8")
init = init.replace("from .claude import ClaudeMotoru\n", "")
init = init.replace("    ClaudeMotoru.ad: ClaudeMotoru,\n", "")
init = init.replace('"OLAY_TURLERI", "ClaudeMotoru", "SahteMotor",',
                    '"OLAY_TURLERI", "SahteMotor", "GeminiMotoru",')

# ---- kurulumda ofis/motor/__init__.py'ye eklenecek IKI SATIR ----
init = init.replace("from .sahte import SahteMotor",
                    "from .sahte import SahteMotor\nfrom .gemini import GeminiMotoru")
init = init.replace("    SahteMotor.ad: SahteMotor,\n",
                    "    SahteMotor.ad: SahteMotor,\n    GeminiMotoru.ad: GeminiMotoru,\n")
# -----------------------------------------------------------------

(motor / "__init__.py").write_text(init, encoding="utf-8")
print("prova paketi kuruldu:", PROVA)
