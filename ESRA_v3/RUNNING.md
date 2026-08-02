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
  * Control Method tab ... "Nearest Car Method", or Metaheuristics/GA
                           (objective: Conventional/Destination Information)
  * Simulation tab ....... duration e.g. 25, initial passengers e.g. 2
  * Display tab .......... "Display traffic flow" on, Display speed 2-3
                           (5 = fastest; 1 = one frame per second)
  * Press Start - the window jumps to the Display tab and animates.
    Pause/Continue and Terminate work mid-run. "Save data" pickles the
    dataConf (reload it via Simulation tab -> Recorded Traffic, *.pkl).

## 3. Still MATLAB-only (pending upload/port)
  * ACO.m / PSO.m / DE.m  (GA + objFunConventional1/objFunDestination
    are ported; remaining objFuns: Number of Passengers, user-defined)
  * MDP path (dataType 3 'New Traffic with Custom Initials' is now
    ported - configuration.py [F4]-[F7], matlab_src/utils originals)
  * (Dispatcher.m / DecisionMaker.m originals uploaded - decision/
    base classes CERTIFIED; findings in decision/decision_maker.py
    and decision/dispatcher.py docstrings.)
