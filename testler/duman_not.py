# -*- coding: utf-8 -*-
"""TUR ICI NOT ve DURDURMA (E17) -- JETONSUZ.

Insan CALISAN bir ajana "dur, sunu degistir" diyebilmeli; ofisi durdurunca
kosan tur hemen kesilmeli. Olculen protokoller (26.09.2026, CLAUDE.md):

* claude `--input-format stream-json`: tur surerken yazilan not bir sonraki
  arac sinirinda AYNI tura girer; arac siniri yoksa ikinci bir tur acar.
  `--replay-user-messages` yankisi notun ULASTIGI andir. `total_cost_usd`
  birikimli, kullanim sonuc basina.
* codex app-server: `turn/steer` / `turn/interrupt` (duman_codex_app.py).

Gercek motor KOSMAZ. Claude adaptorunun dongusu, protokolu konusan SAHTE
bir `claude` surecine karsi sinanir (adaptorun `Popen`i ona yonlendirilir);
koltuk/tahta/postane sahte motorla sinanir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk                         # noqa: E402
from ofis.koltuk import (durdurma_iste, durdurma_istendi,          # noqa: E402
                         durdurma_temizle)
from ofis.motor.sahte import SahteMotor                            # noqa: E402
from ofis.motor.tip import TurKanali                               # noqa: E402
from ofis.motor import claude as CL                                # noqa: E402
from ofis.postane import PostaneHatasi, gorev_notlari              # noqa: E402

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


def reddedilir(baslik, cagri, parca=""):
    try:
        cagri()
        sina(baslik, False, "-- kabul edildi!")
    except PostaneHatasi as exc:
        sina(baslik, parca.lower() in str(exc).lower(), str(exc)[:120])


print("== tur ici not ve durdurma ==\n")
kok = Path(tempfile.mkdtemp(prefix="ofis-not-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Not", amac="a", basari_olcutu="b", kok_klasor=str(kok))
ofis.kadro.ise_al("demir", "lider", lider_mi=True, klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("cinar", "backend", klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("bilge", "backend", klasor=str(kok), motor="sahte")
ofis.kadro.ise_al("ruzgar", "backend", klasor=str(kok), motor="sahte")


def is_ac(baslik, alan):
    return ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h",
                               kabul_olcutu="k", yazma_alani=alan)


# ------------------------------------------------------------------ 1
print("1. NOT DEFTERI -- kapilar")
g1 = is_ac("api", ["api/"])
ofis.tahta.sahiplen(g1["no"], "cinar", g1["revizyon"])
reddedilir("bos not", lambda: ofis.postane.not_birak("cinar", "  "), "bos")
reddedilir("insana not", lambda: ofis.postane.not_birak("insan", "x"), "ajana")
reddedilir("olmayan ajan", lambda: ofis.postane.not_birak("yok", "x"), "yok")
reddedilir("isi olmayan ajan", lambda: ofis.postane.not_birak("bilge", "x"),
           "lidere")
reddedilir("baskasinin isi", lambda: ofis.postane.not_birak(
    "bilge", "x", gorev_no=g1["no"]), "sahibi")
n1 = ofis.postane.not_birak("cinar", "once testleri duzelt")
sina("is verilmeyince ajanin ELINDEKI is bulunur", n1["gorev_no"] == g1["no"])
sina("not bekliyor (ulasmadi)",
     [n["id"] for n in ofis.postane.bekleyen_notlar("cinar", gorev_no=g1["no"])]
     == [n1["id"]])
with db.baglanti() as c:
    sina("'not' olayi yazildi", c.execute(
        "SELECT COUNT(*) FROM olay WHERE tur='not'").fetchone()[0] == 1)

# ------------------------------------------------------------------ 2
print("\n2. BRIFING -- not isin tanimina EK, ulasmayan YENI")
k4 = ofis.brifing.k4_gorev(g1["no"])
sina("K4 notu tasiyor", "once testleri duzelt" in k4 and "Patronun bu ise" in k4)
sina("ulasmamis not YENI isaretli", "**YENI** once testleri duzelt" in k4, k4[-300:])
sina("iletildi isaretlenir", ofis.postane.not_iletildi(n1["id"], yol="tur_ici"))
sina("iki kez isaretlenmez", not ofis.postane.not_iletildi(n1["id"], yol="tur_basinda"))
k4 = ofis.brifing.k4_gorev(g1["no"])
sina("ulasan not artik YENI degil", "once testleri duzelt" in k4
     and "**YENI** once testleri duzelt" not in k4)
with db.baglanti() as c:
    ilet = c.execute("SELECT govde FROM olay WHERE tur='not_iletildi'").fetchall()
sina("iletim olayi YOLU soyluyor", len(ilet) == 1 and "SURERKEN" in ilet[0]["govde"])

# ------------------------------------------------------------------ 3
print("\n3. KOLTUK + KANALLI MOTOR -- tur SURERKEN not ulasir")
BAG = {}


class NotYazan(SahteMotor):
    """Birinci nabizdan sonra insanin notunu (ya da durdurmayi) deftere yazar
    -- baska bir surecteki insanin yaptigi gibi."""

    def __init__(self, **kw):
        super().__init__(senaryo="sessiz", nabiz_sayisi=6, **kw)
        self.yazdi = False

    def tur_kos(self, metin, **ayar):
        BAG["ayar"] = ayar
        BAG["metin"] = metin
        for o in super().tur_kos(metin, **ayar):
            yield o
            if o.tur == "nabiz" and not self.yazdi:
                self.yazdi = True
                if BAG.get("eylem") == "durdur":
                    durdurma_iste(db, ofis.proje_id, "sinama")
                elif BAG.get("eylem") == "not":
                    BAG["tur_ici"] = ofis.postane.not_birak(
                        BAG["ajan"], "tur ortasi: b dosyasini da yaz",
                        gorev_no=BAG["no"])
                BAG["motor"] = self


koltuk = Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: NotYazan())
koltuk.NOT_ARALIGI_S = 0
g2 = is_ac("web", ["web/"])
BAG.update(eylem="not", ajan="bilge", no=g2["no"])
ofis.tahta.sahiplen(g2["no"], "bilge", g2["revizyon"])
once = ofis.postane.not_birak("bilge", "tur oncesi not", gorev_no=g2["no"])
olaylar = list(koltuk.akit(g2["no"], "bilge"))
sina("kanalli motora kanal VERILDI", "kanal" in BAG["ayar"])
sina("tur oncesi not ISTEME girdi", "tur oncesi not" in BAG["metin"])
with db.baglanti() as c:
    oku = {r["govde"]: r["okundu"] for r in c.execute(
        "SELECT govde, okundu FROM mesaj WHERE mod='yonlendirme' AND gorev_id=?",
        (g2["id"],))}
    yol = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur='not_iletildi' AND gorev_id=?",
        (g2["id"],))]
sina("tur oncesi not 'tur BASINDA' ulasti",
     oku.get("tur oncesi not") == 1 and any("BASINDA" in y for y in yol), str(yol))
sina("tur ortasi not motora GITTI (kanal)",
     any("tur ortasi" in m for m in BAG["motor"].cagrilar[-1]["iletilen"]))
sina("iletilen metin PATRON NOTU bicimli",
     any(m.startswith("PATRONUN NOTU") for m in BAG["motor"].cagrilar[-1]["iletilen"]))
sina("tur ortasi not 'tur SURERKEN' ulasti",
     oku.get("tur ortasi: b dosyasini da yaz") == 1
     and any("SURERKEN" in y for y in yol), str(yol))
sina("panele 'not_iletildi' akti", any(o["tur"] == "not_iletildi" for o in olaylar))
sina("tur ONCESI not kanala IKINCI kez itilmedi",
     sum("tur oncesi not" in m for m in BAG["motor"].cagrilar[-1]["iletilen"]) == 0)

# ------------------------------------------------------------------ 4
print("\n4. KANALSIZ MOTOR -- not bekler, SONRAKI tur basinda gider")


class Kanalsiz(NotYazan):
    tur_ici_mesaj = False


koltuk2 = Koltuk(ofis, motor_fabrikasi=lambda ad, **kw: Kanalsiz())
koltuk2.NOT_ARALIGI_S = 0
g3 = is_ac("dok", ["dok/"])
ofis.tahta.sahiplen(g3["no"], "bilge", g3["revizyon"])
BAG.update(eylem="not", ajan="bilge", no=g3["no"])
list(koltuk2.akit(g3["no"], "bilge"))
sina("kanalsiz motora kanal VERILMEDI", "kanal" not in BAG["ayar"])
bek = ofis.postane.bekleyen_notlar("bilge", gorev_no=g3["no"])
sina("not ulasmadi -- BEKLIYOR (uydurulmadi)", len(bek) == 1)
BAG.update(eylem="")
list(koltuk2.akit(g3["no"], "bilge"))
sina("sonraki tur ISTEMINDE", "tur ortasi: b dosyasini da yaz" in BAG["metin"])
sina("sonraki turun basinda ulasti",
     not ofis.postane.bekleyen_notlar("bilge", gorev_no=g3["no"]))

# ------------------------------------------------------------------ 5
print("\n5. DURDURMA -- kosan tur KESILIR, is 'kaldigi yerden' devam eder")
g4 = is_ac("dur", ["dur/"])
ofis.tahta.sahiplen(g4["no"], "cinar", g4["revizyon"])
BAG.update(eylem="durdur", ajan="cinar", no=g4["no"])
olaylar = list(koltuk.akit(g4["no"], "cinar"))
sina("durdurma istegi defterde", bool(durdurma_istendi(db, ofis.proje_id)))
son = [o for o in olaylar if o["tur"] == "tur_bitti"][-1]
sina("tur basarisiz bitti (kesildi)", son["ek"].get("basarili") is False)
with db.baglanti() as c:
    bir = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur='birakildi' AND gorev_id=?", (g4["id"],))]
    uy = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur='uyari' AND gorev_id=?", (g4["id"],))]
sina("birakma sebebi 'insan durdurdu'", any("insan durdurdu" in b for b in bir), str(bir))
sina("kesilme GORUNUR (uyari)", any("KESILIYOR" in u for u in uy), str(uy))
g4s = ofis.tahta.gorev(g4["no"])
sina("is hazir'a dondu (olmedi)", g4s["durum"] == "hazir")
sina("SURDUR ayni oturumdan devam eder (kaynak sebebi)",
     koltuk._devam_mi(g4["no"], "cinar", ofis.kadro.ajan("cinar"), g4s) is True)
durdurma_temizle(db, ofis.proje_id)
sina("istek temizlenir", not durdurma_istendi(db, ofis.proje_id))

g5 = is_ac("dur2", ["dur2/"])
ofis.tahta.sahiplen(g5["no"], "bilge", g5["revizyon"])
BAG.update(eylem="durdur", ajan="bilge", no=g5["no"])
list(koltuk2.akit(g5["no"], "bilge"))
with db.baglanti() as c:
    uy = [r["govde"] for r in c.execute(
        "SELECT govde FROM olay WHERE tur='uyari' AND gorev_id=?", (g5["id"],))]
sina("kanalsiz motorda 'tur bitince durulacak' SOYLENIR (bir kez)",
     sum("kesemiyor" in u for u in uy) == 1, str(uy))
durdurma_temizle(db, ofis.proje_id)

# ------------------------------------------------------------------ 6
print("\n6. ORKESTRA -- durdurulan ofis yeni tur BASLATMAZ")
from ofis.orkestra import Orkestra                                 # noqa: E402
cagrildi = []
ork = Orkestra(ofis, motor_fabrikasi=lambda ad, **kw: cagrildi.append(ad) or SahteMotor())
durdurma_iste(db, ofis.proje_id, "sinama")
ilk = next(ork.kos(azami_tik=3))
sina("ilk adim 'Insan DURDURDU'", ilk.get("bitti") and "DURDURDU" in ilk.get("sebep", ""),
     str(ilk)[:120])
sina("hicbir motor cagrilmadi", not cagrildi)
durdurma_temizle(db, ofis.proje_id)

# ------------------------------------------------------------------ 7
print("\n7. LIDER INCELEMESI ve SOHBET GECMISI")
g6 = is_ac("ince", ["ince/"])
ofis.tahta.sahiplen(g6["no"], "cinar", g6["revizyon"])
nx = ofis.postane.not_birak("cinar", "renkleri koyu yap", gorev_no=g6["no"])
im = ofis.lider.inceleme_metni(g6["no"])
sina("inceleme notu goruyor", "renkleri koyu yap" in im)
sina("ULASMAYAN not ayrica soyleniyor", "ULASMADI" in im)
ofis.postane.not_iletildi(nx["id"], yol="tur_ici")
im = ofis.lider.inceleme_metni(g6["no"])
sina("ulasan notta 'ULASMADI' yok", "renkleri koyu yap" in im and "ULASMADI" not in im)
sina("sohbet gecmisi notlari lidere konusma SANMAZ",
     not any("renkleri koyu" in (m.get("govde") or "") for m in ofis.sohbet.gecmis(50)))
sina("gorev_notlari tek sorgu, sirali",
     [n["govde"] for n in gorev_notlari(db, ofis.proje_id, g6["id"])] == ["renkleri koyu yap"])
# DANISMA da ayni resme bakar. OLCULDU (27.09, D14 codex): danisma notu
# gormedigi icin "notu kullanma" dedi, ayni liderin incelemesi notu gorup
# isi geri gonderdi; is tik sinirinda oldu.
from ofis.danisma import Danisma                                   # noqa: E402
from ofis.postane import NOT_KURALI                                # noqa: E402
sm = Danisma(ofis).soru_metni({"gonderen": "cinar", "gorev_no": g6["no"],
                               "govde": "not is metniyle celisiyor, hangisi?"})
sina("danisma patronun notunu GORUYOR", "renkleri koyu yap" in sm)
sina("danisma isin ANA HEDEFINI goruyor", "- ana hedef: h" in sm)
k4 = ofis.brifing.k4_gorev(g6["no"])
sina("kural TEK cumle: brifing, tur ici not, inceleme, danisma ayni",
     all(NOT_KURALI in m for m in (k4, Koltuk.not_metni("x"), im, sm)),
     str([NOT_KURALI in m for m in (k4, Koltuk.not_metni("x"), im, sm)]))
sina("kural 'NOT gecerlidir' diyor (celiskide sorusuz ilerlenir)",
     "NOT gecerlidir" in NOT_KURALI)

# ------------------------------------------------------------------ 8
print("\n8. PANEL API ve KABUK")
from fastapi.testclient import TestClient                          # noqa: E402
import ofis.panel as _P                                            # noqa: E402
_P.MOTOR_FABRIKASI = lambda ad, **kw: (SahteMotor() if ad == "sahte"
                                       else (_ for _ in ()).throw(RuntimeError(ad)))
ist = TestClient(_P.olustur(str(db.yol), "Not"))
r = ist.post("/api/ajan/cinar/not", json={"metin": "panelden not", "gorev_no": g6["no"]})
sina("panel notu yazar", r.status_code == 200 and r.json().get("gorev_no") == g6["no"],
     r.text[:150])
sina("panel NE ZAMAN gidecegini soyler (tasir)", r.json().get("tasir") is True)
r = ist.post("/api/ajan/ruzgar/not", json={"metin": "x"})
sina("isi olmayan ajana panel 400", r.status_code == 400 and "lidere" in r.text.lower(),
     r.text[:120])
r = ist.post("/api/durdur")
sina("panel Durdur DEFTERE yazar (kabuk halkasi da gorur)",
     r.status_code == 200 and bool(durdurma_istendi(db, ofis.proje_id)), r.text[:150])
# SON cevap "devam et" demek DEGILDIR: durdurulmus ofiste halka
# kendiliginden donmez. Sahne: insanin onunde TEK istek kalsin -- baska
# istek bekleseydi sebep "istek daha bekliyor" olurdu ve bu kapi hic
# sinanmazdi (testin sahnesi olcmek istedigi sinira ULASMALI).
for m in ofis.postane.insan_bekleyenler():
    ofis.postane.cevapla(m["id"], "tamam")
for o in ofis.postane.bekleyen_onaylar():
    ofis.postane.onay_cevapla(o["id"], onayla=False, not_="sahne temizligi")
son_soru = ofis.postane.soru_sor("cinar", "insan", "renk hangisi?", gorev_no=g6["no"])
_P._KOSU.update(calisiyor=False, dur=False)
r = ist.post(f"/api/soru/{son_soru['id']}/cevap", json={"metin": "koyu", "surdur": True})
j = r.json() if r.status_code == 200 else {}
sina("durdurulmus ofiste SON cevap halkayi DONDURMEZ",
     r.status_code == 200 and (j.get("surdurme") or j).get("surduruldu") is False
     and "DURDURULMUS" in json.dumps(j, ensure_ascii=False), r.text[:200])
sina("halka kosmuyor (arka plan baslamadi)", _P._KOSU["calisiyor"] is False)
durdurma_temizle(db, ofis.proje_id)
kab = [sys.executable, "-m", "ofis.kabuk", "--db", str(db.yol), "--proje", "Not"]
kok_dizin = str(Path(__file__).resolve().parent.parent)
r = subprocess.run(kab + ["not", "cinar", "kabuktan not"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace", cwd=kok_dizin)
sina("kabuk 'not' yazar", r.returncode == 0 and "kabuktan not" in r.stdout,
     (r.stdout + r.stderr)[-200:])
r = subprocess.run(kab + ["durdur"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", cwd=kok_dizin)
sina("kabuk 'durdur' deftere yazar", r.returncode == 0
     and bool(durdurma_istendi(db, ofis.proje_id)), (r.stdout + r.stderr)[-200:])
durdurma_temizle(db, ofis.proje_id)

# ------------------------------------------------------------------ 9
print("\n9. CLAUDE ADAPTORU -- sahte `claude` surecine karsi (gercek CLI YOK)")
SAHTE = r'''
import json, os, sys, threading, time, queue
sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
SEN = json.load(open(os.path.join(os.path.dirname(__file__), "senaryo.json"), encoding="utf-8"))
q = queue.Queue()
def oku():
    for s in iter(sys.stdin.readline, ""):
        q.put(s)
    q.put(None)
threading.Thread(target=oku, daemon=True).start()
def yaz(m):
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n"); sys.stdout.flush()
TOPLAM = [0.0]
def sonuc(metin, cikti, hata=False, alt="success"):
    TOPLAM[0] += 0.001 * cikti
    yaz({"type": "result", "subtype": alt, "is_error": hata, "result": metin,
         "total_cost_usd": TOPLAM[0], "usage": {"input_tokens": 10, "output_tokens": cikti,
         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}})
def yanki(t):
    yaz({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": t}]}})
def soz(t):
    # Gercek CLI (`--include-partial-messages`) metni PARCA olarak akitir;
    # adaptor cevabi parcalardan toplar. Sahte de oyle yapmali.
    yaz({"type": "stream_event", "event": {"type": "content_block_delta",
         "delta": {"type": "text_delta", "text": t + " "}}})
    yaz({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}})
def al(sure):
    try:
        s = q.get(timeout=sure)
    except queue.Empty:
        return None
    return "EOF" if s is None else json.loads(s)
if not SEN.get("akis"):
    ilk = sys.stdin.read()
    soz("tek tur"); sonuc("tek tur", 5); sys.exit(0)
ilk = al(10)
yanki(ilk["message"]["content"][0]["text"])
sen = SEN["senaryo"]; kuyruk = []; kesildi = False
def topla(sure):
    global kesildi
    bit = time.time() + sure
    while time.time() < bit:
        m = al(0.05)
        if m is None: continue
        if m == "EOF": sys.exit(0)
        if m.get("type") == "control_request":
            # Gercek CLI yalniz BILDIGI alt turu uygular; bilinmeyen istek
            # hata doner ve tur SURER. Her istegi kesme saymak, adaptorun
            # interrupt yazmadigi hali gizlerdi (mutasyon gosterdi).
            if (m.get("request") or {}).get("subtype") != "interrupt":
                yaz({"type": "control_response", "response": {"subtype": "error",
                     "request_id": m.get("request_id"), "error": "bilinmeyen istek"}})
                continue
            open(os.path.join(os.path.dirname(__file__), "kesme.json"), "w").write(
                json.dumps(m))
            yaz({"type": "control_response", "response": {"subtype": "success",
                 "request_id": m.get("request_id")}})
            yaz({"type": "user", "message": {"content": [{"type": "tool_result",
                 "tool_use_id": "t1", "is_error": True, "content": "rejected"}]}})
            sonuc(None, 3, hata=True, alt="error_during_execution")
            kesildi = True
            return
        if m.get("type") == "user":
            kuyruk.append(m["message"]["content"][0]["text"])
if sen in ("arac_siniri", "durdur"):
    yaz({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1",
         "name": "Bash", "input": {"command": "sleep 2"}}]}})
    topla(SEN.get("arac_sn", 2.0))
    if not kesildi:
        yaz({"type": "user", "message": {"content": [{"type": "tool_result",
             "tool_use_id": "t1", "is_error": False, "content": "ok"}]}})
        for t in kuyruk: yanki(t)
        kuyruk.clear()
        soz("tamam"); sonuc("tamam", 7)
else:
    topla(SEN.get("dusun_sn", 1.0))
    soz("ilk cevap"); sonuc("ilk cevap", 11)
    if sen == "yeni_tur":
        for t in list(kuyruk):
            # Not YENI bir tur acar; o tur da surer (ikinci_sn) ve KESILEBILIR.
            yanki(t); topla(SEN.get("ikinci_sn", 0.0))
            if kesildi: break
            soz("ek cevap"); sonuc("ek cevap", 13)
        kuyruk.clear()
bit = time.time() + 30
while time.time() < bit:
    m = al(0.1)
    if m == "EOF": break
    if isinstance(m, dict) and m.get("type") == "user" and sen == "yeni_tur":
        yanki(m["message"]["content"][0]["text"]); soz("ek cevap"); sonuc("ek cevap", 13)
sys.exit(1 if kesildi else 0)
'''
skl = Path(tempfile.mkdtemp(prefix="ofis-sahteclaude-"))
(skl / "sahte_claude.py").write_text(SAHTE, encoding="utf-8")
calisma = Path(tempfile.mkdtemp(prefix="ofis-claudetur-"))
_gercek_popen = subprocess.Popen
KOMUT = {}


def _sahte_popen(komut, **kw):
    KOMUT["son"] = list(komut)
    return _gercek_popen([sys.executable, str(skl / "sahte_claude.py")], **kw)


def kos(senaryo, eylem, **ek):
    (skl / "kesme.json").unlink(missing_ok=True)
    (skl / "senaryo.json").write_text(json.dumps(
        {"senaryo": senaryo, "akis": eylem != "yok", **ek}), encoding="utf-8")
    m = CL.ClaudeMotoru(calistirilabilir="claude", zaman_asimi=60)
    kanal = TurKanali() if eylem != "yok" else None
    olaylar = []
    CL.subprocess.Popen = _sahte_popen
    try:
        for o in m.tur_kos("gorev metni", klasor=str(calisma), model="haiku",
                           kanal=kanal):
            olaylar.append(o)
            if eylem == "not_arac" and o.tur == "arac":
                kanal.gonder("n1", "EK: b.txt de yaz")
            elif eylem == "not_bas" and o.tur == "basladi":
                kanal.gonder("n2", "EK: TAMAM yaz")
            elif eylem == "durdur" and o.tur == "arac":
                kanal.durdur()
            elif eylem == "yankisiz" and o.tur == "basladi":
                kanal.gonder("n3", "hic islenmeyecek not")
            elif eylem == "not_sonra_dur" and o.tur == "basladi":
                kanal.gonder("n4", "EK: son bir sey daha")
            elif eylem == "not_sonra_dur" and o.tur == "mesaj":
                kanal.durdur()
    finally:
        CL.subprocess.Popen = _gercek_popen
    return olaylar, olaylar[-1].ek


ol, ek = kos("tek", "yok")
k = KOMUT["son"]
sina("kanalsiz tur: --input-format text (olculmus eski yol)",
     k[k.index("--input-format") + 1] == "text" and "--replay-user-messages" not in k)
sina("kanalsiz tur basarili", ek.get("basarili") is True, str(ek)[:150])

ol, ek = kos("arac_siniri", "not_arac")
k = KOMUT["son"]
sina("kanalli tur: stream-json + yanki bayragi",
     k[k.index("--input-format") + 1] == "stream-json" and "--replay-user-messages" in k)
mes = [o for o in ol if o.tur == "mesaj"]
sina("arac sinirinda not ULASTI (mesaj olayi, dogru kimlik)",
     len(mes) == 1 and mes[0].ek.get("kimlik") == "n1", str([o.tur for o in ol]))
sina("tek sonuc, basarili", ek.get("basarili") is True, str(ek)[:160])
sina("jeton tek sonuctan (10+7)", ek.get("jeton") == 17, str(ek.get("jeton")))

ol, ek = kos("yeni_tur", "not_bas", dusun_sn=1.0)
mes = [o for o in ol if o.tur == "mesaj"]
sina("arac siniri yokken not IKINCI turda ulasti", len(mes) == 1
     and mes[0].ek.get("kimlik") == "n2", str([o.tur for o in ol]))
sina("jeton SONUC BASINA toplandi (21+23)", ek.get("jeton") == 44, str(ek.get("jeton")))
sina("maliyet BIRIKIMLI -> son sonuc (0,024)",
     abs((ek.get("maliyet_usd") or 0) - 0.024) < 1e-9, str(ek.get("maliyet_usd")))
sina("cevap iki turu da tasiyor", "ilk cevap" in ol[-1].govde and "ek cevap" in ol[-1].govde,
     ol[-1].govde[:80])

ol, ek = kos("durdur", "durdur", arac_sn=4.0)
sina("durdurulan tur basarisiz, sebep 'durduruldu'",
     ek.get("basarili") is False and ek.get("sebep") == "durduruldu", str(ek)[:160])
# Adaptorun kendi bayragi "durduruldu" der; kesmenin CLI'a GERCEKTEN
# ulastigi ayrica olculur: sahte yalniz `interrupt` alt turuyle keser.
sina("interrupt CLI'a ULASTI (alt tur 'interrupt')", (skl / "kesme.json").exists())
sina("tur KESILDI, arac bitmesi beklenmedi (< 3 sn; arac 4 sn)",
     (ek.get("sure_ms") or 99999) < 3000, str(ek.get("sure_ms")))

# Not bir IKINCI tur actiysa o tur da durdurulabilmeli. Gercek CLI stdin
# kapansa da kuyruktaki notu isler (olculdu 26.09, $0,03) -- yani stdin'i
# sonucta acik tutmanin sebebi notu kurtarmak DEGIL, bu durdurmadir.
ol, ek = kos("yeni_tur", "not_sonra_dur", dusun_sn=0.5, ikinci_sn=4.0)
sina("notun actigi IKINCI tur da kesilebildi",
     (skl / "kesme.json").exists() and ek.get("sebep") == "durduruldu",
     str([o.tur for o in ol if o.tur != "nabiz"]))
sina("durdurma GORUNUR (hata olayi)",
     any(o.tur == "hata" and (o.ek or {}).get("sebep") == "durduruldu" for o in ol))

eski = CL.NOT_BEKLEME_SN
CL.NOT_BEKLEME_SN = 1.5
try:
    ol, ek = kos("yankisiz", "yankisiz", dusun_sn=0.3)
finally:
    CL.NOT_BEKLEME_SN = eski
sina("yankisiz not: surec ASILI kalmadi, tur bitti", ek.get("basarili") is True,
     str(ek)[:160])
# Sahte surec 30 sn sonra kendiliginden cikar -- asilma o sureye kadar
# GIZLENIRDI. Koruma calistiysa tur bekleme suresi + birkac saniyede biter.
sina("yankisiz not: bekleme korumasi SURE olarak tuttu (< 12 sn)",
     (ek.get("sure_ms") or 99999) < 12000, str(ek.get("sure_ms")))
sina("yankisiz not ULASTI sayilmadi (mesaj olayi yok)",
     not any(o.tur == "mesaj" for o in ol))

# ------------------------------------------------------------------ 10
print("\n10. SOZLESME -- tasiyamayan adaptor kanali REDDEDER")
from ofis.motor.codex import CodexMotoru                          # noqa: E402
from ofis.motor.gemini import GeminiMotoru                        # noqa: E402
from ofis.motor.tip import Motor, MotorHatasi                     # noqa: E402
sina("sinif varsayilani kapali", Motor.tur_ici_mesaj is False)
sina("claude tasir", CL.ClaudeMotoru.tur_ici_mesaj is True)
sina("codex app-server tasir, exec tasimaz",
     CodexMotoru(calistirilabilir="codex").tur_ici_mesaj is True
     and CodexMotoru(calistirilabilir="codex", kip="exec").tur_ici_mesaj is False)
for ad, mm in (("codex exec", CodexMotoru(calistirilabilir="codex", kip="exec")),
               ("gemini", GeminiMotoru())):
    try:
        list(mm.tur_kos("x", klasor=str(calisma), kanal=TurKanali()))
        sina(f"{ad}: kanal REDDEDILIYOR", False, "-- kabul etti")
    except MotorHatasi as exc:
        sina(f"{ad}: kanal REDDEDILIYOR", "not" in str(exc).lower(), str(exc)[:90])

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
