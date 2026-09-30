"""
End-to-end regression test for the Python GA/custom-initials path.

The test deliberately crosses the production boundaries that the unit tests
cover separately:

    custom-initials workbook -> DataConf(dataType=3) -> Experiment.run()
    -> Controller -> GA dispatcher -> objFunDestination -> recorded result

Run from the ESRA_v3 root:
    python tests/test_ga_custom_initials_e2e.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from types import SimpleNamespace as NS

import numpy as np
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiment as experiment_module
from data_conf import recKey
from decision.meta import GA
from decision.meta.obj_funs import objFunDestination
from experiment import Experiment
from simulator import Simulator


def _write_initials_workbook(path: str) -> None:
    """Create a minimal two-car scenario with one up and one down call."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["header"] * 16)
    ws.append(["header"] * 16)
    #          A  B   C   D   E  F     G      H  I     J     K  L     M     N  O     P
    ws.append([5, 30, 40, 30, 2, 1, "true", 1, 0, None, 2, 4, None, 4, 1, None])
    ws.append([None] * 7 + [5, 0, None] + [None] * 6)
    wb.save(path)


def _ga_start_data(objective) -> NS:
    return NS(
        stateUpdateTypeForNextDecision="fixed",
        G=6,
        nPop=10,
        mutationFunction="uniform",
        parameterSearch=False,
        numberOfRuns=1,
        seed=2026,
        Pc=0.8,
        Pm=0.1,
        crossoverFcn="crossoverscattered",
        selectionFcn="selectionstochunif",
        objFun=objective,
    )


def _experiment_start_data(workbook: str, decision_maker: GA) -> NS:
    return NS(
        dataType=3,
        fileName=workbook,
        decisionMaker=decision_maker,
        refTime=0,
        endTime=0,
        arrivalRate=float("inf"),
        decisionPeriod=float("inf"),
        numSimulations=1,
        doorOpeningTime=1.0,
        passengerTransferTime=1.0,
        doorClosingTime=1.0,
        carCapacity=10,
        carCapacityFactor=0.8,
        carVelocity=1.0,
        floorHeight=1.0,
    )


def test_custom_initials_ga_destination_experiment_end_to_end():
    objective_calls = []

    def tracked_destination(cars, hall_calls, num_up, population, nf,
                            passengers, optimization_parameter="WT"):
        objective_calls.append(np.asarray(population).shape)
        return objFunDestination(
            cars, hall_calls, num_up, population, nf, passengers,
            optimization_parameter)

    ga = GA(_ga_start_data(tracked_destination))
    old_cwd = os.getcwd()
    old_sleep = experiment_module.time.sleep
    old_simulator_state = (
        Simulator._speed,
        Simulator._displayTrafficFlow,
        Simulator._displayTabularData,
        Simulator._endTime,
    )

    with tempfile.TemporaryDirectory(prefix="esra_ga_e2e_") as tmp_dir:
        workbook = os.path.join(tmp_dir, "custom_initials.xlsx")
        _write_initials_workbook(workbook)

        try:
            # Keep the integration test fast and keep its result workbook out
            # of the repository. The simulation logic and time steps remain
            # real; only UI pacing delays are disabled.
            os.chdir(tmp_dir)
            experiment_module.time.sleep = lambda _seconds: None
            Simulator._speed = None
            Simulator.getSetDisplayTrafficFlow(False)
            Simulator.getSetDisplayTabularData(False)
            Simulator.getSetEndTime(0)

            experiment = Experiment()
            data_conf = experiment.run(
                _experiment_start_data(workbook, ga))

            assert data_conf is experiment.dataConf
            assert ga.nVar == 2 and ga.maxLabel == 2
            assert objective_calls, "GA never evaluated objFunDestination"
            assert all(shape == (10, 2) for shape in objective_calls)

            record = data_conf.RECnew[recKey(1, 1, 1, 1, 1)]
            served_passengers = record.P.served[1] + record.P.served[2]
            served_calls = record.HC.served[1] + record.HC.served[2]

            assert len(served_passengers) == 2
            assert len(served_calls) == 2
            assert not record.P.waiting[1] and not record.P.waiting[2]
            assert not record.P.travelling[1] and not record.P.travelling[2]
            assert not record.HC.waiting[1] and not record.HC.waiting[2]
            assert all(p.carId in (1, 2) for p in served_passengers)
            assert all(h.carId in (1, 2) for h in served_calls)

            call_car_by_key = {
                (h.floor, h.direction): h.carId for h in served_calls
            }
            assert all(
                p.carId == call_car_by_key[(p.floor, p.direction)]
                for p in served_passengers
            ), "dispatcher assignment was not propagated to passengers"
            assert sum(c.numOfServedPassengers for c in record.cars) == 2
            assert all(c.load == 0 for c in record.cars)

            # resetVariables must operate on deep copies; the workbook-backed
            # template remains unassigned and reusable for another run.
            template_calls = (data_conf.initialHC.waiting[1]
                              + data_conf.initialHC.waiting[2])
            template_passengers = (data_conf.initialP.waiting[1]
                                   + data_conf.initialP.waiting[2])
            assert all(h.carId == 0 for h in template_calls)
            assert all(p.carId == 0 for p in template_passengers)

            assert experiment.Pawt.shape == (1, 1, 1, 1)
            assert experiment.HCawt.shape == (1, 1, 1, 1)
            assert np.isfinite(experiment.Pawt).all()
            assert np.isfinite(experiment.HCawt).all()
            result_path = os.path.abspath(experiment.resultsFile)
            assert os.path.isfile(result_path), result_path
        finally:
            os.chdir(old_cwd)
            experiment_module.time.sleep = old_sleep
            (Simulator._speed,
             Simulator._displayTrafficFlow,
             Simulator._displayTabularData,
             Simulator._endTime) = old_simulator_state

    print("PASS  dataType=3 -> Experiment -> Controller -> GA -> "
          "objFunDestination -> recorded/exported result")


if __name__ == "__main__":
    test_custom_initials_ga_destination_experiment_end_to_end()
    print("\nALL GA CUSTOM-INITIALS E2E TESTS PASSED")
