import shlex
import subprocess
from subprocess import check_output
import cv2
import time
import sys
import io
import logging
import platform
from pathlib import Path
import re
from . import directories
from . import environment
from . import video_operations
from . import file_operations

# 合并视频 + 降噪 + 压缩 + 格式为mp4
def concate_to_mp4(d):
    target_dir = directories.get_mts_video_target_dir()
    video_name = str(target_dir.joinpath(d.name + '.mp4').as_posix())
    mylist_file = str(d.joinpath('mylist.txt').as_posix())
    ffmpeg = get_ffmpeg()
    
    audio_options = __get_audio_options()
    options = f'{audio_options} -af afftdn '
    codec, hwaccel_option = get_perfer_hardware_codec()
    if codec == 'h264_videotoolbox':
        options += '-c:v h264_videotoolbox -q:v 50 -profile:v high -allow_sw 1'
    else:
        options += '-c:v libx264 -crf 18 -preset fast'
    # -vf "crop=min(iw\,ih*16/9):ih:(iw-min(iw\,ih*16/9))/2:0,scale=1280:720"
    cmd = f"""
        {ffmpeg} -f concat -safe 0 -i '{mylist_file}'  
        {options} 
        -y '{video_name}'
    """
    #  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" 
    # cmd = f"{ffmpeg} -f concat -safe 0 -i '{mylist_file}' -c:v copy -c:a aac -af afftdn -y '{video_name}'"
    run(cmd)
    return video_name

def compress_with_logo(video:Path, person, scale=(1280, 720), crf=23, preset='fast', horizontal_speed=30, vertical_speed=60, add_invisible_watermark=True):
    """
    视频压缩+动态水印图片
    :param video:视频路径
    :param person: who
    :param scale: 视频分辨率
    :param crf: 控制输出视频的质量。值越小质量越高，23 是常用的默认值。
    :param preset: 控制编码器的速度和压缩效率之间的权衡。
                    ultrafast->编码速度最快，压缩效率最低。适合需要实时编码的场景。
                    superfast->速度较快，效率略低于 ultrafast。适合某些对速度敏感的应用。
                    veryfast->速度和效率之间的平衡体现在此选择上，适合一般用途。
                    faster->编码速度快于 fast，但压缩效率比很快的速度略低。
                    fast->速度和效率的中间选项，适合许多常规应用。
                    medium->默认设置，速度和效率的合理平衡，适合常规使用。
                    slow->编码速度较慢，但效率更高，产生质量更好的视频。
                    veryslow->编码速度更慢，压缩效率更高。适合对质量要求较高的场景。
    :param horizontal_speed: 控制水印在水平方向上移动的速度，单位为像素/秒。增大该值意味着水印在每秒钟内水平移动的像素数增多，因此水印会移动得更快。
    :param vertical_speed: 控制水印在垂直方向上移动的速度
    :return:是否成功
    :@see: https://trac.ffmpeg.org/wiki/Encode/H.264
    """
    if not video.exists():
        logging.info(f" {video} not exists")
    else:
        logging.info(f"开始压缩原视频并添加logo水印图片, video: {video}, person: {person}")
        # compress and add logo image
        output_dir = directories.get_person_video_stage_dir(person) if add_invisible_watermark else directories.get_person_video_result_dir(person)
        output = str(output_dir.joinpath(video.stem + ".mp4").as_posix())
        logo = str(video_operations.get_logo_watermark_image(person).as_posix())
        w, h = scale
        vinfo = get_video_info(video)
        w = min(w, vinfo[0])
        h = min(h, vinfo[1])
        # codec = command.get_perfer_hardware_codec()
        
        # ffmpeg -i "input.mp4" -i logo.png - filter_complex "
        # [0:v]crop=1280:720,scale=1280:720[v];  
        # [1:v]format=rgba,colorchannelmixer=rr=1:gg=1:bb=1:ra=0.5:ga=0.5:ba=0.5[wm];  
        # [v][wm]overlay=x='if(gte(mod(t*${HORIZONTAL_SPEED}, main_w), main_w - w), main_w - w, mod(t*${HORIZONTAL_SPEED}, main_w))':y='if(gte(mod(t*${VERTICAL_SPEED}, main_h), main_h - h), main_h - h, mod(t*${VERTICAL_SPEED}, main_h - h))'" 
        # -c:a copy -crf 23 -preset fast -y output6.mp4  
        ffmpeg = get_ffmpeg()
        options = ''
        hwaccel_option = ''
        if not add_invisible_watermark:
            codec, hwaccel_option = get_perfer_hardware_codec()
            if codec == 'h264_videotoolbox':
                options = '-c:v h264_videotoolbox -q:v 50 -profile:v high -allow_sw 1'
        else:
            options = f'-c:a copy -crf {crf} -preset {preset}' 
        cmd = f'{ffmpeg} {hwaccel_option} -i "{video}" -i "{logo}" -filter_complex "[0:v]crop={w}:{h},scale={w}:{h}[v];[v][1:v]overlay=x=\'if(gte(mod(t*{horizontal_speed}, main_w), main_w - w), main_w - w, mod(t*{horizontal_speed}, main_w))\':y=\'if(gte(mod(t*{vertical_speed}, main_h), main_h - h), main_h - h, mod(t*{vertical_speed}, main_h - h))\'" {options} -y "{output}"'
        res = run(cmd)
        success = is_run_success(res)
        if success:
            logging.info(f"压缩原视频并添加logo水印图片完成, video: {video}, person: {person}")
        else:
            logging.error(f'压缩原视频并添加logo水印图片失败, video: {video}, person: {person}')
        return success

