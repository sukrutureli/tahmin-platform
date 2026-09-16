# tahmin-platform

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
