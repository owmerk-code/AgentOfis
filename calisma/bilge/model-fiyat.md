# Model Fiyat Karsilastirmasi (Anthropic / OpenAI)

**Erisim tarihi:** 2026-09-20

**Okunan tam URL'ler (tarayiciyla dogrudan acildi):**
- https://www.anthropic.com/api -> yonlendi -> https://claude.com/platform/api (Anthropic resmi API fiyat sayfasi)
- https://platform.openai.com/docs/pricing -> yonlendi -> https://developers.openai.com/api/docs/pricing (OpenAI resmi API fiyat sayfasi)

**Dogrulanamayan sayfalar:**
- https://www.anthropic.com/pricing ve https://claude.com/pricing tuketici plan sayfasi (Free/Pro/Max abonelik fiyatlari), API token fiyati icermiyor - bu yuzden /platform/api sayfasi kullanildi.
- https://docs.anthropic.com/en/docs/about-claude/pricing ve https://docs.claude.com/en/docs/about-claude/pricing tarayicida `net::ERR_BLOCKED_BY_CLIENT` hatasi verdi, acilamadi.
- https://openai.com/api/pricing/ WebFetch ile 403 Forbidden dondu; ayrica tarayicida bu URL otomatik olarak https://openai.com/tr-TR/business/pricing/#api adresine yonlendi (isletme/ChatGPT plan sayfasi, API token fiyati yok). Bunun yerine gercek API fiyat sayfasi olan platform.openai.com/docs/pricing kullanildi.

---

## Anthropic (Claude) — kaynak: https://claude.com/platform/api

| Model | Giris ($/1M) | Cikis ($/1M) | Prompt cache okuma ($/1M) | Prompt cache yazma ($/1M) | Kaynak URL |
|---|---|---|---|---|---|
| Claude Fable 5.1 | $10 | $50 | $0.25 | $12.50 | https://claude.com/platform/api |
| Claude Opus 5 | $5 | $25 | $0.50 | $6.25 | https://claude.com/platform/api |
| Claude Sonnet 5 | $2 | $10 | $0.20 | $2.50 | https://claude.com/platform/api |
| Claude Haiku 4.5 | $1 | $5 | $0.10 | $1.25 | https://claude.com/platform/api |

Ek notlar (sayfada belirtilen, sayfadan dogrudan okundu):
- Batch (toplu) isleme: standart fiyata gore %50 indirim ("Apply batch processing discount" seceneği ile).
- Prompt caching fiyatlari 5 dakikalik TTL icin gecerli; 1 saatlik uzatilmis cache ayri fiyatlandirilir (bkz. https://platform.claude.com/docs/en/build-with-claude/prompt-caching#1-hour-cache-duration).
- ABD-icinde-kalan (data residency) cikti/giris islemleri standart fiyatin 1.1 kati.
- Opus 5 icin "fast mode" standart fiyatin 2 kati.

---

## OpenAI — kaynak: https://developers.openai.com/api/docs/pricing (sekme: "Standard")

### Flagship modeller

| Model | Giris ($/1M) | Cache'li giris ($/1M) | Cikis ($/1M) | Kaynak URL |
|---|---|---|---|---|
| gpt-6-astra | $10.00 | $1.00 | $50.00 | https://developers.openai.com/api/docs/pricing |
| gpt-5.6-sol | $4.00 | $0.40 | $20.00 | https://developers.openai.com/api/docs/pricing |
| gpt-5.6-terra | $2.00 | $0.20 | $12.00 | https://developers.openai.com/api/docs/pricing |
| gpt-5.6-luna | $0.20 | $0.02 | $1.20 | https://developers.openai.com/api/docs/pricing |

Not: Yukaridaki tum degerler "kisa baglam" (short context) fiyatlaridir. Sayfada ayrica bu 4 model icin "uzun baglam" (long context) fiyatlari, ~2x seviyesinde, ayri sutunda gosteriliyor (orn. gpt-6-astra uzun baglamda giris $20.00 / cikis $75.00).

### Diger sekmeler (ayni Flagship tablosu icin, sayfadaki "Content switcher" ile dogrulandi)

| Sekme | gpt-6-astra Giris/Cikis ($/1M) | Aciklama |
|---|---|---|
| Standard | $10.00 / $50.00 | Varsayilan/senkron fiyat |
| Batch | $5.00 / $25.00 | Toplu isleme, %50 indirim |
| Flex | $5.00 / $25.00 | Esnek gecikme, %50 indirim |
| Fast mode | $20.00 / $100.00 | Onceki adiyla "priority processing", standart fiyatin 2 kati |

### Cyber modelleri

| Model | Giris ($/1M) | Cache'li giris ($/1M) | Cikis ($/1M) | Kaynak URL |
|---|---|---|---|---|
| gpt-5.6-cyber | $12.50 | $1.25 | $75.00 | https://developers.openai.com/api/docs/pricing |

### Ihtisaslasmis modeller (secili ornekler)

| Kategori | Model | Giris ($/1M) | Cache'li giris ($/1M) | Cikis ($/1M) | Kaynak URL |
|---|---|---|---|---|---|
| ChatGPT | chat-latest | $5.00 | $0.50 | $30.00 | https://developers.openai.com/api/docs/pricing |
| Codex | gpt-5.3-codex | $1.75 | $0.175 | $14.00 | https://developers.openai.com/api/docs/pricing |
| Life Sciences | gpt-rosalind-research | $5.00 | $0.50 | $25.00 | https://developers.openai.com/api/docs/pricing |

Ek notlar (sayfada belirtilen, sayfadan dogrudan okundu):
- Web arama araci: tum modeller icin $10.00 / 1000 cagri (+ arama icerik tokenlari model fiyatindan ayrica faturalanir).
- Duzenli isleme bolgesi (data residency) uc noktalari, 5 Mart 2026 sonrasi yayinlanan uygun modeller icin %10 ek ucret aliyor.
