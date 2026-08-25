# Examples

## Flowchart Extraction

Extract shapes and connections from a flowchart PDF:

```python
import diagramextract
import json

result = diagramextract.extract("flowchart.pdf")

for page in result.pages:
    for diagram in page.diagrams:
        if diagram.diagram_type == "flowchart":
            print("=== Flowchart ===")

            # Print all nodes
            for shape in diagram.shapes:
                print(f"  [{shape.shape_type}] id={shape.id}")
                print(f"    Position: ({shape.center.x:.0f}, {shape.center.y:.0f})")
                print(f"    Size: {shape.bbox.width:.0f} × {shape.bbox.height:.0f}")
                if shape.fill_color:
                    print(f"    Color: rgb{shape.fill_color}")

            # Print connections
            for edge in diagram.edges:
                src = edge.source_shape_id or "?"
                tgt = edge.target_shape_id or "?"
                arrow = "→" if edge.has_arrowhead else "—"
                print(f"  {src} {arrow} {tgt}")
```

---

## Bar Chart Detection

Detect and extract bar chart data:

```python
result = diagramextract.extract("report.pdf")

for page in result.pages:
    for diagram in page.diagrams:
        for chart in diagram.charts:
            if chart.chart_type == "bar_chart":
                print(f"Bar chart at ({chart.bbox.x0:.0f}, {chart.bbox.y0:.0f})")
                print(f"  {len(chart.data_points)} bars detected:")
                for dp in chart.data_points:
                    print(f"    Bar {dp.index}: height={dp.value:.1f}, color={dp.color}")
```

---

## Save Results to File

```python
import diagramextract
import json
from pathlib import Path

result = diagramextract.extract("input.pdf")

# Save as JSON
output = Path("output.json")
output.write_text(result.to_json(indent=2))
print(f"Saved to {output}")
```

---

## Process Multiple PDFs

```python
import diagramextract
from pathlib import Path

pdf_dir = Path("pdfs/")
results = {}

for pdf_file in pdf_dir.glob("*.pdf"):
    result = diagramextract.extract(str(pdf_file))
    results[pdf_file.name] = {
        "pages": result.total_pages,
        "diagrams": sum(len(p.diagrams) for p in result.pages),
        "shapes": sum(
            len(s) for p in result.pages
            for d in p.diagrams for s in [d.shapes]
        ),
    }
    print(f"{pdf_file.name}: {results[pdf_file.name]}")
```

---

## Filter by Shape Type

Find all decision diamonds in a flowchart:

```python
result = diagramextract.extract("flowchart.pdf")

diamonds = [
    shape
    for page in result.pages
    for diagram in page.diagrams
    for shape in diagram.shapes
    if shape.shape_type == "diamond"
]

print(f"Found {len(diamonds)} decision node(s):")
for d in diamonds:
    print(f"  at ({d.center.x:.0f}, {d.center.y:.0f}), area={d.area:.0f}")
```

---

## Build a Graph from Edges

Use the extracted edges to build a graph with NetworkX:

```python
import diagramextract

try:
    import networkx as nx
except ImportError:
    print("Install networkx: pip install networkx")
    raise

result = diagramextract.extract("network.pdf")

for page in result.pages:
    for diagram in page.diagrams:
        G = nx.DiGraph() if any(e.has_arrowhead for e in diagram.edges) else nx.Graph()

        # Add nodes (shapes)
        for shape in diagram.shapes:
            G.add_node(shape.id, shape_type=shape.shape_type,
                       x=shape.center.x, y=shape.center.y)

        # Add edges
        for edge in diagram.edges:
            if edge.source_shape_id and edge.target_shape_id:
                G.add_edge(edge.source_shape_id, edge.target_shape_id,
                           edge_type=edge.edge_type)

        print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        print(f"  Connected: {nx.is_connected(G.to_undirected())}")
```

---

## Raster Extraction (Scanned PDFs)

For scanned PDFs, force raster extraction with a higher DPI:

```python
result = diagramextract.extract(
    "scanned_document.pdf",
    vector_threshold=9999,  # Force raster extraction
    dpi=300,                # Higher resolution for better detection
)

for page in result.pages:
    print(f"Page {page.page_number}: method={page.extraction_method}")
    print(f"  Shapes: {sum(len(d.shapes) for d in page.diagrams)}")
    print(f"  Edges: {sum(len(d.edges) for d in page.diagrams)}")
```

---

## Inspect the Extraction Method

Check whether vector or raster extraction was used:

```python
result = diagramextract.extract("document.pdf")

for page in result.pages:
    method = page.extraction_method
    n_diagrams = len(page.diagrams)
    print(f"Page {page.page_number}: {method} extraction → {n_diagrams} diagram(s)")
```
