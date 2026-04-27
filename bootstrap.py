"""
Инициализация пользовательского config.py.

config.py в проекте — только дефолтные настройки. При первом запуске копируется
в ~/active_time/config.py. Затем эта папка вставляется в начало sys.path,
поэтому `import config` в любом модуле возвращает пользовательскую копию.

Должен быть вызван из main.py до импортов, читающих config.
"""

import os
import shutil
import sys

# Путь должен совпадать с LOG_DIR в config.py. Дублируется здесь намеренно:
# bootstrap решает, из какого файла грузить config, поэтому LOG_DIR ещё нельзя
# импортировать.
USER_LOG_DIR = os.path.join(os.path.expanduser("~"), "active_time")
USER_CONFIG_PATH = os.path.join(USER_LOG_DIR, "config.py")

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_DIR, "config.py")


def setup_user_config():
    """Создаёт пользовательский config.py из дефолтов и подключает его как `config`."""
    os.makedirs(USER_LOG_DIR, exist_ok=True)
    if not os.path.exists(USER_CONFIG_PATH):
        shutil.copy(_DEFAULT_CONFIG_PATH, USER_CONFIG_PATH)
        print(f"[BOOTSTRAP] Создан пользовательский конфиг: {USER_CONFIG_PATH}")
    if USER_LOG_DIR not in sys.path:
        sys.path.insert(0, USER_LOG_DIR)
