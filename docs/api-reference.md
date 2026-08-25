# API Reference

## Main Function

### `diagramextract.extract()`

```python
def extract(
    pdf_path: str | Path,
    *,
    pages: list[int] | None = None,
    vector_threshold: int = 5,
    dpi: int = 200,
) -> ExtractionResult
```

Extract diagram and graph entities from a PDF file.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pdf_path` | `str \| Path` | *(required)* | Path to the PDF file |
| `pages` | `list[int] \| None` | `None` | Zero-indexed page numbers to process. `None` = all pages |
| `vector_threshold` | `int` | `5` | Minimum vector drawing primitives on a page to use vector extraction over raster fallback |
| `dpi` | `int` | `200` | Resolution for rendering pages when using raster extraction |

**Returns:** [`ExtractionResult`](#extractionresult)

**Raises:**

- `FileNotFoundError` — if `pdf_path` does not exist
- `ValueError` — if the file is not a `.pdf`

---

## Data Models

All models are Python dataclasses with a `.to_dict()` method for JSON serialization.

### `ExtractionResult`

Top-level container for the extraction output.

| Field | Type | Description |
|---|---|---|
| `source_file` | `str` | Name of the source PDF file |
| `total_pages` | `int` | Total number of pages in the PDF |
| `pages` | `list[PageResult]` | Per-page extraction results |

**Methods:**

- `.to_dict() -> dict` — Serialize to a dictionary
- `.to_json(indent=2) -> str` — Serialize to a JSON string

---

### `PageResult`

Extraction results for a single page.

| Field | Type | Description |
|---|---|---|
| `page_number` | `int` | Zero-indexed page number |
| `width` | `float` | Page width in PDF points (72 pts/inch) |
| `height` | `float` | Page height in PDF points |
| `extraction_method` | `str` | `"vector"` or `"raster"` — which extractor was used |
| `diagrams` | `list[Diagram]` | Diagrams detected on this page |

---

### `Diagram`

A single diagram or graph detected on a page.

| Field | Type | Description |
|---|---|---|
| `diagram_type` | `str` | One of: `"flowchart"`, `"network"`, `"org_chart"`, `"chart"`, `"generic"` |
| `shapes` | `list[Shape]` | Shape nodes in this diagram |
| `edges` | `list[Edge]` | Edges (connections) in this diagram |
| `charts` | `list[ChartElement]` | Detected chart patterns |
| `text_elements` | `list[dict]` | Deprecated. See Virtual Text Nodes in `shapes` |

---

### `Shape`

A detected geometric shape (node) in the diagram.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier (e.g., `"shp_a1b2c3d4"`) |
| `shape_type` | `str` | One of: `"rectangle"`, `"circle"`, `"ellipse"`, `"diamond"`, `"triangle"`, `"polygon"`, `"text_block"`, `"unknown"` |
| `bbox` | `BoundingBox` | Axis-aligned bounding box |
| `center` | `Point` | Center point |
| `vertices` | `list[Point]` | Ordered vertex list (for polygons) |
| `area` | `float` | Area in PDF coordinate units² |
| `fill_color` | `tuple[int,int,int] \| None` | RGB fill color (0–255), or `None` |
| `stroke_color` | `tuple[int,int,int] \| None` | RGB stroke color (0–255), or `None` |
| `stroke_width` | `float` | Stroke width in points |
| `text` | `str \| None` | Native text physically located inside or absorbed into this shape |

---

### `Edge`

A detected connection (line, arrow, curve) in the diagram.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier (e.g., `"edg_e5f6g7h8"`) |
| `edge_type` | `str` | One of: `"line"`, `"arrow"`, `"curve"` |
| `start_point` | `Point` | Starting point |
| `end_point` | `Point` | Ending point |
| `waypoints` | `list[Point]` | Intermediate points along the path |
| `has_arrowhead` | `bool` | Whether an arrowhead was detected |
| `direction` | `str \| None` | `"forward"`, `"backward"`, `"bidirectional"`, or `None` |
| `source_shape_id` | `str \| None` | ID of the shape at the start |
| `target_shape_id` | `str \| None` | ID of the shape at the end |
| `stroke_color` | `tuple[int,int,int] \| None` | RGB stroke color (0–255) |
| `stroke_width` | `float` | Stroke width in points |

---

### `ChartElement`

A detected chart (bar, pie, line, scatter) within a diagram.

| Field | Type | Description |
|---|---|---|
| `chart_type` | `str` | One of: `"bar_chart"`, `"pie_chart"`, `"line_chart"`, `"scatter_plot"` |
| `bbox` | `BoundingBox` | Bounding box of the entire chart region |
| `data_points` | `list[DataPoint]` | Individual data elements |

---

### `DataPoint`

A single data element within a chart.

| Field | Type | Description |
|---|---|---|
| `index` | `int` | Position index in the data series |
| `value` | `float` | Extracted value (height for bars, Y for line/scatter) |
| `bbox` | `BoundingBox` | Bounding box of this element |
| `color` | `tuple[int,int,int] \| None` | RGB color |

---

### `BoundingBox`

Axis-aligned bounding box.

| Field | Type | Description |
|---|---|---|
| `x0` | `float` | Left edge (PDF points) |
| `y0` | `float` | Top edge (PDF points) |
| `x1` | `float` | Right edge (PDF points) |
| `y1` | `float` | Bottom edge (PDF points) |

**Computed properties:** `width`, `height`, `area`, `center`, `aspect_ratio`

---

### `Point`

A 2D point in PDF coordinate space.

| Field | Type | Description |
|---|---|---|
| `x` | `float` | X coordinate (PDF points) |
| `y` | `float` | Y coordinate (PDF points) |

---

## JSON Output Schema

```json
{
  "source_file": "document.pdf",
  "total_pages": 1,
  "pages": [
    {
      "page_number": 0,
      "width": 612.0,
      "height": 792.0,
      "extraction_method": "vector",
      "diagrams": [
        {
          "diagram_type": "flowchart",
          "shapes": [
            {
              "id": "shp_a1b2c3d4",
              "shape_type": "rectangle",
              "bbox": { "x0": 50.0, "y0": 100.0, "x1": 150.0, "y1": 140.0, "width": 100.0, "height": 40.0 },
              "center": { "x": 100.0, "y": 120.0 },
              "vertices": [],
              "area": 4000.0,
              "fill_color": [51, 102, 204],
              "stroke_color": [0, 0, 0],
              "stroke_width": 1.5,
              "text": "Start Process"
            }
          ],
          "edges": [
            {
              "id": "edg_e5f6g7h8",
              "edge_type": "arrow",
              "start_point": { "x": 150.0, "y": 120.0 },
              "end_point": { "x": 200.0, "y": 120.0 },
              "waypoints": [],
              "has_arrowhead": true,
              "direction": "forward",
              "source_shape_id": "shp_a1b2c3d4",
              "target_shape_id": "shp_i9j0k1l2",
              "stroke_color": [0, 0, 0],
              "stroke_width": 1.0
            }
          ],
          "charts": []
        }
      ]
    }
  ]
}
```
