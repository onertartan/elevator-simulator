"""
decision/meta/mutate.py
========================
Port of matlab_src/mutate.m - the unified categorical-label mutation
used by the metaheuristic dispatchers (GA today; PSO/DE reuse it in
MATLAB as well).

Deviation notes (continuing the [P#] family):

  [P23] RNG: every rand/randi/randperm/randsample call takes the
       dispatcher's seeded numpy Generator ([P12] policy) instead of
       MATLAB's global stream.
  [P24] MATLAB semantics are value-copy: mutate() returns a modified
       COPY and never touches the caller's array.
  [P25] 'scramble' with nVars < 2 would crash MATLAB (randi([1, 0])
       when blockSize=2 > nVars); 'swap' with nVars < 2 likewise
       (randperm(1, 2)). The port returns the particle unchanged for
       those degenerate sizes instead of raising mid-simulation.

MATLAB quirks preserved (flagged !!!):
  * !!! 'frequency': the .m updates freqWeights AFTER overwriting
    particle(j), so the "old label" weight bump actually hits the NEW
    label (+0.1 then -0.1, i.e. a no-op except at the 0.1 clamp). The
    port reproduces this exactly.
"""
from __future__ import annotations

import numpy as np


def mutate(particle: np.ndarray, method: str, mutationRate: float,
           maxLabel: int, rng: np.random.Generator) -> np.ndarray:
    """
    Mutate one label chromosome (values 1..maxLabel). Returns a new
    array [P24]; `method` is one of 'uniform', 'block', 'scramble',
    'swap', 'frequency' (mutate.m switch).
    """
    particle = np.array(particle, dtype=int)   # value-copy [P24]
    nVars = particle.size

    if method == "uniform":
        # Uniform random reset
        mask = rng.random(nVars) < mutationRate
        particle[mask] = rng.integers(1, maxLabel, size=int(mask.sum()),
                                      endpoint=True)

    elif method == "block":
        # Block random reset
        if rng.random() < mutationRate:
            blockSize = int(rng.integers(1, max(1, nVars // 3),
                                         endpoint=True))
            startIdx = int(rng.integers(0, nVars - blockSize,
                                        endpoint=True))   # randi 1-based -> 0-based
            particle[startIdx:startIdx + blockSize] = rng.integers(
                1, maxLabel, size=blockSize, endpoint=True)

    elif method == "scramble":
        # Categorical scramble
        if nVars < 2:                                   # [P25]
            return particle
        if rng.random() < mutationRate:
            blockSize = int(rng.integers(2, max(2, nVars // 3),
                                         endpoint=True))
            startIdx = int(rng.integers(0, nVars - blockSize,
                                        endpoint=True))
            block = slice(startIdx, startIdx + blockSize)
            particle[block] = particle[block][rng.permutation(blockSize)]

    elif method == "swap":
        # Label swap
        if nVars < 2:                                   # [P25]
            return particle
        if rng.random() < mutationRate:
            i, j = rng.choice(nVars, size=2, replace=False)
            particle[i], particle[j] = particle[j], particle[i]

    elif method == "frequency":
        # Frequency-biased mutation: rarely-used labels are favoured
        labelCounts = np.bincount(particle, minlength=maxLabel + 1)[1:]
        freqWeights = 1.0 / (labelCounts + np.finfo(float).eps)

        for j in range(nVars):
            if rng.random() < mutationRate:
                p = freqWeights / freqWeights.sum()
                newLabel = int(rng.choice(np.arange(1, maxLabel + 1), p=p))
                particle[j] = newLabel
                # !!! quirk: particle[j] is already newLabel, so both
                # updates hit the new label (see module docstring)
                freqWeights[particle[j] - 1] += 0.1
                freqWeights[newLabel - 1] = max(
                    0.1, freqWeights[newLabel - 1] - 0.1)

    else:
        raise ValueError(f"Unknown mutation method: {method}")

    return particle
