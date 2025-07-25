import asyncio
import logging
import shlex
import subprocess
import sys
import time
import traceback
import threading
from typing import Optional, Callable, Awaitable, Union, Tuple, List, Dict, Any

DEFAULT_LIMIT = 1024 * 1024  # 1MB
DEFAULT_OUTPUT_TIMEOUT = 5.0  # seconds
PROCESS_TERMINATE_TIMEOUT = 5  # seconds

# Type aliases
OutputCallback = Callable[[str], Union[None, Awaitable[None]]]
TimeoutCallback = Callable[[], Union[None, Awaitable[None]]]
ExceptionCallback = Callable[[Exception], Union[None, Awaitable[None]]]

# 全局变量管理进度显示
_progress_lines = {}  # {process_id: line_number}
_next_line = 0
_progress_lock = threading.Lock()


async def async_run(cmd: str,
                    timeout: Optional[float] = None,  # None means no timeout
                    output_timeout: Optional[float] = None,
                    output_callbacks: Optional[List[OutputCallback]] = None,
                    timeout_callback: Optional[TimeoutCallback] = None,
                    exception_callback: Optional[ExceptionCallback] = None,
                    stdin_data: Optional[bytes] = None,
                    cwd: Optional[str] = None,
                    env: Optional[Dict[str, str]] = None,
                    limit: int = DEFAULT_LIMIT,  # 默认1MB缓冲区
                    capture_output: bool = False,
                    print_cmd=True,
                    process_id: Optional[str] = None,  # 新增参数
                    use_dedicated_line: bool = False,
                    progress_line_checker: Optional[Callable[[str], bool]] = None  # 新增参数
                    ) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Execute a shell command asynchronously with comprehensive monitoring and callback support.

    This function provides powerful command execution capabilities including:
    - Timeout control (total timeout and output idle timeout)
    - Real-time output processing and callbacks
    - Dedicated line display mode (suitable for progress bars and real-time updates)
    - Exception handling and cleanup
    - Output capture and buffer control

    Args:
        :param cmd: The shell command to execute
        :param timeout: Total execution timeout in seconds (None for no timeout)
        :param output_timeout: Timeout for output inactivity in seconds (None for no timeout)
        :param output_callbacks: List of callbacks for processing real-time output
        :param timeout_callback: Callback to execute on timeout
        :param exception_callback: Callback to execute on exception
        :param stdin_data: Data to send to stdin (None for no stdin)
        :param cwd: Working directory for the command
        :param env: Environment variables for the command
        :param limit: Buffer size limit for stdout/stderr
        :param capture_output: Whether to capture and return the full output(default: False)
        :param print_cmd: Whether to logging command str(default: True)
        :param process_id (Optional[str]): Unique identifier for the process, used for progress tracking
        :param use_dedicated_line (bool): Enable dedicated line display mode for progress updates (default: False)
        :param progress_line_checker (Optional[Callable[[str], bool]]): Function to identify progress lines for dedicated display

    :Returns:
        Tuple of (return_code, stdout, stderr) where stdout/stderr are None if not captured


    Usage Examples:
        # Basic command execution
        return_code, stdout, stderr = await async_run("ls -la", capture_output=True)

        # With timeout and callbacks
        def on_output(line):
            print(f"Output: {line}")

        return_code, _, _ = await async_run(
            "long_running_command",
            timeout=300,
            output_timeout=60,
            output_callbacks=[on_output]
        )

        # Progress monitoring with dedicated line display
        def is_progress(line):
            return "progress:" in line.lower()

        return_code, _, _ = await async_run(
            "download_command",
            process_id="download_1",
            use_dedicated_line=True,
            progress_line_checker=is_progress
        )
    """

    start_time = time.time()
    if print_cmd:
        logging.info(f"Running command: {cmd}")

    stdout_data: List[str] = [] if capture_output else []
    stderr_data: List[str] = [] if capture_output else []

    async def handle_stream(
            stream: asyncio.StreamReader,
            is_stderr: bool,
            last_activity_time: List[float]
    ) -> None:
        buffer = b""
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(stream.read(4096), timeout=output_timeout)
                    last_activity_time[0] = time.time()

                    if not chunk:
                        break

                    buffer += chunk
                    # Handle both \n and \r as line separators for ffmpeg progress
                    lines = buffer.replace(b'\r', b'\n').split(b'\n')
                    buffer = lines.pop()

                    for line_bytes in lines:
                        if not line_bytes:
                            continue
                        line_text = line_bytes.decode('utf-8', errors='replace').strip()
                        if line_text:
                            await process_output(line_text, is_stderr)

                except asyncio.TimeoutError:
                    if output_timeout and time.time() - last_activity_time[0] > output_timeout:
                        raise
                    continue
                except asyncio.CancelledError:
                    # Task was cancelled, exit gracefully
                    break
                except Exception as e:
                    logging.error(f"Error reading process output: {e}")
                    break

            if buffer:
                line_text = buffer.decode('utf-8', errors='replace').strip()
                if line_text:
                    await process_output(line_text, is_stderr)
        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass
        finally:
            # 如果使用专用行显示，不需要额外的换行
            if not use_dedicated_line and is_stderr:
                sys.stdout.write('\n')
                sys.stdout.flush()

    async def process_output(line_text: str, is_stderr: bool) -> None:
        # 先检查是否是进度行
        is_progress_line = progress_line_checker and progress_line_checker(line_text)

        # 只有非进度行才添加到capture数据中
        if capture_output and not is_progress_line:
            if is_stderr:
                stderr_data.append(line_text)
            else:
                stdout_data.append(line_text)

        # 如果使用专用行显示
        if use_dedicated_line and process_id:
            # 使用传入的进度行检查函数
            if is_progress_line:
                _display_on_dedicated_line(line_text, process_id)
                return  # 进度行不再输出到其他地方
            else:
                # 非进度行正常输出到日志
                if line_text.strip():
                    print(f"[{process_id}] {line_text}")
        elif not use_dedicated_line and line_text.strip():
            # 如果不使用专用行，正常输出到日志
            print(f"[{process_id or 'unknown'}] {line_text}")

        if output_callbacks:
            for callback in output_callbacks:
                await execute_callback(callback, line_text)

    process = None
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            limit=limit
        )

        # 生成进程ID用于多行显示
        if not process_id:
            process_id = f"pid:{process.pid}"

        if use_dedicated_line and process_id:
            _allocate_progress_line(process_id)

        # Start output handling tasks
        # Track last activity time for true idle timeout
        last_stdout_activity = [time.time()]
        last_stderr_activity = [time.time()]

        stdout_task = asyncio.create_task(
            handle_stream(process.stdout, False, last_stdout_activity)
        )
        stderr_task = asyncio.create_task(
            handle_stream(process.stderr, True, last_stderr_activity)
        )

        # Send stdin data if provided
        if stdin_data and process.stdin:
            try:
                process.stdin.write(stdin_data)
                await process.stdin.drain()
                process.stdin.close()
            except Exception as e:
                logging.warning(f"Error writing to stdin: {e}")

        # Handle main timeout (None means wait forever)
        try:
            if timeout is not None:
                return_code = await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                return_code = await process.wait()
        except asyncio.TimeoutError:
            await execute_callback(timeout_callback)
            raise

        # Cancel output handlers gracefully after process completes
        stdout_task.cancel()
        stderr_task.cancel()

        # Wait for output handlers with reasonable timeout
        try:
            await asyncio.gather(stdout_task, stderr_task)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            # Expected when tasks are cancelled
            pass
        except Exception as ex:
            logging.warning(f"Exception occured for output handlers to complete: {ex}\n{traceback.format_exc()}")

        stdout_result = '\n'.join(stdout_data) if capture_output else None
        stderr_result = '\n'.join(stderr_data) if capture_output else None
        execution_time = time.time() - start_time
        logging.info(f"run cmd costs {execution_time:.2f}s")
        return return_code, stdout_result, stderr_result
    except Exception as e:
        await execute_callback(exception_callback, e)
        raise
    finally:
        # 释放专用行
        if use_dedicated_line and process_id:
            _free_progress_line(process_id)
            # 确保在程序结束时保留最后的输出
            sys.stdout.write('\n')
            sys.stdout.flush()

        if process and process.returncode is None:
            await terminate_process(process)


async def terminate_process(process: asyncio.subprocess.Process) -> None:
    """Gracefully terminate a process with timeout."""
    try:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=PROCESS_TERMINATE_TIMEOUT)
        except asyncio.TimeoutError:
            logging.warning(f"Process {process.pid} did not terminate, killing it")
            process.kill()
            await process.wait()
    except ProcessLookupError:
        pass  # Process already finished
    except Exception as e:
        logging.error(f"Error terminating process: {e}")


async def execute_callback(
        callback: Union[OutputCallback, TimeoutCallback, ExceptionCallback],
        *args: Any
) -> None:
    """Execute a callback with proper error handling."""

    if not callback:
        return

    try:
        if asyncio.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)
    except Exception as e:
        logging.warning(f"Callback execution failed: {e}\n{traceback.format_exc()}")


def run(cmd):
    logging.info(f"begin to run command: {cmd}")
    # if is_windows():
    #     os.system('UTF-8')

    start = time.time()
    # 将整个命令字符串按管道符拆分，并去除多余空格
    commands = [cmd.strip() for cmd in cmd.split("|") if cmd.strip()]

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


def is_run_success(res):
    return res != 'failed'


def _allocate_progress_line(process_id: str) -> int:
    """为进程分配一个进度显示行"""
    global _next_line
    with _progress_lock:
        if process_id not in _progress_lines:
            _progress_lines[process_id] = _next_line
            _next_line += 1
        return _progress_lines[process_id]


def _free_progress_line(process_id: str):
    """释放进度显示行"""
    with _progress_lock:
        if process_id in _progress_lines:
            line_num = _progress_lines[process_id]
            del _progress_lines[process_id]
            # 移动到该行但不清除内容，保留最后的进度信息
            sys.stdout.write(f"\033[{line_num + 1};1H")
            # 移动到行尾并换行，确保后续输出不会覆盖
            sys.stdout.write('\033[999C\n')
            sys.stdout.flush()


def _display_on_dedicated_line(text: str, process_id: str):
    """在专用行显示文本"""
    line_num = _allocate_progress_line(process_id)

    # 格式化显示内容，确保包含进程ID信息
    display_text = f"[{process_id}] {text}"

    with _progress_lock:
        # 保存当前光标位置
        sys.stdout.write("\033[s")
        # 移动到指定行
        sys.stdout.write(f"\033[{line_num + 1};1H")
        # 清除该行并写入新内容，添加足够的空格确保清除之前的内容
        sys.stdout.write(f"\033[K{display_text:<120}")
        # 恢复光标位置
        sys.stdout.write("\033[u")
        sys.stdout.flush()
