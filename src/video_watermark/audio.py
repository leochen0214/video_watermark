from pathlib import Path
import logging

from . import common
from .common import command

def gen_audio():
    # 初始化目录
    target_audio_dir = common.get_audio_dir()
    common.create_dir(target_audio_dir)
    video_dir = common.get_video_dir()
    all = common.get_videos(video_dir)
    if len(all) == 0:
        logging.info(f"{video_dir} 目录下没有原视频文件,请检查VIDEO_DIR路径配置是否正确")
        return
    processed = common.get_videos(target_audio_dir)
    difference = set(all.keys()) - set(processed.keys())
    if len(difference) == 0:
        logging.info(f"{video_dir} 目录下音视频已经处理过了")
        return
    videos = []
    for diff in difference:
        videos.append(all[diff])

    cnt = 0
    for video in videos:
        if command.audio(video, target_audio_dir):
            cnt += 1
    logging.info(f"共提取了{cnt}个音频文件")

if __name__ == '__main__':
    common.init()
    gen_audio()