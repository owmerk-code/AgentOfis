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


from sahte_tui_motor import SahteTui  # noqa: E402


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
dokum = tui.gecici_klasor()
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
# 'arka' urunde yazilamaz (08.10); sinama deftere ELLE yazar ve kuralin ona uydugunu olcer.
db.ayar_yaz(ofis.proje_id, "terminal_kipi", "arka")
sina("arka kipte sarilmaz", not isinstance(kol._motor_ac("sahte-tui"), tui.TuiMotoru))
db.ayar_yaz(ofis.proje_id, "terminal_kipi", "gercek")
sina("gercek kipte sarilir", isinstance(kol._motor_ac("sahte-tui"), tui.TuiMotoru))
m = kol._motor_ac("sahte")
with db.baglanti() as c:
    uy = c.execute("SELECT COUNT(*) FROM olay WHERE tur='arka_kip' AND govde LIKE "
                   "'%ARKA PLANDA%'").fetchone()[0]
sina("desteklemeyen motor arkada + gorunur not",
     not isinstance(m, tui.TuiMotoru) and uy == 1)
kol._motor_ac("sahte")
with db.baglanti() as c:
    uy2 = c.execute("SELECT COUNT(*) FROM olay WHERE tur='arka_kip'").fetchone()[0]
    sari = c.execute("SELECT COUNT(*) FROM olay WHERE tur='uyari' AND govde LIKE '%terminal%'").fetchone()[0]
sina("  her turda TEKRAR yazilmaz, sari uyari degil (07.10 patron: 'bu uyarilar neden')",
     uy2 == 1 and sari == 0, f"{uy2} {sari}")

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

print("\n-- 11. panel --")
try:
    from fastapi.testclient import TestClient
    from ofis.panel import olustur
    ol, bit = kos("panel icin tur")
    poid = bit.get("oturum_id")
    ist = TestClient(olustur(db_yolu))
    d = ist.get("/api/devralinanlar").json()
    sina("canli ajan terminali listede", any(x["oturum"] == poid for x in d.get("tui", [])),
         str(d.get("tui"))[:200])
    with ist.websocket_connect(f"/ws/tui/{poid}") as ws:
        ilk = ws.receive_json()
        sina("kopru ekrani getirdi", ilk.get("tur") == "veri" and "sahte-cli" in ilk.get("govde", ""))
        ws.send_json({"tur": "girdi", "govde": chr(27) + "[200~PANELDEN YAZILDI" + chr(27) + "[201~" + chr(13)})
        time.sleep(3)
    dk = tui.gecici_klasor() / f"sahte-{poid}.jsonl"
    sina("insanin yazdigi terminale ulasti",
         dk.exists() and "PANELDEN YAZILDI" in dk.read_text(encoding="utf-8"))
    with ist.websocket_connect("/ws/tui/olmayan") as ws:
        sina("olmayan terminal: hata", ws.receive_json().get("tur") == "hata")
    sina("kip okunuyor", ist.get("/api/terminal_kipi").json().get("kip") in ("arka", "gercek"))
    sina("yanlis kip 400", ist.post("/api/terminal_kipi", json={"kip": "uzay"}).status_code == 400)
    # 08.10.2026: arka plan kipi URUNDEN kaldirildi -- panel 'arka' yazamaz.
    _once = db.ayar_oku(ofis.proje_id, "terminal_kipi", "")
    r = ist.post("/api/terminal_kipi", json={"kip": "arka"})
    sina("panel 'arka' kipini REDDEDER (kaldirildi), ayar degismez",
         r.status_code == 400 and "kaldirildi" in r.text
         and db.ayar_oku(ofis.proje_id, "terminal_kipi", "") == _once, r.text[:200])
    r = ist.post("/api/terminal_kipi", json={"kip": "gercek"})
    sina("kip yazildi (gercek)", r.status_code == 200 and
         db.ayar_oku(ofis.proje_id, "terminal_kipi", "") == "gercek")
except ImportError as exc:
    print(f"  [ATLANDI] fastapi yok: {exc}")

print("\n-- 12. claude dokum cevirisi: ayri mesajlar YAPISMAZ --")
from ofis.motor.claude import ClaudeMotoru  # noqa: E402
_d = {}
for _t in ("Once dosyaya bakacagim.", "KARAR: kapat"):
    ClaudeMotoru().tui_cevir({"type": "assistant", "message": {
        "id": _t, "content": [{"type": "text", "text": _t}]}}, _d)
