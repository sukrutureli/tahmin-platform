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


## 11 Ekim: günlük geniş HTTP geçmişi

1 Ekim havuzunun yeni takımları kapsamaması giderildi. live_history.py, daha önce
balanced-history deneyinde kullanılan Broadage takım takvimini tekrar kullanır.
Nesine event ID -> widget takım ID eşlemesi, API metadata takım ID doğrulaması
ve endpoint'in verdiği ay navigasyonu kullanılır. Futbol 20/basketbol 25 geçmiş
üst sınırı korunur; en çok 12 aylık sayfa taranır. Aynı gün/gelecek, canlı ve
normal süre skoru bilinmeyen uzatma satırları alınmaz. Basketbolda galibiyet
son skorla, sayı ortalamaları normal süreyle hesaplanır.

500 ms istek aralığı, tek seri istemci, takım bazlı istek önbelleği ve 45 dakika
toplama bütçesi vardır. 429 tüm toplamayı durdurur; eksiklikler saklanmaz.
Ham HTTP yanıtları, istek hataları, takım kimlikleri ve toplama zamanı artifact'e
yazılır. live-history.json aynı gün tekrarında aynen kullanılır; günlük havuzlar
live-history-journal.json ile sonraki artifact'e taşınır. prepare.py yalnız aynı
fixture günü ve event ID için bu veriyi kullanır; eski günlere bugünden geçmiş
uydurmaz. Eksik günlerde eski 1 Ekim havuzu/fallback görünür kalır.

11 Ekim ilk maç-öncesi tahminleri zaten kayıtlıdır: bu ek veri onlara uygulanmaz.
Bugün çekilen geniş geçmişten aynı gün yapılan karşılaştırma retrospektiftir.
Her geniş varyant audit'inde collectedAt/historyBeforeKickoff görünür. Yeni
günlerde geniş geçmiş dondurma adımından önce toplanır; maç-öncesi kaydı yalnız
gerçek kayıt saati kickoff'tan önceyse bağımsız sayılır. Baseline parity, skor,
main, günlük/control üretim iş akışları ve Telegram değişmez.


## 12 Ekim toplama bütçesi onarımı

11 Ekim'de tek bütçe futbol tarafından tüketildiği için basketbol hiç taranmadı.
Artık toplam 45 dakika bütçe spor başına 22.5 dakika ayrılır; futbol süresinin
bitmesi basketbolu atlamaz. 429 yine bütün HTTP toplamayı durdurur. Atlanan her
fixture hata listesinde açıkça görünür. Eski günlük snapshot'lar değişmez.
Bu altyapı düzeltmesidir; yeni tahmin kuralı veya üretim değişikliği değildir.


## 13 Ekim: geçmişten bir/iki koşullu pazar kuralları

mine_rules.py, geçmiş özelliklerinden ayrı MS1/MSX/MS2/Alt/Üst/Var/Yok adayları
çıkarır. En çok iki koşul; güncel sonuç/published pick bir özellik değildir.
Saha gol/sayı farkı, saha toplamı, hücum/savunma farkı, galibiyet oranı,
son üç / önceki üç form değişimi, KG/Üst/gol atamama sıklığı, oynaklık
ve yeterli kayıtlı geniş geçmiş varsa son-altı/geniş farkı taranır.
Rakip gücü/lig kalibrasyonu henüz yoktur; yapılmış gibi gösterilmez.

Eski başarılı 3/5/7/8/9 Ekim artifact'lerinden pruned günler geri alınır;
rule-mining-dataset.json ile günlük artifact'lerde taşınır. Threshold'lar
yalnız eğitimdeki yüzde 25/50/75 kesimlerinden seçilir. En az 40 eğitim,
15 doğrulama örneği, eğitimde en az üç ek doğru ve log loss iyileşmesi
gerekir. İlk 16 atomdan iki farklı özellikli birleşimler ve ilk 10 eğitim
adayı incelenir. Doğrulamada isabet azalmadan log loss iyileşmeli.
MSX adayı gerçekten MSX argmax üretmeli. Son iki bitmiş kaynak gün
doğrulama ve seçime hiçbir etkisi olmayan kronolojik testtir.

Çok aday araması geriye dönük overfit riski taşır; test sonucu kötü olan
aday başka adayla değiştirilmez ve gizlenmez. Bu yeni geliştirme deneyi,
bağımsız maç-öncesi kanıt değildir. mined-rules.json/html her kuralın
koşulları, örnekleri, main ile aynı kohorttaki doğru sayısı, Brier ve
log loss'u, maç listelerini ve elenen adayları gösterir.

