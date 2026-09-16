"""
Тексты интерфейса: подписи кнопок и меню, названия метрик, подсказки.

Всё, что пользователь читает на экране, живёт здесь (по-русски), чтобы
правка формулировки не требовала искать её по модулям. Цвета — в theme.py,
общие константы — в constants.py, Windows API — в winapi.py.
"""

from constants import APP_NAME
from version import __version__

# === Подсказки кнопок Тулбара ===

TOOLTIP_ADD_ACTIVE_TIME = "Добавить активное время"
TOOLTIP_OPEN_SETTINGS = "Настройки"
TOOLTIP_HELP = "Помощь"
TOOLTIP_WIDGETS = "Виджеты на рабочем столе"
TOOLTIP_COLLAPSE = "Свернуть до заголовка"
DEFAULT_MANUAL_ACTIVITY_DESCRIPTION = "Добавлено пользовательское время"

# === Меню «Помощь» ===

HELP_MENU_LABEL = "❓"
HELP_MENU_README = "Помощь"
HELP_MENU_DEV_GUIDE = "Техническая документация"
HELP_MENU_GITHUB = "github"
HELP_MENU_ABOUT = "О программе"
# «Помощь» и «Техническая документация» открывают HTML из docs/ (папка
# поставляется со сборкой — см. main.spec).
USER_GUIDE_PATH = "docs/user_guide.html"
DEV_GUIDE_PATH = "docs/developer_guide.html"
DOC_NOT_FOUND_TEXT = "Файл документации не найден:\n{path}"
GITHUB_URL = "https://github.com/EpicalAndy/user_active_time"

# Окно «О программе»: версия подставляется из version.__version__.
ABOUT_TITLE = "О программе"
ABOUT_DESCRIPTION = "Монитор активности пользователя Windows"

# === Меню «Отчёты» ===

REPORTS_MENU_LABEL = "Отчёты"
REPORT_MENU_TODAY = "Отчёт за сегодня"
REPORT_MENU_LAST = "Последний дневной отчёт"
REPORT_MENU_FOLDER = "Папка с отчётами"
REPORT_MENU_DAILY = "Дневной отчёт"
REPORT_MENU_HEATMAP = "Тепловая карта"
REPORT_MENU_PERIOD = "Отчёт за период"

# === Меню «Виджеты» (мини-виджеты на рабочем столе) ===

WIDGETS_MENU_LABEL = "🧩"

# === Меню «Инструменты» ===

TOOLS_MENU_LABEL = "🧰"
TOOLTIP_TOOLS = "Инструменты"

