import logging
from pathlib import Path

def get_logger(name: str, log_file: str = None, log_level: int = logging.INFO) -> logging.Logger:
    """
    Get a logger with the given name and log level.
    Args:
        name: The name of the logger.
        log_file: The file to log to.
        log_level: The level to log at.
    Returns:
        A logger with the given name and log level.
    """
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(log_level)

    # log directory
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if not log_file:
        log_file = f"{name}.log"
    if not log_file.endswith(".log"):
        log_file += ".log"
    file_path = log_dir / log_file

    # formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # file handler
    file_handler = logging.FileHandler(file_path)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger