// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "receipt-ocr",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "receipt-ocr",
            path: "Sources/receipt-ocr"
        )
    ]
)