# Блокировка ввода
TOOL_INPUT_LOCK_TITLE = "Блокировка ввода"      # имя инструмента (настройки)
TOOL_INPUT_LOCK_LABEL = "Заблокировать ввод"   # пункт меню (действие)
INPUT_LOCK_OVERLAY_TITLE = "Ввод заблокирован"
INPUT_LOCK_OVERLAY_HINT = "Разблокировать: {hotkey}"
INPUT_LOCK_OVERLAY_LEFT = "осталось {time}"
INPUT_LOCK_HOTKEY_INVALID_TITLE = "Неверная комбинация"
INPUT_LOCK_HOTKEY_INVALID_TEXT = (
    "Не удалось разобрать комбинацию «{hotkey}».\n\n"
    "Нужен хотя бы один модификатор (ctrl, alt, shift, win) и одна клавиша, "
    "например: ctrl+alt+shift+U"
)
INPUT_LOCK_UNAVAILABLE_TITLE = "Блокировка недоступна"
INPUT_LOCK_UNAVAILABLE_TEXT = (
    "Мониторинг ввода отключён (таймаут неактивности = 0), "
    "а блокировка работает через те же хуки клавиатуры и мыши."
)
WIDGET_TYPE_ACTIVITY_PIE = "Активность (кольцо)"
WIDGET_TYPE_WORK_TIME_PIE = "Рабочее время (кольцо)"
WIDGET_TYPE_TIMELINE = "Таймлайн дня (диаграмма)"
WIDGET_TYPE_COUNTDOWN = "Счётчик активности (круг)"
WIDGET_TYPE_FREE_TIME_PIE = "Свободное время (кольцо)"
WIDGET_TYPE_BARS = "Метрики (полосы)"
WIDGET_TYPE_TIME_MARKS = "Отметки времени (список)"
WIDGET_TYPE_HEATMAP = "Тепловая карта (сетка)"
# Подписи под кольцами
WIDGET_CAPTION_ACTIVITY = "Активность"
WIDGET_CAPTION_WORK_TIME = "Рабочее время"
WIDGET_CAPTION_TIMELINE = "Таймлайн дня"
WIDGET_CAPTION_COUNTDOWN = "До неактивности"
WIDGET_CAPTION_FREE_TIME = "Свободное время"
WIDGET_CAPTION_BARS = "Метрики"
WIDGET_BARS_EMPTY = "Метрики не выбраны"
WIDGET_CAPTION_TIME_MARKS = "Отметки времени"
WIDGET_CAPTION_HEATMAP = "Тепловая карта"
WIDGET_MARKS_EMPTY = "Отметки не выбраны"
# Контекстное меню отдельного виджета (ПКМ)
WIDGET_REMOVE = "Убрать виджет"

# Диалог управления виджетами
WIDGETS_DIALOG_TITLE = "Виджеты"
WIDGETS_DIALOG_CLOSE = "Закрыть"

# Настройки виджета «Активность (кольцо)»
WIDGET_OPT_METRICS_LABEL = "Показывать"
WIDGET_OPT_CENTER_LABEL = "В центре"
WIDGET_OPT_CENTER_PERCENT = "Процент"
WIDGET_OPT_CENTER_TIME = "Время"
# Настройки тепловой карты: сколько дней и от чего отсчитывать.
WIDGET_OPT_PERIOD_LABEL = "Период"
WIDGET_OPT_PERIOD_WEEK = "Неделя"
WIDGET_OPT_PERIOD_MONTH = "Месяц"
WIDGET_OPT_RANGE_LABEL = "Отсчёт"
WIDGET_OPT_RANGE_CALENDAR = "Календарный"
WIDGET_OPT_RANGE_ROLLING = "Скользящий (по сегодня)"

# === Системный трей ===

# Всплывающая подсказка значка в трее — единственное место, где версия видна
# без открытия «О программе» (у виджета кастомный заголовок фиксированной ширины).
TRAY_TITLE = f"{APP_NAME} {__version__}"
TRAY_MENU_OPEN = "Открыть"
TRAY_MENU_QUIT = "Выход"

# Ошибки для быстрых пунктов «сегодня» / «последний»
REPORT_NO_DATA_TITLE = "Нет отчёта"
REPORT_NO_TODAY_TEXT = (
    "Отчёт за сегодня ещё не создан. Активность за день должна быть записана,"
    " чтобы появился JSON-файл."
)
REPORT_NO_PAST_TEXT = "В папке отчётов не найдено ни одного прошлого дневного отчёта."

# === Окно тепловой карты ===

HEATMAP_WINDOW_TITLE = "Тепловая карта активности"
HEATMAP_LEGEND_HIGH = "≥ {threshold}% (норма)"
HEATMAP_LEGEND_MID = "{min}–{max}%"
HEATMAP_LEGEND_LOW = "< {threshold}%"
HEATMAP_LEGEND_NO_DATA = "Нет данных"
HEATMAP_CLOSE = "Закрыть"
HEATMAP_TOOLTIP_NO_DATA = "Нет данных"
HEATMAP_TOOLTIP_ACTIVE = "Активное"
HEATMAP_TOOLTIP_NORM = "Норма активности"
HEATMAP_TOOLTIP_PERCENT = "Активность"

