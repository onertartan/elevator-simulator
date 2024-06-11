function [A_star,V]=MDPGeneralizedPolicyIteration(building,traffic,A,S,Sid2vec,Svec2id)
NF=building.nf;

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
 
%num_of_states=(NF-2)*num_of_directions*num_of_df_states*num_of_hc_combinations+2*2*num_of_hc_combinations+4*num_of_hc_combinations;%NF-3
%S=zeros(num_of_states,3+dim_hc2);
num_of_states=size(S,1);
V=zeros(num_of_states,1);
timeCounter=7;
k=1;
delta=1;
epsilon=.5;
A_star= zeros(num_of_states,1);
while  k<=50 && (delta>epsilon) 
  delta=0;
  for s_id=1:num_of_states
    [delta ,V,optimalAction,A_star]=MDPValueIteration(delta,V,s_id,Sid2vec,Svec2id,A,NF,traffic,timeCounter,A_star);
  end
   % delta, k;
    %pause(.3)
    k=k+1;
end
delta,pause(1)
%AFTER STOPPING VALUE ITERATION GIVE OPTIMAL ACTIONS
  
% for s_id=1:num_of_states
%     [~,~,optimalAction]=MDPValueIteration(delta,V,s_id,Sid2vec,Svec2id,A,NF,traffic,timeCounter);
%      A_star(s_id)=optimalAction;   
% end

end


