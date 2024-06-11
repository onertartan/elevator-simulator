function  Traffic = generateTrafficConf( startData )
 
  Traffic=struct('INC',[],'INT',[],'OUT',[],'Pa',[],'Pa_inc',[],'Pa_int',[],'Pa_out',[],'Pr',[],'Pr_inc',[],'Pr_int',[],'Pr_out',[]);
    inc=0;
    for INC=startData.INCmin:10:startData.INCmax
        inc=inc+1;
        int=0;
        for INT=startData.INTmin:10:startData.INTmax 
            int=int+1;
            Traffic(inc,int).INC=INC/100;
            Traffic(inc,int).INT=INT/100;
            Traffic(inc,int).OUT=(100-INC-INT)/100;
            %Traffic(inc,int)=GenTrafficConf(INC,INT);
        end
        
    end

end

