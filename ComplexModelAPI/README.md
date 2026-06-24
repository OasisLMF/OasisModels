# ComplexModelAPI

An example Oasis model implementation demonstrating how to build a complex model wrapper for the Oasis Loss Modelling Framework (OasisLMF).

## Overview

This repository showcases how to integrate custom Ground-Up Loss (GUL) calculations into the Oasis workflow by replacing the default ktools `gulcalc` with a custom API-driven approach. The example implements an earthquake peril model supporting buildings and contents coverage.

### Key Features

- **Custom GUL Calculation**: Implements a custom API hook to generate losses instead of using the default ktools gulcalc
- **Complex Model Integration**: Demonstrates how to override the model execution runner with custom logic
- **API-driven Architecture**: Shows a pattern where model calculations can be delegated to external APIs

## Package Structure

```
ComplexModelAPI/
├── complex_model_wrapper/          # Main model implementation
│   ├── ComplexAPIKeysLookup.py     # Keys lookup extending OasisBaseKeysLookup
│   ├── ComplexAPIModelExample_gulcalc.py  # Custom GUL calculation (CLI entry point)
│   └── api_hook.py                 # API implementation for loss generation
├── src/model_execution_worker/     # Model execution overrides
│   └── supplier_model_runner.py    # Custom runner replacing default ktools
├── keys_data/                      # Model keys and versioning
│   └── ModelVersion.csv
├── model_data/                     # Event data (events, occurrences, return periods)
├── meta-data/
│   └── model_settings.json         # Model configuration
└── tests/                          # Test cases
    └── test_1/                     # Example test with UK exposure data
```

## Dependencies

This package requires the following:

- **Python 3.x**
- **oasislmf** - Oasis Loss Modelling Framework (must be installed prior to this package)
- **pandas** - Data manipulation
- **numpy** - Numerical operations

The `oasislmf` package and its dependencies should be installed before installing this package.

## Installation

### Prerequisites

Ensure you have the OasisLMF package installed:

```bash
pip install oasislmf
```

### Installing the Package

Clone the repository and install in development mode:

```bash
cd ComplexModelAPI
pip install -e .
```

Or for a standard installation:

```bash
pip install .
```

This will install the package and create the console script entry point `ComplexAPIModelExample_gulcalc`.

## Running Tests

Test cases are located in the `tests/` directory. Each test contains exposure data, configuration files, and expected outputs.

### Running test_1

Navigate to the test directory and run using the OasisLMF CLI:

```bash
cd tests/test_1
oasislmf model run --config oasislmf.json
```

See `tests/test_1/README.md` for detailed information about this test case.

## How It Works

### Workflow

1. **Keys Generation**: `ComplexAPIKeysLookup` processes location data and generates keys for each location/peril/coverage combination
2. **Custom GUL Calculation**: `ComplexAPIModelExample_gulcalc` reads event batches and complex items, then calls the API hook to generate losses
3. **API Hook**: `api_hook.run_api()` generates loss values (currently returns static values for demonstration)
4. **Binary Output**: Losses are written in ktools binary format for downstream processing
5. **Financial Module**: Standard OasisLMF financial module processes the GUL output

### Supported Perils and Coverages

- **Peril**: Earthquake (QEQ)
- **Coverages**: Buildings, Contents

## Configuration

The model is configured via `oasislmf.json` files in each test directory. Key configuration options:

| Setting | Description |
|---------|-------------|
| `lookup_module_path` | Path to the keys lookup module |
| `model_data_dir` | Directory containing event/occurrence data |
| `model_package_dir` | Directory containing the custom model runner |
| `analysis_settings_json` | Analysis parameters (samples, outputs) |

## License

See LICENSE file for details.
