# OB11 ZBrush Body Cut

## 当前能力
本工具用于整理 ZBrush 自带缩时录制产生的多段视频。当前版本支持素材排序、ffprobe 元数据读取、全局时间线、FFmpeg 拼接、默认 5 倍加速、候选动作节点分析、人工修改 `cut_decision.csv`、45/60/120 秒 body cut 导出、手动 LLM 工作流、Blender Hook 自动拼接、预览、项目清单、中文 GUI、实时日志和共享调试 CLI。

## 边界
本工具只负责雕刻过程的 body cut 基础处理。标题、BGM、字幕、片尾、最终微调和发布包装仍在 DaVinci Resolve 中完成。

Blender Hook 由用户在 Blender 中单独制作。本工具不会生成 Hook，但可以将 Hook 规范化到当前输出分辨率和 FPS，并自动拼接到现有 body cut 前面。

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
.\.venv\Scripts\python.exe app.py --project-dir C:\你的项目目录
```

窗口包含 10 个页面：项目设置、素材管理、基础处理、节点审查、预览、LLM 证据包、应用 LLM 决策、Blender Hook、通用设置和日志。项目设置页可切换项目并选择素材/输出目录；节点审查页支持按标签/保留状态筛选，并可按置信度或时间排序；预览页可显示联系图和活动曲线，并调用系统播放器打开生成的视频；通用设置页可修改宽高、裁剪模式、加速、FPS、采样、边界、目标时长和操作优先级。

## 输出分辨率
在 GUI 的基础处理页中，可选择以下输出分辨率：

- 竖屏 1080p：`1080x1920`，默认值。
- 横屏 1080p：`1920x1080`。
- 横屏 2K：`2560x1440`。
- 竖屏 2K：`1440x2560`。

选择后会保存到项目 `config.yaml` 的 `output_video` 配置。需要重新执行“一键执行基础流程”，新的分辨率才会应用到 `full_concat.mp4` 和 `accelerated_base.mp4`；之后导出的节点预览与 45/60/120 秒 body cut 会继承该分辨率。重新执行会覆盖同名输出文件。

## 素材放置与排序
将 `.mp4`、`.mov` 或 `.mkv` 文件放入 `input/`。如果需要固定顺序，在 `input/order.txt` 中每行写一个文件名。没有 `order.txt` 时，程序会优先使用自然文件名排序；文件名不可靠时会使用修改时间排序并记录 warning。

## 基础输出
- `output/full_concat.mp4`：按最终顺序拼接的基础视频，会重新编码、归一化为 GUI 选择的目标分辨率、强制目标 FPS，并去除音频。
- `output/accelerated_base.mp4`：在拼接结果上再次执行默认 5 倍加速的分析基础视频。
- `output/input_order.txt`：最终顺序、自然文件名顺序、修改时间顺序、warning 和全局时间线。
- `output/edit_report.json`：机器可读的视频元数据、全局时间线和 warning。
- `output/edit_report.txt`：便于人工阅读的视频信息、时间线和 warning。
- `output/project_manifest.json`：项目名称、输入、时间线、输出路径、已选/删除节点和 warning 的持续更新清单。
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

`operation_score_table.csv` 还包含全局、中心、UI 区域和局部变化密度、亮度、细节、稳定度、新颖度、重复度及视觉回退标记。开启 `fine_cut.enabled` 后，程序会围绕粗候选节点按 `fine_sample_every_n_frames` 逐帧搜索边界，并应用搜索窗口和完成保持帧数。`cut_decision.csv` 包含动作开始、峰值、完成和建议切点帧，以及保守的 A→B→A 撤销/重做候选字段。此标记只用于人工审查，不会直接自动删除片段。

## Body Cut 导出
在节点审查页确认或修改 `cut_decision.csv` 后，回到基础处理页点击“导出 body cut”。程序会从同一个 `cut_decision.csv` 读取 `keep_in_body_45s`、`keep_in_body_60s`、`keep_in_body_120s` 三列，调用 FFmpeg 生成：

- `output/body_cut_45s.mp4`：紧凑高亮版。
- `output/body_cut_60s.mp4`：默认发布版。
- `output/body_cut_120s.mp4`：展开过程版。
- `output/auto_node_preview.mp4`：按候选节点拼接的自动预览。
- `output/davinci_markers.csv`：可供 DaVinci Resolve 手工对照的节点 marker 表。

如果某个版本没有勾选任何节点，程序会跳过该版本并在日志中说明。标题、BGM、字幕、片尾和最终发布包装仍在 DaVinci Resolve 中完成。

## 手动 LLM 工作流
第一版不会自动调用 OpenAI API。完成节点分析后，在 GUI 的“LLM 工作流”页先设置“生成 JSON 前约束大型/细化比例”。例如大型 `1`、细化 `2` 会在 60 秒主体里提示 ChatGPT 让大型约 20 秒、细化约 40 秒。然后点击“生成 LLM 视觉证据包”，程序会生成：

```text
output/llm_review_package/
  overview_contact_sheet.jpg
  node_contact_sheet_01.jpg
  high_detail_contact_sheet.jpg
  frame_manifest.json
  operation_candidates.csv
  style_profile.yaml
  llm_prompt.md
  frames/
