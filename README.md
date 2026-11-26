# tahmin-platform

## Güncel günlük tercih yöntemi

27 Kasım 2026'dan itibaren yeni günlük futbol/basketbol kayıtları kullanıcının
aynı turnuvada en fazla 6 maç + genel rekabette en fazla 6 maç, %80/%20 ve son maç
destek kontrolü kurallarıyla üretilir. Tahmini skor yerine açılır hesap detayı
gösterilir; Control gerçek skoru günceller ve dondurulmuş tercihleri değiştirmez.
Önceki günlerin sabit model kayıtları korunur. [Tam kurallar](docs/USER_HISTORY_RULES.md).

Futbol, basketbol ve Nesine veri scraper'ini tek GitHub Actions orkestrasyonu altında toplamak için oluşturulan merkezi repo.

## Kaynaklar

- `football/` ← `sukrutureli/futboltahmin` / `codex-improvements`
- `basketball/` ← `sukrutureli/basketboltahmin` / `ortaklama`
- `scraper/` ← `sukrutureli/Scraper` / `main`
- yayın çıktısı (geçiş boyunca) → `sukrutureli/fathertahmin` / `main`

## Geçiş prensibi

İlk aşamada çalışan Java/Python kodu refactor edilmez. Scraper, CONTROL, algoritmalar ve spor-spesifik modeller ayrı kalır; v1'de `common` modülü yoktur.

Yeni `Daily Prediction` akışı scraper başarıyla tamamlandıktan sonra futbol ve basketbolu paralel çalıştıracak şekilde hazırlanmıştır. Geçiş testlerinde sadece artifact üretir; `fathertahmin` push ve Telegram gönderimi yapmaz.

Ayrıntılar için `ARCHITECTURE.md`, kaynak commitleri için import tamamlandıktan sonra oluşacak `IMPORT_BASELINES.md` dosyasına bakın.
