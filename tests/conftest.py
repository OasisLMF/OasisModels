import difflib
import filecmp
import shutil
import warnings
from pathlib import Path

pytest_plugins = ["tests.azurite_setup"]

import numpy as np
import pandas as pd
import pytest

_NUMERIC_REL_TOL = 1e-4
# Losses are written to 2 decimal places, so a loss on a half-cent boundary can round either
# way when the float summation order changes (e.g. between CPU types on CI runners). A value
# is within tolerance if it is within the relative tolerance OR within one cent. The epsilon
# absorbs the float error of subtracting two 2dp values (22.88 - 22.87 > 0.01 in float64).
_NUMERIC_ABS_TOL = 0.01 + 1e-9


class ResultsWithinToleranceWarning(UserWarning):
    """Output differs from expected_results byte-wise, but every value is within tolerance."""


_TABULAR_SUFFIXES = {".csv", ".parquet"}


def _tabular_diff(actual: Path, expected: Path, inexact: list[str] | None = None) -> list[str] | None:
    """Compare two tabular files (CSV or parquet) with numeric tolerance via pandas.

    Returns a list of diff strings, or None to fall back to text diff.
    Empty list means equivalent within tolerance.

    If `inexact` is given, a description of each numeric column whose values differ but are within
    tolerance is appended to it.
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
        both_na = df_a[col].isna() & df_e[col].isna()
        if pd.api.types.is_numeric_dtype(df_e[col]):
            abs_diff = (df_a[col] - df_e[col]).abs()
            tol = np.maximum(_NUMERIC_REL_TOL * df_e[col].abs().clip(lower=1), _NUMERIC_ABS_TOL)
            mask = ~(abs_diff <= tol)
            n_inexact = int(((abs_diff > 0) & ~mask & ~both_na).sum())
            if inexact is not None and n_inexact:
                inexact.append(f"{col}: {n_inexact} value(s) differ, max abs diff {abs_diff[~mask].max():.6g}")
        else:
            mask = df_a[col] != df_e[col]
        mask = mask & ~both_na
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

def _diff_dirs(actual: Path, expected: Path) -> tuple[list[str], list[str]]:
    """Compare two directories.

    Returns:
        tuple: ``(diffs, within_tolerance)``. ``diffs`` holds human-readable difference strings,
        empty if the directories match within tolerance. ``within_tolerance`` describes the files
        that are not byte-identical but whose values are all within tolerance.
    """
    diffs = []
    within_tolerance = []

    def _walk(a: Path, e: Path, rel: str = "") -> None:
        cmp = filecmp.dircmp(a, e)
        prefix = f"{rel}/" if rel else ""
        for name in cmp.left_only:
            diffs.append(f"  extra in output:   {prefix}{name}")
        for name in cmp.right_only:
            diffs.append(f"  missing in output: {prefix}{name}")
        for name in cmp.diff_files:
            if Path(name).suffix in _TABULAR_SUFFIXES:
                inexact = []
                tab_diffs = _tabular_diff(a / name, e / name, inexact)
                if tab_diffs is None:
                    pass  # fall through to text diff below
                elif tab_diffs:
                    diffs.append(f"  content differs:   {prefix}{name}")
                    diffs.extend(tab_diffs)
                else:
                    # within numeric tolerance — not a failure, but reported as a warning
                    detail = "; ".join(inexact) or "values equal, formatting differs"
                    within_tolerance.append(f"  {prefix}{name} ({detail})")
                    continue
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
    return diffs, within_tolerance


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
        diffs, within_tolerance = _diff_dirs(run_dir / "output", expected)
        if within_tolerance:
            warnings.warn(
                f"output is not byte-identical to {expected}, but is within tolerance "
                f"(rel {_NUMERIC_REL_TOL:g} or abs {_NUMERIC_ABS_TOL:.2f}):\n" + "\n".join(within_tolerance),
                ResultsWithinToleranceWarning,
            )
        if diffs:
            pytest.fail(
                f"--check-results: output differs from {expected}\n"
                + "\n".join(diffs)
            )
