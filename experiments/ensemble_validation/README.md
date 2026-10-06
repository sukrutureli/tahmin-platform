# Mevcut ensemble'ın pazar ve geçmiş deneyi

Üretim modelleri ve Application sınıfları aynen kalır. Ek Java replay sınıfları
aynı BettingAlgorithm sınıflarını çalıştırır. Baseline, yayınlanmış Match JSON'u
ve ilk oranlarla yeniden hesaplanır. Yayınlanmış olasılık/skor ile parity
1e-8 toleransta doğrulanmazsa workflow başarısız olur.

Futbol: EvidenceWeightedModel, SimpleHeuristicModel, FormMomentumModel ve
gerçek EnsembleModel ayrı; PoissonGoalModel ayrıca teşhis amaçlı. Basketbol:
HeuristicPredictor, FormMomentumModel ve gerçek ensemble ayrı. NormalizedFormModel
sadece eski /10 form zayıflatmasını kaldıran bağımsız adaydır; üretim sınıfı değişmez.

Futbolun orijinal form modeli eksik/sıfır MS oranlarında 1/0 ve Infinity/Infinity
nedeniyle NaN üretiyor. ValidOddsFormModel üç oranın tamamı geçerli değilse yalnız
bu modelin piyasa karışımını atlar; form hesabını korur. EnsembleValidOddsForm
aynı ensemble'a bu güvenli adayı ekler. Bu iki deney sınıfı üretimi değiştirmez.
Geçersiz orijinal hesaplar sayılır ve açıkça dışlanır; eğitim kapsamı baseline ile
tam eşleşmeyen bir aday ağırlık seçiminde yarışamaz.

## Veri deneyleri

Eski altı girdi; dengeli altı; basit geniş geçmiş; yalnız güncellik; yalnız saha;
dengeli geniş; güncellik/saha/form çıkarılmış sürümler ve H2H çıkarılmış kontrol.
Altı maç için de basit ve güncellik/saha/form çıkarılmış kontroller bulunur.
Eski arşivin yıl içermeyen Türkçe kısa tarihleri, listenin en yeniden eskiye
sıralandığı varsayımıyla maç gününden geriye doğru yıl çıkarılarak okunur.
Aynı gün satırları alınmaz. Ham tarih ve dateInferred/inferredDateCount kaydedilir;
yılı çıkarılan tarihler doğrulanmış tarih değildir. Bir yıldan uzun ara veren
takımlarda belirsizlik kalır; güncellik katkısı bu sınırlamayla yorumlanmalıdır.
Geniş geçmiş, önceki deneyin 1 Ekim artifact'indeki dondurulmuş takım havuzundan
gelir; yeniden HTTP istekleri yoktur. Önceki günlerde sadece aynı tam takım adıyla
eşleşen takımların geniş geçmişi bulunur. Geniş geçmiş geriye dönük tüm maçlarda
varmış gibi gösterilmez. Her kıyasın N değeri ve ortak baseline kohortu ayrı yazılır.

Genel geçmiş futbol 20, basketbol 25 üst sınır. Güncellik yarılanma ömrü 90/60 gün,
hazırlık ağırlığı 0.25; dengeli sürüm genel %40/saha %35/son altı %25.
Yalnız küçük saha örneği takımın kendi genel ortalamasına çekilir (önsel güç 4).
Ligden bağımsız 80 sayı / 1.35 gol önseli, veri puanıyla ikinci olasılık baskılama
ve ek oran karışımı yoktur. Basketbol formu bilinen son galibiyetle, ortalamaları
normal süre skoruyla hesaplanır. Bilinmeyen uzatma sonucu kayıp sayılmaz.

## Seçim ve doğrulama

29/30 Eylül eğitim; 1 Ekim ayrı kontrol günü. 1 Ekim sonuçları ağırlık/eşik/skor
adayı seçimine girmez. Önceki günler her pazar için ensemble ağırlığı en az %50
kalacak şekilde önceden belirlenen .25/.5 alt model karışımlarını kıyaslar.
Amaç önce log loss; seçicilik ayrıca minimum 20 eğitim seçimi ve %25 kapsamla
ölçülür. Bu yalnız araştırma adayıdır; 2 gün optimal ağırlıkları kanıtlamaz.
Geniş geçmiş eski günlerde yeterli kapsama sahip olmadığından bu ağırlık
aramasına sokulmaz; ayrı eşleşmiş kıyas ve sonraki günler için kayıt vardır.

MS, OU, KG ayrı. MS1/MSX/MS2/Alt/Üst/Var/Yok için seçilen örnek sayısı,
isabet, %95 Wilson aralığı, Brier/log loss ve kapsam raporlanır. N=0 isabeti
%0 veya %100 diye gösterilmez. Handikap, periyot, oyuncu bahisleri için model
yoktur; bu rapor bunları kapsadığını iddia etmez. HTML'de her pazarın yönü ve
yüzdesi hep görünür, eğitimden seçilen eşiği geçen aday ayrı belirtilir.

