# crispy-umbrella
USPS network config

## USPS ZIP-to-facility lookup

Given a 5-digit ZIP code, resolve the destination USPS facility (name,
address, dropsite key) using two data sources:

| File | Format | Source |
|------|--------|--------|
| L606 labeling list | Pipe-delimited, 19 fields | USPS PostalPro |
| FAST facility export | Tab-delimited Excel export | USPS FAST portal |

### How it works

1. **L606** maps every *member ZIP* (Column A) to a *destination ZIP* (Column B)
   plus a finance number and destination city/state.
2. **Facility file** stores USPS facility details indexed by their ZIP code.
3. The **lookup engine** chains these: `query ZIP → L606 → dest ZIP → facility`.

> **Note on the join:** L606 destination ZIPs identify the SCF/P&DC sortation
> point, which may differ from the street ZIP of a downstream delivery unit.
> If your facility file contains delivery units rather than SCFs, some lookups
> will return routing information (dest ZIP, city, state) without a matched
> facility record.  Load the appropriate facility tier (SCF/P&DC) to get full
> facility resolution.

### Usage

```bash
python main.py --l606 data/l606.txt --facilities data/facilities.tsv 00603 00716
```

Sample data for testing is in `data/l606_sample.txt` and
`data/facilities_sample.tsv`.

### Package layout

```
usps/
  l606.py       Parse L606 pipe-delimited labeling list → L606Record
  facility.py   Parse FAST tab-delimited facility export → Facility
  lookup.py     USPSLookup engine + LookupResult
main.py         CLI entry point
data/           Sample files (do not commit production data)
```

### L606 field mapping

| Field | Name |
|-------|------|
| 1 | Finance number |
| 2 | Record flag |
| 3 | Member ZIP (Column A) |
| 4–6 | Reserved |
| 7 | Destination city |
| 8 | Destination state |
| 9 | Destination ZIP (Column B) |
| 10 | Code |
| 11 | Dropsite key variant |
| 12 | Flag |
| 13–15 | Reserved |
| 16 | Effective date (MMDDYYYY) |
| 17 | Expiration date (MMDDYYYY; `12312999` = no expiry) |
| 18 | Reserved |
| 19 | Publication date (MMDDYYYY) |
