function [snext_id,snext_vec,reward]=MDP_find_next_state(a,s_vec,Svec2id,NF,traffic)
[dir,CF,CC_furthest,HC_up,HC_down]=MDPdecode_svec(s_vec);
%display('before action');a,s_vec
if(strcmp(a,'pick_up_up'))
    HC_up(CF)=0;
    dir=1;
    cumProb=traffic.Pr(CF,CF+1:end);
    idx=estimateCarCall(cumProb);
    if(idx~=0 && ((CF+idx)>CC_furthest || CC_furthest==0))
        CC_furthest=(CF+idx);
    else%(isempty(idx))
        CC_furthest=NF;
    end %,CF,CC_furthest,idx
    timeCounter=7;
elseif(strcmp(a,'pick_up_down'))
    HC_down(CF-1)=0;
    dir=2;
    cumProb=traffic.Pr(CF,1:CF-1);
    idx=estimateCarCall(cumProb);
    if(idx~=0 && (idx<CC_furthest || CC_furthest==0))
        CC_furthest=idx;
    else%if(isempty(idx))
        CC_furthest=1;
    end
    timeCounter=7;
else
    timeCounter=2;
    if(strcmp(a,'move_up') )
        if  CC_furthest>(CF+1)
            dir=1;
        else
            dir=0;
        end
        CF=CF+1;
    elseif(strcmp(a,'move_down'))
        if CC_furthest~=0 && CC_furthest<(CF-1)
            dir=2;
        else
            dir=0;
        end
        CF=CF-1;
    end
    
    if CC_furthest==CF
        CC_furthest=0;
        dir=0;
    end
end

if dir==2 && CF ==1%strcmp(a,'move_down') && new_CF==1
    dir=0;
elseif(dir==1 && CF==NF)%strcmp(a,'move_up') && new_CF==NF
    dir=0;
end

snext_vec=[dir CF CC_furthest HC_up HC_down];
%display('after action'),s_vec
snext_id=Svec2id(char(snext_vec));%s_id=1;%
%reward=-(sum(HC_up)+sum(HC_down));
reward=calculateReward(HC_up,HC_down,traffic.Pr,timeCounter);
end

function r=calculateReward(HC_up,HC_down,Pr,timeCounter)
r=-(sum(HC_up)+sum(HC_down));
for i=1:length(HC_up)
    if(HC_up(i)~=0)
        r=r-timeCounter*sum(Pr(i,i+1:end))/10;
    end
    if(HC_down(i)~=0)
        r=r-timeCounter*sum(Pr(i+1,1:i))/10;
    end
end
end

function idx=estimateCarCall(cumProb)
idx=0;
if max(cumProb)~=0
    cumProb=cumProb/sum(cumProb);
    cumProb=cumsum(cumProb);
    cumProbShifted=[0 cumProb(1:end-1)];
    temp=rand;
    %cumProb%cumProbShifted
    idx=find(temp>cumProbShifted  & temp<cumProb);
end
end
