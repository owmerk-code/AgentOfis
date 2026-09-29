# -*- coding: utf-8 -*-
"""GERCEK TERMINAL KIPI duman testi -- jeton yakmadan (29.09.2026).

Gercek ConPTY terminalinde SAHTE bir CLI (`testler/sahte_tui.py`) kosar;
genel dongu (`ofis/motor/tui.py`) gercek CLI'la ayni yoldan gecer:
terminal acilir, brifing yapistirilir, oturum dosyasi okunur.
Gercek claude/codex ile uctan uca olcum ayrica yapildi (GUNLUK).

Sinananlar:
  1. Kapi kendini sinayamazsa tur BASLAMAZ (kapali kalir).
  2. Normal tur: metin/arac olaylari, bitti basarili, kip=terminal,
     maliyet OLCULEMEDI (None, sifir degil).
  3. Ikinci tur AYNI terminale yazilir (surec ayni).
  4. Tur surerken not terminale gider, `mesaj` olayi yayilir.
  5. Durdur: tur kesilir, sebep 'durduruldu'.
  6. Zaman asimi: sebep 'zaman_asimi', ekranin sonu soylenir.
  7. Ilk Enter yutulursa Enter tekrarlanir (codex davranisi).
  8. Dolar tavani istenirse REDDEDILIR.
  9. Koltuk: ayar 'gercek' ise sarar, 'arka' ise sarmaz, desteklemeyen
     motor gorunur uyariyla arkada kalir.
 10. Codex kancasi: izin = HIC cikti (codex `allow` tanimiyor).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani  # noqa: E402
from ofis.motor import tui  # noqa: E402
from ofis.motor.tip import Motor, MotorHatasi, MotorOlayi, TurKanali  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.mcp_sunucu import yapilandirma  # noqa: E402

GECEN = 0
KALAN = 0
SAHTE_CLI = str(Path(__file__).resolve().parent / "sahte_tui.py")


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


class SahteTui(Motor):
    ad = "sahte-tui"
    mcp_konusur = True
    tui_destegi = True

    def musait_mi(self):
        return True

    def tur_kos(self, metin, **k):          # arka plan kipi kullanilmaz
        yield MotorOlayi("bitti", "", {"basarili": True})

    def tui_plani(self, *, oturum_id, gecici, **k):
        oid = oturum_id or str(uuid.uuid4())
        dokum = Path(gecici) / f"sahte-{oid}.jsonl"
        return {"argv": [sys.executable, SAHTE_CLI, str(dokum)],
                "ortam": dict(os.environ), "kapat": "/exit", "oturum_id": oid,
                "dokum": lambda: dokum, "guven": (), "guven_isareti": "",
                "durdur": "\x1b"}

    def tui_cevir(self, k, durum):
        t = k.get("tur")
        if t == "metin":
            durum.setdefault("metin", []).append(k["metin"])
            return [MotorOlayi("metin", k["metin"])], False
        if t == "arac":
            durum["arac_sayisi"] = durum.get("arac_sayisi", 0) + 1
            durum.setdefault("kullanim", {})[str(len(durum.get("kullanim", {})))] = 10
            return [MotorOlayi("arac", k["ad"], {"ozet": k["ozet"]})], False
        if t == "girdi":
            durum.setdefault("girdiler", []).append(k["metin"])
        return [], t == "bitti"


_KOK = Path(tempfile.mkdtemp(prefix="ofis-tui-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Tui", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
MCP = yapilandirma(str(db_yolu), ofis.proje_id, "isci", 1)
M = tui.TuiMotoru(SahteTui())


def kos(metin, **k):
    k.setdefault("klasor", str(_KOK))
    k.setdefault("mcp_yapilandirma", MCP)
    k.setdefault("zaman_asimi", 45)
    olaylar = list(M.tur_kos(metin, **k))
    return olaylar, olaylar[-1].ek if olaylar else {}


print("\n-- 1. kapi sinanamazsa tur baslamaz --")
_asil = tui.KANCA
tui.KANCA = _KOK / "yok_boyle_kanca.py"
ol, bit = kos("merhaba")
tui.KANCA = _asil
sina("sebep kapi, basarisiz", bit.get("sebep") == "kapi" and bit.get("basarili") is False,
     str(bit))
sina("terminal ACILMADI", not tui.acik_oturumlar())

print("\n-- 2. normal tur --")
ol, bit = kos("GOREV:\nsatir iki\nsatir uc")
turler = [o.tur for o in ol]
sina("basarili", bit.get("basarili") is True, str(bit)[:200])
sina("metin ve arac olayi akti", "metin" in turler and "arac" in turler, str(turler))
sina("kip=terminal", bit.get("kip") == "terminal")
sina("maliyet OLCULEMEDI (None)", bit.get("maliyet_usd") is None)
sina("jeton sayildi", bit.get("jeton") == 10, str(bit.get("jeton")))
oid = bit.get("oturum_id")
t1 = tui.oturum_terminali(oid)
sina("terminal tur sonunda ACIK kaldi", t1 is not None and t1.canli())

print("\n-- 3. ikinci tur ayni terminalde --")
ol, bit = kos("devam et", oturum_id=oid)
sina("ikinci tur basarili", bit.get("basarili") is True)
sina("AYNI terminal (yeni surec acilmadi)", tui.oturum_terminali(oid) is t1)
sina("basladi olayi YOK (terminal zaten acikti)", "basladi" not in [o.tur for o in ol])

print("\n-- 4. tur surerken not --")
kanal = TurKanali()
kanal.gonder("n1", "NOT: dosya adini degistir")
ol, bit = kos("YAVAS is", oturum_id=oid, kanal=kanal)
mesajlar = [o for o in ol if o.tur == "mesaj"]
sina("mesaj olayi (kimlikli)", bool(mesajlar) and mesajlar[0].ek.get("kimlik") == "n1")
dokum = Path(tempfile.gettempdir()) / "agentofis-tui"
satirlar = []
for f in dokum.glob(f"sahte-{oid}.jsonl"):
    satirlar = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()]
sina("not CLI'a ulasti", any("dosya adini" in (s.get("metin") or "") for s in satirlar
                             if s.get("tur") == "girdi"))

print("\n-- 5. durdur --")
kanal = TurKanali()
kanal.durdur()
ol, bit = kos("YAVAS durdurulacak", oturum_id=oid, kanal=kanal)
sina("durduruldu", bit.get("sebep") == "durduruldu", str(bit)[:160])
kesildi = []
for f in dokum.glob(f"sahte-{oid}.jsonl"):
    kesildi = [x for x in f.read_text(encoding="utf-8").splitlines() if '"kesildi"' in x]
sina("CLI gercekten KESILDI (Esc ulasti)", bool(kesildi))

print("\n-- 6. zaman asimi --")
ol, bit = kos("ASKIDA", zaman_asimi=5)
sina("sebep zaman_asimi", bit.get("sebep") == "zaman_asimi", str(bit)[:160])
hata = [o.govde for o in ol if o.tur == "hata"]
sina("ekranin sonu soyleniyor", bool(hata) and "Ekranin sonu" in hata[-1])
tui.kapat(bit.get("oturum_id") or "")

print("\n-- 7. ilk Enter yutulursa tekrar --")
ol, bit = kos("YUTENTER uzun yapistirma")
sina("yine gonderildi ve bitti", bit.get("basarili") is True, str(bit)[:160])
sina("gonderilemedi hatasi YOK",
     not [o for o in ol if o.tur == "hata" and "GONDERILMEDI" in o.govde])
tui.kapat(bit.get("oturum_id") or "")

print("\n-- 8. dolar tavani reddedilir --")
try:
    kos("x", butce_usd=0.5)
    sina("tavan reddedildi", False)
except MotorHatasi:
    sina("tavan reddedildi", True)

print("\n-- 9. koltuk kipi --")
from ofis.koltuk import Koltuk  # noqa: E402
kol = Koltuk(ofis, motor_fabrikasi=lambda ad, **k: SahteTui() if ad == "sahte-tui"
             else SahteMotor(cevap="x"))
sina("arka kipte sarilmaz", not isinstance(kol._motor_ac("sahte-tui"), tui.TuiMotoru))
db.ayar_yaz(ofis.proje_id, "terminal_kipi", "gercek")
sina("gercek kipte sarilir", isinstance(kol._motor_ac("sahte-tui"), tui.TuiMotoru))
m = kol._motor_ac("sahte")
with db.baglanti() as c:
    uy = c.execute("SELECT COUNT(*) FROM olay WHERE tur='uyari' AND govde LIKE "
                   "'%gercek terminal kipini desteklemiyor%'").fetchone()[0]
sina("desteklemeyen motor arkada + gorunur uyari",
     not isinstance(m, tui.TuiMotoru) and uy == 1)

print("\n-- 10. codex kancasi --")
cevre = {a: v for a, v in os.environ.items() if not a.startswith("OFIS_") or a == "OFIS_EV"}
cevre["PYTHONIOENCODING"] = "utf-8"
r = subprocess.run([sys.executable, str(tui.KANCA), "--codex"],
                   input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": "a"}}),
                   capture_output=True, text=True, encoding="utf-8", env=cevre, timeout=60)
sina("izin -> bos cikti", r.stdout.strip() == "", repr(r.stdout[:120]))
r = subprocess.run([sys.executable, str(tui.KANCA), "--codex"],
                   input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm x"}}),
                   capture_output=True, text=True, encoding="utf-8", env=cevre, timeout=60)
sina("ret -> deny JSON", '"deny"' in r.stdout)

for x in tui.acik_oturumlar():
    tui.kapat(x["oturum_id"])
sina("butun terminaller kapandi", not tui.acik_oturumlar())
print(f"\n== {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
