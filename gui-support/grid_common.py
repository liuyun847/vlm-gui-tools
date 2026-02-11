#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕截图网格标注工具 - 公共模块

为VLM模型提供带网格和坐标标注的截图处理工具的共享功能。
"""

import argparse
import ctypes
import json
import os
import sys
import tempfile
from ctypes import windll
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from PIL import Image, ImageDraw, ImageFont

# 配置文件路径（固定为技能目录）
CONFIG_FILENAME = "grid_tool_config.json"


def get_config_path() -> Path:
    """获取配置文件路径。

    配置文件存储在技能目录（grid_common.py 所在目录）下，
    不随当前工作目录变化。

    Returns:
        配置文件的完整路径
    """
    # 获取当前文件（grid_common.py）所在的目录
    skill_dir = Path(__file__).parent.resolve()
    return skill_dir / CONFIG_FILENAME


def load_config() -> Dict[str, Any]:
    """加载配置文件。

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在时抛出
        ValueError: 配置文件格式无效时抛出
    """
    config_path = get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {config_path}\n"
            f"请创建配置文件并设置 default_output_path，例如:\n"
            f'{{"default_output_path": "C:\\\\Users\\\\YourName\\\\Desktop\\\\screenshots"}}'
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式无效: {config_path}\n错误: {e}")
    except IOError as e:
        raise ValueError(f"无法读取配置文件: {config_path}\n错误: {e}")

    # 验证必需的配置项
    if "default_output_path" not in config:
        raise ValueError(
            f"配置文件缺少必需的配置项 'default_output_path': {config_path}\n"
            f"请添加配置项，例如:\n"
            f'{{"default_output_path": "C:\\\\Users\\\\YourName\\\\Desktop\\\\screenshots"}}'
        )

    return config


def save_config(config: Dict[str, Any]) -> None:
    """保存配置到文件。

    Args:
        config: 要保存的配置字典
    """
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"警告: 无法保存配置文件: {e}", file=sys.stderr)


def calculate_dynamic_params(width: int, height: int) -> Tuple[int, int]:
    """根据图片尺寸计算动态参数。

    Args:
        width: 图片宽度
        height: 图片高度

    Returns:
        (grid_size, margin) 元组
    """
    short_edge = min(width, height)
    grid_size = max(short_edge // 10, 50)
    margin = max(short_edge // 20, 40)
    return grid_size, margin


def get_point_brightness(
    original: Image.Image, canvas_x: int, canvas_y: int, margin: int
) -> Optional[int]:
    """获取指定画布位置对应原图的亮度。

    Args:
        original: 原图
        canvas_x: 画布上的x坐标
        canvas_y: 画布上的y坐标
        margin: 边距

    Returns:
        亮度值(0-255)或None（不在原图范围内）
    """
    orig_width, orig_height = original.size

    # 将画布坐标转换为原图坐标
    orig_x = canvas_x - margin
    orig_y = canvas_y - margin

    # 检查是否在原图范围内
    if orig_x < 0 or orig_x >= orig_width or orig_y < 0 or orig_y >= orig_height:
        return None

    # 获取像素颜色
    if original.mode != "RGB":
        pixel = original.convert("RGB").getpixel((orig_x, orig_y))
    else:
        pixel = original.getpixel((orig_x, orig_y))

    # 计算亮度
    return sum(pixel) // 3


def get_line_contrasting_color(
    original: Image.Image,
    line_pos: int,
    margin: int,
    start: int,
    end: int,
    is_horizontal: bool,
    num_samples: int = 20,
) -> Tuple[int, int, int, int]:
    """根据整条线的颜色分布计算对比色。

    沿着线分段采样多个点，根据大多数采样点的亮度决定线的颜色。

    Args:
        original: 原图
        line_pos: 线的位置（水平线为y坐标，垂直线为x坐标）
        margin: 边距
        start: 线起点（水平线为x起点，垂直线为y起点）
        end: 线终点（水平线为x终点，垂直线为y终点）
        is_horizontal: 是否为水平线
        num_samples: 采样点数量

    Returns:
        RGBA颜色元组
    """
    bright_count = 0  # 亮度 > 128 的点数
    dark_count = 0  # 亮度 <= 128 的点数

    # 沿着线均匀采样
    step = max((end - start) // num_samples, 1)

    for pos in range(start, end, step):
        if is_horizontal:
            brightness = get_point_brightness(original, pos, line_pos, margin)
        else:
            brightness = get_point_brightness(original, line_pos, pos, margin)

        if brightness is not None:
            if brightness > 128:
                bright_count += 1
            else:
                dark_count += 1

    # 根据大多数采样点的颜色选择对比色
    # 如果大多数点是亮色（亮度>128），用黑色线
    # 如果大多数点是暗色（亮度<=128），用白色线
    if bright_count > dark_count:
        return (0, 0, 0, 220)  # 黑色
    else:
        return (255, 255, 255, 220)  # 白色


def get_font(size: int = 12) -> ImageFont.FreeTypeFont:
    """获取字体对象。

    Args:
        size: 字体大小

    Returns:
        字体对象
    """
    # 尝试常见的中文字体
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        "C:/Windows/Fonts/arial.ttf",  # Arial
    ]

    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue

    # 使用默认字体
    return ImageFont.load_default()


def capture_screenshot() -> Path:
    """使用Windows API捕获屏幕截图。

    Returns:
        截图文件的临时路径

    Raises:
        RuntimeError: 截图失败时抛出
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

    # 创建设备上下文
    hwnd = windll.user32.GetDesktopWindow()
    hdc_screen = windll.user32.GetWindowDC(hwnd)
    hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)

    # 创建位图
    bmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    windll.gdi32.SelectObject(hdc_mem, bmp)

    # 复制屏幕内容
    windll.gdi32.BitBlt(
        hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, 0x00CC0020  # SRCCOPY
    )

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(
        suffix=".png", delete=False, delete_on_close=False
    ) as tmp:
        temp_path = tmp.name

    try:
        # 使用PIL保存图片

        # 获取位图信息
        bmp_info = ctypes.create_string_buffer(40)
        windll.gdi32.GetObjectW(bmp, 40, bmp_info)

        # 提取位图数据
        bmp_data = ctypes.create_string_buffer(width * height * 4)
        windll.gdi32.GetBitmapBits(bmp, width * height * 4, bmp_data)

        # 创建PIL图像（BGR格式需要转换为RGB）
        img = Image.frombuffer(
            "RGB", (width, height), bmp_data.raw, "raw", "BGRX", 0, 1
        )
        img.save(temp_path, "PNG")

    finally:
        # 清理资源
        windll.gdi32.DeleteObject(bmp)
        windll.gdi32.DeleteDC(hdc_mem)
        windll.user32.ReleaseDC(hwnd, hdc_screen)

    return Path(temp_path)


