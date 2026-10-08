# -*- coding: utf-8 -*-
"""CANLI SISTEME DOKUNAN EYLEM (06.10.2026 olcum; 08.10.2026 kural).

Canli sisteme dokunmanin yollari: uretime dagitim (`vercel --prod`), canli
odeme (`stripe ... --live`, `sk_live_` anahtar), paket yayimi (`npm
publish`), baglanmis magaza/reklam hesabina yazma (Shopify, Meta). Ajan
kasadaki anahtari zaten GORMEZ (`tip.ortam_hazirla` sirlari dusurur).

KURAL (08.10.2026, patron: "sahte kip istemiyorum, her sey gercek
calisacak"): 06.10'daki takim basina "deneme kipi" KALDIRILDI. O kipte bu
eylemler SORULMADAN reddediliyordu -- patronun "deploy et" sozu bile
acmiyordu; yani varsayilan durumda ajan gercek isi bitiremiyordu (guc kisan
kisit). Simdi canliya dokunan eylem TEK KAPIDA SORULUR (yayin sinifi);
riskli olcutu onu baska bir sebeple zaten soruyorsa o bulgu kalir.
Patronun acik sozu o is icin izindir (`izin.py`), para HER ZAMAN sorulur.
Bu modul yalniz OLCER: canliya dokunuyor mu, neden.
"""

from __future__ import annotations

import re

#: Kabuk komutunda CANLI'ya dokunan kaliplar. Her biri olculebilir bir
#: komut bicimi; genis kelime ("deploy") burada YOK -- o zaten yayin sinifi.
KABUK_CANLI = [
    # `--prod` yalniz DAGITIM aracinda: `npm install --production` canli degil.
    (re.compile(r"\b(?:vercel|netlify|surge|amplify|deploy)\b[^\n]*?(?<![\w-])--prod(?:uction)?\b"),
     "uretime dagitim (--prod)"),
    (re.compile(r"\bvercel\s+promote\b"), "uretime dagitim (vercel promote)"),
    (re.compile(r"\bfirebase\s+deploy\b"), "uretime dagitim (firebase deploy)"),
    (re.compile(r"\bfly(?:ctl)?\s+deploy\b"), "uretime dagitim (fly deploy)"),
    (re.compile(r"\bwrangler\s+(?:deploy|publish)\b"), "uretime dagitim (wrangler)"),
    (re.compile(r"\bgit\s+push\s+(?:heroku|production|prod|live)\b"), "uretime itme"),
    (re.compile(r"\bshopify\s+(?:theme\s+publish|app\s+deploy)\b"), "magaza yayini (shopify)"),
    (re.compile(r"\bshopify\s+theme\s+push\b(?!.*--(?:unpublished|development))"),
     "canli temaya itme (shopify)"),
    (re.compile(r"\bstripe\b[^\n]*\s--live\b"), "canli odeme kipi (stripe --live)"),
    (re.compile(r"\b(?:sk|rk|pk)_live_[0-9A-Za-z]"), "CANLI odeme anahtari"),
    (re.compile(r"\b(?:npm|pnpm)\s+publish\b|\byarn\s+(?:npm\s+)?publish\b"), "paket yayimi"),
    (re.compile(r"\btwine\s+upload\b|\bcargo\s+publish\b|\bgem\s+push\b"), "paket yayimi"),
]

#: Baglayici (MCP) araci: CANLI hesaba yazan saglayicilar. Okuma serbest
#: (kapi zaten okumayi `None` doner); yazan her cagri canlidir.
BAGLAYICI_CANLI = re.compile(r"shopify|meta_?reklam|meta_ads|__ads_|stripe|woocommerce|paypal",
                             re.IGNORECASE)


def _kabukta(komut: str) -> str:
    for desen, sebep in KABUK_CANLI:
        if desen.search(komut):
            return sebep
    return ""


def degerlendir(arac: str, girdi: dict, bulgu, kok: str = "") -> str:
    """Eylem canliya dokunuyor mu? Doner: sebep ya da ''.

    `bulgu`: tek kapinin (`riskli.arac_degerlendir`) hukmu; baglayicida
    `None` = okuma (serbest), aksi yazma.
    """
    from . import riskli
    if arac in riskli.KABUK_ARACLARI:
        komut = str((girdi or {}).get("command") or "")
        sebep = _kabukta(komut)
        if sebep:
            return sebep
        # BETIK: komut bir dosya calistiriyorsa ICI de taranir (canli komutu
        # betige yazip calistirmak kapiyi asmasin; `riskli.betik_degerlendir`).
        import os
        cwd = str((girdi or {}).get("workdir") or (girdi or {}).get("cwd") or kok or "")
        for m in riskli._BETIK_KOMUTU.finditer(komut):
            yol = riskli._yol_coz(m.group(1), cwd)
            try:
                if not os.path.isfile(yol) or os.path.getsize(yol) > 512_000:
                    continue
                with open(yol, encoding="utf-8", errors="replace") as f:
                    sebep = _kabukta(f.read())
            except OSError:
                continue
            if sebep:
                return sebep + f" (betikte: {os.path.basename(yol)})"
        return ""
    if arac.startswith("mcp__") and BAGLAYICI_CANLI.search(arac) and bulgu is not None:
        return "canli hesaba yazma (" + arac.split("__")[-1] + ")"
    return ""


def bulgu(arac: str, girdi: dict, sebep: str) -> dict:
    """Canliya dokunan eylemin SORULAN bulgusu (onay karti icin; yayin
    sinifi: patronun acik sozu o is icin acar, kalici izin insandan)."""
    from . import riskli
    ad, risk = riskli.SINIFLAR["yayin"]
    hedef = str((girdi or {}).get("command") or arac)[:200]
    return {
        "sinif": "yayin", "ad": ad, "risk": risk, "esles": sebep,
        "arac": arac, "hedef": hedef, "element": hedef, "url": "",
        "sorulur": True,
        "eylem": f"{ad}: {hedef[:80]}",
        "sebep": f"CANLI sisteme dokunuyor ({sebep}); yapilmadan once patrona soruluyor.",
    }
