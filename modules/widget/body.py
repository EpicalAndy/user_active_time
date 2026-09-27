"""
Тело виджета: список метрик с цветной подсветкой значений
и режим «нерабочего дня».

Какие метрики есть, их подписи, текст и цвет — в каталоге (`metrics`); тело
только выбирает включённые флагами config и раскладывает их строками.
"""

import tkinter as tk

import config
from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from modules import theme
from .day_timeline import DayTimelineRow
from .metrics import METRICS


class WidgetBody:
    """Тело виджета: метрики + режим нерабочего дня.

    Создаётся «свежим» при пересборке тела (после изменения настроек) —
    набор отображаемых метрик читается из текущего config на конструировании.
    Пороги активности/рабочего времени читаются динамически при каждом
    обновлении (через атрибуты модуля config), поэтому изменение порогов
    через диалог настроек применяется на следующем тике без пересборки.
    """

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG, padx=0, pady=2)
        self._is_working_day = True

        # Сообщение для нерабочего дня (скрыто по умолчанию).
        self._day_off_label = tk.Label(
            self.frame, text="Сегодня не рабочий день",
            bg=theme.COLOR_GRAY, fg=theme.COLOR_WHITE,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )

        self._metric_labels: dict[str, dict] = {}
        # Таймлайн дня — строка тела, но не «лейбл + значение», а полоса:
        # живёт отдельно от _metric_labels и рисует себя сама.
        self._timeline: DayTimelineRow | None = None
        self._build_metrics()

    def _build_metrics(self):
        # Строка на метрику каталога, в его порядке. Пара «время + процент»
        # склеивается в одну строку, если включены оба флага; без значения
        # остаётся строка с одним процентом (со своей подписью).
        for metric in METRICS:
            show_value = getattr(config, metric.show_attr)
            show_percent = bool(metric.show_percent_attr) and getattr(config, metric.show_percent_attr)
            if not (show_value or show_percent):
                continue
            label = metric.label if show_value else metric.percent_label
            row = self._add_metric(f"{label}:")
            row.update(metric=metric, show_value=show_value, show_percent=show_percent)
            self._metric_labels[metric.key] = row
        # Последней строкой: лента дня подводит итог цифрам над ней.
        if config.WIDGET_SHOW_DAY_TIMELINE:
            self._timeline = DayTimelineRow(self.frame)
            self._timeline.pack(fill=tk.X, pady=2)

    def _add_metric(self, label_text: str) -> dict:
        frame = tk.Frame(self.frame, bg=theme.COLOR_DARK_BG)
        frame.pack(fill=tk.X, pady=2)
        label = tk.Label(
            frame, text=label_text,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
            padx=4,
        )
        label.pack(side=tk.LEFT, fill=tk.Y)
        value = tk.Label(
            frame, text="—",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
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
        if self._timeline is not None:
            self._timeline.update(stats)

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
        for row in self._metric_labels.values():
            text = row["metric"].render(
                stats, value=row["show_value"], percent=row["show_percent"],
            )
            row["value"].configure(text=text)

    def _apply_colors(self, stats: dict):
        """Цвет идёт только на текст значения; фон и лейбл нейтральны."""
        for row in self._metric_labels.values():
            color = row["metric"].color(stats) or theme.COLOR_LIGHT_FG
            row["value"].configure(fg=color)

    def _show_day_off(self):
        self._is_working_day = False
        for widgets in self._metric_labels.values():
            widgets["frame"].pack_forget()
        if self._timeline is not None:
            self._timeline.pack_forget()
        # В нерабочем дне метрики скрыты, поэтому единственный сигнал — серый фон тела.
        self.frame.configure(bg=theme.COLOR_GRAY)
        self._day_off_label.configure(bg=theme.COLOR_GRAY)
        self._day_off_label.pack(fill=tk.X, pady=8)

    def _show_working_day(self):
        self._is_working_day = True
        self._day_off_label.pack_forget()
        # Восстанавливаем нейтральный фон тела (после возможного дня-выходного).
        self.frame.configure(bg=theme.COLOR_DARK_BG)
        for widgets in self._metric_labels.values():
            widgets["frame"].pack(fill=tk.X, pady=2)
        if self._timeline is not None:
            self._timeline.pack(fill=tk.X, pady=2)
