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
various shops. First sample (renamed by Phase 3):
`2026/finance/receipts/20260710-155835.jpeg` — Dagrofa Food Service, 41 line
items, footer totals `I alt 2412.30` / `Total 3015.38`.

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

### Run — 2nd receipt `20260711-111844` — DONE (2026-07-11)
- Second Dagrofa Food Service receipt (`I alt 2298.85`, 35 line items) run
  end-to-end through the existing pipeline: OCR → parse (PARTIAL, 2 flagged
  cells) → rename (EXIF stamp `20260711-111844`) → enrichment → report.
- **Enrichment resolved 5 cells against the photo:** line 5 `Tilbuds Rabat
  22,70%` is a **discount** (−32.00, 22.70% off the cheddar); line 19 `Blandet
  Saft C Rød 1L` = 3×26.95; lines 22/23 gels = 15.95/16.95. Line 5 modelled as
  `non-food/other` with a negative `line_total` so the report reconciles;
  flagged `confidence=low` pending a decision on how discounts should surface.
- **Parser silent-wrong read caught by the checksum, not the flag:** line 11
  `Koriander 15g` parsed as a self-consistent 4×7,95=31,80, but the receipt
  prints 4×**17,95**=71,80 (OCR dropped the leading 1 in both Pris and Total, so
  the row looked internally clean and was *not* flagged). Only the `I alt`
  reconciliation exposed it — the read-rows sum landed exactly 40.00 short, and
  71,80 is the unique fix that ties all 35 lines to 2298.85 to the øre.
  Corrected in the CSV; the parser has a real blind spot when a paired
  Pris/Total corruption stays arithmetically consistent. (No parser change this
  run — noted for a future hardening pass.)
- **Verified:** 35 rows; `line_total` sums to **2298.85 = I alt**; every
  `category`/`type` in the closed taxonomy; every qty×unit_price = line_total;
  report regenerated (2 receipts, 76 items, grand total 4711.15).
- **Next:** if a third receipt is a new shop, add its `vendors/<id>.py`. Consider
  hardening the parser against paired-cell OCR corruption (line-11 class), and
  decide the canonical treatment of discount lines in reports.

### Phase 5 — Reporting (`report/stats.py`) — DONE (2026-07-11)
- Built `tools/report/stats.py` (stdlib only — `csv`, `glob`, `decimal`,
  `collections`, `pathlib`): globs `2026/finance/csv/*.csv`, aggregates across
  all of them, and (re)writes a single `2026/finance/reports/summary.md`.
  Run: `python3 tools/report/stats.py`.
- **Sections**, each a Markdown table: (1) spend by category with % of total
  and a grand-total row; (2) by nutrition type — spend, total kg, total L,
  pieces, sorted by spend descending; (3) top ingredients by spend (top 20,
  or all if fewer); (4) ingredients by weight (kg), for the "how many kg of
  cheese" question; (5) reconciliation — one row per source receipt with line
  count, spend, and count of `confidence=low` rows.
- **Money/quantities use `Decimal`** (not float) throughout so sums reconcile
  exactly to the source CSV — no floating-point drift. Blank numeric cells
  (`total_kg`/`total_l`/`pieces`) are treated as "not applicable" and skipped
  in sums; a group with no applicable values renders `—`, never `0`.
- **Verified on the sample:** spend-by-category grand total and the
  by-nutrition-type spend column both sum to exactly **2412.30**, matching the
  receipt's `I alt`; reconciliation row shows 41 line items, 6
  `confidence=low` rows (matches the CSV). Regenerating a second time
  produces a byte-identical file (deterministic grouping + sort keys).
- **The core pipeline is now complete end-to-end**: photo → OCR → parse →
  enrich → report, all gated and reconciled at each stage. Phase 6
  (ingredient→dish mapping) is the only future work, out of current scope.
- **Next:** Phase 6 (later) — map enriched ingredients to `2026/menu` dishes
  and `recipes/`, when that's prioritized.

### Phase 4 — Enrichment (Sonnet, human session) — DONE (2026-07-11)
- Wrote `2026/finance/csv/20260710-155835.csv`: header + 41 data rows, columns
  `receipt,date,vendor,line,name_da,name_en,category,type,qty,pack_size,pack_unit,
  total_kg,total_l,pieces,unit_price,line_total,confidence`. Built by reading the
  raw parser TSV alongside the receipt photo (cropped with `magick -auto-orient`
  for a clean upright read of the full item table).
- **Filled the 2 `needs_review` cells** straight off the photo: line 4
  (`Heidelberg eddike u/farve 1L`) total `6.95`; line 24 (`Special blend no.2
  hele bønner 1kg`) total `168.00`. Both marked `confidence=low`. `line_total`
  column sums to exactly **2412.30**, matching `I alt`.
