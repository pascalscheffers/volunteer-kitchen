# Dagrofa Food Service receipt layout.
#
# Four columns left-to-right: Varenavn (item name) / Antal (qty) / Pris (unit
# price) / Total. bbox is Vision's normalized boundingBox: 0..1, origin
# bottom-left (see tools/ocr's main.swift). We work entirely in that
# normalized space — no need to denormalize to pixels since we only ever
# compare positions to each other, and the receipt's aspect ratio makes
# normalized x/y directly comparable.
#
# The receipt photo has a slight rotation *and* a slight curl, so a physical
# row's numeric cells don't sit at a constant y-offset from its name text —
# the offset itself drifts smoothly down the page (empirically: a few
# thousandths of y near the top, shrinking and even changing sign near the
# bottom). That rules out a single global offset correction. Worse, the
# offset's magnitude is comparable to the row-to-row gap for the Total
# column specifically, so naive nearest-y matching is genuinely ambiguous
# row to row — and once a single cell goes missing (see below), naive
# greedy nearest-neighbour cascades: every row below quietly claims the
# row-below's value instead of its own.
#
# Fix: `_assign_column_dp` treats column assignment as a monotonic sequence
# alignment (rows and column observations are both already sorted top to
# bottom, and physically can never reorder relative to each other), not a
# per-row nearest-neighbour search. A row or an observation can be left
# unmatched at a fixed cost instead of being forced into the nearest
# available slot, which is what breaks the cascade: a genuine gap stays a
# gap instead of shunting every subsequent row's value up by one.
#
# Recognition quirk (see tools/ocr's dual-pass comment): even merging the
# .accurate and .fast Vision passes, a couple of numeric cells on the sample
# receipt come back with no observation at all, or garbled — confirmed by
# cropping down to a single cell; the text is crisp in the source photo,
# Vision just misreads or drops it (the two worst cases are adjacent rows
# printing the identical amount, which seems to confuse its line detection).
# Every genuine amount on this receipt (Antal/Pris/Total, and the footer)
# prints with exactly two decimal digits, so `_looks_like_clean_amount`
# uses that as a vendor-specific validity filter — a garbled read like
# "0,9" or "Iti8, 00" fails it and is treated as *unread* rather than a
# wrong number silently entering the checksum.
#
# Honest handling of a cell OCR can't read: we never fabricate a value.
#   - `_fix_adjacent_total_swap` resolves the one case where two adjacent
#     rows sit at a near-exact geometric tie (their distances to the same
#     Total observation differ by ten-thousandths) using the numbers' own
#     arithmetic (qty * price == total) — legitimate, since it only moves a
#     value that was genuinely read to the row it actually belongs to.
#   - Any Total still unread after DP alignment + arithmetic fallback stays
#     `total = None` and the row is flagged `needs_review = True`. That's a
#     valid partial result for a later human enrichment pass to complete —
#     the parser reports it, it does not guess.
#   - `_derive_single_gap` will infer a value for exactly ONE unread row by
#     subtracting the read rows from the receipt's own `I alt`, but only
#     when it is the sole remaining unknown, and it marks that row
#     `derived = True` (and leaves `needs_review = True`) so an inferred
#     value can never masquerade as a read one. Two or more unread cells
#     are all left flagged and the driver reports PARTIAL.

import re
import sys

from ._util import parse_danish_number

_CLEAN_AMOUNT_RE = re.compile(r"^\d{1,3}(\.\d{3})*,\d{2}$")


def _looks_like_clean_amount(text):
    """Dagrofa prints every genuine Antal/Pris/Total/footer value with
    exactly two decimal digits. A garbled OCR read of a numeric cell
    ("0,9", "D,95") usually still parses as *some* Danish number, just not
    the right one — this catches those so they're treated as a missing
    cell (recoverable via arithmetic/reconciliation) rather than a wrong
    value that would silently corrupt the checksum."""
    if text is None:
        return False
    return bool(_CLEAN_AMOUNT_RE.match(text.strip()))


_DATE_RE = re.compile(r"Dato[.:]*\s*(\d{2})-(\d{2})-(\d{4})")
_TIME_RE = re.compile(r"Tid[.:]*\s*(\d{2}):(\d{2})(?::(\d{2}))?")


