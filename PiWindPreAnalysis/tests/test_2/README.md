# test_2: pre-analysis output read back with the `pa_dtype` backend

Runs the model with:

- `"oed_backend_dtype": "pa_dtype"`, so ods-tools loads the OED exposure with pyarrow types;
- a pre-analysis hook that needs no external service (`src/exposure_modification/exposure_pre_analysis_tiv.py`, BuildingTIV x2);
- a pre-loss hook (`src/pre_loss/pre_loss_check_exposure.py`) that reloads the exposure saved in the run's `input/` directory.

The location file is the first 20 rows of the PiWind location file.

## What it checks

oasislmf saves the pre-analysis output as parquet (`input/location.parquet`, `input/account.parquet`). With `pa_dtype`, ods-tools dictionary-encodes the low-cardinality string columns (`PortNumber`, `CountryCode`, ...) as `pd.ArrowDtype(pa.dictionary(...))`. pandas cannot read those columns back from parquet, so the reload fails with:

```
TypeError: data type 'dictionary<values=large_string, indices=int8, ordered=0>[pyarrow]' not understood
```

Within one `oasislmf model run` the exposure is passed between steps in memory, so the saved files are never read back. The Oasis platform runs the steps as separate tasks and does read them back. The pre-loss hook reloads them from disk to cover that case.

This test fails until that is fixed (ods-tools 5.0.10, pandas 3.1.0). With `--oed-backend-dtype pd_dtype` it passes, and `expected_results/` comes from that run. The `pd_dtype` and `pa_dtype` loss outputs are expected to be identical.

## Reproducing on the command line

```
cd PiWindPreAnalysis/tests/test_2
oasislmf model run --config oasislmf.json -r /tmp/test_2            # fails in the pre-loss hook
oasislmf model run --config oasislmf.json -r /tmp/test_2_pd --oed-backend-dtype pd_dtype   # passes
python -c "import pandas as pd; pd.read_parquet('/tmp/test_2/input/location.parquet')"     # same TypeError
```
