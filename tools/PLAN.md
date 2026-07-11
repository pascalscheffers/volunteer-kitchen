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

### Phase 0 — Scaffold + method + memory — DONE (2026-07-11)
- Created `tools/` tree: `README.md`, `taxonomy.md` (closed category/type lists),
  this `PLAN.md`. `.gitignore` now ignores `tools/ocr/.build/`.
- Added *How we build software here* to repo `CLAUDE.md` (project-agnostic
  generalization of Pascal's method).
- Saved working-style to machine memory so future sessions default to it.
- **Next:** Phase 1 — Swift Vision OCR CLI. Dispatch a fresh Sonnet worker to
  build `tools/ocr` and verify on `IMG_6575.jpeg`.
