classdef Record <handle
    properties
        HC
        P
        cars
    end
    
     methods
        function record = Record(HC,P,cars)  %Constructor
          record.HC=HC;
          record.P=P;
          record.cars=cars;
        end
     end
    
end