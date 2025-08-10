import os
import random
import time
import shutil
from pathlib import Path
import logging
import asyncio

from .. import common
from .. import core
from .. import tool
from . import pils
from . import videoprocess
from .ffmpeg_processor import FFmpegProcessor


class VideoWatermarkProcessor:
    def __init__(self, config):
        """初始化视频处理器"""
        self.config = config
        self.ffmpeg_processor = FFmpegProcessor(config)
        self.upload_semaphore = asyncio.Semaphore(3)
        self.upload_tasks = set()  # 存储所有上传任务

    async def process_all(self, origin_videos='', persons=None):
        """
        为所有人生成水印视频（按顺序处理每个人）
        """
        logging.info(f"Processing {len(persons)} people: {persons}")
        if not persons:
            return

        origin_videos = origin_videos or str(common.get_video_dir())
        all_videos = common.get_videos(origin_videos)
        if not all_videos:
            return

        invisible_watermark_videos, plain_watermark_videos = self._partition(all_videos)
        logo_title_prefix = self.config['watermark_logo_text']

        # 按顺序处理每个人
        for person in persons:
            if common.is_finished(person):
                logging.info(f"'{person}' is already processed")
                continue

            try:
                await self._process_person(person, logo_title_prefix, invisible_watermark_videos,
                                           plain_watermark_videos, all_videos)
            except Exception as e:
                logging.error(f"Error processing person '{person}': {e}", exc_info=True)
                # 继续处理下一个人，而不是中断整个流程
                continue

        # 等待所有上传任务完成
        if self.upload_tasks:
            logging.info(f"Waiting for {len(self.upload_tasks)} upload tasks to complete...")
            await asyncio.gather(*self.upload_tasks, return_exceptions=True)
            logging.info("All upload tasks completed")

    async def _process_person(self, person, logo_title_prefix, invisible_watermark_videos,
                              plain_watermark_videos, all_videos):
        """处理单个人的所有视频"""
        logging.info(f"Starting video generation for '{person}'")
        text = f'{logo_title_prefix}{person}'
        self._initialize_directories(person)
        self.generate_logo_and_qrcode(person, text, text)
        course_name = common.get_current_course_name() or all_videos[0].parent.name

        # 先处理暗水印视频（串行）
        logging.info(f"Begin to process invisible videos for '{person}'")
        await self._process_person_invisible_watermark_videos(course_name, invisible_watermark_videos, person)
        logging.info(f"Finish to process {len(invisible_watermark_videos)} invisible videos for '{person}'")

        # 暗水印处理完成后，再并发处理明水印视频
        logging.info(f"Begin to process plain videos for '{person}'")
        await self._process_person_plain_watermark_videos(course_name, plain_watermark_videos, person)
        logging.info(f"Finish to process {len(plain_watermark_videos)} plain videos for '{person}'")

        # 检查是否完成对person的处理
        if common.is_done_for_person(all_videos, person):
            common.finish(person)
            logging.info(f"'Finished course videos: {course_name} for person: '{person}'")

    def _partition(self, videos):
        invisible_watermark_videos = []
        plain_watermark_videos = []
        for i, video in enumerate(videos):
            if common.is_need_add_invisible_watermark(i):
                invisible_watermark_videos.append(video)
            else:
                plain_watermark_videos.append(video)
        return invisible_watermark_videos, plain_watermark_videos

    async def _process_person_invisible_watermark_videos(self, course_name, videos, person):
        """处理暗水印视频（串行处理，每个视频处理完成后立即上传）"""
        pending_videos = common.get_pending_to_process_videos(videos, person)
        if not pending_videos:
            return

        processed = []
        try:
            for video in pending_videos:
                success, filename_with_extension = await self.process_single_video_async(
                    person, video, True, course_name
                )
                if success:
                    processed.append(video.name)
        finally:
            common.add_videos_to_person_detail(processed, person)
            logging.info(f"Finished processing {len(processed)} invisible videos for '{person}'")

    async def _process_person_plain_watermark_videos(self, course_name, videos, person):
        """处理明水印视频（并发处理，每个视频处理完成后立即上传）"""
        pending_videos = common.get_pending_to_process_videos(videos, person)
        if not pending_videos:
            return

        processed = []
        try:
            # 创建所有明水印视频的并发处理任务
            tasks = []
            for video in pending_videos:
                # 为每个视频创建处理任务，处理完成后立即上传
                task = asyncio.create_task(
                    self.process_single_video_async(person, video, False, course_name)
                )
                tasks.append(task)

            # 等待所有明水印视频处理完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, tuple) and len(result) == 2:
                    success, filename_with_extension = result
                    if success:
                        processed.append(filename_with_extension)
                elif isinstance(result, Exception):
                    logging.error(f"处理明水印视频时出错: {result}")
        finally:
            # 确保即使在程序被终止时，已处理的视频信息也被记录
            common.add_videos_to_person_detail(processed, person)
            logging.info(f"Finished processing {len(processed)} plain videos for '{person}'")

    async def process_single_video_async(self, person, video, add_invisible_watermark=False, course_name=None):
        """
        处理单个视频文件并立即开始上传任务
        """
        # 1. 压缩原视频并添加logo水印图片
        logo = common.get_logo_watermark_image(person).as_posix()
        filename_with_extension = f"{video.stem}{self.config['result_video_type']}"
        success = await self.ffmpeg_processor.compress_with_logo(video, person, logo, add_invisible_watermark)
        if not success:
            return success, None

        stage1_video = None
        if add_invisible_watermark:
            stage1_video = common.get_person_video_stage_dir(person).joinpath(filename_with_extension)
            success = await self._process_with_invisible_watermark_async(person, video.stem, stage1_video)
        if stage1_video and not common.keep_stage1_file():
            common.delete_file(stage1_video)

        # 如果处理成功且需要上传，立即创建上传任务
        if success and course_name:
            upload_task = asyncio.create_task(
                self._success_post(course_name, filename_with_extension, person)
            )
            self.upload_tasks.add(upload_task)
            upload_task.add_done_callback(lambda t: self.upload_tasks.remove(t))

        return success, filename_with_extension

    async def _success_post(self, course_name, filename_with_extension, person):
        def upload_success_callback(local_path, remote_file):
            if common.is_delete_after_upload_success():
                common.delete_file(local_path)
                logging.info(f"删除已上传完毕的文件, file: {local_path}")

        if common.is_sync_to_baidu():
            f = common.get_person_video_result_dir(person).joinpath(filename_with_extension).resolve()
            if f.exists():
                remote_dir = f"{common.get_root_remote_dir()}/videos/{person}/{course_name}"
                await tool.upload_file_with_limit(self.upload_semaphore, f, remote_dir, upload_success_callback=upload_success_callback)
            else:
                logging.info(f"upload file not exists, file: '{f}'")

    def _initialize_directories(self, person):
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

    async def check_missed_videos_async(self, person, origin_videos):
        """检查并处理遗漏的视频"""
        videos = common.get_pending_to_process_videos(origin_videos, person)
        if videos:
            logging.info(f"Found {len(videos)} missed videos for {person}")
            await self.generate_videos_async(person, videos)
            logging.info(f"Finished processing missed videos for {person}")

    async def generate_videos_async(self, person, videos):
        """
        生成带水印的视频
        """
        logging.info(f"Processing {len(videos)} videos for {person}")

        for i, video in enumerate(videos):
            if common.is_already_processed(video, person):
                logging.info(f"Video already processed: {person}, {video.name}")
            else:
                await self.process_single_video_async(person, video, i)

        if len(videos) == len([v for v in videos if common.is_already_processed(v, person)]):
            common.finish(person)
            logging.info(f"All videos processed for {person}")

    async def _process_with_invisible_watermark_async(self, person, filename, stage1_video):
        """处理带隐形水印的视频"""
        return await self.process_video_async(
            person,
            common.get_qrcode_image(person),
            stage1_video,
            filename,
            watermarkquality=self.config['watermarkquality'],
            crf=self.config['crf'],
            preset=self.config['preset']
        )

    async def process_video_async(self, person, watermark, video, filename, **kwargs):
        """主处理函数"""
        try:
            # 获取视频元数据
            stats = os.stat(str(video))
            video_info = videoprocess.get_video_info(video)
            frame_count, fps = video_info[2], video_info[3]
            # resolution = f"{int(video_info[0])}x{int(video_info[1])}"

            # 提取视频帧
            await self.ffmpeg_processor.extract_all_frames(person, video, fps)

            # 采样和处理帧
            seed = self.generate_seed(kwargs.get('watermarkquality', 35))
            samplelist = videoprocess.sampler(video, kwargs.get('sampletimes', 5), kwargs.get('peroid', 1))
            watermark_shape = self._process_frames(video, samplelist, seed, watermark)

            # 提取音频
            await self.ffmpeg_processor.extract_audio(common.get_person_origin_dir(), video)

            # 合成视频
            await self.ffmpeg_processor.compose_video(person, video, fps, **kwargs)

            # 保存元数据
            self.save_metadata(person, filename, video, stats, frame_count, fps, samplelist, seed, watermark_shape)
            return True
        except Exception as e:
            logging.error(f"Processing failed for {person}, {video}", exc_info=True)
            return False

    def _process_frames(self, video, samplelist, seed, watermark):
        """处理视频帧"""
        frame_output_dir = common.get_frame_output_dir()
        frame_processed_dir = common.get_frame_processed_dir()
        common.delete_then_create(frame_output_dir)
        common.delete_then_create(frame_processed_dir)

        videoprocess.extract_frames(video, samplelist, frame_output_dir, filetype=".png")

        origin_dir = common.get_person_origin_dir()
        watermark_shape = None

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
            'name': str(video),
            'sample_frames': samplelist,
            'fps': fps,
            'total_frames': frame_count,
            'metadata': str(stats),
            'seed': seed,
            'shape': watermark_shape
        }

        metadata_dir = common.get_person_metadata_result_dir(person)
        common.create_dir(metadata_dir)
        common.write_json_to_file(metadata, metadata_dir.joinpath(f'{filename}.json'))
        logging.info(f"Metadata saved for {person}, {filename}")
