# -*- coding: utf-8 -*-
"""DENEME / CANLI AYRIMI (06.10.2026, Asama 4 / K16, E67).

Rakipte "prod anahtari acik bayrak ister" vardi; bizde ajan kasadaki
anahtari zaten GORMEZ (`tip.ortam_hazirla` sirlari dusurur). Canli sisteme
dokunmanin yollari baska: uretime dagitim (`vercel --prod`), canli odeme
(`stripe ... --live`, `sk_live_` anahtar), paket yayimi (`npm publish`),
baglanmis magaza/reklam hesabina yazma (Shopify, Meta).

Kural: takimin **canli bayragi** (varsayilan KAPALI = deneme kipi) acik
degilse bu eylemler SORULMAZ, REDDEDILIR -- patronun "deploy et" sozu bile
acmaz (soz izin verir, kip kurali degistirmez). Ajana ne yapacagi soylenir:
onizleme/deneme yolunu kullan ya da patrona "canliyi ac" de. Bayrak aciksa
bugunku tek kapi aynen isler (yayin/para yine sorulur).

Neden sert ret, soru degil: "deploy et" diyen patron cogu zaman onizlemeyi
kasteder; deneme kipinde ajan canliya yanlislikla cikamaz (yapi, rica degil).
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


def acik_mi(db, kanat_id: str) -> bool:
    if not kanat_id:
        return False
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT canli FROM kanat WHERE id = ?", (kanat_id,)).fetchone()
    except Exception:                       # noqa: BLE001 -- eski defter: sutun yok -> deneme
        return False
    return bool(r and r["canli"])


def ayarla(db, proje_id: str, kanat_id: str, acik: bool) -> bool:
    with db.baglanti() as c:
        n = c.execute("UPDATE kanat SET canli = ? WHERE id = ? AND proje_id = ?",
                      (1 if acik else 0, kanat_id, proje_id)).rowcount
    if not n:
        raise ValueError("Takim yok.")
    db.olay_yaz(proje_id, "canli_kip", f"{kanat_id}: {'CANLI ACIK' if acik else 'deneme'}",
                ajan_ad="insan")
    return bool(acik)


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


def ret_metni(sebep: str) -> str:
    return ("CANLI KAPALI -- bu takim DENEME kipinde: " + sebep + " YAPILMADI ve "
            "sorulmadi. Onizleme / deneme yolunu kullan (orn. `vercel` --prod'suz, "
            "stripe test kipi, magazada taslak). Canliya cikmak gerekiyorsa isi "
            "bitir ve raporunda patrona 'takimin canli kipini Ayarlar'dan acman "
            "gerekiyor' de; bunu kendin asmaya CALISMA.")
