from dataclasses import dataclass
from typing import Any
from .passenger import WAITING_TIME_ENDPOINT


"""
data_structures/record.py
==========================
Port of Record.m - the per-simulation snapshot stored in
dataConf.RECnew[recKey(...)] by Simulator.recordData:

    from data_conf import recKey
    from data_structures.record import Record
    ...
    dataConf.RECnew[recKey(i.nbc, i.ncc, i.inc, i.int, i.nsc)] = \\
        Record(HC, P, cars)
"""


class Record:
    def __init__(self, HC, P, cars):
        self.waiting_time_endpoint = WAITING_TIME_ENDPOINT
        self.HC = HC
        self.P = P
        self.cars = cars
