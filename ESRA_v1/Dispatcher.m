classdef (Abstract) Dispatcher<DecisionMaker
    
    methods(Abstract)
           dispatch(dispatcher,building,cars,HC,P);
    end
    
    methods
          function run(dispatcher,building,cars,HC,P )
              
            dispatcher.dispatch(building,cars,HC,P);
            dispatcher.updateCarServiceLists(cars,HC,P);
            dispatcher.updateCarStates(cars,"fixed");
          end             
    end
    
end
    