```

你可以继续把联系图、帧清单、候选 CSV 和 `llm_prompt.md` 手动上传给 ChatGPT；也可以直接点击“Codex 一键生成剪辑说明书”。Codex 会通过仓库内的 `.agents/skills/bodycut-editor/SKILL.md` 读取证据包、联系图、候选节点和 `style_profile.yaml`，生成：

```text
output/llm_result/codex_generated_edit_decision.json
output/llm_result/edit_decision.json
```

如果 `edit_decision.json` 已经存在，程序会先生成带时间戳的 `.bak.json` 备份，避免覆盖人工修改。新版提示词会要求模型区分前发、鬓发、后发和可选的其他发块，并为每个存在区域识别“大型”和“细化”阶段。60 秒方案会优先保证每个存在区域的两类结果都出现，再按你在证据包生成前设置的大型/细化比例、历史偏好和 `importance` 取舍片段。左右对称或接近左右对称的同类雕刻操作会被分到同一 `symmetry_group`，默认只保留更清晰的一侧作为 `representative`，重复侧标记为 `duplicate_omitted` 并压缩或删除。

```text
output/llm_result/edit_decision.json
```

然后在 GUI 的“应用 LLM 决策”页加载并人工审查 JSON。你可以在表格中修改 `edit_action`、`include_in_body_60s`、`output_duration_seconds`、`hair_region`、`process_phase`、`symmetry_group`、`symmetry_side`、`symmetry_keep_role`、`importance` 和 `reason`，保存后点击“应用生成视频”。程序会校验必填字段、时间码、节点引用、速度范围、`video_type`、前 20 秒计划、60 秒总时长、头发区域/阶段覆盖及对称字段取值。新版决策文件若缺少任一存在发块的大型或细化结果，程序会拒绝应用，避免导出不完整视频；旧版决策文件没有头发覆盖字段时仍可兼容应用并给出警告。校验通过后输出：

```text
output/llm_result/llm_guided_body_cut.mp4
output/llm_result/llm_edit_report.txt
output/llm_result/davinci_markers.csv
```

LLM 只负责雕刻过程 body cut，不处理或生成 Blender Hook。

点击“确认最终方案并学习”后，程序会比较 Codex 原始方案和你最终保存的方案，将差异写入全局偏好档案 `%APPDATA%\OB11BodyCut\editing_profile\`。换电脑时可导出/导入该档案。

## Blender Hook
1. 将 Blender 制作的 Hook 放入 `input/hook/`，或在 GUI 的“Blender Hook”页选择任意视频文件。
2. 启用 Hook 和自动拼接，设置预期时长并保存。
3. 先生成至少一个 body cut，再点击“自动拼接 Hook 与 body cut”。

程序会按预期 Hook 时长截取并生成 `output/normalized_hook.mp4`，再重新编码拼接，按已有版本输出 `final_with_hook_45s.mp4`、`final_with_hook_60s.mp4`、`final_with_hook_120s.mp4`。

## 调试 CLI
日常建议使用 GUI。高级调试可执行：

```powershell
.\.venv\Scripts\python.exe make_timelapse.py --run-foundation
.\.venv\Scripts\python.exe make_timelapse.py --only-full-concat
.\.venv\Scripts\python.exe make_timelapse.py --only-accelerate
.\.venv\Scripts\python.exe make_timelapse.py --analyze-nodes
.\.venv\Scripts\python.exe make_timelapse.py --export-cuts
.\.venv\Scripts\python.exe make_timelapse.py --build-llm-package
.\.venv\Scripts\python.exe make_timelapse.py --codex-generate-decision
.\.venv\Scripts\python.exe make_timelapse.py --apply-llm-decision output/llm_result/edit_decision.json
.\.venv\Scripts\python.exe make_timelapse.py --confirm-llm-decision
.\.venv\Scripts\python.exe make_timelapse.py --export-editing-profile output/editing_profile.zip
.\.venv\Scripts\python.exe make_timelapse.py --import-editing-profile output/editing_profile.zip
.\.venv\Scripts\python.exe make_timelapse.py --use-cut-decision output/manual_cut_decision.csv
.\.venv\Scripts\python.exe make_timelapse.py --generate-body-45
.\.venv\Scripts\python.exe make_timelapse.py --generate-body-60
.\.venv\Scripts\python.exe make_timelapse.py --generate-body-120
.\.venv\Scripts\python.exe make_timelapse.py --export-with-hook
```

阶段开关互斥。`--only-accelerate` 假设 `output/full_concat.mp4` 已经存在；节点分析、body cut 导出和 LLM 工作流需要先生成各自的上游输出。

## 当前版本范围
当前版本已完成输入排序、基础拼接、5 倍加速、报告、候选节点分析、人工审查保存、三版 body cut、手动 LLM/Codex 工作流、Codex 选片学习偏好、预览、设置、项目清单和 Blender Hook 自动拼接。标题、BGM、字幕、片尾和最终发布包装仍由 DaVinci Resolve 完成。

## 验收步骤
1. 将 1 到 5 段真实 ZBrush 缩时视频放入 `input/`。
2. 运行 `.\.venv\Scripts\python.exe app.py`。
3. 在素材管理页扫描并确认顺序。
4. 在基础处理页点击“一键执行基础流程”。
5. 确认进度到达 100，日志包含 FFmpeg 命令，并生成 `full_concat.mp4` 和 `accelerated_base.mp4`。
6. 在基础处理页点击“分析候选节点”，确认生成 `cut_decision.csv`、`node_contact_sheet.jpg` 和 `activity_curve.png`。
7. 在节点审查页修改并保存 `cut_decision.csv`。
8. 在基础处理页点击“导出 body cut”，确认生成 `body_cut_45s.mp4`、`body_cut_60s.mp4`、`body_cut_120s.mp4`、`auto_node_preview.mp4` 和 `davinci_markers.csv`。
9. 在 LLM 工作流页生成证据包，手动取得 `edit_decision.json` 后应用，确认生成 `llm_guided_body_cut.mp4`、`llm_edit_report.txt` 和 LLM markers。
10. 在预览页检查联系图、活动曲线和视频；需要 Hook 时在 Blender Hook 页完成自动拼接。

## 测试
核心、CLI 和 GUI 离屏测试：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest -v
```

如果 PySide6 安装在短路径目标目录，先设置对应 `PYTHONPATH`。
