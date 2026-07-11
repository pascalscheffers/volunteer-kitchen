// receipt-ocr — Vision OCR CLI for kitchen receipt photos.
//
// Usage: receipt-ocr <image-path>
//
// Prints a single JSON object to stdout and nothing else:
//   { "image": {"width": W, "height": H}, "observations": [ {..}, ... ] }
//
// Each observation is:
//   { "text": String, "confidence": Float, "bbox": {"x":.., "y":.., "w":.., "h":..},
//     "source": "accurate" | "fast" }
// `source` records which of the two Vision passes produced the observation
// (see the dual-pass merge below); it's provenance for auditing only and the
// parser does not depend on it.
//
// COORDINATE SYSTEM (matters for Phase 2's parser):
//   `bbox` is Vision's raw normalized `boundingBox`: x/y/w/h are all in the
//   0.0...1.0 range, relative to the (EXIF-corrected, "upright") image, with
//   the ORIGIN AT THE BOTTOM-LEFT corner (Vision/CoreGraphics convention,
//   NOT the top-left convention used by most image/UI coordinate systems).
//   We do NOT flip or convert this here — the downstream parser must handle
//   the bottom-left origin itself when it denormalizes against
//   `image.width` / `image.height` (which are the upright pixel dimensions,
//   i.e. width/height already account for EXIF rotation).
//
// All errors and usage text go to stderr; stdout carries only the JSON.

import Foundation
import ImageIO
import Vision
#if canImport(CoreGraphics)
import CoreGraphics
#endif

func fail(_ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(1)
}

let arguments = CommandLine.arguments
guard arguments.count == 2 else {
    fail("Usage: receipt-ocr <image-path>")
}

let imagePath = arguments[1]
let imageURL = URL(fileURLWithPath: imagePath)

guard FileManager.default.fileExists(atPath: imageURL.path) else {
    fail("Error: file not found: \(imagePath)")
}

guard let imageSource = CGImageSourceCreateWithURL(imageURL as CFURL, nil) else {
    fail("Error: could not open image: \(imagePath)")
}

guard let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
    fail("Error: could not decode image: \(imagePath)")
}

// Read EXIF/TIFF orientation (values 1-8, same numbering CGImagePropertyOrientation
// uses) so Vision reads the photo the right way up regardless of how the camera
// held it. Default to `.up` (1) when the tag is absent.
var cgOrientation: CGImagePropertyOrientation = .up
if let properties = CGImageSourceCopyPropertiesAtIndex(imageSource, 0, nil) as? [CFString: Any],
   let rawOrientation = properties[kCGImagePropertyOrientation] as? UInt32,
   let orientation = CGImagePropertyOrientation(rawValue: rawOrientation) {
    cgOrientation = orientation
}

// Upright pixel dimensions: for orientations that rotate 90/270 degrees, the
// displayed width/height are swapped relative to the raw CGImage's storage
// width/height. Compute them from the orientation so downstream denormalization
// against `image.width`/`image.height` matches the same frame `bbox` is in.
let rawWidth = cgImage.width
let rawHeight = cgImage.height
let swapsDimensions: Bool
switch cgOrientation {
case .left, .leftMirrored, .right, .rightMirrored:
    swapsDimensions = true
default:
    swapsDimensions = false
}
let uprightWidth = swapsDimensions ? rawHeight : rawWidth
let uprightHeight = swapsDimensions ? rawWidth : rawHeight

// Dual-pass OCR. We run Vision twice over the same image and merge:
//
//   .accurate — cleaner text, especially on the Danish item NAMES (its
//     language model fixes up characters .fast garbles, e.g. "Heidelberg"
//     instead of "H&idelberg"), BUT on this dense multi-column table its
//     line-merging heuristics drop whole numeric cells outright — several
//     Pris/Total values produce no observation at all (verified by cropping
//     the source photo: the print is crisp, .accurate just returns nothing
//     there).
//   .fast — splits each column fragment into its own observation and so
//     recovers nearly all of those dropped numeric cells, at the cost of
//     noisier text.
//
// Merge strategy — three cases for each .fast observation, decided by how it
// overlaps the .accurate observations (overlap = either box covering at least
// OVERLAP_THRESHOLD of the other; a whole-name .fast box and .accurate's
// sub-fragments of the same name overlap under this either-direction test,
// which the one-directional test missed):
//
//   1. No overlap with any .accurate box → the .fast obs sits where .accurate
//      saw nothing. KEEP it — this is how .fast fills numeric cells .accurate
//      dropped.
//   2. Overlaps .accurate, and the .fast text is a clean amount (Danish
//      2-decimal, e.g. "15,95") while every overlapping .accurate obs is NOT
//      a clean amount → the region is a numeric cell .accurate garbled
//      ("15,", "95") but .fast read cleanly. REPLACE: drop those .accurate
//      fragments, keep the clean .fast number.
//   3. Otherwise (overlaps .accurate and doesn't beat it on cleanliness) →
//      DROP the .fast obs and keep .accurate's text. This is the common case
//      for NAMES: .accurate's language model gives the cleaner reading
//      ("Heidelberg", not "H&idelberg"), so we prefer it and don't duplicate.
//
// Net effect: .accurate text for names, .fast's clean numbers where .accurate
// garbled them, and .fast gap-fills where .accurate saw nothing. Each
// observation is tagged with the pass it came from ("source") purely for
// audit; the parser ignores it.

