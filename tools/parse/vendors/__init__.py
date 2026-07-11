# Vendor parser registry: maps a vendor id (as returned by detect_vendor.detect)
# to the module that knows how to turn that vendor's OCR observations into
# rows. Every vendor module exposes the same interface:
#
#   parse(observations, image) -> (rows, footer)
#
# where `rows` is a list of dicts with keys
#   line, name, qty, unit_price, total
# and `footer` is a dict with keys
#   subtotal (aka "I alt"), vat (aka "Moms"), total_incl_vat
#
# Adding a new shop = add "vendors/<id>.py" implementing that interface, then
# register it here. Nothing else in the driver needs to change.

from . import dagrofa

PARSERS = {
    "dagrofa": dagrofa,
}


def get(vendor_id):
    return PARSERS.get(vendor_id)
