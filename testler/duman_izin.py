# -*- coding: utf-8 -*-
"""IZIN duman testi -- jeton yakmadan (29.09.2026).

Kullanici: *"git push, deploy yapmani istersem zaten ben soyluyorum, onay
verdigim icin yapiyorsun; ben demeden bana sorarak yapiyorsun. Agent
sistemimizde nasil olacak?"*

Kural: patronun ACIKCA istedigi riskli eylem sorulmaz, istemedigi
sorulur; para ve silme her zaman sorulur.

Sinananlar:
  1. Desenin sinifi OLCULUR (git push / deploy / genel kurma), belirsiz
     desen ('git'), para, silme ve --force reddedilir.
  2. Olumsuzluk kapisi ("push etme", "pushlama", "deploy etme").
  3. Plan izinleri patronun sozune karsi: alinti kelimesi kelimesine.
  4. Defter: kaynak yalniz insan, kalici gerekce ister, kaldirma sebep.
  5. Eslesme: ayni sinif + ardisik jeton; baska isin izni gecmez;
     kalici her iste; kaldirilan gecmez; --force gecmez.
  6. Gercek MCP surecinde izin_sor: izinli push gecer, rm yine sorulur,
     izinsiz iste push sorulur.
  7. Orkestra: plana yazilan izin her kola yazilir; uydurma alinti ve
     patron sozu olmayan izin plani REDDEDER (ret ogretir).
  8. Brifing izinleri soyler.
  9. Noktasiz i: "Yayınla", "Satın al" kapiya takiliyor.
 10. Panel: gorev izinleri gosterir, kaldirma sebepsiz reddedilir.
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

from ofis import Ofis, Veritabani, izin, riskli  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.orkestra import Orkestra, OrkestraHatasi  # noqa: E402

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


def hata_mi(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except Exception as exc:                     # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


_KOK = Path(tempfile.mkdtemp(prefix="ofis-izin-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Izin", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
k = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("lider", "lider", lider_mi=True, kanat_id=k, motor="sahte",
                  klasor=str(_KOK))
ofis.kadro.ise_al("isci", "backend", kanat_id=k, motor="sahte", klasor=str(_KOK))
PID = ofis.proje_id


def is_ac(ad):
    g = ofis.tahta.gorev_ac(ad, neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=[ad.lower() + ".md"], kanat_id=k)
    ofis.tahta.sahiplen(g["no"], "isci", g["revizyon"])
    return ofis.tahta.gorev(g["no"])


def kabuk_bulgu(komut):
    return riskli.kabuk_degerlendir("Bash", {"command": komut})


# --------------------------------------------------------------------------
print("\n-- 1. desenin sinifi olculur --")
sina("git push -> gonderim", izin.desen_sinifi("git push") == "gonderim")
sina("npm run deploy -> yayin", izin.desen_sinifi("npm run deploy") == "yayin")
sina("npm install -g -> sistem", izin.desen_sinifi("npm install -g x") == "sistem")
sina("tek basina 'git' reddedilir", "tanimlamiyor" in hata_mi(izin.dogrula, "", "git"))
sina("silme izinle acilmaz", "HER SEFERINDE" in hata_mi(izin.dogrula, "", "rm -rf dist"))
sina("para izinle acilmaz", "HER SEFERINDE" in hata_mi(izin.dogrula, "", "create-discount"))
sina("--force izinle acilmaz", "yikici" in hata_mi(izin.dogrula, "", "git push --force"))
sina("liderin soyledigi sinif OLCULENLE celisirse ret",
     bool(hata_mi(izin.dogrula, "yayin", "git push")))

# --------------------------------------------------------------------------
print("\n-- 2. olumsuzluk kapisi --")
for soz, al, bek in (("push etme, once bana goster", "push", True),
                     ("hatayi duzelt ve pushlama", "hatayi duzelt", True),
                     ("hatayi duzelt ama deploy etme", "deploy", True),
                     ("sakin pushla", "pushla", True),
                     ("duzelt ve pushla", "pushla", False),
                     ("bana sormadan pushla", "pushla", False),
                     ("duzelt, sonra deploy et", "deploy et", False),
                     ("pushlamadan once bana goster", "pushla", True)):
    sina(f"'{soz}' -> {'olumsuz' if bek else 'olumlu'}",
         izin.olumsuz_mu(soz, al) is bek)

# --------------------------------------------------------------------------
print("\n-- 3. plan izinleri patronun SOZUNE karsi --")
SOZ = "Giris hatasini duzelt, testleri kostur, sonra pushla ve deploy et"
gec, h = izin.plan_izinleri([{"eylem": "git push", "alinti": "sonra pushla"},
                             {"eylem": "npm run deploy", "alinti": "deploy et"}], SOZ)
sina("iki gecerli izin kabul", not h and len(gec) == 2, h)
_, h = izin.plan_izinleri([{"eylem": "git push", "alinti": "hemen pushla"}], SOZ)
sina("mesajda gecmeyen alinti reddedilir", "KELIMESI KELIMESINE" in h, h)
_, h = izin.plan_izinleri([{"eylem": "git push", "alinti": "push"}],
                          "duzelt ama push etme")
sina("olumsuz cumledeki alinti reddedilir", "olumsuz" in h, h)
_, h = izin.plan_izinleri([{"eylem": "git push", "alinti": "pushla"}], "")
sina("patron sozu yoksa izin yazilamaz", "patron" in h.lower(), h)
_, h = izin.plan_izinleri([{"eylem": "rm -rf dist", "alinti": "sil"}], "dist klasorunu sil")
sina("silme plana yazilamaz", "HER SEFERINDE" in h, h)
_, h = izin.plan_izinleri({"eylem": "git push"}, SOZ)
sina("liste olmayan izinler reddedilir", "LISTE" in h, h)
sina("bos izin listesi sorunsuz", izin.plan_izinleri([], SOZ) == ([], ""))

# --------------------------------------------------------------------------
print("\n-- 4. defter kurallari --")
g1 = is_ac("Bir")
g2 = is_ac("Iki")
sina("ajan kaynak olamaz",
     "insandan" in hata_mi(izin.tanimla, db, PID, desen="git push", veren="isci",
                           kaynak="ajan", gorev_id=g1["id"]))
sina("kalici izin gerekce ister",
     "GEREKCE" in hata_mi(izin.tanimla, db, PID, desen="git push origin test",
                          veren="insan", kaynak="insan"))
iz1 = izin.tanimla(db, PID, desen="git push", alinti="pushla", veren="insan",
                   kaynak="patron_sozu", gorev_id=g1["id"])
sina("is izni yazildi, sinif olculdu", iz1["sinif"] == "gonderim")
with db.baglanti() as c:
    sina("izin_verildi olayi yazildi", c.execute(
        "SELECT COUNT(*) FROM olay WHERE tur='izin_verildi'").fetchone()[0] == 1)
sina("kaldirma sebep ister",
     "zorunlu" in hata_mi(izin.kaldir, db, PID, iz1["id"], sebep="").lower())

# --------------------------------------------------------------------------
print("\n-- 5. eslesme --")
sina("izinli iste git push origin main gecer",
     izin.eslesen(db, PID, g1["id"], kabuk_bulgu("git push origin HEAD:main")) is not None)
sina("izinli iste --force GECMEZ",
     izin.eslesen(db, PID, g1["id"], kabuk_bulgu("git push --force origin main")) is None)
sina("baska isin izni gecmez",
     izin.eslesen(db, PID, g2["id"], kabuk_bulgu("git push origin main")) is None)
sina("izin sinifi disi (rm) gecmez",
     izin.eslesen(db, PID, g1["id"], kabuk_bulgu("rm a.txt")) is None)
sina("baska yayin eylemi (docker push) gecmez -- desen dar",
     izin.eslesen(db, PID, g1["id"], kabuk_bulgu("docker push img")) is None)
kal = izin.tanimla(db, PID, desen="npm run deploy", veren="insan", kaynak="insan",
                   gerekce="test ortami")
sina("kalici izin her iste gecer",
     izin.eslesen(db, PID, g2["id"], kabuk_bulgu("npm run deploy")) is not None)
izin.kaldir(db, PID, kal["id"][:8], sebep="bitti")
sina("kaldirilan izin gecmez",
     izin.eslesen(db, PID, g2["id"], kabuk_bulgu("npm run deploy")) is None)
_h = hata_mi(izin.tanimla, db, PID, desen="yayınla", alinti="yayına al",
             veren="insan", kaynak="patron_sozu", gorev_id=g2["id"])
sina("Turkce 'yayınla' deseni kabul edildi", not _h, _h)
tb = riskli.degerlendir("browser_click", {"element": "Yayınla düğmesi"})
sina("tarayici: 'Yayınla' izinle gecer",
     tb is not None and izin.eslesen(db, PID, g2["id"], tb) is not None)
para = riskli.arac_degerlendir("mcp__x__create-discount", {})
sina("para bulgusu hic eslesmez", izin.eslesen(db, PID, g2["id"], para) is None)
sina("bozuk bulgu patlamaz (None)", izin.eslesen(db, PID, g1["id"], {"sinif": None}) is None)

# --------------------------------------------------------------------------
print("\n-- 6. gercek MCP surecinde izin_sor --")


def izin_sor(gorev_no, arac, girdi):
    cevre = os.environ.copy()
    cevre.update({"OFIS_DB": str(db_yolu), "OFIS_PROJE": PID,
                  "OFIS_AJAN": "isci", "OFIS_GOREV": str(gorev_no)})
    p = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "ofis" / "mcp_sunucu.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=cevre)
    istekler = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "izin_sor",
                    "arguments": {"tool_name": arac, "input": girdi}}},
    ]
    cikti, hata = p.communicate("\n".join(json.dumps(x) for x in istekler) + "\n",
                                timeout=60)
    for satir in cikti.splitlines():
        try:
            y = json.loads(satir)
        except ValueError:
            continue
        if y.get("id") == 2:
            return json.loads(y["result"]["content"][0]["text"])
    return {"behavior": "?", "stderr": hata[-400:]}


r = izin_sor(g1["no"], "Bash", {"command": "git push origin main"})
sina("izinli iste push GECTI (allow)", r.get("behavior") == "allow", str(r)[:200])
with db.baglanti() as c:
    sina("izinle_gecti kayda gecti", c.execute(
        "SELECT COUNT(*) FROM olay WHERE tur='izinle_gecti'").fetchone()[0] >= 1)
r = izin_sor(g1["no"], "Bash", {"command": "rm eski.txt"})
sina("ayni iste rm yine SORULDU (deny)", r.get("behavior") == "deny", str(r)[:200])
g3 = is_ac("Uc")
r = izin_sor(g3["no"], "Bash", {"command": "git push origin main"})
sina("izinsiz iste push SORULDU (deny)", r.get("behavior") == "deny", str(r)[:200])

# --------------------------------------------------------------------------
print("\n-- 7. orkestra: plan izinleri --")
kutu = {"cevap": "", "istekler": []}


class Kaydeden(SahteMotor):
    def tur_kos(self, metin, **ayar):
        kutu["istekler"].append(metin)
        return super().tur_kos(metin, **ayar)


ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **kw: Kaydeden(cevap=kutu["cevap"]))


def plan(izinler):
    return "```json\n" + json.dumps({
        "bol": False, "gerekce": "tek is", "izinler": izinler,
        "kollar": [{"baslik": "Duzelt", "sahip": "isci", "neden": "hata var",
                    "kabul_olcutu": "test yesil", "govde": "duzelt",
                    "yazma_alani": ["giris.py"]}]}, ensure_ascii=False) + "\n```"


kutu["cevap"] = plan([{"eylem": "git push", "alinti": "sonra pushla"}])
sonuc = ork.hedef_ver("Giris hatasi", deneme=1, patron_sozu=SOZ)
yeni = sonuc["gorevler"][0]
sina("plan izni kaydedildi", sonuc["izinler"] == ["git push"], str(sonuc.get("izinler")))
sina("izin yeni isin kaydinda",
     [i["desen"] for i in izin.liste(db, PID, gorev_id=yeni["id"], kalici=False)] == ["git push"])
sina("plan istemi patronun mesajini tasiyor",
     "PATRONUN KENDI SOZU" in kutu["istekler"][-1] and SOZ in kutu["istekler"][-1])
# 01.10 (gercek set G14): gecersiz izin ONCEKI denemelerde plani reddeder
# (ret ogretir), SON denemede plani DUSURMEZ -- izin atilir, kayda gecer.
kutu["cevap"] = plan([{"eylem": "git push", "alinti": "pushla hemen"}])
_s2 = ork.hedef_ver("Giris hatasi 2", deneme=2, patron_sozu=SOZ)
with db.baglanti() as _c:
    _red = [r[0] for r in _c.execute("SELECT govde FROM olay WHERE tur='uyari' AND "
                                    "govde LIKE 'Plan reddedildi (1. deneme)%'")]
    _at = [r[0] for r in _c.execute("SELECT govde FROM olay WHERE tur='uyari' AND "
                                   "govde LIKE 'Planin izinleri ATILDI%'")]
sina("uydurma alinti ILK denemede plani REDDETTI (ogretir)",
     any("KELIMESI KELIMESINE" in x for x in _red), str(_red[-1:]))
sina("SON denemede plan DUSMEDI, izin ATILDI ve kayda gecti",
     bool(_s2["gorevler"]) and not _s2.get("izinler") and bool(_at), str(_s2.get("izinler")))
kutu["cevap"] = plan([{"eylem": "git push", "alinti": "pushla"}])
_s3 = ork.hedef_ver("Patronsuz", deneme=1)
sina("patron sozu olmadan izin YAZILMADI, plan yine de acildi",
     bool(_s3["gorevler"]) and not _s3.get("izinler"), str(_s3.get("izinler")))
sina("'Deneme' kelimesi olumsuz SAYILMAZ (G14)",
     izin.olumsuz_mu("formu Ad: Deneme, E-posta: deneme@ornek.com ile doldur ve gonder",
                     "formu Ad: Deneme, E-posta: deneme@ornek.com ile doldur ve gonder") is False)
sina("'formu doldur ama gonderme' -> gonder olumsuz",
     izin.olumsuz_mu("formu doldur, gonderme", "doldur, gonderme") is True)
kutu["istekler"].clear()
kutu["cevap"] = plan([])
ork.hedef_ver("Sozsuz", deneme=1)
sina("patron sozu yoksa istemde izin bolumu YOK",
     "PATRONUN IZINLERI" not in kutu["istekler"][-1])

# --------------------------------------------------------------------------
print("\n-- 8. brifing --")
b = ofis.brifing.k4_gorev(yeni["no"])
sina("brifing izni soyluyor", "ONCEDEN izin" in b and "git push" in b)
sina("izinsiz isin brifinginde blok yok",
     "ONCEDEN izin" not in ofis.brifing.k4_gorev(g3["no"]))

# --------------------------------------------------------------------------
print("\n-- 9. noktasiz i --")
for t, s in (("Yayınla", "yayin"), ("Satın al", "para"), ("Canlıya al", "yayin")):
    b2 = riskli.degerlendir("browser_click", {"element": t})
    sina(f"'{t}' kapiya takiliyor ({s})", bool(b2) and b2["sinif"] == s)

# --------------------------------------------------------------------------
print("\n-- 10. panel --")
try:
    from fastapi.testclient import TestClient
    from ofis.panel import olustur
    ist = TestClient(olustur(db_yolu))
    j = ist.get(f"/api/gorev/{yeni['no']}").json()
    sina("gorev cevabinda izinler", [i["desen"] for i in j.get("izinler", [])] == ["git push"])
    if not j.get("izinler"):
        raise SystemExit(f"== {GECEN} gecti, {KALAN} kaldi ==")
    r = ist.post(f"/api/izin/{j['izinler'][0]['id']}/kaldir", json={"sebep": ""})
    sina("sebepsiz kaldirma 400", r.status_code == 400)
    r = ist.post(f"/api/izin/{j['izinler'][0]['id']}/kaldir", json={"sebep": "vazgectim"})
    sina("sebepli kaldirma 200", r.status_code == 200, r.text[:120])
    j = ist.get(f"/api/gorev/{yeni['no']}").json()
    sina("kaldirilan izin kartta yok", j.get("izinler") == [])
except ImportError as exc:
    print(f"  [ATLANDI] fastapi yok: {exc}")

print(f"\n== {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
