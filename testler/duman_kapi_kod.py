# -*- coding: utf-8 -*-
"""KODLA SILME / BETIK DOSYASI kapi testi (01.10.2026).

Jeton yakmaz. OLCULDU: kapi `rm`, `Remove-Item`, `git clean`i soruyordu
ama ayni silmenin baska yazimlarini -- `python -c "os.remove(..)"`,
`shutil.rmtree`, `Path.unlink()`, heredoc'taki Python, node `fs.rmSync`,
PowerShell `[IO.File]::Delete`, `find -delete`, codex'in kod kipindeki
`tools.exec_command` -- SORMADAN geciriyordu; bir betik dosyasini
calistirmak (`python temizle.py`) icine hic bakilmadan geciyordu.
Sinanan: (1) satir ici kodla silme sorulur, (2) zararsiz komut SERBEST
kalir (onay yorgunlugu), (3) betigin ICI taranir, (4) gercek MCP kapisi
uctan uca ayni karari verir; defter yokken `ls` reddedilmez.
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

from ofis import Ofis, Veritabani, riskli as R  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def karar(arac, komut):
    b = R.arac_degerlendir(arac, {"command": komut})
    return (b["sinif"] if b and b.get("sorulur") else None)


print("== kodla silme / betik kapi testi ==\n")
print("1. satir ici KODLA silme sorulur")
SILME = {
    "python -c os.remove": ("Bash", 'python -c "import os; os.remove(\'a.txt\')"'),
    "python -c os.unlink": ("Bash", 'python3 -c "import os; os.unlink(\'a\')"'),
    "python -c shutil.rmtree": ("Bash", 'python -c "import shutil; shutil.rmtree(\'out\')"'),
    "python -c Path.unlink()": ("Bash", 'python -c "from pathlib import Path; Path(\'a\').unlink()"'),
    "python heredoc os.remove": ("Bash", "python - <<'EOF'\nimport os\nos.remove('a.txt')\nEOF"),
    "node -e fs.rmSync": ("Bash", 'node -e "require(\'fs\').rmSync(\'d\',{recursive:true})"'),
    "node -e fs.unlinkSync": ("Bash", 'node -e "require(\'fs\').unlinkSync(\'a\')"'),
    "node -e fs.promises.rm": ("Bash", 'node -e "require(\'fs\').promises.rm(\'d\')"'),
    "PowerShell [IO.File]::Delete": ("PowerShell", '[System.IO.File]::Delete("a.txt")'),
    "PowerShell [IO.Directory]::Delete": ("PowerShell", '[IO.Directory]::Delete("d", $true)'),
    "find -delete": ("Bash", 'find . -name "*.tmp" -delete'),
    "codex kod kipi exec_command(python os.remove)":
        ("Bash", 'text(await tools.exec_command({cmd:"python -c \\"import os; os.remove(\'a\')\\""}));'),
}
for ad, (arac, komut) in SILME.items():
    sina(f"{ad} -> SORULUR (silme)", karar(arac, komut) == "silme", str(karar(arac, komut)))

print("\n2. zararsiz komut SERBEST kalir (onay yorgunlugu yok)")
ZARARSIZ = {
    "python -c okuma": 'python -c "print(open(\'a.txt\').read())"',
    "metinde 'remove' kelimesi": 'python -c "print(\'remove\')"',
    "liste.remove() (dosya degil)": 'python -c "x=[1,2]; x.remove(1); print(x)"',
    "find -name": 'find . -name "*.py"',
    "git status": "git status",
    "pytest": "python -m pytest -q",
    "heredoc rapor metni": "python - <<'EOF'\nprint('deploy notu ve rm kelimesi')\nEOF",
    "betik calistirma, dosya yok": "python yok_boyle_bir_betik.py",
}
for ad, komut in ZARARSIZ.items():
    sina(f"{ad} -> SERBEST", karar("Bash", komut) is None, str(karar("Bash", komut)))

print("\n3. betik dosyasinin ICI taranir")
D = Path(tempfile.mkdtemp(prefix="ofis-kapi-kod-"))
(D / "sub").mkdir()
BETIKLER = {
    "temizle.py": ('import os\nos.remove("a.txt")\n', "silme"),
    "rapor.py": ('print("deploy ve rm kelimeleri metinde")\n# rm -rf eski yorum\n', None),
    "gonder.py": ('import subprocess\nsubprocess.run("git push", shell=True)\n', "gonderim"),
    "api.py": ('import requests\nrequests.post("https://x.com", json={})\n', "gonderim"),
    "ac.py": ('import webbrowser\nwebbrowser.open("https://x.com")\n', "masaustu"),
    "sil.js": ("require('fs').rmSync('out', {recursive: true})\n", "silme"),
    "temizle.ps1": ("Remove-Item -Recurse out\n", "silme"),
    "kur.sh": ("rm -rf build\n", "silme"),
    "derle.sh": ("echo derleniyor\n", None),
}
for ad, (icerik, beklenen) in BETIKLER.items():
    (D / ad).write_text(icerik, encoding="utf-8")
    yor = {"py": "python", "js": "node", "ps1": "pwsh -File", "sh": "bash"}[ad.rsplit(".", 1)[1]]
    b = R.betik_degerlendir("Bash", {"command": f"{yor} {ad}"}, str(D))
    sina(f"`{yor} {ad}` -> {beklenen or 'SERBEST'}", (b["sinif"] if b else None) == beklenen,
         str(b and (b["sinif"], b["esles"])))
b = R.betik_degerlendir("Bash", {"command": "python ../temizle.py", "workdir": str(D / "sub")}, str(D))
sina("calisma klasoru (workdir) + `../` cozuluyor", b is not None and b["sinif"] == "silme")
b = R.betik_degerlendir("Bash", {"command": f'python "{D / "temizle.py"}"'}, "")
sina("tirnakli MUTLAK yol cozuluyor", b is not None and b["sinif"] == "silme")
b = R.betik_degerlendir("Bash", {"command": "python temizle.py"}, str(D))
sina("  onay karti betigi ve buldugunu SOYLUYOR", b and "temizle.py" in b["sebep"] and "os.remove" in b["sebep"])


# ---------------------------------------------------------------------------
print("\n4. gercek MCP kapisi uctan uca")


class Sunucu:
    def __init__(self, ortam: dict) -> None:
        cevre = os.environ.copy()
        cevre.update(ortam)
        self.p = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1, env=cevre, cwd=str(D))
        self.sayac = 0

    def cagir(self, yontem, parametre=None):
        self.sayac += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.sayac, "method": yontem,
                                       "params": parametre or {}}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def izin(self, arac, komut):
        y = self.cagir("tools/call", {"name": "izin_sor",
                                      "arguments": {"tool_name": arac, "input": {"command": komut}}})
        return json.loads(y["result"]["content"][0]["text"])

    def kapat(self):
        self.p.stdin.close()
        self.p.wait(timeout=20)


db = Veritabani(D / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Kapi", amac="a", basari_olcutu="b", kok_klasor=str(D))
kn = ofis.kanat_ac("ANA", "AN")
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, tur="eller", motor="sahte", klasor=str(D))
g = ofis.tahta.gorev_ac("Is", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                        kanat_id=kn, yazma_alani=["a/"])
ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
s = Sunucu({"OFIS_DB": str(db.yol), "OFIS_PROJE": ofis.proje_id, "OFIS_AJAN": "cinar",
            "OFIS_GOREV": str(g["no"])})
s.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
sina("kapi: `python -c os.remove` -> REDDEDILIR (onay istenir)",
     s.izin("Bash", 'python -c "import os; os.remove(\'x\')"').get("behavior") == "deny")
sina("kapi: `python temizle.py` (betik siliyor) -> REDDEDILIR",
     s.izin("Bash", "python temizle.py").get("behavior") == "deny")
sina("kapi: `python rapor.py` (zararsiz betik) -> SERBEST",
     s.izin("Bash", "python rapor.py").get("behavior") == "allow")
sina("kapi: `git status` -> SERBEST", s.izin("Bash", "git status").get("behavior") == "allow")
with db.baglanti() as c:
    kart = c.execute("SELECT eylem FROM onay WHERE eylem LIKE '%temizle.py%'").fetchone()
sina("  patrona giden onay kartinda betigin adi var", kart is not None, str(kart and kart[0]))
s.kapat()
s2 = Sunucu({"OFIS_DB": "", "OFIS_PROJE": "", "OFIS_AJAN": ""})
s2.cagir("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
sina("defter/kimlik yokken `ls` REDDEDILMEZ (kok alinamasa da)",
     s2.izin("Bash", "ls").get("behavior") == "allow", str(s2.izin("Bash", "ls")))
s2.kapat()

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
