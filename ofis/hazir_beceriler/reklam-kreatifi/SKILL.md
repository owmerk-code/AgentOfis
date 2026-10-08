---
name: reklam-kreatifi
description: Herhangi bir istekten (kisa sohbet, hazir istem ya da ayrintili brif/senaryo) profesyonel Reels, hikaye, gonderi ya da reklam KREATIFI kurmak -- urun kimlik karti, brif, fikir, kanca, sahne listesi, taslak kareler ve patrona giden SENARYO PAKETI. Video ya da gorsel uretiminden ONCE kullanilir; her urun ve her marka icin genel.
---

# Reklam kreatifi: istekten senaryo paketine

Amac: patronun hangi bicimde istedigi fark etmeden (tek cumle, hazir istem,
sayfalarca brif) PAYLASMAYA HAZIR, profesyonel bir isin planini cikarmak.
Uretim (kredi) bu planin patron tarafindan gorulmesinden SONRA baslar.

## 1. Istegi oku -- uc bicim
- **Kisa sohbet** ("Belle icin reels yap"): eksikleri profesyonel varsayimla
  doldur (amac, sure, bicim, ton). Varsayimlarini pakette ACIKCA yaz; patron
  duzeltir.
- **Hazir istem** (patron Flow istemini kendisi yazdi): istemine SADIK kal,
  yalniz teknik kilitleri (asagida 4. madde) ekle ve neyi ekledigini soyle.
- **Ayrintili brif / senaryo**: sahne sahne uy; sapma gerekiyorsa (teknik
  sinir: Flow klibi 4-10 sn, Veo'da sure secimi yok) nedenini yazip oner.

## 2. Urun kimlik karti (urun gorunen her iste ZORUNLU)
Kaynaklar sirasiyla: patronun eki -> urunun sayfasi (site, gomulu tarayici)
-> magaza baglayicisi -> hafiza/belgeler (`belge_ara`). Kart:
- Ad, tur, BOYUT ve gercek olcek (ml, cm; elde nasil durur)
- Bicim (dikdortgen sise, silindir kutu...), malzeme (cam, mat plastik...)
- Renkler: govde, kapak, ICERIK (sivi rengi -- 06.10 denemesinde kaydi)
- Etiket/logoda yazan HER kelime, yeri ve rengi (tirnak icinde, harfi harfine)
- Degismez ayrintilar (kapak acik mi kapali mi, kutu var mi)
- Urun fotograflari: `.ofis/` altina indir/kopyala, yollarini yaz (arka plan
  kalabaliksa `medya_isle` arka_plan ile temiz bir kopya cikar)
Fotograf bulamazsan once ara; yine yoksa `soru_sor` ile patrondan iste.

## 3. Brif (paketin ilk bolumu, kisa)
- Amac: satis / tanitim / bilinirlik / kampanya
- Bicim: Reels-hikaye 9:16 (1080x1920), gonderi 4:5 (1080x1350) ya da 1:1,
  yatay 16:9. Reklam kreatifi istendiyse UC bicim (9:16, 4:5, 1:1).
- Sure: Reels 7-15 sn (tek mesaj) / 15-30 sn (hikaye anlatimi)
- Hedef kitle, his ve ton (luks, samimi, enerjik, sakin...)
- TEK ana mesaj + fayda/kanit + CTA (site, DM, link)
- KANCA: ilk 1-2 saniyede durduran sey (hareket, yakin plan, merak, soru)
- Ses: Flow'un kendi sesi / muzik; seslendirme yalniz patron isterse
- Ekran yazisi Turkce, sahne basina en cok 6-7 kelime

## 4. Fikir
Iki-uc farkli yon (or. "sinematik luks", "UGC samimi", "hizli kesmeli
enerjik"), birer cumle. Birini oner ve nedenini yaz. Patron yon verdiyse uy.

## 5. Sahne listesi
Her sahne TEK cekim (Flow tek klip uretir; hareket sahnenin icinde). Tablo:

| # | sure | ne gorunuyor (eylem) | kamera | isik/renk | ses | ekran yazisi | model + ayar | kredi |

- 1. sahne kanca; son sahne urun + CTA. Kapanis karti ve ekran yazilari
  `video_kurgula` ile cizilir (KREDI HARCAMAZ) -- onlari Flow'a yaptirma.
- Model ve kredi brifingindeki OLCULMUS Flow katalogundan (ezberden degil).
  Kalitesi kritik sahnede iki secenek yaz (or. "Veo 3.1 - Quality 100 /
  Veo 3.1 - Fast 20"); patron secer.
- Yeniden cekim payi: toplamin ~%30'u kadar kredi (gerekmezse harcanmaz).

## 6. Taslak kareler (0 kredi)
Her sahnenin ilk karesini `gorsel_uret` ile uret (`gorsel` becerisi; urun
fotografi `referanslar`, sahnenin `oran`i; olculdu: urun ve kutu birebir).
Flow'da gorsel URETILMEZ (kapida reddedilir). Bu kareler hem patrona onizlemedir hem de videoda BASLANGIC KARESI
olur -- urun ve kompozisyon boylece korunur.

## 7. Senaryo paketi -> patron
`sohbete_yaz` ile: kisa brif, fikir, sahne listesi (model + kredi), TOPLAM
kredi (+ yeniden cekim payi), kredi bakiyesi, varsayimlar; `ekler`de taslak
kareler (en cok 5; fazlasi tek bir kontak gorselinde). Ardindan
`onay_iste(..., kredi=<TOPLAM>, uretim=<kredili tiklama sayisi>)` ile TEK
onay iste ve turu bitir: onaylanan paket o kadar uretimi kapida bir daha
sordurmaz (cift onay yok). Patron duzeltme isterse paketi guncelle (kredi
harcamaz) ve yeniden gonder.

## 8. Paylasim metni (teslimle birlikte)
URUN BILGISI UYDURULMAZ (08.10.2026 olculdu: arka etikette olmayan koku notalari ve var olmayan bir site adresi yazildi). Yalniz KAYNAGI olani yaz: patronun sozu, urunun etiketi/kutusu, verilen site ya da magaza kaydi. Koku notasi, kalicilik, fiyat, indirim, site/adres bilinmiyorsa YAZMA ya da [SITE] gibi yer tutucu birak ve teslimde patrona sor.

Aciklama (2-3 cumle, ilk satir kanca, sonda CTA), 5-10 ilgili etiket, kapak
karesi. Patron baska dil istemedikce Turkce. Konusmali videoda altyazi
(`medya_isle` altyazi, replikle) -- Reels cogu zaman sessiz izlenir.

## Profesyonel olcut (teslimden once kendine sor)
- Ilk 2 saniye kaydirmayi durduruyor mu?
- Urun her karede KIMLIK KARTINA uyuyor mu (yazi, renk, bicim, olcek)?
- Ekran yazisi urunun/etiketin ustune biniyor mu, okunuyor mu (kontrast)?
  Kapanis temiz bir kart mi (urun griye bogulmadan)?
- Tek mesaj net mi, CTA var mi; yazilar guvenli alanda ve okunuyor mu?
- Ses/muzik var mi, sessiz ya da siyah bosluk yok mu (`video_denetle`)?
- Istenen bicim(ler)in hepsi teslim edildi mi?
