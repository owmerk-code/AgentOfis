---
name: flow-video
description: Google Flow (Veo / Omni) ile gomulu tarayicida, patronun hesabiyla PROFESYONEL VIDEO KLIBI uretmek -- olculmus katalogdan model secimi, kilitli istem tarifi, taslak kareden video, indirme, klip denetimi, kurgu ve teslim. Reklam, Reels, hikaye, urun tanitimi, UGC.
---

# Google Flow ile profesyonel video

Once `reklam-kreatifi` ile SENARYO PAKETI hazirlanir ve patrona gider. Bu
beceri paketteki sahneleri Flow'da uretip paylasmaya hazir videoya cevirir.

## On kosul
- Yalniz GOMULU TARAYICI (kabin); patronun kisisel Chrome'u yok. Flow'a
  patron girmis olmali; giris ekrani gorursen `giris_iste`. Sifre yazma.
- Paylasilan kabinde yeni sekme ACMA; ayni sekmede calis.
- Model, secenek ve kredi: brifingindeki FLOW KATALOGU (patronun ekranindan
  olculur, gunluk tazelenir). Ekranda farkli gorursen EKRAN dogrudur;
  farki kanita yaz.

## 1. Kredi kurali (kapida yapiyla durur)
Kredili her uretim tiklamasi (Olusturmaya basla, Enter ile gonderme,
1080p/4K buyutme) ofisin kapisinda DURUR ve patrona sorulur. Bu yuzden:
paketi (sahneler, model, toplam kredi, taslak kareler) ONCE `sohbete_yaz`
ile gonder, sonra uret. Patron "Bu is boyunca" onaylarsa ayni isteki
uretimler bir daha sorulmaz. Resim uretimi (katalogda 0 kredi) sorulmaz.

## 2. Model secimi (sonuca gore; katalogdaki fiyatlarla)
- **Konusan insan, Turkce replik + dudak senkronu, 10 sn tek cekim (UGC):**
  Omni 1.1 Flash, 720p, 10 sn. Patronun kendi UGC videolari bu ayarda.
- **Urun yakin plani, etiket okunurlugu, sinematik isik:** Veo 3.1 -
  Quality en guclu adaydir; Veo 3.1 - Fast daha ucuz. Aralarindaki kalite
  farki henuz OLCULMEDI: pakette ikisini kredisiyle yaz, patron secsin.
- **360p** yalniz hareket/kompozisyon denemesi icin; teslim 720p ve ustu.
- Veo'da sure secenegi YOK (ekranda olculdu); sureyi kurgu belirler.
- Adet x1; x2+ yalniz bilerek varyasyon istendiginde (kredi katlanir).
- Katalogda yeni model gorursen (Flow degisti) dene ve patrona oner.

## 3. Taslak kareden video (tutarlilik icin varsayilan yol)
- Ayar penceresi ("Ayarlar tetikleyicisi"): Video, tur **Kareler**, oran,
  model, cozunurluk/sure, adet.
- Istem cubugunda **"Başlat"** = ilk kare: "Çerçeve resmi seçin" penceresi
  -> Resimler / Yüklemeler -> onaylanan taslak kare -> **"İsteme ekle"**.
  **"Bitir"** = son kare (istege bagli; urunun son durusunu sabitler).
- Urun fotografini yuklemek: **"Medya menüsü ekle" -> "Yükle"**
  (`browser_file_upload`).
- Tur **İçerik öğeleri**: urunu/kisiyi referans oge olarak verip sahneyi
  modele kurdurursun (ilk kare yerine).
- Ayni kisi birden cok sahnede: "Medya menüsü ekle" -> **"Karakter oluştur"**.
- Flow'un kendi **"Ajan"** kipi ve **"Yeni sahne"** (sahne birlestirme /
  uzatma) var -- OLCULMEDI; ise yarayacaksa dene, kredili adim yine kapida.

## 4. Istem tarifi (patronun kendi Flow istemlerinden, 07.10)
INGILIZCE, tek paragraf, bu sirayla. Ekranda/agizda Turkce soz varsa
tirnak icinde AYNEN.
1. **Cekim basligi:** "Single continuous N-second cinematic shot, vertical
   9:16, no cuts."
2. **Ozne + ortam.**
3. **URUN KIMLIK KILIDI** (kimlik kartindan): boyut, bicim, malzeme,
   kapak/govde/ICERIK rengi, etiketteki yazilar tirnakta ve yerleriyle.
