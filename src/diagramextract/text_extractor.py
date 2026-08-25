"""Native text extraction and assignment module."""

from __future__ import annotations

import uuid
from typing import Any

import fitz

from .models import BoundingBox, Shape, Point


def _rect_intersection_area(r1: fitz.Rect, r2: fitz.Rect) -> float:
    """Calculate the area of intersection between two rectangles."""
    intersect = fitz.Rect(r1).intersect(r2)
    if intersect.is_empty:
        return 0.0
    return abs(intersect.get_area())


def cluster_words(words: list[dict[str, Any]], distance_threshold: float = 20.0) -> list[list[dict[str, Any]]]:
    """Group words that are physically close to each other."""
    if not words:
        return []
        
    clusters: list[list[dict[str, Any]]] = []
    
    for word in words:
        w_rect = word["rect"]
        # Inflate the word's rect by the threshold to find overlapping clusters
        search_rect = fitz.Rect(w_rect)
        search_rect.x0 -= distance_threshold
        search_rect.y0 -= (distance_threshold * 0.5) # Less vertical tolerance
        search_rect.x1 += distance_threshold
        search_rect.y1 += (distance_threshold * 0.5)
        
        overlapping_clusters = []
        for i, cluster in enumerate(clusters):
            overlaps = False
            for c_word in cluster:
                if _rect_intersection_area(search_rect, c_word["rect"]) > 0:
                    overlaps = True
                    break
            if overlaps:
                overlapping_clusters.append(i)
                
        if not overlapping_clusters:
            clusters.append([word])
        elif len(overlapping_clusters) == 1:
            clusters[overlapping_clusters[0]].append(word)
        else:
            # Merge multiple clusters
            new_cluster = [word]
            for idx in reversed(overlapping_clusters):
                new_cluster.extend(clusters.pop(idx))
            clusters.append(new_cluster)
            
    return clusters


def rect_distance(r1: fitz.Rect, r2: fitz.Rect) -> float:
    """Calculate the shortest distance between two rectangles."""
    if r1.x1 < r2.x0:
        dx = r2.x0 - r1.x1
    elif r2.x1 < r1.x0:
        dx = r1.x0 - r2.x1
    else:
        dx = 0
        
    if r1.y1 < r2.y0:
        dy = r2.y0 - r1.y1
    elif r2.y1 < r1.y0:
        dy = r1.y0 - r2.y1
    else:
        dy = 0
        
    return (dx**2 + dy**2)**0.5


