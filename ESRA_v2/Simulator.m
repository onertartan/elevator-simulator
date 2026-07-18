classdef Simulator< handle
    properties
        % instance variables
        dataType
        
        time = 0
        refTime
        endTime
        
        arrivalRate  
        decisionPeriod = 1
        Ts = 1

        numSimulations  
        numMaxSimulations
        confIndices
        numMaxConfs
        totalRunCounter = 0
        totalRunTime = 0
        lastRunTime = 0
        
        % static variables(used through setget methods below)
        %speed
        %displayTrafficFlow
        %displayTrafficData
    end
    
    methods (Static)    % STATIC  setget methods for static variables speed, displayTrafficFlow and displayTrafficData
        function speed = setgetSpeed(speed)
            persistent Var;
            if nargin
                Var = speed;
            end
            speed = Var;
        end
       
        function backgroundImage=getSetBackgroundImage(image)
            persistent Var;
            if nargin
                Var = image;
            end
            backgroundImage = Var;
        end    
        function displayTrafficFlow = getSetDisplayTrafficFlow(displayTrafficFlow)
            persistent Var;
            if nargin
                Var = displayTrafficFlow;
            end
            displayTrafficFlow = Var;
        end
        function displayTabularData = getSetDisplayTabularData(displayTabularData)
            persistent Var;
            if nargin
                Var = displayTabularData;
            end
            displayTabularData = Var;
        end

        function out=getSetEndTime(endTime)   % first static "variable"
            persistent var;
            if nargin
                var = endTime;
            end
            out = var;
        end
        function clearScreen(app)
            cla(app.displayFlowUIAxes,"reset");
            imagesc(app.displayFlowUIAxes,  Simulator.getSetBackgroundImage());%imshow(a, 'Parent', displayFlowUIAxes);%   
        end
        
    end
    
    methods
        function simulator = Simulator(startData,numMaxConfs)      % constructor 
            simulator.refTime =startData.refTime;                   %simulation reference time(to remove initial transition effect)
            simulator.endTime =startData.endTime;                   %simulation reference time(to remove initial transition effect)
            simulator.arrivalRate=startData.arrivalRate;            %passenger arrival rate
            simulator.numSimulations=startData.numSimulations;      %number of simulations
            simulator.decisionPeriod=startData.decisionPeriod;                  %simulation dispatching period
            simulator.dataType=startData.dataType;
            simulator.numMaxSimulations=numMaxConfs.Nbc*numMaxConfs.Ncc*numMaxConfs.Nicc*numMaxConfs.Nifc*simulator.numSimulations;
            simulator.numMaxConfs=numMaxConfs; 
        end
                
        function checkNewPassenger(simulator,HC,P,traffic)
            %1 New traffic %2 Recorded Traffic %3 Static Traffic
            switch(simulator.dataType)
                case 1 %1- In new traffic; generate passenger according to arrival rate          
                    if mod(simulator.time,simulator.arrivalRate)==0 && simulator.time<Simulator.getSetEndTime() && simulator.time>0
                         simulator.generatePassenger(HC,P,traffic);                       
                    end
                case 2   %2- In recorded traffic; check the new calls at current time
                    for dir=1:2
                        if(any([P.served{dir}.QJT]==simulator.time))
                            index=find([ P.served{dir}.QJT]==simulator.time);
                            for i=length(index):-1:1
                                passenger=P.served{dir}(index(i));
                                P.transfer(copy(passenger),'waiting' ); %transfer from recorded(served) data to waiting data
                                  %copy is needed not to pass the handle(if handle is passed WT of the passenger is same in RECnew and RECold)                                                                       
                                                                                                                                                                                                                     
                                if ~any([HC.waiting{dir}.floor]==passenger.floor)
                                    hc = HallCall(passenger.floor,simulator.time,dir);
                                    HC.add(hc);
                                end
                            end
                        end
                    end
                case 3 % New traffic; generate passenger according to arrival rate
                    if simulator.arrivalRate~=0 && mod(simulator.time,simulator.arrivalRate)==0 && simulator.time<simulator.endTime  && simulator.time>0
                        simulator.generatePassenger(HC,P,traffic);
                    end
            end
        end
        
        function generatePassenger(simulator,HC,P,traffic)
            
            randomNumber=rand;
            cumPr=cumsum(traffic.Pr(:));
            shifted=reshape(circshift(cumPr,[1,-1]) ,size(traffic.Pr));
            cumPr=reshape(cumPr,size(traffic.Pr));
            [floor,DF]=find(randomNumber>shifted & randomNumber<cumPr );
            
            passenger = Passenger(floor,simulator.time,DF);
            dir = passenger.direction;
            P.add(passenger);
            % if there is no HC at the passenger floor, generate a new HC
            if ~( any([HC.waiting{dir}.floor]==passenger.floor) )
                hc = HallCall(floor,simulator.time,dir);
                HC.add(hc);
            end
            
        end
        
        function recordData(~,HC,P,cars,dataConf,indices)
            [~,k]=sort([P.served{1}.QJT]);
            P.served{1}=P.served{1}(k);
            [~,k]=sort([P.served{2}.QJT]);
            P.served{2}=P.served{2}(k);
            [nbc, ncc, inc, int, nsc] = deal(indices.nbc,indices.ncc,indices.inc,indices.int,indices.nsc);
            dataConf.RECnew{nbc, ncc, inc, int, nsc}=Record(HC,P,cars);
        end
        
        function displayTraffic(simulator,building,traffic,cars,HC,P ,app,nsc)
            % display simulations if the display option is selected               
            if Simulator.getSetDisplayTrafficFlow() % get(handles2.displayTrafficFlowCB,"Value")
                %displayGui(building,traffic,cars,simulator,HC,P, displayFlowUIAxes);
                simulator.drawBackground(building.nf,length(cars),traffic,app.displayFlowUIAxes);
                simulator.drawCars(cars,app.displayFlowUIAxes,building.nf);
                simulator.drawHCs(P,HC,app.displayFlowUIAxes);
          %      pause(10/ 10^Simulator.setgetSpeed() ); %     pause(1);%        
            end
            if Simulator.getSetDisplayTabularData()
                simulator.fillCarTable(app,cars);
                simulator.fillPassengerTables(app,P);        % Monitor waiting passengers in the table
                simulator.fillResultsTable(app,HC,P,cars);          
            end
            simulator.fillCountersTable(app);   
            pause(10/ 10^Simulator.setgetSpeed() ); %
         end

        function drawCars(~,cars,displayFlowUIAxes,nf)
            numCars=length(cars);
            carColumnHeaders = arrayfun(@(x) ['Car-' num2str(x)], 1:numCars, 'UniformOutput', false);     
            %plot(displayFlowUIAxes, 1:numCars+2, rand(1, numCars+2),'Parent', displayFlowUIAxes);
             for id=1: length(cars)
                 %Show Cars
                 rectangle('Position',[id+1.5 cars(id).floor-.5 1 1],'FaceColor',Car.colors(id),'Parent', displayFlowUIAxes);
                 %Show Car Destination Floors
                 if (~isempty(cars(id).DF) )
                     for j=1:length(cars(id).DF)
                         pos=[id+1.5 cars(id).DF(j)-.5 1 1];
                         rectangle('Position',pos,'Curvature',[1 1],'Parent', displayFlowUIAxes);
                     end
                 end
                 %Show Car Directions
                 if(cars(id).stopOverCounter~=0)
                     line([id+1.5 id+2.5],[cars(id).floor cars(id).floor],'LineWidth',2,'Color','w','Parent', displayFlowUIAxes)
                 else
                     x_coords=[id+1.5 id+2 id+2.5];
                     y_coords=[cars(id).floor cars(id).floor+cars(id).state*0.5 cars(id).floor];
                     line(x_coords,y_coords,'LineWidth',2,'Color','w','Parent', displayFlowUIAxes);

                 end
                 textX=id+2;textY=cars(id).floor;
                 text(textX,textY,num2str(cars(id).load),'FontSize',18,'Parent', displayFlowUIAxes);%%%%

             end
             xlabels={['Up';'Down';carColumnHeaders(1:numCars)']};%
             set(displayFlowUIAxes,'XAxisLocation','bottom','units','normalized','Position',[0.15 0.28 .25 .6],...  %[0.12 0.25 .25 .6]
                 'XTick',[1:numCars+2],'XTickLabel',xlabels{1}, 'YDir','normal','YTick',1:nf,'LineWidth',2, 'Visible', 'on')
         end

        function drawHCs(~,P,HC,displayFlowUIAxes)          
             for i=1:2
                 x_coords=[-.5 0 .5]+i;
                 for k=1:length(HC.waiting{i})
                     y_coords=[HC.waiting{i}(k).floor HC.waiting{i}(k).floor+1.5-i HC.waiting{i}(k).floor];
                    if HC.waiting{i}(k).carId==0 %if not a car has been assigned yet
                        selectedColor="w";
                    else
                     selectedColor = Car.colors(HC.waiting{i}(k).carId);
                    end
                     rectangle('Position',[i-.5 HC.waiting{i}(k).floor-.5  1  1],'FaceColor',selectedColor,'Curvature',[1,1],'Parent', displayFlowUIAxes);
                     line(x_coords,y_coords,'LineWidth',2,'Color','w','Parent', displayFlowUIAxes);
                     textX=i ;textY=HC.waiting{i}(k).floor;
                     text(textX,textY,num2str(sum([P.waiting{i}.floor]==HC.waiting{i}(k).floor )),'FontSize',18,'Parent', displayFlowUIAxes  );
                 end
             end
         end
            function drawBackground(simulator,nf,numCars,traffic,displayFlowUIAxes)
            %Show Assigned Hall Calls
            b=ones(nf,2,3);
            b(1:2:nf,1,:)=0.85*ones(round(nf/2),1,3);b(2:2:nf,1,:)=0.7*ones(floor(nf/2),1,3);
            b(1:2:nf,2,:)=0.7*ones(round(nf/2),1,3);b(2:2:nf,2,:)=0.85*ones(floor(nf/2),1,3);
            Simulator.getSetBackgroundImage([b ones(nf,numCars,3)]);  %ilk iki satırın (yukarı ve aşağıa çağrıların) background'u farklı renk.Asansörlerin backgroundu beyaz
            cla(displayFlowUIAxes,"reset");
            imagesc(displayFlowUIAxes,   Simulator.getSetBackgroundImage());%imshow(a, 'Parent', displayFlowUIAxes);%
            str=sprintf('%% %d incoming %% %d interfloor %% %d outgoing\n Simulation time: %d',traffic.inc,traffic.int,traffic.out,simulator.time);
            title(str,'Parent', displayFlowUIAxes)
        end

        function fillCarTable(~,app,cars)          
            numCars = length(cars);
            carColumnHeaders = arrayfun(@(x) ['Car-' num2str(x)], 1:numCars, 'UniformOutput', false);
            app.carTable.ColumnName = carColumnHeaders;
            formattedPositions = compose('%.1f', [cars.floor]); % format as cell array to show position with single decimal
            passengerFloors = arrayfun(@(i) strjoin(string([cars(i).HC.waiting{1}.floor, cars(i).HC.waiting{2}.floor]), ', ') , 1:numCars, 'UniformOutput', false);
            passengerFloors = string(passengerFloors);


            row_data = [formattedPositions; num2cell([cars.state]);  num2cell([cars.stopOverCounter]);num2cell([cars.load]) ;passengerFloors;num2cell([cars.tripTime]); num2cell([cars.numOfServedPassengers])];
            app.carTable.RowName = {'Car position'; 'Car State'; 'Stopover counter';"Car load";"Pickup floors";"Car trip time";"Number of served passengers"};
            app.carTable.Data  = row_data;
            s = uistyle('HorizontalAlignment', 'left');
            addStyle(app.carTable, s); % Apply to entire table
        end
        
        function fillPassengerTables(~,app,P)
            tables = [ app.passengerUpTable, app.passengerDownTable];
            for i=1:2
                numPassengers = length(P.waiting{i});
                if numPassengers
                   ids=[P.waiting{i}.id];
                    passengerColumnHeaders = arrayfun(@(x) ['id-' num2str(ids(x))], 1:numPassengers, 'UniformOutput', false);  
                    tables(i).ColumnName =passengerColumnHeaders;                  

                    row_data = [ [P.waiting{i}.floor];[P.waiting{i}.DF];[P.waiting{i}.QJT];[P.waiting{i}.WT];[P.waiting{i}.carId] ];
                    tables(i).RowName = {'Call Floor'; 'Destination Floor'; 'Queue join time';"Waiting time";"Car id"};
                    tables(i).Data  = row_data;    
               
                    tables(i).ColumnWidth = repmat({ 50 }, 1, numPassengers);   % All columns = 60px
                    s = uistyle('HorizontalAlignment', 'left');
                    addStyle(tables(i), s); % Apply to entire table
                else
                      % Clear the table when there are no passengers
                    tables(i).ColumnName = {};
                    tables(i).Data = {};
                    tables(i).RowName = {};
                end

            end

        end
     
        
        function fillCountersTable(simulator,app)
            %row_data = [nsc;num2cell(sum([cars.tripTime])); num2cell(sum([cars.numOfServedPassengers]))];
            idx =  simulator.confIndices ;
            maxIdx=simulator.numMaxConfs;
            % Calculate total time components
            totalSeconds = round(simulator.totalRunTime);
            hours = floor(totalSeconds / 3600);
            remainingSeconds = mod(totalSeconds, 3600);
            minutes = floor(remainingSeconds / 60);
            seconds = mod(remainingSeconds, 60);
            timeStr = sprintf('%d:%02d:%02d', hours, minutes, seconds);

            app.countersTable.Data = {
                sprintf('%d/%d', idx.nbc,maxIdx.Nbc), ...
                sprintf('%d/%d', idx.ncc, maxIdx.Ncc), ...
                sprintf('%d/%d', idx.inc * idx.int,maxIdx.Nicc *maxIdx.Nifc), ...
                sprintf('%d/%d', idx.nsc,simulator.numSimulations), ...
                sprintf('%d/%d', simulator.totalRunCounter, simulator.numMaxSimulations), ...
                timeStr
                };

        end

        function fillResultsTable(simulator,app,HC,P,cars) 
           % app.resultsTable.RowName = {"Car trip time";"Number of served passengers"} ;
           % row_data = [ num2cell(sum([cars.tripTime])); 
           %     num2cell(sum([cars.numOfServedPassengers]));
           %     length([HC.served{1}.WT HC.served{2}.WT]);
           %     mean([P.served{1}.WT P.served{2}.WT]);
           %     ];

           if simulator.dataType==3
                  p_up = P.served{1};p_down = P.served{2};
                  p_up_wt= [p_up([p_up.QJT]~=-1).WT]; p_down_wt = [p_down([p_down.QJT]~=-1).WT];
                  hc_up = HC.served{1};hc_down = HC.served{2};
                  hc_up_wt= [hc_up([hc_up.QJT]~=-1).WT]; hc_down_wt = [hc_down([hc_down.QJT]~=-1).WT];
             
                  app.resultsTable.Data  = { sprintf('%d', sum([cars.tripTime]) );                      %  Total car trip time
                   sprintf('%d', sum([p_up_wt p_down_wt]));    % Total passenger waiting time
                   sprintf('%d', sum([hc_up_wt hc_down_wt]));      % Total hall call waiting time
                   sprintf('%d',  length(p_up_wt)+  length(p_down_wt) );           % Number of served passengers
                   sprintf('%d', length(hc_up_wt)+  length(hc_down_wt));               % Number of responded hall calls
                   sprintf('%.2f', mean([cars.tripTime]) );                    % Average car trip time
                   sprintf('%.2f', mean([p_up_wt p_down_wt]));     % Average passenger waiting time
                   sprintf('%.2f', mean([hc_up_wt hc_down_wt])) } ;% Average hall call waiting time
           else

               app.resultsTable.Data  = { sprintf('%d', sum([cars.tripTime]) );                      %  Total car trip time
                   sprintf('%d', sum([P.served{1}.WT P.served{2}.WT]));    % Total passenger waiting time
                   sprintf('%d', sum([HC.served{1}.WT HC.served{2}.WT]));% Total hall call waiting time
                   sprintf('%d', sum([cars.numOfServedPassengers]));          % Number of served passengers
                   sprintf('%d', length(HC.served{1})+ length(HC.served{2}) ); % Number of responded hall calls
                   sprintf('%.2f', mean([cars.tripTime]) );                  % Average car trip time
                   sprintf('%.2f', mean([P.served{1}.WT P.served{2}.WT]));   % Average passenger waiting time
                   sprintf('%.2f', mean([HC.served{1}.WT HC.served{2}.WT])) } ;% Average hall call waiting time
            end
        
        end


    end
end