import os

# Пользовательские настройки
MAX_WORK_HOURS = 8

# Пути
LOG_DIR = os.path.join(os.path.expanduser("~"), "active_time")
STATE_FILE = os.path.join(LOG_DIR, "state.json")

# Текущий пользователь
USERNAME = os.getenv("USERNAME", "unknown")

# Форматы дат
DATE_KEY_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_DISPLAY_FORMAT = "%d.%m.%Y"
