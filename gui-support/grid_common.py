#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕截图网格标注工具 - 公共模块

为VLM模型提供带网格和坐标标注的截图处理工具的共享功能。
"""

import argparse
import json
import os
import sys
import tempfile
from ctypes import windll
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from PIL import Image, ImageDraw, ImageFont, ImageGrab

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
    original: Image.Image,
    canvas_x: int,
    canvas_y: int,
    margin: int,
    x_margin: Optional[int] = None,
    y_margin: Optional[int] = None,
) -> Optional[int]:
    """获取指定画布位置对应原图的亮度。

    Args:
        original: 原图
        canvas_x: 画布上的x坐标
        canvas_y: 画布上的y坐标
        margin: 边距（当 x_margin/y_margin 未指定时使用）
        x_margin: x方向边距（可选，覆盖 margin）
        y_margin: y方向边距（可选，覆盖 margin）

    Returns:
        亮度值(0-255)或None（不在原图范围内）
    """
    orig_width, orig_height = original.size

    effective_x_margin = x_margin if x_margin is not None else margin
    effective_y_margin = y_margin if y_margin is not None else margin

    orig_x = canvas_x - effective_x_margin
    orig_y = canvas_y - effective_y_margin

    if orig_x < 0 or orig_x >= orig_width or orig_y < 0 or orig_y >= orig_height:
        return None

    if original.mode != "RGB":
        pixel = original.convert("RGB").getpixel((orig_x, orig_y))
    else:
        pixel = original.getpixel((orig_x, orig_y))

    return sum(pixel) // 3


def get_line_contrasting_color(
    original: Image.Image,
    line_pos: int,
    margin: int,
    start: int,
    end: int,
    is_horizontal: bool,
    num_samples: int = 20,
    x_margin: Optional[int] = None,
    y_margin: Optional[int] = None,
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
        x_margin: x方向边距（可选）
        y_margin: y方向边距（可选）

    Returns:
        RGBA颜色元组
    """
    bright_count = 0
    dark_count = 0

    step = max((end - start) // num_samples, 1)

    for pos in range(start, end, step):
        if is_horizontal:
            brightness = get_point_brightness(
                original, pos, line_pos, margin,
                x_margin=x_margin, y_margin=y_margin
            )
        else:
            brightness = get_point_brightness(
                original, line_pos, pos, margin,
                x_margin=x_margin, y_margin=y_margin
            )

        if brightness is not None:
            if brightness > 128:
                bright_count += 1
            else:
                dark_count += 1

    if bright_count > dark_count:
        return (0, 0, 0, 220)
    else:
        return (255, 255, 255, 220)


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


def get_font(size: int = 12) -> ImageFont.ImageFont:
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
    """使用 Pillow.ImageGrab 捕获屏幕截图。

    Returns:
        截图文件的临时路径

    Raises:
        RuntimeError: 截图失败时抛出
    """
    windll.user32.SetProcessDPIAware()
    img = ImageGrab.grab()

    with tempfile.NamedTemporaryFile(
        suffix=".png", delete=False, delete_on_close=False
    ) as tmp:
        temp_path = tmp.name
    img.save(temp_path, "PNG")
    return Path(temp_path)


def capture_screenshot_region(x1: int, y1: int, x2: int, y2: int) -> Path:
    """使用 Pillow.ImageGrab 捕获指定区域的屏幕截图。

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

    windll.user32.SetProcessDPIAware()
    img = ImageGrab.grab(bbox=(x1, y1, x2, y2))

    with tempfile.NamedTemporaryFile(
        suffix=".png", delete=False, delete_on_close=False
    ) as tmp:
        temp_path = tmp.name
    img.save(temp_path, "PNG")
    return Path(temp_path)


def process_image(
    input_path: Path,
    output_path: Path,
    grid_size: Optional[int] = None,
    margin: Optional[int] = None,
    offset: Optional[Tuple[int, int]] = None,
    scale_factor: float = 1.0,
    display_size: Optional[Tuple[int, int]] = None,
) -> dict:
    """处理图片，添加网格和坐标标注。

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        grid_size: 网格间距（像素），None则自动计算
        margin: 边缘扩展宽度（像素），None则自动计算
        offset: 坐标偏移量 (x_offset, y_offset)，用于区域截图的绝对坐标标注
        scale_factor: 缩放因子（1.0表示无缩放），用于区域截图
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

    # 分离边距：左侧给Y轴，顶部给X轴
    left_margin = max(margin, 70)
    top_margin = max(margin, 50)
    right_margin = 20
    bottom_margin = 20

    # 计算新画布尺寸
    new_width = orig_width + left_margin + right_margin
    new_height = orig_height + top_margin + bottom_margin

    # 坐标偏移（用于区域截图的绝对坐标）
    x_offset = offset[0] if offset else 0
    y_offset = offset[1] if offset else 0

    # 创建新画布（白色背景）
    canvas = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 255))

    # 将原图粘贴到画布
    canvas.paste(original, (left_margin, top_margin))

    # 创建绘图对象
    draw = ImageDraw.Draw(canvas)

    # 获取字体
    font_size = max(left_margin // 5, 12)
    font = get_font(font_size)

    # 计算网格线数量
    h_lines = orig_height // grid_size + 1
    v_lines = orig_width // grid_size + 1

    # 绘制水平网格线和Y轴坐标
    for i in range(h_lines + 1):
        y = top_margin + i * grid_size
        if y > top_margin + orig_height:
            break

        # 绘制网格线（根据背景自动选择对比色）
        line_color = get_line_contrasting_color(
            original, y, top_margin,
            left_margin, left_margin + orig_width,
            is_horizontal=True,
            x_margin=left_margin,
            y_margin=top_margin,
        )
        draw.line([(left_margin, y), (left_margin + orig_width, y)], fill=line_color, width=1)

        # 绘制左侧Y轴坐标（使用绝对坐标）
        # 网格线在缩放图像上的位置是 (y - top_margin)
        # 需要除以缩放因子得到原始坐标
        abs_y = y_offset + (y - top_margin) / scale_factor
        coord_text = str(int(abs_y))
        
        bbox = draw.textbbox((0, 0), coord_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = 5
        text_y = y - text_height // 2
        
        # 确保文字在左侧边距区域内
        if text_y >= 0 and text_y + text_height <= new_height:
            draw.text((text_x, text_y), coord_text, fill=(0, 0, 0), font=font)

    # 绘制垂直网格线和X轴坐标
    for i in range(v_lines + 1):
        x = left_margin + i * grid_size
        if x > left_margin + orig_width:
            break

        # 绘制网格线（根据背景自动选择对比色）
        line_color = get_line_contrasting_color(
            original, x, left_margin,
            top_margin, top_margin + orig_height,
            is_horizontal=False,
            x_margin=left_margin,
            y_margin=top_margin,
        )
        draw.line([(x, top_margin), (x, top_margin + orig_height)], fill=line_color, width=1)

        # 绘制顶部X轴坐标（使用绝对坐标）
        abs_x = x_offset + (x - left_margin) / scale_factor
        coord_text = str(int(abs_x))
        
        bbox = draw.textbbox((0, 0), coord_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = x - text_width // 2
        text_y = 5
        
        # 确保文字在顶部边距区域内
        if text_x >= 0 and text_x + text_width <= new_width:
            draw.text((text_x, text_y), coord_text, fill=(0, 0, 0), font=font)

    # 添加右下角尺寸标注（使用display_size或原图尺寸）
    display_width, display_height = (
        display_size if display_size else (orig_width, orig_height)
    )
    size_text = f"{display_width} x {display_height}"
    bbox = draw.textbbox((0, 0), size_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    size_text_x = new_width - text_width - 5
    size_text_y = new_height - text_height - 5

    draw.text(
        (size_text_x, size_text_y),
        size_text,
        fill=(0, 0, 0),
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
        "border_padding": max(left_margin, top_margin),  # 兼容旧键名
        "left_margin": left_margin,
        "top_margin": top_margin,
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
