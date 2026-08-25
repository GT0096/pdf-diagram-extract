"""Data models for diagram extraction results.

All entities are represented as dataclasses with .to_dict() methods
for JSON serialization. Coordinates use PDF points (72 pts/inch)
with origin at top-left, matching PyMuPDF's coordinate system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def _generate_id(prefix: str = "ent") -> str:
    """Generate a short unique ID for an entity."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class Point:
    """A 2D point in PDF coordinate space."""

    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 2), "y": round(self.y, 2)}

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class BoundingBox:
    """Axis-aligned bounding box defined by two corners."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(
            x=(self.x0 + self.x1) / 2.0,
            y=(self.y0 + self.y1) / 2.0,
        )

    @property
    def aspect_ratio(self) -> float:
        """Width / height ratio. Returns 0 if height is zero."""
        if self.height == 0:
            return 0.0
        return self.width / self.height

    def to_dict(self) -> dict[str, float]:
        return {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }


@dataclass
class Shape:
    """A detected shape (node) in the diagram.

    Attributes:
        id: Unique identifier for this shape.
        shape_type: One of "rectangle", "circle", "ellipse", "diamond",
                     "triangle", "polygon", "unknown".
        bbox: Axis-aligned bounding box enclosing the shape.
        center: Center point of the shape.
        vertices: Ordered vertex list (for polygons/diamonds/triangles).
        area: Area of the shape in PDF coordinate units squared.
        fill_color: RGB fill color as (r, g, b) tuple (0-255), or None.
        stroke_color: RGB stroke color as (r, g, b) tuple (0-255), or None.
        stroke_width: Width of the stroke in points.
    """

    id: str = field(default_factory=lambda: _generate_id("shp"))
    shape_type: str = "unknown"
    bbox: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))
    center: Point = field(default_factory=lambda: Point(0, 0))
    vertices: list[Point] = field(default_factory=list)
    area: float = 0.0
    fill_color: tuple[int, int, int] | None = None
    stroke_color: tuple[int, int, int] | None = None
    stroke_width: float = 1.0
    text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "shape_type": self.shape_type,
            "bbox": self.bbox.to_dict(),
            "center": self.center.to_dict(),
            "vertices": [v.to_dict() for v in self.vertices],
            "area": round(self.area, 2),
            "fill_color": list(self.fill_color) if self.fill_color else None,
            "stroke_color": list(self.stroke_color) if self.stroke_color else None,
            "stroke_width": round(self.stroke_width, 2),
            "text": self.text,
        }


@dataclass
class Edge:
    """A detected edge (connection) in the diagram.

    Attributes:
        id: Unique identifier for this edge.
        edge_type: One of "line", "arrow", "curve".
        start_point: Starting point of the edge.
        end_point: Ending point of the edge.
        waypoints: Intermediate points along the edge path.
        has_arrowhead: Whether an arrowhead was detected.
        direction: "forward" (start→end), "backward", "bidirectional", or None.
        source_shape_id: ID of the shape at the start, or None if unresolved.
        target_shape_id: ID of the shape at the end, or None if unresolved.
        stroke_color: RGB stroke color as (r, g, b) tuple (0-255), or None.
        stroke_width: Width of the stroke in points.
    """

    id: str = field(default_factory=lambda: _generate_id("edg"))
    edge_type: str = "line"
    start_point: Point = field(default_factory=lambda: Point(0, 0))
    end_point: Point = field(default_factory=lambda: Point(0, 0))
    waypoints: list[Point] = field(default_factory=list)
    has_arrowhead: bool = False
    direction: str | None = None
    source_shape_id: str | None = None
    target_shape_id: str | None = None
    stroke_color: tuple[int, int, int] | None = None
    stroke_width: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "edge_type": self.edge_type,
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict(),
            "waypoints": [w.to_dict() for w in self.waypoints],
            "has_arrowhead": self.has_arrowhead,
            "direction": self.direction,
            "source_shape_id": self.source_shape_id,
            "target_shape_id": self.target_shape_id,
            "stroke_color": list(self.stroke_color) if self.stroke_color else None,
            "stroke_width": round(self.stroke_width, 2),
        }


@dataclass
class DataPoint:
    """A single data point extracted from a chart element."""

    index: int = 0
    value: float = 0.0
    bbox: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))
    color: tuple[int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "value": round(self.value, 2),
            "bbox": self.bbox.to_dict(),
            "color": list(self.color) if self.color else None,
        }


@dataclass
class ChartElement:
    """A detected chart (bar, pie, line, scatter) within a diagram.

    Attributes:
        chart_type: One of "bar_chart", "pie_chart", "line_chart", "scatter_plot".
        bbox: Bounding box enclosing the entire chart region.
        data_points: Individual data elements detected in the chart.
    """

    chart_type: str = "unknown"
    bbox: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))
    data_points: list[DataPoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "bbox": self.bbox.to_dict(),
            "data_points": [dp.to_dict() for dp in self.data_points],
        }


@dataclass
class TextElement:
    """A detected text block in the diagram (e.g. edge label, title).

    Attributes:
        id: Unique identifier for this text element.
        text: The extracted string content.
        bbox: Bounding box enclosing the text.
    """

    id: str = field(default_factory=lambda: _generate_id("txt"))
    text: str = ""
    bbox: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": self.bbox.to_dict(),
        }


@dataclass
class Diagram:
    """A single diagram or graph detected on a page.

    Shapes and edges that form a connected component are grouped
    into the same Diagram instance.

    Attributes:
        diagram_type: One of "flowchart", "network", "org_chart", "chart", "generic".
        shapes: Shape nodes belonging to this diagram.
        edges: Edges (connections) belonging to this diagram.
        charts: Chart elements detected within this diagram region.
    """

    diagram_type: str = "generic"
    shapes: list[Shape] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    charts: list[ChartElement] = field(default_factory=list)
    text_elements: list[TextElement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "shapes": [s.to_dict() for s in self.shapes],
            "edges": [e.to_dict() for e in self.edges],
            "charts": [c.to_dict() for c in self.charts],
            "text_elements": [t.to_dict() for t in self.text_elements],
        }


@dataclass
class PageResult:
    """Extraction results for a single PDF page.

    Attributes:
        page_number: Zero-indexed page number.
        width: Page width in PDF points.
        height: Page height in PDF points.
        extraction_method: "vector" or "raster" — which extractor was used.
        diagrams: List of diagrams detected on this page.
    """

    page_number: int = 0
    width: float = 0.0
    height: float = 0.0
    extraction_method: str = "vector"
    diagrams: list[Diagram] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "extraction_method": self.extraction_method,
            "diagrams": [d.to_dict() for d in self.diagrams],
        }


@dataclass
class ExtractionResult:
    """Top-level result of diagram extraction from a PDF.

    Attributes:
        source_file: Path to the source PDF file.
        total_pages: Total number of pages in the PDF.
        pages: Per-page extraction results.
    """

    source_file: str = ""
    total_pages: int = 0
    pages: list[PageResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "total_pages": self.total_pages,
            "pages": [p.to_dict() for p in self.pages],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the entire result to a JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=indent)
