"""
tests/test_gui_sweep_command.py
================================
[W1] The GUI 'parameter search' checkbox delegates to
analysis/run_parallel_sweep.py - verify the command line assembled
from startData (no QApplication needed: _sweep_command is static).

Run from the ESRA_v3/ root:
    QT_QPA_PLATFORM=offscreen python tests/test_gui_sweep_command.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.main_window import ElevatorSimulatorWindow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CAR_KEYS = {"carVelocity": 1.5, "floorHeight": 3.0,
            "doorOpeningTime": 2, "doorClosingTime": 2,
            "passengerTransferTime": 3, "carCapacity": 10,
            "carCapacityFactor": 1.0}


def test_sweep_command():
    cmd = ElevatorSimulatorWindow._sweep_command({
        "objectiveFunction": "Destination Information",
        "fileName": r"E:\somewhere\initials_file_orj.xlsx",
        "nPop": 100, "G": 50, "numberOfRuns": 10, **CAR_KEYS})
    assert cmd[0] == sys.executable
    assert cmd[1] == os.path.join(ROOT, "analysis", "run_parallel_sweep.py")
    assert cmd[2:] == ["--initials", r"E:\somewhere\initials_file_orj.xlsx",
                       "--objective", "destination",
                       "--pop", "100", "--gens", "50", "--runs", "10",
                       "--velocity", "1.5", "--floor-height", "3.0",
                       "--door-open", "2", "--door-close", "2",
                       "--transfer-time", "3", "--capacity", "10",
                       "--capacity-factor", "1.0"]

    cmd = ElevatorSimulatorWindow._sweep_command({
        "objectiveFunction": "Conventional Information",
        "fileName": "f.xlsx", "nPop": 40, "G": 20, "numberOfRuns": 3,
        **dict(CAR_KEYS, carVelocity=2.0)})
    assert cmd[cmd.index("--objective") + 1] == "conventional"
    assert cmd[cmd.index("--runs") + 1] == "3"
    assert cmd[cmd.index("--velocity") + 1] == "2.0"
    print("PASS  [W1] GUI parameter-search command assembly + car params")


if __name__ == "__main__":
    test_sweep_command()
    print("\nAll GUI sweep-command tests passed.")
