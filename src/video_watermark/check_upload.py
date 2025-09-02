import asyncio
import logging
import re

from video_watermark import common
from video_watermark import tool


def main():
    common.init()
    asyncio.run(check_upload())


async def check_upload():
    course_name = common.get_current_course_name()
    total = len(common.get_videos(common.get_video_dir()))
    for person in common.get_person_names():
        try:
            remote_dir = f"{common.get_root_remote_dir()}/videos/{person}/{course_name}"
            stdout = await tool.get_list_info(remote_dir)
            m = extract_info(stdout)
            total_size_str = m.get('total_size')
            file_count = m.get('file_count')
            if file_count is None or file_count != total:
                logging.info(f"未上传完成, person: {person}, {m}")
            else:
                logging.info(f"已经上传完成, person: {person}, {m}")
        except Exception as e:
            logging.error(f"上传人员 {person} 数据失败: {str(e)}", exc_info=True)


def extract_info(data):
    # 匹配总大小（支持B, GB, MB, KB, TB等单位）
    total_size_pattern = r'总:\s*([\d.]+)\s*(GB|MB|KB|B|TB|gb|mb|kb|b|tb)'
    # 匹配文件总数
    file_count_pattern = r'文件总数:\s*(\d+)'

    # 提取总大小
    total_size_match = re.search(total_size_pattern, data, re.IGNORECASE)
    if total_size_match:
        size_value = total_size_match.group(1)
        size_unit = total_size_match.group(2).upper()
        total_size = f"{size_value}{size_unit}"
    else:
        total_size = None

    # 提取文件总数
    file_count_match = re.search(file_count_pattern, data)
    file_count = int(file_count_match.group(1)) if file_count_match else None

    return {
        "total_size": total_size,
        "file_count": file_count
    }


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
