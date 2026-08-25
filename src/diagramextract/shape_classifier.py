"""Shape classifier — post-processes raw shapes from extractors.

Handles deduplication of overlapping shapes, refinement of shape types,
noise filtering, and arrow detection from edge-like shapes.
"""

from __future__ import annotations

import math

from .models import BoundingBox, Edge, Point, Shape
from .utils import bbox_iou, point_distance


# IoU threshold above which two shapes are considered duplicates
DEDUP_IOU_THRESHOLD = 0.6

# Aspect ratio bounds: shapes outside this range are filtered
MIN_ASPECT_RATIO = 0.05
MAX_ASPECT_RATIO = 20.0

# Arrow detection: maximum width-to-height ratio for an elongated shape
# to be classified as an arrowhead
ARROW_MAX_ASPECT = 3.0
ARROW_MIN_VERTICES = 5
ARROW_MAX_VERTICES = 9


def classify_and_clean(
    shapes: list[Shape],
    edges: list[Edge],
) -> tuple[list[Shape], list[Edge]]:
    """Classify shapes, deduplicate, filter noise, and detect arrows.

    This is the central post-processing step after raw extraction.

    Args:
        shapes: Raw shapes from vector or raster extractor.
        edges: Raw edges from vector or raster extractor.

    Returns:
        Cleaned (shapes, edges) lists.
    """
    # Step 1: Filter noise
    shapes = _filter_noise(shapes)

    # Step 2: Deduplicate overlapping shapes
    shapes = _deduplicate_shapes(shapes)

    # Step 3: Refine shape types
    shapes = _refine_types(shapes)

    # Step 4: Detect arrowhead shapes and convert them to edge arrows
    shapes, new_arrow_edges = _detect_arrowhead_shapes(shapes, edges)
    edges = edges + new_arrow_edges

    # Step 5: Detect arrow-like line endpoints (simple heuristic for vector edges)
    edges = _detect_arrow_directions(edges, shapes)

    return shapes, edges


def _filter_noise(shapes: list[Shape]) -> list[Shape]:
    """Remove shapes that are too small, too narrow, or degenerate."""
    cleaned = []
    for shape in shapes:
        # Skip degenerate shapes
        if shape.bbox.width <= 0 or shape.bbox.height <= 0:
            continue

        aspect = shape.bbox.aspect_ratio
        if aspect < MIN_ASPECT_RATIO or aspect > MAX_ASPECT_RATIO:
            continue

        # Skip very tiny shapes (likely artifacts)
        if shape.area < 20:
            continue

        cleaned.append(shape)

    return cleaned


def _deduplicate_shapes(shapes: list[Shape]) -> list[Shape]:
    """Remove duplicate shapes that overlap significantly.

    When two shapes have IoU above the threshold, keep the one with
    more defined geometry (more vertices, or filled).
    """
    if len(shapes) < 2:
        return shapes

    # Sort by area descending — larger shapes are more likely to be "real"
    sorted_shapes = sorted(shapes, key=lambda s: s.area, reverse=True)
    keep: list[Shape] = []
    removed_indices: set[int] = set()

    for i, shape_a in enumerate(sorted_shapes):
        if i in removed_indices:
            continue

        for j in range(i + 1, len(sorted_shapes)):
            if j in removed_indices:
                continue

            shape_b = sorted_shapes[j]
            iou = bbox_iou(shape_a.bbox, shape_b.bbox)

            if iou > DEDUP_IOU_THRESHOLD:
                # Keep the shape with more info (filled > unfilled, more vertices)
                score_a = _shape_quality_score(shape_a)
                score_b = _shape_quality_score(shape_b)
                if score_b > score_a:
                    removed_indices.add(i)
                    break
                else:
                    removed_indices.add(j)

        if i not in removed_indices:
            keep.append(shape_a)

    return keep


