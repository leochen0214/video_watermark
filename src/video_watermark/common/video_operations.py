"""Video operation utilities."""

import re
import logging
from pathlib import Path
from .directories import get_person_video_result_dir
from .environment import is_test


def get_logo_watermark_image(person):
    """Get logo watermark image path for person."""
    from .directories import get_images_dir
    return get_images_dir().joinpath(person + '.png')


def get_qrcode_image(person):
    """Get QR code image path for person."""
    from .directories import get_qrcode_dir
    return get_qrcode_dir().joinpath(person + ".png")


def get_font_file():
    """Get font file path."""
    from .directories import find_project_root
    return str(find_project_root().joinpath('font/SourceHanSansK-Bold.ttf'))


def get_all_videos(origin_videos_path, person):
    """Get all unprocessed videos for person."""
    all_videos = get_videos(origin_videos_path)
    processed_videos = get_videos(get_person_video_result_dir(person))
    difference = set(all_videos.keys()) - set(processed_videos.keys())
    logging.info(f"还未处理的视频共有{len(difference)}个, difference={difference}")

    res = []
    for diff in difference:
        res.append(all_videos[diff])
    sorted_videos = sorted(res, key=extract_key)

    if is_test():
        return sorted_videos[:1]
    else:
        return sorted_videos


def get_videos(video_path):
    """Get videos from path."""
    allowed_extensions = {'.mp4', '.avi', '.mkv', '.wmv', '.mov', '.m4v', '.mp3', ".m4a"}
    videos = {}
    vp = Path(video_path)
    if vp.is_dir():
        for file in vp.rglob('*'):
            if (file.is_file() and file.suffix in allowed_extensions
                    and not file.name.startswith('.') and not file.name.startswith('output')):
                videos[file.stem] = file
    else:
        videos[vp.stem] = vp
    return videos


def is_audio_file(video):
    """Check if file is audio file."""
    allowed_extensions = {".m4a", ".aac", ".mp3"}
    file = Path(video)
    return file.is_file() and file.suffix in allowed_extensions


def extract_key(filename):
    """Extract sorting key from filename."""
    name_part = str(filename).split('/')[-1]
    match = re.search(r'(\d+)月(\d+)日(上午|下午)第(\d+)节', name_part)
    if not match:
        return (0, 0, 0, 0)

    month = int(match.group(1))
    day = int(match.group(2))
    time_of_day = match.group(3)
    section = int(match.group(4))
    am_pm = 0 if time_of_day == '上午' else 1

    return (month, day, am_pm, section)
