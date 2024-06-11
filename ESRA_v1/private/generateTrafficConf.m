function  TRAFFIC = generateTrafficConf( startData )
  
   numOfRows= length(startData.INCmin:10:startData.INCmax);
   numOfCols= length(startData.INTmin:10:startData.INTmax );
   TRAFFIC = cell(numOfRows,numOfCols);
   
   Traffic.getSetEndTime(startData.endTime);
   Traffic.getSetNumInitialPassengers(startData.numInitialPassengers);

   
   incIndex=0;
    for inc=startData.INCmin:10:startData.INCmax
        incIndex=incIndex+1;
        intIndex=0;
        for int=startData.INTmin:10:startData.INTmax 
            
            intIndex=intIndex+1;
      
        if (100-inc-int)>=0
             TRAFFIC{incIndex,intIndex}= Traffic(inc,int);
        else
              TRAFFIC{incIndex,intIndex}= Traffic.empty;
        end
        
      end
        
end



