"""
Helpers for running OasisModels test cases through the OasisPlatform API
using the ``oasislmf`` APIClient.
"""

import json
import logging
import tarfile
import time
from pathlib import Path

import requests

from oasislmf.platform_api.client import APIClient

logger = logging.getLogger(__name__)

# oasislmf.json key -> APIClient.upload_inputs() argument
PORTFOLIO_FILES = {
    "oed_location_csv": "location_fp",
    "oed_accounts_csv": "accounts_fp",
    "oed_account_csv": "accounts_fp",
    "oed_info_csv": "ri_info_fp",
    "oed_scope_csv": "ri_scope_fp",
}

GENERATE_DONE = {"READY"}
GENERATE_FAILED = {"INPUTS_GENERATION_ERROR", "INPUTS_GENERATION_CANCELLED"}
RUN_DONE = {"RUN_COMPLETED"}
RUN_FAILED = {"RUN_ERROR", "RUN_CANCELLED"}


class PlatformRunError(Exception):
    pass


def wait_for_api(api_url, api_ver, username, password, timeout=300, poll=3):
    """Wait for the server healthcheck to pass, then log in and return an APIClient."""
    deadline = time.monotonic() + timeout
    last_err = None
    while True:
        try:
            r = requests.get(f"{api_url}/healthcheck/", timeout=10)
            if r.ok:
                break
            last_err = f"healthcheck status {r.status_code}"
        except requests.RequestException as e:
            last_err = e
        if time.monotonic() > deadline:
            raise PlatformRunError(f"OasisAPI at {api_url} not ready after {timeout}s: {last_err}")
        time.sleep(poll)
    return APIClient(api_url=api_url, api_ver=api_ver, username=username, password=password,
                     auth_type="simple")


def wait_for_model(client, model_id, supplier_id, version_id, timeout=300, poll=3):
    """Wait for a worker to self-register its model, return the model's primary key."""
    search = {"model_id": model_id, "supplier_id": supplier_id, "version_id": version_id}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = client.models.search(search).json()
        if found:
            return found[-1]["id"]
        time.sleep(poll)
    raise PlatformRunError(f"Model {search} was not registered within {timeout}s")


def _poll(client, analysis_id, done, failed, deadline, poll, stage, traceback_endpoint):
    while True:
        status = client.analyses.status(analysis_id)
        if status in done:
            return
        if status in failed:
            try:
                trace = traceback_endpoint.get(analysis_id).text
            except Exception:
                trace = "<no traceback available>"
            raise PlatformRunError(f"{stage} failed for analysis {analysis_id} (status={status})\n{trace}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"{stage} timed out for analysis {analysis_id} (last status={status})")
        time.sleep(poll)


def _extract(tar_path, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")


def run_test_case(client, model_pk, config_path: Path, run_dir: Path, name,
                  timeout=1800, poll=3, lookup_chunks=4, analysis_chunks=4):
    """
    Run one ``<Model>/tests/test_N`` case through the platform.

    Uploads the portfolio and analysis settings referenced by the test's
    ``oasislmf.json``, generates inputs, runs losses and downloads the
    results into ``run_dir``::

        run_dir/input_files.tar.gz, run_dir/input/...
        run_dir/output_files.tar.gz, run_dir/output/...
        run_dir/run_logs.tar.gz

    Returns ``(analysis_id, portfolio_id)``.
    """
    test_dir = config_path.parent
    config = json.loads(config_path.read_text())
    deadline = time.monotonic() + timeout

    upload_args = {arg: str(test_dir / config[key]) for key, arg in PORTFOLIO_FILES.items() if key in config}
    # A location file isn't required: some models run from accounts only (e.g. PiCyber)
    if not {"location_fp", "accounts_fp"} & upload_args.keys():
        raise PlatformRunError(f"{config_path}: neither 'oed_location_csv' nor 'oed_accounts_csv' is set")
    if "analysis_settings_json" not in config:
        raise PlatformRunError(f"{config_path}: no 'analysis_settings_json' set")

    if client.api_ver == "v2":
        # Fixed chunking so results don't depend on the platform's defaults (1 lookup / 1 analysis chunk)
        chunk_cfg = client.models.chunking_configuration.get(model_pk).json()
        chunk_cfg["lookup_strategy"] = "FIXED_CHUNKS"
        chunk_cfg["loss_strategy"] = "FIXED_CHUNKS"
        chunk_cfg["fixed_lookup_chunks"] = lookup_chunks
        chunk_cfg["fixed_analysis_chunks"] = analysis_chunks
        client.models.chunking_configuration.post(model_pk, chunk_cfg)

    portfolio_id = client.upload_inputs(portfolio_name=name, **upload_args)["id"]
    analysis_id = client.create_analysis(
        portfolio_id=portfolio_id,
        model_id=model_pk,
        analysis_name=name,
        analysis_settings_fp=str(test_dir / config["analysis_settings_json"]),
    )["id"]

    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        client.analyses.generate(analysis_id)
        _poll(client, analysis_id, GENERATE_DONE, GENERATE_FAILED, deadline, poll,
              "Input generation", client.analyses.input_generation_traceback_file)

        client.analyses.run(analysis_id)
        _poll(client, analysis_id, RUN_DONE, RUN_FAILED, deadline, poll,
              "Loss analysis", client.analyses.run_traceback_file)
    except TimeoutError:
        for cancel in (client.analyses.cancel_generate_inputs, client.analyses.cancel_analysis_run):
            try:
                cancel(analysis_id)
            except Exception:
                pass
        raise
    finally:
        # Always try to collect what exists, useful for debugging failed runs
        for endpoint, fname in [
            (client.analyses.input_file, "input_files.tar.gz"),
            (client.analyses.output_file, "output_files.tar.gz"),
            (client.analyses.run_log_file, "run_logs.tar.gz"),
        ]:
            try:
                endpoint.download(analysis_id, str(run_dir / fname))
            except Exception:
                pass

    _extract(run_dir / "input_files.tar.gz", run_dir / "input")
    _extract(run_dir / "output_files.tar.gz", run_dir)
    return analysis_id, portfolio_id
