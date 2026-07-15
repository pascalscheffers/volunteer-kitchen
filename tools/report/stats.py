#!/usr/bin/env python3
"""Aggregate all enriched receipt CSVs into a Markdown stats report.

Usage:
    python3 tools/report/stats.py

Reads every `2026/finance/csv/*.csv` (the per-receipt enriched output of the
parse + enrichment stages — see `tools/README.md`) and writes a single
regenerated report, `2026/finance/reports/summary.md`, answering questions
like "how many kg of X did we buy", "what did we spend on protein", "which
ingredient dominated".

Stdlib only. Deterministic: re-running with unchanged input CSVs produces a
byte-identical `summary.md` (all sums grouped and sorted by a stable key,
then by name).

Numeric convention: a blank cell (e.g. `total_kg` for a liquid) means "not
applicable", not zero — it is skipped when summing, and a group with no
applicable values at all renders as "—" rather than `0.000`.

Moms (Danish 25% VAT): every spend figure in this report is incl. moms so the
totals are comparable. Retail receipts (Netto, 365discount, Meny) already
list consumer prices incl. moms. Wholesale receipts (Dagrofa Food Service)
list line prices *ex* moms with moms added once at the register — those lines
are grossed up by 25% at load time. See `is_ex_moms`.
"""

import csv
import glob
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_GLOB = str(REPO_ROOT / "2026" / "finance" / "csv" / "*.csv")
REPORT_PATH = REPO_ROOT / "2026" / "finance" / "reports" / "summary.md"

MONEY_Q = Decimal("0.01")
QTY_Q = Decimal("0.001")

TOP_INGREDIENTS_LIMIT = 20

# Danish VAT. Wholesale receipts list line prices ex moms; grossed up so every
# spend figure in the report is on one incl-moms basis. See module docstring.
MOMS_MULTIPLIER = Decimal("1.25")
EX_MOMS_VENDORS = ("Dagrofa",)  # case-insensitive substring match on `vendor`


def is_ex_moms(vendor):
    """True if this vendor's line prices are ex moms and need grossing up."""
    v = (vendor or "").lower()
    return any(name.lower() in v for name in EX_MOMS_VENDORS)


def parse_decimal(cell):
    """Parse a CSV cell as a Decimal, or None if blank ('not applicable')."""
    cell = (cell or "").strip()
    if cell == "":
        return None
    return Decimal(cell)


def parse_int(cell):
    cell = (cell or "").strip()
    if cell == "":
        return None
    return int(Decimal(cell))


def load_rows():
    """Read every enriched CSV, return (rows, sorted list of csv paths)."""
    paths = sorted(glob.glob(CSV_GLOB))
    rows = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for raw in csv.DictReader(f):
                line_total = parse_decimal(raw["line_total"])
                if line_total is not None and is_ex_moms(raw["vendor"]):
                    line_total *= MOMS_MULTIPLIER
                rows.append(
                    {
                        "receipt": raw["receipt"],
                        "name_en": raw["name_en"],
                        "category": raw["category"],
                        "type": raw["type"],
                        "total_kg": parse_decimal(raw["total_kg"]),
                        "total_l": parse_decimal(raw["total_l"]),
                        "pieces": parse_int(raw["pieces"]),
                        "line_total": line_total,
                        "confidence": raw["confidence"],
                    }
                )
    return rows, paths


def money(d):
    if d is None:
        return "—"
    return f"{d.quantize(MONEY_Q, rounding=ROUND_HALF_UP):,}"


def qty(d):
    if d is None:
        return "—"
    return f"{d.quantize(QTY_Q, rounding=ROUND_HALF_UP)}"


def pieces_fmt(n):
    if n is None:
        return "—"
    return str(n)


def pct(part, whole):
    if not whole:
        return "—"
    return f"{(part / whole * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"


