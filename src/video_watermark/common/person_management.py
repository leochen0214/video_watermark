"""Person management utilities."""

import logging
from .directories import get_video_dir
from .file_operations import read_all_lines, write_lines_to_file, read_json_file, write_json_to_file
from .logging_config import get_person_log, get_person_detail_json
from .environment import is_test


def get_person_names():
    """Get list of person names."""
    lines = read_all_lines(get_video_dir().joinpath("名单.txt"))
    if is_test():
        return lines[:1]
    else:
        return lines


def finish(person):
    """Mark person as finished."""
    dataset = _get_person_dataset()
    if person in dataset:
        logging.info(f"person: '{person}' has already done")
    else:
        dataset.add(person)
        write_lines_to_file(get_person_log(), list(dataset))


def is_finished(person):
    """Check if person is finished."""
    return person in _get_person_dataset()


def _get_person_dataset():
    """Internal function: get finished person set."""
    lines = read_all_lines(get_person_log())
    return set(lines)


def add_video_to_person_detail(video, person):
    """Add processed video to person detail."""
    videos = get_person_videos(person)
    basename = video.name
    if basename in videos:
        logging.info(f"video is already in person_detail.json, video: {basename}, person: {person}")
        return
    videos.add(basename)
    _update_person_videos(person, videos)
    logging.info(f"video: {basename} is written to person: {person}")


def is_already_processed(video, person):
    """Check if video is already processed for person."""
    detail_json = get_person_detail_json()
    data = read_json_file(detail_json)
    if person in data and isinstance(data[person], list):
        dataset = set(data[person])
    else:
        dataset = set()
    return video.name in dataset


def get_person_videos(person):
    """Get processed videos set for person."""
    detail_json = get_person_detail_json()
    data = read_json_file(detail_json)
    if person in data and isinstance(data[person], list):
        return set(data[person])
    return set()


def _update_person_videos(person, videos):
    """Internal function: update person's video list."""
    detail_json = get_person_detail_json()
    data = read_json_file(detail_json)
    data[person] = list(videos)
    write_json_to_file(data, detail_json)