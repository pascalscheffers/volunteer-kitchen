# Vendor detection: match header/footer text in the OCR observations against
# a small, data-driven table of known vendors. Adding a new shop is adding a
# row here (plus a vendors/<id>.py parser) — not rewriting this logic.
#
# Unknown vendor -> "unknown". The driver refuses to guess a layout for a
# shop we haven't built a parser for (see PLAN.md's "unknown vendor -> stop"
# invariant).

# Each entry: vendor id -> list of marker strings. A vendor matches if ANY of
# its markers appears as a substring of ANY observation's text (case-
# sensitive for acronyms/CVR numbers, which is deliberate — "food service"
# lowercase is not the same signal as shouting brand text).
VENDOR_MARKERS = {
    "dagrofa": [
        "Dagrofa",
        "FOOD SERVICE",
        "27626904",  # CVR number printed on the receipt header
    ],
}


def detect(observations):
    """Return the vendor id whose markers appear in `observations`, or
    "unknown" if none match."""
    texts = [o.get("text", "") for o in observations]
    for vendor_id, markers in VENDOR_MARKERS.items():
        for marker in markers:
            if any(marker in text for text in texts):
                return vendor_id
    return "unknown"
