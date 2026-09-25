# semuparfum.com — İlk Kez Gelen Müşteri Gözüyle Analiz

**Yöntem notu:** Analiz iki aşamada yapılmıştır: (1) Sayfa içeriklerinin okunması için WebFetch kullanılmıştır. (2) Sepete ekleme, ödeme sayfasına ilerleme, mobil görünüm ve sayfa yükleme süresi için gerçek bir Chromium tarayıcısı (Playwright ile otomatikleştirilmiş) kullanılarak siteye fiilen tıklanmış, form alanları görüntülenmiş (doldurulmamış). Ekran görüntüsü alma denenmiş ancak dosyalar diske yazılamamıştır; bu nedenle görsel/düzen gözlemleri yalnızca metin ve DOM düzeyinde yapılmıştır, görsel yerleşim (kırılma, taşma vb.) gözlemlenmemiştir. Gerçek kişisel bilgi girilmemiş, sipariş tamamlanmamış, ödeme başlatılmamıştır.

---

## 1) Ana Sayfa ve İlk İzlenim
- Ne satıldığı ilk ekranda nettir: marka **SEMU EXTRAIT DE PARFUM**, slogan "İKİ KOKU. İKİ KARAKTER" / "Kendine yakın bir iz bırak", iki ürün: Belle (kadın) ve Brave (erkek), "%30 Extrait de Parfum, 50 ml" vurgusu. — https://semuparfum.com
- Menüde: Ana sayfa, Belle Kadın, Brave Erkek, Hakkımızda, Deneme ve İade, Kargo takip/Hesabım, İletişim, Sepet linkleri var. — https://semuparfum.com
- **Arama kutusu yok.** Yalnızca 2 ürün olduğu için işlevsel eksiklik büyük değil ama fark edilir bir yokluk. — https://semuparfum.com
- Ana sayfada müşteri yorumu/testimonial **yok**. — https://semuparfum.com

## 2) Güven İşaretleri
- **İletişim:** Telefon (0501 611 36 67), e-posta (iletisim@semuparfum.com), WhatsApp linki ve ad/e-posta/sipariş no/konu alanlı iletişim formu mevcut. — https://semuparfum.com/pages/contact
- **Fiziksel adres/şirket bilgisi:** Satıcı "Yener Kozmetik", açık adres "Çobançeşme Mah. Halitpaşa Sk. No: 2, Bahçelievler / İstanbul" olarak üç kez geçiyor; ayrıca Esnaf ve Sanatkarlar Sicil No 999547, Yenibosna Vergi Dairesi'ne bağlı, Vergi No 9480257942 bilgileri paylaşılmış. — https://semuparfum.com/pages/hakkimizda
- **İade/değişim politikası:** Yasal 14 gün cayma hakkı 30 güne uzatılmış; şart "ana ürünün koruyucu jelatininin açılmamış olması"; testerler açılabilir, iade hakkını etkilemez; iade kargo bedeli satıcıya ait. — https://semuparfum.com/pages/deneme-ve-i%CC%87ade ve https://semuparfum.com/policies/refund-policy
- **Kargo politikası:** Kargo tamamen ücretsiz ve sigortalı, tutar sınırı yok; sipariş onaydan sonra 1-3 iş günü içinde hazırlanıyor, yasal azami teslim süresi 30 gün. Kargo firması adı verilmemiş, yalnızca "anlaşmalı kargo şirketi" deniyor. — https://semuparfum.com/policies/shipping-policy
- **Ödeme seçenekleri:** iyzico, Visa, Mastercard logoları ve kapıda ödeme (49₺ ek ücretli, nakit/kart) seçeneği ana sayfada görünüyor. — https://semuparfum.com
- **Müşteri yorumları:** Ne ana sayfada ne de ürün sayfalarında yıldız puanı veya yorum bölümü bulunmuyor — **görülemedi/mevcut değil**. — https://semuparfum.com, https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
- **Sertifikalar:** IFRA, T.C. Sağlık Bakanlığı onayı, ÜTS ve ETBİS kayıtlarına atıf yapılıyor. — https://semuparfum.com/pages/hakkimizda

## 3) Ürün Sayfaları
**Ürün 1 — Signature Belle for Women:** Fiyat 1.490,00 TL (indirimsiz tek fiyat gösterimi, referans/eski fiyat yok), 50 ml, üst nota Çilek·Böğürtlen, orta nota Yasemin, alt nota Vanilya·Amber·Sandal Ağacı. Yalnızca **1 ürün görseli** var, açıklama metni anlaşılır. "SEPETE EKLE" butonu mevcut, stok durumu sayfada belirtilmiyor. — https://semuparfum.com/products/belle

