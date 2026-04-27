# GUI Support Tools for VLM

专为视觉语言模型（VLM）设计的屏幕截图网格标注和鼠标点击工具。

演示: https://www.bilibili.com/video/BV1ubc7znExR/

## 功能

- **全屏/区域截图标注** - 带网格和坐标标注
- **鼠标点击控制** - 单击、双击、右键点击
- **自适应网格** - 自动计算网格参数
- **对比度网格线** - 自动选择黑/白对比色

## 安装

```bash
pip install -r requirements.txt
```

依赖: Python 3.8+, Windows

## 快速开始

```bash
# 1. 全屏截图（粗定位）
python grid_full.py

# 2. 区域截图（精定位）
python grid_region.py 960,540

# 3. 执行点击
python click_tool.py 800 600
```

## 工具说明

| 工具 | 命令 | 主要参数 |
|------|------|----------|
| grid_full.py | `python grid_full.py [-g GRID_SIZE]` | -g: 网格间距 |
| grid_region.py | `python grid_region.py cx,cy` | cx,cy: 中心点坐标 |
| click_tool.py | `python click_tool.py x y` | x y: 目标坐标 |

### click_tool.py 选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-c, --clicks` | 点击次数 | 1 |
| `-i, --interval` | 点击间隔(秒) | 0.0 |
| `-b, --button` | 按钮(left/right/middle) | left |
| `-d, --duration` | 移动时间(秒) | 0.5 |

## 工作流程

```
全屏截图 → 区域截图 → 执行点击 → 验证结果
grid_full.py → grid_region.py → click_tool.py → grid_full.py
```

## 项目结构

```
gui-support/
├── grid_tool_config.json  # 输出路径配置
├── grid_common.py         # 公共模块
├── grid_full.py           # 全屏截图
├── grid_region.py         # 区域截图
└── click_tool.py          # 鼠标点击
```

## 注意

⚠️ 操作具有风险，请确保坐标准确无误，建议先在测试环境验证。
