"""
Мини-виджет «Тепловая карта» — сетка дней с цветом по активности.

Упрощённый аналог окна «Тепловая карта» (modules/heatmap_viewer.py) прямо на
рабочем столе: без навигации по месяцам, легенды и кликов по дням — только
клетки. Каждая клетка — день с его номером, цвет по проценту активности за
день по той же шкале, что и метрики в теле; сегодня обведён. Виды клеток и
подсказка при наведении — те же, что у недельной полосы (`week_strip`):
данные / нет данных / выходной / ещё не наступил.

Две настройки:
    `period` — сколько дней: неделя (одна строка) или месяц (сетка по неделям);
    `range`  — от чего отсчитывать:
        calendar — календарные неделя (Пн–Вс) или месяц (с 1-го числа), дни
            после сегодня показываются пустыми;
        rolling  — скользящие: последние семь дней или последний месяц по
            сегодня, сегодня — последняя клетка сетки.

Столбцы всегда соответствуют дням недели, и в скользящем режиме тоже: строки
идут по семь дней, поэтому в каждом столбце стоит один и тот же день недели —
просто заголовок сдвинут так, что сегодняшний день недели оказывается справа.
Сетка (`grid_rows`) и заголовок столбцов (`column_weekdays`) считаются без tk и
проверяются тестами.

Клетки — tk.Label в сетке (как в окне тепловой карты), а не Canvas: так у
каждой своя подсказка без ручного попадания в координаты. Пересобираются
только когда меняется раскладка (сменились сутки или настройки), на обычном
тике лишь перекрашиваются.
"""

import calendar
import datetime
import tkinter as tk

from constants import FONT_FAMILY
from texts import WEEKDAY_SHORT_NAMES, WIDGET_CAPTION_HEATMAP
from modules import theme
from modules.ui_utils import attach_tooltip
from modules.week_activity import (
    KIND_DAY_OFF,
    KIND_FUTURE,
    WEEK_LENGTH,
    WEEK_MODE_CALENDAR,
    WEEK_MODE_ROLLING,
    build_days,
    week_dates,
)
from ..week_strip import border_color, cell_color, tooltip_text
from .bars import ink_for
from .base import BaseMiniWidget

# Значения опции `period`.
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
# Значения опции `range` — те же, что у режима недельной полосы.
RANGE_CALENDAR = WEEK_MODE_CALENDAR
RANGE_ROLLING = WEEK_MODE_ROLLING

DEFAULT_PERIOD = PERIOD_WEEK
DEFAULT_RANGE = RANGE_CALENDAR

# Геометрия клетки: ширина в символах (номер дня — не больше двух), рамка
# постоянной толщины и меняет только цвет — иначе «сегодня» было бы крупнее
# соседей и сетка дёргалась бы (тот же приём, что у недельной полосы).
CELL_WIDTH_CHARS = 3
CELL_BORDER = 2
CELL_GAP = 1
PAD = 6
FONT_SIZE = 9
HEADER_FONT_SIZE = 8


# --- Настройки ---


def selected_period(opts: dict) -> str:
    """Период из настроек; мусор из widgets.json → неделя."""
    value = opts.get("period", DEFAULT_PERIOD)
    return value if value in (PERIOD_WEEK, PERIOD_MONTH) else DEFAULT_PERIOD


def selected_range(opts: dict) -> str:
    """Отсчёт из настроек; мусор из widgets.json → календарный."""
    value = opts.get("range", DEFAULT_RANGE)
    return value if value in (RANGE_CALENDAR, RANGE_ROLLING) else DEFAULT_RANGE


# --- Раскладка ---


def rolling_month_start(today: datetime.date) -> datetime.date:
    """Первый день скользящего месяца: день после «сегодня минус месяц».

    «Минус месяц» — то же число предыдущего месяца, поджатое к его длине:
    14.09 → 15.08–14.09, 31.03 → 01.03–31.03, 30.04 → 31.03–30.04.
    """
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    day = min(today.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day) + datetime.timedelta(days=1)


def grid_rows(today: datetime.date, period: str, range_mode: str) -> list[list]:
    """Строки сетки по семь клеток: дата или None (пустое место).

    Календарный месяц — полные недели с Пн, как в окне тепловой карты, только
    дни соседних месяцев не показываются вовсе (None). Скользящий — дни идут
    подряд и заканчиваются сегодняшним, первая строка добивается None слева.
    """
    if period == PERIOD_MONTH:
        if range_mode == RANGE_ROLLING:
            start = rolling_month_start(today)
            dates = [start + datetime.timedelta(days=i) for i in range((today - start).days + 1)]
            return _right_aligned_rows(dates)
        weeks = calendar.Calendar(calendar.MONDAY).monthdatescalendar(today.year, today.month)
        return [[d if d.month == today.month else None for d in week] for week in weeks]
    return [week_dates(today, range_mode)]


def _right_aligned_rows(dates: list[datetime.date]) -> list[list]:
    """Режет даты на строки по семь так, чтобы последняя строка была полной."""
    padded = [None] * (-len(dates) % WEEK_LENGTH) + list(dates)
    return [padded[i:i + WEEK_LENGTH] for i in range(0, len(padded), WEEK_LENGTH)]


