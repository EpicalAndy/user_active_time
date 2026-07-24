"""
Мини-виджет «Активность» в виде кольца-прогресса.

Дуга закрашивается от 12 часов по часовой стрелке пропорционально проценту
активности (активное время / норма), поверх серого трека. Цвет дуги — по тем же
порогам, что и подсветка метрик в теле основного виджета
(зелёный/жёлтый/красный). В центре — процент. Нерабочий день → серое кольцо и «—».
"""

import tkinter as tk

import config
from constants import FONT_FAMILY, WIDGET_TYPE_ACTIVITY_PIE
from modules import theme
from ..body import _color_for_percent
from .base import BaseMiniWidget

# Геометрия канвы и кольца.
_SIZE = 120           # сторона канвы, px
_RING_WIDTH = 14      # толщина кольца, px
_PAD = 12             # отступ дуги от края канвы, px


class ActivityPieWidget(BaseMiniWidget):
    """Кольцо активности с процентом в центре."""

    def _build(self):
        self._canvas = tk.Canvas(
            self.window, width=_SIZE, height=_SIZE,
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack()
        self._caption = tk.Label(
            self.window, text=WIDGET_TYPE_ACTIVITY_PIE.split(" ")[0],  # «Активность»
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption.pack(fill=tk.X, pady=(0, 4))

    def update(self, stats: dict):
        working = stats.get("is_working_day", True)
        pct = min(float(stats.get("activity_percent", 0)), 100.0) if working else 0.0
        self._draw(pct, working)

    def _draw(self, pct: float, working: bool):
        c = self._canvas
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        bbox = (_PAD, _PAD, _SIZE - _PAD, _SIZE - _PAD)

        # Серый трек — полный круг.
        c.create_arc(
            *bbox, start=0, extent=359.999, style=tk.ARC,
            outline=theme.COLOR_LIGHT_GRAY, width=_RING_WIDTH,
        )

        if working and pct > 0:
            # Дуга прогресса: от 12ч (start=90) по часовой (extent < 0).
            extent = -359.999 if pct >= 100 else -360.0 * pct / 100.0
            color = _color_for_percent(
                pct,
                config.RECOMMENDED_ACTIVITY_THRESHOLD,
                config.MIN_ACTIVITY_THRESHOLD,
            )
            c.create_arc(
                *bbox, start=90, extent=extent, style=tk.ARC,
                outline=color, width=_RING_WIDTH,
            )

        center = _SIZE / 2
        text = f"{pct:.0f}%" if working else "—"
        c.create_text(
            center, center, text=text,
            fill=theme.COLOR_LIGHT_FG, font=(FONT_FAMILY, 18, "bold"),
        )
