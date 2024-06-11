classdef Car < matlab.mixin.Copyable
    properties
        id int8
        state 
        floor =1
        previousFloor
        parkFloor = "N/A"
        parkAlgorithm = 1
    
        HC 
        P  
        DF = [] 
        %time parameters
        doorOpeningTime
        passengerTransferTime
        doorClosingTime
        stopOverTime
        %other
        numOfServedPassengers  int8 = 0
        numOfStops  int8 = 0
        stopOverCounter = 0
        tripTime = 0
        load  int8 = 0 
        
        capacity   int8
        velocity    % m/s
        velocityFps %floor per second
        
        HC_up_above = []
        HC_up_below = []
        HC_above     = []
                
        HC_down_above = []
        HC_down_below = []
        HC_below      = []
    end
    
    methods
        function car = Car(startData,id)  %Constructor
            car.id = id;
            car.doorOpeningTime = startData.doorOpeningTime;
            car.passengerTransferTime = startData.passengerTransferTime;
            car.doorClosingTime = startData.doorClosingTime;
            car.stopOverTime =  car.doorOpeningTime + car.passengerTransferTime + car.doorClosingTime;
            
            car.capacity = startData.carCapacity*startData.carCapacityFactor;
            car.velocity = startData.carVelocity;
            car.velocityFps = round(1/(startData.floorHeight/car.velocity),2) ;% floors per second
           
            reset(car);
        end
        
        function reset(car)
            
            car.previousFloor = car.floor;
            car.state = 0;
            
            car.stopOverCounter = 0;
            car.numOfStops = 0;
            car.tripTime   = 0;
            car.load = 0;
            car.numOfServedPassengers = 0;
            
            car.DF = [];
            car.HC= HallCallLists();
            car.P= PassengerLists();
            
            car.HC_up_above   = [];
            car.HC_up_below   = [];
            car.HC_down_above = [];
            car.HC_down_below = [];
            car.HC_above      = [];
            car.HC_below      = [];
        end
        
        function checkStopOver(car,HC,P,currentTime) %Boarding at passenger dest or park floor
            
            if  (car.isAtDF() || car.isAtHC())  && (car.previousFloor~=car.floor)            %(3)   ?
                car.numOfStops = car.numOfStops+1;
            end
            
            if car.isAtDF()           % if the current(reached) floor is at an CAR destination floor
                 car.dropoff(P,currentTime); 
            end
            
            if car.isAtHC()  %(1) If the car arrived at  an assigned HC floor
                 car.pickup(HC,P,currentTime);
            end
            
        end
        
        function result = isAtDF(car)
            result= any(car.DF==car.floor);
        end
        
        function result = isAtHC(car)
            result= ( car.state==1 && any([car.HC.waiting{1}.floor]==car.floor) )   || (car.state==-1 && any([car.HC.waiting{2}.floor]==car.floor) ) || (car.state==0 && (any([car.HC.waiting{2}.floor]==car.floor) || any([car.HC.waiting{1}.floor]==car.floor) ));   %(1) If the car arrived at  an assigned HC floor
        end
        
        function dropoff (car,P,currentTime)
            car.stopOverCounter=car.stopOverTime;                   % set the stopOverCounter for passenger transfer
            for dir=1:2
                
                if(~isempty(car.P.travelling{dir}))                                           %if there is a passenger in the same direction
                    passengers=car.P.travelling{dir}( [car.P.travelling{dir}.DF]==car.floor );
                   
                    for i=1:length(passengers)                      
                        passengers(i).alight(currentTime);
                        P.transfer(passengers(i),'served');    
                        car.P.transfer(passengers(i),'served');
                        car.load=car.load-1;                % decrease CAR load by 1
                        car.numOfServedPassengers=car.numOfServedPassengers+1;                      
                    end
                   
                end
                
            end
            
            car.DF((car.DF==car.floor))=[]; % Check if DF is not any passenger's df but a park floor
            
        end
        
        function pickup(car,HC,P,currentTime)
         
            if car.state==1 || (car.state==0 &&  any([car.HC.waiting{1}.floor]==car.floor) &&  ~any([car.HC.waiting{2}.floor]==car.floor) )
                dir=1;
            elseif car.state==-1 || (car.state==0 &&  ~any([car.HC.waiting{1}.floor]==car.floor) &&  any([car.HC.waiting{2}.floor]==car.floor) )
                dir=2;
            elseif car.state==0 && any([car.HC.waiting{1}.floor]==car.floor)   %?? Two Hall Calls emerge At the same time while car is idle, priority is given upwards
                dir=1;
            end
            
            hallCall = car.HC.waiting{dir}([car.HC.waiting{dir}.floor]==car.floor);
            car.HC.transfer(hallCall);  % find the related HC and delete from HC list
            HC.transfer(hallCall);       % find the related HC and delete from HC list
           
            index=find([car.P.waiting{dir}.floor]==car.floor );                  %(1)   find index i of the P
            if( (car.capacity-car.load) < length(index))                      %(2a)  if  available room is not enough for
                numOfAvailableSpace=(car.capacity-car.load);                                      %      all waiting PASSENGERS set x to available space
                HC.add(HallCall(car.floor,currentTime,dir));%  HC deleted above, but create a new HC %at the same floor
            else
                numOfAvailableSpace=length(index);                                                   %(2b)  else take all the PASSENGERS                                           
            end
            
            numOfAcceptablePassengers= min(numOfAvailableSpace,length(index));
            idx=index(1:numOfAcceptablePassengers);  
            passengers=car.P.waiting{dir}(idx);
            
            for i=1:length(passengers)
              P.transfer(passengers(i),'travelling');     
                passengers(i).board(car.id,currentTime);
              car.P.transfer(passengers(i),'travelling')
            
              car.DF=unique([car.DF  passengers(i).DF]); %(3e)  Add distinct  elements of  new PASSENGERS' DF to CAR.DF
              car.load=car.load+1;          %(3f)  increase CAR load
              car.stopOverCounter=car.stopOverTime; %(3g)            
            end
            
        end
        
        function updateState(car,updateType)
            if   strcmp(updateType,'flexible')
                if any(car.DF> car.floor )
                    car.state=1;
                elseif any(car.DF<car.floor)
                    car.state=-1;
                else
                    car.state=0;
                end
            end
            
            if   strcmp(updateType,'fixed')
                %If HC_assignment is fixed HCs determine direction, otherwise
                %car can reverse direction if it does not have car call(DF)
                switch car.state
                    case 1
                        if(~any(car.DF>car.floor) && isempty(car.HC_above) )           %(1A)if the car does not have a DF and if an above call is not assigned to the car
                            car.state=0;                                         %(1A)set car state to 0 (car is IDLE)
                            if(~isempty(car.HC_below))                           %(1B)if the car has a below call
                                car.state=-1;                                      %set the car state to -1
                            end
                        end
                    case -1
                        if(~any(car.DF<car.floor) && isempty(car.HC_below) )   %(2A)if the car does not have a DF and if an above call is not assigned to the car
                            car.state=0;                                          %(2A)set car state to 0 (car is IDLE)
                            if( ~isempty(car.HC_above) )                     %(2B)if the car has a below call
                                car.state=1;                                     %set the car state to 1    end
                            end
                        end
                    case 0
                        car.updateAboveBelowHCs();
                        min_above=min([car.HC_up_above.floor car.HC_down_above.floor ]);
                        max_below=max([car.HC_up_below.floor  car.HC_down_below.floor ]);
                        if any(car.DF> car.floor )
                            car.state=1;
                        elseif any(car.DF<car.floor)
                            car.state=-1;
                        elseif(~isempty(min_above) && ~isempty(max_below))
                            u=min_above;%u=min(min_above,2*build.nf);
                            d=max_below;%d=max(max_below,-build.nf);
                            if( abs(u-car.floor)>abs(d-car.floor))
                                car.state=-1;%display('u an d'),CAR.HC_list_ups_below{i},above,below,u,d
                            else
                                car.state=1;
                            end
                        elseif((~isempty(min_above) && isempty(max_below)))
                            car.state=1;
                        elseif(isempty(min_above) && ~isempty(max_below))
                            car.state=-1;
                        end
                        
                end
            end
            
        end
        
        function updateServiceList(car,HC,P)
                index=([HC.waiting{1}.carId]==car.id);
                car.HC.waiting{1}=  HC.waiting{1}(index) ;   %i. asansöre atanmış yukarı çağrılar
                index=([P.waiting{1}.carId]==car.id);
                car.P.waiting{1}=  P.waiting{1}(index) ;   %i. asansöre atanmış yukarı yolcular
                
                index=( [HC.waiting{2}.carId]==car.id );
                car.HC.waiting{2}= HC.waiting{2}(index) ;  %i. asansöre atanmış aşağı çağrılar 
                index=([P.waiting{2}.carId]==car.id);
                car.P.waiting{2}=  P.waiting{2}(index) ;   %i. asansöre atanmış aşağı yolcular
        end
        
        function updateAboveBelowHCs(car)
            %Update above below lists according to new car floors
            if ~isempty(car.HC.waiting{1})
            car.HC_up_above = car.HC.waiting{1}([car.HC.waiting{1}.floor]>=car.floor);
            car.HC_up_below = car.HC.waiting{1}([car.HC.waiting{1}.floor]<car.floor);
            else
                car.HC_up_above =HallCall.empty;
                car.HC_up_below = HallCall.empty;
            end
            
           if ~isempty(car.HC.waiting{2})
           
            car.HC_down_below = car.HC.waiting{2}([car.HC.waiting{2}.floor]<=car.floor);
            car.HC_down_above = car.HC.waiting{2}([car.HC.waiting{2}.floor]>car.floor);
           else
               car.HC_down_below =HallCall.empty;
               car.HC_down_above =HallCall.empty;
           end
            
        end
  
        function car=park(car,timeStep)
            if ~isstring(car.parkFloor) %if park floor is not "N/A"(option 1 in the gui)
                car.floor = car.floor+sign(car.parkFloor-car.floor)*car.velocityFps*timeStep;
            end
        end
        
        function move(car,timeStep)
            car.previousFloor=car.floor;
            car.floor = car.floor+car.state*car.velocityFps*timeStep;  
        end
        
    end
end