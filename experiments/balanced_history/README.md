# Dengeli geçmiş deneyi

Bu branch üretim Java algoritmalarını değiştirmez. Ayrı Python deney koşucusu,
yayının tarihli JSON girdisini ve oranlarını dondurur; mevcut tahminleri yeni
hesaplama ile aynı maçlar üzerinde karşılaştırır. Çıktılar yalnızca Actions
artifact'idir. Yayın, Telegram, sonuç kontrolü ve kupon gönderimi yoktur.

## Altı değişiklik

1. Tarih/saha/turnuva ağırlığı: futbol 90, basketbol 60 gün yarılanma ömrü;
   hazırlık maçı ağırlığı 0.25, başka turnuva 0.7. Genel %40, ilgili saha %35,
   son altı %25. Az örnekli saha ortalamaları genel ortalamaya çekilir.
2. Veri desteği: etkin örnek büyüklüğü, güncellik, resmi maç oranı, ilgili saha
   desteği ayrı raporlanır. 0–100 veri puanı isabet olasılığı değildir.
3. Basketbol formu: son sonuçla galibiyet oranı, normal süreyle sayı ortalaması.
   Uzatma normal süre ortalamasına eklenmez; OU için geçmiş uzatma katkısı
   ayrıca hesaplanır. Arşivdeki normal süre beraberlikleri mağlubiyet sayılmaz.
4. MS/OU/BTTS bağımsız aday gruplarıdır. Tek skor ve `getMax()` vetosu yoktur.
   Geçerli oran, minimum veri, %60 olasılık ve %2 model EV eşiği kullanılır.
5. Gerçek sonuçlarla Brier, log loss, en olası sonuç isabeti ve kalibrasyon
   dilimleri. Arşiv az olduğundan kalibrasyon eğitimi kapalıdır; değerlendirme
   sonuçlarıyla katsayı ayarlanmaz. Kalibrasyon için en az 200 maç ve 5 ayrı
   gün hedefi henüz doğrulanmış istatistiksel yeterlilik garantisi değildir.
6. Genel geçmiş futbol en çok 20, basketbol en çok 25 benzersiz maç;
   varsa her saha için en az dört maç korunur. Son altı ayrıca form sinyalidir.
   Rekabet geçmişi en fazla iki yıl ve en fazla %5 katkı ile sınırlıdır.
   Aynı altı girdili yeni model de ablation olarak JSON'a kaydedilir.

Bunlar deney başlangıç katsayılarıdır; optimize edilmiş veya daha başarılı
olduğu gösterilmiş bir model değildir. Oyuncu eksiği, rakip gücü, xG ve tempo
henüz eklenmedi. Üretim modelinde birden fazla modelin ortalaması yerine bu
deneyde tek tutarlı skor dağılımı kullanılır. Basketbol dağılımının varyansı
geçmişten, zayıf örneklerde önselden gelir; futbol Poisson kullanır.

## Doğrulanan HTTP kaynakları

- `api/v3/HeadToHead/{event}/Summary?competitionHistoryCount=20` denendi:
  `SCH` büyür, `SLM` genel ve saha listeleri hâlâ altışardır. Bu parametre
  son 20 takım maçı olarak kullanılmaz.
- `https://istatistik.nesine.com/p1/{event}` içindeki public model alanları:
  `HomeTeamId`, `AwayTeamId`, `TournamentId`, `AccountId`.
- `https://cdn-saas.broadage.com/config/config.json` public accountMap.
- `https://{publicPrefix}.rsc.cdn77.org/{soccer|basketball}/widget/team/schedule`
  parametreleri `teId`, `tId=0`, `calculation=overall`, `rId=YYYYMM`, `options`.
  Ay kimlikleri sunucunun `metaData.rounds` listesinden alınır. En fazla 12
  mevcut ay ziyaret edilir; yeterli örnekte durulur. Takım adı değil ID eşleşir.
  Satırdaki `team` ve `teamType` rakibe aittir; ev/deplasman ters çevrilir.
- Bitmiş durumlar 5/9/11; basketbol 11 dışlanır. Uzatmalı satırda açık normal
  süre skoru yoksa satır dışlanır. Futbol normal süre skoru ayrı kullanılır.
- İstek aralığı 600 ms, takım/URL önbelleği, 25 saniye timeout, geçici ağ ve
  502/503/504 için en fazla üç deneme. 429 bütün koşuyu durdurur; kota aşma
  yöntemleri yoktur. Diğer endpoint hataları görünür arşiv fallback üretir.

ID alanları Nesine/Broadage arasında farklıdır. İki kaynağı havuzlayıp aynı
maçı iki kez saymayız. Kaynak değişimi karşılaştırmada görülebilir. Aynı
günün tüm maçları geçmişten dışlanır; böylece ilk yayından sonraki maçlar
yeniden hesaplamaya sızmaz. Bunun bedeli, günün erken maçlarının sonradan
oluşmuş sonuçlarının yeni geçmişte kullanılmamasıdır.

## Ölçüm sınırları

Mevcut olasılıklar arşivden alınır; eski HTML aynen kopyalanır. Sonuç ölçümü
yalnızca tarihli önceki günlerin dondurulmuş altı maç girdilerindedir. Bu
ölçüm geniş geçmişin üstünlüğünü kanıtlamaz. Geniş geçmiş için yeni günlük
snapshot ve gerçek sonuçları biriktirerek ileriye dönük kıyas yapmak gerekir.
Sonuç etiketi mevcut `RealScores` settlement skorudur; oranlar ve yüzde
karşılaştırmaları gelecekteki sonuçlardan öğrenmez. Tarih sırası korunur.

Artifact'te `index.html`, iki eski ve iki yeni HTML, `evaluation.html`, tüm
olasılıklar/girdiler/geçmişler, HTTP cache, istek audit'i, config ve hash
manifest bulunur. Arşivsel eski HTML filtrelenmiş kuponu gösterir; tabloda
eski `pick` yalnız model etiketi olarak açıkça adlandırılır.

```sh
python -m unittest discover -s experiments/balanced_history -v
python experiments/balanced_history/compare.py --published published \
  --date 2026-10-01 --output comparison-output
```

Workflow manuel tarih ve yayın ref'i alır. İlk koşu 2026-10-01 yayın
commit'ine sabitlenmiştir. Yeniden farklı gün için uygun tarih/ref birlikte
seçilmelidir. Workflow artifact saklama süresi 30 gündür.
