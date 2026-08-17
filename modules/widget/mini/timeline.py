"""
Мини-виджет «Таймлайн дня» — круговая диаграмма рабочего времени.

За 100% круга берётся метрика «Рабочее время»: полный оборот — это отрезок
[первый логин, сейчас]. 12 часов — начало дня, дальше по часовой стрелке.
Круг раскрашен по тому же принципу, что и график дневного отчёта:

- зелёный — активность,
- красный — простой (он же фон круга: всё, что не покрыто отрезками),
- синий  — время, добавленное вручную (рисуется поверх).

Данные приходят готовыми в `stats["timeline"]` (см. session_monitor) — виджет
только отрисовывает.

Нарезка ленты на ячейки (`cell_kinds`) и палитра (`segment_color`) публичные:
ту же ленту, только горизонтальной полосой, рисует виджет «Метрики».
"""

import math
import tkinter as tk

import config
from constants import FONT_FAMILY, WIDGET_CAPTION_TIMELINE
from modules import theme
from .ring import MIN_ARC_PX, PAD, RADIUS, RING_WIDTH, SIZE, RingWidget

# На сколько ячеек делится круг: по длине окружности, ячейка — минимальная
# рисуемая дуга (см. MIN_ARC_PX). Мельче кольцо всё равно не покажет: при
# рабочем дне в 9 часов одна ячейка — это примерно две с половиной минуты.
_CELLS = max(1, int(2 * math.pi * RADIUS / MIN_ARC_PX))


def segment_color(kind: str) -> str:
    """Цвет вида отрезка ленты дня: активность, ручное время, простой.

    Публичная: тем же палитром красится лента таймлайна в виджете «Метрики»,
    где простой рисуется наравне с остальными, а не остаётся фоном.
    """
    if kind == "active":
        return theme.COLOR_GREEN
    if kind == "manual":
        return theme.COLOR_BLUE
    return theme.COLOR_RED


def _color_over_background(kind: str) -> str | None:
    """Цвет дуги поверх фона кольца. None — простой, он и есть фон."""
    return None if kind == "inactive" else segment_color(kind)


# Приоритет вида отрезка, когда в одну ячейку попало поровну разных: ручное
# время дороже активности (его добавили руками, оно не должно теряться).
_KIND_PRIORITY = {"manual": 2, "active": 1, "inactive": 0}


def cell_kinds(timeline: dict, cells: int) -> list[str]:
    """Вид ("active"/"manual"/"inactive"), занявший каждую ячейку ленты дня.

    Лента — отрезок [первый логин, сейчас], нарезанный на `cells` равных ячеек.
    Считается не сам отрезок, а его ПОКРЫТИЕ по ячейкам: отрезок мельче ячейки
    нарисовать нечем, а отбрасывать мелочь нельзя — при коротком таймауте
    отрезков много, и картинка наврала бы в пользу простоя.

    Каждая ячейка достаётся тому виду, которого в ней больше по времени; пустая
    остаётся простоем. Пустой список — дня ещё нет (нулевой span).

    Публичная: по этим же ячейкам рисуется лента таймлайна в виджете «Метрики»,
    только шириной в пиксель полосы, а не в дугу кольца.
    """
    day_start = timeline["start_seconds"]
    span = timeline["end_seconds"] - day_start
    if span <= 0 or cells <= 0:
        return []

    buckets: list[dict[str, float]] = [{} for _ in range(cells)]
    cell_seconds = span / cells
    for seg_start, seg_end, kind in timeline["segments"]:
        start = max(seg_start - day_start, 0)
        end = min(seg_end - day_start, span)
        if end <= start:
            continue
        first = int(start / cell_seconds)
        last = min(int((end - 1e-9) / cell_seconds), cells - 1)
        for index in range(first, last + 1):
            cell_start = index * cell_seconds
            covered = min(end, cell_start + cell_seconds) - max(start, cell_start)
            if covered > 0:
                buckets[index][kind] = buckets[index].get(kind, 0.0) + covered

    return [_winner(bucket) for bucket in buckets]


def arcs(timeline: dict) -> list[tuple[float, float, str]]:
    """Дуги поверх красного фона: [(start, extent, цвет)] в градусах Tk.

    Ячейка кольца — MIN_ARC_PX: вырожденную дугу Tk чертит как полный круг
    (см. `ring.MIN_ARC_DEGREES`), и одна секунда активности закрашивала бы
    зелёным весь таймлайн — простой пропадал с диаграммы целиком.

    Соседние ячейки одного цвета сливаются в одну дугу; простой не рисуется —
    он и есть фон круга.
    """
    colors = [_color_over_background(kind) for kind in cell_kinds(timeline, _CELLS)]
    total = len(colors)

    out = []
    index = 0
    while index < total:
        color = colors[index]
        run = index
        while run + 1 < total and colors[run + 1] == color:
            run += 1
        if color is not None:
            extent = -360.0 * (run - index + 1) / total
            out.append((
                90 - 360.0 * index / total,
                max(extent, -359.999),
                color,
            ))
        index = run + 1
    return out


def _winner(cell: dict[str, float]) -> str:
    """Вид, занявший в ячейке больше всего времени (при равенстве — приоритетный)."""
    if not cell:
        return "inactive"
    return max(cell, key=lambda kind: (cell[kind], _KIND_PRIORITY.get(kind, 0)))


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

        c.create_arc(
            *bbox, start=90, extent=-359.999, style=tk.ARC,
            outline=theme.COLOR_RED, width=RING_WIDTH,
        )
        for start, extent, color in arcs(timeline):
            c.create_arc(
                *bbox, start=start, extent=extent,
                style=tk.ARC, outline=color, width=RING_WIDTH,
            )
