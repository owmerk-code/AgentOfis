# AgentOfis — proje anayasası (özet)

> Her oturumun başında okunan dosya. Burada yalnız **kararlar, kurallar,
> mimari ve güncel durum** durur. Ayrıntılı geçmiş (her ölçüm, hata,
> sınama sayısı, rakip incelemesi) **`docs/GUNLUK.md`**'de; yol haritası
> ve açık işler **`PLAN.md`**'de.
>
> Günlükte arama: `grep -n "^## " docs/GUNLUK.md` başlıkları tarihle
> listeler; bir konunun gerekçesi gerekiyorsa oradan okunur.
>
> **Yazma kuralı:** yeni bulgular, ölçümler ve hata kayıtları
> `docs/GUNLUK.md`'nin SONUNA eklenir. Bu dosya yalnız bir karar, kural,
> mimari ya da durum değişince güncellenir ve **~40 bin harfin altında**
> tutulur (Claude Code 150 bin harfi aşan CLAUDE.md'yi keser; 29.09'da
> 604 bin harfe ulaşmıştı ve bu yüzden bölündü).

## Ne yapıyoruz

Kullanıcının kendi **AI ajan ofisi**: isimli, meslekli, kalıcı kimlikli
ajanlar; bir lider işi böler, işçiler yapar, kanıt üretir, lider inceler.
Kullanıcı Türkçe konuşur, **cevaplar Türkçe ve sade** olur. Günlük işlerinin
%90'ı için kullanacak (yazılım, içerik, araştırma, ileride mağaza/reklam).
Satılmayacak.

**Alan-bağımsız (mimari kısıt):** çekirdekte sektör adı geçmez. Alana özgü
bilgi projeye `olgu`/`karar` olarak girer, koda değil. `testler/ornek_ofis.py`
bir sahnedir.

**Bitti çizgisi (27.09, kullanıcı):** sistem **Claude + Codex (GPT)
abonelikleriyle TAM** kullanılabilir olunca biter. Öteki motorlar (Gemini,
Kimi, Qwen, OpenCode…) eklenti; takılabilmeleri için altyapı hazır durur,
motor matrisinden geçmeden deftere girmez.

## Kesinleşmiş kararlar

