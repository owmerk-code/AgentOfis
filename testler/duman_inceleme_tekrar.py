# -*- coding: utf-8 -*-
"""SONUCSUZ INCELEME (09.10.2026, F1 canli #5): codex brifingi gonderemedi,
inceleme "sonucsuz" kaldi ve is incelemede ASILI durdu. Artik (1) ayni turda
BIR kez yeniden denenir, (2) panel acilisinda incelemede bekleyen is varsa
halka surdurulur."""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani  # noqa: E402
from ofis import kuyruk as K  # noqa: E402
from ofis.toparla import acilista_toparla  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


D = Path(tempfile.mkdtemp(prefix="ofis-inceleme-tekrar-"))
ofis = Ofis.proje_ac(Veritabani(D / "o.sqlite3"), "Inc", amac="a", basari_olcutu="b", kok_klasor=str(D))
kn = ofis.kanat_ac("ANA", "AN")
ofis.kadro.ise_al("ada", "lider", lider_mi=True, kanat_id=kn, motor="sahte", klasor=str(D))
ofis.kadro.ise_al("asli", "backend", kanat_id=kn, motor="sahte", klasor=str(D))


def incelemeye(baslik):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=kn,
                            yazma_alani=[baslik.replace(" ", "_") + ".txt"])
    g = ofis.tahta.sahiplen(g["no"], "asli", g["revizyon"])
    ofis.tahta.kanit_ekle(g["no"], "dosya", "yapildi", "x.txt", "asli")
    return ofis.tahta.incelemeye_ver(g["no"], ofis.tahta.gorev(g["no"])["revizyon"])


ork = ofis.orkestra
CAGRI = []


def sahte_incele(cevaplar):
    def incele(no, **_):
        CAGRI.append(no)
        h = cevaplar.pop(0) if cevaplar else "belirsiz"
        if h == "kapat":
            g = ofis.tahta.gorev(no)
            ofis.tahta.kapat(no, g["revizyon"], kapatan="ada")
        return {"hukum": h, "gerekce": "sahte", "gorev_no": no, "ders": False}
    return incele


print("1. ilk inceleme sonucsuz -> ayni turda BIR kez daha, ikincisi kapatir")
g1 = incelemeye("is bir")
ork.lider.incele = sahte_incele(["belirsiz", "kapat"])
ork.tik()
sina("inceleme iki kez kostu ve is KAPANDI", CAGRI.count(g1["no"]) == 2
     and ofis.tahta.gorev(g1["no"])["durum"] == "bitti", str((CAGRI, ofis.tahta.gorev(g1["no"])["durum"])))

print("\n2. ikisi de sonucsuz -> durur (kota bosuna yanmaz), is incelemede kalir")
CAGRI.clear()
g2 = incelemeye("is iki")
ork.lider.incele = sahte_incele(["belirsiz", "belirsiz", "belirsiz"])
ork.tik()
sina("en fazla IKI deneme, is incelemede", CAGRI.count(g2["no"]) == 2
     and ofis.tahta.gorev(g2["no"])["durum"] == "inceleme", str(CAGRI))
with ofis.db.baglanti() as c:
    _u = c.execute("SELECT COUNT(*) FROM olay WHERE tur='uyari' AND govde LIKE ?",
                   (f"#{g2['no']} inceleme sonucsuz kaldi; BIR kez%",)).fetchone()[0]
sina("  yeniden deneme deftere yazildi", _u == 1, str(_u))

print("\n3. panel acilisinda incelemede bekleyen is -> halka surdurulur")
with ofis.db.baglanti() as c:
    c.execute("UPDATE kuyruk SET durum = 'bitti' WHERE durum = 'bekliyor'")
s = acilista_toparla(ofis)
sina("devam kaydi siraya girdi", s["devam"] == 1 and any(x.get("devam") for x in K.bekleyenler(ofis)), str(s))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
