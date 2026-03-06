"""
ZIP-to-facility lookup engine.

L012 dispatch groups
--------------------
L012 defines *groups* of originating ZIP codes that are consolidated together
and dispatched as a single unit to the Column B destination.  The group is
the fundamental network configuration element: all member ZIPs share the same
dispatch and land at the same facility.

Routing resolution order
------------------------
1. **L012** (if loaded) — general routing list covering all PR/VI ZIPs.
2. **L606** (if loaded) — SCF scheme labeling list (finance-number keyed).

Facility matching order
-----------------------
1. Exact 5-digit ZIP match  (dest ZIP ↔ facility zip5)
2. City + state match        (dest city/state ↔ facility city/state)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .facility import Facility, parse_file as parse_facilities
from .l012 import L012Group, parse_file as parse_l012
from .l606 import L606Record, parse_file as parse_l606


@dataclass(slots=True)
class LookupResult:
    query_zip: str
    dest_zip: str
    dest_city: str
    dest_state: str
    finance_number: str             # empty string when resolved via L012
    route_source: Literal["L012", "L606"]
    # The full dispatch group from L012 (None when routed via L606 only)
    dispatch_group: L012Group | None
    facility_match: Literal["zip", "city_state", "none"]
    facility: Facility | None

    @property
    def group_size(self) -> int:
        """Number of ZIPs consolidated in this dispatch group (0 if N/A)."""
        return len(self.dispatch_group.member_zips) if self.dispatch_group else 0

    def __str__(self) -> str:
        f = self.facility
        match_note = {
            "zip": "matched by ZIP",
            "city_state": "matched by city+state",
            "none": "no facility match",
        }[self.facility_match]

        lines = [
            f"ZIP {self.query_zip} → {self.dest_city}, {self.dest_state} "
            f"{self.dest_zip}  [{self.route_source} / {match_note}]"
        ]

        if self.dispatch_group:
            zips = self.dispatch_group.member_zips
            preview = ", ".join(zips[:8])
            tail = f" … +{len(zips) - 8} more" if len(zips) > 8 else ""
            lines.append(f"  Group   : {len(zips)} ZIPs — {preview}{tail}")

        if f is not None:
            lines += [
                f"  Facility: {f.name} ({f.facility_type})",
                f"  Address : {f.address}, {f.city}, {f.state} {f.zip9}",
                f"  District: {f.district}   Dropsite Key: {f.dropsite_key}",
                f"  DSC     : {f.dsc_name} {f.dsc_phone} / {f.dsc_email}",
                f"  Active in FAST: {f.active_in_fast}",
            ]

        return "\n".join(lines)


class USPSLookup:
    """In-memory lookup engine.  Load one or more of L012, L606, facilities."""

    def __init__(self) -> None:
        # member_zip → L012Group
        self._l012: dict[str, L012Group] = {}
        # member_zip → L606Record
        self._l606: dict[str, L606Record] = {}
        # Facility indices
        self._by_zip5: dict[str, list[Facility]] = {}
        self._by_city_state: dict[tuple[str, str], list[Facility]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_l012(self, path: str | Path) -> tuple[int, int]:
        """Load (or merge) an L012 text file.

        Returns (group_count, zip_count).
        """
        groups = 0
        zips = 0
        for group in parse_l012(path):
            for member_zip in group.member_zips:
                self._l012[member_zip] = group
                zips += 1
            groups += 1
        return groups, zips

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
        """Resolve *query_zip* to its dispatch group, destination, and facility."""
        query_zip = query_zip.strip().zfill(5)

        group: L012Group | None = None

        if query_zip in self._l012:
            group = self._l012[query_zip]
            dest_zip, dest_city, dest_state = (
                group.dest_zip, group.dest_city, group.dest_state
            )
            finance_number = ""
            source: Literal["L012", "L606"] = "L012"
        elif query_zip in self._l606:
            rec = self._l606[query_zip]
            dest_zip, dest_city, dest_state = (
                rec.dest_zip, rec.dest_city, rec.dest_state
            )
            finance_number = rec.finance_number
            source = "L606"
        else:
            return None

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
            dispatch_group=group,
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
        candidates = self._by_zip5.get(zip5, [])
        if candidates:
            return self._best(candidates), "zip"

        key = (city.upper().strip(), state.upper().strip())
        candidates = self._by_city_state.get(key, [])
        if candidates:
            return self._best(candidates), "city_state"

        return None, "none"

    @staticmethod
    def _best(candidates: list[Facility]) -> Facility:
        active = [f for f in candidates if f.active_in_fast.lower() == "yes"]
        return (active or candidates)[0]
