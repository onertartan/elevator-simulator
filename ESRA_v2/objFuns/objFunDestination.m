function AVERAGE=objFunDestination(cars,HC,HC_numofups,chrom,nf,P,optimizationParameter)
 
[P_1_floor,P_upindex]=sort([P.waiting{1}.floor]);
[P_2_floor,P_downindex]=sort([P.waiting{2}.floor]);

if isempty(P_1_floor)
    P_1_DF=[];
else
   df = [P.waiting{1}.DF];
   P_1_DF=df(P_upindex);
end

if isempty(P_2_floor)
    P_2_DF=[];
else
     df = [P.waiting{2}.DF];
     
     P_2_DF=df(P_downindex) ;
end

AVERAGE=zeros(size(chrom,1),1);
intFloor=1/cars(1).velocity;               %Inter floor time

switch optimizationParameter
    case "WT"
        WToptimization()
    case "JT"
        JToptimization
    case "CTT"
        CTToptimization
end
    

function WToptimization             
for n=1:size(chrom,1)
%Here we calculate true values of WT 
WT1=zeros(1,length(P_1_floor));
WT2=zeros(1,length(P_2_floor)); 
   for i=1:length(cars)
  % sprintf('CAR NUMBER %d',i)
  HC_up_index=find(chrom(n,1:HC_numofups)==i);HC_up=HC(HC_up_index );
  HC_up_1_index=HC_up_index(HC_up >=cars(i).floor);HC_up_1=HC(HC_up_1_index); 
  HC_up_2_index=HC_up_index(HC_up<cars(i).floor );HC_up_2=HC(HC_up_2_index); 
            
  HC_dw_index=HC_numofups+find(chrom(n,HC_numofups+1:length(HC))==i); HC_dw=HC(HC_dw_index );
  HC_dw_1_index=HC_dw_index(HC_dw<=cars(i).floor );HC_dw_1=HC(HC_dw_1_index); 
  HC_dw_2_index=HC_dw_index(HC_dw>cars(i).floor);HC_dw_2=HC(HC_dw_2_index); 
                   
  up_all_index=ismember(P_1_floor,HC_up);
  P_up_all_floor=P_1_floor(up_all_index);
  P_up_all_DF=P_1_DF(up_all_index);
   
  up_1_index=ismember(P_1_floor,HC_up_1);
  P_up_1_floor=P_1_floor(up_1_index);
  P_up_1_DF=P_1_DF(up_1_index);
  
  up_2_index=ismember(P_1_floor,HC_up_2);
  P_up_2_floor=P_1_floor(up_2_index);
  P_up_2_DF=P_1_DF(up_2_index);

  down_all_index=ismember(P_2_floor,HC_dw);
  P_down_all_floor=P_2_floor(down_all_index);
  P_down_all_DF=P_2_DF(down_all_index);
  
  down_1_index=ismember(P_2_floor,HC_dw_1);
  P_dw_1_floor=P_2_floor(down_1_index);
  P_dw_1_DF=P_2_DF(down_1_index);
  
  down_2_index=ismember(P_2_floor,HC_dw_2);
  P_dw_2_floor=P_2_floor(down_2_index);
  P_dw_2_DF=P_2_DF(down_2_index);

%  sprintf('CAR NUMBER %d and its destination %d',i,CAR.DF{i})
% if(length(P_up_all_floor)>0)
%  sprintf('up floor %d ',P_up_all_floor)
%  sprintf('up    DF %d ',P_up_all_DF)
%     sprintf( 'up_all_index %d',up_all_index)
% 
% end
% if(length(P_down_all_floor)>0)
%     sprintf('down floor %d ',P_down_all_floor)
%     sprintf('down    DF %d ',P_down_all_DF)
%    sprintf( 'down_all_index %d',down_all_index)
% 
% end
     
               Z= cars(i).DF;
%%%%%%%%%%%%%%%%%%%%%%%%%%%%ASANSOR YUKARI%%%%%%%%%%%%%%%%%%%%%%%%
      if cars(i).state==1
             numof_CAR_STOPS_previous=0;  
             MINI=min(P_down_all_DF);
             MAKS=max([max(P_up_1_DF) cars(i).floor max(cars(i).DF)] );            
