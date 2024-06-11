classdef Traffic <handle
    properties
        inc
        int
        out
        Pa=[]
        Pr=[]
        confCounter int8 =0
    end
     methods(Static)%get-set methods for static variables:  arrivalRate, numInitialPassengers and endTime

        function out=getSetArrivalRate(arrivalRate)   %   static "variable"
             persistent var;
             if isempty(var)
                 var = 1;     % initial value  %ADD RAISE ERROR!
             end

             if nargin < 1; out = var; return; end  % get value
             var = arrivalRate;            % otherwise (if arrivalRate is given) set the value
             out=var;
         end

         function out=getSetNumInitialPassengers(numInitialPassengers)   % first static "variable"
            persistent var;
            if isempty(var) 
                var = 1;% initial value
            end          
            
             if nargin < 1; out = var; return; end  % get value
             var = numInitialPassengers;            % otherwise (if numInitialPassengers is given) set the value
                out=var;
            end   
        function out=getSetEndTime(endTime)   % first static "variable"
            persistent var;
          %  if isempty(var) 
           %     var = 300;% initial value
           % end          
            
             if nargin < 1; out = var; return; end  % get value
             var = endTime;                              % Reset value
                out=var;
            end
        end
        
    methods
      
        function traffic = Traffic(inc,int)  %Constructor
                    traffic.inc=inc;
                    traffic.int=int;
                    traffic.out=round((100-inc-int)); 
                    traffic.confCounter=0;
        end  
        
        function setRouteProbability(traffic,building)
            nf = building.nf;
            traffic.confCounter = traffic.confCounter+1;
            %DESTINATION DISTRIBUTION
            %1 Default uniform distribution
            %2 One floor that has a heavy traffic coming from other interfloors (like caffeteria at coffee breaks)
            %3 Two floors those have mutual heavt traffic(all interfloor between 2 floors)
            destProbSelection=1;
            [IncDestProb,IntDestProb,OutDestProb]=traffic.destProb(destProbSelection,nf);
            
            %1 DEFAULT UNIFORM DISTRIBUTION
            %2 ONE  FLOOR THAT HAS A HEAVY TRAFFIC COMING FROM OTHER INTERFLOORS(LIKE CAFETERIA FOR BREAKS)
            %3 TWO FLOORS THOSE HAVE MUTUAL HEAVY TRAFFIC(All interfloor between 2 floors)
            
            arrivalProbSelection=1;  %DİKKAT 4 HEART CONF  %DİKKAT 4 HEART CONF  %DİKKAT 4 HEART CONF
            [Pa_inc,Pa_int,Pa_out]=traffic.arrivalProb(arrivalProbSelection,nf);
            
            Pr_inc=(traffic.inc/100)*IncDestProb.*Pa_inc;
            Pr_int=(traffic.int/100)*IntDestProb.*Pa_int;
            Pr_out=(traffic.out/100)*OutDestProb.*Pa_out;
            
            traffic.Pr=Pr_inc+Pr_int+Pr_out;
            
            Pa_inc=(traffic.inc/100)*Pa_inc(:,1);
            Pa_int=(traffic.int/100)*Pa_int(:,1);
            Pa_out=(traffic.out/100)*Pa_out(:,1);
            traffic.Pa=Pa_inc+Pa_int+Pa_out;

        end   
        function [IncDestProb,IntDestProb,OutDestProb]=destProb(~,destProbSelection,nf)
        switch destProbSelection
            case 1
                %1DEFAULT UNIFORM DISTRIBUTION
                IncDestProb=[0 ones(1,nf-1)/(nf-1);zeros(nf-1,nf)];
                IntDestProb=[zeros(nf,1) (ones(nf,nf-1)-[ones(1,nf-1);eye(nf-1)]) ]/(nf-2);
                OutDestProb=[[0; ones(nf-1,1)] zeros(nf,nf-1)/(nf-1)];
            case 2
                %2 %ONE  FLOOR THAT HAS A HEAVY TRAFFIC COMING FROM OTHER INTERFLOORS(LIKE CAFETERIA FOR BREAKS)
                IncDestProb=[0 ones(1,nf-1)/(nf-1);zeros(nf-1,nf)];
                OutDestProb=[[0; ones(nf-1,1)] zeros(nf,nf-1)/(nf-1)];
                heavyFloor=[5];
                heavyProbAll=0.4;
                normalDest=setdiff(2:nf,heavyFloor);
                IntDestProb(normalDest,heavyFloor)=heavyProbAll;
                for i=1:length(normalDest)
                    IntDestProb(normalDest(i),setdiff(normalDest,normalDest(i)))=(1-heavyProbAll)/(nf-(2+length(heavyFloor)) );
                end
            case 3
                %3 TWO FLOORS THOSE HAVE MUTUAL HEAVY TRAFFIC(All interfloor between 2 floors)
                IncDestProb=[0 ones(1,nf-1)/(nf-1);zeros(nf-1,nf)];
                OutDestProb=[[0; ones(nf-1,1)] zeros(nf,nf-1)/(nf-1)];
                
                heavyFloor=[3 4];heavyProb=[1 1];
                normalDest=setdiff(2:nf,heavyFloor);
                IntDestProb(heavyFloor(1),heavyFloor(2))=heavyProb(1);
                IntDestProb(heavyFloor(2),heavyFloor(1))=heavyProb(2);
                for i=1:length(normalDest)
                    IntDestProb(normalDest(i),setdiff([2:nf],normalDest(i)))=1/(nf-2); %Normal dest floors have equal probabilities
                end
                for i=1:length(heavyFloor)
                    IntDestProb(heavyFloor(i),setdiff(normalDest,heavyFloor(i)))=(1-heavyProb(i))/(nf-(1+length(heavyFloor)) );
                end                
        end
        end
        function [Painc,Paint,Paout]=arrivalProb(~,arrivalProbSelection,nf)
        switch arrivalProbSelection
            case 1
                %%1 DEFAULT UNIFORM ARRIVALS
                Painc= repmat([1;zeros(nf-1,1)],1,nf);
                Paint= repmat([0;ones(nf-1,1)./(nf-1)],1,nf);
                Paout= repmat([0;ones(nf-1,1)./(nf-1)],1,nf);
                %%2 CUSTOM ARRIVALS 2
            case 2
                Painc= repmat([1;zeros(nf-1,1)],1,nf);
                Paint= repmat([0 0 0.5 0.5 0 0]',1,nf);
                Paout= repmat([0 1/3 0 0 1/3 1/3]',1,nf);
            case 3
                Painc= repmat([1;zeros(nf-1,1)],1,nf);
                Paint= repmat([0 0.2 0.2 0.2 0.2 0.2]',1,nf);
                Paout= repmat([0 0.2 0.2 0.2 0.2 0.2]',1,nf);
            case 4 % Custom Arrivals 3
                Painc=repmat([1;zeros(10,1)],1,nf);
                Paout=repmat([0;0.1*ones(10,1)],1,nf);
                Paint=repmat([0 0 0 0.2 0.3 0 0 0 0 0.2 0.3]',1,nf);
         end
        end
             
     end
  
end