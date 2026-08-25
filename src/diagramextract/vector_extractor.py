"""Vector-based extraction of shapes and edges from native PDF pages.

Uses PyMuPDF's page.get_drawings() API to parse the PDF content stream
and extract line art primitives (rectangles, lines, curves, quads).
These raw primitives are then converted into Shape and Edge model objects.
"""

from __future__ import annotations

import math
from typing import Any

import fitz  # PyMuPDF

from .models import BoundingBox, Edge, Point, Shape
from .utils import classify_polygon, rgb_float_to_int


# Minimum area (in sq points) for a shape to be considered valid.
# Filters out tiny decorative elements and hairlines.
MIN_SHAPE_AREA = 50.0

# Maximum area ratio relative to page — shapes larger than this
# fraction of the page are likely background fills, not diagram nodes.
MAX_SHAPE_PAGE_RATIO = 0.8

# Minimum length for a line to be considered a meaningful edge.
MIN_LINE_LENGTH = 5.0


def extract_page(
    page: fitz.Page,
    min_shape_area: float = MIN_SHAPE_AREA,
    max_shape_page_ratio: float = MAX_SHAPE_PAGE_RATIO,
    min_line_length: float = MIN_LINE_LENGTH,
) -> tuple[list[Shape], list[Edge]]:
    """Extract shapes and edges from a single PDF page using vector paths.

    Args:
        page: A PyMuPDF Page object.
        min_shape_area: Minimum area for a shape to be kept.
        max_shape_page_ratio: Maximum area ratio vs. page size.
        min_line_length: Minimum length for an edge to be kept.

    Returns:
        A tuple of (shapes, edges) extracted from vector drawings.
    """
    drawings = page.get_drawings()
    page_area = page.rect.width * page.rect.height

    shapes: list[Shape] = []
    edges: list[Edge] = []

    for drawing in drawings:
        items = drawing.get("items", [])
        fill_color = rgb_float_to_int(drawing.get("fill"))
        stroke_color = rgb_float_to_int(drawing.get("color"))
        stroke_width = drawing.get("width", 1.0) or 1.0

        # Collect all primitives in this drawing path
        rects: list[fitz.Rect] = []
        lines: list[tuple[Point, Point]] = []
        curves: list[list[Point]] = []
        quads: list[fitz.Quad] = []

        for item in items:
            kind = item[0]

            if kind == "re":
                # Rectangle: item[1] is a fitz.Rect
                rects.append(fitz.Rect(item[1]))

            elif kind == "l":
                # Line: item[1] and item[2] are fitz.Point
                p1 = Point(item[1].x, item[1].y)
                p2 = Point(item[2].x, item[2].y)
                lines.append((p1, p2))

            elif kind == "c":
                # Cubic Bézier curve: item[1..4] are control points
                curve_pts = [Point(item[i].x, item[i].y) for i in range(1, 5)]
                curves.append(curve_pts)

            elif kind == "qu":
                # Quad: item[1] is a fitz.Quad
                quads.append(fitz.Quad(item[1]))

        # --- Process rectangles → Shapes ---
        for rect in rects:
            area = rect.width * rect.height
            if area < min_shape_area:
                continue
            if area > page_area * max_shape_page_ratio:
                continue

            shape = Shape(
                shape_type="rectangle",
                bbox=BoundingBox(rect.x0, rect.y0, rect.x1, rect.y1),
                center=Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2),
                vertices=[
                    Point(rect.x0, rect.y0),
                    Point(rect.x1, rect.y0),
                    Point(rect.x1, rect.y1),
                    Point(rect.x0, rect.y1),
                ],
                area=area,
                fill_color=fill_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
            )
            shapes.append(shape)

        # --- Process quads → Shapes ---
        for quad in quads:
            vertices = [
                Point(quad.ul.x, quad.ul.y),
                Point(quad.ur.x, quad.ur.y),
                Point(quad.lr.x, quad.lr.y),
                Point(quad.ll.x, quad.ll.y),
            ]
            bbox = BoundingBox(
                x0=min(v.x for v in vertices),
                y0=min(v.y for v in vertices),
                x1=max(v.x for v in vertices),
                y1=max(v.y for v in vertices),
            )
            area = bbox.area
            if area < min_shape_area or area > page_area * max_shape_page_ratio:
                continue

            shape_type = classify_polygon(vertices)
            shape = Shape(
                shape_type=shape_type,
                bbox=bbox,
                center=bbox.center,
                vertices=vertices,
                area=area,
                fill_color=fill_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
            )
            shapes.append(shape)

        # --- Process lines → Edges ---
        for p1, p2 in lines:
            length = math.hypot(p2.x - p1.x, p2.y - p1.y)
            if length < min_line_length:
                continue

            edge = Edge(
                edge_type="line",
                start_point=p1,
                end_point=p2,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
            )
            edges.append(edge)

        # --- Process curves ---
        # First, check if the curves form a closed shape (circle/ellipse).
        # PyMuPDF's draw_circle/draw_oval generates multiple Bézier curves
        # whose endpoints chain together into a closed path.
        curves_formed_shape = False
        if curves and not rects and not quads and len(lines) == 0:
            closed_curve_shape = _try_build_closed_curve_shape(
                curves, fill_color, stroke_color, stroke_width,
                min_shape_area, page_area * max_shape_page_ratio,
            )
            if closed_curve_shape is not None:
                shapes.append(closed_curve_shape)
                curves_formed_shape = True

        # Remaining curves that didn't form a shape → Edges
        if not curves_formed_shape:
            for curve_pts in curves:
                if len(curve_pts) < 2:
                    continue

                start = curve_pts[0]
                end = curve_pts[-1]
                length = math.hypot(end.x - start.x, end.y - start.y)
                if length < min_line_length:
                    continue

                edge = Edge(
                    edge_type="curve",
                    start_point=start,
                    end_point=end,
                    waypoints=curve_pts[1:-1],
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                )
                edges.append(edge)

        # --- Handle closed multi-segment paths as shapes ---
        # If the drawing has no rects/quads but has multiple lines forming
        # a closed path, treat it as a polygon shape.
        if not rects and not quads and not curves_formed_shape and len(lines) >= 3:
            closed_shape = _try_build_closed_polygon(
                lines, fill_color, stroke_color, stroke_width,
                min_shape_area, page_area * max_shape_page_ratio,
            )
            if closed_shape is not None:
                shapes.append(closed_shape)
                # Remove the constituent lines from edges
                # (they're part of the shape outline, not connections)
                edges = [
                    e for e in edges
                    if not _line_in_polygon(e, closed_shape)
                ]

    return shapes, edges


