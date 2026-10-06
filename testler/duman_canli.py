# -*- coding: utf-8 -*-
"""DENEME / CANLI AYRIMI (06.10.2026, Asama 4 / K16). Jeton yakmaz.

Takimin canli bayragi KAPALIYKEN (varsayilan) canliya dokunan eylem tek
kapida SORULMADAN reddedilir -- patronun izni bile acmaz; ACIKKEN bugunku
kapi aynen isler. Sinanan: kaliplar (dogru pozitif + yanlis pozitif yok),
betik icindeki canli komut, baglayici yazma/okuma, uctan uca kapi (claude
ve codex ayni `izin_sor`), takim ayrimi, panel ayari.
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


r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("deneme kipinde 'vercel --prod' REDDEDILDI (sorulmadan)",
     r["behavior"] == "deny" and "CANLI KAPALI" in r["message"], str(r)[:200])
with db.baglanti() as c:
    onay = c.execute("SELECT COUNT(*) FROM onay").fetchone()[0]
    eng = c.execute("SELECT COUNT(*) FROM olay WHERE tur = 'canli_engel'").fetchone()[0]
sina("  onay karti ACILMADI, engel kayda gecti", onay == 0 and eng == 1, f"onay={onay} engel={eng}")
IZ.tanimla(db, ofis.proje_id, desen="vercel --prod", veren="insan", kaynak="insan",
           gerekce="sinama: kalici izin")
r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("patronun KALICI izni bile deneme kipini ACMAZ", "CANLI KAPALI" in r.get("message", ""), str(r)[:200])
r = kapi("ece", ga["no"], "Bash", {"command": "npm install --production"})
sina("canli olmayan komut etkilenmedi", r["behavior"] == "allow", str(r)[:200])
r = kapi("can", gb["no"], "mcp__claude_ai_Shopify__update-product", {"id": "1", "title": "x"})
sina("magaza takiminda baglayiciya yazma reddedildi", "CANLI KAPALI" in r.get("message", ""), str(r)[:200])
r = kapi("can", gb["no"], "mcp__claude_ai_Shopify__get-product", {"id": "1"})
sina("  okuma serbest", r["behavior"] == "allow", str(r)[:200])

C.ayarla(db, ofis.proje_id, KA, True)
r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("canli ACIKKEN kipin reddi yok; kalici izinle gecti", r["behavior"] == "allow", str(r)[:200])
r = kapi("can", gb["no"], "mcp__claude_ai_Shopify__update-product", {"id": "1", "title": "x"})
sina("TAKIM AYRI: WEB'in canlisi MAGAZA'yi acmadi", "CANLI KAPALI" in r.get("message", ""))
IZ.kaldir(db, ofis.proje_id, IZ.liste(db, ofis.proje_id)[0]["id"], sebep="sinama")
r = kapi("ece", ga["no"], "Bash", {"command": "vercel --prod"})
sina("canli acik + izinsiz: bugunku kapi SORUYOR (yayin)",
     r["behavior"] == "deny" and "CANLI KAPALI" not in r["message"] and "ONAY" in r["message"].upper(),
     str(r)[:200])

print("\n3. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
r = ist.post(f"/api/kanat/{KB}/duzenle", json={"canli": True})
sina("panelden canli acildi", r.status_code == 200 and C.acik_mi(db, KB))
org = ist.get("/api/organizasyon").json()
sina("organizasyon canli bayragini veriyor",
     all(bool(k["canli"]) for k in org["kanatlar"] if k["id"] in (KA, KB)))
ist.post(f"/api/kanat/{KB}/duzenle", json={"canli": False})
sina("panelden kapatildi", not C.acik_mi(db, KB))
sina("takimsiz/bilinmeyen takim DENEME sayilir", not C.acik_mi(db, "") and not C.acik_mi(db, "yok"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
