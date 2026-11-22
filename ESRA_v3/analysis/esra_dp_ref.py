# -*- coding: utf-8 -*-
"""ESRA kesin çözüm yöntemi: başvuru uygulaması (sürüm 3, 18.11.2026).

Sadeleştirilmiş fizik (ESRA kodu değildir): araç tam katta ve kapıları kapalı başlar;
kat başına 2 s, duruş 7 s; iniş ve biniş varış anında (kapı açılmaya başlarken) sayılır.

  car    = (kat, kabin),  kabin = ((hedef, yolcu), ...)
  groups = ((biniş katı, hedef katı, yolcu), ...)
  Grup hâli: 0 bekliyor, 1 kabinde, 2 indi (ya da bu araca verilmedi).
  Kipler: CC, PR, PRR ve PRS (PR + seçmeli biniş; yalnızca alt sınır hesabı için).
"""
import heapq
import itertools
import random
from functools import lru_cache

T_FLOOR, T_STOP = 2, 7
INF = float('inf')


def sgn(x):
    return (x > 0) - (x < 0)


# ----------------------------------------------------------------------------- kurallar
def stop_effect(car, groups, mode, gs, os, x, d):
    """x katında duruş: hedefi x olanlar iner; binebilecek (bekleyen, yönü uygun) gruplar döner."""
    cabin = car[1]
    G, K = range(len(groups)), range(len(cabin))
    g1 = tuple(2 if gs[i] == 1 and groups[i][1] == x else gs[i] for i in G)
    o1 = tuple(1 if os[k] == 0 and cabin[k][0] == x else os[k] for k in K)
    here = [i for i in G if gs[i] == 0 and groups[i][0] == x]
    if mode != 'PRR':                                    # yönlü biniş (CC, PR, PRS)
        rest = [groups[i][1] for i in G if g1[i] == 1] + [cabin[k][0] for k in K if o1[k] == 0]
        de = sgn(rest[0] - x) if rest else d             # hizmet yönü: kabinde kalanların yönü; kabin boşsa d
        here = [i for i in here if sgn(groups[i][1] - x) == de]
    return g1, o1, here, (g1, o1) != (gs, os)


def options(car, groups, mode, gs, os, f):
    """İzinli sonraki duruşlar: (kat, hizmet yönü, binenler, yeni gs, yeni os) listesi."""
    cabin = car[1]
    G, K = range(len(groups)), range(len(cabin))
    gdir = lambda i: sgn(groups[i][1] - groups[i][0])
    dests = [groups[i][1] for i in G if gs[i] == 1] + [cabin[k][0] for k in K if os[k] == 0]
    wait = [i for i in G if gs[i] == 0]
    if mode == 'PRR':                                    # her kabin hedefi, her bekleyen grubun katı
        cand = [(x, 0) for x in sorted(set(dests) | {groups[i][0] for i in wait})]
    elif dests:                                          # kabin dolu: yolcuların yönünde, en yakın hedefe kadar
        d = sgn(dests[0] - f)
        near = min(dests, key=lambda y: abs(y - f))
        stops = {near} | {groups[i][0] for i in wait if gdir(i) == d
                          and sgn(groups[i][0] - f) in (0, d) and abs(groups[i][0] - f) <= abs(near - f)}
        stops = sorted(stops, key=lambda y: abs(y - f))
        cand = []
        for y in (stops[:1] if mode == 'CC' else stops):  # CC: yalnızca en yakını
            if any(z != y for z in dests):               # kabinde yolcu kalır: hizmet yönü değişmez
                cand.append((y, d))
            elif mode == 'CC':                           # kabin boşalır, toplamalı: yönünde iş varsa sürdürür, yoksa döner
                ahead = any((gdir(i) == d and sgn(groups[i][0] - y) in (0, d))
                            or (gdir(i) == -d and sgn(groups[i][0] - y) == d) for i in wait)
                cand.append((y, d if ahead else -d))
            else:                                        # kabin boşalır, PR / PRS: hizmet yönü o duruşta seçilir
                cand += [(y, 1), (y, -1)]
    elif mode == 'CC':                                   # kabin boş, toplamalı: yön seçilir, gerisi kural
        cand = []
        for d in (1, -1):
            same = [groups[i][0] for i in wait if gdir(i) == d and sgn(groups[i][0] - f) in (0, d)]
            opp = [groups[i][0] for i in wait if gdir(i) == -d and sgn(groups[i][0] - f) == d]
            if same:                                     # yönünde, aynı yöne gidecek en yakın grup
                cand.append((min(same, key=lambda y: abs(y - f)), d))
            elif opp:                                    # yoksa ters yöne gidecek en uzak grup; orada döner
                cand.append((max(opp, key=lambda y: abs(y - f)), -d))
    else:                                                # kabin boş, PR / PRS: bekleyen herhangi bir grup
        cand = sorted({(groups[i][0], gdir(i)) for i in wait})
    out = []
    for x, d in cand:
        g1, o1, here, alighted = stop_effect(car, groups, mode, gs, os, x, d)
        if mode == 'PRS':                                # seçmeli biniş: uygun grupların her altkümesi
            sets = [B for r in range(len(here) + 1) for B in itertools.combinations(here, r) if B or alighted]
        else:                                            # zorunlu biniş: uygun grupların tümü
            sets = [tuple(here)] if (here or alighted) else []
        for B in sets:
            out.append((x, d, B, tuple(1 if i in B else g1[i] for i in G), o1))
    return out


