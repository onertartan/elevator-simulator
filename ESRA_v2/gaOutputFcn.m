function [state, options, optchanged] = gaOutputFcn(options, state, flag,idx1, idx2, idx3, idx4, idx5 )
optchanged = false;

    switch flag
        case 'init'
            % diversityHistory = [];
            % bestFitnessHistory = [];
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
            % Export to base workspace for analysis
            % assignin('base', 'diversityHistory', diversityHistory);
            % assignin('base', 'bestFitnessHistory', bestFitnessHistory);
            % assignin('base', 'mutationMethod', dispatcher.mutationFunction);
            % assignin('base', 'mutationRate', dispatcher.mutationRate);
    
    end
end