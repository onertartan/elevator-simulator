function  [NUMOF_CAR_STOPS_atHC,numof_CAR_STOPS_previous] =NumofCS(HC,CAR_DF,REVERSE,numof_CAR_STOPS_previous)
   
       CAR_STOP_floors=unique([HC CAR_DF]); %Car stops at:HCs, HC destination floors and car destination floors
       NUMOF_CAR_STOPS_atHC=zeros(1,length(HC));
    if REVERSE==true                                           %If the car direction ise reversed
        CAR_STOP_floors=fliplr(CAR_STOP_floors); %CAR_STOPS_J=fliplr(CAR_STOPS_J),
    end
    
    
    
for(i=1:length(HC))
    NUMOF_CAR_STOPS_atHC(i)=find(HC(i)==CAR_STOP_floors)+numof_CAR_STOPS_previous; 
 end
    numof_CAR_STOPS_previous=length(CAR_STOP_floors);           %Number of stops in previous direction

    
 