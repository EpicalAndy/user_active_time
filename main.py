"""
Точка входа: монитор сессий Windows + виджет активности
"""

import os
import sys
import threading

# Корневая директория проекта в sys.path для импортов из modules/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Консоль — до первого print (bootstrap сам печатает), пользовательский
# config.py — до любых импортов, читающих config.
from bootstrap import setup_console, setup_user_config
setup_console()
setup_user_config()

from modules.session_monitor import get_current_stats, request_stop
from modules.session_monitor import main as run_monitor
from modules.widget import App


def main():
    monitor_thread = threading.Thread(
        target=run_monitor, daemon=True, name="SessionMonitor"
    )
    monitor_thread.start()

    app = App(stats_provider=get_current_stats)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        request_stop()
        monitor_thread.join(timeout=5)


if __name__ == "__main__":
    main()
