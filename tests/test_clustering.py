import fitz
import uuid
from typing import Any
from diagramextract.models import Shape, BoundingBox

def _rect_intersection_area(r1: fitz.Rect, r2: fitz.Rect) -> float:
    intersect = fitz.Rect(r1).intersect(r2)
    if intersect.is_empty:
        return 0.0
    return abs(intersect.get_area())

def cluster_words(words: list[dict[str, Any]], distance_threshold: float = 20.0) -> list[list[dict[str, Any]]]:
    """Group words that are physically close to each other."""
    if not words:
        return []
        
    clusters = []
    
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
            # Check if search_rect overlaps with any word in this cluster
            overlaps = False
            for c_word in cluster:
                if _rect_intersection_area(search_rect, c_word["rect"]) > 0:
                    overlaps = True
                    break
            if overlaps:
                overlapping_clusters.append(i)
                
        if not overlapping_clusters:
            # Create a new cluster
            clusters.append([word])
        elif len(overlapping_clusters) == 1:
            # Add to the existing cluster
            clusters[overlapping_clusters[0]].append(word)
        else:
            # Merge multiple clusters
            new_cluster = [word]
            for idx in reversed(overlapping_clusters):
                new_cluster.extend(clusters.pop(idx))
            clusters.append(new_cluster)
            
    return clusters

pdf = 'tests/Corporate-Organizational-Chart-Someka-Example-PDF-V1.pdf'
page = fitz.open(pdf)[0]
raw_words = page.get_text("words")

text_items = []
for w in raw_words:
    text = w[4].strip()
    if text:
        text_items.append({
            "rect": fitz.Rect(w[:4]),
            "text": text,
            "assigned": False,
            "line_no": w[6]
        })

clusters = cluster_words(text_items)
print(f"Found {len(clusters)} clusters")
for i, c in enumerate(clusters[:10]):
    text = " ".join(w["text"] for w in c)
    print(f"Cluster {i}: {text}")
