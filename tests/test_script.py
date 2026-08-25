import fitz
from diagramextract.text_extractor import _rect_intersection_area
from diagramextract import extract

pdf = 'tests/Content-Workflow-Template-Someka-Example-PDF-V1.pdf'
result = extract(pdf)

page = fitz.open(pdf)[0]
diagrams = result.pages[0].diagrams

words = page.get_text('words')
text_items = []
for w in words:
    text = w[4].strip()
    if text:
        text_items.append({
            'rect': fitz.Rect(w[:4]),
            'text': text,
            'assigned': False,
            'line_no': w[6]
        })

padding = 5.0

all_shapes = []
for diagram in diagrams:
    for shape in diagram.shapes:
        area = (shape.bbox.x1 - shape.bbox.x0) * (shape.bbox.y1 - shape.bbox.y0)
        all_shapes.append((area, shape))
        
all_shapes.sort(key=lambda x: x[0])

for area, shape in all_shapes:
    shape_rect = fitz.Rect(shape.bbox.x0, shape.bbox.y0, shape.bbox.x1, shape.bbox.y1)
    shape_rect.x0 -= padding
    shape_rect.y0 -= padding
    shape_rect.x1 += padding
    shape_rect.y1 += padding
    
    shape_words = []
    for item in text_items:
        if item['text'] == 'Finalize':
            print(f"Checking Finalize against shape {shape.shape_type} {shape_rect}")
            print(f"  Assigned: {item['assigned']}")
        
        if item['assigned']:
            continue
        
        overlap_area = _rect_intersection_area(item['rect'], shape_rect)
        item_area = abs(item['rect'].get_area())
        
        if item_area > 0 and (overlap_area / item_area) > 0.3:
            if item['text'] == 'Finalize':
                print(f"  => Assigned to this shape! {shape.shape_type}")
            shape_words.append(item)
            item['assigned'] = True
