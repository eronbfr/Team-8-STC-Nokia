"""
Merge spreadsheet data: combines the existing (old) xlsx from git history
with the newly uploaded xlsx so that no data is lost.

Logic:
- For each member/date cell, if both files have a non-zero value, the new
  value takes precedence.
- If only the old file has a value (and the new cell is 0 or empty), the
  old value is preserved.
- Members and dates are matched by name/date value.

Run by the CI workflow before dashboard_steps.py.
"""

import io
import os
import subprocess
import sys
from datetime import datetime

import openpyxl


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_NAME = 'step-tracking_Team8.xlsx'
XLSX_PATH = os.path.join(BASE_DIR, XLSX_NAME)


def _get_old_xlsx_bytes():
    """Return the previous version of the xlsx from git history, or None."""
    try:
        result = subprocess.run(
            ['git', 'show', 'HEAD~1:' + XLSX_NAME],
            capture_output=True,
            cwd=BASE_DIR,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception:
        pass
    return None


def _read_data(wb):
    """Read member step data from a workbook.

    Returns:
        dates: list of date values (datetime or str) from row 2
        members: dict of {name: {col_index: steps_value}}
    """
    # Try known sheet names, fall back to first sheet
    for name in ('Team 8', 'Team X'):
        if name in wb.sheetnames:
            ws = wb[name]
            break
    else:
        ws = wb[wb.sheetnames[0]]

    # Read dates from row 2, columns E (5) onwards
    dates = {}
    for col in range(5, ws.max_column + 1):
        val = ws.cell(row=2, column=col).value
        if val is not None:
            # Normalize to string for matching
            if isinstance(val, datetime):
                key = val.strftime('%Y-%m-%d')
            else:
                key = str(val)
            dates[col] = (key, val)

    # Read member rows (3–12)
    members = {}
    for row in range(3, min(13, ws.max_row + 1)):
        name = ws.cell(row=row, column=2).value
        if not name:
            continue
        name = str(name).strip()
        steps = {}
        for col, (date_key, _) in dates.items():
            val = ws.cell(row=row, column=col).value
            if val and isinstance(val, (int, float)):
                steps[date_key] = val
        members[name] = steps

    return dates, members


def merge():
    """Merge old and new xlsx data, writing the result back to the xlsx."""
    if not os.path.exists(XLSX_PATH):
        print("merge_xlsx: No xlsx file found, nothing to merge.")
        return

    old_bytes = _get_old_xlsx_bytes()
    if old_bytes is None:
        print("merge_xlsx: No previous version in git history, skipping merge.")
        return

    # Read old workbook
    try:
        old_wb = openpyxl.load_workbook(io.BytesIO(old_bytes), data_only=True)
    except Exception as exc:
        print(f"merge_xlsx: Could not read old xlsx: {exc}")
        return

    # Read new (current) workbook – keep styles by not using data_only
    new_wb = openpyxl.load_workbook(XLSX_PATH)

    old_dates, old_members = _read_data(old_wb)
    new_dates, new_members = _read_data(new_wb)

    # Get the worksheet from the new workbook
    for name in ('Team 8', 'Team X'):
        if name in new_wb.sheetnames:
            ws = new_wb[name]
            break
    else:
        ws = new_wb[new_wb.sheetnames[0]]

    # Build a mapping from date_key -> column index in the NEW workbook
    new_date_to_col = {date_key: col for col, (date_key, _) in new_dates.items()}

    # Build a mapping from member name -> row index in the NEW workbook
    new_name_to_row = {}
    for row in range(3, min(13, ws.max_row + 1)):
        name = ws.cell(row=row, column=2).value
        if name:
            new_name_to_row[str(name).strip()] = row

    merged_count = 0

    for member_name, old_steps in old_members.items():
        if member_name not in new_name_to_row:
            continue  # member not in new sheet, skip
        row = new_name_to_row[member_name]
        new_steps = new_members.get(member_name, {})

        for date_key, old_val in old_steps.items():
            if date_key not in new_date_to_col:
                continue  # date column not in new sheet
            col = new_date_to_col[date_key]
            new_val = new_steps.get(date_key, 0)

            # If new cell is empty/zero but old had data, restore old value
            if (not new_val or new_val == 0) and old_val and old_val != 0:
                ws.cell(row=row, column=col).value = old_val
                merged_count += 1

    if merged_count > 0:
        new_wb.save(XLSX_PATH)
        print(f"merge_xlsx: Restored {merged_count} cell(s) from previous version.")
    else:
        print("merge_xlsx: No cells needed restoring; new file already has all data.")

    old_wb.close()
    new_wb.close()


if __name__ == '__main__':
    merge()
