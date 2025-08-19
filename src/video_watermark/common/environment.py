"""Environment configuration utilities."""

import os

from .directories import find_project_root
from .file_operations import read_all_lines


def init_env():
    """Initialize environment variables from env.txt file."""
    p = find_project_root().joinpath('env.txt')
    lines = read_all_lines(p)
    print(lines)
    if not lines:
        return
    for line in lines:
        k, v = (part.strip() for part in line.split('='))
        if k != '' and v != '':
            os.environ[k] = v


def is_test():
    """Check if running in test mode."""
    t = __get_env('IS_TEST', '0')
    return t == '1'


def is_sync_to_baidu():
    """Check if should sync to Baidu."""
    t = __get_env('IS_SYNC_TO_BAIDU', '0')
    return t == '1'


def get_invisible_watermark_step():
    """Get invisible watermark step."""
    t = __get_env('INVISIBLE_WATERMARK_STEP', '1')
    return int(t)


def get_video_format():
    """Get video format."""
    return __get_env('RECORD_VIDEO_FORMAT', '.MTS')


def get_watermark_logo_text():
    """Get watermark logo text"""
    return __get_env('WATERMARK_LOGO_TEXT', '')


def is_need_add_invisible_watermark(i):
    """Check if need to add invisible watermark."""
    step = get_invisible_watermark_step()
    if step == 0:
        return False
    if step == 1:
        return True
    return i % step == 0


def is_delete_after_upload_success():
    """Check if should delete after upload success."""
    return __get_env('DELETE_AFTER_UPLOAD_SUCCESS', '0') == '1'


def keep_stage1_file():
    """Check if should keep stage1 files."""
    return __get_env('KEEP_STAGE1_VIDEO', '1') == '1'


def is_compress_audio():
    """Check if should compress audio files."""
    return __get_env('COMPRESS_AUDIO', '0') == '1'


def get_compress_audio_options():
    """Get audio compression options."""
    return __get_env('COMPRESS_AUDIO_OPTIONS', '')

def is_keep_origin_quality():
    """keep video origin quality, not compress it"""
    return __get_env('KEEP_ORIGIN_QUALITY', '0') == '1'

def get_ffmpeg_options():
    """Get ffmpeg custom options."""
    return __get_env('FFMPEG_OPTIONS', '')

def get_result_video_type():
    """Get result video type, default is mp4."""
    return __get_env('RESULT_VIDEO_TYPE', '.mp4')


def get_upload_timeout() -> int:
    """上传超时时间,默认3600s"""
    return int(__get_env('UPLOAD_TIMEOUT', '3600'))

def get_root_remote_dir():
    return __get_env('REMOTE_DIR', '/apps/bypy')

def get_current_course_name():
    return __get_env('CURRENT_COURSE_NAME', '')

def get_validity_period():
    return __get_env('VALIDITY_PERIOD', '7')

def get_ffmpeg_concurrency():
    """Get ffmpeg concurrency number."""
    return int(__get_env('FFMPEG_CONCURRENCY', '2'))

def __get_env(name, default_val):
    """Get environment variable with default value."""
    return os.getenv(name, default_val).strip()