Skor özelliği kalır: orijinal model skorları, futbol Poisson beklenen golleri
ve basketbol normalize form skorları karşılaştırılır. Takım MAE/RMSE, toplam,
fark hatası ve yuvarlanmış tam skor isabeti ölçülür. Skor adayı önceki günlerin
MAE'siyle seçilir. Üretim RealScores settlement etiketi kullanılır; futbolda
uzatma/penaltı skoru normal süre tahminiyle farklı hedef olabilir.

Özellik çıkarma sonuçları ilişkisel teşhistir; bağımsız nedensel önem kanıtı
değildir. 1 Ekim henüz tamamlanmamış maçları ve eşleşmeyen sonuçlar dışlanır.
Olasılık eğitiminde sonuç sızıntısı yoktur; öğrenilmiş kalibrasyon henüz yoktur.
Artifact/source SHA'ları ve giriş hash'leri kaydedilir. Main'e geçiş veya
yayın/Telegram yoktur; daha fazla bağımsız gün olmadan otomatik terfi kapalıdır.

## Bugünden kural çıkarma (ayrı araştırma)

Replay hesaplandıktan sonra bugünün bitmiş sonuçları mevcut ResultApiClient ile
yenilenir. Yalnız artifact replay etiketi değişir; üretim dosyası, Application,
Telegram veya control workflow'u çağrılmaz. Canlı maç skoru alınmaz, 429 cooldown
ve mevcut 500 ms istek aralığı korunur. Başarısız istekler ve arşiv/güncel farkları
spor başına outcome-audit.json içinde izlenir. Model girdileri yeniden üretilmez.

today-rules.html ve frozen-today-rules.json, kullanıcı isteğiyle bugünün
sonuçlarından ayrı aday kurallar çıkarır. Önceki günlerde seçilen adayların
bağımsız kontrol tablosu korunur. Bugünden öğrenilen adayın bugünkü isabeti
eğitim başarısıdır; doğrulama başarısı diye sunulmaz. Sabit veri sürümü ve
ensemble karışım ızgarasından her pazar için en düşük bugünkü log loss seçilir;
seçilecek aday aynı maçlarda bugünkü isabeti legacy ensemble'ın altına düşüremez.
Bu bir eğitim kısıtıdır; yarın daha kötü sonuç çıkmayacağını garanti etmez.
skor için aynı kapsamda en düşük takım MAE seçilir. Geniş geçmiş/alt model
yoksa legacy ensemble'a dönüş önceden belirtilir; kötü maçlar düşürülmez.
Kurallar 2 Ekim ve sonrası için dondurulur, otomatik üretime alınmaz.


## Pazar özellikleri ve günlük defter

HistoryBttsModel, gol atma/yeme ve tarihsel KG sıklığını Beta(1,1)
yumuşatmasıyla kullanır. HistoryTotalsModel futbolda tarihsel Üst sıklığını
hücum/savunma gol beklentisiyle, basketbolda beklenen toplamı geçmiş toplam
skor varyansı ve o maçın baremiyle birleştirir. 8 sayı basketbol standart
sapma tabanıdır; öğrenilmiş lig parametresi değildir. Bunlar sabit deney
hipotezleridir; orijinal üretim modeli değiştirilmez. Yalnız doğru pazarda
yarışırlar. error-diagnostics.json ve errors.html doğru/yanlış maçların
özelliklerini, örnek sayısını ve bütün hataları ayrı verir.

experiment-settings.json gün, yayımlanmış kaynak SHA'sı ve önceki başarılı
denemenin artifact/run kimliğini belirler. Önceki günden kural
before-results-predictions.json içine, güncel sonuç yenilemesinden önce
kaydedilir. Aynı günden öğrenilen kural bağımsız doğrulamada kullanılamaz.
Maç başlamadan kayıt zamanı ayrıca denetlenir; geç oluşturulan tahmin
gerçek ileriye dönük tahmin gibi sayılmaz. daily-evaluation.json ve
daily-journal.json önceki artifact defterini taşır; aynı gün tekrarında
satırları çoğaltmaz. Günlük snapshot'ta henüz bitmeyen maçlar paydada
yoktur; bu yüzden farklı snapshot'ların N değerleri değişebilir.

Geniş geçmiş havuzu hâlâ dondurulmuş 1 Ekim referansından gelir; sonraki
günlerin yeni takımlarında yoksa altı maç/baseline kullanılır. Yeni
takımlar için güncel geniş API havuzu toplanmış gibi gösterilmez.
GitHub schedule sadece default branch'te çalıştığından main'e cron
eklenmez; günlük deney ayrıca ChatGPT görevinden settings dosyası
güncellenerek tetiklenir. Çıktılar sadece Actions artifact'tir.

