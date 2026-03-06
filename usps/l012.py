"""
Parser for USPS L012 labeling list (plain-text table format).

L012 maps groups of originating ZIP codes (Column A) to a single "label to"
destination (Column B: city, state, representative ZIP).  Entries alternate:
Column-A block, Column-B block, Column-A block, …, separated by blank lines.

Column A tokens may be:
  - Individual ZIPs: "00601"
  - Hyphenated ranges: "00715-00717"  → expands to 00715, 00716, 00717
  - Comma-separated combinations of the above

Column B format: "<CITY> <STATE> <ZIP>"  (last two tokens = state + ZIP)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(slots=True)
class L012Record:
    member_zip: str   # originating ZIP (Column A member)
    dest_zip: str     # representative destination ZIP (Column B)
    dest_city: str    # destination city (Column B, uppercased)
    dest_state: str   # destination state (Column B, 2-char)


def _expand_range(token: str) -> list[str]:
    """Expand '00715-00717' → ['00715', '00716', '00717']."""
    token = token.strip()
    if "-" in token:
        start_s, end_s = token.split("-", 1)
        start, end = int(start_s), int(end_s)
        width = max(len(start_s), 5)
        return [str(z).zfill(width) for z in range(start, end + 1)]
    return [token.zfill(5)]


def _expand_col_a(text: str) -> list[str]:
    """Parse a Column A block into individual 5-digit ZIP strings."""
    zips: list[str] = []
    for token in re.split(r"[,\s]+", text.strip()):
        token = token.strip().rstrip(",")
        if not token:
            continue
        zips.extend(_expand_range(token))
    return zips


def _parse_col_b(text: str) -> tuple[str, str, str]:
    """Parse 'PONCE PR 00716' → (city='PONCE', state='PR', zip='00716')."""
    parts = text.strip().split()
    if len(parts) < 3:
        raise ValueError(f"Cannot parse Column B: {text!r}")
    dest_zip = parts[-1].zfill(5)
    dest_state = parts[-2].upper()
    dest_city = " ".join(parts[:-2]).upper()
    return dest_city, dest_state, dest_zip


def _blocks(path: Path) -> list[str]:
    """Split file into non-empty blocks separated by blank lines."""
    with open(path, encoding="latin-1") as fh:
        raw = fh.read()
    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw)]
    return [b for b in blocks if b]


def parse_file(path: str | Path) -> Iterator[L012Record]:
    """Yield one L012Record per member ZIP found in the file."""
    path = Path(path)
    blocks = _blocks(path)
    # Blocks strictly alternate: col-A (ZIP list), col-B (city state ZIP).
    #
    # Both block types contain 5-digit numbers, so we distinguish them by
    # structure:
    #   Column A — only digits, commas, hyphens, and whitespace
    #   Column B — contains alphabetic characters (city name, state code)
    col_a_re = re.compile(r"^[\d,\s\-]+$")
    col_b_re = re.compile(r"^[A-Z].*\s+[A-Z]{2}\s+\d{5}\s*$", re.DOTALL)

    # Group into (col_a, col_b) pairs
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if col_a_re.match(a) and col_b_re.match(b):
            pairs.append((a, b))
            i += 2
        else:
            i += 1

    # Also handle the last block if it's a col-A without a col-B
    # (malformed file edge case — skip it silently)

    for col_a_text, col_b_text in pairs:
        try:
            dest_city, dest_state, dest_zip = _parse_col_b(col_b_text)
        except ValueError:
            continue
        for member_zip in _expand_col_a(col_a_text):
            yield L012Record(
                member_zip=member_zip,
                dest_zip=dest_zip,
                dest_city=dest_city,
                dest_state=dest_state,
            )
