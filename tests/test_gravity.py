import fitz
from typing import Any
from diagramextract.text_extractor import cluster_words

def rect_distance(r1: fitz.Rect, r2: fitz.Rect) -> float:
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

pdf = 'tests/Corporate-Organizational-Chart-Someka-Example-PDF-V1.pdf'
page = fitz.open(pdf)[0]

words = page.get_text("words")
text_items = []
for w in words:
    text = w[4].strip()
    if text:
        text_items.append({
            "rect": fitz.Rect(w[:4]),
            "text": text,
            "assigned": False,
            "line_no": w[6]
        })

clusters = cluster_words(text_items)

shapes = [
    {"id": "s1", "rect": fitz.Rect(120.5, 127.34, 150.62, 156.02), "words": []},
    {"id": "s2", "rect": fitz.Rect(120.5, 170.19, 150.62, 198.89), "words": []},
    {"id": "s3", "rect": fitz.Rect(120.5, 213.05, 150.62, 241.73), "words": []},
]

gravity_threshold = 20.0

for i, cluster in enumerate(clusters):
    min_x = min(w["rect"].x0 for w in cluster)
    min_y = min(w["rect"].y0 for w in cluster)
    max_x = max(w["rect"].x1 for w in cluster)
    max_y = max(w["rect"].y1 for w in cluster)
    block_rect = fitz.Rect(min_x, min_y, max_x, max_y)
    block_text = " ".join(w["text"] for w in cluster)
    
    best_shape = None
    best_dist = float("inf")
    
    for s in shapes:
        dist = rect_distance(block_rect, s["rect"])
        if dist < gravity_threshold and dist < best_dist:
            best_dist = dist
            best_shape = s
            
    if best_shape:
        best_shape["words"].append((block_text, best_dist))
        print(f"Assigned '{block_text}' to {best_shape['id']} (dist: {best_dist:.2f})")
    else:
        print(f"Left '{block_text}' as Virtual Node")
