# -*- coding: utf-8 -*-
"""DEVRAL / OFISE GERI VER (PLAN E18) -- jeton yakmadan.

Gercek terminal (Windows ConPTY) + sahte bir "CLI" (satir yankilar,
`/exit` ile duzgun cikar). Gercek claude/codex ile olcum ayri yapildi
(28.09.2026); burada KURALLAR sinanir:

1. Terminal: acilir, yazar, yankilar, gecmisi verir, DUZGUN kapanir, kafese girer.
2. Devral kapilari: ajana gitmemis is, bitmis is, KOSAN tur, devralinamayan motor REDDEDILIR.
3. Devral: is insanda -> koltuk REDDEDER, halka ATLAR (ve soyler), kilit DUSMEZ.
4. Geri ver: terminal duzgun kapanir, insanin degisikligi OLCULUR ("insan"),
   dokum deftere, not + dosyalar AJANA gider, kayit kalkar.
5. Panel: uclar + terminal WebSocket'i; yerel olmayan istemci REDDEDILIR.

Konsol cp1254 oldugu icin cikti ASCII.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, KoltukHatasi
from ofis import devral as DV
from ofis import terminal as TR
from ofis.motor.sahte import SahteMotor
from ofis.motor.tip import Motor

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


def bekle(kosul, sn=8.0):
    son = time.time() + sn
    while time.time() < son:
        if kosul():
            return True
        time.sleep(0.1)
    return False


_pty = TR.pty_durumu()
if _pty:
    print(f"  [ATLANDI] gercek terminal yok -- {_pty}. Devral OLCULMEDI.")
    print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
    sys.exit(0)

sahte_fab = lambda ad, **k: SahteMotor(**k)       # noqa: E731

# ------------------------------------------------------------------ 1
print("\n1. TERMINAL -- gercek ConPTY, sahte CLI")
k = SahteMotor().etkilesimli_komut()
t = TR.Terminal(k["argv"], klasor=tempfile.gettempdir(), ortam=k["ortam"],
                kapat_girdisi=k["kapat"])
sina("acildi ve hazir yazisi geldi", bekle(lambda: "SAHTE TERMINAL hazir" in t.dokum()),
     repr(t.dokum()[-200:]))
gelen = []
gecmis = t.dinle(gelen.append)
sina("dinle(): o ana kadarki GECMIS doner (yeniden baglanan ekran bos acilmaz)",
     "SAHTE TERMINAL" in TR.duz_metin(gecmis))
t.yaz("merhaba ofis\r")
sina("girdi yankilandi", bekle(lambda: "YANKI: merhaba ofis" in t.dokum()), repr(t.dokum()[-200:]))
sina("dinleyiciye canli veri aktı", bekle(lambda: any("YANKI" in (g or "") for g in gelen)))
t.boyutla(90, 20)
sina("kafese girdi (kapaninca alt surecler de biter)", t.kafes.kuruldu, t.kafes.hata)
sina("kapanis DUZGUN (/exit), zorla degil", t.kapat() == "duzgun")
sina("kapaninca dinleyiciye None (kapandi) gitti", bekle(lambda: None in gelen))
try:
    t.yaz("x")
    sina("kapali terminale yazma REDDEDILIR", False)
except TR.TerminalHatasi:
    sina("kapali terminale yazma REDDEDILIR", True)
sina("duz_metin renk kodunu atar", TR.duz_metin("\x1b[31mKIRMIZI\x1b[0m\r\n") == "KIRMIZI\n")

# ------------------------------------------------------------------ sahne
kok = Path(tempfile.mkdtemp(prefix="ofis-devral-"))
(kok / "a.txt").write_text("bir\n", encoding="utf-8")
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Devral", amac="a", basari_olcutu="b", kok_klasor=str(kok))
ofis.kadro.ise_al("lale", "lider", lider_mi=True, motor="sahte", klasor=str(kok))
ofis.kadro.ise_al("cinar", "backend", motor="sahte", klasor=str(kok))
g = ofis.tahta.gorev_ac("Devralinacak is", neden="n", ana_hedef="h",
                        kabul_olcutu="k", yazma_alani=["a.txt"])
no, gid = g["no"], g["id"]

# ------------------------------------------------------------------ 2
print("\n2. KAPILAR")
try:
    DV.devral(ofis, no, fabrika=sahte_fab)
    sina("hic ajana gitmemis is REDDEDILIR", False)
except DV.DevralHatasi as exc:
    sina("hic ajana gitmemis is REDDEDILIR", "ajana gitmedi" in str(exc), str(exc))

ofis.tahta.sahiplen(no, "cinar", ofis.tahta.gorev(no)["revizyon"])
ofis.kadro.oturum_kaydet("cinar", "OTURUM-42")
db.olay_yaz(ofis.proje_id, "oturum", "sahte", ajan_ad="cinar", gorev_id=gid)
db.olay_yaz(ofis.proje_id, "basladi", "tur", ajan_ad="cinar", gorev_id=gid)
ofis.tahta.nabiz(no)
try:
    DV.devral(ofis, no, fabrika=sahte_fab)
    sina("KOSAN tur varken REDDEDILIR (once Durdur)", False)
except DV.DevralHatasi as exc:
    sina("KOSAN tur varken REDDEDILIR (once Durdur)", "Durdur" in str(exc), str(exc))
db.olay_yaz(ofis.proje_id, "tur_ozeti", "{}", ajan_ad="cinar", gorev_id=gid)
sina("tur bitince artik kosuyor SAYILMAZ",
     not DV.tur_kosuyor_mu(db, ofis.proje_id, gid))


class Devralinamaz(Motor):
    ad = "yok"

    def musait_mi(self):
        return True

    def tur_kos(self, metin, **k):
        yield from ()


try:
    DV.devral(ofis, no, fabrika=lambda ad, **k: Devralinamaz())
    sina("terminal yolu bildirmeyen motor REDDEDILIR", False)
except DV.DevralHatasi as exc:
    sina("terminal yolu bildirmeyen motor REDDEDILIR", "devralinamiyor" in str(exc), str(exc))

# ------------------------------------------------------------------ 3
print("\n3. DEVRAL -- is insanda")
try:
    r = DV.devral(ofis, no, fabrika=sahte_fab)
except DV.DevralHatasi as exc:
    r = {}
    sina("devral CALISTI", False, str(exc))
sina("devral dondu, BU ISIN oturumu surdu", r.get("oturum") == "OTURUM-42", str(r))
sina("disk olculdu (insanin degisikligi de olculecek)", r.get("olcum") is True)
sina("kayit DEFTERDE", bool(DV.devralinmis(db, ofis.proje_id, gid)))
sina("terminal acik ve kayitli", bool(TR.al(gid)) and TR.al(gid)["terminal"].canli())
with db.baglanti() as c:
    sina("devral olayi yazildi", c.execute(
        "SELECT count(*) FROM olay WHERE tur='devral' AND gorev_id=?", (gid,)).fetchone()[0] == 1)
try:
    DV.devral(ofis, no, fabrika=sahte_fab)
    sina("ikinci kez devral REDDEDILIR", False)
except DV.DevralHatasi:
    sina("ikinci kez devral REDDEDILIR", True)
try:
    list(Koltuk(ofis, motor_fabrikasi=sahte_fab).akit(no, "cinar", zaman_asimi=10))
    sina("koltuk insandaki isi REDDEDER", False)
except KoltukHatasi as exc:
    sina("koltuk insandaki isi REDDEDER", "INSANDA" in str(exc), str(exc))
ozet = ofis.orkestra.tik()
sina("halka insandaki isi ATLAR ve SOYLER",
     any(isinstance(e, dict) and e.get("gorev_no") == no and "insan devraldi" in e.get("sebep", "")
         for e in ozet.get("engel", [])), str(ozet.get("engel"))[:300])
sina("halka o isi BASLATMADI", not ozet.get("baslatilan"))
with db.baglanti() as c:
    c.execute("UPDATE yazma_kilidi SET son_nabiz='2000-01-01T00:00:00+00:00' WHERE gorev_id=?", (gid,))
ofis.tahta.kilit_dusenleri_temizle()
with db.baglanti() as c:
    kalan = c.execute("SELECT count(*) FROM yazma_kilidi WHERE gorev_id=?", (gid,)).fetchone()[0]
sina("insan calisirken kilit kira yuzunden DUSMEZ (Yasa 1)", kalan >= 1, str(kalan))

# Insanin terminalde ve diskte yaptiklari
if TR.al(gid):
    TR.al(gid)["terminal"].yaz("insan burada\r")
    bekle(lambda: "YANKI: insan burada" in TR.al(gid)["terminal"].dokum())
(kok / "a.txt").write_text("bir\niki (insan)\n", encoding="utf-8")

# ------------------------------------------------------------------ 4
print("\n4. OFISE GERI VER")
try:
    gv = DV.geri_ver(ofis, no, not_="a.txt'ye ikinci satiri ben ekledim")
except DV.DevralHatasi as exc:
    gv = {"kapanis": "", "degisen": [], "not_iletildi": False}
    sina("geri_ver CALISTI", False, str(exc))
sina("terminal DUZGUN kapandi", gv["kapanis"] == "duzgun", gv["kapanis"])
sina("insanin degisikligi OLCULDU", "a.txt" in gv["degisen"], str(gv))
with db.baglanti() as c:
    dg = c.execute("SELECT ajan_ad, yol FROM degisim WHERE gorev_id=?", (gid,)).fetchall()
    dokum = c.execute("SELECT govde FROM olay WHERE tur='devral_dokum' AND gorev_id=?",
                      (gid,)).fetchone()
    notlar = c.execute("SELECT govde FROM mesaj WHERE mod='yonlendirme' AND alici='cinar'"
                       ).fetchall()
    bitti = c.execute("SELECT govde FROM olay WHERE tur='devral_bitti' AND gorev_id=?",
                      (gid,)).fetchone()
sina("degisim 'insan' adina yazildi (ajana yuklenmedi)",
     any(r["ajan_ad"] == "insan" and r["yol"] == "a.txt" for r in dg), str([dict(r) for r in dg]))
sina("terminal dokumu deftere gecti", bool(dokum) and "YANKI: insan burada" in dokum["govde"],
     (dokum["govde"][-200:] if dokum else "yok"))
sina("NOT ajana gitti: insanin notu + olculen dosya",
     any("ben ekledim" in n["govde"] and "a.txt" in n["govde"] for n in notlar),
     str([n["govde"][:160] for n in notlar]))
sina("not_iletildi dogru soyleniyor", gv["not_iletildi"] is True)
sina("kayit KALKTI", DV.devralinmis(db, ofis.proje_id, gid) is None)
sina("terminal kayitli degil", TR.al(gid) is None)
sina("devral_bitti olayi", bool(bitti))
try:
    DV.geri_ver(ofis, no)
    sina("devralinmamis isi geri verme REDDEDILIR", False)
except DV.DevralHatasi:
    sina("devralinmamis isi geri verme REDDEDILIR", True)

# ------------------------------------------------------------------ 4b
print("\n4b. DURDURULMUS (hazir) is devralinir; kilit YENIDEN alinir")
ofis.tahta.birak(no, sebep="insan durdurdu")
sina("sahne: is hazir, kilit yok", ofis.tahta.gorev(no)["durum"] == "hazir")
try:
    r2 = DV.devral(ofis, no, fabrika=sahte_fab)
except DV.DevralHatasi as exc:
    r2 = {}
    sina("hazir isi devral CALISTI", False, str(exc))
with db.baglanti() as c:
    kl = c.execute("SELECT ajan_ad FROM yazma_kilidi WHERE gorev_id=?", (gid,)).fetchall()
sina("hazir is devralindi, son sahip bulundu", r2.get("ajan") == "cinar", str(r2))
sina("KILIT yeniden alindi (insan kilitsiz calismaz)", any(x["ajan_ad"] == "cinar" for x in kl))

# Panel yeniden basladi: terminal kayboldu, kayit defterde.
_ac = TR.cikar(gid)
if _ac:
    _ac["terminal"].kapat(duzgun=False)
try:
    gv2 = DV.geri_ver(ofis, no)
except DV.DevralHatasi as exc:
    gv2 = {"olcum_notu": "", "kapanis": ""}
    sina("terminalsiz geri_ver CALISTI", False, str(exc))
sina("terminalsiz geri ver CALISIR ve olcemedigini SOYLER",
     "OLCULEMEDI" in gv2["olcum_notu"] and gv2["kapanis"] == "terminal yoktu", str(gv2))

# ------------------------------------------------------------------ 5
print("\n5. PANEL -- uclar + terminal WebSocket'i")
from fastapi.testclient import TestClient
import ofis.panel as _P

_P.MOTOR_FABRIKASI = sahte_fab
istemci = TestClient(_P.olustur(kok / "o.sqlite3", "Devral"))
d = istemci.post(f"/api/gorev/{no}/devral", json={"sutun": 100, "satir": 30})
sina("POST devral 200", d.status_code == 200, d.text[:200])
dl = istemci.get("/api/devralinanlar").json()
sina("devralinanlar listesinde", any(x.get("no") == no and x.get("terminal_acik") for x in dl["isler"]),
     str(dl)[:200])
bekle(lambda: "SAHTE TERMINAL" in (TR.al(gid) or {"terminal": t})["terminal"].dokum())
with istemci.websocket_connect(f"/ws/terminal/{no}") as ws:
    ilk = ws.receive_json()
    sina("WS: once ekran gecmisi geldi", ilk["tur"] == "veri" and "SAHTE" in TR.duz_metin(ilk["govde"]),
         str(ilk)[:120])
    ws.send_json({"tur": "girdi", "govde": "panelden\r"})
    gordu = False
    for _ in range(40):
        try:
            m = ws.receive_json()
        except Exception:                # noqa: BLE001 -- baglanti koptu: KALDI say, cokme
            break
        if m["tur"] == "veri" and "YANKI: panelden" in TR.duz_metin(m["govde"]):
            gordu = True
            break
    sina("WS: panelden yazilan terminale gitti, yankisi geldi", gordu)
    ws.send_json({"tur": "boyut", "sutun": 80, "satir": 24})
_eski = _P.TERMINAL_YEREL
_P.TERMINAL_YEREL = ("127.0.0.1",)
try:
    d2 = istemci.post(f"/api/gorev/{no}/devral", json={})
    sina("yerel olmayan istemci devral: 403", d2.status_code == 403, str(d2.status_code))
    with istemci.websocket_connect(f"/ws/terminal/{no}") as ws:
        m = ws.receive_json()
        sina("yerel olmayan istemci terminal WS: REDDEDILIR",
             m["tur"] == "hata" and "bilgisayardan" in m["govde"], str(m))
finally:
    _P.TERMINAL_YEREL = _eski
b = istemci.post(f"/api/gorev/{no}/geri_ver", json={"not_": "panelden geri"})
sina("POST geri_ver 200 ve duzgun kapanis", b.status_code == 200 and b.json()["kapanis"] == "duzgun",
     b.text[:200])
b2 = istemci.post(f"/api/gorev/{no}/geri_ver", json={})
sina("ikinci geri_ver 400", b2.status_code == 400)
v = istemci.get("/varlik/vendor/xterm/xterm.js")
sina("xterm.js panelden servis ediliyor (yerel, internetsiz)", v.status_code == 200 and len(v.content) > 100000)
v2 = istemci.get("/varlik/../ofis/panel.py")
sina("varlik yolu klasor disina CIKAMAZ", v2.status_code == 404, str(v2.status_code))

# ------------------------------------------------------------------ 6
print("\n-- 6. KONSOL: ofisten bagimsiz terminal --")
from ofis import konsol as KS

# Ofisin calisma kokunde ve onun ALTINDA acilmaz (yazma kilidi goremez).
r = istemci.post("/api/konsol", json={"klasor": str(kok), "motor": "sahte"})
sina("ofis kokunde konsol REDDEDILIR", r.status_code == 400 and "koku" in r.text, r.text[:160])
(kok / "alt").mkdir(exist_ok=True)
r = istemci.post("/api/konsol", json={"klasor": str(kok / "alt"), "motor": "sahte"})
sina("ofis kokunun ALTINDA da reddedilir", r.status_code == 400, r.text[:160])
r = istemci.post("/api/konsol", json={"klasor": str(kok / "yok-boyle"), "motor": "sahte"})
sina("var olmayan klasor reddedilir", r.status_code == 400, r.text[:160])

dis = Path(tempfile.mkdtemp(prefix="ofis-konsol-"))
r = istemci.post("/api/konsol", json={"klasor": str(dis), "motor": "sahte"})
sina("ofis disi klasorde konsol ACILIR", r.status_code == 200, r.text[:200])
kk = r.json().get("kimlik", "") if r.status_code == 200 else ""
ls = istemci.get("/api/konsol").json()
sina("konsol listesinde, canli", any(k["kimlik"] == kk and k["canli"] for k in ls["konsollar"]),
     str(ls)[:200])
sina("liste powershell'i sunar", "powershell" in ls.get("motorlar", []), str(ls.get("motorlar")))
sina("devralinan is konsol listesine KARISMAZ",
     all(k["kimlik"].startswith("konsol-") for k in ls["konsollar"]))
if kk:
    bekle(lambda: "SAHTE TERMINAL" in (TR.al(kk) or {"terminal": t})["terminal"].dokum())
    with istemci.websocket_connect(f"/ws/konsol/{kk}") as ws:
        ilk = ws.receive_json()
        sina("konsol WS: once ekran gecmisi", ilk["tur"] == "veri", str(ilk)[:120])
        ws.send_json({"tur": "girdi", "govde": "konsoldan\r"})
        gordu = False
        for _ in range(40):
            try:
                m = ws.receive_json()
            except Exception:                # noqa: BLE001 -- KALDI say, cokme
                break
            if m["tur"] == "veri" and "YANKI: konsoldan" in TR.duz_metin(m["govde"]):
                gordu = True
                break
        sina("konsol WS: yazilan gitti, yankisi geldi", gordu)
# Konsol kimligi ile /ws/terminal (devral koprusu) karistirilamaz, tersi de.
with istemci.websocket_connect(f"/ws/konsol/{gid}") as ws:
    m = ws.receive_json()
    sina("devralinan isin terminali konsol ucundan ACILMAZ", m["tur"] == "hata", str(m)[:120])
_eski = _P.TERMINAL_YEREL
_P.TERMINAL_YEREL = ("127.0.0.1",)
try:
    r2 = istemci.post("/api/konsol", json={"klasor": str(dis), "motor": "sahte"})
    sina("yerel olmayan istemci konsol acamaz: 403", r2.status_code == 403, str(r2.status_code))
    if kk:
        with istemci.websocket_connect(f"/ws/konsol/{kk}") as ws:
            m = ws.receive_json()
            sina("yerel olmayan istemci konsol WS: REDDEDILIR", m["tur"] == "hata", str(m)[:120])
finally:
    _P.TERMINAL_YEREL = _eski
if kk:
    kp = istemci.post(f"/api/konsol/{kk}/kapat", json={})
    sina("konsol DUZGUN kapanir", kp.status_code == 200 and kp.json().get("kapanis") == "duzgun",
         kp.text[:160])
    sina("kapanan konsol listeden kalkar",
         not any(k["kimlik"] == kk for k in istemci.get("/api/konsol").json()["konsollar"]))
kp2 = istemci.post("/api/konsol/konsol-yok/kapat", json={})
sina("olmayan konsolu kapatmak 400", kp2.status_code == 400)
with db.baglanti() as c:
    turler = [x["tur"] for x in c.execute(
        "SELECT tur FROM olay WHERE tur LIKE 'konsol_%' ORDER BY rowid")]
sina("kayda gecer: acildi + kapandi (yalniz bunlar)",
     turler == ["konsol_acildi", "konsol_kapandi"], str(turler))
# PowerShell konsolu gercekten acilir ve 'exit' ile duzgun kapanir.
try:
    ps = KS.ac(ofis, str(dis), "powershell")
    bekle(lambda: len(TR.al(ps["kimlik"])["terminal"].dokum()) > 5, sn=15)
    TR.al(ps["kimlik"])["terminal"].yaz("echo konsol-ps-42\r")
    sina("PowerShell konsolu komut kosar",
         bekle(lambda: "konsol-ps-42" in TR.duz_metin(TR.al(ps["kimlik"])["terminal"].dokum())
               .replace("echo konsol-ps-42", ""), sn=15))
    # Insan satiri YARIM birakmis olabilir; kapanis yine duzgun olmali
    # (PowerShell'de Ctrl+U harf olarak yaziliyordu, olculdu).
    TR.al(ps["kimlik"])["terminal"].yaz("yarimkalan")
    time.sleep(0.5)
    sina("PowerShell konsolu (yarim satirla) duzgun kapanir",KS.kapat(ofis, ps["kimlik"])["kapanis"] == "duzgun")
except KS.KonsolHatasi as exc:
    sina("PowerShell konsolu acilir", False, str(exc))

# ------------------------------------------------------------------ 7
print("\n-- 7. KONSOL ONERILERI: yol YAZMADAN acmak --")
# Son acilan klasor oneride; ofis koku ve var olmayan klasor ONERILMEZ
# (tiklaninca reddedilecek oneri, olmayan bir dugme cizmektir).
# Sahne: kokun kendisi de bir kez "acilmis" gibi deftere yazilir -- oneri
# suzgeci yoksa kok listeye girerdi (sahne sinira ULASMALI).
db.olay_yaz(ofis.proje_id, "konsol_acildi",
            f"insan ofis disi terminal acti: powershell · {kok}")
on = istemci.get("/api/konsol").json().get("oneriler", [])
yollar = [o["yol"].lower() for o in on]
sina("son acilan konsol klasoru oneride (son)",
     any(o["yol"].lower() == str(dis.resolve()).lower() and o["neden"] == "son" for o in on),
     str(on)[:300])
sina("ofis koku ve alti ONERILMEZ",
     not any(y == str(kok.resolve()).lower() or y.startswith(str(kok.resolve()).lower() + "\\")
             for y in yollar), str(yollar)[:300])
sina("oneriler tekrarsiz", len(yollar) == len(set(yollar)))
db.olay_yaz(ofis.proje_id, "konsol_acildi",
            "insan ofis disi terminal acti: powershell · C:\\yok\\boyle-bir-klasor-yok")
on2 = istemci.get("/api/konsol").json().get("oneriler", [])
sina("var olmayan klasor ONERILMEZ",
     not any("boyle-bir-klasor-yok" in o["yol"] for o in on2))
_eski = _P.TERMINAL_YEREL
_P.TERMINAL_YEREL = ("127.0.0.1",)
try:
    r3 = istemci.post("/api/konsol/gozat", json={})
    sina("yerel olmayan istemci klasor penceresi ACAMAZ: 403", r3.status_code == 403,
         str(r3.status_code))
finally:
    _P.TERMINAL_YEREL = _eski

# Klasor verilmezse konsol ana klasorde acilir (kullanici: "proje klasoru
# acmadan terminali baslatamaz miyim").
r4 = istemci.post("/api/konsol", json={"klasor": "", "motor": "sahte"})
sina("klasorsuz konsol ACILIR", r4.status_code == 200, r4.text[:200])
if r4.status_code == 200:
    sina("klasorsuz konsol ANA klasorde",
         Path(r4.json()["klasor"]).resolve() == KS.VARSAYILAN_KLASOR.resolve(), r4.json()["klasor"])
    istemci.post(f"/api/konsol/{r4.json()['kimlik']}/kapat", json={})
# Gozat betigi DERLENIR (pencere ACILMAZ: OFIS_GOZAT_DENE).
import subprocess as _sp
_o = dict(__import__("os").environ, OFIS_GOZAT_DENE="1")
_g = _sp.run(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
              "-File", str(KS.GOZAT_BETIK)], capture_output=True, env=_o, timeout=120)
sina("gozat betigi (modern klasor penceresi) derlenir",
     _g.returncode == 0 and b"derlendi" in _g.stdout, (_g.stderr or b"")[-300:].decode("utf-8", "replace"))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
