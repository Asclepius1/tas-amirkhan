import logging
import sys


def setup_logging(level=logging.DEBUG):
    """Configure root logger to output to console for now."""
    root = logging.getLogger()
    if root.handlers:
        return root

    root.setLevel(level)
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    # Подавление слишком подробных логов от сторонних библиотек
    noisy_loggers = [
        'python_multipart.multipart',
        'urllib3',
        'asyncio',
        'uvicorn.access',
        'uvicorn.error'
    ]
    for nl in noisy_loggers:
        logging.getLogger(nl).setLevel(logging.WARNING)
    return root


def get_logger(name: str):
    setup_logging()
    return logging.getLogger(name)
