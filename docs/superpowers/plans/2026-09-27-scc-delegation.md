# Делегирование подсчёта и сканирования в scc — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить самописные обход дерева и подсчёт метрик на один вызов `scc` 4.1.0 (манифест + COCOMO/LOCOMO), оставив в проекте только детекцию SLOP и формулу SLOCOMO.

**Architecture:** `scc.py` — единственная точка работы с бинарником (резолв, ленивая загрузка, вызов, парсинг json2). Классификация языков — данными в `rules/languages.toml` (366 имён) с точечным пользовательским оверрайдом. `app.run()` собирает `ScannedFile[]` из манифеста, детекторы не меняются, отчёт получает новую JSON-модель и «лестницу затрат».

**Tech Stack:** Python 3.11+ (stdlib: subprocess/tarfile/zipfile/hashlib/urllib), scc 4.1.0 (Go-бинарник с GitHub Releases), typer, pytest.

**Спека:** `docs/superpowers/specs/2026-09-27-scc-delegation-design.md` (далее «спека»). Все данные таблицы языков — из её Приложения A.

**Ветка:** работать в текущей ветке `slopcount-design` (worktree не создавался — от пользователя явной просьбы не было).

**Команды проверки (после каждого таска):**
```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

---

### Task 1: Константы и парсер версии scc

**Files:**
- Create: `src/slopcount/scc.py`
- Test: `tests/test_scc.py`

- [x] **Step 1: Написать падающий тест**

```python
# tests/test_scc.py
from slopcount.scc import SCC_MIN_VERSION, SCC_VERSION, PLATFORM_ASSETS, parse_version


def test_version_parsing():
    assert parse_version("scc version 4.1.0") == (4, 1, 0)
    assert parse_version("scc version 3.7.0") == (3, 7, 0)
    assert parse_version("мусор") is None


def test_pinned_version_satisfies_min():
    assert SCC_VERSION == "4.1.0"
    assert parse_version(f"scc version {SCC_VERSION}") >= SCC_MIN_VERSION


def test_platform_assets_cover_five_platforms():
    assert set(PLATFORM_ASSETS) == {
        ("linux", "amd64"),
        ("linux", "arm64"),
        ("darwin", "amd64"),
        ("darwin", "arm64"),
        ("windows", "amd64"),
    }
    for asset, sha in PLATFORM_ASSETS.values():
        assert asset.endswith((".tar.gz", ".zip")) and len(sha) == 64
```

- [x] **Step 2: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'slopcount.scc'`

- [x] **Step 3: Реализовать минимально**

```python
# src/slopcount/scc.py
"""Единственная точка работы с бинарником scc: резолв, ленивая установка,
вызов и разбор json2. Классификация языков здесь НЕ живёт (см. rules.py)."""
from __future__ import annotations

import sys

SCC_VERSION = "4.1.0"
SCC_MIN_VERSION = (4, 1, 0)
_RELEASE_URL = "https://github.com/boyter/scc/releases/download/v" + SCC_VERSION

# asset → sha256, снято с официального checksums.txt релиза v4.1.0
PLATFORM_ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "amd64"): (
        "scc_Linux_x86_64.tar.gz",
        "c7328436d3027f4357d3d7853f7dc3ac2bbcb4ca08f1adad91a27c593884079b",
    ),
    ("linux", "arm64"): (
        "scc_Linux_arm64.tar.gz",
        "6e0d2a1f8d3540ba7df185477dec40bb7340f1b214bfd303147de5cad2bd7b8b",
    ),
    ("darwin", "amd64"): (
        "scc_Darwin_x86_64.tar.gz",
        "7f705031228add7e55edded409179a60de6b538d41f153ba2922dee95adda50d",
    ),
    ("darwin", "arm64"): (
        "scc_Darwin_arm64.tar.gz",
        "7201c7aa4aace058d43308462cba72adb18f6094c08c0741727455976d0a0747",
    ),
    ("windows", "amd64"): (
        "scc_Windows_x86_64.zip",
        "4a433984f45ff29c94eeb3af6db5b511c58f5bf74063dccedafcbf473cb8ff31",
    ),
}

# Каталоги, которые scc обязан пропустить помимо своего дефолта (.git/.hg/.svn);
# унаследовано от удалённого scanner.py (спека §4.3)
SKIP_DIRS = [
    "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
    "target", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode", ".eggs", ".serena",
]


def parse_version(out: str) -> tuple[int, int, int] | None:
    """'scc version 4.1.0' → (4, 1, 0); мусор → None."""
    tail = out.strip().rsplit("version", 1)[-1].strip()
    parts = tail.split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    return None


def _machine() -> tuple[str, str]:
    import platform

    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(
        machine
    )
    if arch is None:
        raise RuntimeError(f"unsupported architecture: {machine}")
    return sys.platform, arch if arch else ""
```

- [x] **Step 4: Прогнать тест**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: PASS (4 теста)

- [x] **Step 5: Коммит**

```bash
git add src/slopcount/scc.py tests/test_scc.py
git commit -m "feat: scc.py — пин 4.1.0, платформенные asset'ы, парсер версии"
```

---

### Task 2: Резолв бинарника и ленивая загрузка

**Files:**
- Modify: `src/slopcount/scc.py`
- Test: `tests/test_scc.py`

- [x] **Step 1: Дописать падающие тесты (в конец `tests/test_scc.py`)**

```python
import hashlib
import stat
from pathlib import Path

import pytest

from slopcount import scc as scc_mod


def _fake_scc(path: Path, version: str = "4.1.0") -> Path:
    path.write_text(f"#!/bin/sh\necho 'scc version {version}'\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_explicit_path_wins(tmp_path, monkeypatch):
    fake = _fake_scc(tmp_path / "myscc")
    monkeypatch.setenv("SLOPCOUNT_SCC_BIN", "/nonexistent/scc")
    assert scc_mod.ensure_binary(str(fake)) == str(fake)


def test_env_var_used(tmp_path, monkeypatch):
    fake = _fake_scc(tmp_path / "from-env")
    monkeypatch.setenv("SLOPCOUNT_SCC_BIN", str(fake))
    assert scc_mod.ensure_binary(None) == str(fake)


def test_stale_path_version_warns_and_falls_through(tmp_path, monkeypatch, capsys):
    _fake_scc(tmp_path / "scc", version="3.0.0")
    monkeypatch.setenv("PATH", str(tmp_path))
    cached = _fake_scc(tmp_path / "cache" / scc_mod.SCC_VERSION / "scc")
    got = scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")
    assert got == str(cached)
    assert "3.0.0" in capsys.readouterr().err  # предупреждение о версии


def test_cache_hit_skips_download(tmp_path, monkeypatch):
    cached = _fake_scc(tmp_path / "cache" / scc_mod.SCC_VERSION / "scc")
    monkeypatch.setenv("SLOPCOUNT_SCC_BIN", "")  # пустая env игнорируется
    monkeypatch.delenv("SLOPCOUNT_SCC_BIN")
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)
    assert scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache") == str(cached)


def test_download_verifies_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)
    payload = b"FAKE-SCC-BINARY"
    fake = _FakeResponse(payload)
    real_sha = hashlib.sha256(fake.read()).hexdigest()
    fake = _FakeResponse(payload)  # второй экземпляр: первый вычитан для sha
    plat = scc_mod._machine()
    asset = scc_mod.PLATFORM_ASSETS[plat][0]
    monkeypatch.setitem(scc_mod.PLATFORM_ASSETS, plat, (asset, real_sha))
    monkeypatch.setattr(scc_mod.urllib.request, "urlopen", lambda url, timeout=60: fake)
    got = scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")
    assert Path(got).read_bytes() == payload
    assert Path(got).stat().st_mode & stat.S_IEXEC  # распакован и исполняем


def test_download_checksum_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)
    tampered = _FakeResponse(b"TAMPERED")
    monkeypatch.setattr(scc_mod.urllib.request, "urlopen", lambda url, timeout=60: tampered)
    with pytest.raises(RuntimeError, match="checksum"):
        scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")


def test_no_binary_no_network_raises_with_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)

    def boom(url, timeout=60):
        raise OSError("no network")

    monkeypatch.setattr(scc_mod.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="go install"):
        scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")


class _FakeResponse:
    """tar.gz с единственным членом 'scc' (mode 755)."""

    def __init__(self, body: bytes):
        import gzip
        import io
        import tarfile

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo("scc")
            info.size = len(body)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(body))
        self._stream = io.BytesIO(gzip.compress(buf.getvalue()))

    def read(self) -> bytes:
        return self._stream.read()

    def close(self) -> None:
        pass


def test_local_platform_asset_known():
    plat = scc_mod._machine()
    assert plat in scc_mod.PLATFORM_ASSETS
```

