---
name: flow-gorsel
description: Google Flow'da (Nano Banana; olculmus katalogda 0 kredi) gomulu tarayicida PROFESYONEL GORSEL uretmek -- urun gorseli, reklam/gonderi/hikaye gorseli, karakter ya da urun tutarli gorsel seti ve videolar icin TASLAK KARE. Urun fotografini referans alir, varyasyon uretir, secer, boyutlar ve teslim eder.
---

# Google Flow ile profesyonel gorsel

## Ne zaman
- Urun gorseli, kampanya/reklam gorseli, Instagram gonderi/hikaye gorseli.
- Videonun sahne kareleri (senaryo paketi, `reklam-kreatifi` 6. adim):
  bu kareler videoda BASLANGIC KARESI olur.
- Ayni urun/kisiyle birden cok TUTARLI gorsel.
Hizli ve urunsuz genel bir gorsel icin ofisin `gorsel_uret` araci da var;
urune sadik, markali is icin bu beceri.

## Model ve bedel
Brifingindeki FLOW KATALOGU: Resim kipinde Nano Banana Pro / 2.1 / 2 Lite,
olculmus bedel 0 kredi (kapi sormaz). Varsayilan **Nano Banana Pro** (en
guclu aday; aralarindaki fark olculmedi -- sonuc kotuyse digerini dene).
Oranlar: 16:9, 4:3, 1:1, 3:4, 9:16. Adet x1-x4: varyasyon icin x4 kullan.

## 1. Referans (urun gorunuyorsa ZORUNLU)
- Urun fotografini yukle: istem cubugunda **"Medya menüsü ekle" -> "Yükle"**
  (`browser_file_upload`); yuklenen ogeyi isteme ekle ("İsteme ekle").
  Resim kipindeki ekleme dugmesinin adi OLCULMEDI: `browser_snapshot` ile
  bul, okuyarak tikla.
- Ayni kisi birden cok gorselde: "Medya menüsü ekle" -> "Karakter oluştur".
- Urun fotografinin arka plani kalabaliksa once temizle:
  `medya_isle(islem="arka_plan", dosya=<foto>)` -> saydam PNG (daha temiz
  referans; urunu yeni bir sahneye koymak icin de).

## 2. Istem tarifi (Ingilizce, tek paragraf)
1. Gorselin turu ve orani ("Premium product photograph, vertical 9:16").
2. Urun KIMLIK KILIDI: boyut/olcek, bicim, malzeme, renkler (icerik dahil),
   etiket yazilari tirnakta ve yerleriyle -- `reklam-kreatifi` kimlik kartindan.
3. Sahne: zemin, arka plan, aksesuar (urunu golgelemeyen).
4. Kompozisyon: urunun yeri; ekran yazisi gelecekse BOS ALAN birak
   ("leave clean negative space in the upper third for text").
5. Isik ve renk paleti, objektif hissi ("85mm, shallow depth of field").
6. Stil: "photorealistic commercial photography" (ya da istenen stil).
7. Kuyruk: "The label stays sharp, correct and readable; exact product shape
   and colors; no extra text, no watermark, no distortion."
Gorsele YAZI gerekiyorsa: kisa metni tirnakta Nano Banana Pro'ya yazdir ve
harfi harfine kontrol et; tutmazsa yaziyi sonradan ekle (asagida).

## 3. Uret, sec, indir
- Resim kipi, oran, model, x4 -> "Oluşturmaya başla" (0 kredi; kapi sormaz.
  Ayar penceresinde VIDEO secili kalmissa kapi kredi diye sorar -- once
  kipi kontrol et).
- Dort varyasyonu urun fotografiyla karsilastir: etiket yazisi, renk, bicim,
  olcek, el/yuz. En iyi 1-2'yi sec; seciminin gerekcesini yaz.
- Indir ("Medyayı indir"); dosyalar isin `.ofis/indirilenler/` klasorune
  duser. Teslim edilecekleri `.ofis/ekler/`e anlamli adla koy.

## 4. Boyutlar ve son dokunus (ffmpeg PATH'te)
- Buyutme (kaynak hedeften kucukse): `medya_isle(islem="gorsel_buyut",
  dosya=<gorsel>, en=1080)` -- yerel yapay zeka (Real-ESRGAN), ~1 dk, kredi yok.
- Instagram gonderi 4:5 (1080x1350): 3:4 uret, kirp:
  `ffmpeg -i girdi.png -vf "crop=iw:iw*5/4,scale=1080:1350" cikti.png`
- Hikaye/Reels kapagi 9:16 (1080x1920), kare 1:1 (1080x1080).
- Sonradan yazi: `ffmpeg -i girdi.png -vf "drawtext=fontfile='C\:/Windows/Fonts/segoeuib.ttf':text='YENI SEZON':fontsize=96:fontcolor=white:x=(w-tw)/2:y=h*0.12" cikti.png`
  (Turkce harfler calisir -- olculdu. Satira SIGMAZSA tasar, kendisi
  bolmez: `fontsize`i kucult ya da iki drawtext ile iki satir yap; sonucu
  AC ve bak. Yaziyi bos alana koy, kontrasti kontrol et).
- Reklam kreatifi istendiyse ayni gorseli UC bicimde ver (9:16, 4:5, 1:1).

## 5. Teslim
`sohbete_yaz(ekler=[...])` (en cok 5 dosya): hangi model, kac varyasyondan
secildigi, paylasim aciklamasi + etiketler. `kanit_ekle`: tam istem,
ayarlar, referans dosya.

## Olculmus tuzaklar
- Flow son ayari hatirlar: uretmeden once kip RESIM mi, model ve oran dogru mu bak.
- "Diğer seçenekler" adli iki dugmeden biri projenin SIL menusunu acar; proje
  menulerine, cop kutusuna, paylasima, plan/odeme ekranina girme.
- Hesap paneli Escape ile kapanmaz: bos perdeye tikla.
