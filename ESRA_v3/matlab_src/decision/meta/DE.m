classdef DE <MetaheuristicDispatcher
    properties
        F  % mutation factor
        crossoverRate
        variant
    end


    methods

        function dispatcher=DE(startData)
            dispatcher@MetaheuristicDispatcher(startData )%temp solution for param availableInformation(it is 1 for now)
            dispatcher.objFun= startData.objFun;
            dispatcher.F=startData.F;
            dispatcher.crossoverRate=startData.crossoverRate;
            dispatcher.variant = startData.variant;
        end
        function [bestSolution, bestCost] = optimize(dispatcher, objFun)
        
            % Set number of runs based on convergenceExperiment
            if dispatcher.parameterSearch
                crossover_values = .1:.1:1;%[0.3:.1:.8];%[0.1:.1:1];
                mutation_values = .01:.01:.2;%[0.01,0.02,0.05,0.1,0.2];
                variants = {"rand/1" "best/1" "rand/2" "best/2" "current-to-best/1" "rand-to-best/1" "current-to-rand/1"};          
                numRuns = dispatcher.numRunsForDispatcher;
                fitnesses = zeros(length(variants), length(crossover_values), length(mutation_values) ,numRuns);
            else
                numRuns = 1;
                mutation_values = [dispatcher.F]; 
                crossover_values=[dispatcher.crossoverRate];
                variants ={dispatcher.variant};
            end

            total_num_configurations=length(variants)*length(mutation_values)*length(crossover_values)*numRuns;
            
            total_counter=1;   
            for idxV=1:length(variants)
                for idxF =1:length(mutation_values)
                    for idxCR=1:length(crossover_values)
                        for nRun = 1:numRuns
                            fprintf(['\nRunning configurations: Variants=%d/%d, F=%d/%d,CR=%d/%d, Run_Num=%d/%d counter/Total=%d/%d'], ...
                            idxV,length(variants),idxF,length(mutation_values),idxCR,length(crossover_values),nRun,numRuns,total_counter,total_num_configurations);   
       
            % Initialize population randomly
            pop = randi([1, dispatcher.maxLabel], dispatcher.nPop, dispatcher.nVar);

            % Evaluate entire population at once
            costs = objFun(pop);

            % Find initial best
            [bestCost, bestIdx] = min(costs);
            bestSolution = pop(bestIdx,:);
            
                            % Main loop
                            for iter = 1:dispatcher.maxIter
                                % Generate all mutants at once
                                mutants = dispatcher.generateAllMutants(pop, costs,  variants{idxV}, mutation_values(idxF));
                
                                % Generate crossover masks for all individuals
                                masks = rand(dispatcher.nPop, dispatcher.nVar) < crossover_values(idxCR);
                                % Ensure at least one component is inherited from mutant
                                forcedIdx = sub2ind(size(masks), 1:dispatcher.nPop, randi(dispatcher.nVar, [1, dispatcher.nPop]));
                                masks(forcedIdx) = true;
                
                                % Create trial population
                                trials = pop;
                                trials(masks) = mutants(masks);
                
                                % Evaluate all trials at once
                                trialCosts = objFun(trials);
                
                                % Selection - replace if better
                                improved = trialCosts < costs;
                                pop(improved,:) = trials(improved,:);
                                costs(improved) = trialCosts(improved);
                
                                % Update best solution
                                [minCost, minIdx] = min(costs);
                                if minCost < bestCost
                                    bestCost = minCost;
                                    bestSolution = pop(minIdx,:);
                                end
                            end
                            fitnesses(idxV, idxF, idxCR, nRun)=bestCost;

                            total_counter=total_counter+1;
                        end
                    end
                end
            end
               assignin('base', 'fitnesses', fitnesses);
               assignin('base', 'mean_fitnesses', mean(fitnesses, 4));
        end
        function mutants = generateAllMutants(dispatcher, pop, costs, variant, F)
            [~, bestIdx] = min(costs);
            mutants = zeros(size(pop));

            switch lower(variant)
                case 'rand/1'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, i);
                        idx = randperm(length(candidates), 3);
                        r1 = candidates(idx(1));
                        r2 = candidates(idx(2));
                        r3 = candidates(idx(3));

                        for j = 1:dispatcher.nVar
                            base = pop(r1, j);
                            if pop(r2, j) ~= pop(r3, j)
                                if rand < F
                                    mutants(i, j) = pop(r2, j);
                                else
                                    mutants(i, j) = base;
                                end
                            else
                                mutants(i, j) = base;
                            end
                        end
                    end


                case 'best/1'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, [i, bestIdx]);  % exclude current and best individual
                        idx = randperm(numel(candidates), 2);
                        r1 = candidates(idx(1));
                        r2 = candidates(idx(2));

                        for j = 1:dispatcher.nVar
                            base = pop(bestIdx, j);
                            diff = pop(r1, j) ~= pop(r2, j);
                            if diff && rand < F
                                mutants(i, j) = pop(r1, j);
                            else
                                mutants(i, j) = base;
                            end
                        end
                    end
                    % ======== NEW VARIANTS START HERE ========

                case 'rand/2'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, i);
                        r = candidates(randperm(numel(candidates), 5));
                        for j = 1:dispatcher.nVar
                            base = pop(r(1), j);
                            candidates_j = [];
                            if pop(r(2), j) ~= pop(r(3), j)
                                candidates_j = [candidates_j, pop(r(2), j)];
                            end
                            if pop(r(4), j) ~= pop(r(5), j)
                                candidates_j = [candidates_j, pop(r(4), j)];
                            end
                            if rand < F && ~isempty(candidates_j)
                                mutants(i, j) = candidates_j(randi(numel(candidates_j)));
                            else
                                mutants(i, j) = base;
                            end
                        end
                    end
                case 'best/2'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, [i, bestIdx]);
                        r = candidates(randperm(numel(candidates), 4));
                        for j = 1:dispatcher.nVar
                            base = pop(bestIdx, j);
                            candidates_j = [];
                            if pop(r(1), j) ~= pop(r(2), j)
                                candidates_j = [candidates_j, pop(r(1), j)];
                            end
                            if pop(r(3), j) ~= pop(r(4), j)
                                candidates_j = [candidates_j, pop(r(3), j)];
                            end
                            if rand < F && ~isempty(candidates_j)
                                mutants(i, j) = candidates_j(randi(numel(candidates_j)));
                            else
                                mutants(i, j) = base;
                            end
                        end
                    end

                case 'current-to-best/1'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, [i, bestIdx]);
                        r = candidates(randperm(numel(candidates), 2));
                        r1 = r(1);
                        r2 = r(2);

                        for j = 1:dispatcher.nVar
                            current_j = pop(i, j);
                            best_j = pop(bestIdx, j);
                            r1_j = pop(r1, j);
                            r2_j = pop(r2, j);

                            if rand < F
                                % Prefer values that differ from current
                                candidates_j = [];

                                if best_j ~= current_j
                                    candidates_j = [candidates_j, best_j];
                                end
                                if r1_j ~= r2_j
                                    candidates_j = [candidates_j, r1_j];
                                end

                                if ~isempty(candidates_j)
                                    mutants(i, j) = candidates_j(randi(numel(candidates_j)));
                                else
                                    mutants(i, j) = current_j;
                                end
                            else
                                mutants(i, j) = current_j;
                            end
                        end
                    end

                case 'rand-to-best/1' %CLAUDE _AI
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, [i, bestIdx]);
                        r = candidates(randperm(numel(candidates), 3));
                        r1 = r(1);
                        r2 = r(2);
                        r3 = r(3);

                        for j = 1:dispatcher.nVar
                            base = pop(r1, j);
                            best_j = pop(bestIdx, j);
                            r2_j = pop(r2, j);
                            r3_j = pop(r3, j);

                            if rand < F
                                % Collect potential candidates
                                candidates_j = [];

                                % Add best solution if different from base
                                if best_j ~= base
                                    candidates_j = [candidates_j, best_j];
                                end

                                % Add difference component if r2 and r3 are different
                                if r2_j ~= r3_j
                                    candidates_j = [candidates_j, r2_j];
                                end

                                if ~isempty(candidates_j)
                                    mutants(i, j) = candidates_j(randi(numel(candidates_j)));
                                else
                                    mutants(i, j) = base;
                                end
                            else
                                mutants(i, j) = base;
                            end
                        end
                    end

                case 'current-to-rand/1'
                    for i = 1:dispatcher.nPop
                        candidates = setdiff(1:dispatcher.nPop, i);
                        r = candidates(randperm(numel(candidates), 3));
                        r1 = r(1);
                        r2 = r(2);
                        r3 = r(3);

                        for j = 1:dispatcher.nVar
                            current_j = pop(i, j);
                            r1_j = pop(r1, j);
                            r2_j = pop(r2, j);
                            r3_j = pop(r3, j);

                            if rand < F
                                % Collect potential candidates
                                candidates_j = [];

                                % Add random target if different from current
                                if r1_j ~= current_j
                                    candidates_j = [candidates_j, r1_j];
                                end

                                % Add difference component if r2 and r3 are different
                                if r2_j ~= r3_j
                                    candidates_j = [candidates_j, r2_j];
                                end

                                if ~isempty(candidates_j)
                                    mutants(i, j) = candidates_j(randi(numel(candidates_j)));
                                else
                                    mutants(i, j) = current_j;
                                end
                            else
                                mutants(i, j) = current_j;
                            end
                        end
                    end


               
                otherwise
                    display("ERROR")
            end


        end



    end
end