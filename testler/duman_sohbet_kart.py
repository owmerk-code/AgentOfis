# -*- coding: utf-8 -*-
"""SOHBET KARTLARI (09.10.2026, patron: "ne is verdim, ne isi yapti hepsi
birbirine girmis" -> A secildi). Her istek TEK kart, tek durum, tek sonuc;
ofisin ic notlari karta/sohbete girmez; son teslimin dosyasi."""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from ofis import Ofis, Veritabani, takim  # noqa: E402
from ofis import kuyruk as Q  # noqa: E402
from ofis import panel as _panel  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def triyaj(karar, gerekce, **ek):
    return "```json\n" + json.dumps({"karar": karar, "gerekce": gerekce, **ek}, ensure_ascii=False) + "\n```"


K = Path(tempfile.mkdtemp(prefix="ofis-kart-"))
db_yolu = K / "o.sqlite3"
ofis = Ofis.proje_ac(Veritabani(db_yolu), "Kart", amac="a", basari_olcutu="b", kok_klasor=str(K))
kn = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(K))
ofis.kadro.ise_al("cem", "backend", kanat_id=kn, motor="sahte", klasor=str(K))


class Motor(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = triyaj("dagit", "is", hedef="a.txt dosyasina merhaba yaz")
        elif '"kollar"' in metin:
            self.cevap = "```json\n" + json.dumps({"bol": False, "gerekce": "tek", "kollar": [
                {"baslik": "a.txt yaz", "sahip": "cem", "neden": "patron istedi",
                 "kabul_olcutu": "a.txt icinde merhaba", "govde": "a.txt'ye merhaba yaz",
                 "yazma_alani": ["a.txt"]}]}) + "\n```"
        elif "KARAR: kapat" in metin:
            self.cevap = ("Kanit yeterli.\nKARAR: kapat\n"
                          "PATRONA: a.txt yazildi, icinde 'merhaba' var.\nHAFIZA: yok")
        else:
            (Path(ayar.get("klasor") or K) / "a.txt").write_text("merhaba", encoding="utf-8")
            self.cevap = "Yazdim.\nKANIT dosya: a.txt -> merhaba yazildi"
        return super().tur_kos(metin, **ayar)


print("1. istek -> tek kart, tek sonuc")
list(Sohbet(ofis, motor_fabrikasi=lambda ad, **a: Motor(cevap="")).konus("a.txt'ye merhaba yaz", azami_tik=6))
g = ofis.tahta.liste()[0]
# Ajan iki kez teslim mesaji yazdi (iki surum): kartta yalniz SON.
(K / ".ofis" / "ekler").mkdir(parents=True, exist_ok=True)
for ek in ("eski-surum.png", "son-surum.png"):
    (K / ".ofis" / "ekler" / ek).write_bytes(bytes([137]) + b"PNG")
    ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", f"teslim\n[ek] .ofis/ekler/{ek}", ajan_ad="cem", gorev_id=g["id"])
# Ofisin ic notlari: karta da sohbete de GIRMEZ.
ofis.db.olay_yaz(ofis.proje_id, "donus_raporu", "**Donus raporu** -- 1 is", ajan_ad="ofis")
ofis.db.olay_yaz(ofis.proje_id, "kesinti_toparlandi", "Ofis kapanmadan önce yarım kalanlar bulundu", ajan_ad="ofis")
kk = takim.kartlar(ofis)
sina("tek kart (ofis notlari kart OLMADI)", len(kk) == 1 and kk[0]["tip"] == "istek", str([k["tip"] for k in kk]))
k = kk[0]
sina("durum bitti, isi yapan ve is", k["durum"] == "bitti" and k["isler"][0]["sahip"] == "cem", str(k["isler"]))
sina("sonuc: liderin PATRONA ozeti (ara not degil)", k["sonuc"].startswith("a.txt yazildi"), k["sonuc"][:80])
sina("dosyalar: yalniz SON teslim", k["sonuc_ekler"] == [".ofis/ekler/son-surum.png"], str(k["sonuc_ekler"]))
sina("ayrintida ofis notu yok", not any(x["tur"] == "ozet" for x in k["ayrinti"]))

print("\n2. sonuc yoksa ajanin teslim mesaji; kesinti cevabi SONUC SAYILMAZ")
g2 = ofis.tahta.gorev_ac("b raporu", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
m = ofis.postane.soru_sor("insan", "lale", "b raporunu yaz", mod="uyandiran")
with ofis.db.baglanti() as c:
    c.execute("UPDATE gorev SET istek_id = ? WHERE id = ?", (m["id"], g2["id"]))
g2 = ofis.tahta.sahiplen(g2["no"], "cem", g2["revizyon"])
ofis.tahta.kanit_ekle(g2["no"], "dosya", "rapor", "b.md", "cem")
(K / ".ofis" / "ekler" / "b.md").write_text("b", encoding="utf-8")
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "B raporu hazir, ekte.\n[ek] .ofis/ekler/b.md", ajan_ad="cem", gorev_id=g2["id"])
ofis.tahta.insan_kabul(g2["no"])
ofis.postane.cevapla(m["id"], "Ofis kapanmadan önce başlamıştı; kaldığı yerden sürdürüldü.", cevaplayan="lale")
k2 = next(x for x in takim.kartlar(ofis) if x["id"] == m["id"])
sina("liderin ozeti yoksa ajanin teslim mesaji sonuc", k2["sonuc"].startswith("B raporu hazir"), k2["sonuc"][:80])
sina("kesinti cumlesi sonuc DEGIL", "kapanmadan" not in k2["sonuc"])

print("\n3. calisiyor / karar / sirada / ajan sana soruyor")
g3 = ofis.tahta.gorev_ac("c isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn)
m3 = ofis.postane.soru_sor("insan", "lale", "c yap", mod="uyandiran")
with ofis.db.baglanti() as c:
    c.execute("UPDATE gorev SET istek_id = ? WHERE id = ?", (m3["id"], g3["id"]))
ofis.tahta.sahiplen(g3["no"], "cem", g3["revizyon"])
k3 = next(x for x in takim.kartlar(ofis) if x["id"] == m3["id"])
sina("calisan is: durum 'calisiyor', canli satirda kim", k3["durum"] == "calisiyor" and (k3["canli"] or {}).get("kim") == "cem", str(k3.get("canli")))
ofis.postane.onay_iste("cem", "git push", gorev_no=g3["no"])
k3 = next(x for x in takim.kartlar(ofis) if x["id"] == m3["id"])
sina("isin onayi bekliyor: durum 'karar'", k3["durum"] == "karar")
Q.ekle(ofis, "d isi", "lale")
sina("sirada bekleyen istek kart: 'sirada'", any(x["tip"] == "sirada" and x["durum"] == "sirada" for x in takim.kartlar(ofis)))
ofis.postane.soru_sor("cem", "insan", "hangi renk?")
sina("istege bagli olmayan soru: 'soru_sana' karti, durum karar",
     any(x["tip"] == "soru_sana" and x["durum"] == "karar" for x in takim.kartlar(ofis)))

print("\n4. panel ucu")
ist = TestClient(_panel.olustur(db_yolu))
r = ist.get("/api/kartlar").json()
sina("/api/kartlar kartlari doner", len(r["kartlar"]) >= 4 and all("durum" in x for x in r["kartlar"]), str(len(r["kartlar"])))
js = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
sina("panel sohbeti kartlarla ciziyor, onay/soru cizimi TEK (sag kutu ile ortak)",
     'al("/api/kartlar"' in js and "function onayKartiYap" in js and "kap.append(onayKartiYap(a))" in js
     and "kart.append(onayKartiYap(a))" in js)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