**Ürün 2 — Signature Brave for Men:** Fiyat 1.490,00 TL (indirimsiz), 50 ml, üst notalar Armut/Siyah Lavanta/Nane/Bergamot/Limon, kalp notaları Tarçın/Kimyon/Adaçayı, dip notalar Siyah Vanilya/Amber/Paçuli/Sedir. Yine **1 ürün görseli**, açıklama net. Sepete ekle butonu mevcut, stok belirtilmemiş. — https://semuparfum.com/products/brave

- Her iki üründe de **fiyat ve indirim gösterimi sade** (indirim/eski fiyat karşılaştırması yok), koku notaları ve ml bilgisi net biçimde yazılmış, ancak **görsel sayısı yalnızca 1** — kutu, doku, şişe detayı, kullanım anı gibi ek görseller yok. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave

## 4) Sepet ve Ödeme
- Boş sepet sayfası (ürün eklenmeden önce): "Henüz bir koku seçmedin" mesajı, "KOKULARI KEŞFET" butonu, "Ücretsiz sigortalı kargo" vurgusu ve tester bilgisi görünüyor. Zorunlu üyelik uyarısı **yok**. — https://semuparfum.com/cart
- Gerçek tarayıcıyla "Signature Belle for Women" ürünü sepete eklendi: "SEPETE EKLE" butonuna tıklandığında sayfa otomatik olarak sepete yönlendirdi. Sepette ürün adı, birim fiyat (1.490,00 TL), adet ve toplam (1.490,00 TL) net gösteriliyor; "Vergi ve teslimat koşulları ödeme adımında gösterilir" notu var; "ÖDEMEYE GEÇ" butonu mevcut. Zorunlu üyelik/hesap oluşturma uyarısı **yok**. — https://semuparfum.com/cart
- "ÖDEMEYE GEÇ" butonuna tıklandığında gerçek Shopify ödeme sayfasına (checkout) geçildi: https://semuparfum.com/checkouts/cn/hWNHBZ0KIWBr40ermXSwIilX/tr-tr. Bu sayfada: E-posta alanı var ama "Giriş yap" isteğe bağlı — hesap açmadan/üye olmadan e-posta ile misafir olarak devam edilebiliyor, **zorunlu üyelik yok**. Teslimat formunda Ülke, Ad, Soyadı, Adres, Şehir, Telefon alanları isteniyor (doldurulmadı). Kargo yöntemi bölümünde "Sigortalı Kargo — ÜCRETSİZ" **daha ödeme adımında, sepetten sonra ilk ekranda** açıkça gösteriliyor; gizli/sürpriz bir kargo ücreti yok. Ödeme bölümünde "Kapıda Ödeme: Sipariş tutarını teslimat sırasında ödeyebilirsiniz" seçeneği bulunuyor. Maliyet özeti: Alt toplam 1.490,00 TL, Kargo ÜCRETSİZ, Toplam 1.490,00 TL, "248,33 TL vergi dahil" notu ile şeffaf gösteriliyor. Bu noktanın ötesinde (gerçek ad/adres/telefon girme, "Siparişi tamamla" butonuna basma) görev kuralları gereği denenmedi; **bu adımın ötesi görülemedi**. — https://semuparfum.com/checkouts/cn/hWNHBZ0KIWBr40ermXSwIilX/tr-tr

