import AppKit
import SwiftUI

// Renders the planted fixture's settings content to screenshot.png for the
// swift:review screenshot run. Build from the repo root:
//   swiftc -parse-as-library -swift-version 6 -target arm64-apple-macos26 \
//     maintenance/review-fixtures/render/render.swift \
//     maintenance/review-fixtures/planted/Sources/Demo/SettingsView.swift -o render && ./render
@main
struct Render {
    @MainActor
    static func main() throws {
        let screen = SettingsContent(name: "Jordan Lee", isSynced: false, editingName: .constant(false))
            .frame(width: 390)
            .background(Color.white)
            .environment(\.colorScheme, .light)
        let renderer = ImageRenderer(content: screen)
        renderer.scale = 2
        guard let image = renderer.nsImage,
              let tiff = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiff),
              let png = bitmap.representation(using: .png, properties: [:]) else {
            throw CocoaError(.fileWriteUnknown)
        }
        try png.write(to: URL(fileURLWithPath: "maintenance/review-fixtures/screenshot.png"))
    }
}
