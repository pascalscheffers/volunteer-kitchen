#!/usr/bin/env python3
"""Interactive amount-filler for enriched receipt CSVs.

Walks every line that still needs a human amount — flagged `confidence = low`
or missing all of `total_kg` / `total_l` / `pieces` — and lets you type the
pack size fast. The tool converts to total kg / L / pieces (× qty), writes it
back into the same CSV, and marks the line reviewed so it never reappears.

Usage:
    python3 tools/report/fill_amounts.py            # walk all receipts
    python3 tools/report/fill_amounts.py <receipt>  # one receipt (stamp)

Review state lives in `2026/finance/csv/.reviewed.json` (keyed
`receipt|line`), so a genuinely weightless line (a box, cling film, a rebate)
stays put once you mark it, instead of nagging every run. Stdlib only.

Input grammar (per prompt):
    2.5kg  500g  1l  500ml  6pcs      pack size per unit → ×qty auto
    6                                 bare number = pieces per unit
    =12kg  =0.5l                      '=' means that IS the line total, no ×qty
    -   n   none                      no weight applies (box, wrap, rebate)
    <enter>                           keep current values, mark reviewed
    s                                 skip (revisit later; not marked)
    o                                 open the receipt photo
    b                                 redo the previous line
    q                                 save + quit
    ?                                 this help
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parents[2] / "2026" / "finance" / "csv"
IMG_DIR = Path(__file__).resolve().parents[2] / "2026" / "finance" / "receipts"
STATE = CSV_DIR / ".reviewed.json"

FIELDS = [
    "receipt", "date", "vendor", "line", "name_da", "name_en", "category",
    "type", "qty", "pack_size", "pack_unit", "total_kg", "total_l", "pieces",
    "unit_price", "line_total", "confidence",
]

# unit -> (target column, divisor to base kg/l, is_integer)
UNITS = {
    "kg": ("total_kg", Decimal(1), False),
    "g": ("total_kg", Decimal(1000), False),
    "l": ("total_l", Decimal(1), False),
    "ml": ("total_l", Decimal(1000), False),
    "pcs": ("pieces", Decimal(1), True),
    "pc": ("pieces", Decimal(1), True),
    "stk": ("pieces", Decimal(1), True),
    "x": ("pieces", Decimal(1), True),
    "sachet": ("pieces", Decimal(1), True),
}
CANON_UNIT = {"pc": "pcs", "stk": "pcs", "x": "pcs", "sachet": "pcs"}

INPUT_RE = re.compile(r"^(=)?\s*([\d.,]+)\s*([a-z]+)?$", re.I)


def load_state():
    if STATE.exists():
        return set(json.loads(STATE.read_text()))
    return set()


def save_state(done):
    STATE.write_text(json.dumps(sorted(done), indent=0))


def needs_review(r):
    low = r["confidence"].strip().lower() == "low"
    no_qty = not (r["total_kg"].strip() or r["total_l"].strip()
                  or r["pieces"].strip())
    return low or no_qty


def dec(s):
    s = s.strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fmt(d):
    """Trim trailing zeros; keep it looking like the existing hand-typed cells."""
    d = d.normalize()
    s = format(d, "f")
    return s


def apply_amount(r, raw):
    """Mutate row from an amount string. Return (ok, message)."""
    m = INPUT_RE.match(raw)
    if not m:
        return False, "unparsable — try e.g. 2.5kg, 500g, 1l, 6pcs, =12kg"
    is_total, num, unit = m.group(1), m.group(2), (m.group(3) or "").lower()
    value = dec(num)
    if value is None:
        return False, "bad number"
    unit = unit or "pcs"  # bare number = pieces
    if unit not in UNITS:
        return False, f"unknown unit '{unit}'"
    col, div, is_int = UNITS[unit]

    qty = dec(r["qty"]) or Decimal(1)
    per_unit = value / div
    total = per_unit if is_total else per_unit * qty

    # clear the other total columns; only one applies
    r["total_kg"] = r["total_l"] = r["pieces"] = ""
    if is_int:
        r[col] = str(int(total))
    else:
        r[col] = fmt(total)

    # record pack_size/unit when it's a genuine per-unit pack size
    if not is_total:
        r["pack_size"] = fmt(value)
        r["pack_unit"] = CANON_UNIT.get(unit, unit)
    # a human just supplied the amount → trust the line
    r["confidence"] = "high"
    return True, f'{col} = {r[col]}'


def open_image(receipt):
    hits = list(IMG_DIR.glob(f"{receipt}.*"))
    if not hits:
        print(f"  (no image for {receipt})")
        return
    subprocess.run(["open", str(hits[0])], check=False)
    print(f"  opened {hits[0].name}")


def show(r):
    print()
    print("=" * 72)
    flags = []
    if r["confidence"].strip().lower() == "low":
        flags.append("LOW-CONF")
    if not (r["total_kg"].strip() or r["total_l"].strip() or r["pieces"].strip()):
        flags.append("NO-QTY")
    print(f'  {r["receipt"]}  line {r["line"]}  [{", ".join(flags)}]')
    print(f'  {r["name_da"]}   ({r["name_en"]})')
    print(f'  {r["category"]}/{r["type"]}   qty={r["qty"] or "-"}   '
          f'pack={r["pack_size"]}{r["pack_unit"]}   '
          f'unit={r["unit_price"]}   line_total={r["line_total"]}')
    cur = f'kg[{r["total_kg"]}] l[{r["total_l"]}] pcs[{r["pieces"]}]'
    print(f'  current: {cur}')


def process_file(path, done):
    rows = list(csv.DictReader(open(path)))
    targets = [i for i, r in enumerate(rows)
               if needs_review(r) and f'{r["receipt"]}|{r["line"]}' not in done]
    if not targets:
        return False
    print(f'\n### {path.name}  —  {len(targets)} line(s) to review')
    dirty = False
    i = 0
    while i < len(targets):
        idx = targets[i]
        r = rows[idx]
        key = f'{r["receipt"]}|{r["line"]}'
        show(r)
        try:
            raw = input("  amount> ").strip()
        except EOFError:
            raw = "q"
        low = raw.lower()

        if low == "q":
            if dirty:
                write_file(path, rows)
            save_state(done)
            print("saved. bye.")
            sys.exit(0)
        if low == "?":
            print(__doc__)
            continue
        if low == "s":
            i += 1
            continue
        if low == "o":
            open_image(r["receipt"])
            continue
        if low == "b":
            i = max(0, i - 1)
            # un-mark the one we're going back to so it re-shows cleanly
            prev = rows[targets[i]]
            done.discard(f'{prev["receipt"]}|{prev["line"]}')
            continue
        if low in ("-", "n", "none"):
            done.add(key)
            dirty = True  # confidence may not change but state does
            print("  marked: no weight applies.")
            i += 1
            continue
        if raw == "":
            r["confidence"] = "high"
            done.add(key)
            dirty = True
            print("  kept current, marked reviewed.")
            i += 1
            continue

        ok, msg = apply_amount(r, raw)
        print(f'  {msg}')
        if ok:
            done.add(key)
            dirty = True
            i += 1

    if dirty:
        write_file(path, rows)
    return dirty


def write_file(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f'  wrote {path.name}')


def main():
    if not CSV_DIR.exists():
        sys.exit(f"no csv dir: {CSV_DIR}")
    done = load_state()

    if len(sys.argv) > 1:
        files = [CSV_DIR / f"{sys.argv[1]}.csv"]
        if not files[0].exists():
            sys.exit(f"no such receipt csv: {files[0].name}")
    else:
        files = sorted(CSV_DIR.glob("*.csv"))

    remaining = 0
    for path in files:
        rows = list(csv.DictReader(open(path)))
        remaining += sum(
            1 for r in rows
            if needs_review(r) and f'{r["receipt"]}|{r["line"]}' not in done)
    print(f"{remaining} line(s) need an amount. "
          "Type ? for help, q to save+quit.")

    for path in files:
        process_file(path, done)

    save_state(done)
    print("\nAll flagged lines handled. Re-run tools/report/stats.py to refresh.")


if __name__ == "__main__":
    main()
