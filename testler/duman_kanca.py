# -*- coding: utf-8 -*-
"""GERCEK TERMINAL KANCASI duman testi -- jeton yakmadan (29.09.2026).

`ofis/kanca.py`, gercek Claude/Codex terminalinin her arac cagrisini
ofisin TEK kapisina sorar. Sinananlar (hepsi GERCEK alt surecte, CLI'in
cagirdigi bicimde: stdin'e JSON, stdout'tan JSON):
  1. Yerlesik dosya araci ve sirada komut serbest (allow).
  2. rm durur (deny) ve onay defterine kart duser.
  3. Onaylanan kart ayni komutu BIR KEZ gecirir, ikinci kez yine durur.
  4. Patronun izni (izin.py) push'u sorulmadan gecirir.
  5. Kimlik yoksa / defter bozuksa KAPALI kalir (deny).
  6. `--oz-sinama` TAMAM der ve gercek deftere kart YAZMAZ.
  7. Bozuk girdi (JSON degil) de deny, cokme yok.
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

KANCA = str(Path(__file__).resolve().parent.parent / "ofis" / "kanca.py")
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


_KOK = Path(tempfile.mkdtemp(prefix="ofis-kanca-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Kanca", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
k = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("isci", "backend", kanat_id=k, motor="sahte", klasor=str(_KOK))
g = ofis.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k",
                        yazma_alani=["a.txt"], kanat_id=k)
ofis.tahta.sahiplen(g["no"], "isci", g["revizyon"])
KIMLIK = {"OFIS_DB": str(db_yolu), "OFIS_PROJE": ofis.proje_id,
          "OFIS_AJAN": "isci", "OFIS_GOREV": str(g["no"])}


def kanca(girdi, ortam=None, ham=None, ek=()):
    cevre = {a: v for a, v in os.environ.items() if not a.startswith("OFIS_")
             or a == "OFIS_EV"}
    cevre.update(ortam if ortam is not None else KIMLIK)
    cevre["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, KANCA, *ek],
                       input=ham if ham is not None else json.dumps(girdi),
                       capture_output=True, text=True, encoding="utf-8",
                       env=cevre, timeout=60)
    if ek:
        return r.stdout.strip()
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]
    except Exception:                            # noqa: BLE001
        return {"permissionDecision": "?", "ham": r.stdout[-300:] + r.stderr[-300:]}


def kartlar():
    with db.baglanti() as c:
        return [dict(r) for r in c.execute("SELECT * FROM onay")]


print("\n-- 1. serbest --")
sina("Write serbest", kanca({"tool_name": "Write", "tool_input": {"file_path": "a.txt"}})
     ["permissionDecision"] == "allow")
sina("sirada komut serbest", kanca({"tool_name": "Bash", "tool_input": {"command": "python -V"}})
     ["permissionDecision"] == "allow")

print("\n-- 2. rm durur, kart duser --")
c = kanca({"tool_name": "Bash", "tool_input": {"command": "rm sil.txt"}})
sina("rm deny", c["permissionDecision"] == "deny", str(c)[:200])
sina("sebep ajana SIMDI DUR diyor", "DUR" in c.get("permissionDecisionReason", ""))
sina("onay karti defterde", len([x for x in kartlar() if x["durum"] == "bekliyor"]) == 1)

print("\n-- 3. onay bir kez gecer --")
ofis.postane.onay_cevapla(kartlar()[0]["id"], onayla=True)
sina("onaydan sonra ayni komut gecer",
     kanca({"tool_name": "Bash", "tool_input": {"command": "rm sil.txt"}})["permissionDecision"] == "allow")
sina("ikinci kez yine durur (onay tukendi)",
     kanca({"tool_name": "Bash", "tool_input": {"command": "rm sil.txt"}})["permissionDecision"] == "deny")

print("\n-- 4. patronun izni --")
izin.tanimla(db, ofis.proje_id, desen="git push", alinti="pushla", veren="insan",
             kaynak="patron_sozu", gorev_id=g["id"])
sina("izinli push sorulmadan gecer",
     kanca({"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
     ["permissionDecision"] == "allow")

print("\n-- 5. kapali kalir --")
sina("kimlik yoksa rm deny",
     kanca({"tool_name": "Bash", "tool_input": {"command": "rm x"}}, ortam={})
     ["permissionDecision"] == "deny")
sina("bozuk defter yolu: rm deny",
     kanca({"tool_name": "Bash", "tool_input": {"command": "rm x"}},
           ortam=dict(KIMLIK, OFIS_PROJE="yok-boyle-proje"))["permissionDecision"] == "deny")

print("\n-- 6. oz-sinama --")
once = len(kartlar())
sina("oz-sinama TAMAM", kanca(None, ek=("--oz-sinama",)) == "TAMAM")
sina("oz-sinama gercek deftere kart YAZMADI", len(kartlar()) == once)

print("\n-- 7. bozuk girdi --")
c = kanca(None, ham="bu json degil")
sina("JSON olmayan girdi cokmedi", c["permissionDecision"] in ("allow", "deny"), str(c)[:200])

print(f"\n== {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
