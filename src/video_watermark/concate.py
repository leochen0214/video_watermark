from pathlib import Path
import logging
import asyncio

from . import common
from .core.ffmpeg_processor import FFmpegProcessor

def main():
    asyncio.run(concate())

async def concate():
    common.init()
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

    # 创建FFmpeg处理器
    config = {}  # 可以根据需要添加配置
    ffmpeg_processor = FFmpegProcessor(config)

    video_format = "*" + common.get_video_format()
    cnt = 0
    tasks = []
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

        # 添加异步任务
        task = process_directory(ffmpeg_processor, d)
        tasks.append(task)

    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计成功的数量
    for result in results:
        if isinstance(result, str) and Path(result).exists():
            cnt += 1
        elif isinstance(result, Exception):
            logging.error(f"处理目录时出错: {result}")

    logging.info(f'本次共处理了{cnt}集视频')


async def process_directory(ffmpeg_processor: FFmpegProcessor, d: Path) -> str:
    """处理单个目录的视频合并"""
    try:
        target_dir = common.get_mts_video_target_dir()
        ffmpeg_options = common.get_ffmpeg_options()
        result_video = await ffmpeg_processor.concate_to_mp4(d, target_dir, ffmpeg_options)
        if Path(result_video).exists():
            logging.info(f'视频拼接成功: {result_video}')
        else:
            logging.info(f'视频拼接失败: {result_video}')
        return result_video
    except Exception as e:
        logging.error(f'处理目录 {d} 时出错: {e}')
        raise


if __name__ == '__main__':
    main()
