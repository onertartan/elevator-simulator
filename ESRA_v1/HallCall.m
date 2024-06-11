classdef HallCall < matlab.mixin.Heterogeneous & handle  &  matlab.mixin.Copyable
 
    properties
       id int8
       carId int8=0
       floor
       direction  int8
       QJT      % hall call registration time(Queue joint time for Passenger class)
       BT       % car's arrival time at hall call floor
       WT  = 0; % system response time (waiting time for Passenger class)
    end
    
    methods
        function hallCall = HallCall(floor,QJT,direction)
            hallCall.floor = floor;
            hallCall.QJT = QJT;
            hallCall.direction = direction;
            hallCall.id = hallCall.idCounter();
        end
        
        function  board(hallCall,carId,currentTime)
            hallCall.carId=carId;
            hallCall.BT=currentTime;
            hallCall.WT=hallCall.BT-hallCall.QJT;
        end
    end  
    
     methods(Static)
        function resetId()
           HallCall.idCounter(0);
        end
        function out=idCounter(resetValue)   
            persistent var;
            if isempty(var) 
                var = 1;
            else
                var=var+1;
            end          % initial value
            
             if nargin < 1; out = var; return; end  % get value
             var = resetValue;                              % REset value
                out=var;
            end
        end
    
end