def header_datetime(observations):
    """Extract the receipt's printed transaction date/time from the header.

    Returns a dict {"date": "YYYY-MM-DD" or None, "time": "HH:MM:SS" or None}.
    Either field may be None when OCR didn't capture it cleanly (on the sample
    the `Dato:` line reads perfectly but the `Tid:` value is dropped) — callers
    fall back to EXIF/mtime for whatever's missing. `date` is authoritative when
    present; it's the value used for the CSV `date` column downstream.
    """
    date = time = None
    for o in observations:
        t = o.get("text", "")
        if date is None:
            m = _DATE_RE.search(t)
            if m:
                dd, mm, yyyy = m.groups()
                date = f"{yyyy}-{mm}-{dd}"
        if time is None:
            m = _TIME_RE.search(t)
            if m:
                hh, mi, ss = m.groups()
                time = f"{hh}:{mi}:{ss or '00'}"
    return {"date": date, "time": time}


def _center(bbox):
    return bbox["x"] + bbox["w"] / 2, bbox["y"] + bbox["h"] / 2


def _find_header(observations):
    """Locate the Varenavn/Antal/Pris/Total header row and return their x
    centers. Tolerant of OCR noise in the label text itself (e.g. "Pri3")."""
    labeled = {"varenavn": [], "antal": [], "pris": [], "total": []}
    for o in observations:
        t = o["text"].strip().lower()
        cx, cy = _center(o["bbox"])
        if t.startswith("varenavn"):
            labeled["varenavn"].append((cx, cy))
        elif t.startswith("antal"):
            labeled["antal"].append((cx, cy))
        elif t.startswith("pri"):
            labeled["pris"].append((cx, cy))
        elif t.startswith("total"):
            labeled["total"].append((cx, cy))

    if not labeled["varenavn"]:
        raise ValueError("dagrofa: could not find 'Varenavn' column header")
    # Varenavn only ever appears once, as the header — anchor on its y.
    header_y = labeled["varenavn"][0][1]

    def closest(cands):
        if not cands:
            return None
        return min(cands, key=lambda p: abs(p[1] - header_y))

    antal = closest(labeled["antal"])
    pris = closest(labeled["pris"])
    total = closest(labeled["total"])
    if antal is None or pris is None or total is None:
        raise ValueError("dagrofa: could not find full Antal/Pris/Total header row")

    return {
        "y": header_y,
        "varenavn_x": labeled["varenavn"][0][0],
        "antal_x": antal[0],
        "pris_x": pris[0],
        "total_x": total[0],
    }


def _column_bands(header):
    """Column x-boundaries as midpoints between header label centers."""
    v, a, p, t = (
        header["varenavn_x"],
        header["antal_x"],
        header["pris_x"],
        header["total_x"],
    )
    return {
        "name_max": (v + a) / 2,
        "antal_max": (a + p) / 2,
        "pris_max": (p + t) / 2,
    }


def _find_footer(observations, header, item_bottom_y):
    """The three footer totals (I alt / Moms / Total inkl. moms) are the
    first three Danish numbers found in the Total column below the item
    table, in that fixed order. Positional, not label-based, because the
    labels themselves come through with OCR noise ("MOMB l a&t")."""
    bands = _column_bands(header)
    candidates = []
    for o in observations:
        cx, cy = _center(o["bbox"])
        if cy >= item_bottom_y:
            continue
        if cx <= bands["pris_max"]:
            continue
        value = parse_danish_number(o["text"])
        if value is not None:
            candidates.append((cy, value))
    candidates.sort(key=lambda c: -c[0])
    values = [v for _, v in candidates[:3]]
    if len(values) < 3:
        raise ValueError(
            f"dagrofa: expected 3 footer totals (I alt / Moms / Total inkl. moms), found {len(values)}"
        )
    subtotal, vat, total_incl_vat = values
    return {"subtotal": subtotal, "vat": vat, "total_incl_vat": total_incl_vat}


def _cluster_rows(name_obs, row_height):
    """Group name-column observations into rows by y proximity, joining
    same-row fragments left-to-right. Handles the case where a long item
    name arrives as several observations on one physical line."""
    name_obs = sorted(name_obs, key=lambda o: -_center(o["bbox"])[1])
    rows = []
    tolerance = row_height * 0.45
    for o in name_obs:
        cx, cy = _center(o["bbox"])
        if rows and abs(cy - rows[-1]["y"]) <= tolerance:
            rows[-1]["fragments"].append((cx, o["text"]))
            # Recompute the row's representative y as fragments accrue, so
            # a long wrapped cluster doesn't drift off its true center.
            ys = rows[-1]["ys"]
            ys.append(cy)
            rows[-1]["y"] = sum(ys) / len(ys)
        else:
            rows.append({"y": cy, "ys": [cy], "fragments": [(cx, o["text"])]})
    for row in rows:
        row["fragments"].sort(key=lambda f: f[0])
        row["name"] = " ".join(text for _, text in row["fragments"])
    return rows


