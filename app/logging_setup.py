"""Central logging setup: one new log file per application start."""

import logging
import re
from datetime import datetime
from pathlib import Path

from app.config import LoggingConfig

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

logger = logging.getLogger(__name__)


def _log_pattern(suffix: str) -> re.Pattern:
    return re.compile(rf"app_\d{{8}}_\d{{6}}{re.escape(suffix)}\.log")


def _prune_old_logs(directory: Path, keep_existing: int, suffix: str) -> None:
    pattern = _log_pattern(suffix)
    files = sorted(p for p in directory.iterdir() if pattern.fullmatch(p.name))
    for old in files[: max(0, len(files) - keep_existing)]:
        old.unlink(missing_ok=True)


def setup_logging(config: LoggingConfig, suffix: str = "") -> Path:
    """Configure the root logger and return the path of the new log file.

    Keeps at most ``retention_count`` files per kind (live / test, distinguished by
    ``suffix``): before creating the new one, only the ``retention_count - 1`` newest
    existing files of that kind are retained.
    """
    config.directory.mkdir(parents=True, exist_ok=True)
    _prune_old_logs(config.directory, config.retention_count - 1, suffix)

    log_file = config.directory / f"app_{datetime.now():%Y%m%d_%H%M%S}{suffix}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._texxem = True

    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_texxem", False):
            root.removeHandler(existing)
            existing.close()
    root.addHandler(handler)
    root.setLevel(config.level)

    logger.info("Logging initialised, log file: %s", log_file)
    return log_file
