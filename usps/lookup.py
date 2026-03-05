"""
ZIP-to-facility lookup engine.

Join strategy
-------------
1. L606 maps *member ZIP* → *destination ZIP* (field 3 → field 9).
2. Facility records are indexed by the first 5 digits of their 9-digit ZIP.
3. Given a query ZIP, find its destination ZIP in L606, then find the matching
   facility by that ZIP.

If multiple facilities share the same 5-digit ZIP the one with the most
specific match is preferred (active-in-FAST facilities first).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .facility import Facility, parse_file as parse_facilities
from .l606 import L606Record, parse_file as parse_l606


@dataclass(slots=True)
class LookupResult:
    query_zip: str
    dest_zip: str          # resolved destination ZIP from L606
    dest_city: str
    dest_state: str
    finance_number: str
    facility: Facility | None

    def __str__(self) -> str:
        f = self.facility
        if f is None:
            return (
                f"ZIP {self.query_zip} → dest ZIP {self.dest_zip} "
                f"({self.dest_city}, {self.dest_state}) — no matching facility found"
            )
        return (
            f"ZIP {self.query_zip} → {f.name} ({f.facility_type})\n"
            f"  Address : {f.address}, {f.city}, {f.state} {f.zip9}\n"
            f"  District: {f.district}   Dropsite Key: {f.dropsite_key}\n"
            f"  DSC     : {f.dsc_name} {f.dsc_phone} / {f.dsc_email}\n"
            f"  Active in FAST: {f.active_in_fast}"
        )


class USPSLookup:
    """In-memory lookup engine built from an L606 file and a facility file."""

    def __init__(self) -> None:
        # member_zip → L606Record (last record wins; caller can sort by date first)
        self._routes: dict[str, L606Record] = {}
        # zip5 → list[Facility]
        self._facilities: dict[str, list[Facility]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_l606(self, path: str | Path, active_only: bool = True) -> int:
        """Load (or merge) an L606 file.  Returns number of records loaded."""
        count = 0
        for rec in parse_l606(path, active_only=active_only):
            self._routes[rec.member_zip] = rec
            count += 1
        return count

    def load_facilities(self, path: str | Path) -> int:
        """Load (or merge) a facility file.  Returns number of records loaded."""
        count = 0
        for fac in parse_facilities(path):
            self._facilities.setdefault(fac.zip5, []).append(fac)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, query_zip: str) -> LookupResult | None:
        """Return the best-matching facility for *query_zip*, or None if not found."""
        query_zip = query_zip.strip().zfill(5)
        route = self._routes.get(query_zip)
        if route is None:
            return None

        facility = self._best_facility(route.dest_zip[:5])
        return LookupResult(
            query_zip=query_zip,
            dest_zip=route.dest_zip,
            dest_city=route.dest_city,
            dest_state=route.dest_state,
            finance_number=route.finance_number,
            facility=facility,
        )

    def lookup_many(self, zips: list[str]) -> list[LookupResult | None]:
        return [self.lookup(z) for z in zips]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _best_facility(self, zip5: str) -> Facility | None:
        """Find best facility by exact 5-digit ZIP match.

        Note: L606 destination ZIPs refer to the SCF/P&DC sortation point and
        may differ from the street ZIP of a delivery unit.  If no exact match
        exists, callers should treat the LookupResult.dest_zip / dest_city /
        dest_state fields as the routing label even without a resolved facility.
        """
        candidates = self._facilities.get(zip5, [])
        if not candidates:
            return None
        # Prefer active-in-FAST facilities
        active = [f for f in candidates if f.active_in_fast.lower() == "yes"]
        return (active or candidates)[0]