Bu yalnız tablo üretmez: kurallar sonuç yenilemesinden ÖNCE ayrı
mined-before-results.json tahminlerine uygulanır; dışarıda baseline korunur.
Çakışmada doğrulama log loss farkıyla deterministik seçim vardır.
Aynı gün yeniden çalıştırma tahminleri byte olarak korur. Sonradan
mined-daily-evaluation.json yalnız tamamlanmış sonuçları değerlendirir;
maç-öncesi ve geç kayıtlar ayrıdır. Orijinal daybook/skor ve Telegram
değişmez. Mevcut 12 Ekim örneklerine yeni hesap geç yapılmıştır;
ileriye dönük başarı diye sayılmaz.

Hızlı Historical Subgroup Rule Mining workflow'u kayıtlı 12 Ekim artifact'i
üzerinde 10 Ekim seçim/11 Ekim dokunulmamış test raporu çıkarır.
Günlük Ensemble workflow'u bu adımları yeni günlere aynı şekilde uygular.
Main'e otomatik terfi/yayın yoktur.


## 13 Ekim: gerçek sonuçtan doğrudan öğrenme

outcome_learning.py main'i geçme koşulu olmadan gerçek sonuçtan eğitilir.
Her spor/pazar için L2 multinomial softmax; takım skorları için ridge regresyon
vardır. Ham geçmiş özellikleri, mutlak güç farkı, ev/deplasman gol/sayı
ortalamaları, geçerli ilk oranlardan marjı alınmış olasılıklar ve overround
kullanılır. Geçmiş / yalnız oran / birlikte üç özellik grubu ve .1/1/10
regularizasyon yalnız doğrulama log loss'u (skorda MAE) ile seçilir.
Main model olasılıkları/skorları bir girdi, önsel veya seçim şartı değildir.

Medyan, merkezleme ve ölçekler yalnız eğitimde öğrenilir; eksik girdiler için
medyan + eksiklik bayrağı kullanılır. Test gününün etiketleri/özellikleri
eğitimi, ön işlemeyi veya model seçimini değiştiremez. Ağırlıklar standardize
ilişkisel katsayılardır; bağımsız nedensel önem diye sunulmaz. Saha/lige göre
rakip güç düzeltmesi henüz yoktur. Skor başlığı MS/OU/KG başlıklarından ayrı
öğrenilir; sınıf olasılıkları skor dağılımından türetilmiş değildir. Skor hedefi
yayınlanmış settlement skorudur; futbolda uzatma/penaltı farkı olabilir.

İlk hızlı rapor 11 Ekim doğrulama, 12 Ekim dokunulmamış test kullanır. Bu yeni
geliştirme/geriye dönük kıyastır; ileriye dönük kanıt değildir. Küçük test N
saklanmaz; main kıyası yalnız aynı geçerli kohortta yapılır.
outcome-learning.json/html, üç özellik grubunun doğrulama metriklerini,
öğrenilen katsayıları, gerçek skorları ve maç listesini saklar.
learned-before-results.json sonuç yenilemesinden önce bağımsız olasılık/skor
kaydeder; aynı gün dosya byte olarak korunur. learned-daily-evaluation.json
live/eksik sonuçları dışlar ve maç-öncesi/sonradan kayıtları ayırır.
Üretim daybook/skor, main, control ve Telegram değişmez.

Test kıyasının modeli/eşikleri değişmez. Test raporundan sonra, seçilen aynı
özellik grubu ve regularizasyonla tamamlanmış bütün geçmiş günler üzerinde
forecastModel yeniden eğitilir; yalnız gelecek gün tahminleri için kullanılır.
Bu yeniden eğitilmiş modelin kendi eğitim günündeki sonucu bağımsız test sayılmaz.


### Fixed top-half selections

`selection.py` ranks immutable pre-kickoff learned forecasts by maximum probability separately for each sport/market and selects `ceil(N/2)` fixtures. This fixed policy never tunes thresholds against current results. Event ID breaks ties. Forecast time and selection time are separate: a subset first selected after kickoff is exploratory even if its underlying forecast was recorded earlier. Same-day selection bytes and their forecast hash are preserved; changed forecasts fail validation. Missing/live results and basketball pushes are excluded. `selection-before-results.json`, `selection-evaluation.json`, `selection-journal.json` and `selection.html` show all versus selected results, main on exactly the selected cohort, Brier/log loss, and preserved score MAE. Confidence filtering need not improve every market. Initial 13 October selection is retrospective research; subsequent pre-kickoff days test the policy prospectively.


### One choice and score per match

