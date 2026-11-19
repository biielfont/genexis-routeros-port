#!/usr/bin/env python3
"""Genera progress.svg desde progress.json.

El SVG imita el mapa de progreso de AnyPS5: dos paneles oscuros con
treemaps, celdas verdes para lo hecho y grises para lo pendiente. Cada
celda vale un punto de peso, de modo que las dos partes suman 100.

El resultado se embebe en README.md y docs/PROGRESS.md. No se genera
ninguna página HTML: todo el texto vive en Markdown.

Uso:
    python3 tools/progress.py

No usa dependencias externas.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "progress.json"
OUT_SVG = ROOT / "progress.svg"

# Geometría y colores del mapa. Los tres primeros valores son los de AnyPS5.
PANEL_WIDTH = 495
GAP = 10
MAP_HEIGHT = 280
HEADER = 30
WIDTH = 2 * PANEL_WIDTH + GAP
HEIGHT = HEADER + MAP_HEIGHT

DONE_COLOR = "#2ea043"
TODO_COLOR = "#6e7681"
BORDER = "#0d1117"
TEXT_COLOR = "#ffffff"

PANELS = (
    ("platform", "Plataforma y arranque"),
    ("routeros", "RouterOS"),
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fmt_pct(value: float) -> str:
    value = round(float(value), 1)
    if value.is_integer():
        return f"{int(value)}%"
    return f"{value:.1f}%"


def area_done(area: dict) -> int:
    """Puntos de peso completados, redondeados a la celda del mapa."""
    weight = int(area["weight"])
    return max(0, min(weight, round(weight * float(area["percent"]) / 100.0)))


def worst_ratio(row: list[float], side: float) -> float:
    area = sum(row)
    return max(max(side * side * value / area**2, area**2 / (side * side * value)) for value in row)


def place(
    row: list[float],
    x: float,
    y: float,
    width: float,
    height: float,
    rects: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    thickness = sum(row) / min(width, height)
    offset = 0.0
    for area in row:
        length = area / thickness
        if width >= height:
            rects.append((x, y + offset, thickness, length))
        else:
            rects.append((x + offset, y, length, thickness))
        offset += length
    if width >= height:
        return x + thickness, y, width - thickness, height
    return x, y + thickness, width, height - thickness


def squarify(
    values: list[float], x: float, y: float, width: float, height: float
) -> list[tuple[float, float, float, float]]:
    """Reparte un rectángulo en bloques de área proporcional a values."""
    total = sum(values)
    if total <= 0 or width <= 0 or height <= 0:
        return []
    areas = [value * width * height / total for value in values]
    rects: list[tuple[float, float, float, float]] = []
    row: list[float] = []
    while areas:
        side = min(width, height)
        if not row or worst_ratio(row + [areas[0]], side) <= worst_ratio(row, side):
            row.append(areas.pop(0))
            continue
        x, y, width, height = place(row, x, y, width, height, rects)
        row = []
    if row:
        place(row, x, y, width, height, rects)
    return rects


def cells(count: int, x: float, y: float, width: float, height: float) -> list[tuple[float, float, float, float]]:
    """Coloca count celdas en una cuadrícula compacta dentro de un bloque."""
    if count <= 0 or width <= 0 or height <= 0:
        return []
    rows = max(1, min(count, round((count * height / width) ** 0.5)))
    result: list[tuple[float, float, float, float]] = []
    for row in range(rows):
        in_row = count // rows + (1 if row < count % rows else 0)
        cell_width = width / in_row
        result.extend(
            (x + column * cell_width, y + row * height / rows, cell_width, height / rows)
            for column in range(in_row)
        )
    return result


def rect(x: float, y: float, width: float, height: float, fill: str, stroke: float = 0.5) -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'fill="{fill}" stroke="{BORDER}" stroke-width="{stroke}"/>'
    )


def svg_text(x: float, y: float, value: str, size: int) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="sans-serif" font-size="{size}" '
        f'fill="{TEXT_COLOR}" stroke="{BORDER}" stroke-width="3" '
        f'paint-order="stroke">{esc(value)}</text>'
    )


def treemap_panel(title: str, groups: list[dict], left: float) -> list[str]:
    total = sum(int(group["weight"]) for group in groups)
    done = sum(int(group["done"]) for group in groups)
    percent = 100.0 * done / total if total else 0.0
    parts = [svg_text(left + 4, 21, f"{title}: {fmt_pct(percent)} ({done}/{total})", 16)]

    ordered = sorted(groups, key=lambda group: (-int(group["weight"]), str(group["title"])))
    boxes = squarify([float(group["weight"]) for group in ordered], left, HEADER, PANEL_WIDTH, MAP_HEIGHT)
    for group, (x, y, width, height) in zip(ordered, boxes):
        group_total = int(group["weight"])
        group_done = int(group["done"])
        group_percent = 100.0 * group_done / group_total if group_total else 0.0
        parts.append(
            f'<g><title>{esc(group["title"])}: {group_done}/{group_total} '
            f"({fmt_pct(group_percent)})</title>"
        )
        for index, cell in enumerate(cells(group_total, x + 1, y + 1, width - 2, height - 2)):
            parts.append(rect(*cell, DONE_COLOR if index < group_done else TODO_COLOR))
        parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'fill="none" stroke="{BORDER}" stroke-width="2"/>'
        )
        label_length = int((width - 10) / 7)
        label = str(group["short"])[:label_length] if label_length > 0 else ""
        if (label == str(group["short"]) or len(label) >= 3) and width > 24 and height > 22:
            parts.append(svg_text(x + 5, y + 16, label, 12))
            if height > 34:
                parts.append(svg_text(x + 5, y + 30, fmt_pct(group_percent), 11))
        parts.append("</g>")
    return parts


def make_svg(data: dict) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        f'aria-label="Mapa de progreso del port de RouterOS al Genexis Pure ED500">',
        rect(0, 0, WIDTH, HEIGHT, BORDER, 0),
    ]
    for index, (key, title) in enumerate(PANELS):
        groups = [
            {**area, "done": area_done(area)}
            for area in data["areas"]
            if area.get("panel") == key
        ]
        if groups:
            parts.extend(treemap_panel(title, groups, index * (PANEL_WIDTH + GAP)))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    areas = data["areas"]
    done = sum(area_done(area) for area in areas)
    total = sum(int(area["weight"]) for area in areas)
    overall = 100.0 * done / total if total else 0.0

    OUT_SVG.write_text(make_svg(data), encoding="utf-8")
    print(f"escrito {OUT_SVG} (overall {fmt_pct(overall)}, {done}/{total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
