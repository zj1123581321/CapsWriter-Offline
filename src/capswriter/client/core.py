# coding: utf-8

import os
import sys
import asyncio
import signal
from pathlib import Path
from platform import system
from typing import List



import typer
import colorama
import keyboard

from ..config import ClientConfig as Config
from .utils.client_cosmic import console, Cosmic
from .utils.client_stream import stream_open, stream_close
from .utils.client_shortcut_handler import bond_shortcut
from .utils.client_recv_result import recv_result
from .utils.client_show_tips import show_mic_tips, show_file_tips
from .utils.client_hot_update import update_hot_all, observe_hot

from .utils.client_transcribe import transcribe_check, transcribe_send, transcribe_recv
from .utils.client_adjust_srt import adjust_srt

from ..utils.empty_working_set import empty_current_working_set

# 获取项目根目录，确保相对路径正确
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.chdir(BASE_DIR)

# 确保终端能使用 ANSI 控制字符
colorama.init()

# MacOS 的权限设置
if system() == 'Darwin' and not sys.argv[1:]:
    if os.getuid() != 0:
        print('在 MacOS 上需要以管理员启动客户端才能监听键盘活动，请 sudo 启动')
        input('按回车退出'); sys.exit()
    else:
        os.umask(0o000)


async def main_mic():
    Cosmic.loop = asyncio.get_event_loop()
    Cosmic.queue_in = asyncio.Queue()
    Cosmic.queue_out = asyncio.Queue()

    show_mic_tips()

    # 更新热词
    update_hot_all()

    # 实时更新热词
    observer = observe_hot()

    # 打开音频流
    Cosmic.stream = stream_open()

    # Ctrl-C 关闭音频流，触发自动重启
    signal.signal(signal.SIGINT, stream_close)

    # 绑定按键
    bond_shortcut()

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 接收结果
    while True:
        # 检查是否需要退出
        if Cosmic.should_exit:
            console.print('[yellow]检测到退出信号，正在停止主循环...[/yellow]')
            break
        
        try:
            await recv_result()
        except Exception as e:
            if Cosmic.should_exit:
                break
            console.print(f'[red]接收结果时出错: {e}[/red]')
            # 短暂等待后继续
            await asyncio.sleep(0.1)


async def main_file(files: List[Path]):
    show_file_tips()

    for file in files:
        if file.suffix in ['.txt', '.json', 'srt']:
            adjust_srt(file)
        else:
            await transcribe_check(file)
            await asyncio.gather(
                transcribe_send(file),
                transcribe_recv(file)
            )

    if Cosmic.websocket:
        await Cosmic.websocket.close()
    input('\n按回车退出\n')


def init_mic():
    try:
        asyncio.run(main_mic())
    except KeyboardInterrupt:
        console.print(f'再见！')
    finally:
        print('...')


def init_file(files: List[Path]):
    """
    用 CapsWriter Server 转录音视频文件，生成 srt 字幕
    """
    try:
        asyncio.run(main_file(files))
    except KeyboardInterrupt:
        console.print(f'再见！')
        sys.exit()


if __name__ == "__main__":
    # 如果参数传入文件，那就转录文件
    # 如果没有多余参数，就从麦克风输入
    if sys.argv[1:]:
        typer.run(init_file)
    else:
        init_mic()
