# -*- coding: utf-8 -*-
"""OFIS GELISTIRME HATTI (09.10.2026) -- kopya, tam sinama, kurulum karti,
kurma, geri alma; ve calisan ofisin koduna yazma yasagi.

Gercek ofisin koduna DOKUNULMAZ: "calisan ofis" gecici bir git deposudur
(`OFIS_GELISTIRME_KAYNAK`), kopya da gecici (`OFIS_GELISTIRME_KLASOR`).
Kural sinamalari (kendi kodu) gercek yolu yalniz OKUR (degerlendirir).
"""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from ofis import Ofis, Veritabani, riskli as R  # noqa: E402
from ofis import gelistirme as G  # noqa: E402
from ofis import mcp_sunucu as M  # noqa: E402
from ofis import panel as _panel  # noqa: E402
from ofis import sablon as S  # noqa: E402
from ofis.surec import PENCERE_YOK  # noqa: E402
from ofis.yollar import OFIS_KODU  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def git(kok, *a):
    r = subprocess.run(["git", "-C", str(kok), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=PENCERE_YOK)
    return r.stdout.strip()


D = Path(tempfile.mkdtemp(prefix="ofis-gelistirme-"))
KAY = D / "calisan"
KOP = D / "kopya"
os.environ["OFIS_GELISTIRME_KAYNAK"] = str(KAY)
os.environ["OFIS_GELISTIRME_KLASOR"] = str(KOP)
(KAY / "testler").mkdir(parents=True)
(KAY / "testler" / "duman_ornek.py").write_text("print('  [gecti] ornek')\n", encoding="utf-8")
# OFIS_* ortami kopyanin sinamasina SIZMAMALI (panelin gercek evi).
(KAY / "testler" / "duman_ortam.py").write_text(
    "import os, sys\n"
    "s = [k for k in os.environ if k.upper().startswith('OFIS_')]\n"
    "print('  [gecti] ortam temiz' if not s else '  [KALDI] OFIS ortami sizdi ' + str(s))\n"
    "sys.exit(1 if s else 0)\n", encoding="utf-8")
(KAY / "ofis.txt").write_text("surum 1\n", encoding="utf-8")
git(KAY, "init", "-q", "-b", "main")
git(KAY, "add", "-A")
git(KAY, "commit", "-q", "-m", "ilk")

print("1. kopya")
kok = G.kopya_hazirla()
sina("kopya kuruldu, kendi bos evi var (eski eve dusmez)",
     Path(kok, ".git").is_dir() and Path(kok, "ev").is_dir() and Path(kok, "ofis.txt").is_file())
sina("kopya isaretli", G.kopya_mi(kok) and not G.kopya_mi(KAY))
sina("kopyadan GONDERME kapali (push adresi gecersiz)", "KAPALI" in git(kok, "remote", "get-url", "--push", "origin"))
try:
    G.kopya_hazirla(OFIS_KODU / "testler" / "kopya-deneme")
    sina("ofisin kendi yerinde kopya ACILMAZ (hata)", False)
except G.GelistirmeHatasi:
    sina("ofisin kendi yerinde kopya ACILMAZ (hata)", not (OFIS_KODU / "testler" / "kopya-deneme").exists())

print("\n2. is kapanir -> kopyada sinama -> kurulum karti")
db_yolu = D / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Gel", amac="a", basari_olcutu="b", kok_klasor=str(D / "proje"))
kid = ofis.kanat_ac("GELISTIRME", "GL")
ofis.takim_klasoru_ayarla(kid, kok)
ofis.kadro.ise_al("lale", "lider", kanat_id=kid, lider_mi=True, motor="sahte", klasor=kok)
ofis.kadro.ise_al("ece", "backend", kanat_id=kid, motor="sahte", klasor=kok)


def is_kapat(baslik, dosya, icerik):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kid)
    g = ofis.tahta.sahiplen(g["no"], "ece", g["revizyon"])
    Path(kok, dosya).parent.mkdir(parents=True, exist_ok=True)
    Path(kok, dosya).write_text(icerik, encoding="utf-8")
    git(kok, "add", "-A")
    git(kok, "commit", "-q", "-m", f"#{g['no']} {baslik}")
    ofis.tahta.kanit_ekle(g["no"], "dosya", "yazildi", dosya, "ece")
    g = ofis.tahta.incelemeye_ver(g["no"], ofis.tahta.gorev(g["no"])["revizyon"])
    ofis.tahta.kapat(g["no"], g["revizyon"], kapatan="lale")
    return g["no"]


