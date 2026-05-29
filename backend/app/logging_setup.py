import logging

from rich.console import Console
from rich.logging import RichHandler

_is_configured = False


def setup_logging() -> None:
    global _is_configured
    if _is_configured:
        return

    console = Console()
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(isinstance(existing, RichHandler) for existing in root_logger.handlers):
        root_logger.addHandler(handler)

    runtime_logger = logging.getLogger("orbitflow.runtime")
    runtime_logger.setLevel(logging.INFO)
    runtime_logger.propagate = False
    runtime_logger.handlers = [handler]

    _is_configured = True

