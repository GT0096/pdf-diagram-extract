"""Tests for the shape classifier module."""

from __future__ import annotations

import pytest

from diagramextract.models import BoundingBox, Edge, Point, Shape
from diagramextract.shape_classifier import classify_and_clean


def _make_shape(
    shape_type: str = "rectangle",
    x0: float = 0, y0: float = 0,
    x1: float = 100, y1: float = 50,
    fill_color=None, shape_id: str | None = None,
) -> Shape:
    bbox = BoundingBox(x0, y0, x1, y1)
    shape = Shape(
        shape_type=shape_type,
        bbox=bbox,
        center=bbox.center,
        area=bbox.area,
        fill_color=fill_color,
    )
    if shape_id:
        shape.id = shape_id
    return shape


def _make_edge(
    x1: float = 0, y1: float = 0,
    x2: float = 100, y2: float = 0,
) -> Edge:
    return Edge(
        edge_type="line",
        start_point=Point(x1, y1),
        end_point=Point(x2, y2),
    )


class TestDeduplication:
    def test_removes_overlapping_shapes(self):
        # Two shapes with nearly identical bboxes
        s1 = _make_shape(x0=10, y0=10, x1=110, y1=60, shape_id="a")
        s2 = _make_shape(x0=12, y0=12, x1=112, y1=62, shape_id="b")
        shapes, _ = classify_and_clean([s1, s2], [])
        assert len(shapes) == 1

    def test_keeps_non_overlapping_shapes(self):
        s1 = _make_shape(x0=10, y0=10, x1=60, y1=50, shape_id="a")
        s2 = _make_shape(x0=200, y0=200, x1=300, y1=250, shape_id="b")
        shapes, _ = classify_and_clean([s1, s2], [])
        assert len(shapes) == 2


class TestNoiseFiltering:
    def test_filters_tiny_shapes(self):
        tiny = _make_shape(x0=0, y0=0, x1=2, y1=2)
        normal = _make_shape(x0=50, y0=50, x1=150, y1=100)
        shapes, _ = classify_and_clean([tiny, normal], [])
        assert len(shapes) == 1

    def test_filters_extreme_aspect_ratios(self):
        # Very thin horizontal line-like shape
        thin = _make_shape(x0=0, y0=0, x1=500, y1=1)
        shapes, _ = classify_and_clean([thin], [])
        assert len(shapes) == 0


class TestArrowDetection:
    def test_triangle_near_edge_becomes_arrow(self):
        # A triangle near the end of an edge
        tri = Shape(
            shape_type="triangle",
            bbox=BoundingBox(95, 15, 110, 35),
            center=Point(102.5, 25),
            area=200,
        )
        edge = Edge(
            edge_type="line",
            start_point=Point(0, 25),
            end_point=Point(100, 25),
        )
        shapes, edges = classify_and_clean([tri], [edge])
        # Triangle should be consumed as an arrowhead
        assert len(shapes) == 0
        assert edges[0].has_arrowhead is True
        assert edges[0].edge_type == "arrow"
