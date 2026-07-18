classdef Passenger < HallCall
 
    properties
       DF   % destination floor
       DAT % destination arrival time
       TrT  % transit time (~travel time)
       TTD % travel time to destination (~journey time)      
    end
    
    methods
        function passenger = Passenger(floor,QJT,DF)
             passenger@HallCall(floor,QJT, ceil( abs(sign(DF-floor)-.5)) )
             passenger.DF=DF;
        end   
        
        function passenger = alight(passenger,currentTime)
             passenger.DAT=currentTime;                % Destination arrival time
             passenger.TTD=passenger.DAT-passenger.QJT;  %Travel time to destination (total time)
             passenger.TrT=passenger.DAT-passenger.BT;  %Travel time to destination (total time)
        end
        
    end
    
    methods(Static)
        function resetId()  %id i
           Passenger.idCounter(0);
        end
        function out=idCounter(resetValue)   % first static "variable"
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