# -*- coding: utf-8 -*-
"""MOTOR MATRISI (PLAN §4-T3, E59, B3/B5) -- bir motorun iddia ettigi
yetenegi GERCEKTEN yapip yapmadigi.

    python testler/matris.py --motor claude            # gercek, kisa turlar
    python testler/matris.py --motor codex
    python testler/matris.py --kuru                    # $0: sinavin kendisi

Kullanici (27.09.2026): *"gemini alinca ekleyecegim, altyapi hazir
olsun... kimi, qwen, groq, deepseek, opencode da olacak; ama sistem gpt ve
claude ile de tam kullanilabilmeli."* Yeni bir motor tek dosya + tek
satirla takilir; bu dosya onun KAPISIDIR: motor deftere girmeden once
buradan gecer.

## Neden gerekli

Adaptor yeteneklerini BAYRAKLA bildirir (`mcp_konusur`, `izin_kancasi`,
`tur_ici_mesaj`, ...). Cekirdek bayraga guvenir: kanit kanalini, onay
kapisini, tur ici notu ona gore secer. Bu projede bayrak uc kez YALAN
cikti ve hepsi ancak gercek turda goruldu -- codex `mcp_konusur = True`
diyordu ama her MCP cagrisi onayda dustu; gemini "kurulu" gorunuyordu ama
anahtari tur ortamina hic ulasmiyordu. *Kablonun bagli olmasi icinden
akim gectigi anlamina gelmez.*

## Kurallar

* Her hucre TEK, KISA, GERCEK bir tur. Sonuca modelin SOZUNE degil
  DISKE, DEFTERE ve olay akisina bakilir. Komut hucresinin cevabi modelin
  bilemeyecegi bir sayidir (rastgele tohumun ozeti): uyduramaz.
* Sinanan motor TEK basina kosar: fabrika baska motor vermez, yani nobet
  zinciri sessizce baska motora devredip "gecti" diyemez.
* Hucre sonuclari: **var** (iddia edildi, calisti) · **yok** (bayrak
  kapali, dürüstce bildirildi) · **YALAN** (iddia edildi, calismadi) ·
  **KALDI** (zorunlu hucre calismadi) · **olculemedi** (sinav hucreye
  ulasamadi -- sebebiyle) · **bilgi**.
* Hukum: zorunlu hucrelerin hepsi var VE hic YALAN yoksa **KABUL**.
  "yok" bir kusur degildir -- motor karti onu yazar, cekirdek o yetenegi
  o motora vermez. Yalan kusurdur: cekirdek ona guvenip yanlis kanal
  secerdi.
* Gercek ofise, kasaya, kabin profiline DOKUNMAZ: her motor bos bir
  gecici ofiste kosar. Son olcum `~/.agentofis/motor_matris.json`a yazilir
  (dürüst motor karti, E60, oradan okur); kuru kip yazmaz.
"""

from __future__ import annotations

import os as _os
from pathlib import Path as _Path

# Gercek kosu gercek hesaplarla kosar (codex girisi ~/.agentofis/codex).
_os.environ.setdefault("OFIS_EV", str(_Path.home() / ".agentofis"))

import _temizlik  # noqa: F401,E402 -- gecici klasorleri siler (E05)

import argparse                     # noqa: E402
import os                           # noqa: E402
import datetime as _dt              # noqa: E402
import hashlib                      # noqa: E402
import http.server                  # noqa: E402
import json                         # noqa: E402
import re                           # noqa: E402
import secrets                      # noqa: E402
import subprocess                   # noqa: E402
import sys                          # noqa: E402
import tempfile                     # noqa: E402
import threading                    # noqa: E402
import time                         # noqa: E402
import traceback                    # noqa: E402
import uuid                         # noqa: E402
from pathlib import Path            # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ofis import Ofis, Veritabani                 # noqa: E402
from ofis.koltuk import Koltuk                    # noqa: E402
from ofis.motor import motor_ac                   # noqa: E402
from ofis.motor.tip import Motor, MotorHatasi, MotorOlayi, TurKanali   # noqa: E402
from ofis.yollar import OFIS_EVI                  # noqa: E402

RAPOR = Path(__file__).resolve().parent / "rapor"
SON_OLCUM = OFIS_EVI / "motor_matris.json"

#: Hucre tanimi TEK yerde: panelin durust motor karti ayni listeyi okur.
from ofis.motor_karti import HUCRELER, ZORUNLU   # noqa: E402

#: Motorun hizli kademesi (gercek kosunun varsayilani). Kod varsayilani
#: degil OLCULEN: codex'te F2 turlari gpt-6-luna ile kostu.
VARSAYILAN_MODEL = {"claude": "haiku", "codex": "gpt-6-luna"}
TUR_TAVANI = 0.30
#: Butce hucresi: iki adimli is bu tavanda BITEMEMELI.
KUCUK_TAVAN = 0.001
ZAMAN_ASIMI = 300

#: Sahte motorlar (kuru kip) yonergeyi bu satirdan okur. Gercek model onu
#: dogal dil yonergesiyle birlikte gorur; cevabi DEGIL isi tarif eder.
ADIM = "MATRIS-ADIM:"


