function A=MDPgenerateActionSet()
%States do not have identical actian sets.
%They are grouped according to common action sets.

%S_idle: State set that the car is idle at inter-floors(floor other than first&last floors)
A{1}={'move_up','move_down','wait'};P{1}=ones(1,3)*1/3;                 %s='IDLE_no_hc'
A{2}={'move_up','move_down','pick_up_down','wait'};P{2}=ones(1,4)*1/4;  %s='IDLE_down'
A{3}={'move_up','move_down','pick_up_up','wait'};P{3}=ones(1,4)*1/4;    %s='IDLE_up'
A{4}={'move_up','move_down','pick_up_up','pick_up_down','wait'};P{4}=ones(1,5)*1/5;%s='IDLE_up_down'
%S_up : State set that the car direction is up(car has a car call above the car floor)
A{5}={'move_up'};P{5}=1;                             %s=UP_no_up
A{6}={'move_up','pick_up_up'};P{6}=ones(1,2)*1/2;    %s=UP_up
%S_down : State set that the car direction is down(car has a car call below the car floor)
A{7}={'move_down'};P{7}=1;                           %s=DOWN_no_down
A{8}={'move_down','pick_up_down'};P{8}=ones(1,2)*1/2;%s=DOWN_down
%First-Last Floors
A{9}={'move_up','wait'};P{9}=ones(1,2)*1/2;                   %s=IDLE_no_up first(entrance floor)
A{10}={'move_up','pick_up_up'};P{10}=ones(1,2)*1/2;    %up hall call at first(entrance floor) 
A{11}={'move_down','wait'};P{11}=ones(1,2)*1/2;               %s='IDLE_no_down'; last
A{12}={'move_down','pick_up_down'};P{12}=ones(1,2)*1/2;%down hall call at last(highest floor)
end

%Aşağıdakilerden wait silindi, gerek yok
%A{10}={'move_up','pick_up_up','wait'};P{10}=ones(1,3)*1/3;    %up hall call at first(entrance floor) 
%A{12}={'move_down','pick_up_down','wait'};P{12}=ones(1,3)*1/3;%down hall call at last(highest floor)
