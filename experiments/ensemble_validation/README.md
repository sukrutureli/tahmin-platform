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
