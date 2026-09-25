# -*- coding: utf-8 -*-
"""Adaptorun kullandigi HER bayragi ham `gemini --help` metnine karsi dogrular.

Yorum yapmaz: bayrak ham metinde gecmiyorsa YOK der.
"""

import re
from pathlib import Path

CALISMA = Path(__file__).parent.parent
ham = (CALISMA / "gemini_help_raw.txt").read_text(encoding="utf-8", errors="replace")

kod = (Path(__file__).parent / "kurulum_hazir" / "gemini.py").read_text(encoding="utf-8")

# Koddaki string literal olarak gecen tum bayraklar
kullanilan = sorted(set(re.findall(r'"(-{1,2}[a-z][a-z-]*)"', kod)))

print("=== Adaptorun KULLANDIGI bayraklar, ham --help metnine karsi ===")
for b in kullanilan:
    var = re.search(r'(?<![\w-])' + re.escape(b) + r'(?![\w-])', ham) is not None
    print(f"  {'VAR ' if var else 'YOK '} {b}")

print()
print("=== --approval-mode secenekleri (ham metinden) ===")
for satir in ham.splitlines():
    if "approval-mode" in satir:
        print("  " + satir.strip())

print()
print("=== REDDEDILEN parametreler icin ham metinde karsilik araniyor ===")
for etiket, desenler in {
    "butce_usd": ["budget", "cost-limit", "max-cost", "spend"],
    "efor": ["reasoning", "effort", "thinking-budget"],
    "zaman_asimi": ["timeout", "--time"],
    "mcp_yapilandirma": ["mcp-config", "mcp-server-config", "mcpServers"],
}.items():
    bulunan = [d for d in desenler if d in ham]
    print(f"  {etiket}: {'BULUNDU -> ' + str(bulunan) if bulunan else 'ham metinde karsilik YOK -> reddetmek dogru'}")

print()
print("=== mcp ile ilgili ham metindeki TUM satirlar ===")
for satir in ham.splitlines():
    if "mcp" in satir.lower():
        print("  " + satir.strip())
