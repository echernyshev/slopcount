# tests/test_scc.py
import hashlib
import json
import stat
from pathlib import Path

import pytest

from slopcount import scc as scc_mod
from slopcount.scc import PLATFORM_ASSETS, SCC_MIN_VERSION, SCC_VERSION, parse_version


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


def _fake_scc(path: Path, version: str = "4.1.0") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    monkeypatch.delenv("SLOPCOUNT_SCC_BIN", raising=False)
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)

    def boom(url, timeout=60):
        raise OSError("no network")  # попадание в кеш не должно звать сеть

    monkeypatch.setattr(scc_mod.urllib.request, "urlopen", boom)
    assert scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache") == str(cached)


def test_env_var_nonexistent_raises(monkeypatch):
    monkeypatch.setenv("SLOPCOUNT_SCC_BIN", "/nonexistent/scc")
    with pytest.raises(RuntimeError, match="not found"):
        scc_mod.ensure_binary(None)


def test_cache_without_exec_bit_self_heals(tmp_path, monkeypatch):
    cached = tmp_path / "cache" / scc_mod.SCC_VERSION / "scc"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"truncated")  # обрезанный кеш без exec-бита
    monkeypatch.setattr(scc_mod.shutil, "which", lambda _: None)
    payload = b"HEALED-SCC-BINARY"
    fake = _FakeResponse(payload)
    real_sha = hashlib.sha256(fake.read()).hexdigest()
    fake = _FakeResponse(payload)
    plat = scc_mod._machine()
    asset = scc_mod.PLATFORM_ASSETS[plat][0]
    monkeypatch.setitem(scc_mod.PLATFORM_ASSETS, plat, (asset, real_sha))
    monkeypatch.setattr(scc_mod.urllib.request, "urlopen", lambda url, timeout=60: fake)
    got = scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")
    assert Path(got) == cached  # скачали поверх того же пути в кеше
    assert Path(got).read_bytes() == payload
    assert Path(got).stat().st_mode & stat.S_IEXEC


def test_unparseable_path_version_warns_unknown(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "scc"
    bad.write_text("#!/bin/sh\necho 'garbage'\n")
    bad.chmod(bad.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(tmp_path))
    cached = _fake_scc(tmp_path / "cache" / scc_mod.SCC_VERSION / "scc")
    got = scc_mod.ensure_binary(None, cache_dir=tmp_path / "cache")
    assert got == str(cached)
    assert "unknown" in capsys.readouterr().err


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

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        pass


def test_local_platform_asset_known():
    plat = scc_mod._machine()
    assert plat in scc_mod.PLATFORM_ASSETS


def test_machine_normalizes_platforms(monkeypatch):
    for plat_in, expected in [
        ("linux", ("linux", "amd64")),
        ("darwin", ("darwin", "arm64")),
        ("win32", ("windows", "amd64")),
    ]:
        monkeypatch.setattr(scc_mod.sys, "platform", plat_in)
        machine = {"linux": "x86_64", "darwin": "arm64", "win32": "AMD64"}[plat_in]
        import platform as platform_mod

        monkeypatch.setattr(platform_mod, "machine", lambda machine=machine: machine)
        assert scc_mod._machine() == expected


def test_machine_unknown_arch_raises(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "sparc")
    with pytest.raises(RuntimeError, match="unsupported architecture"):
        scc_mod._machine()


# --- Task 3: parse_json2 / collect -------------------------------------------------


@pytest.fixture()
def fixture_json2():
    return json.loads((Path(__file__).parent / "fixtures" / "scc_slop_project.json2").read_text())


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


def test_parse_json2_rejects_path_outside_root(fixture_json2, tmp_path):
    from slopcount.scc import parse_json2

    fixture_json2["languageSummary"][0]["Files"][0]["Location"] = "/elsewhere/CLAUDE.md"
    with pytest.raises(RuntimeError, match="outside scan root"):
        parse_json2(fixture_json2, root=tmp_path)


@pytest.fixture(scope="session")
def scc_cache_dir(tmp_path_factory):
    """Кеш scc вне сканируемых деревьев тестов; одна загрузка на сессию."""
    return tmp_path_factory.mktemp("scc-cache")


def test_collect_runs_real_scc(tmp_path, scc_cache_dir):
    """Интеграционный: настоящий бинарник. Пропуск, если scc недоступен."""
    from slopcount.scc import collect

    (tmp_path / "x.py").write_text("x = 1  # trailing\n" * 3)
    try:
        rep = collect(tmp_path, personcost=4690.50, overhead=2.4, cache_dir=scc_cache_dir)
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
    py = [f for f in rep.files if f.path.endswith("x.py")]
    assert py and py[0].code == 3  # трейлинг-комментарии = код (багфикс)


def test_collect_reports_actual_version(tmp_path):
    """K1: честная версия — манифест от бинарника 4.2.0, а не от пина 4.1.0."""
    from slopcount.scc import collect

    fixture = Path(__file__).parent / "fixtures" / "scc_slop_project.json2"
    fake = tmp_path / "scc-4.2.0"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        '    echo "scc version 4.2.0"\n'
        "else\n"
        f'    cat "{fixture}"\n'
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    empty = tmp_path / "empty"
    empty.mkdir()  # фейк возвращает манифест fixtures независимо от дерева
    rep = collect(empty, personcost=4690.50, overhead=2.4, scc_path=str(fake))
    assert rep.scc_version == "4.2.0"


def test_collect_excludes_skip_dirs(tmp_path, scc_cache_dir):
    """Интеграционный: SKIP_DIRS пробрасывается в scc — node_modules вне манифеста."""
    from slopcount.scc import collect

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text("x = 1\n")
    (tmp_path / "ok.py").write_text("y = 2\n")
    try:
        rep = collect(tmp_path, personcost=4690.50, overhead=2.4, cache_dir=scc_cache_dir)
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
    paths = {f.path for f in rep.files}
    assert not any("node_modules" in p for p in paths)
    assert "ok.py" in paths
