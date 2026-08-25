"""Integration tests — end-to-end extraction via the public API."""

from __future__ import annotations

import json

import pytest

import diagramextract
from tests.conftest import (
    create_bar_chart_pdf,
    create_empty_pdf,
    create_flowchart_pdf,
    create_mixed_page_pdf,
    create_network_diagram_pdf,
    create_org_chart_pdf,
)


@pytest.fixture
def flowchart_pdf(tmp_path):
    return create_flowchart_pdf(tmp_path / "flowchart.pdf")


@pytest.fixture
def bar_chart_pdf(tmp_path):
    return create_bar_chart_pdf(tmp_path / "bar_chart.pdf")


@pytest.fixture
def network_pdf(tmp_path):
    return create_network_diagram_pdf(tmp_path / "network.pdf")


@pytest.fixture
def org_chart_pdf(tmp_path):
    return create_org_chart_pdf(tmp_path / "org_chart.pdf")


@pytest.fixture
def mixed_pdf(tmp_path):
    return create_mixed_page_pdf(tmp_path / "mixed.pdf")


@pytest.fixture
def empty_pdf(tmp_path):
    return create_empty_pdf(tmp_path / "empty.pdf")


class TestExtractAPI:
    def test_returns_extraction_result(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        assert isinstance(result, diagramextract.ExtractionResult)
        assert result.total_pages == 1
        assert len(result.pages) == 1

    def test_to_dict_produces_valid_structure(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        d = result.to_dict()
        assert "source_file" in d
        assert "total_pages" in d
        assert "pages" in d
        assert len(d["pages"]) == 1

    def test_to_json_is_valid_json(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "pages" in parsed

    def test_page_has_diagrams(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        page = result.pages[0]
        assert len(page.diagrams) >= 1

    def test_uses_vector_extraction(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        assert result.pages[0].extraction_method == "vector"

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            diagramextract.extract(str(tmp_path / "nonexistent.pdf"))

    def test_non_pdf_raises(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            diagramextract.extract(str(txt_file))


class TestFlowchartExtraction:
    def test_finds_shapes(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        all_shapes = [
            s for p in result.pages for d in p.diagrams for s in d.shapes
        ]
        assert len(all_shapes) >= 4

    def test_finds_edges(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf))
        all_edges = [
            e for p in result.pages for d in p.diagrams for e in d.edges
        ]
        assert len(all_edges) >= 3


class TestBarChartExtraction:
    def test_detects_bar_chart(self, bar_chart_pdf):
        result = diagramextract.extract(str(bar_chart_pdf))
        all_charts = [
            c for p in result.pages for d in p.diagrams for c in d.charts
        ]
        bar_charts = [c for c in all_charts if c.chart_type == "bar_chart"]
        assert len(bar_charts) >= 1


class TestNetworkExtraction:
    def test_finds_circles(self, network_pdf):
        result = diagramextract.extract(str(network_pdf))
        all_shapes = [
            s for p in result.pages for d in p.diagrams for s in d.shapes
        ]
        circles = [s for s in all_shapes if s.shape_type in ("circle", "ellipse")]
        assert len(circles) >= 3


class TestEmptyPDF:
    def test_empty_pdf_produces_no_diagrams(self, empty_pdf):
        result = diagramextract.extract(str(empty_pdf))
        assert result.total_pages == 1
        page = result.pages[0]
        # Should have no diagrams or only empty ones
        total_shapes = sum(len(d.shapes) for d in page.diagrams)
        assert total_shapes == 0


class TestPageSelection:
    def test_select_specific_pages(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf), pages=[0])
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 0

    def test_out_of_range_page_ignored(self, flowchart_pdf):
        result = diagramextract.extract(str(flowchart_pdf), pages=[0, 999])
        assert len(result.pages) == 1
