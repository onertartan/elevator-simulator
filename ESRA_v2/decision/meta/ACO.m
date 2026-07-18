classdef ACO  <MetaheuristicDispatcher
    properties
       numNodes          % Number of nodes/labels in the solution
        alpha             % Influence of pheromone
        beta              % Influence of heuristic information
        rho               % Evaporation rate
        Q                 % Pheromone deposit factor

    end

    methods 
        function dispatcher = ACO (startData)
            % Constructor for ACO class
            % Inputs:
            %   dispatcher.maxLabel: Maximum label value (e.g., 4 or 6)
            %   numNodes: Number of nodes/labels in the solution
            %   Np: Number of ants in the colony
            %   maxIter: Maximum number of iterations
            %   alpha: Influence of pheromone (default = 1)
            %   beta: Influence of heuristic information (default = 2)
            %   rho: Evaporation rate (default = 0.1)
            %   Q: Pheromone deposit factor (default = 1)

            % Assign parameters
            dispatcher@MetaheuristicDispatcher(startData )

            % dispatcher.alpha = startData.alpha;
            % dispatcher.beta = startData.beta;
            % dispatcher.rho = startData.rho;
            % dispatcher.Q = startData.Q;

        end
function [bestSolution, bestCost] = optimize(dispatcher,objFun )
    % Input parameters:
    % objFun     -  Objective function handle that accepts NxDim matrix
    % dispatcher.nVar       - Number of variables (positions) in each solution
    % dispatcher.maxLabel   - Maximum label value (labels range from 1 to dispatcher.maxLabel)
    % dispatcher.nPop      - Number of ants
    % maxIter    - Maximum number of iterations
    
    % Parameters
    rho = 0.1;          % Evaporation rate
    alpha = 1;          % Pheromone importance
    beta = 2;           % Heuristic importance
    Q = 1;             % Pheromone update constant
    
    % Initialize pheromone matrix (dispatcher.nVar x dispatcher.maxLabel)
    % Each row represents a position, each column represents a possible label
    tau = ones(dispatcher.nVar, dispatcher.maxLabel);
    eta = ones(dispatcher.nVar, dispatcher.maxLabel); % Heuristic information (can be modified based on problem)
    
    % Best solution tracking
    bestSolution = zeros(1, dispatcher.nVar);
    bestCost = inf;
    
    % Pre-allocate solutions matrix
    solutions = zeros(dispatcher.nPop, dispatcher.nVar);
    
    % Main loop
    for iter = 1: dispatcher.maxIter
        % Construct solutions for all positions
        for j = 1:dispatcher.nVar
            % Calculate probabilities for all ants at once for position j
            prob = (tau(j, :) .^ alpha) .* (eta(j, :) .^ beta);
            
            % Normalize probabilities
            prob = prob ./ sum(prob, 2);
            
            % Generate random numbers for all ants
            r = rand(dispatcher.nPop, 1);
            
            % Create cumulative probability matrix
            cumProb = repmat(cumsum(prob), dispatcher.nPop, 1);
            
            % Create matrix of repeated random numbers
            rMat = repmat(r, 1, dispatcher.maxLabel);
            
            % Find next labels for all ants at once
            [~, labels] = max(cumProb > rMat, [], 2);
            
            % Update solutions
            solutions(:, j) = labels;
        end
        
        % Verify all solutions contain valid labels
        assert(all(solutions >= 1 & solutions <= dispatcher.maxLabel, 'all'), ...
            'Invalid label values detected');
        
        % Evaluate solutions
        costs = objFun(solutions);
        
        % Update best solution
        [minCost, minIdx] = min(costs);
        if minCost < bestCost
            bestCost = minCost;
            bestSolution = solutions(minIdx, :);
        end
        
        % Vectorized pheromone update
        deltaTau = zeros(dispatcher.nVar, dispatcher.maxLabel);
        
        % Update pheromone for each position and chosen label
        for i = 1:dispatcher.nPop
            % For each position, increment pheromone for the chosen label
            for j = 1:dispatcher.nVar
                deltaTau(j, solutions(i,j)) = deltaTau(j, solutions(i,j)) + Q/costs(i);
            end
        end
        
        % Update pheromone trails
        tau = (1-rho) * tau + deltaTau;
        
        % Optional: Add minimum and maximum pheromone limits
        tau = max(1e-10, min(1, tau));
    end
end

        function solution = getBestSolution(dispatcher)
            % Return the best solution found
            solution = dispatcher.bestSolution;
        end
        

        function cost = getBestCost(dispatcher)
            % Return the cost of the best solution found
            cost = dispatcher.bestCost;
        end
    end
end