def capture_screenshot_region(x1: int, y1: int, x2: int, y2: int) -> Path:
    """使用Windows API捕获指定区域的屏幕截图。

    Args:
        x1: 区域左上角X坐标
        y1: 区域左上角Y坐标
        x2: 区域右下角X坐标
        y2: 区域右下角Y坐标

    Returns:
        截图文件的临时路径

    Raises:
        RuntimeError: 截图失败时抛出
        ValueError: 坐标无效时抛出
    """
    if x1 >= x2 or y1 >= y2:
        raise ValueError(
            f"无效区域坐标: ({x1}, {y1}, {x2}, {y2}), 需要满足 x1<x2 且 y1<y2"
        )

    # 设置DPI感知
    windll.user32.SetProcessDPIAware()

    # 计算区域尺寸
    width = x2 - x1
    height = y2 - y1

    # 创建设备上下文
    hwnd = windll.user32.GetDesktopWindow()
    hdc_screen = windll.user32.GetWindowDC(hwnd)
    hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)

    # 创建位图
    bmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    windll.gdi32.SelectObject(hdc_mem, bmp)

    # 复制屏幕指定区域内容
    windll.gdi32.BitBlt(
        hdc_mem, 0, 0, width, height, hdc_screen, x1, y1, 0x00CC0020  # SRCCOPY
    )

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(
        suffix=".png", delete=False, delete_on_close=False
    ) as tmp:
        temp_path = tmp.name

    try:
        # 提取位图数据
        bmp_data = ctypes.create_string_buffer(width * height * 4)
        windll.gdi32.GetBitmapBits(bmp, width * height * 4, bmp_data)

        # 创建PIL图像（BGR格式需要转换为RGB）
        img = Image.frombuffer(
            "RGB", (width, height), bmp_data.raw, "raw", "BGRX", 0, 1
        )
        img.save(temp_path, "PNG")

    finally:
        # 清理资源
        windll.gdi32.DeleteObject(bmp)
        windll.gdi32.DeleteDC(hdc_mem)
        windll.user32.ReleaseDC(hwnd, hdc_screen)

    return Path(temp_path)


