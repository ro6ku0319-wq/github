# OB11 ZBrush Timelapse Body Cut Design

## 1. Purpose

Build a Windows desktop application named `ob11_zbrush_timelapse_bodycut`.
It organizes multi-part ZBrush timelapse recordings, generates candidate
action-completion nodes, supports manual review, exports multiple body-cut
versions, packages visual evidence for manual ChatGPT review, applies the
returned edit decision, and optionally prepends a user-rendered Blender hook.

The application is for Xiaohongshu OB11 head sculpting videos. It handles the
sculpting-process body cut only. It does not generate a finished-product hook,
upload videos, automate DaVinci Resolve, or claim to understand actual ZBrush
commands.

## 2. Confirmed Product Decisions

- Implement the complete requested product through verified vertical slices.
- Favor conservative candidate recall: false positives are acceptable because
  the user and the LLM workflow can remove weak nodes.
- Support a typical project containing 1-5 ZBrush videos with about two hours
  of total source duration.
- Validate against real ZBrush source footage supplied by the user.
- Assume the ZBrush window, model region, and UI layout are broadly stable,
  while the model itself is frequently zoomed, rotated, and panned.
- Treat zoom, rotation, and pan as low-priority transition candidates. Retain
  only a small number of short clips where useful for rhythm.
- Implement Blender hook plus body-cut concatenation in the first complete
  release.
- Use Simplified Chinese for the GUI, README, and primary user-facing errors.
  Keep code identifiers in English.

## 3. Delivery Strategy

Use runnable vertical slices so each phase can be validated against real
footage before later features add complexity.

1. Create project structure, configuration, file ordering, probing,
   concatenation, 8x acceleration, and the basic asynchronous GUI.
2. Add batched frame sampling, disk cache, visual features, conservative
   candidate recall, and frame-level boundary refinement.
3. Add `cut_decision.csv`, 45/60/120-second body cuts, contact sheets, preview
   video, activity curve, and DaVinci markers.
4. Add GUI node review, image preview, system-player video opening, and
   settings editing.
5. Add the manual-LLM evidence package, decision validation, and guided export.
6. Add Blender hook configuration and automatic hook concatenation.
7. Complete error handling, Chinese documentation, and real-footage acceptance
   testing.

## 4. Architecture

### 4.1 Core Service Layer

Place reusable Python services in `src/core/`. This layer owns:

- Input discovery and natural ordering
- `ffprobe` metadata collection
- FFmpeg command construction and execution
- Global timeline mapping
- Batched frame sampling and cached thumbnails
- Visual feature extraction
- Coarse segmentation and fine boundary detection
- Undo/redo and low-value candidate detection
- Cut-decision construction and application
- Contact sheets, reports, manifests, and DaVinci markers
- LLM package creation, schema validation, and decision application
- Blender hook normalization and concatenation
- Configuration and path management

Core services do not import PySide6. They expose callable operations and
progress/log callbacks so the GUI and CLI share the same implementation.

### 4.2 GUI Layer

Place PySide6 interface code in `src/gui/`. The approved layout has:

- A left-side workflow navigation panel
- A right-side current-page workspace
- A persistent bottom status area with progress and real-time logs

Every long-running operation runs through a worker thread or subprocess. The
GUI remains responsive and shows the current step, progress, logs, output path,
elapsed time, and success or failure state.

### 4.3 CLI Layer

Keep `make_timelapse.py` as a debugging and advanced-user entrypoint. It calls
the same core services as the GUI. The recommended entrypoint is:

```bash
python app.py
```

## 5. Data Flow

```text
input videos
-> ordering and ffprobe
-> global timeline map
-> full_concat.mp4
-> accelerated_base.mp4
-> batched coarse sampling
-> visual feature cache and activity curve
-> coarse candidate windows
-> fine frame-level boundary refinement
-> cut_decision.csv
-> manual GUI review
-> body_cut_45s.mp4 / body_cut_60s.mp4 / body_cut_120s.mp4
-> optional LLM evidence package and guided decision
-> optional Blender hook concatenation
-> DaVinci Resolve finishing
```

Input ordering uses this precedence:

1. `input/order.txt`, if present
2. Natural filename order
3. File modification time as fallback

Missing files referenced by `order.txt` are errors. Extra input files not
listed in `order.txt` and disagreement between natural order and modification
time produce warnings.

All later reports retain:

- Global timecode
- Source file
- Source timecode

## 6. Candidate Node Analysis

The automatic analyzer is an explainable candidate recall system, not a ZBrush
semantic engine.

### 6.1 Performance Model

Two-hour projects must not load full videos or all decoded frames into memory.
The analyzer:

- Samples coarse frames in batches
- Writes reusable thumbnail and feature caches to disk
- Runs fine frame-level analysis only near candidate windows
- Allows each completed stage to be rerun independently

### 6.2 Feature Set

Use an interpretable combination of:

- Global frame difference
- Edge-map difference
- Region-based change scores
- Motion consistency and direction
- Low-change duration
- Black-frame detection
- Repeated-change patterns
- UI-heavy change candidates

### 6.3 Candidate Labels

The program can label heuristic candidates such as:

- `front_hair_strand_pull`
- `hair_detail`
- `face_features`
- `accessory_detail`
- `rotate_inspect`
- `zoom_pan_view`
- `ui_tool_switch`
- `undo_redo_candidate`
- `static_low_value`
- `blank_or_black`
- `final_display`

Actual sculpting semantics and aesthetic value remain subject to manual review
and the LLM package workflow.

### 6.4 Action Completion

Use continuous motion followed by a stable readable state as the primary
signal for an `action_completion_node`. Fine boundary detection searches near
the coarse candidate window at frame-level precision. The cut ends when the
visual result is understandable, not when all later adjustment finishes.

