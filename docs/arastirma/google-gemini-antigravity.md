# Google yapay zekâsı ve Antigravity: ofis için araştırma (4 Ekim 2026)

Yöntem: yalnız web araştırması; hiçbir şey kurulmadı, giriş yapılmadı, `agy` koşturulmadı.
Güven işareti: **[RESMİ]** Google'ın kendi sayfası · **[ÜÇÜNCÜ]** blog/depo/haber (ölçüm değil, aktarım) · **[DOĞRULANMADI]**.
Hiçbir şey ofiste ölçülmedi; "çalışıyor" denen her şey kaynağın sözüdür. Matris ölçümünden geçmeden deftere girmez.

---

## 0. Kullanıcının ön bilgisinde düzeltilmesi gerekenler

1. **"Argon 4" yanlış ad.** Gerçek ad **Gemini 4 Argon** (bkz. bölüm 3). Var, 30 Eylül 2026'da duyuruldu, ama **Pro aboneliğine henüz gelmedi**.
2. **Flow'un 1000 kredisi var, ama kaynaklar çelişiyor.** Resmi Flow yardım sayfası Pro için ayda 1.000 ek kredi diyor. Android Authority (20 Mayıs 2026) "1.000 ücretsiz Flow kredisinin kaldırıldığını" yazıyor; muhtemelen ücretsiz kullanıcının kredisini kastediyor, ama sayfa net değil. Türkiye'deki abonelik sayfası "200 Flow kredisi" diyor (bölgeye göre farklı olabilir). Bkz. bölüm 2.
3. **Kendi notundaki Gemini sürümleri** (3.8/3.7/3.6 Flash, 3.1 Pro) kaynaklarla uyumlu; Google bazı sayfalarda "Gemini 3.5 Flash" ve "Gemini Omni" da anıyor. Sürüm adları kaynaklar arasında karışık, `agy`'nin kendi model listesi esas alınmalı.

---

## 1. Antigravity (`agy`) ile görsel ve video

### 1.1 Görsel: VAR, ama tek resmî kaynak dolaylı
- Antigravity ajanının yerleşik bir **`generate_image`** aracı var. Google'ın kendi geliştirici ekibi yazısı: araç çalışınca çıktı "konuşmanın iç artifact klasörüne" kaydedilir: `<appDataDir>/brain/<conversation-id>/`, araç mutlak yolu döndürür. Parametreler: istem, `ImageName`, `AspectRatio` (ör. 1:1), `ImagePaths` (en çok 3 referans görsel). **[ÜÇÜNCÜ, Google ekibi yazısı]** https://dev.to/googleai/elevating-antigravity-agent-skills-part-2-image-generation-2jno
  - Yazı alttaki model adını, kotayı ve headless çalışıp çalışmadığını **söylemiyor**.
- Üçüncü taraf arama sonuçları: araç, istem görsel isteyince kendiliğinden tetikleniyor ("Imagen/Nano Banana altında"). Model adı için kesin kaynak yok. **[DOĞRULANMADI]**
- `--generate-image` / `--output-dir` bayrakları **`agy`nin değil, bir Claude Code eklentisinin (cc-antigravity-plugin) bayrakları**; eklenti bunları `generate_imagem` aracını tetiklemek için kullanıyor. Bir arama özeti bunları `agy`nin kendi seçeneği gibi gösterdi; resmî belgede doğrulanmadı. https://github.com/AllanHarlen/cc-antigravity-plugin
- Pro kotasından görsel: **agy-image** MCP sunucusu "Google AI Pro kotasını mevcut Antigravity girişinden" kullanıyor; `gemini-3.1-flash-image` modelini, `https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent` iç adresine, `agy`nin OAuth belirtecini yerelden okuyup çağırıyor. Kendi uyarısı: "genel destekli API değil, iç uç nokta, kendi riskinle kullan". Hata kodu 429 `QUOTA_EXHAUSTED`: "görsel modelinin kotası sohbet kotasından AYRI". **[ÜÇÜNCÜ]** https://glama.ai/mcp/servers/ahmadarif-lab/agy-image
  - **Ofis için sonuç: bu yol KULLANILMAMALI.** Belirteci `agy` ikilisinden/dosyadan çıkarıp başka kodla kullanmak, Google'ın forumdaki resmî cevabına göre ihlal sınırında (bkz. 1.3). Güvenli olan, ajanın `agy -p` ile `generate_image` aracını kendisinin çağırması.
