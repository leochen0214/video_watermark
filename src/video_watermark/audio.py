import logging
import asyncio
import logging

from . import common
from .core.ffmpeg_processor import FFmpegProcessor

def main():
    asyncio.run(gen_audio())

async def gen_audio():
    common.init()
    # 初始化目录
    target_audio_dir = common.get_audio_dir()
    common.create_dir(target_audio_dir)
    video_dir = common.get_video_dir()
    all = common.get_videos(video_dir)
    if len(all) == 0:
        logging.info(f"{video_dir} 目录下没有原视频文件,请检查VIDEO_DIR路径配置是否正确")
        return
    processed_map = common.to_map(common.get_videos(target_audio_dir))
    all_map = common.to_map(all)
    difference = set(all_map.keys()) - set(processed_map.keys())
    if len(difference) == 0:
        logging.info(f"{video_dir} 目录下音视频已经处理过了")
        return
    videos = []
    for diff in difference:
        videos.append(all_map[diff])

    # 创建FFmpeg处理器
    config = {}  # 可以根据需要添加配置
    ffmpeg_processor = FFmpegProcessor(config)

    tasks = []
    for video in videos:
        task = ffmpeg_processor.audio(video, target_audio_dir)
        tasks.append(task)

    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    cnt = 0
    for result in results:
        if isinstance(result, bool) and result == True:
            cnt += 1
        elif isinstance(result, Exception):
            logging.error(f"处理目录时出错: {result}")

    logging.info(f"共提取了{cnt}个音频文件")


if __name__ == '__main__':
    main()
