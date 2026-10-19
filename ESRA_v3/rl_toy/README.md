# Oyuncak simülatör — tasarım belgesindeki kuralların sınanması (paket v2, 2026-10-19)

ESRA değildir. Tasarım belgesindeki kuralları (sayaç 7→0, sayaç 5'te transfer, sayaç 2'de ve yeni
çağrıda karar anı, yalnızca atanmış grupların binmesi, NC-R maskesi, uçuş ortasında dönüş, kapasitesiz
kabin) uygular. Sonuçları tasarım belgesi v3.1 §7.3'te (kilitlenme sayıları) ve
`claude/RL_ortami_tasarim_degerlendirmesi.md`'de anılır. C anlambilimi (v3.1 K20) bu toy'da **yoktur**;
toy yalnızca NC-R kurallarını ve iki fazlı maske mantığını sınar.

- `toy_env.py`     simülatör. `mask_mode` = "new" (tutarlı, iki fazlı), "old" (önceki atamaya göre),
                   "expanded" (tüm bekleyen grupların katları), "none"; `heartbeat=True` kilitlenen
                   sistemde her tik karar anı açar (kalp atışı)
- `policies.py`    rastgele (her şeyi yeniden seç / taahhütleri koru) ve üç sezgisel kural
- `toy_gym.py`     Gymnasium sarmalayıcı: iki fazlı maske (faz 0 atama, faz 1 CH), faz biti, stok
                   MaskablePPO ile çalışır; `show_prev_assign` (O1/O0), `ch_mask`, `heartbeat`
- `train_ppo.py`   eğitim + 40 sabit tohumda değerlendirme:
                   `python train_ppo.py <etiket> <w_kabin> <adım> <F> <C> <lambda> [o0,nomask,expanded,hb]`
- `exp1_deadlock.py`, `exp2_random.py`, `exp3_incentive.py`  kilitlenme / rastgele politika / ödül teşviki tabloları
- `ppo_*.json`     eğitimlerin öğrenme eğrileri ve aynı tohumlardaki sezgisel sonuçlar
                   (wt_only / wt_plus_ride, light / heavy, o0, expanded_hb)
- `logs/`          eğitim koşularının konsol çıktıları (nomask_hb koşuları kontrol noktasına ulaşamadı)

Bulgular (özet): tutarlı maske 0/200 kilitlenme, önceki atama 122/200, genişletilmiş 8/200, maskesiz
200/200; kalp atışıyla hepsi 0 ama donma örtülür. Yalnız bekleme ödülü yanlış yönde taşımaya yol açar
(heavy: WT 6,9 / JT 54 s; kabin terimiyle WT 11,4 / JT 27,9). O0 vs O1 faz-0 gözlemi: light 4,47 / 4,34,
heavy 8,07 / 7,19. Her kararda her şeyi yeniden seçmek vs taahhütleri korumak (C=8): 18,7 / 10,4 s.

Gereksinimler: numpy, gymnasium, stable-baselines3, sb3-contrib, torch.
