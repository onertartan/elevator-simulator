classdef Simulator< handle
    properties
        % instance variables
        dataType
        
        time = 0
        refTime
        endTime
        
        arrivalRate
        numOfSimulations  
        decisionPeriod = 1
        Ts = 1
        
        % static variables(used through setget methods below)
        %speed
        %displayTrafficFlow
        %displayTrafficData
    end
    
    methods (Static)    % STATIC  setget methods for static variables speed, displayTrafficFlow and displayTrafficData
        function speed = setgetSpeed(speed)
            persistent Var;
            if nargin
                Var = speed;
            end
            speed = Var;
        end
        function displayTrafficFlow = setgetdisplayTrafficFlow(displayTrafficFlow)
            persistent Var;
            if nargin
                Var = displayTrafficFlow;
            end
            displayTrafficFlow = Var;
        end
        function displayTrafficData = setgetdisplayTrafficData(displayTrafficData)
            persistent Var;
            if nargin
                Var = displayTrafficData;
            end
            displayTrafficData = Var;
        end
    end
    
    methods
        function simulator = Simulator(startData)                  % constructor 
            simulator.refTime =startData.refTime;                   %simulation reference time(to remove initial transition effect)
            simulator.endTime =startData.endTime;                   %simulation reference time(to remove initial transition effect)
            simulator.arrivalRate=startData.arrivalRate;            %passenger arrival rate
            simulator.numOfSimulations=startData.numOfSimulations;  %number of simulations
            simulator.decisionPeriod=startData.Td;                  %simulation dispatching period
            simulator.dataType=startData.dataType;
        end
                
        function checkNewPassenger(simulator,HC,P,traffic,indices)
            %1 New traffic %2 Recorded Traffic %3 Static Traffic
            switch(simulator.dataType)
                case 1 %1- In new traffic; generate passenger according to arrival rate
                    if mod(simulator.time,simulator.arrivalRate)==0 && simulator.time<traffic.getSetEndTime()
                         simulator.generatePassenger(HC,P,traffic);                       
                    end
                case 2   %2- In recorded traffic; check the new calls at current time
                    for dir=1:2
                        if(any([P.served{dir}.QJT]==simulator.time))
                            index=find([ P.served{dir}.QJT]==simulator.time);
                            for i=length(index):-1:1
                                passenger=P.served{dir}(index(i));
                                P.transfer(copy(passenger),'waiting' ); %transfer from recorded(served) data to waiting data
                                  %copy is needed not to pass the handle(if handle is passed WT of the passenger is same in RECnew and RECold)                                                                       
                                                                                                                                                                                                                     
                                if ~any([HC.waiting{dir}.floor]==passenger.floor)
                                    hc = HallCall(passenger.floor,simulator.time,dir);
                                    HC.add(hc);
                                end
                            end
                        end
                    end
                case 3 % New traffic; generate passenger according to arrival rate
                    if simulator.arrivalRate~=0 && mod(simulator.time,simulator.arrivalRate)==0 && simulator.time<simulator.endTime  && simulator.time>0
                        simulator.generatePassenger(HC,P,traffic);
                    end
            end
        end
        
        function generatePassenger(simulator,HC,P,traffic)
            
            randomNumber=rand;
            cumPr=cumsum(traffic.Pr(:));
            shifted=reshape(circshift(cumPr,[1,-1]) ,size(traffic.Pr));
            cumPr=reshape(cumPr,size(traffic.Pr));
            [floor,DF]=find(randomNumber>shifted & randomNumber<cumPr );
            
            passenger = Passenger(floor,simulator.time,DF);
            dir = passenger.direction;
            P.add(passenger);
            % if there is no HC at the passenger floor, generate a new HC
            if ~( any([HC.waiting{dir}.floor]==passenger.floor) )
                hc = HallCall(floor,simulator.time,dir);
                HC.add(hc);
            end
            
        end
        
        function recordData(~,HC,P,cars,dataConf,indices)
            [~,k]=sort([P.served{1}.QJT]);
            P.served{1}=P.served{1}(k);
            [~,k]=sort([P.served{2}.QJT]);
            P.served{2}=P.served{2}(k);
            [nbc, ncc, inc, int, nsc] = deal(indices.nbc,indices.ncc,indices.inc,indices.int,indices.nsc);
            dataConf.RECnew{nbc, ncc, inc, int, nsc}=Record(HC,P,cars);
        end
        
        function displayTraffic(simulator,building,traffic,cars,HC,P,handles)
          
            % display simulations if the display option is selected               
            if Simulator.setgetdisplayTrafficFlow % get(handles2.displayTrafficFlowCB,"Value")
                displayGui(building,traffic,cars,simulator.time,HC,P,handles);
                pause(1/(2*Simulator.setgetSpeed ));
            else
                pause(.000000001);
            end
            
        end
        
    end
end