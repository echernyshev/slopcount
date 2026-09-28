"""Единственная точка работы с бинарником scc: резолв, ленивая установка,
вызов и разбор json2. Классификация языков здесь НЕ живёт (см. rules.py)."""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

from slopcount.i18n import _

SCC_VERSION = "4.1.0"
SCC_MIN_VERSION = (4, 1, 0)
# защитный таймаут одного прогона scc, сек (спека §4.2)
SCC_TIMEOUT = 300
_RELEASE_URL = "https://github.com/boyter/scc/releases/download/v" + SCC_VERSION

# Подсказка по ручной установке; НЕ локализуется намеренно — команды одинаковы.
_HINT = (
    "brew install scc / snap install scc / choco install scc / "
    "go install github.com/boyter/scc/v4@v4.1.0 / "
    "https://github.com/boyter/scc/releases — or pass --scc-path"
)

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
# унаследовано из удалённого scanner.py
SKIP_DIRS = [
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    ".eggs",
    ".serena",
]


def parse_version(out: str) -> tuple[int, int, int] | None:
    """'scc version 4.1.0' → (4, 1, 0); мусор → None."""
    tail = out.strip().rsplit("version", 1)[-1].strip()
    parts = tail.split(".")
    # isascii() отсекает unicode-цифры («²»), от которых int() падает с ValueError
    if len(parts) == 3 and all(p.isascii() and p.isdigit() for p in parts):
        return int(parts[0]), int(parts[1]), int(parts[2])
    return None


def _machine() -> tuple[str, str]:
    # ключи PLATFORM_ASSETS используют "windows", а sys.platform на Win — "win32"
    plat = {"win32": "windows"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if arch is None:
        raise RuntimeError(f"unsupported architecture: {machine}")
    return plat, arch


def _run_version(binary: str) -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(proc.stdout)


def _cache_dir_default() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "slopcount" / "scc"
    return Path.home() / ".cache" / "slopcount" / "scc"


def _exe_name() -> str:
    return "scc.exe" if sys.platform == "win32" else "scc"


def _download(cache_root: Path) -> Path:
    plat = _machine()
    asset, sha = PLATFORM_ASSETS[plat]
    print(_("slopcount: downloading scc %s (%d MB)…") % (SCC_VERSION, 7), file=sys.stderr)
    try:
        with urllib.request.urlopen(f"{_RELEASE_URL}/{asset}", timeout=120) as resp:
            blob = resp.read()
    # HTTPException — обрыв соединения на read() не является OSError
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError(
            _("slopcount: scc is required but could not be downloaded (%s). Install manually: %s")
            % (exc, _HINT)
        ) from exc
    if hashlib.sha256(blob).hexdigest() != sha:
        raise RuntimeError(
            _("slopcount: scc checksum mismatch for %s; install manually: %s") % (asset, _HINT)
        )
    dest_dir = cache_root / SCC_VERSION
    dest_dir.mkdir(parents=True, exist_ok=True)
    exe_name = _exe_name()
    dest = dest_dir / exe_name
    # атомарная запись: крах/конкурент не оставит в кеше обрезанный бинарник
    tmp = dest.with_name(exe_name + ".tmp")
    if asset.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
            member = next((m for m in tf.getmembers() if m.name.split("/")[-1] == exe_name), None)
            if member is None:
                raise RuntimeError(_("slopcount: scc executable not found in archive %s") % asset)
            tmp.write_bytes(tf.extractfile(member).read())  # type: ignore[union-attr]
    else:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            name = next((n for n in zf.namelist() if n.split("/")[-1] == exe_name), None)
            if name is None:
                raise RuntimeError(_("slopcount: scc executable not found in archive %s") % asset)
            tmp.write_bytes(zf.read(name))
    tmp.chmod(tmp.stat().st_mode | 0o111)
    os.replace(tmp, dest)
    return dest


def ensure_binary(explicit: str | None = None, cache_dir: Path | None = None) -> str:
    """Порядок: --scc-path > SLOPCOUNT_SCC_BIN > PATH (версия ≥ мин.) > кеш > скачивание."""
    candidates = [explicit, os.environ.get("SLOPCOUNT_SCC_BIN")]
    for c in candidates:
        if c:
            if not Path(c).is_file():
                raise RuntimeError(_("slopcount: scc binary not found at %s") % c)
            return c
    on_path = shutil.which("scc")
    if on_path:
        version = _run_version(on_path)
        if version is not None and version >= SCC_MIN_VERSION:
            return on_path
        # непарсящаяся версия → "unknown", а не пустая строка в сообщении
        found = ".".join(map(str, version)) if version else "unknown"
        print(
            _("slopcount: found scc %s in PATH but %s+ required; using managed copy")
            % (found, ".".join(map(str, SCC_MIN_VERSION))),
            file=sys.stderr,
        )
    cache_root = cache_dir or _cache_dir_default()
    cached = cache_root / SCC_VERSION / _exe_name()
    # exec-бит обязателен: битый/обрезанный кеш самолечится повторным скачиванием
    if cached.is_file() and cached.stat().st_mode & 0o111:
        return str(cached)
    return str(_download(cache_root))


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
                if loc.is_absolute():
                    try:
                        rel = loc.relative_to(root).as_posix()
                    except ValueError as exc:
                        # отдельная ветка: relative_to-ValueError — не «битые поля»,
                        # а scc вернул файл вне сканируемого root
                        raise RuntimeError(
                            _("slopcount: scc returned path outside scan root: %s") % loc
                        ) from exc
                else:
                    rel = loc.as_posix()
                files.append(
                    SccFile(
                        path=rel,
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
    binary = ensure_binary(scc_path, cache_dir=cache_dir)
    # Честная версия: фактический бинарник может отличаться от пина (напр.
    # --scc-path на scc 4.2.0) — отчёт не должен врать «4.1.0». Непарсящаяся
    # версия → "unknown" (как в предупреждении ensure_binary), а не пин.
    actual = _run_version(binary)
    actual_version = ".".join(map(str, actual)) if actual else "unknown"
    cmd = [
        binary,
        "--format",
        "json2",
        "--by-file",
        "--cognitive",
        "--locomo",
        # гасит auto-discovery конфига целиком: cwd-.sccconfig И глобальный
        # SCC_CONFIG_PATH (чужой конфиг искажает COCOMO/LOCOMO на порядки)
        "--no-config",
        "--avg-wage",
        str(round(personcost * 12)),
        "--overhead",
        str(overhead),
        "--exclude-dir",
        ",".join([*SKIP_DIRS, ".git", ".hg", ".svn"]),
        str(root.resolve()),
    ]
    # cwd = нейтральный пустой каталог — ремнём гасит cwd-детект .sccconfig
    # (спека, Прил. B); основной фикс — --no-config выше
    with tempfile.TemporaryDirectory() as neutral:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=neutral,
                timeout=SCC_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(_("slopcount: scc timed out after %ds") % SCC_TIMEOUT) from exc
        except OSError as exc:
            # бинарник исчез между резолвом и запуском и прочие exec-провалы
            raise RuntimeError(_("slopcount: failed to execute scc binary: %s") % exc) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            _("slopcount: scc exited with code %d: %s") % (proc.returncode, proc.stderr.strip())
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(_("slopcount: scc output is not valid JSON")) from exc
    rep = parse_json2(data, root=root.resolve())
    return replace(rep, scc_version=actual_version)
