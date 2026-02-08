import os

# Пользовательские настройки
MAX_WORK_HOURS = 8

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
WIDGET_SHOW_SESSION_COUNT = True
WIDGET_SHOW_ACTIVITY_PERCENT = True

# Виджет: интервал обновления данных (в секундах)
WIDGET_UPDATE_INTERVAL = 60

# Форматы дат
DATE_KEY_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_DISPLAY_FORMAT = "%d.%m.%Y"
MAIN_FONT_SIZE = 10