def scale(video:Path, target_dir:Path, scale=(1280, 720), crf=23, preset='fast'):
    """
    视频压缩+动态水印图片
    :param video:视频路径
    :param scale: 视频分辨率
    :param crf: 控制输出视频的质量。值越小质量越高，23 是常用的默认值。
    :param preset: 控制编码器的速度和压缩效率之间的权衡。
                    ultrafast->编码速度最快，压缩效率最低。适合需要实时编码的场景。
                    superfast->速度较快，效率略低于 ultrafast。适合某些对速度敏感的应用。
                    veryfast->速度和效率之间的平衡体现在此选择上，适合一般用途。
                    faster->编码速度快于 fast，但压缩效率比很快的速度略低。
                    fast->速度和效率的中间选项，适合许多常规应用。
                    medium->默认设置，速度和效率的合理平衡，适合常规使用。
                    slow->编码速度较慢，但效率更高，产生质量更好的视频。
                    veryslow->编码速度更慢，压缩效率更高。适合对质量要求较高的场景。
    :return:是否成功
    :@see: https://trac.ffmpeg.org/wiki/Encode/H.264
    """
    if not video.exists():
        logging.info(f" {video} not exists")
    else:
        logging.info(f"开始压缩原视频, video: {video}")
        # compress and add logo image
        output = str(target_dir.joinpath(video.stem + ".mp4").as_posix())
        w, h = scale
        vinfo = get_video_info(video)
        w = min(w, vinfo[0])
        h = min(h, vinfo[1])
        # codec = command.get_perfer_hardware_codec()
        
        ffmpeg = get_ffmpeg()
        codec, hwaccel_option = get_perfer_hardware_codec()
        if codec == 'h264_videotoolbox':
            options = '-af "afftdn=nf=-25" -c:v h264_videotoolbox -q:v 50 -profile:v high -allow_sw 1'
        else:
            options = f'-af "afftdn=nf=-25" -c:a copy -crf {crf} -preset {preset}' 
        hwaccel_option = ''
        # -vf "hqdn3d=4:2" -af "afftdn=nf=-25"
        # cmd = f'{ffmpeg} {hwaccel_option} -i "{video}" -vf "crop=ih*16/9:ih,scale=1280:720" {options} -y "{output}"'
        cmd = f'{ffmpeg} {hwaccel_option} -i "{video}" -vf "crop=min(iw\,ih*16/9):ih:(iw-min(iw\,ih*16/9))/2:0,scale=1280:720" {options} -y "{output}"'
        res = run(cmd)
        success = is_run_success(res)
        if success:
            logging.info(f"开始压缩原视频, video: {video}")
        else:
            logging.error(f'开始压缩原视频, video: {video}')
        return success