def md_table(headers, rows):
    """Render a list of markdown table lines from headers + row cell lists."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def section_spend_by_category(rows):
    sums = defaultdict(lambda: Decimal("0"))
    for r in rows:
        if r["line_total"] is not None:
            sums[r["category"]] += r["line_total"]
    grand_total = sum(sums.values(), Decimal("0"))

    ordered = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    table_rows = [
        [cat, money(spend), pct(spend, grand_total)] for cat, spend in ordered
    ]
    table_rows.append(["**Total**", f"**{money(grand_total)}**", "**100.00%**"])

    lines = ["## Spend by category", ""]
    lines += md_table(["Category", "Spend", "% of total"], table_rows)
    return lines, grand_total


def section_by_type(rows):
    spend = defaultdict(lambda: Decimal("0"))
    kg = defaultdict(lambda: Decimal("0"))
    kg_seen = defaultdict(bool)
    liters = defaultdict(lambda: Decimal("0"))
    l_seen = defaultdict(bool)
    pc = defaultdict(int)
    pc_seen = defaultdict(bool)

    for r in rows:
        t = r["type"]
        if r["line_total"] is not None:
            spend[t] += r["line_total"]
        if r["total_kg"] is not None:
            kg[t] += r["total_kg"]
            kg_seen[t] = True
        if r["total_l"] is not None:
            liters[t] += r["total_l"]
            l_seen[t] = True
        if r["pieces"] is not None:
            pc[t] += r["pieces"]
            pc_seen[t] = True

    types = set(spend) | set(kg) | set(liters) | set(pc)
    ordered = sorted(types, key=lambda t: (-spend.get(t, Decimal("0")), t))

    table_rows = []
    for t in ordered:
        table_rows.append(
            [
                t,
                money(spend.get(t, Decimal("0"))),
                qty(kg[t]) if kg_seen[t] else "—",
                qty(liters[t]) if l_seen[t] else "—",
                pieces_fmt(pc[t]) if pc_seen[t] else "—",
            ]
        )

    lines = ["## By nutrition type", ""]
    lines += md_table(
        ["Type", "Spend", "Total kg", "Total L", "Pieces"], table_rows
    )
    spend_total = sum(spend.values(), Decimal("0"))
    return lines, spend_total


def section_top_ingredients_by_spend(rows):
    sums = defaultdict(lambda: Decimal("0"))
    for r in rows:
        if r["line_total"] is not None:
            sums[r["name_en"]] += r["line_total"]

    ordered = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ordered[:TOP_INGREDIENTS_LIMIT]

    table_rows = [[name, money(spend)] for name, spend in top]

    lines = [
        f"## Top ingredients by spend (top {len(top)} of {len(ordered)})",
        "",
    ]
    lines += md_table(["Ingredient", "Spend"], table_rows)
    return lines


def section_ingredients_by_weight(rows):
    sums = defaultdict(lambda: Decimal("0"))
    for r in rows:
        if r["total_kg"] is not None:
            sums[r["name_en"]] += r["total_kg"]

    ordered = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    table_rows = [[name, qty(mass)] for name, mass in ordered]

    lines = ["## Ingredients by weight", ""]
    lines += md_table(["Ingredient", "Total kg"], table_rows)
    return lines


def section_reconciliation(rows, csv_paths):
    line_count = defaultdict(int)
    spend = defaultdict(lambda: Decimal("0"))
    low_conf = defaultdict(int)

    for r in rows:
        receipt = r["receipt"]
        line_count[receipt] += 1
        if r["line_total"] is not None:
            spend[receipt] += r["line_total"]
        if r["confidence"] == "low":
            low_conf[receipt] += 1

    receipts = sorted(line_count.keys())
    table_rows = [
        [
            receipt,
            str(line_count[receipt]),
            money(spend[receipt]),
            str(low_conf[receipt]),
        ]
        for receipt in receipts
    ]

    lines = ["## Reconciliation", ""]
    lines += md_table(
        ["Receipt", "Line items", "Spend", "Low-confidence rows"], table_rows
    )
    return lines


def build_report(rows, csv_paths):
    receipts = sorted({r["receipt"] for r in rows})

    header = [
        "# Kitchen finance summary",
        "",
        "Aggregate spend/weight/volume stats across all enriched receipt CSVs "
        "in `2026/finance/csv/`. **Generated by `tools/report/stats.py` — "
        "do not edit by hand**; re-run the script to regenerate after adding "
        "or changing a receipt CSV.",
        "",
        f"Covers **{len(receipts)}** receipt(s), **{len(rows)}** line item(s).",
        "",
        "All spend figures are **incl. moms** (25% Danish VAT). Wholesale "
        "receipts list line prices ex moms and are grossed up 25%; retail "
        "prices already include moms.",
        "",
    ]

    cat_lines, cat_total = section_spend_by_category(rows)
    type_lines, type_total = section_by_type(rows)
    top_lines = section_top_ingredients_by_spend(rows)
    weight_lines = section_ingredients_by_weight(rows)
    recon_lines = section_reconciliation(rows, csv_paths)

    body = []
    for section in (cat_lines, type_lines, top_lines, weight_lines, recon_lines):
        body += section
        body.append("")

    return "\n".join(header + body).rstrip("\n") + "\n"


def main():
    rows, csv_paths = load_rows()
    if not csv_paths:
        print("stats.py: no CSVs found matching " + CSV_GLOB, file=sys.stderr)
        sys.exit(1)

    report = build_report(rows, csv_paths)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    receipts = sorted({r["receipt"] for r in rows})
    print(
        f"stats.py: wrote {REPORT_PATH.relative_to(REPO_ROOT)} "
        f"({len(receipts)} receipt(s), {len(rows)} line item(s), "
        f"from {len(csv_paths)} CSV file(s))",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