sina("KARAR satir basinda kaliyor", "\nKARAR: kapat" in "".join(_d["metin"]),
     repr("".join(_d["metin"])))

print("\n-- 13. kip kurali (kipe_gore) --")
db.ayar_yaz(ofis.proje_id, "terminal_kipi", "gercek")
sina("tavan gereken tur ARKADA kalir (fable hakemi)",
     not isinstance(tui.kipe_gore(db, ofis.proje_id, SahteTui(), butce_usd=0.5), tui.TuiMotoru))
_m = tui.kipe_gore(db, ofis.proje_id, SahteTui(), ajan_ad="lale")
sina("tavansiz tur gercek terminalde, ajan adi tasiniyor",
     isinstance(_m, tui.TuiMotoru) and _m.ajan_ad == "lale")
_o1 = list(_m.tur_kos("ilk lider turu", klasor=str(_KOK), zaman_asimi=45))[-1].ek.get("oturum_id")
_o2 = list(tui.kipe_gore(db, ofis.proje_id, SahteTui(), ajan_ad="lale").tur_kos(
    "ikinci lider turu", klasor=str(_KOK), zaman_asimi=45))[-1].ek.get("oturum_id")
_acik = [x["oturum_id"] for x in tui.acik_oturumlar() if x["ajan"] == "lale"]
sina("lider her turda TEMIZ terminal, eskisi kapandi (tek terminal kalir)",
     _o1 != _o2 and _acik == [_o2], f"{_o1} {_o2} {_acik}")
# 08.10: liderin ayari yoksa o da GERCEK terminalde (arka plan kipi kaldirildi).
with db.baglanti() as _c:
    _c.execute("DELETE FROM ayar WHERE proje_id = ? AND anahtar = ?",
               (ofis.proje_id, tui.LIDER_KIP_AYARI))
sina("lider turu VARSAYILAN olarak gercek terminalde",
     isinstance(tui.kipe_gore(db, ofis.proje_id, SahteTui(), ajan_ad="lale", lider=True),
                tui.TuiMotoru))
with db.baglanti() as _c:
    _c.execute("DELETE FROM ayar WHERE proje_id = ? AND anahtar = ?",
               (ofis.proje_id, tui.KIP_AYARI))
sina("hic ayar yokken isci de gercek terminalde (kip_oku varsayilani)",
     tui.kip_oku(db, ofis.proje_id) == "gercek" and
     isinstance(tui.kipe_gore(db, ofis.proje_id, SahteTui(), ajan_ad="lale"), tui.TuiMotoru))
db.ayar_yaz(ofis.proje_id, tui.LIDER_KIP_AYARI, "arka")
db.ayar_yaz(ofis.proje_id, "terminal_kipi", "arka")

print("\n-- 14. codex salt okunur: --add-dir YOK --")
from ofis.motor.codex import CodexMotoru  # noqa: E402
_cm = CodexMotoru()
if _cm.tui_ikilisi():
    def _plan(yaz):
        return _cm.tui_plani(oturum_id="", model="", efor="", yazabilir=yaz,
                             ek_klasorler=("C:/ek",), mcp_yapilandirma="",
                             izinli_araclar=(), ek_ortam=None,
                             kanca_komutu=tui.kanca_komutu(), gecici=_KOK)["argv"]
    sina("salt okunur turda --add-dir verilmez (codex terminali kapatiyordu)",
         "--add-dir" not in _plan(False))
    sina("yazabilen turda --add-dir verilir", "--add-dir" in _plan(True))

    print("\n-- 15. codex paralel turlar: oturum dosyasi TUR ISARETIYLE (30.09) --")
    import json as _js  # noqa: E402
    import os as _os  # noqa: E402
    _ev = _KOK / "codex-ev"
    # Ev ACIKCA gecici klasor: gercek codex evine dosya yazilmaz.
    _p = _cm.tui_plani(oturum_id="", model="", efor="", yazabilir=True,
                       ek_klasorler=(), mcp_yapilandirma="", izinli_araclar=(),
                       ek_ortam={"CODEX_HOME": str(_ev)},
                       kanca_komutu=tui.kanca_komutu(), gecici=_KOK)
    sina("sinama gercek codex evine DOKUNMUYOR", Path(_p["ev"]) == _ev, _p["ev"])
    _ses = Path(_p["ev"]) / "sessions" / "2099" / "01" / "01"
    _ses.mkdir(parents=True, exist_ok=True)
    _benim = _ses / "rollout-a-benim.jsonl"
    _baska = _ses / "rollout-b-baska.jsonl"
    _benim.write_text(_js.dumps({"type": "response_item", "payload": {
        "type": "message", "content": [{"text": _p["ilk_on_ek"]}]}}) + "\n", encoding="utf-8")
    time.sleep(0.05)
    _baska.write_text('{"type":"event_msg","payload":{"type":"task_complete"}}\n', encoding="utf-8")
    sina("isaret ilk mesajda", _p["isaret"] in _p["ilk_on_ek"])
    sina("paralel BASKA turun daha yeni dosyasi SECILMEZ; isaretli dosya secilir",
         _p["dokum"]() == _benim, str(_p["dokum"]()))
    _benim.unlink(); _baska.unlink()
