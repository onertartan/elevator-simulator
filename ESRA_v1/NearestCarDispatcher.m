classdef NearestCarDispatcher<Dispatcher
    
    properties
        FS =cell(1,2);%figure of suitability
    end
    
    methods
        
        %Overriden inherited abstract method from DecisionMaker class (last parameter is ~ because NearestCar method does not use Traffic info)
        function dispatch(dispatcher,building,cars,HC,P,~) %Calculate FS and dispatch cars (assign calls to cars)  
         
            dispatcher.FS={[],[]};
           
            for dir=1:2 
                numOfCars = length(cars);
                numOfHCs=length(HC.waiting{dir}); 
                f=zeros(numOfHCs, numOfCars);    %figure of suitability
                d=zeros(1,numOfCars);            %distances
                assignedCars=zeros(1,numOfHCs);
                 
                for i=1:numOfHCs
                    fmax=0;
                    hallCall=HC.waiting{dir}(i);
                    
                    for j=1:numOfCars
                         
                          d(j) =hallCall.floor -cars(j).floor; %i. asansör ile j. çağrı arasındaki fark                         
                          f(i,j) = dispatcher.calculateFS(hallCall,cars(j),building.nf,d(j));
                        
                        if(f(i,j)>fmax)
                            assignedCars(i)=j;fmax=f(i,j);
                        elseif(f(i,j)==fmax)
                            
                            if(d(j)<d(assignedCars(i)))
                                assignedCars(i)=j;
                            elseif(d(j)==d(assignedCars(i)) && cars(j).stopOverCounter<cars(assignedCars(i)).stopOverCounter)
                                assignedCars(i)=j;
                            end
                        end
                        
                    end
                end
                
                a=num2cell(assignedCars);       
                if ~isempty(HC.waiting{dir})
                    [HC.waiting{dir}.carId]=a{:};  
                    for i=1:length(HC.waiting{dir})
                         query= [P.waiting{dir}.floor]==HC.waiting{dir}(i).floor; 
                         b=num2cell (ones(1,length(query))*assignedCars(i));
                        [P.waiting{dir}(query).carId]=b{:};
                    end
                    
                    dispatcher.FS{dir}=f;
                 
                end 
               
                
            end
             
        end
        
        function fs=calculateFS(~,hallCall,car,nf,d )
                                   
            if(sign(d)*car.state==-1 ||  (d==0 && car.state*hallCall.direction==-1)) %car is moving away
                fs=1;
            elseif(car.state==hallCall.direction)     %HallCall and car have the same direction (car is approaching) 
                fs=nf+1-abs(d);
            else                     %HallCall and car have the opposite direction but the car is approaching Or the car is idle.
                fs=nf-abs(d);
            end
            
        end
         
    end
    
end