func recognize(level: VNRequestTextRecognitionLevel) -> [VNRecognizedTextObservation] {
    // Fresh handler per pass — a VNImageRequestHandler is intended for a
    // single perform, so we don't reuse one across the two recognition levels.
    let handler = VNImageRequestHandler(cgImage: cgImage, orientation: cgOrientation, options: [:])
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = level
    request.recognitionLanguages = ["da-DK", "en-US"]
    request.usesLanguageCorrection = true
    do {
        try handler.perform([request])
    } catch {
        fail("Error: Vision request failed: \(error.localizedDescription)")
    }
    return request.results ?? []
}

struct BBox: Encodable {
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}

struct Observation: Encodable {
    let text: String
    let confidence: Float
    let bbox: BBox
    let source: String
}

struct ImageInfo: Encodable {
    let width: Int
    let height: Int
}

struct Output: Encodable {
    let image: ImageInfo
    let observations: [Observation]
}

func toObservation(_ o: VNRecognizedTextObservation, source: String) -> Observation? {
    guard let candidate = o.topCandidates(1).first else { return nil }
    let box = o.boundingBox
    return Observation(
        text: candidate.string,
        confidence: candidate.confidence,
        bbox: BBox(x: box.origin.x, y: box.origin.y, w: box.width, h: box.height),
        source: source
    )
}

// Fraction of box `a`'s area that lies inside box `b` (normalized coords).
func coverage(_ a: BBox, by b: BBox) -> Double {
    let ix0 = max(a.x, b.x)
    let iy0 = max(a.y, b.y)
    let ix1 = min(a.x + a.w, b.x + b.w)
    let iy1 = min(a.y + a.h, b.y + b.h)
    let iw = ix1 - ix0
    let ih = iy1 - iy0
    if iw <= 0 || ih <= 0 { return 0 }
    let areaA = a.w * a.h
    if areaA <= 0 { return 0 }
    return (iw * ih) / areaA
}

// Two boxes "overlap" if either covers at least this fraction of the other.
// Either-direction so a wide .fast whole-name box and .accurate's narrower
// sub-fragments of the same name still count as overlapping.
let OVERLAP_THRESHOLD = 0.4

func overlaps(_ a: BBox, _ b: BBox) -> Bool {
    return coverage(a, by: b) >= OVERLAP_THRESHOLD || coverage(b, by: a) >= OVERLAP_THRESHOLD
}

// A Dagrofa amount prints as Danish 2-decimal (e.g. "15,95", "1.234,00").
// Used only to decide, at merge time, when a clean .fast number should
// displace a garbled .accurate fragment of the same cell.
let cleanAmount = try! NSRegularExpression(pattern: "^\\d{1,3}(\\.\\d{3})*,\\d{2}$")
func isCleanAmount(_ text: String) -> Bool {
    let t = text.trimmingCharacters(in: .whitespaces)
    let range = NSRange(t.startIndex..<t.endIndex, in: t)
    return cleanAmount.firstMatch(in: t, range: range) != nil
}

let accurateObs = recognize(level: .accurate).compactMap { toObservation($0, source: "accurate") }
let fastObs = recognize(level: .fast).compactMap { toObservation($0, source: "fast") }

// keepAccurate[i] flips to false if a clean .fast number displaces that
// garbled .accurate fragment (case 2 in the merge comment above).
var keepAccurate = [Bool](repeating: true, count: accurateObs.count)
var extras: [Observation] = []
for f in fastObs {
    let overlapping = accurateObs.indices.filter { overlaps(f.bbox, accurateObs[$0].bbox) }
    if overlapping.isEmpty {
        extras.append(f)  // case 1: fills a region .accurate never saw
    } else if isCleanAmount(f.text) && overlapping.allSatisfy({ !isCleanAmount(accurateObs[$0].text) }) {
        for i in overlapping { keepAccurate[i] = false }  // case 2: clean number wins
        extras.append(f)
    }
    // else case 3: .accurate keeps the region (names), drop the .fast obs
}

var results: [Observation] = accurateObs.indices.filter { keepAccurate[$0] }.map { accurateObs[$0] }
results.append(contentsOf: extras)

// Emit in a stable reading order (top to bottom, then left to right in the
// bottom-left-origin frame) so the merged output is deterministic and easy
// to diff, rather than accurate-then-fast append order.
results.sort { lhs, rhs in
    let ly = lhs.bbox.y + lhs.bbox.h / 2
    let ry = rhs.bbox.y + rhs.bbox.h / 2
    if abs(ly - ry) > 0.002 { return ly > ry }
    return (lhs.bbox.x + lhs.bbox.w / 2) < (rhs.bbox.x + rhs.bbox.w / 2)
}

let output = Output(image: ImageInfo(width: uprightWidth, height: uprightHeight), observations: results)

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

do {
    let data = try encoder.encode(output)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
} catch {
    fail("Error: failed to encode JSON: \(error.localizedDescription)")
}
