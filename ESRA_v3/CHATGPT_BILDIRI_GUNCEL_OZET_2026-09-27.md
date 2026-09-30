## ESRA v3 — Bildiri yazımı için güncel durum özeti

- Simülatörün Python tabanlı sürümünde simülasyon motoru, arayüz, Nearest Car ve GA tabanlı kontrol yolları çalışır hâle getirildi.

- Yolcuların bekleme, araca binme ve araçtan inme aşamalarının modellenmesi ve görselleştirilmesi geliştirildi. Yolcu bekleme süresi ile çağrı cevaplama süresi ayrı tutuluyor.

- Statik senaryoların araç konumlarını, hareket yönlerini, kabin hedeflerini ve bekleyen yolcuların başlangıç–hedef katlarını gösteren görselleştirme aracı hazırlandı.

- **Load Custom Initials File** ile önceden belirlenmiş başlangıç koşullarının yüklenmesi destekleniyor. Arayüze ayrıca referans senaryodan zorluk ölçümlü yeni senaryolar oluşturma seçeneği eklendi.

- Statik çağrı–araç atama problemi için altküme dinamik programlamasına dayalı bir **kesin çözücü** geliştirildi. Çözücü, destination-information modelindeki tahmini ortalama **yolcu** bekleme süresini minimize ediyor.

- Senaryo zorluğu ölçümü, aramada gözlenen en iyi çözüm yerine **kesin optimumu referans alacak** şekilde güncellendi. Ölçüt, rastgele başlangıçlı tepe tırmanma aramalarının bu optimuma ulaşma oranıdır; düşük oran, belirtilen arama protokolü için daha zor senaryoyu ifade eder.

- `Dispatcher` sınıfının alt sınıfı olan **ExactDispatcher** oluşturuldu. Kesin çözücüyü simülasyonda kullanıyor ve kontrol yöntemleri paneline eklendi. Sabit başlangıç koşullarıyla, yeni yolcu üretmeden tek seferlik atama yapılabiliyor.

- Destination amaç fonksiyonunun hesaplama kodu kesin çözücüyle ortak kullanılacak şekilde düzenlendi. Geçerli girdilerdeki sonuçlar korunurken geçersiz girdiler için kontroller eklendi.

- GA parametre taraması ayrı bir pencereye taşındı. Parametre aralıkları ve operatör kombinasyonları seçilebiliyor; sonuçlar, kombinasyon başına ortalama, standart sapma, en iyi ve en kötü değerleri içeren `summary.csv` ile kaydediliyor.

- Tekrarlanabilir deneyler için senaryo, parametre ve rastgelelik bilgileri kaydediliyor. Kesin çözücü, arayüz bağlantıları ve simülasyon akışı için doğrulama testleri eklendi.

**Bildiri açısından sınır:** Kesinlik, sınırsız kapasiteli statik amaç fonksiyonu modeli içindir; dinamik simülasyonun genel optimumu değildir. Zorluk ölçütünün genellenebilirliği, zorluk bantlarının kalibrasyonu ve Python’a geçişin hız avantajı henüz kapsamlı deneysel sonuç olarak sunulmamalıdır.
