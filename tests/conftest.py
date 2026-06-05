import difflib
import filecmp
import shutil
from pathlib import Path

import pandas as pd
import pytest

_NUMERIC_REL_TOL = 1e-4


_TABULAR_SUFFIXES = {".csv", ".parquet"}


def _tabular_diff(actual: Path, expected: Path) -> list[str] | None:
    """Compare two tabular files (CSV or parquet) with numeric tolerance via pandas.

    Returns a list of diff strings, or None to fall back to text diff.
    Empty list means equivalent within tolerance.
    """
    try:
        reader = pd.read_parquet if actual.suffix == ".parquet" else pd.read_csv
        df_a = reader(actual)
        df_e = reader(expected)
    except Exception:
        return None

    diffs = []

    if df_a.shape != df_e.shape:
        diffs.append(f"    shape: expected {df_e.shape}, got {df_a.shape}")
        return diffs

    if list(df_a.columns) != list(df_e.columns):
        diffs.append(f"    columns: expected {list(df_e.columns)}, got {list(df_a.columns)}")
        return diffs

    for col in df_e.columns:
        if pd.api.types.is_numeric_dtype(df_e[col]):
            mask = ~((df_a[col] - df_e[col]).abs() <= _NUMERIC_REL_TOL * df_e[col].abs().clip(lower=1))
        else:
            mask = df_a[col] != df_e[col]
        for idx in df_e.index[mask]:
            diffs.append(f"    row {idx + 1} [{col}]: {df_e.at[idx, col]!r} → {df_a.at[idx, col]!r}")

    return diffs


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
            if Path(name).suffix in _TABULAR_SUFFIXES:
                tab_diffs = _tabular_diff(a / name, e / name)
                if tab_diffs is None:
                    pass  # fall through to text diff below
                elif tab_diffs:
                    diffs.append(f"  content differs:   {prefix}{name}")
                    diffs.extend(tab_diffs)
                else:
                    continue  # within numeric tolerance — not a real diff
                if tab_diffs is not None:
                    continue
            diffs.append(f"  content differs:   {prefix}{name}")
            try:
                actual_lines = (a / name).read_text(errors="replace").splitlines(keepends=True)
                expected_lines = (e / name).read_text(errors="replace").splitlines(keepends=True)
                diff = difflib.unified_diff(
                    expected_lines, actual_lines,
                    fromfile=f"expected/{prefix}{name}",
                    tofile=f"actual/{prefix}{name}",
                    lineterm="",
                )
                diffs.extend(f"    {line}" for line in diff)
            except Exception:
                pass
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
