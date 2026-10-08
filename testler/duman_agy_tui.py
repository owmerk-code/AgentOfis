# -*- coding: utf-8 -*-
"""ANTIGRAVITY (agy) GERCEK TERMINAL KIPI (08.10.2026). Jeton yakmaz.

Sahte agy (`sahte_agy_tui.py`) gercek agy 1.3.1'in etkilesimli kipinde
OLCULEN dosyalari ayni bicimde yazar. Sinanan: kurulum isareti patronun kendi
agy'sinden gelir (yoksa terminal ACILMAZ, sebep soylenir); klasor guveni;
sistem eki yalniz yeni konusmanin ilk mesajinda; arac olaylari, sonuclari ve
jeton adim dosyasindan; konusma kimligi `last_conversations`tan; ayni
terminalde ikinci tur; kapanip `--conversation` ile devam; gorsel teslimi;
kota sinyali; Durdur (Esc); salt okunur tur `--mode plan`; kip kurali agy'yi
artik gercek terminale alir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Veritabani  # noqa: E402
from ofis.motor import MotorHatasi  # noqa: E402
from ofis.motor.antigravity import AntigravityMotoru, SISTEM_EKI  # noqa: E402
from ofis.motor.tip import TurKanali  # noqa: E402
from ofis.motor import tui  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


SAHTE = Path(__file__).resolve().with_name("sahte_agy_tui.py")
d = Path(tempfile.mkdtemp(prefix="ofis-agytui-"))
kaynak = d / "patron"
(kaynak / ".gemini" / "antigravity-cli" / "cache").mkdir(parents=True)
(kaynak / ".gemini" / "antigravity-cli" / "cache" / "onboarding.json").write_text(json.dumps(
    {"consumerOnboardingComplete": True, "enterpriseOnboardingComplete": False, "onboardingComplete": True}))
os.environ["OFIS_AGY_KAYNAK_EV"] = str(kaynak)
for k in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV"):
    os.environ.pop(k, None)
is_kl = d / "is"
is_kl.mkdir()
ic = AntigravityMotoru(calistirilabilir=[sys.executable, str(SAHTE)], ev_koku=str(d / "evler"))
EV = ic.ev("ece")
CLI = EV / ".gemini" / "antigravity-cli"


def kos(metin, *, oturum_id="", yazabilir=True, kanal=None, ajan="ece", zaman_asimi=60):
    m = tui.TuiMotoru(ic, ajan_ad=ajan)
    ol = list(m.tur_kos(metin, klasor=str(is_kl), oturum_id=oturum_id, model="gemini-3.8-flash-low",
                        yazabilir=yazabilir, kanal=kanal, zaman_asimi=zaman_asimi,
                        ek_ortam={"OFIS_AJAN": ajan}))
    return ol, (ol[-1].ek if ol and ol[-1].tur == "bitti" else {}), (ol[-1].govde if ol else "")


def kapat_hepsi():
    for o in tui.acik_oturumlar():
        tui.kapat(o["oturum_id"])


print("1. kip kurali")
db = Veritabani(d / "o.sqlite3")
sina("agy artik gercek terminal destekliyor (bayrak)", AntigravityMotoru.tui_destegi is True)
sina("kip kurali agy'yi gercek terminale aliyor",
     isinstance(tui.kipe_gore(db, "p", ic, ajan_ad="ece"), tui.TuiMotoru))

print("\n2. arac kullanan tur")
ol, bit, cevap = kos("#ARAC# isi yap")
araclar = [o.govde for o in ol if o.tur == "arac"]
sonuclar = [(o.ek.get("arac"), o.ek.get("hatali")) for o in ol if o.tur == "arac_sonuc"]
sina("tur basarili", bit.get("basarili") is True, str(bit)[:200])
sina("arac olaylari sirayla (yazma, komut)", araclar == ["write_to_file", "run_command"], str(araclar))
sina("sonuclar araca eslesti; kancada duran komut HATALI",
     sonuclar == [("write_to_file", False), ("run_command", True)], str(sonuclar))
sina("cevap modelin sozu", cevap.startswith("TAMAM"), cevap)
sina("jeton adim dosyasindan (1000+20 + 1100+15 + 1200+8)", bit.get("jeton") == 3343, str(bit.get("jeton")))
sina("arac sayisi 2", bit.get("arac_sayisi") == 2)
oid = bit.get("oturum_id") or ""
kayitli = json.loads((CLI / "cache" / "last_conversations.json").read_text(encoding="utf-8"))
sina("oturum kimligi agy'nin kendi kaydindan", oid and oid in kayitli.values(), f"{oid} {kayitli}")
trs = CLI / "brain" / oid / ".system_generated" / "logs" / "transcript_full.jsonl"
ilk = json.loads(trs.read_text(encoding="utf-8").splitlines()[0])["content"] if trs.exists() else ""
sina("sistem eki YENI konusmanin ilk mesajinda", ilk.startswith(SISTEM_EKI[:40]), ilk[:80])
ayar = json.loads((CLI / "settings.json").read_text(encoding="utf-8"))
sina("calisma klasoru guvenilen listede",
     os.path.normcase(str(is_kl.resolve())) in [os.path.normcase(x) for x in ayar.get("trustedWorkspaces", [])],
     str(ayar))
sina("kancanin izni aynen (command(*))", "command(*)" in ayar["permissions"]["allow"])
kurulum = json.loads((CLI / "cache" / "onboarding.json").read_text(encoding="utf-8"))
sina("kurulum isareti patronun agy'sinden kopyalandi", kurulum.get("onboardingComplete") is True)

print("\n3. ayni terminalde ikinci tur; kapanip devam")
ol, bit2, cevap2 = kos("ikinci soru", oturum_id=oid)
sina("ikinci tur ayni oturumda", bit2.get("basarili") and bit2.get("oturum_id") == oid, str(bit2)[:160])
satirlar = trs.read_text(encoding="utf-8").splitlines()
girdiler = [json.loads(s)["content"] for s in satirlar if json.loads(s)["type"] == "USER_INPUT"]
sina("sistem eki ikinci mesaja EKLENMEDI", len(girdiler) == 2 and not girdiler[1].startswith(SISTEM_EKI[:40]),
     str(girdiler)[:200])
kapat_hepsi()
ol, bit3, _ = kos("ucuncu soru", oturum_id=oid)
argv = json.loads((EV / "sahte_agy_argv.json").read_text(encoding="utf-8"))
sina("kapanan terminal --conversation ile KALDIGI konusmadan acildi",
     "--conversation" in argv and oid in argv and bit3.get("oturum_id") == oid, str(argv))
sina("model bayrakla verildi", "--model" in argv and "gemini-3.8-flash-low" in argv)
kapat_hepsi()

print("\n4. gorsel teslimi, kota, durdur, salt okunur")
ol, bit, cevap = kos("#GORSEL# uret")
ekler = list((is_kl / ".ofis" / "ekler").glob("*.png"))
sina("alt ajanin gorseli .ofis/ekler'e teslim", len(ekler) == 1, str(ekler))
sina("cevap teslimi soyluyor", "URETILEN GORSEL" in cevap, cevap[-120:])
ol, bit, _ = kos("#KOTA# dolu")
sina("kota sinyali bitti'de", bit.get("limit") is True, str(bit)[:160])
kanal = TurKanali()
kanal.durdur()
ol, bit, _ = kos("#YAVAS# durdurulacak", kanal=kanal)
sina("Durdur: tur 'durduruldu' ile kapandi", bit.get("sebep") == "durduruldu", str(bit)[:160])
kapat_hepsi()
ol, bit, _ = kos("salt okunur inceleme", yazabilir=False, ajan="lale")
argv = json.loads((ic.ev("lale") / "sahte_agy_argv.json").read_text(encoding="utf-8"))
sina("salt okunur tur --mode plan ile acildi", "--mode" in argv and "plan" in argv, str(argv))
kapat_hepsi()

print("\n5. patronun agy kurulumu yoksa terminal ACILMAZ")
bos = d / "kurulumsuz"
bos.mkdir()
os.environ["OFIS_AGY_KAYNAK_EV"] = str(bos)
try:
    kos("merhaba", ajan="yeni-ajan")
    sina("kurulumsuz: terminal acilmadi, sebep soylendi", False, "acildi")
except MotorHatasi as exc:
    sina("kurulumsuz: terminal acilmadi, sebep soylendi", "kurulum" in str(exc), str(exc))
sina("  kurulum isareti UYDURULMADI",
     not (ic.ev("yeni-ajan") / ".gemini" / "antigravity-cli" / "cache" / "onboarding.json").exists())
kapat_hepsi()

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
