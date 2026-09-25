#!/usr/bin/env python3
import sys
from pathlib import Path

parent = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent))

# Oku ve yazdır
files = [
    "ofis/motor/tip.py",
    "ofis/motor/codex.py",
    "ofis/motor/claude.py",
]

for fname in files:
    fpath = parent / fname
    print(f"\n{'='*60}\n{fname}\n{'='*60}")
    print(fpath.read_text(encoding="utf-8"))
