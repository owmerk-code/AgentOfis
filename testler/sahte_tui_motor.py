# -*- coding: utf-8 -*-
"""Gercek terminal kipinin sinamasi icin sahte motor: `sahte_tui.py`yi
gercek ConPTY terminalinde kosturur (duman_tui ve gorsel kontrol ortak)."""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis.motor.tip import Motor, MotorOlayi  # noqa: E402

SAHTE_CLI = str(Path(__file__).resolve().parent / "sahte_tui.py")


class SahteTui(Motor):
    ad = "sahte-tui"
    mcp_konusur = True
    tui_destegi = True

    def musait_mi(self):
        return True

    def tur_kos(self, metin, **k):          # arka plan kipi kullanilmaz
        yield MotorOlayi("bitti", "", {"basarili": True})

    def tui_plani(self, *, oturum_id, gecici, **k):
        oid = oturum_id or str(uuid.uuid4())
        dokum = Path(gecici) / f"sahte-{oid}.jsonl"
        return {"argv": [sys.executable, SAHTE_CLI, str(dokum)],
                "ortam": dict(os.environ), "kapat": "/exit", "oturum_id": oid,
                "dokum": lambda: dokum, "guven": (), "guven_isareti": "",
                "durdur": "\x1b"}

    def tui_cevir(self, k, durum):
        t = k.get("tur")
        if t == "metin":
            durum.setdefault("metin", []).append(k["metin"])
            return [MotorOlayi("metin", k["metin"])], False
        if t == "arac":
            durum["arac_sayisi"] = durum.get("arac_sayisi", 0) + 1
            durum.setdefault("kullanim", {})[str(len(durum.get("kullanim", {})))] = 10
            return [MotorOlayi("arac", k["ad"], {"ozet": k["ozet"]})], False
        if t == "girdi":
            durum.setdefault("girdiler", []).append(k["metin"])
        return [], t == "bitti"
