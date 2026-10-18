# Eski public Actions çıktılarını kapatma

Kapsam yalnız sukrutureli/tahmin-platform Actions artifact'leri ve run loglarıdır; git commit geçmişi, uygulama JSON'ları, Daily/Control iş akışları ve deney modelleri değiştirilmez.

Sabit sınır: 2026-10-18T00:43:00Z öncesi. Şifreli migration ve Control kaynak run'ları 39084004424 / 39084079657 ayrıca korunur. Sonraki şifreli çıktılar ve private-backup-* paketleri temizliğe girmez.

Akış:

1. plan: tüm sayfalardan mevcut eski artifact/log envanteri. Expired/404/410 arşivler atlanır; sayfalama yarım kalırsa işlem durur.
2. execute: en fazla dört paralel job. Her kaynak ZIP, mevcut PRIVATE_ARTIFACT_KEY ile AES-256-GCM olarak paketlenir, geri açılıp orijinal ZIP SHA-256 değeri karşılaştırılır. Geçici açık ZIP'ler silinir.
3. Şifreli paket GitHub artifact olarak saklanır (90 gün). Uzak artifact tekrar indirilir; her şifreli dosyanın hash'i doğrulanır. Yalnız bundan sonra karşılık gelen eski artifact veya eski run logu silinir.
4. Yeniden plan çalıştırılıp kalan eski kaynak sayısı sıfır doğrulanır. Daha önce indirilmiş dış kopyalar geri alınamaz.

Her şifreli kaynak `.enc` dosyasının içinde `archive.zip` ve orijinal run/artifact bilgileriyle `source.json` vardır. Dış proof.json yalnız kaynak kimlikleri/isimleri ve şifreli dosya hash'lerini tutar; tahmin/veri/log gövdesi içermez.

Anahtarı güvenli saklayın. Kurtarma: `PRIVATE_ARTIFACT_KEY` ortam değişkenini güvenli biçimde ayarlayın; `python scripts/privacy/artifact.py unpack artifact-<id>.enc restored` veya `logs-<run>.enc` kullanın. Ardından restored/archive.zip normal ZIP olarak açılabilir. Anahtar komut satırına veya public loga yazılmamalıdır.

Yeni backup artifact'lerinin 90 günlük saklama süresi vardır; kalıcı yedek diye değerlendirilmez. Süre dolmadan kişisel güvenli depoya taşınabilir. Günlük deneyin kümülatif kaydı ayrı şifreli artifact zincirinde korunur.
