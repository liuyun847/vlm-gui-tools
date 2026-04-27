#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕截图网格标注工具 - 区域截图模块

为VLM模型提供带网格和坐标标注的区域截图处理工具。
以指定中心点为中心，截取屏幕1/5大小的矩形区域。
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image

from grid_common import (
    load_config,
    save_config,
    get_config_path,
    get_screen_size,
    parse_coordinate,
    capture_screenshot_region,
    process_image,
    resolve_output_path,
)


def process_screenshot_region(
    output_path: str,
    center: Tuple[int, int],
    grid_size: Optional[int] = None,
    margin: Optional[int] = None,
) -> dict:
    """区域截图并处理（Python API）。

    以指定中心点为中心，截取屏幕1/5大小的矩形区域。
    对于小区域截图，会先放大到合适的尺寸再添加网格，避免网格过于密集。

    Args:
        output_path: 输出图片路径
        center: 中心点坐标 (cx, cy)
        grid_size: 网格间距（像素），None则自动计算
        margin: 边缘扩展宽度（像素），None则自动计算

    Returns:
        包含处理元数据的字典
    """
    cx, cy = center

    # 获取屏幕尺寸并计算区域大小（屏幕的1/5）
    screen_width, screen_height = get_screen_size()
    region_width = screen_width // 5
    region_height = screen_height // 5

    # 根据中心点计算区域坐标
    x1 = cx - region_width // 2
    y1 = cy - region_height // 2
    x2 = x1 + region_width
    y2 = y1 + region_height

    # 边界检查：确保区域不超出屏幕
    x1 = max(0, min(x1, screen_width - region_width))
    y1 = max(0, min(y1, screen_height - region_height))
    x2 = x1 + region_width
    y2 = y1 + region_height

    # 捕获区域截图
    screenshot_path = capture_screenshot_region(x1, y1, x2, y2)

    try:
        # 打开截图并检查是否需要放大
        img = Image.open(screenshot_path)
        orig_width, orig_height = img.size

        # 定义目标短边长度（放大后的最小尺寸）
        TARGET_SHORT_EDGE = 400
        short_edge = min(orig_width, orig_height)

        # 如果区域太小，先放大图片
        scale_factor = 1.0
        if short_edge < TARGET_SHORT_EDGE:
            scale_factor = TARGET_SHORT_EDGE / short_edge
            new_width = int(orig_width * scale_factor)
            new_height = int(orig_height * scale_factor)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 保存放大后的图片到临时文件
            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, delete_on_close=False
            ) as tmp:
                enlarged_path = tmp.name
            img.save(enlarged_path, "PNG")
            process_path = Path(enlarged_path)
        else:
            process_path = screenshot_path
            enlarged_path = None

        try:
            # 计算网格大小：根据放大后的尺寸计算，确保网格数量合理（约8-12条线）
            processed_width = int(orig_width * scale_factor)
            processed_height = int(orig_height * scale_factor)
            processed_short_edge = min(processed_width, processed_height)

            if grid_size is None:
                # 目标：短边显示约8-10条网格线
                grid_size = max(processed_short_edge // 8, 40)

            # 处理图片，传入偏移量和缩放因子以显示正确的绝对坐标
            # 传入原始尺寸作为右下角标注的尺寸
            metadata = process_image(
                process_path,
                Path(output_path),
                grid_size,
                margin,
                offset=(x1, y1),
                scale_factor=scale_factor,
                display_size=(orig_width, orig_height),
            )

            # 添加区域信息和缩放信息到元数据
            metadata["region"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            metadata["scale_factor"] = scale_factor
            metadata["original_size"] = {"width": orig_width, "height": orig_height}

            return metadata

        finally:
            # 清理放大后的临时文件
            if enlarged_path:
                Path(enlarged_path).unlink(missing_ok=True)

    finally:
        # 清理临时截图文件
        screenshot_path.unlink(missing_ok=True)


def main():
    """命令行入口函数。"""
    # 加载配置
    config = load_config()
    default_output = config["default_output_path"]

    parser = argparse.ArgumentParser(
        description="区域截图网格标注工具 - 为VLM模型提供带网格和坐标标注的区域截图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
使用示例:
  %(prog)s 960,540                           # 截取以(960,540)为中心的区域（屏幕1/5大小）
  %(prog)s 960,540 -g 100 -m 50              # 自定义网格参数

配置文件:
  配置文件路径: {get_config_path()}
  当前默认输出路径: {default_output}
        """,
    )

    parser.add_argument(
        "center",
        type=str,
        metavar="CX,CY",
        help="中心点坐标，格式: cx,cy（如: 960,540）",
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

    parser.add_argument(
        "--set-default-output",
        type=str,
        metavar="PATH",
        default=None,
        help="设置默认输出路径并退出",
    )

    args = parser.parse_args()

    # 处理设置默认输出路径
    if args.set_default_output is not None:
        output_dir = Path(args.set_default_output).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        config["default_output_path"] = str(output_dir)
        save_config(config)
        print(f"默认输出路径已更新为: {output_dir}")
        sys.exit(0)

    # 解析中心点坐标
    try:
        center = parse_coordinate(args.center)
    except ValueError as e:
        print(f"错误: 无效的中心点坐标格式 '{args.center}': {e}", file=sys.stderr)
        sys.exit(1)

    # 确定输出路径（支持自动时间戳命名）
    output_path = resolve_output_path(default_output, is_region=True)

    try:
        print(f"正在捕获区域截图，中心点: ({center[0]}, {center[1]})...")
        metadata = process_screenshot_region(
            str(output_path), center, args.grid_size, args.margin
        )
        print(f"处理完成！")
        print(f"  输出图片: {output_path}")
        print(
            f"  区域: ({metadata['region']['x1']}, {metadata['region']['y1']}, {metadata['region']['x2']}, {metadata['region']['y2']})"
        )

    except (ValueError, RuntimeError, OSError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
