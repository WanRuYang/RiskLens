import Vision
import Foundation
import AppKit

let arguments = CommandLine.arguments
guard arguments.count > 1 else {
    print("Usage: swift native_ocr.swift <image_path>")
    exit(1)
}

let imagePath = arguments[1]
let imageUrl = URL(fileURLWithPath: imagePath)

guard let image = NSImage(contentsOf: imageUrl),
      let tiffData = image.tiffRepresentation,
      let ciImage = CIImage(data: tiffData) else {
    print("Error: Could not load image at \(imagePath)")
    exit(1)
}

let requestHandler = VNImageRequestHandler(ciImage: ciImage, options: [:])
let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    
    let recognizedStrings = observations.compactMap { observation in
        return observation.topCandidates(1).first?.string
    }
    
    print(recognizedStrings.joined(separator: "\n"))
}

request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

do {
    try requestHandler.perform([request])
} catch {
    print("Error: \(error)")
    exit(1)
}