else:
    print("  [ATLANDI] codex ikilisi yok")

print("\n-- 15b. gonderilemeyen tur HEMEN duser (30.09, gercek set G01) --")


class _Gitmeyen(SahteTui):
    """Oturum dosyasi hic buyumez: mesaj CLI'a ulasmamis gibi."""

    def tui_plani(self, **k):
        p = super().tui_plani(**k)
        bos = Path(k["gecici"]) / "hic-yazilmayan.jsonl"
        p["dokum"] = lambda: bos
        return p


_t0 = time.monotonic()
_ol = list(tui.TuiMotoru(_Gitmeyen(), ajan_ad="gitmeyen").tur_kos(
    "gitmeyecek brifing", klasor=str(_KOK), zaman_asimi=300))
_son = _ol[-1] if _ol else None
sina("gonderilemeyince tur DUSTU (basarisiz, sebep 'gonderilemedi')",
     _son is not None and _son.tur == "bitti" and not _son.ek.get("basarili")
     and _son.ek.get("sebep") == "gonderilemedi", str(_son and _son.ek))
sina("  ve zaman asimini BEKLEMEDI (< 60 sn)", time.monotonic() - _t0 < 60,
     f"{time.monotonic() - _t0:.0f} sn")
sina("  hata mesaji ekranin sonunu tasiyor",
     any(o.tur == "hata" and "Ekranin sonu" in o.govde for o in _ol))
sina("  terminali acik KALMADI", not [x for x in tui.acik_oturumlar() if x["ajan"] == "gitmeyen"])

print("\n-- 16. guven sorusu EKRANA bakarak (30.09, claude 2.1.285) --")
_s = ("Quick safety check ... ❯No, exit\n Yes, I trust this folder\n"
      "No, exit❯Yes, I trust this folder")
sina("imlec evette (son kare)", tui._imlec_evette_mi(_s, "Yes, I trust"))
sina("imlec hayirda iken evet DENMEZ",
     not tui._imlec_evette_mi(_s + "\n❯No, exit Yes, I trust", "Yes, I trust"))
sina("imlec yoksa evet denmez", not tui._imlec_evette_mi("Yes, I trust", "Yes, I trust"))
# 01.10 OLCULEN ekran (claude 2.1.285, yeni klasor): secenekler NUMARALI.
_olc = ("Quicksafetycheck:Isthisaprojectyoucreatedoroneyoutrust?\n\nSecurityguide\n\n"
        "\u276f1.Yes,Itrustthisfolder\n2.No,exit\n\nEntertoconfirm\u00b7Esctocancel\n>0q")
sina("NUMARALI secenek: imlec 1.Yes uzerinde -> evet", tui._imlec_evette_mi(_olc, "Yes, I trust"))
sina("  NUMARALI: imlec 2.No uzerinde -> evet DEGIL",
     not tui._imlec_evette_mi(_olc.replace("\u276f1.Yes", "1.Yes").replace("2.No", "\u276f2.No"), "Yes, I trust"))
sina("asagi tusu Esc sayilan '\\x1b[B' DEGIL", "\x1b[B" not in tui._ASAGI)
# 01.10 OLCULEN ekran (PATRONUN PANELI, baslat.bat ortami): imlec DUZ ">".
_panel = ("Securityguide\n\n>No,exit\nYes,Itrustthisfolder\n\nEntertoconfirm\u00b7Esctocancel\n>0q"
          " No, exit>Yes, I trust this folder\n\n\n")
sina("DUZ '>' imlec Yes uzerinde -> evet (patronun paneli)", tui._imlec_evette_mi(_panel, "Yes, I trust"))
sina("  DUZ '>' imlec No uzerinde -> evet DEGIL",
     not tui._imlec_evette_mi(_panel + ">No, exit Yes, I trust this folder\n\n\n", "Yes, I trust"))
