# Receipt pipeline — build plan + progress log

This file is the **source of truth for where we are**. Work happens in
interrupted sessions with context cleared between phases; a resuming session
reads this file first, then continues. Every phase ends green + committed + with
its progress entry appended below — no phase depends on live chat context.

Method: Opus orchestrates; fresh-context Sonnet workers execute one closed phase
each, verify against a gate, commit, and append a progress entry. See
[`../CLAUDE.md`](../CLAUDE.md) → *How we build software here*.

## Goal

Photos of kitchen receipts → per-receipt enriched CSV (item, category, nutrition
type, deduced weight/pieces, price) → stats reports. Receipts are Danish, from
various shops. First sample: `2026/finance/receipts/IMG_6575.jpeg` — Dagrofa
Food Service, ~40 line items, footer totals `I alt 2412.30` / `Total 3015.38`.

## Design

Layout, CSV schema, taxonomy, and multi-vendor rules are documented alongside:
- [`README.md`](README.md) — pipeline overview + how to run.
- [`taxonomy.md`](taxonomy.md) — closed `category` / `type` vocabularies.

Key invariants:
- **Checksum gate:** sum of parsed line `Total` must reconcile to the receipt's
  own `I alt` subtotal (±0.02) before a receipt is trusted. Catches OCR errors
  before any categorization.
- **Unknown vendor → stop.** The parser never guesses an unseen layout; adding a
  `vendors/<id>.py` is a deliberate, gated step needing a sample + passing
  checksum.
- **Timestamp is the key.** `<stamp>` (`YYYYMMDD-HHMMSS`) ties
  `receipts/`/`ocr/`/`csv/` together and sorts chronologically.

## Phases & gates

| # | Phase | Gate |
|---|---|---|
| 0 | Scaffold + method + memory (Opus, inline) | tree + docs + CLAUDE.md section + memory committed |
| 1 | Swift Vision OCR CLI (`ocr/`) | ~40 item lines + footer totals recognized on sample |
| 2 | Parser + vendor registry (`parse/`) | checksum: line totals == `I alt` 2412.30 (±0.02) |
| 3 | Image rename to timestamp | sample → `20260710-<hhmmss>.jpeg`, keys migrated |
| 4 | Enrichment (Sonnet, human session) | sample rows spot-checked vs image |
| 5 | Reporting (`report/stats.py`) | report totals reconcile to receipt |
| 6 | LATER: ingredient→dish mapping (`2026/menu`+`recipes`) | out of current scope |

## Progress log

Newest first. One tight entry per completed phase: what got done, key decisions,
current state, what's next.

### Phase 2 — Parser + vendor registry (`parse/`) — DONE (2026-07-11)
- Built `tools/parse/parse_receipt.py` (CLI driver, stdlib only), `detect_vendor.py`
  (data-driven marker table, "unknown vendor → stop"), `vendors/__init__.py`
  (registry), `vendors/_util.py` (shared `parse_danish_number` — comma decimal,
  dot thousands separator), and `vendors/dagrofa.py` (the Dagrofa Food Service
  layout). Run: `python3 tools/parse/parse_receipt.py 2026/finance/ocr/IMG_6575.json`.
- **Guiding principle: read what OCR can, flag what it can't, never fabricate a
  value.** A receipt with a genuinely unreadable cell is a valid *partial*
  result for a later human/enrichment pass to complete — not a reason to invent
  a number. The checksum gate now proves "no fabricated reads," not "sum forced
  to match."
- **Output:** TSV `line\tname\tqty\tunit_price\ttotal\tneeds_review\tderived`,
  always printed to stdout (even PARTIAL). `total` is empty for any cell OCR
  couldn't read; that row carries `needs_review=1`. `derived=1` marks the one
  allowed inference (see gate).
- **Gate:**
  - **PASS** (exit 0): every numeric cell was read and the totals reconcile to
    `I alt` (±0.02), OR exactly one cell was `derived` and the rest reconcile.
  - **PARTIAL** (exit 2): one or more `needs_review` cells remain, or the read
    cells don't reconcile. Full TSV still goes to stdout; stderr names the
    flagged rows and the residual `I alt − sum(read)` they must account for.
  - exit 1 for usage / unreadable input / unknown vendor.
- **Result on sample: PARTIAL, 41 rows, 2 cells genuinely unreadable by Vision
  and flagged** — line 4 (Heidelberg, Total `6,95`) and line 24 (Special blend,
  Total `168,00`). The 39 read rows sum to `2237.35`; residual `174.95` =
  `6.95 + 168.00` **exactly**, which independently confirms every read row is
  correct. (41 rows, not the ~40 estimated going in.) This is the honest,
  expected outcome — those two cells are Vision misses, not parser errors (see
  quirks).
- **Row reconstruction:** cluster Varenavn-column observations by y-proximity
  into rows (joining same-row name fragments left to right), bounded below by
  the Antal column's lowest valid value (footer/legal text shares the name
  column's x-band but never has a valid Antal, so this cleanly excludes it
  without needing footer-text detection). Every cluster is a real line item —
  a row whose numeric cells are all unreadable is emitted and flagged, never
  folded into its neighbour.
- **Column reconstruction:** the receipt photo is slightly rotated and curled,
  so a numeric cell sits at a consistent skew offset from its row's name
  centroid (~0.0045 *above*, for Total) — comparable to the row-to-row gap, so
  naive nearest-y matching pulls every value one row too far and resolves
  near-ties wrongly, and one missing cell cascades down every row below.
  Solved with `_assign_column_dp`: a Needleman-Wunsch-style monotonic sequence
  alignment (rows and observations are both top-to-bottom and never reorder)
  where either side can be left unmatched at a fixed cost — a genuine gap stays
  a gap instead of shifting everything. The per-column skew offset is found by a
  small **grid search**: run the DP over a range of offsets and keep the
  lowest-cost alignment (the correct offset makes real matches line up tightly
  while still leaving gaps as skips). A residual near-exact geometric tie
  between two adjacent rows is broken by `_fix_adjacent_total_swap` using the
  numbers' own arithmetic (qty × price) — legitimate, since it only moves a
  *read* value to the row it belongs to.
