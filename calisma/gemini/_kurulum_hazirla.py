# -*- coding: utf-8 -*-
"""Prototipi ofis/motor/ icine kurulmaya HAZIR hale getirir.

Bu betik, ofis/motor/ yazilamadigi icin (sandbox kisiti) ciktisini
calisma/gemini/kurulum_hazir/ altina birakir. Oradaki iki dosya
oldugu gibi ofis/motor/gemini.py ve ofis/motor/testler/test_gemini.py
konumlarina tasinacaktir.
"""

from pathlib import Path

KOK = Path(__file__).parent
HEDEF = KOK / "kurulum_hazir"
HEDEF.mkdir(exist_ok=True)

# --- 1) adaptor: sys.path enjeksiyonu kaldirilir, import paket ici olur ---
kaynak = (KOK / "gemini.py").read_text(encoding="utf-8")

atilacak = 'sys.path.insert(0, str(Path(__file__).parent.parent.parent))\n\n'
assert atilacak in kaynak, "sys.path satiri bulunamadi"
kaynak = kaynak.replace(atilacak, "")

eski_import = "from ofis.motor.tip import Motor, MotorOlayi, MotorHatasi"
yeni_import = "from .tip import Motor, MotorOlayi, MotorHatasi"
assert eski_import in kaynak, "tip import'u bulunamadi"
kaynak = kaynak.replace(eski_import, yeni_import)

# `sys` artik kullanilmiyor -- olu import birakilmaz.
assert "sys." not in kaynak, "sys hala kullaniliyor, import silinemez"
kaynak = kaynak.replace("import sys\n", "")

(HEDEF / "gemini.py").write_text(kaynak, encoding="utf-8")

# --- 2) testler: kurulan modulden import, patch hedefleri guncellenir ---
test = (KOK / "test_gemini.py").read_text(encoding="utf-8")

test = test.replace(
    "sys.path.insert(0, str(Path(__file__).parent.parent.parent))\n\n", ""
)
test = test.replace(
    "from ofis.motor.tip import Motor, MotorOlayi, MotorHatasi\n"
    "from gemini.gemini import GeminiMotoru",
    "from ofis.motor.tip import Motor, MotorOlayi, MotorHatasi\n"
    "from ofis.motor.gemini import GeminiMotoru",
)
# patch() hedefleri kurulan modulu gostermeli
test = test.replace('"gemini.gemini.', '"ofis.motor.gemini.')
test = test.replace("import sys\n", "")

assert "gemini.gemini" not in test, "prototip referansi kaldi"
assert "sys.path" not in test, "sys.path hilesi kaldi"

(HEDEF / "test_gemini.py").write_text(test, encoding="utf-8")

print("yazildi:", HEDEF / "gemini.py")
print("yazildi:", HEDEF / "test_gemini.py")
print("adaptorde sys.path gecen satir sayisi:",
      sum("sys.path" in s for s in kaynak.splitlines()))
print("testte sys.path gecen satir sayisi:",
      sum("sys.path" in s for s in test.splitlines()))
print("adaptor tip import satiri:",
      [s for s in kaynak.splitlines() if "from .tip" in s])
