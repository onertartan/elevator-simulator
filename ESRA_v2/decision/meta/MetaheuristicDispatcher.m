classdef MetaheuristicDispatcher<Dispatcher

    properties
        nPop                % population size
        maxIter           % Maximum number of iterations
        objFun

        population
        maxLabel          % Maximum label value (e.g., 4 or 6)
        nVar
        bestSolution      % Best solution found (sequence of labels)
        bestCost          % Cost of the best solution
        mutationFunction
        parameterSearch
        numRunsForDispatcher
    end

    methods (Abstract)
        % Abstract method to be implemented by subclasses
        [best_chrom, best_cost ] = optimize(dispatcher, FitnessFcn, numofHCs);
    end

    methods
        function dispatcher=MetaheuristicDispatcher(startData)

            dispatcher@Dispatcher(startData )%temp solution for param availableInformation(it is 1 for now)
            dispatcher.maxIter = startData.G;
            dispatcher.nPop = startData.nPop;
            dispatcher.objFun= startData.objFun;
            dispatcher.mutationFunction= startData.mutationFunction;
            dispatcher.parameterSearch = startData.parameterSearch;
            dispatcher.numRunsForDispatcher=startData.numberOfRuns;

        end
        function newPopulation = initializePopulation(dispatcher)
            newPopulation = randi([1, dispatcher.maxLabel], dispatcher.nPop, dispatcher.nVar);
        end

        function dispatch(dispatcher,building,cars,HC,P)
            nf=building.nf;                                 %Number of floors

            [HC_1,upindex]=sort([HC.waiting{1}.floor]);   %sorted   up hall calls
            [HC_2,downindex]=sort([HC.waiting{2}.floor]); %sorted down hall calls

            HC_all=[HC_1 HC_2];                          %[sorted up hall calls, sorted down hall calls]
            HC_numofups= length(HC_1);                   %Number of   up hall calls
            numofHCs=length(HC_all);                     %Number of all hall calls
            nc=length(cars);
            dispatcher.nVar=numofHCs;
            dispatcher.maxLabel=nc;
            if(numofHCs>0)

                % Initialize best solution and cost
                dispatcher.bestSolution = zeros(1, numofHCs); % Random initial solution
                dispatcher.bestCost = inf; % Initialize with worst possible cost
                dispatcher.nVar=numofHCs;
               % dispatcher.population = randi([1, dispatcher.maxLabel], dispatcher.nPop, dispatcher.nVar);
                objFunWrapper = @(population)dispatcher.objFun(cars.copy(),HC_all,HC_numofups,population,nf,P,"WT");
                
                [best_chrom,bestCost] = dispatcher.optimize(objFunWrapper);

                if ~isempty(HC_1) %~isempty(HC(1).waiting)
                    assignedCars=best_chrom(1:HC_numofups);
                    %a=a(upindex);
                    assignedCars(upindex)=assignedCars;
                    res=num2cell(assignedCars);
                    [HC.waiting{1}.carId]=res{:};
                    for i=1:length(HC.waiting{1})
                        query= [P.waiting{1}.floor]==HC.waiting{1}(i).floor;
                        res=num2cell (ones(1,length(query))*assignedCars(i));
                        [P.waiting{1}(query).carId]=res{:};
                    end

                end
                if ~isempty(HC_2)
                    assignedCars=best_chrom(HC_numofups+1:end);
                    assignedCars(downindex)=assignedCars;
                    % b=b(downindex);
                    res=num2cell(assignedCars);
                    [HC.waiting{2}.carId]=res{:};

                    for i=1:length(HC.waiting{2})
                        query= [P.waiting{2}.floor]==HC.waiting{2}(i).floor;
                        res=num2cell (ones(1,length(query))*assignedCars(i));
                        [P.waiting{2}(query).carId]=res{:};
                    end

                end
            end

        end




    end
end