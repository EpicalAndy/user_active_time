"""
Тело виджета: список метрик с цветной подсветкой значений
и режим «нерабочего дня».
"""

import tkinter as tk

import config
from config import MAIN_FONT_SIZE
from constants import (
    COLOR_DARK_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_LIGHT_FG,
    COLOR_RED,
    COLOR_WHITE,
    COLOR_YELLOW,
    FONT_FAMILY,
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_PERCENT,
    METRIC_FULL_DAY_TIME,
    METRIC_FULL_DAY_TIME_PERCENT_FULL,
    METRIC_RECOMMENDED_REMAINING_FULL,
    METRIC_RECOMMENDED_REMAINING_PERCENT_FULL,
    METRIC_REMAINING_TIME_FULL,
    METRIC_SESSION_COUNT,
    METRIC_WORK_DAY_END_FULL,
)
from utility import format_duration_short

BODY_BG = COLOR_DARK_BG
METRIC_FG = COLOR_WHITE

# Шкалы цветовой подсветки: какая метрика по какой шкале считается.
_SCALE_ACTIVITY = "activity"
_SCALE_WORK_TIME = "work_time"
_METRIC_COLOR_SCALES: dict[str, str] = {
    "active_time": _SCALE_ACTIVITY,
    "activity_percent": _SCALE_ACTIVITY,
    "recommended_remaining": _SCALE_ACTIVITY,
    "recommended_remaining_percent": _SCALE_ACTIVITY,
    "full_day_time": _SCALE_WORK_TIME,
    "full_day_time_percent": _SCALE_WORK_TIME,
    "remaining_time": _SCALE_WORK_TIME,
    # session_count, work_day_end — без цветовой шкалы
}


def _color_for_percent(pct: float, recommended: float, minimum: float) -> str:
    """Зелёный/жёлтый/красный по двум порогам."""
    if pct >= recommended:
        return COLOR_GREEN
    if pct >= minimum:
        return COLOR_YELLOW
    return COLOR_RED


def _work_time_percent(stats: dict) -> float | None:
    """% общего рабочего времени относительно нормы; None если нормы нет."""
    max_work = stats.get("max_work_seconds", 0)
    if max_work <= 0:
        return None
    return stats["full_day_seconds"] / max_work * 100


def _recommended_remaining_percent(stats: dict) -> float | None:
    """Сколько осталось добрать до рекомендуемой нормы, в % от неё.

    Считается как `recommended_remaining / recommended × 100`,
    где `recommended = max_work × RECOMMENDED_ACTIVITY_THRESHOLD / 100`.
    None — если нормы или порога нет.
    """
    max_work = stats.get("max_work_seconds", 0)
    threshold = config.RECOMMENDED_ACTIVITY_THRESHOLD
    if max_work <= 0 or threshold <= 0:
        return None
    recommended = max_work * threshold / 100
    remaining = max(0, stats.get("recommended_remaining_seconds", 0))
    return remaining / recommended * 100


