%GENERATE MDP POLICY DATABASE
clc,clear
building.nf=6;
A=MDPgenerateActionSet();
A_star_universe = cell(11,11);
S=MDPgenerateStateSpace(building.nf);

Sid2vec=containers.Map('KeyType','int32','ValueType','any');
Svec2id=containers.Map('KeyType','char','ValueType','int32');
for i=1:size(S,1)
    Svec2id( char(S(i,:)) )= i;
    Sid2vec(i)=S(i,:);
end

startData.INCmin=0;startData.INCmax=100;
startData.INTmin=0;startData.INTmax=100; 

Traffic = generateTrafficConf( startData );
epsilon = 0.00001;%to eliminate zero probabilities which will be never encountered
%( For example in %100 interfloor the state where the car is at the entrance floor will
%never be encountered. However, this state must be in state space for other traffic distributions)
elapsedTime=0;
for inc=1:size(Traffic,1)                      %Repeat for the number of incoming traffic configurations

    for int=1:size(Traffic,2)                  %Repeat for the number of interfloor traffic configurations
            if(Traffic(inc,int).OUT>=0)        %Check incoming,interfloor combinatioon yields a non-zero outgoing traffic value
                traffic=trafficRouteProbability(Traffic(inc,int),building.nf);
                traffic.Pr=traffic.Pr+epsilon;
                tic
                [A_star,V]= MDPGeneralizedPolicyIteration(building,traffic,A,S,Sid2vec,Svec2id);
                A_star_universe{inc,int}=A_star;
                inc,int,t=toc, elapsedTime=elapsedTime+ t
            end
    end
end
save('6floor_20Aralik.mat','A','S','A_star_universe','Svec2id','Sid2vec')