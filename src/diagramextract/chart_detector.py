"""Chart detector — identifies bar, pie, line, and scatter charts.

Uses purely geometric heuristics (no ML) to detect common chart patterns
from the shapes and edges already extracted. When a chart is detected,
its constituent shapes are wrapped in a ChartElement and removed from
the generic shapes list of the diagram.
"""

from __future__ import annotations

from .models import BoundingBox, ChartElement, DataPoint, Diagram, Shape
from .utils import (
    are_aligned_horizontally,
    are_evenly_spaced,
    bbox_contains_bbox,
    have_similar_widths,
    merge_bboxes,
)


# Minimum number of shapes to consider a pattern as a chart
MIN_BAR_COUNT = 3
MIN_PIE_LINES = 2
MIN_LINE_POINTS = 3
MIN_SCATTER_DOTS = 5

# Bar chart: rectangles should have height variance above this ratio
BAR_HEIGHT_VARIANCE_RATIO = 0.1


def detect_charts(diagram: Diagram) -> Diagram:
    """Scan a diagram for chart patterns and extract them.

    Modifies the diagram in-place: detected chart shapes are removed
    from diagram.shapes and wrapped in ChartElement objects added
    to diagram.charts.

    Args:
        diagram: A Diagram object to analyze.

    Returns:
        The same Diagram object, with charts populated.
    """
    # Try each chart detector in order of specificity
    # (pie is most specific, scatter is most general)
    diagram = _detect_pie_charts(diagram)
    diagram = _detect_bar_charts(diagram)
    diagram = _detect_line_charts(diagram)
    diagram = _detect_scatter_plots(diagram)

    return diagram


def _detect_bar_charts(diagram: Diagram) -> Diagram:
    """Detect bar chart patterns: multiple rectangles of similar width,
    aligned along one axis, with varying heights.
    """
    rects = [s for s in diagram.shapes if s.shape_type == "rectangle"]
    if len(rects) < MIN_BAR_COUNT:
        return diagram

    # Try to find groups of rectangles that form bars
    # Sort by x-position (vertical bars) or y-position (horizontal bars)
    bar_groups = _find_bar_groups(rects)

    for group in bar_groups:
        if len(group) < MIN_BAR_COUNT:
            continue

        bboxes = [s.bbox for s in group]
        overall_bbox = merge_bboxes(bboxes)

        # Create data points from bars
        # Sort by x (vertical bars) or y (horizontal bars)
        is_vertical = _is_vertical_bar_group(group)
        if is_vertical:
            sorted_bars = sorted(group, key=lambda s: s.bbox.x0)
        else:
            sorted_bars = sorted(group, key=lambda s: s.bbox.y0)

        data_points = []
        for i, bar in enumerate(sorted_bars):
            value = bar.bbox.height if is_vertical else bar.bbox.width
            data_points.append(DataPoint(
                index=i,
                value=value,
                bbox=bar.bbox,
                color=bar.fill_color,
            ))

        chart = ChartElement(
            chart_type="bar_chart",
            bbox=overall_bbox,
            data_points=data_points,
        )
        diagram.charts.append(chart)

        # Remove bar shapes from the generic shapes list
        bar_ids = {s.id for s in group}
        diagram.shapes = [s for s in diagram.shapes if s.id not in bar_ids]

    return diagram


