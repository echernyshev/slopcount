from slopcount.detectors.docs_bloat import DocsBloatDetector
from slopcount.evidence import Category, ScannedFile


def make_sf(path, n_lines):
    return (
        ScannedFile(path, None, "markdown", 0),
        "\n".join(f"line {i}" for i in range(n_lines)) + "\n",
    )


def test_spec_giant_flagged():
    det = DocsBloatDetector()
    sf, text = make_sf("SPEC.md", 600)
    res = det.detect(sf, text)
    assert any(e.weight == 5 and "spec giant" in e.description for e in res.evidences)
    assert res.evidences[0].category is Category.DOCS


def test_spec_giant_infected_whole_file():
    det = DocsBloatDetector()
    sf, text = make_sf("SPEC.md", 600)
    res = det.detect(sf, text)
    # гигант заражён целиком даже без плотности улико-баллов (5/600 < 0.1)
    assert res.infected == [("SPEC.md", 600)]


def test_sparse_mid_size_file_not_infected():
    det = DocsBloatDetector()
    text = "## 🚀 Header\n" + "plain\n" * 99
    sf = ScannedFile("notes.md", None, "markdown", 0)
    res = det.detect(sf, text)
    # 100 строк, вес 2 → плотность 0.02; не гигант и не плотный — чист
    assert res.infected == []


def test_infected_file_reported_when_density_high():
    det = DocsBloatDetector()
    text = "## 🚀 Header one\n## 🎯 Header two\nplain\nplain\n"
    sf = ScannedFile("README.md", None, "markdown", 0)
    res = det.detect(sf, text)
    assert res.infected == [("README.md", 4)]


def test_small_clean_file_not_infected():
    det = DocsBloatDetector()
    sf, text = make_sf("notes.md", 3)
    res = det.detect(sf, text)
    assert res.infected == [] and res.evidences == []


def test_repo_bloat_evidence():
    from slopcount.detectors.docs_bloat import repo_bloat_evidence

    files = [ScannedFile("big.md", None, "markdown", 300 * 1024)]
    ev = repo_bloat_evidence(files, sloc=1000)
    assert ev and ev.weight == 4 and "docs bloat" in ev.description
    assert repo_bloat_evidence(files, sloc=10_000) is None  # 30 КБ/КЛОК — норм
