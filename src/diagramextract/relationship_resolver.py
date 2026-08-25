"""Relationship resolver — links edges to shapes and groups connected components.

For each edge, determines which shapes (if any) it connects based on
spatial proximity of its endpoints to shape bounding boxes.
Connected shapes and edges are then grouped into separate Diagram instances.
"""

from __future__ import annotations

from .models import BoundingBox, Diagram, Edge, Point, Shape
from .utils import point_to_bbox_distance


# Maximum distance (in PDF points) from an edge endpoint to a shape
# boundary for them to be considered connected.
CONNECTION_TOLERANCE = 15.0


def resolve_relationships(
    shapes: list[Shape],
    edges: list[Edge],
    connection_tolerance: float = CONNECTION_TOLERANCE,
) -> list[Diagram]:
    """Link edges to shapes and group into connected-component Diagrams.

    Args:
        shapes: Classified shapes on the page.
        edges: Detected edges on the page.
        connection_tolerance: Max distance for an edge endpoint to
            "connect" to a shape.

    Returns:
        List of Diagram objects, each containing a connected component
        of shapes and edges.
    """
    # Step 1: For each edge, find the nearest source and target shapes
    _link_edges_to_shapes(shapes, edges, connection_tolerance)

    # Step 2: Build adjacency and group into connected components
    diagrams = _group_into_diagrams(shapes, edges)

    # Step 3: Classify diagram types
    for diagram in diagrams:
        diagram.diagram_type = _classify_diagram_type(diagram)

    return diagrams


def _link_edges_to_shapes(
    shapes: list[Shape],
    edges: list[Edge],
    tolerance: float,
) -> None:
    """For each edge, set source_shape_id and target_shape_id.

    Mutates the Edge objects in place.
    """
    for edge in edges:
        # Find nearest shape to start point
        best_start_dist = float("inf")
        best_start_id: str | None = None

        best_end_dist = float("inf")
        best_end_id: str | None = None

        for shape in shapes:
            start_dist = point_to_bbox_distance(edge.start_point, shape.bbox)
            if start_dist < best_start_dist:
                best_start_dist = start_dist
                best_start_id = shape.id

            end_dist = point_to_bbox_distance(edge.end_point, shape.bbox)
            if end_dist < best_end_dist:
                best_end_dist = end_dist
                best_end_id = shape.id

        # Only link if within tolerance
        if best_start_dist <= tolerance:
            edge.source_shape_id = best_start_id
        if best_end_dist <= tolerance:
            edge.target_shape_id = best_end_id

        # Don't link an edge to the same shape at both ends
        if edge.source_shape_id == edge.target_shape_id:
            if best_start_dist < best_end_dist:
                edge.target_shape_id = None
            else:
                edge.source_shape_id = None


def _group_into_diagrams(
    shapes: list[Shape],
    edges: list[Edge],
) -> list[Diagram]:
    """Group shapes and edges into connected-component Diagrams using union-find."""
    # Build a union-find over shape IDs
    all_shape_ids = {s.id for s in shapes}
    parent: dict[str, str] = {sid: sid for sid in all_shape_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Union shapes connected by edges
    for edge in edges:
        if edge.source_shape_id and edge.target_shape_id:
            if edge.source_shape_id in all_shape_ids and edge.target_shape_id in all_shape_ids:
                union(edge.source_shape_id, edge.target_shape_id)

    # Group shapes by their root
    shape_map = {s.id: s for s in shapes}
    groups: dict[str, list[str]] = {}
    for sid in all_shape_ids:
        root = find(sid)
        groups.setdefault(root, []).append(sid)

    # Build diagrams from groups
    diagrams: list[Diagram] = []

    for root, member_ids in groups.items():
        member_set = set(member_ids)
        group_shapes = [shape_map[sid] for sid in member_ids]

        # Edges that connect shapes within this group
        group_edges = [
            e for e in edges
            if (e.source_shape_id in member_set or e.target_shape_id in member_set)
        ]

        diagram = Diagram(
            shapes=group_shapes,
            edges=group_edges,
        )
        diagrams.append(diagram)

    # Handle orphan edges (not connected to any shape)
    connected_edge_ids = {e.id for d in diagrams for e in d.edges}
    orphan_edges = [e for e in edges if e.id not in connected_edge_ids]

    if orphan_edges:
        # Group orphan edges into a separate diagram
        diagrams.append(Diagram(edges=orphan_edges))

    # Filter out empty diagrams (shouldn't happen, but defensive)
    diagrams = [d for d in diagrams if d.shapes or d.edges]

    return diagrams


def _classify_diagram_type(diagram: Diagram) -> str:
    """Heuristic classification of a diagram's type based on its structure.

    Returns one of: "flowchart", "network", "org_chart", "chart", "generic".
    """
    n_shapes = len(diagram.shapes)
    n_edges = len(diagram.edges)

    if n_shapes == 0 and n_edges == 0:
        return "generic"

    # Charts are identified separately by chart_detector
    if diagram.charts:
        return "chart"

    # Count shape types
    type_counts: dict[str, int] = {}
    for shape in diagram.shapes:
        type_counts[shape.shape_type] = type_counts.get(shape.shape_type, 0) + 1

    n_rects = type_counts.get("rectangle", 0)
    n_diamonds = type_counts.get("diamond", 0)
    n_circles = type_counts.get("circle", 0) + type_counts.get("ellipse", 0)
    has_arrows = any(e.has_arrowhead for e in diagram.edges)

    # Flowchart: has diamonds (decision nodes) and arrows
    if n_diamonds >= 1 and has_arrows:
        return "flowchart"

    # Flowchart: mostly rectangles with directed edges
    if n_rects >= 3 and has_arrows and n_edges >= n_shapes - 1:
        return "flowchart"

    # Network: circles/ellipses with many interconnections
    if n_circles >= 3 and n_edges >= n_shapes:
        return "network"

    # Org chart: tree-like structure (rectangles, edges ≈ shapes - 1, no arrows)
    if n_rects >= 3 and n_edges >= n_shapes - 2 and not has_arrows:
        return "org_chart"

    # Generic fallback
    if n_shapes >= 2 and n_edges >= 1:
        return "flowchart" if has_arrows else "generic"

    return "generic"
