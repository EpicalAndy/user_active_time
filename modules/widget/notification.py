"""
Генерация и проигрывание звукового уведомления виджета.

WAV генерируется один раз при импорте и кладётся в LOG_DIR.
"""

import itertools
import math
import os
import random
import struct
import wave
import winsound

from config import LOG_DIR


def _generate_notification_wav() -> str:
    """Генерирует приятный звук уведомления (~2.5с) — восходящий аккорд."""
    sample_rate = 22050
    duration = 2.5
    n_samples = int(sample_rate * duration)

    notes = [
        (523.25, 0.0, 0.9),    # C5
        (659.25, 0.3, 1.2),    # E5
        (783.99, 0.6, 1.5),    # G5
        (1046.50, 1.0, 2.5),   # C6 (fade out)
    ]

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        value = 0.0
        for freq, start, end in notes:
            if start <= t <= end:
                local_t = (t - start) / (end - start)
                envelope = math.sin(math.pi * local_t)
                value += math.sin(2 * math.pi * freq * t) * envelope * 0.2
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))

    wav_path = os.path.join(LOG_DIR, "notification.wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))
    return wav_path


def _generate_clock_tick_wav(filename: str, resonance: float, seed: int) -> str:
    """Генерирует механический щелчок часов (~50 мс).

    Звук настоящих ходиков — это короткий широкополосный «щелчок» (импульс
    отфильтрованного шума), а не чистая высокая синусоида: именно из-за
    синусоиды старый сигнал звучал электронно и «потусторонне». Здесь шумовой
    щелчок задаёт характерную атаку, а затухающий резонанс — «деревянное» тело.
    """
    sample_rate = 22050
    duration = 0.05
    n_samples = int(sample_rate * duration)

    rnd = random.Random(seed)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Широкополосный «снап»: шум с очень быстрым затуханием — резкая атака.
        snap = rnd.uniform(-1.0, 1.0) * math.exp(-t * 220)
        # Затухающий резонанс даёт «тело» щелчка (тик выше, ток ниже).
        body = math.sin(2 * math.pi * resonance * t) * math.exp(-t * 90)
        value = (snap * 0.7 + body * 0.5) * 0.45
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))

    wav_path = os.path.join(LOG_DIR, filename)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))
    return wav_path


_NOTIFICATION_WAV_PATH = _generate_notification_wav()
# Две слегка разные высоты — классическое чередование «тик… так…».
_TICK_WAV_PATH = _generate_clock_tick_wav("tick.wav", resonance=1700, seed=1)
_TOCK_WAV_PATH = _generate_clock_tick_wav("tock.wav", resonance=1100, seed=2)
# Чередуем тик/так при каждом вызове play_tick().
_tick_tock_cycle = itertools.cycle((_TICK_WAV_PATH, _TOCK_WAV_PATH))


def play_notification():
    """Асинхронно проигрывает звук уведомления."""
    winsound.PlaySound(
        _NOTIFICATION_WAV_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC,
    )


def play_tick():
    """Асинхронно проигрывает щелчок часов, чередуя «тик» и «так»."""
    winsound.PlaySound(
        next(_tick_tock_cycle), winsound.SND_FILENAME | winsound.SND_ASYNC,
    )
