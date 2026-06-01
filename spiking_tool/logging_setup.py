import logging
import sys
from datetime import datetime

LOG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_log_timestamp(when: datetime | None = None) -> str:
    return (when or datetime.now()).strftime(LOG_TIMESTAMP_FORMAT)


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
