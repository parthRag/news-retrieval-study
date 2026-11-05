"""Portable PDF page, text and link inspection; no macOS PDFKit/Swift required."""
import argparse
import json
from pathlib import Path

from pypdf import PdfReader
from news_ir.data import sha256_file


def inspect(source, output):
    source, output = Path(source), Path(output)
    reader = PdfReader(source)
    output.mkdir(parents=True, exist_ok=True)
    rows, parts = [], []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        parts.append(f"\n\n=== PAGE {number} ===\n" + text)
        links = []
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            action = annotation.get("/A", {})
            if action.get("/URI"):
                links.append(str(action["/URI"]))
        rows.append({"page": number, "characters": len(text), "width": float(page.mediabox.width),
                     "height": float(page.mediabox.height), "links": links})
    result = {"page_count": len(rows), "pages": rows, "pdf_sha256": sha256_file(source),
              "inspection_backend": "pypdf; raster screenshots are a separate optional browser check"}
    (output / "extracted.txt").write_text("".join(parts), encoding="utf-8", newline="\n")
    (output / "inspection.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.input, args.output), indent=2))
