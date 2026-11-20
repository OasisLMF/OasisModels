<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# PiCyber Pre-Analysis

A copy of the [PiCyber](../PiCyber) model with an exposure pre-analysis hook, to check that pre-analysis works for account only portfolios (no location file), as used by cyber and liability models.

The hook, `src/exposure_modification/exposure_pre_analysis_revenue.py`, multiplies each account's `AnnualRevenue` by `revenue_scale_factor` (set in `tests/test_1/exposure_pre_analysis.json`). The lookup maps `AnnualRevenue` into revenue bands, so the scaled accounts can be assigned a different area peril and vulnerability.

After a run, the modified account file is in `runs/losses-<UTC timestamp>/input/account.csv`.

## Running the model

```
cd tests/test_1
oasislmf model run --config oasislmf.json
```
