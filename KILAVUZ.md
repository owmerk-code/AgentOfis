# AgentOfis — Gunluk Kullanim Kilavuzu

Bu kilavuz `ofis/kabuk.py` kaynak kodundan ve gercekten kosturulmus
komutlardan derlenmistir. Kosturulan komutlar **gecici bir veritabani**
(`--db ...\kilavuz2.db`) uzerinde calistirilmistir; gercek/varsayilan
ofis veritabanina hicbir yazma yapilmamistir. Model cagiran (para yakan)
komutlar kosturulmamis, yalnizca kaynak kod ve `--help` ciktisina
dayanarak anlatilmistir.

## Dogrulama durumu

| Komut | Kosturuldu mu | Kanit |
|---|---|---|
| `--help` (genel) | EVET | asagida, Bolum 0 |
| `kur` | EVET | Bolum 1 |
| `ise-al` | EVET | Bolum 1 |
| `durum` | EVET | Bolum 1, 4 |
| `bekleyen` | EVET | Bolum 3 |
| `cevapla` | EVET | Bolum 3 |
| `onayla` | EVET | Bolum 3 |
| `saglik` | EVET | Bolum 4 |
| `iptal` | EVET | Bolum 4 |
| `--help` (konus, hedef, devam, ekip, saglik, iptal) | EVET (yalniz help; argparse, model cagirmaz) | ilgili bolumler |
| `konus` (gercek calistirma) | HAYIR — dogrulanamadi (para yakar, kosturulmadi) | Bolum 2 |
| `hedef` (gercek calistirma) | HAYIR — dogrulanamadi (para yakar, kosturulmadi) | Bolum 2 |
| `devam` (gercek calistirma) | HAYIR — dogrulanamadi (para yakar, kosturulmadi) | Bolum 4 |
| `ekip oner` (gercek calistirma) | HAYIR — dogrulanamadi (para yakar, kosturulmadi) | Bolum 4 |

---

## 0. Genel yardim

```
python -m ofis.kabuk --help
```

```
usage: python -m ofis.kabuk [-h] [--db DB] [--proje PROJE]
                            {kur,ise-al,konus,hedef,devam,ekip,hesap,plan,roller,ajan,gorsel,video,iptal,anahtar,yetenek,saglik,durum,bekleyen,cevapla,onayla,panel}
                            ...

AgentOfis komut satiri

positional arguments:
  {kur,ise-al,konus,hedef,devam,ekip,hesap,plan,roller,ajan,gorsel,video,iptal,anahtar,yetenek,saglik,durum,bekleyen,cevapla,onayla,panel}
    kur                 yeni ofis ac
    ise-al              ajan ise al
    konus               LIDERLE KONUS -- ofisin on kapisi
    hedef               hedef ver, halkayi dondur
    devam               halkayi kaldigi yerden surdur
    ekip                EKIP ONERISI -- lider onerir, sen onaylarsin
    hesap               HESAPLAR -- motor kimin adina konussun
    plan                ABONELIK PLANI -- tavanlar buradan olceklenir
    roller              ROL KUTUPHANESI -- hangi rol ne is yapar
    ajan                kadroyu gor / ajanin motorunu degistir
    gorsel              gorsel uret / saglayici durumu
    video               video uret / saglayici durumu
    iptal               yarim isi iptal et (kilitleri birakir)
    anahtar             API anahtarlarini yonet (deger basilmaz)
    yetenek             ofis neyi yapabilir? motor . hesap . anahtar .
                        baglayici . CLI -- hepsi olculmus
    saglik              ofis tikali mi? teshis + care
    durum               ofisin su anki hali
    bekleyen            senden bekleneni goster
    cevapla             bekleyen soruyu cevapla
    onayla              bekleyen onayi cevapla
    panel               paneli ac

options:
  -h, --help            show this help message and exit
  --db DB               veritabani yolu
  --proje PROJE         proje adi
```

