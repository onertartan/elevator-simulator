function S=MDPgenerateStateSpace(NF)
NF=6
%Generates state space.
%A sample state consists of: car direction- cf- carcall_furthest - up hall calls-down hall calls
%Total number of states : car direction 0  NF*NF + car direction 1,2 NF*(NF-1)
num_of_states = ( 2*2^NF - NF-2 ) * 2^(2*(NF-1));
state_dim = 2+4*(NF-1);

hc_up_down=0:2^(2*(NF-1))-1;            %up hall calls-down hall calls
hc_up_down=de2bi(hc_up_down,'left-msb');% bit representation of HCs        F1 F2 - F2 F3
                                         % example for 3 floor-building     1  0 - 0  1  (up HC at F1,down hc at F3)

dim_hc=size(hc_up_down,1);    
S=[];                                 % car direction- cf- df_up-df_down - up hall calls-down hall calls

% Car stopped (direction = 0)
dir=0;
df = zeros(1,2*(NF-1));

for cf=1:NF                                       %For each car floor concate other possible states block
    temp = [repmat([dir cf df],dim_hc,1)   hc_up_down];
    S =  vertcat(S,temp);
end

% Car  moving up (direction = 1)
dir=1;
df_down =zeros(1,(NF-1));
for cf=1:NF-1
    
    df_up=1:2^( (NF-cf))-1;                                           %up hall calls-down hall calls
    df_up=de2bi(df_up,'left-msb');
    zero_padding_pre=repmat(zeros(1,cf-1),size(df_up,1),1); %zero padding for cf and lower floors(if the car is going up df cannot be at lower floors)
    df_up = [zero_padding_pre  df_up];
    
    df_up_down=[df_up repmat(df_down,size(df_up,1),1) ];
    for i=1:size(df_up_down,1)
        row =  df_up_down(i,:);
        temp=[repmat([dir cf row],dim_hc,1) hc_up_down];
        S =  vertcat(S,temp);
    end
    
end

% Car  moving down (direction = 2)
dir=2;
df_up =zeros(1,(NF-1));
for cf=2:NF
    
    df_down=1:2^(cf-1)-1;                                           %up hall calls-down hall calls
    df_down=de2bi(df_down,'left-msb');
    zero_padding_post=repmat(zeros(1,NF-cf),size(df_down,1),1); %zero padding for cf and higher floors(if the car is going down df cannot be at higher floors)
    df_down = [df_down  zero_padding_post];
    
    df_up_down=[repmat(df_up,size(df_down,1),1) df_down ];
    for i=1:size(df_up_down,1)
        row =  df_up_down(i,:);
        temp=[repmat([dir cf row],dim_hc,1) hc_up_down];
        S=  vertcat(S,temp);
    end
    
end

S= cast(S,"int8");
end