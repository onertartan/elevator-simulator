function AVERAGE=objFunNormal1(cars,HC,HC_numofups,chrom,nf)

intFloor=1/cars(1).velocity;               %Inter floor time

AVERAGE=zeros(size(chrom,1),1);

%M= containers.Map;                                     %MAP IMPLEMENTATION    

    for n=1:size(chrom,1)

    % if ~isKey(M,char(chrom(n,:)) )%MAP IMPLEMENTATION    
    
%CTT=zeros(1,CAR.nc);
WT=zeros(1,length(HC));

nc=length(cars);
   for i=1:nc
     %  chrom(n,:)
 
  HC_up_index=find(chrom(n,1:HC_numofups)==i);HC_up=HC(HC_up_index );
  HC_up_1_index=HC_up_index(HC_up >=cars(i).floor);HC_up_1=HC(HC_up_1_index); 
  HC_up_2_index=HC_up_index(HC_up<cars(i).floor );HC_up_2=HC(HC_up_2_index); 
            
  HC_dw_index=HC_numofups+find(chrom(n,HC_numofups+1:length(HC))==i); HC_dw=HC(HC_dw_index );
  HC_dw_1_index=HC_dw_index(HC_dw<=cars(i).floor );HC_dw_1=HC(HC_dw_1_index); 
  HC_dw_2_index=HC_dw_index(HC_dw>cars(i).floor);HC_dw_2=HC(HC_dw_2_index); 
                   
Z= cars(i).DF;
            
MIN=1;
MAKS=nf; 
numof_CAR_STOPS_previous=0;  
if cars(i).state==0
%display('HEY CAR STATE is 0')
             min_above=min([HC_up_1 HC_dw_2]);
             max_below=max([HC_up_2 HC_dw_1]);

                if((~isempty(min_above) && isempty(max_below)))
                    cars(i).state=1;
                elseif(isempty(min_above) && ~isempty(max_below))
                    cars(i).state=-1;
                elseif(~isempty(min_above) && ~isempty(max_below)) 
                     u=min(min_above,2*nf);
                     d=max(max_below,-nf);
                    if( abs(u-cars(i).floor)>abs(d-cars(i).floor))
                    cars(i).state=-1;%display('u an d'),CAR.HC_list_ups_below{i},above,below,u,d
                    
                    else
                     cars(i).state=1;
                    end
                end    
end
%%%%%%%%%%%%%%%%%%%%%%%%%%%%ASANSOR YUKARI%%%%%%%%%%%%%%%%%%%%%%%%
      if cars(i).state==1  
        
%1_)If HC direction is "Up" and HC Floor is bigger or equal %to Car floor"
            if(~isempty(HC_up_1)) 
                flipLeftToRight=false;
                X=HC_up_1;
                [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                WT(HC_up_1_index)= (HC_up_1-cars(i).floor)*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime;
             %   CTT(i)=(MAKS-CAR.floor(i))*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;

                Z=[];
            else
             MAKS=max([max(cars(i).DF)  cars(i).floor ] );            
                numof_CAR_STOPS_previous=length(cars(i).DF);
            end  
%2_) If there is at least one HC whose direction is "Down" 
            if (~isempty(HC_dw)) 
                if ( ~isempty(cars(i).DF) && isempty(HC_up_1) && max(HC_dw)==MAKS )                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                flipLeftToRight=true;
                X=HC_dw;
                MAKS=max([MAKS max(HC_dw)]);
                [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                WT(HC_dw_index)= (MAKS-cars(i).floor+MAKS-HC_dw)*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime;

              %  CTT(i)=(MAKS-CAR.floor(i)+MAKS-MIN)*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;
                Z=[];
            else
                MIN=min(HC_up_2);
            end
%3_)If there is at least one HC whose direction is "Up" and HC floor is "less" than Car floor
             if(~isempty(HC_up_2))
                if ( ~isempty(cars(i).DF) && isempty(HC_dw) && min(HC_up_2)== MIN )                              
                    numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                end
                 flipLeftToRight=false;
                 X=HC_up_2;
                 [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                 WT(HC_up_2_index)=((MAKS-cars(i).floor)+(MAKS-MIN)+(HC_up_2-MIN))*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime;
             %    CTT(i)=(MAKS-CAR.floor(i)+MAKS-MIN+max(HC_up_2)-MIN)*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;
               
             end
                    
      end
%%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%%%%%%%%%%%%%%%%%%%%%%%%THE CAR IS STOPPED OR MOVING DOWNWARDS%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
         if cars(i).state~=1 
            
%1_)If there is at least one HC whose direction is "Down" and HC floor ia "less" than the car floor          
                   if(~isempty(HC_dw_1))
                      flipLeftToRight=true;
                      X=HC_dw_1;
                      [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);%,pause
                      WT(HC_dw_1_index)= (cars(i).floor-HC_dw_1)*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime; 

                 %     CTT(i)=(CAR.floor(i)-MIN)*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;
                      Z=[];
                   else
                       MIN=min([cars(i).DF cars(i).floor]);
                       numof_CAR_STOPS_previous=length(cars(i).DF);
                   end
