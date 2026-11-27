"""
Integration tests that run model test cases through the OasisPlatform API.

A minimal platform stack (``tests/compose/docker-compose.platform.yml``) is
started with testcontainers' DockerCompose for the whole session, using the
given server and worker images.  For every model selected its worker is
added from ``<Model>/docker/worker-container.yml``; models without one are
skipped.  Each worker self-registers as ``OasisLMF/<Model>/<api-version>``.
Each test case uploads the portfolio and analysis settings from
``<Model>/tests/test_N/oasislmf.json``, runs input generation + losses, and
compares the outputs against
``<Model>/tests/test_N/expected_results/output/`` (with ``--skip-results-check``
a case only has to complete without errors and produce output files).

This file is only collected when passed explicitly or when ``--platform-tests``
is set, so a plain ``pytest`` does not start containers.

Examples::

    # default set (PLATFORM_DEFAULT_TESTS: a representative subset) on the v2 API
    pytest tests/test_platform_runs.py

    # select test cases and images
    pytest tests/test_platform_runs.py --platform-tests PiWind,PiWindBI/test_1 \\
        --api-version v1 --db mysql --storage s3 \\
        --server-image coreoasis/api_server:2.5.9 --worker-image coreoasis/model_worker:2.5.9

    # every test case (respecting the skip lists)
    pytest tests/test_platform_runs.py --platform-tests all

    # the default set plus extra cases
    pytest tests/test_platform_runs.py --platform-tests default,PiWindVulnerability/test_2

    # only check that runs complete without errors (e.g. old releases against new images)
    pytest tests/test_platform_runs.py --skip-results-check

    # regenerate expected results from the platform outputs
    pytest tests/test_platform_runs.py --update-results
"""

from pathlib import Path

import pytest

from tests.conftest import apply_results_flags
from tests.model_discovery import REPO_ROOT, _SKIP_REASONS, _collect_test_configs, _param_id
from tests.platform_client import run_test_case, wait_for_api, wait_for_model
from tests.platform_stack import PlatformCompose, worker_compose_file

# Allow list run by default ('--platform-tests default', or no --platform-tests): a small set where each
# case covers a different platform path. '--platform-tests all' runs every case.
PLATFORM_DEFAULT_TESTS = [
    "PiWind/test_1",                       # base case
    "PiWindComplexModel/test_1",           # custom worker image, supplier model runner, custom gulcalc
    "PiWindPostLossAmplification/test_1",  # post loss amplification
    "DynamicFootprint/test_1",             # gulmc dynamic footprint
    "PiCyber/test_1",                      # other peril / class of business, accounts-only portfolio
    "PiCyberPreAnalysis/test_1",           # pre/post-analysis hooks, files written by the pre-analysis hook (OasisPlatform#1532)
    "PiWindDtype/test_1",                  # 64-bit dtypes (OASIS_INT / OASIS_FLOAT / OASIS_AREAPERIL_TYPE)
    "PiWindS3/test_1",                     # Test remote S3 Model data
]
SUPPLIER_ID = "OasisLMF"
ADMIN_USER = "admin"          # set in tests/compose/docker-compose.platform.yml
ADMIN_PASS = "password"

# Files in the platform output that are not compared with expected_results/output:
#   analysis_settings.json  the MDK saves it merged with model settings defaults, the platform does not
#   combine                 platform-only directory (occurrence.bin for result combining)
PLATFORM_OUTPUT_IGNORE = ("analysis_settings.json", "combine")

# Skips that only apply to platform runs (on top of model_discovery.SKIP_MODELS), by model or Model/test_N
PLATFORM_SKIP_REASONS = {
    # Failing until upstream fixes are released
    "PiWindPostcode": "no number_of_samples set in its tests: chunked v2 runs ignore model_default_samples and run "
                      "0 samples (https://github.com/OasisLMF/OasisLMF/issues/2314)",
    "PiWindComplexModel/test_2": "tests implicit model runner discovery (no model_package_dir), which the worker's "
                                 "shared docker/oasislmf.json can't express; expected results also hold no losses",
    "PiWindPostcode/test_4": "exposure pre-analysis settings file lives in the test directory, "
                             "not available to the worker",
}


# ---------------------------------------------------------------------------
# Test selection
# ---------------------------------------------------------------------------

def _select_cases(selection):
    """Return [(model_name, test_name, config_path)] for a '--platform-tests' value.

    Tokens: 'all' (every case), 'default' (PLATFORM_DEFAULT_TESTS), 'Model' or 'Model/test_N'.
    """
    tokens = [t.strip().strip("/") for t in selection.split(",") if t.strip()]
    cases = [(m, t, c) for m, t, c, _env in _collect_test_configs()]

    if "all" in tokens:
        return cases
    if "default" in tokens:
        i = tokens.index("default")
        tokens[i:i + 1] = PLATFORM_DEFAULT_TESTS

    selected = []
    for token in tokens:
        if "/" in token:
            matches = [c for c in cases if _param_id(c[0], c[1]) == token]
        else:
            matches = [c for c in cases if c[0] == token]
        if not matches:
            known = sorted({c[0] for c in cases})
            raise pytest.UsageError(
                f"--platform-tests: no test cases match '{token}'. "
                f"Use 'Model', 'Model/test_N', 'default' or 'all'. Models: {', '.join(known)}"
            )
        selected.extend(m for m in matches if m not in selected)
    return selected


