"""
Мини-виджет «Метрики (полосы)» — несколько метрик компактно в одном окне.

Каждая метрика — горизонтальная полоса: заливка по проценту метрики, цвет по
её собственной шкале порогов, поверх заливки название слева и значение справа.
Набор полос настраивается галочками (опция `metrics`), порядок фиксированный —
он задан `_BARS`, а не порядком кликов, чтобы виджет не «перетасовывался».

Высота окна зависит от числа включённых полос; окно мини-виджета размера не
фиксирует (см. `BaseMiniWidget._position`), поэтому достаточно менять высоту
канвы — окно подстроится само.

Цвет текста на полосе выбирается по яркости подложки под ним: палитры тёмной и
светлой тем инвертированы (в светлой теме заливки тёмные, в тёмной — средней
яркости), поэтому фиксированный белый или фиксированный чёрный читался бы
только в одной из них.
"""

import tkinter as tk

import config
from constants import (
    FONT_FAMILY,
    METRIC_ACTIVITY_PERCENT,
    METRIC_FREE_TIME,
    METRIC_FULL_DAY_TIME,
    WIDGET_BARS_EMPTY,
    WIDGET_CAPTION_BARS,
)
from modules import theme
from utility import format_duration_signed
from ..body import _color_for_percent, free_time_color
from .base import BaseMiniWidget

# Геометрия. Ширина больше кольцевых виджетов: полосе нужно место под название
# и значение одновременно.
WIDTH = 220
BAR_HEIGHT = 22
BAR_GAP = 6
PAD_X = 8
TEXT_PAD = 6
FONT_SIZE = 9

# Чернила для текста на полосе — литеральные, не из палитры: подложкой служит
# то трек, то заливка, и роль палитры тут не поможет (см. шапку модуля).
_INK_LIGHT = "#FFFFFF"
_INK_DARK = "#1B2733"
# Граница яркости, выше которой подложка считается светлой. 0.6 — по факту
# заливок: жёлтая тёмной темы (#F39C12) светлая, зелёная (#27AE60) тёмная.
_INK_THRESHOLD = 0.6


# --- Метрики ---


def _activity(stats: dict):
    pct = stats.get("activity_percent")
    if pct is None:
        return None
    return pct, f"{pct:.0f}%", _color_for_percent(
        pct, config.RECOMMENDED_ACTIVITY_THRESHOLD, config.MIN_ACTIVITY_THRESHOLD,
    )


def _work_time(stats: dict):
    max_work = stats.get("max_work_seconds", 0)
    if max_work <= 0:
        return None
    pct = stats.get("full_day_seconds", 0) / max_work * 100
    return pct, f"{pct:.0f}%", _color_for_percent(
        pct, config.RECOMMENDED_WORK_TIME_THRESHOLD, config.MIN_WORK_TIME_THRESHOLD,
    )


def _free_time(stats: dict):
    budget_min = stats.get("free_budget_min_seconds", 0)
    if budget_min <= 0:
        return None
    remaining = stats.get("free_remaining_seconds", 0)
    remaining_min = stats.get("free_remaining_min_seconds", 0)
    # Шкала та же, что у кольца свободного времени: полная полоса = бюджет до
    # минимальной нормы, а значение показывает остаток до рекомендуемой.
    pct = remaining_min / budget_min * 100
    return pct, format_duration_signed(remaining), free_time_color(remaining, remaining_min)


# Порядок здесь = порядок полос в виджете.
_BARS: dict[str, dict] = {
    "activity": {"label": METRIC_ACTIVITY_PERCENT, "read": _activity},
    "work_time": {"label": METRIC_FULL_DAY_TIME, "read": _work_time},
    "free_time": {"label": METRIC_FREE_TIME, "read": _free_time},
}

# Для реестра: варианты галочек и набор по умолчанию (все).
BAR_CHOICES = [(key, meta["label"]) for key, meta in _BARS.items()]
DEFAULT_BARS = list(_BARS)


def selected_bars(opts: dict) -> list[str]:
    """Ключи включённых полос в фиксированном порядке `_BARS`.

    Значение из настроек чистится намеренно: `widgets.json` правится руками, а
    неизвестный ключ или не-список не должны ронять виджет.
    """
    raw = opts.get("metrics", DEFAULT_BARS)
    if isinstance(raw, str):  # одиночное значение из старого конфига
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return list(DEFAULT_BARS)
    chosen = set(raw)
    return [key for key in _BARS if key in chosen]