sina("  secenek olmayan '>' (>0q) imlec SAYILMAZ",
     not tui._imlec_evette_mi("Yes, I trust\n>0q", "Yes, I trust"))


class _SahteT:
    def __init__(self):
        self.yazilan = []

    def yaz(self, x):
        self.yazilan.append(x)

    def gecmis(self):
        return "❯No, exit Yes, I trust"


_st = _SahteT()
sina("evet bulunamazsa Enter BASILMAZ (yanlis secenek onaylanmaz)",
     tui._guven_sec(_st, "Yes, I trust", deneme=2) is False and "\r" not in _st.yazilan,
     str(_st.yazilan))

print("\n-- 16b. CEVAPLANAMAYAN guven sorusu: brifing YAPISTIRILMAZ, tur acik sebeple duser (01.10) --")
_inatci = _KOK / "inatci_guven.py"
_inatci.write_text(
    "import os, sys, time\n"
    f"open(r'{_KOK / 'inatci.pid'}', 'w').write(str(os.getpid()))\n"
    "sys.stdout.write('Quick safety check: do you trust this folder?\\n\\u276fNo, exit\\n  Yes, I trust this folder\\n')\n"
    "sys.stdout.flush()\n"
    "time.sleep(120)\n", encoding="utf-8")


class _Inatci(SahteTui):
    """Guven sorusu gosterir, imlec HIC 'evet'e gelmez (tus dinlemez)."""

    def tui_plani(self, **k):
        p = super().tui_plani(**k)
        p.update(argv=[sys.executable, str(_inatci)], guven_isareti="trust",
                 guven_evet="Yes, I trust", hazir_mi=None)
        return p


_t0 = time.monotonic()
_ol = list(tui.TuiMotoru(_Inatci(), ajan_ad="inatci").tur_kos(
    "yapistirilmamasi gereken brifing", klasor=str(_KOK), zaman_asimi=300))
_son = _ol[-1] if _ol else None
sina("guven sorusu cevaplanamayinca tur DUSTU (sebep 'guven')",
     _son is not None and _son.tur == "bitti" and not _son.ek.get("basarili")
     and _son.ek.get("sebep") == "guven", str(_son and _son.ek))
sina("  hata ACIK: 'guven sorusu CEVAPLANAMADI', ekran ekte",
     any(o.tur == "hata" and "CEVAPLANAMADI" in o.govde and "trust" in o.govde for o in _ol))
sina("  'gonderilmedi' diye YANILTICI sebep yok", not any(o.tur == "hata" and "GONDERILMEDI" in o.govde for o in _ol))
sina("  zaman asimini beklemedi (< 60 sn)", time.monotonic() - _t0 < 60, f"{time.monotonic() - _t0:.0f} sn")
sina("  terminali acik KALMADI", not [x for x in tui.acik_oturumlar() if x["ajan"] == "inatci"])
# Kayittan dusmek yetmez: CLI SURECI de olmeli (01.10: kayit silindi, surec yasadi).
from ofis import surec as _surec
_ipid = int((_KOK / "inatci.pid").read_text())
sina("  CLI SURECI de kapatildi (arkada acik kalmadi)",
     _surec._olusma(_ipid)[1] is False, str(_surec._olusma(_ipid)))

