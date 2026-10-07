# -*- coding: utf-8 -*-
"""Ofis veritabani: sema ve baglanti.

Bu dosya mimarinin kendisidir. Tasarim kararlarinin her biri burada bir
tablo ya da kisit olarak durur; her degismez, IHLAL EDILDIGINDE SISTEMI
SESSIZCE GUVENILMEZ YAPTIGI icin vardir.

Kanit defteri -- neden boyle:

* **Yazma alani KILITTIR, uyari degil.** Cognition'in olctugu kural: birden
  fazla ajan ayni anda YAZARSA cakisan kararlar cikar (stil, kenar durumu,
  desen). Ajanlar akil verir, tek ajan eder. `yazma_kilidi` tablosu bu yuzden
  gercek bir kilittir; cakisan bir talep REDDEDILIR, uyarilmaz.

* **Olgular cift-zamanlidir.** Bir olgunun ne zaman dogru OLDUGU ile ne zaman
  KAYDEDILDIGI ayri seylerdir. "Iade suresi 14 gun" olgusu Mart'ta gecersiz
  olduysa, duz bir bellek iki olguyu da esit dogrulukta getirir ve ajan
  yanlis olani kullanir. `gecerli_bitis` dolu olan olgu artik dogru degildir;
  brifinge girmez ama gecmis okunabilsin diye silinmez.

* **Her mutasyon revizyon tasir (CAS).** Bayat yazar reddedilir. Aksi halde
  iki lider ayni isi es zamanli duzenler ve biri otekinin degisikligini
  sessizce ezer.

* **Bagimliliklar DAG olmalidir.** Dongu, hicbir isin asla hazir olmamasi
  demektir; tahta calisiyor gorunur, hicbir sey ilerlemez.

* **Kanitsiz gorev kapanmaz.** MAST olcumu: hatalarin %21,3'u dogrulama
  eksikligi. Kapanis bir DURUM MAKINESI kapisidir, aliskanlik degil.

* **Her dagitim karari gerekcesiyle yazilir.** Anthropic'in olcumu: coklu
  ajan ~15x jeton yakar ve performans varyansinin %80'ini jeton kullanimi
  aciklar. Lider boler ya da bolmez -- ama NEDEN'ini yazmak zorundadir.

* **Ad geri donmez.** Basarisiz bir ajan bile adini tuketir. Ad yeniden
  kullanilirsa gecmis okunamaz olur: "demir'e giden mesaj" iki farkli ajani
  gosterebilir ve hangisinin ne yaptigi bir daha bilinemez.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

#: Tum zamanlar UTC ve ISO-8601. Yerel saat kaydedilmez: makine saat dilimi
#: degisirse gecmis kayitlar birbiriyle karsilastirilamaz hale gelir.
def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


VARSAYILAN_YOL = Path(__file__).resolve().parent.parent / "veri" / "ofis.sqlite3"


SEMA = """
-- ---------------------------------------------------------------------------
-- PROJE: isin ne oldugu. Brifingin 2. katmani (kunye) bu satirdan uretilir.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proje (
    id              TEXT PRIMARY KEY,
    ad              TEXT NOT NULL UNIQUE,
    amac            TEXT NOT NULL DEFAULT '',   -- ne yapiyoruz, kimin icin
    basari_olcutu   TEXT NOT NULL DEFAULT '',   -- bittigini nasil anlariz
    kapsam_disi     TEXT NOT NULL DEFAULT '',   -- ne YAPMIYORUZ (en cok atlanan alan)
    kisitlar        TEXT NOT NULL DEFAULT '',   -- teknik/marka kisitlari
    sozluk          TEXT NOT NULL DEFAULT '',   -- projeye ozel terimler
    kok_klasor      TEXT NOT NULL DEFAULT '',
    durum           TEXT NOT NULL DEFAULT 'acik',  -- acik | arsiv
    revizyon        INTEGER NOT NULL DEFAULT 1,
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- KANAT: tek ofis, cok kanat (URUN / PAZARLAMA / DESTEK...). Kadro ve tahta
-- kanada aittir; kunye ve karar gunlugu OFIS GENELIDIR -- pazarlama, urunun
-- ne cikardigini bilmek zorundadir.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kanat (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,
    onek            TEXT NOT NULL,              -- gorev numarasi oneki: UR, PZ, DS
    renk            TEXT NOT NULL DEFAULT '#E0785A',
    olusturuldu     TEXT NOT NULL,
    UNIQUE (proje_id, ad)
);

-- ---------------------------------------------------------------------------
-- AJAN: kadro. Kimlik `oturum_id`de yasar -- makine kapanip acilsa da ajan
-- kaldigi yerden devam eder. `ad` PROJE GENELINDE tekildir ve geri donmez.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ajan (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    kanat_id        TEXT REFERENCES kanat(id),
    ad              TEXT NOT NULL,              -- kebab-case, adres ve kimlik
    meslek          TEXT NOT NULL,              -- lider | backend | arayuz | test | arastirma | metin ...
    lider_mi        INTEGER NOT NULL DEFAULT 0,

    -- Motor katmani FISE TAKILIR: bugun 11 motor var, yarin baskalari olacak.
    -- Cekirdek motoru bilmez, sadece adaptor adini bilir.
    motor           TEXT NOT NULL DEFAULT 'claude',   -- claude | codex | opencode | api
    model           TEXT NOT NULL DEFAULT '',
    efor            TEXT NOT NULL DEFAULT 'normal',   -- dusuk | normal | yuksek

    -- 'eller' komut calistirir, dosya yazar (ajanik CLI sart).
    -- 'kafa' yalnizca dusunup metin uretir (ucuz API yeter).
    -- Bu ayrim maliyet icin degil SORUMLULUK icindir: kafa yazamaz.
    tur             TEXT NOT NULL DEFAULT 'eller',    -- eller | kafa

    klasor          TEXT NOT NULL DEFAULT '',   -- kendi calisma alani
    oturum_id       TEXT NOT NULL DEFAULT '',   -- motorun oturum kimligi (resume)
    faz             TEXT NOT NULL DEFAULT 'kuruluyor',  -- kuruluyor | aktif | basarisiz
    revizyon        INTEGER NOT NULL DEFAULT 1,
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL,
    UNIQUE (proje_id, ad)
);

-- ---------------------------------------------------------------------------
-- GOREV: tahta. `neden` ve `ana_hedef` bos birakilamaz -- MAST'in en buyuk
-- hata kumesi (%41,8) belirtim/sistem tasarimi. Gorev ne icin var oldugunu
-- tasimazsa ajan isi kusursuz yapip projeyi iskalar.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gorev (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    kanat_id        TEXT REFERENCES kanat(id),
    no              INTEGER NOT NULL,           -- insan tarafindan okunan numara
    baslik          TEXT NOT NULL,
    govde           TEXT NOT NULL DEFAULT '',
    neden           TEXT NOT NULL,              -- bu is NICIN var
    ana_hedef       TEXT NOT NULL,              -- bagli oldugu ust hedef (senin cumlen)
    kabul_olcutu    TEXT NOT NULL,              -- bittigini nasil kanitlayacak
    yazma_alani     TEXT NOT NULL DEFAULT '[]', -- JSON dizi: ["api/", "db/"]
    ek_klasorler    TEXT NOT NULL DEFAULT '[]', -- JSON dizi: ofis DISINDA acilan MUTLAK yollar
    -- ZORLUK: bu is ne kadar guc gerektiriyor. Lider yazar, ofis modele cevirir.
    -- Gerekli guc ISIN ozelligidir, kisinin degil: ayni ajan kolay isi ucuz
    -- modelde, zor isi guclu modelde kosabilmeli. (Rakip bunu ISE ALIRKEN
    -- seciyor -- yani kisiye yaziyor; o zaman ayni kisi her ise ayni gucle
    -- girer.) Bos birakilirsa ajanin kendi modeli kullanilir.
    zorluk          TEXT NOT NULL DEFAULT '',   -- '' | kolay | orta | zor
    -- Pahali secim GEREKCE ISTER -- fan-out kapisinin ayni mantigi.
    zorluk_gerekce  TEXT NOT NULL DEFAULT '',
    -- TARAYICI ALANI: bu is hangi kaynaklara (origin) gidebilir.
    -- Yazma alaninin WEB HALI. Bos ise tarayici HIC verilmez -- klasor
    -- gibi: acikligi is beyan eder, ajan degil.
    tarayici_alani  TEXT NOT NULL DEFAULT '[]',
    tarayici_yazma  INTEGER NOT NULL DEFAULT 0,
    -- PAYLASILAN KABIN (patronun oturumu) bu ise VERILDI mi. Yetki
    -- insandan gelir ve ISE yazilir: halkanin bir kosusuna yazilsaydi
    -- is kesilip "Surdur"le devam edince kabin sessizce kaybolurdu.
    tarayici_kabin  INTEGER NOT NULL DEFAULT 0,
    -- Isin dokunacagi claude.ai baglayicilari. BIR SUZGEC DEGIL:
    -- teknik olarak hepsi birden yuklenir (olculdu). Bu alan
    -- 'odemeye deger mi' kararini ve NIYETI kayda gecirir.
    baglayicilar    TEXT NOT NULL DEFAULT '[]',
    sahip           TEXT NOT NULL DEFAULT '',   -- ajan.ad
    durum           TEXT NOT NULL DEFAULT 'bekliyor',
                    -- bekliyor | hazir | calisiyor | inceleme | bitti | iptal
    oncelik         TEXT NOT NULL DEFAULT 'normal',  -- dusuk | normal | yuksek
    revizyon        INTEGER NOT NULL DEFAULT 1,
    silindi         INTEGER NOT NULL DEFAULT 0, -- mezar tasi: gorunmez ama gecmis okunur
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL,
    UNIQUE (proje_id, no)
);

CREATE TABLE IF NOT EXISTS gorev_bagimlilik (
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    bagli_oldugu    TEXT NOT NULL REFERENCES gorev(id),
    PRIMARY KEY (gorev_id, bagli_oldugu)
);

-- ---------------------------------------------------------------------------
-- YAZMA KILIDI: Yasa 1'in kod hali. Bir yol oneki ayni anda TEK ajana aittir.
-- Cakisan talep reddedilir. Bu tablo bos degilse, o yollara baska kimse
-- yazamaz -- uyari yok, ret var.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yazma_kilidi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    yol_oneki       TEXT NOT NULL,              -- normalize edilmis: "api/orders"
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    ajan_ad         TEXT NOT NULL,
    alindi          TEXT NOT NULL,
    -- Kira suresi: ajan olurse kilit sonsuza kadar kalmasin. Heartbeat
    -- gecmezse kilit dusar ve is yeniden sahiplenilebilir.
    son_nabiz       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_kilit_yol ON yazma_kilidi (proje_id, yol_oneki);

-- ---------------------------------------------------------------------------
-- KANIT: kapanisin kapisi. `gorev.durum = 'bitti'` olabilmesi icin bu tabloda
-- en az bir satir olmali. "Calisiyor" demek kanit degil, iddiadir.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kanit (
    id              TEXT PRIMARY KEY,
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    tur             TEXT NOT NULL,              -- terminal | diff | gorsel | dosya | baglanti
    baslik          TEXT NOT NULL,
    icerik          TEXT NOT NULL DEFAULT '',   -- kisa cikti ya da dosya yolu
    ekleyen         TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- KARAR GUNLUGU: ekibin ortak hafizasi. Brifingin 3. katmani buradan uretilir.
-- Fan-out karari da buraya yazilir: lider bolerse de bolmezse de GEREKCE yazar.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS karar (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    tur             TEXT NOT NULL DEFAULT 'genel',
                    -- genel | dagitim | ret | teknik | kapsam
    karar           TEXT NOT NULL,
    gerekce         TEXT NOT NULL,              -- bos birakilamaz
    veren           TEXT NOT NULL,              -- ajan.ad ya da 'insan'
    etkilenen_yollar TEXT NOT NULL DEFAULT '[]',
    olusturuldu     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_karar_proje ON karar (proje_id, olusturuldu DESC);

-- ---------------------------------------------------------------------------
-- OLGU: cift-zamanlı bellek. Dogru olan sey ile ne zaman dogru oldugu ayri.
--   gecerli_baslangic / gecerli_bitis : DUNYADA ne zaman dogruydu
--   kaydedildi                        : BIZ ne zaman ogrendik
-- `gecerli_bitis` NULL ise olgu hala gecerlidir. Dolu ise brifinge GIRMEZ
-- ama silinmez: "eskiden 14 gundu" sorusunun cevabi kaybolmasin.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olgu (
    id                  TEXT PRIMARY KEY,
    proje_id            TEXT NOT NULL REFERENCES proje(id),
    konu                TEXT NOT NULL,          -- "iade suresi", "marka tonu"
    icerik              TEXT NOT NULL,
    kaynak              TEXT NOT NULL DEFAULT '',   -- kim/nereden
    gecerli_baslangic   TEXT NOT NULL,
    gecerli_bitis       TEXT,                   -- NULL = hala gecerli
    kaydedildi          TEXT NOT NULL,
    gecersiz_kilan      TEXT REFERENCES olgu(id)    -- hangi olgu bunu devirdi
);

CREATE INDEX IF NOT EXISTS ix_olgu_konu ON olgu (proje_id, konu, gecerli_bitis);

-- ---------------------------------------------------------------------------
-- DERS: ajan basina sicil. Lider ayni sebeple ikinci kez is geri cevirirse
-- buraya tek satir duser ve o ajanin HER brifinginin 1. katmanina yapisir.
-- Sirket geneli kural degil, KISIYE OZEL ders -- daha isabetli.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ders (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ajan_ad         TEXT NOT NULL,
    ders            TEXT NOT NULL,
    sebep_gorev_id  TEXT REFERENCES gorev(id),
    tekrar          INTEGER NOT NULL DEFAULT 1, -- kac kez ayni hata
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ders_ajan ON ders (proje_id, ajan_ad);

-- ---------------------------------------------------------------------------
-- MESAJ: posta kutusu. `mod = 'bekleyen'` olan mesaj ajani DURDURUR -- soru
-- sorup cevap bekler. Cognition'in acik sorunu: "ajanlar arasi iletisim
-- varsayilan olarak calismiyor". Burada varsayilan olarak calisir.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mesaj (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gonderen        TEXT NOT NULL,
    alici           TEXT NOT NULL,              -- ajan.ad ya da 'insan'
    govde           TEXT NOT NULL,
    mod             TEXT NOT NULL DEFAULT 'sessiz',  -- sessiz | uyandiran | bekleyen | yonlendirme (patronun notu; okundu=1 ajana ULASTI)
    gorev_id        TEXT REFERENCES gorev(id),
    cevap           TEXT NOT NULL DEFAULT '',
    cevaplandi      TEXT,
    okundu          INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mesaj_alici ON mesaj (proje_id, alici, okundu);

-- ---------------------------------------------------------------------------
-- ONAY: riskli adim insana takilir. Tam otonomi istenmez -- is yapan ajan
-- sessizce yanlis yone sapabilir. Kod yazmak sormaz; para harcamak, yayina
-- almak, disariya yazmak sorar.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS onay (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    isteyen         TEXT NOT NULL,
    eylem           TEXT NOT NULL,              -- insan diliyle ne yapacak
    ayrinti         TEXT NOT NULL DEFAULT '',   -- komut / istek govdesi
    risk            TEXT NOT NULL DEFAULT 'orta',   -- dusuk | orta | yuksek
    durum           TEXT NOT NULL DEFAULT 'bekliyor',  -- bekliyor | onaylandi | reddedildi
    cevap_notu      TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    cevaplandi      TEXT
);

-- ---------------------------------------------------------------------------
-- EKIP ONERISI: lider kadro ONERIR, insan ONAYLAR, ofis ISE ALIR.
--
-- Neden ayri bir tablo: oneri iki komut arasinda YASAMALI. `ekip oner`
-- ile `ekip kur` arasinda surec olur, oneri diskte durmali.
--
-- Neden `onay` tablosuna sikistirmadik: onay tek bir eylemi tasir
-- (metin + risk). Ekip onerisi YAPILI bir sey -- her satir bir ajan
-- (ad, rol, motor, model, gerekce) ve kurulurken tek tek ise alinacak.
-- JSON'u insanin okudugu alana gommek, insana makine metni gostermek
-- olurdu; ayri saklamak ikisini de dogru yerinde tutar.
--
-- Kadro kurmak bir YETKI GENISLETMESIDIR: lider senin limitini
-- harcayacak bir kadroyu kendi kuramaz. Ayni kural klasorde de var --
-- yetki insandan gelir, dagitim liderden.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ekip_onerisi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    no              INTEGER NOT NULL,           -- insanin gordugu numara
    kanat_id        TEXT REFERENCES kanat(id),
    hedef           TEXT NOT NULL,              -- hangi istek bunu dogurdu
    gerekce         TEXT NOT NULL,              -- lider NICIN boyle onerdi
    uyeler          TEXT NOT NULL DEFAULT '[]', -- JSON: [{ad, rol, motor, model, gerekce}]
    oneren          TEXT NOT NULL DEFAULT '',   -- lider adi
    durum           TEXT NOT NULL DEFAULT 'bekliyor',  -- bekliyor | kuruldu | reddedildi
    sebep           TEXT NOT NULL DEFAULT '',   -- RET gerekcesi (zorunlu)
    olusturuldu     TEXT NOT NULL,
    karar_verildi   TEXT,
    UNIQUE (proje_id, no)
);

-- ---------------------------------------------------------------------------
-- AYAR: ofis basina anahtar/deger. Bugunku tek musterisi ABONELIK PLANI.
--
-- Neden tablo, neden koda gomulu sabit degil: plan DEGISIR. Kullanici
-- bugun Claude Max 5x + ChatGPT Plus; yarin Max 20x + GPT Pro olabilir
-- ve o zaman butun modeller acilir. Plani koda gomseydik her plan
-- degisikligi bir kod degisikligi olurdu -- zincirde ayni karari bir kez
-- verdik: *"sabit kodlanmis zincir, farkli hesap duzeni olan herkesi
-- kodu degistirmeye zorlardi."*
--
-- Neden dosya degil tablo: ayar ofise aittir, makineye degil. Iki ayri
-- ofis (deneme ve gercek) ayni makinede farkli planlarla kosabilmeli.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ayar (
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    anahtar         TEXT NOT NULL,
    deger           TEXT NOT NULL DEFAULT '',
    guncellendi     TEXT NOT NULL,
    PRIMARY KEY (proje_id, anahtar)
);

-- ---------------------------------------------------------------------------
-- HESAP: motor + KIMLIK. Bir motorun hangi hesapla kostugu.
--
-- Kullanici (20.09.2026): *"abonelik hesaplari degisebilir veya api ile
-- de ai modelleri kullaniriz; ilerde COKLU HESAP bile olabilir."*
--
-- Bugune kadar motor = adaptordu ve kimlik SABITTI: claude CLI'in kendi
-- oturumu, codex'in kendi evi. Yani "iki Claude hesabi" ya da "abonelik
-- + API yan yana" ifade edilemiyordu.
--
-- Hesap bunu ayirir: **motor NASIL konusulacagini, hesap KIMIN adina
-- konusulacagini** soyler. Ayni motorun iki hesabi olabilir; ayni hesap
-- abonelik ya da API olabilir.
--
-- Nobet zinciri bundan sonra (motor, model) degil (HESAP, model)
-- uzerinde yurur -- ki zaten istenen buydu: "limit gelince otekine
-- gec." Iki abonelik arasi gecis, bunun ozel bir halidir.
--
-- ORTAM bir JSON'dur ve **ANAHTAR DEGERI ICERMEZ**: `{"ANTHROPIC_API_KEY":
-- "@gizli:ISIM"}` gibi bir REFERANS tutar, gercek deger tur aninda
-- `ofis/gizli.py`den (proje kokunun DISINDA) cozulur. Anahtari buraya
-- yazsaydik ajanin `Bash(cat *)` izni onu okuyabilirdi.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hesap (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,              -- 'claude-max', 'codex-is', 'api-1'
    motor           TEXT NOT NULL,              -- claude | codex | ...
    tur             TEXT NOT NULL DEFAULT 'abonelik',  -- abonelik | api
    plan            TEXT NOT NULL DEFAULT '',   -- max5 | max20 | plus | pro200 ...
    ortam           TEXT NOT NULL DEFAULT '{}', -- JSON: env; anahtar DEGIL referans
    sira            INTEGER NOT NULL DEFAULT 100,  -- nobet zincirindeki sira
    aktif           INTEGER NOT NULL DEFAULT 1, -- limit dolunca kapatilabilir
    aylik_sinir_usd REAL,                       -- yalniz API hesabi: ayda en cok $
    not_            TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL,
    UNIQUE (proje_id, ad)
);

-- ---------------------------------------------------------------------------
-- OLAY: olay bellegi. Ne oldu, ne zaman, kim. Panel canli akisi buradan okur;
-- "uyanis ozeti" de buradan uretilir -- devam eden oturumun baglami ESKIDIR.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olay (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proje_id        TEXT NOT NULL,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    gorev_id        TEXT,
    tur             TEXT NOT NULL,              -- gorev_acildi | sahiplenildi | cikti | kanit | kapandi ...
    govde           TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_olay_proje ON olay (proje_id, id DESC);

-- ---------------------------------------------------------------------------
-- BRIFING: ajana verilen metnin kaydi. Neden saklaniyor: bir is yanlis
-- gittiginde "ajan ne biliyordu" sorusunun cevabi olmadan hata ayiklanamaz.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brifing (
    id              TEXT PRIMARY KEY,
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    ajan_ad         TEXT NOT NULL,
    metin           TEXT NOT NULL,
    jeton_tahmini   INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- DEGISIM: ajanin ne SOYLEDIGI degil, diskte NE DEGISTIGI.
--
-- Neden ayri bir tablo ve neden `kanit` degil: `kanit` ajanin BILDIRDIGI
-- seydir ve oyle kalmali -- koltuk kanit uydurmaz. Bu tablo ofisin KENDI
-- olcumu: tur oncesi ve sonrasi anlik goruntunun farki. Ikisini ayni yere
-- koymak, olculen ile beyan edileni ayirt edilemez kilardi.
--
-- `beyan_disi`: dosya, isin yazma alaninin DISINDA. Yazma kilidi bir
-- BEYANDIR ve bugune kadar beyanin gercekle uyustugu hic olculmedi.
-- `olculemedi`: ikili / cok buyuk / okunamadi. Bos degilse `yama` da
-- bostur -- okunmamis bir dosyanin yamasi uydurma olurdu.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degisim (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    yol             TEXT NOT NULL,              -- KOK-GORELI, '/' ayracli
    hal             TEXT NOT NULL,              -- eklendi | degisti | silindi
    beyan_disi      INTEGER NOT NULL DEFAULT 0,
    eklenen         INTEGER NOT NULL DEFAULT 0,
    silinen         INTEGER NOT NULL DEFAULT 0,
    yama            TEXT NOT NULL DEFAULT '',
    olculemedi      TEXT NOT NULL DEFAULT '',
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_degisim_proje
    ON degisim (proje_id, olusturuldu DESC);

-- ---------------------------------------------------------------------------
-- TUR_ANLIK: bir turun ONCESI ve SONRASI -- golge depodaki commit kimlikleri.
--
-- `geri_al.py` bununla YALNIZ o turun dokundugu dosyalari geri alir.
-- Geri almanin kendisi de yeni bir satirdir (ajan_ad 'insan (geri alma)'),
-- yani geri alma da geri alinabilir. Silinmez; `geri_alindi` ne zaman ve
-- hangi kayitla geri alindigini yazar.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tur_anlik (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    kok             TEXT NOT NULL,
    once            TEXT NOT NULL,
    sonra           TEXT NOT NULL,
    dosya           INTEGER NOT NULL DEFAULT 0,
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    not_            TEXT NOT NULL DEFAULT '',
    geri_alindi     TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_tur_anlik_proje
    ON tur_anlik (proje_id, olusturuldu DESC);

-- ---------------------------------------------------------------------------
-- KURAL: HER brifinge KOSULSUZ giren, INSAN onayli ofis kurali.
--
-- Olgu goreve gore SECILIR (ve gorevle ortak kelimesi yoksa elenir);
-- kural her ise girer. Bir bilgi ya da tekrarlayan bir ders buraya
-- YUKSELTILIR. Kaynagi tutulur (olgu konusu / ders kimligi).
-- SILINMEZ, kaldirilir: ne zaman, neden -- gecmis okunur.
-- ---------------------------------------------------------------------------
-- HAFIZA ONERISI (06.10.2026, Asama 2 / E31): patron sohbette kalici bir
-- bilgi soyledi ("iade suresi 30 gun"); lider onu ONERIR, patron "Yaz" der.
-- `alinti` patronun mesajindan KELIMESI KELIMESINE (ofis denetler).
CREATE TABLE IF NOT EXISTS hafiza_onerisi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    konu            TEXT NOT NULL,
    icerik          TEXT NOT NULL,
    alinti          TEXT NOT NULL,
    oneren          TEXT NOT NULL,
    durum           TEXT NOT NULL DEFAULT 'bekliyor',   -- bekliyor | yazildi | reddedildi
    olusturuldu     TEXT NOT NULL,
    cevaplandi      TEXT
);

-- KONU TAKMA ADI (06.10.2026, Asama 2 / E32): ayni bilgi iki konu adiyla
-- yazilmisti ("servis portu" / "Servis port numarasi"); patron BIRLESTIRIR.
-- Takma ada sonradan yazilan bilgi ve `[[takma]]` bagi ASIL konuya gider.
CREATE TABLE IF NOT EXISTS konu_takma (
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    takma_anahtar   TEXT NOT NULL,
    asil            TEXT NOT NULL,
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    PRIMARY KEY (proje_id, takma_anahtar)
);

-- BELGE KUTUPHANESI (06.10.2026, Asama 2 / E77): patronun yukledigi belge
-- parcalara bolunur, her parca YERINI (sayfa/bolum/satir) tasir; ajan ve
-- lider sorulara kaynagiyla cevap verir (`ofis/belge.py`).
CREATE TABLE IF NOT EXISTS belge (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,
    yol             TEXT NOT NULL,
    ozet            TEXT NOT NULL,
    tur             TEXT NOT NULL,
    boyut           INTEGER NOT NULL DEFAULT 0,
    parca           INTEGER NOT NULL DEFAULT 0,
    ekleyen         TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT
);

CREATE TABLE IF NOT EXISTS belge_parca (
    belge_id        TEXT NOT NULL REFERENCES belge(id),
    sira            INTEGER NOT NULL,
    yer             TEXT NOT NULL,
    metin           TEXT NOT NULL,
    PRIMARY KEY (belge_id, sira)
);

-- TESLIM PUANI (06.10.2026, Asama 2 / E78): patron kapanan ise 1-5 verir;
-- dusuk puanin gerekcesi ajanin dersi olur, puan karneye gider (`ofis/puan.py`).
CREATE TABLE IF NOT EXISTS teslim_puani (
    gorev_id        TEXT PRIMARY KEY REFERENCES gorev(id),
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    puan            INTEGER NOT NULL,
    gerekce         TEXT NOT NULL DEFAULT '',
    veren           TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL
);

-- CIHAZ (06.10.2026, Asama 3 / telefon): eslestirilmis telefonlar. Anahtar
-- yalniz OZETIYLE durur; cihaz silinmez, kaldirilir (acil kesme).
CREATE TABLE IF NOT EXISTS cihaz (
    id              TEXT PRIMARY KEY,
    ad              TEXT NOT NULL,
    anahtar_ozet    TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    son_gorulme     TEXT NOT NULL,
    push_abonelik   TEXT NOT NULL DEFAULT '',
    kaldirildi      TEXT
);

CREATE TABLE IF NOT EXISTS kural (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    metin           TEXT NOT NULL,
    kaynak_tur      TEXT NOT NULL DEFAULT 'insan',   -- insan | olgu | ders
    kaynak          TEXT NOT NULL DEFAULT '',
    gerekce         TEXT NOT NULL,
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT,
    kaldirma_sebebi TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- IZIN: patronun ACIKCA istedigi riskli eylem sorulmaz (ofis/izin.py).
-- `gorev_id` doluysa o isin (patronun sozunden), bossa KALICI (insan elle).
-- Silinmez, kaldirilir. Para ve silme bu tabloya hic giremez.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS izin (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    sinif           TEXT NOT NULL,
    desen           TEXT NOT NULL,
    alinti          TEXT NOT NULL DEFAULT '',
    kaynak          TEXT NOT NULL,                  -- patron_sozu | insan
    gerekce         TEXT NOT NULL DEFAULT '',
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT,
    kaldirma_sebebi TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- CANLI DEGISIM -- tur SURERKEN olculen ara fark (degisim.CanliIzleyici).
--
-- Ayri tablo, cunku ara olcum KESIN degildir: tur bitince silinir ve
-- yerini `degisim` kaydi alir. Ayni tabloda dursaydi bir dosyanin ara
-- hali ile son hali iki ayri "degisiklik" gibi gorunurdu.
-- (gorev, yol) basina TEK satir: ayni dosyanin her duzenlemesi satiri
-- gunceller, defteri buyutmez. `damga` ns -- "en son dokunulan"
-- siralamasi saniye cozunurlugunde beraberlige dusmesin.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canli_degisim (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT NOT NULL,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    yol             TEXT NOT NULL,
    hal             TEXT NOT NULL,
    beyan_disi      INTEGER NOT NULL DEFAULT 0,
    eklenen         INTEGER NOT NULL DEFAULT 0,
    silinen         INTEGER NOT NULL DEFAULT 0,
    yama            TEXT NOT NULL DEFAULT '',
    olculemedi      TEXT NOT NULL DEFAULT '',
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    guncellendi     TEXT NOT NULL,
    damga           INTEGER NOT NULL DEFAULT 0,
    UNIQUE (gorev_id, yol)
);

-- ---------------------------------------------------------------------------
-- KUYRUK (01.10.2026): patronun lidere verdigi isler SIRAYA girer. Lider
-- mesgulken gelen mesaj reddedilmez (ilk surum 409 "bitmesini bekle"
-- diyordu); sira bosalinca ofis kendisi baslatir. DEFTERDE durur: panel
-- kapanip acilsa da kaybolmaz. `seri`: ara vermeden islenen isler --
-- seri bitince donus raporu yazilir (modelsiz, defterden).
-- durum: bekliyor | kosuyor | bitti | hata | iptal
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kuyruk (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    metin           TEXT NOT NULL,
    lider_ad        TEXT NOT NULL,
    atanan          TEXT NOT NULL DEFAULT '',
    tarayici_alani  TEXT NOT NULL DEFAULT '[]',
    kabin           INTEGER NOT NULL DEFAULT 0,
    kaynak          TEXT NOT NULL DEFAULT 'insan',
    durum           TEXT NOT NULL DEFAULT 'bekliyor',
    seri            TEXT NOT NULL DEFAULT '',
    kosan_surec     TEXT NOT NULL DEFAULT '',
    devam           INTEGER NOT NULL DEFAULT 0,
    gorev_sinir     INTEGER NOT NULL DEFAULT 0,
    not_            TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    basladi         TEXT,
    bitti           TEXT
);

CREATE INDEX IF NOT EXISTS ix_kuyruk_durum ON kuyruk (proje_id, durum);

-- ZAMANLI IS (01.10.2026, F5/4): `zamanlayici.py`. Kural JSON (gunluk,
-- haftalik, bir_kez, aralik), yerel saatle konusulur; `sonraki` UTC.
CREATE TABLE IF NOT EXISTS zamanli (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    no              INTEGER NOT NULL,
    metin           TEXT NOT NULL,
    lider_ad        TEXT NOT NULL,
    kural           TEXT NOT NULL,
    sonraki         TEXT,
    etkin           INTEGER NOT NULL DEFAULT 1,
    son_calisma     TEXT,
    kaynak          TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL
);
"""


def _goc_codex_maliyet(conn) -> None:
    """E11: eski codex turlarinin `maliyet_usd: 0.0` kaydi -> None.

    Codex dolar BILDIRMEZ; adaptor 21.09'a kadar `0.0` yaziyordu ve bu
    OLCULMUS SIFIR demekti -- panel ve kullanim o turlari bedava
    gosterdi. Duzeltme yalniz codex turlarina (motor 'codex' ya da model
    'gpt-' ile baslayan) ve tam 0'a dokunur; Claude'un gercek sifirina
    (baslamadan dusen tur) dokunmaz. Degisen kayda not dusulur.
    """
    import json as _json
    for rowid, govde in conn.execute(
            "SELECT rowid, govde FROM olay WHERE tur = 'tur_ozeti'").fetchall():
        try:
            d = _json.loads(govde or "{}")
        except ValueError:
            continue
        codex = (d.get("motor") == "codex"
                 or str(d.get("model") or "").startswith("gpt-"))
        mal = d.get("maliyet_usd")
        if codex and isinstance(mal, (int, float)) and mal == 0:
            d["maliyet_usd"] = None
            d["maliyet_notu"] = ("E11 gocu: codex dolar bildirmez; eski 0.0 "
                                 "olculmus sifir sanilirdi")
            conn.execute("UPDATE olay SET govde = ? WHERE rowid = ?",
                         (_json.dumps(d, ensure_ascii=False), rowid))


def _goc_takimsiz_isler(conn) -> None:
    """Takimlar gelmeden acilmis isler (kanat_id NULL) bir takim alir.

    OLCULDU (01.10.2026, cok takim sinamasi): takimsiz eski is ANA'nin
    halkasinda WEB'in ajanina verildi (uygun ajan butun kadrodan secildi)
    ve incelemesi "bu kanadin lideri yok" diye halkayi dusurdu. Kural
    `isin_takimi` ile ayni: SAHIBININ takimi; sahibi yoksa projede LIDERI
    olan tek takim. Ikisi de yoksa dokunulmaz (tahmin yok).
    """
    # Sutunlari olmayan (cok eski / yarim) defterde goc ATLANIR: goc paneli
    # acilamaz hale getirmemeli (duman_klasor eski sema sinamasi yakaladi).
    def _sutunlar(tablo):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({tablo})").fetchall()}
    if not ({"proje_id", "sahip", "kanat_id"} <= _sutunlar("gorev")
            and {"proje_id", "ad", "kanat_id", "lider_mi"} <= _sutunlar("ajan")):
        return
    for g_id, proje_id, sahip in conn.execute(
            "SELECT id, proje_id, sahip FROM gorev WHERE kanat_id IS NULL").fetchall():
        kanat = None
        if sahip:
            r = conn.execute("SELECT kanat_id FROM ajan WHERE proje_id = ? AND ad = ?",
                             (proje_id, sahip)).fetchone()
            kanat = r[0] if r else None
        if not kanat:
            liderli = conn.execute("SELECT DISTINCT kanat_id FROM ajan WHERE proje_id = ? "
                                   "AND lider_mi = 1 AND kanat_id IS NOT NULL",
                                   (proje_id,)).fetchall()
            kanat = liderli[0][0] if len(liderli) == 1 else None
        if kanat:
            conn.execute("UPDATE gorev SET kanat_id = ? WHERE id = ?", (kanat, g_id))


#: (surum, islev) -- yalniz SONA eklenir, sira degismez.
VERI_GOCLERI = (
    (1, _goc_codex_maliyet),
    (2, _goc_takimsiz_isler),
)


def _maske_parametre(p):
    from .gizli import maskele
    if isinstance(p, dict):
        return {k: maskele(v) for k, v in p.items()}
    if isinstance(p, (list, tuple)):
        return type(p)(maskele(v) for v in p)
    return p


class MaskeliBaglanti(sqlite3.Connection):
    """ANAHTAR MASKELEME (F3 / E23) -- deftere yazan TEK kapi.

    Deftere metin yazan ~20 tablo ve bir o kadar UPDATE var (olay, kanit,
    mesaj, onay, degisim yamasi, olgu, karar...). Her birine ayri ayri
    maskeleme koymak birinin unutulmasi demekti -- bu projede "iki
    kopyadan biri unutulur" alti kez odendi. Burada baglantinin kendisi
    INSERT/UPDATE/REPLACE parametrelerini `gizli.maskele`den gecirir:
    yarin eklenen tablo da kendiliginden kapsanir.

    Yalniz PARAMETRELER maskelenir (butun yazmalar parametreli); okuma
    dokunulmaz. Sinir: sqlite3 komut satirindan ya da baska bir aractan
    yapilan yazma bu kapidan gecmez.
    """

    def execute(self, sql, parametreler=(), /):
        bas = sql.lstrip()[:7].upper()
        if bas.startswith(("INSERT", "UPDATE", "REPLACE")):
            parametreler = _maske_parametre(parametreler)
        return super().execute(sql, parametreler)

    def executemany(self, sql, dizi, /):
        bas = sql.lstrip()[:7].upper()
        if bas.startswith(("INSERT", "UPDATE", "REPLACE")):
            dizi = [_maske_parametre(p) for p in dizi]
        return super().executemany(sql, dizi)


class Veritabani:
    """SQLite sarmalayici. Tek dosya, tek makine, disa bagimlilik yok."""

    def __init__(self, yol=None) -> None:
        # YOL MUTLAKLASTIRILIR. Bu bir kolaylik degil, SESSIZ BIR HATANIN
        # kapatilmasidir.
        #
        # OLCULDU (19.09.2026): kabuk `--db veri/ofis.sqlite3` ile GORELI
        # bir yol aliyordu. Ofis MCP sunucusu her tur icin ayri bir surec
        # olarak baslar ve AJANIN KLASORUNDE kosar -- yani ayni goreli yol
        # baska bir yere cozulur. Sonuc: `calisma/veri/ofis.sqlite3` diye
        # BOMBOS bir veritabani yaratildi.
        #
        # Hata vermedi. SQLite olmayan dosyayi yaratir, sema kurulur, her
        # sey calisir GORUNUR. Ama:
        #   * ajanin `kanit_ekle` cagrisi "gorev bulunamadi" dedi --
        #     is bitmisti, defterde bitmemis kaldi;
        #   * `durum` araci BOS bir ofis dondurdu, yani ajan OFISIN
        #     YANLIS RESMINI gordu ve ona gore akil yurutta.
        #
        # Ikincisi birincisinden kotu: eksik kayit fark edilir, YANLIS
        # bilgi fark edilmez. Ajan uc tur boyunca dogru is yapti ve
        # sistem onu "0 kanit" diye kaydetti.
        #
        # Mutlaklastirma tek satir ama butun tuketicileri ayni anda
        # duzeltir: koltuk, MCP yapilandirmasi, panel, kabuk.
        self.yol = (Path(yol) if yol else VARSAYILAN_YOL).expanduser().resolve()
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        self._kilit = threading.RLock()
        self._say_kilit = threading.Lock()
        self._bekleyen = 0
        self._derinlik = 0
        self._conn = None
        self._kur()

    def _kur(self) -> None:
        with self.baglanti() as conn:
            # WAL: panel okurken ajanlar yazabilsin. Olmazsa canli izleme,
            # calisan ajani bloklar.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(SEMA)
            self._goc(conn)
            self._veri_goc(conn)

    #: Sonradan eklenen sutunlar: (tablo, sutun, tam ALTER tanimi).
    #: `CREATE TABLE IF NOT EXISTS` var olan bir tabloyu GUNCELLEMEZ --
    #: yeni sutun semaya yazilir ama gercek veritabanina hic ulasmaz ve
    #: sorgu "no such column" ile duser. Bunu bir kez yasamamak icin goc
    #: burada, semanin yaninda duruyor: sutun ekleyen, iki satiri birden
    #: gorur.
    GOCLER = (
        ("gorev", "ek_klasorler", "TEXT NOT NULL DEFAULT '[]'"),
        ("gorev", "zorluk", "TEXT NOT NULL DEFAULT ''"),
        ("gorev", "zorluk_gerekce", "TEXT NOT NULL DEFAULT ''"),
        ("gorev", "tarayici_alani", "TEXT NOT NULL DEFAULT '[]'"),
        ("gorev", "baglayicilar", "TEXT NOT NULL DEFAULT '[]'"),
        # Tarayicida YAZMA yetkisi. Varsayilan 0 (salt okunur) ve eski
        # kayitlar da oyle acilir: bir goc, gecmise sessizce yetki
        # VERMEZ -- geriye donuk genisleyen yetki, kimsenin fark
        # etmedigi bir yetkidir.
        ("gorev", "tarayici_yazma", "INTEGER NOT NULL DEFAULT 0"),
        # Paylasilan kabin ISE yazilir (varsayilan 0: gecmise yetki
        # VERILMEZ). Olculmus bosluk (24.09): kabinle baslayan is
        # "Surdur"le devam edince ayri, oturumsuz tarayicida kosuyordu.
        ("gorev", "tarayici_kabin", "INTEGER NOT NULL DEFAULT 0"),
        # ONAYIN KAPSAMI: 'eylem' (bir kez) ya da 'is' (bu gorev
        # boyunca). Varsayilan DAR olan: genis kapsam insanin ACIK
        # tercihi olmali, bir goc onu kendiliginden vermemeli.
        #
        # Neden gerekli: kapi artik baglayici araclarini da kapsiyor
        # ve ayni eylem bir iste onlarca kez gecebilir (20 urun ->
        # 20 soru). Tek kademeli onay, kullanicinin sikayet ettigi
        # engellemeye baska bir kapidan geri donmek olurdu.
        ("onay", "kapsam", "TEXT NOT NULL DEFAULT 'eylem'"),
        # API HESABININ AYLIK DOLAR SINIRI (27.09.2026 karari). Abonelikte
        # dolar yok; API'de gercek para kesilir ve sinirsiz API hesabi
        # zincire GIRMEZ. Bos (NULL) = tanimsiz.
        ("hesap", "aylik_sinir_usd", "REAL"),
        # KESINTIDEN DEVAM (01.10.2026): isi kosturan surecin kimligi
        # (`surec.kimlik`, pid:olusma). Acilista surec olmusse is ofisce
        # birakilir ve AYNI oturumdan surer. Bos = eski kayit, bilinmiyor.
        ("gorev", "kosan_surec", "TEXT NOT NULL DEFAULT ''"),
        ("kuyruk", "kosan_surec", "TEXT NOT NULL DEFAULT ''"),
        ("kuyruk", "devam", "INTEGER NOT NULL DEFAULT 0"),
        # Is ALINIRKEN gorev tablosunun son rowid'i: bu istekle acilan
        # isler ondan buyuktur. Zaman (saniye) yetmedi: onceki istegin isi
        # ayni saniyede acildiysa yanlis istege baglaniyordu (olculdu).
        ("kuyruk", "gorev_sinir", "INTEGER NOT NULL DEFAULT 0"),
        # ISTEK (02.10.2026): isi doguran patron mesajinin kimligi. Takim
        # sohbeti isin adimlarini o mesajin altinda toplar (Claude Code
        # gibi tek konusma). Bos = eski is ya da istekten dogmayan is.
        ("gorev", "istek_id", "TEXT NOT NULL DEFAULT ''"),
        # DURAKLATILDI (02.10.2026): patronun is basina beklemesi (an).
        ("gorev", "duraklatildi", "TEXT NOT NULL DEFAULT ''"),
        # YANLIS (03.10.2026; rakipte hafiza notunda "Yanlis / Duzelt"):
        # patron bir bilgiyi ya da dersi yanlis diye kapatti -- sebebi burada.
        ("olgu", "yanlis", "TEXT NOT NULL DEFAULT ''"),
        ("ders", "kaldirildi", "TEXT NOT NULL DEFAULT ''"),
        # KABUL (02.10.2026): patron teslimi kabul etti (an).
        ("mesaj", "kabul", "TEXT NOT NULL DEFAULT ''"),
        # MOTOR SECIMI (03.10.2026, `karne`): isin ilk turunda secilen motor;
        # is boyunca ayni motorda kalir (oturum kopmasin). Bos = ajanin motoru.
        ("gorev", "motor_secimi", "TEXT NOT NULL DEFAULT ''"),
        # ORGANIZASYON (05.10.2026): cikarilan ajan SILINMEZ (ad geri donmez,
        # gecmisi okunur kalir) -- arsive gider, hicbir takimda gorunmez.
        ("ajan", "arsiv", "INTEGER NOT NULL DEFAULT 0"),
        # Ofis haritasindaki gorunusu ("sac:ten:kumas" sira numaralari; bos =
        # addan turetilir).
        ("ajan", "karakter", "TEXT NOT NULL DEFAULT ''"),
        # TAKIM KAPSAMI (06.10.2026, patron: "her takim ayri"): hafizanin
        # sahibi takim; bos = ORTAK (eski kayitlarin hepsi ortak kalir).
        ("olgu", "kanat_id", "TEXT NOT NULL DEFAULT ''"),
        ("karar", "kanat_id", "TEXT NOT NULL DEFAULT ''"),
        ("kural", "kanat_id", "TEXT NOT NULL DEFAULT ''"),
        ("belge", "kanat_id", "TEXT NOT NULL DEFAULT ''"),
        ("hafiza_onerisi", "kanat_id", "TEXT NOT NULL DEFAULT ''"),
        # TAKIM KLASORU (06.10.2026): bos = projenin koku (eski davranis).
        ("kanat", "klasor", "TEXT NOT NULL DEFAULT ''"),
        # TAKIM KOTA PAYI (06.10.2026): 0 = sinirsiz (`ofis/pay.py`).
        ("kanat", "kota_payi", "INTEGER NOT NULL DEFAULT 0"),
        # TAKIM KITI (06.10.2026): bitti tanimi (satir satir) + marka kiti (JSON).
        ("kanat", "bitti_tanimi", "TEXT NOT NULL DEFAULT ''"),
        ("kanat", "marka_kiti", "TEXT NOT NULL DEFAULT ''"),
        # DENEME / CANLI (06.10.2026): 0 = deneme kipi (canli eylem reddedilir).
        ("kanat", "canli", "INTEGER NOT NULL DEFAULT 0"),
        # KADRO SONRASI DEVAM (06.10.2026): oneriyi doguran patron mesaji AYNEN.
        ("ekip_onerisi", "patron_mesaji", "TEXT NOT NULL DEFAULT ''"),
    )

    def _veri_goc(self, conn) -> None:
        """VERI goclari -- her defterde BIR KEZ, sirayla.

        Sutun goclerinden farki: bunlar var olan kayitlarin ICERIGINI
        duzeltir, o yuzden iki kez kosmamali. Surum SQLite'in kendi
        `user_version` alaninda tutulur: ayri bir tabloda tutsaydik o
        tablo da bir goc isterdi.
        """
        surum = conn.execute("PRAGMA user_version").fetchone()[0]
        for no, islev in VERI_GOCLERI:
            if no > surum:
                islev(conn)
                conn.execute(f"PRAGMA user_version = {int(no)}")

    def _goc(self, conn) -> None:
        """Eksik sutunlari ekler. Var olan veri KORUNUR.

        Kullanicinin gercek ofisi (`veri/ofis.sqlite3`) gercek is
        gecmisi tasiyor: kararlar, kanitlar, dersler. Semayi yeniden
        kurmak onu silerdi. `ALTER TABLE ADD COLUMN` varsayilan degerle
        ekler, eski satirlar gecerli kalir.
        """
        for tablo, sutun, tanim in self.GOCLER:
            mevcut = {s["name"] for s in
                      conn.execute(f"PRAGMA table_info({tablo})")}
            if not mevcut:
                continue                      # tablo yok: SEMA zaten kuracak
            if sutun not in mevcut:
                conn.execute(
                    f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tanim}")

    #: YUK OLCUMU (E73, 28.09.2026): her cagri YENI baglanti aciyordu
    #: (~1,7 ms) ve kilit bu sure boyunca tutuluyordu. 25 ajan ayni anda
    #: kosunca kilit 12 saniyelik kosunun 9,6 saniyesinde doluydu ve
    #: duvar saati tek turun 4,6 kati cikti.
    #:
    #: Cozum: SIRADA BEKLEYEN VARKEN baglanti acik kalir ve bir sonrakine
    #: devredilir; kimse beklemiyorsa bugunku gibi KAPANIR. Neden hep acik
    #: degil: Windows acik dosyayi kilitler -- sinamalarin gecici klasoru,
    #: yedegin geri yuklemesi, kullanicinin dosyayi tasimasi takilirdi.
    #: Tek basina calisan yol (panel, kabuk, sinama) eskisiyle AYNI kalir.
    #: Kilit ve siralama degismez; yalniz acma bedeli kalabalikta odenmez.
    def _baglan(self):
        conn = sqlite3.connect(str(self.yol), timeout=30.0, check_same_thread=False,
                               factory=MaskeliBaglanti)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def baglanti(self):
        with self._say_kilit:
            self._bekleyen += 1
        try:
            self._kilit.acquire()
        finally:
            with self._say_kilit:
                self._bekleyen -= 1
        try:
            dis = self._derinlik == 0
            if dis and self._conn is None:
                self._conn = self._baglan()
            conn = self._conn
            self._derinlik += 1
            try:
                yield conn
                if dis:
                    conn.commit()
            except Exception:
                if dis:
                    conn.rollback()
                raise
            finally:
                self._derinlik -= 1
                if dis:
                    with self._say_kilit:
                        bekleyen = self._bekleyen
                    if not bekleyen:
                        self._conn = None
                        conn.close()
        finally:
            self._kilit.release()

    def ayar_oku(self, proje_id: str, anahtar: str, varsayilan: str = "") -> str:
        with self.baglanti() as conn:
            row = conn.execute(
                "SELECT deger FROM ayar WHERE proje_id = ? AND anahtar = ?",
                (proje_id, anahtar)).fetchone()
        return row["deger"] if row else varsayilan

    def ayar_yaz(self, proje_id: str, anahtar: str, deger: str) -> None:
        with self.baglanti() as conn:
            conn.execute(
                "INSERT INTO ayar (proje_id, anahtar, deger, guncellendi) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(proje_id, anahtar) "
                "DO UPDATE SET deger = excluded.deger, "
                "guncellendi = excluded.guncellendi",
                (proje_id, anahtar, str(deger), simdi()))

    def olay_yaz(self, proje_id: str, tur: str, govde: str = "",
                 ajan_ad: str = "", gorev_id: str = None) -> None:
        with self.baglanti() as conn:
            conn.execute(
                "INSERT INTO olay (proje_id, ajan_ad, gorev_id, tur, govde, olusturuldu) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (proje_id, ajan_ad, gorev_id, tur, govde, simdi()),
            )
