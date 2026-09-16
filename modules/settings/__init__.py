"""
Настройки приложения: диалог, его вкладки и запись в config.py.

Внешние потребители импортируют SettingsDialog отсюда:
    from modules.settings import SettingsDialog
"""

from .dialog import SettingsDialog

__all__ = ["SettingsDialog"]