# === Календарь рабочего времени (планировщик-исключения) ===

SCHEDULE_CALENDAR_TITLE = "Календарь рабочего времени"
SCHEDULE_CLOSE = "Закрыть"
SCHEDULE_LEGEND_OVERRIDE = "Свой лимит"
SCHEDULE_LEGEND_DAYOFF = "Выходной"
SCHEDULE_LEGEND_DEFAULT = "По расписанию"
SCHEDULE_LEGEND_NOTE = "• заметка"
SCHEDULE_TOOLTIP_LIMIT = "Лимит"
SCHEDULE_TOOLTIP_DAYOFF = "Выходной"
SCHEDULE_TOOLTIP_DEFAULT = "По расписанию (день недели)"
SCHEDULE_TOOLTIP_HOURS_UNIT = "ч"

# Диалог настройки одного дня
DAY_DIALOG_TITLE = "Настройка дня"
DAY_DIALOG_HOURS_LABEL = "Лимит часов:"
DAY_DIALOG_DAYOFF = "Выходной (не отслеживать)"
DAY_DIALOG_USE_SCHEDULE = "По расписанию"
DAY_DIALOG_NOTE_LABEL = "Заметка:"
DAY_DIALOG_SAVE = "Сохранить"
DAY_DIALOG_CANCEL = "Отмена"

# Кнопка вызова календаря из диалога настроек
SETTINGS_TIMEOUT_LABEL = "Таймаут (сек)"
SETTINGS_TIMEOUT_HINT = "Таймаут неактивности; 0 — простой в этот день не считается"
SETTINGS_CALENDAR_BUTTON = "Календарь рабочего времени…"

# === Диалог «Отчёт за период» ===

PERIOD_DIALOG_TITLE = "Отчёт за период"
PERIOD_DIALOG_FROM_LABEL = "С:"
PERIOD_DIALOG_TO_LABEL = "По:"
PERIOD_DIALOG_DATE_PLACEHOLDER = "дд.мм.гггг"
PERIOD_DIALOG_BUILD_BUTTON = "Построить отчёт"
PERIOD_DIALOG_CALENDAR_BUTTON = "📅"
CALENDAR_POPUP_TITLE = "Календарь"
PERIOD_DIALOG_ERROR_INVALID = "Введите корректные даты в формате дд.мм.гггг"
PERIOD_DIALOG_ERROR_RANGE = "Дата «По» должна быть позже даты «С»"
PERIOD_DIALOG_ERROR_SAME_DAY = "Период должен охватывать больше одного дня"
PERIOD_DIALOG_ERROR_NO_DATA_TITLE = "Нет данных"
PERIOD_DIALOG_ERROR_NO_DATA_TEMPLATE = "В выбранном диапазоне нет ни одного отчёта."

# === Окно отчёта за период ===

PERIOD_REPORT_WINDOW_TITLE = "Отчёт за период"
PERIOD_REPORT_PERIOD_LABEL = "Период"
PERIOD_REPORT_TOTALS_LABEL = "Итого за период"
PERIOD_REPORT_BREAKDOWN_LABEL = "По дням"
PERIOD_REPORT_TOTAL_ACTIVE = "Общее активное время"
PERIOD_REPORT_TOTAL_WORK = "Общее время работы"
PERIOD_REPORT_TOTAL_MAX_WORK = "Максимальное рабочее время (норма)"
PERIOD_REPORT_TOTAL_ACTIVITY_NORM = "Норма активности (без перерыва)"
PERIOD_REPORT_DEFICIT_ACTIVE = "Недобор активности до рекомендуемой нормы"
PERIOD_REPORT_DEFICIT_WORK = "Недобор рабочего времени до нормы"
PERIOD_REPORT_COL_DATE = "Дата"
PERIOD_REPORT_COL_ACTIVE = "Активное"
PERIOD_REPORT_COL_WORK = "Работа"
PERIOD_REPORT_COL_MAX = "Норма"
PERIOD_REPORT_COL_ACTIVITY_NORM = "Норма акт."
PERIOD_REPORT_COL_ACTIVE_PCT = "Акт. %"
PERIOD_REPORT_COL_WORK_PCT = "Раб. %"
PERIOD_REPORT_CLOSE = "Закрыть"
PERIOD_REPORT_NO_NORM = "—"

