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
bilgi projeye `olgu`/`karar` olarak girer, koda değil. `veri/ornek_ofis.py`
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
| **Ofis kendini geliştirir, kendini KURMAZ** | Ajan kendi kaynağına (`ofis/`) yazamaz; teslim eder, insan inceler ve kurar. |
| **Ajanlar ortak kökte** (yazma alanı gerçek yoldur) | Yazma kilidi ancak çakışma fiziksel olarak mümkünse anlamlı. |
| **Ürünü (Muratify) almıyoruz** | Rakip olarak izleniyor; bkz. günlük "RAKİP" bölümleri. |

### Hesaplar ve model politikası

- **Hesaplar:** Claude **Max 5x** · ChatGPT **Plus** (şu an; **Pro 5x'e geçilecek**,
  henüz alınmadı — tasarım Plus'a sabitlenmez; ofisin codex evi:
  omerjob34). `codex2` hesabı kayıp (kapalı). Gemini defterden çıkarıldı
  (24.09); Pro alınınca eklenti olarak geri takılır.
- **Kullanıcı API değil ABONELİK kullanıyor:** maliyet **kota diliyle**
  anlatılır (5 saat / 7 gün penceresi yüzdesi), dolar yalnız API hesabında.
- **fable:** YALNIZ KAPI (şartname · ikinci ret sonrası hakem · şüpheli
  inceleme), tavanlı, hiçbir kademede yok. Fable penceresi %80'de kapanır.
- **astra:** otomatik hiçbir yolda YOK (codex tur başına tavan uygulayamıyor,
  ortak havuzdan yer).
- **Kademe (kod değil ayar, `roller.kademe_haritasi`):**
  claude hızlı haiku · standart sonnet · güçlü opus;
  codex hızlı gpt-6-luna · standart gpt-6.1-sol · güçlü gpt-6.1-sol
  (30.09 otomatik güncelleme).
- **Zorluk → model + efor:** kolay→düşük · orta→normal · zor→yüksek ·
  çok_zor→çok_yüksek (gerekçe zorunlu). `max` YOK. Panelde efor düğmesi.
- **Model açıkça verilir** (verilmeyen iş hesabın varsayılanına düşer,
  ölçüldü: on kat maliyet).
- **Model/CLI güncellemesi otomatik** (`guncelleme.py`): aynı ailenin yeni
  nesli, takma adın yeni hedefi, CLI sürümü → deneme turu geçerse uygulanır,
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
  masaüstü onaysız sürülmez. Gizli (stealth) modellere yalnız herkese açık
  içerik gider.
- **GitHub:** yalnız gizli `owmerk-code/AgentOfis`, yalnız
  `python -m ofis.kabuk yedek github` ile. Yeni depo/uzak/hesap sormadan yok,
  asla herkese açık değil, sır ve müşteri verisi yok.
