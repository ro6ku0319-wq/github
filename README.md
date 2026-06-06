# OB11 ZBrush Body Cut

## 当前能力
本工具用于整理 ZBrush 自带缩时录制产生的多段视频。当前可运行切片支持素材排序、ffprobe 元数据读取、全局时间线、FFmpeg 拼接、默认 8 倍加速基础视频、候选动作节点分析、人工修改 `cut_decision.csv`、45/60/120 秒 body cut 导出、中文 GUI、实时日志和共享调试 CLI。

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

窗口包含左侧导航、素材管理页、基础处理页、节点审查页、底部进度条和实时日志。素材页可扫描 `input/`、调整顺序并保存 `input/order.txt`；基础处理页可一键生成基础输出、分析候选节点，并在人工确认后导出 body cut；节点审查页可读取和保存 `cut_decision.csv`。

## 素材放置与排序
将 `.mp4`、`.mov` 或 `.mkv` 文件放入 `input/`。如果需要固定顺序，在 `input/order.txt` 中每行写一个文件名。没有 `order.txt` 时，程序会优先使用自然文件名排序；文件名不可靠时会使用修改时间排序并记录 warning。

## 基础输出
- `output/full_concat.mp4`：按最终顺序拼接的基础视频，会重新编码、归一化为 1080x1920 竖屏、强制目标 FPS，并去除音频。
- `output/accelerated_base.mp4`：在拼接结果上再次执行默认 8 倍加速的分析基础视频。
- `output/input_order.txt`：最终顺序、自然文件名顺序、修改时间顺序、warning 和全局时间线。
- `output/edit_report.json`：机器可读的视频元数据、全局时间线和 warning。
- `output/edit_report.txt`：便于人工阅读的视频信息、时间线和 warning。
- `logs/bodycut-*.log`：FFmpeg 命令、处理步骤、warning 和错误。

原始素材不会被覆盖。

## 节点分析输出
基础处理完成并生成 `output/accelerated_base.mp4` 后，可在 GUI 的基础处理页点击“分析候选节点”。当前节点分析是可解释的候选召回系统，不会假装完全理解 ZBrush 语义；它主要根据画面差异、边缘变化、黑屏/低变化状态生成可人工审查的候选。

- `output/frame_manifest.json`：抽帧时间点、帧序号和缓存图片路径。
- `output/operation_score_table.csv`：每个样本帧的亮度、边缘密度、画面差异和活动分数。
- `output/node_analysis.json`：候选节点、代表帧、置信度和生成原因。
- `output/cut_decision.csv`：后续人工审查、45/60/120 秒 body cut 和 LLM 工作流共用的编辑决策表。
- `output/node_contact_sheet.jpg`：候选节点代表帧联系图。
- `output/activity_curve.png`：整段视频的活动强度曲线。

## Body Cut 导出
在节点审查页确认或修改 `cut_decision.csv` 后，回到基础处理页点击“导出 body cut”。程序会从同一个 `cut_decision.csv` 读取 `keep_in_body_45s`、`keep_in_body_60s`、`keep_in_body_120s` 三列，调用 FFmpeg 生成：

- `output/body_cut_45s.mp4`：紧凑高亮版。
- `output/body_cut_60s.mp4`：默认发布版。
- `output/body_cut_120s.mp4`：展开过程版。
- `output/auto_node_preview.mp4`：按候选节点拼接的自动预览。
- `output/davinci_markers.csv`：可供 DaVinci Resolve 手工对照的节点 marker 表。

如果某个版本没有勾选任何节点，程序会跳过该版本并在日志中说明。标题、BGM、字幕、片尾和最终发布包装仍在 DaVinci Resolve 中完成。

## 调试 CLI
日常建议使用 GUI。高级调试可执行：

```powershell
.\.venv\Scripts\python.exe make_timelapse.py --run-foundation
.\.venv\Scripts\python.exe make_timelapse.py --only-full-concat
.\.venv\Scripts\python.exe make_timelapse.py --only-accelerate
.\.venv\Scripts\python.exe make_timelapse.py --analyze-nodes
.\.venv\Scripts\python.exe make_timelapse.py --export-cuts
```

五个阶段开关互斥。`--only-accelerate` 假设 `output/full_concat.mp4` 已经存在；`--analyze-nodes` 假设 `output/accelerated_base.mp4` 已经存在；`--export-cuts` 假设 `output/cut_decision.csv` 已经存在。

## 后续切片
后续版本会继续加入更完整的预览页、LLM 证据包和 Blender Hook 自动拼接。当前版本先完成稳定的输入排序、基础拼接、8 倍加速、报告、候选节点分析、人工审查保存、三版 body cut 导出和 GUI 操作底座。

## 验收步骤
1. 将 1 到 5 段真实 ZBrush 缩时视频放入 `input/`。
2. 运行 `.\.venv\Scripts\python.exe app.py`。
3. 在素材管理页扫描并确认顺序。
4. 在基础处理页点击“一键执行基础流程”。
5. 确认进度到达 100，日志包含 FFmpeg 命令，并生成 `full_concat.mp4` 和 `accelerated_base.mp4`。
6. 在基础处理页点击“分析候选节点”，确认生成 `cut_decision.csv`、`node_contact_sheet.jpg` 和 `activity_curve.png`。
7. 在节点审查页修改并保存 `cut_decision.csv`。
8. 在基础处理页点击“导出 body cut”，确认生成 `body_cut_45s.mp4`、`body_cut_60s.mp4`、`body_cut_120s.mp4`、`auto_node_preview.mp4` 和 `davinci_markers.csv`。

## 测试
核心、CLI 和 GUI 离屏测试：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest -v
```

如果 PySide6 安装在短路径目标目录，先设置对应 `PYTHONPATH`。