- [x] **Step 2: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: FAIL `AttributeError: module 'slopcount.scc' has no attribute 'ensure_binary'`

- [x] **Step 3: Реализовать `ensure_binary` (добавить в `scc.py`)**

```python
import os
import shutil
import tarfile
import urllib.request
import zipfile

from slopcount.i18n import _

_HINT = (
    "brew install scc / snap install scc / choco install scc / "
    "go install github.com/boyter/scc/v4@v4.1.0 / "
    "https://github.com/boyter/scc/releases — or pass --scc-path"
)


def _run_version(binary: str) -> tuple[int, int, int] | None:
    import subprocess

    try:
        proc = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(proc.stdout)


def _cache_dir_default() -> Path:
    from pathlib import Path

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "slopcount" / "scc"
    return Path.home() / ".cache" / "slopcount" / "scc"


def _download(cache_root: Path) -> Path:
    plat = _machine()
    asset, sha = PLATFORM_ASSETS[plat]
    print(_("slopcount: downloading scc %s (%d MB)…") % (SCC_VERSION, 7), file=sys.stderr)
    try:
        with urllib.request.urlopen(f"{_RELEASE_URL}/{asset}", timeout=120) as resp:
            blob = resp.read()
    except OSError as exc:
        raise RuntimeError(
            _("slopcount: scc is required but could not be downloaded (%s). Install manually: %s")
            % (exc, _HINT)
        ) from exc
    import hashlib

    if hashlib.sha256(blob).hexdigest() != sha:
        raise RuntimeError(
            _("slopcount: scc checksum mismatch for %s; install manually: %s") % (asset, _HINT)
        )
    dest_dir = cache_root / SCC_VERSION
    dest_dir.mkdir(parents=True, exist_ok=True)
    exe_name = "scc.exe" if sys.platform == "win32" else "scc"
    dest = dest_dir / exe_name
    if asset.endswith(".tar.gz"):
        import io

        with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
            member = next(m for m in tf.getmembers() if m.name.split("/")[-1] == exe_name)
            dest.write_bytes(tf.extractfile(member).read())  # type: ignore[union-attr]
    else:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            member = next(n for n in zf.namelist() if n.split("/")[-1] == exe_name)
            dest.write_bytes(zf.read(member))
    dest.chmod(dest.stat().st_mode | 0o111)
    return dest


def ensure_binary(explicit: str | None = None, cache_dir: Path | None = None) -> str:
    """Порядок: --scc-path > SLOPCOUNT_SCC_BIN > PATH (версия ≥ мин.) > кеш > скачивание."""
    from pathlib import Path

    candidates = [explicit, os.environ.get("SLOPCOUNT_SCC_BIN")]
    for c in candidates:
        if c:
            if not Path(c).is_file():
                raise RuntimeError(
                    _("slopcount: scc binary not found at %s") % c
                )
            return c
    on_path = shutil.which("scc")
    if on_path:
        version = _run_version(on_path)
        if version is not None and version >= SCC_MIN_VERSION:
            return on_path
        print(
            _("slopcount: found scc %s in PATH but %s+ required; using managed copy")
            % (".".join(map(str, version or ())),
               ".".join(map(str, SCC_MIN_VERSION))),
            file=sys.stderr,
        )
    cache_root = cache_dir or _cache_dir_default()
    exe_name = "scc.exe" if sys.platform == "win32" else "scc"
    cached = cache_root / SCC_VERSION / exe_name
    if cached.is_file():
        return str(cached)
    return str(_download(cache_root))
```

Импорты `os/shutil/tarfile/urllib.request/zipfile/hashlib/io` сведите в шапку модуля (верхний блок уже содержит `sys`; переносите по мере использования, ruff `I` отсортирует).

- [x] **Step 4: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: PASS (все, включая новые)

- [x] **Step 5: Коммит**

```bash
git add src/slopcount/scc.py tests/test_scc.py
git commit -m "feat: ленивая установка scc — резолв PATH/кеш/скачивание с sha256"
```

---

### Task 3: Вызов scc и разбор json2 → SccReport

**Files:**
- Modify: `src/slopcount/scc.py`
- Create: `tests/fixtures/scc_slop_project.json2` (запечённый реальный вывод)
- Test: `tests/test_scc.py`

- [x] **Step 1: Запечь фикстуру реальным scc 4.1.0**

Бинарник уже доступен через собственный бутстрап:

```bash
SCC=$(.venv/bin/python -c "from slopcount.scc import ensure_binary; print(ensure_binary())")
"$SCC" --format json2 --by-file --cognitive --locomo \
    --avg-wage 56286 --overhead 2.4 \
    tests/fixtures/slop_project > tests/fixtures/scc_slop_project.json2
```

Sanity (не коммитить, только сверить глазами): в файле 4 per-file записи
(defensive.py, greeter.py, CLAUDE.md, README.md), в корне — `estimatedCost`,
`estimatedLLMCost` и др.

- [x] **Step 2: Написать падающие тесты парсера (в конец `tests/test_scc.py`)**

```python
import json

import pytest


@pytest.fixture()
def fixture_json2():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "scc_slop_project.json2").read_text()
    )


def test_parse_json2_totals(fixture_json2, tmp_path):
    from slopcount.scc import parse_json2

    rep = parse_json2(fixture_json2, root=tmp_path)
    assert rep.scc_version  # непусто
    assert len(rep.files) == 4
    by_name = {Path(f.path).name: f for f in rep.files}
    assert by_name["defensive.py"].code == 6
    assert by_name["defensive.py"].comment == 8
    assert by_name["defensive.py"].cognitive == 7
    assert by_name["greeter.py"].code == 2
    assert by_name["CLAUDE.md"].lines == 1
    assert by_name["README.md"].lines == 11
    assert by_name["defensive.py"].path == "defensive.py"  # путь относительный


def test_parse_json2_costs(fixture_json2, tmp_path):
    from slopcount.scc import parse_json2

    rep = parse_json2(fixture_json2, root=tmp_path)
    assert rep.cocomo.cost == pytest.approx(351.53, abs=0.5)
    assert rep.cocomo.schedule_months == pytest.approx(0.6697, abs=1e-3)
    assert rep.locomo.preset == "medium"
    assert rep.locomo.input_tokens == pytest.approx(2396.36, abs=1.0)
    assert rep.locomo.output_tokens == pytest.approx(378.56, abs=1.0)
    assert rep.locomo.generation_seconds == pytest.approx(7.57, abs=0.01)
    assert rep.locomo.review_hours == pytest.approx(0.00267, abs=1e-4)
    assert rep.locomo.cycles == pytest.approx(2.366, abs=1e-3)


def test_parse_json2_rejects_garbage():
    from slopcount.scc import parse_json2

    with pytest.raises(RuntimeError, match="fields"):
        parse_json2({"languageSummary": []}, root=Path("."))


def test_collect_runs_real_scc(tmp_path):
    """Интеграционный: настоящий бинарник. Пропуск, если scc недоступен."""
    scc = pytest.importorskip("slopcount.scc", reason="needs package")
    (tmp_path / "x.py").write_text("x = 1  # trailing\n" * 3)
    try:
        rep = scc.collect(
            tmp_path, personcost=4690.50, overhead=2.4, cache_dir=tmp_path / ".cache"
        )
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
    py = [f for f in rep.files if f.path.endswith("x.py")]
    assert py and py[0].code == 3  # трейлинг-комментарии = код (багфикс)
```

