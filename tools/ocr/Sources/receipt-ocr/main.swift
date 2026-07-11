// receipt-ocr — Vision OCR CLI for kitchen receipt photos.
//
// Usage: receipt-ocr <image-path>
//
// Prints a single JSON object to stdout and nothing else:
//   { "image": {"width": W, "height": H}, "observations": [ {..}, ... ] }
//
// Each observation is:
//   { "text": String, "confidence": Float, "bbox": {"x":.., "y":.., "w":.., "h":..} }
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

let requestHandler = VNImageRequestHandler(cgImage: cgImage, orientation: cgOrientation, options: [:])

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["da-DK", "en-US"]
request.usesLanguageCorrection = true

do {
    try requestHandler.perform([request])
} catch {
    fail("Error: Vision request failed: \(error.localizedDescription)")
}

guard let observations = request.results else {
    fail("Error: no OCR results")
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
}

struct ImageInfo: Encodable {
    let width: Int
    let height: Int
}

struct Output: Encodable {
    let image: ImageInfo
    let observations: [Observation]
}

var results: [Observation] = []
for observation in observations {
    guard let candidate = observation.topCandidates(1).first else { continue }
    let box = observation.boundingBox
    results.append(
        Observation(
            text: candidate.string,
            confidence: candidate.confidence,
            bbox: BBox(x: box.origin.x, y: box.origin.y, w: box.width, h: box.height)
        )
    )
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
