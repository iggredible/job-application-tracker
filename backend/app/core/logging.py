import logging
import sys

REQUEST_LOGGER = "app.request"


def configure_logging() -> None:
    """Send the request logger's messages to stdout as bare lines.

    The request middleware already formats each message as one JSON object, so the handler
    adds nothing around it.
    """
    logger = logging.getLogger(REQUEST_LOGGER)
    logger.setLevel(logging.INFO)
    if not any(getattr(h, "_app_request", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._app_request = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
