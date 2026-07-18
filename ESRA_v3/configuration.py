"""
configuration.py
================
Python port of the DataConf case-1 helper function files:
    configurationNewData.m, generateBuildingConf.m,
    generateCarConf.m, generateTrafficConf.m
data_conf.DataConf imports these lazily for dataType 1 (and 3, once
configurationNewDataWithCustomInitials.m is uploaded and ported).

Deviations / fixes ([F1]..[F3] inline):

  [F1] generateTrafficConf hardcodes a 10-percentage-point grid step
       (INCmin:10:INCmax). Exposed as TRAFFIC_STEP so that
       Experiment.saveResults labels rows/columns with the same step
       (see experiment.py [D8]).

  [F2] The parking-algorithm chain was broken in MATLAB three ways:
       (a) the GUI put the DropDown *widget handle* into
           startData.parkingAlgorithm, not its value;
       (b) the loop variable `parkAlgorithm` was never written onto the
           cars, so setParkFloor compared against Car's default (1);
       (c) consequently Park2..Park4 never changed anything.
       The port parses the GUI string ("Park2" -> 2, "Park1 (No parking
       method)" -> 1), assigns it to each car, then applies
       setParkFloor - so parking selections behave as evidently
       intended. Park1 remains "no parking" (parkFloor stays 'N/A').

  [F3] MATLAB reused a stale function-local `cars` array across
       configurations (safe only because NCmin:NCmax ascends); the port
       builds a fresh list per configuration.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional

from building import Building
from car import Car
from traffic import Traffic

TRAFFIC_STEP = 10  # [F1] MATLAB: INCmin:10:INCmax / INTmin:10:INTmax


def configurationNewData(startData: Any, dataConf: Any) -> None:
    """Port of configurationNewData.m (in-place population of dataConf)."""
    # Building configuration
    dataConf.BUILDING = generateBuildingConf(startData)
    # Simulation configuration: `data.simulation = Simulation(startData)`
    # was commented out in the MATLAB source - kept out here too.
    # Car configuration
    dataConf.CAR = generateCarConf(startData)
    # Traffic configuration
    dataConf.TRAFFIC = generateTrafficConf(startData)


def configurationNewDataWithCustomInitials(startData: Any, dataConf: Any) -> None:
    raise NotImplementedError(
        "configurationNewDataWithCustomInitials.m has not been uploaded/"
        "ported yet (needed only for dataType=3).")


def generateBuildingConf(startData: Any) -> List[Building]:
    """Port of generateBuildingConf.m: one Building per NFmin:NFstep:NFmax."""
    return [Building(n_floor)
            for n_floor in range(int(startData.NFmin),
                                 int(startData.NFmax) + 1,
                                 int(startData.NFstep))]


def generateCarConf(startData: Any) -> List[List[Car]]:
    """
    Port of generateCarConf.m: one car list per
    (number of cars) x (parking algorithm) combination.
    """
    parkingAlgorithms = _parseParkingAlgorithms(startData.parkingAlgorithm)
    CAR: List[List[Car]] = []
    for n_car in range(int(startData.NCmin), int(startData.NCmax) + 1):
        for parkAlgorithm in parkingAlgorithms:
            cars: List[Car] = []                     # [F3] fresh list
            for car_id in range(1, n_car + 1):
                car = Car(startData, car_id)
                car.parkAlgorithm = parkAlgorithm    # [F2b] actually applied
                _setParkFloor(car)
                cars.append(car)
            CAR.append(cars)
    return CAR


def _setParkFloor(car: Car) -> None:
    """Port of the nested setParkFloor function in generateCarConf.m."""
    if car.parkAlgorithm == 2:
        car.parkFloor = 1


def generateTrafficConf(startData: Any) -> List[List[Optional[Traffic]]]:
    """
    Port of generateTrafficConf.m: rows = incoming %, cols = interfloor %,
    both stepping by TRAFFIC_STEP. Combinations with inc + int > 100 are
    invalid and stored as None (MATLAB: Traffic.empty) - Experiment.run
    skips them and saveResults reports NaN for them.
    """
    Traffic.getSetNumInitialPassengers(startData.numInitialPassengers)

    incValues = range(int(startData.INCmin), int(startData.INCmax) + 1,
                      TRAFFIC_STEP)
    intValues = range(int(startData.INTmin), int(startData.INTmax) + 1,
                      TRAFFIC_STEP)

    TRAFFIC: List[List[Optional[Traffic]]] = []
    for inc in incValues:
        row: List[Optional[Traffic]] = []
        for int_ in intValues:
            row.append(Traffic(inc, int_) if (100 - inc - int_) >= 0 else None)
        TRAFFIC.append(row)
    return TRAFFIC


def _parseParkingAlgorithms(value: Any) -> List[int]:
    """
    [F2a] Normalizes startData.parkingAlgorithm into a list of ints.
    Accepts an int, a list/tuple of ints or strings, or GUI strings such
    as 'Park2' / 'Park1 (No parking method)' (first digit run is taken).
    """
    if isinstance(value, (list, tuple)):
        out: List[int] = []
        for v in value:
            out.extend(_parseParkingAlgorithms(v))
        return out
    if isinstance(value, bool):
        raise ValueError(f"Cannot interpret parkingAlgorithm: {value!r}")
    if isinstance(value, int):
        return [value]
    if isinstance(value, float) and value.is_integer():
        return [int(value)]
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return [int(match.group())]
    raise ValueError(f"Cannot interpret parkingAlgorithm: {value!r}")