`--db` her komuta genel bayrak olarak eklenir (altkomuttan ONCE yazilir):
`python -m ofis.kabuk --db <yol> <altkomut> ...`. Verilmezse
`ofis/db.py` icindeki `VARSAYILAN_YOL` kullanilir — yani gercek ofis
veritabani. **Deneme/ogrenme icin her zaman `--db` ver.**

---

## 1. Ofisi acma ve durum gorme

Sifirdan bir ofis; adim adim, hepsi ayni gecici `--db` uzerinde.

### 1.1 Ofisi kur

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" kur --ad "Kilavuz Denemesi" --amac "kilavuz icin ornek ofis" --olcut "kilavuz dogru yazildi"
```

```
Ofis kuruldu: Kilavuz Denemesi
  kanat      : ANA
  veritabani : C:\Users\pc\AppData\Local\Temp\claude\C--Users-pc-Desktop-AgentOfis-calisma\cbe16b29-c0be-4af9-9645-e70e8e2f2b34\scratchpad\kilavuz2.db

Simdi kadro kur:
  python -m ofis.kabuk ise-al demir lider --lider
  python -m ofis.kabuk ise-al cinar backend
```

`kur` yalnizca `--ad` zorunlu tutar; `--amac`, `--olcut`, `--kapsam-disi`,
`--kisitlar`, `--kanat` (varsayilan `ANA`) ve `--klasor` (ajanlarin ortak
calisma koku) opsiyoneldir. Kurulum, tek bir "kanat" (ANA) ile acik bir
proje olusturur.

### 1.2 Kadroyu kur (ise-al)

Bir **lider** zorunludur; onsuz `konus`/`hedef` calismaz (ofis on
kapisini lider acar).

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" ise-al demir lider --lider
```
```
demir ise alindi (lider, eller)
  motor  : claude  model: opus
  klasor : C:\Users\pc\AppData\Local\Temp\claude\...\scratchpad\calisma
```

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" ise-al cinar backend
```
```
cinar ise alindi (backend, eller)
  motor  : claude  model: opus
  klasor : C:\Users\pc\AppData\Local\Temp\claude\...\scratchpad\calisma
```

`ise-al <ad> <meslek>` iki zorunlu konum argumani alir; `<meslek>` rol
kutuphanesinden bir addir (`python -m ofis.kabuk roller` ile listelenir).
`--lider` bu ajani lider yapar. `--motor` (varsayilan `claude`),
`--model`, `--efor` (`dusuk|normal|yuksek`, varsayilan `normal`),
`--kanat`, `--klasor` ve `--kendi-klasoru` (ortak kok yerine yalitilmis
klasor) diger bayraklardir.

### 1.3 Ilk durumu gor

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" durum
```
```
DURUM
  isler   : is yok
```

`durum` hicbir bayrak almaz; is yoksa "is yok" yazar, varsa her
durumdaki (bitti/iptal disinda) isi `#no [durum] baslik sahip kanit-sayisi`
seklinde listeler ve varsa "SENDEN BEKLENEN: N" satirini ekler.

---

## 2. `konus` ile `hedef` farki

**Ikisi de dogrulanamadi (para yakar, kosturulmadi).** Asagidaki bilgi
yalnizca `ofis/kabuk.py` kaynagina (fonksiyon docstring'leri ve
`komut_konus`/`komut_hedef` govdesi) ve `--help` ciktisina dayanir.

### `konus` — ofisin on kapisi

> `ofis/kabuk.py:152` docstring: *"`hedef` her istegi ZORLA bir goreve
> cevirir; bu komut cevirmez. Karari lider verir: cevaplar, kendi yapar
> ya da dagitir. Basit bir soru icin butun makineyi calistirmak jetonu
> da zamani da bosa yakar."*

`konus`, liderle serbest bir mesajlasmadir. Lider mesaji alir ve
**triyaj** yapar — kod uzerinde gorunen dort yol: `cevap` (kendi
cevaplar, ajan kosturulmaz), `kendi` (kendi yapar, inceleme SENDE
kalir), `dagit` (kadroya gorev acar) ya da `kadro` (mevcut kadro
yetmiyor, ekip onerisi getirir). Yani `konus` her zaman bir gorev
DOGURMAZ.

