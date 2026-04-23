import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import Settings

def setup_logging(settings: Settings) -> None:
    log_cfg = settings.log
    log_level = logging.DEBUG if settings.debug else getattr(logging, log_cfg.level.upper())
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handlers: list[logging.Handler] = []
    # will show log in terminal, even in docker, we can use docker logs <container_name>
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    handlers.append(console_handler)

    if log_cfg.file_path:
        file_handler = RotatingFileHandler(
            filename=log_cfg.file_path,
            maxBytes=log_cfg.max_bytes,
            backupCount=log_cfg.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(log_format)
        handlers.append(file_handler)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)

    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)