# --- Цвет текста ---


def _luminance(hex_color: str) -> float:
    """Воспринимаемая яркость цвета #RRGGBB в диапазоне 0..1."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def ink_for(background: str) -> str:
    """Читаемый цвет текста поверх заданной подложки."""
    return _INK_DARK if _luminance(background) > _INK_THRESHOLD else _INK_LIGHT


class MetricBarsWidget(BaseMiniWidget):
    """Несколько метрик горизонтальными полосами в одном окне."""

    caption = WIDGET_CAPTION_BARS

    # --- Каркас ---

    def _build(self):
        self._canvas = tk.Canvas(
            self.window, width=WIDTH, height=self._canvas_height(),
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack()
        self._caption_label = tk.Label(
            self.window, text=self.caption,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption_label.pack(fill=tk.X, pady=(0, 4))

    def _canvas_height(self) -> int:
        """Высота под текущий набор полос (пустой набор — под одну строку)."""
        rows = max(1, len(selected_bars(self.opts)))
        return rows * BAR_HEIGHT + (rows + 1) * BAR_GAP

    # --- Отрисовка ---

    def update(self, stats: dict):
        keys = selected_bars(self.opts)
        working = stats.get("is_working_day", True)

        c = self._canvas
        # Набор мог смениться через настройки — подгоняем высоту, окно
        # пересчитает свой размер само.
        height = self._canvas_height()
        if int(c.cget("height")) != height:
            c.configure(height=height)
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        if not keys:
            self._draw_placeholder(WIDGET_BARS_EMPTY)
            return

        y = BAR_GAP
        for key in keys:
            meta = _BARS[key]
            reading = meta["read"](stats) if working else None
            if reading is None:
                # Нерабочий день или нормы нет — серая полоса с прочерком.
                self._draw_bar(y, meta["label"], "—", 0.0, theme.COLOR_GRAY)
            else:
                pct, value_text, color = reading
                self._draw_bar(y, meta["label"], value_text, pct, color)
            y += BAR_HEIGHT + BAR_GAP

    def _draw_placeholder(self, text: str):
        c = self._canvas
        c.create_text(
            WIDTH / 2, self._canvas_height() / 2, text=text,
            fill=theme.COLOR_MUTED, font=(FONT_FAMILY, FONT_SIZE),
        )

    def _draw_bar(self, y: int, label: str, value: str, pct: float, color: str):
        """Одна полоса: трек, заливка по проценту, название слева, значение справа."""
        c = self._canvas
        x0, x1 = PAD_X, WIDTH - PAD_X
        y1 = y + BAR_HEIGHT

        c.create_rectangle(
            x0, y, x1, y1, fill=theme.COLOR_LIGHT_GRAY, outline="",
        )

        # Заливку подрезаем: активность бывает больше 100%, свободное время
        # уходит в минус — цвет это покажет, а полоса из берегов не выйдет.
        clamped = min(100.0, max(0.0, pct))
        fill_end = x0 + (x1 - x0) * clamped / 100
        if fill_end > x0:
            c.create_rectangle(x0, y, fill_end, y1, fill=color, outline="")

        text_y = y + BAR_HEIGHT / 2
        self._draw_bar_text(x0 + TEXT_PAD, text_y, label, tk.W, fill_end, color)
        self._draw_bar_text(x1 - TEXT_PAD, text_y, value, tk.E, fill_end, color)

    def _draw_bar_text(self, x: float, y: float, text: str, anchor: str,
                       fill_end: float, fill_color: str):
        """Пишет текст цветом, читаемым на той подложке, где он оказался.

        Подложка определяется по точке привязки: она либо ещё внутри заливки,
        либо уже на треке. Текст, повисший ровно на границе, оценивается по
        своему якорю — для названия это левый край, для значения правый.
        """
        background = fill_color if x <= fill_end else theme.COLOR_LIGHT_GRAY
        self._canvas.create_text(
            x, y, text=text, anchor=anchor,
            fill=ink_for(background), font=(FONT_FAMILY, FONT_SIZE),
        )
