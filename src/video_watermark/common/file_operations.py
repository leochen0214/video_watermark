"""File operation utilities."""

import json
import shutil
import logging
from pathlib import Path
from typing import Callable, Optional,List


def delete_file(filename):
    """Delete file or directory."""
    f = Path(filename)
    if not f.exists():
        logging.info(f"{filename} not exists")
    else:
        file_type = None
        if f.is_dir():
            file_type = "directory"
            shutil.rmtree(f)
        else:
            file_type = "file"
            f.unlink(missing_ok=True)
        logging.info(f"delete {file_type} success: {filename}")


def delete_then_create(filename):
    """Delete and then create directory."""
    delete_file(filename)
    from .directories import create_dir
    create_dir(filename)


def write_lines_to_file(filename, lines):
    """Write lines to file."""
    with Path(filename).open('w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + "\n")


def read_all_lines(filename: Path):
    """Read all lines from file."""
    if not filename.exists():
        return []
    with filename.open(mode='r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def write_json_to_file(data, filename):
    """Write JSON data to file."""
    with Path(filename).open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_json_file(filename: Path):
    """Read JSON data from file."""
    if not filename.exists():
        return {}
    with filename.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def get_file_size(file_path: str | Path) -> int:
    """获取本地文件的大小（字节数）"""
    try:
        p = Path(file_path) if isinstance(file_path, str) else file_path
        if not p.exists():
            return 0
        return p.stat().st_size  # 返回字节数
    except Exception as e:  # 捕获其他可能的异常（如权限错误等）
        print(f"获取文件大小时出错: {e}")
        return 0

def get_files(local_path: str, recursive: bool = True, file_filter: Optional[Callable[[Path], bool]] = None) -> List[
    Path]:
    """
       Recursively or non-recursively collects files from a local directory path with optional filtering.

       Args:
           local_path: String path to the target directory or file
           recursive: If True, searches subdirectories recursively (default: True)
           file_filter: Optional filter function that takes a Path and returns a boolean.
                       If None, uses default filter that includes normal files and excludes hidden files (starting with '.')

       Returns:
           List of Path objects matching the criteria. Returns empty list if path doesn't exist.
           For directory input: Returns filtered files in directory
           For file input: Returns single-element list containing the file if it exists

       Examples:
           # Get all python files recursively
           get_files('/project', file_filter=lambda f: f.suffix == '.py')

           # Get immediate files only (non-recursive)
           get_files('/project', recursive=False)
       """

    files = []
    p = Path(local_path)
    # local_path不存在的话，返回空
    if not p.exists():
        return []

    if p.is_dir():
        # 设置默认文件过滤器
        if file_filter is None:
            file_filter = lambda f: f.is_file() and not f.name.startswith('.')
        # 选择遍历方法
        iterator = p.rglob('*') if recursive else p.glob('*')
        for file in iterator:
            if file_filter(file):
                files.append(file)
    else:
        files.append(p)
    return files


def process_files(
        source_dir: Path,
        process_func: Callable[[Path], None],
        file_filter: Optional[Callable[[Path], bool]] = None,
        recursive: bool = True
) -> None:
    """
    Generic file processing template method.

    Args:
        source_dir: Source directory path
        process_func: File processing function
        file_filter: File filter function
        recursive: Whether to process subdirectories recursively
    """
    if file_filter is None:
        file_filter = lambda f: f.is_file() and not f.name.startswith('.')

    iterator = source_dir.rglob('*') if recursive else source_dir.glob('*')

    for file in iterator:
        if file_filter(file):
            try:
                process_func(file)
            except Exception as e:
                logging.error(f"处理失败 {file}: {str(e)}", exc_info=True)


def has_free_space(f):
    """Check if there's enough free space for file."""
    total, used, free = shutil.disk_usage(__file__)
    file_size = Path(f).stat().st_size
    logging.info(f"total: {total}, used: {used}, free: {free}, file_size: {file_size}")
    return free > 2 * file_size