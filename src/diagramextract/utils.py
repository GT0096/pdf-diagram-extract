"""Geometry utility functions used throughout the package.

All functions operate on the model types (Point, BoundingBox) or
raw coordinate tuples. No external dependencies beyond math/numpy.
"""

from __future__ import annotations

import math

import numpy as np

from .models import BoundingBox, Point


# ---------------------------------------------------------------------------
# Distance functions
# ---------------------------------------------------------------------------

def point_distance(p1: Point, p2: Point) -> float:
    """Euclidean distance between two points."""
    return math.hypot(p2.x - p1.x, p2.y - p1.y)


def point_to_bbox_distance(point: Point, bbox: BoundingBox) -> float:
    """Shortest distance from a point to the boundary of a bounding box.

    Returns 0 if the point is inside the bbox.
    """
    dx = max(bbox.x0 - point.x, 0, point.x - bbox.x1)
    dy = max(bbox.y0 - point.y, 0, point.y - bbox.y1)
    return math.hypot(dx, dy)


def point_to_segment_distance(
    point: Point, seg_start: Point, seg_end: Point
) -> float:
    """Shortest distance from a point to a line segment."""
    px, py = point.x, point.y
    ax, ay = seg_start.x, seg_start.y
    bx, by = seg_end.x, seg_end.y

    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay

    ab_sq = abx * abx + aby * aby
    if ab_sq == 0:
        return math.hypot(apx, apy)

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_sq))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)


# ---------------------------------------------------------------------------
# Bounding box operations
# ---------------------------------------------------------------------------

