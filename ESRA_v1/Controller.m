classdef Controller<handle
    
    properties
        decisionMaker
    end
    
    methods
        function controller = Controller(decisionMaker)  %Constructor
            controller.decisionMaker=decisionMaker;
        end
        
        function runDecisionProcess(controller,building,cars,HC,P)
             controller.decisionMaker.run(building,cars,HC,P);
        end
        
         function  updateCarStatesForNextDecision(controller,cars)
            controller.decisionMaker.updateCarStates(cars,controller.decisionMaker.stateUpdateTypeForNextDecision);
         end
       
        function operate(~,cars,simulator,HC,P)
            numOfCars = length(cars);
            
            for i=1:numOfCars
                 cars(i).checkStopOver(HC,P,simulator.time);
            end
            
            for i=1:numOfCars
                if(cars(i).stopOverCounter~=0)                 %(a) If the car is stopped(a passenger is entering or leaving)
                    cars(i).stopOverCounter=cars(i).stopOverCounter-simulator.Ts; %decrease the stopOverCounter(count back to zero)
                    %If a new call is assigned, set new Parking floor
                    %         if(cars(1).parkAlg==3)
                    %             randomNumber=rand;
                    %             cumPa=cumsum(sim.Pa(:));
                    %             shifted=reshape(circshift(cumPa,[1,-1]) ,size(sim.Pa));
                    %             shifted(1)=0;
                    %             cumPa=reshape(cumPa,size(sim.Pa));
                    %             cars(i).PF=find(randomNumber>shifted & randomNumber<cumPa );
                    %         end
                elseif ~isstring(cars(i).parkFloor) && cars(i).state==0 && cars(i).floor~=cars(i).parkFloor                                       %(b) if the car is idle(stopOverCounter is zero) skip the for loop
                    cars(i) = cars(i).park(simulator.Ts);
                elseif cars(i).state~=0
                    cars(i).move(simulator.Ts); %(c) if the car is in a moving state, update the position
                else
                    continue
                end
                
                cars(i).tripTime=cars(i).tripTime+simulator.Ts;
            end
            
            for dir=1:2
                if(~isempty(HC.waiting{dir}))   %Increment the waiting times of waiting calls
                   
                    a=[HC.waiting{dir}.WT]+simulator.Ts;   % dir=1 for upwards, dir=2 for downwards
                    a=num2cell(a);                 
                    [HC.waiting{dir}.WT]=a{:};      
                end
                
                for passenger= P.waiting{dir}               %Increment the waiting times of waiting calls
                    passenger.WT=passenger.WT+simulator.Ts; %  dir=1 for upwards, dir=2 for downwards)
                end
            end
            
            simulator.time=simulator.time+simulator.Ts;
            
        end       
        
        function setTraffic(controller,traffic)
            controller.decisionMaker.setTraffic(traffic)        
        end
        
    end
end