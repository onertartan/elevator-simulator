function AVERAGE=ObjFunWithNofPassengers(CAR,HC,HC_numofups,chrom,P_1_floor,P_2_floor)
TOTAL=zeros(length(chrom),1);
intFloor=2;               %Inter floor time
delay=7;                  %delay at transfer time

             
for n=1:size(chrom,1)
%Here we calculate true values of WT 
WT=zeros(1,length(HC));
   for i=1:CAR.nc
       
  % sprintf('CAR NUMBER %d',i)
  HC_up_index=find(chrom(n,1:HC_numofups)==i);HC_up=HC(HC_up_index );
  HC_up_1_index=HC_up_index(HC_up >=CAR.floor(i));HC_up_1=HC(HC_up_1_index); 
  HC_up_2_index=HC_up_index(HC_up<CAR.floor(i) );HC_up_2=HC(HC_up_2_index); 
            
  HC_dw_index=HC_numofups+find(chrom(n,HC_numofups+1:length(HC))==i); HC_dw=HC(HC_dw_index );
  HC_dw_1_index=HC_dw_index(HC_dw<=CAR.floor(i) );HC_dw_1=HC(HC_dw_1_index); 
  HC_dw_2_index=HC_dw_index(HC_dw>CAR.floor(i));HC_dw_2=HC(HC_dw_2_index); 
                   

  HC_up_nofP=zeros(1, length(HC_up));HC_dw_nofP=zeros(1, length(HC_dw));
  HC_up_1_nofP=zeros(1, length(HC_up_1));  HC_up_2_nofP=zeros(1, length(HC_up_2));
  HC_dw_1_nofP=zeros(1, length(HC_dw_1));  HC_dw_2_nofP=zeros(1, length(HC_dw_2));

   
  for(j=1:length(HC_up))
     HC_up_nofP(j)=sum(HC_up(j)==P_1_floor);
  end  
 
  for(j=1:length(HC_up_1))
     HC_up_1_nofP(j)=sum(HC_up(j)==P_1_floor);
  end  
  
  for(j=1:length(HC_up_2))
     HC_up_2_nofP(j)=sum(HC_up(j)==P_1_floor);
  end  
  
 for(j=1:length(HC_dw))
     HC_dw_nofP(j)=sum(HC_dw(j)==P_2_floor);
 end  
 
  for(j=1:length(HC_dw_1))
     HC_dw_1_nofP(j)=sum(HC_dw_1(j)==P_2_floor);
  end  

   for(j=1:length(HC_dw_2))
     HC_dw_2_nofP(j)=sum(HC_dw_2(j)==P_2_floor);
   end  

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
     
              
Z= CAR.DF{i};

%%%%%%%%%%%%%%%%%%%%%%%%%%%%ASANSOR YUKARI%%%%%%%%%%%%%%%%%%%%%%%%
      if CAR.state(i)==1 ;
             numof_CAR_STOPS_previous=0;  
             MINI=min(HC_dw);
             MAKS=max([max(HC_up_1) max(CAR.DF{i})  CAR.floor(i) ] );            