def bbox_iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection-over-union of two bounding boxes. Returns 0-1."""
    inter_x0 = max(a.x0, b.x0)
    inter_y0 = max(a.y0, b.y0)
    inter_x1 = min(a.x1, b.x1)
    inter_y1 = min(a.y1, b.y1)

    inter_w = max(0, inter_x1 - inter_x0)
    inter_h = max(0, inter_y1 - inter_y0)
    inter_area = inter_w * inter_h

    union_area = a.area + b.area - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def bbox_contains_point(bbox: BoundingBox, point: Point) -> bool:
    """Check if a point lies inside (or on the boundary of) a bbox."""
    return bbox.x0 <= point.x <= bbox.x1 and bbox.y0 <= point.y <= bbox.y1


def bbox_contains_bbox(outer: BoundingBox, inner: BoundingBox) -> bool:
    """Check if `outer` fully contains `inner`."""
    return (
        outer.x0 <= inner.x0
        and outer.y0 <= inner.y0
        and outer.x1 >= inner.x1
        and outer.y1 >= inner.y1
    )


def merge_bboxes(boxes: list[BoundingBox]) -> BoundingBox:
    """Return the smallest bbox that encloses all given boxes."""
    if not boxes:
        return BoundingBox(0, 0, 0, 0)
    return BoundingBox(
        x0=min(b.x0 for b in boxes),
        y0=min(b.y0 for b in boxes),
        x1=max(b.x1 for b in boxes),
        y1=max(b.y1 for b in boxes),
    )


# ---------------------------------------------------------------------------
# Polygon / shape classification
# ---------------------------------------------------------------------------

def _angle_between_vectors(
    v1: tuple[float, float], v2: tuple[float, float]
) -> float:
    """Angle in degrees between two 2D vectors."""
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_angle))


def interior_angles(vertices: list[Point]) -> list[float]:
    """Compute the interior angle at each vertex of a polygon."""
    n = len(vertices)
    if n < 3:
        return []
    angles = []
    for i in range(n):
        p_prev = vertices[(i - 1) % n]
        p_curr = vertices[i]
        p_next = vertices[(i + 1) % n]
        v1 = (p_prev.x - p_curr.x, p_prev.y - p_curr.y)
        v2 = (p_next.x - p_curr.x, p_next.y - p_curr.y)
        angles.append(_angle_between_vectors(v1, v2))
    return angles


def classify_polygon(vertices: list[Point]) -> str:
    """Classify a polygon by its vertex count and angle pattern.

    Returns one of: "triangle", "rectangle", "diamond", "polygon", "unknown".
    """
    n = len(vertices)
    if n < 3:
        return "unknown"

    if n == 3:
        return "triangle"

    if n == 4:
        angles = interior_angles(vertices)
        # Rectangle: all angles near 90°
        if all(abs(a - 90) < 20 for a in angles):
            return "rectangle"
        # Diamond: check if the diagonals are axis-aligned
        # A diamond has alternating acute/obtuse angles
        acute = sum(1 for a in angles if a < 80)
        obtuse = sum(1 for a in angles if a > 100)
        if acute == 2 and obtuse == 2:
            return "diamond"
        return "rectangle"  # default quadrilateral → rectangle

    return "polygon"


def circularity(contour_area: float, contour_perimeter: float) -> float:
    """Compute circularity metric. Perfect circle = 1.0."""
    if contour_perimeter == 0:
        return 0.0
    return (4.0 * math.pi * contour_area) / (contour_perimeter * contour_perimeter)


# ---------------------------------------------------------------------------
# Alignment heuristics (for chart detection)
# ---------------------------------------------------------------------------

def are_aligned_horizontally(
    shapes: list[BoundingBox], tolerance: float = 10.0
) -> bool:
    """Check if shapes are roughly aligned along a horizontal line.

    Tests whether the vertical centers of all shapes are within `tolerance`
    of each other.
    """
    if len(shapes) < 2:
        return False
    centers_y = [b.center.y for b in shapes]
    return (max(centers_y) - min(centers_y)) < tolerance


def are_aligned_vertically(
    shapes: list[BoundingBox], tolerance: float = 10.0
) -> bool:
    """Check if shapes are roughly aligned along a vertical line."""
    if len(shapes) < 2:
        return False
    centers_x = [b.center.x for b in shapes]
    return (max(centers_x) - min(centers_x)) < tolerance


def have_similar_widths(
    bboxes: list[BoundingBox], tolerance_ratio: float = 0.3
) -> bool:
    """Check if all bboxes have similar widths (within tolerance_ratio of mean)."""
    if len(bboxes) < 2:
        return False
    widths = [b.width for b in bboxes]
    mean_w = sum(widths) / len(widths)
    if mean_w == 0:
        return False
    return all(abs(w - mean_w) / mean_w < tolerance_ratio for w in widths)


def are_evenly_spaced(
    centers: list[float], tolerance_ratio: float = 0.4
) -> bool:
    """Check if a sorted list of center coordinates are roughly evenly spaced."""
    if len(centers) < 3:
        return len(centers) >= 2
    sorted_c = sorted(centers)
    gaps = [sorted_c[i + 1] - sorted_c[i] for i in range(len(sorted_c) - 1)]
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap == 0:
        return False
    return all(abs(g - mean_gap) / mean_gap < tolerance_ratio for g in gaps)


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def rgb_float_to_int(
    color: tuple[float, ...] | list[float] | None,
) -> tuple[int, int, int] | None:
    """Convert PyMuPDF's 0.0-1.0 RGB tuple to 0-255 int tuple."""
    if color is None or len(color) < 3:
        return None
    return (
        int(round(color[0] * 255)),
        int(round(color[1] * 255)),
        int(round(color[2] * 255)),
    )


# ---------------------------------------------------------------------------
# Coordinate scaling
# ---------------------------------------------------------------------------

def scale_point(point: Point, scale_x: float, scale_y: float) -> Point:
    """Scale a point by the given factors."""
    return Point(point.x * scale_x, point.y * scale_y)


def scale_bbox(bbox: BoundingBox, scale_x: float, scale_y: float) -> BoundingBox:
    """Scale a bounding box by the given factors."""
    return BoundingBox(
        x0=bbox.x0 * scale_x,
        y0=bbox.y0 * scale_y,
        x1=bbox.x1 * scale_x,
        y1=bbox.y1 * scale_y,
    )


def pixel_to_pdf_coords(
    x: float, y: float, page_width: float, page_height: float,
    img_width: int, img_height: int,
) -> tuple[float, float]:
    """Convert pixel coordinates (from rendered image) to PDF point coordinates."""
    pdf_x = (x / img_width) * page_width
    pdf_y = (y / img_height) * page_height
    return pdf_x, pdf_y