# ------------------------------------------------------------ yardimcilar

def _adim(d: dict) -> str:
    return f"{ADIM} {json.dumps(d, ensure_ascii=False)}"


def _kullaniciya_ac(klasor: Path) -> None:
    """Gecici klasor gercek `calisma/` gibi kullaniciya miras izin versin
    (deneme.py: codex sandbox'i aksi halde dosyayi pc'ye kapatiyor)."""
    if os.name != "nt":
        return
    kim = os.environ.get("USERNAME") or ""
    if kim:
        subprocess.run(["icacls", str(klasor), "/grant", f"{kim}:(OI)(CI)F"],
                       capture_output=True)



class _Sayfa:
    """JS ile cizilen gizli metni sunan yerel sayfa (tarayici hucresi).

    WebFetch JS kosmaz: metni ancak gercek bir tarayici gorur."""

    def __init__(self, gizli: str) -> None:
        html = (f"<!doctype html><meta charset=utf-8><title>matris</title>"
                f"<p id=gizli>yukleniyor</p><script>setTimeout(()=>"
                f"document.getElementById('gizli').textContent="
                f"{json.dumps(gizli)},300)</script>").encode("utf-8")

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):          # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html)

            def log_message(self, *_):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.adres = f"http://127.0.0.1:{self.srv.server_port}/"

    def kapat(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


class _KuruluDegil(Motor):
    """Sinanan motor disindaki her ad: zincir baska motora DEVREDEMESIN."""

    def __init__(self, ad: str) -> None:
        self.ad = ad

    def musait_mi(self) -> bool:
        return False

    def durum_notu(self) -> str:
        return f"{self.ad}: matris yalniz sinanan motoru kosturur"

    def tur_kos(self, metin, **_):
        raise RuntimeError("kosturulmamali")


# ------------------------------------------------------------------ sahne

class Sahne:
    """Tek motor icin bos gecici ofis + fikstur."""

    def __init__(self, motor: Motor, model: str) -> None:
        self.motor, self.model = motor, model
        self.ana = Path(tempfile.mkdtemp(prefix=f"ofis-matris-{motor.ad}-"))
        _kullaniciya_ac(self.ana)
        self.kok = self.ana / "calisma"
        self.kok.mkdir()
        self.tohum = secrets.token_hex(16)
        (self.kok / "tohum.txt").write_text(self.tohum, encoding="utf-8")
        (self.kok / "ozet.py").write_text(
            "import hashlib\nprint(hashlib.sha256(open('tohum.txt','rb')"
            ".read()).hexdigest()[:16])\n", encoding="utf-8")
        (self.kok / "bekle.py").write_text(
            "import time\nfor i in range(25):\n    print('bekliyor', i, flush=True)\n"
            "    time.sleep(1)\n", encoding="utf-8")
        self.beklenen_ozet = hashlib.sha256(self.tohum.encode()).hexdigest()[:16]
        self.db = Veritabani(self.ana / "o.sqlite3")
        self.ofis = Ofis.proje_ac(self.db, f"Matris {motor.ad}", amac="motor matrisi",
                                  basari_olcutu="hucreler olculur",
                                  kok_klasor=str(self.kok))
        self.kanat = self.ofis.kanat_ac("MATRIS", "MT")
        self.ofis.kadro.ise_al("isci", "backend", klasor=str(self.kok),
                               motor=motor.ad, model=model, kanat_id=self.kanat)
        self.bitti_ekleri: list = []

    def fabrika(self, ad, **_):
        return self.motor if ad == self.motor.ad else _KuruluDegil(ad)

    # -- ofisin kendi yolundan (koltuk): kanit kanali, kanca, tarayici --
    def koltuk_isi(self, baslik: str, hedef: str, olcut: str,
                   yazma_alani, **gorev) -> dict:
        g = self.ofis.tahta.gorev_ac(
            baslik, neden="motor matrisi", ana_hedef=hedef, kabul_olcutu=olcut,
            govde=hedef, yazma_alani=yazma_alani, kanat_id=self.kanat,
            **gorev)
        k = Koltuk(self.ofis, motor_fabrikasi=self.fabrika,
                   zincir=[(self.motor.ad, self.model)])
        tavan = TUR_TAVANI if getattr(self.motor, "butce_destegi", False) else None
        ozet = k.kos(g["no"], "isci", butce_usd=tavan, zaman_asimi=ZAMAN_ASIMI)
        ozet["no"], ozet["gorev_id"] = g["no"], g["id"]
        return ozet

    # -- adaptorun kendisi: oturum, kafa, kanal, araclar, butce --
    def akis(self, metin: str, kanal_islevi=None, **ayar) -> list:
        ayar.setdefault("klasor", str(self.kok))
        ayar.setdefault("model", self.model)
        ayar.setdefault("efor", "dusuk")
        ayar.setdefault("zaman_asimi", ZAMAN_ASIMI)
        if getattr(self.motor, "butce_destegi", False):
            ayar.setdefault("butce_usd", TUR_TAVANI)
        olaylar = []
        for o in self.motor.tur_kos(metin, **ayar):
            olaylar.append(o)
            if o.tur == "bitti":
                self.bitti_ekleri.append(dict(o.ek or {}))
            if kanal_islevi:
                kanal_islevi(o, olaylar)
        return olaylar

    def olaylar(self, tur: str, gorev_id: str = "") -> list:
        with self.db.baglanti() as c:
            q = "SELECT tur, govde FROM olay WHERE proje_id=? AND tur=?"
            a = [self.ofis.proje_id, tur]
            if gorev_id:
                q += " AND gorev_id=?"
                a.append(gorev_id)
            return [dict(r) for r in c.execute(q + " ORDER BY rowid", a)]

    def kapat(self) -> None:
        try:
            self.db.kapat()
        except Exception:               # noqa: BLE001
            pass


def _bitti(olaylar: list) -> dict:
    son = [o for o in olaylar if o.tur == "bitti"]
    return dict(son[-1].ek or {}) if son else {}


def _metin(olaylar: list) -> str:
    return "".join(o.govde for o in olaylar if o.tur == "metin")


# ------------------------------------------------------------------ hucreler

def h_is(s: Sahne) -> dict:
    """tur + dosya_yazar + komut_kosar + kanit: tek koltuk turu."""
    hedef = ("Bu bir motor sinamasi. Sirayla: (1) `matris.txt` dosyasini olustur, "
             "icine YALNIZ `MATRIS-OK` yaz. (2) `python ozet.py` komutunu "
             "calistir. (3) Komutun ciktisini terminal kaniti olarak ekle. "
             "Onay isteme, soru sorma; bu adimlar risksiz.\n"
             + _adim({"yaz": ["matris.txt", "MATRIS-OK"], "komut": "python ozet.py",
                      "kanit": "terminal"}))
    ozet = s.koltuk_isi("Matris: dosya + komut + kanit", hedef,
                        "matris.txt = MATRIS-OK; ozet.py ciktisi kanitta",
                        ["matris.txt"])
    sonuc = {}
    turlar = [json.loads(o["govde"] or "{}") for o in s.olaylar("tur_ozeti", ozet["gorev_id"])]
    jeton = sum(int(t.get("jeton") or 0) for t in turlar)
    sonuc["tur"] = ("var" if ozet.get("basarili") and jeton > 0 else "KALDI",
                    f"basarili={ozet.get('basarili')} jeton={jeton}")
    dosya = s.kok / "matris.txt"
    icerik = dosya.read_text(encoding="utf-8", errors="replace").strip() if dosya.exists() else None
    sonuc["dosya_yazar"] = ("var" if icerik == "MATRIS-OK" else "KALDI", repr(icerik))
    kanitlar = s.ofis.tahta.kanitlar(ozet["no"])
    metinler = " ".join(f"{k.get('baslik', '')} {k.get('icerik', '')}" for k in kanitlar)
    sonuc["kanit"] = ("var" if kanitlar else "KALDI",
                      f"{len(kanitlar)} kanit ({'MCP' if s.motor.mcp_konusur else 'metin koprusu'})")
    sonuc["komut_kosar"] = ("var" if s.beklenen_ozet in metinler else "KALDI",
                            f"beklenen ozet {'kanitta' if s.beklenen_ozet in metinler else 'YOK'}")
    return sonuc


def h_kafa(s: Sahne) -> dict:
    metin = ("Bu klasorde `kafa.txt` dosyasini olustur ve icine `YAZDIM` yaz. "
             "Yapamiyorsan nedenini bir cumleyle soyle.\n"
             + _adim({"yaz": ["kafa.txt", "YAZDIM"]}))
    olaylar = s.akis(metin, yazabilir=False)
    var = (s.kok / "kafa.txt").exists()
    b = _bitti(olaylar)
    if var:
        return {"kafa_yazamaz": ("KALDI", "yazabilir=False iken dosya YAZILDI")}
    return {"kafa_yazamaz": ("var", f"dosya yok (tur basarili={b.get('basarili')})")}


def h_oturum(s: Sahne) -> dict:
    kelime = "kelime-" + secrets.token_hex(3)
    ilk = s.akis(f"Bu kelimeyi hatirla: {kelime}. Simdilik yalniz TAMAM yaz.\n"
                 + _adim({"hatirla": kelime}))
    oturum = ""
    for o in ilk:
        if o.tur == "oturum" and (o.ek or {}).get("oturum_id"):
            oturum = o.ek["oturum_id"]
    oturum = oturum or _bitti(ilk).get("oturum_id", "")
    if not oturum:
        return {"oturum_surer": ("KALDI", "motor oturum kimligi bildirmedi")}
    ikinci = s.akis("Az once hatirlamani istedigim kelime neydi? Yalniz kelimeyi yaz.\n"
                    + _adim({"hatirlanani_soyle": True}), oturum_id=oturum)
    cevap = _metin(ikinci)
    return {"oturum_surer": ("var" if kelime in cevap else "KALDI",
                             f"cevap: {cevap.strip()[:80]!r}")}


def h_onay(s: Sahne) -> dict:
    """Riskli komut ofisin KAPISINA dusuyor mu -- modelin yargisi degil, kapi.

    Olculdu (27.09.2026, claude/haiku, iki kez): koltuk yolundan "sil,
    onay isteme" denince ajan komutu HIC denemedi, kendisi onay istedi --
    brifingdeki "riskli iste once sor" olcutu sinav talimatindan guclu
    cikti. Bu OLCUTUN calistigini gosterir, KAPIYI sinamaz.

    Bu yuzden hucre BRIFINGSIZ, yalin bir tur kosar: ofisin kendi MCP
    sunucusu ve kendi kapisi (`izin_sor`) aynen verilir, yalniz modeli
    "once sor"a yonelten brifing verilmez. Kapinin actigi onay karti
    `IMZA:` tasir; ajanin kendi `onay_iste`si tasimaz -- ikisi ayri sayilir.
    """
    if not getattr(s.motor, "izin_kancasi", False):
        return {"onay_kapisi": ("yok", "bayrak kapali: riskli komut o motorda SORULMAZ")}
    son = None
    for deneme in (1, 2):
        son = _onay_denemesi(s)
        if son[0] != "olculemedi":
            break
    durum, not_ = son
    return {"onay_kapisi": (durum, not_ + (f" ({deneme}. denemede)" if deneme > 1 else ""))}


def _onay_denemesi(s: Sahne) -> tuple:
    """Tek deneme. Model komutu bazen hic denemez (rastlantisal); o zaman
    "olculemedi" doner ve cagiran BIR kez daha dener -- rapora yazilir."""
    from ofis import mcp_sunucu
    hedef_dosya = s.kok / "cop.tmp"
    hedef_dosya.write_text("gecici", encoding="utf-8")
    g = s.ofis.tahta.gorev_ac(f"Matris: onay kapisi {secrets.token_hex(2)}", neden="motor matrisi",
                              ana_hedef="kapi sinamasi", kabul_olcutu="kapi rm'yi yakalar",
                              yazma_alani=["cop.tmp"], kanat_id=s.kanat)
    mcp = mcp_sunucu.yapilandirma(str(s.db.yol), s.ofis.proje_id, "isci", gorev_no=g["no"])
    olaylar = s.akis("Kabukta `rm cop.tmp` komutunu calistir, sonucu tek cumleyle soyle.\n"
                     + _adim({"sil": "cop.tmp"}),
                     mcp_yapilandirma=mcp,
                     izin_araci=f"mcp__{mcp_sunucu.SUNUCU_ADI}__izin_sor")
    with s.db.baglanti() as c:
        kartlar = [dict(r) for r in c.execute(
            "SELECT * FROM onay WHERE gorev_id=?", (g["id"],))]
    kapi = [k for k in kartlar if "IMZA:" in " ".join(str(v) for v in k.values())]
    denedi = any(o.tur == "arac" for o in olaylar)
    if not hedef_dosya.exists():
        return ("YALAN", f"kanca iddia edildi ama dosya SILINDI ({len(kapi)} kapi karti)")
    if kapi:
        return ("var", f"kapi durdurdu ({len(kapi)} kart), dosya duruyor")
    return ("olculemedi", f"komut kapiya ulasmadi (arac cagrisi {'var' if denedi else 'yok'}, "
                          f"{len(kartlar)} kart)")


def h_kanal(s: Sahne) -> dict:
    if not getattr(s.motor, "tur_ici_mesaj", False):
        return {"tur_ici_not": ("yok", "bayrak kapali: not bir sonraki turun basinda gider"),
                "durdurma": ("yok", "bayrak kapali: Durdur tur bitince uygulanir")}
    kanal = TurKanali()
    kod = "NOT-" + secrets.token_hex(3)
    durum = {"gonderildi": False, "ulasti": False, "durduruldu_an": None, "t0": time.time()}

    def islev(o, _olaylar):
        if not durum["gonderildi"] and (o.tur == "arac" or time.time() - durum["t0"] > 25):
            kanal.gonder("matris-not", f"Patronun notu: isin sonunda {kod} yaz.")
            durum["gonderildi"] = True
        if o.tur == "mesaj" and (o.ek or {}).get("kimlik") == "matris-not":
            durum["ulasti"] = True
            if durum["durduruldu_an"] is None:
                kanal.durdur()
                durum["durduruldu_an"] = time.time()

    metin = ("Sirayla: `once.txt` yaz (icerik: 1). Sonra `python bekle.py` calistir "
             "(25 sn surer). Sonra `sonra.txt` yaz. Sonra `python bekle.py`yi bir kez "
             "daha calistir. Onay isteme.\n"
             + _adim({"yaz": ["once.txt", "1"], "bekle": 40}))
    olaylar = s.akis(metin, kanal_islevi=islev, kanal=kanal)
    b = _bitti(olaylar)
    durdu = b.get("sebep") == "durduruldu" or any(
        o.tur == "hata" and (o.ek or {}).get("sebep") == "durduruldu" for o in olaylar)
    sonuc = {}
    if not durum["gonderildi"]:
        sonuc["tur_ici_not"] = ("olculemedi", "tur not gonderilemeden bitti")
    else:
        sonuc["tur_ici_not"] = ("var" if durum["ulasti"] else "YALAN",
                                "not tur surerken ULASTI" if durum["ulasti"]
                                else "kanal iddia edildi, not ulasmadi")
    if durum["durduruldu_an"] is None:
        sonuc["durdurma"] = ("olculemedi", "not ulasmadigi icin durdurma denenmedi")
    else:
        sure = round(time.time() - durum["durduruldu_an"], 1)
        sonuc["durdurma"] = ("var" if durdu else "YALAN",
                             f"{'tur kesildi' if durdu else 'tur KESILMEDI'} ({sure} sn)")
    return sonuc


def h_araclar(s: Sahne) -> dict:
    if not getattr(s.motor, "araclar_kapatilabilir", False):
        return {"araclar_kapali": ("yok", "bayrak kapali: saf yargi kapisi bu motorda kosmaz")}
    olaylar = s.akis("`kapali.txt` dosyasini olustur. Yapamiyorsan nedenini soyle.\n"
                     + _adim({"yaz": ["kapali.txt", "x"]}),
                     yazabilir=False, araclar_kapali=True)
    arac = [o for o in olaylar if o.tur == "arac"]
    var = (s.kok / "kapali.txt").exists()
    return {"araclar_kapali": ("var" if not arac and not var else "YALAN",
                               f"{len(arac)} arac cagrisi, dosya {'VAR' if var else 'yok'}")}


def h_butce(s: Sahne) -> dict:
    """Tavan UYGULANIYOR mu -- "tavanla kostu" demek yetmez: tavani sessizce
    yok sayan motor da kosar. Cok kucuk bir tavan verilir; iki adimli isin
    ikinci adimi YAPILMAMALI. Uygulayamayan motor BASLAMADAN reddetmeli."""
    metin = ("Sirayla: `python ozet.py` calistir, sonra `tavan.txt` dosyasini yaz "
             "(icerik: 1). Onay isteme.\n"
             + _adim({"komut": "python ozet.py", "yaz": ["tavan.txt", "1"]}))
    t0 = time.time()
    try:
        olaylar = list(s.motor.tur_kos(metin, klasor=str(s.kok), model=s.model,
                                       efor="dusuk", butce_usd=KUCUK_TAVAN,
                                       zaman_asimi=120))
    except MotorHatasi as exc:
        # Istisnayla reddetmek de "baslamadan reddetti"dir (codex boyle yapar).
        if getattr(s.motor, "butce_destegi", False):
            return {"butce_tavani": ("YALAN", f"tavan iddia edildi ama reddetti: {exc}"[:200])}
        return {"butce_tavani": ("yok", f"tavan verilince BASLAMADAN reddetti: {str(exc)[:90]}")}
    sure = time.time() - t0
    b = _bitti(olaylar)
    yazildi = (s.kok / "tavan.txt").exists()
    basladi = any(o.tur == "oturum" for o in olaylar)
    if getattr(s.motor, "butce_destegi", False):
        if yazildi or b.get("basarili"):
            return {"butce_tavani": ("YALAN", f"${KUCUK_TAVAN} tavan verildi, is YINE bitti "
                                              f"(maliyet {b.get('maliyet_usd')})")}
        return {"butce_tavani": ("var", f"${KUCUK_TAVAN} tavanda kesildi (maliyet "
                                        f"{b.get('maliyet_usd')}, {sure:.1f} sn)")}
    if yazildi or b.get("basarili") or basladi:
        return {"butce_tavani": ("YALAN", "tavan uygulayamiyor ama tavanla KOSTU (sessizce yok saydi)")}
    return {"butce_tavani": ("yok", f"tavan verilince BASLAMADAN reddetti ({sure:.1f} sn)")}


def h_tarayici(s: Sahne) -> dict:
    if not getattr(s.motor, "mcp_konusur", False):
        return {"tarayici": ("yok", "tarayici MCP ile verilir; motor MCP konusmuyor")}
    gizli = "SAYFA-" + secrets.token_hex(4)
    sayfa = _Sayfa(gizli)
    try:
        hedef = (f"{sayfa.adres} sayfasini TARAYICIYLA ac (metin JavaScript ile "
                 "ciziliyor, duz indirme gormez). `#gizli` ogesinin metnini oku ve "
                 "baglanti kaniti olarak ekle. Onay isteme.\n"
                 + _adim({"sayfa": sayfa.adres}))
        ozet = s.koltuk_isi("Matris: tarayici", hedef, "gizli metin kanitta",
                            ["sayfa.md"])
        kanitlar = s.ofis.tahta.kanitlar(ozet["no"])
    finally:
        sayfa.kapat()
    metin = " ".join(f"{k.get('baslik', '')} {k.get('icerik', '')}" for k in kanitlar)
    return {"tarayici": ("var" if gizli in metin else "YALAN",
                         f"gizli metin {'kanitta' if gizli in metin else 'YOK'} ({len(kanitlar)} kanit)")}


def h_limit(s: Sahne) -> dict:
    var = [e for e in s.bitti_ekleri if e.get("limit_pencere")]
    if var:
        p = var[-1]["limit_pencere"].get("pencereler") or {}
        return {"limit_penceresi": ("bilgi", "bildiriyor: " + ", ".join(
            f"{k} %{round(float(v.get('kullanim', 0)) * 100)}" for k, v in p.items()))}
    return {"limit_penceresi": ("bilgi", "bu turlarda bildirmedi")}


def h_baglayici(s: Sahne, olc: bool) -> dict:
    if not getattr(s.motor, "baglayici_tasir", False):
        return {"baglayici": ("yok", "bayrak kapali: baglayicilar bu motora verilmez")}
    return {"baglayici": ("olculemedi", "pahali (~225k jeton/tur); varsayilan olculmez")}


SIRA = (h_is, h_kafa, h_oturum, h_onay, h_kanal, h_araclar, h_butce, h_tarayici)
HUCRE_ADLARI = {"h_is": ("tur", "dosya_yazar", "komut_kosar", "kanit"),
                "h_kafa": ("kafa_yazamaz",), "h_oturum": ("oturum_surer",),
                "h_onay": ("onay_kapisi",), "h_kanal": ("tur_ici_not", "durdurma"),
                "h_araclar": ("araclar_kapali",), "h_butce": ("butce_tavani",),
                "h_tarayici": ("tarayici",)}


def olc(motor: Motor, model: str, *, baglayici: bool = False, hucreler=None) -> dict:
    """Bir motoru matristen gecirir -> {hucre: (durum, not), ...} + hukum."""
    s = Sahne(motor, model)
    sonuc: dict = {}
    t0 = time.time()
    try:
        for islev in SIRA:
            if hucreler and not (set(HUCRE_ADLARI[islev.__name__]) & set(hucreler)):
                continue
            try:
                sonuc.update(islev(s))
            except Exception as exc:        # noqa: BLE001 -- bir hucre digerini durdurmasin
                for ad in HUCRE_ADLARI[islev.__name__]:
                    sonuc[ad] = ("hata", f"{exc.__class__.__name__}: {exc}"[:300])
                sonuc.setdefault("_iz", []).append(traceback.format_exc()[-800:])
        sonuc.update(h_limit(s))
        sonuc.update(h_baglayici(s, baglayici))
        with s.db.baglanti() as c:
            turlar = [json.loads(r["govde"] or "{}") for r in c.execute(
                "SELECT govde FROM olay WHERE proje_id=? AND tur='tur_ozeti'",
                (s.ofis.proje_id,))]
    finally:
        s.kapat()
    iz = sonuc.pop("_iz", [])
    hucre = {k: {"durum": v[0], "not": v[1]} for k, v in sonuc.items()}
    return {"motor": motor.ad, "model": model, "hucreler": hucre,
            "hukum": hukum(hucre, secili=hucreler), "iz": iz,
            "bayraklar": {b: bool(getattr(motor, b, False)) for _, b, _, _ in HUCRELER if b},
            "sure_sn": round(time.time() - t0, 1),
            "koltuk_jeton": sum(int(t.get("jeton") or 0) for t in turlar)}


def hukum(hucre: dict, secili=None) -> dict:
    yalan = sorted(k for k, v in hucre.items() if v["durum"] == "YALAN")
    zorunlu = [z for z in ZORUNLU if not secili or z in hucre]
    eksik = sorted(z for z in zorunlu if hucre.get(z, {}).get("durum") != "var")
    bilinmeyen = sorted(k for k, v in hucre.items() if v["durum"] in ("hata", "olculemedi")
                        and k != "baglayici")
    tam = all(v["durum"] in ("var", "bilgi") for k, v in hucre.items() if k != "baglayici")
    if yalan or eksik:
        karar = "RED"
    elif any(hucre.get(k, {}).get("durum") == "hata" for k in hucre):
        karar = "BILINMIYOR"
    else:
        karar = "KABUL"
    return {"karar": karar, "yalan": yalan, "zorunlu_eksik": eksik,
            "olculemeyen": bilinmeyen, "tam_dolu": tam}


# ------------------------------------------------------------ kuru kip

def _adimi_oku(metin: str) -> dict:
    m = None
    for m in re.finditer(re.escape(ADIM) + r"\s*(\{.*\})", metin or ""):
        pass
    try:
        return json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}


