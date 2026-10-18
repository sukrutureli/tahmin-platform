# Dinamik özel rapor arşivi

Cloudflare Worker bir kez güncellenir. Giriş sonrası `raporlar/` altındaki bugün/dün tarih klasörlerini GitHub Contents API üzerinden listeler; seçilen klasördeki HTML dosyalarını isimlerinden bağımsız gösterir. Yeni dosya için Worker değişikliği gerekmez. HTML içindeki sıralama/filtre JavaScript kodu çalışır; raporlar kendine yeterli HTML olmalıdır.

Üretim Daily/Control mevcut HTML'nin day-title tarihini doğrulayarak aynı tarih klasörüne kopyalar. Deney private_reports tüm izinli HTML raporlarını aynı arşive yazar. İstanbul gününe göre iki gün önce ve daha eski arşiv klasörleri her yayın sırasında silinir. Deneyin tarihli JSON değerlendirmeleri 14 günlük kıyas için korunur. Silme git geçmişini yeniden yazmaz; geçmiş commitlerin boyutu ayrıca kalır.

Worker Secrets: PANEL_PASSWORD, SESSION_SECRET, GITHUB_TOKEN aynı kalır. `cloudflare-panel/worker.mjs` dosyasını bir kez Edit code alanına yapıştırıp Deploy edin. Sonraki HTML/tarih değişiklikleri otomatik okunur. Yeni rapor elle eklemek için `raporlar/YYYY-MM-DD/rapor-adi.html` kullanın. Panel yalnız bugün ve dünü sunar.
