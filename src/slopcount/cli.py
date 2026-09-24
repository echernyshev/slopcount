import argparse

from slopcount import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slopcount",
        description="Count the AI slop in a project and the cost of comprehending it.",
    )
    p.add_argument("--version", action="version", version=f"slopcount {__version__}")
    return p


def main(argv=None) -> int:
    build_parser().parse_args(argv)
    return 0
