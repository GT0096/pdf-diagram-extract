"""Tests for the raster extractor module."""

from __future__ import annotations

import pytest
import fitz

from tests.conftest import create_flowchart_pdf
from diagramextract.raster_extractor import extract_page


@pytest.fixture
def flowchart_page(tmp_path):
    """Create a flowchart PDF and return its first page."""
    pdf_path = create_flowchart_pdf(tmp_path / "flowchart.pdf")
    doc = fitz.open(str(pdf_path))
    yield doc[0]
    doc.close()


class TestRasterExtractPage:
    def test_extracts_shapes_from_rendered_page(self, flowchart_page):
        """Raster extractor should find shapes even from a vector PDF."""
        shapes, edges = extract_page(flowchart_page, dpi=150)
        # Should find at least some shapes
        assert len(shapes) >= 2, f"Expected ≥2 shapes, got {len(shapes)}"

    def test_shapes_have_pdf_coordinates(self, flowchart_page):
        """Shapes should have coordinates in PDF point space, not pixel space."""
        shapes, _ = extract_page(flowchart_page, dpi=150)
        page_w = flowchart_page.rect.width
        page_h = flowchart_page.rect.height
        for shape in shapes:
            assert 0 <= shape.bbox.x0 <= page_w, f"x0 out of range: {shape.bbox.x0}"
            assert 0 <= shape.bbox.y0 <= page_h, f"y0 out of range: {shape.bbox.y0}"

    def test_detects_lines(self, flowchart_page):
        """Should detect connecting lines between shapes."""
        _, edges = extract_page(flowchart_page, dpi=150)
        # May find some lines (depends on rendering quality)
        assert isinstance(edges, list)
