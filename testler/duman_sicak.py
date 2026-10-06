# -*- coding: utf-8 -*-
"""Sicak bekleyen surec duman testi (05.10.2026) -- gercek motor KOSMAZ.

Olculen sorun: liderin turu ~7 sn'sini MODELDEN ONCE eklenti ve baglayici
yuklemeye harciyordu. Cozum: ayni komutla bir sonraki sureci ONCEDEN baslatip
bekletmek. Sinanan: ilk tur soguk + sicak hazirlar · ikinci tur bekleyeni
KULLANIR (yeni surec acmaz, sicagin oturum kimligiyle kosar) · komut degisirse
(model) bekleyen KULLANILMAZ · bayat (omur doldu) surec kapatilir ve
kullanilmaz · `sicak` verilmeyen tur hazirlamaz · devam (oturumlu) tur sicak
kullanmaz · `sicaklari_kapat` hepsini kapatir · sicak tur istemi json kanalindan
yollar ve cevap tam gelir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ofis.motor.claude as CL

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


# Sahte CLI: argumani ve pid'ini kaydeder; json kipinde ILK mesaji BEKLER
# (gercek CLI gibi), cevaplar, stdin kapaninca cikar. Duz metin kipinde stdin'i okur.
SAHTE = r'''
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
kayit = os.path.join(os.path.dirname(__file__), "kayit.jsonl")
argv = sys.argv[1:]
import subprocess as _sp
_yan = _sp.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                 creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
with open(kayit, "a", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid(), "argv": argv, "yan": _yan.pid}) + "\n")
def yaz(m):
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n"); sys.stdout.flush()
oturum = argv[argv.index("--session-id") + 1] if "--session-id" in argv else ""
json_kip = "stream-json" in argv[argv.index("--input-format") + 1: argv.index("--input-format") + 2]
if json_kip:
    satir = sys.stdin.readline()
    if not satir:
        sys.exit(0)
    istem = json.loads(satir)["message"]["content"][0]["text"]
else:
    istem = sys.stdin.read()
yaz({"type": "system", "subtype": "init", "session_id": oturum, "model": "sahte"})
_c = "CEVAP:" + istem[:20] + ":" + str(os.getpid())
yaz({"type": "stream_event", "event": {"type": "content_block_delta",
     "delta": {"type": "text_delta", "text": _c}}})
yaz({"type": "assistant", "message": {"content": [{"type": "text", "text": _c}]}})
yaz({"type": "result", "subtype": "success", "is_error": False, "session_id": oturum,
     "result": "CEVAP:" + istem[:20] + ":" + str(os.getpid()), "total_cost_usd": 0.0,
     "usage": {"input_tokens": 1, "output_tokens": 1}})
if json_kip:
    for _ in iter(sys.stdin.readline, ""):
        pass
'''
skl = Path(tempfile.mkdtemp(prefix="ofis-sicak-"))
(skl / "sahte_claude.py").write_text(SAHTE, encoding="utf-8")
kayit = skl / "kayit.jsonl"
calisma = Path(tempfile.mkdtemp(prefix="ofis-sicakcalisma-"))
_gercek = subprocess.Popen


def _sahte_popen(komut, **kw):
    return _gercek([sys.executable, str(skl / "sahte_claude.py"), *komut[1:]], **kw)


CL.subprocess.Popen = _sahte_popen
m = CL.ClaudeMotoru(calistirilabilir="claude", zaman_asimi=30)


def kos(**ek):
    olaylar = list(m.tur_kos("merhaba lider", klasor=str(calisma), model=ek.pop("model", "sonnet"),
                             yazabilir=False, **ek))
    return olaylar, olaylar[-1]


def surec_sayisi():
    return len(kayit.read_text(encoding="utf-8").splitlines()) if kayit.exists() else 0


print("== sicak bekleyen surec duman testi ==\n")
sina("ClaudeMotoru sicak destekliyor", getattr(CL.ClaudeMotoru, "sicak_destegi", False))

ol, b = kos(sicak=True)
time.sleep(0.5)
sina("ilk tur SOGUK kostu ve basarili", b.ek["basarili"] and "CEVAP:merhaba" in b.govde, b.govde)
sina("ilk tur bir sonraki icin SICAK surec hazirladi", surec_sayisi() == 2 and len(CL._SICAK) == 1,
     f"{surec_sayisi()} surec, havuz {len(CL._SICAK)}")
sicak_oturum = next(iter(CL._SICAK.values()))["oturum"]
sicak_pid = next(iter(CL._SICAK.values()))["surec"].pid

ol, b = kos(sicak=True)
time.sleep(0.5)
sina("ikinci tur BEKLEYENI kullandi (cevap o surecten)", b.ek["basarili"] and str(sicak_pid) in b.govde,
     f"{b.govde} / beklenen pid {sicak_pid}")
sina("ikinci tur sicagin OTURUM kimligiyle kostu", b.ek["oturum_id"] == sicak_oturum,
     f"{b.ek['oturum_id']} != {sicak_oturum}")
sina("ikinci turda yalniz YENI sicak acildi (soguk acilmadi)", surec_sayisi() == 3, str(surec_sayisi()))
_ilk_argv = json.loads(kayit.read_text(encoding="utf-8").splitlines()[1])["argv"]
sina("sicak surec istemi json kanalindan bekliyor (stream-json)",
     _ilk_argv[_ilk_argv.index("--input-format") + 1] == "stream-json")

once = surec_sayisi()
ol, b = kos(sicak=True, model="opus")
time.sleep(0.5)
sina("model DEGISINCE bekleyen kullanilmadi (soguk + yeni sicak)",
     b.ek["basarili"] and surec_sayisi() == once + 2, f"{surec_sayisi() - once}")

CL.SICAK_OMUR_SN = 0
once = surec_sayisi()
eski = [k["surec"] for k in CL._SICAK.values()]
ol, b = kos(sicak=True, model="opus")
time.sleep(0.5)
sina("BAYAT sicak kullanilmadi ve kapatildi",
     surec_sayisi() == once + 2 and all(s.poll() is not None for s in eski[-1:]),
     f"{surec_sayisi() - once}")
CL.SICAK_OMUR_SN = 600

once, havuz = surec_sayisi(), len(CL._SICAK)
ol, b = kos()
sina("`sicak` verilmeyen tur hazirlamaz", surec_sayisi() == once + 1 and len(CL._SICAK) == havuz)
once = surec_sayisi()
ol, b = kos(sicak=True, oturum_id="11111111-2222-3333-4444-555555555555")
time.sleep(0.5)
sina("DEVAM eden (oturumlu) tur sicak kullanmaz ve hazirlamaz", surec_sayisi() == once + 1)

kalan = [k["surec"] for k in CL._SICAK.values()]
_kalan_pid = {k["surec"].pid for k in CL._SICAK.values()}
_yanlar = [json.loads(x)["yan"] for x in kayit.read_text(encoding="utf-8").splitlines()
           if json.loads(x)["pid"] in _kalan_pid]


def _yasiyor(pid: int) -> bool:
    """Windows: surec hala kosuyor mu (cikis kodu STILL_ACTIVE=259)."""
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x1000, False, int(pid))      # QUERY_LIMITED_INFORMATION
    if not h:
        return False
    kod = ctypes.c_ulong()
    k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(kod))
    k32.CloseHandle(ctypes.c_void_p(h))
    return kod.value == 259


sina("bekleyen surecin YAN sureci kapatmadan once yasiyor",
     bool(_yanlar) and all(_yasiyor(p) for p in _yanlar), str(_yanlar))
n = CL.sicaklari_kapat()
time.sleep(0.3)
sina("sicaklari_kapat hepsini kapatti", n == len(kalan) and n > 0
     and all(s.poll() is not None for s in kalan) and not CL._SICAK, f"{n}")
time.sleep(0.5)
sina("bekleyenin YAN SURECLERI de kapandi (yetim kalmadi -- kafes dogumda)",
     _yanlar and not any(_yasiyor(p) for p in _yanlar), str([p for p in _yanlar if _yasiyor(p)]))

print("\n2. PANELIN ONCEDEN ISITMASI = LIDERIN GERCEK TURU (ayni anahtar)")
from ofis import Ofis, Veritabani
_d = Path(tempfile.mkdtemp(prefix="ofis-sicakofis-"))
_db = Veritabani(_d / "o.sqlite3")
_o = Ofis.proje_ac(_db, "Sicak", amac="s", basari_olcutu="s")
_k = _o.kanat_ac("GENEL", "GE")
_kok = _d / "kok"; _kok.mkdir()
_o.kadro.ise_al("arda", "lider", lider_mi=True, kanat_id=_k, klasor=str(_kok),
                motor="claude", model="opus")
_lider = _o.kadro.ajan("arda")
import ofis.motor as _M
_asil_ac = _M.motor_ac
class _KuruluClaude(CL.ClaudeMotoru):
    # Sahte CLI'da "kurulu mu" denetimi gercek programi arar; sinama onu atlar.
    def musait_mi(self):
        return True


_o.orkestra.motor_fabrikasi = lambda ad: _KuruluClaude(calistirilabilir="claude", zaman_asimi=30)
_isindi = _o.orkestra.lider_isit(_lider, butce_usd=0.5)
with _db.baglanti() as _c:
    _uy = [r[0] for r in _c.execute("SELECT govde FROM olay WHERE tur='uyari'")]
sina("lider_isit bekleyen sureci hazirladi", _isindi and len(CL._SICAK) == 1,
     f"{len(CL._SICAK)} {_uy}")
sina("ikinci isitma TAZE olani bozmaz (yeni surec acmaz)",
     not _o.orkestra.lider_isit(_lider, butce_usd=0.5) and len(CL._SICAK) == 1)
_pid = next(iter(CL._SICAK.values()))["surec"].pid
# Sahte CLI kayit satirini yan sureci baslattiktan SONRA yazar: sayim o satir
# dusmeden alinirsa bekleyenin satiri "yeni surec" sayilir.
_bitis = time.time() + 5
while not any(f'"pid": {_pid}' in x for x in kayit.read_text(encoding="utf-8").splitlines())         and time.time() < _bitis:
    time.sleep(0.05)
once = surec_sayisi()
_cevap = _o.orkestra._lideri_kostur(_lider, "naber", 0.5, None)
time.sleep(0.5)
sina("liderin GERCEK turu panelin hazirladigi sureci kullandi",
     str(_pid) in str(_cevap) and surec_sayisi() == once + 1, f"{_cevap!r} {surec_sayisi() - once}")
CL.sicaklari_kapat()

CL.subprocess.Popen = _gercek
print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
