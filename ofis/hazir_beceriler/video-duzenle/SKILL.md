---
name: video-duzenle
description: HAZIR bir videoyu (patronun sohbette verdigi, Flow'dan inen, telefondan gelen) patronun istegine gore DUZENLEMEK -- kesme, kisaltma, sahne secme/siralama, birlestirme, hiz (agir cekim), dikeye/kareye cevirme, yazi, altyazi, muzik, seslendirme, logo, renk; sonra olcup teslim. Kredi harcamaz (yerel ffmpeg + Remotion).
---

# Hazir videoyu duzenleme (montaj, edit, kurgu)

Butun araclar YEREL: kredi ve para harcamaz, her cikti ofisce OLCULUR ve
kanit otomatik yazilir. Video yuklemeye kadar isin klasorunde
(`.ofis/ekler/...`) olmali; patronun yukledigi video zaten orada.

## 1. Once videoyu ANLA (izleyemezsin -- kare panosuna bakarsin)
- `video_denetle(dosya)` -> boyut, oran, sure, fps, ses var mi, siyah/sessiz yer.
- `medya_isle(islem="sahneler", dosya=...)` -> kesme noktalari ve zaman damgali
  KARE PANOSU. Panoyu AC ve BAK (Read/view_file): hangi sahne ne gosteriyor.
  Kesim az ciktiysa `esik=0.15`, cok ciktiysa `0.45`.
- Konusma varsa `medya_isle(islem="altyazi", dosya=...)` -> ne soyleniyor, hangi
  saniyede (Whisper). Kesim noktalarini cumle sinirina koy, kelime ortasina degil.

## 2. Patronun istegini PLANA cevir
Patronun sozunu adim adim yaz ("ilk 3 sn'yi at, urunun gorundugu sahneyi basa
al, 15 sn'ye indir, Reels'e cevir, altyazi koy, sonda logo"). Belirsiz bir sey
varsa (hangi sahne? hangi muzik?) `soru_sor` ile secenekli sor; tahminle kesme.

## 3. Arac secimi
| Is | Arac |
|---|---|
| Tek araligi al | `medya_isle(islem="kes", bas, son)` |
| Konusmali videoda bosluklari at | `medya_isle(islem="sessizlik_kes")` (esik_db -35; gurultuluyse -30) |
| Sesi ayri al (muzigi baska videoda kullan) | `medya_isle(islem="ses_ayir")` |
| Birlestir, sirala, hiz, yazi, gecis, muzik, seslendirme, logo, oran | `video_kurgula` PLANI |
| Gorseli buyut / arka plani sil | `medya_isle` gorsel_buyut / arka_plan |

`video_kurgula` ile duzenleme ornegi (16:9 klipten 9:16 Reels, ilk 2 sn atilir,
ikinci sahne agir cekim, seslendirme altinda muzik kisilir, logo sag ustte):
```json
{"bicim": "9:16", "gecis": "solma", "gecis_sure": 0.4,
 "sahneler": [
  {"tur": "video", "dosya": ".ofis/ekler/ham.mp4", "kirp_bas": 2, "sure": 4,
   "yerlesim": "bulanik", "yazi": "Yeni sezon", "yazi_konum": "ust"},
  {"tur": "video", "dosya": ".ofis/ekler/ham.mp4", "kirp_bas": 9, "sure": 3, "hiz": 0.5,
   "yerlesim": "kapla", "odak": "sag", "filtre": "sinematik"}],
 "muzik": ".ofis/ekler/muzik.mp3", "muzik_bas": 12, "muzik_alcalt": 0.3,
 "sesler": [{"dosya": ".ofis/ekler/seslendirme.mp3", "bas": 0.5}],
 "logo": {"dosya": ".ofis/ekler/logo.png", "konum": "sag_ust", "boyut": 0.16},
 "son_kart": {"metin": "Marka", "alt_metin": "site.com", "sure": 2}}
```
- Ayni videodan birden cok parca: her parca ayri sahne (`kirp_bas` + `sure`).
- `hiz`: 0.5 agir cekim (klipten sure x 0.5 sn harcar), 2 hizli. Klip yetmezse
  ofis CIZMEDEN soyler.
- Yatay klip dikey videoda: `yerlesim: "bulanik"` (kirpmadan, arka bulanik
  dolgu) ya da `kapla` + `odak` (ozne soldaysa "sol"). Yuz/urun kesilmesin.
- Klibin kendi sesi: muzik varsa varsayilan KAPALI; konusma varsa sahnede
  `"ses": true` ve `muzik_ses` 0.2-0.35.
- Sozlu muzik patronun isi (paylasirken ekler); istenmedikce telifli muzik koyma.

## 4. Olc ve bak (teslimden once ZORUNLU)
`video_kurgula` sonucu olcumu verir (oran, sure, ses, siyah ekran) ve kare
ozeti cikarir: kare ozetini AC, bak. Kontrol et:
- Kesim cumle ortasinda mi? Ilk sahne 1 sn icinde dikkat cekiyor mu?
- Yazi/altyazi guvenli alanda mi, okunuyor mu (Reels'te alt %30 ve sag kenar kapali)?
- Urun ve yuz kesilmemis mi? Siyah kare, ani ses sicramasi var mi?
Sorun varsa plani duzeltip yeniden ciz (kredi harcamaz).

## 5. Teslim
`sohbete_yaz(ekler=[video, kare ozeti])`: ne yaptin (patronun her istegine
karsilik bir satir), sure/oran, kullanilan muzik ve kaynagi. Buyuk video da
gonderilir (2 GB'a kadar).
