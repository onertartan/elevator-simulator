# Kesin optimum ve HC zorluğu — uygulama raporu

26 Eylül 2026 tarihli V2 talimatı Python dosyalarına uygulandı. MATLAB
kaynakları, GA operatörleri ve boarding/alighting zamanlaması değiştirilmedi.
Önceden var olan kullanıcı değişiklikleri ve deney çıktıları korundu.

## Değişiklikler

- `decision/exact_assignment.py`: doğrulanan snapshot/atama adaptörü, araç–altküme
  toplam maliyeti, altküme DP, deterministik geri izleme, doğrudan objective
  kontrolü, zaman/çağrı sınırları, iptal ve ayrı tamamlanma statüleri.
- `decision/meta/obj_funs/obj_fun_destination.py`: mevcut araç hizmet sırası
  hesabı ortak bir helper'a ayrıldı. Geçerli atamaların sonuçları korundu;
  geçersiz atamalar ve boş yolcu kümesi artık açık hata veriyor.
- `scenario_generation.py`: HC arama kuralı korunarak başarı referansı
  `exact_optimum` yapıldı; aşama seed'leri, Wilson aralığı, koşu sonuçları,
  bütçeye ulaşarak durma bilgisi, sonraki holdout API'si ve güvenli çift dosya
  kaydı eklendi. Eski `batch_best` yalnızca açıkça etiketlenmiş ön eleme olabilir.
- `gui/scenario_creator.py`, `gui/main_window.py`: yeni ölçümün açıklaması,
  kesin çözücü sınırları, ayrı seed'ler, isabet sayısı/oranı ve güven aralığı.
- `make_scenarios.py`: boş kabin hedef hücrelerinin araç indekslerini kaydırması
  önlendi; yolcu satırı eşleşmesi kontrolü ve aday üretirken iptal kontrolü.
- `analysis/solve_exact_snapshot.py`: var olan tek snapshot üzerinde süre
  sınırlı çözüm; örneği değiştirmeden JSON sonuç raporu.
- `tests/test_exact_assignment.py`, `tests/test_scenario_generation.py`,
  `tests/test_scenario_creator_dialog.py`, `tests/scenario_fixture.py`: küçük
  sentetik örnekler, bağımsız tam tarama ve başarısızlık yolu testleri.
- `RUNNING.md`: kullanım, metadata anlamları ve ayrı holdout değerlendirmesi.

## Korunan problem ve ayrışabilirlik

Bir bit/gen bir **kat–yön çağrısıdır**. Aynı çağrıdaki bütün yolcular birlikte
atanır; farklı hedef katları korunur. Maliyetler araç başına **toplam** bekleme
maliyetidir; toplam, bütün **bekleyen yolcuların sayısına** bölünür. Kabin
hedefleri durak sırasını etkiler ama bu paydaya eklenmez. Kapasite/load
alanlarına dayalı eleme veya ceza yoktur.

Ortak helper yalnızca ilgili aracın sabit durumunu ve o araca atanmış çağrıların
yolcularını okur. Başka bir aracın ataması okunmaz. Bu nedenle araç toplamları
ayrışabilir; ortak katlar arası süre `1 / cars[0].velocityFps` olarak korunur.
DP bütün çağrı bölüşümlerini ve boş altkümeleri kapsar. Küçük iyileşmeler DP
minimumunda toleransla atlanmaz; `1e-9 s`, `rtol=0` yalnızca sonuç doğrulama ve
HC optimum isabeti karşılaştırmasında kullanılır.

## Testler

İlgili 13 test dosyası çalıştırıldı:

- `test_exact_assignment.py`, `test_scenario_generation.py`,
  `test_scenario_creator_dialog.py`, `test_obj_fun_destination.py`;
- `test_obj_fun_conventional1.py`, `test_ga.py`,
  `test_metaheuristic_dispatcher.py`, `test_ga_custom_initials_e2e.py`;
- `test_configuration_custom_initials.py`, `test_experiment_smoke.py`,
  `test_ga_sweep.py`, `test_gui_sweep_command.py`, `test_simulation_config_layout.py`.

Amaç fonksiyonu değişmeden önce 2 araç, 5 çağrı, 6 yolculu fixture'ın bütün
32 atama değeri kaydedildi. Bu sabit değerler ve önceki elle hesaplanmış
objective testleri refaktörden sonra aynı kaldı. 1–3 araç ve 1–6 çağrılı küçük
örneklerde tüm `C^m` atamaları doğrudan objective ile taranarak ayrıştırma,
DP minimumu ve optimum atamanın geri değerlendirmesi karşılaştırıldı.

