# Token ve limit tasarrufu: Codex ayarları ve motordan bağımsız teknikler

Tarih: 03.10.2026. Yöntem: `codex --help`, `codex features list` (v0.160.0), yerel `~/.codex/config.toml` (yalnız okundu), resmi belgeler, GitHub API ile yıldız/tarih/lisans, README'ler.

Uyarı: web sayfaları araçla özetlenerek okundu; tırnak içindekiler o özetten alındı, ham sayfadan doğrulanmadı. Hiçbir aday ofiste KOŞTURULMADI; bütün "% tasarruf" sözleri adayın kendi iddiasıdır, bizim ölçümümüz değildir.

## 1. Codex: limit nasıl sayılıyor

- Resmî fiyat/limit sayfası (learn.chatgpt.com/docs/pricing; eski adres developers.openai.com/codex/pricing): "Local messages and cloud chats share your plan's usage allowance." ve "Model choice, context, reasoning, tool use, retrieval, and caching all affect usage, so prompt length alone isn't a reliable estimate."
- Önbellekten okunan jeton limite/krediye SAYILIR ama çok ucuz. Milyon jeton başına kredi (girdi / önbellekli girdi / çıktı): GPT-6.1 Sol 50 / 2,5 / 250; GPT-6 Sol 50 / 5 / 250; GPT-6 Luna 2,5 / 0,25 / 12,5; GPT-6 Astra 250 / 25 / 1250. Yani 6.1 Sol'da önbellekli girdi normal girdinin %5'i, çıktı ise girdinin 5 katı ve önbellekli girdinin 100 katı.
- "Önbellek YAZMA kredi harcamaz": yalnız üçüncü taraf blogda (smartscope.blog); resmî sayfadan doğrulanmadı.
- Haftalık sayaç: 5 saatlik ile haftalık arasındaki oran yayımlanmamış; haftalık yüzdenin kredi tablosuyla birebir aynı hesap olduğu DOĞRULANMADI (aynı blog "çözülmemiş gözlem" diyor; topluluk/GitHub'da anormal kota düşüşü bildiren kayıtlar var, ör. #30918 numaralı issue; açıp okumadım).
- Bizim için çıkarım (ÖLÇÜLMEDİ): Codex işçi turlarındaki yüzbinlerce jetonun büyük kısmı önbellek okuması ise bedeli girdinin yirmide biri. Pahalı kalem ÇIKTI ve akıl yürütme jetonları. Önce onlar azaltılmalı; önbellek okumasını azaltmak ikincil. Claude tarafında oran farklı, ayrı ölçülmeli.
- Ucuz ölçüm: bir codex turunun jeton olayından (girdi / önbellekli / çıktı) ayrım alınıp yukarıdaki kredi tablosuyla çarpılır; hangi kalemin baskın olduğu görülür. Para harcamaz (mevcut tur kayıtları yeter).

## 2. Codex resmî ayarları (işe yarayabilecekler)

Kaynak: config-reference (learn.chatgpt.com/docs/config-file/config-reference).

| Anahtar | Resmî açıklama | Bize etkisi |
|---|---|---|
| `model_auto_compact_token_limit` | "Token threshold that triggers automatic history compaction (unset uses model defaults)." | Uzun işçi turunda erken özet. Üçüncü taraf blog "özetleme geçmişi yeniden yazar, önbellek önekini öldürür" diyor (doğrulanmadı). Ölçmeden değiştirme. |
| `model_auto_compact_token_limit_scope` | "Controls whether the auto-compaction threshold counts the full active context (`total`, the default) or only growth after the carried compaction-window prefix." | Sabit başlangıç yükü büyükse `body_after_prefix` erken özeti önleyebilir (anlam belgeden çıkarım). |
| `tool_output_token_limit` | "Token budget for storing individual tool/function outputs in history." | Tek araç çıktısının geçmişe girişini sınırlar = "araç çıktısı kırpıcı"nın resmî karşılığı. Risk: ajan aradığını kaçırabilir. Ucuz denenir. |
| `compact_prompt` | "Inline override for the history compaction prompt." | Özet isteminin elle yazılması. |
| `model_reasoning_effort` | "Reasoning effort advertised by the selected model, such as low, medium, high, xhigh, max, or ultra." | Bizde zorluk->efor haritası var. Yerel config zaten `low`. |
| `model_reasoning_summary` | "auto / concise / detailed / none" | `none` özet çıktısını keser; akıl yürütme jetonunu azalttığı DOĞRULANMADI. |
| `model_verbosity` | "low / medium / high" (GPT-5 Responses API) | Çıktı en pahalı kalem; `low` denenebilir, kalite etkisi ölçülmeli. |
| `project_doc_max_bytes` | "Maximum bytes read from AGENTS.md when building project instructions." | AGENTS.md boyutunun tavanı. |
| `skills.max_context_tokens` | "Token budget for the available-skills catalog. Defaults to 2% of the model's context window." | Beceri kataloğu tavanı; güç kısmaz, katalog sığmazsa keser. |
| MCP `enabled_tools` / `disabled_tools` | araç görünürlüğünü kısıtlar | Kullanıcı kuralı (araç kapatma yok) ile çakışır. Yalnız hiç kullanılmadığı ÖLÇÜLMÜŞ araçlar için düşünülür. |

Resmî ipuçları (pricing sayfası, özet): talimatı kesin yaz, gereksiz bağlamı çıkar; yalnız ilgili dosyaları ver; çıktının hedef kitlesini/biçimini/uzunluğunu belirt, zorunlu işi isteğe bağlıdan ayır; AGENTS.md'yi iç içe klasörlere bölerek küçült; kullanılmayan MCP sunucularını kapat (son madde kullanıcı kuralıyla çakışır).

Yerel `codex features list` (v0.160.0) ilgili satırlar: `skill_search` stable/açık, `memories` stable/kapalı, `enable_request_compression` stable/açık, `fast_mode` stable, `context_management` under development, `tool_search` ve `tool_search_always_defer_mcp_tools` "removed" (ne anlama geldiği DOĞRULANMADI). `codex exec` bayrakları: `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--output-schema`, `--json`. `--ignore-user-config`'in başlangıç yüküne etkisi ölçülmedi.
Kullanıcının yerel config'inde çok eklenti açık (browser, chrome, computer-use, slack, google-calendar, documents, pdf, spreadsheets, presentations...). Etkisi ÖLÇÜLMEDİ; ofis ajanının codex evi ayrı olduğu için bu yalnız kişisel codex'i ilgilendirir.

## 3. Aday tablosu

Yıldız / tarih / lisans GitHub API'den 03.10.2026'da okundu (DOĞRULANDI). "İddia" adayın kendi sözüdür.

| Ad | Bağlantı | Yıldız / son güncelleme / lisans | İddia | Nasıl çalışıyor | Bizim bedele dokunuyor mu | Gücü kısıyor mu | Motordan bağımsız mı | Risk | Nasıl ucuza ölçülür |
|---|---|---|---|---|---|---|---|---|---|
| RTK (Rust Token Killer) | github.com/rtk-ai/rtk | 82,3 bin / 03.10.2026 / Apache-2.0 | Kabuk çıktısını %60–90 küçültür | Bash komutunu `rtk git status` gibi yeniden yazan kanca; filtre, gruplama, kırpma, tekrar silme | KISMEN: araç döngüsünde bağlamda kalan kabuk çıktısına dokunur. README kendisi: bu "bash çıktısı"nda azalma, faturada değil; sayım `bayt/4` tahmini | Kırpılan satır kaybolabilir (ham çıktı yolu `rtk proxy` var) | Claude, Codex (`rtk init -g --codex`, PreToolUse kancası), Gemini, Cursor vb. kancası var; Windows yerel ikili destekli (v0.37.2+) | Yalnız Bash araç çağrısı; yerleşik Read/Grep etkilenmez. Bizim izin kancamızla çakışma ölçülmeli | Boş klasörde aynı kabuk komutları (git log, test çıktısı) `rtk` ile ve onsuz; bayt ve jeton karşılaştır |
| Headroom | github.com/headroomlabs-ai/headroom | 74,3 bin / 03.10.2026 / Apache-2.0 | Kodlama ajanlarında %20, JSON'da %60–95 az jeton, aynı cevap | Yerel vekil / MCP / kütüphane; araç çıktısı, günlük, dosya sıkıştırır; özgünler yerelde saklanıp geri alınabilir (CCR); CacheAligner önbellek bozan içeriği işaretler, istemi yeniden yazmaz | KISMEN. Kendi tablosu: kod arama %21, keşif %42, issue %30, olay günlüğü %57; "düzyazı ve yoğun çıktı çok az sıkışır". Doğruluk testi N=100, fark güven aralığında | Geri alınabilir tasarım ama kayıplı olabilir | İddia: çok motor (Claude, Codex dahil). Abonelik (OAuth) trafiğinde çalıştığı DOĞRULANMADI | Araya giren vekil: tüm istem trafiği üçüncü kodun elinden geçer; önbellek öneki kayabilir | Önce README'deki çevrimdışı `benchmarks/index_proof_table.py`; sonra kendi kayıtlı bir işçi turu çıktısı üzerinde `compress()` |
| jCodeMunch MCP | github.com/jgravelle/jcodemunch-mcp | 2,7 bin / 03.10.2026 / "NOASSERTION"; README "dual-use": kişisel ücretsiz, ticari ücretli | Kod keşfinde %86–99 az jeton ("28,3 kat az", kendi kıyası) | Tree-sitter ile simge düzeyinde getirme | EVET, ajan keşifte çok dosya okuyorsa. "838B jeton kurtarıldı" sayacı adayın pazarlama sayacı | Ajan aracı seçerse güç korunur; seçmezse fayda yok | MCP, Codex listelenmiş | Lisans sınırı okunmalı (ofis satılmayacak ama ücretli ticari katman var). Ek araç şeması başlangıç yükünü artırır | Boş klasörde orta boy depo, aynı soru; araçlı/araçsız turun jetonu ve doğruluğu |
| Serena | github.com/oraios/serena | 30 bin / 30.09.2026 / GPL-3.0+ (SolidLSP MIT) | Simge düzeyinde okuma/düzenleme (IDE gibi) | Dil sunucusu tabanlı MCP | KISMEN; README'deki "kanıt" ajanların kendi yorumu (alıntı), jeton ölçümü DEĞİL → jeton iddiası DOĞRULANMADI | Güç artırır (refactor) | MCP; Codex ve Claude kurulum yönergesi var | GPL: ofise kod olarak gömme, ayrı süreç olarak koşturma. Çok araç = başlangıç yükü artar | Başlangıç yükü (araç şeması jetonu) + aynı görev |
| claude-context (Zilliz) | github.com/zilliztech/claude-context | 12,6 bin / 14.07.2026 / MIT | Anlamsal kod araması | Vektör veritabanı + gömme | Belki | Hayır | MCP | Zilliz Cloud anahtarı + OpenAI gömme anahtarı ister (dış hizmet; para kilidiyle çatışır) | — |
| code-context-engine | github.com/elara-labs/code-context-engine | 425 / 23.08.2026 / MIT | %94 az jeton, "yeniden üretilebilir" | Yerel dizin; ajan okumak yerine arar | Belki | — | MCP; Claude, Codex dahil | Küçük proje; Windows'ta C++ derleme araçları ister; iddia doğrulanmadı | Kendi blog ölçümünü boş klasörde yinele |
| sigmap, codesight | github.com/manojmallick/sigmap (644, 03.10.2026); github.com/Houseofmvps/codesight (1,4 bin, 27.07.2026) | lisans DOĞRULANMADI | ~%97 az jeton (sigmap iddiası) | Depo haritası/bağlam dosyası üretir | Belki | — | Dosya tabanlı | Küçük proje, iddia doğrulanmadı | Aider harita fikriyle kıyas |
| LLMLingua | github.com/microsoft/LLMLingua | 6,7 bin / 10.09.2026 / MIT | İstemde 20 kata kadar sıkıştırma, az kayıp | Küçük dil modeli önemsiz jetonları siler | Yalnız düzyazı (brifing/devir) için | Kod ve talimatta tehlikeli; kod kalitesi DOĞRULANMADI | Evet | Yerel model; önbellek önekini bozar | Brifing K2–K3 metninde sıkıştırılmış/ham ile aynı mini iş |
| Aider repo map (fikir) | github.com/Aider-AI/aider | 49,3 bin / 22.05.2026 / Apache-2.0 | Simge özeti haritası bağlamda | Tree-sitter + sıralama | Fikir olarak | — | Fikir bağımsız | Son güncelleme 4+ ay önce | Kurulum gerekmez, fikir |
| RouteLLM | github.com/lm-sys/RouteLLM | 5,6 bin / 08.2024 / Apache-2.0 | Sorguya göre ucuz/pahalı model | Eğitimli yönlendirici | Bizde zorluk->model haritası var | — | API odaklı | 2 yıldır durgun; abonelik CLI'larına uymaz | — |
| ccusage ve kullanım ölçerler | github.com/ccusage/ccusage (18,9 bin, 03.10.2026, NOASSERTION); douglasmonsky/codex-usage-tracker (196, 20.08.2026); jeongwookie/WhereMyTokens (84, 19.09.2026) | — | Jeton/kredi dökümü | Yerel oturum dosyalarını okur | Ölçer, tasarruf etmez | Hayır | ccusage'ın Codex desteği DOĞRULANMADI | — | Bizde `kullanim.py`, `tavan.py`, `testler/carpan.py` var |
| ooples/token-optimizer-mcp | github.com/ooples/token-optimizer-mcp | 538 / 03.10.2026 / MIT | Ölçüm, önbellek, bilgi grafiği, 16 istemci | MCP | Belirsiz | — | MCP | Ne yaptığı doğrulanmadı | — |

### Hükümler

1. RTK: **ölçmeye değer.** Araç döngüsünde bağlamda kalan kabuk çıktısı "her adım bütün bağlamı yeniden okuyor" sorunumuza dokunur. Apache-2.0, Windows yerel, Claude ve Codex kancası var, README kendi iddiasını faturaya çevirmiyor. Riskler: kancamızla çakışma, kırpılan çıktıda iş bozulması. Ayrı boş klasörde, ucuz modelle ölçülür.
2. Headroom: **ölçmeye değer (koşullu).** Açık lisans, çevrimdışı ölçüm betiği var. Abonelik trafiğinde çalıştığı doğrulanmadı ve vekil olması güvenlik sorusu. Önce yalnız çevrimdışı kıyas.
3. Araç çıktısı kırpma, kendi katmanımızda ve Codex `tool_output_token_limit` ile: **ölçmeye değer.** Motordan bağımsız yapılabilir (adaptör çıkışında); RTK sonucu bunun getirisini gösterir.
4. jCodeMunch, Serena, code-context-engine (kod haritası türü): **ölçmeye değer ama düşük öncelik.** Fayda, ajanın büyük depoda çok dosya okumasına bağlı; bizim işler çoğunlukla küçük masaüstü projeleri. Hepsi araç şeması ekler (başlangıç yükü artar). Önce "ajan bir turda kaç dosya okuyor" ölçülmeli. jCodeMunch lisansı ve Serena GPL notu okunmalı.
5. LLMLingua: **bize uymuyor.** Kod/talimatta kesinlik kaybı, önbelleği bozar, kodda kalite doğrulanmadı.
6. RouteLLM: **bize uymuyor** (durgun, API odaklı) ve **zaten bizde var** (zorluk->model haritası).
7. Kullanım ölçerler: **zaten bizde var** (`kullanim.py`, `tavan.py`, `carpan.py`).
8. claude-context: **bize uymuyor** (dış API anahtarı + para).
9. token-optimizer-mcp, sigmap, codesight: **bize uymuyor** şimdilik (iddia kanıtsız, ek araç yükü); yeniden bakılırsa ölçmeden eklenmez.

## 4. Çok ajanlı maliyet: kaynaklar ve bizim sistemle bağı

- Anthropic, "How we built our multi-agent research system": çok ajanlı sistemler sohbete göre ~15x, tek ajan ~4x jeton; "token usage by itself explains 80% of the variance" (tarama değerlendirmesinde); "agents struggle to judge appropriate effort" → istemde ölçek kuralları (basit olgu: 1 ajan 3–10 araç çağrısı; karşılaştırma 2–4 alt ajan; karmaşık 10+); alt ajan çıktıyı dış sisteme yazıp "lightweight references" döndürür (büyük metni konuşma geçmişinden taşımaz); lider Opus, alt ajan Sonnet. Bizde fan-out kapısı ve kanıt kayıtları var; "referansla taşı" ilkesi devir paketinde/brifingde kontrol edilebilir.
- Anthropic, "Effective context engineering for AI agents": özetleme; araç sonucu temizleme ("one of the safest lightest touch forms of compaction"); yapılandırılmış not alma; alt ajanın "often 1,000-2,000 tokens" özet döndürmesi; ihtiyaç anında getirme. Araç sonucu temizlemenin bizde kullanılıp kullanılmadığı DOĞRULANMADI.
- "The Handoff Tax" (Amazon, Ağustos 2026, alphaxiv 2608.24358; yalnız özet okundu): 58 bin koşu, 500 gerçek GitHub issue görevi, ~2 milyon API çağrısı. Güçlü modele geçişte TAM geçmiş aktarımı kalite farkının yarısından azını kapatıp maliyeti iki katına çıkarıyor; önceki modelin akıl yürütme adımlarını çıkarmak sonucu iyileştiriyor ("temiz sayfa"). Güçlüden ucuza inişte tam bağlam yardım ediyor. Bu, bizim yasa 4'ü (inceleme temiz bağlamla, hedef+kanıtla) destekler.
- BudgetMLAgent (Ocak 2025; yalnız arama özeti): ucuz-pahalı model kademesi + "uzmana sor" ile GPT-4 tek ajana göre %94 düşük maliyet iddiası. Makale okunmadı: DOĞRULANMADI.
- Berkeley MAST zaten anayasada.

### Motordan bağımsız, gücü kısmayan teknikler (öncelik sırasıyla)

1. **İnceleme turunu ucuzlat (en büyük kaldıraç, tamamen bizim kodda; gereksiz ret işi 2 kat pahalı yapıyor).** (a) İnceleyiciye işçinin akıl yürütmesini değil yapılandırılmış kanıtı ver (Handoff Tax). (b) Ret yalnız "kabul ölçütüne karşı kanıtlanmış eksik" için; tarz/beğeni notları ret sayılmasın. (c) Kanıt değişmediyse yeniden inceleme yok. (d) Ret sebebini işçiye kısa düzeltme listesi olarak ver ve AYNI oturumdan sürdür (önbellek sıcak). Ölçüm: `testler/carpan.py` ile ret oranı ve ret başına maliyet.
2. **Aynı oturumu sürdür, yeni oturum açma:** Codex'te önbellekli girdi %5; yeni oturum sabit başlangıç yükünü baştan öder.
3. **Önbellek önekini bozma:** oturum ortasında talimat/araç şeması değişimi önekı bozar (üçüncü taraf yazı, doğrulanmadı; ucuzca ölçülebilir: iki ardışık turda önbellekli jeton oranı).
4. **Eforu işe göre ayarla** (var); Codex'te çıktı payını `model_verbosity=low` ile denemek.
5. **Araç çıktısı kırpma** (bkz. hüküm 1 ve 3).
6. **Dosya referansı taşı, metin taşıma** (Anthropic).

## 5. Doğrulanmadı

- Codex haftalık sayacının önbellekli jetonu nasıl saydığı (oran yayımlanmamış).
- "Önbellek yazma kredi harcamaz" (yalnız üçüncü taraf blog).
- Otomatik özetlemenin Codex'te önbellek önekini bozduğu.
- `tool_search` bayrağının "removed" olmasının anlamı; `context_management` bayrağının işlevi.
- Headroom'un abonelik (OAuth) trafiğinde çalıştığı; RTK, Headroom, jCodeMunch, code-context-engine ve sigmap'in tüm tasarruf yüzdeleri.
- ccusage'ın Codex desteği; sigmap/codesight lisansı; BudgetMLAgent ve Handoff Tax tam metinleri.
- Instagram/YouTube/X önerilerinin kendisine bakılmadı (erişim yok); adaylar GitHub etiketleri ve aramalardan geldi.
- Resmî sayfaların ham metni (araç özetinden alındı).
