"""Tiny SYNTHETIC workbook, keeping real 16-call snapshots out of unit tests."""
import openpyxl


def write_small_reference(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sayfa1"
    ws.append(["header"] * 16)
    ws.append(["header"] * 16)
    #          A  B   C   D   E  F     G      H  I  J  K  L     M     N  O     P
    ws.append([8, 30, 40, 30, 2, 1, "true", 1, 1, 5, 2, 4, None, 7, 3, None])
    ws.append([None] * 7 + [8, -1, 4, None, None, None, 6, 2, None])
    wb.save(path)
    wb.close()