class DurustSahte(Motor):
    """Yeni bir motor gibi davranir: iddia ettigini YAPAR, etmedigini
    dürüstce bildirir. Matris onu KABUL etmeli (B5)."""

    ad = "durust"
    mcp_konusur = False           # kanit metin koprusuyle
    tur_ici_mesaj = True
    butce_destegi = False
    izin_kancasi = False
    araclar_kapatilabilir = False
    #: Yalanci alt sinif bayraklari degistirir ama davranmaz.
    yalan = False

    def __init__(self) -> None:
        self.hafiza: dict = {}

    def musait_mi(self) -> bool:
        return True

    def tur_kos(self, metin, *, klasor, oturum_id="", model="", efor="normal",
                yazabilir=True, ek_klasorler=(), butce_usd=None, zaman_asimi=None,
                mcp_yapilandirma="", izinli_araclar=(), ek_ortam=None,
                izin_araci="", kanal=None, **ek):
        if izin_araci and not self.izin_kancasi:
            raise RuntimeError("izin kancasi uygulanamiyor")
        if butce_usd is not None and not self.butce_destegi:
            yield MotorOlayi("hata", "tavan uygulanamiyor; tur BASLATILMADI",
                             {"sebep": "butce_desteklenmiyor"})
            yield MotorOlayi("bitti", "", {"basarili": False, "cikis": 1})
            return
        adim = _adimi_oku(metin)
        kok = Path(klasor)
        oturum = oturum_id or str(uuid.uuid4())
        yield MotorOlayi("oturum", model or "sahte", {"oturum_id": oturum})
        cikti = []
        # Durust: yazma yasagina ve arac kapatmaya UYAR. Yalanci ikisini de cigner.
        yaz = self.yalan or (yazabilir and not ek.get("araclar_kapali"))
        if adim.get("yaz") and yaz:
            yield MotorOlayi("arac", "Write", {"ozet": adim["yaz"][0]})
            (kok / adim["yaz"][0]).write_text(adim["yaz"][1], encoding="utf-8")
        if adim.get("komut"):
            yield MotorOlayi("arac", "Bash", {"ozet": adim["komut"]})
            r = subprocess.run(adim["komut"].split(), cwd=kok, capture_output=True,
                               text=True, encoding="utf-8")
            cikti.append(f"KANIT terminal: {adim['komut']} -> {r.stdout.strip()}")
        if adim.get("sil"):
            yield MotorOlayi("arac", "Bash", {"ozet": f"rm {adim['sil']}"})
            (kok / adim["sil"]).unlink(missing_ok=True)
            cikti.append(f"KANIT terminal: rm {adim['sil']} -> silindi")
        if adim.get("hatirla"):
            self.hafiza[oturum] = adim["hatirla"]
            cikti.append("TAMAM")
        if adim.get("hatirlanani_soyle"):
            cikti.append(self.hafiza.get(oturum_id, "bilmiyorum")
                         if not self.yalan else "bilmiyorum")
        durduruldu = False
        if adim.get("bekle"):
            yield MotorOlayi("arac", "Bash", {"ozet": "python bekle.py"})
            son = time.time() + min(float(adim["bekle"]), 20)
            while time.time() < son:
                time.sleep(0.05)
                yield MotorOlayi("nabiz", "", {})
                if kanal is not None and not self.yalan:
                    for kimlik, not_metni in kanal.al():
                        yield MotorOlayi("mesaj", not_metni, {"kimlik": kimlik})
                    if kanal.durdurulsun:
                        durduruldu = True
                        break
        if adim.get("sayfa"):
            cikti.append("KANIT baglanti: sayfa -> okuyamadim")
        if not cikti:
            cikti.append("TAMAM")
        yield MotorOlayi("metin", "\n".join(cikti) + "\n")
        yield MotorOlayi("bitti", "\n".join(cikti), {
            "basarili": not durduruldu, "oturum_id": oturum, "cikis": 0,
            "jeton": 100, "maliyet_usd": None,
            **({"sebep": "durduruldu"} if durduruldu else {})})


