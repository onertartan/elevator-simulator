from dataclasses import dataclass


@dataclass
class Building:
    """
    Simple container for building configuration.
    """
    nf: int

    def __init__(self, nf: int):
        self.nf = int(nf)