## KG bağımlılık kontrolü (2 Ekim deneyi)

HistoryCoupledBttsModel, gol atma ve gol yeme sıklıklarının çarpımına ek
olarak takımın tarihsel ortak gol frekansını kullanır. Her takım için
KG / (gol-atma * gol-yeme) oranı 0.5–2 bandında tutulur; iki takımın
geometrik ortalaması karşılaşma çarpımını düzeltir. Bu sabit deney
hipotezi 29/30 Eylül ve 1 Ekim'de basit KG modelinin tekrar eden zayıf
sonucundan türetilmiştir; hiçbir 2 Ekim sonucu parametre seçiminde
kullanılmamıştır. Sonuç sızıntısı ve sınır testleri vardır.
Bu adayın 1 Ekim'de basit KG adayından iyi çıkması, üretim ensemble'ından
iyi olduğu anlamına gelmez. Başarısız adaylar raporda kalır.
2 Ekim'in ilk kayıt dosyası yeniden kullanılacak; yeni aday mevcut
dondurulmuş tahminleri değiştirmez. Geniş havuz 1 Ekim'den kalmaktadır.


## Çok günlük güvenlik kuralı (3 Ekim adayı)

2 Ekim'de 1 Ekim'den tek günle seçilen kurallar; ileriye dönük 104 futbol ve
54 basketbol maçının çoğu pazarında mevcut sistemden düşük isabet verdi. Bu nedenle
ertesi gün kuralı artık tek son güne uydurulmaz. Tamamlanmış bütün kaynak günler
birlikte değerlendirilir; adayın her bir günde legacy ensemble isabetinden düşük
olmaması, toplam isabetinin de düşük olmaması ve en az 10 ya da örneklerin yüzde
10'unda gerçekten farklı hesap üretmesi gerekir. Bu koşulları geçen adaylar
arasından toplam log loss en düşük olan seçilir. Skor adayında aynı mantık her gün
legacy takım MAE'sini geçmeme koşuluyla uygulanır. Bu yalnız deney seçimidir;
otomatik üretim terfisi hâlâ kapalıdır.

## 5 Ekim deney onarımı ve oynaklık adayı

Aynı kısa takım adlarıyla kaydedilen U21/büyük takım karşılaşmaları artık Match ve
PredictionResult sırası doğrulanarak eşlenir; tekrar eden adlar ilk oranlarla
ayırt edilir. Belirsiz eşleşme hata verir; parity toleransı değişmez.

VarianceShrinkTotalsModel yalnız basketbol Alt/Üst adayıdır. 3 ve 4 Ekim hata
kohortlarında toplam skor standart sapmasının daha yüksek olmasından türetilen
hipotezdir: p = 0.5 + (HistoryTotals p - 0.5) * min(1, 8 / sigma).
8 mevcut sigma tabanıdır; sonuçlardan ayarlanmış eşik değildir. Skor değişmez,
sonuç etiketi okunmaz. Bu ilişki nedensellik veya bağımsız başarı kanıtı değildir.
5 Ekim adayın geliştirme günüdür; aynı gün başarısı bağımsız doğrulama sayılmaz.
Önceki başarılı artifactlerdeki tahminler değişmez; başarısız 5 Ekim parity
artifact'i teşhis içindir ve doğrulanmış tahmin kaydı olarak kullanılmaz.

## 6 Ekim koşullu kalibrasyon gölge deneyi

conditional_rules.py, sabit model karışımlarından ayrı olarak tek koşullu
olasılık kalibrasyonunu araştırır. Özellik/eşik yalnız hedef tarihten önceki
satırlardan seçilir; son tamamlanmış kaynak gün kronolojik kontroldür. Eğitimde
20 baseline önsel örneği kullanılır, karışım yüzde 25/50 ile sınırlıdır.
Basketbolda gol atamama/KG/2.5-gol frekansları aday ve hata teşhisinden çıkarılır.
Hedef günün sonuçları seçime giremez. Eksik özellikte baseline korunur.

Geçmiş kontrolde yeterli N ile isabet düşmeden log loss iyileşirse koşullu aday
etkinleşir. Elenen/az örnekli aday da researchProbabilities olarak ayrı kaydedilir
ve başarısızlıkları gizlenmeden sonraki günlerde sınanır. İlk kayıt ve kural
parametreleri 7 takvim günü sabittir; aynı gün tekrarında dosya byte olarak
yeniden kullanılır. conditional-before-results.json/conditional-evaluation.json
ve conditional-rules.html günlük daybook'tan ayrıdır; mevcut tahmin, skor,
main ve Telegram değişmez. İlk geliştirme günü 6 Ekimdir; geçmiş kontrol
bağımsız başarı değildir. Lig/rakip gücü henüz eklenmemiştir; geniş havuz hâlâ
1 Ekimden dondurulmuştur, güncel geniş HTTP havuzu toplanmış gibi gösterilmez.
