classdef GeneticAlgorithmDispatcher<Dispatcher
    
    properties
        G    % maximum number of generations -
        Np    % Number of chromosomes
        Pc   % Crossover rate
        Pm   % Mutation rate 0.05 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        gaMethod=1;
    end
    
    methods
        
        function dispatcher=GeneticAlgorithmDispatcher(G,Np,Pc,Pm,gaMethod,stateUpdateTypeForNextDecision,availableInformation)
            dispatcher@Dispatcher(stateUpdateTypeForNextDecision,availableInformation )
            dispatcher.G = G;
            dispatcher.Np = Np;
            dispatcher.Pc = Pc;
            dispatcher.Pm = Pm;
            dispatcher.gaMethod = gaMethod;
        end
        
        function dispatch(dispatcher,building,cars,HC,P)
            nf=building.nf;                                 %Number of floors
           
            [HC_1,upindex]=sort([HC.waiting{1}.floor]);   %sorted   up hall calls
            [HC_2,downindex]=sort([HC.waiting{2}.floor]); %sorted down hall calls
            
            HC_all=[HC_1 HC_2];                          %[sorted up hall calls, sorted down hall calls]
            HC_numofups= length(HC_1);                   %Number of   up hall calls
            numofHCs=length(HC_all);                     %Number of all hall calls
            nc=length(cars);
            
            switch(dispatcher.gaMethod)
                case 1
                    %%START OF BUILT-IN GA APPLICATION
                    lb=ones(1,numofHCs);
                    ub=ones(1,numofHCs)*nc;
                    IntegerVariables = 1:numofHCs;
                    
                    %x=randi(CAR.nc,dispatcher.Np,numofHCs); %Initialize population
                    %x=repmat([3 3 1 2 2 4],50,1);
                    
                    %options = gaoptimset('PopulationType', 'custom',...
                    %'CreationFcn',@create_permutations,'CrossoverFcn',@crossover_permutation,...
                    %'MutationFcn',@mutate_permutation);
                    
                    %options = gaoptimset('OutputFcn',@myoutputfcn,'PopulationSize',dispatcher.Np,'Generations',dispatcher.G,'UseParallel', false,'Vectorized','on','PlotFcns',{@gaplotchange,@gaplotbestf,@gaplotexpectation,@gaplotscorediversity,@gaplotrange,@gaplotscores});
                    
                    options = gaoptimset('PopulationSize',dispatcher.Np,'Generations',dispatcher.G,'UseParallel', false,'Vectorized','on','StallGenLimit',100,'OutputFcns',{@myoutfun});%,'PlotFcns',{@gaplotchange});%,'FitnessScalingFcn',@myfun);%,'PlotFcns',{@gaplotchange,@gaplotbestf,@gaplotexpectation,@gaplotscorediversity,@gaplotrange,@gaplotscores});
                    
                    
                    %   options.TolFun=0;options.TolCon=0;options.StallGenLimit=inf;%,options,pause
                    %         opts = optimoptions(@ga, ...
                    %                     'PopulationSize', 50, ...
                    %                     'MaxGenerations', 100, ...
                    %                     'EliteCount', 10, ...
                    %                     'PlotFcn', @gaplotbestf);
                    
                    
                    if(dispatcher.availableInformation==1)          %1-Conventional system
                        FitnessFcn = @(chrom)objFunNormal1(cars.copy(),HC_all,HC_numofups,chrom,nf);
                    else
                        [P_1_floor,P_upindex]=sort([P(1).waiting.floor]);
                        [P_2_floor,P_downindex]=sort([P(2).waiting.floor]);
                        if (dispatcher.availableInformation==2)     %2-Number of passengers are known
                            FitnessFcn = @(chrom)ObjFunWithNofPassengers(cars.copy(),HC_all,HC_numofups,chrom,P_1_floor,P_2_floor );
                        elseif(dispatcher.availableInformation==3)  %3-Destinations are known
                            P_1_DF=[P(1).waiting(P_upindex).DF];
                            P_2_DF=[P(2).waiting(P_downindex).DF];
                            FitnessFcn = @(chrom) ObjFunWithDestinations(cars.copy(),HC_all,HC_numofups,chrom,P_1_floor,P_2_floor,P_1_DF,P_2_DF,1);
                        end
                    end
                    
                    if(numofHCs>0)
                        
                        [best_chrom,~,~,~,~,~] = ga(FitnessFcn,length(HC_all),[],[],[],[],lb,ub,[],IntegerVariables,options);
                        % [best_chrom,fval,exitflag,output,population,scores] = ga(FitnessFcn,length(HC_all),[],[],[],[],lb,ub,[],IntegerVariables,options);
                        %if(any(scores<0))
                        %   display('NEGATIVE SCORE ALERT');
                        %   pause
                        %end
                        % [best_chrom, fbest, exitflag] = ga(FitnessFcn, HC_all, [], [], [], [], lb, ub,  [1:HC_all], opts);
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
                            
                            %%YENİ 13.08.2023 !!!!(BU ÜSTTEKİ if için de yazılacak 
                            
                            for i=1:length(HC.waiting{2})
                                query= [P.waiting{2}.floor]==HC.waiting{2}(i).floor;
                                res=num2cell (ones(1,length(query))*assignedCars(i));
                                [P.waiting{2}(query).carId]=res{:};
                            end
                            %YENİ_SON
                            
                        end
                    end
                    %%END OF BUILT-IN
                case 2
                    chrom=randi(cars.nc,dispatcher.Np,numofHCs); %Initialize population
                    
                    
                    averageWT=ObjFunNormal1(cars.copy(),HC_all,HC_numofups,chrom,nf);%[TOTAL T]
                    fitness=1./averageWT;
                    %pause
                    if(numofHCs>0)
                        for g=1:dispatcher.G
                            % CAR.floor,CAR.DF,HC_all,chrom,fitness,pause
                            chrom_offspring=crossover(cars.nc,dispatcher.Np,chrom,fitness,dispatcher.Pc,dispatcher.Pm);
                            if(isempty(chrom_offspring))
                                return
                            end
                            
                            averageWT=ObjFunNormal1(cars.copy(),HC_all,HC_numofups,chrom_offspring,nf);%[TOTAL T]
                            fitness=(1./(1+averageWT).^2);
                            chrom=chrom_offspring;
                            
                            [~, index]=max(fitness);
                            best_chrom=chrom(index,:);
                            % chrom,pause(0.3);
                        end
                        if ~isempty(HC_1) %~isempty(HC(1).waiting)
                            a=best_chrom(1:HC_numofups);
                            a(upindex)=a;
                            a=num2cell(a);
                            [HC(1).waiting.AssignedCar]=a{:};
                        end
                        if ~isempty(HC_2)
                            b=best_chrom(HC_numofups+1:end);
                            b(downindex)=b;
                            b=num2cell(b);
                            [HC(2).waiting.AssignedCar]=b{:};
                        end
                    else
                        % display('Number of HCs less than 2.GA not executed.');
                    end
            end
            
            function state = gaplotchange(options, state, flag)
                % GAPLOTCHANGE Plots the logarithmic change in the best score from the
                % previous generation.
                %
                persistent last_best % Best score in the previous generation
                if(state.Score(1)<0)
                    pause
                end
                
                [state.Expectation  state.Score]
                
                best = min(state.Score); % Best score in the current generation
                if state.Generation == 0 % Set last_best to best.
                    last_best = best;
                else
                    change = last_best - best; % Change in best score
                    last_best = best;
                    if change > 0 % Plot only when the fitness improves
                        %figure(2)
                        %plot(state.Generation,change,'xr');
                    end
                end
                state.LastImprovement
            end
            function [state, options,optchanged] = myoutputfcn(options,state,flag)
                %GAOUTPUTFCNTEMPLATE Template to write custom OutputFcn for GA.
                % [STATE, OPTIONS, OPTCHANGED] = GAOUTPUTFCNTEMPLATE(OPTIONS,STATE,FLAG)
                % where OPTIONS is an options structure used by GA.
                %
                % STATE: A structure containing the following information about the state
                % of the optimization:
                % Population: Population in the current generation
                % Score: Scores of the current population
                % Generation: Current generation number
                % StartTime: Time when GA started
                % StopFlag: String containing the reason for stopping
                % Selection: Indices of individuals selected for elite,
                % crossover and mutation
                % Expectation: Expectation for selection of individuals
                % Best: Vector containing the best score in each generation
                % LastImprovement: Generation at which the last improvement in
                % fitness value occurred
                % LastImprovementTime: Time at which last improvement occurred
                %
                % FLAG: Current state in which OutputFcn is called. Possible values are:
                % init: initialization state
                % iter: iteration state
                % interrupt: intermediate state
                % done: final state
                %
                % STATE: Structure containing information about the state of the
                % optimization.
                %
                % OPTCHANGED: Boolean indicating if the options have changed.
                %
                % See also PATTERNSEARCH, GA, GAOPTIMSET
                % Copyright 2004-2006 The MathWorks, Inc.
                % $Revision: 1.1.6.5 $ $Date: 2007/08/03 21:23:22 $
                optchanged = false;
                switch flag
                    case 'init'
                        disp('Starting the algorithm');
                    case {'iter','interrupt'}
                        disp('Iterating ...')
                        avg_score(state.Generation)=mean(state.Score);
                        
                    case 'done'
                        disp('Performing final task');
                        fname=[pwd,'\',num2str(state.Generation),'.mat'];
                        save(fname,'state','avg_score')
                end
            end
            
            
            function [state,options,flag] = myoutfun(options,state,flag)
                % state.Score
            end
            
            function expectation = myfun(scores, nParents)
                display('HEY');expectation=1./(scores.^2);
                
                [expectation scores]
                display('HAY');
            end
            
           %cars= Dispatcher.updateCarServiceLists(cars,HC);
        end
        
    
      
    end
    
end