def bekle(no, durumlar=("kart", "sinama_kaldi"), sn=120):
    son = {}
    for _ in range(int(sn * 4)):
        son = G.teslim_durumu(db, ofis.proje_id, no)
        if son.get("durum") in durumlar:
            return son
        time.sleep(0.25)
    return son


def kartlar():
    return [o for o in ofis.postane.bekleyen_onaylar() if str(o.get("ayrinti") or "").startswith(G.ISARET)]


os.environ["OFIS_EV_DENEME_SIZINTI"] = "1"     # sizinti sinamasi: kopyanin sinamasina GITMEMELI
n1 = is_kapat("yeni ozellik", "ozellik.py", "print('yeni')\n")
d1 = bekle(n1)
sina("is kapaninca kopyada tam sinama kostu ve GECTI", d1.get("durum") == "kart"
     and d1.get("sinama", {}).get("gecti") == 2, str(d1.get("sinama")))
sina("OFIS_* ortami kopyanin sinamasina sizmadi", not d1.get("sinama", {}).get("kotu"))
k1 = kartlar()
sina("patrona KURULUM KARTI (sinama sonucu + degisen dosya + geri alma yolu)",
     len(k1) == 1 and "ozellik.py" in k1[0]["ayrinti"] and "geri-al" in k1[0]["ayrinti"]
     and "OFIS DEGISIKLIGINI KUR" in k1[0]["eylem"], str(k1)[:200])
sina("kart onaylanmadan calisan ofis DEGISMEDI", not (KAY / "ozellik.py").exists())

print("\n3. kaynak kirliyken kurulum DURUR")
(KAY / "ofis.txt").write_text("surum 1 + yarim is\n", encoding="utf-8")
ist = TestClient(_panel.olustur(db_yolu))
r = ist.post(f"/api/onay/{k1[0]['id']}", json={"onayla": True, "not_": "", "kapsam": "eylem", "surdur": False})
sina("kaydedilmemis degisiklik varken kurulmadi, sebep soylendi, kart ACIK kaldi",
     r.status_code == 400 and "KAYDEDILMEMIS" in r.text and not (KAY / "ozellik.py").exists()
     and len(kartlar()) == 1, r.text[:200])
git(KAY, "checkout", "--", "ofis.txt")

print("\n4. onay -> kurulur, kopya esitlenir, geri alinir")
r = ist.post(f"/api/onay/{k1[0]['id']}", json={"onayla": True, "not_": "", "kapsam": "eylem", "surdur": False})
d1 = G.teslim_durumu(db, ofis.proje_id, n1)
sina("panelden onayla: calisan ofise KURULDU (kaydin kendisi)",
     r.status_code == 200 and (KAY / "ozellik.py").is_file() and d1.get("durum") == "kuruldu"
     and f"#{n1} yeni ozellik" in git(KAY, "log", "-1", "--format=%s"), r.text[:200])
sina("kart kapandi", not kartlar())
sina("kopya calisan ofisle ESIT (fazla kayit kalmadi)",
     git(kok, "log", "--oneline", "origin/main..HEAD") == "", git(kok, "log", "--oneline", "-3"))
G.geri_al(ofis, n1)
sina("geri alma: calisan ofiste dosya gitti, kayit 'Revert' ile",
     not (KAY / "ozellik.py").exists() and "Revert" in git(KAY, "log", "-1", "--format=%s"))
try:
    G.geri_al(ofis, n1)
    sina("ikinci geri alma reddedilir", False)
except G.GelistirmeHatasi:
    sina("ikinci geri alma reddedilir", True)

print("\n5. sinama KALIRSA kart yok")
n2 = is_kapat("bozuk is", "testler/duman_bozuk.py", "print('  [KALDI] bozuk')\nraise SystemExit(1)\n")
d2 = bekle(n2)
sina("sinama kaldi -> durum sinama_kaldi, kart ACILMADI",
     d2.get("durum") == "sinama_kaldi" and not kartlar() and d2["sinama"]["kotu"][0]["dosya"] == "duman_bozuk.py",
     str(d2.get("sinama"))[:200])
with db.baglanti() as c:
    _o = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur = 'gelistirme'")]
sina("sebep deftere yazildi (hangi dosya kaldi)", any("SINAMA GECMEDI" in x and "duman_bozuk" in x for x in _o))
G.reddet(ofis, n2)
sina("reddedilen kayit kopyada geri alindi", not Path(kok, "testler", "duman_bozuk.py").exists())
# 09.10: reddet DURUST -- ikinci kez ya da sinama surerken reddedilmez, sebep soylenir.
try:
    G.reddet(ofis, n2)
    sina("  zaten reddedilmis teslim ikinci kez reddedilmez (hata)", False)
