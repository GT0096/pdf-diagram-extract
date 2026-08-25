"""Tests for the chart detector module."""

from __future__ import annotations

import pytest

from diagramextract.models import BoundingBox, Diagram, Edge, Point, Shape
from diagramextract.chart_detector import detect_charts


def _make_rect(x0, y0, x1, y1, fill_color=None) -> Shape:
    bbox = BoundingBox(x0, y0, x1, y1)
    return Shape(
        shape_type="rectangle",
        bbox=bbox,
        center=bbox.center,
        area=bbox.area,
        fill_color=fill_color,
    )


class TestBarChartDetection:
    def test_detects_vertical_bar_chart(self):
        """5 rectangles of similar width, aligned at bottom, varying heights."""
        bars = []
        baseline = 300
        bar_w = 30
        for i, h in enumerate([80, 120, 60, 150, 100]):
            x = 100 + i * 50
            bars.append(_make_rect(x, baseline - h, x + bar_w, baseline))

        diagram = Diagram(shapes=bars, edges=[])
        diagram = detect_charts(diagram)

        assert len(diagram.charts) == 1
        assert diagram.charts[0].chart_type == "bar_chart"
        assert len(diagram.charts[0].data_points) == 5
        # Bar shapes should be removed from shapes list
        assert len(diagram.shapes) == 0

    def test_ignores_non_bar_rectangles(self):
        """Two rectangles with very different widths should not be a bar chart."""
        shapes = [
            _make_rect(10, 10, 200, 100),
            _make_rect(300, 300, 400, 350),
        ]
        diagram = Diagram(shapes=shapes, edges=[])
        diagram = detect_charts(diagram)
        assert len(diagram.charts) == 0
        assert len(diagram.shapes) == 2


class TestPieChartDetection:
    def test_detects_pie_chart(self):
        """A circle with radial line edges inside."""
        circle = Shape(
            shape_type="circle",
            bbox=BoundingBox(100, 100, 300, 300),
            center=Point(200, 200),
            area=200 * 200 * 3.14159 / 4,  # ~31416
        )
        # Radial lines from center
        edges = [
            Edge(start_point=Point(200, 200), end_point=Point(300, 200)),
            Edge(start_point=Point(200, 200), end_point=Point(200, 100)),
            Edge(start_point=Point(200, 200), end_point=Point(100, 200)),
        ]
        diagram = Diagram(shapes=[circle], edges=edges)
        diagram = detect_charts(diagram)
        assert len(diagram.charts) == 1
        assert diagram.charts[0].chart_type == "pie_chart"


class TestScatterPlotDetection:
    def test_detects_scatter_plot(self):
        """Many small circles with no connecting edges."""
        dots = []
        for i in range(8):
            cx = 50 + i * 40
            cy = 100 + (i % 3) * 30
            dots.append(Shape(
                shape_type="circle",
                bbox=BoundingBox(cx - 5, cy - 5, cx + 5, cy + 5),
                center=Point(cx, cy),
                area=78,  # π * 5²
            ))

        diagram = Diagram(shapes=dots, edges=[])
        diagram = detect_charts(diagram)
        assert len(diagram.charts) == 1
        assert diagram.charts[0].chart_type == "scatter_plot"
