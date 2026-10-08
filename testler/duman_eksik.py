# -*- coding: utf-8 -*-
"""OFIS KENDI EKSIGINI ONERIR (06.10.2026, Asama 4 / K17). Jeton yakmaz.

Sinanan: oneriler OLCULMUS tekrardan dogar (esik alti tek olay oneri
DEGIL, 7 gunden eski sayilmaz), her biri kanit tasir; ret dongusu is
basina, kota payi takim basina; saglik uyarisi oneri olur;
Onayla gelistirici listesine yazar, Gereksiz bir daha getirmez; panel ve
kabuk.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, eksik as E  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


E._saglik_bulgulari = lambda ofis: [
    {"agirlik": "uyari", "baslik": "Modelsiz ajan: ece", "ayrinti": "model yok", "care": "model ver"},
    {"agirlik": "bilgi", "baslik": "bilgi bulgusu", "ayrinti": "", "care": ""}]

d = Path(tempfile.mkdtemp(prefix="ofis-eksik-"))
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Eksik", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("WEB", "WB")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "arayuz", kanat_id=KA, motor="sahte", klasor=str(d))
g = ofis.tahta.gorev_ac("site", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
P = ofis.proje_id
db.olay_yaz(P, "hata", "Siradaki is dustu (#3 sepet): codex app-server 12 sn cevap vermedi")
db.olay_yaz(P, "hata", "Siradaki is dustu (#7 rapor): codex app-server 30 sn cevap vermedi")
db.olay_yaz(P, "hata", "Siradaki is dustu (#9): disk dolu")
for _ in range(3):
    db.olay_yaz(P, "uyari", "Masaustu bildirimi gonderilemedi: erisim reddedildi")
db.olay_yaz(P, "uyari", "tek seferlik uyari")
db.olay_yaz(P, "takildi", "#4 kilit bekliyor")
db.olay_yaz(P, "takildi", "#5 onay bekliyor")
for i in range(3):
    db.olay_yaz(P, "ret", f"#{g['no']} geri gonderildi: olcut {i}", gorev_id=g["id"])
    db.olay_yaz(P, "kota_payi_dolu", f"WEB takiminin kota payi doldu [{KA}:claude:5s:202610061200]")
eski = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
for _ in range(3):
    db.olay_yaz(P, "hata", "ESKI_SEBEP cok eski dusus")
with db.baglanti() as c:
    c.execute("UPDATE olay SET olusturuldu = ? WHERE govde LIKE '%ESKI_SEBEP%'", (eski,))

print("1. olculmus oneriler")
on = E.topla(ofis)
bas = [o["baslik"] for o in on]
tur = {o["tur"] for o in on}
sina("ayni sebepli iki dusus (sayilar farkli) TEK oneri", any("2 kez düşüş" in b for b in bas), str(bas))
sina("  kaniti ornekleriyle", any("app-server" in " ".join(o["ornekler"]) for o in on if o["tur"] == "hata"))
sina("tek seferlik dusus oneri DEGIL", not any("disk dolu" in " ".join(o["ornekler"]) for o in on))
sina("7 gunden eski sayilmadi", not any("ESKI_SEBEP" in " ".join(o["ornekler"]) for o in on))
sina("3 kez ayni uyari oneri; tek uyari degil",
     any("3 kez" in b for b in bas) and not any("tek seferlik" in " ".join(o["ornekler"]) for o in on))
sina("takilan isler oneri", "takildi" in tur)
sina("ret dongusu IS basina", any(f"#{g['no']} işi 3 kez" in b for b in bas), str(bas))
sina("kota payi TAKIM basina", any(b.startswith("WEB ") and "kota payı" in b for b in bas))
sina("saglik UYARISI oneri, bilgi bulgusu degil",
     "Modelsiz ajan: ece" in bas and "bilgi bulgusu" not in bas)

print("\n2. karar")
hedef = next((o for o in on if o["tur"] == "hata"), None) or (on[0] if on else None)
if hedef is None:
    print("  [KALDI] hic oneri yok -- karar sinanamadi")
    sys.exit(1)
E.karar_ver(ofis, hedef["anahtar"], "onayla", notu="codex zaman asimi")
liste = E.liste(P)
sina("Onayla -> gelistirici listesine yazildi", len(liste) == 1 and liste[0]["baslik"] == hedef["baslik"]
     and liste[0]["not"] == "codex zaman asimi", str(liste)[:200])
sina("onaylanan bir daha bekleyende yok", hedef["anahtar"] not in {o["anahtar"] for o in E.topla(ofis)})
ger = next((o for o in E.topla(ofis) if o["tur"] == "uyari"), None) or {"anahtar": "yok", "tur": "uyari"}
try:
    E.karar_ver(ofis, ger["anahtar"], "gereksiz")
except ValueError as exc:
    sina("uyari onerisi kapatildi", False, str(exc))
db.olay_yaz(P, "uyari", "Masaustu bildirimi gonderilemedi: erisim reddedildi")
sina("Gereksiz: yeni tekrar olsa da GELMEZ", ger["anahtar"] not in {o["anahtar"] for o in E.topla(ofis)})
sina("gereksiz listeye YAZILMADI", len(E.liste(P)) == 1)
for kotu in ("evet", ""):
    try:
        E.karar_ver(ofis, ger["anahtar"], kotu)
        sina(f"gecersiz karar reddedildi ({kotu!r})", False)
    except ValueError:
        sina(f"gecersiz karar reddedildi ({kotu!r})", True)

print("\n3. panel ve kabuk")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
po = ist.get("/api/oneriler").json().get("ofis", [])
sina("panel onerileri veriyor", len(po) == len(E.topla(ofis)) and po, str(len(po)))
r = ist.post(f"/api/eksik/{po[0]['anahtar']}", json={"karar": "gereksiz"})
sina("panelden karar", r.status_code == 200 and po[0]["anahtar"] not in
     {o["anahtar"] for o in ist.get("/api/oneriler").json()["ofis"]})
r = ist.post("/api/eksik/yokboyle", json={"karar": "onayla"})
sina("olmayan oneri 400", r.status_code == 400)
import subprocess  # noqa: E402
import os  # noqa: E402
kb = subprocess.run([sys.executable, "-m", "ofis.kabuk", "--db", str(db.yol), "--proje", "Eksik",
                     "eksikler"], capture_output=True, text=True, encoding="utf-8",
                    cwd=str(Path(__file__).resolve().parent.parent), env=dict(os.environ))
sina("kabuk 'eksikler' listeyi veriyor", kb.returncode == 0 and "onaylanmis eksik: 1" in kb.stdout,
     (kb.stdout + kb.stderr)[-300:])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
