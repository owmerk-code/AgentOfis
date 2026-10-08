---
name: gorsel
description: PROFESYONEL GORSEL uretmek -- urun gorseli, Instagram/Meta gonderi-hikaye-reklam gorseli, kampanya gorseli, videonun BASLANGIC KARESI, tutarli gorsel seti. Ofisin `gorsel_uret` araciyla (GPT; urun fotografi `referanslar`, `oran`). Flow'da gorsel URETILMEZ (Flow yalniz video). Yazi/CTA, boyutlar, olcum ve teslim.
---

# Profesyonel gorsel (GPT, urun fotografiyla)

## Kural (patron, 08.10.2026)
- GORSEL: `gorsel_uret` (GPT; abonelik, kredi yok). Flow'da gorsel URETILMEZ --
  ofis Flow'daki resim uretimini REDDEDER. Flow yalniz VIDEO icin.
- Gercek URUN gorunuyorsa urunun fotograflari `referanslar`a verilir; urun,
  etiket, kutu ve butun yazilar fotograftaki gibi kalir. Fotografta OLMAYAN
  parca (kutu, kapak, ambalaj) gorsele GIRMEZ: ya birebir ya hic.

## 1. Referanslari hazirla
- Her parca (sise, kutu ...) icin ayri, NET ve DIK fotograf sec. Yan yatik
  cekilmisse once dondur (`ffmpeg -i k.png -vf "transpose=2" k-dik.png`,
  yazi duz okunana kadar).
- Arka plan kalabaliksa temizle: `medya_isle(islem="arka_plan", dosya=...)`.
- Etiketteki yazilari, hacmi ("50 ml · 1.7 FL.OZ.") fotograftan OKU; istemde
  aynen yaz.

## 2. Istem (Ingilizce, tek paragraf)
1. Tur ve oran ("Premium vertical Instagram story product photograph").
2. Urun kimlik kilidi: sekil, malzeme, renk (icerik dahil), etiket yazilari
   tirnakta ve yerleriyle.
3. Sahne: zemin, arka plan, isik, renk paleti, objektif hissi.
4. Kompozisyon: urunun yeri; YAZI gelecekse BOS ALAN ("clean empty space in the
   top quarter for headline").
5. Kuyruk: "No added text, no watermark; exact product shape, colors and label."

```
gorsel_uret(istem="...", dosya_adi="hikaye-9x16.png", oran="9:16",
            referanslar=[".ofis/ekler/sise.jpg", ".ofis/ekler/kutu.jpg"])
```
`oran`: 9:16 hikaye/reels · 4:5 gonderi · 1:1 kare · 16:9 yatay. GPT orana
yakin uretir; tam olcuye kirp (asagida). ~1 dk/gorsel.

## 3. Bak ve sec (ZORUNLU)
Ciktiyi AC, urun fotografiyla yan yana karsilastir: etiket yazisi, renk, sekil,
olcek, kutu. Tutmayan gorsel teslim EDILMEZ; istemi duzeltip yeniden uret.
Onemli iste 2 surum uretip iyisini sec.

## 4. Yazi, CTA, olcu (satis gorseli)
- Yazi modelle DEGIL sonradan eklenir (harf hatasi olmaz): ffmpeg drawtext
  (`C\:/Windows/Fonts/segoeuib.ttf`; Turkce harfler calisir). Baslik + kisa
  fayda + CTA ("Simdi kesfet", "DM'den siparis"); guvenli alanda (hikayede
  ustten/alttan %14). Kontrast yetmezse yazinin arkasina yari saydam serit.
- Hikaye 1080x1920, gonderi 1080x1350, kare 1080x1080:
  `ffmpeg -i g.png -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" c.png`
  (kirpmada urun ve etiket KESILMEZ; gerekirse once `gorsel_buyut`).
- Urun hakkinda yalniz KAYNAGI olani yaz (patronun sozu, etiket, verilen
  site). Fiyat, indirim, koku notasi, site adresi bilinmiyorsa YAZMA.

## 5. Teslim
`sohbete_yaz(ekler=[...])` (en cok 5): son gorseller + kisa aciklama (hangi
referans, hangi oran, ne secildi). Kanit otomatik yazilir.