## 5) Mobil Görünüm ve Hız
- Gerçek tarayıcı iPhone 13 mobil emülasyonuyla kontrol edildi: ana sayfa (https://semuparfum.com), ürün sayfası (https://semuparfum.com/products/belle) ve sepet sayfası (https://semuparfum.com/cart) mobil görünümde hatasız açıldı, sayfa navigasyonu ve içerik yüklemesi (DOM/metin düzeyinde) hatasızdı. Ekran görüntüsü diske yazılamadığı için görsel yerleşim (yatay taşma, kırılma, buton/menü çakışması vb.) **görülemedi**.
- Hız izlenimi (ölçüm değil, tek seferlik gözlem): Ürün sayfası (https://semuparfum.com/products/belle) masaüstü yüklemesi ~2,9 saniyede tamamlandı; ana sayfanın mobil emülasyonda yüklenmesi ~1,2 saniye sürdü. Bu rakamlar tek bir denemeye dayanır, laboratuvar/ağ koşullarına bağlıdır, performans ölçümü olarak değil yalnızca izlenim olarak değerlendirilmelidir. — https://semuparfum.com/products/belle, https://semuparfum.com

## 6) Türkçe Metin Kalitesi
- Ana sayfa, iletişim, hakkımızda, iade ve kargo politikası sayfaları tek tek okundu; belirgin bir yazım hatası veya çeviri kokan ifade bulunamadı. Deneme/iade sayfasındaki "testerlar ana ürün kutusunun dışındadır; jelatini açmadan kokuyu denemeniz, cayma hakkınızı kaybetmeden karar verebilmeniz içindir" cümlesi ile "Alıcı: Sipariş formunda ad, soyad, teslimat adresi, telefon ve e-posta bilgilerini beyan eden kişidir" tanımı ilk bakışta bozuk göründü, ancak sayfadan harfi harfine tekrar alıntılandığında ikisi de dil bilgisi açısından doğru ve standart bir sözleşme/yasal tanım cümlesi olduğu görüldü; gerçek bir hata değil. — https://semuparfum.com/pages/deneme-ve-i%CC%87ade
- İletişim, kargo ve hakkımızda sayfalarında da belirgin yazım/çeviri hatası görülmedi. — https://semuparfum.com/pages/contact, https://semuparfum.com/policies/shipping-policy, https://semuparfum.com/pages/hakkimizda

---

## Güçlü Yönler
1. Marka teklifi net: iki ürün, net konumlandırma, net fiyat, net ml. — https://semuparfum.com
2. İade politikası cömert (30 gün, iade kargosu ücretsiz) ve açıkça yazılı. — https://semuparfum.com/pages/deneme-ve-i%CC%87ade
3. Şirket kimliği (unvan, vergi no, sicil no) hakkımızda sayfasında şeffaf paylaşılmış. — https://semuparfum.com/pages/hakkimizda
4. Çoklu iletişim kanalı: telefon, WhatsApp, e-posta, form. — https://semuparfum.com/pages/contact
5. Ücretsiz ve sigortalı kargo, kapıda ödeme dahil çeşitli ödeme seçenekleri sunuluyor. — https://semuparfum.com
6. Sepetten ödeme sayfasına geçişte zorunlu üyelik yok (e-posta ile misafir olarak devam edilebiliyor), kargo ücreti "ÜCRETSİZ" olarak daha ödeme ekranının ilk adımında net gösteriliyor, toplam tutar sepetten (1.490,00 TL) ödeme özetine kadar değişmiyor — gizli/sürpriz masraf gözlenmedi. — https://semuparfum.com/checkouts/cn/hWNHBZ0KIWBr40ermXSwIilX/tr-tr

## Zayıf Yönler
1. Ürün sayfalarında yalnızca **1 görsel** var; alışveriş kararını güçlendirecek ek açı/detay görseli yok. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
2. **Hiçbir müşteri yorumu/yıldız puanı yok** — sosyal kanıt eksik. — https://semuparfum.com, https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
3. **Arama kutusu yok** (şu an kritik değil ama ürün sayısı artınca sorun olur). — https://semuparfum.com
4. Kargo firmasının adı belirtilmemiş, yalnızca "anlaşmalı kargo şirketi" deniyor — belirsizlik güveni azaltabilir. — https://semuparfum.com/policies/shipping-policy
5. Fiyatlarda indirim/eski fiyat gösterimi yok; kampanya/fiyat karşılaştırması algısı oluşturulamıyor. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
6. Stok durumu ürün sayfalarında belirtilmiyor; müşteri aciliyet/kıtlık hissi ya da güvence göremiyor. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave

## Öneriler (öncelik sırasına göre, en fazla 10)
1. Ürün sayfalarına en az 4-5 görsel ekle (kutu, şişe yakın çekim, doku/uygulama anı, ölçek karşılaştırması); mevcut durumda sayfa başına yalnızca 1 görsel var. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
2. Müşteri yorumu/yıldız puanı modülü ekle; sosyal kanıt hiç yok ve bu iki ürünlü, yüksek fiyatlı (1.490 TL) bir markada güveni doğrudan etkiler. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
3. Kargo firmasının adını (ör. Yurtiçi, Aras, MNG vb.) kargo politikası sayfasında ve/veya sipariş takip sayfasında açıkça belirt. — https://semuparfum.com/policies/shipping-policy
4. Ürün sayfalarına stok durumu bilgisi (ör. "Stokta" / "Son X adet") ekle. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
5. Ana sayfaya bir arama kutusu eklemeyi değerlendir; ürün sayısı artarsa navigasyon kolaylaşır. — https://semuparfum.com
6. Fiyat gösterimine gerekirse referans/eski fiyat veya paket indirimi (2'li set gibi) eklemek dönüşüm artırıcı bir seçenek olabilir. — https://semuparfum.com/products/belle, https://semuparfum.com/products/brave
7. WhatsApp linki ana sayfanın kaynağında (wa.me bağlantısı) mevcut; bunun sayfada görsel olarak ne kadar öne çıktığı **görülemedi** (ekran görüntüsü alınamadı) — görsel yerleşim netleştirilip gerekiyorsa canlı destek varlığı daha görünür kılınabilir. — https://semuparfum.com
