# data.py
import os
import random

# Папка с картинками в репозитории
IMAGE_DIR = "images"
EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

# Очередь, чтобы не повторять картинки до полного цикла
_queue = []

def _rebuild_queue():
    files = [
        os.path.join(IMAGE_DIR, f)
        for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith(EXTS)
    ]
    if not files:
        raise FileNotFoundError("В папке images нет картинок")
    random.shuffle(files)
    return files

def next_image():
    """Вернёт путь до следующей картинки, без повторов до исчерпания очереди."""
    global _queue
    if not _queue:
        _queue = _rebuild_queue()
    return _queue.pop()
