# -*- coding: utf-8 -*-
"""OFIS CARPANI -- ayni is, ofiste ve dogrudan Claude'da: ne kadar fazla harcaniyor?

Patron (03.10.2026): "normal claude veya gpt kullanirken'den fazla token yiyen
bir sistem olursa anlami kalmaz." Bu arac olcer, tahmin etmez.

Her is icin:
  * OFIS: gercek setin kendisi (`gercek_set.is_kos`): lider + isci + inceleme,
    bedel `tur_ozeti`lerden (her yol: lider, inceleme, isci).
  * DOGRUDAN: ayni fikstur, bos gecici klasorde `claude -p <mesaj>` -- patronun
    normal kullanimi gibi (kendi ayarlari, kendi eklentileri), ayni model.
  * IKISI de ayni dogrulayicidan gecer (dosya isleri).
Carpan = ofis maliyeti / dogrudan maliyet (API karsiligi; abonelikte kota
agirligini tasiyan sayi). Jeton toplamlari da yazilir.

Kullanim: python testler/carpan.py G03 G04 [--model sonnet]
Kota harcar (gercek motor). Sonuc `testler/rapor/carpan-*.md`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "testler"))
sys.path.insert(0, str(KOK))
for _a in (sys.stdout, sys.stderr):
    try:
        _a.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import gercek_set as G  # noqa: E402  (OFIS_EV gercek ev: giris orada)
from ofis.motor.claude import ClaudeMotoru  # noqa: E402

RAPOR = KOK / "testler" / "rapor"


def dogrudan(no: str, model: str) -> dict:
    """Ayni isi dogrudan Claude'a verir (bos gecici klasor, ayni fikstur)."""
    tanim = G.ISLER[no]
    ana = Path(tempfile.mkdtemp(prefix=f"ofis-carpan-{no}-"))
    kok = ana / "calisma"
    kok.mkdir()
    bag: dict = {}
    tanim["fikstur"](kok, bag)
    mesaj = tanim["mesaj"](bag)
    exe = ClaudeMotoru().calistirilabilir
    t0 = time.time()
    p = subprocess.run([exe, "-p", mesaj, "--model", model, "--output-format", "json",
                        "--permission-mode", "acceptEdits",
                        "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                        "WebSearch", "WebFetch"],
                       cwd=str(kok), capture_output=True, timeout=900, stdin=subprocess.DEVNULL,
                       encoding="utf-8", errors="replace")
    sure = round(time.time() - t0, 1)
    try:
        j = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"durum": "hata", "hata": (p.stderr or p.stdout)[-300:], "sure_sn": sure}
    u = j.get("usage") or {}
    jeton = sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                              "cache_creation_input_tokens", "cache_read_input_tokens"))
    olcut = []
    try:
        olcut = [(o, bool(g), n) for o, g, n in tanim["dogrula"](kok, None, bag)]
    except Exception as exc:  # noqa: BLE001 -- dogrulayici ofise bakiyorsa olculemez
        olcut = [("dogrulayici ofis istiyor (dogrudanda olculemez)", None, str(exc)[:120])]
    olculen = [o for o in olcut if o[1] is not None]
    return {"durum": ("gecti" if olculen and all(o[1] for o in olculen) else
                      "olculemedi" if not olculen else "kaldi"),
            "olcut": olcut, "jeton": jeton, "maliyet_usd": round(float(j.get("total_cost_usd") or 0), 4),
            "sure_sn": sure, "cevap": str(j.get("result") or "")[:300]}


def ofiste(no: str) -> dict:
    s = G.is_kos(no, "claude")
    bedel = s.get("bedel") or {}
    return {"durum": s.get("durum"), "sure_sn": s.get("sure_sn"),
            "jeton": sum(b["jeton"] for b in bedel.values()),
            "maliyet_usd": round(sum(b["maliyet_usd"] for b in bedel.values()), 4),
            "yol": bedel, "kalan": [o["olcut"] for o in (s.get("olcutler", []) + s.get("kalite", []))
                                    if not o["gecti"]], "hata": s.get("hata", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("isler", nargs="+")
    ap.add_argument("--model", default=G.MODELLER["claude"]["lider"],
                    help="dogrudan kosunun modeli (ofisin lider modeliyle ayni olmali)")
    a = ap.parse_args()
    sonuc = []
    for no in a.isler:
        print(f"== {no} {G.ISLER[no]['ad']}", flush=True)
        o = ofiste(no)
        print(f"   ofis    : {o['durum']} · {o['jeton']:,} jeton · ${o['maliyet_usd']} · {o['sure_sn']} sn",
              flush=True)
        d = dogrudan(no, a.model)
        print(f"   dogrudan: {d['durum']} · {d.get('jeton', 0):,} jeton · ${d.get('maliyet_usd')} · "
              f"{d['sure_sn']} sn", flush=True)
        sonuc.append({"no": no, "ad": G.ISLER[no]["ad"], "ofis": o, "dogrudan": d})
    RAPOR.mkdir(exist_ok=True)
    ad = RAPOR / f"carpan-{_dt.datetime.now():%Y%m%d-%H%M%S}"
    ad.with_suffix(".json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    satir = [f"# Ofis carpani -- ofis (lider {G.MODELLER['claude']['lider']}, isci "
             f"{G.MODELLER['claude']['isci']}) / dogrudan ({a.model})", "",
             "| Is | Ofis | Dogrudan | Maliyet carpani | Jeton carpani | Sure (ofis/dogrudan) |",
             "|---|---|---|---|---|---|"]
    for r in sonuc:
        o, d = r["ofis"], r["dogrudan"]
        mc = (o["maliyet_usd"] / d["maliyet_usd"]) if d.get("maliyet_usd") else None
        jc = (o["jeton"] / d["jeton"]) if d.get("jeton") else None
        satir.append(f"| {r['no']} {r['ad']} | {o['durum']} ${o['maliyet_usd']} | {d['durum']} "
                     f"${d.get('maliyet_usd')} | {mc and f'{mc:.1f}x'} | {jc and f'{jc:.1f}x'} | "
                     f"{o['sure_sn']}/{d['sure_sn']} sn |")
    satir += ["", "Ofis yol dagilimi (tur · jeton · $):", ""]
    for r in sonuc:
        satir.append(f"- {r['no']}: " + " · ".join(
            f"{y} {b['tur']} tur/{b['jeton']:,}/${b['maliyet_usd']}" for y, b in r["ofis"]["yol"].items()))
    ad.with_suffix(".md").write_text("\n".join(satir) + "\n", encoding="utf-8")
    print("\n".join(satir))


if __name__ == "__main__":
    main()
