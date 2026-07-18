function s_group=MDP_find_s_group(s_vec,NF)
 [dir,CF,DF_up,DF_down ,HC_up,HC_down]=MDPdecode_svec(s_vec);
    if CF==1 && ~HC_up(CF)==1    %s=IDLE_no_up first(entrance floor)
        s_group=9;
    elseif CF==1 && HC_up(CF)==1 %up hall call at first(entrance floor)
        s_group=10;
    elseif  CF==NF && ~HC_down(CF-1)==1 %s=IDLE_no_down at last(highest floor)
        s_group=11;
    elseif CF==NF && HC_down(CF-1)==1   %down hall call at last(highest floor)
        s_group=12;

    elseif dir==0 && ~HC_up(CF)==1 && ~HC_down(CF-1)==1 %s=IDLE_no_hc
        s_group=1;                                      
    elseif dir==0 && ~HC_up(CF)==1 && HC_down(CF-1)==1  %s=IDLE_down
        s_group=2;
    elseif dir==0 && HC_up(CF)==1 && ~HC_down(CF-1)==1  %s=IDLE_up
        s_group=3; 
    elseif dir==0 && HC_up(CF)==1 && HC_down(CF-1)==1   %s=IDLE_up_down
        s_group=4; 
   
    elseif dir==1 && ~HC_up(CF)==1                      %s=UP_no_up
        s_group=5;
    elseif dir==1 && HC_up(CF)==1                       %s=UP_up
        s_group=6; 
    elseif dir==2 && ~HC_down(CF-1)==1                  %s=DOWN_no_down
        s_group=7;
    elseif dir==2 && HC_down(CF-1)==1                   %s=DOWN_down
        s_group=8;
    end

end