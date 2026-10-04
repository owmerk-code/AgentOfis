# -*- coding: utf-8 -*-
"""Karne duman testi: isin motorunu ofis KENDI tecrubesiyle secer.

Sinanan:
* Secim kurali (`karne.sec`): deneme payi, temiz gecme orani, limit dengesi,
  esikteki hesap, kova (rol+zorluk -> rol -> hepsi), sahte ajan HIC degismez.
* Karne satirlari evde, bozuk satir atlanir.
* Koltuk: isin ilk turunda motor secilir ve KAYDA gecer; is boyunca ayni kalir;
  ayar "ajan" ise secim yok.
* Lider: kapanan is karneye yazilir; CAPRAZ kontrol -- isi yapan motorun
  tersi inceler; ayar kapaliyken yapmaz.
Gercek motor KOSMAZ: fabrika her adla sahte motor uretir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, karne, ayarlar, roller
from ofis.koltuk import Koltuk
from ofis.lider import Lider
from ofis.motor.sahte import SahteMotor

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


print("== karne duman testi ==\n")

# Secim KURALI iki motorla sinanir (gemini 04.10'da eklendi; kural motor sayisindan bagimsiz).
HARITA = {m: v for m, v in roller.kademe_haritasi().items() if m != "gemini"}


class _M:
    def __init__(self, musait=True):
        self._m = musait

    def musait_mi(self):
        return self._m


def fab(*kapali):
    return lambda ad, **a: _M(ad not in kapali)


def r(motor, ret=0, meslek="backend", zorluk="kolay", gecti=True):
    return {"motor": motor, "meslek": meslek, "zorluk": zorluk, "gecti": gecti, "ret": ret}


kok = Path(tempfile.mkdtemp(prefix="ofis-karne-"))
db = Veritabani(kok / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Karne", amac="a", basari_olcutu="b", kok_klasor=str(kok))
pid = ofis.proje_id


def sec(kayit, dolu=None, esik=0.8, ajan="claude", kapali=(), meslek="backend", zorluk="kolay"):
    return karne.sec(db, pid, ajan_motoru=ajan, meslek=meslek, zorluk=zorluk, fabrika=fab(*kapali),
                     harita=HARITA, kayitlar=kayit, doluluk=dolu or {}, esik=esik)


# --------------------------------------------------------------------------
print("1. SECIM KURALI")
sina("sahte ajanin motoru HIC degismez", sec([], ajan="sahte")[0] is None)
sina("ikinci calisan motor yoksa secim yok", sec([], kapali=("codex",))[0] is None)
m, g = sec([], dolu={"claude": 0.4, "codex": 0.1})
sina("bos karne: deneme payi, limiti bos olana", m == "codex" and "deneme" in g, g)
m, g = sec([r("claude")] * 3, dolu={"claude": 0.1, "codex": 0.9}, esik=0.95)
sina("deneme payi az kaydi olana gider (limit dolu olsa da esik altinda)", m == "codex", g)
iyi_claude = [r("claude")] * 5 + [r("codex", ret=1)] * 3 + [r("codex")] * 2
m, g = sec(iyi_claude, dolu={"claude": 0.7, "codex": 0.1})
sina("karne: temiz orani YUKSEK olan kazanir (limit daha dolu olsa da)", m == "claude", g)
yakin = [r("claude")] * 5 + [r("codex")] * 5
m, g = sec(yakin, dolu={"claude": 0.7, "codex": 0.2})
sina("karne yakin: limiti BOS olan", m == "codex" and "yakin" in g, g)
m, g = sec(iyi_claude, dolu={"claude": 0.9, "codex": 0.1}, esik=0.8)
sina("esikteki hesabin motoru aday olmaz", m == "codex", g)
m, g = sec(iyi_claude, dolu={"claude": 0.9, "codex": 0.9}, esik=0.8)
sina("hepsi esikteyse siralama karneye kalir", m == "claude", g)
kova = [r("codex", meslek="frontend")] * 5 + [r("claude", ret=2, meslek="frontend")] * 5 \
    + [r("codex", meslek="backend", zorluk="zor")] * 5 + [r("claude", ret=1, meslek="backend", zorluk="zor")] * 5
sina("kova: rol+zorluk once", sec(kova, meslek="backend", zorluk="zor")[0] == "codex")
sina("kova: rol+zorluk yoksa rol (alfabe tesadufu degil: codex)",
     sec(kova, meslek="frontend", zorluk="orta")[0] == "codex")
sina("kova: rol de yoksa hepsi (deneme payi)", sec(kova, meslek="yazar", zorluk="kolay")[0] in ("claude", "codex"))

# --------------------------------------------------------------------------
print("\n2. KARNE SATIRLARI (EVDE)")
karne.kaydet(meslek="backend", zorluk="kolay", motor="codex", model="gpt-6-luna", gecti=True, ret=0)
karne.kaydet(meslek="backend", zorluk="kolay", motor="claude", model="haiku", gecti=True, ret=2)
with open(karne._dosya(), "a", encoding="utf-8") as f:
    f.write("bozuk satir\n")
st = karne.satirlar()
sina("satirlar yazildi, bozuk satir atlandi", len(st) == 2, str(len(st)))
oz = karne.ozet("backend", "kolay")
sina("ozet: temiz oran", oz["motorlar"]["codex"]["oran"] == 1.0 and oz["motorlar"]["claude"]["oran"] == 0.0)
_ham = len(open(karne._dosya(), encoding="utf-8").readlines())
karne.kaydet(meslek="x", zorluk="", motor="", model="", gecti=True, ret=0)
sina("motorsuz satir DOSYAYA yazilmaz",
     len(open(karne._dosya(), encoding="utf-8").readlines()) == _ham)
sina("az kayitli aday + kaydi hic olmayan motor: secim COKMEZ",
     sec([r("claude")] * 5, dolu={})[0] == "codex")

# --------------------------------------------------------------------------
print("\n3. KOLTUK: MOTOR SECILIR, KAYDA GECER, IS BOYUNCA AYNI KALIR")
kanat = ofis.kanat_ac("URUN", "UR")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat, klasor=str(kok),
                  motor="claude", model="sonnet")
ofis.kadro.ise_al("cinar", "backend", kanat_id=kanat, klasor=str(kok), motor="claude", model="haiku")
acilan = []          # KOSAN turlar: (motor, model) -- fabrika musaitlik icin de cagrilir


def _kayitli(ad, cevap, liste):
    class K(SahteMotor):
        def musait_mi(self):              # koltuk bolumu iki motorla belirli kalsin
            return ad != "gemini"

        def tur_kos(self, metin, **ayar):
            liste.append((ad, ayar.get("model") or ""))
            return super().tur_kos(metin, **ayar)
    return K(cevap=cevap)


def sahte_fab(ad, **a):
    return _kayitli(ad, "Bitti.\nKANIT terminal: pytest -> 1 passed", acilan)


def is_ac(ad, zorluk="kolay"):
    return ofis.tahta.gorev_ac(ad, neden="n", ana_hedef="h", kabul_olcutu="testler gecsin",
                               yazma_alani=[f"{ad}/"], kanat_id=kanat, zorluk=zorluk,
                               zorluk_gerekce="sinama" if zorluk in ("zor", "cok_zor") else "")


koltuk = Koltuk(ofis, motor_fabrikasi=sahte_fab)
sina("VARSAYILAN: otomatik secim KAPALI (patron karari 04.10)",
     not karne.secim_acik_mi(db, pid) and ayarlar.oku(ofis)["calisma"]["motor_secimi"] == "ajan")
ayarlar.yaz(ofis, "motor_secimi", "karne")                  # bu bolum bilerek acar
g = is_ac("k1")
acilan.clear()
koltuk.kos(g["no"], "cinar")
gs = ofis.tahta.gorev(g["no"])
with db.baglanti() as c:
    ol = [x[0] for x in c.execute("SELECT govde FROM olay WHERE tur='motor_secimi'")]
sina("isin motoru secildi ve isin satirina yazildi", gs["motor_secimi"] in ("claude", "codex"),
     gs["motor_secimi"])
sina("secim gerekcesiyle kayda gecti", len(ol) == 1 and gs["motor_secimi"] in ol[0], str(ol))
sina("tur SECILEN motorla kostu", acilan and acilan[-1][0] == gs["motor_secimi"], str(acilan))
sina("model secilen motorun kademesinden (kolay -> hizli)",
     acilan and acilan[-1][1] == roller.model_sec(gs["motor_secimi"], "hizli", HARITA), str(acilan))
# ikinci tur: ayni motor, yeni secim yok
ofis.tahta.geri_gonder(g["no"], ofis.tahta.gorev(g["no"])["revizyon"], gerekce="x", gonderen="demir")
acilan.clear()
koltuk.kos(g["no"], "cinar")
with db.baglanti() as c:
    n_ol = c.execute("SELECT COUNT(*) FROM olay WHERE tur='motor_secimi'").fetchone()[0]
sina("ikinci tur AYNI motorla, yeniden secim YOK", acilan[-1][0] == gs["motor_secimi"] and n_ol == 1,
     f"{acilan} {n_ol}")

g_zor = is_ac("kzor", zorluk="zor")
acilan.clear()
koltuk.kos(g_zor["no"], "cinar")
_m = ofis.tahta.gorev(g_zor["no"])["motor_secimi"]
sina("zor is: secilen motorun GUCLU modeli", acilan and acilan[-1][1] == roller.model_sec(
    _m, "guclu", HARITA), str(acilan))

ayarlar.yaz(ofis, "motor_secimi", "ajan")
g2 = is_ac("k2")
acilan.clear()
koltuk.kos(g2["no"], "cinar")
sina("ayar 'ajan': secim YOK, ajanin kendi motoru",
     acilan[-1][0] == "claude" and not ofis.tahta.gorev(g2["no"])["motor_secimi"], str(acilan))
ayarlar.yaz(ofis, "motor_secimi", "karne")

# --------------------------------------------------------------------------
print("\n4. LIDER: KARNEYE YAZAR, CAPRAZ KONTROL")
inceleme_motoru = []


def lider_fab(ad, **a):
    return _kayitli(ad, "KARAR: kapat\nPATRONA: tamam", inceleme_motoru)


onceki = len(karne.satirlar())
yapan = ofis.tahta.gorev(g["no"])["motor_secimi"]
inceleme_motoru.clear()
Lider(ofis, motor_fabrikasi=lider_fab).incele(g["no"], lider_ad="demir")
sina("kapanan is karneye yazildi", len(karne.satirlar()) == onceki + 1)
son = karne.satirlar()[-1]
sina("  satirda isi YAPAN motor, rol, zorluk, ret sayisi",
     son["motor"] == yapan and son["meslek"] == "backend" and son["zorluk"] == "kolay"
     and son["ret"] == 1, str(son))
diger = "codex" if yapan == "claude" else "claude"
sina("CAPRAZ: inceleme isi yapanin TERSI motorda", inceleme_motoru and inceleme_motoru[0][0] == diger,
     f"yapan={yapan} inceleme={inceleme_motoru}")
with db.baglanti() as c:
    cap = c.execute("SELECT COUNT(*) FROM olay WHERE tur='capraz_inceleme'").fetchone()[0]
sina("  capraz kontrol kayda gecti", cap == 1)

ayarlar.yaz(ofis, "capraz_inceleme", False)
g3 = is_ac("k3")
ayarlar.yaz(ofis, "motor_secimi", "ajan")
koltuk.kos(g3["no"], "cinar")
inceleme_motoru.clear()
Lider(ofis, motor_fabrikasi=lider_fab).incele(g3["no"], lider_ad="demir")
sina("capraz KAPALI: inceleme liderin kendi motorunda", inceleme_motoru[0][0] == "claude",
     str(inceleme_motoru))
oku = ayarlar.oku(ofis)["calisma"]
sina("ayarlar okunur", oku["motor_secimi"] == "ajan" and oku["capraz_inceleme"] is False
     and isinstance(oku["karne"], dict))
try:
    ayarlar.yaz(ofis, "motor_secimi", "rastgele")
    sina("gecersiz secim reddedilir", False)
except ayarlar.AyarHatasi:
    sina("gecersiz secim reddedilir", True)

print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
