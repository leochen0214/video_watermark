"""Directory management utilities."""

import os
from pathlib import Path


def get_mts_video_root_dir():
    """Get MTS video root directory."""
    return Path(os.getenv('MTS_VIDEO_DIR', str(Path.home().resolve()) + '/Downloads/当期视频'))


def get_mts_video_target_dir():
    """Get MTS video target directory."""
    return get_mts_video_root_dir().joinpath('target')


def get_video_dir():
    """Get source video directory."""
    return Path(os.getenv('VIDEO_DIR', str(find_project_root().joinpath('origin'))))


def get_target_dir():
    """Get target output directory."""
    return Path(os.getenv('TARGET_DIR', str(find_project_root().joinpath('target'))))


def get_person_video_result_dir(person):
    """Get person's video result directory."""
    return get_target_dir() / "result/videos" / person


def get_person_metadata_result_dir(person):
    """Get person's metadata result directory."""
    return get_target_dir() / "result/metadata" / person


def get_person_video_stage_dir(person):
    """Get person's video staging directory."""
    return get_target_dir() / "stage1" / person


def get_person_origin_dir():
    """Get person's origin directory."""
    return get_target_dir() / "stage2"


def get_frame_output_dir():
    """Get frame output directory."""
    return get_target_dir() / "frame_candidate"


def get_frame_processed_dir():
    """Get processed frame directory."""
    return get_target_dir() / "frame_processed"


def get_recover_dir():
    """Get recovery directory."""
    return get_target_dir().joinpath("recover")


def get_recover_result_dir():
    """Get recovery result directory."""
    return get_target_dir().joinpath("recover_result")


def get_qrcode_dir():
    """Get QR code directory."""
    return get_target_dir() / 'qrcode'


def get_images_dir():
    """Get images directory."""
    return get_target_dir() / 'images'


def get_audio_dir():
    """Get audio directory."""
    return get_target_dir() / 'audio'


def get_scale_dir():
    """Get scale directory."""
    return get_target_dir() / 'scale'


def get_logging_dir():
    """Get logging directory."""
    return find_project_root().joinpath("logs").resolve()


def get_baidu_dir():
    """Get baidu directory."""
    return find_project_root().joinpath("baidu").resolve()

def get_screenshot_dir():
    return get_baidu_dir().joinpath("screenshots").resolve()

def find_project_root(marker: str = "pyproject.toml") -> Path:
    """向上递归查找包含标记文件的目录"""
    current_dir = Path(__file__).resolve()
    for parent in current_dir.parents:
        if (parent / marker).exists():
            return parent
    return current_dir  # 未找到时返回当前目录


def is_empty_dir(dir_path):
    """Check if directory is empty."""
    return not any(Path(dir_path).iterdir())


def create_dir(dir_path):
    """Create directory if it doesn't exist."""
    p = Path(dir_path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
