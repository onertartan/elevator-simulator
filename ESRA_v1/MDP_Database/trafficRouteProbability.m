function traffic=trafficRouteProbability(traffic,nf)

%DESTINATION DISTRIBUTION
%Default uniform distribution
%2 One floor that has a heavy traffic coming from other interfloors (like caffeteria at coffee breaks)
%3 Two floors those have mutual heavt traffic(all interfloor between 2 floors)
destProbSelection=1;
[IncDestProb,IntDestProb,OutDestProb]=destProb(destProbSelection,nf);

%1DEFAULT UNIFORM DISTRIBUTION
%2 %ONE  FLOOR THAT HAS A HEAVY TRAFFIC COMING FROM OTHER INTERFLOORS(LIKE CAFETERIA FOR BREAKS)
%3 TWO FLOORS THOSE HAVE MUTUAL HEAVY TRAFFIC(All interfloor between 2 floors)

arrivalProbSelection=1;  %DÝKKAT 4 HEART CONF  %DÝKKAT 4 HEART CONF  %DÝKKAT 4 HEART CONF
[Pa_inc,Pa_int,Pa_out]=arrivalProb(arrivalProbSelection,nf);

Pr_inc=traffic.INC*IncDestProb.*Pa_inc;
Pr_int=traffic.INT*IntDestProb.*Pa_int;
Pr_out=traffic.OUT*OutDestProb.*Pa_out;

Pr=Pr_inc+Pr_int+Pr_out;

Pa_inc=traffic.INC*Pa_inc(:,1);
Pa_int=traffic.INT*Pa_int(:,1);
Pa_out=traffic.OUT*Pa_out(:,1);
Pa=Pa_inc+Pa_int+Pa_out;

traffic.Pa=Pa;
traffic.Pa_inc=Pa_inc;
traffic.Pa_int=Pa_int;
traffic.Pa_out=Pa_out;

traffic.Pr=Pr;
traffic.Pr_inc=Pr_inc;
traffic.Pr_int=Pr_int;
traffic.Pr_out=Pr_out;


%fprintf('setRouteProbability.m INC=%f INT=%f OUT=%f',INC,INT,OUT)
%if(0.09<INC && INC<0.11 && 0.79<INT && INT<0.81 && 0.09<OUT && OUT<0.11) pause; end


function [IncDestProb,IntDestProb,OutDestProb]=destProb(destProbSelection,nf)
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
function [Painc,Paint,Paout]=arrivalProb(arrivalProbSelection,nf)
        switch arrivalProbSelection
            case 1
                %%1 DEFAULT ARRIVALS
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
            case 4 %HEART CONFERENCE
                Painc=repmat([1;zeros(10,1)],1,nf);
                Paout=repmat([0;0.1*ones(10,1)],1,nf);
                Paint=repmat([0 0 0 0.2 0.3 0 0 0 0 0.2 0.3]',1,nf);
         end
end

end