def _dp_align(rows, pool, row_height, y_offset, skip_factor=0.5, max_dist_factor=1.3):
    """Monotonic sequence alignment (Needleman-Wunsch style) of rows against
    a column's observation `pool` (each `(y, text)`, sorted top to bottom),
    with each row shifted by `y_offset` before matching.

    Rows (top to bottom) and the observations (top to bottom) can never
    reorder relative to each other — row 5's Total is never above row 4's.
    That invariant is what a greedy nearest-neighbour match throws away: it
    decides each row's match independently, so one missing cell (see module
    docstring) makes it grab the next row's value instead, and that error
    cascades down every row after it. This DP finds the lowest-cost matching
    *consistent with that ordering*, where leaving a row or an observation
    unmatched costs a fixed penalty — so a genuine gap can stay a gap
    instead of dragging every later row's assignment out of alignment.

    `skip_factor` sets that penalty (as a fraction of row_height) for
    leaving either side unmatched; `max_dist_factor` caps how far apart a
    (shifted) row and an observation can be and still match at all. Returns
    `(assigned, cost)` where `assigned` is a list of text-or-None parallel
    to `rows` and `cost` is the total alignment cost (used to pick the best
    `y_offset` — see `_assign_column_dp`)."""
    n, m = len(rows), len(pool)
    row_skip = row_height * skip_factor
    obs_skip = row_height * skip_factor
    max_dist = row_height * max_dist_factor

    # dp[i][j]: min cost aligning the first i rows against the first j pool
    # entries. choice[i][j]: how we got there ('M'atch / 'R'ow skipped /
    # 'O'bservation skipped), for backtracking the actual assignment.
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    choice = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + row_skip
        choice[i][0] = "R"
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + obs_skip
        choice[0][j] = "O"
    for i in range(1, n + 1):
        ry = rows[i - 1]["y"] + y_offset
        for j in range(1, m + 1):
            best_cost, best_choice = None, None
            d = abs(ry - pool[j - 1][0])
            if d <= max_dist:
                best_cost, best_choice = dp[i - 1][j - 1] + d, "M"
            skip_row_cost = dp[i - 1][j] + row_skip
            if best_cost is None or skip_row_cost < best_cost:
                best_cost, best_choice = skip_row_cost, "R"
            skip_obs_cost = dp[i][j - 1] + obs_skip
            if best_cost is None or skip_obs_cost < best_cost:
                best_cost, best_choice = skip_obs_cost, "O"
            dp[i][j] = best_cost
            choice[i][j] = best_choice

    assigned = [None] * n
    i, j = n, m
    while i > 0 or j > 0:
        c = choice[i][j]
        if c == "M":
            assigned[i - 1] = pool[j - 1][1]
            i -= 1
            j -= 1
        elif c == "R":
            i -= 1
        else:
            j -= 1
    return assigned, dp[n][m]


def _assign_column_dp(rows, col_obs, row_height):
    """Assign a numeric column to rows, correcting for the receipt photo's
    skew before aligning.

    The photo is slightly rotated and curled, so a numeric cell doesn't sit
    at a row's name-centroid y — it's offset by a consistent few thousandths
    (empirically the Total column reads ~0.0045 *above* its row's name). That
    offset is comparable to the row-to-row gap, so without correcting for it
    the alignment pulls every value one row too far and near-ties resolve the
    wrong way. A single global offset is right (the skew is consistent down
    the page for a given column) but its exact size differs per column and
    isn't known a priori.

    So we grid-search the offset: run the monotonic DP for a range of
    candidate offsets and keep the alignment with the lowest total cost. The
    correct offset makes the genuine matches line up tightly (low distance
    cost) while still leaving real gaps as skips, so it wins cleanly — and
    because the DP enforces ordering, a wrong offset can't manufacture a
    lower-cost cascade. Returns a list of text-or-None parallel to `rows`."""
    pool = sorted(
        (
            (_center(o["bbox"])[1], o["text"])
            for o in col_obs
            if _looks_like_clean_amount(o["text"])
        ),
        key=lambda p: -p[0],
    )
    if not pool:
        return [None] * len(rows)

    # Search offsets from clearly-below to clearly-above the name centroid,
    # in fine steps (the observed skew is ~+0.004..0.005 for Total, smaller
    # for the columns nearer the name).
    best = None
    steps = 41  # -0.004 .. +0.008 inclusive, step 0.0003
    lo, hi = -0.004, 0.008
    for k in range(steps):
        off = lo + (hi - lo) * k / (steps - 1)
        assigned, cost = _dp_align(rows, pool, row_height, off)
        if best is None or cost < best[0]:
            best = (cost, assigned)
    return best[1]


