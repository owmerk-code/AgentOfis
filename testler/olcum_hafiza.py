# -*- coding: utf-8 -*-
"""Hafiza isabeti olcumu: brifingde ajanin IHTIYACI olan bilgi var mi?

Neden bu olcum:

Rakip (Muratify) kendi sayisini yayinladi: gorev-hedefli hafiza secimiyle
ajan hafiza isabeti ~%6'dan ~%25'e cikmis. Yani iyilestirmeden SONRA bile
dortte uc iskalaniyor. Bizim dort katmanli brifingimiz bu soruna cevap
olarak tasarlandi -- ama BIZ HIC OLCMEDIK. Olcmeden "daha iyiyiz" demek,
onun hatasini tekrarlamaktir.

Olcumun durustlugu icin: **once olculur, sonra duzeltilir, sonra tekrar
olculur.** Duzeltip sonra olcmek, kendini kandirmanin en kolay yoludur.

Yontem -- sentetik yer gercegi:

Hangi olgunun gercekten gerektigini BIZ kuruyoruz. Bir gorev aciyoruz ve
o gorevin metninde yalnizca belirli konulara deginiyoruz; o konulardaki
olgular "gerekli", digerleri "gereksiz" sayilir. Sonra brifing uretilip
icinde ne oldugu sayilir.

Iki sayi birlikte anlamlidir:

* **ISABET (recall)** = brifingde bulunan gerekli olgu / toplam gerekli
  olgu. Dusukse ajan bilmedigi bir seyle calisir -- MAST'in %41,8'lik
  belirtim hatasi kumesi buradan beslenir.

* **GURULTU (1 - precision)** = brifingdeki gereksiz olgu orani. Yuksekse
  ajanin dikkati dagilir ve jeton yanar ("context rot").

Ucuncu sayi: **jeton**. Isabet %100 olsa bile brifing sisiyorsa
kullanilamaz; 6000 jeton esigi `brifing.JETON_UYARI_ESIGI`de duruyor.

Kural: **eksik bilgi, gurultuden PAHALIDIR.** Gereksiz olgu jeton yakar;
eksik olgu yanlis is urettirir. Bu yuzden secim, sisme olmadikca
kesmemelidir.

Kullanim:  python testler/olcum_hafiza.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani
from ofis.brifing import JETON_UYARI_ESIGI

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


#: Gorevin ihtiyac duydugu konular. Gorev metni YALNIZCA bunlara deginir;
#: yer gercegi budur.
GEREKLI = [
    ("iade suresi", "30 gun icinde kosulsuz iade"),
    ("kargo bedeli", "500 TL uzeri ucretsiz kargo"),
    ("odeme saglayicisi", "Iyzico kullaniliyor"),
    ("stok kaynagi", "stok bilgisi depo sisteminden gelir"),
    ("fiyat kurali", "fiyatlar KDV dahil gosterilir"),
]

#: Gorevle ilgisi OLMAYAN konular. Gurultuyu olcmek icin.
GURULTU_KONULARI = [
    "ofis muzigi", "kahve markasi", "toplanti saati", "park yeri",
    "yemek karti", "tatil takvimi", "kirtasiye siparisi", "temizlik gunu",
    "sunucu odasi sicakligi", "yedekleme saati", "alan adi saglayicisi",
    "logo yazi tipi", "kartvizit baskisi", "arac kiralama", "sigorta yenileme",
    "vergi dairesi", "muhasebe programi", "personel dolabi", "klima ayari",
    "asansor bakimi",
]

GOREV_METNI = (
    "Siparis ozeti ekraninda iade suresi, kargo bedeli ve fiyat kurali "
    "dogru gosterilsin; odeme saglayicisi ve stok kaynagi bilgisiyle "
    "tutarli olsun."
)


def ofis_kur(gurultu_adedi: int) -> tuple:
    kok = Path(tempfile.mkdtemp(prefix="olcum-hafiza-"))
    db = Veritabani(kok / "o.sqlite3")
    ofis = Ofis.proje_ac(db, "Olcum", amac="Hafiza isabetini olcmek",
                         basari_olcutu="Sayilar cikar", kok_klasor=str(kok))
    kanat = ofis.kanat_ac("ANA", "AN")
    ofis.kadro.ise_al("cinar", "yazilim", kanat_id=kanat, motor="sahte",
                      klasor=str(kok))

    # Gurultu olgulari ONCE yazilir: gercek hayatta da eski birikim once
    # olusur, yeni is sonra gelir.
    for i in range(gurultu_adedi):
        konu = GURULTU_KONULARI[i % len(GURULTU_KONULARI)]
        # Icerikler BIRBIRININ ALT DIZESI OLMAMALI: "deger 1" ifadesi
        # "deger 10" ve "deger 100" icinde de gecer ve sayac siser.
        # Olcum aracinin kendisi de olculmeli -- bu hata ucuncu kez cikti.
        ofis.bellek.olgu_yaz(f"{konu} {i // len(GURULTU_KONULARI) + 1}",
                             f"arsiv-kaydi-{i:05d}-son", kaynak="arsiv")
    for konu, icerik in GEREKLI:
        ofis.bellek.olgu_yaz(konu, icerik, kaynak="insan")

    g = ofis.tahta.gorev_ac(
        "Siparis ozeti ekrani",
        neden="Musteri iade ve kargo kosullarini goremiyor",
        ana_hedef="Siparis akisi dogru bilgi gostersin",
        kabul_olcutu="Ekranda iade suresi, kargo bedeli ve fiyat kurali dogru",
        govde=GOREV_METNI,
        yazma_alani=["ekran/"], kanat_id=kanat)
    return ofis, g


def olc(gurultu_adedi: int) -> dict:
    ofis, g = ofis_kur(gurultu_adedi)
    b = ofis.brifing.uret(g["no"], "cinar", diske_yaz=False)
    metin = b["metin"]

    bulunan_gerekli = sum(1 for _, icerik in GEREKLI if icerik in metin)
    tum_olgular = ofis.bellek.gecerli_olgular()
    brifingdeki = sum(1 for o in tum_olgular if o["icerik"] in metin)
    gereksiz = brifingdeki - bulunan_gerekli

    return {
        "olgu": len(tum_olgular),
        "isabet": bulunan_gerekli / len(GEREKLI),
        "brifingdeki": brifingdeki,
        "gurultu": (gereksiz / brifingdeki) if brifingdeki else 0.0,
        "jeton": b["jeton_tahmini"],
        "sisti": b["sisme_uyarisi"],
    }


#: 19.09'da olculen DURUST KAYIP: gerekli ama gorevle HIC ortak kelimesi
#: olmayan olgu. Kelime secimi bunu bulamaz; `[[bag]]` bulur mu?
KOPUK = ("lojistik anlasmasi", "Yillik sozlesme: teslimat iki is gunu")


def olc_bag(gurultu_adedi: int, bagli: bool) -> dict:
    """Altinci gerekli olgu gorevle kelime paylasmiyor. `bagli` ise
    "kargo bedeli" olgusu ona `[[...]]` ile isaret eder."""
    ofis, g = ofis_kur(gurultu_adedi)
    ofis.bellek.olgu_yaz(KOPUK[0], KOPUK[1], kaynak="insan")
    if bagli:
        ofis.bellek.olgu_yaz(
            "kargo bedeli",
            "500 TL uzeri ucretsiz kargo; teslim suresi [[lojistik anlasmasi]]",
            kaynak="insan")
    metin = ofis.brifing.uret(g["no"], "cinar", diske_yaz=False)["metin"]
    gerekli = [i for _, i in GEREKLI] + [KOPUK[1]]
    return {"isabet": sum(1 for i in gerekli if i in metin) / len(gerekli),
            "kopuk_var": KOPUK[1] in metin}


def main() -> None:
    print("== HAFIZA ISABETI OLCUMU ==")
    print()
    print("Yer gercegi: gorevin ihtiyac duydugu 5 olgu var; gerisi gurultu.")
    print("Rakibin yayinladigi sayi: gorev-hedefli secimle ~%25 isabet.")
    print()
    print(f"{'olgu':>6} {'isabet':>8} {'brifingde':>10} {'gurultu':>9} "
          f"{'jeton':>8}  durum")
    print("-" * 58)

    sonuclar = []
    for gurultu in (0, 20, 95, 295):
        s = olc(gurultu)
        sonuclar.append(s)
        durum = "SISTI" if s["sisti"] else "tamam"
        print(f"{s['olgu']:>6} {s['isabet']*100:>7.0f}% {s['brifingdeki']:>10} "
              f"{s['gurultu']*100:>8.0f}% {s['jeton']:>8}  {durum}")

    print()
    print("YORUM")
    isabetler = {round(s["isabet"], 3) for s in sonuclar}
    if isabetler == {1.0}:
        print("  Isabet her olcekte %100: K2 katmani GECERLI olgularin")
        print("  HEPSINI koyuyor, secim yapmiyor. Eksik bilgi yok.")
    else:
        print(f"  Isabet degisiyor: {sorted(isabetler)}")
    en_buyuk = sonuclar[-1]
    print(f"  Ama {en_buyuk['olgu']} olguda gurultu %{en_buyuk['gurultu']*100:.0f} "
          f"ve brifing {en_buyuk['jeton']} jeton "
          f"({'esigi asti' if en_buyuk['sisti'] else 'esik altinda'}; "
          f"esik {JETON_UYARI_ESIGI}).")
    print()
    print("  Yani bugunku zayiflik ISABET degil GURULTU ve SISME.")
    print("  Kucuk ofiste kusursuz, buyuyen ofiste kullanilamaz hale gelir.")
    print("  Dogru duzeltme: sisme esigine kadar HICBIR SEY KESME (eksik")
    print("  bilgi gurultuden pahalidir), esik asilinca goreve gore sec.")

    print()
    print("== BAG OLCUMU (24.09.2026) -- durust kayip kapaniyor mu ==")
    print("6. gerekli olgu gorevle HIC ortak kelime tasimiyor.")
    print(f"{'olgu':>6} {'bagsiz':>8} {'bagli':>8}")
    for gurultu in (20, 95, 295):
        a = olc_bag(gurultu, bagli=False)
        b = olc_bag(gurultu, bagli=True)
        print(f"{gurultu + len(GEREKLI) + 1:>6} {a['isabet']*100:>7.0f}% "
              f"{b['isabet']*100:>7.0f}%")
    print("  Esigin altinda (40) secim yok, kayip da yok. Ustunde kelime")
    print("  secimi kopuk olguyu eliyor; `[[bag]]` onu bir adimda geri getiriyor.")


if __name__ == "__main__":
    main()
