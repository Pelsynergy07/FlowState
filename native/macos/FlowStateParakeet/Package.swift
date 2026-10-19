// swift-tools-version: 6.0
// FlowState's speech helper for macOS: NVIDIA Parakeet TDT 0.6B v2 on the
// Apple Neural Engine through FluidAudio (CoreML). Built by
// packaging/build_macos.sh and bundled inside FlowState.app.
import PackageDescription

let package = Package(
    name: "FlowStateParakeet",
    platforms: [.macOS(.v14)],
    dependencies: [
        // Pinned: the revision FlowState's benchmark measured.
        .package(url: "https://github.com/FluidInference/FluidAudio.git",
                 revision: "6428e29186573c6d33c598e25d460e6690bc0ee1"),
    ],
    targets: [
        .executableTarget(
            name: "FlowStateParakeet",
            dependencies: [.product(name: "FluidAudio", package: "FluidAudio")]
        ),
    ]
)
