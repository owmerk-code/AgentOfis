# -*- coding: utf-8 -*-
"""Sahte Antigravity CLI: argumanlari ve ortami gunluge yazar, stream-json akisi uretir.

Gercegi gibi (`--input-format stream-json`, olculdu 04.10.2026): mesajlar
stdin'den NDJSON (`{"event":"user","message":{"content":...}}`) gelir, her
mesaj icin bir tur kosar ve `result` yazar; stdin kapaninca cikar.

`SAHTE_AGY_GUNLUK` (json yolu) gunluk; `SAHTE_AGY_SENARYO`:
  basarili (varsayilan) · gorsel (evin brain/ klasorune bir .jpg birakir) · hata ·
  yavas (arac sirasinda 2 sn bekler -- tur ici not) · uzun (arac sirasinda 60 sn -- durdurma).
"""
import json
import os
import sys
import time
from pathlib import Path

gunluk = os.environ.get("SAHTE_AGY_GUNLUK")
kayit = {
    "argv": sys.argv[1:], "cwd": os.getcwd(),
    "USERPROFILE": os.environ.get("USERPROFILE", ""),
    "OFIS_AJAN": os.environ.get("OFIS_AJAN", ""),
    "PSModuleAnalysisCachePath": os.environ.get("PSModuleAnalysisCachePath", ""),
    "OFIS_GOREV": os.environ.get("OFIS_GOREV", ""),
    "mesajlar": [],
}


def gunluge():
    if gunluk:
        Path(gunluk).write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")


gunluge()
senaryo = os.environ.get("SAHTE_AGY_SENARYO", "basarili")
kid = "11111111-2222-3333-4444-555555555555"
adim = [0]


def yaz(o):
    print(json.dumps(o, ensure_ascii=False), flush=True)


def basamak(**su):
    adim[0] += 1
    yaz({"event": "step_update", "step_update": {"conversation_id": kid, "step_index": adim[0], **su}})


def ilk_tur():
    basamak(state="DONE", step_type="agent_response",
            usage={"input_tokens": 100, "output_tokens": 10, "thinking_tokens": 5,
                   "cache_read_tokens": 50, "total_tokens": 165})
    basamak(state="ACTIVE", step_type="tool", tool_name="call_mcp_tool",
            tool_info={"name": "call_mcp_tool", "parameters": {
                "ServerName": "ofis", "ToolName": "kanit_ekle", "Arguments": {"baslik": "x"}}})
    if senaryo == "yavas":
        time.sleep(2)
    elif senaryo == "uzun":
        time.sleep(60)
    basamak(state="DONE", step_type="tool", tool_name="call_mcp_tool",
            tool_info={"name": "call_mcp_tool"})
    if senaryo == "gorsel":
        beyin = Path(os.environ["USERPROFILE"]) / ".gemini" / "antigravity-cli" / "brain" / "alt-konusma"
        beyin.mkdir(parents=True, exist_ok=True)
        (beyin / "logo_123.jpg").write_bytes(b"\xff\xd8\xff sahte jpg")
    for parca in ("Is ", "bitti."):
        basamak(state="ACTIVE", step_type="agent_response", text_delta=parca)
    durum = "SUCCESS" if senaryo != "hata" else "ERROR"
    yaz({"event": "result", "result": {"conversation_id": kid, "status": durum, "response": "Is bitti.",
         "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}})


yaz({"event": "init", "conversation_id": kid, "init": {"model": "gemini-3.8-flash-low", "tools": []}})
for satir in sys.stdin:
    if not satir.strip():
        continue
    m = json.loads(satir)
    if m.get("event") != "user":
        sys.stderr.write(f'stream input message event "{m.get("event")}" is not supported yet\n')
        continue
    kayit["mesajlar"].append((m.get("message") or {}).get("content"))
    gunluge()
    basamak(state="DONE", step_type="user_input")
    if len(kayit["mesajlar"]) == 1:
        ilk_tur()
        if senaryo == "hata":
            sys.stderr.write("RESOURCE_EXHAUSTED: quota exceeded")
            sys.exit(1)
    else:
        basamak(state="ACTIVE", step_type="agent_response", text_delta=" Not uygulandi.")
        yaz({"event": "result", "result": {"conversation_id": kid, "status": "SUCCESS",
                                           "response": "Not uygulandi."}})
