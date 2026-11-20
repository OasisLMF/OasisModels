"""
Shared discovery of model test cases.

Every model in this repository may contain test cases laid out as::

    <Model>/tests/test_N/oasislmf.json
    <Model>/tests/test_N/env.json                       (optional)
    <Model>/tests/test_N/expected_results/output/...

Used by both ``test_model_runs.py`` (local MDK runs) and
``test_platform_runs.py`` (runs through the OasisPlatform API).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# List of ordered models to run after collected models
ORDERED_MODELS = [
        "PiWindDtype"
    ]

# Models to skip, as (model_name, reason) tuples
SKIP_MODELS = [
    ("PiWindPreAnalysis", "needs access to an external API call, precisely"),
    ("ComplexModelAPI", "custom gulcalc binary not installed in CI; model needs update for oasislmf 2.5.x GULMC compatibility"),
    ("UKWind", "requires large model data from S3 (run get_large_data.sh first)"),
]

_SKIP_REASONS = {name: reason for name, reason in SKIP_MODELS}

# Models whose data is served from a local Azurite container (see tests/azurite_setup.py)
AZURITE_MODELS = {"PiWindAzure"}


def _collect_test_configs():
    """
    Walk all ``<Model>/tests/test_N/oasislmf.json`` files and yield
    ``(model_name, test_name, abs_config_path, env_path_or_None)`` tuples.
    """
    model_dirs = sorted(REPO_ROOT.iterdir())
    unordered_model_dirs = []
    ordered_model_dirs = []
    for m in model_dirs:
        if not m.is_dir() or m.name.startswith("."):
            continue
        if m.name in ORDERED_MODELS:
            ordered_model_dirs.append(m)
        else:
            unordered_model_dirs.append(m)

    model_dirs = unordered_model_dirs + ordered_model_dirs

    for model_dir in model_dirs:
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
