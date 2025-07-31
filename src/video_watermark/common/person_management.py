"""Person management utilities."""

import logging
from .directories import get_video_dir
from .file_operations import read_all_lines, write_lines_to_file, read_json_file, write_json_to_file
from .logging_config import get_person_log, get_person_detail_json
from .environment import is_test
from .video_operations import to_map


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


def add_videos_to_person_detail(to_add_videos, person):
    """Add processed videos to person detail."""
    if not to_add_videos:
        return
    videos = get_person_videos(person)
    for vd in to_add_videos:
        if vd not in videos:
            videos.add(vd)
    _update_person_videos(person, videos)


def is_done_for_person(all_videos, person):
    return len(get_pending_to_process_videos(all_videos, person)) == 0


def is_already_processed(video, person):
    """Check if video is already processed for person."""
    detail_json = get_person_detail_json()
    data = read_json_file(detail_json)
    if person in data and isinstance(data[person], list):
        dataset = set(data[person])
    else:
        dataset = set()
    return video.name in dataset


def get_pending_to_process_videos(all_videos, person):
    """Get pending to process videos for person"""
    if not all_videos:
        return set()
    processed_set = get_person_videos(person)
    all_map = to_map(all_videos)
    pending_video_names = set(all_map.keys()) - processed_set

    pending_videos = []
    for name in pending_video_names:
        pending_videos.append(all_map[name])
    return pending_videos


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
