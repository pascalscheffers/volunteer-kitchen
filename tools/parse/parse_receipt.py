#!/usr/bin/env python3
"""Parse a receipt OCR JSON (produced by tools/ocr's receipt-ocr) into a TSV
of line items, gated on an honest checksum against the receipt's own subtotal.

Usage:
    python3 tools/parse/parse_receipt.py <ocr.json>

Prints `line\tname\tqty\tunit_price\ttotal\tneeds_review\tderived` (header +
one row per item) to stdout, always — even on a PARTIAL result — so a later
enrichment pass has the full parse to work from. Deliberately decoupled from
the Swift OCR tool: it only ever reads the JSON it produces, never shells out
to it.

The gate proves "no fabricated numbers", not "sum forced to match":

  - `total` is left empty for any cell OCR genuinely could not read; that row
    is flagged `needs_review=1`. This is a valid *partial* parse for a human
    (or a later enrichment pass) to complete — the parser never guesses a
    read value it doesn't have.
  - `derived=1` marks the one allowance: when exactly one cell is unreadable,
    its value is inferred by subtracting the read rows from the receipt's own
    `I alt`. It is flagged so it can never masquerade as a read value.

Exit codes:
    0  PASS — every numeric cell was read and the totals reconcile to the
       vendor's subtotal (within 0.02), OR exactly one cell was derived and
       the rest reconcile. No fabricated reads.
    1  bad usage / unreadable input / unknown vendor / parser error.
    2  PARTIAL — one or more cells are still flagged needs_review, or the read
       cells don't reconcile. The full TSV is still printed to stdout; stderr
       lists the flagged rows and the residual they must account for.
"""

import json
import sys

import detect_vendor
import vendors

CHECKSUM_TOLERANCE = 0.02


def _fmt(value):
    """TSV cell: empty string for an unread (None) numeric, else the value."""
    return "" if value is None else value


def main(argv):
    if len(argv) != 2:
        print(f"Usage: {argv[0]} <ocr.json>", file=sys.stderr)
        return 1

    path = argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error: could not read/parse {path}: {e}", file=sys.stderr)
        return 1

    observations = data.get("observations", [])
    image = data.get("image", {})

    vendor_id = detect_vendor.detect(observations)
    if vendor_id == "unknown":
        print(
            "Error: unknown vendor — no known layout matched this receipt's "
            "header text. Add a vendors/<id>.py parser (see PLAN.md) rather "
            "than guessing.",
            file=sys.stderr,
        )
        return 1

    parser = vendors.get(vendor_id)
    if parser is None:
        print(f"Error: vendor '{vendor_id}' detected but has no registered parser", file=sys.stderr)
        return 1

    try:
        rows, footer = parser.parse(observations, image)
    except ValueError as e:
        print(f"Error: {vendor_id} parser failed: {e}", file=sys.stderr)
        return 1

    expected = footer["subtotal"]

    # Full TSV always goes to stdout, PASS or PARTIAL.
    print("line\tname\tqty\tunit_price\ttotal\tneeds_review\tderived")
    for r in rows:
        print(
            f"{r['line']}\t{r['name']}\t{_fmt(r['qty'])}\t{_fmt(r['unit_price'])}\t"
            f"{_fmt(r['total'])}\t{1 if r['needs_review'] else 0}\t"
            f"{1 if r['derived'] else 0}"
        )

    needs_review = [r for r in rows if r["needs_review"]]
    derived = [r for r in rows if r["derived"]]
    # "read" = actually OCR-read (directly or via qty*price), excluding inferred.
    read_sum = round(
        sum(r["total"] for r in rows if r["total"] is not None and not r["derived"]), 2
    )
    grand_sum = round(sum(r["total"] for r in rows if r["total"] is not None), 2)
    residual = round(expected - read_sum, 2)

    reconciles = abs(round(grand_sum - expected, 2)) <= CHECKSUM_TOLERANCE

    if not needs_review and reconciles:
        if derived:
            print(
                f"# checksum PASS (with 1 derived row): read rows sum to "
                f"{read_sum}, + derived {round(grand_sum - read_sum, 2)} "
                f"= {grand_sum} == I alt {expected}.",
                file=sys.stderr,
            )
        else:
            print(f"# checksum OK: {grand_sum} == {expected}", file=sys.stderr)
        return 0

    # PARTIAL: unread cells remain, and/or the read cells don't reconcile.
    if needs_review:
        print(
            f"PARTIAL: {len(needs_review)} cell(s) unreadable by OCR and left "
            f"flagged (needs_review=1). Read rows sum to {read_sum}; the "
            f"flagged rows must account for the residual I alt - read = "
            f"{residual} (I alt = {expected}). Flagged rows:",
            file=sys.stderr,
        )
        for r in needs_review:
            print(f"  line {r['line']}: {r['name']!r}", file=sys.stderr)
    else:
        # No unread cells, but the read values don't add up — a genuine parse
        # error (e.g. a mis-assigned column), not a missing cell. Fail loudly.
        print(
            f"PARTIAL: all cells were read but they do not reconcile — sum "
            f"{grand_sum} vs I alt {expected} (residual {residual}). This is a "
            f"parsing error, not a missing cell; inspect the rows above.",
            file=sys.stderr,
        )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
