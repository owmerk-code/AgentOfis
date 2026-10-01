# -*- coding: utf-8 -*-
"""MOTOR SAGLIK HAFIZASI (E16) + TEK KOK duman testi. Gercek motor KOSMAZ.

Sinanan:
 1. Tek kok (`ofis/yollar.py`): butun calisma durumu `OFIS_EV` altinda;
    kodda ikinci bir `~/.agentofis` sabiti yok (lint).
 2. Bekci (`_temizlik`): sinama kullanicinin GERCEK hafizasina yazarsa
    sessiz kalinmaz (sahte bir ev klasoruyle, alt surecte).
 3. `motor_saglik`: kayit, parmak izi degisince kendiliginden duser.
 4. Claude adaptoru: hesap hatasi (`error` alani) -> `oturum_kapandi`,
    hatirlanir, `musait_mi` duser; `rate_limit` limit sayilir, hatirlanmaz;
    gecici hata hatirlanmaz. Giris olcumu onbellekli, bilinmeyen engellemez.
 5. Codex ayni hafizayi kullanir; iki motorun kayitlari karismaz.
 6. Zincir elenen basamagin GERCEK sebebini soyler.
 7. Koltuk oturum dusunce AYNI turda devreder; siradan hata devretmez.
 8. Lider devri oturum dusmesinde de calisir, sebebi dogru yazar.
 9. Saglik: kurulu ama kullanilamayan motor + DOLU hesap gorunur.
10. Yetenek ve hesap ekrani motorun kendi teshisini gosterir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorler + tek kok (E05, E16); ILK

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

KOK_DIZIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK_DIZIN))
for akis in (sys.stdout, sys.stderr):
    try:
        akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Claude'un yapilandirma dizini SINAMANIN: parmak izi kullanicinin gercek
# `~/.claude/.credentials.json`una bakmasin.
CLAUDE_DIZIN = Path(tempfile.mkdtemp(prefix="ofis-claudecfg-"))
(CLAUDE_DIZIN / ".credentials.json").write_text("{}", encoding="utf-8")
os.environ["CLAUDE_CONFIG_DIR"] = str(CLAUDE_DIZIN)

from ofis import Ofis, Veritabani, Koltuk, yollar, motor_saglik  # noqa: E402
from ofis import kullanim, hesap, yetenek                          # noqa: E402
from ofis.motor import MotorHatasi, motor_kaydet                   # noqa: E402
from ofis.motor import claude as CL, codex as CX                   # noqa: E402
from ofis.motor.sahte import SahteMotor                            # noqa: E402
from ofis.saglik import Saglik                                     # noqa: E402
from ofis.zincir import elenenler, limitte_devret, lider_devri     # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== motor saglik hafizasi + tek kok ==\n")

# KOSMAYI REDDET: bu sinama codex evine `auth.json` yazar. Kok gercek
# olsaydi kullanicinin GERCEK codex girisinin ustune yazardi. Kokun gecici
# olduguna guvenmek yetmez -- olculur, degilse hic baslanmaz.
if yollar.gercek_ev_mi() or not str(yollar.OFIS_EVI).startswith(
        str(Path(tempfile.gettempdir()).resolve())):
    print(f"  [KALDI] kok GERCEK ya da gecici degil ({yollar.OFIS_EVI}) -- "
          "sinama KOSMUYOR (gercek girisin ustune yazardi)")
    sys.exit(2)

# ------------------------------------------------------------------ 1
print("1. TEK KOK -- butun calisma durumu OFIS_EV altinda")
ev = Path(os.environ["OFIS_EV"]).resolve()
sina("sinamada kok GECICI (gercek degil)",
     yollar.OFIS_EVI == ev and not yollar.gercek_ev_mi(), str(yollar.OFIS_EVI))
from ofis import gorsel, baglayici, gizli, yedek, depo, geri_al     # noqa: E402
sabitler = {
    "gorsel.KOTA_DEFTERI": gorsel.KOTA_DEFTERI,
    "gorsel.AYAR_DEFTERI": gorsel.AYAR_DEFTERI,
    "baglayici.SORUN_DEFTERI": baglayici.SORUN_DEFTERI,
    "motor_saglik.DEFTER": motor_saglik.DEFTER,
    "codex.OTURUM_DEFTERI": CX.OTURUM_DEFTERI,
    "codex ofis evi": Path(CX.CodexMotoru._ev_bul()),
    "gizli.VARSAYILAN_DEPO": gizli.VARSAYILAN_DEPO,
    "yedek.VARSAYILAN_AYAR": yedek.VARSAYILAN_AYAR,
    "depo.VARSAYILAN_AYAR": depo.VARSAYILAN_AYAR,
    "geri_al.VARSAYILAN_GOLGE_KOK": geri_al.VARSAYILAN_GOLGE_KOK,
}
disarida = [a for a, y in sabitler.items() if not str(Path(y).resolve()).startswith(str(ev))]
sina("hafiza/kasa/ev sabitlerinin HEPSI tek kokte", not disarida, str(disarida))
sina("codex hafizasi TEK deftere bagli (motor_saglik)",
     CX.OTURUM_DEFTERI == motor_saglik.DEFTER)
# LINT: ikinci bir `~/.agentofis` kurulusu olmamali -- kopya, bir gun
# yonlendirilmeyi unutulan sabittir (tam olarak duman_gorsel'de olan).
kopya = []
for dosya in (KOK_DIZIN / "ofis").rglob("*.py"):
    if dosya.name == "yollar.py":
        continue
    for i, satir in enumerate(dosya.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r'/\s*"\.agentofis"', satir) and not satir.lstrip().startswith("#"):
            kopya.append(f"{dosya.relative_to(KOK_DIZIN)}:{i}")
sina("kodda ikinci bir ~/.agentofis kurulusu YOK", not kopya, str(kopya))
den = (KOK_DIZIN / "testler" / "deneme.py").read_text(encoding="utf-8")
sina("deneme seti GERCEK kokle kosar (kok _temizlik'ten ONCE sabitlenir)",
     0 < den.find('setdefault("OFIS_EV"') < den.find("import _temizlik"))

# ------------------------------------------------------------------ 2
print("\n2. BEKCI -- sinama gercek hafizaya yazarsa SESSIZ kalinmaz")
sahte_ev = Path(tempfile.mkdtemp(prefix="ofis-sahtehome-"))
ortam = {k: v for k, v in os.environ.items() if k not in ("OFIS_EV", "OFIS_GOLGE_KOK")}
ortam.update(USERPROFILE=str(sahte_ev), HOME=str(sahte_ev), PYTHONIOENCODING="utf-8",
             # Yeni ev de SAHTE (01.10.2026): gercek `AgentOfis\ev` asla yazilmaz.
             OFIS_YENI_EV=str(sahte_ev / "yeni-ev"))
yol_t = str(KOK_DIZIN / "testler")


def alt(kod: str):
    return subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {yol_t!r}); "
                           "import _temizlik, os; " + kod],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=ortam, timeout=120)


# (a) TASIMADAN ONCE: gercek ev eski yerde (`~/.agentofis`).
(sahte_ev / ".agentofis").mkdir()
r = alt("p = os.path.join(os.path.expanduser('~'), '.agentofis'); "
        "os.makedirs(p, exist_ok=True); open(os.path.join(p, 'kota.json'), 'w').write('{}')")
sina("gercek hafizaya yazan sinama BASARISIZ sayilir (kod 3)", r.returncode == 3,
     f"rc={r.returncode} {r.stderr[-200:]}")
sina("hangi dosya oldugu SOYLENIR", "[GERCEK HAFIZA]" in r.stderr and "kota.json" in r.stderr,
     r.stderr[-200:])
# (b) TASIMADAN SONRA: gercek ev yeni yerde (`AgentOfis\ev`); bekci ONU izler.
(sahte_ev / "yeni-ev").mkdir()
r = alt("p = os.environ['OFIS_YENI_EV']; open(os.path.join(p, 'motor_saglik.json'), 'w').write('{}')")
sina("tasimadan sonra YENI eve yazan sinama da yakalanir (kod 3)",
     r.returncode == 3 and "motor_saglik.json" in r.stderr, f"rc={r.returncode} {r.stderr[-200:]}")
r = alt("pass")
sina("yazmayan sinama temiz gecer (her seye alarm vermez)", r.returncode == 0,
     f"rc={r.returncode} {r.stderr[-200:]}")

# ------------------------------------------------------------------ 3
print("\n3. HAFIZA -- kayit, parmak izi degisince KENDILIGINDEN duser")
dosya = Path(tempfile.mkdtemp(prefix="ofis-kimlik-")) / "auth.json"
dosya.write_text("{}", encoding="utf-8")
pi = motor_saglik.parmak_izi_dosya(dosya)
sina("kayit yokken olu DEGIL", motor_saglik.olu_kaydi("x", "k", pi) is None)
motor_saglik.olu_yaz("x", "k", pi, "billing_error")
k = motor_saglik.olu_kaydi("x", "k", pi)
sina("kayit okunuyor, kategori korunuyor", bool(k) and k["kategori"] == "billing_error")
sina("insana ne oldugunu soyluyor", "abonelik" in motor_saglik.kayit_metni("x", k, "CARE")
     and "CARE" in motor_saglik.kayit_metni("x", k, "CARE"))
time.sleep(0.02)
dosya.write_text('{"yeni": 1}', encoding="utf-8")        # yeniden giris
sina("yeniden giris (parmak izi degisti) -> kayit DUSER",
     motor_saglik.olu_kaydi("x", "k", motor_saglik.parmak_izi_dosya(dosya)) is None)
sina("anahtar parmak izi degerin kendisini TASIMAZ",
     "GIZLI123" not in motor_saglik.parmak_izi_anahtar("GIZLI123"))
bozuk = Path(tempfile.mkdtemp(prefix="ofis-bozuk-")) / "dosya"
bozuk.write_text("x", encoding="utf-8")
try:
    motor_saglik.olu_yaz("x", "k", pi, "billing_error", defter=bozuk / "alt.json")
    sina("yazilamayan defter isi DURDURMAZ", True)
except Exception as exc:
    sina("yazilamayan defter isi DURDURMAZ", False, str(exc))

# ------------------------------------------------------------------ 4
print("\n4. CLAUDE ADAPTORU -- sahte `claude` surecine karsi")
SAHTE = r'''
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
SEN = json.load(open(os.path.join(os.path.dirname(__file__), "senaryo.json"), encoding="utf-8"))
sys.stdin.read()
def yaz(m):
    sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
yaz({"type": "system", "subtype": "init", "session_id": "s-1", "model": "claude-sinama"})
hata = SEN.get("hata")
m = {"type": "assistant", "message": {"content": [{"type": "text", "text": SEN["metin"]}]}}
if hata:
    m["error"] = hata
yaz(m)
yaz({"type": "result", "subtype": "success", "is_error": bool(hata), "result": SEN["metin"],
     "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1}})
sys.exit(1 if hata else 0)
'''
skl = Path(tempfile.mkdtemp(prefix="ofis-sahteclaude-"))
(skl / "sahte_claude.py").write_text(SAHTE, encoding="utf-8")
calisma = Path(tempfile.mkdtemp(prefix="ofis-claudetur-"))
_gercek_popen, _gercek_run = subprocess.Popen, subprocess.run
GIRIS = {"loggedIn": True, "n": 0, "patla": False}


def _sahte_run(komut, **kw):
    GIRIS["n"] += 1
    if GIRIS["patla"]:
        raise subprocess.TimeoutExpired(komut, 20)
    return types.SimpleNamespace(stdout=json.dumps({"loggedIn": GIRIS["loggedIn"],
                                                    "email": "sinama@ornek",
                                                    "subscriptionType": "max"}),
                                 returncode=0)


def kos(hata, metin="tamam"):
    (skl / "senaryo.json").write_text(json.dumps({"hata": hata, "metin": metin}),
                                      encoding="utf-8")
    CL.subprocess.Popen = lambda komut, **kw: _gercek_popen(
        [sys.executable, str(skl / "sahte_claude.py")], **kw)
    try:
        ol = list(CL.ClaudeMotoru(calistirilabilir="claude", zaman_asimi=30).tur_kos(
            "gorev", klasor=str(calisma), model="haiku"))
    finally:
        CL.subprocess.Popen = _gercek_popen
    return ol, ol[-1].ek


CL.subprocess.run = _sahte_run
try:
    m = CL.ClaudeMotoru(calistirilabilir="claude")
    CL.ClaudeMotoru._giris_onbellek.clear()
    sina("girisli + kayit yok -> MUSAIT", m.musait_mi() is True and m.durum_notu() == "")
    n = GIRIS["n"]
    m.musait_mi(); m.musait_mi()
    sina("giris olcumu ONBELLEKLI (tekrar sorulmuyor)", GIRIS["n"] == n, f"{n}->{GIRIS['n']}")
    m.giris_durumu(tazele=True)
    sina("tazele=True yeniden olcer", GIRIS["n"] == n + 1)

    GIRIS["loggedIn"] = False
    m.giris_durumu(tazele=True)
    sina("giris YOK -> musait DEGIL, care `claude auth login`",
         m.musait_mi() is False and "claude auth login" in m.durum_notu(), m.durum_notu())
    GIRIS["loggedIn"], GIRIS["patla"] = True, True
    m.giris_durumu(tazele=True)
    sina("olculemeyen giris ENGELLEMEZ (bilinmeyene 'yok' denmez)",
         m.giris_durumu()["girisli"] is None and m.musait_mi() is True)
    GIRIS["patla"] = False
    m.giris_durumu(tazele=True)

    ol, ek = kos("authentication_failed", "Not logged in - Please run /login")
    sina("hesap hatasi -> basarisiz, sebep 'oturum_kapandi'",
         ek.get("basarili") is False and ek.get("sebep") == "oturum_kapandi", str(ek)[:160])
    h = [o for o in ol if o.tur == "hata"]
    sina("hata olayi KATEGORIYI tasiyor ve careyi soyluyor",
         bool(h) and h[0].ek.get("kategori") == "authentication_failed"
         and "claude auth login" in h[0].govde, h[0].govde[:160] if h else "yok")
    sina("limit SAYILMADI (beklemek ise yaramaz)", ek.get("limit") is False)
    sina("HATIRLANDI: musait_mi artik False", m.musait_mi() is False, m.durum_notu()[:120])
    sina("durum notu ne oldugunu ve ne zaman olculdugunu soyluyor",
         "oturum kapanmis" in m.durum_notu() and "dk once" in m.durum_notu())
    time.sleep(0.02)
    (CLAUDE_DIZIN / ".credentials.json").write_text('{"yeni": 1}', encoding="utf-8")
    sina("yeniden giris -> kayit kendiliginden DUSER, musait", m.musait_mi() is True,
         m.durum_notu()[:120])

    # Metin "rate limit" ICERMEZ: adaptor o kelimeyi sonuc metninde de arar;
    # icerseydi `error` alanini okumayan kod da bu sinamayi gecerdi.
    ol, ek = kos("rate_limit", "yavasla")
    sina("`rate_limit` LIMIT sayilir", ek.get("limit") is True)
    sina("limit HESAP SORUNU diye hatirlanmaz", m.musait_mi() is True)
    ol, ek = kos("overloaded", "overloaded")
    sina("gecici hata (overloaded) hatirlanmaz, limit de degil",
         m.musait_mi() is True and ek.get("limit") is False
         and ek.get("sebep") != "oturum_kapandi", str(ek)[:120])
    ol, ek = kos(None, "tamam")
    sina("hatasiz tur BASARILI (tersi yok)", ek.get("basarili") is True, str(ek)[:120])
finally:
    CL.subprocess.run = _gercek_run
    CL.ClaudeMotoru._giris_onbellek.clear()

# ------------------------------------------------------------------ 5
print("\n5. CODEX -- AYNI hafiza, kayitlar karismaz")
cx_ev = Path(CX.CodexMotoru._ev_bul())
cx_ev.mkdir(parents=True, exist_ok=True)
cx = CX.CodexMotoru(calistirilabilir="codex")
sina("girissiz ev -> durum notu 'giris YOK' + care", "giris YOK" in cx.durum_notu()
     and "codex login" in cx.durum_notu(), cx.durum_notu()[:100])
(cx_ev / "auth.json").write_text("{}", encoding="utf-8")
sina("girisli ev -> musait", cx.musait_mi() is True and cx.durum_notu() == "")
CX.oturum_olu_yaz(str(cx_ev))
defter = json.loads(motor_saglik.DEFTER.read_text(encoding="utf-8"))
sina("codex kaydi TEK deftere dustu (codex: onekiyle)",
     any(a.startswith("codex:") for a in defter), str(list(defter)))
sina("olu oturum -> musait DEGIL, 401 metni", cx.musait_mi() is False
     and "token_revoked" in cx.durum_notu())
sina("ayni kimlik baska MOTOR adina okunmaz (anahtar motorla ayrilir)",
     motor_saglik.olu_kaydi("claude", CX._ev_anahtari(str(cx_ev)),
                            CX._parmak_izi(str(cx_ev))) is None
     and motor_saglik.olu_kaydi("codex", CX._ev_anahtari(str(cx_ev)),
                                CX._parmak_izi(str(cx_ev))) is not None)
time.sleep(0.02)
(cx_ev / "auth.json").write_text('{"yeni": 1}', encoding="utf-8")
sina("codex yeniden giris -> kayit duser", cx.musait_mi() is True)

# ------------------------------------------------------------------ 6-10 sahnesi
kok = Path(tempfile.mkdtemp(prefix="ofis-msaglik-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Saglik", amac="a", basari_olcutu="b", kok_klasor=str(kok))
kanat = ofis.kanat_ac("ANA", "AN")


class OluMotor(SahteMotor):
    """Kurulu ama KULLANILAMAYAN motor (girissiz)."""
    ad = "olumotor"
    calistirilabilir = "olumotor.exe"

    def musait_mi(self):
        return False

    def durum_notu(self):
        return "olumotor'a giris YOK -- `olumotor login`"


motor_kaydet(OluMotor)
ofis.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=kanat, motor="sahte",
                  model="sonnet", klasor=str(kok))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kanat, motor="sahte", model="opus",
                  klasor=str(kok))
ofis.kadro.ise_al("ruzgar", "backend", kanat_id=kanat, motor="olumotor", model="x",
                  klasor=str(kok))

# ------------------------------------------------------------------ 6
print("\n6. ZINCIR -- elenen basamagin GERCEK sebebi")
el = elenenler(ofis.kadro.ajan("ruzgar"), zincir=[("sahte", "")],
               fabrika=lambda ad, **a: OluMotor() if ad == "olumotor" else SahteMotor())
sebep = next((e["sebep"] for e in el if e["motor"] == "olumotor"), "")
sina("sebep motorun kendi teshisi ('giris YOK'), 'kurulu degil' DEGIL",
     "giris YOK" in sebep and "kurulu degil" not in sebep, sebep)

# ------------------------------------------------------------------ 7
print("\n7. KOLTUK -- oturum dusunce AYNI turda devreder")
kosanlar = []


class DusenMotor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        model = ayar.get("model") or ""
        kosanlar.append(model)
        self.senaryo = "hata" if model in ("opus", "tek") else "basarili"
        for o in super().tur_kos(metin, **ayar):
            if o.tur == "bitti" and model == "opus":
                o.ek["sebep"] = "oturum_kapandi"
            yield o


def dusen_fabrika(ad, **a):
    if ad != "sahte":
        raise MotorHatasi(f"Bilinmeyen motor: {ad}")
    return DusenMotor(cevap="Bitti." + chr(10) + "KANIT terminal: pytest -q -> 3 passed")


koltuk = Koltuk(ofis, motor_fabrikasi=dusen_fabrika, zincir=[("sahte", "haiku")])
g = ofis.tahta.gorev_ac("Devir", neden="n", ana_hedef="h", kabul_olcutu="k",
                        yazma_alani=["a/"], kanat_id=kanat)
ol = list(koltuk.akit(g["no"], "cinar", zaman_asimi=5))
sina("ONCE opus, oturum dustu, SONRA baska basamak",
     kosanlar[:2] == ["opus", "haiku"], str(kosanlar))
lim = [o for o in ol if o["tur"] == "limit"]
sina("devir GORUNUR ve sebebi 'KULLANILAMIYOR'", bool(lim)
     and "KULLANILAMIYOR" in lim[0]["govde"], lim[0]["govde"] if lim else "yok")
sina("is AYNI turda bitti, incelemede",
     ofis.tahta.gorev(g["no"])["durum"] == "inceleme")
kar = [k for k in ofis.bellek.son_kararlar(10) if "ile kosuldu" in k["karar"]]
sina("devir kararinin gerekcesi 'kullanilamaz'",
     bool(kar) and "kullanilamaz" in kar[0]["gerekce"].lower(), str(kar[:1])[:160])
kosanlar.clear()
ofis.kadro.motor_ayarla("cinar", model="tek")
g2 = ofis.tahta.gorev_ac("Siradan", neden="n", ana_hedef="h", kabul_olcutu="k",
                         yazma_alani=["b/"], kanat_id=kanat)
list(koltuk.akit(g2["no"], "cinar", zaman_asimi=5))
sina("SIRADAN hata devretmez (tek kosu)", kosanlar == ["tek"], str(kosanlar))

# ------------------------------------------------------------------ 8
print("\n8. LIDER DEVRI -- oturum dusmesinde de")
devirler = []


def _kos_lider(b):
    return ({"basarili": False, "sebep": "oturum_kapandi"} if b["motor"] == "a"
            else {"basarili": True}), []


s = limitte_devret([{"motor": "a"}, {"motor": "b"}], _kos_lider,
                   devir=lambda e, y: devirler.append((e, y)))
sina("oturum dusen lider sonraki motora gecti", s[0]["motor"] == "b" and len(devirler) == 1)
sina("devir SEBEBI tasiniyor", bool(devirler)
     and "KULLANILAMIYOR" in devirler[0][0].get("devir_nedeni", ""))
devirler.clear()
limitte_devret([{"motor": "a"}, {"motor": "b"}],
               lambda b: ({"basarili": False, "sebep": "cikis"}, []),
               devir=lambda e, y: devirler.append(1))
sina("siradan hata lideri devretmez", not devirler)
lider_devri(ofis, ofis.kadro.ajan("lale"), dict({"motor": "a"}, devir_nedeni="hesabi KULLANILAMIYOR (x)"),
            {"motor": "b"})
with db.baglanti() as c:
    lo = [r[0] for r in c.execute("SELECT govde FROM olay WHERE proje_id=? AND tur='limit' "
                                  "AND ajan_ad='lale'", (ofis.proje_id,))]
sina("lider devir olayi dogru sebebi yazar", any("KULLANILAMIYOR" in x for x in lo), str(lo))

# ------------------------------------------------------------------ 9
print("\n9. SAGLIK -- kullanilamayan motor ve DOLU hesap gorunur")
sag = Saglik(ofis).denetle()["bulgular"]
b = [x for x in sag if "olumotor" in x["baslik"]]
sina("kurulu ama kullanilamayan motor: INSAN bulgusu, motorun kendi teshisi",
     bool(b) and b[0]["agirlik"] == "insan" and "giris YOK" in b[0]["ayrinti"],
     str(b[:1])[:200])
sina("kurulu DEGIL diye yanlis gostermiyor", not any("kurulu degil" in x["baslik"]
                                                      and "olumotor" in x["baslik"] for x in sag))
gelecek = int(time.time()) + 3 * 3600
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"basarili": False, "limit": True, "limit_pencere": {
    "kaynak": "sinama", "hal": "rejected", "plan": "",
    "pencereler": {"5s": {"kullanim": 1.0, "yenilenme": gelecek}}}}, ajan_ad="cinar", motor="sahte")
dolu = [x for x in Saglik(ofis).denetle()["bulgular"] if "DOLU" in x["baslik"]]
sina("DOLU hesap uyari olarak gorunur, yenilenme yazili",
     bool(dolu) and dolu[0]["agirlik"] == "uyari" and "Yenilenme" in dolu[0]["ayrinti"],
     str(dolu[:1])[:200])
time.sleep(1.1)
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"basarili": True, "limit_pencere": {
    "kaynak": "sinama", "hal": "allowed", "plan": "",
    "pencereler": {"5s": {"kullanim": 0.5, "yenilenme": gelecek}}}}, ajan_ad="cinar", motor="sahte")
sina("yeni olcum %50 -> DOLU bulgusu KALKAR (her seye alarm yok)",
     not [x for x in Saglik(ofis).denetle()["bulgular"] if "DOLU" in x["baslik"]])
gecmis = int(time.time()) - 60
time.sleep(1.1)
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"basarili": False, "limit_pencere": {
    "kaynak": "sinama", "hal": "rejected", "plan": "",
    "pencereler": {"5s": {"kullanim": 1.0, "yenilenme": gecmis}}}}, ajan_ad="cinar", motor="sahte")
sina("YENILENMIS pencere dolu sayilmaz",
     not [x for x in Saglik(ofis).denetle()["bulgular"] if "DOLU" in x["baslik"]])

# ------------------------------------------------------------------ 10
print("\n10. YETENEK ve HESAP -- motorun kendi teshisi")
sat = [x for x in yetenek._motorlar() if x["ad"] == "olumotor"]
sina("yetenek: kurulu ama kullanilamayan motor DAR (YOK degil)",
     bool(sat) and sat[0]["durum"] == yetenek.DAR, str(sat))
sina("yetenek: care motorun kendi sozu", bool(sat) and "giris YOK" in sat[0].get("care", ""),
     str(sat))
hesap.ekle(db, ofis.proje_id, "saglam", "sahte")
hesap.ekle(db, ofis.proje_id, "olu", "olumotor")
hs = {x["ad"]: x for x in yetenek._hesaplar(db, ofis.proje_id)}
sina("yetenek: saglam hesap HAZIR ('olur' anahtari -- eskiden hep DAR)",
     hs.get("saglam", {}).get("durum") == yetenek.HAZIR, str(hs.get("saglam")))
sina("yetenek: olu hesap DAR + motorun teshisi",
     hs.get("olu", {}).get("durum") == yetenek.DAR
     and "giris YOK" in hs.get("olu", {}).get("care", ""), str(hs.get("olu")))
k = hesap.kullanilabilir_mi(next(h for h in hesap.liste(db, ofis.proje_id) if h["ad"] == "olu"))
sina("hesap.kullanilabilir_mi sebebi motorun teshisi", k["olur"] is False
     and "giris YOK" in k["sebep"], str(k))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
