// poza.swift — cheamă Image Playground din linia de comandă.
//
// Image Playground n-are unealtă de terminal și nici dicționar de AppleScript
// util. Are însă `ImageCreator`, un API fără interfață, disponibil din
// macOS 15.4. Programul ăsta îl împachetează, ca să pot genera imagini direct,
// fără să deschidă nimeni aplicația.
//
// Compilare:  swiftc -O poza.swift -o poza
// Folosire:   ./poza "descrierea imaginii" [cate] [stil] [dosar]
//             stil: illustration | animation | sketch
import Foundation
import ImagePlayground
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

@main
struct Poza {
    static func main() async {
        let a = CommandLine.arguments
        guard a.count > 1 else {
            print("folosire: poza \"descriere\" [cate=4] [stil=illustration] [dosar=.]")
            exit(2)
        }
        let descriere = a[1]
        let cate = a.count > 2 ? Int(a[2]) ?? 4 : 4
        let numeStil = a.count > 3 ? a[3] : "illustration"
        let dosar = a.count > 4 ? a[4] : FileManager.default.currentDirectoryPath

        let stil: ImagePlaygroundStyle
        switch numeStil {
        case "animation": stil = .animation
        case "sketch":    stil = .sketch
        default:          stil = .illustration
        }

        do {
            let creator = try await ImageCreator()
            var n = 0
            for try await poza in creator.images(for: [.text(descriere)], style: stil, limit: cate) {
                n += 1
                let cale = URL(fileURLWithPath: dosar)
                    .appendingPathComponent("ip-\(numeStil)-\(n).png")
                guard let dest = CGImageDestinationCreateWithURL(
                        cale as CFURL, UTType.png.identifier as CFString, 1, nil) else { continue }
                CGImageDestinationAddImage(dest, poza.cgImage, nil)
                CGImageDestinationFinalize(dest)
                print("✅ \(cale.path)")
            }
            if n == 0 { print("⚠️  n-a ieșit nicio imagine"); exit(1) }
        } catch {
            print("❌ \(error)")
            exit(1)
        }
    }
}
