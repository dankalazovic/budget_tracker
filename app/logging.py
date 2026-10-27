import sys

from loguru import logger


_configured = False


def configure_logging(app):
    global _configured
    if _configured:
        return

    # Uklanjamo samo Loguru podrazumevani sink, bez diranja dodatih testnih sinkova.
    try:
        logger.remove(0)
    except ValueError:
        pass

    logger.add(
        sys.stderr,
        level=app.config.get("LOG_LEVEL", "INFO"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        serialize=False,
        backtrace=False,
        diagnose=False,
    )
    _configured = True
