"""
Parser for USPS FAST facility file (tab-delimited Excel export).

The file uses a two-row merged header and alternating spacer columns (every
odd column is a visual separator containing a single space).  Column layout
for data rows:

  Col  2: NASS Code
  Col  4: Facility Name
  Col  6: Facility Type
  Col  8: District
  Col 10: BMEU
  Col 12: Dropsite Key
  Col 14: Address
  Col 16: City
  Col 18: State
  Col 20: ZIP Code (9-digit, no dash, e.g. "009796607")
  Col 22: Drop Ship Coordinator — Name
  Col 24: Drop Ship Coordinator — Phone
  Col 26: Drop Ship Coordinator — E-Mail
  Col 28: Drop Ship Coordinator — After Hours Number
  Col 30: Active in FAST
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Minimum columns a data row must have to be considered valid
_MIN_COLS = 25

# Columns that identify a row as a header / separator to skip
_SKIP_TOKENS = {"NASS Code", "Facility Name", "Name", "Phone", "E-Mail", "District"}


def _cell(row: list[str], idx: int) -> str:
    try:
        return row[idx].strip()
    except IndexError:
        return ""


def _is_data_row(row: list[str]) -> bool:
    """True if the row looks like a real data row (not a header or blank line)."""
    if len(row) < _MIN_COLS:
        return False
    # Non-blank content at the Facility Name column indicates a data row
    if not _cell(row, 4):
        return False
    # Skip rows whose col-4 value is a header token
    return _cell(row, 4) not in _SKIP_TOKENS


@dataclass(slots=True)
class Facility:
    nass_code: str
    name: str
    facility_type: str
    district: str
    bmeu: bool | None          # True/False/None (None = not specified)
    dropsite_key: str
    address: str
    city: str
    state: str
    zip9: str                  # 9-digit, e.g. "009796607"
    dsc_name: str
    dsc_phone: str
    dsc_email: str
    dsc_after_hours: str
    active_in_fast: str        # "Yes" / "No" / "Pending"

    @property
    def zip5(self) -> str:
        """First 5 digits of the 9-digit ZIP."""
        return self.zip9[:5]


def _parse_bmeu(val: str) -> bool | None:
    v = val.strip().lower()
    if v == "yes":
        return True
    if v == "no":
        return False
    return None


def parse_file(path: str | Path) -> Iterator[Facility]:
    """Yield Facility objects from a FAST facility export file."""
    with open(path, newline="", encoding="latin-1") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            if not _is_data_row(row):
                continue
            yield Facility(
                nass_code=_cell(row, 2),
                name=_cell(row, 4),
                facility_type=_cell(row, 6),
                district=_cell(row, 8),
                bmeu=_parse_bmeu(_cell(row, 10)),
                dropsite_key=_cell(row, 12),
                address=_cell(row, 14),
                city=_cell(row, 16),
                state=_cell(row, 18),
                zip9=_cell(row, 20),
                dsc_name=_cell(row, 22),
                dsc_phone=_cell(row, 24),
                dsc_email=_cell(row, 26),
                dsc_after_hours=_cell(row, 28),
                active_in_fast=_cell(row, 30),
            )
