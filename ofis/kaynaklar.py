# -*- coding: utf-8 -*-
"""MOTORLARDAN GELENLER -- Claude ve Codex hesabinda ne varsa ajanlara da gelsin.

Patron (02.10.2026): *"claude ve codexteki tum skiller, baglayicilar,
eklentiler otomatik gelsin, ayarlarda gozuksun; ajanlar lazim oldugunda
kullansin; giris gerekiyorsa zaten sorar; gerekirse ben kapatirim."*
Istisnalar (patronun cevabi): masaustu islemi SORULUR, kisisel Chrome
ACILMAZ, kancali eklenti SORULUR, tarayici TEK: gomulu.

## Neden artik ucuz (OLCULDU, 02.10.2026, haiku, ayni tek cumle)

    bugunku ofis (her sey kapali)                  18.611 jeton/tur
    her sey acik, ertelenmis yukleme KAPALI        91.323
    her sey acik, ertelenmis yukleme ACIK          18.848
    + eklentiler, 118 beceri, context7 (restricted) 23.820

Normal Claude Code araclari ERTELENMIS yukler (yalniz adlari gider, gereken
o an acilir). Ofis bunu `ENABLE_TOOL_SEARCH=false` ile kapatmisti -- o gun
baglayici acilmiyordu. Codex eklentiler aciktayken zaten erteliyor
(7.146 jeton; eklentiler kapaliyken 16.926 -- olculdu).

## Yollar (hepsi olculdu)

* claude.ai baglayicilari: `ENABLE_CLAUDEAI_MCP_SERVERS=true`; kapatilan
  `--disallowedTools mcp__claude_ai_<Ad>` ile listeden TAMAMEN cikar.
* Claude eklentileri (claude.ai'dan esitlenen): `--plugin-dir` (her biri).
* Kullanicinin kendi MCP'leri (`~/.claude.json`): ikinci `--mcp-config`
  (`--restricted` kisisel ayari okumaz, acikca verilir). `playwright`
  CIKARILIR: tarayici tek, gomulu.
* Kullanicinin becerileri: ofisin beceri deposuna OTOMATIK kopyalanir
  (`beceri.claude_esitle`), oradan iki motora.
* Ajanin dosya araclari yine isin klasoruyle sinirli (`--restricted` kalir).

Ayarlar `motor_kaynaklari.json`da (ofisin evi): yalniz KAPATILANLAR ve
patronun onayladigi kancali eklentiler tutulur; gerisi varsayilan ACIK.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from .yollar import OFIS_EVI

AYAR = OFIS_EVI / "motor_kaynaklari.json"
GRUPLAR = ("claude_baglayici", "claude_eklenti", "claude_mcp", "codex_eklenti")
#: Tarayici TEK: gomulu (patron karari). Ajanin ikinci bir tarayicisi olmaz.
CIKARILAN_MCP = {"playwright": "Tarayıcı tek: ofisin gömülü tarayıcısı kullanılır."}
CODEX_PAZAR = "openai-curated-remote"


class KaynakHatasi(ValueError):
    pass


def _oku() -> dict:
    try:
        v = json.loads(AYAR.read_text(encoding="utf-8"))
        if isinstance(v, dict):
            return v
    except (OSError, ValueError):
        pass
    return {}


def _yaz(v: dict) -> None:
    AYAR.parent.mkdir(parents=True, exist_ok=True)
    g = AYAR.with_suffix(".json.tmp")
    g.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    g.replace(AYAR)


def kapalilar(grup: str) -> set:
    return set((_oku().get("kapali") or {}).get(grup) or [])


def ayarla(grup: str, ad: str, acik: bool) -> None:
    if grup not in GRUPLAR:
        raise KaynakHatasi(f"Bilinmeyen grup: {grup}")
    ad = str(ad or "").strip()
    if not ad:
        raise KaynakHatasi("Ad bos olamaz.")
    if grup == "claude_mcp" and ad in CIKARILAN_MCP and acik:
        raise KaynakHatasi(CIKARILAN_MCP[ad])
    v = _oku()
    k = set((v.setdefault("kapali", {})).get(grup) or [])
    (k.discard if acik else k.add)(ad)
    v["kapali"][grup] = sorted(k)
    _yaz(v)


def kanca_onayla(ad: str, onay: bool) -> None:
    v = _oku()
    k = set(v.get("kanca_onayli") or [])
    (k.add if onay else k.discard)(ad)
    v["kanca_onayli"] = sorted(k)
    _yaz(v)


# -- Claude ------------------------------------------------------------------

def _claude_ev() -> Path:
    """Patronun Claude klasoru (salt okunur kaynak). `OFIS_CLAUDE_EV`:
    sinamalar BOS bir klasor verir -- yoksa sonuc makineye gore degisir
    (olculdu 02.10: beceri sinamasi patronun gercek becerilerini kopyaladi)."""
    import os
    return Path(os.environ.get("OFIS_CLAUDE_EV") or (Path.home() / ".claude"))


def _claude_json() -> Path:
    import os
    return Path(os.environ.get("OFIS_CLAUDE_JSON") or (Path.home() / ".claude.json"))


def sunucu_adi(baglayici_ad: str) -> str:
    """claude.ai baglayici adi -> arac adindaki sunucu parcasi (olculdu:
    'Meta Reklamları' -> 'claude_ai_Meta_Reklamlar', 'Google Drive' ->
    'claude_ai_Google_Drive'): ASCII disi harf duser, gerisi '_' olur."""
    s = "".join(c for c in baglayici_ad if ord(c) < 128)
    return "claude_ai_" + re.sub(r"[^A-Za-z0-9_-]", "_", s)


def claude_eklentileri() -> list:
    """claude.ai'dan esitlenen eklentiler. Kancali olan varsayilan KAPALI."""
    onayli = set(_oku().get("kanca_onayli") or [])
    kapali = kapalilar("claude_eklenti")
    out = []
    for pj in sorted(_claude_ev().glob("plugins/synced/*/*/.claude-plugin/plugin.json")):
        kok = pj.parent.parent
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        ad = d.get("name") or kok.name
        kancali = (kok / "hooks").exists() or bool(d.get("hooks"))
        mcp = []
        try:
            mcp = list((json.loads((kok / ".mcp.json").read_text(encoding="utf-8"))
                        .get("mcpServers") or {}).keys())
        except (OSError, ValueError):
            pass
        acik = ad not in kapali and (not kancali or ad in onayli)
        out.append({"ad": ad, "yol": str(kok), "aciklama": (d.get("description") or "")[:240],
                    "kancali": kancali, "kanca_onayli": ad in onayli, "mcp": mcp,
                    "beceri": len(list((kok / "skills").glob("*/SKILL.md"))), "acik": acik})
    return out