Tek çağrı/üç yolcu için 6 saniye toplamın 2 saniye ortalamaya dönüşmesi,
sınırsız kapasite, mevcut kabin hedefleri, ortak hız, eşit optimumlar, kesirli
süreler, sıfır optimum, geçersiz etiketler, sıfır yolcu, NaN/negatif maliyet,
maliyet ve DP aşamalarında iptal/zaman aşımı kontrol edildi. HC'de sıfır isabet,
optimumun altındaki tutarsız değer, mutlak tolerans ve Wilson aralığı kapsandı.
Metadata yazma/yerine koyma hatasında yeni kısmi çıktı bırakmama ve mevcut
çıktıları geri alma test edildi. Arayüzde dispatch/objective seçimleri
değiştirilerek senaryo oluşturucuya yalnızca aynı fizik parametrelerinin
aktarıldığı doğrulandı.

## Tek gerçek snapshot denemesi

Dosya: `initials_files/initials_file.xlsx`; 8 araç, 16 kat–yön çağrısı,
17 bekleyen yolcu. Snapshot yeniden örneklenmedi ve dosya hash'i değişmedi.
Parametreler: `stopOverTime=7 s`, `velocityFps=0.5 floor/s`; çağrı sınırı 16,
toplam kesin çözüm bütçesi 120 saniye.

| Sonuç | Ölçüm |
|---|---:|
| Statü | `optimal` |
| Minimum toplam bekleme maliyeti | 296 s |
| Minimum ortalama | 17.41176470588235 s |
| Araç–altküme maliyet girdisi | 524288 |
| Gerçekleştirilen DP geçişi | 258345862 |
| Maliyet önhesabı | 46.7527574 s |
| DP | 54.8060882 s |
| Toplam kesin çözüm | 101.5640534 s |

Optimum atama refaktör sonrası doğrudan Python objective ile yeniden
değerlendirildi. Ayrıca Git HEAD'deki **refaktör öncesi Python objective**
bellekte yüklenerek aynı atama tekrar değerlendirildi: aynı ortalama,
mutlak fark **0.0 s**. Bu ek kontrol yeni helper'ın iki kullanımını
karşılaştırmakla sınırlı değildir.

Ham rapor, çağrı sırası, sıfır tabanlı optimum atama, hash'ler ve süreler:
`cikti/exact_snapshot_check_20260926.json`.
Süreler tek çalıştırmanın duvar saati ölçümleridir; performans karşılaştırması
veya Python/MATLAB hız kazanımı kanıtı değildir.

## Kayıt ayrımı ve kalan sınırlar

Eski kayıtlara dokunulmadı; `reference_type` olmayan eski kayıtlar
`batch_best` olarak yorumlanır. Yeni kayıtlarda `difficulty_metric` değeri
`hc_optimum_hit_rate`, `reference_type` değeri `exact_optimum` olur.
`best_cost` / `best_objective_seconds` gözlenen en iyi HC değerini göstermeye
devam eder; kesin optimum ayrı alanlardadır. Varsayılan ön eleme/seçim/sonraki
holdout seed'leri 11/12/13'tür. Seçim aşaması holdout olarak adlandırılmaz;
sonraki holdout sonucu hedef bandı veya kayıtlı seçimi değiştirmez.

Kesinlik aynı Python objective ve sınırsız kapasiteli statik atama problemi
içindir; dinamik simülasyon optimumu veya biçimsel yazılım doğrulaması değildir.
DP maliyeti üstel büyür; 16 çağrı/120 saniye yapılandırılabilir koruyuculardır.
Mevcut aday üreticinin referans yapısına ilişkin kısıtları genişletilmedi.
İki dosyalı kaydın I/O hatası geri alması elektrik kesintisine karşı atomiklik
garantisi değildir.

Gerçek snapshot'ta 150/600 koşuluk HC zorluk ölçümü, bantların yeniden
kalibrasyonu, büyük aday/holdout senaryo havuzu veya GA faktöriyel deneyi
çalıştırılmadı. Mevcut bantlar kullanıcı hedefi olarak korundu; doğrulanmış yeni
zorluk sınıfları olarak sunulmadı. Yeni bağımlılık veya derlenmiş hızlandırıcı
eklenmedi. Bildiri yöntem/sonuç metni yazılmadı.
