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
from ctypes import windll
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image

from grid_common import (
    load_config,
    save_config,
    get_config_path,
    capture_screenshot_region,
    process_image,
    resolve_output_path,
)


def get_screen_size() -> Tuple[int, int]:
    """获取屏幕尺寸。

    Returns:
        (width, height) 屏幕宽度和高度
    """
    # 设置DPI感知
    windll.user32.SetProcessDPIAware()

    # 获取屏幕尺寸（物理分辨率）
    hdc = windll.user32.GetDC(0)
    width = windll.gdi32.GetDeviceCaps(hdc, 118)  # DESKTOPHORZRES
    height = windll.gdi32.GetDeviceCaps(hdc, 117)  # DESKTOPVERTRES
    windll.user32.ReleaseDC(0, hdc)

    if width <= 0 or height <= 0:
        # 备用方案：使用GetSystemMetrics
        width = windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        height = windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN

    return width, height


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
            # coord_step 是原始坐标系的网格步长，用于坐标标注
            processed_width = int(orig_width * scale_factor)
            processed_height = int(orig_height * scale_factor)
            processed_short_edge = min(processed_width, processed_height)

            if grid_size is None:
                # 目标：短边显示约8-10条网格线
                grid_size = max(processed_short_edge // 8, 40)

            # 计算网格线数量（基于处理后的尺寸）
            h_lines = processed_height // grid_size + 1
            v_lines = processed_width // grid_size + 1

            # 坐标标注步长：确保最后一个坐标正好落在区域边界
            # 使用原始尺寸除以网格线间隔数，确保坐标范围与原始区域匹配
            coord_step_y = (
                max(round(orig_height / (h_lines - 1)), 10)
                if h_lines > 1
                else orig_height
            )
            coord_step_x = (
                max(round(orig_width / (v_lines - 1)), 10)
                if v_lines > 1
                else orig_width
            )

            # 使用较小的步长作为统一的坐标步长（保持正方形网格的视觉一致性）
            coord_step = min(coord_step_x, coord_step_y)

            # 处理图片，传入偏移量以显示绝对坐标，以及coord_step用于正确的坐标标注
            # 传入原始尺寸作为右下角标注的尺寸
            metadata = process_image(
                process_path,
                Path(output_path),
                grid_size,
                margin,
                offset=(x1, y1),
                coord_step=coord_step,
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

    args = parser.parse_args()

    # 解析中心点坐标
    try:
        coords = [int(x.strip()) for x in args.center.split(",")]
        if len(coords) != 2:
            raise ValueError("中心点坐标需要2个数值: cx,cy")
        center = tuple(coords)
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

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
