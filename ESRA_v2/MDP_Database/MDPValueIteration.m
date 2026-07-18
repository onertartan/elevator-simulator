function [delta,V,optimalAction,A_star ]=MDPValueIteration(delta,V,s_id,Sid2vec,Svec2id,A,NF,traffic,timeCounter,A_star)
        gama=1.0;     
        verbose=0;
        s_vec=Sid2vec(s_id);
        [dir,CF,DF_up,DF_down ,HC_up,HC_down]=MDPdecode_svec(s_vec);%split s_vec to components
        timeCounter=0;
        transfer_time = 7;
        move_penalty=0.01;
        wait_penalty=0.02;
        s_group=MDP_find_s_group(s_vec, NF);%find the group of the state
        %s_vec
        % index_of_action=randi(length(A{s_group})); %random policy
        % a=A{s_group}(index_of_action);%action
        q=zeros(length(A{s_group}),1);%action values set for the state belonging to s_group
        action2id = containers.Map({'pick_up_down','move_down','wait','move_up','pick_up_up'},{-2,-1,0,1,2});
      
        if(verbose),display('NEW STATE');s_vec,display('Actions:'), A{s_group} ,end %%test 
      
         %for each action a in the action set
        for a=1:length(A{s_group})
            action=A{s_group}(a);
            HC_up_next=HC_up;
            HC_down_next=HC_down;
            DF_up_next= DF_up;
            DF_down_next=DF_down;
                       
            
           if(verbose), action,end %%test
            if strcmp(action,'pick_up_up')
                HC_up_next(CF)=0;
                CF_next=CF;
                dir_next=1;
                timeCounter=timeCounter+transfer_time;

                probs=traffic.Pr(CF,CF+1:end);
                probs=probs./sum(probs);
                for i=1:length(probs)
                   DF_up_next=DF_up;
                   next_df = i+CF-1;
                   DF_up_next(next_df)=1;
                   %reward=calculateReward(HC_up_next,HC_down_next,traffic.Pr,timeCounter);
                    reward=-transfer_time*(sum(HC_up_next)+sum(HC_down_next));
                    s_vec_next=[dir_next CF_next DF_up_next  DF_down_next HC_up_next HC_down_next];
                   if(verbose), s_vec_next,  "pick_up_up probs:",probs,DF_down_next,end %%test
                    s_id_next=Svec2id(char(s_vec_next));
                    q(a)=q(a)+probs(i)*(reward+gama*V(s_id_next));
                end
                
            elseif (strcmp(action,'pick_up_down'))
               timeCounter=timeCounter+transfer_time;                
                HC_down_next(CF-1)=0;
                CF_next=CF;
                dir_next=2;
 
                probs=traffic.Pr(CF,1:CF-1);
                probs=probs./sum(probs);
                for i=1:length(probs)
                    DF_down_next=DF_down;
                    next_df = i;
                    DF_down_next(next_df)=1;
                    s_vec_next=[dir_next CF_next DF_up_next  DF_down_next HC_up_next HC_down_next];
                    if(verbose),s_vec_next, probs(i),end %%test
                    %reward=calculateReward(HC_up_next,HC_down_next,traffic.Pr,timeCounter);
                    reward=-transfer_time*(sum(HC_up_next)+sum(HC_down_next));
                    s_id_next=Svec2id(char(s_vec_next));
                    q(a)=q(a)+probs(i)*(reward+gama*V(s_id_next));

                end
                
            elseif (strcmp(action,'wait') )
               timeCounter=timeCounter+2;
            
                s_id_next=s_id;
                reward=-2*(sum(HC_up)+sum(HC_down))-wait_penalty*(sum(DF_up)+sum(DF_down));
                q(a)=q(a)+(reward+gama*V(s_id_next));
                 if(verbose), s_vec_next=Sid2vec(s_id_next) ,end%%test
         
            else %move up or move down
                timeCounter=timeCounter+2;      
                
                if(strcmp(action,'move_up') )
                     
                           CF_next=CF+1;
                           
                           if DF_up_next(CF_next-1)==1
                               DF_up_next(CF_next-1)=0;   %reward  alighting  add 7 seconds
                        %!!!!!MOVE UP VE MOVE DONW İÇİN ; YOLCU İNECEKSE VE AYNI KATTA PICKUP YOKSA 7
                        %SANİYE CEZA EKLENMELİ

                           end
                           
                           if any(DF_up_next)
                               dir_next=1;
                           else
                               dir_next=0;
                           end
                           
                           s_vec_next=[dir_next CF_next DF_up_next  DF_down_next  HC_up_next HC_down_next];
                           if(verbose),  s_vec_next ,end%%test
                           reward=-2*(sum(HC_up)+sum(HC_down))-move_penalty;
                           s_id_next=Svec2id(char(s_vec_next));
                           
                            
                           if DF_up_next(CF_next-1)==1 && ~(strcmp(A_star(s_id_next),'pick_up_down')) && ~(strcmp(A_star(s_id_next),'pick_up_up'))
                                reward=reward-transfer_time*(sum(HC_up_next)+sum(HC_down_next));
                           end
                           q(a)=q(a)+(reward+gama*V(s_id_next));
                elseif(strcmp(action,'move_down'))
                    
                        CF_next=CF-1;
                        if DF_down_next(CF_next)==1
                            DF_down_next(CF_next)=0;    %reward  alighting  add 7 seconds
                        end
                        if any(DF_down_next)
                            dir_next=2;
                        else
                            dir_next=0;
                        end
                        s_vec_next=[dir_next CF_next DF_up_next  DF_down_next  HC_up_next HC_down_next];
                        if(verbose),  s_vec_next ,end%%test
                        reward=-2*(sum(HC_up)+sum(HC_down))-move_penalty;
                        s_id_next=Svec2id(char(s_vec_next));
                        
                          if DF_down_next(CF_next)==1 && ~(strcmp(A_star(s_id_next),'pick_up_down')) && ~(strcmp(A_star(s_id_next),'pick_up_up'))
                                reward=reward-transfer_time*(sum(HC_up_next)+sum(HC_down_next));
                           end
                        q(a)=q(a)+(reward+gama*V(s_id_next)); 
                end
                
                
            end
              
           
       end
        
        v=V(s_id);
        [q_best,optimalActionId]=max(q);
        V(s_id)=q_best;
        delta=max(delta,abs(v-V(s_id)));
        optimalAction=A{s_group}{optimalActionId}; 
        A_star(s_id)=cast(action2id(optimalAction),"int8");   

        if(verbose),display("q values for"),A{s_group},q,end
end

function r=calculateReward(HC_up,HC_down,Pr,timeCounter)
r=-2*(sum(HC_up)+sum(HC_down))-0.1;
%Taking into account new emerging passenger 
% for(i=1:length(HC_up))
%     if(HC_up(i)~=0)
%         r=r-timeCounter*sum(Pr(i,i+1:end))/10;
%     end
%     if(HC_down(i)~=0)
%         r=r-timeCounter*sum(Pr(i+1,1:i))/10;
%     end
% end
end