def _try_build_closed_curve_shape(
    curves: list[list[Point]],
    fill_color: tuple[int, int, int] | None,
    stroke_color: tuple[int, int, int] | None,
    stroke_width: float,
    min_area: float,
    max_area: float,
    closure_tolerance: float = 3.0,
) -> Shape | None:
    """Detect if multiple Bézier curves form a closed shape (circle/ellipse).

    PyMuPDF's draw_circle() / draw_oval() produces 4 cubic Bézier curves
    whose endpoints chain together to form a closed loop. This function
    detects that pattern and creates a circle or ellipse Shape.
    """
    if len(curves) < 2:
        return None

    # Collect all curve control points for the bounding box
    all_points: list[Point] = []
    for curve in curves:
        all_points.extend(curve)

    if not all_points:
        return None

    # Check if the curve chain is closed: last curve's end ≈ first curve's start
    first_start = curves[0][0]
    last_end = curves[-1][-1]
    closure_dist = math.hypot(first_start.x - last_end.x, first_start.y - last_end.y)

    # Also check chaining: each curve's start ≈ previous curve's end
    is_chained = True
    for i in range(1, len(curves)):
        prev_end = curves[i - 1][-1]
        curr_start = curves[i][0]
        gap = math.hypot(prev_end.x - curr_start.x, prev_end.y - curr_start.y)
        if gap > closure_tolerance:
            is_chained = False
            break

    if not is_chained or closure_dist > closure_tolerance:
        return None

    # Compute bounding box from all control points
    xs = [p.x for p in all_points]
    ys = [p.y for p in all_points]
    bbox = BoundingBox(min(xs), min(ys), max(xs), max(ys))
    area = bbox.area

    if area < min_area or area > max_area:
        return None

    # Classify as circle vs ellipse based on aspect ratio
    aspect = bbox.width / bbox.height if bbox.height > 0 else 1.0
    if 0.8 < aspect < 1.25:
        shape_type = "circle"
    else:
        shape_type = "ellipse"

    return Shape(
        shape_type=shape_type,
        bbox=bbox,
        center=bbox.center,
        vertices=[],  # Circles don't have discrete vertices
        area=area,
        fill_color=fill_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
    )


