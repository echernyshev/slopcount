from pathlib import Path

from slopcount.scanner import Gitignore, read_text, scan


def make(root: Path):
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (root / "main.c").write_text("int main(){}\n")
    (root / "README.md").write_text("# hi\n")
    (root / "notes.txt").write_text("hi\n")
    (root / "data.bin").write_bytes(b"\x00\x01\x02")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.js").write_text("var x;\n")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x\n")


def test_scan_classifies_and_skips(tmp_path):
    make(tmp_path)
    files = {f.path: f for f in scan(tmp_path)}
    assert set(files) == {"src/app.py", "main.c", "README.md", "notes.txt", "data.bin"}
    assert files["src/app.py"].kind == "code"
    assert files["src/app.py"].language == "python"
    assert files["main.c"].language == "c"
    assert files["README.md"].kind == "markdown"
    assert files["notes.txt"].kind == "prose"


def test_gitignore_excludes(tmp_path):
    make(tmp_path)
    (tmp_path / ".gitignore").write_text("*.bin\nsrc/\n")
    files = {f.path for f in scan(tmp_path)}
    assert "data.bin" not in files and "src/app.py" not in files
    assert "README.md" in files


def test_read_text_none_for_binary(tmp_path):
    make(tmp_path)
    assert read_text(tmp_path / "data.bin") is None
    assert read_text(tmp_path / "README.md") == "# hi\n"


def test_gitignore_slash_pattern_prefix_semantics(tmp_path):
    make(tmp_path)
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "gen.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("a/b/\n")
    files = {f.path for f in scan(tmp_path)}
    assert "a/b/gen.py" not in files
    assert "README.md" in files
    gi = Gitignore(tmp_path)
    assert gi.matches("a/b/gen.py") and not gi.matches("ab/c.py")


def test_scan_survives_broken_symlink(tmp_path):
    make(tmp_path)
    (tmp_path / "dangling").symlink_to(tmp_path / "nonexistent")
    files = [f.path for f in scan(tmp_path)]  # не должно упасть
    assert "dangling" not in files
