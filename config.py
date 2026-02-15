import os

# Пользовательские настройки

# Рабочие часы по умолчанию
DEFAULT_WORK_HOURS = 8

# Рабочие часы по дням недели (None = используется DEFAULT_WORK_HOURS, 0 = не отслеживать)
WORK_HOURS_BY_DAY = {
    "monday": None,
    "tuesday": None,
    "wednesday": None,
    "thursday": None,
    "friday": 7,
    "saturday": 0,
    "sunday": 0,
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

# Текущий пользователь
USERNAME = os.getenv("USERNAME", "unknown")

# Пороги активности (в процентах)
RECOMMENDED_ACTIVITY_THRESHOLD = 80
MIN_ACTIVITY_THRESHOLD = 70

# Виджет: какие метрики отображать
WIDGET_SHOW_ACTIVE_TIME = True
WIDGET_SHOW_SESSION_COUNT = False
WIDGET_SHOW_ACTIVITY_PERCENT = True
WIDGET_SHOW_FULL_DAY_TIME = True

# Виджет: интервал обновления данных (в секундах)
WIDGET_UPDATE_INTERVAL = 60

# Форматы дат
DATE_KEY_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_DISPLAY_FORMAT = "%d.%m.%Y"

# Текст
MAIN_FONT_SIZE = 10