%1_)If HC direction is "Up" and HC Floor is bigger or equal %to Car floor"
            if(P_up_1_floor) 
                reverse=false;
                X=P_up_1_floor;Y=P_up_1_DF;
                [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                
                WT1(up_1_index)= (P_up_1_floor-cars(i).floor)*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime;
                Z=[];
            else numof_CAR_STOPS_previous=length(cars(i).DF);
            end  
%2_) If there is at least one HC whose direction is "Down" 
            if (P_down_all_floor)
                if (max(P_down_all_floor)== MAKS)                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                reverse=true;
                X=P_down_all_floor;Y=P_down_all_DF;
                MAKS=max([MAKS max(P_down_all_floor)]);
                [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                WT2(down_all_index)= (MAKS-cars(i).floor+MAKS-P_down_all_floor)*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime;
                Z=[];
            end
%3_)If there is at least one HC whose direction is "Up" and HC floor is "less" than Car floor
             if(P_up_2_floor)
                 if (min(P_up_2_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                 end
                 reverse=false;
                 X=P_up_2_floor;Y=P_up_2_DF;
                 MINI=min([MINI P_up_2_floor]);
                 [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                 WT1(up_2_index)=((MAKS-cars(i).floor)+(MAKS-MINI)+(P_up_2_floor-MINI))*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime;
         
             end
                    
      end
%%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
         if cars(i).state~=1 
                 numof_CAR_STOPS_previous=0;  
                 MAKS=max(P_up_all_DF);
                 MINI=min([min(P_dw_1_DF) cars(i).floor min(cars(i).DF)]);
%1_)If there is at least one HC whose direction is "Down" and HC floor ia "less" than the car floor          
                   if(P_dw_1_floor)
                      reverse=true;
                      X=P_dw_1_floor;Y=P_dw_1_DF; 
                      [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                      WT2(down_1_index)= (cars(i).floor-P_dw_1_floor)*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime; 
                    
                      Z=[];
                   else numof_CAR_STOPS_previous=length(cars(i).DF);
                   end
%2_)If there is at least one HC whose direction is "Up" 
                 if (P_up_all_floor)
                     if (min(P_up_all_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                     end
                     reverse=false;
                     X=P_up_all_floor;Y=P_up_all_DF; 
                     [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                     MINI=min([min(P_up_all_floor) MINI]);
                     WT1(up_all_index)=((cars(i).floor-MINI)+(P_up_all_floor-MINI))*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime;
                    
                     Z=[];
                 end
%3_)If there is at least one HC whose direction is "Down" and HC floor is greater than Car floor
                   if (P_dw_2_floor)
                       if(max(P_dw_2_floor)==MAKS)
                            numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                       end
                       reverse=true;
                       MAKS=max([MAKS P_dw_2_floor]);
                       X=P_dw_2_floor;Y=P_dw_2_DF;     
                       [numof_CAR_STOPS_atP_floor,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                       WT2(down_2_index)= ((cars(i).floor-MINI)+(MAKS-MINI)+(MAKS-P_dw_2_floor))*intFloor+(numof_CAR_STOPS_atP_floor-1)*cars(i).stopOverTime;                    
                  end
         end
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE CAR STATE%%%%%%%%%%%%%%%%%%%%%%%%
      %  CAR.ncTOPs(i)=numof_CAR_STOPS_previous;%?????????????????????????????????????????????????????????????????
        
   end
 %  sprintf('TOTAL WT1 %d  WT2 %d',sum(WT1),sum(WT2)),WT1,WT2,pause
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE ith CAR%%%%%%%%%%%%%%%%%%%%%%%%
      AVERAGE(n)=mean([WT1 WT2]);
      
 end
end
function JToptimization             
for n=1:size(chrom,1)

%Here we calculate true values of JT

JT1=zeros(1,length(P_1_floor));
JT2=zeros(1,length(P_2_floor));

   for i=1:length(cars)
  % sprintf('CAR NUMBER %d',i)
  HC_up_index=find(chrom(n,1:HC_numofups)==i);HC_up=HC(HC_up_index );
  HC_up_1_index=HC_up_index(HC_up >=cars(i).floor);HC_up_1=HC(HC_up_1_index); 
  HC_up_2_index=HC_up_index(HC_up<cars(i).floor );HC_up_2=HC(HC_up_2_index); 
            
  HC_dw_index=HC_numofups+find(chrom(n,HC_numofups+1:length(HC))==i); HC_dw=HC(HC_dw_index );
  HC_dw_1_index=HC_dw_index(HC_dw<=cars(i).floor );HC_dw_1=HC(HC_dw_1_index); 
  HC_dw_2_index=HC_dw_index(HC_dw>cars(i).floor);HC_dw_2=HC(HC_dw_2_index); 
                   
  up_all_index=ismember(P_1_floor,HC_up);
  P_up_all_floor=P_1_floor(up_all_index);
  P_up_all_DF=P_1_DF(up_all_index);
  
   
  up_1_index=ismember(P_1_floor,HC_up_1);
  P_up_1_floor=P_1_floor(up_1_index);
  P_up_1_DF=P_1_DF(up_1_index);
  
  up_2_index=ismember(P_1_floor,HC_up_2);
  P_up_2_floor=P_1_floor(up_2_index);
  P_up_2_DF=P_1_DF(up_2_index);

  down_all_index=ismember(P_2_floor,HC_dw);
  P_down_all_floor=P_2_floor(down_all_index);
  P_down_all_DF=P_2_DF(down_all_index);
  
  down_1_index=ismember(P_2_floor,HC_dw_1);
  P_dw_1_floor=P_2_floor(down_1_index);
  P_dw_1_DF=P_2_DF(down_1_index);
  
  down_2_index=ismember(P_2_floor,HC_dw_2);
  P_dw_2_floor=P_2_floor(down_2_index);
  P_dw_2_DF=P_2_DF(down_2_index);

%  sprintf('CAR NUMBER %d and its destination %d',i,CAR.DF{i})
% if(length(P_up_all_floor)>0)
%  sprintf('up floor %d ',P_up_all_floor)
%  sprintf('up    DF %d ',P_up_all_DF)
%     sprintf( 'up_all_index %d',up_all_index)
% 
% end
% if(length(P_down_all_floor)>0)
%     sprintf('down floor %d ',P_down_all_floor)
%     sprintf('down    DF %d ',P_down_all_DF)
%    sprintf( 'down_all_index %d',down_all_index)
% 
% end
     
               Z= cars(i).DF;
%%%%%%%%%%%%%%%%%%%%%%%%%%%%ASANSOR YUKARI%%%%%%%%%%%%%%%%%%%%%%%%
      if cars(i).state==1 
             numof_CAR_STOPS_previous=0;  
             MINI=min(P_down_all_DF);
             MAKS=max([max(P_up_1_DF) cars(i).floor max(cars(i).DF)] );            
%1_)If HC direction is "Up" and HC Floor is bigger or equal %to Car floor"
            if(P_up_1_floor) 
                reverse=false;
                X=P_up_1_floor;Y=P_up_1_DF;
                [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                
                JT1(up_1_index)=(P_up_1_DF-cars(i).floor)*intFloor+(numof_CAR_STOPS_atP_DF-1)*cars(i).stopOverTime;
                Z=[];
            else numof_CAR_STOPS_previous=length(cars(i).DF);
            end  
%2_) If there is at least one HC whose direction is "Down" 
            if (P_down_all_floor)
                if (max(P_down_all_floor)== MAKS)                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                reverse=true;
                X=P_down_all_floor;Y=P_down_all_DF;
                MAKS=max([MAKS max(P_down_all_floor)]);
                [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                JT2(down_all_index)=(MAKS-cars(i).floor+MAKS-P_down_all_DF)*intFloor+(numof_CAR_STOPS_atP_DF )*cars(i).stopOverTime;

                Z=[];
            end
%3_)If there is at least one HC whose direction is "Up" and HC floor is "less" than Car floor
             if(P_up_2_floor)
                 if (min(P_up_2_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                 end
                 reverse=false;
                 X=P_up_2_floor;Y=P_up_2_DF;
                 MINI=min([MINI P_up_2_floor]);
                 [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                 JT1(up_2_index)=((MAKS-cars(i).floor)+(MAKS-MINI)+(P_up_2_floor-MINI))*intFloor+(numof_CAR_STOPS_atP_DF*cars(i).stopOverTime);
               
             end
                    
      end
%%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
         if cars(i).state~=1 
                 numof_CAR_STOPS_previous=0;  
                 MAKS=max(P_up_all_DF);
                 MINI=min([min(P_dw_1_DF) cars(i).floor min(cars(i).DF)]);
%1_)If there is at least one HC whose direction is "Down" and HC floor ia "less" than the car floor          
                   if(P_dw_1_floor)
                      reverse=true;
                      X=P_dw_1_floor;Y=P_dw_1_DF; 
                      [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                      JT2(down_1_index)=(cars(i).floor-P_dw_1_DF)*intFloor+(numof_CAR_STOPS_atP_DF-1)*cars(i).stopOverTime;

                      Z=[];
                   else numof_CAR_STOPS_previous=length(cars(i).DF);
                   end
%2_)If there is at least one HC whose direction is "Up" 
                 if (P_up_all_floor)
                     if (min(P_up_all_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                     end
                     reverse=false;
                     X=P_up_all_floor;Y=P_up_all_DF; 
                     [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                     MINI=min([min(P_up_all_floor) MINI]);
                     JT1(up_all_index)=((cars(i).floor-MINI)+(P_up_all_DF-MINI))*intFloor+(numof_CAR_STOPS_atP_DF*cars(i).stopOverTime);
    
                     Z=[];
                 end
%3_)If there is at least one HC whose direction is "Down" and HC floor is greater than Car floor
                   if (P_dw_2_floor)
                       if(max(P_dw_2_floor)==MAKS)
                            numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                       end
                       reverse=true;
                       MAKS=max([MAKS P_dw_2_floor]);
                       X=P_dw_2_floor;Y=P_dw_2_DF;     
                       [~,numof_CAR_STOPS_atP_DF,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                       JT2(down_2_index)=((cars(i).floor-MINI)+(MAKS-MINI)+(MAKS-P_dw_2_DF))*intFloor+(numof_CAR_STOPS_atP_DF*cars(i).stopOverTime);
                      
                  end
         end
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE CAR STATE%%%%%%%%%%%%%%%%%%%%%%%%
       % CAR.ncTOPs(i)=numof_CAR_STOPS_previous; %??????????????????????????
        
   end
 %%%%%%%%%%%%%%%%%%%%%%%%END OF THE ith CAR%%%%%%%%%%%%%%%%%%%%%%%%
   
      TOTAL(n)=sum(JT1)+sum(JT2);
end
end
function CTToptimization             
for n=1:size(chrom,1)

%Here we calculate true values of WT and CTT by considering HC destination floors HC_DF
%Moreover we also calculate JT which was not in GA6
CTT=zeros(1,length(cars)); 

   for i=1:length(cars)
  % sprintf('CAR NUMBER %d',i)
  HC_up_index=find(chrom(n,1:HC_numofups)==i);HC_up=HC(HC_up_index );
  HC_up_1_index=HC_up_index(HC_up >=cars(i).floor);HC_up_1=HC(HC_up_1_index); 
  HC_up_2_index=HC_up_index(HC_up<cars(i).floor );HC_up_2=HC(HC_up_2_index); 
            
  HC_dw_index=HC_numofups+find(chrom(n,HC_numofups+1:length(HC))==i); HC_dw=HC(HC_dw_index );
  HC_dw_1_index=HC_dw_index(HC_dw<=cars(i).floor );HC_dw_1=HC(HC_dw_1_index); 
  HC_dw_2_index=HC_dw_index(HC_dw>cars(i).floor);HC_dw_2=HC(HC_dw_2_index); 
                   
  up_all_index=ismember(P_1_floor,HC_up);
  P_up_all_floor=P_1_floor(up_all_index);
  P_up_all_DF=P_1_DF(up_all_index);
  
   
  up_1_index=ismember(P_1_floor,HC_up_1);
  P_up_1_floor=P_1_floor(up_1_index);
  P_up_1_DF=P_1_DF(up_1_index);
  
  up_2_index=ismember(P_1_floor,HC_up_2);
  P_up_2_floor=P_1_floor(up_2_index);
  P_up_2_DF=P_1_DF(up_2_index);

  down_all_index=ismember(P_2_floor,HC_dw);
  P_down_all_floor=P_2_floor(down_all_index);
  P_down_all_DF=P_2_DF(down_all_index);
  
  down_1_index=ismember(P_2_floor,HC_dw_1);
  P_dw_1_floor=P_2_floor(down_1_index);
  P_dw_1_DF=P_2_DF(down_1_index);
  
  down_2_index=ismember(P_2_floor,HC_dw_2);
  P_dw_2_floor=P_2_floor(down_2_index);
  P_dw_2_DF=P_2_DF(down_2_index);

%  sprintf('CAR NUMBER %d and its destination %d',i,CAR.DF{i})
% if(length(P_up_all_floor)>0)
%  sprintf('up floor %d ',P_up_all_floor)
%  sprintf('up    DF %d ',P_up_all_DF)
%     sprintf( 'up_all_index %d',up_all_index)
% 
% end
% if(length(P_down_all_floor)>0)
%     sprintf('down floor %d ',P_down_all_floor)
%     sprintf('down    DF %d ',P_down_all_DF)
%    sprintf( 'down_all_index %d',down_all_index)
% 
% end
     
               Z= cars(i).DF;
%%%%%%%%%%%%%%%%%%%%%%%%%%%%ASANSOR YUKARI%%%%%%%%%%%%%%%%%%%%%%%%
      if cars(i).state==1 
             numof_CAR_STOPS_previous=0;  
             MINI=min(P_down_all_DF);
             MAKS=max([max(P_up_1_DF) cars(i).floor max(cars(i).DF)] );            
%1_)If HC direction is "Up" and HC Floor is bigger or equal %to Car floor"
            if(P_up_1_floor) 
                reverse=false;
                X=P_up_1_floor;Y=P_up_1_DF;
                [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                 
                CTT(i)=(MAKS-cars(i).floor)*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;

               Z=[];
            else numof_CAR_STOPS_previous=length(cars(i).DF);
            end  
%2_) If there is at least one HC whose direction is "Down" 
            if (P_down_all_floor)
                if (max(P_down_all_floor)== MAKS)                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                reverse=true;
                X=P_down_all_floor;Y=P_down_all_DF;
                MAKS=max([MAKS max(P_down_all_floor)]);
                [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);

                CTT(i)=(MAKS-cars(i).floor+MAKS-MINI)*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;
                Z=[];
            end
%3_)If there is at least one HC whose direction is "Up" and HC floor is "less" than Car floor
             if(P_up_2_floor)
                 if (min(P_up_2_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                 end
                 reverse=false;
                 X=P_up_2_floor;Y=P_up_2_DF;
                 MINI=min([MINI P_up_2_floor]);
                 [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                 CTT(i)=(MAKS-cars(i).floor+MAKS-MINI+max(P_up_2_DF)-MINI)*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;
               
             end
                    
      end
%%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
         if cars(i).state~=1 
                 numof_CAR_STOPS_previous=0;  
                 MAKS=max(P_up_all_DF);
                 MINI=min([min(P_dw_1_DF) cars(i).floor min(cars(i).DF)]);
%1_)If there is at least one HC whose direction is "Down" and HC floor ia "less" than the car floor          
                   if(P_dw_1_floor)
                      reverse=true;
                      X=P_dw_1_floor;Y=P_dw_1_DF; 
                      [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                
                      CTT(i)=(cars(i).floor-MINI)*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;
                      Z=[];
                   else numof_CAR_STOPS_previous=length(cars(i).DF);
                   end
%2_)If there is at least one HC whose direction is "Up" 
                 if (P_up_all_floor)
                     if (min(P_up_all_floor)== MINI)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                     end
                     reverse=false;
                     X=P_up_all_floor;Y=P_up_all_DF; 
                     [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);%,pause
                     MINI=min([min(P_up_all_floor) MINI]);
                     
                     CTT(i)=(cars(i).floor-MINI+MAKS-MINI)*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;
                     Z=[];
                 end
%3_)If there is at least one HC whose direction is "Down" and HC floor is greater than Car floor
                   if (P_dw_2_floor)
                       if(max(P_dw_2_floor)==MAKS)
                            numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                       end
                       reverse=true;
                       MAKS=max([MAKS P_dw_2_floor]);
                       X=P_dw_2_floor;Y=P_dw_2_DF;     
                       [~,~,numof_CAR_STOPS_previous]=NumofCSTrue(X,Y,Z,reverse,numof_CAR_STOPS_previous);
                       CTT(i)=(cars(i).floor-MINI+MAKS-MINI+MAKS-min(P_dw_2_floor))*intFloor+numof_CAR_STOPS_previous*cars(i).stopOverTime;
                      
                  end
         end
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE CAR STATE%%%%%%%%%%%%%%%%%%%%%%%%
       % CAR.ncTOPs(i)=numof_CAR_STOPS_previous; %%%%%%%%%%%%%%%%%%%%%%
        
   end
 %  sprintf('TOTAL WT1 %d  WT2 %d',sum(WT1),sum(WT2)),WT1,WT2,pause
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE ith CAR%%%%%%%%%%%%%%%%%%%%%%%%
   
      AVERAGE(n)=mean([WT1 WT2]);
 end
end



%fitness=(1./TOTAL_WT)';
%%SONUÇLARI GÖSTER
% HC
% WT,sum(WT)
% cell2mat(JT),sum(cell2mat(JT))
% CTT,sum(CTT)
% RESULT_TABLE
% CAR.ncTOPs
end