except G.GelistirmeHatasi:
    sina("  zaten reddedilmis teslim ikinci kez reddedilmez (hata)", True)
_ds = dict(G.teslim_durumu(db, ofis.proje_id, n2), durum="sinaniyor")
G._yaz(db, ofis.proje_id, 99, dict(_ds, no=99))
try:
    G.reddet(ofis, 99)
    sina("  sinama SURERKEN reddedilmez (dosyalar sinamanin altindan degismesin)", False)
except G.GelistirmeHatasi:
    sina("  sinama SURERKEN reddedilmez (dosyalar sinamanin altindan degismesin)", True)
with db.baglanti() as c:
    c.execute("DELETE FROM ayar WHERE anahtar = ?", (G._kayit_anahtari(99),))

print("\n6. reddet karti")
n3 = is_kapat("istenmeyen", "istenmeyen.py", "x = 1\n")
bekle(n3)
k3 = kartlar()
r = ist.post(f"/api/onay/{k3[0]['id']}", json={"onayla": False, "not_": "gerek yok", "kapsam": "eylem", "surdur": False})
sina("patron reddetti: calisan ofis degismedi, kopyada geri alindi",
     r.status_code == 200 and not (KAY / "istenmeyen.py").exists()
     and not Path(kok, "istenmeyen.py").exists()
     and G.teslim_durumu(db, ofis.proje_id, n3).get("durum") == "reddedildi")

print("\n7. kodsuz is -> teslim yok")
g = ofis.tahta.gorev_ac("arastirma", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kid)
g = ofis.tahta.sahiplen(g["no"], "ece", g["revizyon"])
ofis.tahta.kanit_ekle(g["no"], "dosya", "not", "x", "ece")
g = ofis.tahta.incelemeye_ver(g["no"], ofis.tahta.gorev(g["no"])["revizyon"])
ofis.tahta.kapat(g["no"], g["revizyon"], kapatan="lale")
sina("kayitsiz iste teslim/kart yok", not G.teslim_durumu(db, ofis.proje_id, g["no"]) and not kartlar())

print("\n8. CALISAN OFISIN KODUNA YAZILMAZ (kapi)")
ofis_dosyasi = str(OFIS_KODU / "ofis" / "riskli.py")
for ad, arac, girdi in (
        ("Write", "Write", {"file_path": ofis_dosyasi, "content": "x"}),
        ("Edit", "Edit", {"file_path": ofis_dosyasi, "old_string": "a", "new_string": "b"}),
        ("apply_patch", "apply_patch", {"input": f"*** Begin Patch\n*** Update File: {ofis_dosyasi}\n@@\n-a\n+b\n*** End Patch"}),
        ("kabuk cp", "Bash", {"command": f"cp a.py {OFIS_KODU / 'ofis'}"}),
        ("kabuk yonlendirme", "Bash", {"command": f"echo x > {OFIS_KODU / 'ofis' / 'a.py'}"}),
        ("git reset", "Bash", {"command": f'git -C "{OFIS_KODU}" reset --hard'})):
    b = R.arac_degerlendir(arac, girdi)
    sina(f"{ad} -> RET (kural)", bool(b) and b.get("ret") and b["sinif"] == "kural", str(b)[:120])
for ad, arac, girdi in (
        ("kopyaya Write", "Write", {"file_path": str(Path(str(OFIS_KODU) + "-gelistirme") / "ofis" / "a.py")}),
        ("kodu OKUMAK", "Bash", {"command": f"cat {OFIS_KODU / 'ofis' / 'riskli.py'}"}),
        ("ofisin evine yazmak", "Write", {"file_path": str(OFIS_KODU / "ev" / "x.txt")}),
        ("kopyada git commit", "Bash", {"command": f"git -C {str(OFIS_KODU) + '-gelistirme'} commit -m x"})):
    b = R.arac_degerlendir(arac, girdi)
    sina(f"{ad} -> serbest", b is None or not b.get("ret"), str(b)[:120])


class _Oturum:
    def __init__(self):
        self.ofis, self.ajan_ad, self.gorev_no, self.proje_id, self.kanat = ofis, "ece", None, ofis.proje_id, ""