%2_)If there is at least one HC whose direction is "Up" 
                 if (HC_up)
                     if ( ~isempty(cars(i).DF) && isempty(HC_dw_1) && min(HC_up)==MIN)                              
                          numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                     end
                                         
                     flipLeftToRight=false;
                     X=HC_up;
                     [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);%,pause
                     MIN=min([HC_up MIN]);                  
                     WT(HC_up_index)=((cars(i).floor-MIN)+(HC_up-MIN))*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime;
                     
                 %    CTT(i)=(CAR.floor(i)-MIN+MAKS-MIN)*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;
                     Z=[];
                     
                 else
                     MAKS=max(HC_dw_2);
                 end
%3_)If there is at least one HC whose direction is "Down" and HC floor is greater than Car floor
                   if (~isempty(HC_dw_2))
                       if (isempty(HC_up)  )
                           if( ~isempty(cars(i).DF) && max(HC_dw_2)== MAKS)
                           numof_CAR_STOPS_previous=numof_CAR_STOPS_previous-1;
                           end
                       else
                           MAKS=max(HC_dw_2);
                       end
                       flipLeftToRight=true;
                       X=HC_dw_2;   
                       [numof_CAR_STOPS_atHC,numof_CAR_STOPS_previous]=NumofCS(X,Z,flipLeftToRight,numof_CAR_STOPS_previous);
                       WT(HC_dw_2_index)= ((cars(i).floor-MIN)+(MAKS-MIN)+(MAKS-HC_dw_2))*intFloor+(numof_CAR_STOPS_atHC-1)*cars(i).stopOverTime;
               
                   %     CTT(i)=( (CAR.floor(i)-MIN)+(MAKS-MIN)+(MAKS-min(HC_dw_2)))*intFloor+numof_CAR_STOPS_previous*CAR.stopOverTime;
                   end
         end
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE CAR STATE%%%%%%%%%%%%%%%%%%%%%%%%
        %CAR.ncTOPs(i)=numof_CAR_STOPS_previous;
        
   end
 %  sprintf('TOTAL WT1 %d  WT2 %d',sum(WT1),sum(WT2)),WT1,WT2,pause
%%%%%%%%%%%%%%%%%%%%%%%%END OF THE ith CAR%%%%%%%%%%%%%%%%%%%%%%%%

  AVERAGE(n)=mean(WT);
  
 % M(char(chrom(n,:)))=AVERAGE(n);%%MAP IMPLEMENTATION
  %   else                                  %%MAP IMPLEMENTATION
%       AVERAGE(n)=M(char(chrom(n,:)));%MAP IMPLEMENTATION    
    end

     % TOTAL_WT(n)=sum(WT);
     % TOTAL_CTT(n)=sum(CTT);
end
