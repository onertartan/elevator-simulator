function  BUILDING = generateBuildingConf( startData )
n_floors = startData.NFmin:startData.NFstep:startData.NFmax ;
BUILDING = cell(1,length(n_floors));

nbc=0;
for n_floor= n_floors
    nbc=nbc+1;
    BUILDING{nbc}=Building(n_floor);
end