def _skip_reason(model_name, test_name):
    case_id = _param_id(model_name, test_name)
    reason = (_SKIP_REASONS.get(case_id) or _SKIP_REASONS.get(model_name)
              or PLATFORM_SKIP_REASONS.get(case_id) or PLATFORM_SKIP_REASONS.get(model_name))
    if reason:
        return reason
    if not worker_compose_file(REPO_ROOT / model_name).is_file():
        return f"no {model_name}/docker/worker-container.yml, model not set up for platform tests"
    return None


def _selected_cases(config):
    return _select_cases(config.getoption("--platform-tests") or "default")


def pytest_generate_tests(metafunc):
    if "platform_case" not in metafunc.fixturenames:
        return
    params = []
    for model_name, test_name, config_path in _selected_cases(metafunc.config):
        case_id = _param_id(model_name, test_name)
        reason = _skip_reason(model_name, test_name)
        marks = [pytest.mark.skip(reason=reason)] if reason else []
        params.append(pytest.param(
            {"model_name": model_name, "test_name": test_name, "config_path": config_path},
            marks=marks, id=case_id,
        ))
    metafunc.parametrize("platform_case", params)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def platform_logs(request):
    path = Path(request.config.getoption("--platform-logs")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def platform(request, platform_logs):
    """Start the compose stack (or attach to --api-url) and yield ``(client, stack_or_None)``.

    One model worker is started for every model with a selected, non-skipped test case,
    from that model's ``docker/worker-container.yml``.
    """
    opt = request.config.getoption
    api_ver = opt("--api-version")

    if opt("--api-url"):
        client = wait_for_api(opt("--api-url"), api_ver, ADMIN_USER, ADMIN_PASS)
        yield client, None
        return

    # one worker per model with at least one runnable test case
    models = []
    for model_name, test_name, _config_path in _selected_cases(request.config):
        if not _skip_reason(model_name, test_name) and model_name not in models:
            models.append(model_name)
    if not models:
        pytest.skip("all selected platform test cases are skipped")

    stack = PlatformCompose(
        server_image=opt("--server-image"),
        worker_image=opt("--worker-image"),
        model_dirs=[REPO_ROOT / name for name in models],
        api_ver=api_ver,
        db=opt("--db"),
        storage=opt("--storage"),
        debug=opt("--platform-debug"),
        channel_layer=opt("--channel-layer"),
        work_dir=platform_logs / "config",
    )
    try:
        stack.start()
        client = wait_for_api(stack.api_url, api_ver, ADMIN_USER, ADMIN_PASS)
        yield client, stack
    finally:
        stack.dump_logs(platform_logs / "containers")
        stack.stop()


@pytest.fixture(scope="session")
def model_registry():
    """model_name -> registered model primary key, shared across the session."""
    return {}


@pytest.fixture
def model_pk(platform, platform_case, model_registry):
    """Wait for this test's model worker to self-register, return the model's primary key."""
    client, _stack = platform
    model_name = platform_case["model_name"]
    if model_name not in model_registry:
        model_registry[model_name] = wait_for_model(client, model_name, SUPPLIER_ID, client.api_ver)
    return model_registry[model_name]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.platform
def test_platform_run(platform_case, platform, model_pk, platform_logs, request):
    client, _stack = platform
    opt = request.config.getoption
    case_id = _param_id(platform_case["model_name"], platform_case["test_name"])
    run_dir = platform_logs / "runs" / client.api_ver / case_id

    analysis_id, portfolio_id = run_test_case(
        client,
        model_pk=model_pk,
        config_path=platform_case["config_path"],
        run_dir=run_dir,
        name=f"{case_id}-{client.api_ver}",
        timeout=opt("--server-timeout"),
        lookup_chunks=opt("--lookup-chunks"),
        analysis_chunks=opt("--analysis-chunks"),
    )

    # run_test_case raises if input generation or the loss run fail or time out
    assert client.analyses.status(analysis_id) == "RUN_COMPLETED"

    if opt("--skip-results-check"):
        output_files = [f for f in (run_dir / "output").rglob("*") if f.is_file()]
        assert output_files, f"{case_id}: run completed but produced no output files under {run_dir / 'output'}"
    else:
        # compare against expected results, unless regenerating them
        update = opt("--update-results")
        apply_results_flags(run_dir, platform_case["config_path"].parent, check=not update, update=update,
                            ignore=PLATFORM_OUTPUT_IGNORE)

    client.portfolios.delete(portfolio_id)