# ----------------------------------------------------------------------------- iç katman
def rates(car, groups, gs, os):
    nW = sum(g[2] for g, s in zip(groups, gs) if s == 0)
    nT = sum(g[2] for g, s in zip(groups, gs) if s == 1) + sum(c[1] for c, s in zip(car[1], os) if s == 0)
    return nW, nW + nT                                   # (bekleme oranı, yolculuk oranı)


def car_table(car, groups, mode, a):
    """V(gs, os, kat) -> ((birincil, ikincil), plan).  a = 0: birincil WT;  a = 1: birincil TT."""
    @lru_cache(maxsize=None)
    def V(gs, os, f):
        best = None
        for x, d, B, g2, o2 in options(car, groups, mode, gs, os, f):
            r1, r2 = rates(car, groups, gs, os), rates(car, groups, g2, o2)
            dt = T_FLOOR * abs(x - f)
            step = (r1[a] * dt + r2[a] * T_STOP, r1[1 - a] * dt + r2[1 - a] * T_STOP)
            sub, plan = V(g2, o2, x)
            tot = (step[0] + sub[0], step[1] + sub[1])
            if best is None or tot < best[0]:
                best = (tot, ((x, B),) + plan)
        if best is None:                                 # seçenek yoksa herkes inmiş olmalı
            assert all(s == 2 for s in gs) and all(s == 1 for s in os)
            return (0, 0), ()
        return best
    return V


def start(car, groups, S):
    return tuple(0 if i in S else 2 for i in range(len(groups))), (0,) * len(car[1]), car[0]


def account(car, groups, plan):
    """Bir planın (WT, TT) değeri: her yolcunun biniş ve iniş anından, oran kullanmadan."""
    t, f, wt, tt = 0, car[0], 0, 0
    on = {('k', k): c for k, c in enumerate(car[1])}     # kabindekiler: anahtar -> (hedef, yolcu)
    for x, B in plan:
        t += T_FLOOR * abs(x - f)
        f = x
        for key in [key for key, (dest, n) in on.items() if dest == x]:
            tt += on.pop(key)[1] * t
        for i in B:
            assert groups[i][0] == x
            wt += groups[i][2] * t
            on[('g', i)] = (groups[i][1], groups[i][2])
        t += T_STOP
    assert not on
    return wt, tt


