// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS(.v26), .macOS(.v26)],
    products: [.library(name: "Demo", targets: ["Demo"])],
    targets: [.target(name: "Demo")]
)
