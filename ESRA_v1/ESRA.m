function varargout = ESRA(varargin)
  % Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
    'gui_Singleton',  gui_Singleton, ...
    'gui_OpeningFcn', @userInputGui_OpeningFcn, ...
    'gui_OutputFcn',  @userInputGui_OutputFcn, ...
    'gui_LayoutFcn',  [] , ...
    'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT

% --- Executes just before userInputGui is made visible.
function userInputGui_OpeningFcn(hObject, eventdata, handles, varargin)
% This function has no output args, see OutputFcn.
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% varargin   command line arguments to userInputGui (see VARARGIN)
% Choose default command line output for userInputGui
handles.output = hObject;

% Update handles structure
guidata(hObject, handles);


% UIWAIT makes userInputGui wait for user response (see UIRESUME)
% uiwait(handles.userInputGui);

% --- Outputs from this function are returned to the command line.
function varargout = userInputGui_OutputFcn(hObject, eventdata, handles)
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;
 
%SIMULATION DISPLAY OPTIONS
function speedSlider_Fcn(hObject, eventdata, handles)
speed=get(hObject,"Value");
set(handles.simulationSpeedSliderST,"String", strcat("Simulation speed: ",num2str(speed)));  
Simulator.setgetSpeed(speed);
 
function displayTrafficFlow_Fcn(hObject, eventdata, handles)
displayTrafficFlow=get(hObject,"Value"); 
Simulator.setgetdisplayTrafficFlow(displayTrafficFlow);
 
 function displayTrafficData_Fcn(hObject, eventdata, handles)
displayTrafficData=get(hObject,"Value");
 Simulator.setgetdisplayTrafficData(displayTrafficData)
%%Traffic-TRAFFIC CONFIGURATION 
% Interval selection(Third component interval is automatically determined)or fixed selection

 function enableDisableViews(views,on_off)
    for view=views
        set(view,'Enable',on_off); 
    end
        
 function traffic_SelectionChangedFcn(hObject, eventdata, handles)
         fixed_ETs=[handles.INCfixedET,handles.INTfixedET,handles.OUTfixedET];
         interval_ETs =[handles.INCminET,handles.INTminET,handles.INCmaxET,handles.INTmaxET];
         
         if get(hObject,'Tag')=="IntervalSelectionRB"
             enableDisableViews(interval_ETs,'on')
             enableDisableViews(fixed_ETs,'off')
         else
             enableDisableViews(interval_ETs,'off')
             enableDisableViews(fixed_ETs,'on')
         end
        
     function  trafficInterval_Callback(hObject, eventdata, handles)
         input_tag = get(hObject,'Tag');%INCminET,INCmaxET,INTminET or INTmaxET 
         
         if   contains(input_tag,"INC")
             other_boundary_tag  = "INT";
         else
              other_boundary_tag = "INC";
         end
         if  contains(input_tag,"min")
              other_boundary_tag = other_boundary_tag +"maxET";
         else
              other_boundary_tag = other_boundary_tag +"minET";
         end        
         other_boundary_obj = findobj('Tag',other_boundary_tag);
      
         current_input= str2double(get(hObject,'String'));        
         other_boundary = str2double(get(other_boundary_obj,'String'));
        
         if (current_input+other_boundary) >100 
                  msgbox(sprintf("Your input cannot be greater than 100- %s = %d",other_boundary_tag, current_input-other_boundary  )  );
                  set(hObject,'String','');
         elseif (current_input) <0 
                 msgbox(sprintf("Your input cannot be less than 0 = %d",other_boundary_tag, current_input-other_boundary  )  );
                  set(hObject,'String','');
         end

% --- Executes when selected object is changed in arrivalRateRBG.
function arrivalRateRBG_SelectionChangedFcn(hObject, eventdata, handles)
switch get(eventdata.NewValue,'Tag') % Get Tag of selected object.
    case 'arrivalRateRB'
         set(handles.arrivalRateET,'String','10');
         set(handles.arrivalRateET,'visible','on');
    case 'noNewPassengerRB'
        set(handles.arrivalRateET,'String','0');
         set(handles.arrivalRateET,'visible','off');