def extractall(person, video, fps, filepartern=".png"):  # 提取所有视频帧
    logging.info(f"开始提取原视频中所有帧, video: {video}, person: {person}")
    origin_dir = str(directories.get_person_origin_dir().as_posix())
    vd = str(Path(video).as_posix())
    ffmpeg = get_ffmpeg()
    cmd = f'{ffmpeg} -i "{vd}" -vf "fps={fps}" {origin_dir}/%0d{filepartern}'
    res = run(cmd)
    success =  is_run_success(res)
    if success:
        logging.info(f"提取原视频中所有帧成功, video: {video}, person: {person}")
    else:
        logging.info(f"提取原视频中所有帧执行失败, video: {video}, person: {person}")
    return success

def extractaudio(origin_dir:Path, video:Path):  # 提取音频
    video_name = Path(video).name
    aac_file = origin_dir.joinpath(f'{video_name}.aac')
    file_operations.delete_file(aac_file)
    vd = str(video.as_posix())
    ffmpeg = get_ffmpeg()
    try:
        cmd = f'{ffmpeg} -i "{vd}" -vn -c:a copy "{str(aac_file.as_posix())}"'
        return is_run_success(run(cmd))
    except Exception as e:
        logging.error(f"aac failed: video: {vd}", e)
        return False
    
def audio(video, target_dir):
    aac_file = Path(target_dir).joinpath(Path(video).stem + ".m4a").as_posix()
    vd = Path(video).as_posix()
    ffmpeg = get_ffmpeg()
    if video_operations.is_audio_file(video):
        cmd = f'{ffmpeg} -i "{vd}" -af afftdn -c:a aac -b:a 96k  -y "{aac_file}"'
    else:
        options = __get_audio_options()
        cmd = f'{ffmpeg} -i "{vd}" -vn {options} -y "{aac_file}"'
    run(cmd)
    if Path(aac_file).exists():
        logging.info(f"提取音频成功: {vd}")
        return True
    return False

def __get_audio_options():
    options = ''
    if environment.is_compress_audio():
        option = environment.get_compress_audio_options()
        options = f'-c:a aac {option}' 
    else:
        options = '-c:a copy'
    return options

def output(person, origin, video, fps, mtype=".png", vtype=".mp4", crf=19, preset='slow'):  # 视频合成
    """
    进行ffmpeg合成
    :param origin:原视频路径
    :param video: 导出视频名
    :param fps: 帧率
    :param kbps: 目标码率
    :param maxrate: 最大码率,控制瞬时比特率
    :param bufsize: 缓冲区大小,通常设置为maxrate的2倍到2.5倍，让编码器有足够的缓冲来平滑比特率的波动
    :param crf: 0~51,设置 CRF 值为 18，以确保高质量输出。
    :param mtype: 输入图片类型
    :param vtype: 视频类型
    :return: 是否成功
    """
    # 先删除结果文件如果存在的话
    origin_dir = directories.get_person_origin_dir()
    video_result_dir = directories.get_person_video_result_dir(person)
    result_file = video_result_dir.joinpath(video + vtype)
    file_operations.delete_file(result_file)
    result_file_str = str(result_file.as_posix())
    options = f'-c:v libx264 -crf {crf} -preset {preset}'
    video_name = Path(origin).name
    aac_file = str(Path(origin_dir).joinpath(f'{video_name}.aac'))
    ffmpeg = get_ffmpeg()
    # -b:v {kbps}k -maxrate {maxrate}k -bufsize {bufsize}k 
    # -c:v h264_videotoolbox -q:v 50 -profile:v high -level 19 -coder cabac  -allow_sw 1  for macos hardware
    comm = f'{ffmpeg} -framerate {fps} -f image2 -start_number 1 -i "{origin_dir}/%0d{mtype}" -i "{aac_file}" {options} -pix_fmt yuv420p -c:a copy -y "{result_file_str}"'
    return is_run_success(run(comm))

