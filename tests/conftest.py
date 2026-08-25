"""Generate synthetic PDF fixtures for testing.

Creates PDFs containing various diagram types using PyMuPDF's drawing API.
These are vector-based PDFs, suitable for testing the vector extractor.
"""

from __future__ import annotations

import os
from pathlib import Path

import fitz  # PyMuPDF


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def ensure_fixtures_dir() -> Path:
    """Create the fixtures directory if it doesn't exist."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    return FIXTURES_DIR


def create_flowchart_pdf(path: Path | None = None) -> Path:
    """Create a simple flowchart PDF with rectangles, diamonds, and arrows.

    Layout:
        [Start] → [Process A] → <Decision?> → [Process B] → [End]
                                    ↓
                               [Process C]
    """
    if path is None:
        path = ensure_fixtures_dir() / "flowchart.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Colors
    blue = (0.2, 0.4, 0.8)
    green = (0.2, 0.7, 0.3)
    orange = (0.9, 0.5, 0.1)
    black = (0, 0, 0)
    white = (1, 1, 1)

    # --- Shapes ---
    # Start box
    start_rect = fitz.Rect(50, 100, 150, 140)
    page.draw_rect(start_rect, color=black, fill=blue, width=1.5)

    # Process A box
    proc_a_rect = fitz.Rect(200, 100, 320, 140)
    page.draw_rect(proc_a_rect, color=black, fill=green, width=1.5)

    # Decision diamond (drawn as a rotated square via polygon)
    diamond_center = fitz.Point(400, 120)
    diamond_size = 40
    diamond_pts = [
        fitz.Point(diamond_center.x, diamond_center.y - diamond_size),   # top
        fitz.Point(diamond_center.x + diamond_size, diamond_center.y),   # right
        fitz.Point(diamond_center.x, diamond_center.y + diamond_size),   # bottom
        fitz.Point(diamond_center.x - diamond_size, diamond_center.y),   # left
    ]
    shape = page.new_shape()
    shape.draw_polyline(diamond_pts + [diamond_pts[0]])
    shape.finish(color=black, fill=orange, width=1.5, closePath=True)
    shape.commit()

    # Process B box
    proc_b_rect = fitz.Rect(480, 100, 570, 140)
    page.draw_rect(proc_b_rect, color=black, fill=green, width=1.5)

    # End box
    end_rect = fitz.Rect(480, 200, 570, 240)
    page.draw_rect(end_rect, color=black, fill=blue, width=1.5)

    # Process C box (from decision "no" branch)
    proc_c_rect = fitz.Rect(360, 220, 440, 260)
    page.draw_rect(proc_c_rect, color=black, fill=green, width=1.5)

    # --- Arrows (edges) ---
    # Start → Process A
    page.draw_line(fitz.Point(150, 120), fitz.Point(200, 120), color=black, width=1)

    # Process A → Decision
    page.draw_line(fitz.Point(320, 120), fitz.Point(360, 120), color=black, width=1)

    # Decision → Process B (right)
    page.draw_line(fitz.Point(440, 120), fitz.Point(480, 120), color=black, width=1)

    # Decision → Process C (down)
    page.draw_line(fitz.Point(400, 160), fitz.Point(400, 220), color=black, width=1)

    # Process B → End (down)
    page.draw_line(fitz.Point(525, 140), fitz.Point(525, 200), color=black, width=1)

    doc.save(str(path))
    doc.close()
    return path


def create_bar_chart_pdf(path: Path | None = None) -> Path:
    """Create a PDF with a simple vertical bar chart.

    5 bars of varying heights, aligned at the bottom.
    """
    if path is None:
        path = ensure_fixtures_dir() / "bar_chart.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=400)

    # Bar parameters
    bar_width = 40
    gap = 20
    baseline_y = 350
    start_x = 100
    heights = [120, 200, 80, 160, 240]
    colors = [
        (0.2, 0.5, 0.9),
        (0.9, 0.3, 0.3),
        (0.3, 0.8, 0.3),
        (0.9, 0.7, 0.2),
        (0.6, 0.3, 0.8),
    ]

    for i, (h, color) in enumerate(zip(heights, colors)):
        x = start_x + i * (bar_width + gap)
        rect = fitz.Rect(x, baseline_y - h, x + bar_width, baseline_y)
        page.draw_rect(rect, color=(0, 0, 0), fill=color, width=1)

    doc.save(str(path))
    doc.close()
    return path


def create_network_diagram_pdf(path: Path | None = None) -> Path:
    """Create a PDF with a network-style diagram (circles + edges)."""
    if path is None:
        path = ensure_fixtures_dir() / "network_diagram.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=400)

    # Node positions (center x, center y, radius)
    nodes = [
        (150, 100, 25),
        (300, 80, 25),
        (450, 100, 25),
        (100, 250, 25),
        (250, 280, 25),
        (400, 250, 25),
    ]

    # Draw nodes as circles
    for cx, cy, r in nodes:
        rect = fitz.Rect(cx - r, cy - r, cx + r, cy + r)
        page.draw_circle(fitz.Point(cx, cy), r, color=(0, 0, 0), fill=(0.3, 0.6, 0.9), width=1.5)

    # Draw edges between nodes
    connections = [(0, 1), (1, 2), (0, 3), (1, 4), (2, 5), (3, 4), (4, 5)]
    for a, b in connections:
        p1 = fitz.Point(nodes[a][0], nodes[a][1])
        p2 = fitz.Point(nodes[b][0], nodes[b][1])
        page.draw_line(p1, p2, color=(0.3, 0.3, 0.3), width=1)

    doc.save(str(path))
    doc.close()
    return path


def create_org_chart_pdf(path: Path | None = None) -> Path:
    """Create a PDF with a simple org chart (tree of rectangles)."""
    if path is None:
        path = ensure_fixtures_dir() / "org_chart.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=500)

    fill = (0.85, 0.9, 0.95)
    stroke = (0.2, 0.2, 0.6)

    # CEO
    ceo = fitz.Rect(256, 40, 356, 80)
    page.draw_rect(ceo, color=stroke, fill=fill, width=1.5)

    # VPs
    vp1 = fitz.Rect(106, 150, 206, 190)
    vp2 = fitz.Rect(256, 150, 356, 190)
    vp3 = fitz.Rect(406, 150, 506, 190)
    page.draw_rect(vp1, color=stroke, fill=fill, width=1.5)
    page.draw_rect(vp2, color=stroke, fill=fill, width=1.5)
    page.draw_rect(vp3, color=stroke, fill=fill, width=1.5)

    # Managers under VP1
    m1 = fitz.Rect(56, 260, 156, 300)
    m2 = fitz.Rect(180, 260, 280, 300)
    page.draw_rect(m1, color=stroke, fill=fill, width=1.5)
    page.draw_rect(m2, color=stroke, fill=fill, width=1.5)

    # Edges (vertical connections)
    page.draw_line(fitz.Point(306, 80), fitz.Point(156, 150), color=stroke, width=1)
    page.draw_line(fitz.Point(306, 80), fitz.Point(306, 150), color=stroke, width=1)
    page.draw_line(fitz.Point(306, 80), fitz.Point(456, 150), color=stroke, width=1)
    page.draw_line(fitz.Point(156, 190), fitz.Point(106, 260), color=stroke, width=1)
    page.draw_line(fitz.Point(156, 190), fitz.Point(230, 260), color=stroke, width=1)

    doc.save(str(path))
    doc.close()
    return path


def create_mixed_page_pdf(path: Path | None = None) -> Path:
    """Create a PDF with two independent diagrams on the same page.

    Left side: a small flowchart (3 boxes + 2 arrows)
    Right side: a small bar chart (3 bars)
    """
    if path is None:
        path = ensure_fixtures_dir() / "mixed_page.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=400)

    # --- Left: mini flowchart ---
    r1 = fitz.Rect(30, 100, 100, 130)
    r2 = fitz.Rect(30, 180, 100, 210)
    r3 = fitz.Rect(30, 260, 100, 290)
    page.draw_rect(r1, color=(0, 0, 0), fill=(0.4, 0.7, 0.4), width=1)
    page.draw_rect(r2, color=(0, 0, 0), fill=(0.4, 0.7, 0.4), width=1)
    page.draw_rect(r3, color=(0, 0, 0), fill=(0.4, 0.7, 0.4), width=1)
    page.draw_line(fitz.Point(65, 130), fitz.Point(65, 180), color=(0, 0, 0), width=1)
    page.draw_line(fitz.Point(65, 210), fitz.Point(65, 260), color=(0, 0, 0), width=1)

    # --- Right: bar chart ---
    bar_baseline = 350
    bar_w = 30
    bar_x = 350
    for i, h in enumerate([80, 150, 110]):
        x = bar_x + i * (bar_w + 15)
        rect = fitz.Rect(x, bar_baseline - h, x + bar_w, bar_baseline)
        page.draw_rect(rect, color=(0, 0, 0), fill=(0.3, 0.5, 0.8), width=1)

    doc.save(str(path))
    doc.close()
    return path


def create_empty_pdf(path: Path | None = None) -> Path:
    """Create a PDF with no drawings (text-only scenario)."""
    if path is None:
        path = ensure_fixtures_dir() / "empty.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # No drawings, just a blank page
    doc.save(str(path))
    doc.close()
    return path


def generate_all_fixtures() -> dict[str, Path]:
    """Generate all test fixture PDFs and return a dict of name → path."""
    return {
        "flowchart": create_flowchart_pdf(),
        "bar_chart": create_bar_chart_pdf(),
        "network_diagram": create_network_diagram_pdf(),
        "org_chart": create_org_chart_pdf(),
        "mixed_page": create_mixed_page_pdf(),
        "empty": create_empty_pdf(),
    }


if __name__ == "__main__":
    fixtures = generate_all_fixtures()
    for name, path in fixtures.items():
        print(f"Created: {name} → {path}")