def all_plans(car, groups, S, mode):
    """Bütün izinli duruş sıraları, bellek kullanmadan tek tek."""
    def rec(gs, os, f, plan):
        opts = options(car, groups, mode, gs, os, f)
        if not opts:
            yield plan
        for x, d, B, g2, o2 in opts:
            yield from rec(g2, o2, x, plan + ((x, B),))
    yield from rec(*start(car, groups, S), ())


def brute_car(car, groups, S, mode, a):
    vals = [account(car, groups, p) for p in all_plans(car, groups, S, mode)]
    return min((v[a], v[1 - a]) for v in vals)


# ----------------------------------------------------------------------------- dış katman
def tables(cars, groups, mode, a):
    """tab[j][S] = c_j(S): araç başına tek tablodan bütün altkümeler."""
    N, tab = len(groups), []
    for car in cars:
        V = car_table(car, groups, mode, a)
        tab.append([V(*start(car, groups, {i for i in range(N) if S >> i & 1}))[0] for S in range(1 << N)])
    return tab


def outer(tab, N):
    """D(j, M) = min_{S alt M} [D(j-1, M \\ S) + c_j(S)].  Dönen: (değer çifti, atama)."""
    D = [(INF, INF)] * (1 << N)
    D[0] = (0, 0)
    picks = []
    for row in tab:
        D2, ch = [(INF, INF)] * (1 << N), [0] * (1 << N)
        for M in range(1 << N):
            S = M
            while True:
                v = (D[M ^ S][0] + row[S][0], D[M ^ S][1] + row[S][1])
                if v < D2[M]:
                    D2[M], ch[M] = v, S
                if S == 0:
                    break
                S = (S - 1) & M
        D = D2
        picks.append(ch)
    M, asg = (1 << N) - 1, [None] * N
    for j in range(len(tab) - 1, -1, -1):
        for i in range(N):
            if picks[j][M] >> i & 1:
                asg[i] = j
        M ^= picks[j][M]
    return D[(1 << N) - 1], asg


def brute_outer(tab, N):
    best = (INF, INF)
    for asg in itertools.product(range(len(tab)), repeat=N):
        v = (0, 0)
        for j, row in enumerate(tab):
            c = row[sum(1 << i for i in range(N) if asg[i] == j)]
            v = (v[0] + c[0], v[1] + c[1])
        best = min(best, v)
    return best


def fixed_opt(cars, groups, mode, a):
    return outer(tables(cars, groups, mode, a), len(groups))[0][0]


