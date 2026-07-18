classdef HallCallLists < matlab.mixin.Copyable
     
    properties
    %waiting : cell array (1st array:up hall calls, 2nd array down hallcalls)
    %served : cell array (1st array up hall calls, 2nd array down hallcalls)
        waiting = {HallCall.empty,HallCall.empty};
        served  = {HallCall.empty,HallCall.empty};
    end
    
    methods
        
        function add(hallCallLists,hallCall)
            %adds hallCall to the corresponding cell of waiting
            dir = hallCall.direction;
            hallCallLists.waiting{dir}=[hallCallLists.waiting{dir} hallCall];
        end
        
        function transfer(hallCallLists,hallCall)
          %moves hallCall object from the cell 'dir' of "waiting"  to the cell 'dir' of  the "served"  
            dir = hallCall.direction;
            hallCallLists.served{dir}=[hallCallLists.served{dir} hallCall];
            hallCallLists.waiting{dir}([hallCallLists.waiting{dir}.id]==hallCall.id)=[];
        end
        
        function clearCarIds(hallCallLists)
            %clear id's of waiting hall calls
            for dir=1:2
                for k=1:length(hallCallLists.waiting{dir})
                    hallCallLists.waiting{dir}(k).carId=0;
                end
            end
        end
        
    end
    
end