4. **OLCEK KILIDI:** "realistic small scale, no taller than the length of
   her hand, held with fingertips, correct natural proportions between hand
   and product" (urune gore uyarla).
5. **DURUM KILIDI:** sahne boyunca degismeyecek durum: "the cap is already
   removed and stays off the whole shot -- never show the cap changing".
6. **Eylem sirasi:** en cok 3 adim, sirali ("raises it ..., turns it ...,
   then smiles to camera").
7. **Kamera:** "smooth slow push-in, shallow depth of field" vb.
8. **Isik + renk paleti.**
9. **Ses:** konusma varsa `She says in Turkish: "..."` + "accurate lip-sync,
   clear mouth movement"; yoksa "soft ambient music, no dialogue" ya da
   ortam sesi.
10. **Kuyruk:** "The product label stays sharp, correct and readable;
    consistent stable face and identity; no morphing, no warping.
    Photorealistic high-resolution premium commercial."

Ornek (genel): "Single continuous 8-second cinematic shot, vertical 9:16, no
cuts. A slim 30ml frosted-glass serum bottle with a matte white dropper cap
and a minimal beige label reading "AURA" in black above and "VITAMIN C" below
stands on a wet marble surface in soft morning light. Realistic small scale,
about the height of a palm. The dropper cap stays on the whole shot. A single
drop of clear golden serum slides down the glass, then the camera slowly
pushes in to the label. Soft warm window light, cream and gold palette,
shallow depth of field. Gentle ambient piano, no dialogue. The product label
stays sharp, correct and readable; no morphing, no warping. Photorealistic
high-resolution premium skincare commercial."

Sonuc kotu gelirse hangi kilit tutmadiysa onu GUCLENDIR (patronun
istemlerinde olcek kilidi, sise buyuk cikinca sonradan eklenmis).

## 5. Uret, bekle, indir
- "Oluşturmaya başla"ya bir kez bas; uretim dakikalar surer, araliklarla
  `browser_snapshot` al. Bitmeden yeniden basma (cift kredi).
- Indir: "Medyayı indir" -> **"720p Orijinal boyut"** (kredisiz). 1080p / 4K
  "Yükseltilmiş" buyutmedir: bedeli olculmedi, kapida sorulur -- teslim
  kalitesi icin patron onaylarsa kullan.
- Indirilenler kendiliginden isin `.ofis/indirilenler/` klasorune duser.

## 6. Klip denetimi (her klip, kurgudan once)
- `video_denetle`: sure, oran, ses, siyah kare.
- Kare ozetini AC ve urun fotografiyla karsilastir: etiket yazisi harfi
  harfine, renkler (sivi rengi!), bicim, olcek, el/yuz bozulmasi, kapak
  durumu.
- Kusurlu klip: kusuru ve duzeltilmis istemi yaz. Paketteki yeniden cekim
  payi icindeyse yeniden uret; degilse patrona sor.

## 7. Kurgu (paylasmaya hazir)
`video_kurgula` ile PLAN yaz (sahne sirasi, kirpma, ekran yazisi, altyazi,
gecis, muzik ya da Flow sesi, kapanis karti + CTA). Bicim: 9:16 / 4:5 / 1:1 /
16:9; reklamsa uc bicim. Cizim kredi harcamaz: kare ozetine bak, yazi
okunmuyorsa ya da sahne yanlissa plani duzeltip yeniden ciz.

## 8. Teslim
- `sohbete_yaz(ekler=[video(lar), kapak])`: kullanilan modeller ve
  HARCANAN kredi (bakiye once/sonra), paylasim aciklamasi + etiketler.
- `kanit_ekle`: her klibin tam istemi, ayarlari, kredisi; denetim sonucu.

## Olculmus tuzaklar
- Ayni adli ("Diğer seçenekler") iki dugme var; biri projenin SIL menusunu
  acar. Proje menulerine, cop kutusuna, paylasima, plan/odeme ekranina girme.
- Hesap paneli Escape ile kapanmaz: bos perdeye tikla.
- Flow son ayari projede hatirlar: uretime baslamadan ayar penceresinde
  kip/tur/model/oran/adedi KONTROL ET.
- Patronun eski projelerindeki medyayi silme/duzenleme.