# ----------------------------------------------------------------------------- yeniden atama
def joint_opt(cars, groups, mode, a):
    """Yeniden atamalı politikaların en iyisi (Dijkstra; yalnızca zorunlu binişli PR ve PRR).
    Karar anları: başlangıç, her duruşun bitişi ve kimsenin inip binmediği her varış. Her karar anında
    bekleyen bütün gruplar yeniden atanabilir; boştaki her araca yeni duruş verilir ya da araç bekler.
    Yoldaki aracın hedefi değişmez. Kabindeki grup: hâl 10 + araç numarası."""
    C, N = len(cars), len(groups)
    G = range(N)

    def view(gs, asg, c):                                # c aracının gördüğü hâller
        return tuple(1 if gs[i] == 10 + c else 0 if gs[i] == 0 and asg[i] == c else 2 for i in G)

    def rate(gs, os):
        nW = sum(groups[i][2] for i in G if gs[i] == 0)
        nT = sum(groups[i][2] for i in G if gs[i] >= 10)
        nT += sum(n for c in range(C) for (dest, n), s in zip(cars[c][1], os[c]) if s == 0)
        return nW + a * nT

    def finished(gs, os):
        return all(s == 2 for s in gs) and all(s == 1 for o in os for s in o)

    def run(gs, os, cs, asg):                            # bir sonraki karar anına kadar ilerle
        gs, os, cs, cost = list(gs), list(os), list(cs), 0
        while True:
            epoch = False
            for c in range(C):
                if cs[c][0] == 'T' and cs[c][3] == 0:    # varış
                    x, d = cs[c][1], cs[c][2]
                    gv = view(gs, asg, c)
                    g1, o1, here, alighted = stop_effect(cars[c], groups, mode, gv, os[c], x, d)
                    for i in G:
                        if gv[i] == 1 and g1[i] == 2:
                            gs[i] = 2
                    for i in here:
                        gs[i] = 10 + c
                    os[c] = o1
                    if here or alighted:
                        cs[c] = ('S', x, T_STOP)
                    else:                                # kimse inmedi, binmedi: hemen karar anı
                        cs[c] = ('I', x)
                        epoch = True
                elif cs[c][0] == 'S' and cs[c][2] == 0:  # duruş bitti
                    cs[c] = ('I', cs[c][1])
                    epoch = True
            if epoch or finished(gs, os):
                return cost, (tuple(gs), tuple(os), tuple(cs))
            left = [s[-1] for s in cs if s[0] != 'I']
            if not left:
                return None                              # iş var ama hareket eden yok
            dt = min(left)
            cost += rate(gs, os) * dt
            cs = [s if s[0] == 'I' else s[:-1] + (s[-1] - dt,) for s in cs]

    def decisions(gs, os, cs):
        W = [i for i in G if gs[i] == 0]
        idle = [c for c in range(C) if cs[c][0] == 'I']
        for combo in itertools.product(range(C), repeat=len(W)):
            asg = [0] * N
            for i, c in zip(W, combo):
                asg[i] = c
            asg = tuple(asg)
            per_car = []
            for c in idle:
                mv = {(o[0], o[1]) for o in options(cars[c], groups, mode, view(gs, asg, c), os[c], cs[c][1])}
                per_car.append([None] + sorted(mv))
            for moves in itertools.product(*per_car):
                cs2 = list(cs)
                for c, mv in zip(idle, moves):
                    if mv:
                        cs2[c] = ('T', mv[0], mv[1], T_FLOOR * abs(mv[0] - cs[c][1]))
                yield asg, tuple(cs2)

    st0 = (tuple([0] * N), tuple((0,) * len(c[1]) for c in cars), tuple(('I', c[0]) for c in cars))
    best, pq, tick = {st0: 0}, [(0, 0, st0)], 0
    while pq:
        cst, _, st = heapq.heappop(pq)
        if cst > best[st]:
            continue
        if finished(st[0], st[1]):
            return cst
        for asg, cs2 in decisions(*st):
            res = run(st[0], st[1], cs2, asg)
            if res is not None and cst + res[0] < best.get(res[1], INF):
                best[res[1]] = cst + res[0]
                tick += 1
                heapq.heappush(pq, (cst + res[0], tick, res[1]))
    return INF


# ----------------------------------------------------------------------------- sınamalar
def random_instance(rnd, F, C, N, cabin_prob):
    cars = []
    for _ in range(C):
        f, cabin = rnd.randint(1, F), ()
        if rnd.random() < cabin_prob:
            d = rnd.choice([-1, 1])
            side = [x for x in range(1, F + 1) if sgn(x - f) == d]
            if side:
                cabin = tuple((x, rnd.randint(1, 2)) for x in rnd.sample(side, min(len(side), rnd.randint(1, 2))))
        cars.append((f, cabin))
    groups = []
    for _ in range(N):
        o = rnd.randint(1, F)
        groups.append((o, rnd.choice([x for x in range(1, F + 1) if x != o]), rnd.randint(1, 3)))
    return tuple(cars), tuple(groups)


def gap_instance(rnd, F=40):
    """Yönlendirilmiş örnek: A altta ve kabini dolu, B çok uzakta; aynı kattan aynı yöne giden
    uzun yolculuklu kalabalık bir grup ile kısa yolculuklu tek kişilik bir grup."""
    fa, far = rnd.randint(1, 3), rnd.randint(9, 14)
    cars = ((fa, ((far, rnd.randint(1, 2)),)), (rnd.randint(F - 8, F), ()))
    o = rnd.randint(fa + 1, fa + 3)
    groups = [(o, rnd.randint(far - 1, far + 2), rnd.randint(3, 8)), (o, rnd.randint(o + 1, o + 3), 1)]
    if rnd.random() < 0.4:
        o2 = rnd.randint(1, 15)
        groups.append((o2, rnd.choice([x for x in range(1, 16) if x != o2]), rnd.randint(1, 2)))
    return cars, tuple(groups)


