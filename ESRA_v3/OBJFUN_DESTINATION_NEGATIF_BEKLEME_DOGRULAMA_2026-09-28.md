# objFunDestination / WT — Negatif bekleme süresi doğrulaması

**Tarih:** 28 Eylül 2026

## Sonuç

**Sorun güncel kodda hâlâ mevcut.** Aşağıdaki örnek, üretim kodu değiştirilmeden doğrudan çalıştırıldı.

## Kullanılan örnek

- 8 kat, tek asansör, sınırsız kapasite.
- Asansör 3. katta, durmuş durumda (`state=0`), mevcut hedefi yok (`DF=set()`).
- Tek yolcu 3. katta bekliyor; hedefi 5. kat.
- `stopOverTime=2` saniye, `velocityFps=0.5` kat/saniye.
- Tek çağrı tek asansöre atanıyor: `HC=[3]`, `HC_numofups=1`, `chrom=[[1]]`.
- Çağrılan amaç fonksiyonu: `objFunDestination(..., "WT")`.
- Beklenen sonuç: **0 saniye**. Araç yolcuyla aynı katta ve yolcu alınmadan önce hizmet verilecek başka durak yok.

## Gerçek çıktı

Fonksiyon sayısal sonuç döndürmedi; şu hata oluştu:

```text
ValueError: destination/WT produced non-finite or negative waiting times
```

Çalışma anındaki izleme, hata fırlatılmadan önce iç hesapta `WT1=[-2.0]` üretildiğini doğruladı. Dolayısıyla güncel fonksiyonun dışarı döndürdüğü sonuç −2 saniye değil, yukarıdaki hatadır.

## Regresyon testi

`tests/test_obj_fun_destination.py` dosyasına `test_idle_car_same_floor_up_passenger_zero_wait()` testi eklendi. Test, sonucu `np.testing.assert_array_equal(avg, [0.0])` ile kontrol ediyor; hata fırlatılmasını beklenen sonuç olarak kabul etmiyor.

Test ayrıca dosyanın `if __name__ == "__main__":` bölümündeki çalıştırma listesine eklendi ve şu komutla gerçekten çalıştırıldı:

```powershell
.\.venv\Scripts\python.exe tests\test_obj_fun_destination.py
```

- Önceki **9 test geçti**.
- Yeni regresyon testi aynı `ValueError` nedeniyle **başarısız oldu**.
- Komutun çıkış kodu **1** oldu.
- Çıktıdaki traceback, yeni testin çağrıldığını ve `objFunDestination` üzerinden `car_waiting_times` içindeki hata kontrolüne ulaştığını gösterdi.

## Kök neden

İlgili bölüm: `decision/meta/obj_funs/obj_fun_destination.py`, `car_waiting_times()` fonksiyonu, `car.state != 1` dalındaki dönüş durağı düzeltmesi; özellikle doğrulama anındaki **208. satırda** bulunan `prev -= 1` işlemi.

Çalışma anında izlenen hesap sırası:

1. `state=0`, aşağı yön/durmuş araç dalına giriyor.
2. Aşağı yönlü yolcu ve mevcut kabin hedefi yok; önceden sayılmış durak sayısı `prev = len(DF) = 0` oluyor.
3. `MINI=3` ve yukarı yönlü yolcunun bulunduğu kat da 3 olduğu için eşitlik koşulu sağlanıyor.
4. Önceden hiçbir durak sayılmamış olmasına rağmen `prev -= 1` uygulanıyor: **`prev=-1`**.
5. `numOfCarStopsTrue`, yolcunun bulunduğu durağın sırasını `1 + (-1) = 0` olarak hesaplıyor.
6. Seyahat süresi sıfır olduğundan bekleme hesabı **`WT = 0 + (0-1) × 2 = -2` saniye** üretiyor.
7. Negatiflik kontrolü bu değeri tespit ederek **232. satırda** `ValueError` fırlatıyor.

Kök neden, daha önce sayıldığı varsayılan ortak dönüş durağının, önceki durak sayısı sıfırken de sayaçtan düşülmesidir. Negatiflik kontrolü sorunu üretmiyor; hesapta oluşan negatif değeri görünür kılıyor.

## Yapılan değişikliğin kapsamı

- Üretim kodu değiştirilmedi; objective dosyasının işlem öncesi ve sonrası SHA-256 değeri aynı kaldı:

  ```text
  8844B11BF79E2092C65BE3E65C8132FA2C6265B50D4BE8A0DE3EE0D78ED5182C
  ```

- Kod tarafında yalnızca regresyon testi ve testin çalıştırma listesine çağrısı eklendi.
- Objective düzeltilmedi.
- DP, HC veya büyük deney çalıştırılmadı.
