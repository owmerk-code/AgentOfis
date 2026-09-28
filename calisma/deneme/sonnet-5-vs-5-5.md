# Claude Sonnet 5 ve Sonnet 5.5 karşılaştırması

Tarih: 29.09.2026. Birincil kaynaklar: Anthropic'in resmi dokümantasyonu ve duyuru sayfaları.

## Karşılaştırma tablosu

| Ölçüt | Sonnet 5 | Sonnet 5.5 |
| :-- | :-- | :-- |
| Model kimliği (API) | `claude-sonnet-5` ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | `claude-sonnet-5-5` ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| Çıkış tarihi | 30 Haziran 2026 ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | 28 Eylül 2026 ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| Durum | Legacy, en erken 30 Haziran 2027'de emekli ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | Latest, en erken 28 Eylül 2027'de emekli ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| Girdi fiyatı (MTok) | $2 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) | $2 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) |
| Çıktı fiyatı (MTok) | $10 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) | $10 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) |
| Önbellek okuma (MTok) | $0,20 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) | $0,20 ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)) |
| Bağlam penceresi | 1M jeton ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | 1M jeton ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| En fazla çıktı | 128K jeton ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | 128K jeton ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| Güvenilir bilgi kesim tarihi | Ocak 2026 ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | Haziran 2026 ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |
| Terminal-Bench 4.0 (ajan tabanlı kodlama) | %10,3 ([kaynak](https://www.anthropic.com/claude-sonnet-5-5)) | %70,6 ([kaynak](https://www.anthropic.com/claude-sonnet-5-5)) |
| CursorBench 4.0 | %34,1 ([kaynak](https://www.anthropic.com/claude-sonnet-5-5)) | %55,5 ([kaynak](https://www.anthropic.com/claude-sonnet-5-5)) |
| Toplu (batch) çıktı üst sınırı, beta | 300K ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5/overview)) | 300K ([kaynak](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) |

Fiyat notu: Sonnet 5'in $2/$10 fiyatı başta 31 Ağustos 2026'ya kadar tanıtım fiyatıydı. Fiyat sayfasındaki dipnota göre bu artık standart fiyat ve 1 Eylül'de $3/$15'e çıkması planlanan artış olmayacak ([kaynak](https://platform.claude.com/docs/en/about-claude/pricing)).

Fiyat, bağlam ve çıktı sınırı iki modelde aynı. Fark asıl olarak kıyaslama puanlarında ve bilgi kesim tarihinde. Kıyaslama puanları Anthropic'in kendi duyurusundan; bağımsız doğrulama yapılmadı.

## Ofis için tavsiye (3 madde)

1. **Ajan ve kod işlerinde Sonnet 5.5'e geç.** Fiyat aynı ($2/$10) ama Terminal-Bench 4.0'da %10,3'ten %70,6'ya, CursorBench 4.0'da %34,1'den %55,5'e çıkıyor. Ofisin ajan ekibi çoğunlukla araç kullanan çok adımlı işler yürüttüğü için aynı parayla daha çok iş bitirmesi beklenir. (Tablo: fiyat, Terminal-Bench, CursorBench satırları)
2. **Uzun bağlam ve uzun çıktı için model seçimi belirleyici değil.** İkisinde de 1M bağlam ve 128K çıktı var, uzun belge işi için Sonnet 5'te kalmanın avantajı da yok. Maliyeti düşürmek için sabit önekleri önbelleğe al ($0,20/MTok okuma, girdi fiyatının onda biri) ve acil olmayan işleri Batch API ile ver (fiyat sayfasında %50 indirim). (Tablo: bağlam, çıktı, önbellek satırları)
3. **Sonnet 5'i yalnız geçiş süresince tut, `sonnet` takma adını 5.5'te bırak.** Sonnet 5 "legacy" ve en erken 30 Haziran 2027'ye kadar kullanılabilir; 5.5 için de fiyat farkı olmadığından eskiye dönmek için maliyet gerekçesi yok. Geçişte dikkat: 5.5'te zorla araç kullanımı (forced tool use) hata döndürüyor ve düşünme blokları modele bağlı ([geçiş notları](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)); ofis kodunda bunlar kullanılıyorsa önce sına. (Tablo: durum, model kimliği satırları)

## Yöntem notu

Taranan sayfalar:
- https://platform.claude.com/docs/en/models/sonnet-5/overview (kimlik, tarih, bağlam, çıktı, fiyat, kesim tarihi)
- https://platform.claude.com/docs/en/models/sonnet-5-5/overview (aynı alanlar, 5.5 için)
- https://platform.claude.com/docs/en/about-claude/pricing (model fiyat tablosu, batch tablosu, dipnot 3)
- https://platform.claude.com/docs/en/about-claude/models/overview (modellerin yan yana tablosu; 5.5 değerlerini teyit etti)
- https://www.anthropic.com/claude-sonnet-5-5 (kıyaslama puanları, iki model yan yana)
- https://www.anthropic.com/news/claude-sonnet-5 (Sonnet 5 çıkış duyurusu; fiyat ve kimlik teyidi)

Yöntem sınırları:
- Sayfalar bir özetleyici getirme aracıyla okundu; sayılar sayfa metnindeki tablolardan alındı, ancak metin harfi harfine kopya değil.
- Bağlam penceresi ve en fazla çıktı sayılarını duyuru sayfalarında bulamadım ("sayfada yok"); bunlar model sayfalarındaki tablolardan alındı.
- Yalnız iki kıyaslama (Terminal-Bench 4.0, CursorBench 4.0) tabloya alındı; duyuru sayfasındaki diğer kıyaslamalar alınmadı. Bu puanlar Anthropic'in kendi bildirimidir.
- "Sonnet 5.5 yaklaşık %30 daha hızlı / görev başına %30'a kadar ucuz" iddiası yalnız basın haberlerinde çıktı; birincil sayfada doğrulayamadığım için tabloya ve tavsiyeye koymadım.
- Geçiş notları (zorla araç kullanımı, düşünme blokları) 5.5 model sayfasındaki "Overview" maddelerine dayanıyor.