print("\n-- 16c. YAVAS ACILIS: guven sorusu gec gelir, brifing ustune YAPISTIRILMAZ (06.10) --")
# OLCULDU (06.10.2026, patronun ofisinin kopyasi): claude yavas acildi, ekran
# bos durdu, acilis dongusu 4. sn'de "durgun" deyip cikti; guven sorusu SONRA
# geldi, brifing onun ustune yapistirildi ve lider turu "gonderilmedi" diye
# dustu. Sahne: CLI 6 sn hic cizmez, sonra guven sorusu (imlec "No"da), asagi
# okla "Yes"e gecer, Enter'la giris kutusunu cizer ve sahte CLI olarak calisir.
_yavas = _KOK / "yavas_guven.py"
_yavas.write_text(
    "import msvcrt, runpy, sys, time\n"
    "time.sleep(6)\n"
    "def ciz(evet):\n"
    "    sys.stdout.write('\\nQuick safety check: do you trust this folder?\\n' + "
    "('  No, exit\\n\\u276f Yes, I trust this folder\\n' if evet else "
    "'\\u276f No, exit\\n  Yes, I trust this folder\\n'))\n"
    "    sys.stdout.flush()\n"
    "evet = False\n"
    "ciz(evet)\n"
    "while True:\n"
    "    ch = msvcrt.getwch()\n"
    "    if ch in ('\\xe0', '\\x00'):\n"
    "        if msvcrt.getwch() == 'P':\n"
    "            evet = True; ciz(evet)\n"
    "    elif ch == '\\x1b':\n"
    "        a = msvcrt.getwch(); b = msvcrt.getwch()\n"
    "        if a == 'O' and b == 'B':\n"
    "            evet = True; ciz(evet)\n"
    "    elif ch == '\\r':\n"
    "        if evet: break\n"
    "        sys.exit(1)\n"
    "sys.stdout.write('\\n' + '\\u2500' * 30 + '\\n\\u276f \\n'); sys.stdout.flush()\n"
    f"runpy.run_path(r'{Path(__file__).resolve().parent / 'sahte_tui.py'}', run_name='__main__')\n",
    encoding="utf-8")


class _YavasGuven(SahteTui):
    def tui_plani(self, **k):
        p = super().tui_plani(**k)
        p.update(argv=[sys.executable, str(_yavas), p["argv"][2]], guven_isareti="trust",
                 guven_evet="Yes, I trust",
                 hazir_mi=lambda e: "\u276f" in e[-500:] and "\u2500" * 10 in e[-900:])
        return p


_ol = list(tui.TuiMotoru(_YavasGuven(), ajan_ad="yavas").tur_kos(
    "YAVAS_ACILIS brifingi", klasor=str(_KOK), zaman_asimi=120))
_son = _ol[-1] if _ol else None
sina("yavas acilista guven sorusu CEVAPLANDI ve tur BASARILI",
     _son is not None and _son.tur == "bitti" and _son.ek.get("basarili") is True,
     str([(o.tur, o.govde[:80]) for o in _ol if o.tur in ("hata", "bitti")]))
sina("  'gonderilmedi' hatasi YOK", not any(o.tur == "hata" and "GONDERILMEDI" in o.govde for o in _ol))
for _x in tui.acik_oturumlar():
    if _x["ajan"] == "yavas":
        tui.kapat(_x["oturum_id"])

print("\n-- 17. yapistirmanin ardina SAHIP satiri ELLE yazilir (30.09) --")
_st = _SahteT()
tui._yapistir(_st, "plan istemi")
sina("once yapistirma, sonra duz yazilmis sahip satiri, sonra Enter",
     _st.yazilan[0].startswith("\x1b[200~") and _st.yazilan[1].strip() == tui.SAHIP_SATIRI
     and "\x1b[200~" not in _st.yazilan[1] and _st.yazilan[-1] == "\r", str(_st.yazilan)[:200])

for x in tui.acik_oturumlar():
    tui.kapat(x["oturum_id"])
print("\n-- 18. NOT ULASTI MI: motorun KAYDINDAKI kullanici mesaji (08.10) --")
from ofis.motor.claude import ClaudeMotoru as _CM  # noqa: E402
from ofis.motor.codex import CodexMotoru as _XM  # noqa: E402
_ck = _CM.tui_kullanici_metni
sina("claude: SIRAYA alinan (queue-operation enqueue) ulasmis SAYILMAZ",
     _ck({"type": "queue-operation", "operation": "enqueue", "content": "NOT x"}) == "")
sina("claude: arac sinirinda verilen (queued_command) ULASTI",
     "NOT x" in _ck({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "NOT x"}}))
sina("claude: duz kullanici mesaji ve metin parcalari",
     _ck({"type": "user", "message": {"content": [{"type": "text", "text": "NOT y"}]}}) == "NOT y"
     and _ck({"type": "user", "message": {"content": [{"type": "tool_result", "content": "NOT z"}]}}) == "")