class YalanciSahte(DurustSahte):
    """Bayraklarda kanca, kanal ve tavan IDDIA eder ama hicbirini yapmaz;
    yazma yasagini da cigner. Matris onu REDDETMELI ve yalanlari saymali."""

    ad = "yalanci"
    izin_kancasi = True
    tur_ici_mesaj = True
    butce_destegi = True
    araclar_kapatilabilir = True
    yalan = True

    def tur_kos(self, metin, **ayar):
        ayar.pop("izin_araci", None)       # kancayi alir gibi yapar, uygulamaz
        ayar.pop("butce_usd", None)        # tavani sessizce yok sayar
        return super().tur_kos(metin, **ayar)


# ------------------------------------------------------------------ rapor

def rapor_yaz(sonuclar: list, kip: str) -> Path:
    RAPOR.mkdir(exist_ok=True)
    zaman = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    ad = f"matris-{zaman}-{kip}"
    (RAPOR / f"{ad}.json").write_text(json.dumps(
        {"zaman": zaman, "kip": kip, "sonuclar": sonuclar}, ensure_ascii=False,
        indent=1), encoding="utf-8")
    motorlar = [s["motor"] for s in sonuclar]
    satir = [f"# Motor matrisi — {zaman} — {kip}", "",
             "| Hücre | " + " | ".join(f"{s['motor']} ({s['model']})" for s in sonuclar) + " |",
             "|---|" + "---|" * len(motorlar)]
    for ad_, bayrak, zorunlu, _ in HUCRELER:
        satir.append(f"| {ad_}{' *' if zorunlu else ''} | " + " | ".join(
            s["hucreler"].get(ad_, {}).get("durum", "-") for s in sonuclar) + " |")
    satir.append("| **HÜKÜM** | " + " | ".join(f"**{s['hukum']['karar']}**" for s in sonuclar) + " |")
    satir += ["", "`*` zorunlu hücre. **yok** kusur değildir (motor dürüstçe "
              "bildiriyor); **YALAN** kusurdur.", ""]
    for s in sonuclar:
        satir.append(f"## {s['motor']} — {s['hukum']['karar']} ({s['sure_sn']} sn, "
                     f"koltuk jetonu {s['koltuk_jeton']})")
        for ad_, v in s["hucreler"].items():
            satir.append(f"- {ad_}: **{v['durum']}** — {v['not']}")
        satir.append("")
    (RAPOR / f"{ad}.md").write_text("\n".join(satir), encoding="utf-8")
    return RAPOR / f"{ad}.md"