_once = len(ofis.postane.bekleyen_onaylar())
r = json.loads(M.arac_izin_sor(_Oturum(), {"tool_name": "Write", "input": {"file_path": ofis_dosyasi}}))
sina("izin_sor: kendi koduna yazma REDDEDILDI, kart ACILMADI, dogru yol soylendi",
     r["behavior"] == "deny" and "GELISTIRME KOPYASINDA" in r["message"]
     and len(ofis.postane.bekleyen_onaylar()) == _once, str(r)[:200])

print("\n9. sablon + takim kurma")
sina("'Ofis gelistirme' sablonu var", "gelistirme" in S.SABLONLAR)
os.environ["OFIS_GELISTIRME_KLASOR"] = str(D / "kopya2")
r = ist.post("/api/takim/kur", json={"ad": "OFIS GEL", "sablon": "gelistirme", "uyeler": [
    {"ad": "tuna", "rol": "lider"}, {"ad": "umut", "rol": "backend"}]})
_k = next((k_ for k_ in ist.get("/api/organizasyon").json()["kanatlar"] if k_["ad"] == "OFIS GEL"), {})
sina("sablonla kurulan takimin klasoru calisan ofisin KOPYASI",
     r.status_code == 200 and G.kopya_mi(D / "kopya2")
     and ofis.kok_klasoru(r.json()["id"]).lower() == str((D / "kopya2").resolve()).lower(), r.text[:200])

from ofis import kit as _kit  # noqa: E402
_bt = _kit.oku(db, r.json().get("id", ""))["bitti_tanimi"] if r.status_code == 200 else []
sina("gelistirme takiminin bitti tanimi yazildi (kopya, sinama, onizleme, kurulum karari)",
     any("onizle" in x for x in _bt) and any("REDDEDILIR" in x for x in _bt), str(_bt)[:200])
# 09.10 F1 dersleri: gercek defterin kopyasi (YOLU ile), satir sonu, ALAN_EKLE.
sina("  bitti taniminda 09.10 dersleri: defter kopyasi (yol), satir sonu, alan genisletme",
     any("GERCEK DEFTERIN KOPYASINDA" in x and "/veri/ofis.sqlite3" in x for x in _bt)
     and any("sed -i" in x for x in _bt) and any("ALAN_EKLE" in x for x in _bt), str(_bt)[-300:])
_kid = r.json().get("id", "")
_kit.yaz(db, ofis.proje_id, _kid, bitti_tanimi=G.BITTI_TANIMI)          # eski varsayilan
G.takimi_hazirla(db, ofis.proje_id, _kid)
sina("  ESKI varsayilan kit yenisine guncellenir", len(_kit.oku(db, _kid)["bitti_tanimi"]) == len(G.bitti_tanimi()))
_kit.yaz(db, ofis.proje_id, _kid, bitti_tanimi=["patronun kendi maddesi"])
G.takimi_hazirla(db, ofis.proje_id, _kid)
sina("  patronun ELLE yazdigi kite dokunulmaz", _kit.oku(db, _kid)["bitti_tanimi"] == ["patronun kendi maddesi"])

