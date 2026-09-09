"""
Инструмент «Блокировка ввода».

Разложен по слоям: hotkey (чистая логика комбинации) → blocker (фильтр в
hook-потоке) → overlay (плашка) → controller (жизненный цикл). Наружу
торчит только класс инструмента.
"""

from .controller import InputLockTool

__all__ = ["InputLockTool"]
