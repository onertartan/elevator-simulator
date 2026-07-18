
function particle = mutate( particle, method, mutationRate, maxLabel)
% Unified mutation function for categorical labels
% Inputs:
%   particle: single solution vector (1 x nVars)
%   method: mutation strategy name ('uniform', 'block', etc.)
%   mutationRate: probability of mutation
%   maxLabel: maximum label value (dispatcher.maxLabel)

nVars = numel(particle);

switch method
    case 'uniform'
        % Uniform random reset
        mask = rand(1, nVars) < mutationRate;
        particle(mask) = randi([1, maxLabel], 1, nnz(mask));

    case 'block'
        % Block random reset
        if rand < mutationRate
            blockSize = randi([1, max(1, floor(nVars/3))]);
            startIdx = randi([1, nVars - blockSize + 1]);
            particle(startIdx:startIdx+blockSize-1) = ...
                randi([1, maxLabel], 1, blockSize);
        end

    case 'scramble'
        % Categorical scramble
        if rand < mutationRate
            blockSize = randi([2, max(2, floor(nVars/3))]);
            startIdx = randi([1, nVars - blockSize + 1]);
            block = startIdx:startIdx+blockSize-1;
            particle(block) = particle(block(randperm(blockSize)));
        end

    case 'swap'
        % Label swap
        if rand < mutationRate
            idx = randperm(nVars, 2);
            temp = particle(idx(1));
            particle(idx(1)) = particle(idx(2));
            particle(idx(2)) = temp;
        end

    case 'frequency'
        % Frequency-biased mutation
        labelCounts = histcounts(particle, 1:maxLabel+1);
        freqWeights = 1./(labelCounts + eps);  % Inverse frequency weighting

        for j = 1:nVars
            if rand < mutationRate
                newLabel = randsample(1:maxLabel, 1, true, freqWeights);
                particle(j) = newLabel;

                % Update frequency weights locally
                freqWeights(particle(j)) = freqWeights(particle(j)) + 0.1;
                freqWeights(newLabel) = max(0.1, freqWeights(newLabel) - 0.1);
            end
        end

    otherwise
        error('Unknown mutation method: %s', method);
end
end