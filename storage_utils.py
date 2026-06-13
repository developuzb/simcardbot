"""Xavfsiz, atomik JSON yozish yordamchisi.

Yozish jarayonida jarayon to'xtab qolsa fayl buzilmasligi uchun
avval temp faylga yoziladi, keyin os.replace() bilan atomik almashtirish
amalga oshiriladi. Windows va Linux'da xavfsiz ishlaydi.
"""
import json
import os
import tempfile
import logging

logger = logging.getLogger(__name__)


def atomic_write_json(path: str, data, *, ensure_ascii: bool = False, indent=None) -> None:
    """JSON ma'lumotni atomik tarzda faylga yozadi.

    Algoritm:
    1. Fayl bilan bir papkada vaqtinchalik fayl yaratiladi.
    2. Ma'lumot vaqtinchalik faylga yoziladi va disk'ga saqlanadi (fsync).
    3. os.replace() bilan maqsad faylga atomik ko'chiriladi.

    Agar yozish o'rtasida jarayon o'lsa, maqsad fayl o'zgarmaydi —
    faqat vaqtinchalik fayl qoladi (keyingi ishga tushishda o'chirib tashlash mumkin).
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Vaqtinchalik faylni tozalaymiz
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