- **Name fixes from the photo** (parser's OCR names → corrected `name_da`):
  `Lager eddike farvet IL`→`...1L`; `Eblecidereddike`→`Æblecidereddike`;
  `Flydende margarine 70g 500ml`→`...70% 500ml`; `Olivenolie ekstra jomfru
  ll`→`...1L`; `skålfilter`→`Skålfilter` (kept — genuine product, see below);
  `Earl`→`Earl grey te 20 breve`; `Kamt Le Ye 20 br Breve 20 breve`→`Kamille te
  20 breve`; `Pålægschokolade malk`→`...mælk`; `Special blend no.2 hele
  banner`→`...hele bønner`.
- **Weight/piece normalization:** mass and volume packs converted to
  `total_kg`/`total_l` = qty × pack size (e.g. `Hvedemel 2kg` ×6 → 12 kg;
  `Basmati ris 5kg` → 5 kg). Gross/drained packs (`Mix oliven ... 1700g/1000g`,
  `Kikærter forkogte 2,5/1,5kg`) use the **drained** figure per the spec. Piece
  counts recovered from the photo where the parser's name dropped them:
  `Tortilla hvede 30cm 18stk` ×4 → 72 pieces; `Pålægschokolade` (mørk/mælk)
  216g **54stk** ×2 each → 108 pieces each, with `total_kg` *also* filled
  (0.432 each) since these items carry both a mass and a count; tea items
  `20 breve` → `pieces=20` each with `pack_unit=sachet`.
- **Low-confidence calls beyond the 2 filled cells** (flagged for review):
  `Mix oliven uden sten` → `type=vegetable` (vs. `fat-oil`, genuine coin-flip);
  `Græskarkerner varmebehandlet` (pumpkin seeds) → `type=fat-oil` (vs.
  `protein`/`other` — taxonomy has no nuts/seeds bucket); `Skålfilter 250/110
  hvid` → read as catering coffee-filter papers, `category=non-food,
  type=other` (product identity inferred, not printed on receipt in plainer
  terms); `Squeeze plast flaske 0,7L` → `category=non-food, type=other`, and
  `total_l` deliberately left **blank** (it's an empty serving bottle sized in
  litres, not a consumed liquid — filling `total_l` would pollute a "litres of
  liquid food" stat).
- **Verified:** 41 data rows; every `category`/`type` value checked against
  `taxonomy.md`'s closed lists (grep — no stray values); `line_total` sums to
  2412.30; spot-checks (`Basmati ris 5kg`→`total_kg=5`, `Hvedemel 2kg`×6→`12`,
  `Mix oliven`→`total_kg=1` drained) all pass.
- **Next:** Phase 5 — reporting (`report/stats.py`): aggregate `name_en` across
  receipts into kg/L/piece totals per type, reconcile report totals back to
  receipt `line_total` sums.

### Phase 3 — Rename receipts to sortable timestamps — DONE (2026-07-11)
- Added `tools/rename_receipts.py`: renames each `2026/finance/receipts/*` image
  to a sortable `YYYYMMDD-HHMMSS` stem and migrates its sibling `ocr/<stem>.json`
  / `csv/<stem>.csv` (via `git mv` for tracked files, `os.rename` for untracked)
  so the stem stays the shared key. `--dry-run` supported; idempotent (skips
  already-stamped names); collisions get a `-N` suffix.
- **Timestamp source, priority:** (1) receipt's printed date/time via the vendor
  parser; (2) EXIF `DateTimeOriginal` (read with `sips -g creation`, which is
  local time — `mdls` reports UTC, so avoided); (3) file mtime. The receipt
  **date** is authoritative when present.
- Added `header_datetime(observations)` to `vendors/dagrofa.py` (regex on `Dato:`
  / `Tid:`), returning `{date, time}` with either possibly `None`. Also feeds the
  CSV `date` column downstream.
- **Sample outcome:** `Dato: 10-07-2026` reads cleanly but `Tid:` value is
  dropped by OCR, so the date comes from the receipt and the time from EXIF
  (`15:58:35`, the checkout photo — within a minute of the printed 15:57). The
  sample is now `20260710-155835.{jpeg,json}`. Parse still gives 41 rows / 2
  flagged / residual 174.95 (unchanged — only the filename moved). The source
  image is committed for the first time here.
- **Next:** Phase 4 — enrichment (Sonnet, human session): raw rows TSV + image →
  enriched CSV (name_en, category, type from `taxonomy.md`, normalized weights,
  typo fixes, confidence). The 2 `needs_review` cells (`6.95` Heidelberg,
  `168.00` Special blend — both visible on the photo) get filled here.

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
