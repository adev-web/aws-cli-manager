from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_gitignore_covers_all_env_files_with_example_negation():
    content = (ROOT / ".gitignore").read_text()
    assert "config/env.*" in content
    assert "!config/env.*.example" in content
    assert "config/env.base" not in content
    assert "config/env.dev" not in content
    assert "config/env.qa" not in content


def test_gitignore_example_files_stay_visible_to_git():
    base = ROOT / ".gitignore"
    lines = base.read_text().splitlines()
    idx = lines.index("config/env.*")
    assert lines[idx + 1] == "!config/env.*.example"
