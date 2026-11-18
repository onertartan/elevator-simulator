# ESRA 3.0 RL ortamı — tasarım eki: K24 (kabul edilmiş grup kilidi)

**Tarih:** 31 Ekim 2026
**Eklendiği belge:** `RL_ORTAMI_TASARIM_DEVIR_v3.2.md` (aynı klasör; claude.ai projesinde
`claude/ESRA_3.0_RL_Ortami_Tasarim_Devir_v3.1.md`) (bu ek, tasarım belgesinin
§4.1, §5.2, §6.1, §7.2 ve K tablosunu değiştirir; belge v3.2 olarak birleştirilene
kadar ekle birlikte okunur)
**Kaynak:** Motor incelemesi ve [A6] düzeltmesi (`fix/pending-board-direction`,
`RUNNING.md` §11; `CIFT_BINIS_GA_REDDI_VE_ESIT_UZAKLIK_NOTU_2026-10-31.md`)

## K24 — Kabul edilmiş OD grubu yeniden atanamaz

| Kod | Konu | Durum | Karar / Gerekçe |
|---|---|---|---|
| K24 | Kabul edilmiş grubun ataması | **Karara bağlandı (2026-10-31)** | Bir araç bir OD grubunun yolcularını binişe kabul ettiğinde (motorda `beginPickup`: kapı açılmaya başladı, yolcular `pendingBoard`'da, `doorOpeningStartTime` dolu), grubun ataması o araca **kilitlenir**: faz 0 maskesinde bu grubun atama bileşeni yalnızca kabul eden aracı açık bırakır. Kilit, grup binene kadar sürer (sayaç 5); binişten sonra grup artık bekleyen grup değildir. Motor tarafında aynı kural [A6] ile dağıtıcı düzeyinde uygulanır (`Dispatcher.assign_call`) ve `Car.beginPickup` emniyet ağı ihlali hata olarak yakalar; PÖ dağıtıcısı atamayı bu yardımcı üzerinden yazar |

### Gerekçe

- Kapı açılma penceresinde (2 s) kabul edilmiş yolcular hâlâ `P.waiting`'de
  görünür ([A4]). Atama her karar anında serbestçe yenilenirse politika bu
  grubu başka bir araca verebilir; [A6] öncesi motorda bu, iki aracın da aynı
  yolcuyu bindirmesiyle sonuçlanıyordu (çift biniş). Maske düzeyinde kilit,
  hatayı ortam tasarımında imkânsız kılar; emniyet ağı maske hatasını görünür
  yapar.
- Fiziksel olarak tutarlıdır: kapısı açılmakta olan araç yolcuyu almaktadır;
  başka bir aracın aynı anda aynı yolcuyu alması mümkün değildir.
- Ruokokoski vd. (2016)'daki sabit istek (N2/N3) kavramının en dar karşılığıdır:
  yalnızca binişi başlamış gruplar sabitlenir; ilan edilmiş ama henüz
  alınmamış atamalar v3.1'deki gibi serbestçe değiştirilebilir kalır (K5 churn
  izlemesi değişmez).
- CC modunun "biniş bekleyen araç sıfırlanmaz" kuralıyla (§5.2, K20/K22)
  tutarlıdır: kabul edilmiş yolcusu olan araç dolu sayılır, yönü politikaya
  sorulmaz.

### Değişen bölümler

- **§4.1 (çağrı grupları):** "Atama serbestçe yeniden yapılabilir" cümlesine
  istisna: binişi başlamış (kabul edilmiş) grup, biniş tamamlanana kadar kabul
  eden araca bağlıdır.
- **§6.1 (`calls` bloğu):** kabul edilmiş grup, bekleyen yolcu sayısı ve
  bekleme istatistikleriyle gözlemde kalır (hâlâ `P.waiting`'dedir); atama
  one-hot'u kabul eden aracı gösterir. İsteğe bağlı ek özellik: satır başına
  "kabul edildi" biti (1 boyut); boyut formülü o zaman `N·(5 + C) + …` olur.
  Bu bit eklenmezse politika kilidi yalnızca maskeden görür; K17 (faz 0
  sütunları) kararıyla birlikte ele alınmalı.
- **§7.2 (faz 0 maskesi):** aktif OD satırı için "tüm araçlar açık" kuralına
  istisna: kabul edilmiş grup → yalnızca kabul eden araç açık (tek seçenek).
- **§7.3 canlılık sonucu:** değişmez; kilit yalnızca seçenek daraltır.
- **§9 motor ön koşulu:** [A5] (K22) yanına [A6] eklenir: PÖ dağıtıcısı
  `carId`'yi `Dispatcher.assign_call` üzerinden yazar.
- **§11 açık sorular:** yeni madde — §6.1'deki "kabul edildi" bitinin gerekip
  gerekmediği (ampirik; O0/O1 testleriyle birlikte).

### Uygulama notu

`pendingBoard` içindeki yolcuların OD grubu, karar anında `doorOpeningStartTime`
alanından tanınır. Faz 0 maskesi kurulurken her aktif OD satırı için: satırdaki
yolculardan en az biri kabul edilmişse satır kilitlidir ve açık araç, o
yolcuların `carId`'sidir. Aynı OD grubunda hem kabul edilmiş hem yeni gelmiş
yolcu bulunması (aynı kat ve hedefe pencere içinde gelen ikinci yolcu) [A6]'nın
motorda ele aldığı durumdur: yeni yolcu ayrı atanabilir; grup düzeyinde kilit
istenirse ortam, yeni yolcuyu da kabul eden araca bağlamalıdır. Bu seçim
(yolcu düzeyi mi, grup düzeyi mi) uygulamada netleştirilecek; grup düzeyi
önerilir, çünkü v3.1'in atama birimi OD grubudur.
