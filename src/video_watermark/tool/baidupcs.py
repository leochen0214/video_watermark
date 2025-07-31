import asyncio
import logging
import re
from collections import deque
from pathlib import Path

from natsort import natsorted

from ..common import file_operations
from ..common import environment
from ..tool import async_run

# 百度网盘上传工具命令
BAIDUPCS = "BaiduPCS-Go"
UPLOAD_PROGRESS_RE = re.compile(r"([MG])B/s.*\s+in\s+")


async def batch_upload(semaphore: asyncio.Semaphore, file_list, remote_dir_callback, overwrite=False,
                       upload_success_callback=None):
    """
    Batch upload files with concurrency control.

    Args:
        semaphore: Semaphore to control concurrent uploads
        file_list: List of local file paths to upload
        remote_dir_callback: Callback function that takes local file path and returns remote directory
        overwrite: Whether to overwrite existing files (default: False)
        upload_success_callback: Optional callback executed after successful upload

    Returns:
        List of upload results (may contain exceptions if return_exceptions=True)
    """

    async def limited_upload(task):
        async with semaphore:
            return await task

    tasks = []
    for local_file in file_list:
        task = limited_upload(
            upload_file(local_file, remote_dir_callback(local_file), overwrite, upload_success_callback))
        tasks.append(task)
    # 如果你希望即使部分任务失败也继续执行，可以设置 return_exceptions = True：
    return await asyncio.gather(*tasks, return_exceptions=True)


async def upload_file_with_limit(semaphore: asyncio.Semaphore, local_path: Path, remote_dir, overwrite=False,
                                 upload_success_callback=None):
    """
    Upload a single file with concurrency limit.

    Args:
        semaphore: Semaphore to control concurrent uploads
        local_path: Local file path to upload
        remote_dir: Remote directory to upload to
        overwrite: Whether to overwrite existing file (default: False)
        upload_success_callback: Optional callback executed after successful upload

    Returns:
        bool: True if upload succeeded, False otherwise
    """
    async with semaphore:
        return await upload_file(local_path, remote_dir, overwrite, upload_success_callback)


async def upload_file(local_path: Path, remote_dir, overwrite=False, upload_success_callback=None):
    """
    Upload a single file to Baidu PCS.

    Args:
        local_path: Local file path to upload
        remote_dir: Remote directory to upload to
        overwrite: Whether to overwrite existing file (default: False)
        upload_success_callback: Optional callback executed after successful upload

    Returns:
        bool: True if upload succeeded, False otherwise
    """

    def is_upload_progress_line(line: str) -> bool:
        """检查是否是ffmpeg进度行"""
        return bool(UPLOAD_PROGRESS_RE.search(line))

    def on_timeout():
        logging.error(f"upload process for '{local_path}' timed out due to inactivity.")

    def on_exception(e: Exception):
        logging.error(f"upload process for '{local_path}' error: {e}")

    if not local_path.exists():
        logging.info(f"文件不存在，跳过: '{local_path}'")
        return None

    remote_file = f"{remote_dir}/{Path(local_path).name}"
    try:
        if overwrite:
            await delete_remote_file(remote_file)
        upload_cmd = f"{BAIDUPCS} upload '{local_path}' '{remote_dir}'"
        return_code, stdout, _ = await async_run(
            upload_cmd,
            timeout=environment.get_upload_timeout(),
            output_timeout=30,  # 30s idle timeout
            timeout_callback=on_timeout,
            exception_callback=on_exception,
            capture_output=True,
            use_dedicated_line=True,  # 启用专用行显示
            progress_line_checker=is_upload_progress_line  # 传入进度行检查函数
        )
        logging.info(f"upload stdout: {stdout}")
        if return_code == 0 and "上传文件成功" in stdout:
            logging.info(f"upload success, file: {local_path} -> {remote_dir}")
            if upload_success_callback:
                try:
                    if asyncio.iscoroutinefunction(upload_success_callback):
                        await upload_success_callback(local_path, remote_file)
                    else:
                        upload_success_callback(local_path, remote_file)
                except Exception as e:
                    logging.error(f"upload_success_callback occur error, file: {local_path}", e)
            return True
    except Exception as e:
        logging.error(f"upload occur error, file: {local_path}", e)
    return False


async def delete_remote_file(remote_file: str):
    delete_cmd = f"{BAIDUPCS} rm '{remote_file}'"
    return_code, stdout, _ = await async_run(delete_cmd, capture_output=True)
    return return_code == 0 and "操作成功" in stdout


