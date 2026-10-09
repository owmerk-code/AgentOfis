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
_ayar = json.loads((ic.ev("ece") / ".gemini" / "antigravity-cli" / "settings.json").read_text(encoding="utf-8"))
sina("agy izin listesinde url(*) (adres sorusu turu kilitliyordu, 09.10 F1)", "read_url(*)" in _ayar["permissions"]["allow"], str(_ayar))
sina("yazabilen tur --mode accept-edits ile acildi (agy dosya duzenlemesini SORMAZ; kapi kancada, 09.10 F1)",
     argv[argv.index("--mode") + 1:argv.index("--mode") + 2] == ["accept-edits"] if "--mode" in argv else False, str(argv))
kapat_hepsi()

print("\n4. gorsel teslimi, kota, durdur, salt okunur")
(is_kl / "urun-foto.jpg").write_bytes(b"\xff\xd8\xff" + b"urun" * 50)   # girdi fotografi
ol, bit, cevap = kos("#GORSEL# uret")
ekler = list((is_kl / ".ofis" / "ekler").glob("*.png"))
sina("alt ajanin gorseli .ofis/ekler'e teslim", len(ekler) == 1, str(ekler))
sina("GIRDI fotografinin kopyasi (media_*) 'uretilen' sayilmadi",
     not list((is_kl / ".ofis" / "ekler").glob("media_*")), str(list((is_kl / ".ofis" / "ekler").glob("*"))))
sina("cevap teslimi soyluyor", "URETILEN GORSEL" in cevap, cevap[-120:])
ol, bit, _ = kos("#KOTA# dolu")
sina("kota sinyali bitti'de", bit.get("limit") is True, str(bit)[:160])
kanal = TurKanali()
kanal.durdur()
ol, bit, _ = kos("#YAVAS# durdurulacak", kanal=kanal)
sina("Durdur: tur 'durduruldu' ile kapandi", bit.get("sebep") == "durduruldu", str(bit)[:160])
kapat_hepsi()
# NOT ULASTI MI (08.10.2026, gercek agy OLCULDU): tur surerken yazilan
# not SIRAYA girer; ofis onu ancak kayitta USER_INPUT olunca "ulasti" sayar
# ve tur bitince gonderilen notun turunu da AYNI turda izler.
kapat_hepsi()
import threading as _th
kanal = TurKanali()
_th.Timer(2.0, lambda: kanal.gonder("n1", "PATRONUN NOTU: kutuyu birebir yap NOT-ISARETI-7")).start()
ol, bit, cevap = kos("#YAVAS# uzun is", kanal=kanal)
_m = [o for o in ol if o.tur == "mesaj"]
sina("siradaki not ulasinca TEK 'mesaj' olayi", len(_m) == 1 and _m[0].ek.get("kimlik") == "n1",
     str([(o.tur, o.govde[:40]) for o in ol if o.tur in ("mesaj", "metin")]))
_trs2 = next(iter((CLI / "brain").glob(f"{bit.get('oturum_id')}/.system_generated/logs/transcript_full.jsonl")), None)
_g2 = [json.loads(s)["content"] for s in _trs2.read_text(encoding="utf-8").splitlines()
       if json.loads(s)["type"] == "USER_INPUT"] if _trs2 else []
sina("  mesaj olayi notun KAYITTA gorunmesinden SONRA (yapistirma aninda degil)",
     any("NOT-ISARETI-7" in g for g in _g2), str(_g2)[-200:])
sina("  notun actigi devam turu ayni turda izlendi (iki cevap)",
     bit.get("basarili") and cevap.count("TAMAM") == 2, cevap[-160:])
kapat_hepsi()
_eski_bek = tui.SIRADAKI_NOT_SN
tui.SIRADAKI_NOT_SN = 2.0
kanal = TurKanali()
_th.Timer(2.0, lambda: kanal.gonder("n2", "PATRONUN NOTU: bu hic ulasmayacak")).start()
ol, bit, _ = kos("#YUT# uzun is", kanal=kanal)
tui.SIRADAKI_NOT_SN = _eski_bek
sina("ULASMAYAN not 'iletildi' SAYILMIYOR (mesaj olayi yok, tur yine bitti)",
     not any(o.tur == "mesaj" for o in ol) and bit.get("basarili"), str(bit)[:160])
