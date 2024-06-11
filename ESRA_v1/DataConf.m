classdef DataConf<handle
    properties
        BUILDING
        CAR
        TRAFFIC
        RECnew ={} %Initially empty, 
        RECold ={} %Not empty
 
        dataType int8
        initialCars
        initialP
        initialHC
        isInitialDispatch   
        nsc 
    end
    
    methods
        function dataConf = DataConf(startData)
            dataConf.dataType =startData.dataType;
            Passenger.resetId();
            HallCall.resetId();
            
            switch(dataConf.dataType)
                case 1      % 1:Generate new data
                    configurationNewData(startData,dataConf);
                case 2      % 2:Recorded data
                   startData.fileName, dataConf=load(startData.fileName).dataConf;
                 
                     s = size(dataConf.RECnew);
                     nbc= size(dataConf.BUILDING);nbc=nbc(2);
                     ncc= size(dataConf.CAR);     ncc=ncc(2);
                     nt= size(dataConf.TRAFFIC);nint=nt(1);ninc=nt(2);
                     total=1;
                     for i=s
                         total=total*i;
                     end
                     dataConf.RECold= dataConf.RECnew;
                     dataConf.RECnew={};
                     nsc=round(total/(nbc*ncc*nint*ninc));
%                     if nsc>1 % this if statement can be removed?
%                         simulator.numOfSimulations=nsc;
%                     end
                      %evalin('base','dataConf');
                    % [TRAFFIC, CAR, BUILDING,simulation,RT]= configurationRecordedData(startData);
                case 3      % 3:New Data With Custom Initial Conditions
                    configurationNewDataWithCustomInitials(startData,dataConf);
                case 4 %MDP
                    % 
                    %[TRAFFIC,CAR,BUILDING,simulation]= configurationNewData(startData);
            end
            
        end
        
         
    end
end