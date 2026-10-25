import Foundation
import PDFKit
import AppKit
import CryptoKit
let args=CommandLine.arguments
guard args.count == 3 else { fatalError("Usage: swift inspect_pdf.swift input.pdf output-directory") }
let input=args[1], output=args[2]
guard let doc=PDFDocument(url:URL(fileURLWithPath:input)) else { fatalError("Cannot open PDF") }
try FileManager.default.createDirectory(atPath:output,withIntermediateDirectories:true)
var rows:[[String:Any]]=[]
var text=""
for i in 0..<doc.pageCount {
 let p=doc.page(at:i)!
 let t=p.string ?? ""
 text += "\n\n=== PAGE \(i+1) ===\n" + t
 rows.append(["page":i+1,"characters":t.count,"width":p.bounds(for:.mediaBox).width,"height":p.bounds(for:.mediaBox).height,"links":p.annotations.compactMap { $0.url?.absoluteString }])
 let img=p.thumbnail(of:NSSize(width:900,height:1280),for:.mediaBox)
 if let tiff=img.tiffRepresentation, let rep=NSBitmapImageRep(data:tiff), let png=rep.representation(using:.png,properties:[:]) { try png.write(to:URL(fileURLWithPath:output+"/page-\(i+1).png")) }
}
try text.write(toFile:output+"/extracted.txt",atomically:true,encoding:.utf8)
let digest = SHA256.hash(data: try Data(contentsOf: URL(fileURLWithPath:input))).map { String(format:"%02x",$0) }.joined()
let data=try JSONSerialization.data(withJSONObject:["page_count":doc.pageCount,"pages":rows,"pdf_sha256":digest],options:[.prettyPrinted,.sortedKeys])
try data.write(to:URL(fileURLWithPath:output+"/inspection.json"))
print(String(data:data,encoding:.utf8)!)
