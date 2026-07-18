"""
main.py
=======
Entry point for the elevator simulator app. Run from the ESRA/ root:

    python main.py
"""
import sys
from PySide6.QtWidgets import QApplication

from gui.main_window import ElevatorSimulatorWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ElevatorSimulatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