%1_)If HC direction is "Up" and HC Floor is bigger or equal %to Car floor"
            if(HC_up_1) 
                flipLeftToRight=false;
                X=HC_up_1;
                [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                WT(HC_up_1_index)= (HC_up_1-CAR.floor(i))*intFloor.*HC_up_1_nofP+(numof_CAR_STOPS_atHC-1)*delay;
                CTT(i)=(MAKS-CAR.floor(i))*intFloor+numof_CAR_STOPS_previous*delay;

                Z=[];
            else numof_CAR_STOPS_previous=length(CAR.DF{i});
            end  
%2_) If there is at least one HC whose direction is "Down" 
            if (HC_dw)
                if (isempty(HC_up_1) && max(HC_dw)== MAKS)                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                flipLeftToRight=true;
                X=HC_dw;
                MAKS=max([MAKS max(HC_dw)]);
                [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                WT(HC_dw_index)= (MAKS-CAR.floor(i)+MAKS-HC_dw)*intFloor.*HC_dw_nofP+(numof_CAR_STOPS_atHC-1)*delay;

                CTT(i)=(MAKS-CAR.floor(i)+MAKS-MINI)*intFloor+numof_CAR_STOPS_previous*delay;
                Z=[];
            end
%3_)If there is at least one HC whose direction is "Up" and HC floor is "less" than Car floor
             if(HC_up_2)
              
                 flipLeftToRight=false;
                 X=HC_up_2;
                 MINI=min([MINI HC_up_2]);
                 [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                 WT(HC_up_2_index)=((MAKS-CAR.floor(i))+(MAKS-MINI)+(HC_up_2-MINI))*intFloor.*HC_up_2_nofP+(numof_CAR_STOPS_atHC-1)*delay;
                 CTT(i)=(MAKS-CAR.floor(i)+MAKS-MINI+max(HC_up_2)-MINI)*intFloor+numof_CAR_STOPS_previous*delay;
               
             end
                    
      end
%%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
         if CAR.state(i)~=1 
                 numof_CAR_STOPS_previous=0;  
                 MINI=min([min(HC_dw_1) CAR.floor(i) min(CAR.DF{i})]);
                 MAKS=max(HC_up);
%1_)If there is at least one HC whose direction is "Down" and HC floor ia "less" than the car floor          
                   if(HC_dw_1)
                      flipLeftToRight=true;
                      X=HC_dw_1;
                      [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);%,pause
                      WT(HC_dw_1_index)= (CAR.floor(i)-HC_dw_1)*intFloor.*HC_dw_1_nofP+(numof_CAR_STOPS_atHC-1)*delay; 

                      CTT(i)=(CAR.floor(i)-MINI)*intFloor+numof_CAR_STOPS_previous*delay;
                      Z=[];
                   else numof_CAR_STOPS_previous=length(CAR.DF{i});
                   end
%2_)If there is at least one HC whose direction is "Up" 
                 if (HC_up)
                     if (isempty(HC_dw_1) && min(HC_up)== MINI && CAR.state(i)==-1)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                     end
                     flipLeftToRight=false;
                     X=HC_up;
                     [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);%,pause
                     MINI=min([HC_up MINI]);
                     WT1(HC_up_index)=((CAR.floor(i)-MINI)+(HC_up-MINI))*intFloor.*HC_up_nofP+(numof_CAR_STOPS_atHC-1)*delay;
    
                     CTT(i)=(CAR.floor(i)-MINI+MAKS-MINI)*intFloor+numof_CAR_STOPS_previous*delay;
                     Z=[];
                 end
%3_)If there is at least one HC whose direction is "Down" and HC floor is greater than Car floor
                   if (HC_dw_2)
                     
                       flipLeftToRight=true;
                       MAKS=max([MAKS HC_dw_2]);
                       X=HC_dw_2;   
                       [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                       WT(HC_dw_2_index)= ((CAR.floor(i)-MINI)+(MAKS-MINI)+(MAKS-HC_dw_2))*intFloor.*HC_dw_2_nofP+(numof_CAR_STOPS_atHC-1)*delay;
                       CTT(i)=( (CAR.floor(i)-MINI)+(MAKS-MINI)+(MAKS-min(HC_dw_2)))*intFloor+numof_CAR_STOPS_previous*delay;
                      
                  end
         end
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE CAR STATE%%%%%%%%%%%%%%%%%%%%%%%%
       
        CAR.ncTOPs(i)=numof_CAR_STOPS_previous;
        
   end
 %  sprintf('TOTAL WT1 %d  WT2 %d',sum(WT1),sum(WT2)),WT1,WT2,pause
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE ith CAR%%%%%%%%%%%%%%%%%%%%%%%%
      %TOTAL(n)=sum(WT)
      AVERAGE(n)=mean(WT);
      
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