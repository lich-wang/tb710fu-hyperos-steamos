// List / set display modes for a display by name (uses CoreGraphics, no third-party tools)
// usage: displaymode list "<name>" | displaymode set "<name>" <width> <height> [hidpi]
import CoreGraphics
import AppKit

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: list|set <name> [w h hidpi]"); exit(1) }
let screen = NSScreen.screens.first { $0.localizedName.contains(args[2]) }
guard let s = screen, let id = s.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID else {
    print("display not found: \(NSScreen.screens.map { $0.localizedName })"); exit(1)
}
let opts = [kCGDisplayShowDuplicateLowResolutionModes: kCFBooleanTrue] as CFDictionary
let modes = (CGDisplayCopyAllDisplayModes(id, opts) as? [CGDisplayMode]) ?? []
func hidpi(_ m: CGDisplayMode) -> Bool { m.pixelWidth > m.width }
if args[1] == "list" {
    let cur = CGDisplayCopyDisplayMode(id)
    for m in modes {
        print("\(m.width)x\(m.height) px=\(m.pixelWidth)x\(m.pixelHeight) \(hidpi(m) ? "HiDPI" : "") \(Int(m.refreshRate))Hz\(m == cur ? "  <- current" : "")")
    }
} else if args[1] == "set", args.count >= 5, let w = Int(args[3]), let h = Int(args[4]) {
    let wantHi = args.count > 5
    guard let m = modes.first(where: { $0.width == w && $0.height == h && hidpi($0) == wantHi }) ?? modes.first(where: { $0.width == w && $0.height == h }) else {
        print("mode not available"); exit(1)
    }
    var cfg: CGDisplayConfigRef?
    CGBeginDisplayConfiguration(&cfg)
    CGConfigureDisplayWithDisplayMode(cfg, id, m, nil)
    let r = CGCompleteDisplayConfiguration(cfg, .permanently)
    print(r == .success ? "set \(m.width)x\(m.height) px=\(m.pixelWidth)x\(m.pixelHeight)" : "failed \(r.rawValue)")
}