_xk = _XM.tui_kullanici_metni
sina("codex: role=user mesaji ULASTI, asistan sayilmaz",
     "NOT q" in _xk({"type": "response_item", "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "NOT q"}]}})
     and _xk({"type": "response_item", "payload": {"type": "message", "role": "assistant",
              "content": [{"type": "output_text", "text": "NOT q"}]}}) == "")
sina("iz bosluklari tekler (yapistirmada satir sonu degisebilir)",
     tui._iz("A  b\r\n c") == "A b c")

print("\n-- ayni ajanin iki turu AYNI ANDA: acilan terminal kapatilmaz (08.10) --")
import threading  # noqa: E402
_paralel = {}


def _ilk_tur():
    _paralel["a"] = kos("YAVAS birinci is")


_th = threading.Thread(target=_ilk_tur)
_th.start()
time.sleep(1.5)                       # birinci tur hala ACILISTA (en az 4 sn)
_paralel["b"] = kos("ikinci is")
_th.join(60)
_ba, _bb = (_paralel.get("a") or ([], {}))[1], (_paralel.get("b") or ([], {}))[1]
sina("acilistaki birinci tur ikincinin acilisinda KAPATILMADI, ikisi de basarili",
     _ba.get("basarili") is True and _bb.get("basarili") is True,
     f"a={str(_ba)[:160]} b={str(_bb)[:120]}")
for _k in list(tui.acik_oturumlar()):
    tui.kapat(_k["oturum_id"])

print("\n-- panelin terminal bileseninin OTOMATIK cevaplari CLI'a gitmez (09.10) --")
from ofis.terminal import insan_girdisi as _ig  # noqa: E402
_ESC = chr(27)
_cevap = (_ESC + "]10;rgb:d7d7/dddd/e6e6" + _ESC + "\\" + _ESC + "]11;rgb:0d0d/0f0f/1313" + chr(7)
          + _ESC + "[?1;2c" + _ESC + "[>0;276;0c" + _ESC + "[12;40R")
sina("renk (OSC 10/11), kimlik (DA1/DA2), imlec raporu dusuruldu (codex'i 'interrupted' ile kesiyordu)",
     _ig(_cevap) == "", repr(_ig(_cevap)))
sina("insanin tuslari aynen gecer (yazi, Enter, Esc, ok, yapistirma)",
     _ig("merhaba\r") == "merhaba\r" and _ig(_ESC) == _ESC and _ig(_ESC + "[A") == _ESC + "[A"
     and _ig(_ESC + "[200~x" + _ESC + "[201~") == _ESC + "[200~x" + _ESC + "[201~")
sina("karisik girdide yalniz cevap ayiklanir", _ig("a" + _ESC + "[?1;2c" + "b") == "ab")
_d = {}
_ol, _bitti = _XM().tui_cevir({"type": "event_msg", "payload": {"type": "turn_aborted",
                                                                "reason": "interrupted"}}, _d) \
    if hasattr(_XM, "tui_cevir") else ([], False)
sina("codex 'turn_aborted' TUR SONUDUR (zaman asimina dek beklenmez), sebebi saklanir",
     _bitti is True and _d.get("kesildi") == "interrupted", str((_bitti, _d)))

print("\n-- gecici dosyalar %TEMP%'te birikmez (08.10) --")
from ofis import yollar as _yol  # noqa: E402
_gk = tui.gecici_klasor()
sina("terminal gecici klasoru OFISIN EVINDE (sinamada gecici ev)",
     Path(_gk).resolve().is_relative_to(_yol.ofis_evi()) and _gk.name == "tui", str(_gk))
_eski = _gk / "kanca-eski.json"
_yeni = _gk / "kanca-yeni.json"
_eski.write_text("{}", encoding="utf-8")
_yeni.write_text("{}", encoding="utf-8")
_t = time.time() - tui.GECICI_OMUR_SN - 60
os.utime(_eski, (_t, _t))
tui.gecici_klasor()
sina("iki gunden eski dosya supuruldu, yenisi (canli terminalin) kaldi",
     not _eski.exists() and _yeni.exists())
from ofis.motor.claude import _supur_eski_limit  # noqa: E402
_lk = Path(tempfile.mkdtemp(prefix="ofis-sup-"))
(_lk / "ofis-limit-eski").mkdir()
(_lk / "ofis-limit-yeni").mkdir()
(_lk / "baska-eski").mkdir()
_t = time.time() - 7200
for _ad in ("ofis-limit-eski", "baska-eski"):
    os.utime(_lk / _ad, (_t, _t))
_sil = _supur_eski_limit(_lk)
sina("olcum ortasinda oldurulen panelin limit artigi sonraki olcumde silinir; "
     "yenisi ve baska klasor kalir",
     _sil == ["ofis-limit-eski"] and (_lk / "ofis-limit-yeni").exists()
     and (_lk / "baska-eski").exists(), str(_sil))
sina("butun terminaller kapandi", not tui.acik_oturumlar())
print(f"\n== {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
