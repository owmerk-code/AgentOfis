# -*- coding: utf-8 -*-
"""BAGLAM DOLULUGU ve OTURUM TAZELEME (06.10.2026, Asama 3 / E34). Jeton yakmaz.

Olcu: turun SON model cagrisinin girdisi + ciktisi; sinir motorun kendi
bildirimi (olculdu: Claude sonucu `modelUsage.contextWindow` = 1.000.000
Sonnet 5.5; Codex `model_context_window` = 258.400).

Sinanan: (1) Claude arka kipi -- sahte CLI gercek bicimde akis uretir,
`bitti.ek.baglam` son mesajdan, sinir sonuctan; ogrenilen sinir saklanir.
(2) Codex app-server `thread/tokenUsage/updated` ve gercek terminal
`token_count`. (3) Koltuk: son baglam %80'i gectiyse oturum SURDURULMEZ
(tam brifing + devir, `oturum_tazelendi`), altindaysa surer, sinir
bilinmiyorsa karar yok. (4) Panel ajan sicilinde baglam.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ofis.motor.claude as CL  # noqa: E402
from ofis.motor import tip  # noqa: E402
from ofis.motor.codex import CodexMotoru  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== baglam dolulugu ==\n")
print("1. Claude arka kipi (sahte CLI, gercek akis bicimi)")
SAHTE = r'''
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.read()
def yaz(m): sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
yaz({"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-sonnet-5-5"})
for i, (gir, oku) in enumerate([(2, 20000), (3, 150000)]):
    yaz({"type": "assistant", "message": {"id": f"m{i}", "model": "claude-sonnet-5-5",
         "content": [{"type": "text", "text": "x"}],
         "usage": {"input_tokens": gir, "cache_read_input_tokens": oku,
                   "cache_creation_input_tokens": 1000, "output_tokens": 500}}})
yaz({"type": "result", "subtype": "success", "is_error": False, "session_id": "s1", "result": "tamam",
     "total_cost_usd": 0.01, "usage": {"input_tokens": 5, "output_tokens": 1000,
     "cache_read_input_tokens": 170000, "cache_creation_input_tokens": 2000},
     "modelUsage": {"claude-sonnet-5-5": {"contextWindow": 1000000}}})
'''
d = Path(tempfile.mkdtemp(prefix="ofis-baglam-"))
(d / "sahte.py").write_text(SAHTE, encoding="utf-8")
_gercek = subprocess.Popen
CL.subprocess.Popen = lambda komut, **kw: _gercek([sys.executable, str(d / "sahte.py"), *komut[1:]], **kw)
m = CL.ClaudeMotoru(calistirilabilir="claude", zaman_asimi=30)
bitti = [o for o in m.tur_kos("selam", klasor=str(d), model="sonnet", yazabilir=False) if o.tur == "bitti"][-1]
CL.subprocess.Popen = _gercek
bg = bitti.ek.get("baglam") or {}
sina("baglam SON mesajdan (3+150000+1000+500), turun toplamindan degil",
     bg.get("dolu") == 151503, str(bg))
sina("sinir sonucun contextWindow'undan (1.000.000), oran 0,15", bg.get("sinir") == 1000000
     and bg.get("oran") == 0.1515, str(bg))
sina("ogrenilen sinir saklandi (gercek terminal kipi icin)",
     tip.baglam_siniri("claude-sonnet-5-5") == 1000000)
sina("sinirsiz modelde oran None (uydurma yok)",
     tip.baglam_bilgisi(5000, None, model="bilinmeyen-model") == {"dolu": 5000, "sinir": None, "oran": None})
sina("olculemeyen dolu -> None", tip.baglam_bilgisi(0, 1000) is None)

print("\n2. Codex")
cx = CodexMotoru()
durum = {"jeton": 0}
cx._app_bildirim("thread/tokenUsage/updated", {"tokenUsage": {
    "total": {"inputTokens": 900000, "outputTokens": 9000},
    "last": {"totalTokens": 210000, "inputTokens": 208000, "outputTokens": 2000},
    "modelContextWindow": 258400}}, durum, {})
b = tip.baglam_bilgisi(durum.get("son_baglam"), durum.get("baglam_siniri"))
sina("app-server: son cagri 210000 / 258400 (oran 0,81)", b and b["dolu"] == 210000
     and b["sinir"] == 258400 and b["oran"] == 0.8127, str(b))
durum = {}
cx.tui_cevir({"type": "event_msg", "payload": {"type": "token_count", "info": {
    "last_token_usage": {"input_tokens": 25854, "output_tokens": 114, "total_tokens": 25968},
    "model_context_window": 258400}}}, durum)
sina("gercek terminal (oturum kaydi): sinir okundu", durum.get("baglam_siniri") == 258400, str(durum))

print("\n3. koltuk: oturum tazeleme")
from ofis import Koltuk, Ofis, Veritabani, kullanim  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Baglam", amac="a", basari_olcutu="b", kok_klasor=str(d))
kn = ofis.kanat_ac("GENEL", "GE")
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(d))


def senaryo(oran, sinir=1000):
    g = ofis.tahta.gorev_ac(f"Is {oran}", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
    g = ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
    ofis.kadro.oturum_kaydet("cinar", "eski-oturum")
    kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"jeton": 1, "baglam": {
        "dolu": int(oran * 1000), "sinir": sinir, "oran": oran if sinir else None}},
        ajan_ad="cinar", gorev_id=g["id"], motor="sahte")
    kayit = {}

    class Izle(SahteMotor):
        def tur_kos(self, metin, **ayar):
            kayit["oturum"] = ayar.get("oturum_id")
            kayit["metin"] = metin
            return super().tur_kos(metin, **ayar)

    olaylar = list(Koltuk(ofis, motor_fabrikasi=lambda a, **k: Izle()).akit(g["no"], "cinar"))
    return kayit, [o for o in olaylar if o["tur"] == "oturum_tazelendi"]


k, t = senaryo(0.85)
sina("%85: oturum SURDURULMEDI (yeni oturum)", not k.get("oturum"), str(k.get("oturum")))
sina("%85: tam brifing gitti (K1-K4)", "K2" in k.get("metin", "") and "K4" in k.get("metin", ""))
sina("%85: 'oturum tazelendi' olayi sayilarla", t and "%85" in t[0]["govde"], str(t[:1]))
k, t = senaryo(0.50)
sina("%50: oturum SURDU", k.get("oturum") == "eski-oturum" and not t, str(k.get("oturum")))
k, t = senaryo(0.95, sinir=None)
sina("sinir bilinmiyor: karar yok, oturum surdu", k.get("oturum") == "eski-oturum" and not t)

print("\n4. panel")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
st = next(a for a in ist.get("/api/ofis").json()["ajanlar"] if a["ad"] == "cinar")["sicil"]["son_tur"]
sina("baglam bildirmeyen motorun turunda gosterge YOK (None)", st.get("baglam") is None, str(st))
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"jeton": 1, "baglam": {"dolu": 210000, "sinir": 258400,
                       "oran": 0.8127}}, ajan_ad="cinar", motor="codex")
st = next(a for a in ist.get("/api/ofis").json()["ajanlar"] if a["ad"] == "cinar")["sicil"]["son_tur"]
sina("ajan sicili son turun baglamini veriyor", (st.get("baglam") or {}).get("oran") == 0.8127, str(st))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