async def list_remote_dir(remote_dir: str, recursive: bool = False):
    """
    List contents of a remote directory.

    Args:
        remote_dir: Remote directory path to list
        recursive: Whether to list recursively (default: False)

    Returns:
        List of file/directory info dictionaries containing:
        - name: File/directory name
        - size: Size string
        - date: Modification date
        - type: 'd' for directory or 'f' for file
    """

    files = await _do_list(remote_dir)
    if not recursive:
        return files

    all_files = []
    dirs_to_process = deque()  # 使用双端队列

    # 初始目录的子目录先按自然顺序排序
    root_dirs = [
        f"{remote_dir.rstrip('/')}/{file_info['name'].rstrip('/')}"
        for file_info in files
        if file_info['type'] == 'd'
    ]
    dirs_to_process.extend(natsorted(root_dirs))

    # 文件直接加入结果
    all_files.extend(
        file_info
        for file_info in files
        if file_info['type'] == 'f'
    )

    while dirs_to_process:
        cur_remote_dir = dirs_to_process.popleft()  # 按自然顺序出队
        cur_files = await _do_list(cur_remote_dir)

        new_dirs = []
        for file_info in cur_files:
            if file_info['type'] == 'd':
                sub_remote_path = f"{cur_remote_dir.rstrip('/')}/{file_info['name'].rstrip('/')}"
                new_dirs.append(sub_remote_path)
            else:
                # 保持完整路径
                file_info['name'] = f"{cur_remote_dir}/{file_info['name']}"
                all_files.append(file_info)

        # 新发现的目录按自然排序后加入队列
        dirs_to_process.extend(natsorted(new_dirs))

    logging.info(f"Found {len(all_files)} files")
    return all_files


async def is_uploaded(local_file_path, remote_file_path):
    """
    Check if a local file has already been uploaded by comparing sizes.

    Args:
        local_file_path: Path to local file
        remote_file_path: Path to remote file

    Returns:
        bool: True if file exists remotely with matching size
    """
    _, remote_file_size_bytes = await get_remote_file_metadata(remote_file_path)
    local_file_size_bytes = file_operations.get_file_size(local_file_path)
    return remote_file_size_bytes == local_file_size_bytes


async def get_remote_file_metadata(remote_file_path: str):
    """
    Get metadata for a remote file.

    Args:
        remote_file_path: Path to remote file

    Returns:
        tuple: (file_name, file_size_bytes)
    """
    cmd = f"{BAIDUPCS} meta '{remote_file_path}'"
    return_code, stdout, _ = await async_run(cmd, capture_output=True)
    lines = stdout.split('\n')
    file_name = ''
    file_size_bytes = 0
    for line in lines:
        if '文件名称' in line:
            file_name = line.split('文件名称')[1].strip()
        elif '文件大小' in line:
            # 提取文件大小部分，并取第一个数值（字节数）
            size_part = line.split('文件大小')[1].strip()
            file_size_bytes = int(size_part.split(',')[0].strip())
    return file_name, file_size_bytes


async def ensure_remote_dir_exists(remote_dir: str):
    """
       Ensure a remote directory exists, creating it if necessary.

       Args:
           remote_dir: Remote directory path to check/create
    """
    if await is_remote_exists(remote_dir):
        logging.info(f"remote_dir: '{remote_dir}' is already exists")
    else:
        cmd = f"{BAIDUPCS} mkdir '{remote_dir}'"
        return_code, _, _ = await async_run(cmd)
        if return_code == 0:
            logging.info(f"create remote_dir: '{remote_dir}' success")
        else:
            logging.error(f"create remote_dir: '{remote_dir}' failed")


async def is_remote_exists(remote_file: str) -> bool:
    """
        Check if a remote file or directory exists.

        Args:
            remote_file: Remote path to check

        Returns:
            bool: True if the path exists remotely
    """
    cmd = f"{BAIDUPCS} ls '{remote_file}'"
    # 文件或目录不存在
    return_code, stdout, _ = await async_run(cmd, capture_output=True)
    return return_code == 0 and not "文件或目录不存在" in stdout


async def _do_list(remote_dir: str):
    """
       Internal method to list directory contents from Baidu PCS.

       Args:
           remote_dir: Remote directory path to list

       Returns:
           List of parsed file/directory info dictionaries
    """
    list_cmd = f"{BAIDUPCS} ls '{remote_dir}'"
    return_code, stdout, _ = await async_run(list_cmd, capture_output=True)
    if return_code != 0 or not stdout:
        return []
    files = []
    lines = stdout.strip().split('\n')
    # 找到数据开始的行（跳过标题行）
    data_line_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('#') and '文件大小' in line:
            data_line_start = i + 1
            break
    if data_line_start == -1:
        return []
    # 解析文件数据行
    for line in lines[data_line_start:]:
        line = line.strip()
        if not line or line.startswith('总:') or line.startswith('----'):
            continue

        # 使用正则表达式解析每行数据
        # 格式: 序号 文件大小 日期 时间 文件名
        pattern = r'^\s*\d+\s+(\S+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.+)$'
        match = re.match(pattern, line)

        if match:
            size = match.group(1)
            date = match.group(2)
            name = match.group(3)
            # 判断文件类型
            file_type = 'd' if name.endswith('/') else 'f'

            files.append({
                'name': name,
                'size': size,
                'date': date,
                'type': file_type
            })
    return files