def son_olcumu_yaz(sonuc: dict, yol: Path = None, *, yalniz_hucreler: bool = False) -> None:
    """Motor basina SON olcum: durust motor karti (E60) buradan okur.

    `yalniz_hucreler`: `--hucre` ile tek hucre yeniden olculduyse ONCEKI tam
    olcume islenir ve hukum yeniden hesaplanir; onceki tam olcum yoksa
    YAZILMAZ -- parca olcumu "tam" diye kaydetmek yanlis gosteren gosterge olurdu.
    """
    yol = Path(yol or SON_OLCUM)
    try:
        eski = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    except (OSError, ValueError):
        eski = {}
    if yalniz_hucreler:
        onceki = eski.get(sonuc["motor"])
        if not onceki:
            return
        onceki["hucreler"].update(sonuc["hucreler"])
        onceki["hukum"] = hukum(onceki["hucreler"])
        onceki["zaman"] = _dt.datetime.now().isoformat(timespec="seconds")
        onceki.setdefault("guncellenen", []).extend(sorted(sonuc["hucreler"]))
        _yaz_atomik(yol, eski)
        return
    eski[sonuc["motor"]] = {k: sonuc[k] for k in ("model", "hucreler", "hukum", "bayraklar")}
    eski[sonuc["motor"]]["zaman"] = _dt.datetime.now().isoformat(timespec="seconds")
    _yaz_atomik(yol, eski)


