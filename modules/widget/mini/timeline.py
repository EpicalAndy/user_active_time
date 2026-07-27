"""
Мини-виджет «Таймлайн дня» — круговая диаграмма рабочего времени.

За 100% круга берётся метрика «Рабочее время»: полный оборот — это отрезок
[первый логин, сейчас]. 12 часов — начало дня, дальше по часовой стрелке.
Круг раскрашен по тому же принципу, что и график дневного отчёта:

- зелёный — активность,
- красный — простой (он же фон круга: всё, что не покрыто отрезками),
- синий  — время, добавленное вручную (рисуется поверх).

Данные приходят готовыми в `stats["timeline"]` (см. session_monitor) — виджет
только отрисовывает. Опция `scale` добавляет часовые риски по стенным часам:
каждый круглый час внутри дня прорезает кольцо цветом фона.
"""

import math
import tkinter as tk

import config
from constants import FONT_FAMILY, WIDGET_CAPTION_TIMELINE
from modules import theme
from .ring import PAD, RING_WIDTH, SIZE, RingWidget

# Радиусы кольца: bbox задаёт осевую линию дуги, толщина растёт в обе стороны.
_MID_RADIUS = (SIZE - 2 * PAD) / 2
_INNER_RADIUS = _MID_RADIUS - RING_WIDTH / 2 - 1
_OUTER_RADIUS = _MID_RADIUS + RING_WIDTH / 2 + 1

_HOUR = 3600  # шаг часовой шкалы, с

# Отрезок короче этой доли круга не рисуем — дуга всё равно выродится в точку.
_MIN_EXTENT_DEGREES = 0.05


def _segment_color(kind: str) -> str | None:
    """Цвет отрезка таймлайна. None — рисовать не нужно (простой = фон круга)."""
    if kind == "active":
        return theme.COLOR_GREEN
    if kind == "manual":
        return theme.COLOR_BLUE
    return None


class TimelineWidget(RingWidget):
    """Круговой таймлайн дня: активность/простой/ручное время за рабочее время."""

    caption = WIDGET_CAPTION_TIMELINE

    # --- Метрика для центра кольца ---

    def _fraction(self, stats: dict) -> float | None:
        """Доля активности от рабочего времени (то самое «100% = рабочее время»)."""
        full_day = stats.get("full_day_seconds", 0)
        if full_day <= 0:
            return None
        return stats.get("active_seconds", 0) / full_day * 100

    def _time_seconds(self, stats: dict) -> int:
        return int(stats.get("active_seconds", 0))

    def _thresholds(self) -> tuple[float, float]:
        return (
            config.RECOMMENDED_ACTIVITY_THRESHOLD,
            config.MIN_ACTIVITY_THRESHOLD,
        )

    # --- Отрисовка ---

    def update(self, stats: dict):
        working = stats.get("is_working_day", True)
        timeline = stats.get("timeline") if working else None
        if timeline and timeline["end_seconds"] <= timeline["start_seconds"]:
            timeline = None

        frac = self._fraction(stats) if working else None
        available = timeline is not None and frac is not None
        # Процент не подрезаем: с добавленным вручную временем активность
        # честно может превысить рабочее время.
        pct = float(frac) if frac is not None else 0.0
        self._draw_timeline(timeline if available else None,
                            self._center_text(stats, available, pct))

    def _draw_timeline(self, timeline: dict | None, center_text: str):
        c = self._canvas
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        bbox = (PAD, PAD, SIZE - PAD, SIZE - PAD)
        if timeline is None:
            # Нерабочий день или логина ещё не было — пустой серый трек.
            c.create_arc(
                *bbox, start=0, extent=359.999, style=tk.ARC,
                outline=theme.COLOR_LIGHT_GRAY, width=RING_WIDTH,
            )
        else:
            self._draw_segments(bbox, timeline)
            if self.opts.get("scale", "on") == "on":
                self._draw_hour_ticks(timeline)

        center = SIZE / 2
        # Время («5ч 51м») длиннее процента — уменьшаем шрифт, чтобы влезло.
        font_size = 18 if len(center_text) <= 4 else 12
        c.create_text(
            center, center, text=center_text,
            fill=theme.COLOR_LIGHT_FG, font=(FONT_FAMILY, font_size, "bold"),
        )

    def _draw_segments(self, bbox: tuple, timeline: dict):
        """Круг = рабочее время: фон-простой, поверх — активность и ручное время."""
        c = self._canvas
        day_start = timeline["start_seconds"]
        span = timeline["end_seconds"] - day_start

        c.create_arc(
            *bbox, start=90, extent=-359.999, style=tk.ARC,
            outline=theme.COLOR_RED, width=RING_WIDTH,
        )
        for seg_start, seg_end, kind in timeline["segments"]:
            color = _segment_color(kind)
            if color is None:
                continue  # простой уже нарисован фоном круга
            extent = -360.0 * (seg_end - seg_start) / span
            if -extent < _MIN_EXTENT_DEGREES:
                continue
            c.create_arc(
                *bbox,
                start=90 - 360.0 * (seg_start - day_start) / span,
                extent=max(extent, -359.999),
                style=tk.ARC, outline=color, width=RING_WIDTH,
            )

    def _draw_hour_ticks(self, timeline: dict):
        """Риски на круглых часах — прорези цветом фона (шкала таймлайна)."""
        c = self._canvas
        center = SIZE / 2
        day_start = timeline["start_seconds"]
        span = timeline["end_seconds"] - day_start

        first_mark = (day_start // _HOUR + 1) * _HOUR
        for mark in range(int(first_mark), int(timeline["end_seconds"]) + 1, _HOUR):
            angle = math.radians(90 - 360.0 * (mark - day_start) / span)
            dx, dy = math.cos(angle), -math.sin(angle)
            c.create_line(
                center + dx * _INNER_RADIUS, center + dy * _INNER_RADIUS,
                center + dx * _OUTER_RADIUS, center + dy * _OUTER_RADIUS,
                fill=theme.COLOR_DARK_BG, width=2,
            )