- **OCR-corruption filter:** every genuine Antal/Pris/Total value on this
  receipt prints with exactly two decimal digits; `_looks_like_clean_amount`
  treats a garbled read like `"0,9"` or `"Iti8, 00"` as *unread* rather than
  letting a wrong number silently enter the checksum.
- **The one allowed inference:** `_derive_single_gap` fills a value ONLY when
  exactly one row is unread and the read rows + that one value reconcile to
  `I alt`; it marks the row `derived=1` so it can never masquerade as a read
  value. Two or more unread cells (as on this sample) are all left flagged and
  the gate reports PARTIAL — no guessing. (No receipt-specific data lives in
  the parser; an earlier draft that baked in a hand-verified cell value was
  removed as a matter of principle.)
- **Quirks:**
  - The two unreadable cells were confirmed genuine by cropping the source
    photo directly (`magick` + read): the print is crisp, Vision drops or
    garbles them — both are cases of two adjacent rows printing the identical
    amount (`6,95` twice, `168,00` twice across Pris/Total), which appears to
    confuse Vision's line detection. Not recoverable via config.
  - Dual-pass OCR (see Phase 1 note) recovered every *other* previously-missing
    numeric cell and restored clean item names, so the flag count dropped from
    ~4 down to these 2 truly-unreadable ones.
  - `detect_vendor.py`'s CVR marker is `27626904`, not `26626904` as
    originally assumed — corrected to the value actually printed on the
    receipt.
  - Saved the merged-OCR JSON to `2026/finance/ocr/IMG_6575.json` as the audit
    artifact backing this phase's result (each observation tagged with its
    source pass).
- **Next:** Phase 3 — image rename to timestamp (`20260710-<hhmmss>.jpeg`),
  migrating `receipts/`/`ocr/` keys together. Phase 4 (enrichment) should also
  complete the 2 `needs_review` cells from the receipt photo.

### Phase 1 — Swift Vision OCR CLI — DONE (2026-07-11)
- Built `tools/ocr` as a SwiftPM package (`.macOS(.v13)`, no third-party deps):
  `Package.swift` + `Sources/receipt-ocr/main.swift`, executable product
  `receipt-ocr`. Uses only `Foundation`, `ImageIO`, `Vision`.
- **Orientation:** reads `kCGImagePropertyOrientation` via `CGImageSource` and
  passes it straight to `VNImageRequestHandler(cgImage:orientation:)` — the EXIF
  orientation values (1–8) line up 1:1 with `CGImagePropertyOrientation`'s raw
  values, so no manual mapping needed. `image.width`/`image.height` in the
  output are the *upright* pixel dimensions (swapped for the 90°/270°
  orientations) so they match the frame `bbox` is normalized against. Sample
  is shot rotated 90°; without correct orientation handling Vision returns
  near-garbage — verified fix by comparing output before/after.
- **JSON shape:** `{ "image": {"width", "height"}, "observations": [...] }`,
  each observation `{ "text", "confidence", "bbox": {"x","y","w","h"} }`.
  `bbox` is Vision's raw normalized `boundingBox` — 0–1, origin bottom-left —
  passed through unflipped. Documented at the top of `main.swift` since
  Phase 2's parser depends on this convention.
- **Verified on sample:** `swift build --package-path tools/ocr` is clean;
  running on `IMG_6575.jpeg` returns 171 observations (well above the ~40
  item-line floor — includes header/footer/legal text too), all three footer
  totals (`2.412,30` / `603,08` / `3.015,38`) and sample item lines (`Majsmel
  2,5kg`, `Hvedemel`, etc.) recognized correctly. Output is valid JSON
  (parsed with `json.loads`). **Amended in Phase 2:** OCR is now **dual-pass**
  — Vision runs at both `.accurate` and `.fast`, and the results are merged
  (`.accurate` for names, since its language model reads them more cleanly;
  `.fast`'s clean numbers where `.accurate` garbled a numeric cell; `.fast`
  gap-fills where `.accurate` saw nothing). `.accurate` alone silently dropped
  numeric cells on the dense item table; `.fast` alone garbled the names.
  Merging gets both. Each observation now also carries a `source` field
  (`"accurate"`/`"fast"`) for audit. See the Phase 2 entry above for rationale.
- **Next:** Phase 2 — parser + vendor registry (`parse/`). Consumes this JSON,
  denormalizes `bbox` against `image.width/height` (remember: bottom-left
  origin), groups observations into line items, and must reconcile parsed
  line totals to the `I alt` subtotal (2412.30, ±0.02) before a receipt is
  trusted.

### Phase 0 — Scaffold + method + memory — DONE (2026-07-11)
- Created `tools/` tree: `README.md`, `taxonomy.md` (closed category/type lists),
  this `PLAN.md`. `.gitignore` now ignores `tools/ocr/.build/`.
- Added *How we build software here* to repo `CLAUDE.md` (project-agnostic
  generalization of Pascal's method).
- Saved working-style to machine memory so future sessions default to it.
- **Next:** Phase 1 — Swift Vision OCR CLI. Dispatch a fresh Sonnet worker to
  build `tools/ocr` and verify on `IMG_6575.jpeg`.