class WidgetBody:
    """Тело виджета: метрики + режим нерабочего дня.

    Создаётся «свежим» при пересборке тела (после изменения настроек) —
    набор отображаемых метрик читается из текущего config на конструировании.
    Пороги активности/рабочего времени читаются динамически при каждом
    обновлении (через атрибуты модуля config), поэтому изменение порогов
    через диалог настроек применяется на следующем тике без пересборки.
    """

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent, bg=BODY_BG, padx=0, pady=2)
        self._is_working_day = True

        # Сообщение для нерабочего дня (скрыто по умолчанию).
        self._day_off_label = tk.Label(
            self.frame, text="Сегодня не рабочий день",
            bg=COLOR_GRAY, fg=METRIC_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )

        self._metric_labels: dict[str, dict] = {}
        self._build_metrics()

    def _build_metrics(self):
        # Парные метрики «время + процент» склеиваются в одну строку, если
        # оба чекбокса включены. Процент-only остаётся отдельной строкой
        # (в позиции активности — после session_count, как было раньше).
        if config.WIDGET_SHOW_ACTIVE_TIME:
            self._metric_labels["active_time"] = self._add_metric(f"{METRIC_ACTIVE_TIME}:")
        if config.WIDGET_SHOW_SESSION_COUNT:
            self._metric_labels["session_count"] = self._add_metric(f"{METRIC_SESSION_COUNT}:")
        if config.WIDGET_SHOW_ACTIVITY_PERCENT and not config.WIDGET_SHOW_ACTIVE_TIME:
            self._metric_labels["activity_percent"] = self._add_metric(f"{METRIC_ACTIVITY_PERCENT}:")
        if config.WIDGET_SHOW_FULL_DAY_TIME:
            self._metric_labels["full_day_time"] = self._add_metric(f"{METRIC_FULL_DAY_TIME}:")
        if config.WIDGET_SHOW_FULL_DAY_TIME_PERCENT and not config.WIDGET_SHOW_FULL_DAY_TIME:
            self._metric_labels["full_day_time_percent"] = self._add_metric(f"{METRIC_FULL_DAY_TIME_PERCENT_FULL}:")
        if config.WIDGET_SHOW_REMAINING_TIME:
            self._metric_labels["remaining_time"] = self._add_metric(f"{METRIC_REMAINING_TIME_FULL}:")
        if config.WIDGET_SHOW_RECOMMENDED_REMAINING:
            self._metric_labels["recommended_remaining"] = self._add_metric(f"{METRIC_RECOMMENDED_REMAINING_FULL}:")
        if config.WIDGET_SHOW_RECOMMENDED_REMAINING_PERCENT and not config.WIDGET_SHOW_RECOMMENDED_REMAINING:
            self._metric_labels["recommended_remaining_percent"] = self._add_metric(
                f"{METRIC_RECOMMENDED_REMAINING_PERCENT_FULL}:",
            )
        if config.WIDGET_SHOW_WORK_DAY_END:
            self._metric_labels["work_day_end"] = self._add_metric(f"{METRIC_WORK_DAY_END_FULL}:")

    def _add_metric(self, label_text: str) -> dict:
        frame = tk.Frame(self.frame, bg=BODY_BG)
        frame.pack(fill=tk.X, pady=2)
        label = tk.Label(
            frame, text=label_text,
            bg=BODY_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
            padx=4,
        )
        label.pack(side=tk.LEFT, fill=tk.Y)
        value = tk.Label(
            frame, text="—",
            bg=BODY_BG, fg=METRIC_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.E,
            padx=4,
        )
        value.pack(side=tk.RIGHT, fill=tk.Y)
        return {"frame": frame, "label": label, "value": value}

    # --- Публичный API ---

    def update(self, stats: dict):
        """Применяет stats к телу: режим дня, значения, подсветка."""
        if not stats.get("is_working_day", True):
            self._show_day_off()
            return

        if not self._is_working_day:
            self._show_working_day()

        self._update_values(stats)
        self._apply_colors(stats)

    def is_working_day(self) -> bool:
        return self._is_working_day

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def destroy(self):
        self.frame.destroy()

    # --- Внутреннее ---

    def _update_values(self, stats: dict):
        labels = self._metric_labels
        if "active_time" in labels:
            text = format_duration_short(stats["active_seconds"])
            # Парная склейка: если включён парный процент — дописываем в скобках.
            if config.WIDGET_SHOW_ACTIVITY_PERCENT:
                text += f" ({stats['activity_percent']:.1f}%)"
            labels["active_time"]["value"].configure(text=text)
        if "session_count" in labels:
            labels["session_count"]["value"].configure(text=str(stats["session_count"]))
        if "activity_percent" in labels:
            labels["activity_percent"]["value"].configure(
                text=f"{stats['activity_percent']:.1f}%",
            )
        if "full_day_time" in labels:
            text = format_duration_short(stats["full_day_seconds"])
            if config.WIDGET_SHOW_FULL_DAY_TIME_PERCENT:
                pct = _work_time_percent(stats)
                if pct is not None:
                    text += f" ({pct:.1f}%)"
            labels["full_day_time"]["value"].configure(text=text)
        if "full_day_time_percent" in labels:
            pct = _work_time_percent(stats)
            labels["full_day_time_percent"]["value"].configure(
                text=f"{pct:.1f}%" if pct is not None else "—",
            )
        if "remaining_time" in labels:
            labels["remaining_time"]["value"].configure(
                text=format_duration_short(max(0, stats.get("remaining_work_seconds", 0))),
            )
        if "recommended_remaining" in labels:
            text = format_duration_short(max(0, stats.get("recommended_remaining_seconds", 0)))
            if config.WIDGET_SHOW_RECOMMENDED_REMAINING_PERCENT:
                pct = _recommended_remaining_percent(stats)
                if pct is not None:
                    text += f" ({pct:.1f}%)"
            labels["recommended_remaining"]["value"].configure(text=text)
        if "recommended_remaining_percent" in labels:
            pct = _recommended_remaining_percent(stats)
            labels["recommended_remaining_percent"]["value"].configure(
                text=f"{pct:.1f}%" if pct is not None else "—",
            )
        if "work_day_end" in labels:
            labels["work_day_end"]["value"].configure(text=stats.get("work_day_end") or "—")

    def _apply_colors(self, stats: dict):
        """Цвет идёт только на текст значения; фон и лейбл нейтральны."""
        for metric_id, widgets in self._metric_labels.items():
            color = self._metric_color(metric_id, stats) or METRIC_FG
            widgets["value"].configure(fg=color)

    def _metric_color(self, metric_id: str, stats: dict) -> str | None:
        scale = _METRIC_COLOR_SCALES.get(metric_id)
        if scale == _SCALE_ACTIVITY:
            return _color_for_percent(
                stats["activity_percent"],
                config.RECOMMENDED_ACTIVITY_THRESHOLD,
                config.MIN_ACTIVITY_THRESHOLD,
            )
        if scale == _SCALE_WORK_TIME:
            max_work = stats.get("max_work_seconds", 0)
            if max_work <= 0:
                return None
            pct = stats["full_day_seconds"] / max_work * 100
            return _color_for_percent(
                pct,
                config.RECOMMENDED_WORK_TIME_THRESHOLD,
                config.MIN_WORK_TIME_THRESHOLD,
            )
        return None

    def _show_day_off(self):
        self._is_working_day = False
        for widgets in self._metric_labels.values():
            widgets["frame"].pack_forget()
        # В нерабочем дне метрики скрыты, поэтому единственный сигнал — серый фон тела.
        self.frame.configure(bg=COLOR_GRAY)
        self._day_off_label.configure(bg=COLOR_GRAY)
        self._day_off_label.pack(fill=tk.X, pady=8)

    def _show_working_day(self):
        self._is_working_day = True
        self._day_off_label.pack_forget()
        # Восстанавливаем нейтральный фон тела (после возможного дня-выходного).
        self.frame.configure(bg=BODY_BG)
        for widgets in self._metric_labels.values():
            widgets["frame"].pack(fill=tk.X, pady=2)
