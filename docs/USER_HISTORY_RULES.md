# Günlük tercih kuralı · competition-six-80-20-v1

İlk yeni günlük kayıt: **27 Kasım 2026**. Önceden dondurulmuş günlükler yeniden hesaplanmaz. Ana futbol ve basketbol HTML adresleri değişmez. Eski sabit model ve ağırlıkları arşivde değişmeden kalır; yeni günlüklerin tercihini artık bu kurallar üretir. Yeni eğitim veya araştırma otomasyonu yoktur.

1. Her takım için mevcut turnuvanın en yeni en fazla altı tamamlanmış maçı alınır. O takımda bu turnuvanın geçmişi yoksa genel geçmişten en fazla altı maç kullanılır. Ev/deplasman geçmişi yer ayrımı olmadan alınır. Turnuva kimliği doğrulanamıyorsa genel kullanım açıkça gösterilir. Daha az maç varsa gerçek payda kullanılır; hayali maçla altıya tamamlanmaz.
2. MS1: ev sahibinin galibiyetleri + deplasmanın mağlubiyetleri. MS0: beraberlikler. MS2: ev sahibinin mağlubiyetleri + deplasmanın galibiyetleri. AÜ ve KG sayıları iki tarafın örnekleri üzerinden hesaplanır. Normal takım ağırlığı %80'dir.
3. İki takımın kendi rekabet listesinden turnuva sınırlaması olmadan en yeni en fazla altı maç kullanılır. Geçmiş karşılaşmalar bugünkü ev sahibinin bakış açısına çevrilir. Rekabet ağırlığı %20'dir. Rekabet yoksa takım geçmişi %100 olur. Her seçeneğin iki katkısı toplanır.
4. Futbolda MS1/MS0/MS2, 2,5 Üst/Alt, KG Var/Yok; basketbolda MS1/MS2 ve bugünkü maçın toplam sayı baremi kullanılır. Basketbol geçmişinde nihai skor (uzatma dahil) esas alınır. Baremde eşitlik iadedir; isabet veya kayıp sayılmaz. İlgili takımın geçerli AÜ örneği hiç yoksa AÜ adayı üretilmez.
5. Eski `complete-market-price-v2` oran güvenliği korunur: pazarın tüm seçeneklerinde sonlu, >1 sayısal oran bulunmalıdır. Geçersiz/eksik pazarlar ilk iki aday arasına alınmaz. Uygun pazar yoksa Tahmin yok.
6. En yüksek yüzdeli iki uygun seçenek belirlenir. Son rekabet maçı, ev sahibinin son maçı ve deplasmanın son maçı aynı tercihi destekliyorsa birer puan verir. Takımların son maçları 1. adımda seçilen havuzdan alınır. Rekabet genel kalır. Kayıt yoksa o oy sayılmaz: örneğin 2/2. Deplasmanın son galibiyeti MS2'yi, mağlubiyeti MS1'i destekler.
7. Destek puanı daha düşük aday seçilir. Eşit puanda tüm mevcut oylar destekliyorsa düşük yüzdeli aday; diğer eşitliklerde yüksek yüzdeli aday seçilir. Yüzdeler ve destek kesirleri de eşitse farklı pazarlardan iki aday birden gösterilir. Aynı pazarın en yüksek iki zıt seçeneği yüzde ve destekte eşitse o pazar tamamen atlanır. İki pazar atlanırsa kalan pazardan tercih yapılır; tüm pazarlar kararsızsa Tahmin yok. Yuvarlatılmış ekran yüzdesi karar ölçütü değildir. Adayların geçerli oy sayısı basketbol iadesi nedeniyle farklıysa karşılaştırılamayan puanlar üzerinden ters seçim yapılmaz; yüksek yüzde kullanılır ve eksikliği yazılır.

## Görünüm ve sonuç kontrolü

- Tahmini skor ve olası skorlar kaldırılır. Gerçek skor Control sonrasında görünür.
- Seçilen tercihin yüzdesi güven sıralamasını ve %25/%50/%75 dilimlerini belirler. İkinci aday seçilmişse birincinin yüzdesi kullanılmaz.
- Tam eşitlikte çift tercih ayrı ayrı vurgulanır ve sonuçlandırılır; birleşik kupon olasılığı uydurulmaz. Filtre özeti maç bazındadır: Tuttu (bütün tercihler tuttu), Kısmi tuttu (biri tuttu biri yattı), Yattı (bütün tercihler yattı), Bekliyor. Ana isabet = Tuttu / (Tuttu + Kısmi tuttu + Yattı). Bekleyen, iade/doğrulanmamış ve tahmin verilmeyen maçlar paydaya girmez. Tercih filtresi çift tercihin herhangi biriyle eşleşir; minimum oran filtresinde çiftin düşük oranı esas alınır.
- Hesap detayı, maç kartı genişliğinde açılır. Takım pay/payda × ağırlık, rekabet pay/payda × ağırlık, toplam yüzde ve ilk iki adayın son maç desteği numaralı gösterilir. Tek tek geçmiş maç listesi gösterilmez.
- Yeni `user-rules-before-results.json` bir kere yazılır. Control yalnız sonuçları yeniler; snapshot, geçmiş ve yapılandırma SHA-256 değerleri doğrulanır. Yeni değerlendirmeler eski modelin kohortlarıyla karıştırılmaz. Yüzdeler geçmiş sıklıklarıdır, kalibre edilmiş başarı garantisi değildir.

## Veri sınırları

Mevcut HTTP geçmişi ve maçın kendi kaydedilmiş TeamMatchHistory rekabet listesi kullanılır. Bir yıllık havuzda tesadüfen rastlanan rekabetler, varsa doğrudan rekabet listesinin yerine geçmez. Geçmiş tarih ve kimlik doğrulaması korunur; başlangıç saati olmayan aynı günkü geçmiş maçlar dahil edilmez. Havuzda bulunmayan eski maçların mevcut olduğu varsayılmaz. İki takımın da hiç geçerli geçmişi yoksa veya bir tarafın genel geçmişi de yoksa tahmin üretilmez.
