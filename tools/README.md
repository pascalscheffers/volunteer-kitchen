# tools/ — receipt pipeline

Turns scanned kitchen receipts (`2026/finance/receipts/`) into structured,
categorized CSVs we can run stats over: *how many kg of cheese did we eat, what
did we spend on protein, which ingredient dominated.*

Receipts are photos, often from **different shops** and in **Danish**. The
pipeline OCRs on-device, parses per-vendor, enriches with categories, and
reports.

## Pipeline

```
receipts/<stamp>.jpeg          source photo (renamed to a sortable timestamp)
  │  ocr/receipt-ocr           Swift + Apple Vision  → text + bbox + confidence
  ▼
ocr/<stamp>.json               raw OCR (audit artifact)
  │  parse/parse_receipt.py    detect vendor, rebuild columns, parse weights
  ▼                            GATE: line totals must reconcile to receipt total
raw rows TSV
  │  Sonnet enrichment pass    translate, categorize, normalize weights, fix typos
  ▼
csv/<stamp>.csv                enriched canonical CSV (one per receipt)
  │  report/stats.py           aggregate all CSVs
  ▼
reports/                       kg by type, top ingredients, spend by category
```

## Parts

- **`ocr/`** — `receipt-ocr <image>` Swift CLI wrapping Apple
  `VNRecognizeTextRequest`. On-device, Danish, handles rotated scans. Emits JSON
  observations with bounding boxes (needed to rebuild the receipt's columns).
- **`parse/`** — `parse_receipt.py` drives it: `detect_vendor.py` routes to a
  `vendors/<id>.py` parser (per-shop column layout, date format, footer wording).
  **A new shop = a new vendor module, added deliberately** (see PLAN.md) — the
  parser refuses to guess an unknown layout.
- **`rename_receipts.py`** — renames source photos to `YYYYMMDD-HHMMSS` so they
  sort, using the receipt's printed date (or EXIF, or mtime). That timestamp is
  the shared key across `receipts/` / `ocr/` / `csv/`.
- **`taxonomy.md`** — the closed `category` / `type` vocabularies. Read before
  enriching.
- **`report/stats.py`** — aggregates `2026/finance/csv/*.csv` into
  `2026/finance/reports/`.

## How this work is run

See **[`PLAN.md`](PLAN.md)** — it holds the build plan *and* a running progress
log, so work survives interrupted sessions. The method (Opus orchestrates,
fresh-context Sonnet workers do closed jobs, memory lives in the repo) is in the
repo [`CLAUDE.md`](../CLAUDE.md).

## Licensing

Code is **MIT** (repo convention). Swift + Python stdlib only — no third-party
runtime dependencies. Building `ocr/` needs the Xcode command-line tools.