`match_choice.py` chooses the highest saved model probability across valid markets for each pre-kickoff fixture, independently of labels, main, and score forecasts. It selects the top `ceil(N/2)` matches per sport, not separate final lists per market. Market choices, scores, and selection timestamps are immutable. `match-choice-before-results.json`, `match-choice-evaluation.json`, and `match-choice-journal.json` separate late exploratory selections from genuine before-kickoff subsets. Chosen-event binary Brier/log loss, isabet and same-market/cohort main accuracy are recorded along with score MAE. `best-matches.html` lists all forecasted matches: time, match name, one pick, score and model confidence; default time ordering and one-click descending confidence sorting. Initial 13 October choices are exploratory. Production HTML and Telegram stay unchanged.


### Confidence subsets without hiding fixtures

The HTML displays every match with a single best market, score and confidence; top-half membership is a badge, not a visibility filter. Its default order is kickoff time, with one-click descending-confidence sorting. Statistics separately preserve fixed top 25%, 50%, 75% and 100% cohorts per sport, ranked from frozen probabilities without outcomes. `confidenceSubsets` in `match-choice-evaluation.json` and the daily journal include planned count, finished sample count, accuracy, Wilson 95% interval, mean forecast confidence, calibration gap, chosen-event binary Brier/log loss, score MAE and prospective-versus-exploratory separation. These nested cohorts are not independent samples. Higher hit rate in a small or single-day subset is not evidence of a general rule; compare repeated prospective days and confidence calibration.


### Exact football score distributions

`score_distribution.py` uses the independent learner's mean-goal forecasts to compare Poisson, bounded low-score dependence and negative-binomial candidates on the prior validation day's joint score log loss. The untouched later test never chooses a distribution. It predicts the modal joint score and top three alternatives with explicit exact-score probabilities, rather than rounding the mean. Original mean forecasts and same-day score/choice snapshots are preserved byte-for-byte; missing/live outcomes are excluded. Intensity is bounded to [0.05,12] for football stability, distributions still assign probability to scores beyond the bounded modal search. Basketball remains on its existing score method. `score-before-results.json`, `score-distribution.json/html` and `score-distribution-evaluation.json` separately record modal exact hits, rounded-mean comparison, team/total/margin MAE and joint log loss. Exact-score accuracy and MAE are different objectives: a more likely exact score can have worse MAE. First 13 October modal forecasts are retrospective development. Future first-day `best-matches.html` uses modal football scores and shows their probability separately from market confidence. Never force a score to agree with a market pick; these remain separately measured models.


### Scores conditional on the selected preference

`conditional_score.py` chooses football scores only within the saved MS/OU/BTTS event; conditional probabilities and original joint probabilities are separate. Basketball uses a Gaussian residual covariance fitted only on prior training matches, and chooses a compatible non-tied integer score. Market choice/rank never sees outcomes or the score candidate. `match-choice-evaluation.json` now reports conditional-score MAE/exact hits separately from independent score forecasts. Existing same-day choice snapshots remain byte-identical. Sparse validation days pool earlier days until 20 samples, retaining the latest completed date as untouched test; validation dates are explicitly recorded.

### On-demand experimental control

Control reuses a successful same-date artifact, refreshes finished outcomes through HTTP, and rerenders daily/selection/score reports without refitting models, collecting history or regenerating any forecast. `control-provenance.json` proves all frozen forecast and fitted-model SHA256 hashes were preserved. Pending/live results and pushes remain excluded. `best-matches.html` displays actual scores and preference results as well as all forecasts.

GitHub's manual workflow input supports `mode=control`, optional `target_date`, and optional `source_run_id`. Since this workflow file exists only on the experimental branch, the Run workflow button may not appear while GitHub requires the file on the default branch; main is deliberately unchanged. Branch-only fallback: edit `experiments/ensemble_validation/experiment-settings.json`, set `control_target_date` to the current `target_date` and update `control_request_at` to a fresh ISO timestamp, then commit only on `experiment/ensemble-market-validation`. This triggers the control build and automatically finds the latest successful same-date artifact. For another check of that day, change the timestamp again. A first daily artifact is mandatory; control fails clearly if none exists. When advancing `target_date` to a new date, the old `control_target_date` no longer matches and normal daily prediction/training resumes automatically. To run daily for the same date, remove `control_target_date`. Concurrent experiment checks queue instead of cancelling an in-flight first daily run. Production control and Telegram are untouched.


### 14 October: display late fixtures without counting them as prospective

