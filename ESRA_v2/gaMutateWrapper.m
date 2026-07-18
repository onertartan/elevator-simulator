function mutationChildren = gaMutateWrapper(parents, options, ~, ~, ~, ~, thisPopulation, mutationRate,mutationFunction)
    % Wrapper for GA to use unified mutate function
    nParents = length(parents);
    nVars = size(thisPopulation, 2);
    mutationChildren = thisPopulation(parents, :);
    maxLabel = options.PopInitRange(2,1);  % Upper bound from options
    
    % Apply mutation to each parent
    for i = 1:nParents
        mutationChildren(i,:) = mutate(...
            mutationChildren(i,:), ...
            mutationFunction, ...
            mutationRate, ...
            maxLabel);
    end
end