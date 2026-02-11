# GUI Support Tools for VLM

一套专为视觉语言模型（VLM）设计的屏幕截图网格标注和鼠标点击工具，帮助 AI Agent 通过视觉方式精确操作图形界面。

## 功能特性

- **全屏截图标注** - 捕获整个屏幕并添加网格和坐标标注
- **区域截图标注** - 以指定中心点截取屏幕 (1/5)**2 大小的区域，支持自动放大
- **鼠标点击控制** - 在指定坐标执行单击、双击、右键点击
- **自适应网格** - 根据图片尺寸自动计算网格参数
- **对比度网格线** - 自动选择黑/白对比色确保网格线清晰可见
- **绝对坐标标注** - 区域截图也显示屏幕绝对坐标
- **DPI 感知** - 正确处理高 DPI 屏幕的缩放问题

## 安装

### 依赖要求

- Python 3.8+
- Windows 系统（使用 Windows API 进行截图）

### 安装依赖

```bash
pip install -r requirements.txt
```

或使用 uv：

```bash
uv pip install -r requirements.txt
```

## 快速开始

### 1. 配置输出路径

编辑 `grid_tool_config.json`：

```json
{
  "default_output_path": "C:\\Users\\YourName\\Desktop\\screenshots"
}
```

### 2. 标准工作流程

#### 步骤 1：全屏截图（粗定位）

```bash
python grid_full.py
```

将生成带网格标注的全屏截图，供 VLM 识别目标大致位置。

#### 步骤 2：区域截图（精定位）

```bash
python grid_region.py 960,540
```

以坐标 (960, 540) 为中心截取屏幕 1/5 大小的区域，并显示绝对坐标。

#### 步骤 3：执行点击

```bash
python click_tool.py 800 600
```

在坐标 (800, 600) 执行鼠标点击。

#### 步骤 4：验证结果

```bash
python grid_full.py
```

再次全屏截图，验证操作是否成功。

## 工具说明

### grid_full.py - 全屏截图工具

```bash
python grid_full.py [-g GRID_SIZE] [-m MARGIN]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --grid-size` | 网格间距（像素） | 自动计算 |
| `-m, --margin` | 边缘扩展宽度（像素） | 自动计算 |

### grid_region.py - 区域截图工具

```bash
python grid_region.py cx,cy [-g GRID_SIZE] [-m MARGIN]
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `cx,cy` | 中心点坐标（必需） | `960,540` 或 `(960, 540)` |
| `-g, --grid-size` | 网格间距（像素） | 自动计算 |
| `-m, --margin` | 边缘扩展宽度（像素） | 自动计算 |

### click_tool.py - 鼠标点击工具

```bash
python click_tool.py x y [options]
```

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `x` | - | 屏幕 X 坐标 | - |
| `y` | - | 屏幕 Y 坐标 | - |
| `--clicks` | `-c` | 点击次数 | `1` |
| `--interval` | `-i` | 多次点击间隔（秒） | `0.0` |
| `--button` | `-b` | 鼠标按钮（left/right/middle） | `left` |
| `--duration` | `-d` | 鼠标移动时间（秒） | `0.5` |
| `--position` | `-p` | 获取当前鼠标位置 | - |

#### 常用示例

```bash
# 单击坐标 (100, 200)
python click_tool.py 100 200

# 双击
python click_tool.py 500 300 -c 2

# 右键点击
python click_tool.py 800 600 -b right

# 点击 3 次，间隔 0.5 秒
python click_tool.py 100 200 -c 3 -i 0.5

# 移动 1 秒后点击
python click_tool.py 100 200 -d 1.0

# 获取当前鼠标位置
python click_tool.py --position
```

## 项目结构

```
gui-support/
├── grid_tool_config.json  # 配置文件
├── grid_common.py         # 公共模块（截图、图像处理）
├── grid_full.py           # 全屏截图工具
├── grid_region.py         # 区域截图工具
└── click_tool.py          # 鼠标点击工具
README.md              # 项目说明文档
requirements.txt       # Python 依赖
```

## 工作原理

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. 粗定位       │ --> │  2. 精定位       │ --> │  3. 执行操作     │ --> │  4. 验证结果     │
│  grid_full.py   │     │ grid_region.py  │     │  click_tool.py  │     │  grid_full.py   │
│   全屏截图      │     │  区域放大截图    │     │   精确点击      │     │   验证效果      │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **粗定位**：全屏截图带网格标注，VLM 识别目标大致位置
2. **精定位**：区域截图放大细节，VLM 获取精确坐标
3. **执行操作**：在精确坐标执行鼠标点击
4. **验证结果**：操作后再次截图，验证操作是否成功

## 注意事项

⚠️ **风险提示**：本工具执行的操作具有高风险性，可能导致意外的系统行为或数据丢失。

- 在开始任务前，请评估操作可能带来的风险
- 确保 VLM 模型识别的坐标准确无误
- 首次使用建议先在测试环境验证

## 系统要求

- **操作系统**：Windows 10/11
- **Python**：3.8 或更高版本
- **权限**：可能需要管理员权限才能执行某些操作

## 许可证

MIT License