def _find_bar_groups(rects: list[Shape]) -> list[list[Shape]]:
    """Find groups of rectangles that form bar chart patterns.

    Bars in a bar chart typically:
    - Have similar widths
    - Are aligned along one edge (bottom or left)
    - Have varying heights/widths
    """
    groups: list[list[Shape]] = []

    # Try vertical bars: similar widths, aligned at bottom
    # Group by bottom-edge y-coordinate
    bottom_groups: dict[int, list[Shape]] = {}
    for rect in rects:
        # Quantize bottom y to group nearby bars
        bottom_key = round(rect.bbox.y1 / 10) * 10
        bottom_groups.setdefault(bottom_key, []).append(rect)

    for key, group in bottom_groups.items():
        if len(group) < MIN_BAR_COUNT:
            continue

        bboxes = [s.bbox for s in group]
        if have_similar_widths(bboxes, tolerance_ratio=0.4):
            # Check height variance
            heights = [b.height for b in bboxes]
            if len(heights) > 0:
                mean_h = sum(heights) / len(heights)
                if mean_h > 0:
                    variance_ratio = (max(heights) - min(heights)) / mean_h
                    if variance_ratio > BAR_HEIGHT_VARIANCE_RATIO:
                        groups.append(group)

    # Try horizontal bars: similar heights, aligned at left
    left_groups: dict[int, list[Shape]] = {}
    for rect in rects:
        left_key = round(rect.bbox.x0 / 10) * 10
        left_groups.setdefault(left_key, []).append(rect)

    for key, group in left_groups.items():
        if len(group) < MIN_BAR_COUNT:
            continue

        bboxes = [s.bbox for s in group]
        heights = [b.height for b in bboxes]
        mean_h = sum(heights) / len(heights) if heights else 0
        if mean_h > 0:
            # Similar heights for horizontal bars
            similar_heights = all(
                abs(h - mean_h) / mean_h < 0.4 for h in heights
            )
            if similar_heights:
                widths = [b.width for b in bboxes]
                mean_w = sum(widths) / len(widths)
                if mean_w > 0:
                    variance_ratio = (max(widths) - min(widths)) / mean_w
                    if variance_ratio > BAR_HEIGHT_VARIANCE_RATIO:
                        # Make sure this group doesn't overlap with
                        # already-detected vertical bar groups
                        group_ids = {s.id for s in group}
                        already_used = any(
                            s.id in group_ids
                            for g in groups
                            for s in g
                        )
                        if not already_used:
                            groups.append(group)

    return groups


def _is_vertical_bar_group(group: list[Shape]) -> bool:
    """Determine if a bar group is vertical (bars stand up) or horizontal."""
    # Vertical bars: wider spread in X than Y
    xs = [s.bbox.center.x for s in group]
    ys = [s.bbox.center.y for s in group]
    x_range = max(xs) - min(xs) if xs else 0
    y_range = max(ys) - min(ys) if ys else 0
    return x_range >= y_range


def _detect_pie_charts(diagram: Diagram) -> Diagram:
    """Detect pie chart patterns: a large circle/ellipse containing
    radial line segments or colored wedge-like sectors.
    """
    circles = [
        s for s in diagram.shapes
        if s.shape_type in ("circle", "ellipse") and s.area > 500
    ]

    for circle in circles:
        # Look for edges (radial lines) whose endpoints are inside the circle
        radial_edges = []
        for edge in diagram.edges:
            start_in = _point_in_circle(edge.start_point, circle)
            end_in = _point_in_circle(edge.end_point, circle)
            if start_in or end_in:
                radial_edges.append(edge)

        # Look for small shapes (wedge-like sectors) inside the circle
        inner_shapes = [
            s for s in diagram.shapes
            if s.id != circle.id and bbox_contains_bbox(circle.bbox, s.bbox)
        ]

        if len(radial_edges) >= MIN_PIE_LINES or len(inner_shapes) >= 2:
            # It's a pie chart
            data_points = []
            for i, edge in enumerate(radial_edges):
                data_points.append(DataPoint(
                    index=i,
                    value=0,  # Can't determine value without labels
                    bbox=BoundingBox(
                        min(edge.start_point.x, edge.end_point.x),
                        min(edge.start_point.y, edge.end_point.y),
                        max(edge.start_point.x, edge.end_point.x),
                        max(edge.start_point.y, edge.end_point.y),
                    ),
                ))

            chart = ChartElement(
                chart_type="pie_chart",
                bbox=circle.bbox,
                data_points=data_points,
            )
            diagram.charts.append(chart)

            # Remove pie chart elements from shapes
            remove_ids = {circle.id} | {s.id for s in inner_shapes}
            diagram.shapes = [s for s in diagram.shapes if s.id not in remove_ids]

            # Remove radial edges
            radial_ids = {e.id for e in radial_edges}
            diagram.edges = [e for e in diagram.edges if e.id not in radial_ids]

    return diagram


