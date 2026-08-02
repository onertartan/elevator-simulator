"""
tests/test_configuration_custom_initials.py
============================================
Verification of configuration.configurationNewDataWithCustomInitials
(port of matlab_src/utils/configurationNewDataWithCustomInitials.m)
against the reference workbook matlab_src/initials_file.xlsx, plus a
synthetic workbook exercising the assigned-cars path and the
carInitials='false' defaults.

Run from the ESRA_v3/ root:
    python tests/test_configuration_custom_initials.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_conf import DataConf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "matlab_src", "initials_file.xlsx")


def startData(fileName):
    return NS(dataType=3, fileName=fileName,
              doorOpeningTime=2.0, passengerTransferTime=3.0,
              doorClosingTime=2.0, carCapacity=10, carCapacityFactor=0.8,
              carVelocity=1.0, floorHeight=3.0)


def test_reference_workbook():
    """The uploaded initials_file.xlsx loads end-to-end via DataConf."""
    dc = DataConf(startData(XLSX))

    # scalars override the GUI grid: 1 building, 1 traffic cell, 1 fleet
    assert len(dc.BUILDING) == 1 and dc.BUILDING[0].nf == 40
    assert len(dc.TRAFFIC) == 1 and len(dc.TRAFFIC[0]) == 1
    assert len(dc.CAR) == 1 and len(dc.CAR[0]) == 8
    assert dc.initialCars is dc.CAR[0], "same objects, as in MATLAB"

    cars = dc.CAR[0]
    assert [c.floor for c in cars] == [10, 34, 6, 38, 16, 1, 20, 40]
    assert [c.previousFloor for c in cars] == [c.floor for c in cars]
    assert [c.state for c in cars] == [1, -1, 1, -1, -1, 1, 1, -1]
    assert cars[2].DF == {12, 15}, "string cell '12 15' -> two DFs"
    assert [sorted(c.DF) for c in cars] == [
        [14], [24], [12, 15], [12], [10], [8], [25], [35]]
    assert all(c.parkAlgorithm == 1 for c in cars)           # [F7]

    # every car DF -> one boarded passenger (QJT=BT=-1) in travelling
    assert [c.load for c in cars] == [1, 1, 2, 1, 1, 1, 1, 1]
    boarded = [p for c in cars for d in (1, 2) for p in c.P.travelling[d]]
    assert len(boarded) == 9
    assert all(p.QJT == -1 and p.BT == -1 for p in boarded)
    assert all(p.carId == c.id for c in cars
               for d in (1, 2) for p in c.P.travelling[d])

    # waiting passengers: floor-sorted per direction (stable), QJT 0
    up, dw = dc.initialP.waiting[1], dc.initialP.waiting[2]
    assert [(p.floor, p.DF) for p in up] == [
        (4, 8), (9, 16), (12, 20), (12, 18), (15, 20),
        (18, 23), (25, 35), (33, 38)], "stable sort keeps (12,20),(12,18)"
    assert [(p.floor, p.DF) for p in dw] == [
        (5, 1), (10, 5), (13, 6), (14, 1), (22, 4),
        (25, 20), (28, 20), (30, 25), (35, 25)], \
        "9 down passengers - sheet row 11 adds (10 -> 5)"
    assert all(p.carId == 0 and p.QJT == 0 for p in up + dw), \
        "assigned-car columns empty -> unassigned"

    # one hall call per unique floor, direction preserved, unassigned
    assert [h.floor for h in dc.initialHC.waiting[1]] == \
        [4, 9, 12, 15, 18, 25, 33]
    assert [h.floor for h in dc.initialHC.waiting[2]] == \
        [5, 10, 13, 14, 22, 25, 28, 30, 35]
    assert all(h.carId == 0 and h.direction == d
               for d in (1, 2) for h in dc.initialHC.waiting[d])
    assert dc.isInitialDispatch is False
    print("PASS  reference initials_file.xlsx loads end-to-end")


def test_assigned_cars_and_false_initials():
    """carInitials='false' keeps default cars; filled assigned-car
    columns set passenger/HC carIds and isInitialDispatch."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["h"] * 16)                                  # header row 1
    ws.append(["h"] * 16)                                  # header row 2
    #          A  B   C   D   E  F      G     H     I     J    K  L  M  N  O  P
    ws.append([6, 50, 30, 20, 2, 1, "false", None, None, None, 3, 5, 2, 5, 2, 1])
    ws.append([None] * 10 + [2, 4, 1, None, None, None])
    tmp = os.path.join(tempfile.gettempdir(), "esra_test_initials.xlsx")
    wb.save(tmp)
    try:
        dc = DataConf(startData(tmp))

        cars = dc.CAR[0]
        assert len(cars) == 2
        assert all(c.floor == 1.0 and c.state == 0 and c.DF == set()
                   for c in cars), "carInitials 'false' -> defaults kept"
        assert all(c.load == 0 for c in cars)

        up, dw = dc.initialP.waiting[1], dc.initialP.waiting[2]
        assert [(p.floor, p.DF, p.carId) for p in up] == \
            [(2, 4, 1), (3, 5, 2)], "sorted by floor, carIds follow"
        assert [(p.floor, p.DF, p.carId) for p in dw] == [(5, 2, 1)]
        assert [(h.floor, h.carId) for h in dc.initialHC.waiting[1]] == \
            [(2, 1), (3, 2)]
        assert [(h.floor, h.carId) for h in dc.initialHC.waiting[2]] == \
            [(5, 1)]
        assert dc.isInitialDispatch is True
    finally:
        os.remove(tmp)
    print("PASS  assigned-car columns + carInitials='false' defaults")


if __name__ == "__main__":
    test_reference_workbook()
    test_assigned_cars_and_false_initials()
    print("\nALL custom-initials configuration TESTS PASSED")
