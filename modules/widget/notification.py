"""
Генерация и проигрывание звукового уведомления виджета.

WAV генерируется один раз при импорте и кладётся в LOG_DIR.
"""

import math
import os
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


_NOTIFICATION_WAV_PATH = _generate_notification_wav()


def play_notification():
    """Асинхронно проигрывает звук уведомления."""
    winsound.PlaySound(
        _NOTIFICATION_WAV_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC,
    )
