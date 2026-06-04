from pathlib import Path


def test_foundation_entrypoints_docs_and_runtime_dirs_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "app.py").exists()
    assert (root / "make_timelapse.py").exists()
    for directory in ("input", "input/hook", "output", "logs"):
        assert (root / directory).is_dir()
        assert (root / directory / ".gitkeep").exists()

    readme = (root / "README.md").read_text(encoding="utf-8")
    for expected in (
        "python app.py",
        "python make_timelapse.py --run-foundation",
        "full_concat.mp4",
        "accelerated_base.mp4",
        "Blender Hook",
        "DaVinci Resolve",
        "ZBrush",
    ):
        assert expected in readme