end
function DispatchRB_SelectionChangedFcn(hObject, eventdata, handles)
   if(get(handles.mdpRB,'Value')  )
        [FileName,PathName] = uigetfile('*.mat','Select the MDP data file');
        startData=get(handles.startButton,'UserData');
        startData.mdpFileName=FileName;
        set(handles.startButton,'UserData',startData);
   end
   

function trafficDataType_SelectionChangedFcn(hObject, eventdata, handles)
    startData=get(handles.startButton,'UserData');
    startData.numInitialPassengers = 0;
   if(get(handles.recordedTrafficRB,'Value')  )
        startData.dataType = 2;
        %%BROWSE FILE
        [FileName,PathName] = uigetfile('*.mat','Select the recorded Traffic file');        
        startData.fileName=FileName;       
        % set(handles.recordedTrafficPanel,'visible','on');
        %else if(get(handles.customInitializedTrafficRB,'Value'))
        %        set(handles.recordedTrafficPanel,'visible','on')
        %   else
        %      set(handles.recordedTrafficPanel,'visible','off')        
    elseif get(handles.customInitializedTrafficRB,"Value")
        startData.dataType = 3;
        [FileName,PathName] = uigetfile('*.xlsx','Select the xlsx configuration code file');       
        startData.fileName=FileName;
    end
          set(handles.startButton,'UserData',startData);
   
function availableInfoRBG_SelectionChangedFcn(hObject, eventdata, handles)
 %availableInformation=find([handles.passengerInfoRBG.Children.Value])
 availableInformation = find(handles.passengerInfoRBG.Children==eventdata.NewValue);
  



%START BUTTON

% --- Executes on button press in startButton.
function startButton_Callback(hObject, eventdata, handles)

 
 availableInformation=find([handles.passengerInfoRBG.Children.Value])
    
startData=get(hObject,'UserData');
%S NFmin-NFmax-NFfixed
if(get(handles.NFintervalRB,'Value'))
    startData.NFmin=str2double(get(handles.NFminET,'String'));
    startData.NFmax=str2double(get(handles.NFmaxET,'String'));
else%if(get(handles.NFfixedRB,'Value'))
    startData.NFmin=str2double(get(handles.NFfixedET,'String'));
    startData.NFmax=str2double(get(handles.NFfixedET,'String'));
end
%S NCmin-NCmax-NCfixed
if(get(handles.NCintervalRB,'Value'))
    startData.NCmin=str2double(get(handles.NCminET,'String'));
    startData.NCmax=str2double(get(handles.NCmaxET,'String'));
else%if(get(handles.NCfixedRB,'Value'))
    startData.NCmin=str2double(get(handles.NCfixedET,'String'));
    startData.NCmax=str2double(get(handles.NCfixedET,'String'));
end
startData.NFstep=str2double(get(handles.NFstepET,'String'));
 
if(get(handles.FixedSelectionRB,'Value'))
    startData.INCmin=str2double(get(handles.INCfixedET,'String'));
    startData.INCmax=str2double(get(handles.INCfixedET,'String'));
    startData.INTmin=str2double(get(handles.INTfixedET,'String'));
    startData.INTmax=str2double(get(handles.INTfixedET,'String'));
    startData.OUTmin=str2double(get(handles.OUTfixedET,'String'));
    startData.OUTmax=str2double(get(handles.OUTfixedET,'String'));
       if( (startData.INCmax+startData.INTmax+startData.OUTmax)>100)
        msgbox('Sum of Incoming, Interfloor and Outgoing Traffic cannot be greater than 100');
    elseif((startData.INCmax+startData.INTmax+startData.OUTmax)<100)
        msgbox('Sum of Incoming, Interfloor and Outgoing Traffic cannot be smaller than 100');
       end
    
else
     startData.INCmin=str2double(get(handles.INCminET,'String'));
    startData.INCmax=str2double(get(handles.INCmaxET,'String'));
    startData.INTmin=str2double(get(handles.INTminET,'String'));
    startData.INTmax=str2double(get(handles.INTmaxET,'String'));
    startData.OUTmin=100-  startData.INCmax-   startData.INTmax;
    startData.OUTmax=100-  startData.INCmin-   startData.INTmin;
