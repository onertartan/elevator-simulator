# Çift biniş hatasının iki yan konusu: GA'nın anlık görüntü reddi ve eşit uzaklık kuralı

**Tarih:** 31 Ekim 2026
**Dal:** `fix/pending-board-direction` (PR #1), [A6] düzeltmesiyle birlikte
**İlgili:** `RUNNING.md` §11 ([A6]), §7 (bekleme süresi bitişi), §10 ([A5]);
`analysis/headless_benchmark.py`; `tests/test_accepted_passenger_reassignment.py`

Çift biniş hatasının kendisi [A6] ile düzeltildi: kabul edilmiş (kapısı
açılmakta olan araca `pendingBoard` ile bağlanmış) yolcu artık başka bir
araca yeniden atanmıyor. Bu not, inceleme sırasında ortaya çıkan ve [A6]
kapsamına alınmayan iki konuyu kaydeder.

## 1. GA ve kesin çözücü kapı açılma penceresinde anlık görüntüyü reddediyor

### Gözlem

`objFunDestination`, bekleyen çağrıların kat kümesinin bekleyen yolcuların
kat kümesiyle birebir eşleşmesini ister
(`decision/meta/obj_funs/obj_fun_destination.py`, "calls must match waiting
passenger floor-direction groups exactly"). Kapı açılma penceresinde
(varıştan kapı tam açılana kadar, 2 s) kabul edilmiş yolcuların çağrısı
`served` listesine geçmiş, yolcuların kendileri ise hâlâ `P.waiting`'dedir
([A4]). Kümeler uyuşmaz ve fonksiyon `ValueError` verir. `ExactDispatcher`
aynı durumda `pendingBoard` dolu olduğu için zaten açıkça reddeder.

Sonuç: GA dağıtıcısı kabul edilmiş yolcuyu sessizce yeniden atamaz; bu
yüzden çift biniş hatası yalnızca en yakın araç dağıtıcısında ortaya
çıkıyordu. Ama GA, pencereye denk gelen her kararda hata verir.
`headless_benchmark.py` çıktısındaki "GA(2026) period=1 ... rejected"
satırları budur. Varsayılan "yeni çağrı kaydedildiğinde dağıt" ayarında
karar her `arrivalRate` tikte alındığından, dinamik bir GA koşusu bu
pencereye er geç denk gelir.

### Neden önemli

TÜBİTAK 3501 önerisinin yöntem bölümünde GA, "her yeni çağrıda yeniden
optimizasyon" karşılaştırma tabanı olarak planlanıyor. Dinamik koşuda
pencereye denk gelen kararlarda çöken bir taban kullanılamaz. Kesin
yeniden optimizasyon tabanı (küçük binada her çağrıda kesin çözüm) için de
aynı engel geçerli.

### Öneri (ayrı bir iş; [A6] kapsamında değil)

Anlık görüntü adaptöründe (`DestinationInstance` ve GA'nın `objFunWrapper`
tarafı) kabul edilmiş yolcular Ruokokoski vd. (2016)'daki **sabit istek**
(fixed request, N2) gibi ele alınmalı:

- atanabilir kümeden çıkarılırlar (kromozomda gen almazlar, DP'de bölüşüme
  girmezler);
- hedef katları, kabul eden aracın kabin hedefi sayılır ([A5]'in
  `updateState` için yaptığının amaç fonksiyonuna taşınması);
- bekleme süreleri zaten donmuş olduğundan amaç değerine katkıları sabittir
  ve ihmal edilebilir ya da sabit terim olarak eklenebilir.

Bu değişiklikle `objFunDestination`'ın küme eşleşme kontrolü, kabul edilmiş
yolcular düşüldükten sonraki kümeler üzerinde yapılır; `ExactDispatcher`'ın
`pendingBoard` koruması da aynı mantıkla gevşetilebilir. Statik (tek
seferlik, yeni geliş olmayan) koşular etkilenmez: orada pencere hiç
görülmez ve yayımlanmış amaç değerleri değişmez. Regresyon testi olarak
pencere içinde GA kararı alınan dinamik bir senaryo (ör.
`headless_benchmark.py`'deki "GA period=1" satırlarının reddedilmemesi)
kullanılabilir.

Alternatif, daha basit ama daha zayıf seçenek: pencere içinde karar anını
ertelemek (araçlardan birinde `pendingBoard` doluyken dağıtıcıyı
çağırmamak). Bu, karar anlarını fiziksel olaylardan koparır ve PÖ ortamının
olay güdümlü karar anı tanımıyla çelişir; önerilmez.

## 2. En yakın araç dağıtıcısının eşit uzaklık kuralı — doğrulandı

### Kural

`NearestCarDispatcher.dispatch`: eşit FS'de daha yakın araç seçilir; uzaklık
da eşitse **daha küçük `stopOverCounter`** değerine sahip araç kazanır.
Aynı katta duran iki araçtan kapı çevrimi kapalı olan (sayaç 0) ya da
çevrimi daha ileride olan, kapısı yeni açılmakta olana (sayaç 7, 6, 5)
karşı tercih edilir.

### Doğrulama (tohum 17, [A5] motoru, [A6] öncesi)

`headless_benchmark.py` trafik yapılandırması (8 kat, 3 araç, 5 s'de bir
geliş, 600 s), tohum 17, t = 400'deki dağıtım anı:

| Araç | Kat | Yön | Sayaç | Yük | DF |
|---|---|---|---|---|---|
| 1 | 4,0 | aşağı | 3 | 1 | {2} |
| 2 | 7,0 | aşağı | 0 | 1 | {7} |
| 3 | 7,0 | aşağı | 5 | 1 | {5} |

Bekleyen çağrılar: 6-aşağı (t = 370), 7-aşağı (t = 400, yeni).
FS (aşağı çağrılar × araçlar): 6-aşağı → [1, 7, 7]; 7-aşağı → [1, 8, 8].

Araç 3, 7. kattaki aşağı yolcuları (id 79 ve 81) t = 398'de kabul etmiş ve
kapısını açmaktadır (sayaç 5). Araç 2 ise aynı kata kendi yolcusunu
bırakmak için gelmiştir (DF {7}, sayaç 0). t = 400'de 7. kata yeni bir
aşağı yolcu gelir. 7-aşağı çağrısı için araç 2 ve 3'ün FS'si (8) ve
uzaklığı (0) eşittir; sayaç kuralı araç 2'yi seçer. [A6] öncesi dağıtıcı,
7. kattaki bütün aşağı yolcuların `carId`'sini 2 yapar; araç 2'nin
`beginPickup`'ı 79 ve 81'i de kabul eder; iki araç da bindirir ve indirir
(`dup = 2`). `main`'deki tohum 1 vakası (yolcu 85, 8. kat, araç 2 → 3) aynı
mekanizmadır. Bu geometri `tests/test_accepted_passenger_reassignment.py`
içindeki deterministik yeniden üretimin temelidir (iki araç 7. katta,
t = 0 ve t = 1'de iki aşağı yolcu).

### Değerlendirme

Kuralın kendisi bir hata değil: aynı katta sayacı kapalı araç, yeni yolcuyu
daha erken alabilir. Hatayı yaratan, bu seçimin kabul edilmiş yolculara da
uygulanmasıydı; [A6] bunu kapattı. İki yan etkisi not edilmeli:

- [A6] sonrasında aynı katta iki araç aynı anda kapı açabilir: biri kabul
  edilmiş yolcular, diğeri yeni gelen için. Fiziksel olarak tutarlı, ama
  yeni yolcunun kapısı zaten açık olan araca verilmesi çoğu zaman daha iyi
  olurdu. Bu, dağıtıcının (en yakın araç, GA, PÖ politikası) kalite
  sorunudur; motor kısıtı değildir. PÖ ortamında politika bunu ödülden
  öğrenebilir.
- Kuralın MATLAB'daki işaretli uzaklık ayrıntısı (`nearest_car_dispatcher.py`
  başlık notu) değişmedi.

## 3. Durum

- [A6] düzeltmesi, emniyet ağı, 4 regresyon testi ve `--strict` bayrağı bu
  dalda (`RUNNING.md` §11).
- §1'deki GA/kesin çözücü uyarlaması açık; İP1 (motor doğrulama ve
  genişletme) kapsamında planlanmalı.
- PÖ ortamı tasarımında karşılık: kabul edilmiş grup faz 0'da kabul eden
  araca kilitlenir (tasarım belgesi K24).
