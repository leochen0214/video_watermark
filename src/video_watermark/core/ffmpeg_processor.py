import asyncio
import logging
import re
from pathlib import Path
from typing import Tuple

from .. import common
from . import videoprocess
from ..tool import shell_utils

# This regex is designed to capture the key fields from an ffmpeg progress line.
# It handles variations in spacing and the optional 'L' in the final 'size' field.
FFMPEG_PROGRESS_RE = re.compile(
    r"(?:L)?size=\s*(?P<size>\S+)\s+"
    r"time=\s*(?P<time>\S+)\s+"
    r"bitrate=\s*(?P<bitrate>\S+)\s+"
    r"speed=\s*(?P<speed>\S+)"
)


class FFmpegProcessor:
    """专门处理ffmpeg命令相关操作的类"""

    def __init__(self, config: dict):
        self.config = config
        # 限制加暗水印操作的并发为1
        self._serial_semaphore = asyncio.Semaphore(1)
        # 限制其他ffmpeg操作的并发为2
        self._general_ffmpeg_semaphore = asyncio.Semaphore(2)
        self.result_video_type = self.config.get('result_video_type')

    async def compress_with_logo(self, video: Path, person: str, logo: str,
                                 add_invisible_watermark: bool = True) -> bool:
        """压缩视频并添加logo水印"""
        cmd, is_serial = self._build_compress_command(video, person, logo, add_invisible_watermark)
        process_id = f'compress_{person}_{video.stem}'
        if is_serial:
            return await self._limited(self._serial_semaphore, self._run_ffmpeg(cmd, process_id=process_id))
        else:
            return await self._limited(self._general_ffmpeg_semaphore, self._run_ffmpeg(cmd, process_id=process_id))

    async def extract_all_frames(self, person: str, video: Path, fps: int) -> bool:
        """提取视频所有帧"""
        return await self._limited(self._serial_semaphore, self._extract_all_frames_impl(person, video, fps))

    async def extract_audio(self, origin_dir: Path, video: Path) -> bool:
        """提取视频音频"""
        return await self._limited(self._serial_semaphore, self._extract_audio_impl(origin_dir, video))

    async def compose_video(self, person: str, origin_video: Path, fps: int, **kwargs) -> bool:
        """合成最终视频"""
        return await self._limited(self._serial_semaphore,
                                   self._compose_video_impl(person, origin_video, fps, **kwargs))

    async def concate_to_mp4(self, d: Path, target_dir: Path, ffmpeg_options: str = '') -> str:
        """合并视频 + 降噪 + 压缩 + 格式为mp4"""
        return await self._limited(self._general_ffmpeg_semaphore,
                                   self._concate_to_mp4_impl(d, target_dir, ffmpeg_options))

    async def audio(self, video, target_dir):
        """提取音频"""
        return await self._limited(self._general_ffmpeg_semaphore, self._audio_impl(video, target_dir))

    async def scale(self, video: Path, target_dir: Path, scale=(1280, 720)):
        """视频scale, example: from 1080p -> 720p"""
        return await self._limited(self._general_ffmpeg_semaphore, self._scale_impl(video, target_dir, scale))

    async def _audio_impl(self, video, target_dir):
        aac_file = Path(target_dir).joinpath(Path(video).stem + ".m4a").as_posix()
        vd = Path(video).as_posix()

        if common.is_audio_file(video):
            cmd = f'ffmpeg -i "{vd}" -af afftdn -c:a aac -b:a 96k -y "{aac_file}"'
        else:
            cmd = f'ffmpeg -i "{vd}" -vn -c:a aac -b:a 96k -y "{aac_file}"'
        await self._run_ffmpeg(cmd, process_id=f'audio-{video.stem}')
        if Path(aac_file).exists():
            logging.info(f"提取音频成功: {vd}")
            return True
        return False

    async def _scale_impl(self, video, target_dir, scale):
        logging.info(f"开始压缩原视频, video: {video}")
        output = target_dir.joinpath(f"{video.stem}{self.result_video_type}").as_posix()
        ffmpeg_options = self.config.get('ffmpeg_options', '')
        if ffmpeg_options:
            options = ffmpeg_options
        else:
            options = f"-c:a copy -crf {self.config['crf']} -preset {self.config['preset']}"
        cmd = f'ffmpeg -i "{video}" -vf "crop=min(iw\,ih*16/9):ih:(iw-min(iw\,ih*16/9))/2:0,scale=1280:720" {options} -y "{output}"'
        return await self._run_ffmpeg(cmd, process_id=f'scale-{video.stem}')

    def _build_compress_command(self, video: Path, person: str, logo: str, add_invisible_watermark: bool) -> Tuple[
        str, bool]:
        """
        构建压缩并添加logo命令
        :param video: 视频文件
        :param person: 人物
        :param logo: logo图片
        :param add_invisible_watermark: 是否添加不可见水印
        :return: cmd, 是否串行运行
        """

        output_dir = common.get_person_video_stage_dir(person) if add_invisible_watermark else common.get_person_video_result_dir(person)
        output_file = output_dir.joinpath(f"{video.stem}{self.result_video_type}")

        scale = self.config['scale']
        # 控制水印在水平方向上移动的速度，单位为像素 / 秒。增大该值意味着水印在每秒钟内水平移动的像素数增多，因此水印会移动得更快。
        horizontal_speed = self.config['horizontal_speed']
        # 控制水印在垂直方向上移动的速度
        vertical_speed = self.config['vertical_speed']

        w, h = scale
        vinfo = videoprocess.get_video_info(video)
        w = min(w, vinfo[0])
        h = min(h, vinfo[1])

        if add_invisible_watermark:
            crf = self.config['stage_crf']
            preset = self.config['stage_preset']
            options = f'-c:a copy -crf {crf} -preset {preset}'
            is_serial = True
        else:
            ffmpeg_options = self.config.get('ffmpeg_options', '')
            if ffmpeg_options:
                options = ffmpeg_options
                is_serial = False
            else:
                crf = self.config['crf']
                preset = self.config['stage_preset']
                options = f'-c:a copy -crf {crf} -preset {preset}'
                is_serial = True

        cmd = f'ffmpeg -i "{video}" -i "{logo}" -filter_complex "[0:v]crop={w}:{h},scale={w}:{h}[v];[v][1:v]overlay=x=\'if(gte(mod(t*{horizontal_speed}, main_w), main_w - w), main_w - w, mod(t*{horizontal_speed}, main_w))\':y=\'if(gte(mod(t*{vertical_speed}, main_h), main_h - h), main_h - h, mod(t*{vertical_speed}, main_h - h))\'" {options} -y "{output_file}"'
        return cmd, is_serial

    async def _extract_all_frames_impl(self, person: str, video: Path, fps: int) -> bool:
        """提取视频所有帧的实现"""
        origin_dir = common.get_person_origin_dir().as_posix()
        common.delete_then_create(origin_dir)
        cmd = f'ffmpeg -i "{video.as_posix()}" -vf "fps={fps}" {origin_dir}/%0d.png'
        process_id = f"extract_frames_{person}_{video.stem}"
        success = await self._run_ffmpeg(cmd, process_id=process_id)
        if success:
            logging.info(f"提取原视频中所有帧成功, video: {video}, person: {person}")
        else:
            logging.error(f"提取原视频中所有帧执行失败, video: {video}, person: {person}")
        return success

    async def _extract_audio_impl(self, origin_dir: Path, video: Path) -> bool:
        """提取视频音频的实现"""
        aac_file = origin_dir.joinpath(f'{video.stem}.aac')
        common.delete_file(aac_file)
        cmd = f'ffmpeg -i "{video.as_posix()}" -vn -c:a copy "{aac_file.as_posix()}"'
        process_id = f"extract_audio_{video.stem}"
        return await self._run_ffmpeg(cmd, process_id=process_id)

    async def _compose_video_impl(self, person: str, origin_video: Path, fps: int, **kwargs) -> bool:
        """合成最终视频的实现"""

        # -b:v {kbps}k -maxrate {maxrate}k -bufsize {bufsize}k
        # -c:v h264_videotoolbox -q:v 50 -profile:v high -level 19 -coder cabac  -allow_sw 1  for macos hardware

        source_video_dir = common.get_person_origin_dir()
        filename = origin_video.stem
        result_file = common.get_person_video_result_dir(person).joinpath(f'{filename}{self.result_video_type}')
        aac_file = str(source_video_dir.joinpath(f'{filename}.aac'))
        # 先删除结果文件如果存在的话
        common.delete_file(result_file)
        # 构建编码选项
        crf = kwargs.get('crf', self.config.get('crf', 18))
        preset = kwargs.get('preset', self.config.get('preset', 'slow'))
        cmd = f'ffmpeg -framerate {fps} -f image2 -start_number 1 -i "{source_video_dir}/%0d.png" -i "{aac_file}" -c:v libx264 -crf {crf} -preset {preset} -pix_fmt yuv420p -c:a copy -y "{result_file}"'
        process_id = f"compose_video_{person}_{filename}"
        success = await self._run_ffmpeg(cmd, process_id)
        if success:
            common.delete_file(source_video_dir)
            logging.info(f"合成最终视频成功, video: {origin_video}, person: {person}")
        else:
            logging.error(f"合成最终视频失败, video: {origin_video}, person: {person}")
        return success

    async def _concate_to_mp4_impl(self, d: Path, target_dir: Path, ffmpeg_options: str = '') -> str:
        """合并视频的实现"""
        result_video = target_dir.joinpath(d.name + '.mp4').as_posix()
        mylist_file = d.joinpath('mylist.txt').as_posix()
        options = ffmpeg_options or '-c:v libx264 -crf 18 -preset slow'

        cmd = f"ffmpeg -f concat -safe 0 -i '{mylist_file}' -c:a aac -af afftdn {options} -y '{result_video}'"
        process_id = f"concate_to_mp4_{d.name}"
        success = await self._run_ffmpeg(cmd, process_id)
        if success:
            common.delete_file(mylist_file)
        return result_video if success else ''

    @staticmethod
    async def _limited(semaphore: asyncio.Semaphore, task):
        async with semaphore:
            return await task

    @staticmethod
    async def _run_ffmpeg(cmd: str, process_id: str):
        def is_ffmpeg_progress(line: str) -> bool:
            """检查是否是ffmpeg进度行"""
            return bool(FFMPEG_PROGRESS_RE.search(line))

        def on_exception(e: Exception):
            logging.error(f"ffmpeg process error for ID {process_id}: {e}")

        try:
            return_code, _, _ = await shell_utils.async_run(
                cmd,
                output_timeout=300,  # 5分钟无输出超时
                exception_callback=on_exception,
                process_id=process_id,
                use_dedicated_line=True,
                progress_line_checker=is_ffmpeg_progress
            )
            return return_code == 0
        except Exception as e:
            logging.error(f"run ffmpeg failed: '{cmd}' {e}")
            return False
