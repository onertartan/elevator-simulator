function configurationNewDataWithCustomInitials(startData,dataConf)
table = readcell(startData.fileName);

%data = readcell("test.xlsx"); %readcell("test6floor.xlsx");
table=table(3:end,:);
nf = cell2mat(table(1,1));
dataConf.BUILDING{1} = Building(nf);
%Column explanation
%1:Build configuration
%2:Number of cars
%3:Park algorithm
%4:Car initials
%5:Car floors
%6:Car states
%7:Car destination floors
%8: P_1_floor ( passenger floors going up)
%9: Destinations of passengers going up
%10: Cars assigned to passengers going up 
%11: P_2_floor( passenger floors going down)
%12:Destinations of passengers going down (P_2_DF)
%13: Incoming traffic
%14: Inter-floor traffic
%15: Outgoing traffic
 
inc=cell2mat(table(1,2));
int=cell2mat(table(1,3));
out=cell2mat(table(1,4));
dataConf.TRAFFIC{1,1}=Traffic(inc,int);
%1-Read car initials from file
startData.nc = cell2mat(table(1,5));
startData.parkAlg = cell2mat(table(1,6));
for i=1:startData.nc
   cars(i) = Car(startData,i);
end

startData.carInitials = cell2mat(table(1,7));
if(startData.carInitials =="true")
    startData.carFloors = cell2mat(table(1:end,8));
    startData.carStates = cell2mat(table(1:end,9));
   
    for i=1:startData.nc
        
        try
            startData.carDestinationFloors{i} = sscanf(cell2mat(table(i,10)), '%d ')';
        catch
            try
                startData.carDestinationFloors{i} = cell2mat(table(i,10));
            catch
                startData.carDestinationFloors{i} = [];
            end
        end
        cars(i).floor =  startData.carFloors(i);
        cars(i).previousFloor= cars(i).floor;
        cars(i).state = startData.carStates(i);
        cars(i).DF =  startData.carDestinationFloors{i};          
    end
end

%2-Read car initials from file
P_initials(2) = struct("floor",[],"DF",[],"car",[]);
HC_initials(2)=struct("floor",[],"car",[]);

col_index=10;
P = PassengerLists();
HC = HallCallLists();

for i=1:2
    
    C= table(1:end,(i-1)*3+col_index+1);
    C( cellfun( @(c) isa(c,'missing'), C ) ) = {[]};
    P_initials(i).floor=cell2mat(C)';
    
    C= table(1:end,(i-1)*3+col_index+2);
    C( cellfun( @(c) isa(c,'missing'), C ) ) = {[]};
    P_initials(i).DF=cell2mat(C)';
    
    C= table(1:end,(i-1)*3+col_index+3);
    C( cellfun( @(c) isa(c,'missing'), C ) ) = {[]};
    P_initials(i).car=cell2mat(C)';
    
    [P_initials(i).floor,pind]=sort(P_initials(i).floor);
    P_initials(i).DF=P_initials(i).DF(pind);
    
    if  ~isempty(P_initials(i).floor)
        [HC_initials(i).floor,hind]=unique(P_initials(i).floor);
    end
    
    if ~isempty(P_initials(i).car)
        P_initials(i).car=P_initials(i).car(pind);
        HC_initials(i).car=P_initials(i).car(hind);
    else
        HC_initials(i).car=zeros(length(HC_initials(i).floor),1);
    end
    
    for j=1:length(P_initials(i).floor)
        P_initials(i).floor
        passenger = Passenger(P_initials(i).floor(j),0,P_initials(i).DF(j)); %floor,QJT, DF
        try
        passenger.carId=P_initials(i).car(j);
        catch
            
        end            
        P.add(passenger );
    end
       
     for j=1:length(HC_initials(i).floor)
         hc = HallCall(HC_initials(i).floor(j),0,i); %floor,QJT
         hc.carId = HC_initials(i).car(j) ;
         HC.add(hc);
         
    end
    
end 
 
dataConf.isInitialDispatch=(~isempty(P_initials(1).car) || ~isempty(P_initials(2).car)); %%1 if already assigned cars %%0 if cars not assigned

for i=1:length(cars)
    if ~isempty([cars(i).DF])
        
        for df=cars(i).DF   %add passengers in the car
            passenger= Passenger(cars(i).floor,0,df);
            passenger.board(cars(i).id,0);
            cars(i).P.transfer(passenger,"travelling");
            cars(i).load=cars(i).load+1;
        end
        
    end
    
end

dataConf.CAR{1}=cars; 
dataConf.initialCars=cars;
dataConf.initialP=P;
dataConf.initialHC=HC; 