# OB11 ZBrush Body Cut

## 当前能力
本工具用于整理 ZBrush 自带缩时录制产生的多段视频。当前可运行切片支持素材排序、ffprobe 元数据读取、全局时间线、FFmpeg 拼接、加速基础视频、中文 GUI、实时日志和共享调试 CLI。

## 边界
本工具只负责雕刻过程的 body cut 基础处理。标题、BGM、字幕、片尾、最终微调和发布包装仍在 DaVinci Resolve 中完成。

Blender Hook 是后续完整版本的一部分：用户先在 Blender 中制作开场 Hook，本项目后续会支持自动拼接 Hook 与 body cut。当前基础切片会保留 `input/hook/` 目录和配置字段，便于后续接入。

## Windows 安装
1. 安装 Python 3.10 或更高版本。
2. 安装 FFmpeg，并确认 `ffmpeg -version` 和 `ffprobe -version` 可以运行。
3. 创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果在较深目录安装 PySide6 时遇到 Windows 长路径限制，先把普通依赖安装进 `.venv`，再把 PySide6 安装到任意较短目录，运行测试或启动 GUI 时通过 `PYTHONPATH` 引入。例如：

```powershell
.\.venv\Scripts\python.exe -m pip install PyYAML pytest
.\.venv\Scripts\python.exe -m pip install --target C:\短路径\pyside6-py312 "PySide6>=6.7,<7"
$env:PYTHONPATH="C:\短路径\pyside6-py312"
```

## GUI 启动
推荐使用 GUI：

```powershell
.\.venv\Scripts\python.exe app.py
```

窗口包含左侧导航、素材管理页、基础处理页、底部进度条和实时日志。素材页可扫描 `input/`、调整顺序并保存 `input/order.txt`；基础处理页可一键生成基础输出。

## 素材放置与排序
将 `.mp4`、`.mov` 或 `.mkv` 文件放入 `input/`。如果需要固定顺序，在 `input/order.txt` 中每行写一个文件名。没有 `order.txt` 时，程序会优先使用自然文件名排序；文件名不可靠时会使用修改时间排序并记录 warning。

## 基础输出
- `output/full_concat.mp4`：按最终顺序拼接的基础视频，会重新编码、归一化为 1080x1920 竖屏、强制目标 FPS，并去除音频。
- `output/accelerated_base.mp4`：在拼接结果上再次加速的分析基础视频。
- `output/input_order.txt`：最终顺序、自然文件名顺序、修改时间顺序、warning 和全局时间线。
- `output/edit_report.json`：机器可读的视频元数据、全局时间线和 warning。
- `output/edit_report.txt`：便于人工阅读的视频信息、时间线和 warning。
- `logs/bodycut-*.log`：FFmpeg 命令、处理步骤、warning 和错误。

原始素材不会被覆盖。

## 调试 CLI
日常建议使用 GUI。高级调试可执行：

```powershell
.\.venv\Scripts\python.exe make_timelapse.py --run-foundation
.\.venv\Scripts\python.exe make_timelapse.py --only-full-concat
.\.venv\Scripts\python.exe make_timelapse.py --only-accelerate
```

三个阶段开关互斥。`--only-accelerate` 假设 `output/full_concat.mp4` 已经存在。

## 验收步骤
1. 将 1 到 5 段真实 ZBrush 缩时视频放入 `input/`。
2. 运行 `.\.venv\Scripts\python.exe app.py`。
3. 在素材管理页扫描并确认顺序。
4. 在基础处理页点击“一键执行基础流程”。
5. 确认进度到达 100，日志包含 FFmpeg 命令，并生成 `full_concat.mp4` 和 `accelerated_base.mp4`。

## 测试
核心、CLI 和 GUI 离屏测试：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest -v
```

如果 PySide6 安装在短路径目标目录，先设置对应 `PYTHONPATH`。
