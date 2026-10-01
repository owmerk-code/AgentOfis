"""MASAUSTU BILDIRIMI duman testi -- `ofis/bildirim.py`.

Ekrana GERCEK bildirim atmaz: gonderici bir listeye toplar. Sinanan:
  1. XML kacirma (ajan metni `<`, `&`, tirnak tasiyabilir), uzun metin kisalir
  2. PowerShell komutu UTF-16 base64 -- Turkce harf kodlamadan bagimsiz,
     tek tirnak kacirilir
  3. izleyici: ACILISTAN ONCEKI olaylari bildirmez; onay, soru, cevap,
     donus raporu, kesinti, siradaki is dususu bildirilir; siradan ajan
     hatasi bildirilmez; ayni olay iki kez gelmez
  4. kapali: kutuphane varsayilani kapali; patron ayari kapatir
  5. yagmur: cok olay tek turda en fazla AZAMI_SATIR + ozet
  6. gonderici duserse izleyici durmaz, bir kez SOYLER
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import base64
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis import bildirim as B
from ofis.db import simdi

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


print("== bildirim duman testi ==\n")

print("1. XML")
x = B.toast_xml("Onay <x>", "a & b </text><text>enjeksiyon", "http://h/?a=1&b=2")
sina("metin kacirildi (enjeksiyon etiketi kirilmadi)",
     "&lt;/text&gt;" in x and x.count("<text>") == 2, x)
sina("adres kacirildi", 'launch="http://h/?a=1&amp;b=2"' in x)
sina("uzun metin kisaldi", len(B.toast_xml("b", "x" * 2000)) < 600)

print("\n2. PowerShell komutu")
k = B.powershell_komutu(B.toast_xml("çınar", "ğüşıöç İĞÜŞ 'tırnak'"))
cozulen = base64.b64decode(k[-1]).decode("utf-16-le")
sina("-EncodedCommand UTF-16 base64, Turkce harf korunuyor", "-EncodedCommand" in k
     and "ğüşıöç İĞÜŞ" in cozulen and "çınar" in cozulen)
sina("tek tirnak PowerShell icin ikilendi", "''tırnak''" in cozulen)

print("\n3. izleyici")
kok = Path(tempfile.mkdtemp(prefix="ofis-bildirim-"))
db = Veritabani(kok / "ofis.sqlite3")
ofis = Ofis.proje_ac(db, "Bildirim", amac="haber", basari_olcutu="gelir",
                     kok_klasor=str(kok / "calisma"))
kn = ofis.kanat_ac("GENEL", "GN")
ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kn, motor="sahte",
                  klasor=str(kok / "calisma"))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(kok / "calisma"))
ofis.postane.onay_iste("cinar", "ESKI onay", ayrinti="x", risk="yuksek")   # acilistan ONCE
giden = []
B.GONDERICI = lambda b, m, a="": giden.append((b, m, a))
B.ACIK = True
iz = B.Izleyici(ofis, "http://127.0.0.1:8900/")
sina("acilistan once olan olay BILDIRILMEDI", iz.tik() == 0 and giden == [])
ofis.postane.onay_iste("cinar", "GONDERIM: form yolla", ayrinti="x", risk="yuksek")
ofis.postane.soru_sor("cinar", "insan", "Hangi renk olsun?")
m = ofis.postane.soru_sor("insan", "demir", "rapor hazirla")
with db.baglanti() as c:
    c.execute("UPDATE mesaj SET cevap = ?, cevaplandi = ? WHERE id = ?",
              ("Rapor hazir.\n[ek] ekler/r.md", simdi(), m["id"]))
ofis.db.olay_yaz(ofis.proje_id, "donus_raporu", "**Dönüş raporu**", ajan_ad="ofis")
ofis.db.olay_yaz(ofis.proje_id, "hata", "Tur basarisiz (cikis 1)", ajan_ad="cinar")
n = iz.tik()
basliklar = [g[0] for g in giden]
sina("onay bildirildi", "Onay bekliyor" in basliklar, str(basliklar))
sina("ajanin patrona sorusu bildirildi", "cinar sana soruyor" in basliklar, str(basliklar))
sina("liderin cevabi bildirildi, ek satiri YOK",
     any(b == "demir cevapladı" and "[ek]" not in mm for b, mm, _ in giden), str(giden))
sina("yagmur: 4 olay -> en fazla AZAMI_SATIR + ozet",
     n == B.AZAMI_SATIR + 1 and giden[-1][0] == "Ofiste başka gelişmeler", f"{n} {basliklar}")
sina("siradan ajan hatasi BILDIRILMEDI", not any("düştü" in b for b in basliklar))
sina("bildirime tiklayinca panel acilir (adres)", all(g[2] == "http://127.0.0.1:8900/" for g in giden))
giden.clear()
sina("ayni olaylar ikinci turda TEKRAR gelmez", iz.tik() == 0 and giden == [])
ofis.db.olay_yaz(ofis.proje_id, "hata", "Siradaki is dustu (x): y", ajan_ad="")
ofis.db.olay_yaz(ofis.proje_id, "kesinti_toparlandi", "yarım kalan iş: #4", ajan_ad="ofis")
iz.tik()
sina("siradaki is dususu ve kesinti bildirildi",
     [g[0] for g in giden] == ["Ofis kaldığı yerden sürüyor", "Bir iş düştü"]
     or [g[0] for g in giden] == ["Bir iş düştü", "Ofis kaldığı yerden sürüyor"], str(giden))

print("\n4. kapali")
giden.clear()
ofis.db.ayar_yaz(ofis.proje_id, B.AYAR, "kapali")
ofis.postane.onay_iste("cinar", "GONDERIM: baska", ayrinti="x", risk="yuksek")
sina("patron kapattiysa bildirim YOK", iz.tik() == 0 and giden == [])
ofis.db.ayar_yaz(ofis.proje_id, B.AYAR, "acik")
B.ACIK = False
ofis.postane.onay_iste("cinar", "GONDERIM: ucuncu", ayrinti="x", risk="yuksek")
sina("kutuphane varsayilani (panel acmadi) bildirim YOK", iz.tik() == 0 and giden == [])
B.ACIK = True

print("\n6. gonderici duserse")


def _patla(*a, **k):
    raise OSError("powershell yok")


B.GONDERICI = _patla
ofis.postane.onay_iste("cinar", "GONDERIM: dorduncu", ayrinti="x", risk="yuksek")
iz.tik()
ofis.postane.onay_iste("cinar", "GONDERIM: besinci", ayrinti="x", risk="yuksek")
iz.tik()
with db.baglanti() as c:
    _u = c.execute("SELECT COUNT(*) FROM olay WHERE tur='uyari' AND govde LIKE '%bildirimi gonderilemedi%'"
                   ).fetchone()[0]
sina("dusus bir kez deftere yazildi, izleyici durmadi", _u == 1, str(_u))
B.ACIK = False

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
print(f"klasor: {kok}")
sys.exit(1 if KALAN else 0)
