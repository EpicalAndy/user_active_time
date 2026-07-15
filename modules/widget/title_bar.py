"""
Заголовок виджета: название, мин/закрыть, обратный отсчёт неактивности,
дополнительные метрики (процент, остаток до конца дня, до рекомендуемой нормы).

Drag-логика тоже здесь — окно двигается «за заголовок».
"""

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable

import config
from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from modules import theme

# Состояния countdown'а для внешней индикации (например, рамка виджета).
_COUNTDOWN_NORMAL = "normal"
_COUNTDOWN_WARNING = "warning"
_COUNTDOWN_ZERO = "zero"


def _format_hm(seconds: int) -> str:
    """Форматирует секунды в «Xч Yм» (без секунд)."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}ч {m}м"


def _bold_pixel_width(text: str, size: int) -> int:
    """Ширина текста в пикселях при ЖИРНОМ начертании FONT_FAMILY этого размера.

    По этой (максимальной) ширине задаётся фиксированный слот лейбла, чтобы при
    переключении bold/normal раскладка не «прыгала». Требует существующего root.
    """
    return tkfont.Font(family=FONT_FAMILY, size=size, weight="bold").measure(text)


class TitleBar:
    """Заголовок виджета. Управляет своими лейблами, countdown'ом и drag'ом.

    INPUT_ACTIVITY_TIMEOUT читается из config один раз при создании TitleBar
    (сохраняем поведение исходной реализации: появление/исчезание countdown'а
    требует перезапуска приложения). Прочие WIDGET_SHOW_TITLE_* читаются
    динамически через `rebuild_metric_labels()` — диалог настроек умеет
    дёргать его после сохранения.
    """

    def __init__(
        self,
        parent_window: tk.Toplevel,
        on_close: Callable[[], None],
        on_minimize: Callable[[], None],
        on_position_changed: Callable[[], None],
    ):
        self._window = parent_window
        self._on_close = on_close
        self._on_minimize = on_minimize
        self._on_position_changed = on_position_changed

        self._countdown_blinking = False
        self._countdown_blink_bold = False
        self._countdown_state = _COUNTDOWN_NORMAL
        # Режим «норма выработана»: title и border всегда зелёные.
        # _goal_placeholder=True дополнительно заменяет countdown на «__:__».
        self._goal_reached = False
        self._goal_placeholder = False
        self._drag_x = 0
        self._drag_y = 0

        self._countdown_label: tk.Label | None = None
        self._countdown_slot: tk.Frame | None = None
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
        title_w = _bold_pixel_width("Активность", MAIN_FONT_SIZE) + 2 * MAIN_FONT_SIZE + 2
        self._title_slot = tk.Frame(self.frame, bg=theme.COLOR_DARK_BG, width=title_w)
        self._title_slot.pack(side=tk.LEFT, fill=tk.Y)
        self._title_slot.pack_propagate(False)
        self._title_label = tk.Label(
            self._title_slot, text="Активность",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), padx=MAIN_FONT_SIZE,
        )
        self._title_label.pack(side=tk.LEFT, fill=tk.Y)

        self._close_btn = self._make_action_button("  ✕  ", self._on_close)
        self._close_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self._minimize_btn = self._make_action_button("  —  ", self._on_minimize)
        self._minimize_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # Countdown-лейбл создаётся один раз — переключение
        # INPUT_ACTIVITY_TIMEOUT 0↔N требует перезапуска приложения.
        if config.INPUT_ACTIVITY_TIMEOUT > 0:
            # Слот фиксированной ширины по жирному «88:88»; лейбл центрирован,
            # поэтому жирный/мигающий текст растёт симметрично и не толкает
            # метрики справа.
            cd_w = max(
                _bold_pixel_width("88:88", MAIN_FONT_SIZE - 1),
                _bold_pixel_width("__:__", MAIN_FONT_SIZE - 1),
            ) + 4
            self._countdown_slot = tk.Frame(self.frame, bg=theme.COLOR_DARK_BG, width=cd_w)
            self._countdown_slot.pack(side=tk.LEFT, fill=tk.Y)
            self._countdown_slot.pack_propagate(False)
            self._countdown_label = tk.Label(
                self._countdown_slot, text="",
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._countdown_label.pack(expand=True)

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
        if self._countdown_slot:
            widgets.append(self._countdown_slot)
        if self._countdown_label:
            widgets.append(self._countdown_label)
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
                text=f" {stats['activity_percent']:.1f}%",
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

    def has_countdown(self) -> bool:
        return self._countdown_label is not None

    def update_countdown(self, remaining: int | None):
        """Применяет остаток до неактивности к countdown-лейблу.

        remaining: None — сессии нет / не отслеживается, скрываем текст.
        0 — пользователь неактивен, жирный красный без мигания.
        >0 — таймер обратного отсчёта; вблизи нуля включается мигание.

        Если виджет в режиме «норма выработана» (`_goal_reached`):
          * `_goal_placeholder=True` — обновление полностью пропускается
            (на месте countdown остаётся зелёный «__:__»);
          * иначе обновляются только цифры countdown, а цвет/шрифт
            заголовка не трогаются — заголовок остаётся зелёным.
        """
        if self._countdown_label is None:
            return
        if self._goal_placeholder:
            # Заполнитель уже отрисован в enter_goal_reached, не трогаем.
            return
        if remaining is None:
            self._countdown_label.configure(text="")
            self._countdown_blink_bold = False
            self._countdown_state = _COUNTDOWN_NORMAL
            return

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        if remaining == 0:
            # Неактивен — жирный красный, мигание выключено.
            self._countdown_state = _COUNTDOWN_ZERO
            self._countdown_blinking = False
            self._countdown_blink_bold = False
            self._countdown_label.configure(
                text=text, fg=theme.COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
            )
            self._apply_title_state(theme.COLOR_RED, weight="bold")
            return

        warning_threshold = config.COUNTDOWN_WARNING_SECONDS
        if warning_threshold > 0 and remaining <= warning_threshold:
            # Приближение к неактивности — мигание управляется тикером.
            self._countdown_state = _COUNTDOWN_WARNING
            self._countdown_label.configure(text=text, fg=theme.COLOR_LIGHT_FG)
            self._apply_title_state(theme.COLOR_LIGHT_FG, weight="normal")
            self._countdown_blinking = True
            return

        # Обычное состояние.
        self._countdown_state = _COUNTDOWN_NORMAL
        self._countdown_blinking = False
        self._countdown_blink_bold = False
        self._countdown_label.configure(
            text=text, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        self._apply_title_state(theme.COLOR_LIGHT_FG, weight="normal")

    def _apply_title_state(self, color: str, weight: str):
        """Красит заголовок «Активность» с учётом overriding'а goal_reached.

        Когда `_goal_reached` — заголовок принудительно зелёный нормальный.
        """
        if self._goal_reached:
            self._title_label.configure(
                fg=theme.COLOR_GREEN, font=(FONT_FAMILY, MAIN_FONT_SIZE),
            )
        else:
            self._title_label.configure(
                fg=color, font=(FONT_FAMILY, MAIN_FONT_SIZE, weight),
            )

    def clear_countdown(self):
        """Скрывает countdown (например, на нерабочем дне)."""
        if self._countdown_label is None:
            return
        self._countdown_label.configure(text="")
        self._countdown_blinking = False
        self._countdown_state = _COUNTDOWN_NORMAL
        # Сброс goal-состояния — на не-рабочем дне нет смысла его держать.
        self.exit_goal_reached()

    def enter_goal_reached(self, show_placeholder: bool):
        """Включает режим «норма выработана».

        Заголовок «Активность» и countdown-alert (рамка) становятся
        зелёными — это работает всегда, пока режим активен.

        show_placeholder=True — countdown-лейбл заменяется зелёным
        «__:__», и update_countdown игнорируется до выхода из режима.
        show_placeholder=False — countdown продолжает обновляться
        и мигать по обычным правилам; зелёным остаётся только заголовок.
        """
        if self._countdown_label is None:
            return
        self._goal_reached = True
        # Заголовок сразу красим зелёным; следующий update_countdown учтёт флаг.
        self._title_label.configure(
            fg=theme.COLOR_GREEN, font=(FONT_FAMILY, MAIN_FONT_SIZE),
        )
        if show_placeholder:
            self._goal_placeholder = True
            self._countdown_state = _COUNTDOWN_NORMAL
            self._countdown_blinking = False
            self._countdown_blink_bold = False
            self._countdown_label.configure(
                text="__:__", fg=theme.COLOR_GREEN,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
        else:
            self._goal_placeholder = False

    def exit_goal_reached(self):
        """Выключает режим «норма выработана» — возвращаемся к обычной логике."""
        self._goal_reached = False
        self._goal_placeholder = False

    def countdown_alert_color(self) -> str | None:
        """Цвет для внешней индикации (например, рамка окна).

        - Режим «норма выработана» → сплошной зелёный (имеет приоритет
          над red-предупреждениями). Отключается настройкой
          WIDGET_PROGRESS_HIGHLIGHT — тогда индикация идёт по обычным
          правилам countdown'а, а зелёным остаётся только заголовок.
        - Фаза нуля → сплошной красный (как у текста заголовка).
        - Фаза предупреждения, кадр «жирный красный» → красный.
        - Иначе → None (индикатор не нужен).
        """
        if self._goal_reached and config.WIDGET_PROGRESS_HIGHLIGHT:
            return theme.COLOR_GREEN
        if self._countdown_state == _COUNTDOWN_ZERO:
            return theme.COLOR_RED
        if self._countdown_state == _COUNTDOWN_WARNING and self._countdown_blink_bold:
            return theme.COLOR_RED
        return None

    def tick_blink(self):
        """Один шаг анимации мигания (вызывать каждые ~500мс)."""
        if not self._countdown_blinking or self._countdown_label is None:
            return
        self._countdown_blink_bold = not self._countdown_blink_bold
        weight = "bold" if self._countdown_blink_bold else "normal"
        fg = theme.COLOR_RED if self._countdown_blink_bold else theme.COLOR_LIGHT_FG
        self._countdown_label.configure(
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, weight), fg=fg,
        )
        # Заголовок мигает только если не в режиме «норма выработана».
        if not self._goal_reached:
            self._title_label.configure(
                font=(FONT_FAMILY, MAIN_FONT_SIZE, weight), fg=fg,
            )

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
