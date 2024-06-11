clc
s_next_vec=[0 3 0 0 0 1 0 0 1 0 0 0 0]
NF=6;
s_id = Svec2id( char(s_next_vec) );
action = A_star(s_id)
display("START")

for i=1:10
[s_next_id,s_next_vec,reward]=MDP_find_next_state(action,s_next_vec,Svec2id,NF,traffic);
s_next_vec
action = A_star(s_next_id)

end

