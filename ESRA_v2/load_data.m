function load_data(filename)

    addpath(genpath('utils'));  % Adds the 'classes' folder and subfolders
    addpath(genpath('decision'));  % Adds the 'classes' folder and subfolders
    addpath(genpath('dataStructures'));  % Adds the 'classes' folder and subfolders
    addpath(genpath('objFuns'));  % Adds the 'classes' folder and subfolders
    dataConf=load(filename);
    dataConf=dataConf(1);
    assignin('base', 'dataConf', dataConf); % Save 'myVar' to the base workspace
end