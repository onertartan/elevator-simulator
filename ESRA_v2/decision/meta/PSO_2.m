classdef PSO_2 < MetaheuristicDispatcher
    properties
        w   % Mutation probability
        c1  % Cognitive component
        c2  % Social component
    end

    methods
        function dispatcher = PSO_2(startData)
           dispatcher@MetaheuristicDispatcher(startData);
           dispatcher.w = startData.w;
           dispatcher.c1 = startData.c1;
           dispatcher.c2 = startData.c2;
        end

        function [bestSolution, bestCost] = optimize(dispatcher, objFun)
            % Initialize parameters

            % Initialize personal bests
            personalBestPositions = dispatcher.population;
            personalBestCosts = objFun(dispatcher.population);

            % Initialize global best
            [globalBestCost, idx] = min(personalBestCosts);
            globalBestPosition = dispatcher.population(idx, :);

            % Best solution tracking
            bestSolution = globalBestPosition;
            bestCost = globalBestCost;

            % Main PSO loop
            for iter = 1:dispatcher.maxIter
                newPositions = zeros(dispatcher.nPop, dispatcher.nVar);
                for i = 1:dispatcher.nPop
                    % Mutation (F1)
                        lambda_i =  mutate(...
                            dispatcher.population(i, :), ...
                            dispatcher.mutationFunction, ...
                            dispatcher.w, ... %dispatcher.mutationRate
                            dispatcher.maxLabel);
                 

                    % Crossover for Cognitive Component (F2)
                    if rand < dispatcher.c1
                        delta_i = crossover(lambda_i, personalBestPositions(i, :));
                    else
                        delta_i = lambda_i;
                    end

                    % Crossover for Social Component (F3)
                    if rand < dispatcher.c2
                        X_i = crossover(delta_i, globalBestPosition);
                    else
                        X_i = delta_i;
                    end

                    newPositions(i, :) = X_i;
                end

                % Evaluate new dispatcher.population
                costs = objFun(newPositions);

                % Update personal bests
                improvedIdx = costs < personalBestCosts;
                personalBestPositions(improvedIdx, :) = newPositions(improvedIdx, :);
                personalBestCosts(improvedIdx) = costs(improvedIdx);

                % Update global best
                [minCost, idx] = min(costs);
                if minCost < globalBestCost
                    globalBestCost = minCost;
                    globalBestPosition = newPositions(idx, :);
                end

                % Update best solution
                if globalBestCost < bestCost
                    bestCost = globalBestCost;
                    bestSolution = globalBestPosition;
                end

                % Update dispatcher.population for next iteration
                dispatcher.population = newPositions;
            end
        end
    end
end
%% Crossover Operator
function child = crossover(parent1, parent2)
    n = length(parent1);
    child = parent1;
    
    % Select a random segment using sort and permutation
    indices = sort(randperm(n, 2));
    startIdx = indices(1);
    endIdx = indices(2);
    
    % Copy segment from parent2 to child
    child(startIdx:endIdx) = parent2(startIdx:endIdx);
end