- Mağaza/reklam/sosyal hesaplar (Shopify, Meta…): **altyapı HAZIR olur**
  (Ayarlar > Entegrasyonlar'da kart + Bağla), bağlamayı kullanıcı gerektiğinde
  kendisi yapar (02.10 kararı; "ertelendi" diye hatırlatılmaz). Para/yayın
  eylemleri yine kapıda sorulur. Tauri F9'u bekler.
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
PROTOKOL    ofis MCP sunucusu (stdio JSON-RPC, 16 araç)
ÇEKİRDEK    kadro · DAG tahta · yazma kilidi · kanıt kapısı · karar günlüğü
            orkestra (halka) · lider (3 kapı) · sohbet (ön kapı) · takım
BELLEK      olay · olgu (çift-zamanlı) · bilgi/kural/ders · brifing K1–K4
MOTORLAR    claude (stream-json) · codex (app-server) · sahte · [gemini dosyada]
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
| `ofis/roller.py` | 19 rol / 5 kategori; rol = sözleşme (tür · izin · MCP · kanıt türü · ölçüt şablonu · kademe · bütçe). Kademe/efor haritaları. |
| `ofis/tahta.py` | Görev, DAG, yazma kilidi (kira+nabız), kanıt kapısı, CAS, `iptal_et`, `medya_hedefi`, kök-göreli alan doğrulama. |
| `ofis/bellek.py` | Olgular, karar günlüğü, bilgi kapısı (`bilgi_ekle`), `[[bağ]]`, kurallar (yalnız insandan). |
| `ofis/brifing.py` | Dört katmanlı brifing (K1 kimlik/rol · K2 künye+kural+olgu · K3 kararlar · K4 iş+kanıt+not), devir paketi. |
| `ofis/koltuk.py` | Seat Runner: kilit → brifing → motor → olaylar → nabız → kanıt → inceleme. Zincir/devir, kaçak freni, not/durdurma kanalı, disk ölçümü, gölge anlık, kabin izleme. |
| `ofis/lider.py` | Fan-out · ayrık alan · kanıta karşı inceleme (temiz bağlam, salt okunur, yapan inceleyemez); ret ≥2'de kapı modeline yükseltme; lider zinciri. |
| `ofis/orkestra.py` | Halka (`tik`/`kos`): planlama JSON'u + kapılar ("ret öğretir"), paralel atama (rezerv), kabin kiralama, danışma teslimi. |
| `ofis/sohbet.py` | Liderin ön kapısı: triyaj (cevap/kendi/dağıt/kadro), ofis özeti, rapor, cevap akışı (`AkisYazici`). |
| `ofis/takim.py` | Takım sohbeti: `@ajan` yönlendirme (lider · not · soru · `iş:`), tek akış. |
| `ofis/kuyruk.py` | İş kuyruğu (F5/1): lidere giden her panel mesajı sıraya girer (`kuyruk` tablosu, kalıcı); panel işçisi sırayı boşaltır, düşen iş sırayı durdurmaz; seri bitince MODELSİZ dönüş raporu. |
| `ofis/surec.py` · `toparla.py` | Kesintiden devam (F5/2): iş, koşturan sürecin kimliğini (`pid:oluşma`) taşır; panel açılışında ölü sürecin işi `kesinti` ile bırakılır ve AYNI oturumdan sürer; yaşayan/kimliksiz kayda ve PATRONU BEKLEYEN işe dokunulmaz; sürdürülen isteğin yarım mesajı ofisin modelsiz cevabıyla kapanır. Canlı iki çökmede ölçüldü. |
| `ofis/bildirim.py` | Masaüstü bildirimi (F5/3): panel defteri izler; onay, patrona soru, lider cevabı, dönüş raporu, kesinti, sıra düşüşü → Windows bildirimi (PowerShell+WinRT, `-EncodedCommand`); yalnız gerçek panel açar, ayar `bildirim`. |
| `ofis/zamanlayici.py` | Zamanlayıcı (F5/4): sohbetten kurulur (triyaj `karar=zamanla`, saati ofis doğrular ve cevabı ofis kurar); gunluk/haftalik/bir_kez/aralik; vakti gelen iş kuyruğa; kaçırılan birikmez, bir kez koşar. |
| `ofis/postane.py` | Soru/onay, patronun notu (`NOT_KURALI`), imza/kapsam ile onay eşleştirme. |
| `ofis/danisma.py` | Ajana sorulan soruyu teslim eder (araçsız, salt okunur); cevaplanamazsa insana yükseltir. |
| `ofis/mcp_sunucu.py` | Ofis MCP: durum · kanit_ekle · karar_yaz · sohbete_yaz · soru_sor · onay_iste · bilgi_yaz · gorev_ac · gorsel_uret/iste · video_uret/durum/iste · izin_sor (kanca) · giris_iste. Kimlik ORTAMDAN gelir. |
| `ofis/motor/tui.py` | GERÇEK TERMİNAL KİPİ: iç motoru (claude/codex) ConPTY'de gerçek CLI olarak koşturan sarmalayıcı; brifing yapıştırılır, olaylar CLI'ın oturum dosyasından okunur, terminal turlar arası açık kalır. Ayar `terminal_kipi` (`arka`/`gercek`); tek kural `kipe_gore` (işçi + lider; tavan gereken tur arkada). |
| `ofis/kanca.py` | Gerçek terminal (TUI) kancası: CLI'ın her araç çağrısını arka plan kipindeki AYNI kapıya sorar; hata = deny; `--oz-sinama`. |
| `ofis/izin.py` | Patronun ACIKCA istedigi riskli eylem (push, deploy) sorulmaz: lider planda patronun sozunden KELIMESI KELIMESINE alintiyla izin yazar, ofis sinifi olcer, olumsuz cumleyi reddeder; is basina ve kalici (insan). Para ve silme izinle acilmaz. |
| `ofis/riskli.py` | Riskli eylem ölçütü (geri alınabilir mi · dışarı çıkıyor mu · para var mı) + sert durak; kabuk kuralları; araç adı polaritesi (okuma serbest, tanınmayan sorulur); şifre/kart alanı. |
| `ofis/tarayici.py` · `tarayici_kapi.py` | Playwright MCP'yi bağlar (varsayılan serbest, riskli tıklama vekilde sorulur, sayfadaki gerçek adı okur); kabin CDP. |
| `ofis/kabin.py` | Panelin içindeki paylaşılan başsız Chrome (kare akışı), öğe seçici. |
| `ofis/giris.py` | Giriş isteği: şifre ajana geçmez, insan kabinde girer, iş onun oturumuyla sürer. |
| `ofis/motor/tip.py` | Motor sözleşmesi: olay akışı, bayraklar, `durum_notu`, `limit_oku`, `TurKanali`, `SurecKafesi` (Job Object), `etkilesimli_komut`. |
| `ofis/motor/claude.py` · `codex.py` · `sahte.py` · `gemini.py` | Adaptörler. Claude: `.exe` doğrudan, `--permission-prompt-tool` kancası. Codex: app-server (onay kapısı, steer, interrupt), `exec` yalnız görselde. |
| `ofis/zincir.py` · `hesap.py` · `plan.py` | Nöbet zinciri (hesap üzerinde, önceden geçiş), çoklu hesap (anahtar referansla), abonelik planı. |
| `ofis/motor_saglik.py` · `kullanim.py` · `tavan.py` · `butce.py` | Oturum/kota hafızası; hesap pencereleri (tur koşmadan okunur); kaçak freni + jeton tavanı; Fable kapı payı. |
| `ofis/degisim.py` · `geri_al.py` | Diskte ölçülen fark (beyan dışı yazma, canlı izleme) · gölge git ile tur geri alma. |
| `ofis/devral.py` · `terminal.py` · `konsol.py` | Ajanın terminalini insan devralır (ConPTY) · bağımsız konsol. |
| `ofis/ekler.py` | Sohbete dosya/görsel: kökün `ekler/` klasörü, `[ek] ekler/ad` satırı, ad/boyut/yol kapıları; `paylas` (ajan `sohbete_yaz(ekler=…)`, lider `[ek] <yol>` satırı; kök dışı/gizli ret); GitHub'a ve disk ölçümüne girmez. |
| `ofis/gorsel.py` · `video.py` | Medya; codex aboneliğiyle görsel; para kilidi. |
| `ofis/kaynaklar.py` | Motorlardan gelenler: Claude/Codex hesabında ne varsa ajanlara da (ertelenmiş yükleme, ölçüldü +5k jeton/tur); eklentiler `--plugin-dir`, kendi MCP'ler (playwright hariç), kapatılan bağlayıcı `--disallowedTools`; kancalı eklenti sorulur; Codex'in kendi tarayıcıları kapalı; tarayıcı tek: gömülü. |
| `ofis/beceri.py` | Beceri deposu (`ev/beceriler`, aynı zamanda Claude eklentisi): GENEL, tek tek kapatılır; Claude'a `--plugin-dir`, Codex evine işaretli kopya; ajan `beceri_oner` ile kanıtlı TASLAK yazar, patron onaylar. |
| `ofis/ayarlar.py` · `entegrasyon.py` · `web/ayarlar.js` | Ayarlar ekranı (⚙): tek okuma + İZİNLİ yazma, kural evinde · entegrasyon kartları (claude.ai bağlayıcıları `claude mcp list`, gh, vercel; bağla/kopar KOMUTU söylenir, giriş insanın) · takım başına bağlayıcı izni (lider izinliyi kola yazar, `lider.dagit` verir). |
| `ofis/karne.py` | KARNE (03.10): kapanan her iş `ev/karne.jsonl`'a (rol, zorluk, motor, model, ret); işin motoru ilk turda karne + limit dengesiyle seçilir (deneme payı, temiz oran, eşik), `gorev.motor_secimi`; çapraz kontrol (yapanın tersi inceler). Ayar `motor_secimi` (VARSAYILAN `ajan`: her ajanın sabit motoru, patron kararı 04.10 "Murat gibi"; `karne` yalnız bilerek), `capraz_inceleme` (açık). Lider planda ajanın motor/modelini görür. |
| `ofis/ekip.py` · `sablon.py` | Ekip önerisi (lider önerir, insan onaylar) · takım şablonları. |
| `ofis/saglik.py` · `yetenek.py` · `denetim.py` · `baglayici.py` · `klasor.py` · `sartname.py` · `guncelleme.py` · `motor_karti.py` | Tıkanma teşhisi · yetenek envanteri · denetim kaydı · claude.ai bağlayıcıları · dış klasör kapısı · şartname kapısı (fable, araçsız) · otomatik güncelleme · motor kartı. |
| `ofis/yedek.py` · `depo.py` | Günlük ZIP (bilgisayar + Drive) · gizli GitHub (kod + defterin metni, üç kapı), `metinden_defter`. |
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
  sorulur; kalıcı izin yalnız insandan (`kabuk izin`).
- **Tarayıcı:** her işte serbest; riskli tıklama ve beyan edilmemiş site
  (daraltılmış işte) sorulur; sayfadaki gizli talimat işaretlenir.
- **Zincir:** limit/oturum düşünce aynı turda sıradaki hesaba devreder, devir
  paketiyle kaldığı yerden sürer; pencere eşikteyse (işçi %80/%85, lider
  %95/%97) hesap önceden sona alınır.
- **Tur içi not ve Durdur:** defter üzerinden; Claude stdin/interrupt, Codex
  steer/interrupt. Durdurulan iş arıza değil, Sürdür aynı oturumdan devam.
- **Genel kanal:** çok takımlı ofiste "Tüm ofis"ten `@TAKIM` o takımın liderine; adres yoksa ofis takım ÖNERİR (model yok), insan seçer.
- **Takım sohbeti:** adres yok → lider; `@ajan` → işi varsa not, boşsa soru;
  `@ajan iş:` → lider planlar ama sahip o ajan.
- **Hafıza:** patron bilgiyi/dersi **Yanlış** diye kapatır (geri gelmez), panelde arama ve geri bağ sayısı; bilgi kapısı (insanın yazdığını ajan devremez), `[[bağ]]`,
  kurallar her brifinge; lider incelemede `BILGI:` yazar (yalnız kapanan işte): değer, TUZAK, kök sebep, patron tercihi ya da `HAFIZA: yok` (adım `hafiza_adimi` olayıyla sayılır); hata dolanmasını anlatan ajan yazısı patrona `hata_suphesi` olarak bildirilir.
- **Yedek:** günlük ZIP (bilgisayar + Drive), gizli GitHub (defter metin
  olarak); gölge depoyla tur geri alma.

## Güncel durum (29.09.2026)

- **Fazlar:** F0–F3 KAPANDI (güvenilirlik, motor eşitliği Claude+Codex,
  güvenlik). Açık: **F4** model seçimi + hafıza · **F5** gece otopilotu,
  bildirim, **sesli komut** · **F6** şirket yapısı, yeni motorlar · **F7**
  medya · **F8** panel · **F9** masaüstü · **F10** kabul. Ayrıntı `PLAN.md`.
- **Son işler:** liderin cevabı panelde akıyor; takım sohbeti (`@ajan`) ve
  kendi sütunu; "Ajanlar kabinde" (tarayıcılı tek iş panelde canlı).
- **Codex ajanı kapı varken tam erişimle** koşar (workspace-write'ta `git add` bile yapamıyordu, push sandbox kullanıcısı yüzünden düşüyordu); riskli adım kapıda.
- **Gerçek terminal kipi** kuruldu ve panelde (üst çubuk anahtarı, ajan panosu = gerçek terminal); lider de gerçek terminalde (her tur temiz); varsayılan hâlâ `arka`.
  30.09 düzeltmeleri: brifing kopyası ajan başına ofis evinde (ortak kökte
  `BRIFING.md` YOK), yapıştırmanın ardına elle yazılan sahip satırı, güven
  sorusu ekrana bakarak, codex oturum dosyası tur işaretiyle.
- **Aşama 1 (gerçek iş kalitesi) sürüyor:** `testler/gercek_set.py` patron gibi
  sohbetten 12 iş verir; gece 03:30 iki motor (`gece_kos.py`). 30.09: codex
  14 işin 14'ü iki motorda geçti (01.10; G13 Excel, G14 form+patron izni dahil); tek koşuda claude 13/14, codex 12/14 (kalanlar düzeltildi, yeniden geçti). Set 18 işe çıktı (not, durdur/sürdür, Word, proje); 01.10 tek koşuda claude **17/18** (kalan G15 tek savunulabilir ret), codex **14/18** (4 kök sebep düzeltildi, dördü yeniden geçti) → 18 işin 18'i iki motorda. Codex haftalık eşiği dolunca `gercek_set.py --kota-esigi 0.95` (yalnız geçici ofiste). Patronun GERÇEK ofisinin kopyasında (`testler/ofis_kopyasi.py`, lider demir/Opus) 4/4 iş bitti. Liderin turları varsayılan ARKA kipte (`lider_terminal_kipi`), işçi gerçek terminalde; basit iş ~70–80 sn. Gece görevi DEVRE DIŞI (PC gece kapalı), set gündüz koşulur. Kural: gerçek motorla geçmeyen "bitti" değil.
- **AYRIM (01.10, uygulandı):** ofisin evi `AgentOfis\ev`, Ofisim `Masaüstü\Ofisim`. Ölçüldü: ajan artık ofisin anayasasını GÖRMÜYOR (önce ilk satırını okuyordu). Açık: `.playwright-mcp/` proje kökünde (ölçmeden taşınmadı); kapı satır içi Python silmesini görmüyor.
- **ÇOK TAKIM (01.10, patron: "ofis sadece tanım"):** bir işin takımı TEK kural (`Orkestra.isin_takimi`/`takimin_isi`, `Kadro.gorevin_lideri`); halka `kanat_id` süzgeci alır (sohbet kendi takımıyla koşar, Sürdür bütün ofis); iş takımsız açılmaz (veri göçü 2). Her yeni özellik çok takımla sınanır (`duman_cok_takim.py`).
- **GÖMÜLÜ TARAYICI (02.10):** ajan tarayıcı gereken işe başlarken kabin kapalıysa ofis AÇAR (yalnız çalışan panel, `KABIN_ACICI`); "ajanlar burada" varsayılan açık; başsız Chrome normal kimlikle (Google "HeadlessChrome"u engelliyordu); adres çubuğu Chrome gibi arar; Chrome gibi SEKMELER ve Google ile açılış; önceki oturumdan kalan eski ayarlı kabin açılışta kapanır; sınama kabini ayrı kapıda (`OFIS_KABIN_KAPI`). Motorların KENDİ Chrome eklentileri ofiste KAPALI (Claude `--no-chrome`: etkileşimli kipte patronun kişisel Chrome'unu süren 21 araç geliyordu; codex evinde eklenti yok). İki motor aynı tarayıcı işinde ölçüldü: ikisi de temiz (yazma `browser_type`, tıklama `browser_click`, `browser_evaluate` yalnız okuma).
- **F5 "ben yokken" altyapısı (01.10):** kuyruk + dönüş raporu, kesintiden devam, masaüstü bildirimi, zamanlayıcı — dördü canlı (8911, gerçek motor) ölçüldü. Kalan F5: telefon, onay yorgunluğu (E80), bağlam göstergesi, ses (en son).
- **Güncelleme hemen:** 30 dakikada bir ölçer, uyguladıktan sonra yeniden
  ölçer (`olc_ve_ilerle`). CLI güncellemesinin deneme turu, ofis gerçek terminal kipindeyse terminalde de koşar (30.09).
- **Sınamalar:** **4220/4220** (04.10; 65 dosya; tam takım ÇIKIŞ KODUYLA koşulur — kod 3 = artık klasör) + gerçek set (`gercek_set.py`, her gece 03:30). Deneme seti 15/15
  (Claude ve Codex, işçi+lider).
- **MALİYET (03.10, `testler/carpan.py`):** basit iş ofiste doğrudan Claude'un **~1,6–1,8×**'i (sabah 3,9×). Claude önbelleği 5 dakika (`CLAUDE_CODE_PROMPT_CACHE_TTL=5m`, ~%30 ucuz lider turu); RET ÖLÇÜTE BAĞLI (`lider.ret_dayanagi`: `OLCUT:` alıntısı ya da `BOZULDU:`, yoksa bir kez sorulur). Liderin triyaj+planı TEK TUR (`hedef_ver(hazir_plan=)`, geçmezse plan turu); "anlattı yapmadı" koruması (`yazilacak_dosyalar`); her tur `jeton_dokumu`, terminal turuna ölçülmüş birimden `maliyet_tahmini_usd` (`ev/fiyat_olcumu.json`). Asıl sabit bedel: Claude her yeni oturumda ~12k (Haiku)/~23k (Sonnet) jetonu 1 sa önbelleğe yazar. Yalın lider (güç kısar) ve çatal/`--fork-session` (Sonnet'te önbellek kullanmıyor, ölçüldü) DENENDİ, GERİ ALINDI. Araştırma `docs/arastirma/`. KARMA (karne + çapraz kontrol, varsayılan): 20 işlik sette 19/20, gereksiz ret 0, Claude payı yalnız-Claude'a göre %40 az (Codex Plus 5 sa +26 puan). Ofis köke bırakılan YENİ yardımcı dosyayı `.ofis/` altına taşır (`degisim.yardimcilari_topla`). Sıradaki: Ponytail ölçümü, Caveman (muhtemelen faydasız).
- **Kullanıcının belirttiği eksikler (29.09):** her panoda her zaman açık
  yazma yeri; sesli orkestratör;
  seçenekli karar ekranı; "her iş gerçek
  durumuyla" ekranı; gece otopilotu.
- **Karar bekleyen (kullanıcı):** ajan panoları **gerçek Claude/Codex
  terminali mi** olsun, yoksa bugünkü yapılı akış CLI'a benzetilsin mi.
  Öneri: önce yapılı akışı CLI görünümüne yaklaştır, paralelde gerçek
  terminali ucuza ölç (kanca `rm`'i durduruyor mu, oturum `.jsonl`'dan
  kanıt/jeton/limit okunuyor mu, yazılan not ulaşıyor mu).
  **Claude yarısı ÖLÇÜLDÜ (29.09): kanca rm'i durdurdu, not tur
  sürerken ulaştı, döküm yapılı veri veriyor; limit yüzdesi dökümde yok
  (limit_oku var). Codex terminali de ÖLÇÜLDÜ: kanca Remove-Item'ı
  durdurdu, not ulaştı, döküm limit yüzdesini bile taşıyor; AMA kanca
  düşerse Codex AÇIK kalıyor (rm koştu).** Ayrıntı: günlük sonu.
  **Yerleşik izin kipleri de ölçüldü (29.09): Claude Auto (sonnet) git
  push + rm + dışarı POST'u SORMADAN yaptı; Codex "Approve for me" rm'i
  sormadan yaptı, POST'u sandbox kesti (sormadı). İki motorda da kanca
  her komutu gördü. Karar: gerçek terminal kipinde de KARAR ofisin kancası
  (riskli.py); yerleşik kip tek başına yetmez. Haiku'da Auto yok.**

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
- **`.playwright-mcp/` SİLİNMEZ**: rakip dökümleri/kareleri orada ve yedeğe
  girmiyor (30.09'da ekran görüntüsü temizliğiyle silindi, geri gelmedi).
  Geçici ekran görüntüsü tek tek dosya adıyla silinir; kalıcı rakip dökümü
  `docs/rakip/`e (metin) yazılır.
- Ortam: Python 3.12 · `claude`, `codex` CLI'ları npm'de; kullanıcının öteki
  kodu `C:\Users\pc\Desktop\JarvisForge` (çalışan parça varsa ödünç al).

## Sınamayı koşturmak

```
python testler/duman_<ad>.py                       # tek dosya
for f in testler/duman_*.py; do python "$f"; done  # tam takım (bash)
python testler/deneme.py --hizli --kuru            # deneme seti, $0
python testler/deneme.py --hizli                   # gerçek motor (kota!)
python testler/matris.py --kuru                    # motor matrisi, $0
```

Tam takımdan sonra `%TEMP%`'te `ofis-*` artığı kalmamalı; ofisin gerçek
evi değişmemeli (bekçi çıkış kodu 3 verir).
