#!/usr/bin/env python3
"""
USPS ZIP-to-facility lookup CLI.

Usage:
    python main.py --l606 data/l606.txt --facilities data/facilities.tsv 00603 00612 00680
"""

import argparse
import sys

from usps.lookup import USPSLookup


def main() -> None:
    parser = argparse.ArgumentParser(description="Look up a USPS facility by ZIP code.")
    parser.add_argument("--l606", required=True, metavar="FILE",
                        help="Path to the L606 pipe-delimited labeling list file")
    parser.add_argument("--facilities", required=True, metavar="FILE",
                        help="Path to the FAST facility tab-delimited file")
    parser.add_argument("--all", action="store_true",
                        help="Include expired L606 records")
    parser.add_argument("zips", nargs="+", metavar="ZIP",
                        help="One or more 5-digit ZIP codes to look up")
    args = parser.parse_args()

    engine = USPSLookup()

    l606_count = engine.load_l606(args.l606, active_only=not args.all)
    fac_count = engine.load_facilities(args.facilities)
    print(f"Loaded {l606_count} L606 records, {fac_count} facilities.\n",
          file=sys.stderr)

    for zip_code in args.zips:
        result = engine.lookup(zip_code)
        if result is None:
            print(f"ZIP {zip_code}: not found in L606 routing table.")
        else:
            print(result)
        print()


if __name__ == "__main__":
    main()
