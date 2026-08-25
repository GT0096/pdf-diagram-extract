# Getting Started

## Installation

### From PyPI (recommended)

```bash
pip install pdf-diagram-extract
```

### From source

```bash
git clone https://github.com/GT0096/pdf-diagram-extract.git
cd pdf-diagram-extract
pip install -e .
```

### For development

```bash
pip install -e ".[dev]"
```

This installs additional dependencies for testing (`pytest`, `reportlab`, `matplotlib`).

---

## Basic Usage

### Extract entities from a PDF

```python
import diagramextract
import json

# Extract all diagram entities
result = diagramextract.extract("path/to/document.pdf")

# Get JSON output
data = result.to_dict()
print(json.dumps(data, indent=2))
```

### Iterate over results

```python
result = diagramextract.extract("document.pdf")

for page in result.pages:
    print(f"Page {page.page_number} ({page.extraction_method} extraction)")
    print(f"  Page size: {page.width} × {page.height} points")

    for diagram in page.diagrams:
        print(f"  Diagram type: {diagram.diagram_type}")
        print(f"    Shapes: {len(diagram.shapes)}")
        print(f"    Edges: {len(diagram.edges)}")
        print(f"    Charts: {len(diagram.charts)}")

        for shape in diagram.shapes:
            print(f"      {shape.shape_type} at ({shape.center.x:.0f}, {shape.center.y:.0f})")
```

### Process specific pages

```python
# Only process pages 0 and 2
result = diagramextract.extract("document.pdf", pages=[0, 2])
```

### Control extraction behavior

```python
result = diagramextract.extract(
    "document.pdf",
    vector_threshold=10,  # Require more vector paths before using vector extraction
    dpi=300,              # Higher resolution for raster fallback (slower but more accurate)
)
```

---

## How It Works

The extraction pipeline has 5 stages:

```
PDF → Type Detection → Extraction → Classification → Relationship Resolution → Chart Detection → JSON
```

### 1. Type Detection

Each page is analyzed for vector drawing primitives. If the page has ≥ `vector_threshold` primitives (default: 5), **vector extraction** is used. Otherwise, the page is rendered to an image and **raster extraction** kicks in.

### 2. Extraction

- **Vector**: Parses rectangles, lines, curves, quads, and closed polygon/circle paths from the PDF content stream using PyMuPDF's `get_drawings()` API.
- **Raster**: Renders the page at the specified DPI, applies adaptive thresholding, then uses OpenCV contour detection and Hough line transform.

### 3. Shape Classification

Raw primitives are classified into shape types (rectangle, circle, diamond, triangle, ellipse, polygon), deduplicated via IoU overlap, and filtered for noise. Small triangles near edge endpoints are converted into arrowheads.

### 4. Relationship Resolution

Edge endpoints are matched to nearby shape boundaries using spatial proximity. Connected shapes and edges are grouped into separate `Diagram` instances using union-find. Each diagram is classified as a flowchart, network, org chart, etc.

### 5. Chart Detection

Heuristic rules identify common chart patterns:

| Chart | Pattern |
|---|---|
| Bar chart | Multiple rectangles of similar width, aligned on one axis |
| Pie chart | Large circle with radial line segments inside |
| Line chart | Evenly-spaced small dots connected by edges |
| Scatter plot | Cluster of small unconnected dots |

---

## Dependencies

| Package | Purpose | Why |
|---|---|---|
| **PyMuPDF** | PDF parsing | Vector path extraction + page rendering |
| **opencv-python-headless** | Image processing | Contour detection for scanned PDFs |
| **numpy** | Numerical operations | Array math (transitive dep of both) |

!!! note "No ML, no OCR, no LLM"
    This package uses only geometric heuristics. There are no machine learning models, no Tesseract OCR, and no LLM API calls. It's pure code.
