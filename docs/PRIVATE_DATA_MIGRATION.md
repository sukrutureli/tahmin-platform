# Private fathertahmin hazırlığı

Durum: hazırlık branch'i. Main, çalışan deney branch'i, Telegram ve repo görünürlüğü değiştirilmedi. Bu değişiklik tek başına gizlilik sağlamaz; aşağıdaki geçiş tamamlanmalıdır. Hesaplama kodu public kalır.

## Ne hazır?

- Daily/Control üretimleri ve kontrol seed'leri public artifact'e çıkmadan AES-256-GCM ile şifrelenir. Job'lar aynı dosyaları doğrulayarak çözer. Anahtar eksik/yanlışsa veya içerik bozulmuşsa plaintext'e dönülmez.
- Uygulama stdout/stderr çıktısı public log yerine şifreli tanı artifact'inde tutulur. Hata çıkış kodu korunur.
- Private fathertahmin checkout'ları özel okuma token'ı kullanır. Push ayrı yazma token'ı kullanır. Mevcut ADMIN_USER geçiş uyumluluğu için fallback'tir; yetkisi gerçekten kontrol edilmelidir.
- İki Java JsonReader ve basketbolun ek updater okuyucusu GitHub Contents API raw yanıtını kullanır. 401/403 sessizce boş veri sayılmaz; timeout uygulanır.
- docs/migration/ensemble-market-validation.yml deney workflow'unun şifreli taşıma taslağıdır; main'de deney kodu olmadığı için aktif workflow olarak eklenmemiştir. Etkinleştirirken güncel deney workflow'una aynı script uygulanmalı, bu snapshot körlemesine kopyalanmamalıdır.
- Panel export'u yalnız mevcut futbol/basketbol HTML'lerini alır; veri klasörlerini ve GitHub token'ını tarayıcıya taşımaz. Bu HTML'lerin içinde görüntülenen veri doğal olarak bulunur.
- Access denetimi anonim isteklerin HTML/veri yollarında giriş kapısına yönlendiğini kontrol eder. Bu test tek başına email allowlist'ini veya preview adreslerini doğrulamaz.

## GitHub Secrets

Tahmin-platform → Settings → Secrets and variables → Actions:

1. FATHERTAHMIN_READ_TOKEN: yalnız fathertahmin için Contents: Read. Fine-grained token private repoya da erişmeli.
2. FATHERTAHMIN_WRITE_TOKEN: yalnız fathertahmin için Contents: Read and write. Repo içindeki .github/workflows dosyalarına dokunulmaz; Workflows yazma yetkisi gerekmez.
3. PRIVATE_ARTIFACT_KEY: 32 rastgele byte'ın base64 değeri. Örnek üretim: `openssl rand -base64 32`. Anahtarı sohbete veya repoya koymayın. GitHub Secret olarak kaydedin, güvenli yedeğini saklayın. Değişirse eski artifact'ler eski anahtarla açılır; plansız rotasyon yapmayın.

Cron-job.org için oluşturulan yalnız Actions yetkili token bu Contents token'larının yerine geçmez. Cron isteğinin URL/body/ref ayarı aynı kalır.

## Doğrulama ve geçiş sırası

