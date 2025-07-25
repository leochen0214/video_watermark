"""Logging configuration utilities."""

import logging
from .directories import get_logging_dir, create_dir


def init_logging():
    """Initialize logging configuration."""
    logs_dir = get_logging_dir()
    create_dir(logs_dir)
    app_log_file = str(logs_dir.joinpath("app.log"))
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(app_log_file),
            logging.StreamHandler()
        ],
        format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_person_log():
    """Get person log file path."""
    return get_logging_dir().joinpath("person.log")


def get_person_detail_json():
    """Get person detail JSON file path."""
    return get_logging_dir().joinpath("person_detail.json")