```
python -m ofis.kabuk konus --help
```
```
usage: python -m ofis.kabuk konus [-h] [--lider LIDER] [--butce BUTCE]
                                  [--zaman-asimi ZAMAN_ASIMI]
                                  [--azami-tik AZAMI_TIK] [--paralel PARALEL]
                                  [--izin ARAC] [--klasor YOL]
                                  mesaj

positional arguments:
  mesaj

options:
  -h, --help            show this help message and exit
  --lider LIDER
  --butce BUTCE         tur basina $
  --zaman-asimi ZAMAN_ASIMI
  --azami-tik AZAMI_TIK
  --paralel PARALEL     ayni anda kac is kossun (1 = sirali)
  --izin ARAC
  --klasor YOL          ofis DISINDA bir klasoru bu ise ac (tekrarlanabilir),
                        orn: --klasor "C:/Users/pc/Desktop/projem"
```

Ornek (kaynaktaki `--help` bicimine gore, KOSTURULMADI):
```
python -m ofis.kabuk konus "Bu hafta hangi isler bitti?"
```

### `hedef` — halkayi ZORLA baslatir

`hedef`, mesaji dogrudan `ofis.orkestra.hedef_ver(...)`'e verir: lider
**her zaman** bir plan cikarir (bol/bolme), gorevleri acar ve
`--sadece-plan` verilmedigi surece halka (`_dongu_yaz`) hemen
dondurmeye baslar. Yani `hedef` bir triyaj sunmaz — dogrudan is acar.

```
python -m ofis.kabuk hedef --help
```
```
usage: python -m ofis.kabuk hedef [-h] [--lider LIDER] [--butce BUTCE]
                                  [--zaman-asimi ZAMAN_ASIMI]
                                  [--azami-tik AZAMI_TIK] [--sadece-plan]
                                  [--paralel PARALEL] [--izin ARAC]
                                  [--klasor YOL] [--web URL] [--sartname]
                                  [--baglayici AD]
                                  hedef

positional arguments:
  hedef

options:
  -h, --help            show this help message and exit
  --lider LIDER
  --butce BUTCE         tur basina $
  --zaman-asimi ZAMAN_ASIMI
  --azami-tik AZAMI_TIK
  --sadece-plan         plani goster, is baslatma
  --paralel PARALEL     ayni anda kac is kossun (1 = sirali)
  --izin ARAC           bu is icin ek izin, orn: --izin "Bash(codex *)"
  --klasor YOL          ofis DISINDA bir klasoru bu ise ac (tekrarlanabilir),
                        orn: --klasor "C:/Users/pc/Desktop/projem"
  --web URL             acilacak web kaynagi (tekrarlanabilir), orn: --web
                        https://rakip.com
  --sartname            kabul olcutlerini KAPI MODELI (fable) denetlesin.
                        Zayif bulursa plan lidere geri doner. Tavan zorunlu;
                        haftalik pay dolduysa ATLANIR ve soylenir.
  --baglayici AD        hesabin claude.ai baglayicisini bu ise ac
                        (tekrarlanabilir), orn: --baglayici Shopify. DIKKAT:
                        teknik olarak hesabin TUMU yuklenir ve tur ~95k ek
                        jeton yakar; bildirim bir suzgec degil, odemeye deger
                        mi kararidir. Liste: `kabuk baglayici`
```

Ornek (KOSTURULMADI):
```
python -m ofis.kabuk hedef "Siparis toplami dogru hesaplansin" --sadece-plan
```

### Ne zaman hangisi

- **Basit bir soru, bir aciklama, "bu ne durumda"** turu istekler icin:
  `konus`. Lider karar verir; gereksiz yere kadro calistirmaz.
- **Gercek bir is/degisiklik yapilmasi gereken** istekler icin: `hedef`.
  Lider ZORUNLU olarak plan cikarir ve halkayi dondurur.
- `--sadece-plan` ile `hedef`, is BASLATMADAN sadece plani gosterir —
  "ne olacagini once gormek" istendiginde kullanilir.

---

## 3. Bekleyen soru/onay cevaplama

Bir ajan (`postane.soru_sor` ya da `postane.onay_iste` ile) sana
soru sordugunda ya da onay beklediginde, senin gorecegin ve
yazacagin TAM komutlar asagida — gercekten bekleyen bir soru + bir
onay olusturulup cevaplanarak dogrulanmistir (model cagrilmadan, dogrudan
`Postane` API'siyle veri eklenmistir; `bekleyen`/`cevapla`/`onayla`
komutlarinin KENDISI gercek CLI'dir).

### 3.1 Bekleyeni gor

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" bekleyen
```
```
[soru] da1be2a3  demir
       Bu ozellik icin hangi renk paletini kullanayim?
       cevapla: python -m ofis.kabuk cevapla da1be2a3 "..."
[onay] 4675d606  demir  risk: yuksek
       Uretim veritabanina yaz
       migrasyon calistirilacak
       onayla : python -m ofis.kabuk onayla 4675d606
       reddet : python -m ofis.kabuk onayla 4675d606 --hayir --not "gerekce"
```

Not: kimlikler kisa onektir (ilk 8 karakter). Onek birden fazla kayitla
eslesirse kabuk "birden fazla ile eslesiyor, daha uzun yaz" der
(`_kimlik_coz`, `kabuk.py:1134`).

### 3.2 Soruyu cevapla

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" cevapla da1be2a3 "Koyu mavi kullan"
```
```
Cevap iletildi. Halkayi surdurmek icin:
  python -m ofis.kabuk devam
```

`cevapla <kimlik> <metin>` iki zorunlu konum argumani alir; bayrak yoktur.

### 3.3 Onayi cevapla

Onayla:
```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" onayla 4675d606
```
```
Onay onaylandi. Halkayi surdurmek icin:
  python -m ofis.kabuk devam
```

Reddet (gerekce ZORUNLU — kod bunu `--hayir` ile birlikte `--not`
verilmezse `PostaneHatasi` ile reddeder):
```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" onayla <kimlik> --hayir --not "gerekce"
```
Bu ret ornegi ayrica kosturulmadi (yukaridaki onay zaten onaylandi ve
"bir istek bir kez cevaplanir" kurali ikinci cevaba izin vermez); komut
bicimi `--help` ciktisindan alinmistir:
```
python -m ofis.kabuk onayla --help
```
```
usage: python -m ofis.kabuk onayla [-h] [--hayir] [--not NOT_] kimlik

positional arguments:
  kimlik

options:
  -h, --help  show this help message and exit
  --hayir     reddet
  --not NOT_  ret icin ZORUNLU gerekce
```

### 3.4 Kuyrugun bosaldigini gor

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" bekleyen
```
```
Senden beklenen bir sey yok.
```

### 3.5 Sonra halkayi surdur

Cevap/onay verdikten sonra yapilacak sey **yeni bir `hedef` vermek
degil**, `devam` komutudur — kaynaktaki uyari acik:

> `komut_devam` docstring (`kabuk.py:280`): *"Halkayi kaldigi yerden
> dondurur -- yeni hedef VERMEDEN. Soru cevaplandiktan ya da onay
> verildikten sonra gereken sey budur. Yeni hedef vermek, bekleyen isin
> ustune ikinci bir is yigmak olurdu."*

`devam` de model cagirdigi icin burada **dogrulanamadi (para yakar,
kosturulmadi)**; bicimi `--help`'ten:
```
python -m ofis.kabuk devam --help
```
```
usage: python -m ofis.kabuk devam [-h] [--butce BUTCE]
                                  [--zaman-asimi ZAMAN_ASIMI]
                                  [--azami-tik AZAMI_TIK] [--paralel PARALEL]
                                  [--izin ARAC]

options:
  -h, --help            show this help message and exit
  --butce BUTCE
  --zaman-asimi ZAMAN_ASIMI
  --azami-tik AZAMI_TIK
  --paralel PARALEL     ayni anda kac is kossun (1 = sirali)
  --izin ARAC
```

---

## 4. Tikanan isi acma

`saglik` "ofis tikali mi" diye SORAR (durum sayilarinin ANLAMLI olup
olmadigina bakar); `durum` yalnizca SAYAR. Asagida gercek bir is acilip
kosacak ajan bulunamayarak "TIKALI" hale getirilmis, sonra `iptal` ile
kilitleri birakilarak cozulmustur.

### 4.1 Bir is acildiginda durum

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" durum
```
```
DURUM
  isler   : 1 hazir
  #1 [hazir] Deneme is  demir  0 kanit
```

### 4.2 Saglik tanisi

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" saglik
```
```
[TIKALI] #1 'Deneme is' hazir ama KOSACAK AJAN YOK
          Bu kanatta hic uygun ajan yok
          -> `ise-al` ile bu kanada 'eller' bir ajan ekle, ya da isi baska kanada tasi.

1 tikali, 0 senden bekleniyor.
```

`saglik` bayrak almaz; sag ustte `[TIKALI]`, `[SENDEN]`, `[UYARI]`,
`[BILGI]` etiketleriyle bulgu basar, her bulgunun yaninda `-> care`
satiriyla ne yapilmasi gerektigini soyler. Hicbir bulgu yoksa
`SAGLIKLI -- tikanan is yok, senden beklenen yok.` yazar.

### 4.3 Isi iptal ederek kilitleri birak

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" iptal 1 --sebep "kilavuz denemesi bitti"
```
```
#1 Deneme is -> iptal
  sebep: kilavuz denemesi bitti
```

```
python -m ofis.kabuk --db "C:\...\kilavuz2.db" durum
```
```
DURUM
  isler   : 1 iptal
```

`iptal <no> --sebep <metin>` — `--sebep` ZORUNLUDUR; bos verilirse
kabuk "gerekcesiz iptal, alti ay sonra 'bu is neden yarim kaldi'
sorusunu cevapsiz birakir" diyerek reddeder (`kabuk.py:800`). Iptal,
isin tuttugu yazma kilitlerini de birakir ve hangi kilitlerin
birakildigini/hala kilitli kaldigini basar.

### 4.4 Yeniden akitmak icin

Iptal edilen bir is bir daha akmaz (durumu `iptal`, `bitti`
degildir); yeniden calistirmak icin ayni istek yeni bir `hedef` ile
verilmelidir. Yarim kalmis ama iptal EDILMEMIS bir is icin (ornegin
soru/onay bekliyorsa) dogru komut Bolum 3'teki `cevapla`/`onayla`,
ardindan `devam`dir — `iptal` yalnizca isin tamamen birakilacagi
durumlar icindir.

Ekip onerisi bekliyor ve kadro yetmiyorsa (`kadro` triyaj sonucu),
gorunur kilmak ve akitmak icin:
```
python -m ofis.kabuk ekip liste
```
kosturulabilir (veritabanini okur, model cagirmaz) — bu komut bos
kadroda "Bekleyen ekip onerisi yok." doner; boyle bir oneri yokken bu
ofiste kosturulmamistir, dolayisiyla dolu-liste ciktisi icin **dogrulanamadi**.
`ekip oner "..."` ve `ekip kur <no>` ise model cagirdigi/kadro
kurdugu icin **dogrulanamadi (para yakar, kosturulmadi)**; `--help`
bicimi:
```
python -m ofis.kabuk ekip --help
```
```
usage: python -m ofis.kabuk ekip [-h] [--no NO] [--sebep SEBEP]
                                 [--lider LIDER] [--butce BUTCE]
                                 [--zaman-asimi ZAMAN_ASIMI] [--klasor KLASOR]
                                 {oner,liste,kur,red} [istek]

positional arguments:
  {oner,liste,kur,red}
  istek                 `oner` icin: ne yapilacak

options:
  -h, --help            show this help message and exit
  --no NO               `kur`/`red` icin oneri numarasi
  --sebep SEBEP         `red` icin ZORUNLU gerekce
  --lider LIDER
  --butce BUTCE         tur basina $
  --zaman-asimi ZAMAN_ASIMI
  --klasor KLASOR       ajanlarin calisma koku
```

---

## 5. Ofisin sinirlari

### 5.1 Baglayici yetkisi: BAGLI / YETKI YOK / OLCULEMEDI

`ofis/baglayici.py` uc durumu ASLA uydurmaz (`lider_blogu`,
`baglayici.py:150`):

- **BAGLI** — CLI (Claude Code) o baglayiciya (ornegin Shopify) fiilen
  erisebiliyor.
- **YETKI YOK** — baglayici tanimli ama Claude Code girisi yapilmamis;
  bu durumda is **acilmaz**, patrona hangi komutu calistirmasi gerektigi
  soylenir:
  ```
  claude mcp login "claude.ai <Ad>"
  ```
- **OLCULEMEDI** — `claude mcp list` hic kosmadi; bu durumda kod "yok"
  demez, olcemedigini soyler.

Kod ayrica olculmus bir tuzagi belgeliyor: claude.ai WEB arayuzu ile
CLI ayni seyi soylemez — web'de "bagli" gorunen bir baglayici (orn.
Canva, Higgsfield, n8n, Supabase) CLI'da "yetki bekliyor" olabilir;
`GitHub Integration` web'de varken CLI listesinde HIC yoktur. **Ofis CLI
uzerinden kostugu icin gecerli olan CLI'in gordugudur.**

