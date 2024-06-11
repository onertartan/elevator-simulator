function displayGui(build,traffic,cars,time,HC,P,handles)

numOfCars = length(cars);

carColumnHeader=cell(1,numOfCars+1);
for  i=1:numOfCars 
carColumnHeader{i}=['Car ' num2str(i)];
end

carColumnHeader{i+1}='Total';
 
%Update Car Table 1
try
set(handles.carTable1,'Data',[cars.floor;cars.state;cars.stopOverCounter],'ColumnName',carColumnHeader(1:numOfCars));
catch
    
end
%Update (Car table 2) Assigned Hall Calls
car_struct.HC_listStr=cell(1,numOfCars);
for  i=1:numOfCars 
    car_struct.HC_listStr{i}=num2str([cars(i).HC.waiting{1}.floor cars(i).HC.waiting{2}.floor]);
end

% Car Destination Floors
car_struct.DFStr=cell(1,numOfCars);
for i=1:numOfCars
   car_struct.DFStr{i}= num2str(cars(i).DF);
end
set(handles.carTable2,'Data',[car_struct.HC_listStr;car_struct.DFStr]);
set(handles.carTable2,'ColumnName',carColumnHeader(1:numOfCars));

%Update (Car table 3)CAR.tripSys.time, CAR.numofstops
set(handles.carTable3,'Data',[[ [cars.numOfStops] sum([cars.numOfStops])];[ [cars.tripTime] sum([cars.tripTime])] ],'ColumnName',carColumnHeader);

%Update Hall Call Table 

for  i=1:numOfCars 
    FSrowTitle{i}=[num2str(i) '.car suitability'];
end
%ONEMLI: Dispatch interval hatası: F'yi görüntülemek dispatch update büyükse sorun oluyor. HC silinse de, F
%silinen HC varken hesaplandığı için dimension mismatch oluyor. Td ile Ts
%aynı yapılırsa sorun ortadan kalkıyor. Yani Dispatching interval ile display interval aynı olunca
%Özetle Nearest Car'da EXPLORER while içindeki 31 ifi kullanıp, 32' ifi yorumlamak hatayı gideriyor.
  %set(handles.hallCallTableUp,'Data',[[HC(1).waiting.floor];[HC(1).waiting.WT];[HC(1).waiting.AssignedCar];F{1}'],'RowName',['Waiting HC','HC Waiting(Response) Time','Allocated Car',FSrowTitle]);%STRUCT
  %set(handles.hallCallTableDown,'Data',[[HC(2).waiting.floor];[HC(2).waiting.WT];[HC(2).waiting.AssignedCar];F{2}'],'RowName',['Waiting HC','HC Waiting(Response) Time','Allocated Car',FSrowTitle]);%STRUCT
 
try
 set(handles.hallCallTableUp,'Data',[[HC.waiting{1}.floor];[HC.waiting{1}.WT];[HC.waiting{1}.carId]],'RowName',char('Waiting HC','HC Waiting(Response) Time','Allocated Car'));%STRUCT
 set(handles.hallCallTableDown,'Data',[[HC.waiting{2}.floor];[HC.waiting{2}.WT];[HC.waiting{2}.carId]],'RowName',char('Waiting HC','HC Waiting(Response) Time','Allocated Car'));%STRUCT
catch
    display("CANNOT FILL TABLE IN DISPLAYGUI ROW 49-50");
     qq=HC.waiting{1},
pp=HC.waiting{2},
end
%Update Hall Call Table
set(handles.time,'String',time);  
set(handles.parkEditText,'String',join(string([cars.parkFloor]), '-')   );

 
%Update Results Up
   
    if   ~isempty(P.served{1})
    set(handles.resultTableUp,'Data',fliplr([ [P.served{1}.floor];[P.served{1}.DF];[P.served{1}.QJT];[P.served{1}.WT];[P.served{1}.carId] ]) );
    end
%Update Results Down
    if   ~isempty(P.served{2})
    set(handles.resultTableDown,'Data',fliplr ([ [P.served{2}.floor];[P.served{2}.DF];[P.served{2}.QJT];[P.served{2}.WT];[P.served{2}.carId] ] ));  
    end

%Show Assgined Hall Calls
b=ones(build.nf,2,3);
b(1:2:build.nf,1,:)=0.85*ones(round(build.nf/2),1,3);b(2:2:build.nf,1,:)=0.7*ones(floor(build.nf/2),1,3);
b(1:2:build.nf,2,:)=0.7*ones(round(build.nf/2),1,3);b(2:2:build.nf,2,:)=0.85*ones(floor(build.nf/2),1,3);

a=[b ones(build.nf,numOfCars,3)];  %ilk iki satırın (yukarı ve aşağıa çağrıların) background'u farklı renk.Asansörlerin backgroundu beyaz
imagesc(a);
%Show Assgined Hall Calls
colors=['r','g','c','m','y','b','w' ,'k','r','g'];
 
for i=1:numOfCars
    %Show Cars
    rectangle('Position',[i+1.5 cars(i).floor-.5 1 1],'FaceColor',colors(i));

    %Show Car Destination Floors
         if (~isempty(cars(i).DF) )
               for j=1:length(cars(i).DF) 
                    pos=[i+1.5 cars(i).DF(j)-.5 1 1];
                    rectangle('Position',pos,'Curvature',[1 1]);
               end
         end
%Show Car Directions
if(cars(i).stopOverCounter~=0)
    line([i+1.5 i+2.5],[cars(i).floor cars(i).floor],'LineWidth',2,'Color','w')
else
    x_coords=[i+1.5 i+2 i+2.5];
    y_coords=[cars(i).floor cars(i).floor+cars(i).state*0.5 cars(i).floor];
    line(x_coords,y_coords,'LineWidth',2,'Color','w');
    
end
    textX=i+2;textY=cars(i).floor;
    text(textX,textY,num2str(cars(i).load),'FontSize',18);%%%%

end

for i=1:2
    x_coords=[-.5 0 .5]+i;
     for k=1:length(HC.waiting{i})
         selectedColor='b';
        for j=1:numOfCars
            y_coords=[HC.waiting{i}(k).floor HC.waiting{i}(k).floor+1.5-i HC.waiting{i}(k).floor];
            if(HC.waiting{i}(k).carId==j)
                selectedColor= colors(j);
            end
        end
        
       rectangle('Position',[i-.5 HC.waiting{i}(k).floor-.5  1  1],'FaceColor',selectedColor,'Curvature',[1,1]); 
       line(x_coords,y_coords,'LineWidth',2,'Color','w');
        textX=i ;textY=HC.waiting{i}(k).floor;
%         aaa=P.waiting{i}.floor;
%         bbb=HC.waiting{i}(k).floor;
   text(textX,textY,num2str(sum([P.waiting{i}.floor]==HC.waiting{i}(k).floor )),'FontSize',18  );
    end
end

xlabels={['Up';'Down';carColumnHeader(1:numOfCars)']};%
set(gca,... 
'XAxisLocation','bottom', ...
'units','normalized','outerposition',[0.15 0.28 .25 .6],...  %[0.12 0.25 .25 .6]   
     'XTick',[1:numOfCars+2],'XTickLabel',xlabels{1}, ...
     'YDir','normal','YTick',1:build.nf,'LineWidth',2)
% axis([0.5 length(CAR.floor)+2.5 .5 20.5])
str=sprintf('%% %d incoming %% %d interfloor %% %d outgoing',traffic.inc,traffic.int,traffic.out);
title(str);

 
end

