import logging
import asyncio
import logging

from . import common
from .core.ffmpeg_processor import FFmpegProcessor

def main():
    asyncio.run(gen_scale())

async def gen_scale():
    common.init()
    # 初始化目录
    target_dir = common.get_scale_dir()
    common.create_dir(target_dir)
    video_dir = common.get_video_dir()
    all = common.get_videos(video_dir)
    if len(all) == 0:
        logging.info(f"{video_dir} 目录下没有原视频文件,请检查VIDEO_DIR路径配置是否正确")
        return
    all_map = common.to_map(all)
    processed_map = common.to_map(common.get_videos(target_dir))
    difference = set(all_map.keys()) - set(processed_map.keys())
    if len(difference) == 0:
        logging.info(f"{video_dir} 目录下音视频已经处理过了")
        return
    videos = []
    for diff in difference:
        videos.append(all_map[diff])

    # 创建FFmpeg处理器
    config = {
        'scale': (1280, 720),
        'crf': 17,
        'preset': 'slow',
        'ffmpeg_options': common.get_ffmpeg_options(),
        'result_video_type': common.get_result_video_type()
    }
    ffmpeg_processor = FFmpegProcessor(config)

    tasks = []
    for video in videos:
        task = ffmpeg_processor.scale(video, target_dir, config['scale'])
        tasks.append(task)

    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    cnt = 0
    for result in results:
        if isinstance(result, bool) and result == True:
            cnt += 1
        elif isinstance(result, Exception):
            logging.error(f"处理时出错: {result}")
    logging.info(f"共提取了{cnt}个视频文件")


if __name__ == '__main__':
    main()