## 7. Body Cut Selection

Build all three outputs from the same reviewed candidate set:

- `body_cut_45s.mp4`: tight highlight version
- `body_cut_60s.mp4`: default publishing version
- `body_cut_120s.mp4`: expanded process version

Rules:

- Start body cut at sculpting content at output second zero.
- Do not generate or select a finished-product intro from ZBrush footage.
- Ensure the first 20 seconds of the 60-second body cut contain at least three
  clear change nodes.
- Prioritize front hair, facial features, accessories, and readable sculpting
  progression.
- Deprioritize back hair, hair tail, UI activity, duplicate work, undo/redo,
  and static content.
- Keep only a small number of short zoom, rotation, or pan transitions.
- Allow subsecond and frame-level cuts where necessary.

## 8. GUI Pages

Implement these GUI pages:

1. Project settings
2. Input management and ordering
3. Base processing
4. Node review
5. Preview
6. LLM evidence package
7. Apply LLM edit decision
8. Blender Hook
9. Settings
10. Logs

The node-review table is editable and includes at least:

- `node_id`
- `label`
- `start_global_time`
- `end_global_time`
- `duration_seconds`
- `confidence`
- `keep_in_body_45s`
- `keep_in_body_60s`
- `keep_in_body_120s`
- `speed_multiplier`
- `reason`
- `human_note`

The preview page displays images inside the GUI and opens videos with the
system default player in the initial release.

## 9. Manual LLM Workflow

The initial release must not call the OpenAI API. Generate a local package:

```text
output/llm_review_package/
  overview_contact_sheet*.jpg
  node_contact_sheet*.jpg
  high_detail_contact_sheet*.jpg
  frame_manifest.json
  operation_candidates.csv
  llm_prompt.md
```

The user manually uploads these files to ChatGPT, saves the returned decision
to `output/llm_result/edit_decision.json`, and applies it through the GUI or:

```bash
python make_timelapse.py --apply-llm-decision output/llm_result/edit_decision.json
```

Validate required fields, timecodes, node references, numeric ranges,
`video_type`, and first-20-second plan warnings before rendering. Generate:

```text
output/llm_result/llm_guided_body_cut.mp4
output/llm_result/llm_edit_report.txt
output/llm_result/davinci_markers.csv
```

## 10. Blender Hook

The Blender hook is external user-generated footage. It is never analyzed as
ZBrush input and never generated by this program.

The GUI records:

- Whether a hook is enabled
- Hook path
- Expected hook duration
- Whether automatic concatenation is enabled

When enabled, normalize only the necessary resolution, frame rate, and format,
then prepend the hook and output:

```text
final_with_hook_45s.mp4
final_with_hook_60s.mp4
final_with_hook_120s.mp4
```

DaVinci Resolve remains responsible for titles, BGM, captions, ending, final
rhythm tuning, and export inspection.

## 11. Error Handling and Logging

- Check `ffmpeg`, `ffprobe`, and required Python dependencies at startup.
- Report an empty input directory explicitly.
- Skip and log unreadable individual videos.
- Stop with a clear reason if every input video is unreadable.
- Create missing output and log directories automatically.
- Never overwrite user source footage.
- Log every FFmpeg command, warning, error, output path, and elapsed time.
- Mirror logs to the GUI and `logs/`.
- Preserve earlier successful outputs if a later stage fails.
- Keep intermediate paths configurable or generated relative to the project.
- Support Windows paths without hard-coded machine-specific absolute paths.

## 12. Testing

### 12.1 Unit Tests

Cover:

- Configuration load/save and defaults
- Natural ordering and `order.txt` precedence
- Timeline mapping
- CSV load/save
- LLM JSON validation
- Candidate scoring
- Duration budgeting and segment selection

### 12.2 Integration Tests

Use non-destructive short excerpts from user-provided real ZBrush footage to
test:

- Probing and ordering
- Concatenation
- Acceleration
- Node analysis
- Body-cut rendering
- Hook normalization and concatenation

### 12.3 Acceptance Test

Run one complete approximately two-hour real project through the GUI. Confirm:

- The UI remains responsive.
- Logs and progress are readable.
- Memory use remains bounded.
- All required outputs are created.
- The 60-second cut begins with sculpting and has sufficient first-20-second
  change density.
- Low-value view motion does not crowd out meaningful sculpting changes.
- Manual CSV edits and LLM decisions can be applied successfully.

## 13. Required Outputs

The complete release includes:

- `output/input_order.txt`
- `output/full_concat.mp4`
- `output/accelerated_base.mp4`
- `output/edit_report.json`
- `output/edit_report.txt`
- `output/operation_score_table.csv`
- `output/cut_decision.csv`
- `output/project_manifest.json`
- `output/activity_curve.png`
- `output/node_contact_sheet.jpg`
- `output/auto_node_preview.mp4`
- `output/body_cut_45s.mp4`
- `output/body_cut_60s.mp4`
- `output/body_cut_120s.mp4`
- `output/davinci_markers.csv`
- `output/llm_review_package/`
- `output/llm_result/llm_guided_body_cut.mp4`
- `output/llm_result/llm_edit_report.txt`
- `output/llm_result/davinci_markers.csv`
- `output/final_with_hook_45s.mp4`
- `output/final_with_hook_60s.mp4`
- `output/final_with_hook_120s.mp4`

## 14. Out of Scope

- Automatic Xiaohongshu upload
- DaVinci Resolve API integration
- PyAutoGUI automation of DaVinci Resolve
- Automatic OpenAI API calls
- Automatic Blender hook generation
- Choosing a finished-product hook from ZBrush timelapse footage
- Claiming exact ZBrush command recognition from visual frames

