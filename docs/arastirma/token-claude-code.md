# Claude Code token ve limit tasarrufu: araştırma (03.10.2026)

Kapsam: yalnız araştırma. Kod yazılmadı, hiçbir şey kurulmadı, gerçek model turu koşmadı
(yalnız `claude --help` ve `claude --version` = 2.1.287). Belge alıntıları code.claude.com
sayfalarından; sayfalar küçük bir özetleyici modelden geçtiği için alıntılar harfi harfine
garanti değil, ama anlamları doğrudan belgeden. Yıldız sayıları 03.10.2026'da `gh api` ile
okundu. "Doğrulanmadı" yazan her şey ölçülmedi ya da okunmadı.

## 1. En önemli bulgu: sabit bedelin kaynağı büyük olasılıkla bilinen bir Claude Code kusuru

Bizim ölçtüğümüz "her yeni oturumda Haiku ~12 bin, Sonnet ~23 bin jeton önbellek yazma" ile
örtüşen açık kayıtlar var (hepsi `anthropics/claude-code` deposunda):

- **#98513** (30.09.2026, açık): "Session-invariant context (skill/agent listings, deferred
  tools, CLAUDE.md) is sent after the first user prompt, so every new session and subagent
  rewrites it to the prompt cache." Ölçüm (claude-sonnet-5-5, 31 deneme): ilk turda ~16 bin
  jeton yazma kalıyor ve "no option moves it in front of the prompt"; yazar
  `excludeDynamicSections: true`'nun konumu değiştirmediğini de ölçmüş. Yani beceri/ajan
  listesi, ertelenmiş araç adları, ortam bloğu kullanıcının İLK mesajından SONRA gidiyor.
  İlk mesaj her oturumda farklı olduğundan önek eşleşmiyor, hepsi yeniden yazılıyor.
- **#93499** (11.09, açık): CLAUDE.md/kurallar her oturum başında yeniden yazılıyor; yalnız
  sistem istemi + araç tanımları (~24 bin) oturumlar arası okunuyor.
  `--exclude-dynamic-system-prompt-sections` buna YARAMIYOR (aynı ilk kullanıcı mesajına
  taşıyor). Ölçülmüş çözüm: sabit içeriği `--append-system-prompt-file` ile sistem istemine
  koymak (2. oturum 66.942 okuma / 13.157 yazma).
- **#94815** (17.09, açık): arka plan oturumlarında oturuma özgü geçici klasör yolu sistem
  isteminin paylaşılan bloğuna giriyor, ~23-28 bin jeton her seferinde yazılıyor. Bizim kipimiz
  `claude -p`; "arka plan oturumu" yolu bizde kullanılıyor mu: doğrulanmadı.
