"""
Mini chart card — shows symbol header + a sparkline chart.
Uses pyqtgraph for fast OpenGL-accelerated rendering.
"""

from typing import List

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from widget.style import theme

pg.setConfigOptions(antialias=True)


def _color(hex_str: str, alpha: int = 255) -> QColor:
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


class MiniChart(QWidget):
    """A compact card with a sparkline chart and current price header."""

    CHART_H = 80

    def __init__(self, symbol: str, label: str, category: str, parent=None):
        super().__init__(parent)
        self.symbol   = symbol
        self.label    = label
        self.category = category
        self._prices: List[float] = []
        self._setup_ui()

    # ── UI Setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MiniChart {{
                background: {theme.CARD_COLOR};
                border: 1px solid {theme.CARD_BORDER};
                border-radius: {theme.CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(theme.CARD_PADDING, 8, theme.CARD_PADDING, 8)
        root.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(10)
        self._dot.setStyleSheet(f"color: {theme.COLOR_DIM}; font-size: 8px;")

        self._sym_lbl = QLabel(self.label)
        self._sym_lbl.setFont(QFont(theme.FONT_FAMILY_MAIN, theme.FONT_SIZE_TITLE, QFont.Weight.Bold))
        self._sym_lbl.setStyleSheet(f"color: {theme.COLOR_WHITE};")

        self._price_lbl = QLabel("—")
        self._price_lbl.setFont(QFont(theme.FONT_FAMILY_MONO, theme.FONT_SIZE_CHANGE, QFont.Weight.Bold))
        self._price_lbl.setStyleSheet(f"color: {theme.COLOR_WHITE};")

        self._change_lbl = QLabel()
        self._change_lbl.setFont(QFont(theme.FONT_FAMILY_MAIN, theme.FONT_SIZE_SMALL))
        self._change_lbl.setStyleSheet(f"color: {theme.COLOR_NEUTRAL};")

        header.addWidget(self._dot)
        header.addWidget(self._sym_lbl)
        header.addStretch()
        header.addWidget(self._price_lbl)
        header.addWidget(self._change_lbl)
        root.addLayout(header)

        # Chart widget
        self._chart = pg.PlotWidget(background=None)
        self._chart.setFixedHeight(self.CHART_H)
        self._chart.hideAxis("left")
        self._chart.hideAxis("bottom")
        self._chart.setMouseEnabled(x=False, y=False)
        self._chart.setMenuEnabled(False)
        self._chart.getPlotItem().setContentsMargins(0, 0, 0, 0)

        # Remove all margins / frame
        self._chart.setFrameShape(self._chart.Shape.NoFrame)
        self._chart.viewport().setStyleSheet("background: transparent;")
        self._chart.setStyleSheet("background: transparent;")

        self._line = None
        self._fill = None
        root.addWidget(self._chart)

    # ── Public Update ─────────────────────────────────────────────────────────

    def update_data(self, data: dict):
        price      = data.get("price", 0)
        change     = data.get("change", 0)
        change_pct = data.get("change_pct", 0)

        sign  = "+" if change >= 0 else ""
        color = theme.COLOR_UP if change >= 0 else theme.COLOR_DOWN
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "—")

        self._price_lbl.setText(f"{price:,.2f}")
        self._change_lbl.setText(f"{arrow} {sign}{change_pct:.2f}%")
        self._change_lbl.setStyleSheet(f"color: {color};")
        self._dot.setText(arrow)
        self._dot.setStyleSheet(f"color: {color}; font-size: 8px;")

    def update_history(self, prices: List[float]):
        """Replace sparkline with new price history."""
        if not prices or len(prices) < 2:
            return
        self._prices = prices

        is_up = prices[-1] >= prices[0]
        color_hex = theme.CHART_LINE_UP if is_up else theme.CHART_LINE_DOWN

        # Remove old curves
        self._chart.clear()

        x = list(range(len(prices)))
        y = prices

        # Build fill gradient
        grad = QLinearGradient(0, 0, 0, self.CHART_H)
        grad.setColorAt(0.0, _color(color_hex, 60))
        grad.setColorAt(1.0, _color(color_hex, 0))

        # Line
        pen = QPen(_color(color_hex), 1.5)
        self._line = self._chart.plot(x, y, pen=pen)

        # Fill under line
        fill_brush = pg.mkBrush(grad)
        self._fill = pg.FillBetweenItem(
            self._line,
            self._chart.plot(x, [min(y)] * len(y), pen=pg.mkPen(None)),
            brush=fill_brush,
        )
        self._chart.addItem(self._fill)

        # Auto range y with small padding
        mn, mx = min(y), max(y)
        pad = (mx - mn) * 0.15 or 1
        self._chart.setYRange(mn - pad, mx + pad, padding=0)
        self._chart.setXRange(0, len(x) - 1, padding=0.02)
