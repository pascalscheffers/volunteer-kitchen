#!/usr/bin/env python3
"""Rename receipt photos to a sortable `YYYYMMDD-HHMMSS` stem, and migrate the
sibling OCR/CSV artifacts so the stem stays the shared key across
`2026/finance/{receipts,ocr,csv}/`.

Usage:
    python3 tools/rename_receipts.py [--dry-run] [paths...]

With no paths, processes every image in `2026/finance/receipts/`.

Timestamp source, in priority order (macOS-only, matching the rest of the
pipeline):
  1. The receipt's own printed date/time, read from its OCR JSON via the vendor
     parser (`vendors/<id>.header_datetime`). Authoritative for the date.
  2. EXIF `DateTimeOriginal` (via `sips -g creation`) when the receipt time
     wasn't captured — the photo is taken at checkout, so it's within a minute.
  3. File mtime, last resort.

Idempotent: a file already named `YYYYMMDD-HHMMSS` (optionally `-N`) is skipped,
so re-running is a no-op. Collisions get a `-2`, `-3`, … suffix.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RECEIPTS = os.path.join(REPO, "2026", "finance", "receipts")
OCR_DIR = os.path.join(REPO, "2026", "finance", "ocr")
CSV_DIR = os.path.join(REPO, "2026", "finance", "csv")

IMAGE_EXTS = {".jpeg", ".jpg", ".png", ".heic"}
STAMP_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")

# Import the parse package the same way parse_receipt.py does (its dir on path).
sys.path.insert(0, os.path.join(HERE, "parse"))
import detect_vendor  # noqa: E402
import vendors  # noqa: E402


def _receipt_datetime(stem):
    """(date 'YYYY-MM-DD', time 'HH:MM:SS') from the receipt's OCR JSON via its
    vendor parser, each possibly None. Returns (None, None) if no OCR JSON."""
    ocr_path = os.path.join(OCR_DIR, stem + ".json")
    if not os.path.exists(ocr_path):
        return None, None
    import json

    try:
        with open(ocr_path, encoding="utf-8") as f:
            obs = json.load(f).get("observations", [])
    except (OSError, ValueError):
        return None, None
    vendor_id = detect_vendor.detect(obs)
    parser = vendors.get(vendor_id)
    if parser is None or not hasattr(parser, "header_datetime"):
        return None, None
    dt = parser.header_datetime(obs)
    return dt.get("date"), dt.get("time")


def _exif_datetime(path):
    """(date, time) from EXIF DateTimeOriginal via `sips -g creation`, or
    (None, None). sips prints e.g. `creation: 2026:07:10 15:58:35` in local
    time (unlike mdls, which reports UTC)."""
    try:
        out = subprocess.run(
            ["sips", "-g", "creation", path],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    m = re.search(r"creation:\s*(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", out)
    if not m:
        return None, None
    y, mo, d, hh, mi, ss = m.groups()
    return f"{y}-{mo}-{d}", f"{hh}:{mi}:{ss}"


def _mtime_datetime(path):
    import datetime

    dt = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def _stamp_for(path):
    """Resolve the sortable stem base (`YYYYMMDD-HHMMSS`) for an image, plus a
    short note on where the timestamp came from."""
    stem = os.path.splitext(os.path.basename(path))[0]
    r_date, r_time = _receipt_datetime(stem)
    e_date, e_time = _exif_datetime(path)

    if r_date and r_time:
        date, time, src = r_date, r_time, "receipt"
    elif e_date and e_time:
        # Receipt date is authoritative when we have it; borrow EXIF's time.
        if r_date and r_date != e_date:
            date, time, src = r_date, e_time, "receipt-date+exif-time (date mismatch!)"
        else:
            date, time, src = e_date, e_time, ("exif" if not r_date else "receipt-date+exif-time")
    elif r_date:
        date, time, src = r_date, "00:00:00", "receipt-date only (time unknown)"
    else:
        date, time, src = (*_mtime_datetime(path),)  # noqa
        src = "mtime"
    base = date.replace("-", "") + "-" + time.replace(":", "")
    return base, src


def _is_tracked(path):
    return subprocess.run(
        ["git", "-C", REPO, "ls-files", "--error-unmatch", path],
        capture_output=True,
    ).returncode == 0


def _move(src, dst, dry_run):
    rel_src = os.path.relpath(src, REPO)
    rel_dst = os.path.relpath(dst, REPO)
    print(f"  {'[dry-run] ' if dry_run else ''}{rel_src} -> {rel_dst}")
    if dry_run:
        return
    if _is_tracked(src):
        subprocess.run(["git", "-C", REPO, "mv", src, dst], check=True)
    else:
        os.rename(src, dst)


def process(image_path, dry_run):
    stem = os.path.splitext(os.path.basename(image_path))[0]
    if STAMP_RE.match(stem):
        return False  # already stamped — idempotent skip
    ext = os.path.splitext(image_path)[1].lower()

    base, src = _stamp_for(image_path)
    # Collision: bump -2, -3, … against existing receipt filenames.
    new_stem = base
    n = 1
    while os.path.exists(os.path.join(RECEIPTS, new_stem + ext)):
        n += 1
        new_stem = f"{base}-{n}"

    print(f"{os.path.basename(image_path)} -> {new_stem}{ext}  ({src})")
    _move(image_path, os.path.join(RECEIPTS, new_stem + ext), dry_run)
    # Migrate siblings that share the old stem.
    for d, sib_ext in ((OCR_DIR, ".json"), (CSV_DIR, ".csv")):
        old = os.path.join(d, stem + sib_ext)
        if os.path.exists(old):
            _move(old, os.path.join(d, new_stem + sib_ext), dry_run)
    return True


def main(argv):
    dry_run = "--dry-run" in argv
    paths = [a for a in argv[1:] if a != "--dry-run"]
    if not paths:
        if not os.path.isdir(RECEIPTS):
            print(f"No receipts dir at {RECEIPTS}", file=sys.stderr)
            return 1
        paths = [
            os.path.join(RECEIPTS, f)
            for f in sorted(os.listdir(RECEIPTS))
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS
        ]

    changed = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"Skip (missing): {p}", file=sys.stderr)
            continue
        if process(p, dry_run):
            changed += 1
    if changed == 0:
        print("Nothing to rename (all already stamped).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
