# -*- coding: utf-8 -*-
"""Tek tur ve bedel duman testi (03.10.2026, "ofis carpani").

Olculdu: liderin her turu ~12-24 bin jetonluk on eki 1 saatlik onbellege
BASTAN yaziyor (duz `claude -p`de de: Claude Code'un davranisi). Triyaj +
plan iki turdu, yani bu bedel iki kez odeniyordu. Gercek terminal kipinde
isci turunun dolari OLCULEMIYOR ve carpanda $0 gorunuyordu.

Sinanan:

* Triyaj istemi planin TAMAMINI tasiyor (kadro, cikti bicimi, kurallar),
  baglayici envanteri TEK kopya.
* Gecerli plan triyajda gelirse plan turu HIC kosmaz, is acilir.
* Gecersiz plan SESSIZCE kabul edilmez: ret kayda gecer ve plan turu ret
  metnini gorerek kosar (ret ogretir).
* `cevap` kararinda gelen plan yok sayilir; is acilmaz.
* Jeton dokumu: tur basina toplanir, terminal kipinde mesaj basina son deger.
* Fiyat: olculmus birimden tahmin; olculmemis modelde tahmin YOK; tahmin
  `maliyet_usd`ye (olcum) yazilmaz.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, kullanim
from ofis.sohbet import Sohbet
from ofis.motor.sahte import SahteMotor
from ofis.motor.tip import dokum_ekle
from ofis.motor.claude import ClaudeMotoru
from ofis.motor import tui as tui_mod

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


def triyaj(karar, gerekce, **ek):
    return "```json\n" + json.dumps(
        {"karar": karar, "gerekce": gerekce, **ek}, ensure_ascii=False) + "\n```"


print("== tek tur ve bedel duman testi ==\n")

kok = Path(tempfile.mkdtemp(prefix="ofis-tektur-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Tek Tur", amac="a", basari_olcutu="b", kok_klasor=str(kok))
kanat = ofis.kanat_ac("URUN", "UR")
for ad, meslek, lider_mi in (("demir", "lider", True), ("cinar", "backend", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi,
                      tur="eller", motor="sahte", klasor=str(kok))

KOL = {"baslik": "API yaz", "sahip": "cinar", "neden": "Siparis alinamiyor",
       "kabul_olcutu": "pytest yesil", "govde": "yaz", "yazma_alani": ["api/"],
       "zorluk": "kolay"}
PLAN = {"bol": False, "gerekce": "Tek parca is.", "kollar": [KOL]}
kutu = {"triyaj": "", "plan_turu": [], "istekler": []}


def plan_turu_mu(metin: str) -> bool:
    return "## KADRON" in metin and "# PATRONUN MESAJI" not in metin


class Motor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        kutu["istekler"].append(metin)
        if "# PATRONUN MESAJI" in metin:
            self.cevap = kutu["triyaj"]
        elif plan_turu_mu(metin):
            kutu["plan_turu"].append(metin)
            self.cevap = "```json\n" + json.dumps(PLAN) + "\n```"
        elif "PATRONUN ISTEGI" in metin:
            self.cevap = "API yazildi."
        else:
            self.cevap = "KANIT terminal: pytest -> 1 passed"
        return super().tur_kos(metin, **ayar)


sohbet = Sohbet(ofis, motor_fabrikasi=lambda ad, **a: Motor(cevap=""))


def olay_say(tur):
    with db.baglanti() as c:
        return c.execute("SELECT COUNT(*) FROM olay WHERE proje_id=? AND tur=?",
                         (ofis.proje_id, tur)).fetchone()[0]


# --------------------------------------------------------------------------
print("1. TRIYAJ ISTEMI PLANI TASIYOR")
m = sohbet.triyaj_metni("api yazilsin", kanat_id=kanat)
sina("PLAN bolumu var", "# PLAN (yalniz karar=kendi ya da dagit ise)" in m)
sina("kadro plan bolumunde", "## KADRON" in m and "**cinar**" in m)
sina("plan JSON'u `plan` alanina", "`plan` alanina koy" in m)
sina("plan icin 'yalnizca bu JSON' denmiyor (ic ice)",
     "Yalnizca su JSON'u ver, baska hicbir sey yazma:" in m
     and m.count("Yalnizca su JSON'u ver") == 1)
sina("zorluk kurallari tasindi", "`cok_zor`" in m)
sina("baglayici envanteri TEK kopya", m.count("## BAGLAYICILAR") == 1,
     f"({m.count('## BAGLAYICILAR')})")
sina("plan zorunlulugu kurali", "`plan` dolu olmali" in m)
sina("plan turu metni degismedi (baglayici orada var)",
     "## BAGLAYICILAR" in ofis.orkestra.plan_metni("x", kanat)
     and "Yalnizca su JSON'u ver" in ofis.orkestra.plan_metni("x", kanat))

# --------------------------------------------------------------------------
print("\n2. GECERLI PLAN -> PLAN TURU KOSMAZ")
kutu["triyaj"] = triyaj("dagit", "uzmanlik", hedef="API yazilsin", plan=PLAN)
onceki = len(ofis.tahta.liste())
olaylar = list(sohbet.konus("api yazilsin", azami_tik=2))
turler = [o["tur"] for o in olaylar]
sina("plan turu KOSMADI", kutu["plan_turu"] == [], f"({len(kutu['plan_turu'])})")
sina("is acildi", len(ofis.tahta.liste()) == onceki + 1)
sina("plan olayi akti (gerekceyle)",
     any(o["tur"] == "plan" and "Tek parca" in o["govde"] for o in olaylar))
sina("isin sahibi plandaki ajan", ofis.tahta.liste()[-1]["sahip"] == "cinar")
sina("'plan triyajda' kayda gecti", olay_say("plan_triyajda") == 1)
sina("rapor uretildi", "rapor" in turler)

# --------------------------------------------------------------------------
print("\n3. GECERSIZ PLAN -> RET OGRETIR, PLAN TURU KOSAR")
kutu["plan_turu"].clear()
bozuk = {"bol": False, "gerekce": "x", "kollar": [dict(KOL, sahip="hayalet")]}
kutu["triyaj"] = triyaj("dagit", "uzmanlik", hedef="API yazilsin 2", plan=bozuk)
onceki = len(ofis.tahta.liste())
list(sohbet.konus("api yazilsin 2", azami_tik=2))
sina("plan turu kostu", len(kutu["plan_turu"]) == 1, f"({len(kutu['plan_turu'])})")
sina("plan turu reddi GORDU",
     kutu["plan_turu"] and "ONCEKI PLANIN REDDEDILDI" in kutu["plan_turu"][0]
     and "hayalet" in kutu["plan_turu"][0])
sina("is plan turunun planiyla acildi",
     len(ofis.tahta.liste()) == onceki + 1 and ofis.tahta.liste()[-1]["sahip"] == "cinar")
with db.baglanti() as c:
    uy = [r[0] for r in c.execute("SELECT govde FROM olay WHERE proje_id=? AND tur='uyari'",
                                  (ofis.proje_id,))]
sina("ret kayda gecti", any("Triyajdaki plan reddedildi" in u for u in uy))

# --------------------------------------------------------------------------
print("\n4. PLANSIZ DAGIT -> ESKI YOL")
kutu["plan_turu"].clear()
kutu["triyaj"] = triyaj("dagit", "uzmanlik", hedef="API yazilsin 3")
list(sohbet.konus("api yazilsin 3", azami_tik=2))
sina("plan turu kostu", len(kutu["plan_turu"]) == 1)
sina("plansiz dagit ret kaydi YAZMAZ (ret yok, plan yok)",
     not any("API yazilsin 3" in u for u in uy))

# --------------------------------------------------------------------------
print("\n5. CEVAP KARARINDA PLAN YOK SAYILIR")
kutu["plan_turu"].clear()
onceki = len(ofis.tahta.liste())
kutu["triyaj"] = triyaj("cevap", "bilgi", cevap="14 gun.", plan=PLAN)
olaylar = list(sohbet.konus("iade kac gun?"))
sina("is acilmadi", len(ofis.tahta.liste()) == onceki)
sina("cevap gitti", any(o["tur"] == "cevap" and "14 gun" in o["govde"] for o in olaylar))

# --------------------------------------------------------------------------
print("\n6. SARTNAME KAPISI ACIKKEN HAZIR PLAN KULLANILMAZ")
kutu["plan_turu"].clear()
try:
    from ofis import sartname as _sart
    _eski = _sart.denetle
    _sart.denetle = lambda *a, **k: ""
    sohbet.orkestra.hedef_ver("API yazilsin 4", hazir_plan=PLAN, sartname_denetimi=True)
    _sart.denetle = _eski
    sina("plan turu kostu (sartname plan turuna bagli)", len(kutu["plan_turu"]) == 1)
except Exception as exc:                          # noqa: BLE001 -- test cokmesin
    sina("sartname yolu", False, f"({exc})")

# --------------------------------------------------------------------------
print("\n7. JETON DOKUMU")
d = dokum_ekle({}, {"input_tokens": 3, "output_tokens": 7, "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 50,
                    "cache_creation": {"ephemeral_1h_input_tokens": 40}})
d = dokum_ekle(d, {"input_tokens": 1, "cache_creation_input_tokens": 5})
sina("alanlar toplanir", d == {"girdi": 4, "cikti": 7, "onbellek_okuma": 100,
                               "onbellek_yazma": 55, "onbellek_yazma_1sa": 40}, f"({d})")

cm = ClaudeMotoru.__new__(ClaudeMotoru)
durum = {"oturum_id": "x", "metin": [], "kullanim": {}}
kul = {"input_tokens": 2, "output_tokens": 10, "cache_read_input_tokens": 1000,
       "cache_creation_input_tokens": 500}
for cikti in (5, 10):                             # ayni id yinelenir: son deger
    cm.tui_cevir({"type": "assistant", "message": {"id": "m1", "model": "claude-x",
                                                   "usage": dict(kul, output_tokens=cikti),
                                                   "content": []}}, durum)
cm.tui_cevir({"type": "assistant", "message": {"id": "m2", "usage": kul, "content": []}}, durum)
top = tui_mod._dokum_topla(durum.get("dokum_mesaj"))
sina("terminal: mesaj basina SON deger, mesajlar toplanir",
     top and top["cikti"] == 20 and top["onbellek_okuma"] == 2000, f"({top})")
sina("terminal: dokum yoksa None (sifir degil)", tui_mod._dokum_topla({}) is None)

durum2 = {"metin": [], "jeton": 0, "jeton_dokumu": {}}
cm._mesaji_cevir({"type": "result", "usage": kul, "total_cost_usd": 0.1}, durum2)
sina("arka kip: sonuc kullanimi dokume girer",
     durum2["jeton_dokumu"].get("onbellek_yazma") == 500, f"({durum2['jeton_dokumu']})")

# --------------------------------------------------------------------------
print("\n8. FIYAT: OLCULMUS BIRIMDEN TAHMIN")
os.environ["OFIS_EV"] = tempfile.mkdtemp(prefix="ofis-tektur-ev-")
dk = {"girdi": 0, "cikti": 1000, "onbellek_okuma": 10000, "onbellek_yazma": 10000,
      "onbellek_yazma_1sa": 10000}
sina("olculmemis modelde tahmin YOK", kullanim.tahmini_maliyet("model-a", dk) is None)
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"maliyet_usd": None, "jeton_dokumu": dk,
                                           "model": "model-a"}, yol="isci")
with db.baglanti() as c:
    v = json.loads(c.execute("SELECT govde FROM olay WHERE tur='tur_ozeti' ORDER BY rowid DESC"
                             ).fetchone()[0])
sina("birim yokken tur ozetinde tahmin alani YOK", "maliyet_tahmini_usd" not in v)
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"maliyet_usd": 0.026, "jeton_dokumu": dk,
                                           "model": "model-a"}, yol="lider")
sina("olculen tur birimi ogretti", kullanim.tahmini_maliyet("model-a", dk) == 0.026)
sina("baska model yine bilinmiyor", kullanim.tahmini_maliyet("model-b", dk) is None)
yarim = dict(dk, onbellek_yazma=5000, onbellek_yazma_1sa=5000, onbellek_okuma=5000, cikti=500)
sina("tahmin agirlikla olcekli", kullanim.tahmini_maliyet("model-a", yarim) == 0.013,
     f"({kullanim.tahmini_maliyet('model-a', yarim)})")
bes = dict(dk, onbellek_yazma_1sa=0)
sina("5 dakikalik yazma 1 saatlikten ucuz",
     kullanim.tahmini_maliyet("model-a", bes) < kullanim.tahmini_maliyet("model-a", dk))
kullanim.tur_ozeti_yaz(db, ofis.proje_id, {"maliyet_usd": None, "jeton_dokumu": dk,
                                           "model": "model-a"}, yol="isci")
with db.baglanti() as c:
    v = json.loads(c.execute("SELECT govde FROM olay WHERE tur='tur_ozeti' ORDER BY rowid DESC"
                             ).fetchone()[0])
sina("terminal turu tahmin aldi", v.get("maliyet_tahmini_usd") == 0.026, f"({v})")
sina("olcum alani BOS kaldi (tahmin olcum sanilmaz)", v.get("maliyet_usd") is None)
sina("dokum tur ozetinde", v.get("jeton_dokumu") == dk)
sina("dokumsuz turda tahmin yok", kullanim.tahmini_maliyet("model-a", None) is None)

# --------------------------------------------------------------------------
print("\n9. ANLATTI, YAPMADI -> ISTENEN DOSYA YOKSA IS AJANA")
from ofis.sohbet import yazilacak_dosyalar
(kok / "satislar.csv").write_text("a,b\n", encoding="utf-8")
sina("yazma fiili + olmayan dosya", yazilacak_dosyalar(
    "satislar.csv ciroyu bul; rapor.md dosyasina yaz", kok) == ["rapor.md"])
sina("soru (fiil yok) -> bos", yazilacak_dosyalar("rapor.md nerede?", kok) == [])
sina("var olan girdi dosyasi sayilmaz",
     yazilacak_dosyalar("satislar.csv'yi oku ve ozetle yaz", kok) == [])
sina("alt klasorlu yol", yazilacak_dosyalar("site/index.html yap", kok) == ["site/index.html"])

kutu["plan_turu"].clear()
onceki = len(ofis.tahta.liste())
kutu["triyaj"] = triyaj("cevap", "okudum", cevap="Ciro 11.185.")
olaylar = list(sohbet.konus("satislar.csv toplam ciroyu bul; rapor.md dosyasina yaz", azami_tik=2))
sina("cevap patrona GITMEDI, triyaj dagit oldu", olaylar[0]["govde"] == "dagit")
sina("is acildi", len(ofis.tahta.liste()) == onceki + 1)
with db.baglanti() as c:
    uy = [r[0] for r in c.execute("SELECT govde FROM olay WHERE proje_id=? AND tur='uyari'",
                                  (ofis.proje_id,))]
sina("kayda gecti (dosya adiyla)", any("rapor.md" in u and "yazdirmadan" in u for u in uy))

onceki = len(ofis.tahta.liste())
kutu["triyaj"] = triyaj("cevap", "bilgi", cevap="Henuz yok.")
olaylar = list(sohbet.konus("rapor.md nerede?"))
sina("soru cevap yolunda kaldi",
     olaylar[0]["govde"] == "cevap" and len(ofis.tahta.liste()) == onceki)

# --------------------------------------------------------------------------
print("\n10. LIDER TAM GUC (yalin kip YOK)")
from ofis import ayarlar
sina("yalin kip ayari yok", "lider_yalin" not in ayarlar.oku(ofis)["calisma"])
sina("motor sozlesmesinde yalin alani yok", not hasattr(SahteMotor, "yalin"))

# --------------------------------------------------------------------------
print("\n11. ONBELLEK 5 DAKIKA")
import inspect as _ins
from ofis.motor import claude as _cl
sina("Claude tur ortami 5 dakikalik onbellek ister",
     _cl.TUR_ORTAMI.get("CLAUDE_CODE_PROMPT_CACHE_TTL") == "5m")
_src = _ins.getsource(_cl)
sina("her ortam kurulumu TUR_ORTAMI'ni tasir (arka, terminal, limit okuma)",
     _src.count("ek={**TUR_ORTAMI") == 4, f"({_src.count('ek={**TUR_ORTAMI')})")

# --------------------------------------------------------------------------
print("\n12. RET OLCUTE BAGLIDIR")
from ofis.lider import Lider, ret_dayanagi
OLC = ["sayfada menu ve iletisim bolumleri var; baslik 'Kahve Duragi'"]
sina("olcutten alinti (Turkce harf/buyuk-kucuk farkiyla) dayanaktir",
     ret_dayanagi('KARAR: geri -- x\nOLCUT: "Menü ve İletişim bölümleri var"', OLC).startswith("OLCUT"))
sina("olcutte OLMAYAN alinti dayanak degil",
     ret_dayanagi('KARAR: geri -- x\nOLCUT: "zaman damgasi gosterilmeli"', OLC) == "")
sina("tek kelimelik alinti dayanak degil (her olcutte gecer)",
     ret_dayanagi('KARAR: geri -- x\nOLCUT: "menu"', OLC) == "")
sina("BOZULDU dayanaktir", ret_dayanagi("KARAR: geri -- x\nBOZULDU: a.py silindi", OLC) != "")
sina("dayanaksiz ret dayanaksizdir", ret_dayanagi("KARAR: geri -- surec kaniti yok", OLC) == "")
sina("inceleme istemi dayanagi sart kosuyor",
     'OLCUT: "<kabul olcutunden karsilanmayan kisim, aynen>"' in _ins.getsource(Lider.inceleme_metni))


def _inceleme_isi(ad):
    g = ofis.tahta.gorev_ac(ad, neden="n", ana_hedef="kafe sitesi", kabul_olcutu=OLC[0],
                            yazma_alani=[f"{ad}/"], kanat_id=kanat, sahip="cinar")
    g = ofis.tahta.gorev(g["no"])
    if g["durum"] == "hazir":
        ofis.tahta.sahiplen(g["no"], "cinar", g["revizyon"])
    ofis.tahta.kanit_ekle(g["no"], "terminal", "yazildi", "ok", "cinar")
    ofis.tahta.incelemeye_ver(g["no"], ofis.tahta.gorev(g["no"])["revizyon"])
    return g["no"]


def _hakem(cevaplar, sorular):
    class H(SahteMotor):
        def tur_kos(self, metin, **ayar):
            sorular.append(metin)
            self.cevap = cevaplar[min(len(sorular), len(cevaplar)) - 1]
            return super().tur_kos(metin, **ayar)
    return lambda ad, **a: H(cevap="")


def _olaylar(tur):
    with db.baglanti() as c:
        return [r[0] for r in c.execute("SELECT govde FROM olay WHERE proje_id=? AND tur=?",
                                        (ofis.proje_id, tur))]


# a) dayanaksiz ret -> sorulur -> lider KAPATIR
q = []
no = _inceleme_isi("reta")
s = Lider(ofis, motor_fabrikasi=_hakem(
    ["Dosyalar dogru.\nKARAR: geri -- surecin kaniti yok",
     "KARAR: kapat\nPATRONA: Site hazir."], q)).incele(no, lider_ad="demir")
sina("dayanaksiz retten sonra DAYANAK soruldu",
     len(q) == 2 and "DAYANAK yazmadin" in q[1] and OLC[0] in q[1], str(len(q)))
sina("  lider kapatinca is KAPANDI", s["hukum"] == "kapat" and ofis.tahta.gorev(no)["durum"] == "bitti")
sina("  kayda gecti", any("KAPATTI" in o for o in _olaylar("ret_dayanaksiz")))

# b) dayanakli ret -> sorulmaz, ajan maddeyi gorur
q = []
no = _inceleme_isi("retb")
s = Lider(ofis, motor_fabrikasi=_hakem(
    ['KARAR: geri -- iletisim bolumu yok\nOLCUT: "menu ve iletisim bolumleri var"'], q)).incele(
    no, lider_ad="demir")
sina("dayanakli ret ek tur ISTEMEZ", len(q) == 1, str(len(q)))
sina("  is geri gitti, gerekcede olcut maddesi var",
     s["hukum"] == "geri" and "OLCUT: menu ve iletisim bolumleri var" in s["gerekce"], s.get("gerekce", ""))

# c) BOZULDU -> sorulmaz
q = []
no = _inceleme_isi("retc")
s = Lider(ofis, motor_fabrikasi=_hakem(
    ["KARAR: geri -- baska dosya bozuldu\nBOZULDU: index.css silindi"], q)).incele(no, lider_ad="demir")
sina("BOZULDU'lu ret ek tur istemez ve gecer", len(q) == 1 and s["hukum"] == "geri")

# d) ikinci kez de dayanaksiz -> ret gecer (kapi kendiliginden kapatmaz), kayda duser
q = []
no = _inceleme_isi("retd")
s = Lider(ofis, motor_fabrikasi=_hakem(
    ["KARAR: geri -- belgelenmedi", "KARAR: geri -- yine belgelenmedi"], q)).incele(no, lider_ad="demir")
sina("iki kez dayanaksiz: is KENDILIGINDEN KAPANMAZ, geri gider",
     len(q) == 2 and s["hukum"] == "geri" and ofis.tahta.gorev(no)["durum"] != "bitti")
sina("  'baglanamadi' kayda gecti", any("BAGLANAMADI" in o for o in _olaylar("ret_dayanaksiz")))

# e) kapatan inceleme ek tur istemez
q = []
no = _inceleme_isi("rete")
Lider(ofis, motor_fabrikasi=_hakem(["KARAR: kapat\nPATRONA: tamam"], q)).incele(no, lider_ad="demir")
sina("kapatan inceleme tek tur", len(q) == 1)

# --------------------------------------------------------------------------
print("\n13. PATRONUN ISTEDIGI BELGE SOHBETE GIDER (G17)")
import time as _t
from ofis.ekler import gonderilmemisler
(kok / "eski.docx").write_bytes(b"girdi")          # isten ONCE vardi: girdi
_t.sleep(2.5)                                       # is saati saniye hassas + 1 sn pay
gb = ofis.tahta.gorev_ac("belge", neden="n", ana_hedef="h", kabul_olcutu="docx var",
                         yazma_alani=["toplanti.docx"], kanat_id=kanat)
_t.sleep(1.2)
(kok / "toplanti.docx").write_bytes(b"belge")
ofis.tahta.kanit_ekle(gb["no"], "terminal", "yazildi", "python uret.py -> tamam", "cinar")
sina("kanitta adi gecmeyen belge eskiden KACIYORDU", gonderilmemisler(ofis, [gb["id"]]) == [])
sina("patronun mesajinda / liderin cevabinda adi gecen belge EKLENIR",
     gonderilmemisler(ofis, [gb["id"]], ek_metinler=("Dosya: toplanti.docx", "")) == ["toplanti.docx"])
sina("isten ONCE duran belge (girdi) eklenmez",
     gonderilmemisler(ofis, [gb["id"]], ek_metinler=("eski.docx'u oku",)) == [])
sina("diskte olmayan belge eklenmez",
     gonderilmemisler(ofis, [gb["id"]], ek_metinler=("yok.docx",)) == [])
sina("kod dosyasi eklenmez", gonderilmemisler(ofis, [gb["id"]], ek_metinler=("uret.py",)) == [])
_ssrc = _ins.getsource(Sohbet._taslaktan_rapor) + _ins.getsource(Sohbet._rapor)
sina("rapor patronun mesajini ve liderin cevabini da tarar (kablo)",
     "ek_metinler=(metin, mesaj)" in _ssrc and "ek_metinler=(mesaj,)" in _ssrc
     and "self._taslaktan_rapor(plan, mesaj)" in _ssrc)

# --------------------------------------------------------------------------
print("\n14. PLANIN DISINA YAZILAN IZIN PLANA TASINIR (G14)")
from ofis.sohbet import _hazir_plan
_iz = [{"eylem": "git push", "alinti": "pushla"}]
sina("ustteki izin plana tasinir",
     (_hazir_plan({"plan": {"kollar": []}, "izinler": _iz}) or {}).get("izinler") == _iz)
sina("plandaki izin EZILMEZ",
     (_hazir_plan({"plan": {"kollar": [], "izinler": ["p"]}, "izinler": _iz}) or {}).get("izinler") == ["p"])
sina("plan yoksa None", _hazir_plan({"izinler": _iz}) is None)
kutu["plan_turu"].clear()
kutu["triyaj"] = triyaj("dagit", "uzmanlik", hedef="API yazilsin ve pushla", plan=PLAN, izinler=_iz)
list(sohbet.konus("api yazilsin ve pushla", azami_tik=2))
with db.baglanti() as c:
    _izr = [tuple(r) for r in c.execute("SELECT desen, alinti FROM izin")]
    _uy = [r[0] for r in c.execute("SELECT govde FROM olay WHERE tur='uyari'")]
sina("izin gecerli ve ise yazildi (patronun sozune karsi olculdu)",
     any("push" in d for d, _ in _izr), str(_izr))
sina("tasima kayda gecti", any("planin DISINA" in u for u in _uy))
sina("plan turu KOSMADI", kutu["plan_turu"] == [])

# --------------------------------------------------------------------------
print("\n15. PATRONA TASLAGI DEFTER SATIRLARINDA BITER (G16)")
from ofis.lider import patrona_ayikla
_t16 = patrona_ayikla("KARAR: kapat\nPATRONA: b1, b2, b3 yazildi.\nHAFIZA: yok\n"
                      "KANIT terminal: python -c x\nOLCUT: \"a\"\nDURUM: bitti")
sina("HAFIZA / KANIT / OLCUT / DURUM satiri patrona gitmez", _t16 == "b1, b2, b3 yazildi.", repr(_t16))
sina("duz cumledeki 'kanit' kelimesi kesmez",
     patrona_ayikla("KARAR: kapat\nPATRONA: Kanit terminal ciktisi temiz.") == "Kanit terminal ciktisi temiz.")

print(f"\n{GECEN} gecti, {KALAN} kaldi")
sys.exit(1 if KALAN else 0)
