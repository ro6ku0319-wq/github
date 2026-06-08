---
name: bodycut-editor
description: Generate OB11 ZBrush body cut edit_decision.json from an llm_review_package, contact sheets, candidate CSV, and user style_profile.yaml. Use when asked to choose body cut segments, classify hair regions, balance blockout/refinement, or produce a strict edit_decision.json.
---

# Bodycut Editor

You generate `edit_decision.json` for OB11 ZBrush timelapse body cut videos.

## Inputs

Read the package directory named in the prompt. Use:
- `llm_prompt.md` as the active editing instruction.
- `operation_candidates.csv` for candidate node IDs and time ranges.
- `frame_manifest.json` for frame IDs and timecodes.
- `style_profile.yaml` for the user's learned preferences.
- Attached contact sheets for visual judgment.

## Editing Rules

- Output only strict JSON matching the requested schema.
- Do not include Markdown, explanations, comments, or code fences.
- Do not invent real ZBrush brush or command names.
- The body cut starts directly with sculpting; no Blender hook is included.
- Preserve every present hair region's `blockout` and `refinement` result in the 60 second version.
- Hair regions are `front_hair`, `sideburns`, `back_hair`, `other_hair_blocks`, or `not_hair`.
- Process phases are `blockout`, `refinement`, or `other`.
- Detect left/right symmetric or near-symmetric sculpting operations inside `blockout`
  and `refinement`.
- For a symmetric left/right pair in the same hair region and process phase, keep only
  the clearer representative side in the 60 second version, and omit or heavily
  compress the duplicate side.
- Use the same `symmetry_group` for both sides of one symmetric pair.
- Set `symmetry_side` to `left`, `right`, `center`, `both`, `not_applicable`, or
  `unknown`.
- Set `symmetry_keep_role` to `representative`, `duplicate_omitted`,
  `not_symmetric`, `supporting_context`, or `unknown`.
- Mark the kept side as `symmetry_keep_role: "representative"` and usually
  `include_in_body_60s: true`.
- Mark the omitted duplicate side as `symmetry_keep_role: "duplicate_omitted"` and
  usually `include_in_body_60s: false` or `output_duration_seconds: 0`.
- Favor user `style_profile.yaml` over generic defaults when there is a tradeoff.
- If the style profile contains a phase ratio or preferred durations, allocate `output_duration_seconds` accordingly.
- Keep UI-only, repeated rotation, unclear, static, or result-not-visible segments short or deleted.

## Output Contract

Return a single JSON object with:
- `video_type: "body_cut_only"`
- `recommended_body_duration_seconds: 60`
- `hair_region_presence`
- `first_20_seconds_body_plan`
- `segments`
- `cover_candidates`
- `davinci_markers`
- `notes_for_human_editor`

Each segment must contain the fields required by the schema, including
`hair_region`, `process_phase`, `shows_phase_result`, `symmetry_group`,
`symmetry_side`, `symmetry_keep_role`, and `importance`.
