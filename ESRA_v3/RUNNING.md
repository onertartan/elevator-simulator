# Running the ESRA simulator (Python port)

## 1. One-time setup
    pip install -r requirements.txt        # PySide6, numpy, pandas, openpyxl, pyqtgraph
    python tests/check_real_data_structures.py   # verifies YOUR data_structures package
    python tests/test_experiment_smoke.py        # engine suite (12 tests)

## 2. Run the app
    python main.py

Then in the window:
  * Building & Car tab ... pick floors/cars (small first: 8 floors, 3 cars)
  * Traffic tab .......... select "Passenger Arrival Rate", e.g. 4 s/passenger
  * Control Method tab ... select "Nearest Car Method"  (only runnable one yet)
  * Simulation tab ....... duration e.g. 25, initial passengers e.g. 2
  * Display tab .......... "Display traffic flow" on, Display speed 2-3
                           (5 = fastest; 1 = one frame per second)
  * Press Start - the window jumps to the Display tab and animates.
    Pause/Continue and Terminate work mid-run. "Save data" pickles the
    dataConf (reload it via Simulation tab -> Recorded Traffic, *.pkl).

## 3. Still MATLAB-only (pending upload/port)
  * GA.m / ACO.m / PSO.m / DE.m + objFun*.m  (Metaheuristics path)
  * MDP path, configurationNewDataWithCustomInitials.m (dataType 3)
  * Dispatcher.m / DecisionMaker.m originals - please upload to certify
    the reconstructed decision/ base classes ([P1]-[P7] notes inside).
