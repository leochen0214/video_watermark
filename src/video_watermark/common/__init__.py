"""Common utilities and configuration for video_watermark."""


from .directories import *
from .file_operations import *
from .environment import *
from .logging_config import *
from .person_management import *
from .video_operations import *

# Main initialization function
def init():
    """Initialize the application environment and logging."""
    init_env()
    init_logging()