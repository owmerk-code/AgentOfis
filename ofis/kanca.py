# -*- coding: utf-8 -*-
"""GERCEK TERMINAL KANCASI -- CLI'in her arac cagrisini ofisin kapisina sorar.

Ajan gercek Claude Code / Codex terminalinde (TUI) calisirken CLI, her
arac cagrisindan once `PreToolUse` kancasini calistirir. Bu betik o
kancadir: girdiyi ofisin TEK kapisina (`mcp_sunucu.arac_izin_sor`, arka
plan kipinde de ayni islev) verir ve cevabi CLI'in anladigi bicime
cevirir.

Neden ayni islev: kapinin iki kopyasi olsaydi biri duzeltilir oteki
unutulurdu. Riskli eylem olcutu, patronun izinleri, onay defteri, bir
kez / is boyunca kapsami -- hepsi tek yerde kalir.

## Kapali kalir

Olculdu (29.09): Codex kanca PATLARSA eylemi CALISTIRIYOR (rm kostu).
O yuzden bu betik hicbir kosulda istisnayla cikmaz: her hata `deny` olur.
Python'un hic baslayamamasi burada yakalanamaz; onu turdan once
`--oz-sinama` yakalar (`oz_sinama` cagrisini koltuk yapar).

Kimlik ORTAMDAN gelir (OFIS_DB · OFIS_PROJE · OFIS_AJAN · OFIS_GOREV),
argumandan asla -- MCP sunucusuyla ayni kural.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _cevap(karar: str, sebep: str) -> str:
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": karar,
        "permissionDecisionReason": sebep}}, ensure_ascii=False)


def karar_ver(girdi: dict) -> str:
    """Kanca girdisi -> CLI cevabi (JSON metni). Hic istisna atmaz."""
    try:
        from ofis.mcp_sunucu import Oturum, arac_izin_sor
        arac = str(girdi.get("tool_name") or "")
        arg = girdi.get("tool_input")
        if not isinstance(arg, dict):
            arg = {}
        c = json.loads(arac_izin_sor(Oturum(), {"tool_name": arac, "input": arg}))
        if c.get("behavior") == "allow":
            return _cevap("allow", "ofis: serbest")
        return _cevap("deny", str(c.get("message") or "ofis kapisi durdurdu"))
    except Exception as exc:                     # noqa: BLE001 -- kapali kal
        return _cevap("deny", f"Ofis kapisi karar veremedi ({exc}). Guvenli "
                              "tarafta kaliyoruz: bu eylem YAPILMADI.")


def main() -> None:
    for akis in (sys.stdin, sys.stdout):
        try:
            akis.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if "--oz-sinama" in sys.argv:
        # Tur basinda: kanca gercekten calisiyor ve riskli komutu
        # durduruyor mu? Codex kanca duserse ACIK kaldigi icin sart.
        # KIMLIK SILINIR: sinama gercek onay defterine kart YAZMAMALI
        # (olculdu: ilk surum "rm -rf /oz-sinama" kartini patrona
        # dusurdu). Karar yine ayni olcutten gecer.
        import os
        for ad in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV"):
            os.environ.pop(ad, None)
        c = json.loads(karar_ver({"tool_name": "Bash",
                                  "tool_input": {"command": "rm -rf /oz-sinama"}}))
        print("TAMAM" if c["hookSpecificOutput"]["permissionDecision"] == "deny"
              else "BOZUK")
        return
    try:
        girdi = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        girdi = {}
    if not isinstance(girdi, dict):
        girdi = {}
    sys.stdout.write(karar_ver(girdi))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
