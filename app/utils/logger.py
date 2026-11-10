import logging
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

# In-memory log buffer for Web Dashboard
LOG_BUFFER = deque(maxlen=200)

class BufferHandler(logging.Handler):
    """Logging handler that appends formatted logs to an in-memory deque."""
    def emit(self, record):
        try:
            msg = self.format(record)
            LOG_BUFFER.append({
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "message": msg
            })
        except Exception:
            pass

def setup_logger(name: str = "IQBot", log_file: str = "bot.log") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File output
    log_path = Path(__file__).resolve().parent.parent.parent / log_file
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # In-memory buffer handler for Web UI
    buf_handler = BufferHandler()
    buf_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(buf_handler)

    return logger

logger = setup_logger()

def get_recent_logs() -> list[dict]:
    return list(LOG_BUFFER)