def assign_text(page: fitz.Page, shapes: list[Shape], padding: float = 5.0) -> None:
    """Extract text words from a page, assign to vector shapes, and create virtual text shapes."""
    words = page.get_text("words")
    
    text_items: list[dict[str, Any]] = []
    for w in words:
        text = w[4].strip()
        if text:
            # Simple Deduplication
            new_rect = fitz.Rect(w[:4])
            is_duplicate = False
            for existing in text_items:
                if existing["text"] == text:
                    overlap = _rect_intersection_area(new_rect, existing["rect"])
                    if overlap > 0 and (overlap / new_rect.get_area()) > 0.9:
                        is_duplicate = True
                        break
            if is_duplicate:
                continue
                
            text_items.append({
                "rect": new_rect,
                "text": text,
                "assigned": False,
                "line_no": w[6]
            })
                
    if not text_items:
        return
        
    # Phase 1: Assign to Vector Shapes by overlap
    shapes_by_area = []
    for shape in shapes:
        area = (shape.bbox.x1 - shape.bbox.x0) * (shape.bbox.y1 - shape.bbox.y0)
        shapes_by_area.append((area, shape))
        
    shapes_by_area.sort(key=lambda x: x[0])
    
    for _, shape in shapes_by_area:
        shape_rect = fitz.Rect(shape.bbox.x0, shape.bbox.y0, shape.bbox.x1, shape.bbox.y1)
        shape_rect.x0 -= padding
        shape_rect.y0 -= padding
        shape_rect.x1 += padding
        shape_rect.y1 += padding
        
        shape_words = []
        for item in text_items:
            if item["assigned"]:
                continue
            
            overlap_area = _rect_intersection_area(item["rect"], shape_rect)
            item_area = abs(item["rect"].get_area())
            
            if item_area > 0 and (overlap_area / item_area) > 0.3:
                shape_words.append(item)
                item["assigned"] = True
            
        if shape_words:
            current_line = shape_words[0]["line_no"]
            lines = []
            current_text = []
            for w in shape_words:
                if w["line_no"] != current_line:
                    lines.append(" ".join(current_text))
                    current_text = [w["text"]]
                    current_line = w["line_no"]
                else:
                    current_text.append(w["text"])
            if current_text:
                lines.append(" ".join(current_text))
            
            shape.text = "\n".join(lines)
            
    # Phase 2: Create Virtual Shapes for unassigned text OR assign them by proximity (Gravity)
    unassigned_words = [w for w in text_items if not w["assigned"]]
    clusters = cluster_words(unassigned_words)
    gravity_threshold = 20.0
    
    for cluster in clusters:
        cluster.sort(key=lambda w: (w["rect"].y0, w["rect"].x0))
        current_line = cluster[0]["line_no"]
        lines = []
        current_text = []
        
        min_x = min(w["rect"].x0 for w in cluster)
        min_y = min(w["rect"].y0 for w in cluster)
        max_x = max(w["rect"].x1 for w in cluster)
        max_y = max(w["rect"].y1 for w in cluster)
        block_rect = fitz.Rect(min_x, min_y, max_x, max_y)
        
        for w in cluster:
            if w["line_no"] != current_line:
                lines.append(" ".join(current_text))
                current_text = [w["text"]]
                current_line = w["line_no"]
            else:
                current_text.append(w["text"])
        if current_text:
            lines.append(" ".join(current_text))
            
        block_string = "\n".join(lines)
        
        # Phase 2a: Try to assign to the closest vector shape via Gravity
        best_shape = None
        best_dist = float("inf")
        
        # We only apply gravity to existing vector shapes (not newly added virtual shapes)
        # So we check shapes that don't have shape_type == "text_block"
        vector_shapes = [s for s in shapes if s.shape_type != "text_block"]
        for s in vector_shapes:
            s_rect = fitz.Rect(s.bbox.x0, s.bbox.y0, s.bbox.x1, s.bbox.y1)
            dist = rect_distance(block_rect, s_rect)
            if dist < gravity_threshold and dist < best_dist:
                best_dist = dist
                best_shape = s
                
        if best_shape:
            # Merge text block into this vector shape
            if best_shape.text:
                best_shape.text += "\n" + block_string
            else:
                best_shape.text = block_string
                
            # Expand bounding box to encompass the text!
            best_shape.bbox.x0 = min(best_shape.bbox.x0, min_x)
            best_shape.bbox.y0 = min(best_shape.bbox.y0, min_y)
            best_shape.bbox.x1 = max(best_shape.bbox.x1, max_x)
            best_shape.bbox.y1 = max(best_shape.bbox.y1, max_y)
            
            best_shape.center.x = (best_shape.bbox.x0 + best_shape.bbox.x1) / 2
            best_shape.center.y = (best_shape.bbox.y0 + best_shape.bbox.y1) / 2
            best_shape.area = (best_shape.bbox.x1 - best_shape.bbox.x0) * (best_shape.bbox.y1 - best_shape.bbox.y0)
            
            # Update vertices if they exist to match the new expanded bounding box
            if best_shape.vertices:
                best_shape.vertices = [
                    Point(best_shape.bbox.x0, best_shape.bbox.y0),
                    Point(best_shape.bbox.x1, best_shape.bbox.y0),
                    Point(best_shape.bbox.x1, best_shape.bbox.y1),
                    Point(best_shape.bbox.x0, best_shape.bbox.y1)
                ]
            continue
            
        # Phase 2b: If no nearby shape, create a new Virtual Shape
        virtual_shape = Shape(
            id=f"shp_{uuid.uuid4().hex[:8]}",
            shape_type="text_block",
            bbox=BoundingBox(min_x, min_y, max_x, max_y),
            center=Point((min_x + max_x) / 2, (min_y + max_y) / 2),
            vertices=[
                Point(min_x, min_y),
                Point(max_x, min_y),
                Point(max_x, max_y),
                Point(min_x, max_y)
            ],
            area=(max_x - min_x) * (max_y - min_y),
            fill_color=None,
            stroke_color=None,
            stroke_width=0,
            text=block_string
        )
        shapes.append(virtual_shape)