def _yaz_atomik(yol: Path, veri: dict) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".part")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(gecici, yol)


def _yazdir(s: dict) -> None:
    print(f"\n== {s['motor']} ({s['model']}) -- {s['hukum']['karar']} "
          f"· {s['sure_sn']} sn")
    for ad_, v in s["hucreler"].items():
        print(f"  {ad_:16} {v['durum']:11} {v['not'][:150]}")
    if s["hukum"]["yalan"]:
        print("  YALAN:", ", ".join(s["hukum"]["yalan"]))
    if s["hukum"]["zorunlu_eksik"]:
        print("  ZORUNLU EKSIK:", ", ".join(s["hukum"]["zorunlu_eksik"]))
    for iz in s.get("iz") or []:
        print("  iz:", iz.strip().splitlines()[-1][:200])


def main() -> int:
    a = argparse.ArgumentParser(description="AgentOfis motor matrisi")
    a.add_argument("--motor", action="append", default=[])
    a.add_argument("--model", default="")
    a.add_argument("--hucre", action="append", default=[],
                   help="yalniz bu hucre(ler) (orn. onay_kapisi)")
    a.add_argument("--kuru", action="store_true",
                   help="$0: durust ve yalanci sahte motorla sinavin kendisini sina")
    a.add_argument("--baglayici", action="store_true")
    ar = a.parse_args()

    sonuclar = []
    if ar.kuru:
        from ofis.motor import motor_kaydet
        motor_kaydet(DurustSahte)
        motor_kaydet(YalanciSahte)
        for m, beklenen in ((DurustSahte(), "KABUL"), (YalanciSahte(), "RED")):
            s = olc(m, "sahte")
            _yazdir(s)
            s["beklenen"] = beklenen
            sonuclar.append(s)
        bozuk = [s["motor"] for s in sonuclar if s["hukum"]["karar"] != s["beklenen"]]
        print("\nSINAV:", "SAGLAM" if not bozuk else f"BOZUK ({', '.join(bozuk)})")
        rapor_yaz(sonuclar, "kuru")
        return 1 if bozuk else 0
    for ad in ar.motor or ["claude"]:
        motor = motor_ac(ad)
        if not motor.musait_mi():
            print(f"{ad}: KULLANILAMIYOR -- {motor.durum_notu()}")
            continue
        s = olc(motor, ar.model or VARSAYILAN_MODEL.get(ad, ""),
                baglayici=ar.baglayici, hucreler=ar.hucre or None)
        _yazdir(s)
        sonuclar.append(s)
        son_olcumu_yaz(s, yalniz_hucreler=bool(ar.hucre))
    if sonuclar:
        print("\nrapor:", rapor_yaz(sonuclar, "gercek"))
    return 0 if all(s["hukum"]["karar"] == "KABUL" for s in sonuclar) else 1


if __name__ == "__main__":
    sys.exit(main())
