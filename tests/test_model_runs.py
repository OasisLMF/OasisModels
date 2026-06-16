"""
End-to-end integration tests for all model configurations in this repository.

Each test discovers an ``oasislmf.json`` config under a model's ``tests/`` directory
and runs it with ``oasislmf model run``, checking that the run completes without error.

Models that require cloud storage credentials (Azure, S3) are marked with
``@pytest.mark.cloud`` and skipped by default.  To include them, run with::

    pytest -m cloud

or to run everything::

    pytest -m ""
"""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import apply_results_flags

# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

# Models to skip, as (model_name, reason) tuples
SKIP_MODELS = [
    #("PiWindAzure", "requires Azure cloud credentials"),
    #("PiWindS3", "requires S3 cloud credentials"),
    #("PiWindPostcode/test_2", "Exception: rehashed too many times --> bug in oasislmf"),
    ("PiWindPreAnalysis", "needs access to an external API call, precisely"),
]

_SKIP_REASONS = {name: reason for name, reason in SKIP_MODELS}


def _collect_test_configs():
    """
    Walk all ``<Model>/tests/test_N/oasislmf.json`` files and yield
    ``(model_name, test_name, abs_config_path)`` triples.
    """
    for model_dir in sorted(REPO_ROOT.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("."):
            continue
        tests_dir = model_dir / "tests"
        if not tests_dir.is_dir():
            continue
        for test_dir in sorted(tests_dir.iterdir()):
            config = test_dir / "oasislmf.json"
            if config.is_file():
                yield model_dir.name, test_dir.name, config


def _param_id(model_name, test_name):
    return f"{model_name}/{test_name}"


def _build_params():
    params = []
    for model_name, test_name, config_path in _collect_test_configs():
        marks = []
        param_id = _param_id(model_name, test_name)
        skip_key = param_id if param_id in _SKIP_REASONS else model_name
        if skip_key in _SKIP_REASONS:
            marks.append(pytest.mark.cloud)
            marks.append(pytest.mark.skip(reason=_SKIP_REASONS[skip_key]))
        params.append(
            pytest.param(
                config_path,
                marks=marks,
                id=_param_id(model_name, test_name),
            )
        )
    return params


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("config_path", _build_params())
def test_model_run(config_path, tmp_path, check_results, update_results, azurite_service):
    """Run ``oasislmf model run`` for the given config and assert it succeeds."""
    run_dir = tmp_path / "run"
    cmd = [
        "oasislmf",
        "model",
        "run",
        "--config",
        str(config_path),
        "--model-run-dir",
        str(run_dir),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            f"oasislmf model run failed for {config_path}\n"
            f"--- re-run command ---\n{' '.join(cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )

    apply_results_flags(run_dir, config_path.parent, check_results, update_results)
