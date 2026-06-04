from pathlib import Path


def test_foundation_entrypoints_docs_and_runtime_dirs_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "app.py").exists()
    assert (root / "make_timelapse.py").exists()
    for directory in ("input", "input/hook", "output", "logs"):
        assert (root / directory).is_dir()
        gitkeep = root / directory / ".gitkeep"
        assert gitkeep.exists()
        assert gitkeep.read_bytes() == b""

    readme = (root / "README.md").read_text(encoding="utf-8")
    for expected in (
        "full_concat.mp4",
        "accelerated_base.mp4",
        "Blender Hook",
        "DaVinci Resolve",
        "ZBrush",
    ):
        assert expected in readme

    for expected in (
        r".\.venv\Scripts\python.exe app.py",
        r".\.venv\Scripts\python.exe make_timelapse.py --run-foundation",
        "重新编码",
        "1080x1920",
        "去除音频",
        "8 倍加速",
        "后续切片",
        "节点分析",
        "人工审查",
        "45/60/120 秒 body cut",
        "LLM 证据包",
        "Blender Hook 自动拼接",
    ):
        assert expected in readme


def test_runtime_outputs_are_gitignored_but_gitkeep_files_are_tracked() -> None:
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    for expected in (
        "input/*",
        "!input/.gitkeep",
        "!input/hook/",
        "input/hook/*",
        "!input/hook/.gitkeep",
        "output/*",
        "!output/.gitkeep",
        "logs/*",
        "!logs/.gitkeep",
    ):
        assert expected in gitignore
