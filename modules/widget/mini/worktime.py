"""
Мини-виджет «Рабочее время» — кольцо доли отработанного времени от нормы.

Заполнение = общее рабочее время (от первого логина до сейчас) / норма, цвет —
по порогам рабочего времени. В центре: процент или общее рабочее время.
"""

import config
from constants import WIDGET_CAPTION_WORK_TIME
from .ring import RingWidget


class WorkTimePieWidget(RingWidget):
    """Кольцо рабочего времени."""

    caption = WIDGET_CAPTION_WORK_TIME

    def _fraction(self, stats: dict) -> float | None:
        max_work = stats.get("max_work_seconds", 0)
        if max_work <= 0:
            return None
        return stats.get("full_day_seconds", 0) / max_work * 100

    def _time_seconds(self, stats: dict) -> int:
        return int(stats.get("full_day_seconds", 0))

    def _thresholds(self) -> tuple[float, float]:
        return (
            config.RECOMMENDED_WORK_TIME_THRESHOLD,
            config.MIN_WORK_TIME_THRESHOLD,
        )
