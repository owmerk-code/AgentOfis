# -*- coding: utf-8 -*-
"""Sahte Antigravity CLI: argumanlari ve ortami gunluge yazar, stream-json akisi uretir.

`SAHTE_AGY_GUNLUK` (json yolu) gunluk; `SAHTE_AGY_SENARYO`:
  basarili (varsayilan) · gorsel (evin brain/ klasorune bir .jpg birakir) · hata.
"""
import json
import os
import sys
import time
from pathlib import Path

gunluk = os.environ.get("SAHTE_AGY_GUNLUK")
if gunluk:
    Path(gunluk).write_text(json.dumps({
        "argv": sys.argv[1:], "cwd": os.getcwd(),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "OFIS_AJAN": os.environ.get("OFIS_AJAN", ""),
        "OFIS_GOREV": os.environ.get("OFIS_GOREV", ""),
    }), encoding="utf-8")
senaryo = os.environ.get("SAHTE_AGY_SENARYO", "basarili")
kid = "11111111-2222-3333-4444-555555555555"


def yaz(o):
    print(json.dumps(o, ensure_ascii=False), flush=True)


yaz({"event": "init", "conversation_id": kid, "init": {"model": "gemini-3.8-flash-low", "tools": []}})
yaz({"event": "step_update", "step_update": {"conversation_id": kid, "step_index": 1, "state": "DONE",
     "step_type": "agent_response", "usage": {"input_tokens": 100, "output_tokens": 10,
                                               "thinking_tokens": 5, "cache_read_tokens": 50,
                                               "total_tokens": 165}}})
yaz({"event": "step_update", "step_update": {"conversation_id": kid, "step_index": 2, "state": "ACTIVE",
     "step_type": "tool", "tool_name": "call_mcp_tool",
     "tool_info": {"name": "call_mcp_tool", "parameters": {"ServerName": "ofis", "ToolName": "kanit_ekle",
                                                          "Arguments": {"baslik": "x"}}}}})
yaz({"event": "step_update", "step_update": {"conversation_id": kid, "step_index": 2, "state": "DONE",
     "step_type": "tool", "tool_name": "call_mcp_tool", "tool_info": {"name": "call_mcp_tool"}}})
if senaryo == "gorsel":
    beyin = Path(os.environ["USERPROFILE"]) / ".gemini" / "antigravity-cli" / "brain" / "alt-konusma"
    beyin.mkdir(parents=True, exist_ok=True)
    (beyin / "logo_123.jpg").write_bytes(b"\xff\xd8\xff sahte jpg")
for parca in ("Is ", "bitti."):
    yaz({"event": "step_update", "step_update": {"conversation_id": kid, "step_index": 3, "state": "ACTIVE",
         "step_type": "agent_response", "text_delta": parca}})
durum = "SUCCESS" if senaryo != "hata" else "ERROR"
yaz({"event": "result", "result": {"conversation_id": kid, "status": durum, "response": "Is bitti.",
     "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}})
if senaryo == "hata":
    sys.stderr.write("RESOURCE_EXHAUSTED: quota exceeded")
    sys.exit(1)
