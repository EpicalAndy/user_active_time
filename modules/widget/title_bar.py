"""
Заголовок виджета: название, кнопки окна, обратный отсчёт неактивности,
дополнительные метрики (процент, остаток до конца дня, до рекомендуемой нормы).

Drag-логика тоже здесь — окно двигается «за заголовок». Сам countdown с
миганием, режимом «норма выработана» и цветом рамки — в
`countdown_indicator`; заголовок отдаёт ему свой лейбл названия и
делегирует публичные методы, чтобы конфигуратор говорил только с заголовком.
"""

import tkinter as tk
from collections.abc import Callable

import config
from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from modules import theme
from modules.ui_utils import bold_pixel_width
from utility import format_percent
from .countdown_indicator import CountdownIndicator


def _format_hm(seconds: int) -> str:
    """Форматирует секунды в «Xч Yм» (без секунд)."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}ч {m}м"


class TitleBar:
    """Заголовок виджета. Управляет своими лейблами, countdown'ом и drag'ом.

    WIDGET_SHOW_TITLE_* читаются динамически через `rebuild_metric_labels()` —
    диалог настроек дёргает его после сохранения. Countdown создаётся один раз
    (см. `CountdownIndicator`).
    """

    def __init__(
        self,
        parent_window: tk.Toplevel,
        on_close: Callable[[], None],
        on_minimize: Callable[[], None],
        on_position_changed: Callable[[], None],
        on_collapse: Callable[[], None] | None = None,
    ):
        self._window = parent_window
        self._on_close = on_close
        self._on_minimize = on_minimize
        self._on_collapse = on_collapse
        self._on_position_changed = on_position_changed

        self._drag_x = 0
        self._drag_y = 0

        self._countdown: CountdownIndicator | None = None
        self._title_slot: tk.Frame | None = None
        self._title_percent_label: tk.Label | None = None
        self._title_remaining_label: tk.Label | None = None
        self._title_recommended_remaining_label: tk.Label | None = None

        self._build()

    def _build(self):
        self.frame = tk.Frame(self._window, bg=theme.COLOR_DARK_BG, height=30)
        self.frame.pack(fill=tk.X)
        self.frame.pack_propagate(False)

        # Слот фиксированной ширины: заголовок жирнеет при мигании, но слот
        # рассчитан по жирному начертанию — соседние метки не «прыгают».
        title_w = bold_pixel_width("Активность", MAIN_FONT_SIZE) + 2 * MAIN_FONT_SIZE + 2
        self._title_slot = tk.Frame(self.frame, bg=theme.COLOR_DARK_BG, width=title_w)
        self._title_slot.pack(side=tk.LEFT, fill=tk.Y)
        self._title_slot.pack_propagate(False)
        self._title_label = tk.Label(
            self._title_slot, text="Активность",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), padx=MAIN_FONT_SIZE,
        )
        self._title_label.pack(side=tk.LEFT, fill=tk.Y)

        # Порядок слева направо (как в Windows): «—» (в трей), «□» (до
        # заголовка с тулбаром), «✕» (закрыть). Пакуются справа-налево, поэтому «✕» —
        # первым (крайний справа), «—» — последним (крайний слева).
        self._close_btn = self._make_action_button("  ✕  ", self._on_close)
        self._close_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # «□» — свернуть до заголовка с тулбаром и обратно.
        if self._on_collapse is not None:
            self._collapse_btn = self._make_action_button("  □  ", self._on_collapse)
            self._collapse_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # «—» — свернуть в трей (без трея — свернуть до заголовка с тулбаром).
        self._minimize_btn = self._make_action_button("  —  ", self._on_minimize)
        self._minimize_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # Countdown ставит свой слот сразу за названием (пакуется LEFT до метрик).
        self._countdown = CountdownIndicator(self.frame, self._title_label)

        self._build_metric_labels()
        self._bind_drag()

    def _make_action_button(self, text: str, command: Callable[[], None]) -> tk.Label:
        btn = tk.Label(
            self.frame, text=text,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
        )
        btn.bind("<Button-1>", lambda _e: command())
        btn.bind("<Enter>", lambda _e: btn.configure(fg=theme.COLOR_HOVER))
        btn.bind("<Leave>", lambda _e: btn.configure(fg=theme.COLOR_LIGHT_FG))
        return btn

    def _build_metric_labels(self):
        if config.WIDGET_SHOW_TITLE_PERCENT:
            self._title_percent_label = self._make_metric_label()
        if config.WIDGET_SHOW_TITLE_REMAINING_TIME:
            self._title_remaining_label = self._make_metric_label()
        if config.WIDGET_SHOW_TITLE_RECOMMENDED_REMAINING:
            self._title_recommended_remaining_label = self._make_metric_label()

    def _make_metric_label(self) -> tk.Label:
        label = tk.Label(
            self.frame, text="",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        label.pack(side=tk.LEFT, fill=tk.Y)
        return label

    def _bind_drag(self):
        widgets: list[tk.Widget] = [self.frame, self._title_slot, self._title_label]
        widgets += self._countdown.drag_widgets()
        if self._title_percent_label:
            widgets.append(self._title_percent_label)
        if self._title_remaining_label:
            widgets.append(self._title_remaining_label)
        if self._title_recommended_remaining_label:
            widgets.append(self._title_recommended_remaining_label)
        for w in widgets:
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", lambda _e: self._on_position_changed())

    # --- Публичный API ---

    def update_metric_labels(self, stats: dict):
        """Обновляет тексты лейблов заголовка из stats."""
        if self._title_percent_label is not None:
            self._title_percent_label.configure(
                text=f" {format_percent(stats['activity_percent'])}",
            )
        if self._title_remaining_label is not None:
            self._title_remaining_label.configure(
                text=f" {_format_hm(max(0, stats.get('remaining_work_seconds', 0)))}",
            )
        if self._title_recommended_remaining_label is not None:
            self._title_recommended_remaining_label.configure(
                text=f" {_format_hm(max(0, stats.get('recommended_remaining_seconds', 0)))}",
            )

    def clear_metric_labels(self):
        """Очищает тексты лейблов (для режима «нерабочего дня»)."""
        for label in (
            self._title_percent_label,
            self._title_remaining_label,
            self._title_recommended_remaining_label,
        ):
            if label is not None:
                label.configure(text="")

    # --- Countdown и рамка: делегирование в CountdownIndicator ---

    def has_countdown(self) -> bool:
        return self._countdown.enabled

    def update_countdown(self, remaining: int | None):
        self._countdown.update(remaining)

    def clear_countdown(self):
        self._countdown.clear()

    def enter_goal_reached(self, show_placeholder: bool):
        self._countdown.enter_goal_reached(show_placeholder)

    def exit_goal_reached(self):
        self._countdown.exit_goal_reached()

    def set_progress_level(self, level: str):
        self._countdown.set_progress_level(level)

    def border_indicator_color(self) -> str | None:
        return self._countdown.border_color()

    def tick_blink(self):
        self._countdown.tick_blink()

    def rebuild_metric_labels(self):
        """Пересоздаёт опциональные лейблы заголовка по текущему config.

        Вызывать после сохранения настроек.
        """
        for attr in (
            "_title_percent_label",
            "_title_remaining_label",
            "_title_recommended_remaining_label",
        ):
            label = getattr(self, attr)
            if label is not None:
                label.destroy()
                setattr(self, attr, None)
        self._build_metric_labels()
        # Перепривязываем drag-обработчики к новым лейблам.
        self._bind_drag()

    # --- Drag ---

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self._window.winfo_x() + event.x - self._drag_x
        y = self._window.winfo_y() + event.y - self._drag_y
        self._window.geometry(f"+{x}+{y}")

    # --- Жизненный цикл ---

    def destroy(self):
        """Уничтожает фрейм заголовка (для пересборки при смене темы)."""
        self.frame.destroy()
