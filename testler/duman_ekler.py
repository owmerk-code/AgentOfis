# -*- coding: utf-8 -*-
"""EKLER duman testi -- sohbete dosya/gorsel (29.09.2026), jeton yakmadan.

Sinananlar:
  1. Ad temizleme (Turkce harf, yol parcasi, bos ad).
  2. Kaydet: kokun `ekler/` klasoru, benzersiz ad, boyut siniri, bos dosya
     reddi, `.part` artigi kalmaz, olay yazilir.
  3. Okuma: klasor disi / yol parcali / olmayan ad REDDEDILIR.
  4. Ayiklama: `[ek] ekler/ad` satirlari mesajdan cikar.
  5. Panel: yukle (base64), bozuk veri 400, cok buyuk 400, oku 200/404.
  6. Takim akisi: balonda metin temiz, ekler ayri alan.
  7. Sohbet: lider hedefi yeniden yazsa bile ek yolu ISE tasinir.
  8. Disk olcumu `ekler/`i saymaz; `.gitignore` onu GitHub'a gondermez.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, ekler, takim  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def hata(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except Exception as exc:                     # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


_KOK = Path(tempfile.mkdtemp(prefix="ofis-ekler-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Ekler", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
kn = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("demir", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(_KOK))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(_KOK))

print("\n-- 1. ad temizleme --")
sina("Turkce harf sadelesir", ekler.ad_temizle("Ekran Görüntüsü (1).png") == "Ekran-Goruntusu-1-.png"
     or ekler.ad_temizle("Ekran Görüntüsü (1).png").startswith("Ekran-Goruntusu"),
     ekler.ad_temizle("Ekran Görüntüsü (1).png"))
sina("yol parcasi atilir", ekler.ad_temizle("..\\..\\windows\\x.ini") == "x.ini",
     ekler.ad_temizle("..\\..\\windows\\x.ini"))
sina("bos ad -> 'ek'", ekler.ad_temizle("") == "ek")

print("\n-- 2. kaydet --")
r = ekler.kaydet(ofis, "rapor.pdf", b"%PDF-1 deneme")
sina("kokun ekler/ klasorune yazildi", (_KOK / r["yol"]).is_file() and r["yol"].startswith("ekler/"))
r2 = ekler.kaydet(ofis, "rapor.pdf", b"ikinci")
sina("ayni ad ustune YAZMAZ (benzersiz)", r2["yol"] != r["yol"] and
     (_KOK / r["yol"]).read_bytes() == b"%PDF-1 deneme")
sina("gorsel bayragi", ekler.kaydet(ofis, "a.PNG", b"x")["gorsel"] is True)
sina("bos dosya reddedilir", "Bos" in hata(ekler.kaydet, ofis, "b.txt", b""))
sina("sinirdan buyuk reddedilir",
     "buyuk" in hata(ekler.kaydet, ofis, "c.bin", b"0" * (ekler.AZAMI_BAYT + 1)))
sina(".part artigi yok", not list((_KOK / "ekler").glob("*.part")))
with db.baglanti() as c:
    sina("ek_eklendi olayi", c.execute("SELECT COUNT(*) FROM olay WHERE tur='ek_eklendi'").fetchone()[0] == 3)

print("\n-- 3. okuma kapisi --")
sina("var olan ek okunur", ekler.dosya(ofis, r["ad"]).is_file())
(_KOK / "gizli.txt").write_text("sir", encoding="utf-8")
sina("klasor disi (..) reddedilir", bool(hata(ekler.dosya, ofis, "../gizli.txt")))
sina("yol parcali ad reddedilir", bool(hata(ekler.dosya, ofis, "alt/x.txt")))
sina("olmayan ek reddedilir", bool(hata(ekler.dosya, ofis, "yok.txt")))

print("\n-- 4. ayiklama --")
m, y = ekler.ayikla("buna bak\n[ek] ekler/a.png\n[ek] ekler/b.pdf")
sina("satirlar cikti", m == "buna bak" and y == ["ekler/a.png", "ekler/b.pdf"], f"{m!r} {y}")
sina("sahte ek satiri (yol kacisi) taninmaz",
     ekler.ayikla("[ek] ekler/../gizli.txt")[1] == [])

print("\n-- 5. panel --")
try:
    from fastapi.testclient import TestClient
    from ofis.panel import olustur
    ist = TestClient(olustur(db_yolu))
    yan = ist.post("/api/ek", json={"ad": "ekran.png",
                                    "veri": base64.b64encode(b"\x89PNG deneme").decode()})
    sina("yukleme 200", yan.status_code == 200, yan.text[:120])
    ad = yan.json().get("ad", "")
    sina("okuma 200 ve icerik ayni", ist.get(f"/api/ek/{ad}").content == b"\x89PNG deneme")
    sina("bozuk veri 400", ist.post("/api/ek", json={"ad": "x", "veri": "!!!"}).status_code == 400)
    sina("cok buyuk 400", ist.post("/api/ek", json={
        "ad": "x", "veri": "A" * (ekler.AZAMI_BAYT * 4 // 3 + 100)}).status_code == 400)
    sina("yol kacisi 404", ist.get("/api/ek/..%2Fgizli.txt").status_code == 404)
except ImportError as exc:
    print(f"  [ATLANDI] fastapi yok: {exc}")

print("\n-- 6. takim akisi --")
ofis.postane.soru_sor("insan", "demir", "sayfa bozuk\n[ek] ekler/" + r["ad"], mod="uyandiran")
x = [o for o in takim.akis(ofis) if o["kimden"] == "insan"][-1]
sina("balon metni temiz", x["metin"] == "sayfa bozuk", repr(x["metin"]))
sina("ek ayri alanda", x["ekler"] == ["ekler/" + r["ad"]], str(x["ekler"]))

print("\n-- 7. sohbet: ek ise tasinir --")
KOL = [{"baslik": "Duzelt", "sahip": "cinar", "neden": "hata", "kabul_olcutu": "k",
        "govde": "duzelt", "yazma_alani": ["a.txt"]}]


class Lider(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps({"karar": "dagit", "gerekce": "is",
                                                   "hedef": "Sayfayi duzelt"}) + "\n```"
        elif '"kollar"' in metin:
            self.cevap = "```json\n" + json.dumps({"bol": False, "gerekce": "tek",
                                                   "kollar": KOL}) + "\n```"
        else:
            self.cevap = "tamam"
        return super().tur_kos(metin, **ayar)


s = Sohbet(ofis, motor_fabrikasi=lambda ad, **k: Lider(cevap=""))
list(s.konus("sayfa bozuk, ekrana bak\n[ek] ekler/" + r["ad"], azami_tik=0))
g = ofis.tahta.liste()[-1]
sina("lider hedefi yeniden yazdi ama ek yolu ISE tasindi",
     ("ekler/" + r["ad"]) in (g.get("ana_hedef") or ""), (g.get("ana_hedef") or "")[:200])

print("\n-- 8. olcum ve yedek disi --")
from ofis import degisim  # noqa: E402
sina("disk olcumu ekler/ klasorunu saymaz", "ekler" in degisim.ATLANAN_KLASOR)
kok = Path(__file__).resolve().parent.parent
r = subprocess.run(["git", "check-ignore", "-q", "calisma/ekler/x.png"], cwd=kok)
sina(".gitignore calisma/ekler/'i GitHub'dan dislar", r.returncode == 0)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
