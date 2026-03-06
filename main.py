#!/usr/bin/env python3
"""
USPS ZIP-to-facility lookup CLI.

Usage:
    python main.py --l012 data/l012_sample.txt \\
                   --l606 data/l606_sample.txt \\
                   --facilities data/facilities_sample.tsv \\
                   00601 00716 00968
"""

import argparse
import sys

from usps.lookup import USPSLookup


def main() -> None:
    parser = argparse.ArgumentParser(description="Look up a USPS facility by ZIP code.")
    parser.add_argument("--l012", metavar="FILE",
                        help="L012 plain-text labeling list (general routing)")
    parser.add_argument("--l606", metavar="FILE",
                        help="L606 pipe-delimited SCF scheme labeling list")
    parser.add_argument("--facilities", metavar="FILE",
                        help="FAST facility tab-delimited export")
    parser.add_argument("--include-expired", action="store_true",
                        help="Include expired L606 records")
    parser.add_argument("zips", nargs="+", metavar="ZIP",
                        help="5-digit ZIP codes to look up")
    args = parser.parse_args()

    if not args.l012 and not args.l606:
        parser.error("At least one of --l012 or --l606 is required.")

    engine = USPSLookup()

    if args.l012:
        groups, zips = engine.load_l012(args.l012)
        print(f"Loaded {groups} L012 groups ({zips} member ZIPs).", file=sys.stderr)

    if args.l606:
        n = engine.load_l606(args.l606, active_only=not args.include_expired)
        print(f"Loaded {n} L606 records.", file=sys.stderr)

    if args.facilities:
        n = engine.load_facilities(args.facilities)
        print(f"Loaded {n} facilities.", file=sys.stderr)

    print(file=sys.stderr)

    for zip_code in args.zips:
        result = engine.lookup(zip_code)
        if result is None:
            print(f"ZIP {zip_code}: not found in any routing table.")
        else:
            print(result)
        print()


if __name__ == "__main__":
    main()
