# -*- coding: utf-8 -*-
"""SAHTE AGY ETKILESIMLI KIPI -- Antigravity'nin gercek terminal sinamasi (jeton yok).

Gercek agy 1.3.1'in etkilesimli kipinde OLCULEN (08.10.2026) dosyalari ayni
bicimde yazar (USERPROFILE = ajanin evi):
  .gemini/antigravity-cli/cache/last_conversations.json  {calisma klasoru: kimlik}
  .gemini/antigravity-cli/brain/<kimlik>/.system_generated/logs/transcript_full.jsonl
    USER_INPUT / PLANNER_RESPONSE (tool_calls, jeton) / GENERIC (arac sonucu)
Ekran: hazir olunca "? for shortcuts"; `/exit` kapatir; Esc turu keser.
Kurulum isareti (`cache/onboarding.json` tamam) YOKSA gercek agy gibi kurulum
ekranini gosterir ve mesaj almaz.

Davranis mesajdaki isaretlerden:
  #ARAC#   -> once write_to_file (DONE) sonra run_command (ERROR) adimi
  #GORSEL# -> evin brain klasorune bir PNG birakir (tur sonu teslimi sinamasi)
  #YAVAS#  -> cevap 6 sn surer (Esc sinamasi)
  #KOTA#   -> cevap RESOURCE_EXHAUSTED hatasiyla biter
Argumanlar: agy'ninkiler (--model, --conversation ...).
"""
import json
import msvcrt
import os
import sys
import time
import uuid
from pathlib import Path

EV = Path(os.environ["USERPROFILE"]) / ".gemini" / "antigravity-cli"
KLASOR = os.getcwd()
arg = sys.argv[1:]
kimlik = arg[arg.index("--conversation") + 1] if "--conversation" in arg else ""
model = arg[arg.index("--model") + 1] if "--model" in arg else "gemini-3.8-flash-medium"
with open(Path(os.environ["USERPROFILE"]) / "sahte_agy_argv.json", "w", encoding="utf-8") as f:
    json.dump(arg, f)

try:
    kurulum = json.loads((EV / "cache" / "onboarding.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    kurulum = {}
if not kurulum.get("onboardingComplete"):
    print("Welcome to Antigravity CLI!\nChoose your color scheme:", flush=True)
    while True:
        time.sleep(1)


def satir(k):
    trs = EV / "brain" / kimlik / ".system_generated" / "logs" / "transcript_full.jsonl"
    trs.parent.mkdir(parents=True, exist_ok=True)
    with open(trs, "a", encoding="utf-8") as f:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")


def mesaj_oku():
    tampon = ""
    while True:
        ch = msvcrt.getwch()
        if ch == "\r":
            return tampon
        if ch == "\x1b":
            dizi = ""
            while msvcrt.kbhit():
                dizi += msvcrt.getwch()
                if dizi.endswith("~"):
                    break
            continue
        if ch == "\x15":
            tampon = ""
            continue
        tampon += ch


print(f"Antigravity CLI 1.3.1 (sahte)\n{KLASOR}\n> \n? for shortcuts  {model}", flush=True)
adim = 0
while True:
    m = mesaj_oku()
    if m.strip() == "/exit":
        break
    if not m.strip():
        continue
    if not kimlik:
        kimlik = str(uuid.uuid4())
    (EV / "cache").mkdir(parents=True, exist_ok=True)
    (EV / "cache" / "last_conversations.json").write_text(json.dumps({KLASOR: kimlik}), encoding="utf-8")
    satir({"step_index": adim, "type": "USER_INPUT", "status": "DONE", "content": m})
    adim += 1
    print("esc to cancel  Generating...", flush=True)
    if "#ARAC#" in m:
        satir({"step_index": adim, "type": "PLANNER_RESPONSE", "status": "DONE", "input_tokens": 1000,
               "output_tokens": 20, "tool_calls": [{"name": "write_to_file", "args": {
                   "TargetFile": os.path.join(KLASOR, "notlar.txt"), "CodeContent": "merhaba"}}]})
        adim += 1
        Path(KLASOR, "notlar.txt").write_text("merhaba", encoding="utf-8")
        satir({"step_index": adim, "type": "GENERIC", "status": "DONE", "content": "Created file notlar.txt"})
        adim += 1
        satir({"step_index": adim, "type": "PLANNER_RESPONSE", "status": "DONE", "input_tokens": 1100,
               "output_tokens": 15, "tool_calls": [{"name": "run_command", "args": {
                   "CommandLine": "Remove-Item notlar.txt"}}]})
        adim += 1
        satir({"step_index": adim, "type": "GENERIC", "status": "ERROR",
               "content": "JSON hook failed: exit status 2, stderr: OFIS: silme sorulmali"})
        adim += 1
    if "#GORSEL#" in m:
        g = EV / "brain" / kimlik / "kedi.png"
        g.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    if "#YAVAS#" in m:
        bas = time.time()
        kesildi = False
        while time.time() - bas < 6:
            if msvcrt.kbhit() and msvcrt.getwch() == "\x1b":
                kesildi = True
                break
            time.sleep(0.05)
        if kesildi:
            print("Cancelled.\n? for shortcuts", flush=True)
            continue
    if "#KOTA#" in m:
        satir({"step_index": adim, "type": "GENERIC", "status": "ERROR",
               "content": "RESOURCE_EXHAUSTED: quota exceeded"})
        adim += 1
        satir({"step_index": adim, "type": "PLANNER_RESPONSE", "status": "DONE",
               "input_tokens": 10, "output_tokens": 1, "content": ""})
        adim += 1
        print("? for shortcuts", flush=True)
        continue
    cevap = "TAMAM: " + " ".join(m.split())[-40:]
    satir({"step_index": adim, "type": "PLANNER_RESPONSE", "status": "DONE", "input_tokens": 1200,
           "cache_read_tokens": 300, "output_tokens": 8, "content": cevap})
    adim += 1
    print(cevap + "\n? for shortcuts", flush=True)
