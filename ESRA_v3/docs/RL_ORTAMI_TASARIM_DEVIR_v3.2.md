# ESRA 3.0 — Asansör Grup Kontrolü için Pekiştirmeli Öğrenme (RL) Ortamı
## Tasarım Devir Dokümanı

> **Bu dokümanın amacı.** Bu dosya, ESRA 3.0 simülatörü üzerine kurulacak pekiştirmeli
> öğrenme (RL) ortamının tasarım sözleşmesini, alınmış kararları ve açık soruları **tek
> dosyada** başka bir LLM'e (veya yeni bir mühendise) aktarmak için yazılmıştır.
> Kaynak kodu okumadan, yalnızca aşağıdaki sözleşme üzerinden sistem anlaşılabilir.
> Amaç, okuyan modelin aynı tasarımı sürdürebilmesi, tutarsızlıkları yakalayabilmesi ve
> uygulama (kod) düzeyinde yardımcı olabilmesidir.
>
> **Kısmi devir.** Gözlem (§6) ve eylem (§7) tasarımı tek başına da paylaşılabilir: bu iki
> bölüm, kesitin dışında kalan tanımları içeren bir **bağlam kapsülü** (§6.0) ve
> `KESİT BAŞLANGICI` / `KESİT SONU` işaretleriyle donatılmıştır. Hazır paket
> `esra-3-rl-kesit-6-7.md` dosyasındadır; ilgili istem §13.2'dedir.
>
> **Revizyon notu (2026-10-15).** K13 karara bağlandı: karar anı, aynı simülasyon anında
> art arda gelen iki mikro-adıma bölünür (faz 0 atama, faz 1 hedef); bkz. §7.3. Bu
> revizyonla değişen bölümler: §0, §2, §3.4, §5.1–§5.3, §6.0, §6.1, §6.3–§6.6, §7.1–§7.3,
> §8.2, §9, K13/K14/K17, §11/4, §11/6, §13.2, §14. `esra-3-rl-kesit-6-7.md` paketi bu
> sürümden yeniden üretilmelidir.
>
> **Revizyon notu 2 (2026-10-15, v3).** Park katı seçimi v4.0'a ertelendi (K21, §15): işi olmayan
> araç durma katında kalır. C modunda `CH` yalnızca boş aracın yönünü seçer, kabin doluyken
> işlemsizdir ve kolektif kontrolör sürer (K20, §5.2). Maskeler ve iki fazlı karar anı (K13)
> korunmuştur. Değişen bölümler: §0, §2, §3.4, §5.1–§5.3, §6.0, §7.1–§7.3, K1/K14/K18, K20–K21,
> §11/2–3, §11/10, §14, §15.
>
> **Revizyon notu 3 (2026-10-19, v3.1).** C modunda `CH` yerine araç başına **3 değerli öncelikli
> yön** bileşeni (`{−1, 0, +1}`); karar anında kabini boş olan **her** araç (hareket hâlindekiler
> dâhil) `state = 0`'a çekilir ve yönünü politika seçer — "C anlambilimi" (K20 revize). Faz 1
> maske tablosu yeniden yazıldı; iki yanlı atamada `0` kapalı; faz 1 hiçbir karar anında atlanmaz.
> ESRA motoru ön koşulu kaydedildi: `Car.updateState` biniş bekleyen yolcuların hedeflerini kabin
> hedefi sayar ([A5], K22; depo PR #1). Yarım katta işsiz kalma pürüzü (K23) ve işsiz araç hareketi
> için `parkFloor` ilkeli (§15.2) not edildi. "Hedefte mi" biti C modunda `state == 0` olarak
> tanımlandı (K18). Atama bloğu ortak, ikinci blok moda özgü (K14). Değişen bölümler: §0, §2, §3.4,
> §4.2, §5, §5.2–§5.3, §6.0, §6.2, §6.3, §6.5–§6.6, §7.1–§7.3, §9, K1/K13/K14/K15/K18/K20,
> K22–K23 (yeni), §11/2, §11/7, §11/10, §14, §15. Belge sürümü (v3.1) ile proje sürümü (4.0 =
> park genişlemesi) farklı numaralandırmalardır.
>
> **Revizyon notu 4 (2026-11-07, v3.2).** Simülasyon sınıflandırması düzeltildi: ESRA motoru
> **sabit adımlı** (*fixed-increment time advance*, `Ts = 1 s`) çalışır; önceki sürümlerdeki "ayrık
> olaylı (discrete-event)" ifadesi yalnızca **modellenen sistem** için doğrudur, zaman ilerletme
> mekanizması için değil (§3.1). Rastgeleliğin yalnızca trafik üretiminde olduğu ve yolcu
> varışlarının sabit aralıklı (Poisson değil) olduğu kaydedildi. Yeni **§3.5 ve K25:** GUI aktif
> değilken (başsız mod) **olay tabanlı** (*next-event*) zaman ilerletme uygulanacak; adımlı modla
> birebir eşdeğerlik zorunlu ve regresyon testiyle bağlanacak. Değişen bölümler: §0/1, §2, §3.1,
> §3.5 (yeni), §6.0, §8.1, §9, K25 (yeni), §12, §14.
> *Not:* Teklifin statik örnek tasarımı (Yöntem v10–v12: yalnızca statik örnekler; `T_ufuk` ve
> birikmiş süre özelliklerinin kaldırılması; gözlem `N·(1+C) + C·(3F+1) + 1`; CC/PR/PRR
> adlandırması; kabul edilmiş grup kilidi K24) bu belgeye henüz işlenmemiştir; belge, K24 eki ve
> planlanan statik tasarım ekiyle birlikte okunmalıdır. claude.ai projesindeki kopyanın dosya adı
> süreklilik için `v3.1` olarak korunmuştur; depo kopyası `ESRA_v3/docs/RL_ORTAMI_TASARIM_DEVIR_v3.2.md`,
> K24 eki `ESRA_v3/docs/RL_TASARIM_EK_K24_2026-10-31.md`.

---

## 0. Özet (Abstract)

ESRA 3.0, **varış yeri (hedef) tabanlı** bir asansör grup kontrol simülatörüdür. Mevcut
kontrolör bir genetik algoritma (GA) tabanlıdır ve korunmaktadır. Bu çalışmada, aynı
simülatör üzerine **stable-baselines3 (MaskablePPO)** ile eğitilebilir bir RL ortamı
eklenmektedir.

Tasarımın ayırt edici dört özelliği şunlardır:

1. **Olay güdümlü karar anları (SMDP).** Karar anları sabit bir `Δt` ile değil, yalnızca **iki**
   ayrık olayla tetiklenir: yeni çağrı (OD talebi) geldi; sayaç `7`'den `2`'ye indi (kapı
   açıldı, yolcu inişi/binişi tamamlandı). Araç hareketi ve boş katlarda bekleme karar anı
   **üretmez**. Bu, ortamın özelliğidir ve motorun zamanı adım adım mı yoksa olaydan olaya mı
   ilerlettiğinden bağımsızdır (§3.1, §3.5). Her karar anı, aynı simülasyon anında iki mikro-adımdan oluşur: önce atama,
   sonra yeni atamaya göre maskelenmiş ikinci blok — NC-R'de hedef kat, C'de öncelikli yön (§7.3).
2. **Ortak atama bloğu + moda özgü ikinci blok ve maske.** Non-collective (NC-R) ve collective (C)
   kontrol modları aynı `MultiDiscrete` atama bloğunu paylaşır; ikinci blok NC-R'de araç başına
   **hedef kat** (`CH`, `F + 1` değer), C modunda araç başına **öncelikli yön** (`{−1, 0, +1}`,
   3 değer) bileşenidir (K14). C modunda araçları ESRA'nın kolektif kontrolörü sürer; politika
   yalnızca karar anında kabini boş olan araçların yönünü seçer (C anlambilimi, K20). İşi olmayan
   araç her iki modda bulunduğu katta kalır; park katı seçimi v4.0'a ertelenmiştir (K21).
3. **Yolcu-saniye ödülü, γ = 1.** Ödül, bekleyen her yolcu için geçen her saniyeye `-1`
   yazar. `γ = 1` seçildiğinde bölüm getirisi doğrudan **toplam yolcu-bekleme süresinin
   negatifi** olur.
4. **Mevcut fiziksel durum gözlemi (uygulanmamış eylem sızıntısı yok).** Gözlem,
   henüz uygulanmamış yeni eylemi değil, karar anındaki fiziksel durumu ve gerekli kalıcı
   kontrol durumunu içerir. Atama artık fiziksel rezervasyon olduğundan, ikinci mikro-adımın
   gözlemi o karar anında seçilip uygulanmış yeni atamayı içerir (K13); önceki karar anından
   kalan atamanın ilk mikro-adımda gösterilip gösterilmeyeceği açık bırakılmıştır (K17). NC-R'de
   mevcut hedef, hareket yönü ve `CH == konum` ilişkisinin temsil biçimi geçiş sözleşmesine bağlıdır
   (§6.1, §6.2, §6.6); C modunda boş aracın yönü her karar anında yeniden seçildiğinden gözlemde yön
   taşınmaz (K18).

---

## 1. Proje Bağlamı

| Başlık | Bilgi |
|---|---|
| Sistem | ESRA 3.0 — hedef (varış yeri) tabanlı asansör grup kontrol simülatörü |
| Dil / araçlar | Python, PyCharm, Claude Code |
| Mevcut kontrolör | Genetik algoritma (GA); RL ek/alternatif olarak ekleniyor, GA kaldırılmıyor |
| İlgili dosyalar | `simulator.py`, `controller.py`, `configuration.py`, `traffic.py`, `obj_fun_destination.py`, `scenario_generation.py` |
| Birlikte çalışılan kişi | Öner (`car.py`, `building.py`, `main.py` ve veri tarafı) |
| Ölçek | Asansör sayısı `C = 4–8`; OD (başlangıç–varış) çifti sayısı `N ≈ 10–30` |
| Örnek senaryo | `F = 4` kat, `N = 12` OD çifti (5'i aktif), `C = 2` (şema doğrulaması için) |
| Hedef kütüphane | `stable-baselines3` + `sb3-contrib` (MaskablePPO), `gymnasium` API |
| Akademik bağlam | Ruokokoski 2015, Torres & Bierlaire 2023 vb. ile ilişkilendirilebilir |

---

## 2. Terminoloji

| Terim (TR) | Karşılık (EN) | Anlam |
|---|---|---|
| Kat | Floor | Binanın katı; `1 … F` |
| Araç / kabin | Car / cabin | Tek bir asansör |
| Yolcu çağrısı | Call | Bir yolcunun OD talebi |
| Kabin çağrısı | Car call | Kabine binmiş yolcunun hedef katı talebi |
| Kat çağrısı | Hall call / landing call | Yolcu çağrısının oluşturulduğu kat |
| OD çifti | Origin–Destination pair | `(başlangıç katı, varış katı)` |
| Konum | Position | Aracın kat cinsinden sürekli olmayan konumu (0.5'in katları) |
| Yön | Direction | Aracın hareket yönü `state ∈ {−1, 0, +1}`. NC-R'de `yön ≡ sign(CH − konum)`; C modunda kolektif kontrolörün kalıcı durumu, karar anında kabini boş araç için politika seçer (K20). **Gözlemde yer almaz** (K18) |
| Hedefte mi | At-target flag | Gözlemde 1 bit; NC-R'de aracın `CH`'si bulunduğu kata eşit mi, C modunda `state == 0` mı (hareketsiz / bu duruştan sonra işsiz). İki modda da "boşta mı / taahhütlü mü" ayrımını verir (K18) |
| Öncelikli yön | Prioritized (preferred) direction | C modunda karar anında kabini boş araç için politikanın seçtiği yön; `{−1 aşağı, 0 yok, +1 yukarı}`, araç başına 3 değerli bileşen (§7.1) |
| Sayaç | Counter | Kapı/transfer geri sayımı, `7 → 0` |
| Karar anı | Decision epoch | Politikanın çağrıldığı ayrık an |
| CH | Car target | NC-R'de aracın gitmesi emredilen tamsayı hedef kat; C modunda kullanılmaz (yerini öncelikli yön alır) |
| Maske | Action mask | Geçersiz eylem bileşenlerini kapatma |
| Karar fazı | Decision phase | Bir karar anının iki mikro-adımından biri: faz 0 = atama, faz 1 = ikinci blok (NC-R: hedef kat `CH`; C: öncelikli yön). Kapı fazlarıyla (§3.2) ilgisi yoktur (§7.3) |
| Motor | Engine | ESRA v3 Python simülatörü (`car.py`, `controller.py`, `decision/`); `updateState`, `operate`, `beginPickup` gibi adlar bu koddandır |
| Yolcu-saniye | Passenger-second | Bekleyen yolcu × bekleme süresi toplamı |
| Durma katı | Hold floor | İşi olmayan aracın kaldığı kat: tam kattaysa o kat, yarım kattaysa son hareket yönündeki bir sonraki tam kat (§5.3) |
| Zaman ilerletme | Time advance | Motorun zamanı nasıl ilerlettiği: **adımlı mod** (sabit adım, `Ts = 1 s`; GUI aktifken) ya da **olay tabanlı mod** (bir sonraki olaya atlama; başsız modda, K25). İki modda da karar anları ve ödül aynıdır (§3.1, §3.5) |

---

## 3. Simülasyon Modeli (deterministik, ayrık)

### 3.1 Zaman ve zaman ilerletme
- `1 tik = 1 saniye`; motor **sabit adımlı** çalışır: `Controller.operate` her çağrıda
  `time += Ts` (`Ts = 1 s`) yapar ve her tikte sırayla yeni yolcu kontrolü, (periyodunda) karar
  süreci, araç hareketi ve durum güncellemesi işlenir (`Experiment` döngüsü).
- **Sınıflandırma** (Law, 2015; Banks vd., 2010): modellenen sistem **ayrık olaylıdır** (durum
  yalnızca yolcu gelişi, kata varış ve sayaç geçişlerinde değişir), ancak zaman ilerletme
  mekanizması **sabit adımlıdır** (*fixed-increment time advance*, "time-stepped"); dünya görüşü
  etkinlik taramasıdır (*activity scanning*): her tikte her araç koşullarını denetler ve etkinliğini
  yürütür. ESRA bu anlamda bir *olay tabanlı* (*next-event time advance*) simülatör **değildir**;
  zaman bir sonraki olaya atlamaz, her saniye işlenir. (v3.1 ve öncesindeki "ayrık olaylı
  (discrete-event)" ifadesi gevşekti; düzeltildi. GUI olmadan çalışan olay tabanlı mod §3.5'tedir.)
- Motor **deterministiktir**: verilen yolcu listesi için geçişlerde rastgelelik yoktur. Rastgelelik
  yalnızca trafik üretimindedir: yolcunun kalkış–varış çifti trafik örüntüsünün rota-olasılık
  matrisinden çekilir (`Simulator.generatePassenger`); **varış anları deterministik ve sabit
  aralıklıdır** (her `arrivalRate` saniyede bir yolcu; Poisson süreci değildir). Kayıtlı trafik
  yeniden oynatılabilir (`dataType = 2`). Statik bir örnek (anlık görüntü) tamamen deterministiktir.
- **Karar anları** her tikte değil, yalnızca olaylarda doğar (§3.4); problem bu yüzden bir
  **yarı-Markov karar süreci (SMDP)** olarak modellenir. Bu, RL ortamının özelliğidir ve motorun
  zaman ilerletme biçiminden bağımsızdır: ortam, iki karar anı arasında motoru ya tik tik (adımlı
  mod) ya da doğrudan bir sonraki olaya (olay tabanlı mod, §3.5) ilerletir; politika ikisinde de
  aynı anlarda, aynı gözlemle çağrılır.

### 3.2 Sayaç (kapı/transfer geri sayımı)
Sayaç `7`'den `0`'a iner; `0 = kapı kapalı, harekete hazır`. Fazlar:

| Sayaç değeri | Faz | Süre |
|---|---|---|
| `7 → 5` | Kapı açılma | 2 s |
| `5 → 2` | Yolcu transferi (iniş + biniş) | 3 s |
| `2 → 0` | Kapı kapanma | 2 s |

Toplam durma süresi 7 saniyedir. Araç yalnızca `sayaç = 0` iken hareket edebilir.

### 3.3 Konum ve hareket
- Hız: **1 saniyede 0.5 kat** ⇒ 1 kat = 2 saniye.
- Konum her zaman **0.5'in tam katıdır**: `F = 4` için `{1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0}`
  yani `2F − 1 = 7` ayrık değer. (Konum sürekli bir değişken **değildir**.)
- **NC-R soyutlaması:** Araç uçuş ortasında (ör. `konum = 1.5`) **anında** yön değiştirebilir.
  İvme, fren, mekanik atalet gibi fiziksel detaylar **ihmal edilir**; model "bilgisayar oyunu"
  düzeyinde bir dinamik kullanır. Bu soyutlama bilinçli bir tercihtir.

### 3.4 Karar Anları (Decision Epochs) — en kritik bölüm
Politika **yalnızca** aşağıdaki **iki** olayda çağrılır:

1. **Yeni çağrı (OD talebi) sisteme girdi.**
2. **Sayaç `7`'den `2`'ye indi** — kapı açılmış (`7 → 5`) ve yolcu inişi/binişi
   **tamamlanmıştır** (`5 → 2`). Bu tek olay hem inişi hem binişi kapsar: kapı açıldı,
   yolcu indi **veya** kapı açıldı, yolcu bindi.

> **Yorum:** Karar anı sayaç `2`'de doğar. "`7`'den `2`'ye" ifadesi, kapı açılışından
> transfer bitişine kadar süren **tek bir duruş penceresini** tanımlar; karar bu pencerenin
> **sonunda** (transfer tamamlandığında) verilir.

Bunun sonuçları:

- Araçların katlar arası intikali ve boş katlarda beklemesi karar anı **üretmez**.
- Bir aracın `CH` hedef katına **varışı**, yalnızca transfer doğuruyorsa (yukarıdaki 2. olay)
  karar üretir; varışta transfer olayı yoksa araç o katta **bekler** (kapı hiç açılmaz,
  sayaç dönmez).
- Karar anı sayaç `2`'de doğduğu için politika, karar verirken **transfer sonrası yükü**
  görür: bu duruşta inen ve binen yolcular artık kabin/kuyruk durumuna yansımıştır.
- Karar anında kabin hâlâ kapı fazındadır; seçilen `CH` (NC-R) ya da öncelikli yön (C), sayaç
  `0`'a indiğinde (kapı kapandığında) uygulanmaya başlar. Motorda hareketi sayaç yönetir:
  `Controller.operate` sayaç sıfırlanana kadar `state`'e bakmaz; kapı çevrimi sırasında yön
  `±1` olması aracı kımıldatmaz.
- Her duruşta **tam olarak bir** karar anı doğar. Bu, "hedefsiz kalan araç" (liveness)
  sorununu doğal olarak çözer: her duruş yeni bir `CH` üretir; hedefe varan araç, işi kalmadıysa
  orada kalır (park katı seçimi v4.0'a ertelendi, §15). (Bu zincirin kopmaması, `CH` maskesinin
  **yeni** atamadan hesaplanmasına bağlıdır; bkz. §7.3 "canlılık sonucu".)
- Ortam API'sinde her karar anı, aynı simülasyon anında art arda gelen **iki mikro-adımdır**
  (iki `step()` çağrısı): faz 0 atama, faz 1 ikinci blok (NC-R: hedef kat `CH`; C: öncelikli
  yön). İki adım arasında zaman ilerlemez ve olay işlenmez; karar anı sayısı değişmez (§7.3).
  Faz 1, seçimsiz (her bileşen tek seçeneğe maskeli) olsa bile atlanmaz.
- **Eski tasarıma göre fark:** Sayaç `7`'deki (biniş başlangıcı) ayrı karar anı
  **kaldırılmıştır**. Politika artık kapı açılışında değil, duruş tamamlandığında karar verir;
  bu, aynı duruş için gereksiz ikinci bir karar noktasını ortadan kaldırır.

### 3.5 Zaman ilerletme modları: adımlı ve olay tabanlı (K25)

**Adımlı mod (mevcut, referans).** GUI aktifken zorunludur: animasyon her tiki çizer
(`displayTraffic`) ve akış `time.sleep` ile gerçek zamana yakın tutulur. Referans davranış bu
moddur; eşdeğerlik testleri buna göre yapılır.

**Olay tabanlı mod (başsız; uygulanacak).** GUI aktif değilken — RL eğitimi, toplu değerlendirme,
kesin referans üretimi, `headless_benchmark.py` — motor zamanı doğrudan bir sonraki olaya ilerletir
(*next-event time advance*):

- **Olay takvimi.** Her araç için en yakın durum değişikliği anı:
  - hareket hâlindeki araç: bir sonraki **duruş yapacağı** kata varış (kabin hedefi ya da
    kendisine atanmış, yönündeki kat çağrısı; NC-R'de `CH`) — `Δ = |hedef − konum| / 0.5` s.
    Duruş yapmayacağı katlardan geçiş olay değildir;
  - kapı çevrimindeki araç: sayaç geçişleri `7→5` (2 s), `5→2` (3 s), `2→0` (2 s);
  - işsiz araç: olay yok.

  Sistem düzeyinde: bir sonraki yolcu gelişi (dinamik trafikte `arrivalRate`'in bir sonraki katı;
  statik örnekte yok) ve GA için periyodik karar süreci (`decisionPeriod`; RL ortamında kullanılmaz).
- **İlerletme.** `t* = min(olay anları)`; zaman `t*`'a atlanır, hareket hâlindeki araçların konumu
  kapalı biçimde güncellenir (`konum += state · 0.5 · (t* − t)`), sonra `t*`'a düşen bütün olaylar
  adımlı modun aynı tik içindeki sırasıyla işlenir (yeni yolcu → karar süreci → `operate` →
  `updateState`). Bütün süreler tam saniye olduğundan zaman tamsayı kalır; `_atPeriod` yalnızca
  `t*` noktalarında değerlendirilir.
- **Ödül.** İki olay arasında bekleyen (`n_W`) ve kabindeki (`n_T`) yolcu sayıları sabittir;
  yolcu-saniye toplamı kapalı biçimde `−(n_W + a · n_T) · (t* − t)` olarak hesaplanır ve §8.1'deki
  saniye bazlı toplamla aynı değeri verir.
- **Eşdeğerlik zorunluluğu.** Olay tabanlı mod, adımlı modla **birebir aynı yörüngeyi**
  üretmelidir: araç konumları ve sayaçları, biniş/iniş anları, WT/TrT/TTD, karar anları ve
  gözlemler. Doğrulama: aynı örnek ve tohumda iki modun durum izleri (trace) karşılaştırılır;
  `headless_benchmark.py`'ye `--event-mode` bayrağı eklenir ve 20 tohumluk kıyaslama iki modda özdeş
  olmalıdır; karşılaştırma regresyon testi olarak kalıcılaştırılır. Eşdeğerlik testi geçmeden olay
  tabanlı modda eğitime başlanmaz.
- **Kazanç.** İşlenen adım sayısı saniye sayısından olay sayısına düşer; statik bir bölümde tipik
  olarak 60–200 tik yerine 10–30 olay. RL eğitiminin maliyeti simülasyon saniyesiyle değil olay
  sayısıyla ölçeklenir.
- **Uygulama ilkesi.** Zaman ilerletme motorda tek bir noktada soyutlanır (`tick()` /
  `advance_to_next_event()`); `Experiment` GUI açıkken `tick()`, başsızken olay tabanlı ilerletmeyi
  kullanır. Kontrol mantığı (`updateState`, `operate`, `beginPickup`) değişmez; yalnızca kaç kez
  çağrıldığı değişir. Olay tabanlı modun doğruluğu "olaylar arasında karar durumu değişmez"
  varsayımına dayanır; bu varsayımı ihlal eden her mantık (ör. uçuş ortasında her tik yeniden
  değerlendirilen bir kural) eşdeğerlik testinde ortaya çıkar ve olay listesine eklenir. Tik bazlı
  kayıtlar (zaman serisi grafikleri) olay tabanlı modda ya kapalı tutulur ya da olaylar arası sabit
  değerlerden yeniden oluşturulur.

---

## 4. Yolcu / Çağrı Modeli

### 4.1 Çağrı grupları — Birleşik fiziksel rezervasyon durumu
- Her **aktif** OD çifti için mutlaka tam olarak bir araç atanır; **erteleme (deferral) yoktur**.
- Atama **serbestçe yeniden yapılabilir** (FREE reassignment). Bir OD grubu aynı anda yalnızca bir araca atanır; bir araç aynı anda birden fazla OD grubunu taşıyabilir veya alabilir.
- Atama, karar anında üretilen eylemin bir parçasıdır ve bir sonraki yeniden atama kararına kadar **fiziksel rezervasyon** olarak geçerlidir.
- Aynı OD çiftine yeni bir çağrı geldiğinde grup bölünmez ve birleşmez; eski + yeni yolcular tek grup olarak birlikte taşınır.
- Aktif olmayan (boş) OD çiftleri **maskelenir**.
- Simülatör, WT/TT için yolcu başına kuyruğa katılma ve biniş zamanlarını **bireysel** tutar; gözlemdeki ortalama/min/maks yalnızca politika için bir **özet**tir.

### 4.2 Biniş / iniş modeli
- Biniş modeli basitleştirilmiştir: kapı açıldığında, o katta bekleyen **ve o araca atanmış** OD grubunun tamamı anında biner (`β = ∞` gibi), grup bölünmez.
- Aynı katta birden fazla OD grubu bekliyorsa, kapısı açılan araç yalnızca kendisine atanmış grupları alır. Örneğin iki grup aynı katta bekliyorsa ve yalnızca birinci grup bu araca atanmışsa, yalnızca birinci grup biner; ikinci grup binmez.
- Aynı araç aynı katta birden fazla OD grubuna atanmışsa, bu grupların tamamı aynı duruşta biner.
- **Atanmamış bir kabin** kapısını açarsa o katta bekleyen yolcular binmez; kapı açılması tek başına rezervasyonu değiştirmez.
- İniş benzer şekilde, o katta inecek tüm kabin yolcuları anında iner. İniş, OD grubunun atamasından bağımsız olarak kabindeki yolcunun hedef katına göre gerçekleşir.
- Atama bu modelde yalnızca yönlendirme niyeti değildir; hangi kabinin hangi bekleyen OD grubunu alabileceğini belirleyen fiziksel bir rezervasyondur.
- **C modunda biniş yönlüdür** (§11/10 çözümü): kapısı açılan araç yalnızca hizmet yönündeki (`state`'inin gösterdiği yöndeki) atanmış grupları alır; aynı kattaki ters yönlü atanmış grup aracın dönüşünü bekler ve bu bekleme ödüle yansır. Aynı katta iki yönlü grup atanmış duran araçta hangi grubun önce bineceğini faz 1 yön seçimi belirler (§5.2). NC-R'de §4.2'nin yönsüz kuralı geçerlidir.
- Gözlemde önceki atamanın (atanmış araç kimliğinin) tutulup tutulmayacağı **henüz açık bir tasarım kararıdır** (§6.1, §6.6, §11/6). Atama fiziksel durumun parçası olduğundan, gözlemden çıkarılması ancak geçiş ve maske sözleşmesinin kısmi gözlemlilik üretmediği gösterilirse kabul edilebilir.

### 4.3 Bekleme süresi tanımı (ödül ile doğrudan bağlantılı)
Bir yolcunun bekleme süresi, **kuyruğa katıldığı andan**, kendisini alan ve kendisine atanmış kabinin **kapısı açılıp binme işleminin başladığı ana** kadar geçen süredir. Bu an, sayaç `5`'e düştüğü andır (kapı açılmıştır ve binme başlar). Sayaç `5 → 2` transfer ve `2 → 0` kapanma fazları artık beklemeye dahil değildir.

> **Ödül entegrasyonu saniye bazında yapılmalıdır.** Bekleme sayaç `5`'te bitiyor, karar anı ise sayaç `2`'de doğuyor (§3.4). Yani bir karar aralığının **içinde** yolcu beklemeleri sona erebilir. Bu yüzden `r_t`, aralığın uç noktalarındaki bekleyen sayısından değil, **her saniyedeki bekleyen sayısının toplamından** hesaplanmalıdır (§8.1).

---

## 5. Kontrol Modları: NC-R ve C

Her iki mod da aynı **atama bloğunu** kullanır (§7.1); ikinci blok moda özgüdür: NC-R'de araç
başına hedef kat `CH[c] ∈ {0, 1 … F}`, C modunda araç başına öncelikli yön `d[c] ∈ {−1, 0, +1}`.
İzinli kümeler (maskeler) iki modda da faz 1'de yeni atamadan hesaplanır (K13).

### 5.1 NC-R (Non-Collective)
`CH[c] ∈ K_olay(c)`; `K_olay(c) = ∅` ise `CH[c] = durma katı` (araç bulunduğu katta kalır, §5.3)

- **Olay üreten katlar:** Aracın gidişiyle yeni bir karar olayı doğurabilecek hedefler:

  ```
  K_olay(c) = { kabin c içindeki yolcuların hedef katları }                       ← iniş olayı üretir
            ∪ { bekleyen ve c aracına atanmış OD gruplarının başlangıç katları } ← biniş olayı üretir
  ```

- İkinci kümede yalnızca **c aracına fiziksel olarak atanmış** ve hâlâ bekleyen OD grupları bulunur. Başka bir araca atanmış grupların başlangıç katları, c aracı için olay üreten kat değildir; c bu katta kapı açsa bile yolcular binmez.
- Bu tanım artık atama bilgisinden bağımsız değildir. Atama fiziksel rezervasyon olduğu için `K_olay(c)`, kabin içi yük ve atama durumunun birlikte fonksiyonudur.
- Araçta bekleyen iş yoksa (`K_olay(c) = ∅`) `CH[c]` tek seçeneğe maskelenir: **durma katı** (§5.3). Araç bulunduğu katta kalır, başka bir kata gitmez. Buradaki “bekleyen iş”, c aracına atanmış bekleyen OD grubu veya kabin içi hedef anlamındadır.
- **Park katı seçimi bu sürümde yoktur.** Boş aracın `CH` ile bir park katına yönlendirilmesi (ilk tasarımdaki "park katı serbestisi") v4.0 temasıdır (§15, K21).

> **Maskenin gözlemden üretilebilirliği:** Önceki tasarımda atama fiziksel olmadığı için maske yalnızca kuyruklar ve kabin içeriğinden hesaplanabiliyordu. Yeni birleşik durumda maske, atanmış OD grubunu bilmeye ihtiyaç duyar. K13 kararı (§7.3) ile `CH` maskesi yalnızca karar anının **faz 1**'inde ve o anda **yeni seçilmiş** atamaya göre hesaplanır; faz 1 gözlemi bu atamayı gösterdiğinden (§6.1) maske gözlemden yeniden üretilebilir.

### 5.2 C (Collective) — C anlambilimi

C modunda araç hareketini ESRA'nın kolektif kontrolörü (`Car.updateState('fixed')`) yürütür: araç,
yönündeki kabin hedeflerinde (DF) ve kendisine atanmış kat çağrılarında durur; yönünde iş kalmayınca
döner ya da durur. Politika bu kontrolöre tek bir yerde girdi verir: **karar anında kabini boş olan
aracın yönü** (K20). Kural, "C anlambilimi":

1. Faz 1'de ortam, **gerçekten boş** her araca `state = 0` yazar: kabinde yolcu yok, kabin hedefi
   (DF) yok **ve** binmek üzere seçilmiş yolcu (`pendingBoard`) yok. Hareket hâlindeki boş araç da
   dâhildir; karar anında yönünü "unutur".
2. Politika her araç için öncelikli yön `d[c] ∈ {−1, 0, +1}` seçer (maske aşağıda). Ortam bunu
   `car.preferredDirection`'a yazar; `Dispatcher.run()` içindeki `updateState`, `state == 0` dalında
   DF yoksa bu değeri `state` olarak alır.
3. Karar anları arasında `updateState` olduğu gibi çalışır: seçilen yönü önde iş varken korur,
   yolcu binince DF yönünü sürdürür, kabin boşalınca kalan işe döner. Dolu araç için politika hiçbir
   şey seçmez (`{0}`); kontrolör sürer.

Faz 1 maskesi (yeni atamaya göre, araç başına):

| Aracın durumu (yeni atama sonrası) | İzinli küme | Gerçek seçim |
|---|---|---|
| Kabinde yolcu var **veya** binmek üzere yolcu var (`pendingBoard`) | `{0}` — kontrolör sürer | yok |
| Boş, atanmış çağrı yok | `{0}` — yerinde kalır (K21) | yok |
| Boş, atanmış çağrılar yalnızca üstte | `{+1}` | yok |
| Boş, atanmış çağrılar yalnızca altta | `{−1}` | yok |
| Boş, iki yanda da atanmış çağrı | `{−1, +1}` — `0` **kapalı** | **var** |

"Üst/alt" sınıflaması motorun `updateAboveBelowHCs` kuralıdır: aracın bulunduğu kattaki yukarı
çağrı "üst", aşağı çağrı "alt" sayılır; aynı katta iki yönlü grup atanmış duran araç son satıra
girer ve seçim "önce hangi grup binsin" anlamına gelir (§4.2).

- **`0` iki yanlı durumda kapalıdır.** Motorun yakınlık kuralı (`case 0`: yakın çağrıya yönel,
  eşitlikte yukarı) politikanın erişebildiği bir eylem değildir; yalnızca maske delinirse çalışan
  emniyet ağıdır. İşi olmayan tarafı seçen bir yön de `updateState`'in `±1` dalı tarafından
  düzeltilir (önde iş yoksa döner/durur); doğru maskeyle bu hiç tetiklenmez.
- **Hareket hâlindeki boş araç da yeniden yönlendirilir.** Örnek: 4'te boş araç 12'deki yukarı
  çağrıya atanıp yola çıkmış, 5,0'a geldiğinde 4'te aşağı çağrı doğup aynı araca atanmışsa politika
  `−1` seçebilir: araç döner, 4'teki yolcuyu alır, yolcunun hedefine iner, sonra 12'ye çıkar. Portun
  kendi kuralı (yönü koru) olsaydı araç 12'ye devam ederdi; MATLAB ESRA 2.0'ın "her karar anında
  hafızasız boş araç" davranışının politikalı sürümü budur.
- **Biniş bekleyen araç sıfırlanmaz.** Kapı açılma penceresinde (`beginPickup` sonrası, biniş
  öncesi) kabin boş görünür ama hedefi bellidir; [A5] (K22) bu hedefi `updateState`'e gösterir,
  ortam da bu aracı dolu sayar. Aksi hâlde araç yukarı yolcuyla aşağı inebilir (K22'deki iz).
- Aynı katta başka bir araca atanmış OD gruplarının bulunması, c aracı için kat çağrısı oluşturmaz;
  c bu kata yönelip kapısını açsa bile bu gruplar binmez.
- İşi olmayan araç yerinde kalır; yarım kattaysa orada kalır (K23).

> **Uygulama notu.** `updateState` kapatılmaz, değiştirilen tek yer `case 0`'daki iki yanlı
> daldır: `preferredDirection ∈ {−1, +1}` ise o yön, `0` ise eski yakınlık kuralı. Sıfırlama ve
> `preferredDirection` yazımı RL dağıtıcısında, `Dispatcher.run()` çağrısından önce yapılır;
> `preferredDirection` her karar anında yeniden yazılır (seçilmediyse `0`). Ortam, emniyet ağının
> tetiklenme sayısını `info` ile raporlamalıdır (maske hatası göstergesi).

### 5.3 Ortak kurallar
- İkinci blok her karar anında her araç için üretilir (faz 1). NC-R'de `CH` her zaman bir kattır
  (`0` faz 1'de kapalı); C modunda öncelikli yön, seçimsiz araçlar için maskeyle tek değere iner
  (§5.2). Eski `false` değeri yoktur.
- **Durma katı (K21, NC-R):** aracın işi yoksa `CH` tek seçeneğe maskelenir ve araç yerinde kalır.
  Araç tam kattaysa durma katı o kattır; yarım kattaysa son hareket yönündeki bir sonraki tam
  kattır (deterministik; politika seçim yapmaz). C modunda işi olmayan araç bulunduğu konumda kalır
  (yarım kat dâhil, K23). Boş araçların park katına yönlendirilmesi v4.0 temasıdır (§15).
- Sıra K13 ile tanımlıdır: **önce atama (faz 0), sonra yeni atamaya göre hesaplanan ikinci blok
  maskesi (faz 1)**; bkz. §7.3. Maske her araç için faz 1'de kesin olarak üretilir; faz 1 atlanmaz.
- Gözlemde ayrı bir `mevcut_hedef` değişkeninin gerekip gerekmediği NC-R için açıktır (§6.2 ve
  §11/7); C modunda hedef kavramı yoktur. İkinci bloktaki `0` indeksi faz 0'da her araç için tek
  seçenektir; faz 1'de NC-R'de kapalı, C modunda §5.2 tablosuna göre açıktır.


---

<!-- ==== KESİT BAŞLANGICI: §6–§7 · başka bir modele buradan itibaren verilir ==== -->

## 6. Gözlem Uzayı

### 6.0 Bağlam Kapsülü (kesit §6–§7 için)

> **Bu bölüm tek başına paylaşılabilir.** §6 ve §7, gözlem/eylem tasarımını bağımsız olarak
> inceletmek üzere `KESİT BAŞLANGICI` / `KESİT SONU` işaretleri arasında toplanmıştır; hazır
> paket `esra-3-rl-kesit-6-7.md` dosyasındadır. Aşağıdaki kapsül, kesitin **dışında** kalan
> tüm tanımları özetler. Kesitte geçen `§3.x`, `§4.x`, `§5.x` gibi referanslar kaynak
> dokümanın ilgili bölümlerine aittir.

**Sabitler ve boyutlar**

| Sembol | Anlam |
|---|---|
| `F` | Kat sayısı; katlar `1 … F` |
| `C` | Asansör (kabin) sayısı; etiketler `1 … C` |
| `N` | OD (başlangıç–varış) çifti sayısı; satırlar `1 … N` |
| `N_max` | Sayım normalizasyonu için yolcu ölçeği |
| `T_ref` | Bekleme/seyahat süresi **ölçek referansı** = `300` s (**üst sınır değil**) |
| `T_ufuk` | Bölüm (epizod) süresi; **garantili üst sınır** |

**Kesitin dışından gereken tanımlar**

- **Zaman:** `1 tik = 1 s`; motor sabit adımlıdır, başsız modda olaydan olaya ilerletilir (§3.5;
  ortam davranışı iki modda aynıdır). Araç `1 s`'de `0.5 kat` ilerler ⇒ konum her zaman `0.5`'in
  katıdır (`F = 4` için `{1.0, 1.5, …, 4.0}`, yani `2F − 1 = 7` ayrık değer).
- **Sayaç:** `7 → 0`. `7→5` kapı açılma (2 s), `5→2` yolcu transferi (3 s), `2→0` kapı
  kapanma (2 s). Araç **yalnızca** `sayaç = 0` iken hareket eder.
- **Karar anı (SMDP):** yalnızca iki olay — (i) yeni çağrı (OD talebi) sisteme girdi;
  (ii) sayaç `7`'den `2`'ye indi (kapı açıldı, iniş/biniş tamamlandı). Her karar anı, aynı
  simülasyon anında iki mikro-adımdan (iki `step()` çağrısından) oluşur: **faz 0** atama,
  **faz 1** ikinci blok (NC-R: hedef kat `CH`; C: öncelikli yön); bkz. §7.3. Faz 1 atlanmaz.
- **Bekleme (WT):** yolcunun kuyruğa katılma anından **sayaç `5`'e** (kapı açıldı, binme
  başlıyor) kadar geçen süre.
- **`CH[c]` (NC-R):** karar anında `c` aracına verilen **tamsayı hedef kat**, `∈ {1 … F}`. İşi
  olmayan araç için durma katına (yerinde kalır) maskelenir (§5.1, §5.3).
- **`d[c]` (C):** karar anında kabini boş `c` aracı için **öncelikli yön** `∈ {−1, 0, +1}`; dolu
  araç, işi olmayan araç ve tek yanlı atama için maskeyle tek değere iner, yalnızca iki yanlı atamada
  `{−1, +1}` seçimi vardır (§5.2). Karar anında kabini boş her araç `state = 0`'a çekilir ve yönü bu
  bileşenden alır (C anlambilimi, K20).
- **Mevcut hedef ve yön:** Karar anında seçilen yeni `CH`, kararlar arasındaki mevcut hareket hedefiyle karıştırılmamalıdır. Mevcut hedef/yönün gözlemde nasıl temsil edileceği §6.2 ve §11/7'de açık sorudur; yeni aday `CH`'den önceden türetilmez.
- **Birleşik fiziksel rezervasyon durumu:** her aktif OD grubu tam olarak bir araca atanır; yalnızca atanmış araç kapısı açıldığında bu grubun yolcuları biner. Atanmamış kabin bekleyen grubu alamaz. `calls` bloğu her OD satırında `C` boyutlu atama one-hot'u taşır (K13): faz 1'de o karar anında seçilen yeni atama; faz 0 sütunlarının içeriği (sıfır mı, önceki rezervasyon mu) açık karardır (K17).
- **Kontrol modları:** NC-R (non-collective) ve C (collective) aynı atama bloğunu paylaşır;
  ikinci blok NC-R'de `[F + 1] × C` (hedef kat), C'de `[3] × C` (öncelikli yön). Modlar ayrı
  eğitilir (K14).
- **Ödül:** `r = − Σ bekleyen yolcu × saniye` (yolcu-saniye), `γ = 1`.
- **Uygulama kısıtı:** `sb3_contrib.MaskablePPO`; eylem `MultiDiscrete` (**`Box` eylem
  desteklenmez**); gözlem `Dict` (`MultiInputPolicy`); maske her adımda `np.int8` dizisi ve
  ortamın `action_masks()` yöntemiyle **karar fazına göre** üretilir (§7.2).

---

`gymnasium.spaces.Dict` altında **3 adet `Box` yaprağı**: `"calls"`, `"cars"`, `"globals"`.

### 6.1 `"calls"` — temel boyut `N × 4`, atama özelliği açık
Her OD çifti için fiziksel durumun politika açısından özetlenmesi:
1. Bekleyen yolcu sayısı, `log(1 + n) / log(1 + N_max)`
2. Ortalama bekleme süresi, `log(1 + WT̄) / log(1 + T_ref)`
3. Minimum bekleme süresi, `log(1 + WT_min) / log(1 + T_ref)`
4. Maksimum bekleme süresi, `log(1 + WT_max) / log(1 + T_ref)`

> **`T_ref = 300` s (ölçek referansı, K19).** Sayımlarda kullanılan `log1p` sıkıştırması zamanlara da uygulanır. Seçilen değerler:

| Bekleme | Lineer `/1000` | **Log, `T_ref=300`** |
|---|---|---|
| 15 s | 0.015 | **0.486** |
| 30 s | 0.030 | **0.602** |
| 60 s | 0.060 | **0.720** |
| 120 s | 0.120 | **0.840** |
| 300 s | 0.300 | 1.000 |
| 1000 s | 1.000 | 1.211 |
| 3000 s | 3.000 | 1.403 |

> Tipik bant (`15 … 120` s) aralığın **%35.5**'ini kullanır (lineer `/1000` ile yalnızca %10.5'i). Minimum bekleme özelliği de `[0.000, 0.534]` bandına yayıldığı için **ölmez**.
>
> **`T_ref` bir üst sınır DEĞİLDİR.** `T_ref` yalnızca bir ölçek sabitidir; değer `1`'i aşabilir (`WT = 3000` s için `1.40`). Bu yüzden gözlem uzayının bu özellik için üst sınırı `1.0` değil, güvenli bir tavan (ör. `1.5`) veya `T_ufuk`'tan türetilmiş finite bir değer olmalıdır.

#### Atanmış araç kimliğinin gözlemde tutulması — düzen karara bağlandı (K13), faz 0 içeriği açık (K17)

Yeni birleşik durumda atama **fiziksel rezervasyondur**. Bu nedenle atanmış araç kimliği, yalnızca politikanın önceki eyleminin etiketi değil, sonraki biniş olayını belirleyen kalıcı bir durum değişkeni olabilir.

K13 kararı (§7.3) ile `calls` bloğu **`N × (4 + C)`** düzenindedir: her OD satırına atanmış araç için `C` boyutlu one-hot eklenir; pasif OD satırı bu alanlarda sıfırdır. Sütunların içeriği karar fazına göre değişir:

- **Faz 1 (hedef / yön fazı):** one-hot, bu karar anının faz 0'ında seçilen ve rezervasyon durumuna yazılmış **yeni atamadır**. Faz 1'deki ikinci blok maskesi (`CH` ya da öncelikli yön) bu atamadan hesaplanır; dolayısıyla maske gözlemden yeniden üretilebilir.
- **Faz 0 (atama fazı):** içerik K17'de açık karardır:
  - **O0 anlamı:** sütunlar sıfır; politika atamayı yalnızca kuyruk özetlerine ve araç durumlarına bakarak yapar. Bu seçenek ancak her karar anında aktif grupların atamasının faz 0'da tamamen yenilendiği ve önceki rezervasyonun geçişi veya ödülü etkilemediği (churn cezası, atama kilidi veya `KEEP` benzeri kalıcılık olmadığı) durumda Markov'dur.
  - **O1 anlamı:** sütunlar önceki karar anından kalan **mevcut rezervasyonu** gösterir. Önceki atama geçişi veya ödülü etkiliyorsa bu seçenek zorunludur.

Her iki anlamda da bilgi, yeni seçilecek eylemle karıştırılmamalıdır: faz 0 gözlemindeki atama (varsa) **önceki kararın sonucu**, faz 0 eylemindeki atama **bu karar anı için seçilen yeni rezervasyon**, faz 1 gözlemindeki atama ise **uygulanmış yeni rezervasyondur**.

Bekleyen yolcusu olmayan OD satırları temel dört özellikte tümüyle sıfırdır; pasif satırlarda atanmış araç one-hot'u da sıfırdır. Faz 0 için O0 anlamı seçilirse, bunun geçiş fonksiyonuyla birlikte Markovluk testi yapılmalıdır.

### 6.2 `"cars"` — boyut `C × (5F + 2)`; mevcut hedef durumu ayrıca doğrulanmalı
Her araç için:
1. Konum — `One-Hot(2F − 1)`
2. **Hedefte mi** — boolean, 1 bit. NC-R: `CH == konum`. C: `state == 0` (kontrolörün yön durumu
   sıfır: araç hareketsiz ya da bu duruştan sonra işsiz kalıyor; faz 1'de sıfırlanmış her boş araç
   için `1`, dolu araç için `0`). İki modda da satır uzunluğu aynıdır (K18)
3. Sayaç — `sayaç / 7.0`
4. Kabindeki toplam yolcu sayısı — `log(1 + n)`
5. Varış katı istatistikleri — `F × 3`: her hedef kat için `[yolcu sayısı, ortalama seyahat süresi, maksimum seyahat süresi]`

`5F + 2 = (2F − 1) + 1 + 1 + 1 + 3F`

> **Önemli ayrım:** Eylemde seçilen yeni `CH`, mevcut araç hareket komutuyla aynı şey değildir. Eğer araç karar anları arasında önceki hedefe göre ilerlemeye devam ediyorsa, mevcut hedef veya hareket yönü geçişin fiziksel durumunun parçasıdır. Sadece `CH == konum` biti mevcut hedefin hangi kat olduğunu ve hangi yönde hareket edildiğini göstermez. Bu nedenle mevcut hedefin gözleme eklenmesi veya geçişin her karar anında tamamen yeni eylemle yeniden tanımlanması §11/7'de açık karardır.

> Yönün yeni eylem `CH`'sinden türetilmesi, aynı anda üretilecek eylem öncesindeki mevcut hareket yönünün gözlemden silinmesi anlamına gelmemelidir (NC-R). C modunda bu sorun kalkar: boş aracın yönü karar anında sıfırlanıp yeniden seçildiğinden önceki yön geçişi etkilemez; dolu aracın yönü varış katı istatistiklerinden çıkar (DF'ler hep seyir yönündedir, çünkü biniş yönlüdür, §4.2). Faz 1 maskesi (§5.2) yalnızca yeni atama ve kabin durumundan hesaplanır (K18).

### 6.3 `"globals"` — boyut `5`
`[simülasyon_zamanı / T_ufuk, toplam_kuyruk / N_max, toplam_kabindekiler / N_max, tamamlanan_yolcu / N_max, faz_biti]`

`faz_biti`: `0` = atama fazı (faz 0), `1` = ikinci faz (NC-R hedef / C yön, faz 1); bkz. §7.3.
Faz 0'ın atlandığı karar anlarında (aktif OD grubu yok) değer `1`'dir; faz 1 hiçbir karar anında
atlanmadığından her karar anında en az bir `faz_biti = 1` adımı vardır.

> **`T_ufuk` ile `T_ref` farklıdır ve karıştırılmamalıdır:**
> - `T_ufuk` = bölümün (epizodun) toplam süresi → **garantili üst sınırdır**, `[0,1]` içinde kalır.
> - `T_ref = 300` s = bekleme özelliklerinin **ölçek referansı** → üst sınır değildir (§6.1).
>
> Aynı sabiti iki iş için kullanmak, ya `Box` sınır ihlali ya da aşırı sıkışma üretir.

### 6.4 Toplam boyut
K13 kararı (§7.3) uyarınca faz 1 gözlemi seçilen yeni atamayı göstermek zorunda olduğundan `calls`
bloğu her OD satırında `C` boyutlu atama one-hot'u taşır ve `globals` bloğuna faz biti eklenir:

```
D = N · (4 + C) + C · (5F + 2) + 5
```

| Yapılandırma | D |
|---|---:|
| `F = 4, C = 2, N = 12` | `12·6 + 2·22 + 5 = 121` |
| `F = 6, C = 8, N = 24` | `24·12 + 8·32 + 5 = 549` |
| `F = 6, C = 8, N = 12` | `12·12 + 8·32 + 5 = 405` |

> Faz 0'da atama sütunlarının içeriği (sıfır mı, önceki rezervasyon mu) K17'de açık karardır;
> bu seçim boyutu değiştirmez. Eski `D_O0 = N·4 + …` formülü geçersizdir.

### 6.5 Normalizasyon ilkeleri

| Değişken türü | Dönüşüm | Not |
|---|---|---|
| Sayımlar (bekleyen, kabindeki, kuyruk) | `log(1 + n) / log(1 + N_max)` | Sıkıştırma |
| Süreler (WT ortalama/min/maks) | `log(1 + WT) / log(1 + T_ref)`, `T_ref = 300` s | Sıkıştırma; `1`'i aşabilir |
| Bölüm zamanı | `/ T_ufuk` | Üst sınırlı, `[0,1]` |
| Sayaç | `/ 7.0` | Sınırlı, `[0,1]` |
| Konum | `One-Hot(2F − 1)` | Kategorik (ayrık) |
| Hedefte mi (`CH == konum` / `state == 0`) | Boolean (0/1) | NC-R / C tanımı §6.2; mevcut hedefin yerine geçmez |
| Atanmış araç | `C` boyutlu one-hot | Faz 1: yeni atama (K13); faz 0 içeriği K17 |
| Faz biti | 0/1 | Faz 0 / faz 1 (§7.3) |
| Yön | Yeni aday eylemden türetilmez | NC-R: mevcut hareket yönü gerekiyorsa ayrıca tanımlanmalı. C: gözleme konmaz; boş araç karar anında sıfırlanır, dolu aracın yönü DF istatistiklerinden çıkar (K18) |

- Zaman özelliklerinde **lineer bölme yerine log sıkıştırma** tercih edildi: lineer ölçekleme tipik bandı aralığın küçük bir kısmına sıkıştırıyor ve minimum bekleme özelliğini pratikte ölü hale getiriyordu.
- Atanmış araç kimliği fiziksel rezervasyon olduğundan, gözlemden çıkarılması artık eylem sızıntısı gerekçesiyle otomatik olarak savunulamaz. Faz 1'de yeni atama her zaman gözlemdedir (K13); faz 0 için O0 anlamı seçilirse Markovluk test edilmelidir.
- Kabin içi seyahat süresi özelliklerinin de WT ile uyumlu biçimde normalize edilmesi gerekir; kabin içi alanların dönüşümü ve finite Box üst sınırları ayrıca belirtilmelidir.
- Gözlem uzayındaki tüm bileşenlerin üst sınırı, gerçekte ulaşılabilecek değere göre tanımlanmalıdır. `log` ile sıkıştırılan zaman özellikleri için bu değer `1` değildir.


---

### 6.6 Gözlemde eylem sızıntısı yok; fiziksel geçmiş durumu saklanmamalı değil, doğru temsil edilmeli

**İlke:** Gözlem `o_t`, karar anındaki **mevcut fiziksel durumun** ve politika için gerekli kalıcı kontrol durumunun fonksiyonudur. Henüz uygulanmamış yeni eylem `a_t` gözleme konmaz. Buna karşılık önceki eylemlerin fiziksel sonuçları sistemde kalıcı hâle gelmişse, bunlar “eylem sızıntısı” sayılmaz; Markov gözlem için gerekli durum değişkenleridir.

```
o_t = f(durum_t)      ,    a_t ∉ o_t
```

Bu ilke her iki mikro-adımda da geçerlidir: faz 1 gözlemi, faz 0 eyleminin **uygulanmış sonucunu** (rezervasyon durumu) içerir, bekleyen bir eylemi değil (§7.3).

Yeni birleşik durum açısından ayrım:

| Bilgi | Durum | Gerekçe |
|---|---|---|
| Yeni kararın atama bloğu | **Faz 0'da yalnızca eylem; faz 1'de gözlem** | Faz 0'da seçilir ve rezervasyon durumuna yazılır; faz 1'de artık uygulanmış durumdur, bekleyen eylem değildir (§7.3) |
| Önceki karar anından kalan atama | **Faz 0 için açık karar (K17)** | Fiziksel rezervasyondur; hangi aracın hangi bekleyen grubu alabileceğini belirler (§6.1) |
| Yeni kararın `CH` / öncelikli yön değeri | **Yalnızca eylem** | Faz 1'de üretilir; faz 1 gözlemine girmez |
| Mevcut hareket hedefi | **Açık karar / doğrulama gerekli** | Araç kararlar arasında önceki hedefe göre hareket ediyorsa geçişin parçasıdır (§6.2, §11/7) |
| Mevcut yön | **Mevcut fiziksel durumdan türetilir** | Yeni aday `CH`'den önceden türetilmemelidir. C modunda karar anında boş araç için sıfırlanır (K20); gözleme girmez (K18) |

Atamanın faz 0 gözleminden çıkarılması (O0 anlamı), eski tasarımdaki gibi “atama fiziksel kısıt değildir” gerekçesiyle savunulamaz; yeni durumda atama binişi doğrudan sınırlar. O0 anlamı seçilecekse ortamın aşağıdaki sözleşmeyi sağladığı gösterilmelidir:

1. Her karar anında tüm aktif OD gruplarının yeni ataması faz 0'da tamamen belirlenir.
2. Yeni atama, herhangi bir biniş veya `CH` maskesi değerlendirilmesinden önce rezervasyon durumuna uygulanır (faz 0 → faz 1 geçişi; K13 ile sağlanır).
3. Geçiş ve faz 1 maskesi, önceki atamaya ihtiyaç duymadan yeni atama ve gözlenen fiziksel durumdan hesaplanır (K13 ile sağlanır).
4. Önceki atama ödülü veya geçişi başka bir yoldan (churn cezası, atama kilidi, `KEEP`) etkilemez.

Madde 4 sağlanmıyorsa faz 0 sütunları **önceki karardan kalan mevcut rezervasyonu** göstermelidir (O1 anlamı); bu one-hot yeni eylemin kendisi değildir. Faz 1 sütunları her durumda uygulanmış yeni atamayı gösterir.

**Uygulama kuralı:** Atama değişimleri ve churn hata ayıklama için `info` sözlüğünde tutulmalıdır. Fiziksel atama gözlemde tutulmasa bile `info` log'unda önceki/yeni atama, değişen OD sayısı ve yeniden atanan grup sayısı raporlanmalıdır. Churn cezası ilk v1'e eklenmeden önce fiziksel geçiş ve atama gözleminin seçimi doğrulanmalıdır.


---

## 7. Eylem Uzayı

### 7.1 Yapı (tek boyutlu düz `MultiDiscrete`)
```
A_NC-R = MultiDiscrete( [C + 1] × N   +   [F + 1] × C )
                       └── N adet atama bileşeni ──┘   └── C adet CH bileşeni ──┘

A_C    = MultiDiscrete( [C + 1] × N   +   [3] × C )
                       └── N adet atama bileşeni ──┘   └── C adet öncelikli yön bileşeni ──┘
```

**Atama bloğu (`a_1 … a_N`):**
- `0` : maskeli / o OD'de aktif bekleyen yok
- `1 … C` : fiziksel olarak atanmış asansör etiketi
- Aktif her OD satırında tam olarak bir araç seçilmelidir. Bu seçim, grubun hangi kabinin kapısı açıldığında bineceğini belirler.
- Atama **faz 0**'da seçilir; faz 1'de bu bileşenler seçilen değere kilitlidir (§7.3).

**CH bloğu (`CH_1 … CH_C`), NC-R:**
- `0` : işlemsiz. **Faz 0**'da her araç için tek seçenektir; **faz 1**'de kapalıdır (§7.3)
- `1 … F` : gidilecek tamsayı hedef kat (faz 1'de seçilir); işi olmayan araç için durma katına maskelidir (§5.3)

**Öncelikli yön bloğu (`d_1 … d_C`), C modu:** araç başına 3 değerli bileşen (one-hot)
- `0` : yön yok / işlemsiz (`state = 0` kalır). **Faz 0**'da her araç için tek seçenek; **faz 1**'de dolu, biniş bekleyen ve işi olmayan araçlar için tek seçenek (§5.2)
- `1` : aşağı (`−1`); `2` : yukarı (`+1`). Faz 1'de yalnızca o tarafta atanmış çağrısı olan boş araç için açık; iki yanlı atamada ikisi açık, `0` kapalı

> **Not (eski tasarımdan fark):** Negatif indeks (`X = -1`) ve `KEEP` bileşeni kaldırılmıştır. Etiketleme tamamen 0-tabanlı pozitiftir. `KEEP`'in çıkarılması, mevcut hedefin gözlemde tutulup tutulmayacağı sorununu ortadan kaldırmaz; hareket kararlar arasında devam ediyorsa bu durum §6.2 ve §11/7'de ayrıca ele alınmalıdır.
>
> **Atama bloğu neden eylemde kalıyor?** Yeni birleşik durumda atama, fiziksel rezervasyondur: `CH` (NC-R) yalnızca *nereye*, öncelikli yön (C) yalnızca *hangi yöne* gidileceğini, atama bloğu ise *hangi OD grubunun hangi araca ait olduğunu* söyler. İki blok birbirinin alternatifi değil, tamamlayıcısıdır.
>
> **Uygulama sırası (K13, §7.3):** Atama faz 0'da seçilir ve rezervasyon durumuna uygulanır; ikinci blok (`CH` ya da öncelikli yön) faz 1'de, yeni atamaya göre hesaplanan maskeyle seçilir. Standart düz `MultiDiscrete` maskesi bunu tek aşamada ifade edemediği için karar anı aynı simülasyon anında iki mikro-adıma bölünür; eylem uzayı mod içinde değişmez.

### 7.2 Aksiyon Maskesi `M(s, faz)`

Maske, ortamın `action_masks()` yöntemiyle her mikro-adımda üretilir ve karar fazına bağlıdır (§7.3).
Düzen, `MultiDiscrete` bileşenlerinin sırasıyla bitiştirilmiş `sum(nvec)` uzunluğunda tek bir ikili dizidir.

**Faz 0 — atama fazı**

- Atama bloğu (`N × (C + 1)`): OD boşsa yalnızca `0` açık: `[1, 0, …, 0]`; OD aktifse `0` kapalı, tüm araçlar açık: `[0, 1, 1, …, 1]`.
- İkinci blok (NC-R `C × (F + 1)`, C `C × 3`): her araç için yalnızca `0` (işlemsiz) açık: `[1, 0, …, 0]`.

**Faz 1 — hedef / yön fazı** (hiçbir karar anında atlanmaz)

- Atama bloğu: OD boşsa yalnızca `0` açık; OD aktifse yalnızca faz 0'da seçilen araç açık (tek seçenek, kilitli).
- CH bloğu, **NC-R:** `K_olay(c) ≠ ∅` ise `K_olay(c)` açık (kabin içi hedefler ∪ faz 0'da c aracına atanmış bekleyen grupların başlangıç katları, §5.1); `K_olay(c) = ∅` ise yalnızca durma katı açık (§5.3). `0` kapalı.
- Öncelikli yön bloğu, **C** (§5.2 tablosu): kabinde yolcu var ya da biniş bekleyen yolcu var → yalnızca `0`; boş ve atanmış çağrı yok → yalnızca `0`; boş ve çağrılar tek yanda → yalnızca o yön; boş ve iki yanda çağrı → `{−1, +1}` açık, `0` kapalı.

Her bileşen için her fazda en az bir seçenek açıktır. Faz 1 maskesi, faz 0'da uygulanmış **yeni** atamadan hesaplandığı için atama ile ikinci blok arasında aynı adımda döngü oluşmaz; bu, K13'ün çözümüdür (§7.3). Tek seçenekli bileşenler öğrenmeye katkı yapmaz (log-olasılık 0, entropi 0); faz 1 yine de her karar anında koşar; böylece faz 1 adımı her karar anında vardır (faz 0 yalnızca aktif OD grubu yokken atlanır) ve faz biti her zaman anlamlıdır.

### 7.3 K13 — Atama ile `CH` maskesi arasındaki adım içi (intra-step) sıralama: **çözüldü (iki mikro-adımlı karar anı)**

**Sorun.** `K_olay(c)` (§5.1), `c` aracına atanmış bekleyen grupların başlangıç katlarını içerir;
dolayısıyla `CH` maskesi aynı karar anında seçilen **yeni** atamaya bağlıdır:

```
yeni atama → hangi katların hangi araç için olay ürettiğini belirler
          → CH maskesi değişir
CH maskesi  → hangi CH değerlerinin seçilebileceğini belirler
```

Standart MaskablePPO, düz bir `MultiDiscrete` eylemin bileşenlerini **tek bir sabit maskeyle ve
birbirinden bağımsız** örnekler; bir bileşenin maskesini aynı adımda örneklenen başka bir bileşene
bağlayan mekanizma yoktur. Atama ve `CH` tek `step()` içinde birlikte seçildiğinde
`CH_maskesi(c) = K_olay(c)` tanımsız kalır.

**Karar.** Karar anı, aynı simülasyon anında art arda gelen **iki mikro-adıma** (iki `step()`
çağrısına) bölünür. Eylem uzayı değişmez: iki adım aynı düz `MultiDiscrete` eylemini kullanır,
yalnızca maskeleri farklıdır.

| | Faz 0 — atama fazı | Faz 1 — hedef / yön fazı |
|---|---|---|
| Karar verilen blok | Atama bloğu (`a_1 … a_N`) | İkinci blok: NC-R `CH` bloğu (`CH_1 … CH_C`), C öncelikli yön bloğu (`d_1 … d_C`) |
| Atama bloğu maskesi | Boş OD → yalnızca `0`; aktif OD → `1 … C` açık | Aktif OD → faz 0'da seçilen araca **kilitli** (tek seçenek); boş OD → yalnızca `0` |
| İkinci blok maskesi | Her araç için yalnızca `0` (işlemsiz) açık | §5.1/§5.2 izinli kümesi, **yeni atamaya göre** hesaplanmış; `0` NC-R'de kapalı, C modunda yalnızca seçimsiz araçlar (dolu, biniş bekleyen, işsiz) için açık |
| Gözlem | Karar anındaki fiziksel durum; `calls` atama sütunlarının içeriği K17 (§6.1); `faz_biti = 0` | Aynı fiziksel durum; `calls` atama sütunlarında **seçilen yeni atama** (one-hot); `faz_biti = 1` |
| Geçiş | Yeni atama rezervasyon durumuna yazılır; **zaman ilerlemez**, olay işlenmez | `CH` / öncelikli yön uygulanır (C: boş araçlar sıfırlanır, `preferredDirection` yazılır, `Dispatcher.run()` koşar); fizik bir sonraki karar anına kadar ilerler |
| Ödül | `0` | §8.1'e göre aralıkta biriken yolcu-saniye |

Kurallar:

- Faz 0'ın ardından her zaman faz 1 gelir; iki adım arasında olay işlenmez, yeni çağrı kabul edilmez.
- Aktif OD grubu yoksa faz 0 atlanır; karar anı yalnızca faz 1'den oluşur (`faz_biti = 1`).
- Faz 1 hiçbir koşulda atlanmaz; ikinci bloğun bütün bileşenleri tek seçeneğe maskeli olsa bile
  adım ajana sorulur ve `faz_biti = 1` gözlemi üretilir.
- Gözleme bir **faz biti** eklenir (§6.3). Faz 1 gözlemi yeni atamayı göstermek zorunda olduğundan
  `calls` bloğu `N × (4 + C)` düzenindedir (§6.1, §6.4); bu, O1 düzenini zorunlu kılar.
- Maske, ortamın `action_masks()` yöntemiyle faza göre üretilir (§7.2). Standart `MaskablePPO`,
  `MultiInputPolicy` ve düz `MultiDiscrete` yeterlidir; özel politika veya dağılım kodu gerekmez.

**Neden getiriyi değiştirmez.** Faz 0 adımının süresi ve ödülü sıfırdır. `γ = 1` altında bölüm
getirisi yalnızca faz 1 adımlarında biriken yolcu-saniye toplamıdır, yani tek adımlı formülasyonla
aynıdır; en iyi politika da değişmez. Dolayısıyla önceki sürümdeki gerekçe ("aynı fiziksel zamanda
iki ayrı RL kararı oluşturulmamalıdır") bir kısıt değildir. `γ < 1` seçilirse §8.2'deki `γ^{Δt}`
biçimi faz 0 için `Δt = 0` verir; sabit `γ` ile çalışan standart SB3'te faz 0 adımı yine de `γ`
ile indirimlenir, bu küçük sapma `γ = 1` seçiminde oluşmaz.

**Reddedilen seçenekler.**

- *Önceki atamaya göre maske:* yeni gelen grubun önceki ataması yoktur; hiçbir aracın maskesi o
  kata gitmeyi zorlamaz. Karar anları yalnızca yeni çağrı ve transferle doğduğu için (§3.4),
  gönderilmeyen grup bir sonraki dış çağrıya kadar bekler; çağrı gelmezse sistem kalıcı olarak
  kilitlenir.
- *Genişletilmiş maske:* araç, başka araca atanmış grubun katına gönderilebilir; kapı açılmaz, olay
  doğmaz. İki grup ve iki araçla çapraz gönderme sistemi kilitler.
- *Hiyerarşik / koşullu politika:* aynı sonucu verir, ancak standart `MaskablePPO` dışında özel
  politika ve dağılım kodu gerektirir.

Bu belgedeki kuralları uygulayan bir oyuncak simülatörde rastgele maskeli politikayla 200 bölümde
kalıcı kilitlenme sayısı: iki fazlı (tutarlı) maske 0, önceki atamaya göre maske 122, genişletilmiş
maske 8 (F = 6, C = 4; ölçüm bu belgeden ayrı bir doğrulama notundadır).

> **Öneri (karar değil).** Ek bir emniyet olayı: *bekleyen yolcu varken hiçbir araç olay üretecek
> durumda değilse* (hepsi `sayaç = 0`, hedefinde ve hedefi transfer üretmiyor) yeni bir karar anı
> doğar. İki fazlı maske doğru uygulandığında bu olay hiç tetiklenmez; bir maske hatasını sessiz
> kilitlenme yerine görünür ve düzeltilebilir kılar.

**Canlılık sonucu.** NC-R'de faz 1 maskesi, `K_olay(c) ≠ ∅` olan her aracı olay üretecek bir kata
göndermeye zorlar; `K_olay(c) = ∅` olan araç durma katında kalır ve zaten ona atanmış bekleyen grup
yoktur. İki karar anı arasında atama değişemez; dolayısıyla ya yola çıkan araç hedefine varıp transfer
olayı doğurur ya da daha önce başka bir olay yeni bir karar anı doğurur. Her iki durumda da karar
anları sürer. Yeni dış çağrı gelmediğinde kabin içi inişler sonludur; sonunda yalnızca biniş olayları
kalır ve bekleyen her grup biner. C modunda canlılık kontrolörden gelir: atanmış çağrısı veya kabin
hedefi olan araç kolektif kuralla ona yönelir; öncelikli yön yalnızca atanmış çağrısı olan tarafa
açılır, seçilen her yön bir atanmış çağrıya varıp biniş olayı doğurur. Her iki modda §3.4'teki "her duruş yeni bir karar anı doğurur" zinciri
kopmaz. (Politikanın bir grubu sürekli yeniden atayarak geciktirmesi mümkündür; bu kilitlenme değil,
ödülle cezalandırılan bir politika niteliği sorunudur.) §5.1 ve §5.2'deki izinli kümeler yalnızca
faz 1'de ve yeni atamayla hesaplanır.

<!-- ==== KESİT SONU: §6–§7 ==== -->

---

## 8. Ödül

### 8.1 Yolcu-saniye tanımı
```
r_t = − Σ_{s ∈ (t-1, t]} bekleyen(s)        (her saniye için ayrı toplam)
```
- Bekleyen her yolcu için geçen her saniye ödüle `-1` ekler.
- Bir yolcu, kuyruğa katıldığı andan **kapısı açılıp transfer başlayana** kadar bekleyen
  sayılır (§4.3).
- Yani `r_t`, o karar aralığındaki **yolcu-saniye** (kişi × süre) toplamının negatifidir.

> **Neden uç noktalardan değil, saniye saniye toplanmalı?** Bekleme sayaç `5`'te biter
> (§4.3), karar anı ise sayaç `2`'de doğar (§3.4). Bir karar aralığının **içinde** beklemeler
> sona erer. Eğer `r_t` yalnızca `bekleyen(t)` ve `bekleyen(t-1)` farkından hesaplanırsa, bu
> iç bitişler yanlış sayılır. Doğru uygulama: simülatör her tikte `bekleyen(s)` değerini
> biriktirir, karar anında bu toplamı raporlar. Bu, `γ = 1` altında bölüm getirisinin
> **birebir** toplam yolcu-bekleme süresine eşit olmasını garanti eder (§8.2).
>
> Olay tabanlı modda (§3.5) aynı toplam kapalı biçimde hesaplanır: iki olay arasında bekleyen sayısı
> sabittir, dolayısıyla `bekleyen · Δ` toplanır; sonuç saniye bazlı toplamla özdeştir.

### 8.2 İndirimleme (γ)
- **`γ = 1` ile başlanacak.** Bu seçimde bölüm getirisi tam olarak
  `G = − (toplam yolcu-bekleme süresi)` olur; ödül ile amaç fonksiyonu birebir örtüşür.
  (Bu eşitlik, §8.1'deki **saniye bazlı** toplama ile birlikte geçerlidir; uç nokta farkıyla
  hesaplanırsa karar aralıkları içinde biten beklemeler kaybolur.)
- `γ < 1` kullanılması gerekirse, ayrık tik yapısı nedeniyle `γ^{Δt}` biçiminde (gerçek
  geçen süreye göre) uygulanmalıdır; aksi hâlde "bekleme" yapay olarak indirimlenir ve
  uzun beklemeler sistematik olarak küçümsenir.
- Karar anının iki mikro-adıma bölünmesi (§7.3) getiriyi değiştirmez: faz 0 adımının ödülü `0`,
  süresi `0`'dır; `γ = 1` altında bölüm getirisi yine toplam yolcu-bekleme süresinin negatifidir.
  `γ < 1` kullanılırsa faz 0 adımı için `Δt = 0`, yani indirim çarpanı `1` olmalıdır.

### 8.3 Ölçekleme (Reward Scaling)
`γ = 1` altında yoğun senaryolarda bölüm getirisi `−2000 … −5000` mertebesine çıkabilir.
PPO'nun değer ağı kaybının patlamaması için ödülü sabit bir katsayıyla ölçeklemek
(ör. `1 / N_max` veya `0.01`) gerekebilir. Ölçekleme, `γ = 1` olduğu için politika sırasını
**bozmaz**; yalnızca optimizasyon sayısal dengesini iyileştirir.

---

## 9. Stable-Baselines3 Uygulama Kısıtları

| Konu | Kısıt / Çözüm |
|---|---|
| Algoritma | `sb3_contrib.MaskablePPO` (aksiyon maskesi zorunlu) |
| Eylem uzayı | `MultiDiscrete` desteklenir; **`Box` eylemleri desteklenmez**. İkinci blok moda göre `[F + 1] × C` (NC-R) ya da `[3] × C` (C); modlar ayrı eğitilir |
| Gözlem uzayı | `Dict` desteklenir (`MultiInputPolicy`); `Tuple` **desteklenmez**; `Graph` desteklenmez |
| Maske tipi | Her adımda `np.int8` dizisi; her eylem bileşenine karşılık gelen ikili (0/1) maske |
| Karar anı yapısı | İki mikro-adım (faz 0 atama, faz 1 `CH` / öncelikli yön; faz 1 atlanmaz), aynı `MultiDiscrete`; maske faza göre `action_masks()` ile üretilir (§7.3). `SubprocVecEnv` kullanılacaksa `action_masks` ortam sınıfında tanımlı olmalıdır (`ActionMasker` sarmalayıcısı bu durumda kullanılamaz) |
| Negatif indeks | `X = -1` SB3 tarafından desteklenmez → 0-tabanlı pozitif etiketleme |
| Ortam doğrulama | `gymnasium.utils.env_checker.check_env(env)` geçilmeli |
| Motor ön koşulu | ESRA v3 deposunda [A5] yaması (K22): `Car.updateState` biniş bekleyen yolcuların hedeflerini kabin hedefi sayar. RL dağıtıcısı `preferredDirection` alanını ve karar anında boş araç sıfırlamasını ekler; `updateState` kapatılmaz (§5.2) |
| Zaman ilerletme | Eğitim ve toplu değerlendirme başsız **olay tabanlı** modda (K25, §3.5); adımlı modla eşdeğerlik testi geçmeden eğitime başlanmaz. `SubprocVecEnv` altında GUI yoktur, dolayısıyla olay tabanlı mod varsayılandır |

---

## 10. Tasarım Kararları (K Tablosu)

| Kod | Konu | Durum | Karar / Gerekçe |
|---|---|---|---|
| K1 | CH liveness & park | **Çözüldü (park ertelendi)** | Varışta transfer yoksa araç bekler; son iniş (sayaç `2`) ek karar üretir; işi olmayan araç durma katında (C: bulunduğu konumda) kalır. Park katı seçimi v4.0 (K21, §15) |
| K2 | Uçuş ortasında dönüş | **Çözüldü** | Fizik ihmal edilir; oyun düzeyi dinamik kabul |
| K3 | Ödül & indirimleme | **Çözüldü** | `r = −Σ Δt` (yolcu-saniye), `γ = 1` |
| K5 | Atama çalkantısı (churn) | **İzlemede** | Atama artık fiziksel rezervasyondur ve serbestçe yeniden yapılabilir; önceki/yeni atama ve değişen OD sayısı `info` üzerinden loglanacak; churn cezası daha sonra değerlendirilecek |
| K7 | Sayaç bitiş anı | **Netleşti** | Bekleme, sayaç `5`'e düşünce (kapı açıldı, binme başlıyor) biter |
| K8 | Biniş modeli | **Revize edildi** | Grup tamamı anında biner, ancak yalnızca o araca atanmış OD grupları biner; atanmamış kabin bekleyen grubu alamaz |
| K9 | Kuyruk kuyrukları / p95 | **Açık (metodolojik)** | Gözlemde özet; p95 değerlendirmede sağdan sansürsüz |
| K12 | Negatif indeks | **Çözüldü** | `-1` terk edildi; 0-tabanlı etiketleme |
| K13 | İkinci blok maskesinin atamaya bağımlılığı | **Çözüldü** | Karar anı aynı simülasyon anında iki mikro-adıma bölünür: faz 0 atama (ikinci blok işlemsiz), faz 1 ikinci blok (atama kilitli, maske **yeni** atamadan). Süresi ve ödülü sıfır adım `γ = 1` altında getiriyi değiştirmez; standart MaskablePPO yeterlidir. Faz 1 hiçbir karar anında atlanmaz (v3.1). Önceki atamaya göre maske ve genişletilmiş maske, canlılığı bozduğu için reddedildi (§7.3) |
| K14 | C vs NC-R model ayrımı | **Revize (v3.1)** | Tek politika mimarisi, ortak atama bloğu; ikinci blok moda özgü: NC-R `[F + 1] × C` hedef kat, C `[3] × C` öncelikli yön. Modlar ayrı eğitilir. Atama sırası K13 ile; C modunda yön, kabin doluyken kontrolörün, karar anında kabin boşken politikanın kararıdır (K20) |
| K15 | Gözlemde mevcut hedef | **İzlemede (NC-R)** | Yeni eylem `CH` ile kararlar arasında kullanılan mevcut hareket hedefi ayrılmalıdır; yalnızca `CH == konum` biti yeterli olmayabilir (§6.2, §11/7). C modunda hedef kavramı yoktur; soru yalnızca NC-R için açıktır |
| K16 | Karar anı tanımı | **Revize (son hâl)** | Yalnızca **iki** olay: yeni çağrı; sayaç `7`'den `2`'ye indi (kapı açıldı, iniş/biniş tamamlandı). Sayaç `7`'deki ayrı biniş-başlangıcı olayı kaldırıldı (§3.4) |
| K17 | Gözlemde atanmış araç kimliği | **Kısmen çözüldü** | Düzen K13 ile sabitlendi: `calls` bloğu `N × (4 + C)`, faz 1'de yeni atama one-hot'u. Açık kalan: faz 0 sütunlarının sıfır mı (O0 anlamı) yoksa önceki rezervasyon mu (O1 anlamı) olacağı; kalıcılık (churn cezası, kilit, `KEEP`) eklenirse O1 anlamı zorunlu (§6.1) |
| K18 | Gözlemde yön | **Çözüldü (v3.1)** | Yön gözleme konmaz. NC-R: her karar anında tam yeniden yazma, gerekmez. C: boş araç karar anında sıfırlanıp yönü yeniden seçildiğinden önceki yön geçişi etkilemez; dolu aracın yönü varış katı istatistiklerinden çıkar (biniş yönlü, §4.2). "Hedefte mi" biti C modunda `state == 0` olarak tanımlanır; satır uzunluğu (`5F + 2`) ve `D` iki modda aynıdır (§6.2) |
| K20 | Boş araç yön seçimi (C modu) | **Revize (v3.1, C anlambilimi)** | Faz 1'de kabini boş, DF'siz ve biniş bekleyen yolcusu olmayan her araç `state = 0`'a çekilir; yönünü politikanın 3 değerli öncelikli yön bileşeni seçer. Maske: dolu/biniş bekleyen/işsiz `{0}`; tek yanlı atama o yön; iki yanlı `{−1, +1}`, `0` kapalı. Hareket hâlindeki boş araç da yeniden yönlendirilir. `updateState` dolu araç ve karar anları arası için değişmez; yakınlık kuralı yalnızca emniyet ağı (§5.2). v3'teki `CH` tabanlı kat seçimi kaldırıldı |
| K21 | Park katı seçimi | **Ertelendi (v4.0)** | İşi olmayan araç durma katında / bulunduğu konumda kalır (ikinci blok tek seçeneğe maskeli). Park katına yönlendirme §15'te v4.0 teması olarak kayıtlıdır; motor ilkeli `parkFloor` (§15.2) |
| K22 | Motor ön koşulu: biniş penceresi yönü | **Uygulandı (PR #1, birleştirme bekliyor)** | Aşamalı biniş ([A4]) çağrıyı varışta siler, DF'yi 2 s sonra ekler; aradaki pencerede `updateState` aracın diğer çağrılarına bakarak yönü değiştiriyordu (yukarı yolcuyla aşağı iniş; aynı kattaki ters yönlü çağrının aynı duruşta alınması). [A5]: `updateState` `pendingBoard` yolcularının hedeflerini kabin hedefi sayar. `onertartan/elevator-simulator` `fix/pending-board-direction`, `tests/test_pending_board_direction.py`, `analysis/headless_benchmark.py`, RUNNING.md §10 |
| K23 | Yarım katta işsiz kalma | **Bilinen pürüz (kabul)** | Hareket hâlindeki boş aracın tüm çağrıları başka araca verilirse `state = 0` olur ve araç yarım katta durur (port davranışı; GA de üretebilir). C modunda yön `0`'a maskelenir, araç bir sonraki atamaya kadar orada kalır; simülasyon için zararsız. İsteğe bağlı motor eki: işsiz boş araç son yönünde bir sonraki tam kata kadar gider |
| K19 | Zaman normalizasyonu | **Çözüldü** | WT özellikleri `log(1 + WT) / log(1 + T_ref)`, `T_ref = 300` s; ölçek referansı olduğu için `Box` üst sınırı `1` değil, finite güvenli tavan olmalıdır (§6.1, §6.3) |
| K25 | Zaman ilerletme modu | **Karar (v3.2); uygulama bekliyor** | Motor sabit adımlıdır (`Ts = 1 s`); GUI aktifken adımlı mod referanstır. GUI aktif değilken olay tabanlı (*next-event*) ilerletme uygulanacak: olay takvimi (duruş katına varış, sayaç geçişleri, yolcu gelişi), kapalı biçimde konum ve ödül güncellemesi. Adımlı modla birebir özdeş yörünge zorunlu; `headless_benchmark.py --event-mode` ile 20 tohumda özdeşlik regresyon testi olarak bağlanır (§3.1, §3.5). Ortamın karar anları, gözlemi ve ödülü iki modda aynıdır |


---

## 11. Açık Sorular

1. **Ödül ölçeği:** `1 / N_max` mi, sabit `0.01` mi, yoksa ölçekleme yok mu? (Ampirik karar.)
2. ~~C modu yön vekili~~ **Çözüldü (K20 rev., K18):** kabin dolu araçta yön kontrolörün durumudur, maske için vekil gerekmez; karar anında kabini boş araç sıfırlanır ve yönü öncelikli yön bileşeni seçer (§5.2). Yön gözleme konmaz; "hedefte mi" biti C modunda `state == 0`.
3. ~~C modu öncelik kuralı~~ **Çözüldü:** kabin dolu araçta `CH` işlemsiz olduğundan öncelikli kabin hedefi ile atanmış kat çağrısı arasında `CH` düzeyinde çatışma yoktur; sıralamayı kolektif kural belirler (§5.2).
4. ~~Atama ve CH'nin aynı eylemde uygulanma sırası (K13)~~ **Çözüldü:** iki mikro-adımlı karar anı; CH maskesi faz 1'de yeni atamadan hesaplanır (§7.3). Numara, çapraz referanslar bozulmasın diye korunmuştur.
5. **Churn (K5):** Atama serbestçe yeniden yapılabildiği için aynı grubun ardışık karar anlarında farklı araçlara atanması fiziksel davranış olarak mümkündür. Önceki ve yeni atama vektörleri arasındaki değişim sayısı izlenecek mi, yoksa küçük bir churn cezası eklenecek mi? Cezanın fiziksel rezervasyon/WT hedefini bozmayacak ölçeği ampirik belirlenmelidir.
6. **Önceki atamanın faz 0 gözleminde tutulması (K17):** `calls` bloğunun düzeni K13 ile `N×(4+C)` olarak sabittir ve faz 1'de yeni atamayı gösterir. Açık soru, faz 0 sütunlarının içeriğidir:
   - O0 anlamı: faz 0'da sütunlar sıfır; politika atamayı yalnızca kuyruk özetlerinden ve araç durumlarından yapar.
   - O1 anlamı: faz 0'da sütunlar önceki karar anından kalan rezervasyonu gösterir.

   O1 anlamı Markovluk açısından daha güvenlidir ve önceki atama geçişi/ödülü etkiliyorsa (churn cezası, kilit, `KEEP`) zorunludur. O0 anlamı ancak yeni atama her karar anında faz 0'da tamamen yenileniyor ve önceki atama geçişte/ödülde kullanılmıyorsa seçilmelidir; bu durumda kısmi gözlemlilik oluşmadığı testlerle gösterilmelidir.
7. **Mevcut hedef ve hareket durumu (K15, yalnızca NC-R):** Eylemdeki yeni `CH` ile kararlar arasında simülatörün kullandığı mevcut hedef aynı kavram mı? Değilse mevcut hedef, yön veya eşdeğer hareket durumu gözleme eklenmelidir. Yalnızca `CH == konum` biti mevcut hedefin değerini temsil etmez. C modunda hedef yoktur ve yön her karar anında yeniden seçilir (K18 çözüldü).
8. **Değerlendirme (K9):** Bölüm sonunda hizmeti tamamlanmamış yolcular için ceza süresi nasıl tanımlanacak? (p95 WT'nin sağdan sansürlenmesini önlemek için.)
9. **Aynı katta birden fazla OD grubu:** Aynı araca birden fazla grup atanırsa hepsi aynı kapı çevriminde mi biner? Farklı araçlara atanırsa ilk açılan kapının diğer grupların bekleme ve atama durumuna etkisi tam olarak nedir?
10. ~~C modunda biniş yönü (§4.2 ile tutarlılık)~~ **Çözüldü (v3.1):** C modunda biniş yönlüdür (ESRA `beginPickup` kuralı, `isAtHC`'nin yön süzgeci); aynı kattaki ters yönlü atanmış grup aracın dönüşünü bekler ve bu bekleme ödüle yansır. Hangi grubun önce bineceğini faz 1 yön seçimi belirler (§4.2, §5.2). [A5] olmadan motor bu kuralı kapı açılma penceresinde ihlal ediyordu (K22).
11. **Emniyet ağı sayacı (C modu):** `updateState`'in politika seçimini düzelttiği (işi olmayan tarafa yön) karar anlarının sayısı `info` ile izlenmeli; sıfırdan farklıysa maske hatası var demektir. Ölçüm, değerlendirme protokolüne eklenmeli.


---

## 12. Değerlendirme Metodolojisi Notları

- **p95 bekleme süresi:** Test senaryoları bittiğinde sistemde hâlâ bekleyen yolcular varsa
  (sağdan sansürleme), p95 metriği **yapay olarak düşük** çıkar. Bölüm bitişinde
  tamamlanmamış yolcular için bir ceza süresi ekleme kuralı dokümante edilmelidir.
- **Karşılaştırma tabanı:** GA kontrolörü ile aynı trafik senaryolarında (`scenario_generation.py` çıktıları) karşılaştırma yapılmalı. GA ve RL için fiziksel atama/rezervasyon, biniş ve terminal kuralları birebir aynı olmalıdır.
- **Atama görünürlüğü:** O0/O1 gözlem seçimi, aynı trafik senaryolarında atama gözlemli ve atama gözlemsiz politikaların Markovluk, öğrenme hızı ve performans açısından karşılaştırılmasıyla doğrulanmalıdır.
- **Determinizm:** Simülasyon deterministik olduğu için tohum (seed) sabitlemesi ve tekrarlanabilirlik doğrudan sağlanabilir.
- **Zaman ilerletme eşdeğerliği (K25):** Adımlı ve olay tabanlı modlar aynı örnekte özdeş iz üretmelidir; eğitim ve değerlendirme olay tabanlı modda yapılsa da raporlanan her sonuç adımlı modda (GUI ile) yeniden üretilebilir olmalıdır.

---

## 13. Devir İstemleri (başka bir LLM'e yapıştırılacak promptlar)

### 13.1 Tam devir — tüm doküman

```
Aşağıda ESRA 3.0 adlı bir asansör grup kontrol simülatörü üzerine kurulacak
pekiştirmeli öğrenme (RL) ortamının tasarım sözleşmesi verilmiştir. Tasarımı
eleştirel biçimde incele: (1) gözlem/eylem/ödül tanımlarında tutarsızlık veya
eksik bilgi var mı? (2) SMDP formülasyonu ve maske mantığı matematiksel olarak
tutarlı mı? (3) stable-baselines3 (MaskablePPO) ile uygulanabilirlik açısından
riskli noktalar neler? (4) akademik literatür (ör. Ruokokoski 2015, Torres &
Bierlaire 2023) ile karşılaştırıldığında bu formülasyonun eksikleri neler?
Yanıtını madde madde ve gerekçeli ver; kod önerisi istersen ayrıca belirt.

[Doküman buradan itibaren yapıştırılır.]
```

### 13.2 Kısmi devir — yalnızca §6 (Gözlem) ve §7 (Eylem)

**Paket:** `esra-3-rl-kesit-6-7.md`. Bu dosya, bu dokümandan üretilmiş **bağımsız bir
kesittir**: başlık + görev tanımı + §6.0 bağlam kapsülü + §6 + §7. Kapsül, kesitin
dışında kalan tanımları (sabitler, sayaç, karar anları, `CH`, modlar, birleşik fiziksel
rezervasyon durumu, ödül, SB3 kısıtları) özetlediği için alıcı model ek bağlam olmadan
çalışabilir. Dosyayı
olduğu gibi yükleyip aşağıdaki istemi yapıştırmak yeterlidir. (Paket, K13 revizyonundan sonra bu
dokümandan yeniden üretilmelidir.)

```
Aşağıdaki kesit, bir asansör grup kontrol simülatörü (ESRA 3.0) üzerine kurulacak
pekiştirmeli öğrenme ortamının YALNIZCA gözlem uzayı (§6) ve eylem uzayı (§7)
bölümlerini içerir. Başındaki "Bağlam Kapsülü" bölümü, kesitin dışında kalan
tanımları özetler; önce onu oku.

Yalnızca bu iki bölüme odaklanarak eleştirel incele:

(1) BOYUT VE TUTARLILIK: §6.1–§6.4'teki gözlem boyutu formülü
    D = N·(4+C) + C·(5F + 2) + 5, blok tanımlarıyla (atama one-hot'u, faz biti)
    birebir tutarlı mı? Herhangi bir bileşen tanımsız, yinelenen veya eksik mi?
    Boyut tablosundaki sayıları yeniden hesaplayıp doğrula.
(2) GÖZLEM TASARIMI: Özellik seçimleri (konum one-hot, CH == konum biti, sayaç,
    kabin içi hedefler, WT istatistikleri) yeterli mi? Ödülle ilişkili hangi durum
    bilgisi eksik? "Saf durum ilkesi" (§6.6) tutarlı biçimde uygulanmış mı, yoksa
    gözlemde başka eylem sızıntısı kalmış mı?
(3) NORMALİZASYON: §6.5'teki log(1+WT)/log(1+T_ref) sıkıştırması ve T_ref/T_ufuk
    ayrımı doğru mu? Box üst sınırları için önerin ne olur?
(4) EYLEM UZAYI: MultiDiscrete yapısı (§7.1; ikinci blok NC-R'de hedef kat, C'de
    3 değerli öncelikli yön) ve iki fazlı maske mantığı (§7.2–§7.3) sağlam mı? Faz 0 / faz 1 bölünmesi γ = 1 altında getiriyi gerçekten değiştirmiyor
    mu? Faz 1 maskesi, gözlemdeki yeni atamadan birebir yeniden üretilebiliyor mu?
    Canlılık (kilitlenmeme) argümanında boşluk var mı?
(5) SB3 UYGULANABİLİRLİĞİ: MaskablePPO + MultiDiscrete + Dict gözlem ile bu tasarım
    doğrudan uygulanabilir mi? Maskenin her adımda np.int8 olarak üretilmesi ve
    mask(o_t) bağımlılığı açısından riskli noktalar neler?
(6) §6.6'daki istisnayı değerlendir: "CH == konum" biti gerçekten türev değişken
    değil mi, yoksa saf durum ilkesinin ihlali mi?

Yanıtını madde madde, gerekçeli ve doğrudan bu kesitteki ifadelere atıf yaparak ver.
Kod önerisi istersen ayrıca belirt. Kesitin dışındaki bölümler (ödül, karar anları,
simülasyon modeli) hakkında varsayımda bulunman gerekirse bunu açıkça belirt.

[Kesit buradan itibaren yapıştırılır.]
```

---

## 14. Sözlük (TR → EN)

| TR | EN |
|---|---|
| Varış yeri kontrolü | Destination control / destination dispatch |
| Grup kontrol | Group control |
| Karar anı | Decision epoch |
| Sayaç | Counter |
| Konum | Position |
| Yön | Direction |
| Hedefte mi | At-target flag |
| Çağrı | Call |
| Kabin çağrısı | Car call |
| Kat çağrısı | Landing / hall call |
| Hedef kat | Target floor |
| Park katı | Parking floor |
| Durma katı | Hold floor |
| Öncelikli yön | Prioritized / preferred direction |
| Biniş penceresi | Pre-boarding window (door opening before boarding) |
| Yolcu-saniye | Passenger-second |
| Bekleme süresi | Waiting time (WT) |
| Seyahat süresi | Travel time (TT) |
| Atama çalkantısı | Assignment churn |
| Maske | Action mask |
| Karar fazı / mikro-adım | Decision phase / micro-step |
| Sabit adımlı zaman ilerletme (adımlı mod) | Fixed-increment (time-stepped) time advance |
| Olay tabanlı zaman ilerletme | Next-event time advance |
| Etkinlik taraması | Activity scanning |
| Başsız mod | Headless mode (no GUI) |

---

## 15. Ertelenen temalar (v4.0)

### 15.1 Boş araç için park katı seçimi (K21)

**Bu sürümdeki durum.** İşi olmayan araç (kabin boş, atanmış grup yok) durma katında kalır; `CH`
tek seçeneğe maskelidir (§5.1–§5.3). Politika park kararı vermez.

**v4.0 teması.** `CH`'nin, işi olmayan boş aracı bir park katına yönlendirmek için kullanılması:
`K_olay(c) = ∅` olan araç için maske `{1 … F}` tamamına açılır; araç seçilen kata gider ve orada
bekler. İlk tasarımın "park katı serbestisi" kuralı budur.

**O zaman karara bağlanacaklar:**

- Park hareketi karar anı üretmez (§3.4); park yolculuğu sırasında gelen çağrı yeni karar anı
  doğurur. Canlılık etkilenmez: maskenin açılması yalnızca işi olmayan araçlar içindir.
- Park yolculuğu ödülde görünmez (bekleyen yolcu yok); politika park değerini yalnızca sonraki
  çağrıların beklemesi üzerinden öğrenir. Bu zayıf ve gecikmeli bir sinyaldir; hareket/enerji
  maliyeti terimi (kat başına küçük ceza) eklenip eklenmeyeceği.
- Keşif maliyeti: tüm katların açılması öğrenme bütçesini büyütür; başlangıçta `{bulunduğu kat,
  lobi}` gibi dar bir küme ile başlanıp genişletilmesi.
- Trafik örüntüsüne bağlı park (sabah lobi, öğle ara katlar) için gözleme zaman-of-day veya yakın
  geçmiş varış yoğunluğu özelliği gerekip gerekmediği.
- Karşılaştırma tabanı: ESRA'nın park seçenekleri (`parkAlgorithm`, `parkFloor`) ve klasik
  bölgeleme (zoning) kuralları.
- `CH == konum` bitinin (§6.2) park hedefiyle ilişkisi: park yolundaki araç için bit 0 olur;
  mevcut hedefin gözleme girmesi (K15) bu temayla birlikte yeniden değerlendirilir.

### 15.2 Uygulama notu: işsiz araç hareketi için motor ilkeli

- C modunda öncelikli yön, işi olmayan araç için **açılmamalıdır**: çıplak bir yönün durma kuralı
  yoktur ve `Car.move` bina sınırı bilmez (`floor += state · v · Ts`, kırpma yok). Zaten
  `updateState` çağrısız araçta `±1`'i hemen `0`'a çevirir, araç kımıldamaz; yön eylemi bu iş
  için yanlış ilkeldir.
- Motorun hazır mekanizması `parkFloor`: `Controller.operate`'in (b) dalı, `state == 0` ve
  `floor != parkFloor` iken aracı her tik yarım kat hedefe yürütür, `state`'e dokunmaz, varınca durur.
  Yolda çağrı atanırsa `updateState` yönü `±1` yapar ve (c) dalı devreye girer; park kendiliğinden
  iptal olur. GUI'deki "Park2" seçeneği aynı mekanizmadır (`parkFloor = 1`).
- v4.0'da park/konumlandırma eylemi bu yüzden **hedef kat** olarak tasarlanmalı ve `car.parkFloor`'a
  yazılmalıdır; NC-R'nin `CH`'si de işsiz araç için aynı alana düşebilir.
- `Experiment._simulationActive` park hareketini etkin iş saymaz (`stopOverCounter`, `DF`, `state`,
  bekleyenler, süre). Dinamik trafikte sorun yok; statik anlık görüntüde son yolcu inince döngü,
  park yolundaki araç varmadan bitebilir. `parkFloor` kullanılacaksa koşula bir terim eklenmeli.

---

*Bu doküman, tasarım sözleşmesinin tek dosyalık özetidir. Kod okumadan anlaşılabilmesi
hedeflenmiştir; simülatörün iç ayrıntıları (ör. trafik üretimi) yalnızca RL için gereken
ölçüde betimlenmiştir.*
