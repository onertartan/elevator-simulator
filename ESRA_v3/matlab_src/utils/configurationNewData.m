function configurationNewData(startData, data)

%%Building Configutation
data.BUILDING = generateBuildingConf(startData);

%%Simulation Configuration
%data.simulation = Simulation(startData);

%%Car Configuration
data.CAR = generateCarConf(startData);

%%Traffic Configuration
data.TRAFFIC = generateTrafficConf(startData);

end
 