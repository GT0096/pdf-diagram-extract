# pdf-diagram-extract

[![PyPI version](https://img.shields.io/pypi/v/pdf-diagram-extract)](https://pypi.org/project/pdf-diagram-extract/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/pdf-diagram-extract)](https://pypi.org/project/pdf-diagram-extract/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/GT0096/pdf-diagram-extract/blob/main/LICENSE)

Extract diagram and graph entities from PDFs as structured JSON — **no LLM, pure code**.
---
**[📖 Documentation](https://gt0096.github.io/pdf-diagram-extract/)**

## Features

- **Vector extraction** — parses native PDF drawing primitives (rectangles, lines, curves) via PyMuPDF
- **Raster fallback** — renders scanned/image-based pages and uses OpenCV contour detection
- **Shape classification** — identifies rectangles, circles, diamonds, ellipses, polygons
- **Native text extraction** — precise assignment of text to shapes using Intersection and Gravity physics
- **Virtual text nodes** — detects floating text and dynamically generates `text_block` shapes so nothing is lost
- **Edge detection** — detects lines, arrows, and curves with directionality
- **Relationship resolution** — links edges to shapes via spatial proximity
- **Chart detection** — heuristically identifies bar, pie, line, and scatter charts
- **JSON output** — returns a fully structured, serializable result

## Installation

```bash
pip install pdf-diagram-extract
```

Or install from source:

```bash
git clone https://github.com/GT0096/pdf-diagram-extract.git
cd pdf-diagram-extract
pip install -e .
```

## Quick Start

```python
import diagramextract
import json

result = diagramextract.extract("path/to/document.pdf")

# Get JSON output
data = result.to_dict()
print(json.dumps(data, indent=2))

# Access specific pages
for page in result.pages:
    print(f"Page {page.page_number}: {len(page.diagrams)} diagram(s)")
    for diagram in page.diagrams:
        print(f"  Type: {diagram.diagram_type}")
        print(f"  Shapes: {len(diagram.shapes)}")
        print(f"  Edges: {len(diagram.edges)}")
        print(f"  Charts: {len(diagram.charts)}")
```

## API Reference

### `diagramextract.extract(pdf_path, *, pages=None, vector_threshold=5, dpi=200)`

Extract entities from all diagrams/graphs in a PDF.

**Parameters:**
- `pdf_path` (str): Path to the PDF file
- `pages` (list[int] | None): Specific page numbers to process (0-indexed). `None` = all pages.
- `vector_threshold` (int): Minimum vector paths on a page to prefer vector extraction over raster fallback. Default: `5`.
- `dpi` (int): Resolution for raster rendering when falling back to image-based extraction. Default: `200`.

**Returns:** `ExtractionResult` with `.to_dict()` for JSON serialization.

### Output Structure

```json
{
  "source_file": "document.pdf",
  "total_pages": 3,
  "pages": [
    {
      "page_number": 0,
      "width": 612.0,
      "height": 792.0,
      "diagrams": [
        {
          "diagram_type": "flowchart",
          "shapes": [...],
          "edges": [...],
          "charts": [...]
        }
      ]
    }
  ]
}
```

## Dependencies

| Package | Purpose |
|---|---|
| PyMuPDF | PDF parsing, vector paths, page rendering |
| opencv-python-headless | Contour detection, shape classification |
| numpy | Numerical operations |

## License

MIT