1. Private data readiness CI test/compile başarılı olsun. Manual export-panel, kaynak HTML'leri okuyup yalnız şifreli çıktı üretsin. Bu test private görünürlük değişimini veya yazma yetkisini tek başına kanıtlamaz.
2. Fathertahmin geçmiş dosyaları/deney son başarılı artifact'i güvenli yedeklensin. Deneyin şifreli taşıma değişiklikleri ve helper'ları deney branch'ine ayrı commit ile alınsın; model dosyaları/parametreleri değiştirilmesin. Hazırlık kodu deney branch'ine otomatik merge edilmez.
3. İlk şifreli günlük çalıştırmadan önce `migrate-private-artifact.yml`, deney branch'inde açıkça seçilen son başarılı plaintext artifact'i yeniden hesaplamadan şifrelesin. Roundtrip testi tüm kaynak dosyaların SHA-256 değerlerini karşılaştırır. Yeni migration run ID'si previous_run_id olarak kullanılır; artifact adı aynı tarihtir. Control kaynak seçici migration run adını tanır. İlk testte kontrol için source_run_id açık verilsin. Güncel snapshot reference/rule-mining dosyalarını içermiyorsa migration durur; eski bootstrap artifact'leri ayrıca taşınmadan çalıştırmayın.
4. Sadece şifreli son kayıttan sonraki Control'ün dondurulmuş tahminleri aynen koruduğu, sonraki Daily'nin aynı geçmişi okuduğu doğrulansın. Eski plaintext artifact'ler ve eski veri içeren public run logları bu doğrulamadan önce silinmesin. Silme sonrası daha önce alınmış kopyalar geri alınamaz.
5. Panel için Cloudflare hesabında Pages projesi boş içerikle hazırlansın. Access yalnız sahibin tek e-postasına izin versin; One-time PIN etkinleşsin. Everyone/Bypass kuralı olmasın. Ana proje.pages.dev, *.proje.pages.dev preview'ları ve varsa özel alan adı ayrı ayrı korunsun. Gerçek rapor yüklenmeden her adres anonim/gizli sekmede ve izinli hesapla denetlensin. `python scripts/privacy/verify_access.py https://proje.pages.dev` yardımcı denetimdir; yalnız başına yayın izni değildir.
6. Cloudflare GitHub entegrasyonu yalnız private fathertahmin repoya bağlanabilir. Build: bu helper'ı o repoya taşıyarak `python3 scripts/privacy/build_panel.py --source . --output site`; output: `site`. Helper henüz fathertahmin'a eklenmedi, bu adımı tamamlamadan build komutunu kullanmayın. Production dalı main; preview deploy'ları kapatın veya tamamını Access'e alın. GitHub Actions'tan Cloudflare'a ayrıca ücretli build taşımak gerekmez. Kotalar/ücretsiz plan hesapta doğrulanmalıdır.
7. Tüm hazırlıklar doğrulandıktan sonra üretim privacy değişiklikleri main'e alınsın; günlük/control trigger saatleri değişmesin. Birer gerçek Daily/Control doğrulansın. Ardından fathertahmin private yapılır; private erişimde gerçek okuma/push/Telegram tekrar doğrulanır. Hata durumunda public'e dönmek yerine erişim düzeltmesi yapılır.
8. Panelin izinli ve izinsiz testi tekrar yapılsın. Chrome sabit bağlantıdan raporu açar. Telegram mevcut davranışıyla çalışır; panel linki eklemek ayrıca yapılacak değişikliktir.

## Ücret ve kapsam sınırları

Tahmin-platform public kaldığında standart GitHub-hosted hesaplama işleri private repo Actions dakikasını tüketmez. Private fathertahmin içindeki mevcut Telegram ve cleanup workflow'ları ise private Actions kotasını kullanır; aylık süreleri ölçülmelidir. GitHub Free hesabının private Actions kotası 2.000 dakika/ay ve 500 MB artifact'tir. Ücretsiz kullanım garantisi için bütçe/ödemesiz durdurma ayarı ve gerçek kullanım kontrol edilmeli; pahalı runner kullanılmamalıdır.

Private repo tek başına paneli gizlemez, noindex veya bilinmeyen URL erişim kontrolü değildir. Eski public artifact/log çıktıları ayrıca ele alınmalıdır. Public kod/veri içeren mevcut başka repolar (ör. Scraper), bu değişikliğin kapsamına otomatik girmez. Private kaynak erişimi için token'lar yalnız yetkili workflow'lara verilmeli; pull_request_target ile yabancı kod çalıştırılmamalıdır.

## Kontroller

`python3 -m pip install cryptography==46.0.3 PyYAML==6.0.3`

`python3 -m unittest discover -s tests/privacy -v`

Üretim token'ları, Cloudflare hesabı ve gerçek private repo erişimi CI fixture testleriyle doğrulanmış sayılmaz. Henüz repo private yapılmadı veya site yayınlanmadı.
