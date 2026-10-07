# -*- coding: utf-8 -*-
"""GUVENLI SIFIRLAMA (08.10.2026). Jeton yakmaz; her sey gecici klasorde.

Sinanan: plan HICBIR SEY silmez ve korunanlari (kadro, ayar, giris, kadrodaki
ajanin evi, patronun dosyasi, patronun baska Claude projeleri, kod deposunun
kendi kaydi) listelemez; yanlis onay, mesgul ofis ve dogrulanmayan yedek
HICBIR SEY silmez; dogru onayda once yedek alinir, sonra yalniz plan silinir;
yeni yedek kalir; Codex'in var olan klasore guveni kalir; ev ya da masaustu
kok olarak yazilsa bile Claude eslesmesi patronun projelerine tasmaz; panel
ve kabuk.
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

from ofis import Ofis, Veritabani  # noqa: E402
from ofis import sifirla as S  # noqa: E402
from ofis import yedek as Y  # noqa: E402
from ofis.yollar import OFIS_KODU, ofis_evi  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def yaz(p: Path, metin: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(metin, encoding="utf-8")
    return p


EV = ofis_evi()
sina("ev gecici klasorde (gercek eve dokunulmaz)",
     Path(tempfile.gettempdir()).resolve() in EV.resolve().parents, str(EV))
d = Path(tempfile.mkdtemp(prefix="ofis-sifirla-"))
kok = d / "Proje"
kok.mkdir()
db = Veritabani(d / "veri" / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Sifir", amac="a", basari_olcutu="b", kok_klasor=str(kok))
KA = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("ece", "arayuz", kanat_id=KA, motor="sahte", klasor=str(kok))
P = ofis.proje_id
g = ofis.tahta.gorev_ac("deneme isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
db.olay_yaz(P, "uyari", "deneme olayi")
ofis.bellek.bilgi_ekle("deneme konusu", "deneme degeri", yazan="insan")
db.ayar_yaz(P, "terminal_kipi", "gercek") if hasattr(db, "ayar_yaz") else None

# Ev: karne, eksik, brifing, golge, arsiv, ajan evleri, codex, kabin gunlugu.
yaz(EV / "karne.jsonl", '{"meslek": "arayuz"}\n')
yaz(EV / "ofis_eksikleri.jsonl", '{"baslik": "x"}\n')
yaz(EV / "brifing" / "abc" / "lale.md")
from ofis.geri_al import golge_koku  # noqa: E402
yaz(golge_koku() / "eski.git" / "HEAD")
_nesne = yaz(golge_koku() / "eski.git" / "objects" / "ab" / "cdef")
os.chmod(_nesne, 0o444)          # git nesneleri Windows'ta salt okunur (olculdu 08.10)
yaz(EV / "arsiv" / "eski-kok" / "a.txt")
yaz(EV / "gemini_ev" / "ada" / ".gemini" / "x.json")              # kadroda yok
yaz(EV / "gemini_ev" / "ece" / ".gemini" / "oauth_creds.json")    # kadroda: KALIR
yaz(EV / "gemini_ev" / "_ortak" / ".gemini" / "antigravity-cli" / "brain" / "k.md")
yaz(EV / "gemini_ev" / "_ortak" / ".gemini" / "antigravity-cli" / "settings.json")  # KALIR
yaz(EV / "codex" / "auth.json", "{}")                              # KALIR
yaz(EV / "codex" / "models_cache.json", "{}")                      # KALIR
yaz(EV / "codex" / "sessions" / "2026" / "r.jsonl")
yaz(EV / "codex" / "history.jsonl")
yok_klasor = d / "silinmis-gecici"
yaz(EV / "codex" / "config.toml",
    'model = "gpt-6.1-sol"\n\n'
    f"[projects.'{kok}']\ntrust_level = \"trusted\"\n\n"
    f"[projects.'{yok_klasor}']\ntrust_level = \"trusted\"\n\n"
    '[mcp_servers.ofis]\ncommand = "python"\n')
yaz(EV / "kabin.log", "gunluk satiri\n")
# Proje izleri ve patronun dosyasi.
yaz(kok / ".ofis" / "ekler" / "a.png")
yaz(kok / ".playwright-mcp" / "console.log")
patron = yaz(kok / "patronun-dosyasi.txt", "dokunma")
# Claude oturumlari.
CP = S.claude_projeler_koku()
sina("Claude klasoru gecici (gercege dokunulmaz)",
     Path(tempfile.gettempdir()).resolve() in CP.resolve().parents, str(CP))
gecici_oturum = yaz(CP / (S._kodla(Path(tempfile.gettempdir()).resolve()) + "-ofis-x-calisma") / "s.jsonl").parent
kok_oturum = yaz(CP / S._kodla(kok.resolve()) / "s.jsonl").parent
patron_proje = yaz(CP / "c--Users-pc-Desktop-HARMAN" / "s.jsonl").parent
depo_oturum = yaz(CP / S._kodla(OFIS_KODU).replace("C-", "c-", 1) / "s.jsonl").parent
ev_oturum = yaz(CP / S._kodla(Path.home()) / "s.jsonl").parent
# Yedekler: yerel, ek hedef, elle, defter kopyasi.
eski_zip = yaz(Y.yedek_koku() / (Y.AD_ONEKI + "20260926-000000-eski.zip"))
yaz(Y.yedek_koku() / (Y.AD_ONEKI + "20260927-000000-yeni.zip"))   # en yeni: KALIR
hedef = d / "drive"
eski_drive = yaz(hedef / (Y.AD_ONEKI + "20260926-000000-eski.zip"))
Y.ayar_yaz({"hedefler": [str(hedef)], "son": ""})
elle = yaz(EV / "yedek" / "elle" / "ofis-eski.sqlite3")
kopya = yaz(db.yol.parent / "ofis.sqlite3.yedek-20261001")

print("\n1. plan hicbir sey silmez, korunani listelemez")
pl = S.plan(ofis)
yollar = {Path(k["yol"]) for k in pl if k["yol"]}
ad = {k["ad"] for k in pl}
sina("defter gecmisi listede (gorev, olay)", {"defter: gorev", "defter: olay"} <= ad, str(ad))
sina("hafiza listede", "defter: olgu" in ad)
sina("kadro ve ayar listede DEGIL",
     not any(k.get("tablo") in ("ajan", "kanat", "proje", "ayar", "hesap", "kural", "izin") for k in pl))
for p, neden in ((EV / "gemini_ev" / "ada", "kadroda olmayan ajan evi"),
                 (EV / "codex" / "sessions", "codex oturumlari"),
                 (gecici_oturum, "gecici klasor Claude oturumu"), (kok_oturum, "proje koku Claude oturumu"),
                 (eski_zip, "eski yerel yedek"), (eski_drive, "eski Drive yedegi"), (elle, "elle yedek"),
                 (kopya, "defter kopyasi"), (kok / ".ofis", "proje .ofis"),
                 (kok / ".playwright-mcp", "proje tarayici dokumu")):
    sina(f"listede: {neden}", p in yollar)
for p, neden in ((EV / "gemini_ev" / "ece", "kadrodaki ajanin evi"), (EV / "codex" / "auth.json", "codex girisi"),
                 (EV / "codex" / "config.toml", "codex yapilandirmasi (yalniz guven kaydi ayiklanir)"),
                 (EV / "codex" / "models_cache.json", "codex model listesi"), (patron, "patronun dosyasi"),
                 (patron_proje, "patronun baska Claude projesi"), (depo_oturum, "kod deposunun kendi kaydi"),
                 (ev_oturum, "ev klasoru Claude kaydi"), (OFIS_KODU / ".playwright-mcp", "rakip dokumu")):
    sina(f"listede DEGIL: {neden}", p not in yollar or (neden.startswith("codex yap") and any(
        k["tur"] == "codex_guven" for k in pl)))
sina("codex guven: yalniz yok olan klasor", S.codex_bayat_guvenler() == [str(yok_klasor)],
     str(S.codex_bayat_guvenler()))
sina("plan sonrasi hepsi yerinde", all(p.exists() for p in yollar))
oz = S.ozet(pl)
sina("ozet kategori basina", set(oz) <= set(S.KATEGORILER) and all(o["kalem"] for o in oz.values()))

print("\n2. guvenlik: yanlis onay, mesgul ofis, dogrulanmayan yedek")
for kotu in ("", "sifirla", "EVET", "SIFIRLA!"):
    try:
        S.uygula(ofis, kotu, yedek_al=False)
        sina(f"yanlis onay reddedildi ({kotu!r})", False)
    except S.SifirlaHatasi:
        sina(f"yanlis onay reddedildi ({kotu!r})", all(p.exists() for p in yollar))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'calisiyor', kosan_surec = '' WHERE id = ?", (g["id"],))
try:
    S.uygula(ofis, "SIFIRLA", yedek_al=False)
    sina("mesgul ofis sifirlanmaz", False)
except S.SifirlaHatasi as exc:
    sina("mesgul ofis sifirlanmaz", "calisiyor" in str(exc) and all(p.exists() for p in yollar), str(exc))
with db.baglanti() as c:
    c.execute("UPDATE gorev SET durum = 'acik' WHERE id = ?", (g["id"],))
yk = d / "yedek-kaynak"
yaz(yk / "a.txt")
YS = {"kok": yk, "hedef_kok": Y.yedek_koku(), "ek_hedefler": [], "projeler": []}
_asil = Y.dogrula
Y.dogrula = lambda a: {"tamam": False, "bulgular": ["bozuk"]}
try:
    S.uygula(ofis, "SIFIRLA", yedek_secenek=YS)
    sina("dogrulanmayan yedek: hicbir sey silinmez", False)
except S.SifirlaHatasi as exc:
    sina("dogrulanmayan yedek: hicbir sey silinmez", all(p.exists() for p in yollar)
         and "HICBIR SEY SILINMEDI" in str(exc), str(exc))
Y.dogrula = _asil
try:
    S.uygula(ofis, "SIFIRLA", kategoriler=["yok-boyle"], yedek_al=False)
    sina("bilinmeyen kategori reddedilir", False)
except S.SifirlaHatasi:
    sina("bilinmeyen kategori reddedilir", True)

from ofis import guncelleme as G  # noqa: E402
G._kilit_al(db, P, "guncelleme-deneme")
try:
    S.uygula(ofis, "SIFIRLA", yedek_al=False)
    sina("guncelleme surerken sifirlanmaz", False)
except S.SifirlaHatasi as exc:
    sina("guncelleme surerken sifirlanmaz", "guncelleme" in str(exc) and all(p.exists() for p in yollar), str(exc))
G._kilit_birak(db, P, "guncelleme-deneme")

print("\n3. dogru onay: once yedek, sonra yalniz plan")
ajan_once = [a["ad"] for a in ofis.kadro.liste()]
r = S.uygula(ofis, "SIFIRLA", yedek_secenek=YS)
sina("yedek alindi ve dogrulandi", r["yedek"] and Y.dogrula(Path(r["yedek"]))["tamam"], str(r.get("yedek")))
sina("yeni yedek silinmedi", Path(r["yedek"]).exists())
sina("hata yok (salt okunur git nesnesi dahil)", not r["hatalar"] and not (golge_koku() / "eski.git").exists(),
     str(r["hatalar"]))
with db.baglanti() as c:
    sina("kilit birakildi", not c.execute("SELECT 1 FROM ayar WHERE anahtar = ?", (G.ANAHTAR_KILIT,)).fetchone())
with db.baglanti() as c:
    sayi = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("gorev", "mesaj", "olgu", "kuyruk", "karar")}
    olay = [x[0] for x in c.execute("SELECT tur FROM olay")]
sina("defter gecmisi bos", not any(sayi.values()), str(sayi))
sina("tek olay: sifirlandi", olay == ["sifirlandi"], str(olay))
sina("kadro aynen kaldi", [a["ad"] for a in ofis.kadro.liste()] == ajan_once)
sina("plandaki her sey gitti (bosaltilanlar bos)", all(
    (not p.exists()) or (p.is_dir() and not any(p.iterdir())) or (p.is_file() and p.stat().st_size == 0)
    or p.name == "config.toml" for p in yollar), str([str(p) for p in yollar if p.exists()][:5]))
for p, neden in ((EV / "gemini_ev" / "ece" / ".gemini" / "oauth_creds.json", "kadrodaki ajanin girisi"),
                 (EV / "gemini_ev" / "_ortak" / ".gemini" / "antigravity-cli" / "settings.json", "ortak ev ayari"),
                 (EV / "codex" / "auth.json", "codex girisi"), (EV / "codex" / "models_cache.json", "codex modelleri"),
                 (patron, "patronun dosyasi"), (patron_proje, "patronun Claude projesi"),
                 (depo_oturum, "kod deposu kaydi"), (ev_oturum, "ev klasoru kaydi"), (kok, "proje koku")):
    sina(f"YERINDE: {neden}", p.exists())
cfg = (EV / "codex" / "config.toml").read_text(encoding="utf-8")
sina("codex: var olan klasorun guveni ve MCP ayari kaldi, yok olanin gitti",
     str(kok) in cfg and "mcp_servers.ofis" in cfg and str(yok_klasor) not in cfg, cfg)
sina("karne bosaltildi", (EV / "karne.jsonl").read_text(encoding="utf-8") == "")
ikinci = [k for k in S.plan(ofis) if k["ad"] != "defter: olay"]
sina("ikinci plan bos: yeni yedek EN YENI oldugu icin kalir", not ikinci, str(ikinci)[:300])
yaz(Y.yedek_koku() / (Y.AD_ONEKI + "20260101-000000-cok-eski.zip"))
ikinci = [Path(k["yol"]).name for k in S.plan(ofis) if k["kategori"] == "yedekler"]
sina("en yeniden eski olan listede, en yeni degil",
     ikinci == [Y.AD_ONEKI + "20260101-000000-cok-eski.zip"], str(ikinci))

print("\n4. ev/masaustu kok yazilsa bile patronun projeleri eslesmez")
with db.baglanti() as c:
    c.execute("UPDATE kanat SET klasor = ?", (str(Path.home()),))
    c.execute("UPDATE ajan SET klasor = ? WHERE ad = 'ece'", (str(Path.home() / "Desktop"),))
sina("ev ve masaustu kok sayilmaz",
     not ({Path.home().resolve(), (Path.home() / "Desktop").resolve()} & set(S._ofis_kokleri(ofis))))
sina("patronun Claude projesi listede degil",
     not any(Path(k["yol"]) == patron_proje for k in S.plan(ofis)))

print("\n5. panel ve kabuk")
db.olay_yaz(P, "uyari", "yeni deneme")
from fastapi.testclient import TestClient  # noqa: E402
from ofis.panel import olustur  # noqa: E402
ist = TestClient(olustur(db.yol))
j = ist.get("/api/sifirla").json()
sina("panel listeyi veriyor", j["onay_metni"] == "SIFIRLA" and any(o["kategori"] == "gecmis" for o in j["ozet"]),
     json.dumps(j)[:300])
r = ist.post("/api/sifirla", json={"onay": "evet"})
sina("panel yanlis onay 400", r.status_code == 400)
with db.baglanti() as c:
    sina("panel yanlis onayda silmedi", c.execute("SELECT COUNT(*) FROM olay").fetchone()[0] >= 2)
kb = subprocess.run([sys.executable, "-m", "ofis.kabuk", "--db", str(db.yol), "--proje", "Sifir", "sifirla"],
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(OFIS_KODU), env=dict(os.environ))
sina("kabuk onaysiz yalniz liste", kb.returncode == 0 and "HICBIR SEY SILINMEDI" in kb.stdout,
     (kb.stdout + kb.stderr)[-300:])
with db.baglanti() as c:
    sina("kabuk listesi silmedi", c.execute("SELECT COUNT(*) FROM olay").fetchone()[0] >= 2)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