def process_image(
    input_path: Path,
    output_path: Path,
    grid_size: Optional[int] = None,
    margin: Optional[int] = None,
    offset: Optional[Tuple[int, int]] = None,
    coord_step: Optional[int] = None,
    display_size: Optional[Tuple[int, int]] = None,
) -> dict:
    """处理图片，添加网格和坐标标注。

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        grid_size: 网格间距（像素），None则自动计算
        margin: 边缘扩展宽度（像素），None则自动计算
        offset: 坐标偏移量 (x_offset, y_offset)，用于区域截图的绝对坐标标注
        coord_step: 坐标标注的步长（像素），None则使用grid_size
        display_size: 右下角显示的尺寸标注 (width, height)，None则使用原图尺寸

    Returns:
        包含处理元数据的字典
    """
    # 打开原图
    original = Image.open(input_path)
    orig_width, orig_height = original.size

    # 计算动态参数
    if grid_size is None or margin is None:
        calc_grid, calc_margin = calculate_dynamic_params(orig_width, orig_height)
        grid_size = grid_size or calc_grid
        margin = margin or calc_margin

    # 坐标标注步长，默认为网格间距
    coord_step = coord_step or grid_size

    # 计算新画布尺寸
    new_width = orig_width + 2 * margin
    new_height = orig_height + 2 * margin

    # 坐标偏移（用于区域截图的绝对坐标）
    x_offset = offset[0] if offset else 0
    y_offset = offset[1] if offset else 0

    # 创建新画布（白色背景）
    canvas = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 255))

    # 将原图粘贴到画布中心
    canvas.paste(original, (margin, margin))

    # 创建绘图对象
    draw = ImageDraw.Draw(canvas)

    # 获取字体
    font_size = max(margin // 3, 10)
    font = get_font(font_size)

    # 绘制网格线和坐标标注
    grid_color = (128, 128, 128, 100)  # 默认灰色半透明

    # 计算网格线数量
    h_lines = orig_height // grid_size + 1
    v_lines = orig_width // grid_size + 1

    # 绘制水平网格线和Y轴坐标
    for i in range(h_lines + 1):
        y = margin + i * grid_size
        if y > margin + orig_height:
            break

        # 绘制网格线 - 在网格线自身位置分段采样，取最频繁的颜色
        line_color = get_line_contrasting_color(
            original, y, margin, margin, margin + orig_width, is_horizontal=True
        )
        draw.line([(margin, y), (margin + orig_width, y)], fill=line_color, width=1)

        # 绘制左侧Y轴坐标（使用绝对坐标）
        abs_y = y_offset + i * coord_step
        coord_text = str(abs_y)
        bbox = draw.textbbox((0, 0), coord_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = margin - text_width - 5
        text_y = y - text_height // 2

        # 确保文字在边距范围内
        if text_x >= 0 and text_y >= 0:
            draw.text((text_x, text_y), coord_text, fill=(0, 0, 0, 255), font=font)

    # 绘制垂直网格线和X轴坐标
    for i in range(v_lines + 1):
        x = margin + i * grid_size
        if x > margin + orig_width:
            break

        # 绘制网格线 - 在网格线自身位置分段采样，取最频繁的颜色
        line_color = get_line_contrasting_color(
            original, x, margin, margin, margin + orig_height, is_horizontal=False
        )
        draw.line([(x, margin), (x, margin + orig_height)], fill=line_color, width=1)

        # 绘制顶部X轴坐标（使用绝对坐标）
        abs_x = x_offset + i * coord_step
        coord_text = str(abs_x)
        bbox = draw.textbbox((0, 0), coord_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = x - text_width // 2
        text_y = margin - text_height - 5

        # 确保文字在边距范围内
        if text_x >= 0 and text_y >= 0:
            draw.text((text_x, text_y), coord_text, fill=(0, 0, 0, 255), font=font)

    # 添加右下角尺寸标注（使用display_size或原图尺寸）
    display_width, display_height = (
        display_size if display_size else (orig_width, orig_height)
    )
    size_text = f"{display_width} x {display_height}"
    bbox = draw.textbbox((0, 0), size_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    draw.text(
        (new_width - text_width - 5, new_height - text_height - 5),
        size_text,
        fill=(0, 0, 0, 255),
        font=font,
    )

    # 转换为RGB保存（去除透明通道）
    final_image = canvas.convert("RGB")
    final_image.save(output_path, "PNG")

    # 生成元数据
    metadata = {
        "original_image": str(input_path),
        "width": orig_width,
        "height": orig_height,
        "grid_size": grid_size,
        "border_padding": margin,
        "coord_step": coord_step,
        "output_size": {"width": new_width, "height": new_height},
        "grid_lines": {"horizontal": h_lines, "vertical": v_lines},
        "generated_at": datetime.now().isoformat(),
    }

    return metadata


def generate_timestamp_filename(output_dir: Path, prefix: str = "screenshot") -> Path:
    """生成带时间戳的文件路径。

    Args:
        output_dir: 输出目录
        prefix: 文件名前缀

    Returns:
        带时间戳的完整文件路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    return output_dir / filename


def resolve_output_path(config_path: str, is_region: bool = False) -> Path:
    """解析输出路径。

    使用配置文件中的路径，确保路径存在：
    1. 如果路径是文件夹或以路径分隔符结尾，创建目录并生成带时间戳的文件名
    2. 如果路径是文件，创建父目录

    Args:
        config_path: 配置文件中的路径
        is_region: 是否为区域截图

    Returns:
        解析后的输出路径
    """
    config_path_obj = Path(config_path)

    # 如果路径以路径分隔符结尾，视为目录
    if config_path.endswith(("\\", "/")):
        output_dir = Path(config_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = "region" if is_region else "screenshot"
        return generate_timestamp_filename(output_dir, prefix)

    # 检查是否为文件路径
    try:
        # 尝试获取文件扩展名
        if config_path_obj.suffix:
            # 是文件路径，创建父目录
            output_path = Path(config_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path
        else:
            # 是目录路径，创建目录并生成时间戳文件名
            output_dir = Path(config_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            prefix = "region" if is_region else "screenshot"
            return generate_timestamp_filename(output_dir, prefix)
    except Exception:
        # 处理异常情况，视为文件路径
        output_path = Path(config_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path
