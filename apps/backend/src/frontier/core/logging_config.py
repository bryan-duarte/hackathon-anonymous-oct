import logging
from typing import Literal

import structlog

LogFormat = Literal["console", "json"]

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
URL_LOGGING_HTTP_CLIENTS = ("httpx", "httpx2", "httpcore")

SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]


def configure_logging(log_format: LogFormat) -> None:
    structlog.configure(
        processors=[*SHARED_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=SHARED_PROCESSORS,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                _renderer_for(log_format),
            ],
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
    _route_uvicorn_through_root()
    _silence_request_url_logs()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


def _renderer_for(log_format: LogFormat) -> structlog.typing.Processor:
    if log_format == "json":
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer()


def _route_uvicorn_through_root() -> None:
    for logger_name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def _silence_request_url_logs() -> None:
    for logger_name in URL_LOGGING_HTTP_CLIENTS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
