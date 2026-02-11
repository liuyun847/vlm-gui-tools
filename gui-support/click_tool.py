#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕坐标点击工具

使用 PyAutoGUI 模拟鼠标点击指定坐标位置。
"""

import argparse
import sys
from pathlib import Path
from typing import Tuple, Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None


def click_at(
    x: int,
    y: int,
    clicks: int = 1,
    interval: float = 0.0,
    button: str = "left",
    duration: float = 0.5,
) -> None:
    """在指定坐标位置模拟鼠标点击。

    Args:
        x: 屏幕 X 坐标
        y: 屏幕 Y 坐标
        clicks: 点击次数，默认为 1 次
        interval: 多次点击之间的间隔（秒），默认为 0
        button: 鼠标按钮，可选 "left"、"right"、"middle"，默认为 "left"
        duration: 鼠标移动时间（秒），默认为 0.5

    Raises:
        RuntimeError: PyAutoGUI 未安装时抛出
        ValueError: 坐标超出屏幕范围时抛出

    Note:
        坐标是相对于屏幕左上角的绝对坐标，(0, 0) 为左上角。
    """
    if pyautogui is None:
        raise RuntimeError("PyAutoGUI 未安装，请运行: uv add pyautogui")

    # 获取屏幕尺寸
    screen_width, screen_height = pyautogui.size()

    # 验证坐标范围
    if not (0 <= x <= screen_width and 0 <= y <= screen_height):
        raise ValueError(
            f"坐标 ({x}, {y}) 超出屏幕范围 ({screen_width}, {screen_height})"
        )

    # 移动鼠标到目标位置
    pyautogui.moveTo(x, y, duration=duration)

    # 执行点击
    pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)


def parse_coordinate(coord_str: str) -> Tuple[int, int]:
    """解析坐标字符串。

    支持的格式：
    - "100,200" -> (100, 200)
    - "100 200" -> (100, 200)
    - "(100, 200)" -> (100, 200)

    Args:
        coord_str: 坐标字符串

    Returns:
        (x, y) 坐标元组

    Raises:
        ValueError: 格式无效时抛出
    """
    # 移除括号和多余空格
    cleaned = coord_str.strip().replace("(", "").replace(")", "").replace(",", " ")
    parts = cleaned.split()

    if len(parts) != 2:
        raise ValueError(f"坐标格式无效: '{coord_str}'，期望格式: 'x,y' 或 'x y'")

    try:
        x = int(parts[0])
        y = int(parts[1])
        return x, y
    except ValueError as e:
        raise ValueError(f"坐标必须是整数: '{coord_str}'") from e


def get_current_mouse_position() -> Tuple[int, int]:
    """获取当前鼠标位置。

    Returns:
        (x, y) 当前鼠标坐标

    Raises:
        RuntimeError: PyAutoGUI 未安装时抛出
    """
    if pyautogui is None:
        raise RuntimeError("PyAutoGUI 未安装，请运行: uv add pyautogui")

    return pyautogui.position()


def main():
    """命令行入口函数。"""
    parser = argparse.ArgumentParser(
        description="屏幕坐标点击工具 - 使用 PyAutoGUI 模拟鼠标点击",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s 100 200                    # 在坐标 (100, 200) 点击
  %(prog)s 500 300 -c 2               # 在坐标 (500, 300) 双击
  %(prog)s 800 600 -b right           # 在坐标 (800, 600) 右键点击
  %(prog)s 100 200 -c 3 -i 0.5        # 点击 3 次，每次间隔 0.5 秒
  %(prog)s 100 200 -d 1.0             # 移动 1 秒后点击
  %(prog)s --position                 # 获取当前鼠标位置
        """,
    )

    parser.add_argument(
        "x",
        type=int,
        nargs="?",
        help="屏幕 X 坐标",
    )

    parser.add_argument(
        "y",
        type=int,
        nargs="?",
        help="屏幕 Y 坐标",
    )

    parser.add_argument(
        "-c",
        "--clicks",
        type=int,
        default=1,
        help="点击次数，默认为 1",
    )

    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0.0,
        help="多次点击之间的间隔（秒），默认为 0",
    )

    parser.add_argument(
        "-b",
        "--button",
        type=str,
        default="left",
        choices=["left", "right", "middle"],
        help="鼠标按钮，可选 left、right、middle，默认为 left",
    )

    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=0.5,
        help="鼠标移动时间（秒），默认为 0.5",
    )

    parser.add_argument(
        "-p",
        "--position",
        action="store_true",
        help="获取当前鼠标位置",
    )

    args = parser.parse_args()

    # 检查 PyAutoGUI 是否安装
    if pyautogui is None:
        print("错误: PyAutoGUI 未安装，请运行: uv add pyautogui", file=sys.stderr)
        sys.exit(1)

    # 获取当前鼠标位置
    if args.position:
        x, y = get_current_mouse_position()
        print(f"当前鼠标位置: ({x}, {y})")
        sys.exit(0)

    # 验证坐标参数
    if args.x is None or args.y is None:
        parser.print_help()
        print(
            "\n错误: 必须提供坐标参数 x 和 y，或使用 --position 获取当前位置",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # 获取屏幕尺寸
        screen_width, screen_height = pyautogui.size()
        print(f"屏幕尺寸: {screen_width} x {screen_height}")
        print(f"点击坐标: ({args.x}, {args.y})")
        print(
            f"点击设置: {args.clicks} 次, 按钮: {args.button}, 间隔: {args.interval}s, 移动时长: {args.duration}s"
        )

        # 执行点击
        click_at(args.x, args.y, args.clicks, args.interval, args.button, args.duration)
        print("点击完成！")

    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
