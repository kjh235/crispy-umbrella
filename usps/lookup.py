"""
ZIP-to-facility lookup engine.

Routing resolution order
------------------------
1. **L012** (if loaded) — general routing list covering all PR/VI ZIPs.
   Maps member ZIP → (dest city, dest state, dest ZIP).
2. **L606** (if loaded) — SCF scheme labeling list.
   Maps member ZIP → (finance number, dest ZIP, dest city, dest state).

Facility matching order (applied to whichever routing source matched)
----------------------------------------------------------------------
1. Exact 5-digit ZIP match  (dest ZIP ↔ facility zip5)
2. City + state match        (dest city/state ↔ facility city/state)

The city+state fallback is essential because L012 destination ZIPs (e.g.
00716 for Ponce) often differ from the facility's street ZIP (e.g. 00730 for
ATOCHA station), while the city name ("PONCE") matches exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .facility import Facility, parse_file as parse_facilities
from .l012 import L012Record, parse_file as parse_l012
from .l606 import L606Record, parse_file as parse_l606


@dataclass(slots=True)
class LookupResult:
    query_zip: str
    dest_zip: str
    dest_city: str
    dest_state: str
    finance_number: str          # empty string when resolved via L012
    route_source: Literal["L012", "L606"]
    facility_match: Literal["zip", "city_state", "none"]
    facility: Facility | None

    def __str__(self) -> str:
        f = self.facility
        match_note = {
            "zip": "matched by ZIP",
            "city_state": "matched by city+state",
            "none": "no facility match",
        }[self.facility_match]
        header = (
            f"ZIP {self.query_zip} → {self.dest_city}, {self.dest_state} "
            f"{self.dest_zip}  [{self.route_source} / {match_note}]"
        )
        if f is None:
            return header
        return (
            f"{header}\n"
            f"  Facility: {f.name} ({f.facility_type})\n"
            f"  Address : {f.address}, {f.city}, {f.state} {f.zip9}\n"
            f"  District: {f.district}   Dropsite Key: {f.dropsite_key}\n"
            f"  DSC     : {f.dsc_name} {f.dsc_phone} / {f.dsc_email}\n"
            f"  Active in FAST: {f.active_in_fast}"
        )


class USPSLookup:
    """In-memory lookup engine.  Load one or more of L012, L606, facilities."""

    def __init__(self) -> None:
        self._l012: dict[str, L012Record] = {}
        self._l606: dict[str, L606Record] = {}
        # Facility indices
        self._by_zip5: dict[str, list[Facility]] = {}
        self._by_city_state: dict[tuple[str, str], list[Facility]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_l012(self, path: str | Path) -> int:
        """Load (or merge) an L012 text file.  Returns record count."""
        count = 0
        for rec in parse_l012(path):
            self._l012[rec.member_zip] = rec
            count += 1
        return count

    def load_l606(self, path: str | Path, active_only: bool = True) -> int:
        """Load (or merge) an L606 pipe-delimited file.  Returns record count."""
        count = 0
        for rec in parse_l606(path, active_only=active_only):
            self._l606[rec.member_zip] = rec
            count += 1
        return count

    def load_facilities(self, path: str | Path) -> int:
        """Load (or merge) a FAST facility export.  Returns record count."""
        count = 0
        for fac in parse_facilities(path):
            self._by_zip5.setdefault(fac.zip5, []).append(fac)
            key = (fac.city.upper().strip(), fac.state.upper().strip())
            self._by_city_state.setdefault(key, []).append(fac)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, query_zip: str) -> LookupResult | None:
        """Resolve *query_zip* to a destination and, if possible, a facility."""
        query_zip = query_zip.strip().zfill(5)

        # 1. Determine routing
        if query_zip in self._l012:
            rec = self._l012[query_zip]
            dest_zip, dest_city, dest_state = rec.dest_zip, rec.dest_city, rec.dest_state
            finance_number = ""
            source: Literal["L012", "L606"] = "L012"
        elif query_zip in self._l606:
            rec = self._l606[query_zip]  # type: ignore[assignment]
            dest_zip, dest_city, dest_state = rec.dest_zip, rec.dest_city, rec.dest_state
            finance_number = rec.finance_number
            source = "L606"
        else:
            return None

        # 2. Match facility
        facility, match_type = self._resolve_facility(
            dest_zip[:5], dest_city, dest_state
        )
        return LookupResult(
            query_zip=query_zip,
            dest_zip=dest_zip,
            dest_city=dest_city,
            dest_state=dest_state,
            finance_number=finance_number,
            route_source=source,
            facility_match=match_type,
            facility=facility,
        )

    def lookup_many(self, zips: list[str]) -> list[LookupResult | None]:
        return [self.lookup(z) for z in zips]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_facility(
        self, zip5: str, city: str, state: str
    ) -> tuple[Facility | None, Literal["zip", "city_state", "none"]]:
        # Try exact ZIP match first
        candidates = self._by_zip5.get(zip5, [])
        if candidates:
            return self._best(candidates), "zip"

        # Fall back to city + state match
        key = (city.upper().strip(), state.upper().strip())
        candidates = self._by_city_state.get(key, [])
        if candidates:
            return self._best(candidates), "city_state"

        return None, "none"

    @staticmethod
    def _best(candidates: list[Facility]) -> Facility:
        """Return the highest-priority facility from a non-empty list."""
        active = [f for f in candidates if f.active_in_fast.lower() == "yes"]
        return (active or candidates)[0]
