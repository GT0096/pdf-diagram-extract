"""Tests for the vector extractor module."""

from __future__ import annotations

import pytest
import fitz

from tests.conftest import create_flowchart_pdf, create_bar_chart_pdf
from diagramextract.vector_extractor import extract_page, count_vector_primitives


@pytest.fixture
def flowchart_page(tmp_path):
    """Create a flowchart PDF and return its first page."""
    pdf_path = create_flowchart_pdf(tmp_path / "flowchart.pdf")
    doc = fitz.open(str(pdf_path))
    yield doc[0]
    doc.close()


@pytest.fixture
def bar_chart_page(tmp_path):
    """Create a bar chart PDF and return its first page."""
    pdf_path = create_bar_chart_pdf(tmp_path / "bar_chart.pdf")
    doc = fitz.open(str(pdf_path))
    yield doc[0]
    doc.close()


class TestCountVectorPrimitives:
    def test_flowchart_has_primitives(self, flowchart_page):
        count = count_vector_primitives(flowchart_page)
        # Flowchart has 6 rects + 1 polygon + 5 lines = at least 12 primitives
        assert count >= 10

    def test_empty_page_has_no_primitives(self, tmp_path):
        from tests.conftest import create_empty_pdf
        pdf_path = create_empty_pdf(tmp_path / "empty.pdf")
        doc = fitz.open(str(pdf_path))
        count = count_vector_primitives(doc[0])
        doc.close()
        assert count == 0


class TestExtractPage:
    def test_flowchart_extracts_shapes(self, flowchart_page):
        shapes, edges = extract_page(flowchart_page)
        # Should find rectangles (5 boxes)
        rect_count = sum(1 for s in shapes if s.shape_type == "rectangle")
        assert rect_count >= 4, f"Expected ≥4 rects, got {rect_count}"

    def test_flowchart_extracts_edges(self, flowchart_page):
        shapes, edges = extract_page(flowchart_page)
        # Should find connecting lines
        assert len(edges) >= 4, f"Expected ≥4 edges, got {len(edges)}"

    def test_shapes_have_valid_bboxes(self, flowchart_page):
        shapes, _ = extract_page(flowchart_page)
        for shape in shapes:
            assert shape.bbox.width > 0
            assert shape.bbox.height > 0
            assert shape.area > 0

    def test_edges_have_valid_endpoints(self, flowchart_page):
        _, edges = extract_page(flowchart_page)
        for edge in edges:
            assert edge.start_point is not None
            assert edge.end_point is not None

    def test_bar_chart_extracts_bars(self, bar_chart_page):
        shapes, _ = extract_page(bar_chart_page)
        rects = [s for s in shapes if s.shape_type == "rectangle"]
        # Should find exactly 5 bars
        assert len(rects) == 5, f"Expected 5 bars, got {len(rects)}"

    def test_shapes_have_colors(self, flowchart_page):
        shapes, _ = extract_page(flowchart_page)
        colored = [s for s in shapes if s.fill_color is not None]
        assert len(colored) >= 1, "Expected at least some colored shapes"