- [x] **Step 3: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: FAIL `cannot import name 'parse_json2'`

- [x] **Step 4: Реализовать модель и парсер (добавить в `scc.py`)**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SccFile:
    path: str  # posix, относительно root
    language_name: str  # display name scc, напр. "C Header"
    size: int
    lines: int
    code: int
    comment: int
    blank: int
    complexity: int
    cognitive: int
    binary: bool


@dataclass(frozen=True)
class Cocomo:
    cost: float
    schedule_months: float
    people: float


@dataclass(frozen=True)
class Locomo:
    cost: float
    input_tokens: float
    output_tokens: float
    generation_seconds: float
    review_hours: float
    cycles: float
    preset: str


@dataclass(frozen=True)
class SccReport:
    files: list[SccFile]
    scc_version: str
    cocomo: Cocomo
    locomo: Locomo


def parse_json2(data: dict, *, root: Path) -> SccReport:
    """Разбирает вывод `scc --format json2 --by-file`. Битая структура → RuntimeError."""
    try:
        files: list[SccFile] = []
        for lang_summary in data["languageSummary"]:
            for f in lang_summary["Files"]:
                loc = Path(f["Location"])
                files.append(
                    SccFile(
                        path=loc.relative_to(root).as_posix() if loc.is_absolute() else loc.as_posix(),
                        language_name=f["Language"],
                        size=f["Bytes"],
                        lines=f["Lines"],
                        code=f["Code"],
                        comment=f["Comment"],
                        blank=f["Blank"],
                        complexity=f["Complexity"],
                        cognitive=f["Cognitive"],
                        binary=bool(f["Binary"]),
                    )
                )
        cocomo = Cocomo(
            cost=float(data["estimatedCost"]),
            schedule_months=float(data["estimatedScheduleMonths"]),
            people=float(data["estimatedPeople"]),
        )
        locomo = Locomo(
            cost=float(data["estimatedLLMCost"]),
            input_tokens=float(data["estimatedLLMInputTokens"]),
            output_tokens=float(data["estimatedLLMOutputTokens"]),
            generation_seconds=float(data["estimatedLLMGenerationSeconds"]),
            review_hours=float(data["estimatedLLMReviewHours"]),
            cycles=float(data["estimatedLLMCycles"]),
            preset=str(data["estimatedLLMPreset"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(_("slopcount: scc output is missing expected fields: %s") % exc) from exc
    return SccReport(
        files=sorted(files, key=lambda f: f.path),
        scc_version=SCC_VERSION,
        cocomo=cocomo,
        locomo=locomo,
    )


def collect(
    root: Path,
    *,
    personcost: float,
    overhead: float,
    scc_path: str | None = None,
    cache_dir: Path | None = None,
) -> SccReport:
    """Единственный вызов scc: манифест per-file + COCOMO + LOCOMO (спека §4.2)."""
    import json
    import subprocess
    import tempfile

    binary = ensure_binary(scc_path, cache_dir=cache_dir)
    cmd = [
        binary,
        "--format", "json2",
        "--by-file",
        "--cognitive",
        "--locomo",
        "--avg-wage", str(round(personcost * 12)),
        "--overhead", str(overhead),
        "--exclude-dir", ",".join([*SKIP_DIRS, ".git", ".hg", ".svn"]),
        str(root.resolve()),
    ]
    # cwd = нейтральный пустой каталог: гасит cwd-детект .sccconfig (спека, Прил. B)
    with tempfile.TemporaryDirectory() as neutral:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=neutral, timeout=300
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(_("slopcount: scc timed out after 300s")) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            _("slopcount: scc exited with code %d: %s") % (proc.returncode, proc.stderr.strip())
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(_("slopcount: scc output is not valid JSON")) from exc
    return parse_json2(data, root=root.resolve())
```

Добавьте `from pathlib import Path` в шапку (если ещё нет).

- [x] **Step 5: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/test_scc.py -q`
Expected: PASS. Если `test_collect_runs_real_scc` скачал scc — это первый живой прогон бутстрапа, спокойно дайте ему скачать ~7 МБ.

- [x] **Step 6: Коммит**

```bash
git add src/slopcount/scc.py tests/test_scc.py tests/fixtures/scc_slop_project.json2
git commit -m "feat: collect() — один вызов scc json2 → SccReport; запечённая фикстура"
```

---

### Task 4: Каталог `rules/languages.toml` и `load_languages()`

**Files:**
- Create: `src/slopcount/rules/languages.toml`
- Modify: `src/slopcount/rules.py`
- Test: `tests/test_rules.py`

- [x] **Step 1: Создать builtin-каталог**

Формат файла (данные — **дословно** из Приложения A спеки; имена в кавычках, если содержат `#`, пробелы или точки):

```toml
# Классификация языков scc 4.1.0 (все 366 display-имён из `scc -l`).
# kind: code | markdown | prose | data. Пользовательский --rules TOML может
# точечно переопределять записи секцией [languages] (спека §5.2).

[languages]
# --- code, tier 1+2 (67 имён; списки tier 3 добавить из Приложения A) ---
BASH = "code"
C = "code"
"C Header" = "code"
"C#" = "code"
"C++" = "code"
"C++ Header" = "code"
Dart = "code"
Go = "code"
JSX = "code"
Java = "code"
JavaScript = "code"
Kotlin = "code"
Lua = "code"
PHP = "code"
Perl = "code"
Powershell = "code"
Python = "code"
R = "code"
Ruby = "code"
Rust = "code"
SQL = "code"
Scala = "code"
Shell = "code"
Swift = "code"
TypeScript = "code"
"TypeScript Typings" = "code"
Zsh = "code"
ABAP = "code"
Apex = "code"
Assembly = "code"
Astro = "code"
Batch = "code"
Bazel = "code"
CMake = "code"
Clojure = "code"
Cuda = "code"
Cython = "code"
Dockerfile = "code"
Elixir = "code"
Erlang = "code"
"FORTRAN Legacy" = "code"
"Fortran Modern" = "code"
"Fragment Shader File" = "code"
GDScript = "code"
GLSL = "code"
Gradle = "code"
Groovy = "code"
HCL = "code"
Julia = "code"
MATLAB = "code"
Makefile = "code"
Nix = "code"
"Objective C" = "code"
OpenTofu = "code"
"PL/SQL" = "code"
SAS = "code"
Solidity = "code"
Svelte = "code"
SystemVerilog = "code"
Terraform = "code"
VHDL = "code"
Verilog = "code"
"Vertex Shader File" = "code"
"Visual Basic" = "code"
"Visual Basic for Applications" = "code"
Vue = "code"
Zig = "code"

# --- code, tier 3: 184 имени — переписать ВСЕ из Приложения A спеки ---
AL = "code"
# … (все 184; копировать списком из спеки, по одному на строку) …

# --- markdown / prose ---
Markdown = "markdown"
ReStructuredText = "markdown"
"Plain Text" = "prose"

# --- data: 112 имён — переписать ВСЕ из Приложения A спеки ---
JSON = "data"
YAML = "data"
TOML = "data"
# … (все 112) …

[extractors]
# scc Language → id, который понимает extractors.extract_comments()
Python = "python"
JavaScript = "javascript"
JSX = "javascript"
TypeScript = "typescript"
"TypeScript Typings" = "typescript"
ArkTs = "typescript"
Go = "go"
"Go+" = "go"
Rust = "rust"
C = "c"
"C Header" = "c"
"C++" = "cpp"
"C++ Header" = "cpp"
Cuda = "cpp"
Java = "java"
Ruby = "ruby"
Rakefile = "ruby"
Gemfile = "ruby"
BASH = "sh"
Shell = "sh"
Zsh = "sh"
"Korn Shell" = "sh"
"C Shell" = "sh"
Fish = "sh"
Nushell = "sh"
PKGBUILD = "sh"
PHP = "php"
"C#" = "csharp"
Swift = "swift"
Kotlin = "kotlin"
Scala = "scala"
```

Контроль полноты даёт тест из Step 2 (сумма 366). tier-3 и data-списки копируются
из спеки целиком — не выборочно.

- [x] **Step 2: Написать падающие тесты (добавить в `tests/test_rules.py`)**

```python
def test_languages_catalog_counts():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    kinds = {}
    for name, (kind, _ext) in catalog.items():
        kinds[kind] = kinds.get(kind, 0) + 1
    assert kinds == {"code": 251, "markdown": 2, "prose": 1, "data": 112}
    assert len(catalog) == 366


def test_extractor_languages_are_code():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    assert catalog["Python"] == ("code", "python")
    assert catalog["C Header"] == ("code", "c")
    assert catalog["BASH"] == ("code", "sh")
    # каждый язык с extractor-id обязан быть code
    assert all(kind == "code" for kind, ext in catalog.values() if ext)


def test_user_override_merges_and_warns(tmp_path, capsys):
    from slopcount.rules import load_languages

    rules = tmp_path / "r.toml"
    rules.write_text('[languages]\n"Zig" = "data"\n"Org" = "prose"\n"Nope" = "code"\n')
    catalog = load_languages([rules])
    assert catalog["Zig"] == ("data", None)
    assert catalog["Org"] == ("prose", None)
    assert "Nope" in capsys.readouterr().err  # неизвестное имя — предупреждение


def test_markdown_and_prose_kinds():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    assert catalog["Markdown"] == ("markdown", None)
    assert catalog["ReStructuredText"] == ("markdown", None)
    assert catalog["Plain Text"] == ("prose", None)
    assert catalog["JSON"] == ("data", None)
```

- [x] **Step 3: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_rules.py -q`
Expected: FAIL `cannot import name 'load_languages'`

- [x] **Step 4: Реализовать `load_languages` (добавить в `rules.py`)**

```python
VALID_KINDS = ("code", "markdown", "prose", "data")


def load_languages(extra_paths: list[Path] | None = None) -> dict[str, tuple[str, str | None]]:
    """builtin rules/languages.toml + точечные [languages] из пользовательских --rules.

    Возвращает {scc display name: (kind, extractor_id | None)}. Неизвестные
    имена в пользовательских файлах — предупреждение; битый TOML — RuntimeError."""
    import os
    import sys
    import tomllib

    base = resources.files("slopcount").joinpath("rules")
    path = Path(os.fspath(base / "languages.toml"))
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"slopcount: bad built-in languages.toml: {exc}") from exc

    def merge(section: dict, source: Path) -> None:
        for name, kind in section.items():
            if kind not in VALID_KINDS:
                raise RuntimeError(
                    f"slopcount: bad rules file {source}: kind must be one of {VALID_KINDS}"
                )
            if name not in languages:
                print(
                    _("slopcount: unrecognized language %s in --rules [languages]; "
                      "known names are in the built-in languages.toml") % name,
                    file=sys.stderr,
                )
            languages[name] = (kind, None)  # оверрайд стирает extractor-id

    languages: dict[str, tuple[str, str | None]] = {}
    for name, kind in data.get("languages", {}).items():
        languages[name] = (kind, None)
    for name, ext in data.get("extractors", {}).items():
        kind, _ = languages[name]
        languages[name] = (kind, ext)
    for p in extra_paths or []:
        if not p.is_file():
            continue  # load_rules уже предупредил о каждом отсутствующем файле
        try:
            user = tomllib.loads(p.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise RuntimeError(f"slopcount: bad rules file {p}: {exc}") from exc
        merge(user.get("languages", {}), p)
    return languages
```

- [x] **Step 5: Прогнать тесты (сначала добить каталог до 366 имён)**

Run: `.venv/bin/python -m pytest tests/test_rules.py -q`
Expected: PASS. Тест counts — главный контроль: он упадёт, пока tier-3 (184) и
data (112) не переписаны из Приложения A полностью.

- [x] **Step 6: Коммит**

```bash
git add src/slopcount/rules/languages.toml src/slopcount/rules.py tests/test_rules.py
git commit -m "feat: builtin-каталог 366 языков scc + пользовательский [languages]-оверрайд"
```

---

### Task 5: `ScannedFile`/`read_text` → evidence.py, новые поля Report

**Files:**
- Modify: `src/slopcount/evidence.py`, `src/slopcount/app.py`, `src/slopcount/detectors/perplexity.py`, `src/slopcount/detectors/docs_bloat.py`, `src/slopcount/detectors/env_markers.py`, `src/slopcount/detectors/phrase.py`, `src/slopcount/detectors/code_style.py`
- Modify: `tests/test_code_style.py`, `tests/test_perplexity.py`, `tests/test_i18n.py`, `tests/test_phrase.py`, `tests/test_docs_bloat.py`
- Test: `tests/test_evidence.py`

Отступление от спеки (одна строка §9): `read_text` живёт в `evidence.py`, а не в
`app.py` — детекторы импортируют его рядом с `ScannedFile`, а из `app.py` был бы
циклический импорт (app → детекторы → app). По той же строке спеки поправить
формулировку «read_text → app.py» на «read_text → evidence.py» (см. Step 5).

- [x] **Step 1: Перенести в `evidence.py` (после `Evidence`)**

```python
@dataclass(frozen=True)
class ScannedFile:
    path: str  # posix-путь относительно корня скана
    language: str | None  # id для extractors (напр. "python") или None
    kind: str  # "code" | "markdown" | "prose" | "data"
    size: int  # байты


def read_text(path: Path) -> str | None:
    """Читает файл как UTF-8; None = бинарный/нечитаемый (счётчик skip)."""
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in blob[:1024]:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
```

Скопируйте реализацию `read_text` дословно из действующего `scanner.py` (там она
уже написана; проверьте на месте — возможно, декодирование другое). В `Report`
добавить поля (в конец, до `slocomo`):

```python
    scc_version: str = ""
    complexity: int = 0  # Σ Complexity по kind=code (факт о проекте)
    cognitive_total: int = 0  # Σ Cognitive по kind=code (в JSON; ≠ входу SLOCOMO)
    files_total: int = 0  # всего файлов в манифесте scc
    cocomo: "SccCocomo | None" = None
    locomo: "SccLocomo | None" = None
```

и под `if TYPE_CHECKING:` — `from slopcount.scc import Cocomo as SccCocomo, Locomo as SccLocomo`.

- [x] **Step 2: Массовая замена импортов**

Во всех перечисленных файлах (src + tests): `from slopcount.scanner import ScannedFile`
→ `from slopcount.evidence import ScannedFile`. В `app.py` мульти-импорт
`from slopcount.scanner import ScannedFile, read_text, scan` заменить на ДВЕ строки:
`from slopcount.evidence import ScannedFile, read_text` и
`from slopcount.scanner import scan` — `scan` ещё нужен до Таска 7. Сам `scanner.py`
теряет собственные определения ScannedFile/read_text и реэкспортирует их из
evidence (`from slopcount.evidence import ScannedFile, read_text`) ради
test_scanner.py/test_env_markers.py, которые перепишутся/удалятся в Таске 7.
В `tests/test_env_markers.py` пока НЕ трогать (Task 7 перепишет его целиком).

```bash
grep -rl "from slopcount.scanner import" src tests | xargs sed -i \
  -e 's/from slopcount.scanner import ScannedFile/from slopcount.evidence import ScannedFile/'
```

- [x] **Step 3: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: FAIL только в `test_scanner.py` (он ещё импортирует Gitignore/scan —
умирает в Task 7) и, возможно, `test_env_markers.py` (импортирует scan — тоже Task 7).
Остальные PASS.

- [x] **Step 4: Коммит**

```bash
git add -A
git commit -m "refactor: ScannedFile/read_text переезживают в evidence.py; Report + scc-поля"
```

- [x] **Step 5: Синхронизировать спеку (одна строка)**

В `docs/superpowers/specs/2026-09-27-scc-delegation-design.md`, §9, таблица:
`scanner.py (130) | удалить; read_text → app.py; SKIP_DIRS → scc.py` заменить на
`scanner.py (130) | удалить; read_text + ScannedFile → evidence.py (цикл импортов); SKIP_DIRS → scc.py`.

```bash
git add docs/superpowers/specs/2026-09-27-scc-delegation-design.md
git commit -m "docs: спека — read_text живёт в evidence.py (без цикла импортов)"
```

---

### Task 6: SLOCOMO без Halstead и approximate

**Files:**
- Modify: `src/slopcount/metrics/slocomo.py`
- Test: `tests/test_slocomo.py` (переписать)

- [x] **Step 1: Переписать тесты (файл целиком)**

```python
from slopcount.app import Options
from slopcount.metrics.slocomo import compute


def test_cocomo_parody_numbers():
    res = compute(slop=10_000, prose_words=23_800, cognitive_points=100, opts=Options())
    assert abs(res.person_months - 2.4 * 10**1.05) < 1e-6
    assert abs(res.schedule_months - 2.5 * res.person_months**0.38) < 1e-6
    assert abs(res.therapists - res.person_months / res.schedule_months) < 1e-6
    assert abs(res.cost - res.person_months * 4690.50 * 2.4) < 1e-6
    # чтение: 23800/238/60*2.3 = 3.83 ч; когниция: 100*0.5/60
    assert abs(res.reading_hours - (23_800 / 238 / 60 * 2.3 + 100 * 0.5 / 60)) < 1e-6
    assert res.coffee_cups == 2
    assert not hasattr(res, "approximate")


def test_joke_conversions():
    res = compute(slop=1000, prose_words=20_000, cognitive_points=0, opts=Options())
    tokens = 20_000 * 1.3
    assert abs(res.context_windows_200k - tokens / 200_000) < 1e-9
    assert abs(res.gpu_hours - tokens / 100 / 3600) < 1e-9
    assert res.therapy_sessions == 5


def test_no_therapy_flag():
    res = compute(slop=1000, prose_words=100, cognitive_points=0, opts=Options(no_therapy=True))
    assert res.therapy_sessions == 0 and res.therapy_cost == 0.0


def test_one_million_window():
    res = compute(slop=1000, prose_words=20_000, cognitive_points=0, opts=Options())
    assert abs(res.context_windows_1m - 20_000 * 1.3 / 1_000_000) < 1e-9
```

- [x] **Step 2: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_slocomo.py -q`
Expected: FAIL (лишние/отсутствующие параметры `compute`)

- [x] **Step 3: Править `slocomo.py`**

- Удалить `halstead_secs` и `approximate` из сигнатуры `compute` и из `SlocomoResult`
  (поле `approximate: bool = True` удалить).
- Формула чтения:
  ```python
  reading = prose_words / WPM / 60 * REREAD + cognitive_points * COG_MINUTES / 60
  ```
- Комментарий-константы COG_MINUTES/WPM/REREAD/TOKENS_PER_WORD — без изменений.

- [x] **Step 4: Прогнать**

Run: `.venv/bin/python -m pytest tests/test_slocomo.py -q`
Expected: PASS

- [x] **Step 5: Коммит**

```bash
git add src/slopcount/metrics/slocomo.py tests/test_slocomo.py
git commit -m "feat!: SLOCOMO без Halstead-слагаемого и флага approximate"
```

---

### Task 7: `app.run()` на манифесте scc; удалить scanner/sloc/cognitive

**Files:**
- Modify: `src/slopcount/app.py` (переписать `run`, `Options` + `scc_path`)
- Delete: `src/slopcount/scanner.py`, `src/slopcount/metrics/sloc.py`, `src/slopcount/metrics/cognitive.py`
- Delete: `tests/test_scanner.py`, `tests/test_sloc.py`, `tests/test_cognitive.py`
- Modify: `tests/test_env_markers.py` (перестать звать `scan`)
- Modify: `tests/conftest.py` (session-фикстура scc)

- [x] **Step 1: conftest — scc-фикстура**

```python
# tests/conftest.py — добавить
import pytest


@pytest.fixture(scope="session")
def scc_ready():
    """e2e-тесты гоняют настоящий конвейер → нужен бинарник scc.
    Ленивая установка (при сети) — часть проверяемого поведения; оффлайн — skip."""
    from slopcount import scc as scc_mod

    try:
        scc_mod.ensure_binary()
        return True
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
```

- [x] **Step 2: Переписать `app.py`**

Новый `run()` целиком (импорты в шапке: убрать `scan`, добавить `from slopcount import scc`,
`from slopcount.rules import load_languages, load_rules`):

```python
def run(opts: Options) -> Report:
    root = Path(opts.paths[0])
    if len(opts.paths) > 1:
        print(
            _("slopcount: multiple paths given, scanning only the first: %s") % opts.paths[0],
            file=sys.stderr,
        )
    langmap = load_languages(opts.rules)
    manifest = scc.collect(
        root, personcost=opts.personcost, overhead=opts.overhead, scc_path=opts.scc_path
    )
    files = [
        ScannedFile(
            path=f.path,
            language=langmap.get(f.language_name, ("data", None))[1],
            kind=langmap.get(f.language_name, ("data", None))[0],
            size=f.size,
        )
        for f in manifest.files
    ]
    phrase = PhraseDetector(load_rules(opts.rules))
    docs_bloat = DocsBloatDetector()
    style_detector = CodeStyleDetector()
    pplx = None
    if opts.perplexity:
        from slopcount.detectors.perplexity import PerplexityDetector, available

        if not available():
            raise RuntimeError(
                _(
                    "slopcount: --perplexity requires extras; "
                    "pipx install 'slopcount[perplexity]' and "
                    "python -m slopcount.download_model"
                )
            )
        pplx = PerplexityDetector()
    by_path = {f.path: f for f in manifest.files}
    evidences: list[Evidence] = []
    infected: list[tuple[str, int]] = []
    sloc = 0
    skip = 0
    md_files = 0
    md_lines = 0
    comment_lines = 0
    complexity_total = 0
    cognitive_total = 0
    prose_words = 0
    cog_points = 0
    n = 0
    progressed = False
    is_stderr_tty = sys.stderr.isatty()
    total = sum(1 for f in files if f.kind in ("code", "markdown", "prose"))
    for sf in files:
        if sf.kind not in ("code", "markdown", "prose"):
            continue
        text = read_text(root / sf.path)
        if text is None:
            skip += 1
            continue
        n += 1
        if is_stderr_tty and n % 200 == 0:
            print(f"\rscanned {n}/{total} files...", end="", file=sys.stderr)
            progressed = True
        file_evidences: list[Evidence] = []
        if sf.kind == "code":
            row = by_path[sf.path]
            sloc += row.code
            comment_lines += row.comment
            complexity_total += row.complexity
            cognitive_total += row.cognitive
            style_evs = style_detector.detect(sf, text)
            evidences.extend(style_evs)
            file_evidences.extend(style_evs)
            if style_evs:  # SLOCOMO: cognitive только слоп-кода (матрица §5.3)
                cog_points += row.cognitive
        if sf.kind == "markdown":
            # числитель MD/SLOC — только .md/.markdown (калибровка 2026-09-26)
            if sf.path.lower().endswith((".md", ".markdown")):
                md_files += 1
                md_lines += by_path[sf.path].lines
            bloat = docs_bloat.detect(sf, text)
            evidences.extend(bloat.evidences)
            file_evidences.extend(bloat.evidences)
            infected.extend(bloat.infected)
            if bloat.infected:
                prose_words += int(len(text.split()) * 0.8)
        phrase_evs = phrase.detect(sf, text)
        evidences.extend(phrase_evs)
        file_evidences.extend(phrase_evs)
        if pplx is not None and sf.kind in ("markdown", "prose"):
            evidences.extend(pplx.detect(sf, text))
        prose_words += flagged_words(text, file_evidences)
    if progressed:
        print(file=sys.stderr)
    rb = repo_bloat_evidence(files, sloc)
    if rb:
        evidences.append(rb)
    evidences.extend(EnvMarkerDetector().detect(root, files, read_text))
    history_commits: int | None = None
    if opts.history:
        from slopcount.detectors.git_history import GitUnavailable
        from slopcount.detectors.git_history import detect as git_detect

        try:
            hist_evs, commits = git_detect(root, opts.history)
            evidences.extend(hist_evs)
            history_commits = commits
        except GitUnavailable:
            print(_("slopcount: git history unavailable; skipping archaeology"), file=sys.stderr)
    report = aggregate(
        evidences,
        sloc=sloc,
        infected=infected,
        skip_count=skip,
        root=str(root),
        history_commits=history_commits,
        md_files=md_files,
        md_lines=md_lines,
        comment_lines=comment_lines,
    )
    report.scc_version = manifest.scc_version
    report.complexity = complexity_total
    report.cocomo = manifest.cocomo
    report.locomo = manifest.locomo
    from slopcount.metrics.slocomo import compute as slocomo_compute

    report.slocomo = slocomo_compute(
        slop=report.slop,
        prose_words=prose_words,
        cognitive_points=cog_points,
        opts=opts,
    )
    return report
```

В `Options` добавить поле `scc_path: str | None = None`. Удалить импорты
`count_sloc_and_comments`, `approx_cognitive_complexity`, `cognitive_complexity_tspython`,
`exact_available`, `halstead_seconds`, `scan`.

- [x] **Step 3: Удалить мёртвые модули и их тесты**

```bash
git rm src/slopcount/scanner.py src/slopcount/metrics/sloc.py src/slopcount/metrics/cognitive.py \
       tests/test_scanner.py tests/test_sloc.py tests/test_cognitive.py
```

- [x] **Step 4: Переписать `tests/test_env_markers.py` без `scan`**

Заменить каждый вызов `det.detect(tmp_path, scan(tmp_path), lambda p: read_text(p))`
на явный список (детектор принимает любые kind — матрица §5.3: env ортогонален):

```python
from slopcount.evidence import ScannedFile, read_text


def _manifest(tmp_path):
    """Ручной манифест вместо удалённого scan(): все файлы, какие видит детектор."""
    out = []
    for p in sorted(tmp_path.rglob("*")):
        if p.is_file():
            out.append(ScannedFile(p.relative_to(tmp_path).as_posix(), None, "code", p.stat().st_size))
    return out


# в тестах:
evs = det.detect(tmp_path, _manifest(tmp_path), lambda q: read_text(q))
```

- [x] **Step 5: Пометить e2e-тесты фикстурой scc**

В `tests/test_e2e.py`, `tests/test_render.py`, `tests/test_cli.py` добавить
`pytestmark = pytest.mark.usefixtures("scc_ready")` после импортов
(в test_e2e `run_cli` уже есть; `import pytest` добавить при отсутствии).
`tests/test_cli.py::test_cli_runs_on_directory` и прочие, вызывающие `main()` на
директории, — тоже под этим marker'ом.

- [x] **Step 6: Прогнать всё**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (числа фикстуры slop_project не должны были сдвинуться:
SLOC=8, comment=12, md_lines=12; если что-то differs — сверить с
`tests/fixtures/scc_slop_project.json2` и разобрать расхождение, это регресс).

- [x] **Step 7: Коммит**

```bash
git add -A
git commit -m "feat!: run() на манифесте scc; удалены scanner.py, metrics/sloc.py, metrics/cognitive.py"
```

---

### Task 8: Рендер — лестница затрат, новый JSON, золотой файл

**Files:**
- Modify: `src/slopcount/render/text.py`, `src/slopcount/render/json_out.py`, `src/slopcount/cli.py` (одна строка вывода)
- Modify: `tests/test_render.py` (JSON-тесты переписать), `tests/golden/slop_project_en.txt` (перегенерировать)

- [x] **Step 1: Переписать JSON-тест (в `tests/test_render.py` заменить `test_json_output_stable_keys`)**

```python
def test_json_output_new_model():
    _code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert set(data) == {"scan", "code", "slop", "docs", "costs", "evidence_count", "verdict"}
    assert set(data["scan"]) == {"tool", "files", "skipped", "history_commits"}
    assert set(data["code"]) == {"sloc", "comment_lines", "complexity", "cognitive"}
    assert set(data["slop"]) == {"total", "infected_md_lines", "ratio", "categories"}
    assert set(data["docs"]) == {"md_files", "md_lines", "md_sloc_ratio"}
    assert set(data["costs"]) == {"cocomo", "locomo", "slocomo"}
    assert set(data["costs"]["cocomo"]) == {"cost", "schedule_months", "people"}
    assert set(data["costs"]["locomo"]) == {
        "cost", "input_tokens", "output_tokens",
        "generation_seconds", "review_hours", "cycles", "preset",
    }
    assert data["code"]["sloc"] == 8
    assert data["code"]["comment_lines"] == 12
    assert data["docs"] == {"md_files": 2, "md_lines": 12, "md_sloc_ratio": 1.5}
    assert data["slop"]["total"] == 16
    assert data["slop"]["infected_md_lines"] == 9
    assert data["scan"]["tool"].startswith("scc ")
    assert data["costs"]["locomo"]["preset"] == "medium"
    assert data["verdict"]["code"] == "RECURSION"
    json.dumps(data)
```

- [x] **Step 2: Запустить, убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_render.py -q`
Expected: FAIL (старая модель ключей)

- [x] **Step 3: Переписать `render/json_out.py` целиком**

```python
from __future__ import annotations

import json
import math

from slopcount.evidence import Category, Report
from slopcount.verdicts import verdict_for


def _r4(x: float) -> float | None:
    return None if math.isinf(x) else round(x, 4)


def render_json(report: Report) -> str:
    sc = None
    if report.slocomo is not None:
        sc = {
            "reading_hours": round(report.slocomo.reading_hours, 3),
            "person_months": round(report.slocomo.person_months, 3),
            "person_years": round(report.slocomo.person_years, 3),
            "schedule_months": round(report.slocomo.schedule_months, 3),
            "therapists": round(report.slocomo.therapists, 3),
            "cost": round(report.slocomo.cost, 2),
            "context_windows_200k": round(report.slocomo.context_windows_200k, 4),
            "context_windows_1m": round(report.slocomo.context_windows_1m, 4),
            "gpu_hours": round(report.slocomo.gpu_hours, 4),
            "coffee_cups": report.slocomo.coffee_cups,
            "coffee_cost": round(report.slocomo.coffee_cost, 2),
            "therapy_sessions": report.slocomo.therapy_sessions,
            "therapy_cost": round(report.slocomo.therapy_cost, 2),
        }
    cocomo = locomo = None
    if report.cocomo is not None:
        cocomo = {
            "cost": round(report.cocomo.cost, 2),
            "schedule_months": round(report.cocomo.schedule_months, 2),
            "people": round(report.cocomo.people, 3),
        }
    if report.locomo is not None:
        locomo = {
            "cost": round(report.locomo.cost, 2),
            "input_tokens": round(report.locomo.input_tokens, 1),
            "output_tokens": round(report.locomo.output_tokens, 1),
            "generation_seconds": round(report.locomo.generation_seconds, 1),
            "review_hours": round(report.locomo.review_hours, 2),
            "cycles": round(report.locomo.cycles, 2),
            "preset": report.locomo.preset,
        }
    v = verdict_for(report.md_sloc_ratio)
    return json.dumps(
        {
            "scan": {
                "tool": f"scc {report.scc_version}",
                "files": report.files_total,
                "skipped": report.skip_count,
                "history_commits": report.history_commits,
            },
            "code": {
                "sloc": report.sloc,
                "comment_lines": report.comment_lines,
                "complexity": report.complexity,
                "cognitive": report.cognitive_total,
            },
            "slop": {
                "total": report.slop,
                "infected_md_lines": report.infected_md_lines,
                "ratio": _r4(report.slop_ratio),
                "categories": {
                    c.value: {
                        "files": report.categories[c].files,
                        "slop_lines": report.categories[c].slop_lines,
                        "weight": report.categories[c].weight,
                        "cognitivity": report.categories[c].cognitivity,
                    }
                    for c in Category
                },
            },
            "docs": {
                "md_files": report.md_files,
                "md_lines": report.md_lines,
                "md_sloc_ratio": _r4(report.md_sloc_ratio),
            },
            "costs": {"cocomo": cocomo, "locomo": locomo, "slocomo": sc},
            "evidence_count": len(report.details),
            "verdict": {"code": v.code, "md_sloc_ratio": _r4(report.md_sloc_ratio)},
        },
        indent=2,
    )
```

Поля `report.files_total` / `report.cognitive_total` объявлены в `Report` ещё в
Task 5 и заполняются в `run()` (см. Task 8 Step 4).

- [x] **Step 4: Лестница в `render/text.py` + кли**

Добавить функцию:

```python
def render_ladder(report: Report) -> str:
    """COCOMO/LOCOMO/SLOCOMO — написать / перегенерировать / осознать (спека §7.1)."""
    lines = ["-" * 79, _("Cost Ladder (write / regenerate / comprehend)"), "-" * 79]
    if report.cocomo is not None:
        lines.append(
            f"{_('COCOMO  write it all with humans'):<41} = $ {fmt_float(report.cocomo.cost)}"
            f" ({fmt_float(report.cocomo.schedule_months)} {_('mo')})"
        )
    if report.locomo is not None:
        lines.append(
            f"{_('LOCOMO  regenerate it with an LLM'):<41} = $ {fmt_float(report.locomo.cost)}"
            f" ({fmt_float(report.locomo.generation_seconds / 3600)} h"
            f" + {fmt_float(report.locomo.review_hours)} h {_('review')})"
        )
    r = report.slocomo
    if r is not None:
        lines.append(
            f"{_('SLOCOMO become aware of the slop'):<41} = $ {fmt_float(r.cost)}"
            f" ({fmt_float(r.person_months)} {_('person-months')})"
        )
    return "\n".join(lines)
```

В `render_slocomo` удалить строку `mode = " (approximate)" …` и `{mode}`.
В `cli.py`: импортировать `render_ladder` и добавить вывод между `render_slocomo`
и `render_verdict`:

```python
        print(render_text(report))
        print(render_slocomo(report))
        print(render_ladder(report))
        print(render_verdict(report))
```

В `run()` (Task 7) рядом с `report.complexity` заполнить (поля уже объявлены в
`Report` задачей Task 5):

```python
    report.files_total = len(manifest.files)
    report.cognitive_total = cognitive_total
```

- [x] **Step 5: Перегенерировать золотой файл**

```bash
.venv/bin/slopcount --lang en tests/fixtures/slop_project > /tmp/new_golden.txt
.venv/bin/python - <<'EOF'
from pathlib import Path
old = Path("tests/golden/slop_project_en.txt").read_text()
new = Path("/tmp/new_golden.txt").read_text()
print("SLOC line old:", [l for l in old.splitlines() if "SLOC)" in l])
print("SLOC line new:", [l for l in new.splitlines() if "SLOC)" in l])
EOF
```

Сверить глазами (SLOC=8, SLOP=16 — не должны измениться), затем:

```bash
cp /tmp/new_golden.txt tests/golden/slop_project_en.txt
```

- [x] **Step 6: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (включая `test_text_renderer_golden` и новый JSON-тест)

- [x] **Step 7: Коммит**

```bash
git add -A
git commit -m "feat!: новая JSON-модель и лестница затрат; golden перегенерирован"
```

---

### Task 9: CLI `--scc-path`, версия 0.4.0, pyproject

**Files:**
- Modify: `src/slopcount/cli.py`, `src/slopcount/__init__.py`, `pyproject.toml`
- Test: `tests/test_cli.py`

- [x] **Step 1: Падающий тест (добавить в `tests/test_cli.py`)**

```python
def test_scc_path_env_exit_2(tmp_path):
    # явный несуществующий путь → RuntimeError → exit 2 с подсказкой
    code, _ = run_cli([str(tmp_path), "--scc-path", "/nonexistent/scc", "--lang", "en"])
    assert code == 2
```

и на `--scc-path` с валидным бинарником (если scc доступен):

```python
def test_scc_path_valid(tmp_path):
    import shutil

    from slopcount import scc as scc_mod

    try:
        binary = scc_mod.ensure_binary()
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
    (tmp_path / "a.py").write_text("x = 1\n")
    code, out = run_cli(
        [str(tmp_path), "--scc-path", binary, "--lang", "en"]
    )
    assert code == 0 and "SLOC" in out
```

- [x] **Step 2: Убедиться в падении**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: FAIL на `--scc-path` (no such option)

- [x] **Step 3: Реализовать**

`cli.py`, в сигнатуру `scan` (рядом с `--rules`):

```python
    scc_path: str | None = typer.Option(
        None, "--scc-path", help="Path to the scc binary (else PATH/env/download)"
    ),
```

и в конструктор `Options`: `scc_path=scc_path,`.

`src/slopcount/__init__.py`: `__version__ = "0.4.0"`.
`pyproject.toml`: `version = "0.4.0"`; удалить строки
`treesitter = ["tree-sitter>=0.22", "tree-sitter-python>=0.23"]` целиком.

- [x] **Step 4: Прогнать**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [x] **Step 5: Коммит**

```bash
git add src/slopcount/cli.py src/slopcount/__init__.py pyproject.toml tests/test_cli.py
git commit -m "feat: --scc-path; версия 0.4.0; [treesitter] extra удалён"
```

---

### Task 10: Локализация новых строк

**Files:**
- Modify: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po`
- Recompile: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo`

- [x] **Step 1: Внести записи в .po (блоком рядом с существующими, формат файла сохранить)**

```
msgid "slopcount: downloading scc %s (%d MB)…"
msgstr "slopcount: скачиваем scc %s (%d МБ)…"

msgid "slopcount: found scc %s in PATH but %s+ required; using managed copy"
msgstr "slopcount: найден scc %s в PATH, но требуется %s+; используем управляемую копию"

msgid ""
"slopcount: scc is required but could not be downloaded (%s). Install manually: %s"
msgstr ""
"slopcount: scc необходим, но скачать не удалось (%s). Установите вручную: %s"

msgid "slopcount: scc checksum mismatch for %s; install manually: %s"
msgstr "slopcount: чексумма scc не совпала (%s); установите вручную: %s"

msgid "slopcount: scc exited with code %d: %s"
msgstr "slopcount: scc завершился с кодом %d: %s"

msgid "slopcount: scc timed out after %ds"
msgstr "slopcount: превышен таймаут scc (%d с)"

msgid "slopcount: scc returned path outside scan root: %s"
msgstr "slopcount: scc вернул путь вне корня скана: %s"

msgid "slopcount: failed to execute scc binary: %s"
msgstr "slopcount: не удалось запустить бинарник scc: %s"

msgid "slopcount: scc output is not valid JSON"
msgstr "slopcount: вывод scc не является корректным JSON"

msgid "slopcount: scc output is missing expected fields: %s"
msgstr "slopcount: в выводе scc не хватает ожидаемых полей: %s"

msgid "slopcount: scc binary not found at %s"
msgstr "slopcount: бинарник scc не найден: %s"

msgid "slopcount: scc executable not found in archive %s"
msgstr "slopcount: исполняемый файл scc не найден в архиве %s"

msgid ""
"slopcount: unrecognized language %s in --rules [languages]; known names are in "
"the built-in languages.toml"
msgstr ""
"slopcount: неизвестный язык %s в --rules [languages]; известные имена — во "
"встроенном languages.toml"

msgid "Cost Ladder (write / regenerate / comprehend)"
msgstr "Лестница затрат (написать / перегенерировать / осознать)"

msgid "COCOMO  write it all with humans"
msgstr "COCOMO  написать всё это людьми"

msgid "LOCOMO  regenerate it with an LLM"
msgstr "LOCOMO  перегенерировать LLM-ом"

msgid "SLOCOMO become aware of the slop"
msgstr "SLOCOMO осознать весь слоп"

msgid "mo"
msgstr "мес"

msgid "h"
msgstr "ч"

msgid "review"
msgstr "ревью"

msgid "person-months"
msgstr "чел-мес"
```

- [x] **Step 2: Перекомпилировать и проверить drift-guard**

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
.venv/bin/python -m pytest tests/test_i18n.py -q
```

Expected: PASS (побайтовое совпадение .po/.mo — тест гарантирует).

- [x] **Step 3: Проверить ru-вывод руками**

```bash
.venv/bin/slopcount tests/fixtures/slop_project | head -40
```

Expected: «Лестница затрат…» по-русски; SLOCOMO-блок без «(approximate)».

- [x] **Step 4: Коммит**

```bash
git add src/slopcount/locale/ru/LC_MESSAGES/slopcount.po src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo
git commit -m "i18n: строки scc-бутстрапа и лестницы затрат (ru)"
```

---

### Task 11: CI-workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [x] **Step 1: Создать workflow**

```yaml
name: ci
on:
  push:
    branches: [main, slopcount-design]
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e .[dev]
      - name: Install scc 4.1.0 (pinned)
        run: |
          curl -sL https://github.com/boyter/scc/releases/download/v4.1.0/scc_Linux_x86_64.tar.gz \
            | sudo tar xz -C /usr/local/bin scc
      - run: ruff check .
      - run: ruff format --check .
      - run: python -m pytest tests/ -q
```

- [x] **Step 2: Локальная проверка синтаксиса**

Run: `.venv/bin/python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>/dev/null || python3 -c "print('yaml-module отсутствует — проверить глазами отступы')"`
Expected: либо пусто (валидно), либо явная проверка отступов глазами.

- [x] **Step 3: Коммит**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: pytest+ruff со скармливанием scc 4.1.0 в PATH"
```

---

### Task 12: Документация и финальная проверка

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [x] **Step 1: CLAUDE.md — переписать секции «Команды» и «Архитектура»**

Заменить устаревшие абзацы (сканер, extractors-инвариант остаётся, cognitive —
удалить упоминания treesitter/exact):

- В «Команды» добавить: `slopcount .` по-прежнему; проверить, что упоминаний
  `[treesitter]` и `count_sloc` не осталось.
- В «Архитектура»:
  - конвейер теперь `scc (манифест+числа) → детекторы → Evidence[] → aggregate → SLOCOMO → render`;
  - `scc.py` — резолв бинарника (ленивая загрузка, sha256), один subprocess json2,
    `SKIP_DIRS`;
  - `rules/languages.toml` — 366 языков, kind-классификация, пользовательский
    `[languages]`-оверрайд; неизвестные scc-имена → `data`;
  - `metrics/` — только `slocomo.py` (без halstead/approximate);
  - extractors.py — только для нумерации улик phrase-детектора;
  - i18n-раздел не меняется.

- [x] **Step 2: README — обновить примеры и breaking-список**

- Обновить оба примера вывода (верхний самоскан и скриншот фикстуры) реальным
  выводом `--lang en` (SLOC/вердикт могли сдвинуться на самоскане из-за
  trailing-комментариев — снять фактический вывод).
- В секцию «Совместимость CLI (0.2.0)» / добавить блок «0.4.0 — breaking»:
  новый JSON, SLOC по scc-семантике, `[treesitter]` удалён, scc обязателен
  (ленивая установка), `--scc-path`.

- [x] **Step 3: Финальный прогон**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest tests/ -q
.venv/bin/slopcount . --lang en | tail -15   # лестница в конце, без approximate
```

Expected: всё зелёное; самоскан отрабатывает, в конце — лестница затрат.

- [x] **Step 4: Коммит**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md/README под конвейер scc; breaking-список 0.4.0"
```

---

## Само-ревизия плана (выполнена)

1. **Покрытие спеки:** §3 конвейер → Task 7; §4.1 резолв → Task 2; §4.2–4.3 вызов/модель →
   Task 3; §5 каталог+оверрайд → Task 4 (матрица §5.3 реализована диспетчеризацией
   в Task 7 и описана в README — Task 12); §6 метрики → Task 7; §7.1–7.2 → Task 8;
   §8 CLI → Task 9; §9 удаления → Tasks 5–7; §10 ошибки → Tasks 2–3 (все семь строк
   таблицы имеют код-пути и тесты); §11 тесты → Tasks 1–9 + фикстура Task 3;
   §12 CI/доки → Tasks 11–12; §13 breaking → Tasks 6–9, 12.
2. **Плейсхолдеры:** единственное «дословно из Приложения A» — про 184+112 имён
   в `languages.toml` (Task 4): источник — закоммиченная спека, полнота
   контролируется тестом counts (366), это данные, не решение.
3. **Консистентность типов:** `SccFile/SccReport/Cocomo/Locomo` — Task 3, переиспользованы
   в Task 5 (Report) и Task 8 (json); `ensure_binary(explicit, cache_dir)` — одна
   сигнатура в Tasks 2–3 и conftest; `load_languages → dict[name, (kind, ext|None)]` —
   Task 4 и Task 7 сходятся; `files_total`/`cognitive_total` введены в Task 8
   (добавить в Report при его правке в Task 5 — отмечено в Task 8 Step 4).