| Karar | Gerekçe |
|---|---|
| **Yerel panel** (FastAPI + düz HTML/JS), exe değil | Paketleme son adım (F9, Tauri). Derleme adımı yok. |
| **Python + FastAPI + SQLite** | Kullanıcının yığını; CLI'ları alt süreçle koşturmak Python'da yerli. |
| **Fan-out kararı liderde, gerekçe zorunlu** | Bölmek de bölmemek de karar günlüğüne yazılır. |
| **Bellek SQLite'ta, kendimiz yazıyoruz** | Dış hafıza servisine bağlanılmaz. |
| **Ofisin TEK evi** `Masaüstü\AgentOfis` (kod) + `AgentOfis\ev` (hafıza, kasa, oturumlar, gölge, yedekler) | 01.10 kullanıcı kararı + ölçüm: kök ofisin içindeyken Claude ajanı ofisin CLAUDE.md'sini okuyordu. Ev GitHub'a ve ZIP'e girmez. |
| **Projeler masaüstünde** `Masaüstü\<proje>` (Ofisim = genel işler, iş adlı alt klasörler) | Kök ofisin içinde AÇILAMAZ (`yollar.ofis_icinde_mi`). Projede ofisin tek izi gizli `.ofis/` (ekler, karalama). |
| **Ofis kendini geliştirir, kendini KURMAZ** | Ajan çalışan ofisin koduna yazamaz (09.10'dan beri KAPIDA: Write/Edit/yama/kabuk → RET; o güne dek yalnız yazılıydı). Geliştirme takımı ayrı KOPYADA çalışır, ofis tam sınamayı koşar, patron kurulum kartıyla kurar (`gelistirme.py`). |
| **Ajanlar ortak kökte** (yazma alanı gerçek yoldur) | Yazma kilidi ancak çakışma fiziksel olarak mümkünse anlamlı. |
| **Her takım ayrı** (06.10, patron) | Hafıza/belge/karar/kural takımın + ORTAK (`kanat_id` ''); takımın kendi klasörü (yeni takım `Masaüstü\<takım>`), kota payı, kiti. Git: dal değil İŞ BAŞINA KAYIT (ortak kökte iki dal olmaz). |
| **Ürünü (Muratify) almıyoruz** | Rakip olarak izleniyor; bkz. günlük "RAKİP" bölümleri. |

### Hesaplar ve model politikası

- **Hesaplar:** Claude **Max 5x** · ChatGPT **Plus** (şu an; **Pro 5x'e geçilecek**,
  henüz alınmadı — tasarım Plus'a sabitlenmez; ofisin codex evi:
  omerjob34). `codex2` hesabı kayıp (kapalı). Google AI Pro VAR: Flow/Veo
  kabinde, Gemini ajanları Antigravity (`agy`).
- **Kullanıcı API değil ABONELİK kullanıyor:** maliyet **kota diliyle**
  anlatılır (5 saat / 7 gün penceresi yüzdesi), dolar yalnız API hesabında.
- **fable / astra YALNIZ PATRONUN SÖZÜYLE** (08.10, patron: "ben eklersem,
  istersem veya lidere söylersem"): sistem onları KENDİLİĞİNDEN kullanmaz
  (iki ret sonrası otomatik hakem kaldırıldı; inceleme liderin modeliyle).
  Yollar: ajana elle atama / takım kurarken · patron mesajda "şu işi şu
  ajana şu modelle" der → lider kola `model` (HER model, listeden) +
  patronun mesajından kelimesi kelimesine `model_alinti` (`izin.plan_modeli`;
  olumsuz cümle ret; listede yoksa ret; `gorev.patron_modeli`) · şartname
  yalnız `--sartname` ile. Hiçbir kademede yok; elle atamada bir kez sorulur, `uyari` olayı.
- **Model listesi** (`guncelleme.model_listesi`): üç motorun BÜTÜN modelleri
  gerçek adlarıyla (Claude kataloğu, Codex `models_cache`, `agy models`);
  önerilmeyenin yanında gerekçe (`roller.DISLANAN_MODELLER`, motora bağlı:
  Haiku 4.5, Gemini 3.1 Pro, Antigravity'nin Claude/GPT-OSS'u) — güncelleme
  bunları "yeni model" diye SORMAZ.
- **MESLEK KATALOĞU (05.10, patron; BenchLM kategori puanları + patronun
  görüşü):** yeni ajan motor/modelini mesleğinden alır (`roller.MESLEK_MOTORU`,
  ayar `meslek:<rol>`, panelde Organizasyon > Meslek kataloğu): lider Claude
  Opus · yazılım meslekleri Claude Sonnet · ürün/kalite/analiz GPT-6.1 Sol (akıl
  79,4, kodlama 59 → kod YAZMAZ) · mağaza ve bilgisayar/tarayıcı GPT-5.6 Sol
  (BrowseComp %92,2) · araştırma/içerik Gemini 3.8 Flash High · **tasarım/video Sonnet 5.5** (08.10 patron, ölçüm: Flow'u Sonnet 171 sn, Gemini ~608 sn sürdü).
  Haiku ve Gemini 3.1 Pro hiçbir yerde yok; Antigravity'nin Claude/GPT-OSS
  modelleri kullanılmaz. Ajan sabit, model değişebilir.
- **Kademe (kod değil ayar, `roller.kademe_haritasi`):**
  claude hızlı sonnet · standart sonnet · güçlü opus;
  codex hızlı gpt-6-luna · standart gpt-6.1-sol · güçlü gpt-6.1-sol;
  gemini 3.8-flash low / medium / high.
- **Zorluk → efor** (05.10): kolay→düşük · orta→normal · zor→yüksek ·
  çok_zor→çok_yüksek (gerekçe zorunlu). `max` YOK. Varsayılan kipte (`zorluk_modeli=ajan`)
  zorluk MODELE dokunmaz (ajanın sabit modeli); kademe yalnız modelsiz ajanda,
  karne kipinde ya da ayar `kademe` iken.
- **Model açıkça verilir** (verilmeyen iş hesabın varsayılanına düşer,
  ölçüldü: on kat maliyet).
- **Model/CLI güncellemesi otomatik** (`guncelleme.py`): takma adın yeni
  hedefi, CLI sürümü, emekliye ayrılan model (codex'te 'yeni nesil' 09.10'dan beri SORULUR: 5.6 Sol→6.1 Sol patronun seçimini ezdi) → deneme turu geçerse uygulanır,
  geri alınabilir; yeni aile ve kapı modeli insana sorulur. Takma adlar
  ofisin onayladığı kimliğe sabitlenir (sessiz kayma yok).

### Kullanıcının kalıcı kuralları (her oturumda geçerli)

- Cevaplar Türkçe, sade; kısaltma ve jargon yok. Yalan yok, atlama yok;
  **ölçmeden iddia yok**. "Yapılamaz" demeden önce aracın TAM `--help`'i ve
  belgesi okunur; "şu yol kapalı, ölçtüm" ≠ "yapılamaz".
- Gerçek testler serbest ama **boş geçici klasörde, ucuz modelle, tavanla**;
  asla proje kökünde (CLAUDE.md bağlama yüklenir, bir "merhaba" $2,29 tuttu).
- Sınamalar gerçek kataloğa, kasaya, kabin profiline, gerçek deftere ve
  ofisin gerçek evine (`AgentOfis\ev`; eski `~/.agentofis`) dokunmaz; para harcamaz (`testler/_temizlik.py` kökü
  geçiciye çevirir, bekçi gerçek hafızayı izler).
- `~/.codex` salt okunur. Kimlik/oturum işlemleri geri alınamaz: önce
  kopyada ölçülür; **`--device-auth` önerilmez** (codex2 böyle kaybedildi).
  Girişleri (OAuth, Drive) kullanıcı yapar.
- **Para kilidi "sadece free"** kalır; OpenRouter bakiyesi başka bir botun.
  API anahtarı asla yazdırılmaz, gönderilmez.
- `veri/ofis.sqlite3` değiştirilmeden önce yedeklenir.
- Kullanıcının panelini (8900) ellemem; sınama paneli **8911**, geçici
  defter kopyasıyla. Paneli kullanıcı kendisi yeniden başlatır.
- Kullanıcının kendi Chrome'u ve tüketici AI arayüzleri sürülmez; canlı
  masaüstü onaysız sürülmez. **İSTİSNA (04.10 patron kararı):** gömülü
  tarayıcıda (kabin) patronun KENDİ girdiği Google Flow / Gemini uygulaması
  hesabıyla ajan görsel/video üretebilir; kredi harcayan üretim kapıda
  sorulur (patronun açık sözü o iş için izindir). Gizli (stealth) modellere yalnız herkese açık
  içerik gider.
- **GitHub:** yalnız gizli `owmerk-code/AgentOfis`, yalnız
  `python -m ofis.kabuk yedek github` ile. Yeni depo/uzak/hesap sormadan yok,
  asla herkese açık değil, sır ve müşteri verisi yok.
- Mağaza/reklam/sosyal hesaplar (Shopify, Meta…): **altyapı HAZIR olur**
  (Ayarlar > Entegrasyonlar'da kart + Bağla), bağlamayı kullanıcı gerektiğinde
  kendisi yapar (02.10 kararı; "ertelendi" diye hatırlatılmaz). Para/yayın
  eylemleri yine kapıda sorulur. Tauri F9'u bekler.
- **Güç kısan kısıt yok** (07.10, patron): ajanın çalışmasını/çıktısını kısan kural, araç kapatma, bağlam kırpma konmaz; kapı yalnız patronun istediği yerde (para, silme, kredi öncesi senaryo paketi); tasarruf güç pahasına yapılmaz.
- Commit sonu: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Sıra kararı: **sesli orkestratör ve panel görünüşü EN SON** (kullanıcı,
  29.09); görünüş için önce 2–3 tasarım yönü gösterilir, kullanıcı seçer.

## Beş yasa — mimarinin dayandığı ölçümler

1. **Yazma tek iplikli kalır** (Cognition) → `yazma_kilidi`; çakışan talep
   REDDEDİLİR.
2. **Çoklu ajan yalnız genişlik işinde kazanır, ~15× jeton yakar**
   (Anthropic) → liderin gerekçeli fan-out kapısı.
3. **Hataların %79'u mimari** (Berkeley MAST: belirtim %41,8 · uyumsuzluk
   %36,9 · doğrulama %21,3) → `neden`/`ana_hedef`/`kabul_olcutu` zorunlu,
   kanıt kapısı, şartname kapısı.
4. **Temiz bağlam birikmiş bağlamı yener** → lider incelemeye transkriptle
   değil hedef + kanıt + ofisin disk ölçümüyle girer.
5. **Zayıf model ne zaman yardım isteyeceğini bilmez** → kural rica değil
   yapı: araç yoksa yapamaz, kapı sorar.

## Mimari

```
YÜZEYLER    panel · kabuk (CLI) · telefon(sonra) · ses(sonra)
PROTOKOL    ofis MCP sunucusu (stdio JSON-RPC, 22 araç)
ÇEKİRDEK    kadro · DAG tahta · yazma kilidi · kanıt kapısı · karar günlüğü
            orkestra (halka) · lider (3 kapı) · sohbet (ön kapı) · takım
BELLEK      olay · olgu (çift-zamanlı) · bilgi/kural/ders · brifing K1–K4
MOTORLAR    claude (stream-json) · codex (app-server) · gemini (Antigravity agy) · sahte (YALNIZ sınamada)
```

Kural: **dayanıklı kısım çekirdeğe, çürüyecek kısım fişe.** Motor bir
adaptör, model bir ayar, arayüz bir istemci. Motora bağlı her yetenek bir
**bayrak** olarak bildirilir (`mcp_konusur`, `butce_destegi`,
`izin_kancasi`, `tur_ici_mesaj`, `araclar_kapatilabilir`,
`baglayici_tasir`); çekirdek bayrağa bakar, taşıyamayan motor istenen
kısıtı **kapalı kalarak reddeder**. Motor kartı (`motor_karti.py`) bayrağı
matrisin ölçümüyle karşılaştırır.

## Kod haritası

| Dosya | Ne yapar |
|---|---|
| `ofis/db.py` | Şema + sütun göçleri (`GOCLER`) + veri göçleri (`user_version`). Yol mutlaklaştırılır. Parametreler anahtar maskelemesinden geçer. |
| `ofis/yollar.py` | TEK kök `OFIS_EV` (yoksa `AgentOfis\ev`, o da yoksa eski `~/.agentofis`): kasa, kota, motor sağlığı, codex evi, kabin profili, yedek, gölge depo. Proje içi `.ofis/` adları, `ofis_icinde_mi`, masaüstü varsayılanı. |
| `ofis/tasima.py` | Ayrım taşıması (`kabuk tasi`, varsayılan DENEME): ev kopyası, proje eşlemeli doğrulamalı kopya, defter en son, eskiler silinmez. 01.10'da gerçek ofiste uygulandı. |
| `ofis/kadro.py` | İşe alma, motor/model/efor/klasör, faz, `ders` sicili. |
| `ofis/roller.py` | 20 rol / 6 kategori (05.10 `bilgisayar` eklendi), meslek kataloğu, Türkçe meslek adları; rol = sözleşme (tür · izin · MCP · kanıt türü · ölçüt şablonu · kademe · bütçe). Kademe/efor haritaları. |
| `ofis/tahta.py` | Görev, DAG, yazma kilidi (kira+nabız), kanıt kapısı, CAS, `iptal_et`, `medya_hedefi`, kök-göreli alan doğrulama. |
| `ofis/bellek.py` | Olgular, karar günlüğü, bilgi kapısı (`bilgi_ekle`), `[[bağ]]`, kurallar (yalnız insandan). 06.10: sohbetten hafıza önerisi (`sohbet_onerileri`, alıntı denetimli, patron "Yaz"), birleştirme (`birlesim_adaylari`/`birlestir`, `konu_takma`). |
| `ofis/belge.py` · `arama.py` | Belge kütüphanesi (06.10): PDF/Word/Excel/CSV/metin → yerli parçalar (`.ofis/belgeler/`), `belge_ara` MCP aracı, brifing ve triyaja kaynaklı ilk 3 parça. `arama.sirala` hafıza seçimi + belge aramasının TEK kuralı (kelime kapısı + harf dizisi sırası; ölçüldü `olcum_anlamsal.py`: 13→15/30, yerel anlam modeli 19/30 ama 1 GB → alınmadı). |
| `ofis/telefon.py` · `web/telefon.*` · `web/sw.js` | TELEFON (06.10, Tailscale): panelin GİRİŞ kapısı `_UzakKapi` uzak isteği tanır (adres, aktarıcı izi, Host); uzak websocket HEP ret; uzak HTTP yalnız eşleşmiş cihaz (tek kullanımlık kod, HttpOnly+Secure çerez, acil kesme) ve `telefon.IZINLI` uçlar. Web Push (VAPID evde). Ayrıntı günlükte. |
| `ofis/pay.py` · `kit.py` · `canli.py` · `git_kaydi.py` · `onizleme.py` · `eksik.py` | AŞAMA 4 (06.10): takım kota payı (takım % = hesap doluluğu × takımın jeton oranı; dolunca yeni işi bekler) · takım kiti (bitti tanımı + marka; yasak kelime incelemede TARANIR) · canlı eylem ölçümü (`canli.py`: --prod, canlı ödeme, paket yayımı, mağaza/reklam yazma → tek kapıda SORULUR; takım deneme kipi 08.10'da kalktı) · iş başına git kaydı (kapanışta ölçülen dosyalar `#no başlık`, kartta `git revert`) · önizleme (127.0.0.1 küçük sunucu) · ofisin kendi eksik önerisi (ölçülmüş tekrar → kart, `kabuk eksikler`). Kök TEK çözücü: `tahta.kanat_koku` → `Ofis.kok_klasoru(kanat)` / `Ofis.isin_koku(iş)`; kilit KÖKE göre çakışır. |
| `ofis/puan.py` · `tahmin.py` · `dosya.py` | Teslime 1–5 puan (düşük puanın gerekçesi ajanın dersi, karnede temiz sayılmaz) · ön tahmin (karneden süre/jeton; kota % yalnız tutarlı pencere ölçümünde) · `atomik_yaz` (benzersiz geçici dosya + Windows yeniden deneme; eşzamanlı yazan süreçler artık düşmüyor). |
| `ofis/brifing.py` | Dört katmanlı brifing (K1 kimlik/rol · K2 künye+kural+olgu · K3 kararlar · K4 iş+kanıt+not), devir paketi. |
| `ofis/koltuk.py` | Seat Runner: kilit → brifing → motor → olaylar → nabız → kanıt → inceleme. Zincir/devir, kaçak freni, not/durdurma kanalı, disk ölçümü, gölge anlık, kabin izleme. |
| `ofis/lider.py` | Fan-out · ayrık alan · kanıta karşı inceleme (temiz bağlam, salt okunur, yapan inceleyemez); ret ≥2'de kapı modeline yükseltme; lider zinciri. |
| `ofis/orkestra.py` | Halka (`tik`/`kos`): planlama JSON'u + kapılar ("ret öğretir"), paralel atama (rezerv), kabin kiralama, danışma teslimi; BİTEN KOL BEKLEMEZ (11.10, ara adım). |
| `ofis/sohbet.py` | Liderin ön kapısı: triyaj (cevap/kendi/dağıt/kadro), ofis özeti, rapor, cevap akışı (`AkisYazici`). |
| `ofis/takim.py` | Takım sohbeti: `@ajan` yönlendirme (lider · not · soru · `iş:`), tek akış. |
| `ofis/kuyruk.py` | İş kuyruğu (F5/1): lidere giden her panel mesajı sıraya girer (`kuyruk` tablosu, kalıcı); panel işçisi sırayı boşaltır, düşen iş sırayı durdurmaz; seri bitince MODELSİZ dönüş raporu. |
| `ofis/surec.py` · `toparla.py` | Kesintiden devam (F5/2): iş, koşturan sürecin kimliğini (`pid:oluşma`) taşır; panel açılışında ölü sürecin işi `kesinti` ile bırakılır ve AYNI oturumdan sürer; yaşayan/kimliksiz kayda ve PATRONU BEKLEYEN işe dokunulmaz; sürdürülen isteğin yarım mesajı ofisin modelsiz cevabıyla kapanır. Ajana/lidere sorulmuş soru ya da incelemede iş varsa açılışta halka sürer; sürdürülen işin `kosan_surec`'i tazelenir (`tahta.kosani_yaz`). |
| `ofis/bildirim.py` | Masaüstü bildirimi (F5/3): panel defteri izler; onay, patrona soru, lider cevabı, dönüş raporu, kesinti, sıra düşüşü → Windows bildirimi (PowerShell+WinRT, `-EncodedCommand`); yalnız gerçek panel açar, ayar `bildirim`. |
| `ofis/zamanlayici.py` | Zamanlayıcı (F5/4): sohbetten kurulur (triyaj `karar=zamanla`, saati ofis doğrular ve cevabı ofis kurar); gunluk/haftalik/bir_kez/aralik; vakti gelen iş kuyruğa; kaçırılan birikmez, bir kez koşar. |
| `ofis/postane.py` | Soru/onay, patronun notu (`NOT_KURALI`), imza/kapsam ile onay eşleştirme. |
| `ofis/danisma.py` | Ajana sorulan soruyu teslim eder (araçsız, salt okunur); cevaplanamazsa insana yükseltir. İşin LİDERİ, sahibine cevapta `ALAN_EKLE: yol` yazarsa ofis yazma alanını genişletir (`tahta.alan_ekle`: takım kökü, başka işin kilidi RET; sonuç cevaba eklenir). |
| `ofis/mcp_sunucu.py` | Ofis MCP: durum · kanit_ekle · karar_yaz · sohbete_yaz · soru_sor · onay_iste · bilgi_yaz · gorev_ac · gorsel_uret/iste · video_uret/durum/iste · video_kurgula · video_denetle · medya_isle · masaustu_bak/eylem · izin_sor (kanca) · giris_iste. Kimlik ORTAMDAN gelir. Riskli bulgunun kararı TEK yerde: `_kapi_karari` (izin_sor + masaüstü). Araç sözlük dönerse sonuçta görsel (MCP `image`). |
| `ofis/motor/tui.py` | GERÇEK TERMİNAL KİPİ — TEK KİP `gercek` (08.10, patron; `arka` yalnız sınamada; kural `kipe_gore`): iç motor (claude/codex/agy) ConPTY'de gerçek CLI; brifing yapıştırılır, olaylar CLI'ın oturum dosyasından, terminal turlar arası açık. Not ulaştı mı CLI'ın KAYDINDAN (`tui_kullanici_metni`; sıradaki not için tur sonunda 20 sn). CLI'ın kendi soruları `ekran_sorulari` (agy: oluşturma/düzenleme/URL ONAY, çalışma alanı dışı RET); agy yazabilen tur `accept-edits`, izin `read_url(*)`. Panelden gelen terminal otomatik cevapları CLI'a gitmez (`terminal.insan_girdisi`; codex'i kesiyordu). Tur terminali sahiplendiği an "koşuyor". Uzun yapıştırmada CLI'ın işareti beklenir, gönderme beklemesi boya göre (codex 41 bin harfi 10 sn'de gönderemiyordu). Çağıran bırakırsa CLI durur. Geçici dosyalar `ev/tui` (2 günde süpürülür). İstisna: tavanlı şartname turu. |
| `ofis/kanca.py` | Gerçek terminal (TUI) kancası: CLI'ın her araç çağrısını arka plan kipindeki AYNI kapıya sorar; hata = deny; `--oz-sinama`. |
| `ofis/izin.py` | Patronun ACIKCA istedigi riskli eylem (push, deploy) sorulmaz: lider planda patronun sozunden KELIMESI KELIMESINE alintiyla izin yazar, ofis sinifi olcer, olumsuz cumleyi reddeder; is basina ve kalici (insan). Para ve silme izinle acilmaz. |
| `ofis/riskli.py` | Riskli eylem ölçütü (geri alınabilir mi · dışarı çıkıyor mu · para var mı) + sert durak; kabuk kuralları; araç adı polaritesi (okuma serbest, tanınmayan sorulur); şifre/kart alanı.; betik taraması: Python'da yalnız alt sürece GİDEN metin (ast; değişken, liste, f-string), ayrıştırılamazsa tamamı. |
| `ofis/tarayici.py` · `tarayici_kapi.py` | Playwright MCP'yi bağlar (varsayılan serbest, riskli tıklama vekilde sorulur, sayfadaki gerçek adı okur); kabin CDP. |
| `ofis/kabin.py` | Panelin içindeki paylaşılan başsız Chrome (kare akışı), öğe seçici. `IndirmeYeri` (07.10): indirmeler `.ofis/indirilenler/`e (CDP ayarı yalnız bağlantı açıkken geçerli; tutucu iplik). Panel süreci ölünce kabin de kapanır (Job Object, 08.10). İlk açılış "ölümleri" = profil başka kabinde açık (çıkış 21, kayda yazılır); 20/20 temiz açılış ölçüldü. |
| `ofis/masaustu.py` | MASAÜSTÜ (D1, 08.10): iki CLI da masaüstü aracı vermiyor (ölçüldü) → ofisin MCP'sinde `masaustu_bak` (ekran görüntüsü görsel olarak + pencereler + öğe adları) ve `masaustu_eylem` (tıkla/sürükle/kaydır/yaz/tuş/pencere/uygulama aç). Fare/klavye SendInput (Türkçe harf), öğe adları UI Automation (PowerShell, paketsiz). Kapı `riskli.masaustu_degerlendir`: ilk eylem (bakmak dahil) sorulur, "bu iş boyunca" açar; gönder/sil/öde/yayınla düğmesi ve şifre alanı her seferinde; terminal penceresi RET; patron fareye/klavyeye dokunduysa ajan durur. |
| `ofis/gelistirme.py` | OFİS GELİŞTİRME (09.10, patron): şablon "Ofis geliştirme" → kök `Masaüstü\AgentOfis-gelistirme` (klon, kendi `ev/`'i, push KAPALI). İş kapanınca: kopya son koda EŞİTLENİR (rebase; çakışma = kurulamaz), toptan değişen satır sonu geri konur, eksik npm paketi kurulur, ffmpeg/RIFE çalışan ofisten ÇALIŞTIRILIR (bağlantı yok: kapı yolu metinle ölçer); `#no` kaydı kopyada TAM sınamadan geçer → kurulum KARTI; onay → çalışan depoya cherry-pick (kirli depo DURUR); ret → kopyada revert (düşerse SÖYLER). Panel açılışında yarım sınama sürer. `kabuk gelistirme durum|esitle|sina|reddet|geri-al <no>`. Önizleme: kopyada `python -m ofis.gelistirme onizle` (8920+). Bitti tanımı: gerçek defterin KOPYASINDA deneme, satır sonu koruma, `ALAN_EKLE`. İlk kurulum #6 (10.10). |
| `ofis/giris.py` | Giriş isteği: şifre ajana geçmez, insan kabinde girer, iş onun oturumuyla sürer. |
| `ofis/motor/tip.py` | Motor sözleşmesi: olay akışı, bayraklar, `durum_notu`, `limit_oku`, `TurKanali`, `SurecKafesi` (Job Object), `etkilesimli_komut`. |
| `ofis/motor/claude.py` · `codex.py` · `antigravity.py` · `sahte.py` · `gemini.py` | Adaptörler (`sahte` yalnız `OFIS_SINAMA_MOTORU=1` iken kayıtlı; `_temizlik` koyar; ürün onu hiç görmez). Claude: `.exe` doğrudan, `--permission-prompt-tool` kancası; SICAK BEKLEYEN SÜREÇ (06.10, `sicak_isit`): lider turu 9–12 → 3,5–6,4 sn. Codex: app-server (onay kapısı, steer, interrupt), `exec` yalnız görselde. Gemini = `antigravity.py` (`agy`; ajan başına ev, kanca ret = çıkış 2, kanca komutu TIRNAKSIZ + öz-sınama; Durdur = süreç kesilir + `--conversation`; KOTA `agy -p /usage` modelsiz, ≥1.2.15); eski `gemini.py` (Gemini CLI) Pro'ya kapalı. |
| `ofis/zincir.py` · `hesap.py` · `plan.py` | Nöbet zinciri (hesap üzerinde, önceden geçiş), çoklu hesap (anahtar referansla), abonelik planı. |
| `ofis/motor_saglik.py` · `kullanim.py` · `tavan.py` · `butce.py` | Oturum/kota hafızası; hesap pencereleri (tur koşmadan okunur); kaçak freni (08.10: kör sayı değil DÖNGÜ — aynı çağrı art arda 50 ya da son 80'de ≤2 farklı; sert sınır 1000) + jeton tavanı; Fable kapı payı. |
| `ofis/degisim.py` · `geri_al.py` | Diskte ölçülen fark (beyan dışı yazma, canlı izleme) · gölge git ile tur geri alma. |
| `ofis/devral.py` · `terminal.py` · `konsol.py` | Ajanın terminalini insan devralır (ConPTY) · bağımsız konsol. |
| `ofis/ekler.py` | Sohbete dosya/görsel: kökün `ekler/` klasörü, `[ek] ekler/ad` satırı, ad/boyut/yol kapıları; `paylas` (ajan `sohbete_yaz(ekler=…)`, lider `[ek] <yol>` satırı; kök dışı/gizli ret); GitHub'a ve disk ölçümüne girmez. Video/ses AKIŞLA (`/api/ek_akis`, 2 GB; telefondan da), öteki 20 MB; projede 200 MB üstü dosya günlük yedeğe girmez, `buyuk_atlandi` diye söylenir. |
| `ofis/gorsel.py` · `video.py` | Medya; codex aboneliğiyle görsel; para kilidi. ÜRÜN GÖRSELİ (08.10, ölçüldü): `gorsel_uret(referanslar=[ürün fotoğrafları])` → codex `--image`; şişe/etiket/kutu birebir. Referans alamayan üretici atlanır; `oran` (9:16/4:5/1:1). **Flow'da GÖRSEL ÜRETİLMEZ** (08.10 patron): resim ayarlı üretim tıklaması kapıda RET; beceri `gorsel` (`flow-gorsel` emekli). Gemini görseli yalnız agy etkileşimli kipte (`generate_image`; GPT'den yavaş ve zayıf). |
| `ofis/kurgu.py` · `medya/remotion/` | VİDEO KURGU (06.10, patron): yapay zekâ videosu Flow'da (kabin, `flow-video` becerisi); ajan `video_kurgula`ya PLAN yazar (sahne/yazı/altyazı/geçiş/müzik; 4 oran), ofis tek Remotion şablonuyla çizer ve ÖLÇER (ffprobe; siyah ekran, sessizlik, kare özeti, kapak) — ölçüm otomatik kanıt. ffmpeg ofisin evinde (`ev/araclar/ffmpeg`, ajan PATH'ine eklenir). Uzun araç 15 dk. 08.10 DÜZENLEME: sahnede `hiz`, `yerlesim` (bulanık dolgu)/`odak`, `filtre`; planda `sesler[]` (seslendirme; çalarken müzik `muzik_alcalt`), `muzik_bas`, `logo`, geçiş kayma/silme/yukarı; klip yetmezse çizmeden ret. Hazır video `video_islem.py` (medya_isle): `sahneler` (kesim + kare panosu), `kes`, `ses_ayir`, `sessizlik_kes`, `kare_ara` (RIFE v4.6, `ev/araclar/rife`). Beceri `video-duzenle`. |
| `ofis/medya_arac.py` · `medya_yardimci.py` | YEREL MEDYA (07.10, `medya_isle`; kredi harcamaz): görsel büyütme Real-ESRGAN (parça 128 sabit — oto/256'da çıktı SİYAH ve çıkış kodu 0, ölçüldü; siyah çıktı reddedilir; VİDEO büyütülmez: hızlı model yüzü mumlaştırıyor), altyazı Whisper large-v3-turbo (replik verilirse yazım replikten zaman sesten; uyum düşükse "ses repliği yanlış"), arka plan rembg birefnet-lite, `vokal_ayir` (UVR MDX-Net ONNX, torch yok; konuşmanın SDR'i −9,3 → +18,4 dB ölçüldü). Whisper/rembg ayrı ortamda `ev/araclar/medya-py` (sistem numpy'si yükselmesin). |
| `ofis/flow.py` | FLOW KATALOĞU (07.10, patron: "ölç, ileride güncellenecek"): gömülü tarayıcıdaki Flow'un modelleri/seçenekleri/kredileri ÜRETMEDEN ölçülür (`YASAK` düğme listesi; ölçüm patronun ayarını geri koyar ve döndüğünü ölçer), `ev/flow_katalog.json` + geçmiş + `flow_degisti` olayı/bildirimi; panel 24 sa'te bir tazeler (kabin açık + ofis boşken; ofis kabin AÇMAZ); `kabuk flow olc|goster`. Video/tasarım/reklam brifinginde TAM katalog, liderde TEK satır. |
| `ofis/kaynaklar.py` | Motorlardan gelenler: Claude/Codex hesabında ne varsa ajanlara da (ertelenmiş yükleme, ölçüldü +5k jeton/tur); eklentiler `--plugin-dir`, kendi MCP'ler (playwright hariç), kapatılan bağlayıcı `--disallowedTools`; kancalı eklenti sorulur; Codex'in kendi tarayıcıları kapalı; tarayıcı tek: gömülü. |
| `ofis/beceri.py` | Beceri deposu (`ev/beceriler`, aynı zamanda Claude eklentisi): GENEL, tek tek kapatılır; Claude'a `--plugin-dir`, Codex ve GEMİNİ evine (`~/.gemini/config/skills`) işaretli kopya; ajan `beceri_oner` ile kanıtlı TASLAK yazar, patron onaylar. Ofisin KENDİ becerileri kodla gelir (`ofis/hazir_beceriler/`: `reklam-kreatifi` istekten senaryo paketine, `flow-video`, `flow-gorsel`) ve depoya eşitlenir; patron kapatırsa kapalı, silerse bir daha gelmez. |
| `ofis/ayarlar.py` · `entegrasyon.py` · `web/ayarlar.js` | Ayarlar ekranı (⚙): tek okuma + İZİNLİ yazma, kural evinde · entegrasyon kartları (claude.ai bağlayıcıları `claude mcp list`, gh, vercel; bağla/kopar KOMUTU söylenir, giriş insanın) · takım başına bağlayıcı izni (lider izinliyi kola yazar, `lider.dagit` verir). |
| `ofis/karne.py` | KARNE (03.10): kapanan her iş `ev/karne.jsonl`'a (rol, zorluk, motor, model, ret); işin motoru ilk turda karne + limit dengesiyle seçilir (deneme payı, temiz oran, eşik), `gorev.motor_secimi`; çapraz kontrol (yapanın tersi inceler). Ayar `motor_secimi` (VARSAYILAN `ajan`: her ajanın sabit motoru, patron kararı 04.10 "Murat gibi"; `karne` yalnız bilerek), `capraz_inceleme` (açık). Lider planda ajanın motor/modelini görür. |
| `ofis/ekip.py` · `sablon.py` | Ekip önerisi (lider önerir, insan onaylar) · takım şablonları (9 hazır: mağaza, mobil, SaaS, web, bot, içerik, stüdyo, araştırma, bilgisayar + patronun kaydettikleri `sablon_ozel`). |
| ORGANİZASYON (05.10) | `/api/organizasyon` + panel: şirket ağacı ve takımın "⚙ Yönet"i AYNI uçlar; "Yeni ajan" (meslek kartı → katalog motor/model). Kurallar `kadro`da: `katalogdan_al`, `tasi` (açık işli/lider taşınmaz), `cikar` → ARŞİV (ad geri dönmez), `lider_yap`, `karakter`. Takım yalnız BOŞSA ya da "ajanlarıyla" silinir (açık iş varsa hiçbir şey). Yeni takım TEK AKIŞ (`/api/sablon/<ad>/onizleme` + `/api/takim/kur`: önce her şey denetlenir, sorun varsa HİÇBİR ŞEY kurulmaz). Ayrıntı günlükte (05.10). |
| `ofis/durum_tablosu.py` · `deger.py` | PANEL B (08.10): Durum panosu — her açık işin "nerede" satırı ölçülmüş kayıttan (seni/giriş/kredi/başka ajan/durdu/sıra), ajanlar, lidere giden sıra; "Bu hafta" değer özeti (biten/ilk seferde/geri dönen, puan, hesap başına jeton+kota). Seçenekli soru (`postane.secim_dogrula`, toplu kabul yalnız SORU). |
| `ofis/saglik.py` · `yetenek.py` · `denetim.py` · `baglayici.py` · `klasor.py` · `sartname.py` · `guncelleme.py` · `motor_karti.py` | Tıkanma teşhisi · yetenek envanteri · denetim kaydı · claude.ai bağlayıcıları · dış klasör kapısı · şartname kapısı (fable, araçsız) · otomatik güncelleme · motor kartı. |
| `ofis/yedek.py` · `depo.py` · `sifirla.py` | Günlük ZIP (bilgisayar + Drive) · gizli GitHub (kod + defterin metni, üç kapı), `metinden_defter` · GÜVENLİ SIFIRLAMA (08.10): önce liste → yedek + doğrulama → patron `SIFIRLA` yazarsa siler; kadro/ayar/hesap/giriş/beceri/patron dosyası ve EN YENİ yedek kalır; güncelleme kilidiyle çakışmaz (`kabuk sifirla`, Ayarlar > Yedek). |
| `ofis/panel.py` · `web/` | Panel: pano yerleşimi (sütun→yığın→sekme, `agentofis.yerlesim.v2`), ofis haritası, terminal panoları, takım sohbeti, kod/diff, kabin, hesap panosu, kuyruk. |
| `ofis/kabuk.py` | Komut satırı (~30 komut): kur · ise-al · konus · hedef · devam · not · durdur · iptal · ekip · hesap · kullanim · saglik · yedek · geri-al · guncelle · panel … |
| `testler/` | Duman sınamaları (jeton yakmaz), deneme seti (`deneme.py`, gerçek motor), motor matrisi (`matris.py`), yük ölçümü, hafıza isabeti. |

## Temel davranışlar (kısa)

- **Kanıt kapısı:** kanıtsız iş kapanmaz. Kanıt bir defter kaydıdır, iş
  ilerledikçe eklenir. Lider kanıtla birlikte **ofisin disk ölçümünü** görür
  (ajanın sözü ile ayrı başlıkta). Çelişen kanıt geri gönderilir.
- **Onay kapısı (tek kapı):** her araç çağrısı `izin_sor`dan geçer (Claude
  kancası, Codex app-server onayı). Yerleşik dosya araçları serbest; kabukta
  silme · gönderim · yayın · sistem sorulur; bağlayıcıda okuma serbest,
  tanınmayan sorulur; onay "bir kez" ya da "bu iş boyunca".
  **Patronun sözü izindir:** mesajında açıkça istediğin push/deploy o iş
  için sorulmaz (kartta görünür, kaldırılabilir); para ve silme her zaman
  sorulur; kalıcı izin yalnız insandan (`kabuk izin` ya da onay kartında
  **"Bu projede hep"** — 06.10: kart TAM komutu / TAM araç adını kalıcı
  izne çevirir, kural `izin.karttan_izin`; para/silme/şifre/masaüstü ve çok
  satırlı komut çevrilmez; tanınmayan bağlayıcı aracı yalnız ADIYLA açılır,
  lider bunu plana yazamaz). Panelde günlük sayaç (`izin.gun_sayaci`).
  Kabuk izni SIKI eşleşir (gevşek eşleşme yalnız tarayıcı tıklamasında).
  **Üretim kredisi (07.10, patron: "videoyu üretmeden önce bana gelsin"):** kredi sitesinde (Flow) üretim tıklaması / Enter / büyütme indirmesi sorulur ("bu projede hep" açmaz; 11.10: patron mesajında SINIR yazarsa — "150 krediye kadar" — isteğin toplamı o sınıra kadar sorulmaz, ajan durmaz, `kredi_izni.py`); kart üretim ayarını (ekrandan) gösterir; "bu iş boyunca" onayı o işin üretimlerini açar (tarayıcı kapısı bu kapsamı o güne dek tanımıyordu, her tıklamada yeniden soruyordu). Ölçülmüş katalogda 0 kredi olan resim üretimi (taslak kareler) sorulmaz. Ajanın `onay_iste(kredi, uretim)` paketi onaylanınca o kadar üretim tıklaması sorulmaz (çift onay yok); onay ajanın turu sürerken gelirse iş incelemeye gitmez (`onay_geldi`). `duman_kredi`.
- **Tarayıcı:** her işte serbest; riskli tıklama ve beyan edilmemiş site
  (daraltılmış işte) sorulur; sayfadaki gizli talimat işaretlenir.
- **Zincir:** limit/oturum düşünce aynı turda sıradaki hesaba devreder, devir
  paketiyle kaldığı yerden sürer; pencere eşikteyse (işçi %80/%85, lider
  %95/%97) hesap önceden sona alınır.
- **Tur içi not ve Durdur:** defter üzerinden; Claude stdin/interrupt, Codex
  steer/interrupt. Durdurulan iş arıza değil, Sürdür aynı oturumdan devam.
- **Ret freni (09.10):** 3. retten sonra iş ajana dönmez; duraklar, patrona seçenekli soru (kabul / bir tur daha / iptal), cevap uygulanır (`lider.RET_FRENI`, `tahta.insan_kabul`). Lider eksiklerin HEPSİNİ bir kerede yazar. **Sıra:** yeni istek önceki işin bitmesini beklemez (`konus(ara_ver=)`).
- **Genel kanal:** çok takımlı ofiste "Tüm ofis"ten `@TAKIM` o takımın liderine; adres yoksa ofis takım ÖNERİR (model yok), insan seçer.
- **Takım sohbeti (09.10, KARTLAR):** her istek TEK kart (`takim.kartlar`, `/api/kartlar`): tek durum, canlı satır, sonuç, son dosyalar, kararlar kartın içinde, ayrıntı katlı; ofis notları sohbete girmez; ajanın yanında SAHİBİNİN turundan ölçülen model, Tüm Ofis'te takım etiketi, geliştirme işinde kurulum durumu. Adres yok → lider; `@ajan` → işi varsa not, boşsa soru; `@ajan iş:` → lider planlar ama sahip o ajan.
- **Bağlam (06.10):** her tur `baglam` {dolu, sınır, oran} bildirir (son çağrı; sınır motorun kendi bildirimi, Claude terminal kipinde arka kipte öğrenilen); panel ajan başlığında %; aynı işte %80'i geçince sonraki tur devir paketli TEMİZ oturum (`oturum_tazelendi`). Sınır bilinmezse karar yok.
- **Güncelleme penceresi (06.10):** model/CLI yalnız `guncelleme.mesgul` boşken (canlı süreçli `calisiyor` iş, sıradaki mesaj); incelemedeki iş ve ölü süreç kaydı engellemez; insan CLI onayı meşgulken ret.
- **Hafıza satırı (06.10):** işçi bitirirken ZORUNLU `BILGI: konu -> değer (nereden)` ya da `HAFIZA: yok` yazar; ofis `bilgi_onerisi` kaydeder (hafızaya doğrudan GİTMEZ), lider kanıtla doğrulayıp kendi `BILGI:` satırıyla yazar; `hafiza_adimi` işçinin satırını da sayar.
- **Hafıza:** patron bilgiyi/dersi **Yanlış** diye kapatır (geri gelmez), panelde arama ve geri bağ sayısı; bilgi kapısı (insanın yazdığını ajan devremez), `[[bağ]]`,
  kurallar her brifinge; lider incelemede `BILGI:` yazar (yalnız kapanan işte): değer, TUZAK, kök sebep, patron tercihi ya da `HAFIZA: yok` (adım `hafiza_adimi` olayıyla sayılır); hata dolanmasını anlatan ajan yazısı patrona `hata_suphesi` olarak bildirilir.
- **Yedek:** günlük ZIP (bilgisayar + Drive), gizli GitHub (defter metin
  olarak); gölge depoyla tur geri alma.

## Güncel durum (08.10.2026)

- **Fazlar:** F0–F3 KAPANDI (güvenilirlik, motor eşitliği Claude+Codex,
  güvenlik). Açık: **F4** model seçimi + hafıza · **F5** gece otopilotu,
  bildirim, **sesli komut** · **F6** şirket yapısı, yeni motorlar · **F7**
  medya · **F8** panel · **F9** masaüstü · **F10** kabul. Ayrıntı `PLAN.md`.
- **Codex ajanı kapı varken tam erişimle** koşar (workspace-write'ta `git add`/push düşüyordu); riskli adım kapıda.
- **TEMİZ BAŞLANGIÇ (08.10, patron: "gerçek iş yapmadık, denemeler yaptık"):** deneme izleri `kabuk sifirla` ile silindi (1.431 kalem; yedek `AgentOfis-yedek-20261008-021420-sifirlama-oncesi.zip`). "Her şey gerçek": sahte motor ve örnek ofis (`testler/ornek_ofis.py`) yalnız sınamada; ilk açılış (`baslat.bat`) GERÇEK ofis kurar (Ofisim + GENEL + lider arda/Opus); deneme kipi ve arka plan kipi kaldırıldı.
- **Gerçek terminal kipi** tek kip (ajan panosu = gerçek terminal; lider de gerçek terminalde, her tur temiz).
- **Aşama 1 (gerçek iş kalitesi):** `testler/gercek_set.py` patron gibi sohbetten iş verir (18 iş); 01.10'da 18'in 18'i iki motorda geçti, 08.10'da G01 Gemini ile gerçek terminalde geçti. Gündüz koşulur (gece görevi kapalı). Kural: gerçek motorla geçmeyen "bitti" değil. Ayrıntı günlükte.
- **AYRIM (01.10, uygulandı):** ofisin evi `AgentOfis\ev`, Ofisim `Masaüstü\Ofisim`. Ölçüldü: ajan artık ofisin anayasasını GÖRMÜYOR (önce ilk satırını okuyordu). Açık: `.playwright-mcp/` proje kökünde (ölçmeden taşınmadı).
- **ÇOK TAKIM (01.10, patron: "ofis sadece tanım"):** bir işin takımı TEK kural (`Orkestra.isin_takimi`/`takimin_isi`, `Kadro.gorevin_lideri`); halka `kanat_id` süzgeci alır (sohbet kendi takımıyla koşar, Sürdür bütün ofis); iş takımsız açılmaz (veri göçü 2). Her yeni özellik çok takımla sınanır (`duman_cok_takim.py`).
- **GÖMÜLÜ TARAYICI (02.10):** tarayıcı gereken işte kabin kapalıysa ofis AÇAR (yalnız çalışan panel); başsız Chrome normal kimlikle; Chrome gibi sekmeler; sınama kabini ayrı kapıda (`OFIS_KABIN_KAPI`). Motorların KENDİ Chrome eklentileri KAPALI (Claude `--no-chrome`). İki motor aynı tarayıcı işinde temiz. Ayrıntı günlükte.
- **F5 "ben yokken" altyapısı (01.10):** kuyruk + dönüş raporu, kesintiden devam, masaüstü bildirimi, zamanlayıcı — dördü canlı (8911, gerçek motor) ölçüldü. Kalan F5: telefon, onay yorgunluğu (E80), bağlam göstergesi, ses (en son).
- **Güncelleme hemen:** 30 dakikada bir ölçer, uyguladıktan sonra yeniden
  ölçer (`olc_ve_ilerle`). Deneme turu gerçek terminalde.
- **Sınamalar:** **5642/5642** (11.10; 110 dosya; tam takım ÇIKIŞ KODUYLA koşulur — kod 3 = artık klasör) + gerçek set (`gercek_set.py`, her gece 03:30). Deneme seti 15/15
  (Claude ve Codex, işçi+lider).
- **MALİYET (03.10, `testler/carpan.py`):** basit iş ofiste doğrudan Claude'un ~1,6–1,8×'i; Claude önbelleği 5 dk; ret ölçüte bağlı (`lider.ret_dayanagi`); triyaj+plan tek tur; KARMA (karne + çapraz kontrol) 20 işte 19/20, Claude payı %40 az. Yalın lider ve `--fork-session` denendi, geri alındı. Tam metin: günlük "08.10 ANAYASADAN TAŞINAN: MALİYET".
- **Kalan işler:** `PLAN.md` "00. KALAN İŞLER — 08.10" (A–F; ses, görünüş, uygulama en son).

## Kalıcı dersler (ilkeler)

- **Sistem sağlıklı görünürken yanlış çalışması** en tehlikeli hata
  sınıfıdır; projenin karşı kurulduğu şey budur.
- **Ölçtüğün şey, baktığın yer kadar geçerlidir.** Bir yolun kapalı
  olduğunu ölçmek, bütün yolların kapalı olduğunu göstermez.
- **Ölçüm aracının kendisi de ölçülmeli.** Geçen test ölçtüğünü kanıtlamaz;
  koparılınca ateş ederse kanıtlar (mutasyon). Çöken test kalandan kötüdür.
  Testin kurduğu sahne ölçmek istediği sınıra ulaşmalı.
- **Bir iş türünü / motoru koşturmadıysan onun için hiçbir şey
  bilmiyorsun** — test sayısı ne olursa olsun.
- **Sessizce yok sayılan ayar, ayar değildir.** Fabrika alan parça onu
  çağırdığı her parçaya geçirir. Geniş `except` bu hatanın en kolay yolu.
- **İki kopyadan biri düzeltilir, öteki unutulur** → kural tek yerde.
- **Yanlış gösteren gösterge, göstergesizlikten kötüdür.** Uydurmaz;
  bilmediğine "BİLİNMİYOR" der; ölçülmüş 0 ile ölçülemeyen `None` ayrıdır.
- **Görmeden karar vermek tahmindir** → lider klasörü, rolleri,
  bağlayıcıları, medya/para durumunu, künyeyi görür.
- **Rica ile duran kural, kural değildir** → tam şablon + örnek, ya da yapı.
- **Fazladan kilit bedava değildir**; bedeli ölçülmemiş güvenlik önlemi
  ölçülmemiş risktir.
- **Yetki insandan gelir, dağıtım liderden** (klasör, kadro, kabin, para).
- **Süreç sınırını geçen her yol MUTLAK olmalı** (hayalet veritabanı).
- **Ölçüm aracı, ölçtüğü şeyden pahalı olmamalı.**

## Teknik tuzaklar (Windows ve bu depo)

- Konsol cp1254: `print`te `→` patlar; dosyaya `encoding="utf-8"`.
- Kod içi adlar/yorumlar Türkçe ve ASCII (şapkasız); docstring **neden**
  anlatır.
- **Satır sonları dosyaya göre farklı** (CRLF/LF karışık): özgün hâl
  korunur. **`sed -i` kullanılmaz** (CRLF'i siler). Yama: Python betiği
  dosyaya yazılır, `newline=""` ile okunur, her değişiklik `assert
  s.count(a)==1` ile uygulanır. Bash heredoc içinde `\n` gerçek satır
  sonuna döner — betik Write aracıyla yazılır.
- Yerinde yazma atomik olmalı (`'w'` önce dosyayı boşaltır).
- `SahteMotor.__init__` `mcp_konusur`'u örnek değişkeniyle ezer:
  `SahteMotor(mcp_konusur=True)` ile verilir.
- MCP sunucusu betik olarak koşar: işlev içi göreli içe aktarma
  (`from . import`) patlar; mutlak `from ofis import`.
- `claude` npm `.CMD`'si çok satırlı argümanda bayrakları düşürür:
  `claude.exe` doğrudan (`_calistirilabilir_bul`).
- `Ofis.proje_ac` olmayan projeyi YARATIR: ölçüm betiğinde ad doğru olmalı.
- Codex sandbox'ının açtığı `.pytest_cache` kullanıcıya kapalı olabilir
  (yönetici izni); yedek ve ölçüm onu atlar.
- Mutasyon koşularında `PYTHONDONTWRITEBYTECODE=1` (bayat `.pyc` tuzağı).
- **Her `subprocess` çağrısı `creationflags=PENCERE_YOK`** (`ofis.surec`): konsolsuz
  koşarken her `git`/`npm` ekrana pencere açar (patron oyunda gördü, 04.10;
  o seferki kaynak Claude Code eklentisiydi). `duman_pencere.py` kaynaktan tarar.
- **`.playwright-mcp/` SİLİNMEZ**: rakip dökümleri/kareleri orada ve yedeğe
  girmiyor (30.09'da ekran görüntüsü temizliğiyle silindi, geri gelmedi).
  Geçici ekran görüntüsü tek tek dosya adıyla silinir; kalıcı rakip dökümü
  `docs/rakip/`e (metin) yazılır.
- Ortam: Python 3.12 (ek paketler: `pypdf` belge, `pywebpush` telefon bildirimi) · ffmpeg 9.0.2 `ev/araclar/ffmpeg` · Real-ESRGAN ncnn `ev/araclar/realesrgan` · medya ortamı `ev/araclar/medya-py` (faster-whisper 1.2.1, rembg 2.0.85; modeller `ev/araclar/modeller`) · Remotion 4.0.533 `medya/remotion` (`npm install`, node_modules depoya girmez) · `claude`, `codex` CLI'ları npm'de; kullanıcının öteki
  kodu `C:\Users\pc\Desktop\JarvisForge` (çalışan parça varsa ödünç al).

## Sınamayı koşturmak

```
python testler/duman_<ad>.py                       # tek dosya
for f in testler/duman_*.py; do python "$f"; done  # tam takım (bash)
python testler/deneme.py --hizli --kuru            # deneme seti, $0
python testler/deneme.py --hizli                   # gerçek motor (kota!)
python testler/matris.py --kuru                    # motor matrisi, $0
```

Sınama kabini her süreçte işletim sisteminden BOŞ kapı alır (07.10: sabit 9399 canlı gösterinin kapısıydı, sınama canlı kabinin indirme ayarını bozdu). Tam takımdan sonra `%TEMP%`'te `ofis-*` artığı kalmamalı; ofisin gerçek
evi değişmemeli (bekçi çıkış kodu 3 verir).
