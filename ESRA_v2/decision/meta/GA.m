classdef GA   <MetaheuristicDispatcher
    properties
        crossoverRate   % Crossover rate
        mutationRate   % Mutation rate 0.05 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        gaMethod=1
        crossoverFcn
        selectionFcn
    end

    methods

        function dispatcher=GA  (startData)
            dispatcher@MetaheuristicDispatcher(startData )%temp solution for param availableInformation(it is 1 for now)
            dispatcher.crossoverRate = startData.Pc;
            dispatcher.mutationRate = startData.Pm;
            dispatcher.gaMethod = startData.gaMethod;
            dispatcher.objFun= startData.objFun;
            dispatcher.crossoverFcn = str2func(startData.crossoverFcn);
        end
        function [bestSolution, bestCost] = optimize(dispatcher,objFunWrapper )
            %%START OF BUILT-IN GA APPLICATION
            lb=ones(1,dispatcher.nVar);
            ub=ones(1,dispatcher.nVar)*dispatcher.maxLabel;
            IntegerVariables = 1:dispatcher.nVar;
            % Set number of runs based on convergenceExperiment
            if dispatcher.parameterSearch
                crossover_values = [0.3:.1:.8];%[0.1:.1:1];
                mutation_values = [0.01,0.02,0.05,0.1,0.2];
                selection_functions ={"selectionstochunif" "selectionroulette" "selectiontournament"};
                crossover_functions = {"crossoverscattered" "crossoversinglepoint" "crossovertwopoint"};
                mutation_functions= {'uniform' 'block' 'scramble' 'swap' 'frequency'};
                numRuns = dispatcher.numRunsForDispatcher;
            else
                numRuns = 1;
                mutation_values = [dispatcher.mutationRate];
                mutation_functions={dispatcher.mutationFunction};
                selection_functions={dispatcher.selectionFcn};
                crossover_functions={dispatcher.crossoverFcn};
                crossover_values=[dispatcher.crossoverRate];
            end
                fitnesses = zeros(length(crossover_values), length(mutation_values),length(selection_functions),length(crossover_functions),length(mutation_functions),numRuns);

            function [state, options, optchanged] = gaOutputFcn1(options, state, flag )
                optchanged = false;
                total_num_configurations = length(crossover_values)*length(mutation_values)*length(selection_functions)*length(crossover_functions)*length(mutation_functions)*numRuns;
    
               switch flag
                    case 'init'
                        % diversityHistory = [];
                        % bestFitnessHistory = [];
                          fprintf(['Running configurations: Pc=%d/%d, Pm=%d/%d,Selection_Func=%d/%d, Crossover_Func=%d/%d, Mutation_Func=%d/%d, Run_Num=%d/%d\n counter/Total=%d/%d'], ...
                            idx1,length(crossover_values),idx2, length(mutation_values),idx3,length(selection_functions),idx4,length(crossover_functions), ...
                            idx5,length(mutation_functions), idx6,numRuns,total_counter,total_num_configurations);   
                    case {'iter', 'interrupt'}
                        % % Compute population diversity
                        % pop = state.Population;
                        % n = size(pop, 1);
                        % if n > 1
                        %     dists = pdist(pop, 'hamming'); % Hamming distance for categorical data
                        %     avgDiversity = mean(dists);
                        % else
                        %     avgDiversity = 0;
                        % end
                        %
                        % % Record metrics
                        % diversityHistory = [diversityHistory; avgDiversity];
                        % bestFitnessHistory = [bestFitnessHistory; min(state.Score)];
                    case 'done'
                        fitnesses(idx1, idx2, idx3, idx4, idx5, idx6)=min(state.Score);
                        % Export to base workspace for analysis
                        % assignin('base', 'diversityHistory', diversityHistory);
                        % assignin('base', 'bestFitnessHistory', bestFitnessHistory);
                        % assignin('base', 'mutationMethod', dispatcher.mutationFunction);
                        if idx1==length(crossover_values) && idx2==length(mutation_values) && idx3==length(selection_functions) && idx4==length(crossover_functions) && idx5==length(mutation_functions) && idx6==numRuns
                               assignin('base', 'fitnesses', fitnesses);
                                assignin('base', 'mean_fitnesses', mean(fitnesses, 6));

                        end


                end
            end
          
            total_counter=0;
            for idx1=1:length(crossover_values)
                for idx2=1:length(mutation_values)
                   for idx3=1:length(selection_functions)
                     for idx4=1:length(crossover_functions)
                        for idx5=1:length(mutation_functions)
                            for idx6 = 1:numRuns
                                % Define output function only if convergenceExperiment is true
                                if dispatcher.parameterSearch
                                    outputFcn =@gaOutputFcn1;% @(options, state, flag)gaOutputFcn(idx1, idx2, idx3, idx4, idx5,idx6);
                                else
                                    outputFcn = [];
                                end
                                options = optimoptions('ga', ...
                                    'CrossoverFcn',crossover_functions{idx4}, ...% ,dispatcher.crossoverFcn
                                    'CrossoverFraction',crossover_values(idx1),... % dispatcher.crossoverRate
                                    'MutationFcn',{@gaMutateWrapper, mutation_values(idx2),mutation_functions{idx5} },...%mutation rate, func
                                    'SelectionFcn',selection_functions{idx3},...
                                    'PopulationSize', dispatcher.nPop, ...
                                    'MaxGenerations', dispatcher.maxIter, ...
                                    'UseParallel', false,...
                                    "Vectorized","on",...
                                    'OutputFcn', outputFcn );
                                %    'PlotFcn', {@gaplotbestf} ...
                               
                                [bestSolution,bestCost,~,~,~,~] = ga(objFunWrapper,dispatcher.nVar,[],[],[],[],lb,ub,[],IntegerVariables,options);
                                total_counter=total_counter+1;
                            end
                        end
                      end
                   end
                end
            end



        end


    end

end