function [NUMOF_CAR_STOPS_atP_floor,NUMOF_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(P_floor,P_DF,CAR_DF,REVERSE,numof_CAR_STOPS_previous)
    DESTINATIONS=unique([(P_DF) CAR_DF]); %Destinations of HCs and cars
    CAR_STOP_floors=unique([P_floor DESTINATIONS]); %Car stops at:HCs, HC destination floors and car destination floors
    
    NUMOF_CAR_STOPS_atP_floor=zeros(1,length(P_floor));
    NUMOF_CAR_STOPS_atP_DF=zeros(1,length(P_floor));         %Number of car stops at hall call destination floors   
    
    
    if REVERSE==true                                           %If the car direction ise reversed
        CAR_STOP_floors=fliplr(CAR_STOP_floors); %CAR_STOPS_J=fliplr(CAR_STOPS_J),
    end
    
    
    for(i=1:length(P_floor))
        NUMOF_CAR_STOPS_atP_floor(i)=find(P_floor(i)==CAR_STOP_floors)+numof_CAR_STOPS_previous ;
        NUMOF_CAR_STOPS_atP_DF(i)=find(P_DF(i)==CAR_STOP_floors)+numof_CAR_STOPS_previous;
    end
 
    numof_CAR_STOPS_previous=length(CAR_STOP_floors);           %Number of stops in previous direction

    
 