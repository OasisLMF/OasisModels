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
import json
import os

import pytest

from tests.conftest import apply_results_flags

# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

# Models to skip, as (model_name, reason) tuples
SKIP_MODELS = [
    ("PiWindAzure", "requires Azure cloud credentials"),
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
            env_file = test_dir / "env.json"
            if not env_file.is_file():
                env_file = None

            if config.is_file():
                yield model_dir.name, test_dir.name, config, env_file


def _param_id(model_name, test_name):
    return f"{model_name}/{test_name}"


def _build_params():
    params = []
    for model_name, test_name, config_path, env_path in _collect_test_configs():
        marks = []
        param_id = _param_id(model_name, test_name)
        skip_key = param_id if param_id in _SKIP_REASONS else model_name
        if skip_key in _SKIP_REASONS:
            marks.append(pytest.mark.cloud)
            marks.append(pytest.mark.skip(reason=_SKIP_REASONS[skip_key]))

        test_config = {
                "config_path": config_path,
                "env_path": env_path
                }
        params.append(
            pytest.param(
                test_config,
                marks=marks,
                id=_param_id(model_name, test_name),
            )
        )
    return params


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("test_config", _build_params())
def test_model_run(test_config, tmp_path, check_results, update_results):
    """Run ``oasislmf model run`` for the given config and assert it succeeds."""
    run_dir = tmp_path / "run"
    config_path = test_config["config_path"]
    env_path = test_config.get("env_path", None)
    cmd = [
        "oasislmf",
        "model",
        "run",
        "--config",
        str(config_path),
        "--model-run-dir",
        str(run_dir),
    ]

    new_env = None
    if env_path is not None:
        with open(env_path, 'r') as f:
            new_env = dict(os.environ, **json.load(f))

    if new_env is not None:
        clear_cmd = ["oasislmf", "clearcache"]
        proc = subprocess.Popen(
                clear_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                )
        proc.wait()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=new_env,
    )
    output_lines = []
    for line in proc.stdout:
        output_lines.append(line)
        print(line, end="", flush=True)
    proc.wait()
    output = "".join(output_lines)

    if proc.returncode != 0:
        pytest.fail(
            f"oasislmf model run failed for {config_path}\n"
            f"--- re-run command ---\n{' '.join(cmd)}\n"
            f"--- output ---\n{output}"
        )

    apply_results_flags(run_dir, config_path.parent, check_results, update_results)
