# -*- coding: utf-8 -*-
"""Ornek ofis: paneli DOLU veriyle cizebilmek icin gercekci bir kurulum.

Neden var: bos ekranda arayuz tasarlanmaz. Bos bir panelde her sey ferah
gorunur; yogunluk sorunlari ancak bes sutun dolu, uc ajan calisiyor, bir
soru bekliyor ve onay kuyrugunda bir sey varken ortaya cikar. Ilk panel
taslaginin "cok basit, cok eksik" gorunmesinin sebeplerinden biri de
buydu.

Veri BILINCLI OLARAK GENELDIR. Ofis hicbir alana ozgu degildir --
cekirdekte tek bir sektor adi gecmez; yazilim, icerik, arastirma, reklam,
magaza yonetimi, hepsi ayni kadro/tahta/kanit makinesiyle kosar. Ornek
veri bir SAHNEDIR, sistemin konusu degil.

Sahte motorla kosar -- jeton yakmaz, tekrarlanabilir.

Kullanim:  python veri/ornek_ofis.py [--db yol]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, Koltuk, Lider
from ofis.motor.sahte import SahteMotor

VARSAYILAN = Path(__file__).resolve().parent / "ornek.sqlite3"


def kur(db_yolu: Path) -> None:
    if db_yolu.exists():
        db_yolu.unlink()
    for ek in (".sqlite3-wal", ".sqlite3-shm"):
        yan = db_yolu.with_suffix(ek)
        if yan.exists():
            yan.unlink()

    # Ornek ofisin koku de ofisin DISINDA (01.10.2026 ayrim kurali; proje
    # koku ofisin kendi yerinde olamaz). Gecici klasor: demo.
    import tempfile as _tf
    kok = Path(_tf.gettempdir()) / "agentofis-ornek-calisma"
    kok.mkdir(parents=True, exist_ok=True)

    db = Veritabani(db_yolu)
    ofis = Ofis.proje_ac(
        db, "Ornek Ofis",
        amac="Yeni surumu cikarmak: urun tarafi, icerik ve duyuru",
        basari_olcutu="Surum yayinda, geri bildirim toplaniyor",
        kapsam_disi="Altyapi degisikligi, yeni platform",
        kisitlar="Mevcut yigin, Turkce icerik",
        sozluk="Kanat=takim · Kabul olcutu=bittigini kanitlayan sey",
        kok_klasor=str(kok),
    )

    urun = ofis.kanat_ac("URUN", "UR", "#E0785A")
    pazarlama = ofis.kanat_ac("PAZARLAMA", "PZ", "#6BA3C7")

    # DEMO AJANLARI `sahte` MOTORDA. Panel artik isi GERCEKTEN surduruyor
    # (onay/cevap sonrasi halka, "Surdur" dugmesi); demo ajanlari `claude`
    # olsaydi, sahnede bir dugmeye basmak gercek jeton yakardi (olculdu,
    # 23.09.2026). Sahne, parasi olmayan bir yerde oynanir.
    kadro = [
        ("demir", "lider", urun, True, "eller", "sahte"),
        ("cinar", "backend", urun, False, "eller", "sahte"),
        ("yaprak", "arayuz", urun, False, "eller", "sahte"),
        ("bilge", "arastirma", urun, False, "kafa", "sahte"),
        ("ruzgar", "lider", pazarlama, True, "eller", "sahte"),
        ("deniz", "metin", pazarlama, False, "kafa", "sahte"),
        ("kaya", "reklam", pazarlama, False, "eller", "sahte"),
    ]
    for ad, meslek, kanat, lider_mi, tur, motor in kadro:
        ofis.kadro.ise_al(ad, meslek, kanat_id=kanat, lider_mi=lider_mi,
                          tur=tur, motor=motor, efor="normal",
                          klasor=str(kok / ad))
        (kok / ad).mkdir(parents=True, exist_ok=True)

    # -- bellek: gecerli ve DEVRILMIS olgular -----------------------------
    ofis.bellek.olgu_yaz("yayin gunu", "ayin 15i", kaynak="insan")
    ofis.bellek.olgu_yaz("yayin gunu", "ayin 22si", kaynak="insan")   # devirir
    ofis.bellek.olgu_yaz("yazim tonu", "sade, abartisiz, samimi", kaynak="insan")
    ofis.bellek.olgu_yaz("destek kanali", "e-posta, 24 saat icinde", kaynak="insan")
    ofis.bellek.olgu_yaz("hedef kitle", "kucuk isletme sahipleri", kaynak="insan")

    ofis.bellek.karar_yaz(
        "Tanitim metinleri 120 kelimeyi gecmeyecek.",
        "Uzun metinler mobilde katlaniyor ve okunmuyor; olcum: mobil "
        "oturumlarin %71'i ilk ekranda kaliyor.",
        "ruzgar", tur="kapsam")
    ofis.bellek.karar_yaz(
        "Degisken degerler metne gomulmeyecek, ayardan okunacak.",
        "Deger degisince elle yazilmis her metin bayatliyor.",
        "demir", tur="teknik")

    # -- sahte motor: jeton yakmadan gercek halka -------------------------
    kutu = {"senaryo": "basarili", "cevap": ""}

    def fabrika(ad, **ayar):
        return SahteMotor(senaryo=kutu["senaryo"], cevap=kutu["cevap"])

    koltuk = Koltuk(ofis, motor_fabrikasi=fabrika)
    lider = Lider(ofis, motor_fabrikasi=fabrika)

    # -- URUN kanadi: lider dagitiyor -------------------------------------
    urun_kollar = [
        {"baslik": "Arama sonucu isaretlemesi",
         "neden": "Sayfalar arama sonucunda zayif gorunuyor",
         "kabul_olcutu": "Dogrulama araci hatasiz donsun",
         "govde": "Yapisal veri isaretlemesi ekle.",
         "yazma_alani": ["sayfa/urun"]},
        {"baslik": "Acilis ekrani hiz iyilestirmesi",
         "neden": "Ekran 4.2 saniyede aciliyor, terk orani yuksek",
         "kabul_olcutu": "Performans olcumu 80 uzeri",
         "govde": "Gereksiz betikleri kaldir, gorselleri tembel yukle.",
         "yazma_alani": ["sayfa/acilis"]},
        {"baslik": "Bildirim akisi",
         "neden": "Bekledigi sey hazir olunca kullanici haber alamiyor",
         "kabul_olcutu": "Test kaydinda bildirim ulassin",
         "govde": "Hazir oldugunda bildirim gonderen akisi kur.",
         "yazma_alani": ["akis/bildirim"]},
    ]
    urun_gorevler = lider.dagit(
        "Kullanici deneyimi iyilessin", urun_kollar,
        gerekce=("Uc kol ayri dosyalara dokunuyor ve birbirini beklemiyor; "
                 "genislik-oncelikli is, paralel kazanir."),
        lider_ad="demir", kanat_id=urun)

    # 1. gorev: bitmis (kanitli, lider kapatmis)
    kutu["cevap"] = ("Isaretleme eklendi.\n"
                     "KANIT terminal: dogrulama araci -> 0 hata, 2 zengin sonuc\n"
                     "KANIT dosya: sayfa/urun/sablon -> yapisal veri eklendi")
    koltuk.kos(urun_gorevler[0]["no"], "yaprak")
    kutu["cevap"] = "Kanitlar olcutu karsiliyor.\nKARAR: kapat"
    lider.incele(urun_gorevler[0]["no"], lider_ad="demir")

    # 2. gorev: incelemede bekliyor
    kutu["cevap"] = ("Hiz iyilestirildi.\n"
                     "KANIT terminal: performans olcumu -> 84\n"
                     "KANIT diff: sayfa/acilis/betik.js -> 3 kutuphane kaldirildi")
    koltuk.kos(urun_gorevler[1]["no"], "cinar")

    # 3. gorev: calisiyor ve SORU SORMUS -> bekleme odasi
    kutu["cevap"] = "Basliyorum."
    koltuk.kos(urun_gorevler[2]["no"], "yaprak") if False else None
    g3 = ofis.tahta.gorev(urun_gorevler[2]["no"])
    ofis.tahta.sahiplen(g3["no"], "yaprak", g3["revizyon"])
    ofis.postane.soru_sor(
        "yaprak", "demir",
        "Bildirim, harici servis uzerinden mi yoksa kendi akisimizdan "
        "mi gitsin? Ikisi de kurulu ve ikisinde de sablon yok.",
        gorev_no=g3["no"])

    # Ikinci soru INSANA. Sahne bilerek iki turlu: bir soru ajana sorulur
    # (ofis kendi cozer, `danisma` teslim eder), biri insana sorulur --
    # cunku bilgi ofisin disindadir ve hicbir ajan onu bilemez. Ikisini
    # ayni kuyruga koymak, insana kendisine dusmeyen isi gosterirdi.
    ofis.postane.soru_sor(
        "bilge", "insan",
        "Rakip fiyat listesine erisim icin bir hesap gerekiyor. "
        "Boyle bir hesabimiz var mi, yoksa acik kaynaklarla mi yetineyim?",
        gorev_no=g3["no"])

    # -- PAZARLAMA kanadi -------------------------------------------------
    pz_kollar = [
        {"baslik": "Duyuru metinleri",
         "neden": "Surum cuma yayinda, metin yok",
         "kabul_olcutu": "5 varyant, yazim tonuna uygun, 120 kelime alti",
         "govde": "5 birincil metin + 3 baslik yaz.",
         "yazma_alani": []},
        {"baslik": "Tanitim butcesi ve hedefleme",
         "neden": "Mevcut tanitim geri donusu dusuk",
         "kabul_olcutu": "Yeni taslak hazir, yayina ALINMAMIS",
         "govde": "Ilgi alani ve benzer kitle kirilimi hazirla.",
         "yazma_alani": ["tanitim/kampanya"]},
    ]
    pz_gorevler = lider.dagit(
        "Yeni surum duyurusu", pz_kollar,
        gerekce=("Metin ve hedefleme ayri uzmanlik, ayri dosya; bekleyen "
                 "bagimlilik yok."),
        lider_ad="ruzgar", kanat_id=pazarlama)

    # metin isi: bitmis
    kutu["cevap"] = ("5 varyant hazir.\n"
                     "KANIT dosya: metinler/duyuru.md -> 5 birincil + 3 baslik\n"
                     "KANIT baglanti: onizleme -> dahili")
    koltuk.kos(pz_gorevler[0]["no"], "deniz")
    kutu["cevap"] = "Yazim tonu tutuyor, uzunluk sinirina uyulmus.\nKARAR: kapat"
    lider.incele(pz_gorevler[0]["no"], lider_ad="ruzgar")

    # reklam isi: calisiyor ve ONAY beklemis -> onay kapisi
    g5 = ofis.tahta.gorev(pz_gorevler[1]["no"])
    ofis.tahta.sahiplen(g5["no"], "kaya", g5["revizyon"])
    ofis.tahta.kanit_ekle(g5["no"], "dosya", "tanitim/kampanya/taslak.json",
                          "3 set, gunluk 750 TL onerisi", "kaya")
    ofis.postane.onay_iste(
        "kaya", "Tanitimi yayina al ve gunluk 750 TL butce ayir",
        ayrinti="3 set · benzer kitle %1 · 14 gun",
        risk="yuksek", gorev_no=g5["no"])

    # -- bekleyen ve bagimli isler (bes sutun dolsun) ---------------------
    b1 = ofis.tahta.gorev_ac(
        "Geri bildirim akisini sadelestir",
        neden="Talepler elle isleniyor, 2 gun suruyor",
        ana_hedef="Kullanici deneyimi iyilessin",
        kabul_olcutu="Kullanici kendi baslatabilsin, test kaydi tamamlansin",
        yazma_alani=["akis/geribildirim"], kanat_id=urun, acan="demir")
    b2 = ofis.tahta.gorev_ac(
        "Geri bildirim ekrani metinleri",
        neden="Yeni akisin ekran metinleri yok",
        ana_hedef="Kullanici deneyimi iyilessin",
        kabul_olcutu="Her ekran icin metin, yazim tonunda",
        yazma_alani=["metinler/geribildirim"], kanat_id=urun, acan="demir")
    ofis.tahta.bagimlilik_ekle(b2["no"], b1["no"])   # b2 bekliyor

    # -- MASADA calisanlar: panelde en kalabalik oda burasi olmali --------
    # Bos bir "masalar" odasi, ofisin durmus oldugunu soyler. Ornek veri
    # gercekci olmali: her zaman calisan biri vardir.
    a1 = ofis.tahta.gorev_ac(
        "Rakip karsilastirmasi",
        neden="Pazara gore nerede oldugumuzu bilmiyoruz",
        ana_hedef="Kullanici deneyimi iyilessin",
        kabul_olcutu="5 rakip, 20 baslik, tablo halinde",
        yazma_alani=[], kanat_id=urun, acan="demir")
    ofis.tahta.sahiplen(a1["no"], "bilge", a1["revizyon"])

    a2 = ofis.tahta.gorev_ac(
        "Surum duyuru e-postasi",
        neden="Yayin cuma, liste hazir ama metin yok",
        ana_hedef="Yeni surum duyurusu",
        kabul_olcutu="Konu satiri + govde, yazim tonunda",
        yazma_alani=[], kanat_id=pazarlama, acan="ruzgar")
    ofis.tahta.sahiplen(a2["no"], "deniz", a2["revizyon"])

    # -- sicil: tekrarlayan ders ------------------------------------------
    ofis.kadro.ders_yaz("cinar", "Kenar durumlarini kabul olcutune yaz",
                        urun_gorevler[1]["id"])
    ofis.kadro.ders_yaz("cinar", "Kenar durumlarini kabul olcutune yaz",
                        urun_gorevler[1]["id"])
    ofis.kadro.ders_yaz("kaya", "Butce degisiminde once onay iste")

    print(f"Ornek ofis kuruldu: {db_yolu}")
    print(f"  kanat   : 2   ajan: {len(kadro)}")
    say = {}
    for g in ofis.tahta.liste():
        say[g["durum"]] = say.get(g["durum"], 0) + 1
    print(f"  gorevler: {say}")
    print(f"  bekleyen: {len(ofis.postane.bekleyen_sorular())} soru, "
          f"{len(ofis.postane.bekleyen_onaylar())} onay")
    print(f"  olgu    : {len(ofis.bellek.gecerli_olgular())} gecerli")
    print(f"  karar   : {len(ofis.bellek.son_kararlar(50))}")


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Ornek ofis kur")
    a.add_argument("--db", default=str(VARSAYILAN))
    kur(Path(a.parse_args().db))
