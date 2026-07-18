function [dir,CF,DF_up,DF_down ,HC_up,HC_down]=MDPdecode_svec(s_vec)
dir=s_vec(1);
CF=s_vec(2);
window = (length(s_vec)-2)/4; 
DF_up=s_vec(3:window+2);
DF_down=s_vec(window+3: 2*window+2 );
HC_up= s_vec(2*window+3:3*window+2);%first threee elements are [dir CF df_next], remaining elements are[HC_up HC_down]
HC_down=s_vec(3*window+3:end) ;
end