classdef (Abstract) DecisionMaker<handle
    
    properties
        stateUpdateTypeForNextDecision
        availableInformation
    end
    
    methods(Abstract)
        run(decisionMaker,building,cars,HC,P);
    end
    
    methods
        
        function  decisionMaker = DecisionMaker(stateUpdateTypeForNextDecision,availableInformation)
            decisionMaker.stateUpdateTypeForNextDecision=stateUpdateTypeForNextDecision;
            decisionMaker.availableInformation=availableInformation;
        end
        
        function  updateCarStates(~,cars,updateType)
            for i=1:length(cars)
               cars(i).updateState(updateType);
            end
        end
        
        function   updateCarServiceLists(~,cars,HC,P)
            for i=1:length(cars)
                cars(i).updateServiceList(HC,P);
            end
        end
        
         function setTraffic(decisionMaker,traffic)
          
        end
    end
    
end