import logging

from . import common
from .core import VideoWatermarkProcessor


def main():
    """Main entry point for the video watermark processing application."""
    common.init()
    config = {
        'watermark_logo_text': common.get_watermark_logo_text(),
        'font_size': 24,
        'bg_color': 'white',
        'font_color': 'red',
        'spacing': 4,
        'padding': 5,
        'align': 'center',
        'watermarkquality': 35,
        'scale': (1280, 720),
        'stage_crf': 24,
        'stage_preset': 'fast',
        'crf': 17,
        'preset': 'slow',
        'horizontal_speed': 20,
        'vertical_speed': 40
    }
    processor = VideoWatermarkProcessor(config)
    videos = str(common.get_video_dir())
    persons = common.get_person_names()
    processor.process_all(origin_videos=videos, persons=persons)
    logging.info("All videos processed successfully")
    # 测试暗水印提取功能
    person = '陈龙'
    filename = '11-24上午第1节'
    recover_json = common.get_person_metadata_result_dir(person).joinpath(f"{filename}.json")
    video_path = common.get_person_video_result_dir(person).joinpath(f"{filename}.mp4")
    VideoWatermarkProcessor.recover(recover_json, video_path)
    print("Done")


if __name__ == '__main__':
    main()