def compare_with_search(instances):
    stat = {'deneme': 0, 'PRR: sabit != yeniden atamalı': 0, 'PR: yeniden atamalı < sabit': 0,
            'PR: yeniden atamalı > sabit': 0, 'PR: yeniden atamalı < PRS': 0, 'PR: yeniden atamalı > PRS': 0}
    for cars, groups in instances:
        for a in (0, 1):
            stat['deneme'] += 1
            stat['PRR: sabit != yeniden atamalı'] += joint_opt(cars, groups, 'PRR', a) != fixed_opt(cars, groups, 'PRR', a)
            j, fx, lb = joint_opt(cars, groups, 'PR', a), fixed_opt(cars, groups, 'PR', a), fixed_opt(cars, groups, 'PRS', a)
            stat['PR: yeniden atamalı < sabit'] += j < fx
            stat['PR: yeniden atamalı > sabit'] += j > fx
            stat['PR: yeniden atamalı < PRS'] += j < lb
            stat['PR: yeniden atamalı > PRS'] += j > lb
    for k, v in stat.items():
        print(f'    {k}: {v}', flush=True)


def main():
    import sys
    print('Python', sys.version.split()[0])
    NAME = {0: 'WT', 1: 'TT'}
    print('[0] Dış katman, metindeki küçük örnek (2 araç, 3 grup)')
    c1, c2 = [0, 10, 14, 20, 30, 45, 40, 60], [5, 28, 18, 40, 14, 38, 26, 50]     # indis: bit 0 = grup 1
    val, asg = outer([[(v, 0) for v in c1], [(v, 0) for v in c2]], 3)
    print(f'    optimum {val[0]}, atama (grup -> araç) {[j + 1 for j in asg]}')

    print('[1] Sayısal örnek: boş araç 3. katta; g1 4->6 (1 yolcu), g2 2->1 (2 yolcu)')
    car, groups = (3, ()), ((4, 6, 1), (2, 1, 2))
    for mode in ('CC', 'PR', 'PRR'):
        for a in (0, 1):
            (v, w), plan = car_table(car, groups, mode, a)(*start(car, groups, {0, 1}))
            print(f'    {mode:3s} en iyi {NAME[a]} = {v:3d} (diğer amaç {w:3d}), duruşlar {[x for x, B in plan]}')
    print('    duruşlar [4, 6, 2, 1] için (WT, TT) =', account(car, groups, ((4, (0,)), (6, ()), (2, (1,)), (1, ()))))
    print('    duruşlar [2, 4, 6, 1] için (WT, TT) =', account(car, groups, ((2, (1,)), (4, (0,)), (6, ()), (1, ()))))

    rnd = random.Random(2026)
    print('[2] İç katman = bütün duruş sıralarının denenmesi + yolcu başına sayım (sıralı çift)')
    n = bad = 0
    for _ in range(300):
        (car,), groups = random_instance(rnd, 6, 1, rnd.randint(1, 4), 0.5)
        S = set(range(len(groups)))
        for mode in ('CC', 'PR', 'PRS', 'PRR'):
            for a in (0, 1):
                v, plan = car_table(car, groups, mode, a)(*start(car, groups, S))
                acc = account(car, groups, plan)
                n += 1
                bad += (v != brute_car(car, groups, S, mode, a)) or (v != (acc[a], acc[1 - a]))
    print(f'    deneme {n}, uyuşmazlık {bad}')

    print('[3] Sıra: CC >= PR >= PRS >= PRR (araç başına, her altküme, iki amaç)')
    n = bad = 0
    for _ in range(300):
        (car,), groups = random_instance(rnd, 6, 1, rnd.randint(1, 4), 0.5)
        for a in (0, 1):
            tab = {m: tables((car,), groups, m, a)[0] for m in ('CC', 'PR', 'PRS', 'PRR')}
            for S in range(1 << len(groups)):
                n += 1
                bad += not (tab['CC'][S][0] >= tab['PR'][S][0] >= tab['PRS'][S][0] >= tab['PRR'][S][0])
    print(f'    deneme {n}, ihlal {bad}')

    print('[4] Tek tablo = her altküme için ayrı çözüm')
    n = bad = 0
    for _ in range(150):
        (car,), groups = random_instance(rnd, 6, 1, rnd.randint(1, 4), 0.5)
        for mode in ('CC', 'PR', 'PRS', 'PRR'):
            for a in (0, 1):
                tab = tables((car,), groups, mode, a)[0]
                for S in range(1 << len(groups)):
                    sub = tuple(g for i, g in enumerate(groups) if S >> i & 1)
                    n += 1
                    bad += tab[S] != car_table(car, sub, mode, a)(*start(car, sub, set(range(len(sub)))))[0]
    print(f'    deneme {n}, uyuşmazlık {bad}')

    print('[5] Dış katman = bütün atamaların denenmesi (sıralı çift)')
    n = bad = 0
    for _ in range(100):
        cars, groups = random_instance(rnd, 6, rnd.randint(2, 3), rnd.randint(2, 5), 0.4)
        for mode in ('CC', 'PR', 'PRR'):
            for a in (0, 1):
                tab = tables(cars, groups, mode, a)
                n += 1
                bad += outer(tab, len(groups))[0] != brute_outer(tab, len(groups))
    print(f'    deneme {n}, uyuşmazlık {bad}')

    print('[6] Sabit atama ile yeniden atama (yolculuk süresi amacı, elle kurulmuş iki örnek)')
    cars, groups = ((1, ((6, 5),)), (30, ())), ((3, 4, 1),)
    moved = account(cars[0], groups, ((6, ()), (3, (0,)), (4, ())))[1]
    tab = tables(cars, groups, 'CC', 1)
    print(f'    CC örneği: g A\'da {tab[0][1][0] + tab[1][0][0]}, g B\'de {tab[0][0][0] + tab[1][1][0]}; '
          f'sabit atama en iyisi {fixed_opt(cars, groups, "CC", 1)}; '
          f'g önce B\'ye, A boşalınca A\'ya: {moved}; PR sabit en iyisi {fixed_opt(cars, groups, "PR", 1)}; '
          f'PRS (alt sınır) {fixed_opt(cars, groups, "PRS", 1)}')
    cars, groups = ((1, ((10, 1),)), (30, ())), ((3, 10, 6), (3, 5, 1))
    print(f'    PR örneği: sabit atama en iyisi {fixed_opt(cars, groups, "PR", 1)}; yeniden atamalı en iyi '
          f'{joint_opt(cars, groups, "PR", 1)}; PRS (alt sınır) {fixed_opt(cars, groups, "PRS", 1)}; '
          f'PRR sabit {fixed_opt(cars, groups, "PRR", 1)}, PRR yeniden atamalı {joint_opt(cars, groups, "PRR", 1)}')

    print('[7] Yeniden atamalı arama ile karşılaştırma: rastgele örnekler (birkaç dakika sürer)', flush=True)
    cases = [(F, 2, N) for F in (6, 10, 16) for N in (2, 3, 4)] * 8 + [(6, 3, N) for N in (2, 3)] * 6
    compare_with_search([random_instance(rnd, F, C, N, 0.5) for F, C, N in cases])

    print('[8] Yeniden atamalı arama ile karşılaştırma: yönlendirilmiş örnekler (40 kat, 2 araç)', flush=True)
    compare_with_search([gap_instance(rnd) for _ in range(150)])


if __name__ == '__main__':
    main()
