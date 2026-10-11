"""Utilidades para PDFs sintéticos que imitan layouts reales con datos FICTICIOS.

Los identificadores válidos (CLABE, tarjeta) se generan en código para que (1) los
detectores los reconozcan si se filtran y (2) la guardia de git no vea valores literales.
"""

from __future__ import annotations

from reportlab.pdfgen import canvas as rl_canvas

PAGE_H = 792


def make_clabe(prefix17: str) -> str:
    weights = (3, 7, 1)
    total = sum(int(d) * weights[i % 3] % 10 for i, d in enumerate(prefix17))
    return prefix17 + str((10 - total % 10) % 10)


def make_pan(prefix15: str) -> str:
    for check in "0123456789":
        digits = prefix15 + check
        total = 0
        for i, d in enumerate(reversed(digits)):
            n = int(d)
            if i % 2:
                n = n * 2 - 9 if n > 4 else n * 2
            total += n
        if total % 10 == 0:
            return digits
    raise AssertionError


class Sheet:
    """Canvas con coordenadas como las reporta pdfplumber (``top`` desde arriba)."""

    def __init__(self, path):
        self.c = rl_canvas.Canvas(str(path), pagesize=(612, PAGE_H))

    def put(self, x: float, top: float, text: str, size: float = 10, right: bool = False) -> None:
        self.c.setFont("Helvetica", size)
        y = PAGE_H - top - 0.72 * size
        if right:
            self.c.drawRightString(x, y, text)
        else:
            self.c.drawString(x, y, text)

    def page(self) -> None:
        self.c.showPage()

    def save(self) -> None:
        self.c.save()