end
 
 
 
%ATTACH BUILDING HEIGHT TO startData
startData.floorHeight=str2double(get(handles.floorHeightET,'String'));
%ATTACH SIMULATION CONFIGURATION TO startData
startData.endTime=str2double(get(handles.SimTimeET,'String'));
startData.arrivalRate=str2double(get(handles.arrivalRateET,'String'));
startData.numOfSimulations=str2double(get(handles.NS_ET,'String'));
startData.Td=str2double(get(handles.TdET,'String'));
startData.refTime=str2double(get(handles.refTimeET,'String'));
%DISPLAY options in simulation configuration
Simulator.setgetdisplayTrafficFlow(get(handles.displayTrafficFlowCB,'Value'))
Simulator.setgetdisplayTrafficData(get(handles.displayTrafficDataCB,'Value'))
Simulator.setgetSpeed(get(handles.simulationSpeedSlider,"Value"));
%ATTACH CAR PARAMETERS TO startData
startData.doorOpeningTime=str2double(get(handles.doorOpeningET,'String'));
startData.passengerTransferTime=str2double(get(handles.transferTimeET,'String'));
startData.doorClosingTime=str2double(get(handles.doorClosingET,'String'));

startData.carCapacity=str2double(get(handles.carCapacityET,'String'));
startData.carCapacityFactor=str2double(get(handles.carCapacityFactorET,'String'));
startData.carVelocity=str2double(get(handles.carVelocityET,'String'));


startData.parkAlgorithm=[];
if(get(handles.park1,'Value'))
       startData.parkAlgorithm=1;
end
if(get(handles.park2,'Value'))
    startData.parkAlg=[startData.parkAlgorithm 2];
end
if(get(handles.park3,'Value'))
    startData.parkAlg=[startData.parkAlgorithm 3];
end 
if(get(handles.park4,'Value'))
    startData.parkAlg=[startData.parkAlgorithm 4];
end 


if(get(handles.nearestCarRB,'Value'))
    startData.decisionMaker =  NearestCarDispatcher( "fixed",availableInformation);
elseif(get(handles.gaRB,'Value'))
    G= (str2double(get(handles.generationsET,'String')));  % maximum number of generations -
    Np= (str2double(get(handles.populationET,'String')));    % Number of chromosomes
    Pc=str2double(get(handles.crossoverET,'String'));  % Crossover rate
    Pm=str2double(get(handles.mutationET,'String')); % Mutation rate 0.05 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    gaMethod=1;
    startData.decisionMaker = GeneticAlgorithmDispatcher(G,Np,Pc,Pm,gaMethod,  "flexible");
elseif(get(handles.mdpRB,'Value'))
    [A_star_universe,Svec2id,~,~,~]= MDPloadData(startData.mdpFileName);%'\6floor_20Haziran.mat');%[A_star_cell,Svec2id,Sid2vec,A,S]
     startData.decisionMaker =  MDP( "flexible",Svec2id,A_star_universe);
    % startData.method='MDP';
 %   startData.displayOption=startData.displayOption+0.5;%display update for MDP in Engine
end


 if  (get(handles.newTrafficRB,'Value')  )
        %ATTACH number of initial passengers TO startData
        startData.dataType = 1;
        startData.numInitialPassengers = str2double( get(handles.numInitialPassengersET,'String') );
 end

clc
set(hObject,'UserData',startData);

%dataConf=EXPLORER(startData);
% 
% dataConf.RECold=dataConf.RECnew;
% dataConf.RECnew={};

assignin('base','startData',startData)
experiment = Experiment();
dataConf=experiment.run(startData);
assignin('base','data',dataConf)


% --- Executes on button press in saveButton.
function saveButton_Callback(hObject, eventdata, handles)
dataConf= evalin('base','dataConf');
uisave({'dataConf'});

% hObject    handle to saveButton (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
