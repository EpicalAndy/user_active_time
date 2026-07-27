"""
Базовый мини-виджет «кольцо-прогресс».

Общая отрисовка (серый трек + цветная дуга от 12 часов по часовой + текст в
центре) и настройка «что в центре» (`center` = процент/время). Конкретную
метрику задаёт подкласс: долю заполнения кольца, секунды для режима «время»
и пороги цвета.
"""

import tkinter as tk

from constants import FONT_FAMILY
from modules import theme
from utility import format_duration_short
from ..body import _color_for_percent
from .base import BaseMiniWidget

# Геометрия канвы и кольца. Публичные — их переиспользуют другие кольцевые
# мини-виджеты (например, таймлайн), чтобы все кольца были одного размера.
SIZE = 120           # сторона канвы, px
RING_WIDTH = 14      # толщина кольца, px
PAD = 12             # отступ дуги от края канвы, px


class RingWidget(BaseMiniWidget):
    """Кольцо-прогресс с процентом/временем в центре. Метрику задаёт подкласс."""

    caption = ""  # подпись под кольцом (переопределяет подкласс)

    # --- Переопределяют подклассы ---

    def _fraction(self, stats: dict) -> float | None:
        """Доля заполнения кольца, %. None — метрика недоступна (нет нормы)."""
        raise NotImplementedError

    def _time_seconds(self, stats: dict) -> int:
        """Секунды для режима «Время» в центре."""
        raise NotImplementedError

    def _thresholds(self) -> tuple[float, float]:
        """(recommended, min) — пороги цвета; читать из config динамически."""
        raise NotImplementedError

    # --- Отрисовка ---

    def _build(self):
        self._canvas = tk.Canvas(
            self.window, width=SIZE, height=SIZE,
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack()
        self._caption_label = tk.Label(
            self.window, text=self.caption,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption_label.pack(fill=tk.X, pady=(0, 4))

    def update(self, stats: dict):
        working = stats.get("is_working_day", True)
        frac = self._fraction(stats) if working else None
        available = frac is not None
        pct = min(float(frac), 100.0) if available else 0.0
        self._draw(pct, available, self._center_text(stats, available, pct))

    def _center_text(self, stats: dict, available: bool, pct: float) -> str:
        """Текст в центре кольца: процент или время (настройка `center`)."""
        if not available:
            return "—"
        if self.opts.get("center") == "time":
            return format_duration_short(int(self._time_seconds(stats)))
        return f"{pct:.0f}%"

    def _draw(self, pct: float, available: bool, center_text: str):
        c = self._canvas
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        bbox = (PAD, PAD, SIZE - PAD, SIZE - PAD)

        # Серый трек — полный круг.
        c.create_arc(
            *bbox, start=0, extent=359.999, style=tk.ARC,
            outline=theme.COLOR_LIGHT_GRAY, width=RING_WIDTH,
        )

        if available and pct > 0:
            # Дуга прогресса: от 12ч (start=90) по часовой (extent < 0).
            extent = -359.999 if pct >= 100 else -360.0 * pct / 100.0
            recommended, minimum = self._thresholds()
            color = _color_for_percent(pct, recommended, minimum)
            c.create_arc(
                *bbox, start=90, extent=extent, style=tk.ARC,
                outline=color, width=RING_WIDTH,
            )

        center = SIZE / 2
        # Время («5ч 51м») длиннее процента — уменьшаем шрифт, чтобы влезло.
        font_size = 18 if len(center_text) <= 4 else 12
        c.create_text(
            center, center, text=center_text,
            fill=theme.COLOR_LIGHT_FG, font=(FONT_FAMILY, font_size, "bold"),
        )