def _fix_adjacent_total_swap(rows_qty, rows_price, total_assigned, tolerance=0.02):
    """Break the one tie the DP alignment can't: on this receipt, a couple
    of adjacent rows sit close enough to equidistant from a Total value that
    ten-thousandths of y decide which one the DP picks, and it can pick the
    row above instead of the true owner below.

    Resolve it with arithmetic instead of geometry: if row i has a Total
    assigned but no reliable qty*price of its own to confirm it (so the
    assignment is unverified), and row i+1 has *no* Total assigned but its
    own qty*price matches row i's assigned value exactly, the value belongs
    to row i+1 — move it and leave row i's slot open for arithmetic
    fallback or, failing that, the needs_review flag. Mutates
    `total_assigned` in place."""
    for i in range(len(total_assigned) - 1):
        total_text = total_assigned[i]
        if total_text is None or total_assigned[i + 1] is not None:
            continue
        total = parse_danish_number(total_text)
        if total is None:
            continue
        qty, price = rows_qty[i], rows_price[i]
        if qty is not None and price is not None and abs(round(qty * price, 2) - total) <= tolerance:
            continue  # confirmed for its own row — not the ambiguous case
        nxt_qty, nxt_price = rows_qty[i + 1], rows_price[i + 1]
        if nxt_qty is None or nxt_price is None:
            continue
        if abs(round(nxt_qty * nxt_price, 2) - total) <= tolerance:
            total_assigned[i + 1] = total_text
            total_assigned[i] = None


def _derive_single_gap(rows, subtotal, tolerance=0.02):
    """If EXACTLY ONE row's total is still unreadable (no OCR observation,
    direct or arithmetic, could fill it in) and everything else reconciles
    against the receipt's `I alt` once that one value is filled, back that
    single value out of the subtotal and mark the row `derived=True`, so it
    can never be mistaken for a value that was actually read off the
    receipt. The row is resolved (its contribution to the total is now
    known exactly from the subtotal), so it clears `needs_review` — the
    `derived` flag is what keeps it honestly distinct from a read value.

    Refuses to touch anything when two or more rows are unreadable: with
    more than one unknown the subtotal can't attribute the gap to a
    specific row, so those rows stay flagged and the caller reports a
    PARTIAL result. This is the *only* place a value is inferred rather
    than read, it fires on at most one row, and it never overwrites a read
    value.

    A total derived from qty * price is NOT treated as an unknown here —
    that arithmetic is independently validated (both factors passed the
    clean-amount check and column alignment), so it counts as read for the
    purpose of finding the single remaining gap."""
    unreadable = [r for r in rows if r["total"] is None]
    if len(unreadable) != 1:
        return  # 0: nothing to derive. 2+: can't attribute — leave flagged.

    computed = sum(r["total"] for r in rows if r["total"] is not None)
    diff = round(subtotal - computed, 2)
    if abs(diff) <= tolerance:
        return  # the sole gap contributes ~0; nothing meaningful to fill

    row = unreadable[0]
    row["total"] = diff
    row["derived"] = True
    row["needs_review"] = False
    if row.get("qty") not in (None, 0):
        row["unit_price"] = round(diff / row["qty"], 2)
    print(
        f"# NOTE: dagrofa row {row.get('line', '?')} "
        f"({row.get('name', '')!r}) total was UNREADABLE by OCR; DERIVED as "
        f"{diff} by subtracting the read rows from I alt ({subtotal}). This "
        f"is an inferred value, not a read one — row stays flagged for review.",
        file=sys.stderr,
    )


