classdef Experiment
    
    methods
        
        function dataConf=run(experiment,startData)
            rng(70);                                           % set seed for random number generator(optional)  
            guiData=guidata(mygui);                            % get user data from gui
            
            simulator = Simulator(startData);                  % create a Simulator object
            controller = Controller(startData.decisionMaker);  % create a Controller object
            dataConf = DataConf(startData);                    % create a DataConf object according to the user input(from gui) or provided configuration file
            
            tt=0;counter=0;
            
            for nbc=1:length(dataConf.BUILDING)             % repeat for the number of buildinging configurations
                building = dataConf.BUILDING{nbc};
                for ncc=1:length(dataConf.CAR)                % repeat for the number of car configurations
                    cars=dataConf.CAR{ncc};
                    
                    for incIndex=1:size(dataConf.TRAFFIC,1)                % repeat for each (incoming, interfloor, outgoing) traffic combination
                        for intIndex=1:size(dataConf.TRAFFIC,2)            % (outgoing traffic is determined from  (incoming,interfloor) pair) 
                            traffic = dataConf.TRAFFIC{incIndex,intIndex};
                            if ~isempty(traffic)                           % check valid traffic configuration in the Traffic configuration matrix
                                
                                traffic.setRouteProbability(building);     % set route,arrival and destination probabilities
                                controller.setTraffic(traffic);
                                for nsc=1:simulator.numOfSimulations       % repeat for the maximum number of simulations
                                    indices=struct('nbc',nbc,'ncc',ncc,'int',intIndex,'inc',incIndex,'nsc',nsc);
                                    tic;
                                    
                                    [cars,HC,P]=experiment.resetVariables(simulator,building,cars,dataConf,traffic,indices); % reset cars, HC, P and simulator time before each new simulation
                                                                        
                                    if(dataConf.isInitialDispatch==0 )
                                        %tic %measure a calculation
                                        controller.runDecisionProcess(building,cars,HC,P);
                                        controller.updateCarStatesForNextDecision(cars);
                                        %tc=toc;tt=tt+tc;clc,%counter=counter+1;  %display("INITIAL DISPATCH 0"),pause
                                    end
                                    
                                    %While there is an waiting car(transferring passenger or moving) or maximum simulation time is not reached
                                    while any([cars.stopOverCounter]) || any([cars.DF]) || any([cars.state])  ||  (simulator.time<traffic.getSetEndTime() && simulator.arrivalRate~=0) || ~isempty(P.waiting{1}) || ~isempty(P.waiting{2})
                                        simulator.checkNewPassenger(HC,P,traffic,indices);
                                        if mod(simulator.time,simulator.arrivalRate)==0 ||  mod(simulator.time,simulator.decisionPeriod)==0  %if a new passenger has arrived or redispatching period is reached
                                        %if  (mod(Sim.time,Sim.arrivalRate)==0)   %run decision process only if a new passenger has arrived
                                            controller.runDecisionProcess(building,cars,HC,P);
                                        end
                                        simulator.displayTraffic(building,traffic,cars,HC,P,guiData);        %Display simulations if the display option is selected
                                         controller.operate(cars,simulator,HC,P);
                                        controller.updateCarStatesForNextDecision(cars);
                                    end
                                    
                                    simulator.recordData(HC,P,cars,dataConf,indices);
                                    tc=toc;tt=tt+tc;counter=counter+1;%measure a single simulation
                                end
                                fprintf('inc:%d int %d building % d. counter: %d Sim counter: %.3f Total time: %.2f \n',incIndex,intIndex,nbc,counter,tc,tt);%pause(.5)
                                
                            end
                            
                        end
                    end
                end
            end
            assignin("base","dataConf",dataConf); % save data at workspace
          
        end
        
        function [cars,HC,P]= resetVariables(~,simulator,building, cars,dataConf,traffic,indices)
            
            simulator.time=0;    % reset simulation time at each simulation start
            Passenger.resetId(); % reset static Passenger id
            HallCall.resetId();  % reset static HallCall id

            %reset CAR, active HC and active P for new simulation
            switch simulator.dataType
                case {1,2}  %1: New Data 2: Recorded Data
                    HC=HallCallLists();
                    for i =1:length(cars)
                        cars(i)=copy(cars(i));
                    end
                    %reset floor
                    %CAR.floor=randi(Build.nf,1,nc);           %random car floors
                    %CAR.floor=round((1:nc)*Build.nf/(nc+1)); %CAr floors for : Equal intervals
                    %CAR.floor=Build.nf/2*ones(1,nc);         %cars start from mid-floor
                    if length(cars)>1
                        evenlyDistributedFloors = num2cell( round(linspace(1,building.nf,length(cars) )) );
                        [cars.floor] = deal( evenlyDistributedFloors{:}) ; %evenly distributed cars
                    elseif length(cars)==1
                        cars(1).floor =randi(building.nf);% aynı sonuçları elde ettiğimizi ispatlamak için 1 yapıyoruz.
                    end
                    for i =1:length(cars)
                        cars(i).reset();
                    end
                    
                    if simulator.dataType==1 % 1:New data
                        P=PassengerLists();
                        for i = 1:Traffic.getSetNumInitialPassengers()-1
                            simulator.generatePassenger(HC,P,traffic);
                        end
                        
                    else                     %2: recorded data
                        [nbc, ncc, inc, int, nsc] = deal(indices.nbc,indices.ncc,indices.inc,indices.int,indices.nsc);
                        P=copy(dataConf.RECold{nbc, ncc, inc, int, nsc}.P);
                        simulator.checkNewPassenger(HC,P,traffic,indices);% load  P_waiting from P_served
                    end
                case 3                      %3: New data with custom initials
                    cars= copy(dataConf.initialCars); % cars at initial state
                    P=copy(dataConf.initialP);        % passengers at initial state
                    HC=copy(dataConf.initialHC);      % hall calls at initial state
            end
            
        end
        
        
        
    end
end