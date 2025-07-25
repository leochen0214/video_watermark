import os
import random
import time
import shutil
from pathlib import Path
import logging

from .. import common
from .. import core
from . import pils
from . import videoprocess
from ..common import command


class VideoWatermarkProcessor:
    def __init__(self, config):
        """初始化视频处理器"""
        self.config = config

    def process_all(self, origin_videos='', persons=None):
        """
        为所有人生成水印视频
        """
        logging.info(f"Processing {len(persons)} people: {persons}")
        if not persons:
            return

        origin_videos = origin_videos or str(common.get_video_dir())
        logo_title_prefix = self.config['watermark_logo_text']
        for person in persons:
            if common.is_finished(person):
                logging.info(f"'{person}' is already processed")
            else:
                self.process_person(logo_title_prefix, person, origin_videos)
                self.check_missed_videos(person, origin_videos)

    def process_person(self, logo_title_prefix, person, origin_videos):
        """
        处理单个人的视频
        """
        # logo text
        text = f'{logo_title_prefix}{person}'
        logging.info(f"Starting video generation for '{person}'")

        self.initialize_directories(person)
        self.generate_logo_and_qrcode(person, text, text)

        videos = common.get_all_videos(origin_videos, person)
        self.generate_videos(person, videos)

        logging.info(f"Finished video generation for '{person}'")

    def initialize_directories(self, person):
        """
        初始化必要的目录结构
        """
        dirs_to_create = [
            common.get_qrcode_dir(),
            common.get_images_dir(),
            common.get_person_video_stage_dir(person),
            common.get_person_origin_dir(),
            common.get_person_video_result_dir(person),
            common.get_person_metadata_result_dir(person)
        ]
        for directory in dirs_to_create:
            common.create_dir(directory)

    def generate_logo_and_qrcode(self, person, logo_text, qrcode_text):
        """
        生成logo和二维码图片
        """
        pils.makeimage(
            text=logo_text,
            filename=person,
            font_size=self.config['font_size'],
            bg_color=self.config['bg_color'],
            font_color=self.config['font_color'],
            spacing=self.config['spacing'],
            padding=self.config['padding'],
            align=self.config['align']
        )
        pils.genqrcode(text=qrcode_text, filename=person, pix=4)
        logging.info(f"Generated logo and QR code for {person}")

    def check_missed_videos(self, person, origin_videos):
        """检查并处理遗漏的视频"""
        videos = common.get_all_videos(origin_videos, person)
        if videos:
            logging.info(f"Found {len(videos)} missed videos for {person}")
            self.generate_videos(person, videos)
            logging.info(f"Finished processing missed videos for {person}")

    def generate_videos(self, person, videos):
        """
        生成带水印的视频
        """
        logging.info(f"Processing {len(videos)} videos for {person}")

        for i, video in enumerate(videos):
            if common.is_already_processed(video, person):
                logging.info(f"Video already processed: {person}, {video.name}")
            else:
                self.process_single_video(person, video, i)

        if len(videos) == len([v for v in videos if common.is_already_processed(v, person)]):
            common.finish(person)
            logging.info(f"All videos processed for {person}")

    def process_single_video(self, person, video, index):
        """
        处理单个视频文件
        """
        add_invisible_watermark = common.is_need_add_invisible_watermark(index)
        stage_crf = self.config['crf'] if not add_invisible_watermark else self.config['stage_crf']

        # 1. 压缩原视频并添加logo水印图片
        if not self.compress_with_watermark(person, video, stage_crf, add_invisible_watermark):
            return False

        filename = video.stem
        filename_with_extension = filename + ".mp4"
        if add_invisible_watermark:
            stage1_video = common.get_person_video_stage_dir(person).joinpath(filename_with_extension)
            self.process_with_invisible_watermark(person, video.stem, stage1_video)

        if common.is_sync_to_baidu():
            pending_to_upload_file = common.get_person_video_result_dir(person).joinpath(
                filename_with_extension).resolve()
            if pending_to_upload_file.exists():
                pass
            else:
                logging.info(f"upload file not exists, file: '{pending_to_upload_file}'")

    def compress_with_watermark(self, person, video, stage_crf, add_invisible_watermark):
        """压缩视频并添加水印"""
        return command.compress_with_logo(
            video, person,
            scale=self.config['scale'],
            crf=stage_crf,
            preset=self.config['stage_preset'],
            horizontal_speed=self.config['horizontal_speed'],
            vertical_speed=self.config['vertical_speed'],
            add_invisible_watermark=add_invisible_watermark
        )

    def process_with_invisible_watermark(self, person, filename, stage1_video):
        """处理带隐形水印的视频"""
        success = self.process_video(
            person,
            common.get_qrcode_image(person),
            stage1_video,
            filename,
            watermarkquality=self.config['watermarkquality'],
            crf=self.config['crf'],
            preset=self.config['preset']
        )

        if success:
            common.add_video_to_person_detail(stage1_video, person)
            logging.info(f"Added invisible watermark successfully: {filename}.mp4, {person}")
            if not common.keep_stage1_file():
                common.delete_file(stage1_video)
        return success

    def process_video(self, person, watermark, video, filename, **kwargs):
        """主处理函数"""
        try:
            # 获取视频元数据
            stats = os.stat(str(video))
            video_info = command.get_video_info(video)
            frame_count, fps = video_info[2], video_info[3]
            resolution = f"{int(video_info[0])}x{int(video_info[1])}"

            # 准备处理环境
            self.prepare_processing_environment(person, video, fps)

            # 采样和处理帧
            seed = self.generate_seed(kwargs.get('watermarkquality', 35))
            samplelist = videoprocess.sampler(video, kwargs.get('sampletimes', 5), kwargs.get('peroid', 1))
            watermark_shape = self.process_frames(video, samplelist, seed, watermark)

            # 提取音频
            if not command.extractaudio(common.get_person_origin_dir(), video):
                logging.info(f"No audio in video: {video}")
                return False

            # 合成视频
            if not command.output(
                    person,
                    origin=video,
                    video=filename,
                    fps=fps,
                    mtype=".png",
                    vtype=".mp4",
                    crf=kwargs.get('crf', 18),
                    preset=kwargs.get('preset', 'slow')
            ):
                return False

            # 保存元数据
            self.save_metadata(person, filename, video, stats, frame_count, fps, samplelist,
                               seed, watermark_shape)
            return True
        except Exception as e:
            logging.error(f"Processing failed for {person}, {video}", exc_info=True)
            return False

    def prepare_processing_environment(self, person, video, fps):
        """准备处理环境"""
        origin_dir = common.get_person_origin_dir()
        common.delete_then_create(origin_dir)
        command.extractall(person, video, fps, ".png")

    def process_frames(self, video, samplelist, seed, watermark):
        """处理视频帧"""
        frame_output_dir = common.get_frame_output_dir()
        frame_processed_dir = common.get_frame_processed_dir()
        common.delete_then_create(frame_output_dir)
        common.delete_then_create(frame_processed_dir)

        videoprocess.extract_frames(video, samplelist, frame_output_dir, filetype=".png")


        origin_dir = common.get_person_origin_dir()
        watermark_shape=None

        def process_frame(file: Path):
            nonlocal watermark_shape
            imlen = core.encodewatermark_image(frame_processed_dir, file, watermark, seed)
            # 进行帧替换
            shutil.copy(frame_processed_dir.joinpath(file.name), origin_dir)
            if watermark_shape is None:
                watermark_shape = imlen
            return imlen

        common.process_files(frame_output_dir, process_frame)
        return watermark_shape

    def generate_seed(self, watermarkquality):
        """生成随机种子"""
        return [random.randint(1, 9999) for _ in range(2)] + [watermarkquality]

    def save_metadata(self, person, filename, video, stats, frame_count, fps, samplelist, seed, watermark_shape):
        """保存视频元数据"""
        metadata = {
            'algorithm': "image",
            'date': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
            'version': '0.4.4',
            'videoname': str(video),
            'freamdata': samplelist,
            'fps': fps,
            'totalfream': frame_count,
            'metadata': str(stats),
            'seed': seed,
            'shape': watermark_shape
        }

        metadata_dir = common.get_person_metadata_result_dir(person)
        common.create_dir(metadata_dir)
        common.write_json_to_file(metadata, metadata_dir.joinpath(f'{filename}.json'))
        logging.info(f"Metadata saved for {person}, {filename}")

    @staticmethod
    def recover(recoverfile: Path, video: Path):
        """恢复水印"""
        logging.info(f'Recovering from: {recoverfile}, video: {video}')

        recover_dir = common.get_recover_dir()
        recover_result_dir = common.get_recover_result_dir()
        common.delete_then_create(recover_dir)
        common.delete_then_create(recover_result_dir)

        recoverdata = common.read_json_file(recoverfile)
        if not recoverdata:
            logging.error(f'Recover file not found: {recoverfile}')
            return

        flist = recoverdata['freamdata']
        videoprocess.extract_frames(video, flist, output_path=recover_dir, filetype=".png")

        def process_recovery(file: Path):
            core.decodewatermark_image(file, recover_result_dir, recoverdata['shape'], recoverdata['seed'])
            logging.info(f"解码成功: {file.name}")

        common.process_files(recover_dir, process_recovery)
