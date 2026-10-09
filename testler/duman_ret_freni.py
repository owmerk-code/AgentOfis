# -*- coding: utf-8 -*-
"""RET FRENI (09.10.2026, F1 canli: kargo raporu ALTI kez geri dondu, patron:
"2 saatte bir is yapamadik"). 3. retten sonra is ajana DONMEZ: duraklar,
patrona secenekli soru gider; cevap (kabul / bir tur daha / iptal) uygulanir."""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani  # noqa: E402
from ofis import lider as L  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


D = Path(tempfile.mkdtemp(prefix="ofis-retfreni-"))
db = Veritabani(D / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Fren", amac="a", basari_olcutu="b", kok_klasor=str(D))
ofis.kadro.ise_al("lale", "lider", lider_mi=True, motor="sahte", klasor=str(D))
ofis.kadro.ise_al("ece", "arastirma", motor="sahte", klasor=str(D))


def is_ac(baslik):
    g = ofis.tahta.gorev_ac(baslik, neden="n", ana_hedef="h", kabul_olcutu="her iddia kaynakli")
    g = ofis.tahta.sahiplen(g["no"], "ece", g["revizyon"])
    ofis.tahta.kanit_ekle(g["no"], "dosya", "rapor", "rapor.md", "ece")
    return g["no"]


def teslim_ret(no, kac):
    sonuc = None
    for i in range(kac):
        g = ofis.tahta.gorev(no)
        if g.get("duraklatildi"):
            break
        ofis.tahta.incelemeye_ver(no, g["revizyon"])
        sonuc = ofis.lider._hukmu_uygula(no, f"KARAR: geri -- satir {10 + i} kaynaksiz\n"
                                             'OLCUT: "her iddia kaynakli"', "lale", "ece")
    return sonuc


def fren_sorusu(no):
    gid = ofis.tahta.gorev(no)["id"]
    return [m for m in ofis.postane.insan_bekleyenler()
            if m.get("gorev_id") == gid and (m.get("kaynak") or "") == L.RET_FRENI_KAYNAK]


print("1. ilk iki ret normal")
n1 = is_ac("kargo raporu")
s = teslim_ret(n1, 2)
g = ofis.tahta.gorev(n1)
sina("2 retten sonra is ajanda calisiyor, duraklamadi, soru yok",
     g["durum"] == "calisiyor" and not g.get("duraklatildi") and not fren_sorusu(n1) and not s.get("fren"))

print("\n2. 3. ret: FREN")
s = teslim_ret(n1, 1)
g = ofis.tahta.gorev(n1)
sq = fren_sorusu(n1)
sina("3. retten sonra is DURAKLADI (ajan yeni tura baslamaz)", bool(g.get("duraklatildi")) and s.get("fren"), str(g.get("duraklatildi")))
sina("patrona SECENEKLI soru: kabul / bir tur daha / iptal + son gerekce",
     len(sq) == 1 and (sq[0].get("secim") or {}).get("secenekler") == [L.FREN_KABUL, L.FREN_TUR, L.FREN_IPTAL]
     and "satir 10" in sq[0]["govde"] and "3 kez" in sq[0]["govde"], str(sq)[:300])

print("\n3. cevaplar uygulanir")
r = ofis.postane.cevapla(sq[0]["id"], L.FREN_KABUL)
g = ofis.tahta.gorev(n1)
sina("'Oldugu gibi kabul et' -> is KAPANDI (kapatan insan)", g["durum"] == "bitti" and r.get("eylem", {}).get("eylem") == "kabul", str((g["durum"], r)))
n2 = is_ac("ikinci rapor")
teslim_ret(n2, 3)
ofis.postane.cevapla(fren_sorusu(n2)[0]["id"], L.FREN_TUR)
g = ofis.tahta.gorev(n2)
sina("'Bir tur daha dene' -> duraklama kalkti, is ajanda surer", g["durum"] == "calisiyor" and not g.get("duraklatildi"), str(g))
s = teslim_ret(n2, 1)
sina("  bir tur sonra yine ret -> fren yeniden sorar (dongu yine durur)",
     s.get("fren") and len(fren_sorusu(n2)) == 1 and ofis.tahta.gorev(n2).get("duraklatildi"))
n3 = is_ac("ucuncu rapor")
teslim_ret(n3, 3)
ofis.postane.cevapla(fren_sorusu(n3)[0]["id"], L.FREN_IPTAL)
sina("'Iptal et' -> is IPTAL", ofis.tahta.gorev(n3)["durum"] == "iptal")
n5 = is_ac("kesintiye ugrayan")
teslim_ret(n5, 3)
with db.baglanti() as _c:          # kesinti: is 'hazir'a dustu, sahipsiz (09.10 canli)
    _c.execute("UPDATE gorev SET durum = 'hazir', sahip = '' WHERE no = ?", (n5,))
r = ofis.postane.cevapla(fren_sorusu(n5)[0]["id"], L.FREN_KABUL)
sina("kesintiden sonra 'hazir' is de kabul ile KAPANDI", ofis.tahta.gorev(n5)["durum"] == "bitti", str(r))
n6 = is_ac("kanitsiz")
teslim_ret(n6, 3)
with db.baglanti() as _c:
    _c.execute("DELETE FROM kanit WHERE gorev_id = (SELECT id FROM gorev WHERE no = ?)", (n6,))
r = ofis.postane.cevapla(fren_sorusu(n6)[0]["id"], L.FREN_KABUL)
with db.baglanti() as _c:
    _yalan = _c.execute("SELECT 1 FROM olay WHERE tur='karar' AND govde LIKE ?", (f"%#{n6} ret freni%KABUL%",)).fetchone()
sina("kapanamayan is (kanitsiz) icin 'KABUL edildi' kaydi YAZILMAZ, sebep soylenir",
     ofis.tahta.gorev(n6)["durum"] != "bitti" and not _yalan and r.get("eylem", {}).get("eylem") == "hata", str(r))
n4 = is_ac("dorduncu")
teslim_ret(n4, 3)
r = ofis.postane.cevapla(fren_sorusu(n4)[0]["id"], "baska bir sey yaz")
sina("secenek disi serbest cevap is DURUMUNU DEGISTIRMEZ (duraklatilmis kalir)",
     ofis.tahta.gorev(n4).get("duraklatildi") and "eylem" not in r)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
