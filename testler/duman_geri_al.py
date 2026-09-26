# -*- coding: utf-8 -*-
"""GERI AL: bir ajan turunun diskte yaptigi -- YALNIZ o -- geri aliniyor mu.

Sinanan:

1. Koltuk her turun oncesini/sonrasini golge depoya isliyor mu (modulun
   var olmasi bir baglanti degildir -- `video.py` dersi)?
2. Geri alma degisen, eklenen, silinen, IKILI dosyayi dogru donduruyor mu,
   ve tura DAHIL OLMAYAN dosyaya dokunmuyor mu?
3. Turdan SONRA yeniden degisen dosya varsa REDDEDIYOR mu (sonraki isi
   ezmemek)? Kosan is varken? Sebepsiz?
4. Geri alma da geri alinabiliyor mu?
5. Golge depo proje kokunun DISINDA mi?

Gercek golge klasorune DOKUNMAZ (`OFIS_GOLGE_KOK` gecici).
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import os
import shutil
import sys
import tempfile
from pathlib import Path

ANA = Path(tempfile.mkdtemp(prefix="ofis-geri-al-sinama-"))
os.environ["OFIS_GOLGE_KOK"] = str(ANA / "golge")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk        # noqa: E402
from ofis import geri_al as G                    # noqa: E402
from ofis.motor.sahte import SahteMotor          # noqa: E402

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


def reddedildi(islev, *a, **kw):
    # HER istisna ret sayilir; ama retten sonra diskin DEGISMEDIGI ayrica
    # sinanir -- ikinci bir kapinin (orn. karar_yaz) gec reddi, dosyalar
    # zaten degistirildikten sonra gelebilir.
    try:
        islev(*a, **kw)
        return ""
    except Exception as exc:        # noqa: BLE001
        return str(exc) or "reddedildi"


def dene(islev, *a, **kw):
    """Cokme degil KALDI: cokerse geri kalan sinamalar hic kosmaz."""
    try:
        return islev(*a, **kw)
    except Exception as exc:        # noqa: BLE001
        sina(f"beklenmeyen istisna yok ({islev.__name__})", False, str(exc))
        return {}


RESIM_ESKI = bytes(range(256)) * 4
RESIM_YENI = b"\x00BOZUK" * 100

try:
    kok = ANA / "calisma"
    kok.mkdir()
    (kok / "a.txt").write_text("eski\n", encoding="utf-8")
    (kok / "resim.png").write_bytes(RESIM_ESKI)
    (kok / "sil.md").write_text("silinecek\n", encoding="utf-8")
    (kok / "dokunma.txt").write_text("insanin dosyasi\n", encoding="utf-8")

    db = Veritabani(ANA / "o.sqlite3")
    ofis = Ofis.proje_ac(db, "Geri", amac="a", basari_olcutu="b",
                         kok_klasor=str(kok))
    kanat = ofis.kanat_ac("URUN", "UR")
    ofis.kadro.ise_al("demir", "lider", lider_mi=True, kanat_id=kanat,
                      klasor=str(kok), motor="sahte")
    ofis.kadro.ise_al("cinar", "backend", klasor=str(kok), motor="sahte")

    class Bozan(SahteMotor):
        def tur_kos(self, metin, **ayar):
            (kok / "a.txt").write_text("AJAN DEGISTIRDI\n", encoding="utf-8")
            (kok / "resim.png").write_bytes(RESIM_YENI)
            (kok / "sil.md").unlink(missing_ok=True)
            (kok / "yeni").mkdir(exist_ok=True)
            (kok / "yeni" / "b.py").write_text("x = 1\n", encoding="utf-8")
            return super().tur_kos(metin, **ayar)

    koltuk = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: Bozan(
        cevap="Bitti.\nKANIT dosya: a.txt -> yazildi"))
    g = ofis.tahta.gorev_ac("Boz", neden="n", ana_hedef="h", kabul_olcutu="k",
                            yazma_alani=["a.txt", "resim.png", "sil.md", "yeni"],
                            kanat_id=kanat)
    olaylar = list(koltuk.akit(g["no"], "cinar"))

    # ------------------------------------------------ 1. BAGLANTI
    print("\n1. KOLTUK turu golgeye isliyor")
    kayitlar = G.liste(db, ofis.proje_id)
    sina("tur kaydi yazildi", len(kayitlar) == 1, str(kayitlar))
    k = kayitlar[0] if kayitlar else {"id": "yok"}
    sina("4 dosya sayildi", k.get("dosya") == 4, str(k.get("dosya")))
    sina("geri alma uyarisi YOK (kayit alindi)",
         not any("Geri alma kaydi" in o["govde"] for o in olaylar
                 if o["tur"] == "uyari"))
    sina("golge proje kokunun DISINDA",
         not (kok / ".git").exists()
         and ANA / "golge" in G.Golge(kok).git_dir.parents)

    # ------------------------------------------------ 2. KAPILAR
    print("\n2. KAPILAR -- sebepsiz / sonradan degisen / kosan is")
    sina("sebepsiz REDDEDILDI",
         bool(reddedildi(G.geri_al, ofis, k["id"], sebep="  ")))
    sina("sebepsiz denemede disk DEGISMEDI",
         (kok / "a.txt").read_text(encoding="utf-8") == "AJAN DEGISTIRDI\n")
    (kok / "a.txt").write_text("INSAN SONRADAN YAZDI\n", encoding="utf-8")
    r = reddedildi(G.geri_al, ofis, k["id"], sebep="deneme")
    sina("sonradan degisen dosya varsa REDDEDILDI", "a.txt" in r, r)
    sina("red dosyayi ezmedi", (kok / "a.txt").read_text(
        encoding="utf-8") == "INSAN SONRADAN YAZDI\n")
    (kok / "a.txt").write_text("AJAN DEGISTIRDI\n", encoding="utf-8")

    g2 = ofis.tahta.gorev_ac("Kosan", neden="n", ana_hedef="h",
                             kabul_olcutu="k", yazma_alani=["baska"],
                             kanat_id=kanat)
    ofis.tahta.sahiplen(g2["no"], "demir", g2["revizyon"])
    r = reddedildi(G.geri_al, ofis, k["id"], sebep="deneme")
    sina("kosan is varken REDDEDILDI", "calisiyor" in r, r)
    ofis.tahta.iptal_et(g2["no"], sebep="sinama", iptal_eden="demir")

    # ------------------------------------------------ 3. GERI ALMA
    print("\n3. GERI ALMA -- yalniz o turun dosyalari")
    (kok / "dokunma.txt").write_text("insan tur SONRASI degistirdi\n",
                                     encoding="utf-8")
    s = dene(G.geri_al, ofis, k["id"], sebep="ajan a.txt'yi bozdu")
    sina("metin eski haline dondu",
         (kok / "a.txt").read_text(encoding="utf-8") == "eski\n")
    sina("IKILI dosya bayt bayt dondu",
         (kok / "resim.png").read_bytes() == RESIM_ESKI)
    sina("silinen dosya geri geldi",
         (kok / "sil.md").exists()
         and (kok / "sil.md").read_text(encoding="utf-8") == "silinecek\n")
    sina("eklenen dosya kaldirildi", not (kok / "yeni" / "b.py").exists())
    sina("tura DAHIL OLMAYAN dosyaya dokunulmadi",
         (kok / "dokunma.txt").read_text(encoding="utf-8")
         == "insan tur SONRASI degistirdi\n")
    sina("gecici .part kalmadi", not list(kok.rglob("*.part")))
    sina("4 dosya bildirildi", len(s.get("dosyalar", [])) == 4)
    with db.baglanti() as c:
        karar = c.execute("SELECT gerekce FROM karar WHERE karar LIKE "
                          "'%geri alindi%'").fetchone()
        olay = c.execute("SELECT count(*) FROM olay WHERE tur='geri_alindi'"
                         ).fetchone()[0]
    sina("karar gunlugune SEBEBIYLE yazildi",
         karar and karar[0] == "ajan a.txt'yi bozdu")
    sina("olay yazildi", olay == 1)
    sina("ayni tur iki kez geri alinamaz",
         "zaten" in reddedildi(G.geri_al, ofis, k["id"], sebep="x"))

    # ------------------------------------------------ 4. GERI ALMAYI GERI AL
    print("\n4. GERI ALMA DA GERI ALINABILIR")
    yeni = dene(G.bul, db, ofis.proje_id, s.get("yeni_kayit", "yok"))
    sina("geri alma yeni bir kayit oldu",
         yeni.get("ajan_ad") == "insan (geri alma)")
    dene(G.geri_al, ofis, yeni.get("id", "yok")[:10],
         sebep="yanlis tura basmistim")
    sina("ajanin hali geri geldi",
         (kok / "a.txt").read_text(encoding="utf-8") == "AJAN DEGISTIRDI\n"
         and (kok / "yeni" / "b.py").exists()
         and (kok / "resim.png").read_bytes() == RESIM_YENI
         and not (kok / "sil.md").exists())
    sina("insanin dosyasi yine ayni",
         (kok / "dokunma.txt").read_text(encoding="utf-8")
         == "insan tur SONRASI degistirdi\n")

    # ------------------------------------------------ 5. ZORLA
    print("\n5. ZORLA -- bilerek sonraki isi ezer, SOYLER")
    k3 = (G.liste(db, ofis.proje_id) or [{"id": "yok"}])[0]
    (kok / "a.txt").write_text("yine sonradan\n", encoding="utf-8")
    z = dene(G.geri_al, ofis, k3["id"], sebep="bilerek", zorla=True)
    sina("zorla gecti ve ezileni soyledi", "a.txt" in z.get("sonradan_ezilen", []))
    sina("belirsiz kisa kimlik REDDEDILDI", "belirsiz" in reddedildi(
        G.bul, db, ofis.proje_id, "") or "Boyle" in reddedildi(
        G.bul, db, ofis.proje_id, ""))

    # ------------------------------------------------ 6. DEGISIKLIKSIZ TUR
    print("\n6. DOSYA DEGISTIRMEYEN tur kayit acmaz")
    once_sayi = len(G.liste(db, ofis.proje_id, limit=100))
    koltuk2 = Koltuk(ofis, motor_fabrikasi=lambda ad, **a: SahteMotor(
        cevap="Bitti.\nKANIT dosya: x -> y"))
    g3 = ofis.tahta.gorev_ac("Bos", neden="n", ana_hedef="h", kabul_olcutu="k",
                             yazma_alani=["bos"], kanat_id=kanat)
    list(koltuk2.akit(g3["no"], "cinar"))
    sina("kayit acilmadi", len(G.liste(db, ofis.proje_id, limit=100)) == once_sayi)

    # ------------------------------------------------ 7. SAHIPSIZ TEMIZLIK
    print("\n7. SAHIPSIZ golge depo temizleniyor, kimsesiz olana dokunulmuyor")
    olu = ANA / "golge" / "olu.git"
    olu.mkdir(parents=True)
    (olu / "ofis-kok.txt").write_text(str(ANA / "artik-yok"), encoding="utf-8")
    bilinmeyen = ANA / "golge" / "bilinmeyen.git"
    bilinmeyen.mkdir()
    silinen = G.sahipsizleri_temizle(ANA / "golge")
    sina("koku olmayan depo silindi", "olu.git" in silinen and not olu.exists())
    sina("sahibi bilinmeyene DOKUNULMADI", bilinmeyen.exists())
    sina("canli depo duruyor", G.Golge(kok).git_dir.exists())
finally:
    def _sil(islev, yol, _hata):
        os.chmod(yol, 0o700)
        islev(yol)
    shutil.rmtree(ANA, onexc=_sil)
    sina("gecici klasor silindi (artik yok)", not ANA.exists())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
