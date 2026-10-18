# Kartsız özel tahmin paneli — Workers Free

Bu sürüm Zero Trust/Access, Pages, özel alan adı, R2 veya ücretli plan gerektirmez. Worker girişten sonra GitHub Contents API üzerinden yalnız `sukrutureli/fathertahmin` main dalının futbol/basketbol rapor ve data yollarını okur. Her yenilemede güncel dosyayı ister; Daily/Control sonrası yeniden deploy gerekmez. Şifre/token hiçbir yanıtta veya uygulama logunda yazdırılmaz. GitHub kullanım limitleri ve token süresi yine geçerlidir.

## Mevcut Worker'a kurulum

1. Worker: `jolly-lake-9037`, adres: `https://jolly-lake-9037.sukrutureli.workers.dev`.
2. Settings → Variables and Secrets altında üç Secret tanımlayın:
   - PANEL_PASSWORD: en az 12 karakter; tercihen parola yöneticisinden üretilmiş uzun rastgele şifre.
   - SESSION_SECRET: farklı, en az 32 karakterlik rastgele değer.
   - GITHUB_TOKEN: fine-grained, yalnız fathertahmin, Contents: Read-only. Cron tetikleme token'ı değildir.
3. Edit code içindeki Hello World kodunun tamamını `worker.mjs` içeriğiyle değiştirip Deploy yapın. Dosya adının editörde worker.js olarak kalması sorun değil; Modules Worker (`export default`) biçimidir. Ek paket, import veya build gerektirmez.
4. Statik assets binding eklemeyin; bu Worker bütün yolları kendisi yönetir. Static asset/Pages dağıtımı bu sürümün parçası değildir.
5. Preview URL kapalı kalsın. Production adresinden giriş ekranı → doğru şifre → futbol/basketbol raporları doğrulansın. Tarayıcı parola yöneticisine şifreyi kaydedebilir; imzalı oturum 7 gün sürer. Şifre veya SESSION_SECRET değişince eski oturumlar geçersiz olur.
6. Gizli sekmede doğrudan `/futbol/`, `/basketbol/` ve mevcut bir `/futbol/data/MatchInfo-YYYY-MM-DD.json` adresini açın: giriş ekranına yönlenmeli. Kaynak HTML'de token bulunmamalı. Yanlış şifre erişim vermemeli. Girişten sonra iki raporda filtre/sıralama çalışmalı. Çıkış yapıldıktan sonra erişim tekrar engellenmeli.
7. Gerçek private repo okuması, tahmin-platform hazırlığı devreye alındıktan ve fathertahmin private yapıldıktan sonra ayrıca doğrulanmalıdır. Panel çalışması public Actions artifact/loglarını gizlemez; hazırlık PR'ındaki geçiş adımları ayrıca tamamlanır.
8. Panel gerçek telefonda doğrulanmadan Telegram kapatılmaz. Panel doğrulandıktan sonra Telegram workflow'u kullanıcının tercihiyle devre dışı bırakılabilir.

## Davranış ve sınırlar

Giriş kontrolü yalnız istemci JavaScript'i değildir; GitHub isteğinden önce sunucuda yapılır. Oturum HMAC-SHA256, HttpOnly/Secure/SameSite=Strict ve __Host- cookie ile korunur. Kimlik gerektiren tüm yanıtlar `private, no-store`; upstream redirect'leri takip edilmez. Hata gövdeleri kullanıcıya aktarılmaz. Yetki yokken veya secret eksikken veri servis edilmez. CORS açılmaz. İzin verilen yollar sabit repoyla sınırlıdır.

On deneme/dakika/IP için isolate belleğinde ek sınır vardır; dağıtık/global bir brute-force garantisi değildir. Güçlü, farklı bir parola gereklidir; daha sıkı koruma gerekirse ayrıca Turnstile veya platform rate limiter eklenmelidir. Parola bilen erişebilir; bu e-posta kimlik doğrulaması değildir. Session cookie ele geçirilirse süresi dolana veya secret değişene kadar kullanılabilir.

Bu dağıtım private veriyi statik asset olarak barındırmadığından Free limitine ulaşılması public HTML'ye düşmemelidir; gerçek ortamda kota ve hata senaryoları ayrıca kontrol edilir. Şifreli Actions artifact zinciri panelden bağımsızdır. Workers Free planı seçili tutulmalı; ücretli ürün/deneme yükseltmesi yapılmamalıdır.

Test: `node --test cloudflare-panel/worker.test.mjs`

17 test; sentetik env/token kullanır. Cloudflare hesabındaki gerçek secret'ları, private repo erişimini veya mobil tarayıcı davranışını bu testler doğrulamaz.

## Mobil form düzeltmesi

Login yanıtlarında Referrer-Policy `same-origin` olmalıdır. `no-referrer` normal HTML form POST isteğinin Origin bilgisini null yapabilir ve aynı-kaynak kontrolü haklı olarak isteği reddeder. Null veya yabancı Origin kabul edilmez; tarayıcıya doğru policy verilir. Plain-text yanıtlar UTF-8 belirtir. Deploy sonrası eski giriş sayfasını yenileyin.

## Gün seçimi

Varsayılan gün Europe/Istanbul tarihidir. Panel bugün/dün arasında geçiş verir. Her spor için seçilen günün PredictionData dosyasını en son değiştiren main commit seçilir ve HTML o commit üzerinden okunur. Böylece gecenin Control çalışmasının dünün sonuçlarını ana HTML üzerine yazması bugünün raporunu gizlemez. Bugünün kaydı yoksa dünün raporu bugünmüş gibi sunulmaz. Bugün/dün sınırı mevcut cleanup saklama süresiyle uyumludur.
