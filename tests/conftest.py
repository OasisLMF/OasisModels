import difflib
import filecmp
import os
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
        both_na = df_a[col].isna() & df_e[col].isna()
        if pd.api.types.is_numeric_dtype(df_e[col]):
            mask = ~((df_a[col] - df_e[col]).abs() <= _NUMERIC_REL_TOL * df_e[col].abs().clip(lower=1))
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

    # Options for tests/test_platform_runs.py (model runs through the OasisPlatform API)
    group = parser.getgroup("platform", "OasisPlatform integration tests (test_platform_runs.py)")
    group.addoption(
        "--platform-tests", default=None,
        help="Comma separated test cases to run through the platform: 'Model', 'Model/test_N', "
             "'default' (allow list PLATFORM_DEFAULT_TESTS in test_platform_runs.py) or 'all'. "
             "Default: default. Setting this also enables collection of test_platform_runs.py.",
    )
    group.addoption(
        "--api-version", default=os.getenv("WORKER_API_VER", "v2"), choices=["v1", "v2"],
        help="Platform API / worker run mode. Default: v2 (env WORKER_API_VER).",
    )
    group.addoption(
        "--db", default=os.getenv("PLATFORM_DB", "postgres"), choices=["postgres", "mysql"],
        help="Database backend for the platform stack. Default: postgres (env PLATFORM_DB).",
    )
    group.addoption(
        "--storage", default=os.getenv("PLATFORM_STORAGE", "shared-fs"), choices=["shared-fs", "s3"],
        help="File storage between server and workers: a shared docker volume, or S3 emulated "
             "with moto. Default: shared-fs (env PLATFORM_STORAGE).",
    )
    group.addoption(
        "--server-image", default=os.getenv("SERVER_IMAGE", "coreoasis/api_server:latest"),
        help="Server image [name:tag]. Default: coreoasis/api_server:latest (env SERVER_IMAGE).",
    )
    group.addoption(
        "--worker-image", default=os.getenv("WORKER_IMAGE", "coreoasis/model_worker:latest"),
        help="Model worker image [name:tag]. Default: coreoasis/model_worker:latest (env WORKER_IMAGE).",
    )
    group.addoption(
        "--api-url", default=os.getenv("OASIS_API_URL"),
        help="Use an already running platform at this URL instead of starting containers. "
             "Its workers must already be registered as OasisLMF/<Model>/<api-version>.",
    )
    group.addoption(
        "--platform-debug", action="store_true", default=False,
        help="Run the platform containers with OASIS_DEBUG=1.",
    )
    group.addoption(
        "--platform-logs", default="platform-logs",
        help="Directory for container logs and downloaded results. Default: ./platform-logs",
    )
    group.addoption(
        "--server-timeout", type=int, default=int(os.getenv("SERVER_TIMEOUT", 1800)),
        help="Max seconds for a single test case (generate + run). Default: 1800.",
    )
    group.addoption(
        "--lookup-chunks", type=int, default=int(os.getenv("WORKER_LOOKUP_CHUNKS", 4)),
        help="v2 only: fixed number of lookup chunks. Default: 4 (env WORKER_LOOKUP_CHUNKS).",
    )
    group.addoption(
        "--analysis-chunks", type=int, default=int(os.getenv("WORKER_ANALYSIS_CHUNKS", 4)),
        help="v2 only: fixed number of analysis chunks. Default: 4 (env WORKER_ANALYSIS_CHUNKS).",
    )


def pytest_ignore_collect(collection_path, config):
    """Only collect test_platform_runs.py (which starts docker containers) when asked for.

    It is collected when the file is passed explicitly on the command line,
    or when --platform-tests is set; a bare ``pytest`` skips it.
    """
    if collection_path.name != "test_platform_runs.py":
        return None
    explicit = any("test_platform_runs" in str(arg) for arg in config.args)
    if explicit or config.getoption("--platform-tests") is not None:
        return None
    return True


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

def _diff_dirs(actual: Path, expected: Path, ignore=()) -> list[str]:
    """Return a list of human-readable difference strings between two directories.

    ``ignore`` is a list of file or directory names to leave out of the comparison.
    """
    diffs = []

    def _walk(a: Path, e: Path, rel: str = "") -> None:
        cmp = filecmp.dircmp(a, e, ignore=list(filecmp.DEFAULT_IGNORES) + list(ignore))
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


def apply_results_flags(run_dir: Path, test_dir: Path, check: bool, update: bool, ignore=()) -> None:
    """
    Called after a successful model run.

    - update=True  →  replace <test_dir>/expected_results/ with run_dir contents.
    - check=True   →  assert run_dir matches <test_dir>/expected_results/.

    ``ignore`` lists file or directory names (top level of output/) that are
    not compared, and on update are neither copied nor removed, so the
    existing expected versions are kept.
    """
    expected = test_dir / "expected_results" / "output"

    if update:
        if not ignore:
            if expected.exists():
                shutil.rmtree(expected)
            shutil.copytree(run_dir / "output", expected)
        else:
            expected.mkdir(parents=True, exist_ok=True)
            for old in expected.iterdir():
                if old.name not in ignore:
                    shutil.rmtree(old) if old.is_dir() else old.unlink()
            for new in (run_dir / "output").iterdir():
                if new.name not in ignore:
                    copy = shutil.copytree if new.is_dir() else shutil.copy2
                    copy(new, expected / new.name)

    if check:
        if not expected.exists():
            pytest.fail(
                f"--check-results: no expected_results/output dir found at {expected}\n"
                "Run with --update-results first to create it."
            )
        diffs = _diff_dirs(run_dir / "output", expected, ignore=ignore)
        if diffs:
            pytest.fail(
                f"--check-results: output differs from {expected}\n"
                + "\n".join(diffs)
            )
