function [HC,P]=UseRecordedTraffic(HC,P,Sim  )

for dir=1:2
  
   if(any([P.served{dir}.QJT]==Sim.time))
        index=find([ P.served{dir}.QJT]==Sim.time);
        for i=length(index):-1:1
            P.served{dir}(index(i)).WT=0;%zaten �st�ne yaz�lacak ancak yine de �imdilik g�venlik ama�l� s�f�rlayal�m veya silelim
            P.served{dir}(index(i)).DAT=0;
            P.served{dir}(index(i)).TrT=0;
            P.served{dir}(index(i)).TTD=0;
            
            P.add(P.served{dir}(index(i)) );
        end
                    
   end
end 
      
 