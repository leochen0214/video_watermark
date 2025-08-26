import asyncio
import logging
import time

from pathlib import Path
from typing import Optional, Callable

from . import common
from . import tool

SEMAPHORE = asyncio.Semaphore(3)


def main():
    common.init()
    asyncio.run(batch_upload())


async def batch_upload():
    """批量上传所有人员的视频和元数据"""
    for person in common.get_person_names():
        try:
            logging.info(f"开始为人员： {person} 上传")
            start = time.time()
            await upload_files_for_person(person)
            end = time.time()
            logging.info(f"Finished upload for person: {person}, costs {end - start:.2f} seconds")
        except Exception as e:
            logging.error(f"上传人员 {person} 数据失败: {str(e)}", exc_info=True)


async def upload_files_for_person(person):
    """上传单个人员的所有文件"""

    # 并行上传视频和元数据
    upload_tasks = [
        upload_files_by_type(person, "videos"),
        upload_files_by_type(person, "metadata")
    ]
    results = await asyncio.gather(*upload_tasks, return_exceptions=True)

    # 检查结果，如果有异常可以处理
    for result in results:
        if isinstance(result, Exception):
            logging.error(f"上传任务失败: {result}")


async def upload_files_by_type(person, file_type):
    """
    通用文件上传方法
    :param person: 人员名称
    :param file_type: 文件类型 ('videos' 或 'metadata')
    """

    def upload_success_callback(local_path, remote_file):
        if common.is_delete_after_upload_success() and file_type == 'videos':
            common.delete_file(local_path)
            logging.info(f"删除已上传完毕的文件, file: {local_path}")

    course_name = common.get_current_course_name()
    remote_dir = f"{common.get_root_remote_dir()}/{file_type}/{person}/{course_name}"

    # 根据文件类型获取本地目录
    local_dir = (
        common.get_person_video_result_dir(person) if file_type == "videos"
        else common.get_person_metadata_result_dir(person)
    ).resolve().as_posix()

    pending_files = await get_pending_to_upload_files(person, local_dir, remote_dir)
    logging.info(f'type: {file_type}, pending_files: {len(pending_files)}, person: {person}')
    if pending_files:
        for file in pending_files:
            logging.info(f'pending to upload file: {file}')
        return await tool.batch_upload(
            SEMAPHORE,
            pending_files,
            lambda _: remote_dir,  # 统一使用固定远程目录
            overwrite=True,
            upload_success_callback=upload_success_callback
        )
    return True


async def get_pending_to_upload_files(person, local_dir: str, remote_dir: str,
                                      file_filter: Optional[Callable[[Path], bool]] = None):
    """
    只有当本地文件与远程文件不同，或者文件仅存在于本地时，文件才会被添加到待上传列表中
    """
    local_files = common.get_files(local_path=local_dir, recursive=True, file_filter=file_filter)
    if not local_files:
        return []
    remote_files = await tool.list_remote_dir(remote_dir, recursive=True)
    logging.info(f'remote_files: {len(remote_files)}')
    if not remote_files:
        return local_files

    pending_to_upload_files = []
    for local_file_path in local_files:
        if is_need_to_upload(person, local_file_path, remote_files):
            pending_to_upload_files.append(local_file_path.resolve())
    return pending_to_upload_files


def is_need_to_upload(person, local_file_path, remote_files):
    local_file_size = common.get_file_size(local_file_path)
    if local_file_size == 0:
        return False

    # 正在处理中的不能加入上传列表中
    if local_file_path.suffix == common.get_result_video_type() and not common.is_already_processed(local_file_path, person):
        logging.info(f'还未处理完成的不能加入上传列表中， local_file_path: {local_file_path}, person: {person}')
        return False
    local_filename = local_file_path.name
    # 如果local_filename在remote_files中且文件大小差不多大小，就认为已经上传成功，不需要加入上传列表中
    for remote_file in remote_files:
        if (local_filename == remote_file['name']
                and is_size_approximately_advanced(remote_file['size'], local_file_size, 0.1)):
            return False
    return True


def parse_file_size(size_str):
    """
    智能解析文件大小字符串，支持小数点和多种单位
    支持格式: 82.67 MB, 1.5GB, 1024B, 2.5K, 3.14M 等
    """
    import re

    # 匹配数字（支持小数点）和单位
    match = re.match(r'(\d+\.?\d*)\s*([BKMGT]?B?)', size_str.upper().strip())
    if not match:
        return 0

    try:
        size = float(match.group(1))  # 使用float支持小数
        unit = match.group(2)
    except ValueError:
        return 0

    # 单位转换
    unit_multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
        'K': 1024,  # 简写支持
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4
    }

    # 处理简写单位（如 K, M, G, T）
    if len(unit) == 1 and unit in ['K', 'M', 'G', 'T']:
        multiplier = unit_multipliers.get(unit, 1)
    else:
        multiplier = unit_multipliers.get(unit, 1)

    return int(size * multiplier)  # 返回整数字节数

def is_size_approximately_advanced(size_str, target_size, tolerance=0.1):
    """
    高级大小比较，支持百分比容差
    """
    actual_size = parse_file_size(size_str)
    if actual_size == 0:
        return False

    # 使用百分比容差
    difference = abs(actual_size - target_size) / target_size
    # print(f'size_str: {size_str}, actual_size: {actual_size}, target_size: {target_size}, difference: {difference}')
    return difference <= tolerance


if __name__ == '__main__':
    main()