def parse(observations, image):
    header = _find_header(observations)
    bands = _column_bands(header)

    name_obs, antal_obs, pris_obs, total_obs = [], [], [], []
    for o in observations:
        cx, cy = _center(o["bbox"])
        if cy >= header["y"]:
            continue  # header or above
        if cx <= bands["name_max"]:
            name_obs.append(o)
        elif cx <= bands["antal_max"]:
            antal_obs.append(o)
        elif cx <= bands["pris_max"]:
            pris_obs.append(o)
        else:
            total_obs.append(o)

    # Bound the item table using the Antal column: only real item rows ever
    # carry a quantity, so the footer (I alt / Moms / Total incl. moms),
    # payment-method line, and legal boilerplate below it never do — even
    # though several of those lines' *labels* fall inside the name column's
    # x-band and would otherwise get clustered in as bogus "item rows".
    antal_ys = [
        _center(o["bbox"])[1]
        for o in antal_obs
        if parse_danish_number(o["text"]) is not None
    ]
    if not antal_ys:
        raise ValueError("dagrofa: no Antal values found — can't bound the item table")
    row_height_guess = 0.008
    item_bottom_y = min(antal_ys) - row_height_guess
    name_obs = [o for o in name_obs if _center(o["bbox"])[1] > item_bottom_y]

    rows = _cluster_rows(name_obs, row_height=row_height_guess)
    if len(rows) < 2:
        raise ValueError("dagrofa: found too few item rows to be plausible")

    # Row height from the actual data (median gap between consecutive item
    # rows) gives tighter column-matching windows than the bootstrap guess.
    ys = sorted((r["y"] for r in rows), reverse=True)
    gaps = [ys[i] - ys[i + 1] for i in range(len(ys) - 1)]
    gaps.sort()
    row_height = gaps[len(gaps) // 2] if gaps else row_height_guess

    # Footer totals live below the last item row.
    footer_boundary_y = min(r["y"] for r in rows) - row_height * 0.5
    footer = _find_footer(observations, header, footer_boundary_y)

    # Re-cluster with the refined row height, then assign numeric columns.
    rows = _cluster_rows(name_obs, row_height=row_height)
    antal_assigned = _assign_column_dp(rows, antal_obs, row_height)
    pris_assigned = _assign_column_dp(rows, pris_obs, row_height)
    total_assigned = _assign_column_dp(rows, total_obs, row_height)

    qtys = [parse_danish_number(t) for t in antal_assigned]
    prices = [parse_danish_number(t) for t in pris_assigned]
    # Break the one geometric tie the DP alignment can't resolve on its own
    # (see _fix_adjacent_total_swap) using the numbers' own arithmetic.
    _fix_adjacent_total_swap(qtys, prices, total_assigned)

    built = []
    for row, qty, unit_price, total_text in zip(rows, qtys, prices, total_assigned):
        total = parse_danish_number(total_text)
        if total is None and qty is not None and unit_price is not None:
            # Total OCR missed but qty and price both read cleanly — the
            # product is an independently-validated read, not a guess.
            total = round(qty * unit_price, 2)
        elif unit_price is None and qty not in (None, 0) and total is not None:
            unit_price = round(total / qty, 2)
        elif qty is None and unit_price not in (None, 0) and total is not None:
            qty = round(total / unit_price, 2)

        # NB: we do NOT merge an all-numbers-unreadable row into the previous
        # one. A clustered name row is a real line item even when OCR failed
        # to read any of its numeric cells (see Heidelberg on the sample — a
        # genuine item whose qty/pris/total Vision all dropped or garbled).
        # Such a row is emitted and flagged needs_review below, never silently
        # folded away. The only rows dropped are ones with no name text at all.
        if not row["name"].strip():
            continue

        built.append(
            {
                "name": row["name"],
                "qty": qty,
                "unit_price": unit_price,
                "total": total,
                # Set once the total is finalized below. A row whose total is
                # still None after all recovery is unread → flagged for a human
                # enrichment pass. `derived` marks a value inferred from I alt
                # rather than read (see _derive_single_gap).
                "needs_review": False,
                "derived": False,
            }
        )

    for i, row in enumerate(built, start=1):
        row["line"] = i

    # Any total we still couldn't read is flagged, not fabricated.
    for row in built:
        if row["total"] is None:
            row["needs_review"] = True

    # The single allowed inference: if exactly one row is unread, fill it from
    # the receipt's own subtotal, marked derived (stays flagged). Two or more
    # unread rows are all left flagged → the driver reports PARTIAL.
    _derive_single_gap(built, footer["subtotal"])

    out_rows = [
        {
            "line": r["line"],
            "name": r["name"],
            "qty": r["qty"],
            "unit_price": r["unit_price"],
            "total": r["total"],
            "needs_review": r["needs_review"],
            "derived": r["derived"],
        }
        for r in built
    ]
    return out_rows, footer
