"""Raster-based extraction of shapes and edges from scanned/image PDF pages.

When a PDF page contains no (or too few) vector drawing primitives,
this module renders the page to a bitmap and uses OpenCV contour detection
to identify shapes and lines.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import fitz  # PyMuPDF

from .models import BoundingBox, Edge, Point, Shape
from .utils import circularity, classify_polygon, pixel_to_pdf_coords


# ---------- Thresholds ----------
MIN_CONTOUR_AREA_PX = 200      # Minimum contour area in pixels
MAX_CONTOUR_AREA_RATIO = 0.7   # Max ratio of contour area to image area
MIN_LINE_LENGTH_PX = 20        # Minimum line length in pixels for HoughLinesP
CIRCULARITY_THRESHOLD = 0.75   # Above this → circle/ellipse
APPROX_EPSILON_RATIO = 0.02    # cv2.approxPolyDP epsilon as fraction of perimeter


def extract_page(
    page: fitz.Page,
    dpi: int = 200,
    min_contour_area: int = MIN_CONTOUR_AREA_PX,
) -> tuple[list[Shape], list[Edge]]:
    """Extract shapes and edges from a page rendered as a raster image.

    Args:
        page: A PyMuPDF Page object.
        dpi: Resolution for rendering (higher = more detail, slower).
        min_contour_area: Minimum contour area in pixels to keep.

    Returns:
        A tuple of (shapes, edges) in PDF coordinate space.
    """
    # Render page to image
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )

    # Convert to BGR (OpenCV default) if needed
    if pix.n == 4:  # RGBA
        img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:  # Grayscale
        img_bgr = cv2.cvtColor(img_data, cv2.COLOR_GRAY2BGR)
    else:
        img_bgr = img_data.copy()

    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    img_h, img_w = img_gray.shape[:2]
    img_area = img_h * img_w
    page_w, page_h = page.rect.width, page.rect.height

    # --- Preprocessing ---
    # Adaptive threshold for robust binarization across lighting conditions
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2,
    )

    # Morphological close to fill small gaps in shape outlines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    # --- Contour detection ---
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )

    shapes: list[Shape] = []
    shape_contours: list[np.ndarray] = []  # Track which contours became shapes

    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < min_contour_area:
            continue
        if area > img_area * MAX_CONTOUR_AREA_RATIO:
            continue

        # Approximate the contour to a simpler polygon
        perimeter = cv2.arcLength(contour, True)
        epsilon = APPROX_EPSILON_RATIO * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)
        n_vertices = len(approx)

        # Get bounding rect
        x, y, w, h = cv2.boundingRect(contour)

        # Convert pixel coords to PDF coords
        pdf_x0, pdf_y0 = pixel_to_pdf_coords(x, y, page_w, page_h, img_w, img_h)
        pdf_x1, pdf_y1 = pixel_to_pdf_coords(
            x + w, y + h, page_w, page_h, img_w, img_h
        )

        bbox = BoundingBox(pdf_x0, pdf_y0, pdf_x1, pdf_y1)

        # Convert vertices to PDF coords
        vertices = []
        for pt in approx:
            px, py = pt[0]
            vx, vy = pixel_to_pdf_coords(px, py, page_w, page_h, img_w, img_h)
            vertices.append(Point(vx, vy))

        # Classify the shape
        circ = circularity(area, perimeter)

        if circ > CIRCULARITY_THRESHOLD:
            # Circle or ellipse
            aspect = w / h if h > 0 else 1
            shape_type = "circle" if 0.8 < aspect < 1.2 else "ellipse"
        elif n_vertices == 3:
            shape_type = "triangle"
        elif n_vertices == 4:
            shape_type = classify_polygon(vertices)
        elif n_vertices >= 5 and n_vertices <= 8:
            # Could be a diamond or other regular polygon with noise
            if circ > 0.6:
                shape_type = "circle"
            else:
                shape_type = "polygon"
        else:
            shape_type = "polygon"

        # Estimate dominant color inside the contour
        fill_color = _estimate_fill_color(img_bgr, contour)

        shape = Shape(
            shape_type=shape_type,
            bbox=bbox,
            center=bbox.center,
            vertices=vertices,
            area=bbox.area,
            fill_color=fill_color,
            stroke_color=(0, 0, 0),  # Assume black stroke for raster
            stroke_width=1.0,
        )
        shapes.append(shape)
        shape_contours.append(contour)

    # --- Line detection ---
    # Create a mask that removes detected shapes so we only detect connecting lines
    line_mask = binary.copy()
    for contour in shape_contours:
        cv2.drawContours(line_mask, [contour], -1, 0, thickness=cv2.FILLED)

    edges = _detect_lines(line_mask, page_w, page_h, img_w, img_h)

    return shapes, edges


def _detect_lines(
    binary_mask: np.ndarray,
    page_w: float, page_h: float,
    img_w: int, img_h: int,
) -> list[Edge]:
    """Detect straight lines in the binary mask using Hough transform.

    Args:
        binary_mask: Binary image with shapes removed.
        page_w, page_h: PDF page dimensions in points.
        img_w, img_h: Rendered image dimensions in pixels.

    Returns:
        List of Edge objects in PDF coordinate space.
    """
    edges: list[Edge] = []

    lines = cv2.HoughLinesP(
        binary_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=MIN_LINE_LENGTH_PX,
        maxLineGap=10,
    )

    if lines is None:
        return edges

    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Convert to PDF coordinates
        pdf_x1, pdf_y1 = pixel_to_pdf_coords(x1, y1, page_w, page_h, img_w, img_h)
        pdf_x2, pdf_y2 = pixel_to_pdf_coords(x2, y2, page_w, page_h, img_w, img_h)

        edge = Edge(
            edge_type="line",
            start_point=Point(pdf_x1, pdf_y1),
            end_point=Point(pdf_x2, pdf_y2),
            stroke_color=(0, 0, 0),
            stroke_width=1.0,
        )
        edges.append(edge)

    # Merge collinear lines that are close together
    edges = _merge_collinear_edges(edges)

    return edges


def _merge_collinear_edges(
    edges: list[Edge], angle_tolerance: float = 5.0, gap_tolerance: float = 8.0
) -> list[Edge]:
    """Merge nearly-collinear edges that are close together.

    Hough transform often splits a single long line into multiple segments.
    This merges them back if they share similar angles and endpoints are close.
    """
    if len(edges) < 2:
        return edges

    merged: list[Edge] = []
    used = set()

    for i, e1 in enumerate(edges):
        if i in used:
            continue

        # Compute angle of e1
        dx1 = e1.end_point.x - e1.start_point.x
        dy1 = e1.end_point.y - e1.start_point.y
        angle1 = math.degrees(math.atan2(dy1, dx1)) % 180

        current = e1
        used.add(i)

        for j, e2 in enumerate(edges):
            if j in used:
                continue

            dx2 = e2.end_point.x - e2.start_point.x
            dy2 = e2.end_point.y - e2.start_point.y
            angle2 = math.degrees(math.atan2(dy2, dx2)) % 180

            # Check angle similarity
            angle_diff = abs(angle1 - angle2)
            if angle_diff > angle_tolerance and (180 - angle_diff) > angle_tolerance:
                continue

            # Check if endpoints are close
            min_dist = min(
                math.hypot(
                    current.end_point.x - e2.start_point.x,
                    current.end_point.y - e2.start_point.y,
                ),
                math.hypot(
                    current.end_point.x - e2.end_point.x,
                    current.end_point.y - e2.end_point.y,
                ),
                math.hypot(
                    current.start_point.x - e2.start_point.x,
                    current.start_point.y - e2.start_point.y,
                ),
                math.hypot(
                    current.start_point.x - e2.end_point.x,
                    current.start_point.y - e2.end_point.y,
                ),
            )

            if min_dist < gap_tolerance:
                # Merge: take the two most distant points
                all_pts = [
                    current.start_point, current.end_point,
                    e2.start_point, e2.end_point,
                ]
                max_dist = 0
                best_pair = (current.start_point, current.end_point)
                for a_idx in range(len(all_pts)):
                    for b_idx in range(a_idx + 1, len(all_pts)):
                        d = math.hypot(
                            all_pts[a_idx].x - all_pts[b_idx].x,
                            all_pts[a_idx].y - all_pts[b_idx].y,
                        )
                        if d > max_dist:
                            max_dist = d
                            best_pair = (all_pts[a_idx], all_pts[b_idx])

                current = Edge(
                    edge_type="line",
                    start_point=best_pair[0],
                    end_point=best_pair[1],
                    stroke_color=current.stroke_color,
                    stroke_width=current.stroke_width,
                )
                used.add(j)

        merged.append(current)

    return merged


def _estimate_fill_color(
    img_bgr: np.ndarray, contour: np.ndarray
) -> tuple[int, int, int] | None:
    """Estimate the dominant fill color inside a contour.

    Creates a mask from the contour and computes the mean color
    of pixels inside it (excluding near-white/near-black pixels).
    """
    mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)

    # Erode slightly to avoid edge pixels
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.erode(mask, kernel, iterations=1)

    masked = img_bgr[mask > 0]
    if len(masked) == 0:
        return None

    # Filter out near-white and near-black pixels
    gray_vals = cv2.cvtColor(
        masked.reshape(-1, 1, 3), cv2.COLOR_BGR2GRAY
    ).flatten()
    color_mask = (gray_vals > 30) & (gray_vals < 225)

    if color_mask.sum() < 10:
        return None

    colored = masked[color_mask]
    mean_color = colored.mean(axis=0).astype(int)

    # Convert BGR → RGB
    return (int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))
