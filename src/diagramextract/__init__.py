"""diagramextract — Extract diagram and graph entities from PDFs as JSON.

No LLM calls, no agentic behavior — pure geometric and heuristic extraction.

Usage:
    import diagramextract
    import json

    result = diagramextract.extract("path/to/document.pdf")
    print(json.dumps(result.to_dict(), indent=2))
"""

from .core import extract
from .models import (
    BoundingBox,
    ChartElement,
    DataPoint,
    Diagram,
    Edge,
    ExtractionResult,
    PageResult,
    Point,
    Shape,
)

__version__ = "0.1.0"

__all__ = [
    "extract",
    "ExtractionResult",
    "PageResult",
    "Diagram",
    "Shape",
    "Edge",
    "ChartElement",
    "DataPoint",
    "BoundingBox",
    "Point",
    "__version__",
]
