import filecmp
import shutil
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--check-results",
        action="store_true",
        default=False,
        help="Compare test output against expected_results/ under each test dir.",
    )
    parser.addoption(
        "--update-results",
        action="store_true",
        default=False,
        help="Write (or replace) expected_results/ under each test dir with current output.",
    )


def pytest_configure(config):
    if config.getoption("--check-results", default=False) and config.getoption("--update-results", default=False):
        pytest.exit("--check-results and --update-results are mutually exclusive", returncode=1)


@pytest.fixture
def check_results(request):
    return request.config.getoption("--check-results")


@pytest.fixture
def update_results(request):
    return request.config.getoption("--update-results")


# ---------------------------------------------------------------------------
# Helpers used by tests
# ---------------------------------------------------------------------------

def _diff_dirs(actual: Path, expected: Path) -> list[str]:
    """Return a list of human-readable difference strings between two directories."""
    diffs = []

    def _walk(a: Path, e: Path, rel: str = "") -> None:
        cmp = filecmp.dircmp(a, e)
        prefix = f"{rel}/" if rel else ""
        for name in cmp.left_only:
            diffs.append(f"  extra in output:   {prefix}{name}")
        for name in cmp.right_only:
            diffs.append(f"  missing in output: {prefix}{name}")
        for name in cmp.diff_files:
            diffs.append(f"  content differs:   {prefix}{name}")
        for sub in cmp.common_dirs:
            _walk(a / sub, e / sub, f"{prefix}{sub}")

    _walk(actual, expected)
    return diffs


def apply_results_flags(run_dir: Path, test_dir: Path, check: bool, update: bool) -> None:
    """
    Called after a successful model run.

    - update=True  →  replace <test_dir>/expected_results/ with run_dir contents.
    - check=True   →  assert run_dir matches <test_dir>/expected_results/.
    """
    expected = test_dir / "expected_results" / "output"

    if update:
        if expected.exists():
            shutil.rmtree(expected)
        shutil.copytree(run_dir / "output", expected)

    if check:
        if not expected.exists():
            pytest.fail(
                f"--check-results: no expected_results/output dir found at {expected}\n"
                "Run with --update-results first to create it."
            )
        diffs = _diff_dirs(run_dir / "output", expected)
        if diffs:
            pytest.fail(
                f"--check-results: output differs from {expected}\n"
                + "\n".join(diffs)
            )
