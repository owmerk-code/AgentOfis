# -*- coding: utf-8 -*-
"""MOTORLARDAN GELENLER duman testi (02.10.2026).

Patron: "Claude ve Codex'te ne varsa otomatik gelsin, ayarlarda gorunsun,
gerekirse ben kapatirim." Istisnalar: kancali eklenti SORULUR, tarayici tek
(kullanicinin playwright'i ve Codex'in tarayicilari kapali), masaustu
kapatilmaz (kapida sorulur). Sinanan (sahte Claude klasoruyle, jeton yok):
  1. eklentiler: normal ACIK, kancali onaysiz KAPALI, onaylaninca acik
  2. kendi MCP'ler: acik; playwright CIKARILIR ve acilamaz
  3. Claude komutu: eklentiler --plugin-dir, MCP'ler ikinci --mcp-config,
     kapatilan baglayici --disallowedTools; saf yargi turunda hicbiri
  4. beceriler otomatik gelir, guncellenir, silinen bir daha gelmez
  5. Codex: kendi tarayicilari kapali, masaustu kapatilmadi
  6. panel: liste, MCP tanimindaki ANAHTAR panele sizmaz, ac/kapat
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- OFIS_CLAUDE_EV bos gecici klasor; ILK

import json
import os
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import Ofis, Veritabani, beceri, kaynaklar  # noqa: E402
from ofis.motor.claude import ClaudeMotoru  # noqa: E402
from ofis.motor import codex as CX  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== motorlardan gelenler duman testi ==\n")
CEV = Path(os.environ["OFIS_CLAUDE_EV"])
sina("Claude klasoru GECICI (patronunkine dokunulmaz)", "ofis-claude-sinama-" in str(CEV))


def eklenti(ad: str, kancali: bool = False):
    k = CEV / "plugins" / "synced" / "hesap1" / ad
    (k / ".claude-plugin").mkdir(parents=True)
    (k / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": ad, "description": f"{ad} eklentisi"}),
                                                      encoding="utf-8")
    (k / "skills" / f"{ad}-becerisi").mkdir(parents=True)
    (k / "skills" / f"{ad}-becerisi" / "SKILL.md").write_text(f"---\nname: {ad}-becerisi\ndescription: d\n---\n",
                                                             encoding="utf-8")
    (k / ".mcp.json").write_text(json.dumps({"mcpServers": {"slack": {"type": "http", "url": "u"}}}),
                                 encoding="utf-8")
    if kancali:
        (k / "hooks").mkdir()
        (k / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")
    return k


def kullanici_becerisi(ad: str, metin: str = "Yordam."):
    k = CEV / "skills" / "synced" / "hesap1" / ad
    k.mkdir(parents=True, exist_ok=True)
    (k / "SKILL.md").write_text(f"---\nname: {ad}\ndescription: {ad} becerisi\n---\n\n{metin}\n", encoding="utf-8")
    return k


print("1. eklentiler")
e_tasarim = eklenti("tasarim")
e_kanca = eklenti("kancali", kancali=True)
ek = {e["ad"]: e for e in kaynaklar.claude_eklentileri()}
sina("normal eklenti varsayilan ACIK", ek["tasarim"]["acik"] and not ek["tasarim"]["kancali"])
sina("kancali eklenti onaysiz KAPALI (kapinin gormedigi komut)", ek["kancali"]["kancali"] and not ek["kancali"]["acik"])
sina("eklentinin bagladigi MCP'ler gorunur", ek["tasarim"]["mcp"] == ["slack"])

print("\n2. kendi MCP'ler")
Path(os.environ["OFIS_CLAUDE_JSON"]).write_text(json.dumps({"mcpServers": {
    "context7": {"type": "http", "url": "https://mcp.context7.com/mcp", "headers": {"Authorization": "Bearer COK-GIZLI-1"}},
    "playwright": {"command": "npx", "args": ["@playwright/mcp"]}}}), encoding="utf-8")
mc = {m["ad"]: m for m in kaynaklar.claude_mcpleri()}
sina("context7 ACIK", mc["context7"]["acik"])
sina("playwright CIKARILDI (tarayici tek: gomulu)", not mc["playwright"]["acik"] and mc["playwright"]["cikarildi"])
try:
    kaynaklar.ayarla("claude_mcp", "playwright", True)
    sina("playwright ACILAMAZ", False)
except kaynaklar.KaynakHatasi:
    sina("playwright ACILAMAZ", True)

print("\n3. Claude komutu")
kb = kaynaklar.claude_bayraklari()
sina("acik eklenti --plugin-dir ile, kancali VERILMEDI",
     str(e_tasarim) in kb["argv"] and str(e_kanca) not in kb["argv"], str(kb["argv"]))
sina("ikinci MCP yapilandirmasinda context7 var, playwright YOK",
     "context7" in kb["mcp"] and "playwright" not in kb["mcp"])
kaynaklar.kanca_onayla("kancali", True)
sina("kanca onaylaninca eklenti gelir", str(e_kanca) in kaynaklar.claude_bayraklari()["argv"])
kaynaklar.kanca_onayla("kancali", False)
kaynaklar.ayarla("claude_eklenti", "tasarim", False)
sina("kapatilan eklenti gelmez", str(e_tasarim) not in kaynaklar.claude_bayraklari()["argv"])
kaynaklar.ayarla("claude_eklenti", "tasarim", True)
kaynaklar.ayarla("claude_baglayici", "Meta Reklamları", False)
sina("kapatilan baglayici olculen ad kuraliyla yasak", kaynaklar.claude_bayraklari()["yasak"]
     == ["mcp__claude_ai_Meta_Reklamlar"])
cm = ClaudeMotoru(calistirilabilir="claude")
k = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False, model="haiku", efor="normal",
                  yazabilir=True, ek_klasorler=(), butce_usd=None)
sina("komutta eklenti, kullanici MCP'si ve yasak var",
     str(e_tasarim) in k and any("context7" in x for x in k)
     and "--disallowedTools" in k and "mcp__claude_ai_Meta_Reklamlar" in k, str(k)[-300:])
sina("komutta ToolSearch (ertelenmis yukleme)", any("ToolSearch" in x for x in k))
ks = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False, model="haiku", efor="normal",
                   yazabilir=False, ek_klasorler=(), butce_usd=None, araclar_kapali=True)
sina("saf yargi turunda HICBIRI yok (strict, eklentisiz)",
     "--strict-mcp-config" in ks and str(e_tasarim) not in ks and not any("context7" in x for x in ks))
kaynaklar.ayarla("claude_baglayici", "Meta Reklamları", True)

print("\n4. beceriler otomatik")
kullanici_becerisi("docx-yaz", "Ilk surum.")
yeni = beceri.claude_esitle(zorla=True)
sina("kullanicinin becerisi depoya KENDILIGINDEN geldi", yeni == ["docx-yaz"]
     and (beceri.KOK / "skills" / "docx-yaz" / "SKILL.md").exists(), str(yeni))
time.sleep(1.1)
kullanici_becerisi("docx-yaz", "Ikinci surum.")
beceri.claude_esitle(zorla=True)
sina("kaynakta degisen beceri GUNCELLENDI", "Ikinci surum" in (beceri.KOK / "skills" / "docx-yaz" / "SKILL.md")
     .read_text(encoding="utf-8"))
beceri.sil("docx-yaz")
beceri.claude_esitle(zorla=True)
sina("patronun SILDIGI otomatik beceri bir daha GELMEDI", not (beceri.KOK / "skills" / "docx-yaz").exists())

kullanici_becerisi("chrome-browser")
beceri.claude_esitle(zorla=True)
sina("kisisel Chrome'u suren beceri KAPALI gelir (tarayici tek: gomulu)",
     (beceri.KOK / "kapali" / "chrome-browser" / "SKILL.md").exists()
     and not (beceri.KOK / "skills" / "chrome-browser").exists())

print("\n5. Codex")
sina("Codex'in kendi tarayicilari KAPALI", all(f"features.{o}=false" in CX.OFIS_KURALLARI
                                              for o in ("browser_use", "in_app_browser")))
sina("masaustu (computer_use) KAPATILMADI -- kapida sorulur",
     not any("computer_use" in x for x in CX.OFIS_KURALLARI))
_cx = CX.CodexMotoru(calistirilabilir="codex")
_k = _cx._komut_kur("", devam=False, model="m", efor="", yazabilir=False, ek_klasorler=(), klasor=str(KOK))
sina("Codex komutunda kurallar var", "features.browser_use=false" in _k)

print("\n6. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis import panel  # noqa: E402
_d = Path(tempfile.mkdtemp(prefix="ofis-kaynak-"))
Ofis.proje_ac(Veritabani(_d / "o.sqlite3"), "Kaynak", amac="a", basari_olcutu="b", kok_klasor=str(_d))
kaynaklar.codex_eklentileri = lambda *a, **k: [{"ad": "github", "kurulu": True, "acik": True, "surum": "1"}]
cl = TestClient(panel.olustur(_d / "o.sqlite3", "Kaynak"))
r = cl.get("/api/kaynaklar")
sina("GET /api/kaynaklar", r.status_code == 200 and r.json()["claude_eklenti"] and r.json()["codex_eklenti"])
sina("MCP tanimindaki ANAHTAR panele SIZMAZ", "COK-GIZLI-1" not in r.text, r.text[:200])
sina("eklenti yolu panele gitmez (yalniz ad)", "plugins" not in json.dumps(r.json()["claude_eklenti"]))
r = cl.post("/api/kaynaklar", json={"grup": "claude_mcp", "ad": "context7", "acik": False})
sina("panelden kapat", r.status_code == 200 and "context7" not in kaynaklar.claude_bayraklari()["mcp"])
r = cl.post("/api/kaynaklar", json={"grup": "claude_mcp", "ad": "playwright", "acik": True})
sina("panelden playwright acilamaz (400)", r.status_code == 400)
JS = (KOK / "web" / "ayarlar.js").read_text(encoding="utf-8")
sina("Ayarlar'da 'Eklentiler ve MCP' ve kartta 'ajanlara acik'",
     "function ayarKaynak(" in JS and "ajanlara açık" in JS)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
