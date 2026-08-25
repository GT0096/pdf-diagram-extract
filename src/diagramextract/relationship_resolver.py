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
    tolerance: float = CONNECTION_TOLERANCE,
) -> list[Diagram]:
    """Group shapes and edges into connected-component Diagrams using union-find."""
    # Build a union-find over both shape IDs and edge IDs
    parent: dict[str, str] = {s.id: s.id for s in shapes}
    parent.update({e.id: e.id for e in edges})

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 1. Union edges to their connected shapes
    for edge in edges:
        if edge.source_shape_id and edge.source_shape_id in parent:
            union(edge.id, edge.source_shape_id)
        if edge.target_shape_id and edge.target_shape_id in parent:
            union(edge.id, edge.target_shape_id)

    # 2. Union edges to other edges (to fix fragmented lines/polylines)
    for i, e1 in enumerate(edges):
        e1_pts = [e1.start_point, e1.end_point]
        for e2 in edges[i + 1:]:
            e2_pts = [e2.start_point, e2.end_point]
            connected = False
            for p1 in e1_pts:
                for p2 in e2_pts:
                    dist = ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
                    if dist <= tolerance:
                        union(e1.id, e2.id)
                        connected = True
                        break
                if connected:
                    break

    # Group all entities by their root
    groups: dict[str, list[str]] = {}
    for item_id in parent:
        root = find(item_id)
        groups.setdefault(root, []).append(item_id)

    # Build diagrams from groups
    shape_map = {s.id: s for s in shapes}
    edge_map = {e.id: e for e in edges}
    
    diagrams: list[Diagram] = []

    for root, member_ids in groups.items():
        group_shapes = [shape_map[sid] for sid in member_ids if sid in shape_map]
        group_edges = [edge_map[eid] for eid in member_ids if eid in edge_map]

        if group_shapes or group_edges:
            diagram = Diagram(
                shapes=group_shapes,
                edges=group_edges,
            )
            diagrams.append(diagram)

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
