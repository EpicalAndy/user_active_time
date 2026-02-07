"""
Точка входа: монитор сессий Windows + виджет активности
"""

import os
import sys
import threading

# Корневая директория проекта в sys.path для импортов из modules/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.session_monitor import main as run_monitor
from modules.widget import ActivityWidget, is_widget_enabled


def main():
    if is_widget_enabled():
        from modules.session_monitor import get_current_stats, request_stop

        monitor_thread = threading.Thread(
            target=run_monitor, daemon=True, name="SessionMonitor"
        )
        monitor_thread.start()

        widget = ActivityWidget(stats_provider=get_current_stats)
        try:
            widget.run()
        except KeyboardInterrupt:
            pass
        finally:
            request_stop()
            monitor_thread.join(timeout=5)
    else:
        run_monitor()


if __name__ == "__main__":
    main()
