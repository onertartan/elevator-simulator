classdef MDP<DecisionMaker
    properties
        A_star
        A_star_universe
        Svec2id
    end
    
    methods
        function mdp = MDP( stateUpdateTypeForNextDecision,Svec2id,A_star_universe)
            mdp@DecisionMaker(stateUpdateTypeForNextDecision);   %superclass constructor
            mdp.A_star_universe=A_star_universe;
            mdp.Svec2id=Svec2id;
        end
        function setTraffic(mdp,traffic)
            row=round(traffic.inc/10)+1;
            col=round(traffic.int/10)+1;
            mdp.A_star=mdp.A_star_universe{row,col};
        end
        
        function run(mdp,building,cars,HC,P)
          %22 ve 35'de code2action ??????????
            code2action=  containers.Map({-2,-1,0,1,2},{'pick_up_down','move_down','wait','move_up','pick_up_up'});
            HC.clearCarIds();             %Clear HC assigned cars
            for i=1:length(cars)
                CF=cars(i).floor;
                if(abs(floor(CF)-CF)==0 ) %Ara katta değilse && isKey(Svec2id,char(svec)))
                    [HC_up,HC_down,DF_up,DF_down]= mdp.getHCandDF(building,HC,cars(i));%get current hall calls and destination floors
                    
                    dir=mod(cars(i).state,3);
                    s_vec=[dir CF DF_up DF_down HC_up HC_down];
                    
                    s=mdp.Svec2id(char(s_vec));
                    
                   a_star=mdp.A_star(s);        %optimal action (code) at state s (-2,-1,0,1 or 1)
                   a_star = code2action(a_star); %optimal action name('pick_up_down','move_down','wait','move_up' or 'pick_up_up')
                    %s_vec   , mdp.a_star
                    
                    switch(a_star)
                        case('move_up') 
                            cars(i).state=1;
                        case('move_down')
                            cars(i).state=-1;
                        case ('pick_up_up')
                            %     svec,display('pick up up'),  pause
                            %  HC=resetHC_Cars(HC);
                            index= ([HC.waiting{1}.floor]==CF);
                            [HC.waiting{1}(index).carId]=cars(i).id;
                             [P.waiting{1}(index).carId]=cars(i).id;  %YENİ EKLENDİ (22.12(
                             cars(i).updateServiceList(HC,P);%YENİ EKLENDİ (22.12(
                                 cars(i).state=1;
                            %cars(i).HC_up=CF;
                            %[cars(i),HC,P] = cars(i).pickup(HC,P,sim.time);
                            
                        case ('pick_up_down')
                            %svec,display('pick up down')
                            %HC(2).active.floor,car.floor
                            %   HC=resetHC_Cars(HC);
                            index= ([HC.waiting{2}.floor]==CF);
                            
                            [HC.waiting{2}(index).carId]=cars(i).id;
                              [P.waiting{2}(index).carId]=cars(i).id;  %YENİ EKLENDİ (22.12(
                             cars(i).updateServiceList(HC,P);%YENİ EKLENDİ (22.12(
                            cars(i).state=-1;
                         
                           % cars(i).HC_down=CF;
                            % [cars(i),HC,P] = cars(i).pickup(HC,P,sim.time);
                        case('wait')
                            cars(i).state=0;
                    end
                end
            end
            
        end
        
        function [HC_up,HC_down,DF_up,DF_down]= getHCandDF(~,building,HC,car)
            
            HC_up=zeros(1,building.nf-1);
            HC_down=zeros(1,building.nf-1);
            DF_up=zeros(1,building.nf-1);
            DF_down=zeros(1,building.nf-1);
            
            if(~isempty([HC.waiting{1}.floor]))
                HC_up([HC.waiting{1}.floor])=1;
            end
            if(~isempty([HC.waiting{2}.floor]) )
                HC_down([HC.waiting{2}.floor]-1)=1;
            end
            
            if  any( car.DF>car.floor )
                DF_up(car.DF(car.DF>car.floor)-1)=1;
            end
            if  any( car.DF<car.floor )
                DF_down(car.DF(car.DF<car.floor))=1;
                
            end
        end
        
        %Override  Inherited Method of DecisionMaker
        function updateCarStates(~,cars,updateType)
            for i = 1:length(cars)
                if mod(cars(i).floor,1)==0%(abs(floor(cars(i).floor)-cars(i).floor)==0)
                    cars(i).updateState(updateType);
                end
            end
        end
        
    end
    
end