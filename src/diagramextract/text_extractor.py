"""Native text extraction and assignment module."""

from __future__ import annotations

from typing import Any

import fitz

from .models import BoundingBox, Diagram, TextElement


def _rect_intersection_area(r1: fitz.Rect, r2: fitz.Rect) -> float:
    """Calculate the area of intersection between two rectangles."""
    intersect = r1.intersect(r2)
    if intersect.is_empty:
        return 0.0
    return abs(intersect.get_area())


def assign_text(page: fitz.Page, diagrams: list[Diagram], padding: float = 5.0) -> None:
    """Extract text blocks from a page and assign them to shapes or diagrams.
    
    Args:
        page: PyMuPDF Page object.
        diagrams: List of Diagrams to assign text to.
        padding: Margin (in points) to expand bounding boxes when checking for text overlap.
    """
    # 1. Extract all text blocks from the page
    # get_text("blocks") returns tuples: (x0, y0, x1, y1, "text", block_no, block_type)
    blocks = page.get_text("blocks")
    
    text_blocks: list[dict[str, Any]] = []
    for b in blocks:
        if len(b) >= 7 and b[6] == 0:  # block_type == 0 means text (1 is image)
            text = b[4].strip()
            if text:
                text_blocks.append({
                    "rect": fitz.Rect(b[:4]),
                    "text": text,
                    "assigned": False
                })
                
    if not text_blocks:
        return  # No native text found on this page
        
    # Phase 1: Assign to Shapes
    # We assign a text block to a shape if it mostly overlaps the shape's padded bbox.
    for diagram in diagrams:
        for shape in diagram.shapes:
            shape_rect = fitz.Rect(shape.bbox.x0, shape.bbox.y0, shape.bbox.x1, shape.bbox.y1)
            # Expand by padding to catch text that touches or slightly exceeds the border
            shape_rect.x0 -= padding
            shape_rect.y0 -= padding
            shape_rect.x1 += padding
            shape_rect.y1 += padding
            
            shape_texts = []
            for tb in text_blocks:
                if tb["assigned"]:
                    continue
                
                overlap_area = _rect_intersection_area(tb["rect"], shape_rect)
                tb_area = abs(tb["rect"].get_area())
                
                # If more than 50% of the text block is inside the shape, assign it
                if tb_area > 0 and (overlap_area / tb_area) > 0.5:
                    shape_texts.append(tb["text"])
                    tb["assigned"] = True
            
            if shape_texts:
                shape.text = "\n".join(shape_texts)
                
    # Phase 2: Assign unassigned text to Diagrams (Floating Text Elements)
    # E.g., Edge labels, chart titles, axis labels.
    for diagram in diagrams:
        if not diagram.shapes and not diagram.edges:
            continue
            
        # Calculate diagram's overall bounding box
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        
        for s in diagram.shapes:
            min_x, min_y = min(min_x, s.bbox.x0), min(min_y, s.bbox.y0)
            max_x, max_y = max(max_x, s.bbox.x1), max(max_y, s.bbox.y1)
        for e in diagram.edges:
            min_x, min_y = min(min_x, e.start_point.x, e.end_point.x), min(min_y, e.start_point.y, e.end_point.y)
            max_x, max_y = max(max_x, e.start_point.x, e.end_point.x), max(max_y, e.start_point.y, e.end_point.y)
            for w in e.waypoints:
                min_x, min_y = min(min_x, w.x), min(min_y, w.y)
                max_x, max_y = max(max_x, w.x), max(max_y, w.y)
                
        if min_x != float("inf"):
            diag_rect = fitz.Rect(min_x, min_y, max_x, max_y)
            # Expand more aggressively for diagram-level text (e.g. titles outside the strict boundary)
            diag_rect.x0 -= padding * 3
            diag_rect.y0 -= padding * 3
            diag_rect.x1 += padding * 3
            diag_rect.y1 += padding * 3
            
            for tb in text_blocks:
                if tb["assigned"]:
                    continue
                
                overlap = _rect_intersection_area(tb["rect"], diag_rect)
                tb_area = abs(tb["rect"].get_area())
                
                # If the text is near/inside this diagram (even a small overlap with the expanded box)
                if tb_area > 0 and (overlap / tb_area) > 0.1:
                    te = TextElement(
                        text=tb["text"],
                        bbox=BoundingBox(tb["rect"].x0, tb["rect"].y0, tb["rect"].x1, tb["rect"].y1)
                    )
                    diagram.text_elements.append(te)
                    tb["assigned"] = True
