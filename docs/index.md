# pdf-diagram-extract

**Extract diagram and graph entities from PDFs as structured JSON — no LLM, pure code.**

[![PyPI version](https://img.shields.io/pypi/v/pdf-diagram-extract)](https://pypi.org/project/pdf-diagram-extract/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/pdf-diagram-extract)](https://pypi.org/project/pdf-diagram-extract/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/GT0096/pdf-diagram-extract/blob/main/LICENSE)

---

## What does it do?

`pdf-diagram-extract` takes a PDF file and extracts the geometric entities inside diagrams and graphs — shapes, edges, connections, and chart elements — returning everything as structured JSON.

### Supported Diagram Types

| Type | Detection Method |
|---|---|
| **Flowcharts** | Rectangles + diamonds + directed arrows |
| **Network diagrams** | Circles/ellipses with interconnecting edges |
| **Org charts** | Tree-structured rectangles |
| **Bar charts** | Aligned rectangles with varying heights |
| **Pie charts** | Circle with radial line segments |
| **Line charts** | Evenly-spaced connected data points |
| **Scatter plots** | Clusters of small unconnected dots |

### Key Features

- 🔍 **Vector extraction** — parses native PDF drawing primitives (PyMuPDF)
- 🖼️ **Raster fallback** — OpenCV contour detection for scanned PDFs
- 🔗 **Relationship resolution** — links edges to shapes via spatial proximity
- 📊 **Chart detection** — heuristic identification of common chart types
- 📦 **JSON output** — fully serializable structured results
- ⚡ **3 dependencies only** — PyMuPDF, OpenCV-headless, NumPy

---

## Quick Start

```bash
pip install pdf-diagram-extract
```

```python
import diagramextract
import json

result = diagramextract.extract("document.pdf")
print(json.dumps(result.to_dict(), indent=2))
```

[Get started →](getting-started.md){ .md-button .md-button--primary }
[API Reference →](api-reference.md){ .md-button }