def _shape_quality_score(shape: Shape) -> float:
    """Score a shape's "quality" for deduplication preference."""
    score = 0.0
    if shape.fill_color is not None:
        score += 2.0
    if shape.stroke_color is not None:
        score += 1.0
    if shape.shape_type != "unknown":
        score += 1.0
    score += len(shape.vertices) * 0.1
    return score


def _refine_types(shapes: list[Shape]) -> list[Shape]:
    """Apply additional heuristics to refine shape classification."""
    for shape in shapes:
        if shape.shape_type == "rectangle":
            # Very square rectangles with small area might be checkboxes/dots
            aspect = shape.bbox.aspect_ratio
            if 0.9 < aspect < 1.1 and shape.area < 100:
                shape.shape_type = "circle"  # Likely a small dot

        elif shape.shape_type == "polygon":
            # Re-check circularity for polygons with many vertices
            if len(shape.vertices) >= 6:
                # Compute a rough circularity from bbox
                aspect = shape.bbox.aspect_ratio
                if 0.8 < aspect < 1.25:
                    shape.shape_type = "ellipse"

    return shapes


def _detect_arrowhead_shapes(
    shapes: list[Shape], edges: list[Edge]
) -> tuple[list[Shape], list[Edge]]:
    """Detect small triangular shapes that are arrowheads.

    Small triangles near the endpoint of an edge are likely arrowheads.
    These are removed from shapes and instead mark the nearest edge
    as having an arrowhead.
    """
    new_edges: list[Edge] = []
    arrowhead_ids: set[str] = set()

    triangles = [s for s in shapes if s.shape_type == "triangle" and s.area < 500]

    for tri in triangles:
        # Check if this triangle is near the endpoint of any edge
        tri_center = tri.center
        best_edge: Edge | None = None
        best_dist = float("inf")
        at_end = True  # Whether the triangle is at the end (vs start) of the edge

        for edge in edges:
            dist_to_end = point_distance(tri_center, edge.end_point)
            dist_to_start = point_distance(tri_center, edge.start_point)

            if dist_to_end < best_dist:
                best_dist = dist_to_end
                best_edge = edge
                at_end = True
            if dist_to_start < best_dist:
                best_dist = dist_to_start
                best_edge = edge
                at_end = False

        # If close enough, mark this triangle as an arrowhead
        if best_edge is not None and best_dist < 20:
            best_edge.has_arrowhead = True
            best_edge.edge_type = "arrow"
            if at_end:
                best_edge.direction = "forward"
            else:
                best_edge.direction = "backward"
            arrowhead_ids.add(tri.id)

    # Remove arrowhead shapes from the shapes list
    shapes = [s for s in shapes if s.id not in arrowhead_ids]

    return shapes, new_edges


def _detect_arrow_directions(
    edges: list[Edge], shapes: list[Shape]
) -> list[Edge]:
    """Heuristic: if an edge endpoint is near a shape boundary but not
    the other endpoint, it likely points toward that shape.

    For vector PDFs, arrows are often drawn as lines with a small
    filled triangle at one end. This has already been handled above.
    This function adds a fallback direction based on shape proximity.
    """
    for edge in edges:
        if edge.has_arrowhead:
            continue  # Already resolved

        # Check if one end touches a shape and the other doesn't
        start_near_shape = False
        end_near_shape = False

        for shape in shapes:
            if _point_near_bbox(edge.start_point, shape.bbox, tolerance=5):
                start_near_shape = True
            if _point_near_bbox(edge.end_point, shape.bbox, tolerance=5):
                end_near_shape = True

        # If both ends touch shapes, it's a connector (no arrow direction inferred)
        # If neither touches, leave as is
        # These heuristics are conservative — we don't want false positives

    return edges


def _point_near_bbox(point: Point, bbox: BoundingBox, tolerance: float) -> bool:
    """Check if a point is within tolerance of a bbox boundary."""
    dx = max(bbox.x0 - point.x, 0, point.x - bbox.x1)
    dy = max(bbox.y0 - point.y, 0, point.y - bbox.y1)
    return math.hypot(dx, dy) <= tolerance