- **#96578** (24.09, açık): bir depoda her kullanıcı mesajında önbellek yeniden yazılıyor;
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` onarıyor (macOS, Opus, o depoya özgü). Bizde olup
  olmadığı: doğrulanmadı.
- **#91971** (açık): zincirleme `-p --resume` çağrılarında önbellek okuması hiç artmıyor. Bizim
  "çatal Sonnet'te okunmadı" bulgumuzla uyumlu olabilir; nedenini kanıtlamıyor.

Sonuç: bu sabit bedel bizim ayarımızdan değil, ürünün iç sıralamasından geliyor olabilir ve düz
bir bayrakla kapanmıyor. Çıkış yolları: Anthropic'in düzeltmesini beklemek (kayıtlar açık, yorum
yok), listeleri küçültmek (güç kısma, reddedildi), ya da aşağıdaki kısmi önlemler.

## 2. Resmi belgelerden işe yarayabilecek ayar ve bayraklar

Kaynaklar: https://code.claude.com/docs/en/prompt-caching , /costs , /env-vars ,
/agent-sdk/modifying-system-prompts , /skills , /mcp.

### 2.1 Önbellek süresi SEÇİLEBİLİYOR (en umutlu bulgu)

> "Unless you choose a TTL yourself, Claude Code requests the one-hour TTL only on a Claude
> subscription within your plan's included usage. There it requests the hour for the main
> conversation ..."

> "`CLAUDE_CODE_PROMPT_CACHE_TTL` - Set `5m` or `1h`, the only values Claude Code accepts, to
> choose the prompt cache TTL for the main conversation: your interactive, `-p`, and SDK turns
> ... The API bills 1-hour cache writes at a higher rate. Requires Claude Code v2.1.242 or later"

Ayar karşılığı `promptCacheTtl`. İkinci kova (alt ajan, sıkıştırma vb.) için
`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` / `subagentPromptCacheTtl`. `FORCE_PROMPT_CACHING_5M=1`
ikisini birden 5 dakikaya zorlar.

> "The longer TTL helps when you leave a session idle and come back to it ... It costs more on
> short bursts of work that never idle past five minutes, where the higher write rate applies
> and the longer cache lifetime goes unused."

Bizim durumumuz tam bu: lider ve inceleme turları tek tek, kısa, geri dönülmeyen oturumlar, ve
yazdığımız 12-23 bin jeton "1 saatlik (2 kat fiyat)" yazma. API fiyatında 5 dakikalık yazma
1,25x, 1 saatlik 2x (kaynak: #93499 metni "1.25x input price, 2x with the 1-hour TTL"). Aynı
yazma yaklaşık %37 ucuz olabilir.

ÖLÇÜLMEDİ ve KRİTİK BİLİNMEYEN: abonelik LİMİTİ önbellek yazmayı API fiyat oranıyla mı sayıyor?
Belge bunu söylemiyor. Ucuz ölçüm: aynı basit işi `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` ile koş,
`claude -p ... --output-format json` çıktısında `usage.cache_creation.ephemeral_5m_input_tokens`
mı `ephemeral_1h_input_tokens` mı dolduğuna bak (belgenin kendi tarifi), sonra `/usage` plan
yüzdesindeki farkı ölç (yüzde kaba, çok tekrar gerekir).
Risk: işçi turu uzun; her istek zamanlayıcıyı sıfırlar ama 5 dakikayı aşan tek bir bekleme
(örn. uzun bir komut) önbelleği düşürür. Lider/inceleme için güvenli görünür; işçi ayrıca
ölçülmeli. Codex'te karşılığı yok (Claude'a özgü).

### 2.2 Önbellek kapsamı (oturumlar arası okuma ne zaman olur)

> "In Claude Code, the cache is effectively scoped to one machine and directory. ... Two
> sessions in different directories therefore build different prefixes and miss each other's
> cache. Sessions you run in parallel in the same directory build matching prefixes and read
> each other's cache. Sequential sessions share the prefix only when the git status snapshot
> taken at startup matches"

> "Each model has its own cache." (Haiku işçi ile Sonnet lider birbirinin önbelleğini okuyamaz.)

Ölçüm önerisi: Sonnet lider ve Sonnet inceleme turlarının (1) AYNI çalışma klasöründen, (2) AYNI
ek-istem metniyle, (3) AYNI araç/MCP kümesiyle, (4) git durumu değişmeden koşup koşmadığına bak.
Biri farklıysa sistem+araç kısmı (#93499'a göre ~24 bin) bile okunmaz. Bizim 23 bin Sonnet yazmamız
"sistem+araç (okunabilirdi) + #98513'teki ~16 bin" olabilir; DOĞRULANMADI. Ofisin hangi klasörden
koştuğu ve ek istemin tur başına değişip değişmediği koda bakılarak denetlenmeli (bu araştırmada
koda bakılmadı).

### 2.3 Bayraklar ve ayarlar

- `--exclude-dynamic-system-prompt-sections` (claude --help, v2.1.287): "Move per-machine
  sections (cwd, env info, memory paths, git status) from the system prompt into the first user
  message. Improves cross-user prompt-cache reuse. Only applies with the default system prompt
  (ignored with --system-prompt)." Beklenti DÜŞÜK: #93499 ve #98513 kalan yazmayı çözmediğini
  ölçmüş. Yine de ucuz; farklı klasörlerden koşan turların sistem kısmını ortaklaştırabilir.
- `--system-prompt-snapshot on` (varsayılan): istem ilk istekte kaydedilir, sonraki isteklerde ve
  resume'da aynen gönderilir. Zaten varsayılan.
- Sabit içeriği (ofisin kendi ~5-6 bin jetonluk sabit kimlik/kural kısmı) `--append-system-prompt`
  ile vermek: #93499 Test 3'e göre sistem istemindeki sabit metin oturumlar arası OKUNUYOR,
  ilk kullanıcı mesajındakiler okunmuyor. Bizde şu an hangisinin nerede durduğu: doğrulanmadı.
- `CLAUDE_CODE_ATTRIBUTION_HEADER=0`: belgeye göre sistem isteminin başındaki sürüm + "prompt
  fingerprint" bloğunu atar. Önek kararlılığına etkisi belgelenmemiş: doğrulanmadı.
- `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1` / `includeGitInstructions:false` (belge: "The built-in
  commit and pull request instructions and the git status snapshot"). Git durum kesitini kaldırır;
  yani "ardışık oturumlar ancak git durumu aynıysa öneki paylaşır" engelini ortadan kaldırır.
  İşçi git kullanıyorsa gücü etkiler. Salt okunur lider/inceleme için güç kısmaz diye düşünülür;
  ölçülmedi.
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`: #96578'e göre bir depoda her mesajda yazmayı önlüyor.
  Ofis kendi belleğini kullanıyor; Claude'un otomatik belleği ajan için gerekli mi, kullanıcıya
  sorulmalı. Önbelleğe etkisi bizde: doğrulanmadı.
