#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕截图网格标注工具 - 完整截图模块

为VLM模型提供带网格和坐标标注的全屏截图处理工具。
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from grid_common import (
    load_config,
    get_config_path,
    capture_screenshot,
    process_image,
    resolve_output_path,
)


def process_screenshot(
    output_path: str, grid_size: Optional[int] = None, margin: Optional[int] = None
) -> dict:
    """截图并处理（Python API）。

    Args:
        output_path: 输出图片路径
        grid_size: 网格间距（像素），None则自动计算
        margin: 边缘扩展宽度（像素），None则自动计算

    Returns:
        包含处理元数据的字典
    """
    # 捕获截图
    screenshot_path = capture_screenshot()

    try:
        # 处理图片
        metadata = process_image(screenshot_path, Path(output_path), grid_size, margin)

        return metadata

    finally:
        # 清理临时截图文件
        screenshot_path.unlink(missing_ok=True)


def main():
    """命令行入口函数。"""
    # 加载配置
    config = load_config()
    default_output = config["default_output_path"]

    parser = argparse.ArgumentParser(
        description="全屏截图网格标注工具 - 为VLM模型提供带网格和坐标标注的截图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
使用示例:
  %(prog)s                                  # 截图并使用默认输出路径
  %(prog)s -g 100 -m 50                     # 截图并处理（自定义参数）

配置文件:
  配置文件路径: {get_config_path()}
  当前默认输出路径: {default_output}
        """,
    )

    parser.add_argument(
        "-g",
        "--grid-size",
        type=int,
        default=None,
        help="网格间距（像素），默认根据图片尺寸自适应",
    )

    parser.add_argument(
        "-m",
        "--margin",
        type=int,
        default=None,
        help="边缘扩展宽度（像素），默认根据图片尺寸自适应",
    )

    args = parser.parse_args()

    # 确定输出路径（支持自动时间戳命名）
    output_path = resolve_output_path(default_output, is_region=False)

    try:
        print("正在捕获屏幕截图...")
        metadata = process_screenshot(str(output_path), args.grid_size, args.margin)
        print(f"处理完成！")
        print(f"  输出图片: {output_path}")
        print(f"  原图尺寸: {metadata['width']} x {metadata['height']}")
        print(f"  网格间距: {metadata['grid_size']}px")
        print(f"  外边框: {metadata['border_padding']}px")
        print(
            f"  输出尺寸: {metadata['output_size']['width']} x {metadata['output_size']['height']}"
        )

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
