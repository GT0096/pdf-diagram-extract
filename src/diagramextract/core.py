"""Core orchestrator — the main extraction pipeline.

Loads a PDF, decides per-page whether to use vector or raster extraction,
runs shape classification, relationship resolution, and chart detection,
then assembles the final ExtractionResult.
"""

from __future__ import annotations

import os
from pathlib import Path

import fitz  # PyMuPDF

from . import chart_detector, raster_extractor, shape_classifier, vector_extractor
from .models import ExtractionResult, PageResult
from .relationship_resolver import resolve_relationships


def extract(
    pdf_path: str | Path,
    *,
    pages: list[int] | None = None,
    vector_threshold: int = 5,
    dpi: int = 200,
) -> ExtractionResult:
    """Extract diagram and graph entities from a PDF file.

    This is the main entry point of the package.

    Args:
        pdf_path: Path to the PDF file.
        pages: Zero-indexed page numbers to process.
               None (default) processes all pages.
        vector_threshold: Minimum number of vector drawing primitives
               on a page to prefer vector extraction over raster fallback.
               Default: 5.
        dpi: Resolution for raster rendering when falling back to
               image-based extraction. Higher values yield better shape
               detection but slower processing. Default: 200.

    Returns:
        An ExtractionResult containing per-page diagrams, shapes,
        edges, and charts. Call .to_dict() or .to_json() to serialize.

    Raises:
        FileNotFoundError: If pdf_path does not exist.
        ValueError: If the file is not a valid PDF.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not pdf_path.suffix.lower() == ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path.suffix}")

    doc = fitz.open(str(pdf_path))

    try:
        total_pages = len(doc)

        # Determine which pages to process
        if pages is not None:
            page_indices = [p for p in pages if 0 <= p < total_pages]
        else:
            page_indices = list(range(total_pages))

        page_results: list[PageResult] = []

        for page_idx in page_indices:
            page = doc[page_idx]
            page_result = _process_page(
                page, page_idx, vector_threshold, dpi
            )
            page_results.append(page_result)

        return ExtractionResult(
            source_file=str(pdf_path.name),
            total_pages=total_pages,
            pages=page_results,
        )

    finally:
        doc.close()


def _process_page(
    page: fitz.Page,
    page_index: int,
    vector_threshold: int,
    dpi: int,
) -> PageResult:
    """Process a single PDF page through the full extraction pipeline.

    Pipeline:
    1. Count vector primitives → decide extraction method
    2. Extract raw shapes and edges
    3. Classify shapes & clean up
    4. Resolve relationships & group into diagrams
    5. Detect charts within each diagram

    Args:
        page: PyMuPDF Page object.
        page_index: Zero-indexed page number.
        vector_threshold: Minimum vector primitives for vector extraction.
        dpi: Resolution for raster fallback.

    Returns:
        A PageResult with all detected diagrams.
    """
    page_width = page.rect.width
    page_height = page.rect.height

    # Step 1: Decide extraction method
    n_primitives = vector_extractor.count_vector_primitives(page)
    use_vector = n_primitives >= vector_threshold

    # Step 2: Extract raw shapes and edges
    if use_vector:
        shapes, edges = vector_extractor.extract_page(page)
        extraction_method = "vector"
    else:
        shapes, edges = raster_extractor.extract_page(page, dpi=dpi)
        extraction_method = "raster"

    # Step 3: Classify and clean
    shapes, edges = shape_classifier.classify_and_clean(shapes, edges)

    # Step 4: Resolve relationships and group into diagrams
    diagrams = resolve_relationships(shapes, edges)

    # Step 4.5: Merge isolated single-shape diagrams for chart detection.
    # Bar charts have no edges between bars, so each bar ends up as its
    # own 1-shape diagram. We merge these into one combined diagram so
    # the chart detector can see the full pattern.
    isolated = [d for d in diagrams if len(d.shapes) == 1 and len(d.edges) == 0]
    connected = [d for d in diagrams if not (len(d.shapes) == 1 and len(d.edges) == 0)]

    if len(isolated) >= 3:
        from .models import Diagram
        merged_diagram = Diagram(
            shapes=[s for d in isolated for s in d.shapes],
            edges=[],
        )
        diagrams = connected + [merged_diagram]
    else:
        diagrams = connected + isolated

    # Step 5: Detect charts within each diagram
    for diagram in diagrams:
        chart_detector.detect_charts(diagram)

    # Remove empty diagrams (shapes consumed by chart detection)
    diagrams = [d for d in diagrams if d.shapes or d.edges or d.charts]

    return PageResult(
        page_number=page_index,
        width=page_width,
        height=page_height,
        extraction_method=extraction_method,
        diagrams=diagrams,
    )
