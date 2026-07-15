import os

# Пользовательские настройки.
#
# Конвенция hot-reload: значения, изменяемые через диалог настроек,
# должны читаться в коде как `config.X` (через `import config`), а не
# через `from config import X` — иначе name биндится при импорте модуля
# и обновления через SettingsDialog._apply_runtime не применяются до
# перезапуска. Сам диалог пишет в `config.X` напрямую, поэтому
# динамическое чтение — единственное, что нужно для горячего применения.

# Рабочие часы по умолчанию
DEFAULT_WORK_HOURS = 8

# Рабочие часы по дням недели (None = используется DEFAULT_WORK_HOURS, 0 = не отслеживать)
WORK_HOURS_BY_DAY = {
    "monday": 8.50,
    "tuesday": 8.50,
    "wednesday": 8.50,
    "thursday": 8.50,
    "friday": 7.50,
    "saturday": 1,
    "sunday": 1,
}

# Таймаут неактивности ввода (мышь/клавиатура) в секундах. 0 = отключено.
INPUT_ACTIVITY_TIMEOUT = 300

# Считать движение мыши за активность (клики и скролл отслеживаются всегда)
TRACK_MOUSE_MOVE = False

# Порог предупреждения о скором переходе в неактивность (секунды). 0 = отключено.
COUNTDOWN_WARNING_SECONDS = 60

# Пути
LOG_DIR = os.path.join(os.path.expanduser("~"), "active_time")
STATE_FILE = os.path.join(LOG_DIR, "state.json")
# Календарь-исключения: переопределения дневного лимита и заметки по конкретным датам
CALENDAR_FILE = os.path.join(LOG_DIR, "work_calendar.json")

# Текущий пользователь
USERNAME = os.getenv("USERNAME", "unknown")

# Пороги активности (в процентах от нормы)
RECOMMENDED_ACTIVITY_THRESHOLD = 80
MIN_ACTIVITY_THRESHOLD = 70

# Пороги общего рабочего времени (в процентах от нормы).
# Используются для подсветки метрик «Рабочее время» и «Осталось до конца дня».
RECOMMENDED_WORK_TIME_THRESHOLD = 100
MIN_WORK_TIME_THRESHOLD = 80

# Звуковое уведомление при достижении рекомендуемого порога активности
SOUND_NOTIFICATION = False

# Тиканье часов в предупредительной фазе обратного отсчёта неактивности
COUNTDOWN_TICK_SOUND = False

# Скрывать обратный отсчёт неактивности после достижения рекомендуемой нормы
# (норма заработана — больше не нужно уведомлять о приближении к простою)
STOP_COUNTDOWN_AT_RECOMMENDED = False

# Подсвечивать рамку виджета зелёным при достижении рекомендуемой нормы
WIDGET_PROGRESS_HIGHLIGHT = True

# Виджет: какие метрики отображать
WIDGET_SHOW_ACTIVE_TIME = True
WIDGET_SHOW_SESSION_COUNT = False
WIDGET_SHOW_ACTIVITY_PERCENT = True
WIDGET_SHOW_FULL_DAY_TIME = False
WIDGET_SHOW_FULL_DAY_TIME_PERCENT = False
WIDGET_SHOW_REMAINING_TIME = True
WIDGET_SHOW_REMAINING_TIME_PERCENT = False
WIDGET_SHOW_RECOMMENDED_REMAINING = False
WIDGET_SHOW_RECOMMENDED_REMAINING_PERCENT = False
WIDGET_SHOW_WORK_DAY_END = False
WIDGET_SHOW_TITLE_PERCENT = True
WIDGET_SHOW_TITLE_REMAINING_TIME = False
WIDGET_SHOW_TITLE_RECOMMENDED_REMAINING = False

# Виджет: интервал обновления данных (в секундах)
WIDGET_UPDATE_INTERVAL = 60

# Интервал промежуточного сохранения сессии в секундах (защита от потери данных). 0 = отключено.
CHECKPOINT_INTERVAL = 60

# Форматы дат
DATE_KEY_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_DISPLAY_FORMAT = "%d.%m.%Y"

# Текст
MAIN_FONT_SIZE = 10

# Тема оформления интерфейса: "dark" (тёмная) или "light" (светлая).
# Палитры заданы в theme.py.
THEME = "dark"