def column_weekdays(today: datetime.date, range_mode: str) -> list[int]:
    """Дни недели столбцов (0 = Пн): календарный — Пн–Вс, скользящий — сегодня справа."""
    if range_mode == RANGE_ROLLING:
        return [(today.weekday() + 1 + i) % WEEK_LENGTH for i in range(WEEK_LENGTH)]
    return list(range(WEEK_LENGTH))


def _ink(data: dict, background: str) -> str:
    """Цвет номера дня: на пустых клетках приглушённый, на заливке — читаемый."""
    if data["kind"] in (KIND_FUTURE, KIND_DAY_OFF):
        return theme.COLOR_MUTED
    return ink_for(background)


class HeatmapWidget(BaseMiniWidget):
    """Сетка дней: неделя строкой или месяц по неделям, цвет по активности."""

    caption = WIDGET_CAPTION_HEATMAP

    # --- Каркас ---

    def _build(self):
        self._grid = tk.Frame(self.window, bg=theme.COLOR_DARK_BG, padx=PAD, pady=PAD)
        self._grid.pack()
        self._caption_label = tk.Label(
            self.window, text=self.caption,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption_label.pack(fill=tk.X, pady=(0, 4))

        # Что сейчас разложено: (сегодня, период, отсчёт). Меняется — сетка
        # пересобирается; иначе клетки только перекрашиваются.
        self._layout_key: tuple | None = None
        self._headers: list[tk.Label] = []
        self._cells: dict[tuple[int, int], tk.Label] = {}
        self._tooltips: dict[tuple[int, int], str] = {}
        # Сетка нужна уже здесь: базовый класс меряет окно до первого update,
        # чтобы вписать его в экран.
        self._ensure_layout(datetime.date.today())

    # --- Отрисовка ---

    def _ensure_layout(self, today: datetime.date) -> list[list]:
        """Раскладка под сегодня и настройки; пересобирает сетку, если она сменилась."""
        period = selected_period(self.opts)
        range_mode = selected_range(self.opts)
        rows = grid_rows(today, period, range_mode)

        key = (today, period, range_mode)
        if key != self._layout_key:
            self._rebuild_grid(rows, column_weekdays(today, range_mode))
            self._layout_key = key
        return rows

    def update(self, stats: dict):
        today = datetime.date.today()
        rows = self._ensure_layout(today)

        # Палитру переназначаем на каждом тике: мини-виджеты не перекрашивают
        # себя при смене темы, а так подхватят её со следующим обновлением.
        self._grid.configure(bg=theme.COLOR_DARK_BG)
        self._caption_label.configure(bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED)
        for header in self._headers:
            header.configure(bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED)

        # Прошлые дни читаются с диска на каждом обновлении, без кэша, как и у
        # недельной полосы: до 31 небольшого JSON раз в WIDGET_UPDATE_INTERVAL,
        # зато правка прошедшего дня через «Добавить активность» видна сразу.
        positions = [
            (row_index, col_index, date)
            for row_index, row in enumerate(rows)
            for col_index, date in enumerate(row)
            if date is not None
        ]
        days = build_days([date for _, _, date in positions], today, stats)
        for (row_index, col_index, _), data in zip(positions, days):
            background = cell_color(data)
            self._cells[(row_index, col_index)].configure(
                bg=background, fg=_ink(data, background),
                highlightbackground=border_color(data),
            )
            self._tooltips[(row_index, col_index)] = tooltip_text(data)

    def _rebuild_grid(self, rows: list[list], weekdays: list[int]):
        """Пересоздаёт заголовок и клетки под новую раскладку."""
        for child in self._grid.winfo_children():
            child.destroy()
        self._headers = []
        self._cells = {}
        self._tooltips = {}

        for col_index, weekday in enumerate(weekdays):
            header = tk.Label(
                self._grid, text=WEEKDAY_SHORT_NAMES[weekday],
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
                font=(FONT_FAMILY, HEADER_FONT_SIZE), width=CELL_WIDTH_CHARS,
            )
            header.grid(row=0, column=col_index, padx=CELL_GAP, pady=(0, 2))
            self._headers.append(header)

        for row_index, row in enumerate(rows, start=1):
            for col_index, date in enumerate(row):
                if date is None:
                    # Пустое место держит колонку той же ширины, что и клетка.
                    tk.Label(
                        self._grid, text="", width=CELL_WIDTH_CHARS,
                        bg=theme.COLOR_DARK_BG, font=(FONT_FAMILY, FONT_SIZE, "bold"),
                        highlightthickness=CELL_BORDER, highlightbackground=theme.COLOR_DARK_BG,
                    ).grid(row=row_index, column=col_index, padx=CELL_GAP, pady=CELL_GAP)
                    continue
                position = (row_index - 1, col_index)
                cell = tk.Label(
                    self._grid, text=str(date.day), width=CELL_WIDTH_CHARS,
                    bg=theme.COLOR_GRAY, fg=theme.COLOR_LIGHT_FG,
                    font=(FONT_FAMILY, FONT_SIZE, "bold"),
                    highlightthickness=CELL_BORDER, highlightbackground=theme.COLOR_DARK_BG,
                )
                cell.grid(row=row_index, column=col_index, padx=CELL_GAP, pady=CELL_GAP)
                # Подсказка читает текст через замыкание: перевешивать биндинг
                # на каждом тике незачем (как у недельной полосы).
                attach_tooltip(cell, lambda pos=position: self._tooltips.get(pos, ""))
                self._cells[position] = cell
