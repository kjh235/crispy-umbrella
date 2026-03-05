"""
Parser for USPS L606 labeling list (pipe-delimited).

Field layout (1-indexed):
  1  Finance number
  2  Record flag
  3  Member ZIP (Column A — the ZIP being routed)
  4-6 Reserved (empty)
  7  Destination city
  8  Destination state
  9  Destination ZIP (Column B — where to route)
  10 Code
  11 Dropsite key variant (e.g. V17137)
  12 Flag
  13-15 Reserved
  16 Effective date (MMDDYYYY)
  17 Expiration date (MMDDYYYY; 12312999 = no expiry)
  18 Reserved
  19 Publication date (MMDDYYYY)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator


_FOREVER = date(2999, 12, 31)


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%m%d%Y").date()
    except ValueError:
        return None


@dataclass(slots=True)
class L606Record:
    finance_number: str
    record_flag: str
    member_zip: str          # Column A — the ZIP being routed
    dest_city: str
    dest_state: str
    dest_zip: str            # Column B — destination ZIP
    code: str
    dropsite_key: str        # e.g. "V17137"
    flag: str
    effective_date: date | None
    expiration_date: date | None
    publication_date: date | None

    @property
    def is_active(self) -> bool:
        today = date.today()
        if self.effective_date and today < self.effective_date:
            return False
        if self.expiration_date and self.expiration_date != _FOREVER and today > self.expiration_date:
            return False
        return True


def parse_file(path: str | Path, active_only: bool = True) -> Iterator[L606Record]:
    """Yield L606Record objects from a pipe-delimited L606 file."""
    with open(path, newline="", encoding="latin-1") as fh:
        reader = csv.reader(fh, delimiter="|")
        for row in reader:
            if len(row) < 19:
                continue
            rec = L606Record(
                finance_number=row[0].strip(),
                record_flag=row[1].strip(),
                member_zip=row[2].strip(),
                dest_city=row[6].strip(),
                dest_state=row[7].strip(),
                dest_zip=row[8].strip(),
                code=row[9].strip(),
                dropsite_key=row[10].strip(),
                flag=row[11].strip(),
                effective_date=_parse_date(row[15]),
                expiration_date=_parse_date(row[16]),
                publication_date=_parse_date(row[18]),
            )
            if active_only and not rec.is_active:
                continue
            yield rec
