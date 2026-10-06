# -*- coding: utf-8 -*-
"""ONAY YORGUNLUGU: "Bu projede hep" ve gunluk sayac (06.10.2026, E80). Jeton yakmaz.

Patron ayni araci / ayni push'u her iste yeniden onayliyordu (gercek
baglayici olcumu: Atria `load_skill` her cagrida "TANINMAYAN ARAC" karti).
Onay kartinin ucuncu kademesi KALICI izin yazar; kural `izin.karttan_izin`.

Sinanan (gercek ofis MCP sureci, `izin_sor`):
 1. kapinin karti `sinif`/`desen` satirlarini tasiyor
 2. taninmayan arac -> "bu projede hep" -> BASKA iste sorulmadan gecer;
    BASKA bir taninmayan arac yine sorulur
 3. push karti -> kalici izin -> baska iste ayni push gecer, --force SORULUR
 4. silme/para karti kalici izne DONUSMEZ, kart bekliyor kalir
 5. cok satirli komut kalici izne donusmez
 6. lider plana arac-adi izni YAZAMAZ (yalniz insan)
 7. izin kaldirilinca yine sorulur
 8. gunluk sayac; panel dugme bilgisini ve sayaci veriyor, `proje` kapsamini kabul ediyor
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, izin  # noqa: E402
from ofis.postane import PostaneHatasi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


_KOK = Path(tempfile.mkdtemp(prefix="ofis-yorgunluk-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Yorgunluk", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
k = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=k, motor="sahte", klasor=str(_KOK))
ofis.kadro.ise_al("isci", "backend", kanat_id=k, motor="sahte", klasor=str(_KOK))
PID = ofis.proje_id
ATRIA = "mcp__claude_ai_Atria__load_skill"
ATRIA2 = "mcp__claude_ai_Atria__transcribe_library_ad"


def is_ac(ad):
    g = ofis.tahta.gorev_ac(ad, neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=[ad.lower() + ".md"], kanat_id=k)
    ofis.tahta.sahiplen(g["no"], "isci", g["revizyon"])
    return ofis.tahta.gorev(g["no"])


def izin_sor(gorev_no, arac, girdi):
    cevre = os.environ.copy()
    cevre.update({"OFIS_DB": str(db_yolu), "OFIS_PROJE": PID,
                  "OFIS_AJAN": "isci", "OFIS_GOREV": str(gorev_no)})
    p = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=cevre,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    istekler = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "izin_sor", "arguments": {"tool_name": arac, "input": girdi}}},
    ]
    cikti, hata = p.communicate("\n".join(json.dumps(x) for x in istekler) + "\n", timeout=60)
    for satir in cikti.splitlines():
        try:
            y = json.loads(satir)
        except ValueError:
            continue
        if y.get("id") == 2:
            return json.loads(y["result"]["content"][0]["text"]).get("behavior")
    return "? " + hata[-300:]


def son_kart():
    b = ofis.postane.bekleyen_onaylar()
    return b[-1] if b else None


g1, g2 = is_ac("Bir"), is_ac("Iki")

print("1. taninmayan arac -> kart -> bu projede hep")
sina("ilk cagri SORULUR", izin_sor(g1["no"], ATRIA, {"name": "ornek"}) == "deny")
kart = son_kart()
ki = izin.karttan_izin(kart)
sina("kart sinif/desen satirlarini tasiyor ve kalici izne donusebilir",
     ki["verilebilir"] and ki["sinif"] == "bilinmiyor" and ki["desen"] == ATRIA, str(ki))
r = ofis.postane.onay_cevapla(kart["id"], onayla=True, kapsam="proje")
sina("kart 'proje' kapsamiyla onaylandi", r["kapsam"] == "proje" and r["durum"] == "onaylandi")
sina("kalici izin yazildi (gorevsiz)", any(i["desen"] == ATRIA and i["gorev_id"] is None
                                         for i in izin.liste(db, PID)))
sina("BASKA iste ayni arac SORULMADAN gecer", izin_sor(g2["no"], ATRIA, {"name": "x"}) == "allow")
sina("BASKA taninmayan arac yine sorulur", izin_sor(g2["no"], ATRIA2, {}) == "deny")
with db.baglanti() as c:
    gecti = c.execute("SELECT COUNT(*) FROM olay WHERE tur='izinle_gecti'").fetchone()[0]
sina("izinle gecis deftere yazildi", gecti >= 1, str(gecti))

print("\n2. push karti -> kalici izin")
sina("push sorulur", izin_sor(g1["no"], "Bash", {"command": "git push origin main"}) == "deny")
kart = son_kart()
sina("push karti kalici izne donusebilir", izin.karttan_izin(kart)["verilebilir"],
     str(izin.karttan_izin(kart)))
ofis.postane.onay_cevapla(kart["id"], onayla=True, kapsam="proje")
sina("baska iste ayni push gecer", izin_sor(g2["no"], "Bash", {"command": "git push origin main"}) == "allow")
sina("--force yine sorulur",
     izin_sor(g2["no"], "Bash", {"command": "git push --force origin main"}) == "deny")
sina("baska dala push yine sorulur (dar izin)",
     izin_sor(g2["no"], "Bash", {"command": "git push origin canli"}) == "deny")

print("\n3. her zaman sorulanlar kalici izne donusmez")
for ad, arac, girdi in (("silme", "Bash", {"command": "rm eski.txt"}),
                        ("para", "mcp__claude_ai_Shopify__create-discount", {"code": "X"})):
    sina(f"{ad} sorulur", izin_sor(g1["no"], arac, girdi) == "deny")
    kart = son_kart()
    ki = izin.karttan_izin(kart)
    sina(f"{ad} karti kalici izne DONUSMEZ", not ki["verilebilir"], str(ki))
    try:
        ofis.postane.onay_cevapla(kart["id"], onayla=True, kapsam="proje")
        sina(f"{ad}: 'proje' kapsami reddedildi", False)
    except PostaneHatasi as exc:
        sina(f"{ad}: 'proje' kapsami reddedildi", "verilemez" in str(exc), str(exc))
    sina(f"{ad} karti hala bekliyor (yarim degisiklik yok)",
         any(o["id"] == kart["id"] for o in ofis.postane.bekleyen_onaylar()))

print("\n4. cok satirli komut")
sina("cok satirli push sorulur",
     izin_sor(g1["no"], "Bash", {"command": "git add .\ngit push origin dev"}) == "deny")
sina("cok satirli komut kalici izne donusmez", not izin.karttan_izin(son_kart())["verilebilir"])

print("\n5. lider plana arac-adi izni yazamaz")
gecerli, ret = izin.plan_izinleri([{"eylem": ATRIA2, "alinti": "load skill"}], "load skill kullan")
sina("plan izni reddedildi", not gecerli and bool(ret), ret[:80])
try:
    izin.tanimla(db, PID, desen=ATRIA2, veren="lider", kaynak="lider", gerekce="x", sinif="bilinmiyor")
    sina("lider kaynak olamaz", False)
except izin.IzinHatasi:
    sina("lider kaynak olamaz", True)

print("\n6. izin kaldirilinca yine sorulur")
iz = next(i for i in izin.liste(db, PID) if i["desen"] == ATRIA)
izin.kaldir(db, PID, iz["id"], sebep="vazgectim")
sina("kaldirilan izinden sonra SORULUR", izin_sor(g2["no"], ATRIA, {"name": "y"}) == "deny")

print("\n7. sayac ve panel")
sy = izin.gun_sayaci(db, PID)
sina("sayac bugunun onaylarini sayiyor", sy["bugun_soruldu"] >= 6, str(sy))
sina("sayac izinle gecenleri sayiyor", sy["bugun_izinle_gecti"] >= 2, str(sy))
sina("sayac kalici izinleri sayiyor (push kaldi)", sy["kalici_izin"] == 1, str(sy))
try:
    from fastapi.testclient import TestClient
    from ofis.panel import olustur
    ist = TestClient(olustur(db_yolu))
    j = ist.get("/api/bekleyenler").json()
    sina("bekleyenler sayaci veriyor", j.get("onay_sayaci", {}).get("bugun_soruldu", 0) >= 6)
    kalici = {o["eylem"][:40]: o["kalici"]["verilebilir"] for o in j["onaylar"]}
    sina("bekleyenler her kartin kalici bilgisini veriyor",
         all("kalici" in o for o in j["onaylar"]) and any(kalici.values()) and not all(kalici.values()),
         str(kalici))
    ac = next(o for o in j["onaylar"] if o["kalici"]["verilebilir"])
    r = ist.post(f"/api/onay/{ac['id']}", json={"onayla": True, "not_": "", "kapsam": "proje"})
    sina("panel 'proje' kapsamini kabul ediyor", r.status_code == 200 and r.json()["kapsam"] == "proje",
         r.text[:150])
    kapali = next(o for o in ist.get("/api/bekleyenler").json()["onaylar"]
                  if not o["kalici"]["verilebilir"])
    r = ist.post(f"/api/onay/{kapali['id']}", json={"onayla": True, "not_": "", "kapsam": "proje"})
    sina("panel kapali karta 'proje' vermiyor (400)", r.status_code == 400, r.text[:150])
    r = ist.post(f"/api/onay/{kapali['id']}", json={"onayla": True, "not_": "", "kapsam": "hep"})
    sina("bilinmeyen kapsam 400", r.status_code == 400)
except ImportError as exc:
    print(f"  [ATLANDI] fastapi yok: {exc}")

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