The single-choice HTML also displays fixtures whose saved forecasts were created after kickoff, marked as late/out of cohort. Those rows receive no confidence rank and cannot change the fixed top 25/50/75/100% sample sizes or success metrics. Market and score settlement evaluate original pre-kickoff forecasts only; selection timing remains independently tracked. Existing same-day snapshots are still reused byte-for-byte. This fixes the visible omission of early-morning fixtures without retrospectively turning them into forward predictions.


### 15 October: opponent strength / competition ablations (no promotion)

`context_features.py` keeps provider/sport/team IDs, raw season IDs when supplied,
and a separate deduplicated finished-match ledger. Old `live-history*.json` and
native forecasts are never rewritten. Current raw cached team schedules hydrate
missing opponent IDs; no team-name joins are permitted. Broadage and Nesine IDs
are different namespaces. Conflicting copies of a match are quarantined, with
persistent tombstones; missing IDs remain missing. Historical context rebuilt
from later collections is explicitly retrospective, even though every feature
uses outcomes strictly before its fixture date. Same-day outcomes are excluded;
Elo changes are batched per calendar day, never dependent on same-day ordering.

An optional one-hop scan uses the existing verified endpoint/account and a shared
serial 500ms client. It first resolves at most 60 exact old training-fixture IDs
for sports with sparse context; p1 sport/home/away IDs are verified and no names
are used to match teams. These retrospective bindings and timestamps persist
separately. It then alternates sports, at most 8 sparse opponent nodes and two
endpoint-supplied calendar pages per node, with a 90-second request deadline.
No recursive crawl or guessed pagination; a 429 stops all extra requests. Cache,
identity mismatches, coverage gaps and request errors are saved in the artifact.
The extra scan's actual collection timestamp is retained; it is not backdated.

Four arms are retained: unchanged independent learner (`baseline`), opponent-only,
competition-only, and both; production `main` is a fifth comparison, not a training
input. Opponent context is date-causal Elo (fixed K=.15, sparse shrinkage 5),
opponent-adjusted goal/point margin and historical opponent strength. Competition
context uses trailing-365-day goal/point totals, home advantage, variability and
football KG/Over rates, shrunk by 30 prior observations towards the available
sport pool. Season IDs are not guessed when absent; this is a rolling-window
competition feature, not a claim of complete season data. Baseline native model
selection is unchanged. Each new arm uses its own prior validation for feature
mode/L2 selection and retains the same untouched chronological test.

A context head requires at least 30 training and 10 validation fixtures with its
required context features. Otherwise it copies the unchanged baseline model and
explicitly records `fallback-insufficient-context`. A fully covered new day does
not imply sufficient historical training coverage. Candidate results and failures
remain visible; no winning backtest arm is automatically promoted to native HTML,
main, production daily/control workflows or Telegram.

`context_experiment.py prepare` runs before outcome refresh, in both experiment
daily and experiment control. Same-date candidate forecasts, model reports,
feature bank and ledger are copied byte-for-byte, protected by hashes. Existing
native model/snapshot hashes remain separately checked by control_runtime.
`context_experiment.py settle` evaluates only completed common outcomes; live,
missing and pushes are excluded. `context-before-results.json`,
`context-learning.json`, `context-features.json`, `context-ledger.json`,
`context-enrichment.json` and `context-evaluation.json` provide provenance.
The first development day is 15 October; old-day tests and same-day results are
research. Future pre-kickoff snapshots are tracked separately; benefit must repeat
prospectively before activation is considered.

**Default system comparison:** each system independently picks its own maximum
probability market (MS/OU/KG football, MS/OU basketball), then ranks its own matches
by that confidence. Compare all fixtures and fixed top 25/50/75% separately per
sport, with N, hits, Wilson interval, chosen-event binary Brier/log loss and score
MAE. Ranks include pending matches; measurement uses common completed fixtures.
All-fixture cohorts match, while confidence subsets may contain different matches.
Do not describe `mainSameMarkets` from the old single-choice report as main's own
selection performance: it is a separate conditional diagnostic. The new default
comparison is `context-comparison.html` / `context-evaluation.json`, retaining all
candidate arms and unchanged baseline/main.

Score diagnostics retain mean and conditional scores separately. Football exact
score distribution selection uses prior validation only; untouched-test exact
hits, modal concentration, joint log loss, 4+ goal observed/predicted frequency
and Brier are saved. Basketball high totals use the training 90th-percentile
threshold and validation residual scale; both sports report untouched-test
coverage of a validation-derived total interval. Large scores are never injected
for cosmetic variety. Kadro/sakatlik and xG are not added: no verified historical
pre-kickoff source is currently available.
