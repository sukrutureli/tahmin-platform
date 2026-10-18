# Eski ve yeni raporların paralel izlemesi

Üretim Daily Prediction ve Control aynı algoritma ve Telegram davranışıyla kalır.
Başarılı main run'ından sonra Parallel experimental reports, ayrı deney branchine
workflow_dispatch gönderir. Main'deki ensemble workflow dosyası sadece boş dispatch
arayüzüdür; model uygulaması main'e taşınmamıştır.

Yeni günlük gün başlamadan önce önceki günün mevcut dondurulmuş artifact'i varsa
HTTP sonuç kontrolü yapılır; ardından yeni gün, bu başarılı artifact üzerinden
oluşturulur. O günün tahmini zaten varsa yeni günlük hesap yerine kontrol çalışır.
Üretim run ID'siyle aynı istek tekrarında yeni tahmin/run oluşturulmaz. Kontrol için
o güne ait kayıt yoksa geçmişe yeni tahmin uydurulmaz. İstanbul saatinde 06:00 öncesi
üretim Control'ün önceki günü kullanması burada da korunur.

Yeni tahminler deneyin daha uzun geçmiş toplama adımından sonra hazır olur; eski
Daily/Control bunları beklemez. Eksik yeni rapor panelde 'henüz hazır değil' görünür.
Tarayıcıdaki görünüm tahmin oluşturulması değil, kaydedilmiş dosyanın gösterimidir.

İki rapor futbol-yeni.html ve basketbol-yeni.html olarak private fathertahmin'de
deney/reports/YYYY-MM-DD/ altında saklanır. Aynı gün Control sadece sonuçları ve
raporu yeniler; tahmin/model dosyalarının hash'leri doğrulanır. Anahtar GitHub Secret'ta
kalır. Büyük veri seti, ham HTTP ve loglar şifreli artifact dışında yayınlanmaz.

Aynı tarihli checkpoint-manifest.json ve stability/context/daily evaluation kopyaları
sonuçların kaynağını tutar. Gece yarısından sonra önceki güne gelen sonuçların güncel
kıyasını o günün tarihli raporundan okuyun. current/ son güncellenen güne işaret eder;
bu her zaman takvimde bugün değildir. Kümülatif kıyası her günün en son tarihli
stability-evaluation kopyasından hesaplayın; daha önce sonraki güne taşınmış bir
journal eski günün gecikmiş sonuçlarını henüz içermeyebilir.

Cloudflare ana sayfa Futbol, Basketbol, Futbol Yeni ve Basketbol Yeni bağlantılarını
gösterir. Yeni yönlendirmeler /futbol-yeni/ ve /basketbol-yeni/; bugün/dün ayrı kalır.
Worker kodunu mevcut Cloudflare editöründe güncelleyip Deploy etmek gerekir; aynı
Secret'lar korunur. Kimlik doğrulaması yapılmadan hiçbir özel rapor okunmaz.

opponent-locked-v1 ağırlıkları ve parametreleri sabittir; takım gücü girdileri güncel
geçmişle hesaplanır. 18 Ekim kaynak/ön izleme; ilk bağımsız gün 19 Ekimdir. En az 14
ölçülmüş gün sonunda her sistemin kendi en yüksek pazarı ve kendi güven sırasındaki
ilk %50 karşılaştırılır; %25/%75/tümü ek ölçüdür. Otomatik main terfisi yoktur.