# === Названия метрик ===
# *_FULL — расширенная форма для настроек; короткая — для тела виджета и отчёта.

METRIC_ACTIVE_TIME = "Активное время"
METRIC_SESSION_COUNT = "Сессий"
METRIC_SESSION_COUNT_FULL = "Количество сессий"
METRIC_ACTIVITY_PERCENT = "Активность"
METRIC_ACTIVITY_PERCENT_FULL = "Активность (%)"
METRIC_FULL_DAY_TIME = "Рабочее время"
METRIC_FULL_DAY_TIME_PERCENT_FULL = "Рабочее время (%)"
METRIC_REMAINING_TIME_FULL = "Осталось до конца дня"
METRIC_REMAINING_TIME_PERCENT_FULL = "Осталось до конца дня (%)"
METRIC_RECOMMENDED_REMAINING_FULL = "До рекомендуемой нормы"
METRIC_RECOMMENDED_REMAINING_PERCENT_FULL = "До рекомендуемой нормы (%)"
METRIC_FREE_TIME = "Свободное время"
METRIC_FREE_TIME_FULL = "Свободное время"
METRIC_FREE_TIME_PERCENT_FULL = "Свободное время (%)"
METRIC_WORK_DAY_END = "Конец дня"
METRIC_WORK_DAY_END_FULL = "Окончание рабочего дня"
# Расчётный момент выхода на рекомендуемую норму активности: пока порог
# не взят — прогноз «сейчас + остаток», после — фактическое время взятия.
METRIC_RECOMMENDED_ETA = "До рекомендуемой активности"
METRIC_RECOMMENDED_ETA_FULL = "Достижение нормы активности"
METRIC_BREAK_TIME = "Перерыв"
METRIC_ACTIVITY_NORM = "Норма активности"
METRIC_FIRST_LOGIN = "Начало рабочего дня"
METRIC_LAST_LOGOUT = "Конец рабочего дня"
METRIC_HIDE_OPTION = "Не отображать"
# Полоса-лента дня: строка в теле виджета и полоса в мини-виджете «Метрики» —
# тот же таймлайн, что и на кольце.
METRIC_TIMELINE = "Таймлайн"
METRIC_TIMELINE_FULL = "Таймлайн дня"
# Недельная полоса активности в теле виджета: семь квадратиков по дням.
METRIC_WEEK_ACTIVITY = "Неделя"
METRIC_WEEK_ACTIVITY_FULL = "Неделя активности"

# === Недельная полоса ===

WEEKDAY_SHORT_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

WEEK_MODE_LABEL = "Режим:"
WEEK_MODE_CALENDAR_LABEL = "Календарная (Пн–Вс)"
WEEK_MODE_ROLLING_LABEL = "Скользящая (7 дней по сегодня)"

WEEK_TOOLTIP_ACTIVITY = "Активность"
WEEK_TOOLTIP_WORK_TIME = "Рабочее время"
WEEK_TOOLTIP_NO_DATA = "Нет данных"
WEEK_TOOLTIP_DAY_OFF = "Нерабочий день"
WEEK_TOOLTIP_FUTURE = "Ещё не наступил"
WEEK_TOOLTIP_TODAY = "сегодня"

# === Таймлайн дня в теле виджета ===

TIMELINE_TOOLTIP_ACTIVITY = "Активность"
TIMELINE_TOOLTIP_OF_WORK_TIME = "рабочего времени"
TIMELINE_TOOLTIP_NO_DATA = "Сессий сегодня ещё не было"