def claude_mcpleri() -> list:
    """Kullanicinin Claude Code'daki kendi MCP sunuculari (`~/.claude.json`)."""
    try:
        d = json.loads(_claude_json().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    kapali = kapalilar("claude_mcp")
    out = []
    for ad, tanim in (d.get("mcpServers") or {}).items():
        out.append({"ad": ad, "tanim": tanim, "cikarildi": CIKARILAN_MCP.get(ad, ""),
                    "acik": ad not in kapali and ad not in CIKARILAN_MCP})
    return out


def claude_bayraklari() -> dict:
    """Claude turuna eklenecekler: argv, ortam ve ikinci MCP yapilandirmasi."""
    argv, sunucular = [], {}
    for e in claude_eklentileri():
        if e["acik"]:
            argv += ["--plugin-dir", e["yol"]]
    for m in claude_mcpleri():
        if m["acik"]:
            sunucular[m["ad"]] = m["tanim"]
    yasak = [f"mcp__{sunucu_adi(a)}" for a in sorted(kapalilar("claude_baglayici"))]
    return {"argv": argv, "yasak": yasak,
            "mcp": json.dumps({"mcpServers": sunucular}, ensure_ascii=False) if sunucular else "",
            "ortam": {"ENABLE_TOOL_SEARCH": "true", "ENABLE_CLAUDEAI_MCP_SERVERS": "true"}}


# -- Codex -------------------------------------------------------------------

_CODEX_ONBELLEK = {"an": 0.0, "liste": []}


def codex_eklentileri(codex_evi: str = "", *, taze: bool = False) -> list:
    """Ofisin Codex evindeki eklentiler ve katalog (`codex plugin list`)."""
    if not taze and time.time() - _CODEX_ONBELLEK["an"] < 600 and _CODEX_ONBELLEK["liste"]:
        return _CODEX_ONBELLEK["liste"]
    yol = shutil.which("codex")
    if not yol:
        return []
    ortam = None
    if codex_evi:
        import os
        ortam = dict(os.environ, CODEX_HOME=str(codex_evi))
    try:
        p = subprocess.run([yol, "plugin", "list"], capture_output=True, timeout=60, env=ortam,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for s in (p.stdout or "").splitlines():
        m = re.match(r"^(\S+)@(\S+)\s+(installed, enabled|installed, disabled|not installed)\s+(\S+)", s)
        if m:
            out.append({"ad": m.group(1), "pazar": m.group(2), "kurulu": m.group(3).startswith("installed"),
                        "acik": m.group(3) == "installed, enabled", "surum": m.group(4)})
    _CODEX_ONBELLEK.update(an=time.time(), liste=out)
    return out


def codex_kur(ad: str, codex_evi: str, *, kaldir: bool = False) -> str:
    """Katalogdaki bir eklentiyi ofisin Codex evine kurar ya da kaldirir."""
    if not re.match(r"^[A-Za-z0-9._-]{1,120}$", ad or ""):
        raise KaynakHatasi("Gecersiz eklenti adi.")
    yol = shutil.which("codex")
    if not yol:
        raise KaynakHatasi("codex kurulu degil.")
    import os
    p = subprocess.run([yol, "plugin", "remove" if kaldir else "add", f"{ad}@{CODEX_PAZAR}"],
                       capture_output=True, timeout=180, encoding="utf-8", errors="replace",
                       env=dict(os.environ, CODEX_HOME=str(codex_evi)), stdin=subprocess.DEVNULL)
    _CODEX_ONBELLEK["an"] = 0.0
    if p.returncode != 0:
        raise KaynakHatasi((p.stderr or p.stdout or "codex hata verdi").strip()[-300:])
    return (p.stdout or "").strip()[-300:]


#: Codex'in KENDI tarayicilari kapali: tarayici tek, gomulu (patron karari).
#: Masaustu (computer_use) KAPATILMAZ: masaustu isi onay kapisinda SORULUR.
CODEX_KAPALI_OZELLIKLER = ("browser_use", "browser_use_external", "in_app_browser")


def codex_bayraklari() -> list:
    out = []
    for oz in CODEX_KAPALI_OZELLIKLER:
        out += ["-c", f"features.{oz}=false"]
    return out
