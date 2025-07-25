from pathlib import Path
import logging

from . import common
from .common import command


def concate():
    p = common.get_mts_video_root_dir()
    if not p.exists():
        logging.info(f'dir: {p} not exists')
        return
    target_dir = p.joinpath('target')
    common.create_dir(target_dir)
    all_subdirs = [d for d in p.rglob('*') if d.is_dir() and d.name != 'target']
    last_layer_subdirs = []
    for subdir in all_subdirs:
        # 如果一个目录没有子目录，则认为它是最后一层目录
        if not any(d.is_dir() for d in subdir.iterdir()):
            last_layer_subdirs.append(subdir)
    
    video_format = "*" + common.get_video_format()
    cnt = 0
    for d in last_layer_subdirs:
        logging.info(f'begin to process dir: {d}')
        # create mylist.txt
        video_files = sorted([f for f in d.rglob(video_format) if f.is_file()], key=lambda x: x.name)
        if len(video_files) == 0:
            continue
        lines = []
        for v in video_files:
            lines.append(f"file '{v.name}'")
        common.write_lines_to_file(d.joinpath('mylist.txt'), lines)

        # concate videos
        video_name = command.concate_to_mp4(d)
        if Path(video_name).exists():
            logging.info(f'视频拼接成功: {video_name}')
            cnt += 1
        else:
            logging.info(f'视频拼接失败: {video_name}')
    logging.info(f'本次共处理了{cnt}集视频')

if __name__ == '__main__':
    common.init()
    concate()


