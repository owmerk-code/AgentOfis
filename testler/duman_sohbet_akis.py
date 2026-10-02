# -*- coding: utf-8 -*-
"""TAKIM SOHBETI CLAUDE CODE GIBI duman testi (02.10.2026).

Patron: *"senle ya da codex'le konusurken cevaplar nasil ilerliyorsa ayni
sekilde calissin"*. Jeton yakmaz, sahte motorla. Sinanan:
  1. istekten dogan is ISTEGE baglanir (`gorev.istek_id`)
  2. akis her ogeye `istek` koyar; istek canli durumu tasir (calisan ajan,
     son durum notu, adim sayisi, adim listesi)
  3. adim ozeti okunur (Codex'in kod kipi sarmali acilir)
  4. rapor yonergesi BASLIKLI kalip istemez (sade cevap)
  5. panel: adimlar istegin altinda katli, once liderin cumlesi, canli sure,
     kaydirma korunur
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ofis import Ofis, Veritabani, takim  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== sohbet akisi (Claude Code gibi) duman testi ==\n")
_d = Path(tempfile.mkdtemp(prefix="ofis-sohbet-akis-"))
ofis = Ofis.proje_ac(Veritabani(_d / "o.sqlite3"), "Akis", amac="a", basari_olcutu="b", kok_klasor=str(_d))
kn = ofis.kanat_ac("ANA", "AN")
for ad, meslek, lider in (("demir", "lider", True), ("cinar", "backend", False)):
    ofis.kadro.ise_al(ad, meslek, kanat_id=kn, lider_mi=lider, tur="eller", motor="sahte", klasor=str(_d))

KOL = [{"baslik": "API yaz", "sahip": "cinar", "neden": "n", "kabul_olcutu": "pytest yesil",
        "govde": "yaz", "yazma_alani": ["api/"]}]
_istekler = []


class _Motor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps({"karar": "dagit", "gerekce": "g", "hedef": "API"}) + "\n```"
        elif '"kollar"' in metin:
            self.cevap = "```json\n" + json.dumps({"bol": False, "gerekce": "tek", "kollar": KOL}) + "\n```"
        elif "PATRONUN ISTEGI" in metin:
            _istekler.append(metin)
            self.cevap = "API yazildi, testler yesil."
        else:
            self.cevap = "KANIT terminal: pytest -> 4 passed"
        return super().tur_kos(metin, **ayar)


list(Sohbet(ofis, motor_fabrikasi=lambda ad, **a: _Motor(cevap="")).konus("api yazilsin", azami_tik=2))
with ofis.db.baglanti() as c:
    m = c.execute("SELECT id FROM mesaj WHERE govde = 'api yazilsin'").fetchone()
    g = c.execute("SELECT no, istek_id FROM gorev ORDER BY no DESC LIMIT 1").fetchone()

print("1. is istege baglanir")
sina("istekten dogan isin istek_id'si o mesaj", g is not None and m is not None and g["istek_id"] == m["id"],
     str(g and dict(g)))

print("\n2. akis istegi ve canli durumu tasir")
db = ofis.db
db.olay_yaz(ofis.proje_id, "ajan_sohbet", "API hazir", ajan_ad="cinar",
            gorev_id=ofis.tahta.gorev(g["no"])["id"])
ak = takim.akis(ofis)
istek = next(x for x in ak if x["tur"] == "sohbet" and x["metin"].startswith("api yazilsin"))
sina("istek ogesinin `istek`i kendisi", istek["istek"] == istek["id"])
sina("ajanin mesaji ayni istege ait", any(x["tur"] == "bildirim" and x["istek"] == istek["id"] for x in ak))
d = istek.get("istek_durum") or {}
sina("istek durumu: bagli is ve adim sayisi", d.get("isler") and d.get("adim", 0) >= 1, str(d)[:200])
sina("  adim listesi okunur (ajan + arac adi)", d.get("adimlar") and d["adimlar"][0].get("ajan") == "cinar",
     str(d.get("adimlar"))[:200])
from ofis.tahta import HAZIR  # noqa: E402,F401
_g2 = ofis.tahta.gorev_ac("ikinci", neden="n", ana_hedef="h", kabul_olcutu="k", govde="g",
                          kanat_id=kn, sahip="cinar", yazma_alani=["b/"])
with db.baglanti() as c:
    c.execute("UPDATE gorev SET istek_id = ? WHERE no = ?", (istek["id"], _g2["no"]))
ofis.tahta.sahiplen(_g2["no"], "cinar", ofis.tahta.gorev(_g2["no"])["revizyon"])
db.olay_yaz(ofis.proje_id, "durum_notu", "testleri kosuyorum\nikinci satir", ajan_ad="cinar",
            gorev_id=ofis.tahta.gorev(_g2["no"])["id"])
d2 = takim.istek_durumlari(ofis, [istek["id"]])[istek["id"]]
sina("calisan is ve SON durum notu (ilk satir)", d2["aktif"] and d2["aktif"]["sahip"] == "cinar"
     and d2["son"] == "testleri kosuyorum" and d2["aktif"]["basladi"], str(d2)[:200])

print("\n3. adim ozeti")
sina("mcp araci kisaltilir", takim.adim_ozeti("mcp__tarayici__browser_navigate\nhttps://x.com")
     == {"ad": "browser_navigate", "ozet": "https://x.com"})
sina("Codex kod kipi sarmali acilir", takim.adim_ozeti(
    'Bash\nconst r = await tools.mcp__tarayici__browser_type({target:"f2",text:"Galata"}); text(r);')["ad"]
     == "browser_type")
sina("duz kabuk komutu oldugu gibi", takim.adim_ozeti("Bash\ncurl -s https://x")["ozet"] == "curl -s https://x")

print("\n4. sade rapor")
sina("rapor yonergesi BASLIK istemez, ilk cumle sonuc",
     _istekler and "BASLIK yazma" in _istekler[-1] and "ILK CUMLE SONUC" in _istekler[-1]
     and "bu ucu gecir" not in _istekler[-1])

print("\n5. panel")
JS = (KOK / "web" / "panel.js").read_text(encoding="utf-8")
sina("istegin adimlari katli blokta (adimBlogu)", "function adimBlogu(" in JS
     and "cocuk[x.istek] = cocuk[x.istek] || []" in JS)
sina("senden bekleyen (onay, sana soru) DISARIDA kalir",
     'x.tur === "onay"' in JS and '(x.bekliyor && x.kime === "insan")' in JS)
sina("once liderin akan cumlesi, ALTINDA adimlar",
     JS.index('if (x.tur === "sohbet" && x.bekliyor && x.akis) {') < JS.index("kap.append(adimBlogu("))
sina("canli sure yazilir", "setInterval(sureleriYaz, 1000)" in JS)
sina("istek surerken sohbet tazelenir, kaydirma korunur",
     'querySelector(".sohbet-adimlar.suruyor")' in JS and 'kap.dataset.altta !== "0"' in JS)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