- Başka üçüncü taraf eklentiler (Pi, OpenClaw, dsh) Vertex AI `gemini-3.1-flash-image-preview` / `gemini-3-pro-image-preview`'i dener, olmazsa `agy` modeline düşer. Vertex = ücretli API; para kilidine takılır. https://github.com/vedang/pi-antigravity-image-gen
- Çıktı dosyasının yeri: yukarıdaki iç `brain/<conversation-id>/` klasörü (Google yazısı). Ofis bunu `conversation_id` ile bulup proje içine kopyalamak zorunda kalır; **gerçekte nereye yazıldığı ölçülmedi**.

### 1.2 Video (Veo): `agy` içinden dönen bir kanıt BULUNAMADI
- `agy`de Veo çağıran resmî bir araç adı **bulunamadı. [DOĞRULANMADI]**
- Veo yalnız şu yerlerde: Gemini uygulaması, Flow (kredili), Gemini API/Vertex (ücretli, saniye başı). Pro için Flow'da Veo 3.1 Lite/Fast/Quality.
- Veo API: ücretli ve para kilidine aykırı. (Veo 3.0 uç noktaları 30 Haziran 2026'da kapandı, Veo 3.1'e geçildi: https://costgoat.com/pricing/google-veo , **[ÜÇÜNCÜ]**.)
- Sonuç: Pro aboneliğiyle video üretmenin programatik, resmî ve ücretsiz yolu **yok** görünüyor (bölüm 2.3).

### 1.3 Headless (`-p`) kullanım resmen serbest mi?
- Google görevlisinin forum cevabı: `agy -p` ile resmî ikiliyi yerelden çağırmak "resmen desteklenen bir özellik, Bölüm 6'yı ihlal etmez; yeter ki aracın kullanıcının OAuth bilgisini çıkarmasın, saklamasın, araya girmesin". "Yoğun otomatik toplu çalıştırma kişisel plan kotalarında sınır tetikleyebilir." Üretim için AI Studio/Vertex anahtarı önerilmiş. **[ÜÇÜNCÜ: Google forumu, Google çalışanı]** https://discuss.ai.google.dev/t/is-it-allowed-for-an-open-source-tool-to-call-the-official-agy-cli-in-headless-mode/183429
- Ofis için çıkarım: `agy -p` çağırmak güvenli; belirteç dosyasına dokunmak değil.

---

## 2. Google AI Pro içeriği (Ekim 2026)

### 2.1 Antigravity kotası
- Resmî: Pro ve Ultra abonelerine "öncelikli erişim, en cömert limitler, **kotalar her 5 saatte yenilenir**" (5 Aralık 2025). Ücretsiz plan haftalık. **[RESMİ]** https://blog.google/feed/new-antigravity-rate-limits-pro-ultra-subsribers/
- 19-20 Mayıs 2026'dan beri Gemini uygulaması, Flow ve Antigravity **ortak, hesaplamaya dayalı kota** kullanıyor: 5 saatlik kayan pencere + haftalık tavan; kota istemin karmaşıklığına, kullanılan özelliğe, sohbet uzunluğuna göre tükeniyor. Ücretsiz katmanın 4 katı, tam sayı verilmemiş. https://www.androidauthority.com/google-ai-pro-usage-limits-3669063/ **[ÜÇÜNCÜ]**; Google destek sayfası da aynı yapıyı doğruluyor ("5 saatte yenilenir, haftalık tavan; medya üretimi ve Deep Research daha çok tüketir; limitler haber verilmeden değişebilir"): https://support.google.com/gemini/answer/16275805 **[RESMİ]**
- Tüm Google ürünleri **aynı havuzdan** yer: Gemini uygulamasında görsel üretmek Antigravity kotasını da yer. (Android Authority.)
- Antigravity abonelik sayfasında Pro için ifade "giriş düzeyi sıklık sınırlaması" (Türkçe sayfa): https://gemini.google/subscriptions/ **[RESMİ]**. Yani Pro, Claude Max 5x'e göre açıkça sınırlı.
- Ultra $100: Pro'nun 5 katı, Ultra $200: 20 katı. https://www.droid-life.com/2026/05/19/google-updates-ai-subscription-plans/ **[ÜÇÜNCÜ]**
- Sayısal kota (jeton/yüzde): **resmî rakam yok. [DOĞRULANMADI]** Yüzde ölçmek için bölüm 5.4.
- Gemini ve Claude modelleri `agy` içinde **iki ayrı havuz** (agy-sdk'ye göre `weekly` ve `fiveHour` pencereleri, ikisi için). https://github.com/nghyane/agy-sdk **[ÜÇÜNCÜ]**
- Dikkat: "Antigravity Pro'da Claude/GPT-OSS modellerini de koşturur" — kendi ölçümün (claude-sonnet-4-6, opus-4-6-thinking, gpt-oss-120b) bununla tutarlı; Claude modellerini bu havuzdan koşturmak Claude Max kotasını yemez, ama Google'ın havuzunu yer.

### 2.2 Flow kredileri
- Resmî Flow yardım sayfası: aboneliksiz günlük 50 kredi; ek aylık: Plus 200, **Pro 1.000**, Ultra $100 10.000, Ultra $200 25.000. Yeni aylık krediler fatura döneminin başında yenilenir, devretmez. Maliyet: Veo 3.1 Lite 5-10, Fast 10-20, Quality 100 kredi; Gemini Omni Flash (360p) 4-7. Yani Pro ayda yaklaşık 50-100 Lite/Fast ya da 10 Quality video. **[RESMİ]** https://support.google.com/flow/answer/16526234?hl=en
- Çelişki: Android Authority "1.000 ücretsiz Flow kredisi kaldırıldı" dedi; Google'ın yardım sayfası ise Pro'ya 1.000 diyor. Türkiye abonelik sayfasında 200 yazıyor. **Bölgeye ve tarihe göre değişiyor olabilir; kullanıcının hesabında "Flow > krediler" ekranından teyit edilmeli. [DOĞRULANMADI]**

### 2.3 Flow programatik erişimi
- Flow için resmî CLI/API bulunamadı. Aboneliğin Flow kredileri yalnız Flow ve Gemini uygulaması arayüzünde; Veo'ya programatik erişim Gemini API/Vertex (ücretli, saniye başı) üzerinden. https://costgoat.com/pricing/google-veo **[ÜÇÜNCÜ]**
- "Flow'da API erişimi var" diyen bir derleme sitesi (saascrmreview) ayrıntı vermiyor; resmî doğrulama yok. **[DOĞRULANMADI]**
- Kullanıcının kuralı: Gemini uygulaması/Flow web arayüzü ajanlarla sürülmez. Bu yüzden Flow kredisi ofis için **fiilen kullanılamaz**; kullanıcı elle kullanır.

### 2.4 Gemini uygulamasında görsel/video sınırı
- Pro için günde 3 Veo videosu (Veo 3.1 Fast) yazan bir kaynak var (costgoat, Ekim 2026) **[ÜÇÜNCÜ]**; Google'ın destek sayfası sayı vermiyor, "kullanımınıza göre Ayarlar'dan bak" diyor. Kesin günlük sayı **[DOĞRULANMADI]**.
- Pro içeriği (Türkçe resmî sayfa): Gemini 3.1 Pro (farklı düzeylerde), Deep Research, 1M bağlam, görsel üretimi ve düzenleme, Veo 3.1 Lite (sınırlı), Flow kredisi, Antigravity giriş düzeyi limit, 400 GB depolama. I/O 2026 duyurusu: Pro abonelerine Gemini Omni ve Gemini 3.5 Flash, YouTube Premium Lite (bazı ülkeler). https://gemini.google/subscriptions/ · https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/ **[RESMİ]**

### 2.5 "Abonelik içi, ücretsiz, resmî programatik yol" var mı?
- **Metin/kod:** evet, `agy -p` (resmen destekli, bölüm 1.3).
- **Görsel:** `agy` içindeki `generate_image` aracı bu yolun tek aday. Kota ve çalışma biçimi **ölçülmeden bilinmez**.
- **Video:** bulunamadı. Veo = Flow/Gemini uygulaması (elle) ya da ücretli API.

---

## 3. "Argon 4"

**Gerçek ürün: Gemini 4 Argon.** Çıkış tarihi **30 Eylül 2026**.
- Resmî duyuru: "gelişmiş gerçek dünya uzun-ufuklu yazılım mühendisliğinde yeni en iyi sonuç". Şu an **yalnız güvenilir siber savunucu ortaklara, Fairwind Programı üzerinden**; "geliştiricilere, kuruluşlara ve tüketicilere mümkün olan en kısa sürede" genişleyecek; **önce ücretli API müşterilerine ve Google AI Ultra abonelerine**. **[RESMİ]** https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/
- Giriş fiyatı (tanıtım): 1M girdi jetonu $2, çıktı $10; sonra $4/$20. Çıktı sınırı 1 milyon jeton. DeepSWE v1.1 %77,9; CWE-bench %68; LVBench %91,7 (üretici ölçümü).
- Bağımsız yorum: Artificial Analysis "halüsinasyon oranı %15, öncülerin en düşüğü; GPT-6 Astra ile aynı zeka endeksi, görev başına %60 maliyet" (Engadget/Yahoo aktarımı). https://techcrunch.com/2026/09/30/google-releases-gemini-4-argon-called-its-most-powerful-model-yet/ · https://www.engadget.com/2274263/google-gemini-4-model-argon/ **[ÜÇÜNCÜ]**
- **Pro'ya ne zaman gelir: açıklanmadı. [DOĞRULANMADI]** Ultra ve API önce; Pro için tarih yok. Antigravity'de Argon seçeneği için de kaynak bulunamadı.
- Ofis çıkarımı: Argon şimdilik `agy` modeli olarak planlanmamalı; model listesi (`/model`) zaten güncelleme mekanizmasıyla (`guncelleme.py`) yeni Gemini ailesini yakalar. Argon "yeni aile" olduğu için insana sorulur.

---

## 4. Gemini 3.x güçlü ve zayıf yanları

Uyarı: aşağıdakilerin çoğu üçüncü taraf özet; ölçüm yok. Model adları kaynaklarda birbirine karışık (3.5/3.8). Ofisin kendi karnesi (`karne.py`) nihai hakem olmalı.

**Güçlü (kaynaklı):**
- **Video ve ses girdisi:** üç ana model arasında videoyu/sesi okuyan tek model; Gemini 3.8 Flash LVBench %87,8. https://www.secondtalent.com/resources/gpt-6-vs-claude-vs-gemini/ **[ÜÇÜNCÜ]** (Argon %91,7, resmî.)
- **Hız ve fiyat:** 3.8 Flash ~239 çıktı jetonu/sn, girdi $0,75/M (Opus 5.5'in yaklaşık beşte biri). Aynı kaynak. Ocak 2027'de fiyatı iki katına çıkarma planı var (API fiyatı; abonelikte kota).
- **Arayüz görünümü:** karşılaştırmalı yorumlarda Gemini (3.1 Pro / 3.5 Flash) "daha az yapay zekâ gibi görünen" arayüz, iyi kontrast/denge, SVG ve animasyonlu SVG; Claude ise yapı, sayfa metni ve çok adımlı gereksinimde daha güvenilir. https://www.banani.co/blog/gemini-3.1-for-web-and-ui-design · https://www.mindstudio.ai/blog/gemini-3-5-flash-vs-claude-opus-4-8-ui-generation **[ÜÇÜNCÜ, öznel]**
- **Uzun bağlam:** 1M jeton (Pro sayfası, resmî). Doğruluk karşılaştırması için bağımsız kaynak bulunamadı. **[DOĞRULANMADI]**
- **Google ekosistemi:** Workspace/Gmail/Drive entegrasyonu (yorumlarda).

**Zayıf (kaynaklı):**
- **Kod / ajan döngüsü:** LMArena kod arenasında Gemini 3.8 Flash 28. sırada (1.580 Elo) karşı Opus 5.5 1.827, GPT-6 Astra 1.792; Terminal-Bench 4.0'da Artificial Analysis ölçümü Gemini %19,7, Opus 5.5 %59,6, Astra %59,1. https://www.secondtalent.com/resources/gpt-6-vs-claude-vs-gemini/ **[ÜÇÜNCÜ, rakamlar Artificial Analysis/LMArena'dan aktarılıyor, ham veri kontrol edilmedi]**
- Ön uç kod arenasında ilk sırada GPT-6 Astra (1.793), sonra Fable 5.1 (1.755), Opus 5 (1.691); Gemini ilk onda anılmıyor. https://www.morphllm.com/best-ai-model-for-coding (özet arama sonucundan; sayfa açılamadı, **[DOĞRULANMADI]**)
- **Halüsinasyon / eski bilgi:** Google forumunda 3.8 Flash için "ciddi halüsinasyon, eski bilgiyi güvenle sunma, güncel bilgiyi kullanmama" şikâyeti; model kartı da halüsinasyon, yavaşlama/zaman aşımı, yüksek eforda fazla jeton uyarısı veriyor. Bilgi kesimi Mart 2026. https://discuss.ai.google.dev/t/gemini-3-8-flash-severe-hallucinations-outdated-information-and-failure-to-use-current-information/185870 · https://deepmind.google/models/model-cards/gemini-3-8-flash/
- **Ayrıntılılık:** Artificial Analysis'e göre 3.7'ye göre görev başına ~%40 fazla maliyet, aynı test için 120M çıktı jetonu (medyan 71M).
- Araştırma görevlerinde: yalnız bir inceleme bulundu (sayfa açılmadı). Claude/GPT ile bağımsız kıyas **bulunamadı. [DOĞRULANMADI]**
- UI tasarımı için "kesin kazanan yok; araç ve iş akışı sonucu belirliyor" (uxmagic.ai, Eylül 2026): çoğu kanıt anekdot. https://uxmagic.ai/blog/best-ai-model-for-ui-design

**Ofis için öneri (bu kaynaklara dayalı hipotezdir, ölçülmeli):** Gemini'yi *ana işçi* değil, şu iş türlerinde karne ile denenecek *uzman* yap: (1) video/ses/uzun belge okuma, (2) arayüzün ilk görsel taslağı ve SVG, (3) görsel üretim (`generate_image`), (4) ucuz/hızlı yardımcı tur. Kod yazma ve inceleme Claude/Codex'te kalsın. Çapraz inceleme için Gemini "ikinci göz" olarak ölçülebilir.

---

## 5. Antigravity kancaları, MCP, izinler (motor bağlantısı için)

Tümü resmî belgeden, Windows notları ayrıca belirtilmiştir.

### 5.1 Kancalar (hooks) **[RESMİ]** https://antigravity.google/docs/hooks/
- Dosya: proje `.agents/hooks.json` ya da genel `~/.gemini/config/hooks.json`.
- Şema: `{ "kanca-adi": { "enabled": true, "PreToolUse": [...], "PostToolUse": [...], "PreInvocation": [...], "PostInvocation": [...], "Stop": [...] } }`. Olay işleyicisi: `type: "command"`, `command`, `timeout` (sn, varsayılan 30). `PreToolUse`/`PostToolUse` için araç adı eşleştirici (regex). Tam işleyici dizisi örneği bu özette görülmedi; kurmadan önce belgeden alınmalı.
- **PreToolUse girdisi (stdin JSON):** `toolCall` (ad ve argümanlar), `stepIdx`, `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`.
- **Çıktı (stdout JSON):** `{"decision": "allow|deny|ask|force_ask|deny_unless_prior_grant", "reason": "...", "permissionOverrides": ["kaynak"]}`. Reddetmek: `decision: "deny"` + `reason`. (Üçüncü taraf: ret JSON olarak çıkış kodu 0 ile gider.)
- PostToolUse: çıktı olarak `{}` yeter; girdide isteğe bağlı `error` alanı var.
- **KRİTİK HATA (açık):** `decision:"allow"` headless modda **yok sayılıyor**; izni olmayan komut yine otomatik reddediliyor ("headless mod soramaz, otomatik reddedildi"). `deny` ise açıkça izin verilmiş komutu bile engelliyor. Yani kanca *yalnız kısıtlayıcı* katman; onay mekanizması değil. Sürüm 1.2.7, açık, bakımcı cevabı yok. https://github.com/google-antigravity/antigravity-cli/issues/1053 **[ÜÇÜNCÜ]**
  - Ofise etkisi: ofisin "kapıdan sor, insan onaylayınca çalıştır" modeli `agy` headless'ta kancayla *yürümez*. Yapılabilecek: (a) ofisin kapısı kancada `deny` ile engeller; izin verilecekleri `permissions.allow` ile önceden yazılır (iş başına dinamik ayar dosyası); (b) onay gereken eylemde iş durdurulup insana sorulur, onaydan sonra izin eklenip `--conversation` ile sürdürülür. `--dangerously-skip-permissions` kapıyı kancaya bırakır ama `allow` hatası yüzünden kanca `deny` dışında bir şey söyleyemez; **kancanın bu bayrakla `deny`yi gerçekten sürdürdüğü ölçülmeli. [DOĞRULANMADI]**
- `permissionOverrides` ve `force_ask` interaktif kip içindir; headless davranışı **[DOĞRULANMADI]**. Kancalar izin katmanından önce çalışır (agenticcontrolplane.com).

### 5.2 İzinler **[RESMİ]** https://antigravity.google/docs/permissions/ · https://antigravity.google/docs/settings/
- Dosya: genel `~/.gemini/antigravity-cli/settings.json`; proje düzeyi ayar `.agents/` ya da `.gemini/` içinde (tam dosya adı özette yok, **[DOĞRULANMADI]**); komut satırı bayrakları kalıcı ayarı geçici ezer.
- Biçim: `{"permissions": {"allow": [...], "deny": [...], "ask": [...]}}`, her kural `eylem(hedef)`: `read_file`, `write_file`, `read_url`, `execute_url`, `command` (önek, `regex:desen` ya da `*`), `mcp` (`sunucu/araç`, `sunucu/*`, `*`), `unsandboxed`. Örnek: `"allow": ["command(git)", "read_url(google.com)"]`, `"deny": ["command(sudo)", "write_file(.git/)"]`.
- Öncelik: **Deny > Ask > Allow**. Yazma izni aynı yola okumayı da verir; okumayı yasaklamak yazmayı da engeller. Çalışma klasörü otomatik izinli. Komut öneki eşleşmesi komut ikamesi (`$(...)`), küme genişletme gibi şeyler varsa kapanır ve soruya düşer (üçüncü taraf: https://agenticcontrolplane.com/blog/antigravity-permissions-reference).
- **Windows:** "önceki izin sistemi", kum havuzu önizleme aşamasında; yol normalizasyonu sürücü harfini siler, ters bölüyü düzler. Kural yazarken bunu hesaba kat.
- Headless varsayılanı: çalışma klasöründeki dosya işlemleri otomatik izinli; onay isteyen komutlar yumuşak reddedilir. Önceden izin için `permissions.allow` ya da `--dangerously-skip-permissions`. https://antigravity.google/docs/cli/headless/ **[RESMİ]**
- Modlar: `default`, `accept-edits` (`--mode=accept-edits`), `plan`. "`--approve` politikası yok." (aibuilderclub.com, üçüncü taraf)

### 5.3 MCP **[RESMİ]** https://antigravity.google/docs/mcp/
- Dosya: genel `~/.gemini/config/mcp_config.json`, proje `.agents/mcp_config.json`.
- Biçim: `{"mcpServers": {"ad": {"command": "...", "args": [...], "env": {...}}}}`; uzak sunucu için `serverUrl`. İsteğe bağlı: `cwd`, `headers`, `authProviderType`, `oauth`, `disabled`, `disabledTools`.
- MCP araçları varsayılan **Ask** modunda; headless'ta sorulamaz, bu yüzden her MCP aracı için `mcp(sunucu/araç)` ya da `mcp(sunucu/*)` allow gerekir. Ofis MCP'si için `mcp(ofis/*)` kuralı + araç kanıtı için ölçüm gerekir.
- Eklentiler (plugin): "yetenek, ajan, kural, MCP sunucusu ve kancayı tek pakette" taşır (`/plugin`). https://antigravity.google/docs/cli/features/

### 5.4 Başsız çalıştırma, sürdürme, kota **[RESMİ]** https://antigravity.google/docs/cli/headless/
- `-p`/`--print`/`--prompt`. `--output-format text|json|stream-json`. Zarf (json): `conversation_id`, `status`, `response`, `duration_seconds`, `num_turns`, `usage` (`input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens`), isteğe bağlı `structured_output`/`json_schema` (`--json-schema`).
- Akış (stream-json) olayları: `init`, `step_update`, `result`. `--input-format stream-json` ile tek süreçte çok tur (stdin'e `{"event":"user","message":{"content":...}}`).
- `status`: `SUCCESS, ERROR, CANCELED, INTERRUPTED, INVALID, WAITING, RUNNING`. `WAITING` = onay bekliyor.
- Bayraklar: `--model`, `--effort low|medium|high`, `--agent`, `--add-dir` (çalışma alanı; varsayılan yok), `--print-timeout` (varsayılan 5 dk), `--dangerously-skip-permissions`, `--sandbox`.
- **Sürdürme:** `--conversation <id>` ya da `-c/--continue`. `-c` "çalışma alanındaki en son" konuşmayı seçer, yanlış konuşmaya düşebilir; kimlikle sürdürmek önerilir (call-agy belgesi, https://github.com/F1rstDan/call-agy/blob/main/references/cli-reference.md **[ÜÇÜNCÜ]**). Kimlik `init`/json zarfındaki `conversation_id`'dir.
- **Kota yüzdesi:** `agy -p /usage` modele kota harcamaz, "kesin yüzdeleri ve sıfırlanma zamanını" döndürür; yapı: iki havuz (Gemini, Claude) × `weekly` ve `fiveHour` pencereleri, her birinde `pct` ve `resetAt`. https://github.com/nghyane/agy-sdk **[ÜÇÜNCÜ]**. Resmî olarak `/usage` komutu "tüm modeller için kota ve hız sınırı durumunu" gösterir (aibuilderclub.com). Çıktı biçimi `agy` sürümüne göre değişebilir; ölçülmeli.
- Kota bitince (eklenti belgesi): çıkış kodu 10 `QUOTA_EXAUSTED` + yeniden deneme komutu; 11 giriş gerekli; 13 `agy` yok. Bunlar **eklentinin** kodları, `agy`nin kendi çıkış kodları değil olabilir **[DOĞRULANMADI]**. `agy` kendisi başarısızlıkta sıfırdan farklı kod ve `status`/`error` döner.
- Ajan kendi kalan kotasını göremez ve kendini kısmaz: ofisin dışarıdan izlemesi şart.
- Sabit bedel: önemsiz bir tur bile yaklaşık 13k girdi jetonu (agy-sdk); `usage` alanları oturum içinde birikimli, tur başına fark alınmalı.

---

## 6. Ofis için öneri özeti

1. **Gemini motoru `agy -p` ile takılabilir** (resmen serbest). Bayrak karşılığı: `mcp_konusur` evet (config ile), `izin_kancasi` KISMİ (yalnız deny), `tur_ici_mesaj` bilinmiyor (stream-json girişi var), `butce_destegi` yok (`/usage` ile dışarıdan), `araclar_kapatilabilir` `permissions.deny` ve `disabledTools` ile evet.
2. **İzin kapısı:** kanca sadece reddeder; "sor-onayla" modeli ofiste Gemini için ayrıca tasarlanmalı (bölüm 5.1).
3. **Görsel:** `generate_image` aracını `agy -p` ile denemek tek temiz aday; iç uç noktayı doğrudan çağıran MCP'ler kullanılmaz.
4. **Video:** abonelik içi programatik yol yok; Flow elle.
5. **Argon:** Pro'ya ne zaman geleceği belirsiz; beklenmesi gerekir.
6. İlk gerçek ölçümler (kullanıcı onayıyla, boş geçici klasörde, ucuz modelle): `agy -p /usage` çıktısı · `generate_image` headless çıktı yeri · `deny` kancasının `--dangerously-skip-permissions` altında çalışması · `--conversation` ile sürdürme · Windows'ta kural yazımı.