def _point_in_circle(point, circle_shape: Shape) -> bool:
    """Approximate check: is a point inside a circular shape?"""
    cx = circle_shape.center.x
    cy = circle_shape.center.y
    rx = circle_shape.bbox.width / 2
    ry = circle_shape.bbox.height / 2

    if rx <= 0 or ry <= 0:
        return False

    # Ellipse equation: ((x-cx)/rx)^2 + ((y-cy)/ry)^2 <= 1
    dx = (point.x - cx) / rx
    dy = (point.y - cy) / ry
    return (dx * dx + dy * dy) <= 1.2  # Slight tolerance


def _detect_line_charts(diagram: Diagram) -> Diagram:
    """Detect line chart patterns: connected polyline/curve with
    regularly spaced X coordinates.
    """
    # Look for sequences of small circles/dots connected by edges
    dots = [
        s for s in diagram.shapes
        if s.shape_type in ("circle", "ellipse") and s.area < 300
    ]

    if len(dots) < MIN_LINE_POINTS:
        return diagram

    # Check if dots are roughly evenly spaced in X
    dot_centers_x = sorted([d.center.x for d in dots])
    if not are_evenly_spaced(dot_centers_x, tolerance_ratio=0.5):
        return diagram

    # Check if there are edges connecting consecutive dots
    connected_dots = set()
    connecting_edges = []
    for edge in diagram.edges:
        src = edge.source_shape_id
        tgt = edge.target_shape_id
        dot_ids = {d.id for d in dots}
        if src in dot_ids or tgt in dot_ids:
            connected_dots.add(src)
            connected_dots.add(tgt)
            connecting_edges.append(edge)

    # Need at least some connections to confirm it's a line chart
    if len(connecting_edges) >= MIN_LINE_POINTS - 1:
        sorted_dots = sorted(dots, key=lambda d: d.center.x)
        data_points = []
        for i, dot in enumerate(sorted_dots):
            data_points.append(DataPoint(
                index=i,
                value=dot.center.y,  # Y position as proxy for value
                bbox=dot.bbox,
                color=dot.fill_color,
            ))

        overall_bbox = merge_bboxes([d.bbox for d in dots])
        chart = ChartElement(
            chart_type="line_chart",
            bbox=overall_bbox,
            data_points=data_points,
        )
        diagram.charts.append(chart)

        # Remove chart elements
        dot_ids = {d.id for d in dots}
        diagram.shapes = [s for s in diagram.shapes if s.id not in dot_ids]
        edge_ids = {e.id for e in connecting_edges}
        diagram.edges = [e for e in diagram.edges if e.id not in edge_ids]

    return diagram


def _detect_scatter_plots(diagram: Diagram) -> Diagram:
    """Detect scatter plot patterns: cluster of small circles/dots
    with no connecting edges between them.
    """
    dots = [
        s for s in diagram.shapes
        if s.shape_type in ("circle", "ellipse") and s.area < 200
    ]

    if len(dots) < MIN_SCATTER_DOTS:
        return diagram

    # Scatter plots: dots without edges connecting them
    dot_ids = {d.id for d in dots}
    connected_dot_edges = [
        e for e in diagram.edges
        if e.source_shape_id in dot_ids and e.target_shape_id in dot_ids
    ]

    # If very few connections relative to dot count, it's a scatter plot
    if len(connected_dot_edges) <= len(dots) * 0.3:
        data_points = []
        for i, dot in enumerate(sorted(dots, key=lambda d: d.center.x)):
            data_points.append(DataPoint(
                index=i,
                value=dot.center.y,
                bbox=dot.bbox,
                color=dot.fill_color,
            ))

        overall_bbox = merge_bboxes([d.bbox for d in dots])
        chart = ChartElement(
            chart_type="scatter_plot",
            bbox=overall_bbox,
            data_points=data_points,
        )
        diagram.charts.append(chart)

        diagram.shapes = [s for s in diagram.shapes if s.id not in dot_ids]

    return diagram