kapat_hepsi()
# CLI'IN KENDI SORUSU (08.10.2026 canli: agy "Allow access to this file?"
# sordu, tur KILITLENDI): ofis taniyip REDDEDER, tur biter, olay gorunur.
kapat_hepsi()
ol, bit, _ = kos("#ERISIM# disari bak", zaman_asimi=40)
_secim = (ic.ev("ece") / "sahte_agy_erisim.txt")
sina("agy'nin erisim sorusu REDDET (3) ile kapandi, tur bitti",
     bit.get("basarili") and _secim.is_file() and _secim.read_text(encoding="utf-8") == "3",
     str(bit)[:200])
_trs3 = next(iter((CLI / "brain").glob(f"{bit.get('oturum_id')}/.system_generated/logs/transcript_full.jsonl")), None)
_g3 = [json.loads(s)["content"] for s in _trs3.read_text(encoding="utf-8").splitlines()
       if json.loads(s)["type"] == "USER_INPUT"] if _trs3 else []
sina("  ret turu kesti; ofis DEVAM mesajini yazdi, ajan surdu (asili kalmadi)",
     len(_g3) == 2 and "KALDIGIN YERDEN" in _g3[1], str(_g3)[-200:])
sina("  patrona gorunur olay: yol + 'izin patronun'",
     any(o.tur == "arac_sonuc" and "mcp_sunucu.py" in o.govde and "REDDETTI" in o.govde for o in ol),
     str([o.govde[:90] for o in ol if o.tur == "arac_sonuc"]))
kapat_hepsi()
# OLUSTURMA SORUSU (09.10.2026 F1 canli): agy calisma alanina dosya olustururken
# sordu, tur KILITLENDI. Kapi araci zaten gecirdigi icin ofis ONAYLAR.
ol, bit, _ = kos("#OLUSTUR# rapor yaz", zaman_asimi=40)
_sec4 = ic.ev("ece") / "sahte_agy_olustur.txt"
sina("agy'nin OLUSTURMA sorusu 'Evet' (1) ile kapandi, tur bitti (kilitlenmedi)",
     bit.get("basarili") and _sec4.is_file() and _sec4.read_text(encoding="utf-8") == "1",
     str(bit)[:200])
sina("  gorunur olay: ofis ONAYLADI (kapi zaten gecirmisti), hata sayilmaz",
     any(o.tur == "arac_sonuc" and "ONAYLADI" in o.govde and not o.ek.get("hatali") for o in ol),
     str([o.govde[:90] for o in ol if o.tur == "arac_sonuc"]))
kapat_hepsi()
# YARIDA BIRAKILAN TUR (08.10.2026 canli: fren turu kesti, agy arkada yasadi,
# ikinci terminal acildi): cagiran akisi birakinca CLI durur ve terminal kapanir.
_m = tui.TuiMotoru(ic, ajan_ad="ece")
_ak = _m.tur_kos("#YAVAS# kesilecek", klasor=str(is_kl), model="gemini-3.8-flash-low",
                 zaman_asimi=60, ek_ortam={"OFIS_AJAN": "ece"})
for _o in _ak:
    if _o.tur == "nabiz":     # brifing gitti, tur KOSUYOR
        break
_ak.close()
sina("yarida birakilan tur: ajanin terminali KAPANDI (arkada CLI kalmadi)",
     not [o for o in tui.acik_oturumlar() if o.get("ajan") == "ece"],
     str(tui.acik_oturumlar()))
kapat_hepsi()
ol, bit, _ = kos("salt okunur inceleme", yazabilir=False, ajan="lale")
argv = json.loads((ic.ev("lale") / "sahte_agy_argv.json").read_text(encoding="utf-8"))
sina("salt okunur tur --mode plan ile acildi (accept-edits YOK)", "--mode" in argv and "plan" in argv and "accept-edits" not in argv, str(argv))
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
