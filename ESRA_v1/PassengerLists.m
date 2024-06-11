classdef PassengerLists < HallCallLists &  matlab.mixin.Copyable
    
    properties
        travelling 
    end
    
    methods
          function passengerLists = PassengerLists()
          Passenger.resetId();   
          passengerLists.travelling={Passenger.empty,Passenger.empty};            
          end
         
        function transfer(passengerLists,passenger,transerToList)
            dir = passenger.direction;
            if  strcmp(transerToList,'travelling')   % from waiting list to serving list
                passengerLists.waiting{dir}([passengerLists.waiting{dir}.id]==passenger.id)=[];
                passengerLists.travelling{dir}=[passengerLists.travelling{dir} passenger];
            elseif strcmp(transerToList,'served') % from travelling to served
                passengerLists.travelling{dir}([passengerLists.travelling{dir}.id]==passenger.id)=[];
                passengerLists.served{dir}=[passengerLists.served{dir} passenger];
             elseif strcmp(transerToList,'waiting') % from served(recorded) to waiting                 
                passengerLists.served{dir}([passengerLists.served{dir}.id]==passenger.id)=[];
                passengerLists.waiting{dir}=[passengerLists.waiting{dir} passenger];               
             end
        end
        
    end
    
end