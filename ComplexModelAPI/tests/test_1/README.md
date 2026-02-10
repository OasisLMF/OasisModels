# Test 1 - UK Earthquake Exposure

This test case demonstrates running the ComplexModelAPI with a sample UK property exposure dataset.

## Overview

This test explicitly defines the package runner in the `oasislmf.json` file, which is then used to build the ktools `run_ktools.sh` script with the custom GUL calculation.

## Test Data

### Exposure Data

- **location.csv**: 64 UK properties located in the Melton Mowbray area with building and contents values
- **account.csv**: 2 policy layers with the following structure:
  - Layer 1: GBP 5M limit, 500K attachment
  - Layer 2: GBP 100M limit, 5.5M attachment

### Configuration Files

- **oasislmf.json**: Main configuration file pointing to model data and lookup modules
- **analysis_settings.json**: Analysis parameters including:
  - Model: ComplexAPI by OasisLMF
  - 10 samples per event
  - GUL and IL outputs enabled
  - Summary outputs: aalcalc, eltcalc, leccalc

## Running the Test

### Prerequisites

1. Ensure the ComplexModelAPI package is installed:

```bash
cd /path/to/ComplexModelAPI
pip install -e .
```

2. Ensure oasislmf is installed:

```bash
pip install oasislmf
```

### Execute the Test

From this directory, run:

```bash
oasislmf model run --config oasislmf.json
```

This will:
1. Generate keys for all location/peril/coverage combinations
2. Create the complex items file with model data
3. Execute the custom GUL calculation via the API hook
4. Process results through the financial module
5. Generate summary outputs (AAL, ELT, loss exceedance curves)

### Output

Results will be written to a `run/` directory (or as specified in analysis settings) containing:
- Ground-up loss (GUL) outputs
- Insured loss (IL) outputs
- Summary statistics (aalcalc, eltcalc, leccalc)

## Configuration Details

The `oasislmf.json` configuration points to:

| Setting | Value |
|---------|-------|
| Lookup module | `../../complex_model_wrapper/ComplexAPIKeysLookup.py` |
| Model data | `../../model_data/` |
| Model runner | `../../src/model_execution_worker/` |
| Keys data | `../../keys_data/` |
