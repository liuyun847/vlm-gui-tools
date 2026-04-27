# 代码审查问题记录

> 审查日期: 2026-04-28
> 范围: `vlm-gui-tools` 全项目（含 README、SKILL.md、配置文件及 4 个 Python 模块）

---

## 严重问题

### 1. GDI 资源泄漏风险

- **位置**: `gui-support/grid_common.py`
  - `capture_screenshot()` (L221-L287)
  - `capture_screenshot_region()` (L290-L355)
- **原因**: `hwnd`、`hdc_screen`、`hdc_mem`、`bmp` 等 GDI 资源的创建逻辑位于 `try` 块**外部**。如果在 `CreateCompatibleDC`、`CreateCompatibleBitmap` 或 `BitBlt` 阶段抛出异常，`finally` 块无法执行，导致屏幕 DC 和内存 DC 泄漏。
- **改进建议**: 将资源创建全部移入 `try` 块，或在每个创建步骤后添加独立的错误处理与释放逻辑。

### 2. `grid_region.py` 坐标解析与文档/工具不一致

- **位置**:
  - `gui-support/grid_region.py` `main()` (L228-L232)
  - `gui-support/SKILL.md` (L52)
- **原因**: `SKILL.md` 和 `click_tool.py` 均声称支持 `x,y`、`x y`、`(x, y)` 三种格式，但 `grid_region.py` 的 `main()` 仅做了简单的 `args.center.split(",")`，不支持空格和括号。
- **改进建议**: 复用 `click_tool.py` 中的 `parse_coordinate()`（需先提取到公共模块），或在 `grid_region.py` 中统一解析逻辑。

### 3. SKILL.md 声明了未实现的 CLI 参数

- **位置**: `gui-support/SKILL.md` (L161-L167) `--set-default-output`
- **原因**: 文档声称全屏和区域截图工具都支持 `--set-default-output` 参数，但 `grid_full.py` 和 `grid_region.py` 的 `argparse` 定义中均**未注册**此参数。
- **改进建议**: 删除文档中的错误描述，或补全参数实现。

### 4. 点击坐标边界检查包含等号

- **位置**: `gui-support/click_tool.py` (L52)
- **原因**: `0 <= x <= screen_width` 允许 `x == screen_width`，但屏幕有效坐标的最大值应为 `screen_width - 1`。
- **改进建议**: 改为 `0 <= x < screen_width and 0 <= y < screen_height`。

---

## 警告问题

### 5. 定义了未使用的变量

- **位置**: `gui-support/grid_common.py` (L416) `grid_color`
- **原因**: `grid_color = (128, 128, 128, 100)` 被赋值后从未使用，实际网格线颜色由 `get_line_contrasting_color()` 动态决定。
- **改进建议**: 删除该行，或保留为后备色并明确使用场景。

### 6. `get_font()` 返回类型与实际不符

- **位置**: `gui-support/grid_common.py` (L194-L218)
- **原因**: 函数签名返回 `ImageFont.FreeTypeFont`，但当所有字体路径均不可用时，返回的是 `ImageFont.ImageFont`（默认位图字体）。这在静态类型检查或 IDE 提示中会产生误导。
- **改进建议**: 将返回类型改为 `ImageFont.ImageFont`（基类），或统一使用 `typing.Union`。

### 7. 屏幕尺寸获取逻辑重复

- **位置**:
  - `gui-support/grid_common.py` (L230-L242) `capture_screenshot()`
  - `gui-support/grid_region.py` (L29-L49) `get_screen_size()`
- **原因**: DPI 感知设置和 `GetDeviceCaps`/`GetSystemMetrics` 的屏幕尺寸获取逻辑在两个文件中重复实现。
- **改进建议**: 将 `get_screen_size()` 提取到 `grid_common.py` 并复用。

### 8. `parse_coordinate()` 未在本项目内被复用

- **位置**: `gui-support/click_tool.py` (L64-L93)
- **原因**: 该函数解析能力完善，但仅存在于 `click_tool.py` 中，且 `click_tool.py` 自身的 `main()` 并未使用它（而是直接要求两个独立整数参数）。`grid_region.py` 也未复用。
- **改进建议**: 提取到 `grid_common.py` 作为公共函数，供 `grid_region.py` 使用。

### 9. 异常捕获过于宽泛

- **位置**:
  - `gui-support/grid_full.py` (L103-L105)
  - `gui-support/grid_region.py` (L251-L253)
- **原因**: `except Exception as e:` 会吞掉所有非预期错误（如 `KeyboardInterrupt`、名称错误等），不利于调试。
- **改进建议**: 细分为 `ValueError`、`RuntimeError`、`OSError` 等具体异常，或至少使用 `except (ValueError, RuntimeError) as e:`。

### 10. 坐标文字颜色固定为黑色

- **位置**: `gui-support/grid_common.py` (L446-L472)
- **原因**: 网格线已根据背景亮度自动选择黑/白对比色，但坐标文字固定使用黑色。在深色背景区域边缘，黑色文字可读性差。
- **改进建议**: 坐标文字也使用与网格线一致的对比色逻辑，或统一使用带半透明背景的文本框。

---

## 待实现功能

### 11. 实现 `--set-default-output` CLI 参数

- **位置**: `gui-support/grid_full.py`、`gui-support/grid_region.py`
- **背景**: `SKILL.md` 中已描述了该参数的使用方式，但代码中缺失实现。
- **建议实现方案**:
  1. 在 `grid_full.py` 和 `grid_region.py` 的 `argparse` 中新增 `--set-default-output` 参数。
  2. 参数接受一个路径字符串，写入 `grid_tool_config.json` 的 `default_output_path` 字段。
  3. 写入后打印确认信息并直接退出，不执行截图操作。
  4. 注意路径校验（确保目录存在或可创建）。
- **示例行为**:
  ```bash
  python grid_full.py --set-default-output "C:\Users\Me\Pictures\VLM"
  # 输出: 默认输出路径已更新为: C:\Users\Me\Pictures\VLM
  ```

---

## 待评估改进

### 12. 评估是否换用 `Pillow.ImageGrab.grab()` 替代原生 GDI

- **位置**: `gui-support/grid_common.py` (`capture_screenshot()`、`capture_screenshot_region()`)
- **背景**: 项目已经依赖 `Pillow`，而 `ImageGrab.grab()` 同样支持多显示器和 DPI 感知（通过 `ctypes.windll.user32.SetProcessDPIAware()`）。当前使用原生 GDI 增加了内存管理和资源释放的复杂度。
- **评估维度**:
  - **兼容性**: `ImageGrab` 是否在所有目标 Windows 版本（10/11）上表现一致？是否支持高 DPI 缩放？
  - **性能**: `ImageGrab.grab()` 与原生 GDI 的截图速度差异如何？对 4K 屏幕是否有性能瓶颈？
  - **功能**: `ImageGrab` 是否支持精确的区域截图（带坐标偏移）？
  - **可靠性**: 是否解决了当前 GDI 的资源泄漏风险？
- **建议**: 先编写一个 `screenshot_pillow.py` 原型对比两者输出结果和耗时，确认无差异后再替换，降低引入回归问题的风险。

---

## 统计

| 级别 | 数量 | 状态 |
|------|------|------|
| 严重 | 4 | 待修复 |
| 警告 | 6 | 待修复 |
| 待实现功能 | 1 | 待实现 |
| 待评估改进 | 1 | 待评估 |
