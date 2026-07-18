thisPopulation= [1,2,3;4,5,6];parents=[1,2];GenomeLength=3;mutationRate=1;

 mutationChildren = zeros(length(parents),GenomeLength);
    for i=1:length(parents)
        child = thisPopulation(parents(i),:);
        % Each element of the genome has mutationRate chance of being mutated.
        mutationPoints = find(rand(1,length(child)) < mutationRate);
        % each gene is replaced with a value chosen randomly from the range.
display("kj")
mutationPoints
        range = [1;6];
        % range can have one column or one for each gene.
        [r,c] = size(range);
        if(c ~= 1)
            range = range(:,mutationPoints);
        end   
display("abc")
        lower = range(1,:);
        upper = range(2,:);
        span = upper - lower;
        display("def")
        
        child(mutationPoints) = lower + rand(1,length(mutationPoints)) .* span;
        mutationChildren(i,:) = child;
    end

    mutationChildren

     mutationChildren = zeros(length(parents),GenomeLength);
    for i=1:length(parents)
        child = thisPopulation(parents(i),:);
        mutationPoints = find(rand(1,length(child)) < mutationRate);
        child(mutationPoints) = ~child(mutationPoints);
        mutationChildren(i,:) = child;
    end
    mutationChildren