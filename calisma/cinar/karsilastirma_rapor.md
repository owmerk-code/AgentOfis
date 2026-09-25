# 5 CLI Araç Karşılaştırması: Headless Modu, Hesap Gereksinimleri ve Akış Çıktısı Desteği

## Karşılaştırmalı Tablo

| Araç | Headless Komut Örneği | Ücretli Hesap Gereksinimi | Stream-JSON/Akış Çıktısı Desteği | Kaynak |
|------|----------------------|--------------------------|----------------------------------|--------|
| **Goose** | `goose --recipe workflow.yaml --no-session` | Hayır (Free & Open-source, BYOK model; API anahtarı gerekli) | Evet: `--output-format stream-json` ve `--output-format json` | [goose-docs.ai/tutorials/headless-goose](https://goose-docs.ai/docs/tutorials/headless-goose/) |
| **Gemini CLI** | `gemini -p "prompt"` | Hayır (Free tier: 1000 req/gün, Google hesabı yeterli) | Evet: `--output-format json` (JSON), `--output-format jsonl` (streaming JSONL) | [geminicli.com/docs/cli/headless](https://geminicli.com/docs/cli/headless/) |
| **Copilot CLI** | `copilot -p "prompt" --allow-tool='shell(git)'` | Hayır (Free: 2000 completion/ay; CLI credit kullanır) | Evet: `--output-format json` (JSONL, newline-delimited) | [docs.github.com/copilot/cli](https://docs.github.com/copilot/concepts/agents/about-copilot-cli) |
| **OpenCode** | `opencode run "prompt"` | Hayır (Free tier: OpenCode Zen, API key gerekli) | Evet: `--format json` (JSONL event stream) | [opencode.ai/docs/cli](https://opencode.ai/docs/cli/) |
| **Cursor** | `agent -p "prompt"` | Hayır (Free Hobby tier; Pro/Pro+ paid options var) | Evet: `--output-format stream-json`, `--stream-partial-output` | [cursor.com/docs/cli/headless](https://cursor.com/docs/cli/headless) |

---

## Değerlendirme ve Öneriler

### En Uygun 3 Araç: Gemini CLI, Copilot CLI, OpenCode

**Gemini CLI**'nin AgentOfis'e ilk motor-adaptörü olarak eklenmesi önerilir. Nedeni: Aracın Google'ın resmi Gemini API'sine doğrudan erişimi vardır; ücretsiz tier 1000 istek/gün sağlayarak hafif ve orta ölçekli otomasyonlar için yeterlidir; `--output-format jsonl` ile tam akış desteğine sahiptir ve doğrudan `-p` bayrağı ile headless çalıştırması basit ve güvenilirdir. Kaynak: resmi GitHub repo ve geminicli.com belgeleri.

**Copilot CLI** ikinci tercih olmalıdır. GitHub'ın geniş kullanıcı tabanı ve entegrasyon ekosistemi göz önüne alındığında, Copilot CLI free tier (aylık 2000 completion) hafif otomasyonlar için uygundur; ancak daha yoğun kullanımda kredi tüketimi ciddi maliyetler yaratabilir. `-p` bayrağı ve `--output-format json` (JSONL) desteği headless senaryoları güvenir. Kaynak: docs.github.com/copilot ve fiyatlandırma belgeleri.

**OpenCode** üçüncü seçimdir. Go tabanlı hafif yapısı ve açık protokol (JSONL event stream) ile başta CI/CD pipeline otomasyonlarına ideal uygundur. `--format json` ile raw event yayını öğe-düzeyinde kontrol sağlar. Ancak OpenCode Zen free tier'ı API anahtarı gereksinimi ve sınırlı dokümandasyon nedeniyle ayar maliyeti yüksektir.

### Hızlı Başlangıç İçin Tavsiye

Gemini CLI ile başlayın: `-p` tek bayrağı ile komut satırı çalıştırması hızlı ve doğru çıktı garantilidir. Copilot CLI free tier kredileri bittiğinde veya daha yoğun otomasyonlar gerektiğinde OpenCode'a geçin. Goose ve Cursor hali hazırda sağlam alternatiflerse de—Goose'un açık kaynak esnekliği, Cursor'ün IDE entegrasyonu—ama bu görev bağlamında headless otomasyona odaklanıldığında, önerilen 3'ü ücretsiz erişim, basit komut yapısı ve güvenilir akış çıktısı açısından ön plana çıkarır.

---

**Rapor hazırlanış tarihi:** 2026-09-19  
**Araştırma kaynakları:** Resmi belgelendirme (GitHub repo, AI Studio docs), WebSearch ve WebFetch ile doğrulanmış.
