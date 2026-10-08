# -*- coding: utf-8 -*-
"""CANLI SISTEME DOKUNAN EYLEM (06.10 olcum; 08.10.2026 kural). Jeton yakmaz.

08.10 (patron: "sahte kip istemiyorum, her sey gercek calisacak"): takim
"deneme kipi" KALDIRILDI. Canliya dokunan eylem REDDEDILMEZ, tek kapida
SORULUR; patronun kalici izni acar; para her zaman sorulur. Sinanan:
kaliplar (dogru pozitif + yanlis pozitif yok), betik icindeki canli komut,
baglayici yazma/okuma, uctan uca kapi (claude ve codex ayni `izin_sor`),
panelde deneme kipi ayari YOK.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, canli as C, izin as IZ, mcp_sunucu as M  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("1. kaliplar")
CANLI = ["vercel --prod", "npx vercel deploy --prod --yes", "netlify deploy --prod --dir=dist",
         "firebase deploy --only hosting", "stripe charges create --amount 100 --live",
         "export STRIPE_KEY=sk_live_51Habc", "npm publish", "pnpm publish --access public",
         "git push heroku main", "shopify theme push", "flyctl deploy", "wrangler deploy",
         "python -c \"import subprocess; subprocess.run(['vercel','--prod'])\""]
DENEME = ["vercel", "vercel deploy", "npm install --production", "npm ci --production",
          "shopify theme push --unpublished", "firebase hosting:channel:deploy pr1",
          "git push origin main", "stripe listen --forward-to localhost:3000",
          "echo sk_test_51Habc", "python deploy_notlari.py --help", "ls -la"]
for k in CANLI:
    sina(f"CANLI: {k[:50]}", C.degerlendir("Bash", {"command": k}, None) != "")
for k in DENEME:
    sina(f"canli DEGIL: {k[:50]}", C.degerlendir("Bash", {"command": k}, None) == "",
         C.degerlendir("Bash", {"command": k}, None))
d = Path(tempfile.mkdtemp(prefix="ofis-canli-"))
(d / "yayinla.sh").write_text("#!/bin/sh\nnpm run build\nvercel --prod\n", encoding="utf-8")
sina("betigin ICINDEKI canli komut bulunur",
     "betikte" in C.degerlendir("Bash", {"command": "bash yayinla.sh"}, None, str(d)))
sina("baglayici YAZMA (Shopify) canli",
     C.degerlendir("mcp__claude_ai_Shopify__update-product", {}, {"sorulur": False}) != "")
sina("baglayici OKUMA (bulgu yok) canli degil",
     C.degerlendir("mcp__claude_ai_Shopify__get-product", {}, None) == "")
sina("magaza/reklam disi baglayici canli sayilmaz",
     C.degerlendir("mcp__claude_ai_Gmail__create_draft", {}, {"sorulur": True}) == "")

print("\n2. tek kapi uctan uca")
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Canli", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("WEB", "WB")
KB = ofis.kanat_ac("MAGAZA", "MG")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("mert", "lider", kanat_id=KB, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("can", "arayuz", kanat_id=KB, motor="sahte", klasor=str(d))
ga = ofis.tahta.gorev_ac("site", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
ga = ofis.tahta.sahiplen(ga["no"], "ece", ga["revizyon"])
gb = ofis.tahta.gorev_ac("magaza", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KB)
gb = ofis.tahta.sahiplen(gb["no"], "can", gb["revizyon"])


class _Oturum:
    def __init__(self, ajan, no):
        self.ofis, self.ajan_ad, self.gorev_no, self.proje_id = ofis, ajan, no, ofis.proje_id

    def ajan(self):
        return ofis.kadro.ajan(self.ajan_ad)

    def gorev(self):
        return ofis.tahta.gorev(self.gorev_no)

    @property
    def kanat(self):
        return self.gorev().get("kanat_id") or ""


def kapi(ajan, no, arac, girdi):
    return json.loads(M.arac_izin_sor(_Oturum(ajan, no), {"tool_name": arac, "input": girdi}))


def onay_sayisi():
    with db.baglanti() as c:
        return c.execute("SELECT COUNT(*) FROM onay").fetchone()[0]


o0 = onay_sayisi()
r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("'vercel --prod' REDDEDILMEDI, SORULDU (onay karti acildi)",
     r["behavior"] == "deny" and "CANLI KAPALI" not in r["message"] and onay_sayisi() == o0 + 1,
     str(r)[:200])
with db.baglanti() as c:
    sina("  'canli_engel' olayi artik dogmuyor",
         c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'canli_engel'").fetchone()[0] == 0)
IZ.tanimla(db, ofis.proje_id, desen="vercel --prod", veren="insan", kaynak="insan",
           gerekce="sinama: kalici izin")
r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("patronun KALICI izni canliya cikmayi acar", r["behavior"] == "allow", str(r)[:200])
r = kapi("ece", ga["no"], "Bash", {"command": "npm install --production"})
sina("canli olmayan komut etkilenmedi", r["behavior"] == "allow", str(r)[:200])
o1 = onay_sayisi()
r = kapi("can", gb["no"], "mcp__claude_ai_Shopify__update-product", {"id": "1", "title": "x"})
sina("baglanmis magazaya yazma SORULDU (ret degil)",
     r["behavior"] == "deny" and "CANLI KAPALI" not in r.get("message", "") and onay_sayisi() == o1 + 1,
     str(r)[:200])
r = kapi("can", gb["no"], "mcp__claude_ai_Shopify__get-product", {"id": "1"})
sina("  okuma serbest", r["behavior"] == "allow", str(r)[:200])
o2 = onay_sayisi()
r = kapi("ece", ga["no"], "Bash", {"command": "export K=sk_live_51Habc && node odeme.js"})
sina("canli odeme anahtari SORULDU", r["behavior"] == "deny" and onay_sayisi() == o2 + 1, str(r)[:200])
b = C.bulgu("Bash", {"command": "npm publish"}, "paket yayimi")
sina("canli bulgusu yayin sinifi, sorulur", b["sinif"] == "yayin" and b["sorulur"] and "paket" in b["sebep"])

print("\n3. panel: deneme kipi ayari yok")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
org = ist.get("/api/organizasyon").json()
sina("organizasyon 'canli' bayragi vermiyor", all("canli" not in k for k in org["kanatlar"]))
sina("canli modulunde bayrak islevleri yok",
     not any(hasattr(C, a) for a in ("acik_mi", "ayarla", "ret_metni")))
js = (Path(__file__).resolve().parent.parent / "web" / "ayarlar.js").read_text(encoding="utf-8")
sina("ayarlar ekraninda 'deneme kipi' yok", "deneme kipi" not in js and "Canlı kip" not in js)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