_k = subprocess.run([sys.executable, "-m", "ofis.kabuk", "--db", str(db_yolu), "gelistirme"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    cwd=str(OFIS_KODU), creationflags=PENCERE_YOK)
sina("kabuk 'gelistirme': teslimler ve durumlari listelenir",
     f"#{n1}" in _k.stdout and "geri_alindi" in _k.stdout and "1 kaldi" in _k.stdout and "reddedildi" in _k.stdout,
     repr(_k.stdout[-600:]) + ' ERR ' + _k.stderr[-600:])

print("\n10. kopyanin KENDI paneli (onizleme)")
# ORTAMDAN BAGIMSIZ (09.10 canli): bu sinama gelistirme KOPYASINDA da kosar
# (kurulumdan once tam takim); orada kod zaten kopya. "Calisan ofis" kosulu
# kurulur, ortamdan okunmaz.
_asil_kopya_mi = G.kopya_mi
G.kopya_mi = lambda kok: False
try:
    G.onizleme_hazirla()
    sina("calisan ofiste onizleme paneli ACILMAZ", False)
except G.GelistirmeHatasi:
    sina("calisan ofiste onizleme paneli ACILMAZ", True)
finally:
    G.kopya_mi = _asil_kopya_mi
from ofis import yollar as _Y, bildirim as _B  # noqa: E402
_asil_kod, _asil_ortam = _Y.OFIS_KODU, dict(os.environ)
try:
    _Y.OFIS_KODU = Path(kok)
    h = G.onizleme_hazirla()
finally:
    _Y.OFIS_KODU = _asil_kod
    _ortam_kopya = dict(os.environ)
    os.environ.clear()
    os.environ.update(_asil_ortam)
_db2 = Veritabani(h["db"])
with _db2.baglanti() as _c:
    _pid = _c.execute("SELECT id FROM proje").fetchone()[0]
sina("onizleme: patronun paneli/sinama paneli/kabini KULLANILMAZ",
     h["kapi"] >= 8920 and h["kapi"] not in (8900, 8911) and h["kabin"] != 9222, str(h))
sina("onizleme: defter ve ev KOPYANIN icinde (gercek defter degil)",
     Path(h["db"]).resolve().is_relative_to(Path(kok).resolve())
     and Path(_ortam_kopya["OFIS_EV"]).resolve() == (Path(kok) / "ev").resolve(), str(h))
sina("onizleme: masaustu bildirimi kapali", _db2.ayar_oku(_pid, _B.AYAR, "acik") == "kapali")
import shutil as _sh  # noqa: E402
_sh.rmtree(G.onizleme_proje_koku(), ignore_errors=True)

print("\n9. kopyanin ev/i disk olcusune girmez (09.10 canli: yanlis 'beyan disi' uyarisi)")
from ofis import degisim as _dg  # noqa: E402
_dk = Path(tempfile.mkdtemp(prefix="ofis-gel-ev-"))
for _y in ("ev/gemini_ev/_kota/x.txt", "ofis/a.py", "alt/ev/b.txt"):
    (_dk / _y).parent.mkdir(parents=True, exist_ok=True)
    (_dk / _y).write_text("x", encoding="utf-8")
subprocess.run(["git", "init", "-q", str(_dk)], check=True)
_once = sorted(r for r, _ in _dg._gez(_dk))
sina("kopya olmayan klasorde ev/ OLCULUR (patronun projesinde ev adli klasor olabilir)",
     "ev/gemini_ev/_kota/x.txt" in _once, str(_once))
subprocess.run(["git", "-C", str(_dk), "config", "agentofis.gelistirme", "1"], check=True)
_sonra = sorted(r for r, _ in _dg._gez(_dk))
sina("  gelistirme kopyasinda kok ev/ ATLANIR, kod ve alt klasordeki ev/ olculur",
     "ev/gemini_ev/_kota/x.txt" not in _sonra and "ofis/a.py" in _sonra and "alt/ev/b.txt" in _sonra,
     str(_sonra))
_sh.rmtree(_dk, ignore_errors=True)

print("\n10. panel kapanip acilinca YARIM sinama yeniden kosar (09.10 canli: #5 karti hic gelmedi)")
n9 = is_kapat("yarim kalan sinama", "yarim.py", "print('y')\n")
bekle(n9)
_d9 = G.teslim_durumu(db, ofis.proje_id, n9)
# SAHIBI YASAYAN sinamaya dokunulmaz (10.10 canli: panel acilisi baska surecteki
# sinamayi ikinci kez baslatti, ikisi ayni kopyada yaristi).
_d9.update(durum="sinaniyor", sinama=None, kosan=G._surec.kimlik())
G._yaz(db, ofis.proje_id, n9, _d9)
sina("sahibi YASAYAN sinama yeniden baslatilmaz", G.yarim_sinamalari_surdur(db, ofis.proje_id, arkada=False) == [])
_d9.update(durum="sinaniyor", sinama=None, kosan="999999:1")   # sahibi OLU (panel sinama sirasinda oldu)
G._yaz(db, ofis.proje_id, n9, _d9)
_kart_once = len(kartlar())
_ys = G.yarim_sinamalari_surdur(db, ofis.proje_id, arkada=False)
_d9 = G.teslim_durumu(db, ofis.proje_id, n9)
sina("acilista yarim sinama yeniden kostu, sonuc yazildi", _ys == [n9] and _d9.get("durum") in ("kart", "sinama_kaldi"),
     str((_ys, _d9.get("durum"))))
sina("  biten/kurulan teslime DOKUNULMAZ (ikinci acilista bos)",
     G.yarim_sinamalari_surdur(db, ofis.proje_id, arkada=False) == [])
_py = (OFIS_KODU / "ofis" / "panel.py").read_text(encoding="utf-8")
sina("  panel acilisi bunu cagiriyor", "yarim_sinamalari_surdur(_db, pid)" in _py)

print("\n11. kopyada eksik npm paketleri (09.10 canli: Remotion yoktu, tam sinama hep kaliyordu)")
_dn = Path(tempfile.mkdtemp(prefix="ofis-gel-npm-"))
sina("kilit dosyasi yoksa npm KOSMAZ", G.bagimliliklari_kur(_dn) == [])
(_dn / "medya" / "remotion" / "node_modules").mkdir(parents=True)
(_dn / "medya" / "remotion" / "package-lock.json").write_text("{}", encoding="utf-8")
sina("  paketler zaten varsa npm KOSMAZ", G.bagimliliklari_kur(_dn) == [])
_gk = (OFIS_KODU / "ofis" / "gelistirme.py").read_text(encoding="utf-8")
sina("  baglanti (junction) VERILMEZ, kopya kendi paketini kurar; sinamadan once cagrilir",
     "mklink" not in _gk and "bagimliliklari_kur(kok)" in _gk and "bagimliliklari_kur(hedef)" in _gk)
_sh.rmtree(_dn, ignore_errors=True)

print("\n12. sinamadan ONCE kopya calisan ofisin son koduna esitlenir (09.10 canli: D17 eski koddan kaldi)")
(KAY / "testler" / "duman_yeni_duzeltme.py").write_text("print('  [gecti] calisan ofisin yeni duzeltmesi')\n", encoding="utf-8")
git(KAY, "add", "-A")
git(KAY, "commit", "-q", "-m", "calisan ofise sonradan giren duzeltme")
n12 = is_kapat("eski tabanda yazilan is", "is12.py", "print(12)\n")
d12 = bekle(n12)
sina("kopyadaki sinama calisan ofisin SONRADAN giren kaydini da kostu",
     Path(kok, "testler", "duman_yeni_duzeltme.py").is_file()
     and d12.get("sinama", {}).get("dosya", 0) >= 3, str(d12.get("sinama"))[:200])
sina("  isin kaydi son kodun USTUNDE (kurulacak sey = sinanan sey)",
     git(kok, "log", "-1", "--format=%s").startswith(f"#{n12} ")
     and "calisan ofise sonradan" in git(kok, "log", "--format=%s"), git(kok, "log", "-4", "--format=%s"))

print("\n13. satir sonlari toptan degisirse ofis geri koyar (09.10 canli: sed -i, 7 satir -> 14.793 satir fark)")
_karisik = b"".join((f"satir {i}".encode() + (b"\r\n" if i % 10 == 0 else b"\n")) for i in range(200))
git(KAY, "config", "core.autocrlf", "false")   # gercek kopyada dosya KAYITTA karisik (git normallestirmez)
git(kok, "config", "core.autocrlf", "false")
(KAY / "karisik.js").write_bytes(_karisik)
git(KAY, "add", "-A")
git(KAY, "commit", "-q", "-m", "karisik satir sonlu dosya")
G.esitle(kok)
_bozuk = _karisik.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n").replace(b"satir 7\r\n", b"satir 7 DEGISTI\r\n")
Path(kok, "karisik.js").write_bytes(_bozuk)
git(kok, "add", "-A")
git(kok, "commit", "-q", "-m", "#77 sed ile duzenleme")
_on = G.satir_sonu_onar(kok, 77)
_son = Path(kok, "karisik.js").read_bytes()
sina("toptan satir sonu degisimi ONARILDI, icerik degisikligi KORUNDU",
     _on == ["karisik.js"] and _son == _karisik.replace(b"satir 7\n", b"satir 7 DEGISTI\n"), str(_on))
sina("  onarim #no kaydi olarak yazildi (kurulumda isle birlikte gider)",
     git(kok, "log", "-1", "--format=%s").startswith("#77 satir sonlari"))
sina("  saglam is DOKUNULMAZ (ikinci cagri bos)", G.satir_sonu_onar(kok, 77) == [])
_gk2 = (OFIS_KODU / "ofis" / "gelistirme.py").read_text(encoding="utf-8")
sina("  is kapanirken sinamadan once cagriliyor", "satir_sonu_onar(kok, gorev[\"no\"])" in _gk2)
git(kok, "reset", "-q", "--hard", "origin/main")
git(kok, "config", "--unset", "core.autocrlf")
git(KAY, "config", "--unset", "core.autocrlf")

print("\n14. kopya calisan ofisin araclarini CALISTIRIR (09.10 canli: ffmpeg yoktu); kalan teslim yeniden sinanir")
_ao = G.arac_ortami()
sina("arac ortami yalniz VAR OLAN yollari verir", all(Path(v).exists() for v in _ao.values()), str(_ao))
_gk3 = (OFIS_KODU / "ofis" / "gelistirme.py").read_text(encoding="utf-8")
sina("  sinama ve onizleme bu ortami kullanir", "**arac_ortami()" in _gk3 and "arac_ortami().items()" in _gk3)
n14 = is_kapat("sinamasi kalan", "testler/duman_k14.py", "import sys\nprint('  [KALDI] ortam')\nsys.exit(1)\n")
bekle(n14)
sina("  sinama kaldi", G.teslim_durumu(db, ofis.proje_id, n14).get("durum") == "sinama_kaldi")
Path(kok, "testler", "duman_k14.py").write_text("print('  [gecti] ortam')\n", encoding="utf-8")   # ortam duzeldi
git(kok, "commit", "-qam", f"#{n14} ortam")
_ys14 = G.yeniden_sina(db, ofis.proje_id, n14)
sina("  yeniden sinandi, gecti, KART acildi", _ys14.get("durum") == "kart", str(_ys14.get("durum")))
try:
    G.yeniden_sina(db, ofis.proje_id, n14)
    sina("  karti acik teslim yeniden sinanmaz (hata)", False)
except G.GelistirmeHatasi:
    sina("  karti acik teslim yeniden sinanmaz (hata)", True)

print("\n15. kararlasmis kayitlar kopyadan duser; cakisma kaydedilir; is basinda esitleme (10.10 canli: #9)")
git(kok, "reset", "-q", "--hard", "origin/main")
(KAY / "ortak.txt").write_text("satir 1\n", encoding="utf-8")
git(KAY, "add", "-A")
git(KAY, "commit", "-q", "-m", "ortak dosya")
G.esitle(kok)
Path(kok, "ortak.txt").write_text("satir 1 -- #80 degistirdi\n", encoding="utf-8")
git(kok, "commit", "-qam", "#80 reddedilecek degisiklik")
git(kok, "revert", "--no-edit", "HEAD")
Path(kok, "yeni81.txt").write_text("81\n", encoding="utf-8")
git(kok, "add", "-A")
git(kok, "commit", "-qm", "#81 karar bekleyen is")
(KAY / "ortak.txt").write_text("satir 1 -- calisan ofis degistirdi\n", encoding="utf-8")   # #80 ile cakisir
git(KAY, "commit", "-qam", "calisan ofiste ayni satir")
sina("(sahne) kararlasmis #80 dusurulmeden esitleme CAKISIR", G.esitle(kok).get("tamam") is False)
_e = G.esitle(kok, cikar={80})
_log = git(kok, "log", "--format=%s", "origin/main..HEAD")
sina("#80 ve geri alinisi DUSTU, #81 son kodun ustunde", _e.get("tamam") and _log == "#81 karar bekleyen is", str((_e, _log)))
sina("  calisan ofisin degisikligi kopyada", "calisan ofis" in Path(kok, "ortak.txt").read_text(encoding="utf-8"))
G._yaz(db, ofis.proje_id, 80, {"no": 80, "durum": "reddedildi"})
sina("  kararli isler defterden okunur", 80 in G.kararli_isler(db, ofis.proje_id))
# cakisan iste durum KAYDEDILIR ve sonra yeniden sinanir
git(kok, "reset", "-q", "--hard", "origin/main")
n82 = None
g82 = ofis.tahta.gorev_ac("cakisan is", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kid)
g82 = ofis.tahta.sahiplen(g82["no"], "ece", g82["revizyon"])
Path(kok, "ortak.txt").write_text("satir 1 -- isin degisikligi\n", encoding="utf-8")
git(kok, "commit", "-qam", f"#{g82['no']} cakisan is")
(KAY / "ortak.txt").write_text("satir 1 -- yine calisan ofis\n", encoding="utf-8")
git(KAY, "commit", "-qam", "calisan ofis yine degisti")
ofis.tahta.kanit_ekle(g82["no"], "dosya", "yazildi", "ortak.txt", "ece")
g82 = ofis.tahta.incelemeye_ver(g82["no"], ofis.tahta.gorev(g82["no"])["revizyon"])
ofis.tahta.kapat(g82["no"], g82["revizyon"], kapatan="lale")
_t0 = time.time()
while time.time() - _t0 < 30 and G.teslim_durumu(db, ofis.proje_id, g82["no"]).get("durum") != "cakisti":
    time.sleep(0.25)
sina("cakisan isin durumu KAYDEDILDI (kart ve kabuk gorur)", G.teslim_durumu(db, ofis.proje_id, g82["no"]).get("durum") == "cakisti")
# cakisma cozuldu: isin kaydi son kodun ustune elle tasindi
git(kok, "fetch", "-q", "origin")
git(kok, "reset", "-q", "--hard", "origin/main")
Path(kok, "ortak.txt").write_text("satir 1 -- yine calisan ofis + isin degisikligi\n", encoding="utf-8")
git(kok, "commit", "-qam", f"#{g82['no']} cakisan is (cozuldu)")
_ys82 = G.yeniden_sina(db, ofis.proje_id, g82["no"])
sina("  cozulunce `gelistirme sina` bastan yurutur: sinama + KART", _ys82.get("durum") == "kart", str(_ys82.get("durum")))
# is basinda esitleme
(KAY / "is_basi.txt").write_text("son kod\n", encoding="utf-8")
git(KAY, "add", "-A")
git(KAY, "commit", "-qm", "is basinda gelmesi gereken kod")
G.is_basinda(db, ofis.proje_id, kok, {"no": 99, "id": None})
sina("is basinda kopya son koda esitlendi", Path(kok, "is_basi.txt").is_file())
_kt = (OFIS_KODU / "ofis" / "koltuk.py").read_text(encoding="utf-8")
sina("  koltuk yeni iste cagiriyor, ayni kopyada suren baska is varsa DOKUNMUYOR",
     "self._gelistirme_is_basi(gorev)" in _kt and 'g["durum"] in ("calisiyor", "inceleme")' in _kt)

print("\n16. sinama KAYDIN ayri agacinda (kopyada suren is sinamaya karismaz)")
Path(kok, "testler", "duman_kirli.py").write_text("import sys\nprint('  [KALDI] kaydedilmemis is')\nsys.exit(1)\n", encoding="utf-8")
Path(kok, "testler", "duman_ornek.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")   # kayitli dosya diskte bozuldu
_ks = G.kayit_sinamasi(kok)
sina("kopyadaki KAYDEDILMEMIS degisiklik sinamaya girmedi (yalniz kayit sinandi)", _ks.get("tamam"), str(_ks.get("kotu"))[:200])
_wt = git(kok, "worktree", "list")
sina("  gecici agac silindi (worktree listesinde yalniz kopya)", len(_wt.splitlines()) == 1, _wt)
git(kok, "checkout", "--", "testler/duman_ornek.py")
Path(kok, "testler", "duman_kirli.py").unlink()

print("\n17. kurulum sinanan ICERIGI kurar (hash degisse de); icerik degistiyse KURMAZ (10.10 canli: bad object)")
git(kok, "fetch", "-q", "origin")
git(kok, "reset", "-q", "--hard", "origin/main")
n17 = is_kapat("tabani degisecek is", "is17.py", "print(17)\n")
d17 = bekle(n17)
sina("(sahne) kart acildi", d17.get("durum") == "kart", str(d17.get("durum")))
_h_once = d17["kayitlar"][0]["commit"]
(KAY / "sonradan.txt").write_text("x\n", encoding="utf-8")
git(KAY, "add", "-A")
git(KAY, "commit", "-qm", "calisan ofise sinamadan sonra giren kayit")
G.esitle(kok)                                     # is basi esitlemesi gibi: yeni taban, yeni hash
_h_simdi = G._isin_kayitlari(kok, n17)[0]["commit"]
sina("(sahne) esitleme kaydin hash'ini DEGISTIRDI", _h_once != _h_simdi)
sina("  yama kimligi AYNI", G._yama_kimligi(kok, _h_once) == G._yama_kimligi(kok, _h_simdi) is not None)
_kd = G.kur(ofis, n17)
sina("  kurulum GUNCEL kaydi kurdu (eskiden: bad object)", _kd.get("durum") == "kuruldu" and (KAY / "is17.py").is_file(), str(_kd.get("durum")))
n18 = is_kapat("icerigi degisecek is", "is18.py", "print(18)\n")
d18 = bekle(n18)
Path(kok, "is18.py").write_text("print('sinanmamis')\n", encoding="utf-8")
git(kok, "commit", "-qam", f"#{n18} sinamadan sonra degisiklik")
try:
    G.kur(ofis, n18)
    sina("  sinamadan SONRA degisen icerik KURULMAZ", False)
except G.GelistirmeHatasi as _e:
    sina("  sinamadan SONRA degisen icerik KURULMAZ", "SINAMADAN SONRA" in str(_e) and not (KAY / "is18.py").exists(), str(_e)[:160])
G.reddet(ofis, n18)
sina("  ret GUNCEL kayitlari geri aldi", not Path(kok, "is18.py").exists())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