- Çıktı stilleri: önbelleği bozmaz (mesaj olarak gelir, belge); jeton kazancı belgelenmemiş.
- `/usage` içinde "Prompt cache (main)" satırı (v2.1.251+): istek sayısı, isabet oranı, ıska
  sayısı, "likely cause: ..." (v2.1.260+); statusline'da `prompt_cache` nesnesi. Ucuz TEŞHİS aracı.
  `-p` çıktısında `usage.cache_creation` zaten okunabiliyor.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `CLAUDE_CODE_AUTOCOMPACT_PCT_OVERRIDE`: işçinin 150-600 bin
  okumasını sınırlayabilir; ama belge "compacting a large context is itself a large request"
  diyor. Etkisi belirsiz: ölçülmedi.
- Efor: Sonnet 5.5 ve Opus 5.5'te düşünme kapatılamaz, yalnız efor düşer (belge). Ofis zaten efor
  ayarlıyor. Efor değişiminin önbelleği bozup bozmadığı: belge "Opus 5.5/Sonnet 5.5/Fable 5.1'de
  bozmaz" diyor, #92444 "Sonnet 5 ve Opus 5'te bozuyor" diyor; çelişki, doğrulanmadı.
- MCP araç tanımları ZATEN varsayılan ertelenmiş ("MCP tool definitions are deferred by default,
  so only tool names and server instructions enter context"). `ENABLE_TOOL_SEARCH` değer listesi
  ve `auto` eşiği bulunamadı (özetleyici bölümü bulamadı): doğrulanmadı.
- `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` (varsayılan 2048): "each MCP tool description and each
  MCP server's instructions" kırpma sınırı. Sunucu yönergelerini kısaltır; talimat kesilir, güç
  kısma sınıfına yakın; önerilmez, ölçülmedi.
- `skillOverrides` (`"name-only"`, `"off"`, `"user-invocable-only"`) ve `disable-model-invocation`:
  beceri açıklamasını listeden çıkarır. Model beceriyi bulamaz: reddedilen seçenek (a) ile aynı
  sınıf. `/skill-doctor` (v2.1.252+) hangi becerinin ne kadar bağlam yediğini ve ne kadar
  kullanıldığını gösterir: karar için SALT OKUNUR veri, güç kısmaz.
- `ENABLE_CLAUDEAI_MCP_SERVERS=false`, `disableClaudeAiConnectors`: claude.ai bağlayıcılarını
  kapatır (özetleyici çıktısında okundu, harfi harfine doğrulanmadı). Güç kısma.
- `CLAUDE_CODE_DISABLE_ATTACHMENTS=1`: beceri listesi + dosya-değişti notları + görev notlarını
  kapatır (belge). Beceri keşfini öldürür: güç kısma.
- `--bare` / `--safe-mode`: hepsini kapatır; güç kısma.
- Abonelikte limit nasıl sayılıyor: belgede yalnız "5 saatlik pencere + haftalık pencere, koltuk
  payı, tüm modeller ortak" ve "cache miss reprocesses your full context" anlatımı var. Önbellek
  okuma/yazmanın plan limitine hangi ağırlıkla yazıldığı sayısal olarak YOK: doğrulanmadı.
  `/usage` plan dökümü "recent usage attributed to skills, subagents, plugins, and individual MCP
  servers" ve "behavior flags (long context, cache misses) at 10%+" gösteriyor; ucuz bir ölçüm
  kaynağı (yüzdeler yaklaşık, yalnız bu makine).

## 3. Aday tablo

Ortak not: hiçbir "yüzde X tasarruf" iddiası bizim tarafımızdan ölçülmedi. Hiçbiri "oturum başı
sabit yazma" kalemini doğrudan azaltmıyor; MCP/eklenti/beceri ekleyenler o kalemi artırır.
Kısaltmalar: S1 = oturum başı sabit önbellek yazma, S2 = Sonnet lider/inceleme turları,
S3 = Haiku işçinin büyük okuması.

| Ad | Bağlantı | Yıldız / son güncelleme / lisans | İddia | Nasıl çalışıyor | S1 | S2 | S3 | Gücü kısıyor mu | Codex/başka motor | Risk | Ucuz ölçüm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rtk (Rust Token Killer) | github.com/rtk-ai/rtk | 82.285 / 03.10.2026 / Apache-2.0 | "reduces LLM token consumption by 60-90% on common dev commands"; README: "cuts up to 90% of the bash output your agent reads" | Tek Rust ikilisi; kabuk komutlarının (ls, git, test, grep...) çıktısını süzüp özetler | Hayır | Az | Evet olabilir: araç çıktısı bağlamı büyütür, her istekte okunur | Kısmen: çıktı kırpılır, ajan eksik görebilir; `cat/read` için "signatures over full bodies" | README'de ajan listesi okunmadı: doğrulanmadı | Kanca komutu yeniden yazıyor; Windows desteği doğrulanmadı | Aynı gerçek işi rtk açık/kapalı koş; `cache_read` toplamı ve işin geçip geçmediği |
| context-mode | github.com/mksglu/context-mode | 25.170 / 03.10.2026 / Elastic License 2.0 (GitHub: NOASSERTION) | "Sandboxes tool output (98% reduction), persists session memory ... 17 platforms via MCP + hooks" | MCP sunucusu + kancalar; büyük çıktıyı sanal alanda tutar, bağlama özet verir | KÖTÜ: yeni MCP araçları + SessionStart kancası ek bağlam ekler (#96578 bu eklentinin ~4,6 bin karakter `additionalContext` eklediğini anıyor) | Olumsuz | Olabilir olumlu | Yönlendirmeyi zorlar, davranışı değiştirir | Başka platform iddiası var; Codex doğrulanmadı | Kısıtlı lisans, kapalı kutu davranış | Kurmadan: eklentinin eklediği jetonu tek turda `cache_creation` farkıyla gör |
| Caveman | github.com/JuliusBrussee/caveman | 109.337 / 03.10.2026 / Apache-2.0 | "cuts 65% of tokens by talking like a caveman". Kendi dürüst notu: JetBrains 86 görevde yalnız %8,5 daha az ÇIKTI jetonu; kendi deneyinde "default caveman: 3% fewer output tokens at the median" | Beceri (kısa konuşma) + ayrı PROXY (ajanın okuduğu günlük/test/JSON/fark çıktısını küçültür, orijinali diskte tutar) | Hayır; kural metni her çağrıya GİRDİ ekler (README: "The rules add input tokens on every call") | Olumsuz/belirsiz | Proxy kısmı olabilir | Beceri: kalitede ölçülebilir düşüş yok (JetBrains p=0,82); proxy: kayıp riski | `caveman claude/codex/...` sarmalıyor (README); doğrulanmadı | Proxy `ANTHROPIC_BASE_URL`'e girer: abonelik girişiyle çalışıp çalışmadığı doğrulanmadı | Proxy için kendi A/B aracı `caveman trial -- claude` |
| pxpipe | github.com/teamchong/pxpipe | 7.495 / 02.10.2026 / lisans doğrulanmadı | Sistem istemi + araç belgesi + eski geçmişi PNG'ye çevirerek "~59-70% lower end-to-end bill" | Yerel proxy (`ANTHROPIC_BASE_URL` ya da `pxpipe warp -- claude`) isteği yeniden yazıp metni görsele çevirir | Kâğıt üstünde evet (kendi örneği: ~25 bin metin jetonu ≈ 2,7 bin görsel jetonu) | Kâğıt üstünde evet | Kâğıt üstünde evet | Model metni görselden okuyor: hata riski; README "needed a nudge" notu veriyor | `warp -- codex` diyor; doğrulanmadı | Önbellek davranışı, Anthropic koşulları, abonelik kimliği, güvenilirlik: doğrulanmadı | Yalnız boş klasörde tek ucuz tur; agresif |
| token-optimizer (alexgreensh) | github.com/alexgreensh/token-optimizer | 2.481 / 30.09.2026 / NOASSERTION | "Find the ghost tokens. Fix them. Survive compaction." | Claude Code eklentisi; Codex, Cursor, OpenCode sürümleri rozetlerde görünüyor | Hayır, kendisi beceri/kanca ekler | Olumsuz | Belirsiz | Denetim güç kısmaz; kurtarma kancaları davranış ekler | Codex eklentisi iddiası var (doğrulanmadı) | Eklenti = bağlam listesine ek | Zaten bizde var: `/context`, `/skill-doctor`, `/usage` |
| claude-context-optimizer (egorfedorov) | github.com/egorfedorov/claude-context-optimizer | 114 / 30.09.2026 / MIT | "saves 30-50% on API costs" | Eklenti; boşa giden dosya okumalarını izler | Hayır | Hayır | Belirsiz | Düşük | Doğrulanmadı | Küçük proje, kanıt yok | Gerekmez |
| claude-token-optimizer (nadimtuhin) | github.com/nadimtuhin/claude-token-optimizer | 610 / 17.08.2026 / MIT | "90%": açılışta 4 dosya (~800 jeton) | Belge düzeni önerisi | Zaten bizde var: brifing katmanlı, CLAUDE.md kısa | Hayır | Hayır | Düşük | Motordan bağımsız fikir | Yüzde iddiası dayanaksız | Gerekmez |
| KINGSTAR-OMEGA/claude-token-optimizer | github.com/KINGSTAR-OMEGA/claude-token-optimizer | 121 / 12.04.2026 / MIT | "60-80%": "zero-English, JSON-only" çıktı kipi | Beceri/istem şablonu | Hayır (girdi ekler) | Hayır | Hayır | Çıktı biçimini bozar | - | Dayanaksız | Gerekmez |
| AzozzALFiras/claude-context-optimizer | github.com/AzozzALFiras/claude-context-optimizer | 43 / 01.05.2026 / lisans doğrulanmadı | "up to 98%": dosya önbelleği, anlamsal okuma | MCP sunucusu | KÖTÜ (MCP ekler) | - | Belirsiz | Belirsiz | - | Küçük, sabit maliyeti artırır | Gerekmez |
| ai-context-stack | github.com/aandersen2323/ai-context-stack | 2 / 09.08.2026 / lisans yok | "Reduce Claude Code Tokens by 80-90%" | Otomatik bağlam enjeksiyonu | Hayır | - | - | - | - | 2 yıldız, kanıt yok | Gerekmez |
| serena | github.com/oraios/serena | 29.955 / 30.09.2026 / NOASSERTION | "semantic retrieval and editing capabilities - the IDE for your agent" | MCP; dil sunucusuyla sembol bazlı arama/düzenleme | KÖTÜ: MCP araç adları + sunucu yönergesi listeye girer | Olumsuz | Büyük kod tabanında olumlu olabilir | Güç artabilir | MCP istemcisi olan her motor; belge okunmadı, doğrulanmadı | Sabit maliyeti artırır | Büyük bir kod işinde `cache_read` toplamı |
| claude-code-router | github.com/musistudio/claude-code-router | 37.523 / 26.09.2026 / MIT | Claude Code isteklerini başka model/sağlayıcıya yönlendirme | Yerel proxy | Hayır | Hayır | Hayır | Güç farkı model | Başka sağlayıcılar | Abonelik girişiyle çakışır; ofis zaten rol bazlı model seçiyor | Zaten bizde var (kademe haritası, zincir) |
| ccusage | github.com/ryoppippi/ccusage | 18.852 / 03.10.2026 / NOASSERTION | Yerel `.jsonl` günlüklerinden kullanım/maliyet raporu | Salt okunur günlük okuyucu | Yalnız ölçer | - | - | Yok | Codex ayrı (doğrulanmadı) | Dış bağımlılık | Zaten bizde var: `kullanim.py`, `testler/carpan.py` |
| claude-usage / tokenmeter / ai-token-monitor | github.com/phuryn/claude-usage (2.243), serkankorkut/tokenmeter (22), soulduse/ai-token-monitor (340) | 2026 | Yerel panolar | Günlük okuyucu | Yok | Yok | Yok | Yok | tokenmeter açıklamasında Codex ve Copilot CLI geçiyor | - | Zaten bizde var |
| houtini-lm | github.com/houtini-ai/houtini-lm | 120 / 24.09.2026 / lisans doğrulanmadı | Sınırlı işleri yerel/ucuz LLM'e devreden MCP | MCP | KÖTÜ (MCP ekler) | - | Olabilir | Yerel model zayıf | - | Ek MCP, kalite düşer | Zaten bizde var: Haiku işçi + kademe |

Not: zilliz/claude-context ve Maciek-roboto/Claude-Code-Usage-Monitor adresleri `gh` ile 404
verdi; listeye alınmadı (doğrulanmadı).

## 4. Hükümler

| Aday | Hüküm | Gerekçe |
|---|---|---|
| `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` (resmi; lider ve inceleme için) | **ölçmeye değer** (en umutlu) | Tek turluk Sonnet oturumları 1 saatlik 2x yazma ödüyor ve geri dönmüyor; belge kısa işte 1 saatin boşa gittiğini söylüyor. Bilinmeyen: abonelik limiti yazma ağırlığını bu oranla sayıyor mu. Güç kısmaz, Codex'e dokunmaz, geri alması tek değişken. |
| Aynı klasör + aynı ek-istem + sabit/değişken ayrımı (sabit kimlik sistem istemine, iş metni mesaja) | **ölçmeye değer** | #93499 Test 3: sistem istemindeki sabit metin oturumlar arası okunuyor (66.942 okuma / 13.157 yazma). Lider ile inceleme (ikisi de Sonnet) aynı öneki paylaşabilir. Mevcut yapıyı incelemek gerekir. |
| Teşhis: `/usage` "Prompt cache (main)" + "likely cause" ve `usage.cache_creation` | **ölçmeye değer** (ölçüm aracı, maliyetsiz) | Her ıskanın nedenini söyleyebilir; diğer ölçümler buna dayanır. |
| `--exclude-dynamic-system-prompt-sections` | **ölçmeye değer**, düşük beklenti | Belge "cross-user reuse" diyor; #93499/#98513 kalan yazmayı çözmediğini ölçmüş. Farklı klasörlerden koşan turların sistem kısmını ortaklaştırabilir. |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1` (yalnız salt okunur lider/inceleme) | **ölçmeye değer** (küçük) | Git durumuna bağlı önek ayrışmasını kaldırır. İşçide commit yönergeleri gittiği için orada değil. |
| rtk | **ölçmeye değer** (yalnız işçi, ikinci sıra) | Haiku işçinin 150-600 bin okuması araç çıktısıyla büyür; süzmek büyümeyi azaltır. Ama kancayla komutu yeniden yazar, kayıp riski ve Windows uyumu doğrulanmadı. Sabit bedele dokunmaz. |
| Resmi `skillOverrides` / `ENABLE_CLAUDEAI_MCP_SERVERS=false` / `--bare` / `DISABLE_ATTACHMENTS` | **bize uymuyor** | Sabit bedeli keser ama gücü kısar (kullanıcı reddetti, deneme (a)). Yalnız `/skill-doctor` salt okunur envanter olarak kullanılabilir. |
| Çatallama (`--fork-session`) | **zaten denendi, reddedildi** | Haiku'da okuma var, Sonnet'te yok; #91971 ve #98513 ile tutarlı olabilir, kanıtlamadım. |
| Anthropic'in düzeltmesi (#98513 / #93499) | **izle** | Asıl çözüm orada: ürün listeleri ilk mesajdan ÖNCEYE alırsa sabit bedel kendiliğinden okumaya döner. Yorum yok, durum açık. |
| context-mode, serena, houtini-lm, AzozzALFiras | **bize uymuyor** | Hepsi MCP/eklenti; asıl sorun olan oturum başı liste şişmesini artırır. |
| Caveman (beceri) | **bize uymuyor** | Maliyetimiz çıktı değil girdi/önbellek; kendi sayıları: çıktıda %3-8,5; kural metni her çağrıya girdi ekler. Proxy kısmı: abonelik girişi riski doğrulanmadı. |
| pxpipe | **bize uymuyor** (şimdilik) | Görselden okuma: kayıp ve kural çatışması riski; proxy; lisans ve abonelik uyumu doğrulanmadı. |
| token-optimizer (alexgreensh), claude-context-optimizer (egorfedorov) | **zaten bizde var** | Denetim/ısı haritası işi; `/context`, `/skill-doctor`, `/usage` ve ofisin kendi ölçümü aynı işi görüyor. |
| ccusage, claude-usage, tokenmeter, ai-token-monitor | **zaten bizde var** | Yerel günlük okuyucular; ofiste `kullanim.py` ve `testler/carpan.py` var. |
| claude-code-router | **zaten bizde var** | Rol bazlı model seçimi ve hesap zinciri ofiste; proxy abonelik girişiyle çakışabilir. |
| nadimtuhin / KINGSTAR / ai-context-stack | **bize uymuyor** | Belge düzeni ya da çıktı protokolü fikirleri; dayanaksız yüzde iddiaları. |

## 5. Önerilen ölçüm sırası (hepsi boş geçici klasörde, ucuz modelle)

1. `claude -p "merhaba" --model haiku --output-format json` iki kez (varsayılan), sonra aynısı
   `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` ile. `usage.cache_creation.ephemeral_*` hangi kovada
   dolduğuna bak. Sonra Sonnet'te aynı. (Bu yalnız kovanın değiştiğini doğrular; limit etkisi
   ayrı: `/usage` yüzdesi.)
2. Aynı klasörden art arda iki Sonnet turu: ek-istem aynı / farklı; `cache_read` ve
   `cache_creation` karşılaştır (sistem+araç ~8-24 bin okunuyor mu).
3. Aynısı `--exclude-dynamic-system-prompt-sections` ve `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1` ile.
4. Gerçek işçi işinde rtk (kurmak gerekir; bu araştırmada kurulmadı).

## 6. Doğrulanamayanlar

- Abonelik limitinin önbellek yazma/okumayı hangi ağırlıkla saydığı (belgede sayısal kural yok);
  5 dakikalık TTL'nin LİMİTTE gerçekten tasarruf yaptığı.
- Bizdeki 12/23 bin yazmanın tam bileşimi (sistem+araç mı, #98513'teki ilk-mesaj-sonrası liste mi).
- Ofisin lider/inceleme turlarında klasör, ek-istem ve git durumunun turdan tura değişip değişmediği
  (koda bakılmadı).
- `ENABLE_TOOL_SEARCH` değer listesi ve `auto` eşiği; `ENABLE_CLAUDEAI_MCP_SERVERS` ve
  `disableClaudeAiConnectors` harfi harfine alıntıyla görülmedi.
- Hiçbir aday aracın iddiasını ölçmedim; rtk'nin Codex/Windows desteği, context-mode, serena ve
  pxpipe'in Codex uyumu, pxpipe lisansı, Caveman proxy'sinin abonelik girişiyle çalışması.
- zilliz/claude-context ve Maciek-roboto/Claude-Code-Usage-Monitor adresleri bulunamadı.
- #96578 (otomatik bellek) ve #94815 (arka plan oturumu) bizim kurulumda geçerli mi.
- #92444 ile belge arasındaki çelişki (Sonnet'te efor değişimi önbelleği bozuyor mu).
- pasqualepillitteri.it listesi bağlantı hatası verdi, okunamadı; adaylar WebSearch + `gh` ile bulundu.
- GitHub kayıtlarının açık/kapalı durumu yalnız 03.10.2026 itibarıyla.
