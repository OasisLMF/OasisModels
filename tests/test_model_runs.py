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
import json
import os

import pytest

from tests.conftest import apply_results_flags

from tests.model_discovery import _SKIP_REASONS, _collect_test_configs, _param_id


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

    output_lines = []

    if new_env is not None:
        clear_cmd = ["oasislmf", "clearcache"]
        proc = subprocess.Popen(
                clear_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                )
        for line in proc.stdout:
            output_lines.append(line)
            print(line, end="", flush=True)
        proc.wait()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=new_env,
    )
    for line in proc.stdout:
        output_lines.append(line)
        print(line, end="", flush=True)
    proc.wait()

    # reset the cache
    if new_env is not None:
        clear_cmd = ["oasislmf", "clearcache"]
        proc = subprocess.Popen(
                clear_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                )
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
