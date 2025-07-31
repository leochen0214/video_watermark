import logging
import asyncio

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
        'stage_crf': 23,
        'stage_preset': 'fast',
        'crf': 17,
        'preset': 'slow',
        'horizontal_speed': 20,
        'vertical_speed': 40,
        'ffmpeg_options': common.get_ffmpeg_options(),
        'result_video_type': common.get_result_video_type()
    }
    processor = VideoWatermarkProcessor(config)
    videos = str(common.get_video_dir())
    persons = common.get_person_names()
    asyncio.run(processor.process_all(origin_videos=videos, persons=persons))
    logging.info("All videos processed successfully")


if __name__ == '__main__':
    main()