def _try_build_closed_polygon(
    lines: list[tuple[Point, Point]],
    fill_color: tuple[int, int, int] | None,
    stroke_color: tuple[int, int, int] | None,
    stroke_width: float,
    min_area: float,
    max_area: float,
    closure_tolerance: float = 3.0,
) -> Shape | None:
    """Attempt to build a closed polygon shape from a sequence of lines.

    Lines are chained end-to-start; if the chain closes back to the
    first point (within tolerance), a polygon Shape is returned.
    """
    if len(lines) < 3:
        return None

    # Try to chain lines into a sequence
    chain: list[Point] = [lines[0][0], lines[0][1]]
    used = {0}
    remaining = set(range(1, len(lines)))

    for _ in range(len(lines) - 1):
        current_end = chain[-1]
        found = False
        for idx in list(remaining):
            p1, p2 = lines[idx]
            # Forward match
            dist_fwd = math.hypot(p1.x - current_end.x, p1.y - current_end.y)
            if dist_fwd < closure_tolerance:
                chain.append(p2)
                used.add(idx)
                remaining.discard(idx)
                found = True
                break
            # Reverse match
            dist_rev = math.hypot(p2.x - current_end.x, p2.y - current_end.y)
            if dist_rev < closure_tolerance:
                chain.append(p1)
                used.add(idx)
                remaining.discard(idx)
                found = True
                break
        if not found:
            break

    # Check closure
    if len(chain) < 4:  # Need at least 3 distinct vertices + closure
        return None
    start, end = chain[0], chain[-1]
    if math.hypot(start.x - end.x, start.y - end.y) > closure_tolerance:
        return None

    # Remove duplicate closure point
    vertices = chain[:-1]

    # Compute bounding box and area
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    bbox = BoundingBox(min(xs), min(ys), max(xs), max(ys))
    area = bbox.area  # Approximate with bbox area

    if area < min_area or area > max_area:
        return None

    shape_type = classify_polygon(vertices)

    return Shape(
        shape_type=shape_type,
        bbox=bbox,
        center=bbox.center,
        vertices=vertices,
        area=area,
        fill_color=fill_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
    )


def _line_in_polygon(edge: Edge, shape: Shape) -> bool:
    """Check if an edge's start and end are both vertices of a shape."""
    if not shape.vertices:
        return False
    tolerance = 3.0
    start_match = any(
        math.hypot(edge.start_point.x - v.x, edge.start_point.y - v.y) < tolerance
        for v in shape.vertices
    )
    end_match = any(
        math.hypot(edge.end_point.x - v.x, edge.end_point.y - v.y) < tolerance
        for v in shape.vertices
    )
    return start_match and end_match


def count_vector_primitives(page: fitz.Page) -> int:
    """Count the total number of vector drawing primitives on a page.

    Used by the orchestrator to decide whether to use vector or raster extraction.
    """
    drawings = page.get_drawings()
    count = 0
    for drawing in drawings:
        count += len(drawing.get("items", []))
    return count