def get_video_info(video):
    videoc = cv2.VideoCapture(str(video))
    # 获取视频的宽度（单位：像素）
    width = videoc.get(cv2.CAP_PROP_FRAME_WIDTH)
    # 获取视频的高度（单位：像素）
    height = videoc.get(cv2.CAP_PROP_FRAME_HEIGHT)
    frame_count = int(videoc.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(videoc.get(cv2.CAP_PROP_FPS))
    videoc.release()
    return [width, height, frame_count, fps]

def get_perfer_hardware_codec():
    # ffmpeg -hwaccels
    ffmpeg = get_ffmpeg()
    # 是否是Apple M芯片
    if is_exists(run(f'{ffmpeg} -encoders | grep videotoolbox')):
        return ('h264_videotoolbox', '-hwaccel videotoolbox ')
    # 如果您的系统有 NVIDIA GPU，可以使用 NVENC 进行编码
    if is_exists(run(f'{ffmpeg} -encoders | grep nvenc')):
        return 'h264_nvenc'
    # 如果您的系统有支持 Intel Quick Sync 的处理器，可以使用 QSV 进行编码
    if is_exists(run(f'{ffmpeg} -encoders | grep qsv')):
        return 'h264_qsv'
    # 如果您使用的是支持 VCE 的 AMD GPU，可以使用 AMF 进行编码。
    if is_exists(run(f'{ffmpeg} -encoders | grep amf')):
        return 'h264_amf'
    # 如果都没有，使用软件libx264编码
    return ('libx264', '')

def run(command_string):
    logging.info(f"begin to run command: {command_string}")
    # if is_windows():
    #     os.system('UTF-8') 

    start = time.time()
    # 将整个命令字符串按管道符拆分，并去除多余空格  
    commands = [cmd.strip() for cmd in command_string.split("|") if cmd.strip()]  
    
    # 存储所有进程的列表  
    processes = []  
    try: 
        for i, command in enumerate(commands):  
            # 拆分每个命令的参数  
            args = shlex.split(command)  
            if i == 0:  
                # 第一个命令，直接执行  
                process = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)  
            else:  
                # 后续命令，将前一个命令的输出作为输入  
                process = subprocess.Popen(args, stdin=processes[-1].stdout, stdout=subprocess.PIPE, text=True)  
            processes.append(process)  

        # 关闭第一个命令的 stdout 以允许后续操作  
        for process in processes[:-1]:  
            process.stdout.close()  
        
        # 获取最后一个进程的输出  
        output, errors = processes[-1].communicate()
        end = time.time()
        elapsed_time = end - start  # 计算耗时
        logging.info(f"Function took {elapsed_time:.2f} seconds to complete.")
        if processes[-1].returncode != 0: 
            logging.error(f"Command run failed with return code {processes[-1].returncode}, errors: {errors}")
            return "failed"
        else:
            return output if output else ''
    except Exception as e:  
        logging.exception("An error occurred while running the command.", e)  
        return "failed"  

def is_exists(output):
    return output != 'failed' and output != ''

def get_ffmpeg():
    if is_windows():
        return str(Path('ffmpeg/bin/ffmpeg.exe').as_posix())
    else:
        return 'ffmpeg'
    
def is_windows():
    """Checks if the current operating system is Windows."""
    return platform.system() == 'Windows'

def get_cmd_prefix_for_windows():
    if is_windows():
        return 'py -m '
    return ''

def is_run_success(res):
    return res != 'failed'

def extract_list_by_regex(regex, text):
    match = re.search(regex, text, re.S)
    if match:
        g = match.group(1)
        filenames = re.findall(r"F\s+-\s+(.+)", g)
        print("filenames:", filenames)
        return filenames
    else:
        return []