### 5.2 Baglayici acmanin maliyeti

`ofis/baglayici.py:245-258` ve `kabuk.py --baglayici` yardim metni:
bir baglayici `hedef --baglayici <Ad>` ile acildiginda **teknik olarak
hesabin TUMU yuklenir** ve tur basina **~95.000 ek jeton** odenir.
Bu bir suzgec degildir — "odemeye deger mi" kararidir; gereksiz yere
istenmemesi gerekir.

### 5.3 Ofisin SECEMEDIGI sey

`baglayici.py:184`: *"Baglayici SECEMEZSIN. Yetki insandan gelir; sen
yalnizca GEREKTIGINI soylersin."* Bir is BAGLI olmayan bir baglayici
gerektiriyorsa ofis isi ACMAZ; hangi `claude mcp login` komutunun
calistirilmasi gerektigini yazar ve durur. Baglayici KURMAK/YETKI
VERMEK insanin elindedir, ofisin degil.

### 5.4 BAGLI olmak, hesabin BIZIM oldugunu KANITLAMAZ

`baglayici.py:191`: *"BAGLI olmasi o hesabin BIZIM oldugunu
KANITLAMAZ. Hangi hesaba bagli oldugu bir OLGUdur; bilmiyorsan sor,
varsayma."* Ayni ihtiyatlilik `hesap durum` (Codex icin) icin de
gecerlidir — `kabuk.py:388-421` kod, kullanicinin iki farkli hesabi
olabilecegini ve "girisliyim" demenin HANGI hesap oldugunu
kanitlamadigini acikca ele alir; bu yuzden `hesap durum` e-postayi
ve plan bilgisini gosterir, sadece "bagli/bagli degil" demez.

### 5.5 Coklu ajan maliyeti (~15 kat)

Bu ofisteki baglayici kararlarda (bkz. K3 — Su Anki Durum) tekrar eden
olcum: bir isi birden fazla ajana bolmek, tek ajanda kosandan
**yaklasik 15 kat** daha fazla jeton yakar (paralel kollarin her biri
kendi baglamini yeniden kurar, birlestirme koluna ihtiyac duyar).
Bu yuzden is; ayni dosyaya yaziyorsa, sirali/bagimli adimlardan
olusuyorsa ya da hacmi kucukse **bolunmez, tek ajanda kosturulur** —
bolme kararini KOD degil, isin gercek bagimlilik yapisi belirler.
