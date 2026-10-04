# -*- coding: utf-8 -*-
"""Antigravity (`gemini` motoru) duman testi -- gercek agy KOSMAZ, sahte program.

Sinanan: komut bayraklari · ajan basina AYRI ev · kanca/MCP/izin dosyalari ·
akisin olaylara cevrilmesi (oturum, arac adi `ofis.kanit_ekle`, metin, izin,
jeton dokumu) · gorselin `.ofis/ekler/`e teslimi · tavanli ve aracsiz turun
reddi · limit isareti · kancanin (`kanca.py --agy`) arac cevirisi ve kararlari.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis.motor import motor_ac, kayitli_motorlar
from ofis.motor.antigravity import AntigravityMotoru
from ofis.motor.tip import MotorHatasi
from ofis import roller
from ofis.kanca import agy_cevir

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


print("== antigravity (gemini) duman testi ==\n")
d = Path(tempfile.mkdtemp(prefix="ofis-agy-"))
ev_koku = d / "ev"
is_k = d / "is"
is_k.mkdir()
gunluk = d / "gunluk.json"
SAHTE = str(KOK / "testler" / "sahte_agy.py")
os.environ["SAHTE_AGY_GUNLUK"] = str(gunluk)
m = AntigravityMotoru(calistirilabilir=[sys.executable, SAHTE], ev_koku=str(ev_koku))
MCP = json.dumps({"mcpServers": {
    "ofis": {"command": "python", "args": ["mcp.py"], "alwaysLoad": True,
             "env": {"OFIS_AJAN": "nova", "OFIS_GOREV": "7", "OFIS_DB": "x.db"}},
    "tarayici": {"command": "npx", "args": ["@playwright/mcp"]}}})


def kos(**ayar):
    return list(m.tur_kos("isi yap", klasor=str(is_k), **ayar))


# --------------------------------------------------------------------------
print("1. KAYIT VE KADEME")
sina("motor adi 'gemini' defterde", "gemini" in kayitli_motorlar())
sina("motor_ac('gemini') Antigravity", isinstance(motor_ac("gemini"), AntigravityMotoru))
sina("bayraklar: mcp + kanca, tavan yok",
     AntigravityMotoru.mcp_konusur and AntigravityMotoru.izin_kancasi
     and not AntigravityMotoru.butce_destegi)
sina("kademe: hizli/standart/guclu gercek model",
     all(roller.KADEME_MODEL["gemini"][k] for k in ("hizli", "standart", "guclu")))

# --------------------------------------------------------------------------
print("\n2. TUR: KOMUT, EV, DOSYALAR, OLAYLAR")
ol = kos(model="gemini-3.8-flash-low", mcp_yapilandirma=MCP, yazabilir=True)
g = json.loads(gunluk.read_text(encoding="utf-8"))
argv = g["argv"]
sina("stream-json + model", "stream-json" in argv and argv[argv.index("--model") + 1] == "gemini-3.8-flash-low")
sina("istem stdin kanalindan (stream-json), -p YOK, sistem eki basta",
     "-p" not in argv and argv[argv.index("--input-format") + 1] == "stream-json"
     and g["mesajlar"] and g["mesajlar"][0].startswith("AgentOfis agent sisteminde"))
sina("tek mesajli tur: kanal kapanir, agy cikar (asili kalmaz)",
     len(g["mesajlar"]) == 1 and ol[-1].ek["cikis"] == 0)
sina("yeni turda --conversation YOK", "--conversation" not in argv)
sina("modelin efor eki varken --effort verilmez", "--effort" not in argv)
ev = ev_koku / "nova"
sina("AJANIN kendi evi (USERPROFILE)", Path(g["USERPROFILE"]) == ev, g["USERPROFILE"])
sina("kimlik surece gecti (MCP sunucusu ve kanca icin)", g["OFIS_AJAN"] == "nova" and g["OFIS_GOREV"] == "7")
h = json.loads((ev / ".gemini" / "config" / "hooks.json").read_text(encoding="utf-8"))
kom = h["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
sina("kanca: PreToolUse -> kanca.py --agy", "kanca.py" in kom and kom.endswith("--agy"))
mc = json.loads((ev / ".gemini" / "config" / "mcp_config.json").read_text(encoding="utf-8"))
sina("MCP: sistemin sunuculari (alwaysLoad ayiklandi)",
     set(mc["mcpServers"]) == {"ofis", "tarayici"} and "alwaysLoad" not in mc["mcpServers"]["ofis"])
st = json.loads((ev / ".gemini" / "antigravity-cli" / "settings.json").read_text(encoding="utf-8"))
sina("izin: komut + her MCP sunucusu kancaya ulasir",
     set(st["permissions"]["allow"]) == {"command(*)", "mcp(ofis/*)", "mcp(tarayici/*)"})
turler = [o.tur for o in ol]
sina("olay sirasi basladi..bitti", turler[0] == "basladi" and turler[-1] == "bitti")
otr = [o for o in ol if o.tur == "oturum"]
sina("oturum kimligi akistan", otr and otr[0].ek["oturum_id"] == "11111111-2222-3333-4444-555555555555")
ar = [o for o in ol if o.tur == "arac"]
sina("MCP araci 'ofis.kanit_ekle' adiyla", ar and ar[0].govde == "ofis.kanit_ekle", str([a.govde for a in ar]))
sina("arac sonucu", any(o.tur == "arac_sonuc" and not o.ek.get("hatali") for o in ol))
sina("reddedilen eylem 'izin' olayi", any(o.tur == "izin" for o in ol))
b = ol[-1]
sina("bitti: basarili, cevap metni", b.ek["basarili"] and b.govde == "Is bitti.")
sina("bitti: jeton ve dokum (dusunme ciktiya katilir, onbellek okuma)",
     b.ek["jeton"] == 165 and b.ek["jeton_dokumu"]["cikti"] == 15
     and b.ek["jeton_dokumu"]["onbellek_okuma"] == 50, str(b.ek.get("jeton_dokumu")))
sina("bitti: dolar OLCULEMEDI (None, sifir degil)", b.ek["maliyet_usd"] is None)
sina("bitti: oturum kimligi", b.ek["oturum_id"].startswith("11111111"))

# --------------------------------------------------------------------------
print("\n3. SURDURME, SALT OKUNUR, EFOR")
kos(model="gemini-3.8-flash", oturum_id="aaaa", yazabilir=False, efor="yuksek", mcp_yapilandirma=MCP)
argv = json.loads(gunluk.read_text(encoding="utf-8"))["argv"]
sina("surdurme --conversation <id>", argv[argv.index("--conversation") + 1] == "aaaa")
sina("salt okunur -> --mode plan", argv[argv.index("--mode") + 1] == "plan")
sina("efor eki olmayan modelde --effort", argv[argv.index("--effort") + 1] == "high")

# --------------------------------------------------------------------------
print("\n4. GORSEL TESLIMI")
os.environ["SAHTE_AGY_SENARYO"] = "gorsel"
ol = kos(mcp_yapilandirma=MCP)
os.environ["SAHTE_AGY_SENARYO"] = "basarili"
b = ol[-1]
sina("evdeki yeni gorsel .ofis/ekler/'e alindi",
     b.ek["uretilen_gorseller"] == [".ofis/ekler/logo_123.jpg"]
     and (is_k / ".ofis" / "ekler" / "logo_123.jpg").exists(), str(b.ek.get("uretilen_gorseller")))
sina("cevaba gorsel yolu eklendi", "URETILEN GORSEL" in b.govde)
ol = kos(mcp_yapilandirma=MCP)
sina("ESKI gorsel ikinci turda tekrar alinmaz", ol[-1].ek["uretilen_gorseller"] == [])

# --------------------------------------------------------------------------
print("\n5. RED VE HATA")
for baslik, ayar in (("tavanli tur reddedilir", {"butce_usd": 0.5}),
                     ("aracsiz tur reddedilir", {"araclar_kapali": True})):
    try:
        kos(**ayar)
        sina(baslik, False)
    except MotorHatasi:
        sina(baslik, True)
os.environ["SAHTE_AGY_SENARYO"] = "hata"
ol = kos(mcp_yapilandirma=MCP)
os.environ["SAHTE_AGY_SENARYO"] = "basarili"
sina("kota hatasi: basarisiz + limit isareti",
     not ol[-1].ek["basarili"] and ol[-1].ek["limit"] and ol[-1].ek["sebep"] == "limit")
yok = AntigravityMotoru(calistirilabilir=str(d / "yok.exe"))
sina("kurulu degilse musait degil + kurulum notu", not yok.musait_mi() and "irm" in yok.durum_notu())

# --------------------------------------------------------------------------
print("\n5b. TUR ICI NOT VE DURDURMA (kanal)")
from ofis.motor.tip import TurKanali                                 # noqa: E402
import time                                                          # noqa: E402
sina("bayrak: tur_ici_mesaj", AntigravityMotoru.tur_ici_mesaj is True)
os.environ["SAHTE_AGY_SENARYO"] = "yavas"
k = TurKanali()
ol = []
for o in m.tur_kos("isi yap", klasor=str(is_k), mcp_yapilandirma=MCP, kanal=k):
    ol.append(o)
    if o.tur == "arac":
        k.gonder("not-1", "EK: z.txt de yaz")
os.environ["SAHTE_AGY_SENARYO"] = "basarili"
g = json.loads(gunluk.read_text(encoding="utf-8"))
sina("not tur surerken AYNI surece gitti", g["mesajlar"][1:] == ["EK: z.txt de yaz"], str(g["mesajlar"]))
ms = [o for o in ol if o.tur == "mesaj"]
sina("ulasan not 'mesaj' olayi (kimlik, tur_ici)",
     len(ms) == 1 and ms[0].ek == {"kimlik": "not-1", "yol": "tur_ici"}, str([o.ek for o in ms]))
sina("not, bitti'den ONCE ulasti", ms and ol.index(ms[0]) < len(ol) - 1)
sina("notlu tur basarili, cevapta notun isi da var",
     ol[-1].ek["basarili"] and "Not uygulandi" in ol[-1].govde, ol[-1].govde)

os.environ["SAHTE_AGY_SENARYO"] = "uzun"
k = TurKanali()
ol = []
t0 = time.monotonic()
for o in m.tur_kos("isi yap", klasor=str(is_k), mcp_yapilandirma=MCP, kanal=k):
    ol.append(o)
    if o.tur == "arac":
        k.durdur()
sure = time.monotonic() - t0
os.environ["SAHTE_AGY_SENARYO"] = "basarili"
b = ol[-1]
sina("durdur: tur KESILDI (60 sn beklemedi)", sure < 20, f"{sure:.1f} sn")
sina("durdur: sebep 'durduruldu', basarisiz, oturum korunur",
     not b.ek["basarili"] and b.ek["sebep"] == "durduruldu" and b.ek["oturum_id"].startswith("11111111"),
     str(b.ek.get("sebep")))
sina("durdur: ariza diye degil, 'durduruldu' hata olayi",
     any(o.tur == "hata" and o.ek.get("sebep") == "durduruldu" for o in ol))

# --------------------------------------------------------------------------
print("\n6. KANCA: ANTIGRAVITY ARAC CEVIRISI")
sina("kendi tarayicisi KAPALI", agy_cevir({"toolCall": {"name": "browser_click_element"}})[0][0] == "ret")
sina("open_browser_url KAPALI", agy_cevir({"toolCall": {"name": "open_browser_url"}})[0][0] == "ret")
sina("generate_image serbest", agy_cevir({"toolCall": {"name": "generate_image"}})[0] == ("izin", ""))
sina("run_command -> kapinin kabuk kurali",
     agy_cevir({"toolCall": {"name": "run_command", "args": {"CommandLine": "rm x"}}})[1]
     == ("Bash", {"command": "rm x"}))
sina("call_mcp_tool -> mcp__sunucu__arac",
     agy_cevir({"toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "ofis", "ToolName": "onay_iste",
                                                                "Arguments": {"a": 1}}}})[1]
     == ("mcp__ofis__onay_iste", {"a": 1}))
sina("write_to_file -> Write", agy_cevir({"toolCall": {"name": "write_to_file",
                                                        "args": {"TargetFile": "a.txt"}}})[1][0] == "Write")
sina("tanimadigi arac kapiya sorulur", agy_cevir({"toolCall": {"name": "yeni_arac"}})[1][0] == "yeni_arac")


def kanca(girdi):
    ortam = {k: v for k, v in os.environ.items() if not k.startswith("OFIS_")}
    p = subprocess.run([sys.executable, str(KOK / "ofis" / "kanca.py"), "--agy"], input=json.dumps(girdi),
                       capture_output=True, text=True, encoding="utf-8", env=ortam, timeout=60)
    return p.returncode, p.stderr


k, e = kanca({"toolCall": {"name": "run_command", "args": {"CommandLine": "Remove-Item sil.txt"}}})
sina("silme: cikis 2 + gerekce stderr'de (kapali kalir)", k == 2 and e.strip(), f"{k} {e[:80]}")
k, e = kanca({"toolCall": {"name": "run_command", "args": {"CommandLine": "echo merhaba"}}})
sina("zararsiz komut: sessiz cikis 0", k == 0 and not e.strip(), f"{k} {e[:80]}")
k, e = kanca({"toolCall": {"name": "browser_click_element"}})
sina("kendi tarayici: cikis 2", k == 2 and "KAPALI" in e)
k, e = kanca({"toolCall": {"name": "generate_image"}})
sina("gorsel: cikis 0", k == 0)
p = subprocess.run([sys.executable, str(KOK / "ofis" / "kanca.py"), "--agy"], input="{bozuk",
                   capture_output=True, text=True, encoding="utf-8", timeout=60)
sina("bozuk girdi COKMEZ", p.returncode in (0, 2))

# --------------------------------------------------------------------------
print("\n7. KAPI KENDINI SINAR (gercek set G03/G05/G11 gemini, 04.10)")
from ofis.motor import antigravity as AG
sina("kanca komutu calisiyor (silme reddedildi)", AG.kanca_sina(AG.kanca_komutu()) == "")
_py = Path(sys.executable).as_posix()
_kc = (KOK / "ofis" / "kanca.py").as_posix()
_bozuk = f'"{_py}" "{_kc}" --agy'                    # cmd'nin bozdugu eski bicim
sina("eski TIRNAKLI bicim kendini sinamada YAKALANIR", AG.kanca_sina(_bozuk) != "",
     AG.kanca_sina(_bozuk)[:80])
_eski = AG.kanca_komutu
AG.kanca_komutu = lambda: "yok_boyle_bir_komut --agy"
try:
    ol = kos(mcp_yapilandirma=MCP)
finally:
    AG.kanca_komutu = _eski
sina("kapi calismiyorsa tur BASLAMAZ (agy hic kosmaz)",
     [o.tur for o in ol] == ["hata", "bitti"] and ol[-1].ek["sebep"] == "kapi", str([o.tur for o in ol]))

print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
