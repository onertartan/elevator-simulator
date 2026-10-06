GA parameter-search results - ESRA elevator simulator
=======================================================
Source: sonuclarGA.mat (MATLAB), variable `fitnesses`
(6 x 5 x 3 x 3 x 5 x 10 double). Exported without `Pawt` (excluded on
purpose) and `dataConf` (opaque MATLAB class object).

Experiment: full-factorial sweep of GA operator/parameter settings for
elevator group dispatching (one car label per waiting hall call,
integer encoding). Every configuration was run 10 times; each value is
that run's best objective = estimated mean passenger waiting time in
seconds. LOWER IS BETTER.

fitnesses_long.csv - one row per GA run (13,500 rows):
    Pc            crossover fraction        {0.3, 0.4, 0.5, 0.6, 0.7, 0.8}
    Pm            mutation rate             {0.01, 0.02, 0.05, 0.1, 0.2}
    selection     selection function        {stochunif, roulette, tournament}
    crossover_fn  crossover function        {scattered, singlepoint, twopoint}
    mutation_fn   mutation operator         {uniform, block, scramble, swap,
                                             frequency}
    run           run index                 1..10 (independent RNG streams)
    best_cost_s   best cost of the run      seconds, lower is better

mean_fitnesses_long.csv - one row per configuration (1,350 rows):
    same factor columns, plus
    mean_cost_s   mean of best_cost_s over the 10 runs
    (matches the MATLAB variable `mean_fitnesses`)
